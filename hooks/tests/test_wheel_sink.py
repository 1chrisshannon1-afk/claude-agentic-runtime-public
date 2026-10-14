"""Tests for hooks/wheel_sink.py — THE ISSUE WHEEL session's sanctioned write channel into
~/.claude (GH #4767). Spec: the module docstring and the L1.1 design §5.

Every test runs the REAL sink as a subprocess under an isolated $HOME, with the env the wrapper
exports (WHEEL_SLUG, OVERSIGHT_JOB_LABEL, OVERSIGHT_RUN_SCRATCH, OVERSIGHT_WRAPPER_START_ISO,
OVERSIGHT_CADENCE); nothing here touches the real ~/.claude.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import pytest

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SINK = os.path.join(_HOOKS_DIR, "wheel_sink.py")
_SCRUB_ENV_RE = re.compile(r"^(WHEEL_|OVERSIGHT_|CSA_)")
_ISO_Z = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

START = "2026-09-24T04:10:00Z"
CADENCE = "22:10 Mon-Fri"


class _Sink:
    def __init__(self, tmp_path, slug="csa", label=None):
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir(exist_ok=True)
        self.scratch = tmp_path / "scratch"
        self.scratch.mkdir(exist_ok=True)
        self.slug = slug
        self.label = label or f"com.oversight.wheel.{slug}"
        self.env = {k: v for k, v in os.environ.items() if not _SCRUB_ENV_RE.match(k)}
        self.env.update({
            "HOME": str(self.home),
            "WHEEL_SLUG": slug,
            "OVERSIGHT_JOB_LABEL": self.label,
            "OVERSIGHT_RUN_SCRATCH": str(self.scratch),
            "OVERSIGHT_WRAPPER_START_ISO": START,
            "OVERSIGHT_CADENCE": CADENCE,
        })

    @property
    def claude(self):
        return self.home / ".claude"

    @property
    def hb(self):
        return self.claude / "schedules" / "heartbeats" / f"{self.label}.json"

    @property
    def audit(self):
        return self.claude / "telemetry" / "wheel" / self.slug / "sink_audit.jsonl"

    def put(self, name, content):
        p = self.scratch / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        if isinstance(content, str):
            content = content.encode("utf-8")
        p.write_bytes(content)
        return p

    def run(self, *args, stdin=None):
        return subprocess.run([sys.executable, _SINK, *[str(a) for a in args]], env=self.env,
                              capture_output=True, text=True, timeout=30, input=stdin)


def _end(**over):
    d = {"exit": 0, "finished_at": "now", "summary": "triaged 3 / closed 0"}
    d.update(over)
    return d


# --- heartbeat --------------------------------------------------------------------


def test_heartbeat_happy_path_fills_stamps_and_marks(tmp_path):
    s = _Sink(tmp_path)
    src = s.put("end.json", _end(written_via="forged", sink_version=99))
    before = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    r = s.run("heartbeat", "--from", src)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    hb = json.loads(s.hb.read_text())
    assert hb["job"] == s.label and hb["started_at"] == START and hb["cadence"] == CADENCE
    assert _ISO_Z.match(hb["finished_at"])
    stamped = datetime.datetime.strptime(hb["finished_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    assert abs((stamped - before).total_seconds()) <= 5
    assert hb["written_via"] == "wheel_sink" and hb["sink_version"] == 1
    assert "status" not in hb
    assert out["ok"] is True and out["kind"] == "heartbeat" and out["dest"] == str(s.hb)
    assert out["sha256"] == hashlib.sha256(s.hb.read_bytes()).hexdigest()
    assert [p.name for p in s.hb.parent.iterdir()] == [s.hb.name], "no temp file may be left behind"
    audit = [json.loads(line) for line in s.audit.read_text().splitlines()]
    assert len(audit) == 1 and audit[0]["kind"] == "heartbeat" and audit[0]["sink_version"] == 1


def test_heartbeat_null_finished_at_is_kept(tmp_path):
    s = _Sink(tmp_path)
    r = s.run("heartbeat", "--from", s.put("mid.json", _end(finished_at=None, exit=1, summary="lane 1 parked")))
    assert r.returncode == 0, r.stderr
    hb = json.loads(s.hb.read_text())
    assert hb["finished_at"] is None and hb["exit"] == 1


@pytest.mark.parametrize("payload,why", [
    (_end(status="ok"), "status"),
    (_end(job="com.oversight.wheel.agency"), "job"),
    (_end(started_at="2026-09-23T04:10:00Z"), "started_at"),
    (_end(cadence="daily"), "cadence"),
    ({"exit": 0, "summary": "x"}, "finished_at"),
    (_end(finished_at="2026-09-24T05:00:00Z"), "finished_at"),
    (_end(exit="0"), "exit"),
    (_end(exit=True), "exit"),
    (_end(summary=None), "summary"),
    ([1, 2], "object"),
], ids=["status", "foreign-job", "started_at", "cadence", "no-finished_at", "caller-timestamp",
        "str-exit", "bool-exit", "no-summary", "non-object"])
def test_heartbeat_refusals(tmp_path, payload, why):
    s = _Sink(tmp_path)
    r = s.run("heartbeat", "--from", s.put("end.json", payload))
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert r.stderr.startswith("wheel_sink: refused: ") and why in r.stderr
    assert not s.hb.exists()
    assert not s.audit.exists()


def test_heartbeat_refuses_oversize(tmp_path):
    s = _Sink(tmp_path)
    big = _end(summary="x" * (1024 * 1024 + 10))
    r = s.run("heartbeat", "--from", s.put("end.json", big))
    assert r.returncode == 2 and "cap" in r.stderr
    assert not s.hb.exists()


# --- env ------------------------------------------------------------------------------


@pytest.mark.parametrize("key,val", [
    ("OVERSIGHT_RUN_SCRATCH", None),
    ("OVERSIGHT_JOB_LABEL", "com.oversight.csa.daily"),
    ("WHEEL_SLUG", "csa/../x"),
    ("OVERSIGHT_WRAPPER_START_ISO", "2026-09-24 04:10"),
], ids=["no-scratch", "non-wheel-label", "slug-with-slash", "bad-start-iso"])
def test_env_refusals(tmp_path, key, val):
    s = _Sink(tmp_path)
    if val is None:
        s.env.pop(key)
    else:
        s.env[key] = val
    r = s.run("heartbeat", "--from", s.put("end.json", _end()))
    assert r.returncode == 2 and r.stderr.startswith("wheel_sink: refused: ")
    assert not (s.claude / "schedules").exists()


def test_home_symlink_refused(tmp_path):
    """N7 (trust-architect, fix round): HOME must equal its own realpath, matching the launcher's
    own home-unsafe check -- a symlinked HOME would otherwise route every destination this script
    writes (heartbeat, patches, plans, the audit log) through an unresolved path."""
    s = _Sink(tmp_path)
    real_home = s.home
    linked_home = tmp_path / "home_link"
    linked_home.symlink_to(real_home)
    s.env["HOME"] = str(linked_home)
    r = s.run("heartbeat", "--from", s.put("end.json", _end()))
    assert r.returncode == 2 and "realpath" in r.stderr
    assert not (real_home / ".claude" / "schedules").exists()


def test_run_scratch_dot_claude_via_symlinked_parent_refused(tmp_path):
    """N7 (trust-architect, fix round): the .claude-component check must run on the REALPATH of
    OVERSIGHT_RUN_SCRATCH, not the unresolved string -- a symlinked parent directory that only
    resolves under .claude after following it must still be refused, even though the raw string
    itself contains no literal ".claude" component."""
    s = _Sink(tmp_path)
    real_dotclaude_scratch = s.claude / "oversight_wheel.abcdef"
    real_dotclaude_scratch.mkdir(parents=True)
    sneaky = tmp_path / "not_claude_looking"
    sneaky.symlink_to(real_dotclaude_scratch)
    s.env["OVERSIGHT_RUN_SCRATCH"] = str(sneaky)
    r = s.run("heartbeat", "--from", str(sneaky / "end.json"))
    assert r.returncode == 2 and ".claude component" in r.stderr


# --- --from ------------------------------------------------------------------------


def test_from_outside_scratch_refused(tmp_path):
    s = _Sink(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(_end()))
    r = s.run("heartbeat", "--from", outside)
    assert r.returncode == 2 and "outside RUN_SCRATCH" in r.stderr
    assert not s.hb.exists()


def test_from_dotdot_escape_refused(tmp_path):
    s = _Sink(tmp_path)
    (tmp_path / "outside.json").write_text(json.dumps(_end()))
    r = s.run("heartbeat", "--from", f"{s.scratch}/../outside.json")
    assert r.returncode == 2 and "outside RUN_SCRATCH" in r.stderr


def test_from_symlink_pointing_outside_refused(tmp_path):
    s = _Sink(tmp_path)
    (tmp_path / "outside.json").write_text(json.dumps(_end()))
    (s.scratch / "link.json").symlink_to(tmp_path / "outside.json")
    r = s.run("heartbeat", "--from", s.scratch / "link.json")
    assert r.returncode == 2 and "outside RUN_SCRATCH" in r.stderr


def test_from_symlink_pointing_inside_refused(tmp_path):
    s = _Sink(tmp_path)
    target = s.put("real.json", _end())
    (s.scratch / "link.json").symlink_to(target)
    r = s.run("heartbeat", "--from", s.scratch / "link.json")
    assert r.returncode == 2 and "symlink" in r.stderr
    assert not s.hb.exists()


def test_from_fifo_and_directory_refused(tmp_path):
    s = _Sink(tmp_path)
    fifo = s.scratch / "fifo"
    os.mkfifo(fifo)
    r = s.run("heartbeat", "--from", fifo)
    assert r.returncode == 2 and "regular file" in r.stderr
    (s.scratch / "adir").mkdir()
    r = s.run("heartbeat", "--from", s.scratch / "adir")
    assert r.returncode == 2 and "regular file" in r.stderr


def test_from_parent_directory_symlink_still_refused(tmp_path):
    """N7, static case: a symlinked PARENT directory of the --from path, present for the whole
    call (no race). The existing realpath-based containment check alone already catches this
    (real = os.path.realpath(absolute) follows the parent symlink too), so this stays green even
    without the fd-reverification fix below -- it documents that the static case was never the
    gap. The genuine TOCTOU gap (the parent symlink changing BETWEEN the realpath check and the
    open) is covered by test_from_toctou_parent_symlink_swap_after_realpath_check below."""
    s = _Sink(tmp_path)
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    outside_file = outside_dir / "end.json"
    outside_file.write_text(json.dumps(_end()))
    linked_subdir = s.scratch / "linked_subdir"
    linked_subdir.symlink_to(outside_dir)
    r = s.run("heartbeat", "--from", str(linked_subdir / "end.json"))
    assert r.returncode == 2 and "outside RUN_SCRATCH" in r.stderr
    assert not s.hb.exists()


def test_from_toctou_parent_symlink_swap_after_realpath_check(tmp_path, monkeypatch):
    """N7 (trust-architect, fix round), the genuine TOCTOU: read_from() computes `real =
    os.path.realpath(absolute)` (verified inside RUN_SCRATCH) and only LATER opens `absolute`
    with O_NOFOLLOW (which guards only the last path component, not a parent). If a parent
    directory symlink is swapped in the window between those two calls, the fd actually opened
    can be a DIFFERENT file than the one `real` was computed from and verified against --
    O_NOFOLLOW alone cannot detect this since it only inspects the last component.

    This is exercised IN-PROCESS (not via subprocess) because reliably winning a real filesystem
    race from a test is non-deterministic; monkeypatching os.path.realpath to perform the swap AT
    the exact moment read_from() calls it deterministically simulates "the parent symlink changed
    right after the check" on every run, which is the shape O_NOFOLLOW's last-component-only
    guard cannot see. The fstat(fd)-vs-stat(realpath) re-verification this fix adds is what
    catches it: after the (attacker-controlled) swap, re-stat'ing `real` a second time (post-open)
    sees the NEW target, which no longer matches the fd that was actually opened against the OLD
    (pre-swap) resolution -- a mismatch this fix refuses on.
    """
    import importlib
    import sys as _sys

    sys_path_added = _HOOKS_DIR not in _sys.path
    if sys_path_added:
        _sys.path.insert(0, _HOOKS_DIR)
    try:
        wheel_sink = importlib.import_module("wheel_sink")
        importlib.reload(wheel_sink)

        home = tmp_path / "home"
        home.mkdir()
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        env = wheel_sink.Env({
            "HOME": str(home), "WHEEL_SLUG": "csa", "OVERSIGHT_JOB_LABEL": "com.oversight.wheel.csa",
            "OVERSIGHT_RUN_SCRATCH": str(scratch), "OVERSIGHT_WRAPPER_START_ISO": START,
            "OVERSIGHT_CADENCE": CADENCE,
        })

        # The file the check-time realpath will resolve to (legitimately inside scratch).
        legit_dir = scratch / "legit_subdir"
        legit_dir.mkdir()
        (legit_dir / "end.json").write_text(json.dumps(_end()))

        # The parent-symlink whose target swaps mid-call.
        swap_link = scratch / "swap_link"
        swap_link.symlink_to(legit_dir)

        # A DIFFERENT file, outside scratch, that the swap will redirect the open to.
        attacker_dir = tmp_path / "attacker_dir"
        attacker_dir.mkdir()
        (attacker_dir / "end.json").write_text(json.dumps(_end(summary="ATTACKER-PLANTED")))

        real_realpath = os.path.realpath
        call_count = {"n": 0}

        def _racing_realpath(path, *a, **kw):
            result = real_realpath(path, *a, **kw)
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: read_from()'s own check-time realpath. Right after it returns
                # (still legitimately resolving inside scratch), swap the parent symlink.
                swap_link.unlink()
                swap_link.symlink_to(attacker_dir)
            return result

        monkeypatch.setattr(wheel_sink.os.path, "realpath", _racing_realpath)
        try:
            wheel_sink.read_from(env, str(swap_link / "end.json"), wheel_sink.HEARTBEAT_MAX)
            assert False, "read_from must refuse when the fd's real target no longer matches the check"
        except wheel_sink.Refused as exc:
            assert "different file" in str(exc) or "re-verified" in str(exc), str(exc)
    finally:
        if sys_path_added:
            _sys.path.remove(_HOOKS_DIR)


def test_audit_log_symlink_target_not_followed(tmp_path):
    """N7 (trust-architect, fix round): the audit append now opens with O_NOFOLLOW -- a symlink
    planted at the audit log's own path must make the open fail (ELOOP) rather than silently
    appending through it to wherever it points. The heartbeat write itself must still succeed
    (audit failure is non-fatal, matching the existing audit() contract), but the symlinked
    target must be left untouched."""
    s = _Sink(tmp_path)
    audit_target = tmp_path / "audit_target.jsonl"
    audit_target.write_text("PRE-EXISTING\n")
    s.audit.parent.mkdir(parents=True, exist_ok=True)
    s.audit.symlink_to(audit_target)
    r = s.run("heartbeat", "--from", s.put("end.json", _end()))
    assert r.returncode == 0, r.stderr
    assert s.hb.exists(), "the heartbeat write itself must still succeed"
    assert audit_target.read_text() == "PRE-EXISTING\n", "the symlink target must not be written through"


def test_from_stdin_refused(tmp_path):
    s = _Sink(tmp_path)
    r = s.run("heartbeat", "--from", "-", stdin=json.dumps(_end()))
    assert r.returncode == 2 and "stdin" in r.stderr
    assert not s.hb.exists()


# --- patch -----------------------------------------------------------------------------


GOOD_PATCH = "csa-4767-20260924T041000Z.patch"


@pytest.mark.parametrize("name", [
    "agency-4767-20260924T041000Z.patch",
    "../csa-4767-20260924T041000Z.patch",
    "csa-4767-2026-09-24.patch",
    "csa-12345678-20260924T041000Z.patch",
], ids=["wrong-slug", "traversal", "wrong-stamp", "issue-too-long"])
def test_patch_name_refusals(tmp_path, name):
    s = _Sink(tmp_path)
    r = s.run("patch", "--name", name, "--from", s.put("p.patch", "diff\n"))
    assert r.returncode == 2 and "patch name" in r.stderr


def test_patch_fresh_home_creates_dir_and_is_create_only(tmp_path):
    s = _Sink(tmp_path)
    assert not (s.claude / "schedules" / "patches").exists()
    r = s.run("patch", "--name", GOOD_PATCH, "--from", s.put("p.patch", "diff --git a b\n"))
    assert r.returncode == 0, r.stderr
    dest = s.claude / "schedules" / "patches" / GOOD_PATCH
    assert json.loads(r.stdout)["dest"] == str(dest)
    original = dest.read_bytes()
    r2 = s.run("patch", "--name", GOOD_PATCH, "--from", s.put("q.patch", "DIFFERENT\n"))
    assert r2.returncode == 2 and "create-only" in r2.stderr
    assert dest.read_bytes() == original
    assert sorted(p.name for p in dest.parent.iterdir()) == [GOOD_PATCH]


# --- plan --------------------------------------------------------------------------------


GOOD_PLAN = "wheel-4767-20260924T041000Z.md"


def test_plan_fresh_home_destination_and_create_only(tmp_path):
    s = _Sink(tmp_path)
    r = s.run("plan", "--name", GOOD_PLAN, "--from", s.put("plan.md", "# plan\n"))
    assert r.returncode == 0, r.stderr
    dest = s.claude / "plans" / "wheel" / "csa" / "plans" / GOOD_PLAN
    assert dest.read_text() == "# plan\n"
    r2 = s.run("plan", "--name", GOOD_PLAN, "--from", s.put("plan.md", "# other\n"))
    assert r2.returncode == 2 and dest.read_text() == "# plan\n"


def test_plan_refuses_non_utf8_and_bad_name(tmp_path):
    s = _Sink(tmp_path)
    r = s.run("plan", "--name", GOOD_PLAN, "--from", s.put("plan.md", b"\xff\xfe\x00bad"))
    assert r.returncode == 2 and "UTF-8" in r.stderr
    r = s.run("plan", "--name", "plan.md", "--from", s.put("plan2.md", "# x\n"))
    assert r.returncode == 2 and "plan name" in r.stderr


# --- retention ------------------------------------------------------------------------


def _patch_file(s, name, age_days):
    d = s.claude / "schedules" / "patches"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("diff\n")
    t = time.time() - age_days * 86400
    os.utime(p, (t, t))
    return p


def test_patches_due_lists_only_own_old_patches(tmp_path):
    s = _Sink(tmp_path)
    _patch_file(s, "csa-11-20260801T000000Z.patch", 30)
    _patch_file(s, "csa-12-20260801T000000Z.patch", 30)
    _patch_file(s, "csa-13-20260920T000000Z.patch", 3)
    _patch_file(s, "agency-14-20260801T000000Z.patch", 30)
    r = s.run("patches-due")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"issues": [11, 12], "files": 2}


def test_reap_patches_deletes_only_old_closed_own_regular(tmp_path):
    s = _Sink(tmp_path)
    old_closed = _patch_file(s, "csa-11-20260801T000000Z.patch", 30)
    old_open = _patch_file(s, "csa-12-20260801T000000Z.patch", 30)
    young_closed = _patch_file(s, "csa-13-20260920T000000Z.patch", 3)
    other_slug = _patch_file(s, "agency-11-20260801T000000Z.patch", 30)
    target = tmp_path / "keepme"
    target.write_text("x")
    link = s.claude / "schedules" / "patches" / "csa-11-20260802T000000Z.patch"
    link.symlink_to(target)
    t = time.time() - 30 * 86400
    os.utime(link, (t, t), follow_symlinks=False)
    r = s.run("reap-patches", "--closed", "11,13")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["deleted"] == 1
    assert not old_closed.exists()
    assert old_open.exists() and young_closed.exists() and other_slug.exists()
    assert link.is_symlink() and target.exists()
    assert json.loads(s.audit.read_text().splitlines()[-1])["kind"] == "reap-patches"


def test_retention_floor_is_21_days(tmp_path):
    s = _Sink(tmp_path)
    assert s.run("reap-patches", "--closed", "11", "--days", "20").returncode == 2
    assert s.run("patches-due", "--days", "20").returncode == 2
    assert s.run("patches-due", "--days", "21").returncode == 0


# --- now --------------------------------------------------------------------------------


def test_now_reports_clock_and_elapsed(tmp_path):
    s = _Sink(tmp_path)
    start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=90)
    s.env["OVERSIGHT_WRAPPER_START_ISO"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = s.run("now")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert set(out) == {"now", "today", "elapsed_sec"}
    assert _ISO_Z.match(out["now"]) and out["today"] == out["now"][:10]
    assert 85 <= out["elapsed_sec"] <= 150
    assert not s.claude.exists(), "now is read-only"
