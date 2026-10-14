#!/usr/bin/env python3
"""wheel_sink.py — THE ISSUE WHEEL session's sanctioned write channel into ~/.claude (GH #4767).

A headless `claude -p` session cannot write under a directory named `.claude` with the Write
tool, a redirect, `cp`, `mkdir`, `rm` or `sed -i`: the CLI refuses them as a "sensitive file",
whatever the grants (knowledge/oversight_install.md §1). The exceptions: the CLI's own
auto-memory dir (`~/.claude/projects/<cwd-slug>/memory/`) takes Write-tool and redirect writes
with no grant (the launcher's whole-tree `~/.claude/**` deny closes it for the wheel); a heredoc
the analyzer bails on gets through under a bare `Bash` allow (CSA), even past `//` denies; and
two commands are decided by allow rules alone: a python3 subprocess's own file I/O (#5902)
and `tee` (the launcher denies `Bash(tee:*)`, best effort). This script is the ONE python3 entry
point the wheel launcher grants by exact path (`Bash(python3 <abs>/hooks/wheel_sink.py:*)`), so a
wheel session
writes its END heartbeat, patches and plans the same way in every repo.

The allowlist is the code: no destination path argument exists at all.

  heartbeat --from F                 -> ~/.claude/schedules/heartbeats/<OVERSIGHT_JOB_LABEL>.json
  patch --name N --from F            -> ~/.claude/schedules/patches/N        (create-only)
  plan --name N --from F             -> ~/.claude/plans/wheel/<slug>/plans/N (create-only)
  patches-due [--days D]             read-only: this slug's patches older than D (>= 21) days
  reap-patches --closed N[,N] [--days D]   delete this slug's patches for CLOSED issues, older than D
  now                                read-only: UTC now, today, seconds since the wrapper's start

`--from F` must resolve inside $OVERSIGHT_RUN_SCRATCH (the run's own scratch dir), must not itself
be a symlink, must be a regular file, and is size-capped per kind. stdin is never accepted: a JSON
heredoc trips the CLI's "brace with quote" check in a repo without a bare `Bash` allow (Agency),
so the file form is the only one that works in every repo.

Env (exported by run_oversight_job.sh; missing or invalid -> exit 2, nothing written):
HOME, WHEEL_SLUG, OVERSIGHT_JOB_LABEL, OVERSIGHT_RUN_SCRATCH, OVERSIGHT_WRAPPER_START_ISO,
OVERSIGHT_CADENCE.

Output: one JSON line on stdout on success. A refusal prints `wheel_sink: refused: <reason>` on
stderr and exits 2; an I/O error exits 1. Writes are atomic (temp file in the destination dir,
then replace, or link for create-only kinds): never partial.

WHAT THIS DOES NOT DO (stated plainly). It adds no capability — python3 can already write
anywhere. It adds a sanctioned, schema-checked, MARKED channel: the heartbeat kind refuses a
session-written `status` (only the wrapper writes it), a foreign label, a wrong `started_at` or
`cadence`, and a session-invented `finished_at` (it stamps its own clock for "now"). It stamps
`written_via: "wheel_sink"` and `sink_version`. The marker proves the channel was used, not that
the content is honest: the wrapper still trusts the session's own `exit` field.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import sys
import time

SINK_VERSION = 1

HEARTBEAT_MAX = 1 * 1024 * 1024
PATCH_MAX = 50 * 1024 * 1024
PLAN_MAX = 2 * 1024 * 1024
MIN_RETENTION_DAYS = 21

_SLUG_RE = re.compile(r"^[a-z0-9]+$")
_ISO_Z_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
_PLAN_NAME_RE = re.compile(r"^wheel-[0-9]{1,7}-[0-9]{8}T[0-9]{6}Z\.md$")


class Refused(Exception):
    pass


def _refuse(msg: str) -> None:
    raise Refused(msg)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class Env:
    def __init__(self, environ: dict) -> None:
        home = environ.get("HOME", "")
        if not home or not os.path.isabs(home) or not os.path.isdir(home):
            _refuse("HOME is unset, relative or not a directory; run the sink only from a wheel session")
        # N7 (trust-architect, fix round): the helper (wheel_launch_context.py's `home-unsafe`
        # check) requires HOME == realpath(HOME); this script never had the matching check, so a
        # symlinked HOME could route every destination below through an unresolved path. Only the
        # caller that can set env vars in front of the sink command reaches this at all (CSA can;
        # Agency's "requires approval" refused it, T10a) -- this adds no NEW capability beyond
        # python3, but closes the one place this script itself trusted an unresolved path.
        if os.path.realpath(home) != home:
            _refuse(f"HOME={home!r} must equal its own realpath (matches the launcher's home-unsafe check)")
        slug = environ.get("WHEEL_SLUG", "")
        if not _SLUG_RE.match(slug):
            _refuse(f"WHEEL_SLUG={slug!r} must match ^[a-z0-9]+$; run the sink only from a wheel session")
        label = environ.get("OVERSIGHT_JOB_LABEL", "")
        if label not in (f"com.oversight.wheel.{slug}", f"manual-wheel-{slug}"):
            _refuse(f"OVERSIGHT_JOB_LABEL={label!r} is not com.oversight.wheel.{slug} or manual-wheel-{slug}")
        scratch = environ.get("OVERSIGHT_RUN_SCRATCH", "")
        # N7 (trust-architect, fix round): the .claude-component check ran on the UNRESOLVED
        # `scratch` string, before realpath -- a symlink component that only resolves to
        # something under `.claude` after following it would pass this check on the raw string
        # while genuinely landing inside `.claude` once realpath'd below. Check the realpath.
        _scratch_real = os.path.realpath(scratch) if scratch and os.path.isabs(scratch) else ""
        if (not scratch or not os.path.isabs(scratch) or not os.path.isdir(scratch)
                or not _scratch_real or ".claude" in _scratch_real.split(os.sep)):
            _refuse("OVERSIGHT_RUN_SCRATCH must be the run's existing absolute scratch dir (no .claude component)")
        start = environ.get("OVERSIGHT_WRAPPER_START_ISO", "")
        if not _ISO_Z_RE.match(start):
            _refuse(f"OVERSIGHT_WRAPPER_START_ISO={start!r} is not UTC ISO-8601 with Z")
        cadence = environ.get("OVERSIGHT_CADENCE")
        if not cadence:
            _refuse("OVERSIGHT_CADENCE is unset or empty")
        self.home = home
        self.slug = slug
        self.label = label
        self.scratch = os.path.realpath(scratch)
        self.start_iso = start
        self.cadence = cadence
        # The ONE data root. Every destination below is derived from it; nothing else is.
        self.claude_root = os.path.join(home, ".claude")

    @property
    def heartbeat_path(self) -> str:
        return os.path.join(self.claude_root, "schedules", "heartbeats", f"{self.label}.json")

    @property
    def patches_dir(self) -> str:
        return os.path.join(self.claude_root, "schedules", "patches")

    @property
    def plans_dir(self) -> str:
        return os.path.join(self.claude_root, "plans", "wheel", self.slug, "plans")

    @property
    def audit_path(self) -> str:
        return os.path.join(self.claude_root, "telemetry", "wheel", self.slug, "sink_audit.jsonl")

    def patch_name_re(self) -> re.Pattern:
        return re.compile(rf"^{re.escape(self.slug)}-([0-9]{{1,7}})-[0-9]{{8}}T[0-9]{{6}}Z\.patch$")


# ---------------------------------------------------------------------------
# --from
# ---------------------------------------------------------------------------


def read_from(env: Env, src: str, cap: int) -> bytes:
    if src in ("-", "/dev/stdin") or not src:
        _refuse("--from must name a file under RUN_SCRATCH; stdin is not accepted (write the file first)")
    absolute = os.path.abspath(src)
    real = os.path.realpath(absolute)
    try:
        inside = os.path.commonpath([real, env.scratch]) == env.scratch and real != env.scratch
    except ValueError:
        inside = False
    if not inside:
        _refuse(f"--from {src!r} resolves outside RUN_SCRATCH ({env.scratch}); write the file there first")
    try:
        lst = os.lstat(absolute)
    except FileNotFoundError:
        _refuse(f"--from {src!r} does not exist")
    if stat.S_ISLNK(lst.st_mode):
        _refuse(f"--from {src!r} is a symlink; pass the real file under RUN_SCRATCH")
    if not stat.S_ISREG(lst.st_mode):
        _refuse(f"--from {src!r} is not a regular file")
    try:
        fd = os.open(absolute, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        _refuse(f"--from {src!r} could not be opened without following a symlink ({exc.strerror})")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != (lst.st_dev, lst.st_ino):
            _refuse(f"--from {src!r} changed while being opened")
        # N7 (trust-architect, fix round): O_NOFOLLOW on `absolute` only guards its LAST path
        # component -- a symlink in a PARENT directory (e.g. RUN_SCRATCH/link-dir/file, where
        # link-dir is a symlink) is followed by the kernel when resolving `absolute`, same as
        # `real`. The earlier `inside` check already confirmed `real` (the fully-resolved path)
        # sits under env.scratch; this confirms the fd actually opened IS that same resolved
        # file, not something a parent-directory symlink silently substituted between the
        # `os.path.realpath` call above and this `os.open`.
        try:
            real_st = os.stat(real)
        except OSError:
            _refuse(f"--from {src!r} could not be re-verified against its resolved path")
        if (real_st.st_dev, real_st.st_ino) != (st.st_dev, st.st_ino):
            _refuse(f"--from {src!r} resolved to a different file than the one opened "
                    "(a parent-directory symlink may have changed)")
        if st.st_size > cap:
            _refuse(f"--from {src!r} is {st.st_size} bytes; the cap for this kind is {cap}")
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                _refuse(f"--from {src!r} exceeds the {cap}-byte cap for this kind")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _tmp_path(dest: str) -> str:
    d, base = os.path.split(dest)
    return os.path.join(d, f".{base}.sink-tmp.{os.getpid()}.{time.monotonic_ns()}")


def _write_tmp(dest: str, payload: bytes) -> str:
    tmp = _tmp_path(dest)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        view = memoryview(payload)
        while view:
            n = os.write(fd, view)
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return tmp


def write_replace(dest: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = _write_tmp(dest, payload)
    try:
        os.replace(tmp, dest)
    except BaseException:
        _unlink_quiet(tmp)
        raise


def write_create_only(dest: str, payload: bytes) -> None:
    """Create `dest` whole or not at all; never overwrite (patches and plans are evidence)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.lexists(dest):
        _refuse(f"{dest} already exists; patches and plans are create-only (use a fresh <UTC-stamp>)")
    tmp = _write_tmp(dest, payload)
    try:
        os.link(tmp, dest)  # atomic, and fails with EEXIST if a racer created dest first
    except FileExistsError:
        _refuse(f"{dest} already exists; patches and plans are create-only (use a fresh <UTC-stamp>)")
    finally:
        _unlink_quiet(tmp)


def _unlink_quiet(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def audit(env: Env, kind: str, dest: str, nbytes: int, sha: str, **extra) -> bool:
    record = {"at": _iso(_utc_now()), "job": env.label, "kind": kind, "dest": dest, "bytes": nbytes,
              "sha256": sha, "sink_version": SINK_VERSION}
    record.update(extra)
    line = (json.dumps(record) + "\n").encode("utf-8")
    try:
        os.makedirs(os.path.dirname(env.audit_path), exist_ok=True)
        # N7 (trust-architect, fix round): a plain `open(path, "a")` follows a symlink at
        # audit_path -- O_NOFOLLOW makes the open itself fail (ELOOP) if audit_path is ever a
        # symlink, rather than silently appending through it to wherever it points.
        fd = os.open(env.audit_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def _result(kind: str, dest: str, payload: bytes, audited: bool) -> dict:
    out = {"ok": True, "kind": kind, "dest": dest, "bytes": len(payload),
           "sha256": hashlib.sha256(payload).hexdigest()}
    if not audited:
        out["audit"] = "failed"
    return out


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------


def do_heartbeat(env: Env, args: argparse.Namespace) -> dict:
    raw = read_from(env, args.src, HEARTBEAT_MAX)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        _refuse(f"heartbeat file is not valid UTF-8 JSON ({exc.__class__.__name__})")
    if not isinstance(data, dict):
        _refuse("heartbeat must be a JSON object")
    if "status" in data:
        _refuse("heartbeat must not carry a `status` key; the wrapper stamps status itself — remove it")
    for key, expected in (("job", env.label), ("started_at", env.start_iso), ("cadence", env.cadence)):
        if key not in data:
            data[key] = expected
        elif data[key] != expected:
            _refuse(f"heartbeat `{key}`={data[key]!r} differs from this run's {expected!r}; omit it or fix it")
    if "finished_at" not in data:
        _refuse('heartbeat needs `finished_at`: "now" for END, or null for an in-progress update')
    fin = data["finished_at"]
    if fin == "now":
        data["finished_at"] = _iso(_utc_now())
    elif fin is not None:
        _refuse(f'heartbeat `finished_at`={fin!r}: only "now" (the sink stamps the time) or null is accepted')
    ex = data.get("exit")
    if "exit" not in data or not isinstance(ex, int) or isinstance(ex, bool):
        _refuse("heartbeat needs an integer `exit` (0 only if every step completed)")
    if not isinstance(data.get("summary"), str):
        _refuse("heartbeat needs a string `summary`")
    data["written_via"] = "wheel_sink"
    data["sink_version"] = SINK_VERSION
    payload = json.dumps(data).encode("utf-8")
    dest = env.heartbeat_path
    write_replace(dest, payload)
    sha = hashlib.sha256(payload).hexdigest()
    return _result("heartbeat", dest, payload, audit(env, "heartbeat", dest, len(payload), sha))


def do_patch(env: Env, args: argparse.Namespace) -> dict:
    if not env.patch_name_re().match(args.name or ""):
        _refuse(f"patch name {args.name!r} must match {env.slug}-<issue>-<YYYYMMDDTHHMMSSZ>.patch")
    payload = read_from(env, args.src, PATCH_MAX)
    dest = os.path.join(env.patches_dir, args.name)
    write_create_only(dest, payload)
    sha = hashlib.sha256(payload).hexdigest()
    return _result("patch", dest, payload, audit(env, "patch", dest, len(payload), sha))


def do_plan(env: Env, args: argparse.Namespace) -> dict:
    if not _PLAN_NAME_RE.match(args.name or ""):
        _refuse(f"plan name {args.name!r} must match wheel-<issue>-<YYYYMMDDTHHMMSSZ>.md")
    payload = read_from(env, args.src, PLAN_MAX)
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("plan file is not valid UTF-8")
    dest = os.path.join(env.plans_dir, args.name)
    write_create_only(dest, payload)
    sha = hashlib.sha256(payload).hexdigest()
    return _result("plan", dest, payload, audit(env, "plan", dest, len(payload), sha))


def _days(args: argparse.Namespace) -> int:
    d = args.days if args.days is not None else MIN_RETENTION_DAYS
    if d < MIN_RETENTION_DAYS:
        _refuse(f"--days {d} is below the {MIN_RETENTION_DAYS}-day retention floor")
    return d


def _own_old_patches(env: Env, days: int):
    """Yield (name, issue, path) for this slug's regular-file patches older than `days`."""
    pattern = env.patch_name_re()
    cutoff = time.time() - days * 86400
    try:
        names = sorted(os.listdir(env.patches_dir))
    except FileNotFoundError:
        return
    for name in names:
        m = pattern.match(name)
        if not m:
            continue
        path = os.path.join(env.patches_dir, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_mtime >= cutoff:
            continue
        yield name, int(m.group(1)), path


def do_patches_due(env: Env, args: argparse.Namespace) -> dict:
    items = list(_own_old_patches(env, _days(args)))
    return {"issues": sorted({issue for _, issue, _ in items}), "files": len(items)}


def do_reap_patches(env: Env, args: argparse.Namespace) -> dict:
    days = _days(args)
    tokens = [t.strip() for t in (args.closed or "").split(",") if t.strip()]
    if not tokens or not all(re.fullmatch(r"\d+", t) for t in tokens):
        _refuse("--closed must be a comma-separated list of CLOSED issue numbers")
    closed = {int(t) for t in tokens}
    deleted = 0
    for _, issue, path in list(_own_old_patches(env, days)):
        if issue in closed:
            os.unlink(path)
            deleted += 1
    audited = audit(env, "reap-patches", env.patches_dir, 0, "", deleted=deleted)
    out = {"ok": True, "kind": "reap-patches", "deleted": deleted}
    if not audited:
        out["audit"] = "failed"
    return out


def do_now(env: Env, args: argparse.Namespace) -> dict:
    now = _utc_now()
    start = datetime.datetime.strptime(env.start_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return {"now": _iso(now), "today": now.strftime("%Y-%m-%d"),
            "elapsed_sec": max(0, int((now - start).total_seconds()))}


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # a usage error is a refusal: exit 2, nothing written
        sys.stderr.write(f"wheel_sink: refused: {message}\n")
        sys.exit(2)


def parse(argv: list[str]) -> argparse.Namespace:
    p = _Parser(prog="wheel_sink.py", description="THE ISSUE WHEEL's sanctioned write channel (GH #4767)")
    sub = p.add_subparsers(dest="kind", required=True, parser_class=_Parser)
    hb = sub.add_parser("heartbeat")
    hb.add_argument("--from", dest="src", required=True)
    for kind in ("patch", "plan"):
        k = sub.add_parser(kind)
        k.add_argument("--name", required=True)
        k.add_argument("--from", dest="src", required=True)
    due = sub.add_parser("patches-due")
    due.add_argument("--days", type=int)
    reap = sub.add_parser("reap-patches")
    reap.add_argument("--closed", required=True)
    reap.add_argument("--days", type=int)
    sub.add_parser("now")
    return p.parse_args(argv)


HANDLERS = {
    "heartbeat": do_heartbeat,
    "patch": do_patch,
    "plan": do_plan,
    "patches-due": do_patches_due,
    "reap-patches": do_reap_patches,
    "now": do_now,
}


def main(argv: list[str] | None = None) -> int:
    args = parse(sys.argv[1:] if argv is None else argv)
    try:
        env = Env(dict(os.environ))
        out = HANDLERS[args.kind](env, args)
    except Refused as exc:
        sys.stderr.write(f"wheel_sink: refused: {exc}\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"wheel_sink: I/O error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
