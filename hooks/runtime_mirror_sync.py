#!/usr/bin/env python3
"""runtime_mirror_sync — keep the public runtime mirror current on every push.

OPERATOR DIRECTIVE (2026-08-30): every time a `git push` leaves this machine
from ANY repo, the runtime agent system (~/.claude's committed content) must
also reach its GitHub mirror. This module is the mechanical half of that
promise: posttooluse_bash.py calls `maybe_trigger(ev)` on every Bash event,
and when the event's command contains a `git push` segment it spawns
`--sync` as a DETACHED background process, so the operator's own push is
never slowed by the mirror's.

The standing-authorization scope is deliberately narrow, and — unlike a
docstring promise — it is ENFORCED by `validate_config()`: the only push
this module ever performs autonomously is `<clone_dir> -> remote_url` where
clone_dir must resolve UNDER ~/.claude/.mirror/ and remote_url must be a
well-formed https/ssh GitHub URL that also matches the clone's actual
`origin` at push time. It never pushes ~/.claude itself, never pushes a
product repo, and never force-pushes. Every git positional is passed after
`--`, and no config value may begin with `-`, so a corrupted or malicious
config cannot smuggle options into git argv; a config that fails any check
renders the whole subsystem inert (with the reason logged) rather than
running degraded.

DESIGN — deterministic export, fail-closed publish:

  1. SOURCE IS COMMITTED CONTENT ONLY. Everything is exported from
     `git archive HEAD` in ~/.claude — never the working tree, which in a
     multi-session setup holds other agents' unreviewed in-flight edits.
  2. CONFIG IS UNTRACKED (~/.claude/.mirror/config.json). The include
     manifest, the redaction replacement map, and the forbidden-pattern gate
     all live there, NOT in this file — so the exported copy of this module
     carries no operator-specific strings and is inert until an adopter
     writes their own config. No config -> every entry point no-ops.
  3. REDACT, THEN GATE, THEN PUSH — and the gate fails CLOSED. After the
     literal replacement map is applied, EVERYTHING that would publish is
     scanned for the config's forbidden regexes: the fresh export, the
     mirror-managed files, and every other path `git ls-files` says the
     clone tracks (a file left behind by a shrunken manifest, or added
     upstream on GitHub, publishes just the same). Any surviving hit aborts
     the push entirely and writes .mirror/BLOCKED.md naming the file and
     pattern. Exported `.py` files must byte-compile and `.json` files must
     parse AFTER redaction, so a replacement that breaks source can never
     publish. Files the gate cannot vouch for — binaries, files over
     MAX_TEXT_BYTES, non-UTF-8 text, symlinks — are EXCLUDED from publish
     entirely (removed from the export and logged), never published
     unscanned; a mirror-managed binary needs an explicit "<unscannable>"
     forbidden_allow entry. A change that would delete most of what was
     previously published is refused (CSA_MIRROR_ALLOW_MASS_DELETE=1
     overrides, deliberately, for a real restructuring). The mirror is a
     text mirror by construction.
  4. MIRROR-MANAGED FILES ARE NEVER OVERWRITTEN. The mirror's own
     CLAUDE.md / README.md / LICENSE / .gitignore (and any other path the
     config lists) are curated by hand at milestones; the deterministic sync
     leaves their content alone (but still scans them — they publish too).
  5. EVERY FAILURE IS SURFACED, AND SUCCESS IS VERIFIED, NEVER INFERRED.
     The clone's origin URL and branch identity are checked before any
     mutation; anything local ahead of origin/<branch> is pushed whether or
     not this run produced a new diff (so a failed push is retried, never
     erased by a later "no diff" run); after a push, origin/<branch> must
     equal HEAD or the run fails without recording state. Any non-zero
     outcome writes .mirror/last_error with the reason (cleared on the next
     success), and `--check` is a health probe: it reports the state and
     exits non-zero unless config is valid, the mirror is current, and
     nothing is blocked — a wedged mirror must never look healthy.
  6. A FAILURE NOBODY READS IS NOT SURFACED. Point 5's outputs are FILES,
     and for most of this module's life nothing read them: 9 BLOCKED events
     stood against 2 successful pushes while the mirror sat quietly stale.
     `--status` is the machine-consumable reporter that closes that. It
     answers WHICH of four states the mirror is in (OK / BLOCKED / DRIFTED /
     INERT), leads line 1 with that bare token, and returns a distinct exit
     code per state, so a watcher relays the specific failure rather than a
     flat "unhealthy". It is strictly READ-ONLY — no copy, commit, push,
     state write, log line, or network call (hence `config_status()` rather
     than `load_config()`, whose REJECTED path logs) — so running it costs
     nothing and perturbs nothing, even mid-sync. INERT is decided FIRST:
     an inert subsystem never even logs a block, it simply never runs.

  7. A GATE YOU CANNOT TRY IS A GATE YOU EDIT BLIND. `--dry-run` runs the SAME
     export -> redact -> gate stages `--sync` runs (they are shared functions,
     `_export_and_redact` / `_gate`, not a copy), but into a throwaway
     `tempfile.mkdtemp` directory, and then stops: it reports and publishes
     nothing. It writes no `last_synced_head`, takes no `sync.lock`, appends no
     `sync.log` line, writes no `BLOCKED.md`/`last_error`, and never writes to
     the clone: the temp tree is seeded from the clone's INDEX with
     `git checkout-index -a --prefix=<temp>/` (no `-u`, so not even the index's
     stat data is refreshed). The INDEX, not the working tree, because
     `--sync` first resets the clone's working tree to the index
     (`git checkout -- .`): what it gates is the index plus the fresh export,
     and a dry run that read the dirty working tree could call CLEAN what
     `--sync` would block (and miss tracked files deleted from it). Mirror-
     managed files are therefore gated exactly as `--sync` gates them. It does
     not fetch or pull, so it scans the clone as last synced. The report names
     forbidden-pattern hits by FILE and PATTERN only — never the matched text;
     replacements that landed inside quoted string literals by `file:line` +
     count — never the text or the replacement values; `include` entries
     missing from the runtime's `git ls-files`; and a `gate:` line counting the
     patterns, replacement pairs and allow entries actually in force. It NEVER
     prints an exception's repr or message — those can carry raw config bytes or
     the full unredacted text being written — only the exception TYPE. A gate
     that is not really there is an error, not a clean: `forbidden_patterns`
     missing, empty, or not a list of strings exits 1, and unknown top-level
     config keys are listed by name (a misspelled key is how a gate silently
     disappears). Its verdict (`DRY-RUN CLEAN` / `DRY-RUN BLOCKED: N hit(s)` /
     `DRY-RUN ERROR: ...`) is its exit code: 0 / 1 / 1.
     `--config PATH` points a dry run at a CANDIDATE config (validated by the
     same `validate_config`, so `clone_dir` must still resolve under
     ~/.claude/.mirror/) and is accepted ONLY together with `--dry-run`: the
     standing push authority stays bound to `.mirror/config.json` and must not
     become re-pointable. `--dry-run` is mutually exclusive with every other
     mode, and every argument problem is a usage error (exit 2) decided before
     anything runs. The dry-run path never reaches the code that publishes.

The TRIGGER degrades open (a hook must never break the agent); the SYNC
degrades closed (an uncertain export must never publish).

Standalone:  python3 runtime_mirror_sync.py --sync   (run one sync now)
             python3 runtime_mirror_sync.py --check  (health probe; exit 0 only
                     when healthy; no state writes, may append one log line)
             python3 runtime_mirror_sync.py --status (STRICTLY read-only state
                     report: OK / BLOCKED / DRIFTED / INERT as a leading token
                     on line 1, a distinct exit code per state, and no write
                     of any kind — not even a log line — so any watcher can
                     run it repeatedly, concurrently with a real sync)
             python3 runtime_mirror_sync.py --dry-run [--config PATH]
                     (export + redact + gate into a temp dir and REPORT:
                     forbidden hits by file/pattern, replacements inside quoted
                     string literals, include entries not in git ls-files;
                     publishes nothing, touches no .mirror state; exit 0 =
                     DRY-RUN CLEAN, 1 = BLOCKED/error, 2 = usage error;
                     --config is valid only with --dry-run, never with --sync)
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402

MIRROR_DIR = os.path.join(_lib.CLAUDE_DIR, ".mirror")
CONFIG_PATH = os.path.join(MIRROR_DIR, "config.json")
STATE_PATH = os.path.join(MIRROR_DIR, "last_synced_head")
LOCK_PATH = os.path.join(MIRROR_DIR, "sync.lock")
LOG_PATH = os.path.join(MIRROR_DIR, "sync.log")
BLOCKED_PATH = os.path.join(MIRROR_DIR, "BLOCKED.md")
LAST_ERROR_PATH = os.path.join(MIRROR_DIR, "last_error")

# A file larger than this cannot be vouched for by the redaction gate and is
# therefore excluded from publish entirely (see DESIGN point 3).
MAX_TEXT_BYTES = 4 * 1024 * 1024

_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_REMOTE_RE = re.compile(
    r"^(https://github\.com/[\w.-]+/[\w.-]+(\.git)?|git@github\.com:[\w.-]+/[\w.-]+(\.git)?)$"
)


def _log(msg: str) -> None:
    """Append one timestamped line to the sync log. Never raises."""
    try:
        os.makedirs(MIRROR_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")
    except Exception:
        pass


def _fail(reason: str) -> int:
    """Log a failure AND surface it durably in .mirror/last_error, so a
    wedged mirror is visible to `--check` (and any sweep reading the dir)
    instead of rotting silently. Always returns 1 for `return _fail(...)`.
    """
    _log(f"sync: FAILED — {reason}")
    try:
        os.makedirs(MIRROR_DIR, exist_ok=True)
        with open(LAST_ERROR_PATH, "w", encoding="utf-8") as fh:
            fh.write(
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {reason}\n"
            )
    except Exception:
        pass
    return 1


def _clear_failure() -> None:
    for path in (LAST_ERROR_PATH, BLOCKED_PATH):
        try:
            os.remove(path)
        except OSError:
            pass


def _rel_path_ok(entry: str) -> bool:
    """A manifest entry must be a clean, relative, in-tree path."""
    if not entry or not isinstance(entry, str):
        return False
    if entry.startswith(("-", "/", "~")):
        return False
    norm = os.path.normpath(entry)
    return not (norm.startswith("..") or os.path.isabs(norm) or norm == ".")


def validate_config(cfg: dict) -> str | None:
    """Return None when the config is safe to act on, else the reason it
    isn't. This is the enforcement of the module's standing-authorization
    scope — every value here later reaches git/shutil argv, and the config
    file is untracked and writable by any local process, so nothing in it is
    trusted until it passes.
    """
    if not isinstance(cfg, dict):
        return "config is not an object"
    for key in ("remote_url", "clone_dir", "branch", "include"):
        if not cfg.get(key):
            return f"missing required key: {key}"
    remote = str(cfg["remote_url"])
    if not _REMOTE_RE.match(remote) or "/./" in remote or "/../" in remote or remote.endswith(("/.", "/..")):
        return "remote_url is not a well-formed GitHub https/ssh URL"
    clone_dir = os.path.realpath(os.path.expanduser(str(cfg["clone_dir"])))
    mirror_root = os.path.realpath(MIRROR_DIR)
    if not clone_dir.startswith(mirror_root + os.sep):
        return "clone_dir must resolve under ~/.claude/.mirror/"
    if not _BRANCH_RE.match(str(cfg["branch"])):
        return "branch contains disallowed characters"
    if not isinstance(cfg["include"], list) or not cfg["include"]:
        return "include must be a non-empty list"
    for entry in cfg["include"]:
        if not _rel_path_ok(entry):
            return f"unsafe include entry: {entry!r}"
    for entry in cfg.get("mirror_managed", []):
        if not _rel_path_ok(entry):
            return f"unsafe mirror_managed entry: {entry!r}"
    return None


def load_config(path: str = CONFIG_PATH) -> dict | None:
    """Parse and VALIDATE the mirror config; None (=> inert) on any problem,
    with the reason logged when the file exists but fails validation.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        return None
    except Exception as exc:
        _log(f"config: unreadable ({exc!r}); subsystem inert")
        return None
    reason = validate_config(cfg) if isinstance(cfg, dict) else "not an object"
    if reason:
        _log(f"config: REJECTED ({reason}); subsystem inert")
        return None
    # Freeze the validated resolution: validate_config proved the REALPATH is
    # under ~/.claude/.mirror/, so hand every consumer that same resolved
    # path — a symlink swapped in between validation and use must not let
    # the un-resolved spelling escape the guarantee (TOCTOU).
    cfg["clone_dir"] = os.path.realpath(os.path.expanduser(str(cfg["clone_dir"])))
    return cfg


def command_has_push(command: str) -> bool:
    """True iff any git segment of the command is a `git push`.

    Reuses _lib.git_segments so this agrees with the gate chain's own
    tokenization: each returned argv is ["git", <subcommand>, ...] with ENV=
    prefixes and git global options (-C, -c k=v, ...) already stripped, so
    the verb is argv[1]. Never raises.

    Deliberately loose on the open side: a `--dry-run` push, a push that
    FAILED (the PostToolUse result is not consulted), or a false positive
    all just cost a background HEAD-unchanged no-op. Deliberately quiet on
    the closed side: git_segments' untokenizable sentinel ("\\x00...") is not
    "push", so a compound/quoted push is simply not auto-mirrored — the next
    clean push (or a manual --sync) catches the mirror up.
    """
    try:
        for seg in _lib.git_segments(command):
            if len(seg) > 1 and seg[1] == "push":
                return True
    except Exception:
        return False
    return False


def maybe_trigger(ev: dict) -> bool:
    """PostToolUse trigger: spawn a detached --sync when this event pushed.

    Returns True iff a sync process was spawned (for tests). Degrades OPEN:
    any failure is swallowed — the operator's own push already happened and
    must not be disturbed. No/invalid config -> never spawns.
    """
    try:
        if _lib.tool_name(ev) != "Bash":
            return False
        if not command_has_push(_lib.bash_command(ev)):
            return False
        cfg = load_config()
        if cfg is None:
            return False
        clone_dir = os.path.realpath(os.path.expanduser(cfg["clone_dir"]))
        where = os.path.realpath(_lib.cwd(ev) or os.getcwd())
        if where == clone_dir or where.startswith(clone_dir + os.sep):
            return False  # the mirror's own push must not re-trigger itself
        with open(os.devnull, "rb") as devnull, open(LOG_PATH, "a") as logf:
            subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--sync"],
                stdin=devnull,
                stdout=logf,
                stderr=logf,
                start_new_session=True,
            )
        return True
    except Exception:
        return False


def _run(cwd: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env
    )


def _err(proc: subprocess.CompletedProcess) -> str:
    """Both streams, because git reports some failures on stdout."""
    return (proc.stdout.strip() + " " + proc.stderr.strip()).strip()[:400]


def _is_text(data: bytes) -> bool:
    return b"\x00" not in data


def apply_replacements(
    data: str,
    replacements: list,
    log: Callable[[str], None] | None = None,
    on_apply: Callable[[int, str, str, str], None] | None = None,
) -> str:
    """Apply the config's ordered literal replacement pairs. A malformed
    entry is skipped but LOGGED — a redaction the operator wrote silently
    not happening is exactly the kind of quiet failure this module bans.

    `log` (default: the sync log) and `on_apply` exist for `--dry-run`, which
    must run this exact function without writing the sync log and needs to see
    where each pair is about to land: `on_apply(index, old, new, text)` is
    called with the text as it stands just BEFORE pair `index` is applied. With
    both left at None the behaviour is exactly what sync() has always had.
    """
    if log is None:
        log = _log
    for index, pair in enumerate(replacements):
        if isinstance(pair, list) and len(pair) == 2:
            if on_apply is not None:
                on_apply(index, pair[0], pair[1], data)
            data = data.replace(pair[0], pair[1])
        else:
            log(f"redact: malformed replacement entry skipped: {pair!r}")
    return data


def scan_forbidden(
    root: str, rel_paths: list[str], patterns: list[str], allow: dict
) -> list[tuple[str, str]]:
    """Scan would-publish files for surviving forbidden regexes.

    Returns (rel_path, pattern) violations. `allow` maps an exact rel_path to
    a list of pattern strings permitted in that one file (e.g. the LICENSE's
    copyright holder). Fail-closed: a file that cannot be read or vouched for
    (binary, oversize) is itself a violation here — callers must have
    excluded such files from publish before scanning.
    """
    compiled = [(p, re.compile(p, re.IGNORECASE)) for p in patterns]
    violations: list[tuple[str, str]] = []
    for rel in rel_paths:
        full = os.path.join(root, rel)
        try:
            with open(full, "rb") as fh:
                raw = fh.read(MAX_TEXT_BYTES + 1)
        except Exception:
            violations.append((rel, "<unreadable>"))
            continue
        if not _is_text(raw) or len(raw) > MAX_TEXT_BYTES:
            # A mirror-managed binary (a hand-curated logo, say) can't be
            # excluded from publish the way an exported one is — permit it
            # only through an explicit "<unscannable>" allow entry for that
            # exact path, so the exemption is a deliberate config decision.
            if "<unscannable>" not in set(allow.get(rel, [])):
                violations.append((rel, "<unscannable: binary or oversize>"))
            continue
        text = raw.decode("utf-8", errors="replace")
        allowed_here = set(allow.get(rel, []))
        for src, rx in compiled:
            if src in allowed_here:
                continue
            if rx.search(text):
                violations.append((rel, src))
    return violations


def _exported_files(clone_dir: str, include: list[str]) -> list[str]:
    """All regular files currently under the include paths, clone-relative,
    deduplicated (nested include entries must not double-process a file).
    """
    out: set[str] = set()
    for top in include:
        full = os.path.join(clone_dir, top)
        if os.path.isfile(full):
            out.add(top)
        elif os.path.isdir(full):
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = [d for d in dirnames if d != ".git"]
                for name in filenames:
                    out.add(
                        os.path.relpath(os.path.join(dirpath, name), clone_dir)
                    )
    return sorted(out)


def _remove_under(clone_dir: str, rel: str) -> None:
    """Delete clone_dir/rel, refusing anything that escapes clone_dir.

    The containment check realpaths only the PARENT directory — never the
    final component. Realpathing the whole path follows a symlink and would
    delete the TARGET instead of the link (and a link pointing outside the
    clone would be refused as an "escape" when deleting the link entry
    itself is exactly what's wanted).
    """
    root = os.path.realpath(clone_dir)
    candidate = os.path.join(root, rel)
    parent = os.path.realpath(os.path.dirname(candidate))
    if parent != root and not parent.startswith(root + os.sep):
        raise ValueError(f"refusing to delete outside clone: {rel!r}")
    dest = os.path.join(parent, os.path.basename(candidate))
    if os.path.islink(dest):
        try:
            os.remove(dest)
        except OSError:
            pass
    elif os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    else:
        try:
            os.remove(dest)
        except OSError:
            pass


def _present_pathspecs(clone_dir: str, include: list[str]) -> list[str]:
    """Include entries that exist in the worktree or the index right now.

    A path deleted upstream vanishes from both after its deletion has
    propagated once, and a pathspec naming it then makes `git add`/`commit`
    fatal — which would wedge every later sync (found in review, blocker 2).
    """
    keep: list[str] = []
    for top in include:
        if os.path.exists(os.path.join(clone_dir, top)):
            keep.append(top)
            continue
        tracked = _run(clone_dir, "git", "ls-files", "--", top)
        if tracked.returncode == 0 and tracked.stdout.strip():
            keep.append(top)
    return keep


def _compile_gate(clone_dir: str, rel_paths: list[str]) -> list[tuple[str, str]]:
    """Post-redaction sanity: exported .py must byte-compile, .json must
    parse. A replacement that breaks source must never publish (review
    finding 17 — the map can legitimately delete tokens mid-expression).
    """
    bad: list[tuple[str, str]] = []
    for rel in rel_paths:
        full = os.path.join(clone_dir, rel)
        try:
            if rel.endswith(".py"):
                # builtin compile(): a pure syntax check, no bytecode file.
                # (py_compile with cfile=os.devnull raises FileExistsError
                # unconditionally — CPython refuses special files there.)
                with open(full, encoding="utf-8", errors="surrogateescape") as fh:
                    compile(fh.read(), rel, "exec")
            elif rel.endswith(".json"):
                with open(full, encoding="utf-8") as fh:
                    json.load(fh)
        except Exception as exc:
            bad.append((rel, f"<post-redaction {type(exc).__name__}>"))
    return bad


def _bind_observer(
    on_apply: Callable[[str, int, str, str, str], None], rel: str
) -> Callable[[int, str, str, str], None]:
    """Close a per-file observer over `rel` for apply_replacements()."""

    def observer(index: int, old: str, new: str, text: str) -> None:
        on_apply(rel, index, old, new, text)

    return observer


def _export_and_redact(
    src: str,
    dest: str,
    include: list[str],
    managed: set[str],
    replacements: list,
    log: Callable[[str], None] | None = None,
    on_apply: Callable[[str, int, str, str, str], None] | None = None,
    safe_errors: bool = False,
) -> tuple[list[str], list[tuple[str, str]], str | None]:
    """The export + redact stages of a sync, shared by sync() and --dry-run.

    Exports HEAD's committed content for every non-managed include path into
    `dest` (sync passes the mirror clone; --dry-run passes a throwaway temp
    dir), then redacts every exported text file in place and EXCLUDES anything
    the gate cannot vouch for. `log` receives the same human-readable lines
    sync() has always logged (default: the sync log); `on_apply(rel, index,
    old, new, text)` observes each replacement as it is applied.

    Returns (publishable, excluded, failure): `excluded` is [(rel, reason)] for
    every file kept out of publish; `failure` is None on success, else the
    exact reason sync() hands to _fail() — the caller aborts on it.
    `safe_errors` (--dry-run only; default off so sync()'s reasons are
    unchanged) reports a redaction failure by exception TYPE, not repr.
    """
    if log is None:
        log = _log
    excluded: list[tuple[str, str]] = []

    # Export: for each include path, replace the mirror's copy wholesale with
    # HEAD's committed content, so upstream deletions propagate. Paths gone
    # from HEAD entirely are removed from the mirror too.
    for top in include:
        if top in managed:
            continue
        # Distinguish "absent at HEAD" (a legitimate upstream deletion, so
        # the mirror copy goes too) from "archive errored" (transient repo
        # trouble) BEFORE wiping anything — otherwise a transient error
        # right after the wipe would publish a mass deletion as success.
        exists_at_head = (
            _run(src, "git", "-C", src, "cat-file", "-e", f"HEAD:{top}").returncode
            == 0
        )
        try:
            _remove_under(dest, top)
        except ValueError as exc:
            return [], excluded, str(exc)
        if not exists_at_head:
            log(f"sync: {top} absent at HEAD; removed from mirror")
            continue
        archive = subprocess.run(
            ["git", "-C", src, "archive", "HEAD", "--", top],
            capture_output=True, timeout=120,
        )
        if archive.returncode != 0:
            return [], excluded, f"git archive failed for {top}"
        extract = subprocess.run(
            ["tar", "-x", "-C", dest], input=archive.stdout, timeout=120
        )
        if extract.returncode != 0:
            return [], excluded, f"tar extract failed for {top}"

    # Redact every exported text file; EXCLUDE from publish anything the
    # gate cannot vouch for (binary, oversize, non-UTF-8-round-trippable) —
    # published-unscanned is the one outcome this module must never allow.
    exported = [p for p in _exported_files(dest, include) if p not in managed]
    publishable: list[str] = []
    for rel in exported:
        full = os.path.join(dest, rel)
        try:
            if os.path.islink(full):
                # A symlink's target can lie outside the clone: writing the
                # redacted content back "through" it would rewrite that
                # target, and publishing the link itself publishes an
                # unscanned pointer. Excluded outright.
                _remove_under(dest, rel)
                log(f"sync: excluded from publish (symlink): {rel}")
                excluded.append((rel, "symlink"))
                continue
            with open(full, "rb") as fh:
                raw = fh.read(MAX_TEXT_BYTES + 1)
            if not _is_text(raw) or len(raw) > MAX_TEXT_BYTES:
                _remove_under(dest, rel)
                log(f"sync: excluded from publish (binary/oversize): {rel}")
                excluded.append((rel, "binary/oversize"))
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                _remove_under(dest, rel)
                log(f"sync: excluded from publish (not UTF-8): {rel}")
                excluded.append((rel, "not UTF-8"))
                continue
            observer = _bind_observer(on_apply, rel) if on_apply else None
            redacted = apply_replacements(text, replacements, log, observer)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(redacted)
            publishable.append(rel)
        except Exception as exc:  # an unredactable file must not publish
            if safe_errors:
                return [], excluded, f"redaction failed for {rel} ({_safe_exc(exc)})"
            return [], excluded, f"redaction failed for {rel}: {exc!r}"
    return publishable, excluded, None


def _tracked_paths(clone_dir: str) -> tuple[set[str], str | None]:
    """Every path `git ls-files` says the clone tracks, or (empty set, reason).

    -z: NUL-delimited, so a non-ASCII filename is not C-quoted by
    core.quotePath into a spelling lexists() can't find — that would
    silently drop exactly the tracked-outside-manifest files the gate scan
    exists to cover. Read-only (ls-files never writes the index).
    """
    tracked = _run(clone_dir, "git", "ls-files", "-z")
    if tracked.returncode != 0:
        return set(), f"git ls-files failed: {_err(tracked)}"
    return {p for p in tracked.stdout.split("\0") if p}, None


def _gate(
    root: str,
    publishable: list[str],
    tracked_paths: set[str],
    patterns: list[str],
    allow: dict,
) -> list[tuple[str, str]]:
    """The gate stage shared by sync() and --dry-run: scan EVERYTHING that
    will publish — the fresh export, the mirror-managed files, and anything
    else tracked in the clone (a file left behind by a shrunken manifest, or
    added upstream on GitHub and brought in by the pull, publishes just the
    same). Tracked paths whose worktree copy no longer exists are pending
    deletions — nothing of theirs publishes, so they are not scanned.
    Exported .py must also byte-compile and .json parse after redaction.
    Returns the (rel_path, pattern) violations; empty means the gate is clear.
    """
    scan_set = sorted(tracked_paths | set(publishable))
    scan_set = [
        rel for rel in scan_set
        if os.path.lexists(os.path.join(root, rel))
    ]
    violations = scan_forbidden(root, scan_set, patterns, allow)
    violations += _compile_gate(root, publishable)
    return violations


def sync(cfg: dict) -> int:
    """Run one full export->redact->gate->commit->push cycle. Returns 0 on
    success or benign no-op, 1 on a blocked/failed publish (surfaced via
    .mirror/last_error / BLOCKED.md, plus the log).
    """
    src = _lib.CLAUDE_DIR
    clone_dir = os.path.expanduser(cfg["clone_dir"])
    branch = cfg["branch"]
    include: list[str] = cfg["include"]
    managed = set(cfg.get("mirror_managed", []))
    replacements = cfg.get("replacements", [])
    patterns = cfg.get("forbidden_patterns", [])
    allow = cfg.get("forbidden_allow", {})

    head = _run(src, "git", "-C", src, "rev-parse", "HEAD").stdout.strip()
    if not head:
        return _fail("cannot resolve ~/.claude HEAD")
    try:
        last = open(STATE_PATH, encoding="utf-8").read().strip()
    except Exception:
        last = ""
    if head == last:
        _log(f"sync: HEAD {head[:10]} already mirrored; no-op")
        return 0

    existed = os.path.isdir(os.path.join(clone_dir, ".git"))
    if not existed:
        _log(f"sync: cloning {cfg['remote_url']} -> {clone_dir}")
        got = _run(
            MIRROR_DIR, "git", "clone", "--branch", branch, "--",
            cfg["remote_url"], clone_dir, timeout=300,
        )
        if got.returncode != 0:
            return _fail(f"clone failed: {_err(got)}")

    # Identity checks BEFORE any mutation of the clone: it must be ours
    # (origin matches config) and on the configured branch.
    origin = _run(clone_dir, "git", "remote", "get-url", "origin").stdout.strip()
    if origin != cfg["remote_url"]:
        return _fail(
            f"clone origin {origin!r} does not match config remote_url; refusing"
        )
    on_branch = _run(clone_dir, "git", "symbolic-ref", "--short", "HEAD")
    if on_branch.returncode != 0 or on_branch.stdout.strip() != branch:
        actual = on_branch.stdout.strip()
        where_desc = repr(actual) if actual else "a detached HEAD"
        return _fail(f"clone is on {where_desc}, not {branch!r}; refusing")

    if existed:
        # This clone is the module's own private, mechanical working copy —
        # no session ever edits it — so discarding tracked leftovers from a
        # prior blocked/failed run here is safe and is what keeps a
        # recoverable block from turning into a pull conflict.
        cleaned = _run(clone_dir, "git", "checkout", "-q", "--", ".")
        if cleaned.returncode != 0:
            _log(f"sync: cleanup checkout degraded: {_err(cleaned)}")
        pulled = _run(clone_dir, "git", "pull", "--ff-only", "origin", branch)
        if pulled.returncode != 0:
            return _fail(f"pull --ff-only failed (diverged?): {_err(pulled)}")

    publishable, _excluded, export_failure = _export_and_redact(
        src, clone_dir, include, managed, replacements
    )
    if export_failure is not None:
        return _fail(export_failure)

    # Gate: scan EVERYTHING that will publish — see _gate().
    tracked_paths, tracked_error = _tracked_paths(clone_dir)
    if tracked_error is not None:
        return _fail(tracked_error)
    violations = _gate(clone_dir, publishable, tracked_paths, patterns, allow)
    if violations:
        lines = [
            "# Mirror sync BLOCKED — the publish gate found problems",
            "",
            f"Source HEAD: {head}",
            "The push was withheld. Extend the replacement map in "
            "`.mirror/config.json` (or redact upstream) and re-run "
            "`python3 ~/.claude/hooks/runtime_mirror_sync.py --sync`.",
            "",
        ]
        lines += [f"- `{rel}` matched `{pat}`" for rel, pat in violations[:50]]
        try:
            with open(BLOCKED_PATH, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        except Exception:
            pass
        return _fail(f"BLOCKED — {len(violations)} gate hits; see BLOCKED.md")

    pathspecs = _present_pathspecs(clone_dir, include)
    if not pathspecs:
        return _fail("no include path exists in the mirror; manifest wrong?")
    added = _run(clone_dir, "git", "add", "-A", "--", *pathspecs)
    if added.returncode != 0:
        return _fail(f"git add failed: {_err(added)}")
    status = _run(clone_dir, "git", "status", "--porcelain", "--", *pathspecs)
    if status.returncode != 0:
        return _fail(f"git status failed: {_err(status)}")
    status_lines = [line for line in status.stdout.splitlines() if line.strip()]

    if status_lines:
        # Mass-deletion guard: a mirror update that deletes most of what was
        # previously published is far more likely to be a broken export than
        # a real upstream restructuring. Park it for a human/agent decision.
        deletions = sum(1 for line in status_lines if "D" in line[:2])
        # `git add -A` already staged the deletions, so ls-files no longer
        # counts them — the pre-deletion denominator is survivors + deleted.
        survivors = len(
            _run(clone_dir, "git", "ls-files", "-z", "--", *pathspecs)
            .stdout.split("\0")
        ) - 1
        pre_deletion_total = max(survivors, 0) + deletions
        if (
            deletions > 20
            and deletions * 2 > pre_deletion_total
            and os.environ.get("CSA_MIRROR_ALLOW_MASS_DELETE") != "1"
        ):
            return _fail(
                f"refusing to publish a mass deletion ({deletions} of "
                f"{pre_deletion_total} previously-published files); set "
                "CSA_MIRROR_ALLOW_MASS_DELETE=1 and re-run --sync if intended"
            )
        committed = _run(
            clone_dir, "git",
            "-c", "user.name=runtime-mirror-sync",
            "-c", "user.email=noreply@anthropic.com",
            "commit", "-q",
            "-m", f"sync: auto-mirror of runtime HEAD {head[:10]}",
            "--", *pathspecs,
        )
        if committed.returncode != 0:
            return _fail(f"git commit failed: {_err(committed)}")

    # Success is verified against the REMOTE, never inferred from "no local
    # diff": a prior run's committed-but-unpushed work (a failed push) makes
    # the export reproduce no new diff, and declaring victory there would
    # erase the failure while the remote still lacks the commit. Anything
    # local ahead of origin/<branch> gets pushed, diff or no diff.
    ahead = _run(
        clone_dir, "git", "rev-list", "--count", f"origin/{branch}..HEAD"
    )
    if ahead.returncode != 0:
        return _fail(f"cannot compare against origin/{branch}: {_err(ahead)}")
    if int(ahead.stdout.strip() or "0") > 0:
        pushed = _run(clone_dir, "git", "push", "origin", "--", branch, timeout=300)
        if pushed.returncode != 0:
            return _fail(f"git push failed: {_err(pushed)}")
        local = _run(clone_dir, "git", "rev-parse", "HEAD").stdout.strip()
        remote = _run(clone_dir, "git", "rev-parse", f"origin/{branch}").stdout.strip()
        if not local or local != remote:
            return _fail(
                f"push reported success but origin/{branch} != HEAD; not recording"
            )
        _log(f"sync: pushed mirror for runtime HEAD {head[:10]}")
    else:
        _log(f"sync: HEAD {head[:10]} produced no mirror diff; state advanced")
    _write_state(head)
    _clear_failure()
    return 0


def _write_state(head: str) -> None:
    try:
        os.makedirs(MIRROR_DIR, exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            fh.write(head + "\n")
    except Exception:
        pass


def _locked_sync() -> int:
    """Serialize concurrent syncs: whoever holds the flock is a LIVE process
    (the kernel releases flocks on death, so there is no stale-lock case),
    and a second invocation simply skips. The holder may have captured a HEAD
    older than what triggered the skipper, in which case the mirror stays
    that far behind until the next push (or a manual --sync) — an accepted
    lag, not silent loss: --check reports BEHIND the whole time.
    """
    cfg = load_config()
    if cfg is None:
        _log("sync: no valid config at .mirror/config.json; no-op")
        return 0
    os.makedirs(MIRROR_DIR, exist_ok=True)
    lock = open(LOCK_PATH, "a+")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _log("sync: another sync holds the lock; skipping")
            return 0
        os.utime(LOCK_PATH)
        return sync(cfg)
    finally:
        lock.close()


# ===========================================================================
# --status — the READ-ONLY state report
# ===========================================================================

# A DISTINCT exit code per state, so a watcher can branch on WHICH failure
# without parsing prose. Deliberately not 1 or 2: main() already spends 1 on
# `--check`'s generic "unhealthy" and 2 on the usage no-op, and conflating a
# silently-inert subsystem with either of those is exactly the ambiguity this
# mode exists to remove.
STATUS_EXIT_CODES = {"OK": 0, "BLOCKED": 3, "DRIFTED": 4, "INERT": 5}


def _safe_exc(exc: BaseException) -> str:
    """An exception reduced to what is safe to PRINT: its type, plus the
    position for a JSON syntax error. Never `repr(exc)` / `str(exc)`: a
    UnicodeDecodeError's repr carries the raw bytes it choked on and a
    UnicodeEncodeError's carries the full text being encoded -- for a config
    or a file mid-redaction, that is replacement values / unredacted text.
    """
    name = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        return f"{name} at line {exc.lineno} column {exc.colno}"
    return name


def config_status(
    path: str | None = None, safe_errors: bool = False
) -> tuple[dict | None, str | None]:
    """Read + validate the mirror config with NO side effect whatsoever.

    Returns (cfg, None) when the config is safe to act on, else (None,
    reason). This is `load_config()` minus its `_log()` calls — that logging
    is precisely what makes load_config a WRITE, and `--status` must be safe
    to run from a watcher, repeatedly, changing nothing. It also does not
    rewrite cfg["clone_dir"] into its realpath the way load_config does,
    because nothing on the status path ever acts on that value.

    `safe_errors` (used only by --dry-run, default off so --status output is
    unchanged) swaps the `config unreadable (<repr>)` detail for the exception
    type alone -- see _safe_exc().
    """
    cfg_path = CONFIG_PATH if path is None else path
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        return None, f"no config at {cfg_path}"
    except Exception as exc:
        detail = _safe_exc(exc) if safe_errors else repr(exc)
        return None, f"config unreadable ({detail})"
    # validate_config itself reports a non-object config, so json's other
    # top-level types (list, string, number) need no separate branch here.
    reason = validate_config(cfg)
    if reason:
        return None, reason
    return cfg, None


def parse_blocked(text: str) -> tuple[str, list[str]]:
    """Pull the recorded source HEAD and the gate-hit lines out of a
    BLOCKED.md body, both VERBATIM — that file already names the offending
    path and the pattern it matched, which is exactly what a watcher has to
    relay for anyone to act on the block.

    Returns ("", []) for a body it cannot recognise; the caller then prints
    the whole body rather than silently reporting an empty block.
    """
    head = ""
    hits: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not head and stripped.startswith("Source HEAD:"):
            head = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- "):
            hits.append(stripped)
    return head, hits


def _read_text(path: str) -> str | None:
    """File content, or None if it cannot be read. Never raises, never writes."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return None


def _git_out(src: str, *args: str) -> str:
    """stdout of a read-only local git command, or "" on ANY failure.

    `--status` must be runnable by a watcher unconditionally: a missing git
    binary, an unreadable repo, or a timeout has to degrade into a reported
    state, never a traceback. Swallowing here is what makes that true.
    """
    try:
        proc = _run(src, *args)
    except Exception:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _commits_behind(src: str, last: str, head: str) -> int | None:
    """How many runtime commits landed since `last`, or None when git cannot
    say (no state recorded yet, or a sha that is not an ancestor of HEAD /
    no longer exists). Local and read-only — `rev-list` never contacts a
    remote.
    """
    if not last or not head or last == head:
        return None
    out = _git_out(src, "git", "-C", src, "rev-list", "--count", f"{last}..{head}")
    try:
        return int(out)
    except ValueError:
        return None


def status() -> int:
    """Report the mirror's state; return that state's distinct exit code.

    STRICTLY READ-ONLY — no copy, no commit, no push, no state write, not
    even a log line, and no network call. That is the load-bearing property:
    this is meant to be run by any watcher, on any cadence, concurrently
    with a real sync, without perturbing anything.

    The four states, in the precedence they are decided:

      INERT   — the config is missing/unreadable/rejected, so NOTHING runs.
                Checked FIRST because it is the only state that never even
                logs a failure: an inert subsystem does not block, it simply
                never syncs. Its remediation (fix the config) also has to
                happen before any BLOCKED.md remediation could matter.
      BLOCKED — .mirror/BLOCKED.md exists: the gate withheld a push. Its
                recorded source HEAD and gate hits are printed verbatim.
      DRIFTED — nothing blocked, but last_synced_head != runtime HEAD: a sync
                that never ran, or ran and died. Both shas and the commit
                distance are printed.
      OK      — config valid, nothing blocked, last_synced_head == HEAD.

    Line 1 leads with the bare state token (parse it with `awk '{print $1}'`);
    everything after it is for a human.
    """
    src = _lib.CLAUDE_DIR
    cfg, cfg_reason = config_status()
    head = _git_out(src, "git", "-C", src, "rev-parse", "HEAD")
    last = (_read_text(STATE_PATH) or "").strip()
    last_error = (_read_text(LAST_ERROR_PATH) or "").strip()

    blocked_body = None
    blocked_head, blocked_hits = "", []
    if os.path.exists(BLOCKED_PATH):
        # An existing-but-unreadable BLOCKED.md is still a block.
        blocked_body = _read_text(BLOCKED_PATH) or ""
        blocked_head, blocked_hits = parse_blocked(blocked_body)

    behind = None
    if cfg is None:
        state = "INERT"
        headline = f"subsystem disabled, nothing syncs — {cfg_reason}"
    elif blocked_body is not None:
        state = "BLOCKED"
        headline = (
            f"publish gate withheld the push — {len(blocked_hits)} gate hit(s); "
            f"see {BLOCKED_PATH}"
        )
    elif head and last and head == last:
        state = "OK"
        headline = f"mirror is current at runtime HEAD {head[:10]}"
    else:
        state = "DRIFTED"
        if not head:
            headline = "runtime HEAD is unresolvable; mirror state cannot be confirmed"
        elif not last:
            headline = "no successful sync has ever been recorded (no last_synced_head)"
        else:
            behind = _commits_behind(src, last, head)
            headline = (
                f"mirror is {behind} commit(s) behind runtime HEAD {head[:10]}"
                if behind is not None
                else f"last mirrored sha differs from runtime HEAD {head[:10]}"
            )

    print(f"{state}  {headline}")
    if cfg is None:
        print(f"config:        REJECTED — {cfg_reason}")
    else:
        print(f"config:        valid (branch {cfg['branch']} -> {cfg['remote_url']})")
    print(f"runtime HEAD:  {head or '(unresolvable)'}")
    print(f"last mirrored: {last or '(never)'}")
    if behind is not None:
        print(f"commits behind:{behind:>4}")
    print(
        "blocked:       "
        + (f"YES — see {BLOCKED_PATH}" if blocked_body is not None else "no")
    )
    print(f"last error:    {last_error or 'none'}")

    if blocked_body is not None:
        print("")
        print(f"BLOCKED.md source HEAD: {blocked_head or '(unrecorded)'}")
        if blocked_hits:
            print("BLOCKED.md gate hits (verbatim):")
            for line in blocked_hits:
                print(f"  {line}")
        else:
            print("BLOCKED.md (verbatim — no recognised gate-hit lines):")
            for line in blocked_body.splitlines():
                print(f"  {line}")

    return STATUS_EXIT_CODES[state]


# ===========================================================================
# --dry-run — export + redact + gate into a temp dir, REPORT, publish nothing
# ===========================================================================

# File types whose replacements are checked for landing inside a quoted string
# literal, and the scanner dialect used for each.
_QUOTE_SCAN_LANGS = {
    ".py": "py",
    ".sh": "sh",
    ".mjs": "js",
    ".cjs": "js",
    ".js": "js",
    ".json": "json",
}

# Compiled lazily, on the first --dry-run only: this module is imported by
# posttooluse_bash.py on EVERY Bash tool call, so nothing --dry-run needs may
# add import-time work or an import-time failure mode.
_QUOTE_TABLES: dict | None = None


def _quote_tables() -> dict:
    """{lang: (opening-token regex, {token: (closer regex, single_line)})}."""
    global _QUOTE_TABLES
    if _QUOTE_TABLES is not None:
        return _QUOTE_TABLES

    def line(q: str) -> tuple:
        c = re.escape(q)
        return re.compile(rf"[^{c}\\\n]*(?:\\.[^{c}\\\n]*)*{c}", re.S), True

    def multi(q: str) -> tuple:
        c = re.escape(q)
        return re.compile(rf"[^{c}\\]*(?:\\.[^{c}\\]*)*{c}", re.S), False

    def triple(q: str) -> tuple:
        c = re.escape(q)
        return re.compile(
            rf"[^{c}\\]*(?:(?:\\.|{c}(?!{c}{c}))[^{c}\\]*)*{c}{c}{c}", re.S
        ), False

    raw_single = (re.compile(r"[^']*'"), False)  # shell '...': no escapes
    _QUOTE_TABLES = {
        "py": (
            re.compile(r"\"\"\"|'''|\"|'|#"),
            {
                '"""': triple('"'), "'''": triple("'"),
                '"': line('"'), "'": line("'"),
            },
        ),
        "sh": (
            # '#' opens a comment only at a word start ($#, ${#x}, ${x#p} don't).
            re.compile(r"\"|'|(?<![^\s;&|(])#"),
            {'"': multi('"'), "'": raw_single},
        ),
        "js": (
            re.compile(r"\"|'|`|//|/\*"),
            {'"': line('"'), "'": line("'"), "`": multi("`")},
        ),
        "json": (re.compile(r"\""), {'"': line('"')}),
    }
    return _QUOTE_TABLES


def _quoted_spans(text: str, lang: str) -> list[tuple[int, int]]:
    """(start, end) of every quoted string literal in `text`, delimiters
    included, comments skipped. A HEURISTIC scanner (no real parser per
    language: a stray apostrophe in a shell heredoc can mispair) feeding an
    advisory report only — it must never raise and never decide a verdict.
    """
    opener, closers = _quote_tables()[lang]
    spans: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    while i < n:
        m = opener.search(text, i)
        if m is None:
            break
        token = m.group()
        if token in ("#", "//"):
            nl = text.find("\n", m.end())
            if nl == -1:
                break
            i = nl + 1
            continue
        if token == "/*":
            close = text.find("*/", m.end())
            if close == -1:
                break
            i = close + 2
            continue
        closer, single_line = closers[token]
        found = closer.match(text, m.end())
        if found is not None:
            end = found.end()
        elif single_line:  # unterminated: the literal ends with its line
            nl = text.find("\n", m.end())
            end = n if nl == -1 else nl
        else:
            end = n
        spans.append((m.start(), end))
        i = max(end, m.start() + 1)
    return spans


class _QuotedReplacementTracker:
    """`apply_replacements` observer: records every replacement occurrence
    that lands inside a quoted string literal of a .py/.sh/.mjs/.js/.cjs/.json
    file, as (file, line) -> the replacement indexes that hit there. It keeps
    positions and indexes ONLY — never the matched text or the replacement
    values — so the report cannot leak them. Advisory: any internal failure
    is swallowed so observation can never change a redaction or a verdict.
    """

    def __init__(self) -> None:
        self.hits: dict[tuple[str, int], list[int]] = {}
        self._text: str | None = None
        self._spans: list[tuple[int, int]] = []
        self._starts: list[int] = []

    def __call__(self, rel: str, index: int, old: str, new: str, text: str) -> None:
        try:
            lang = _QUOTE_SCAN_LANGS.get(os.path.splitext(rel)[1].lower())
            if lang is None or not old or old not in text:
                return
            if self._text is None or self._text != text:
                self._spans = _quoted_spans(text, lang)
                self._starts = [start for start, _ in self._spans]
                self._text = text
            if not self._spans:
                return
            import bisect  # lazy: this module is on the per-Bash-call import chain

            newlines: list[int] | None = None
            pos = text.find(old)
            while pos != -1:
                k = bisect.bisect_right(self._starts, pos) - 1
                if k >= 0 and pos < self._spans[k][1]:
                    if newlines is None:
                        newlines = [m.start() for m in re.finditer("\n", text)]
                    line_no = bisect.bisect_left(newlines, pos) + 1
                    self.hits.setdefault((rel, line_no), []).append(index)
                pos = text.find(old, pos + len(old))
        except Exception:
            return


def _discard(msg: str) -> None:
    """A log sink that drops everything — --dry-run writes no log line."""
    return None


def _git_paths(src: str, *args: str) -> set[str] | None:
    """NUL-delimited path set from a read-only git listing, None on failure."""
    try:
        proc = _run(src, "git", "-C", src, *args)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return {p for p in proc.stdout.split("\0") if p}


def _covers(paths: set[str], entry: str) -> bool:
    """True when `entry` is one of `paths` or a directory holding any."""
    norm = os.path.normpath(entry)
    if norm in paths:
        return True
    prefix = norm + "/"
    return any(p.startswith(prefix) for p in paths)


def _stage_clone_index(clone_dir: str, stage: str) -> str | None:
    """Seed the temp tree from the clone's INDEX; None on success, else the
    failure reason.

    `git checkout-index -a --prefix=<stage>/` writes every index entry under
    the prefix and writes NOTHING in the clone: with no `-u` it does not even
    refresh the index's stat data. The index, not the working tree, because
    `--sync` first resets the working tree to the index (`git checkout -- .`)
    and only then exports over it -- so the index is what `--sync` gates, while
    a dry run that copied the working tree would see a prior blocked sync's
    leftovers (calling CLEAN what `--sync` blocks), miss tracked files deleted
    from the working tree, and skip gitlinks.
    """
    proc = _run(clone_dir, "git", "checkout-index", "-a", "--prefix=" + stage.rstrip("/") + "/")
    if proc.returncode != 0:
        return f"git checkout-index failed: {_err(proc)}"
    return None


# The top-level config keys this module reads. Anything else is a typo or dead
# config; --dry-run names it, because a misspelled key is how a gate silently
# disappears (`forbiden_patterns` -> no patterns -> nothing can ever hit).
_CONFIG_KEYS = frozenset({
    "remote_url", "clone_dir", "branch", "include", "mirror_managed",
    "replacements", "forbidden_patterns", "forbidden_allow",
})


def _dry_run_config_check(cfg: dict) -> tuple[list[str], str | None]:
    """(notes, error) for a config that already passed validate_config.

    validate_config checks what is DANGEROUS (paths, URL, branch); it does not
    check that the gate exists, and sync() reads `forbidden_patterns` with a
    default of [] -- so a missing, misspelled or emptied key is a gate that
    can never fire and a clean verdict that means nothing. A dry run must not
    say CLEAN about a gate it cannot show is there.
    """
    notes: list[str] = []
    unknown = sorted(k for k in cfg if k not in _CONFIG_KEYS)
    if unknown:
        notes.append(
            "note:          unknown config key(s), ignored: "
            + ", ".join(repr(k) for k in unknown)
        )
    patterns = cfg.get("forbidden_patterns")
    if not (
        isinstance(patterns, list)
        and patterns
        and all(isinstance(p, str) for p in patterns)
    ):
        return notes, "no forbidden_patterns configured"
    if not isinstance(cfg.get("replacements", []), list):
        return notes, "replacements must be a list"
    if not isinstance(cfg.get("forbidden_allow", {}), dict):
        return notes, "forbidden_allow must be an object"
    return notes, None


# Longest hit list printed in full; the per-pattern summary always is.
_DRY_RUN_MAX_LISTED = 500


def _dry_run_in(
    stage: str, src: str, head: str, cfg: dict, cfg_path: str, notes: list[str]
) -> int:
    """The dry run proper, against an empty temp dir `stage`. Prints the
    report; returns 0 (clean) or 1 (blocked or a failed stage)."""
    clone_dir = os.path.realpath(os.path.expanduser(str(cfg["clone_dir"])))
    include: list[str] = cfg["include"]
    managed = set(cfg.get("mirror_managed", []))
    replacements = cfg.get("replacements", [])
    patterns = cfg.get("forbidden_patterns", [])
    allow = cfg.get("forbidden_allow", {})

    tracked: set[str] = set()
    clone_note = ""
    if os.path.isdir(os.path.join(clone_dir, ".git")):
        tracked, tracked_error = _tracked_paths(clone_dir)
        if tracked_error is not None:
            print(f"DRY-RUN ERROR: {tracked_error}")
            return 1
        staged_error = _stage_clone_index(clone_dir, stage)
        if staged_error is not None:
            print(f"DRY-RUN ERROR: {staged_error}")
            return 1
    else:
        clone_note = (
            "no clone at the configured clone_dir: mirror-managed and "
            "already-tracked files were NOT scanned (only the fresh export was)"
        )

    tracker = _QuotedReplacementTracker()
    publishable, excluded, failure = _export_and_redact(
        src, stage, include, managed, replacements, _discard, tracker, True
    )
    if failure is not None:
        print(f"DRY-RUN ERROR: {failure}")
        return 1
    violations = _gate(stage, publishable, tracked, patterns, allow)

    added = sum(1 for rel in publishable if rel not in tracked)
    removed = sum(
        1 for rel in tracked if not os.path.lexists(os.path.join(stage, rel))
    )
    pairs = sum(
        1 for pair in replacements if isinstance(pair, list) and len(pair) == 2
    )
    malformed = len(replacements) - pairs

    out: list[str] = []
    out.append(
        f"DRY-RUN  runtime HEAD {head[:10]} -> temp export "
        "(nothing published, no .mirror state touched)"
    )
    out.append(f"config:        {cfg_path}")
    out.append(
        f"export:        {len(publishable)} publishable; vs clone: "
        f"{added} new, {removed} removed; {len(excluded)} excluded"
    )
    out.append(
        f"gate:          {len(patterns)} patterns, {pairs} replacement pairs, "
        f"{len(allow)} allow entries"
    )
    out += notes
    if clone_note:
        out.append(f"note:          {clone_note}")
    if malformed:
        out.append(
            f"note:          {malformed} malformed replacement entr"
            f"{'y' if malformed == 1 else 'ies'} skipped (not shown)"
        )

    out.append("")
    out.append(f"forbidden-pattern hits: {len(violations)}")
    by_pattern: dict[str, int] = {}
    for _rel, pat in violations:
        by_pattern[pat] = by_pattern.get(pat, 0) + 1
    for rel, pat in violations[:_DRY_RUN_MAX_LISTED]:
        out.append(f"  {rel}  {pat}")
    if len(violations) > _DRY_RUN_MAX_LISTED:
        out.append(f"  ... and {len(violations) - _DRY_RUN_MAX_LISTED} more")
    for pat, count in sorted(by_pattern.items()):
        out.append(f"  by pattern: {pat} x{count}")

    quoted = sorted(tracker.hits.items())
    quoted_files = {rel for (rel, _line), _ in quoted}
    total = sum(len(v) for v in tracker.hits.values())
    out.append("")
    out.append(
        "quoted-string replacements (.py/.sh/.mjs/.js/.cjs/.json): "
        + (f"{total} in {len(quoted_files)} file(s)" if quoted else "none")
    )
    for (rel, line_no), idxs in quoted[:_DRY_RUN_MAX_LISTED]:
        which = ",".join(f"#{i}" for i in sorted(set(idxs)))
        out.append(f"  {rel}:{line_no}  x{len(idxs)}  repl={which}")
    if len(quoted) > _DRY_RUN_MAX_LISTED:
        out.append(f"  ... and {len(quoted) - _DRY_RUN_MAX_LISTED} more lines")

    out.append("")
    index_paths = _git_paths(src, "ls-files", "-z")
    head_paths = _git_paths(src, "ls-tree", "-r", "--name-only", "-z", "HEAD")
    membership_failed = index_paths is None or head_paths is None
    if membership_failed:
        out.append("include entries not in git ls-files: UNAVAILABLE (git failed)")
    else:
        untracked = [
            e for e in include if e not in managed and not _covers(index_paths, e)
        ]
        uncommitted = [
            e for e in include
            if e not in managed
            and _covers(index_paths, e)
            and not _covers(head_paths, e)
        ]
        out.append(f"include entries not in git ls-files: {len(untracked)}")
        out += [f"  {e}" for e in untracked]
        out.append(
            f"include entries tracked but absent at HEAD (the export skips them): "
            f"{len(uncommitted)}"
        )
        out += [f"  {e}" for e in uncommitted]

    if excluded:
        out.append("")
        out.append(f"excluded from publish: {len(excluded)}")
        out += [f"  {rel}  ({why})" for rel, why in excluded[:_DRY_RUN_MAX_LISTED]]

    out.append("")
    if membership_failed:  # a stage that could not run is an error, never clean
        out.append("DRY-RUN ERROR: include membership unavailable")
    elif violations:
        out.append(f"DRY-RUN BLOCKED: {len(violations)} hit(s)")
    else:
        out.append("DRY-RUN CLEAN")
    print("\n".join(out))
    return 1 if (violations or membership_failed) else 0


def dry_run(cfg_path: str | None = None) -> int:
    """`--dry-run`: run the sync's export -> redact -> gate stages into a
    throwaway temp dir, print the report, publish nothing, touch no state.

    Exit 0 = DRY-RUN CLEAN, 1 = DRY-RUN BLOCKED (gate hits) or DRY-RUN ERROR
    (a failed stage: config rejected or without a real gate, HEAD unresolvable,
    export/redaction/git failure, include membership unreadable). It NEVER
    reports clean on a failure, and never prints an exception's repr or
    message -- only its type (see _safe_exc). It does not call sync(), take
    the lock, write state, log, or write BLOCKED.md / last_error, and it never
    writes to the clone -- the one directory it writes is its own mkdtemp,
    removed on exit.
    """
    path = CONFIG_PATH if cfg_path is None else os.path.expanduser(cfg_path)
    cfg, reason = config_status(path, safe_errors=True)
    if cfg is None:
        print(f"DRY-RUN ERROR: config rejected — {reason}")
        return 1
    notes, config_error = _dry_run_config_check(cfg)
    if config_error is not None:
        print("\n".join(notes + [f"DRY-RUN ERROR: {config_error}"]))
        return 1
    src = _lib.CLAUDE_DIR
    head = _git_out(src, "git", "-C", src, "rev-parse", "HEAD")
    if not head:
        print("DRY-RUN ERROR: cannot resolve ~/.claude HEAD")
        return 1
    import tempfile  # lazy: this module is on the per-Bash-call import chain

    stage = tempfile.mkdtemp(prefix="mirror-dry-run-")
    try:
        return _dry_run_in(stage, src, head, cfg, path, notes)
    except Exception as exc:
        print(f"DRY-RUN ERROR: crashed — {_safe_exc(exc)}")
        return 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)


_MODE_FLAGS = ("--sync", "--check", "--status")


def _parse_dry_run_argv(argv: list[str]) -> tuple[str | None, str | None]:
    """(config_path, usage_error) for an argv holding --dry-run and/or
    --config. Every rule here is decided BEFORE anything runs:

      * --config is accepted ONLY together with --dry-run: the standing push
        authority is bound to .mirror/config.json and must not be re-pointable
        by a flag on --sync / --check / --status;
      * --dry-run is mutually exclusive with --sync / --check / --status;
      * --config needs a PATH (as `--config PATH` or `--config=PATH`), once;
      * nothing else is accepted.
    """
    has_config = any(a == "--config" or a.startswith("--config=") for a in argv)
    if has_config and "--dry-run" not in argv:
        return None, "--config is accepted only together with --dry-run"
    for flag in _MODE_FLAGS:
        if flag in argv:
            return None, f"--dry-run cannot be combined with {flag}"
    cfg_path: str | None = None
    seen_config = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--dry-run":
            pass
        elif arg == "--config" or arg.startswith("--config="):
            if seen_config:
                return None, "--config given more than once"
            seen_config = True
            if arg == "--config":
                i += 1
                value = argv[i] if i < len(argv) else ""
                if value.startswith("--"):  # a following flag is not a path
                    value = ""
            else:
                value = arg.split("=", 1)[1]
            if not value:
                return None, "--config needs a PATH"
            cfg_path = value
        else:
            return None, f"unrecognised argument: {arg}"
        i += 1
    return cfg_path, None


def main(argv: list[str]) -> int:
    # --dry-run / --config are decided FIRST and in one place, so a usage
    # error (exit 2) is reached before any other mode can run, and --config
    # can never reach --sync / --check / --status.
    if "--dry-run" in argv or any(
        a == "--config" or a.startswith("--config=") for a in argv
    ):
        cfg_path, usage_error = _parse_dry_run_argv(argv)
        if usage_error is not None:
            print(f"error: {usage_error}", file=sys.stderr)
            print(
                "usage: runtime_mirror_sync.py --dry-run [--config PATH]",
                file=sys.stderr,
            )
            return 2
        return dry_run(cfg_path)
    if "--status" in argv:
        return status()
    if "--check" in argv:
        cfg = load_config()
        head = _run(
            _lib.CLAUDE_DIR, "git", "-C", _lib.CLAUDE_DIR, "rev-parse", "HEAD"
        ).stdout.strip()
        try:
            last = open(STATE_PATH, encoding="utf-8").read().strip()
        except Exception:
            last = "(never)"
        lag = "current" if head and head == last else "BEHIND runtime HEAD"
        try:
            last_error = open(LAST_ERROR_PATH, encoding="utf-8").read().strip()
        except Exception:
            last_error = "none"
        blocked = os.path.exists(BLOCKED_PATH)
        print(f"config: {'valid' if cfg else 'MISSING or invalid (sync disabled)'}")
        print(f"runtime HEAD:  {head or '(unresolvable)'}")
        print(f"last mirrored: {last}  [{lag}]")
        print(f"last error: {last_error}")
        print(f"blocked: {'YES — see ' + BLOCKED_PATH if blocked else 'no'}")
        # bundle_parity summary (runtime_bundle_repo_agnostic_plan.md §0
        # assertion 2/6, WS5.6): the mirror-sync `--check` is the natural
        # place a caller already looks for "is this subsystem healthy", and
        # bundle completeness is a SIBLING health question to content
        # freshness -- but it is deliberately advisory here: a bundle_parity
        # exception (or a nonzero finding count) must NEVER change this
        # command's own `healthy`/exit-code semantics, which stay scoped to
        # the mirror-sync pipeline alone. Fail-open, always.
        try:
            import bundle_parity

            findings = bundle_parity.check()
            real_findings = [f for f in findings if not bundle_parity._is_informational(f)]
            print(f"bundle_parity: {len(real_findings)} finding(s)")
        except Exception as exc:
            print(f"bundle_parity: check failed ({exc.__class__.__name__}: {exc})")
        # Health-probe semantics: non-zero when anything is wrong, so a
        # sweep/heartbeat can consume this without parsing the text.
        healthy = bool(cfg) and lag == "current" and last_error == "none" and not blocked
        return 0 if healthy else 1
    if "--sync" in argv:
        try:
            return _locked_sync()
        except Exception as exc:
            return _fail(f"crashed: {exc!r}")
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main(sys.argv[1:]))
