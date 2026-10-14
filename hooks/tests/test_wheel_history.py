"""Tests for hooks/wheel_history.py (WS14-S1 slice, item 1, paragraph 1b).

Two halves:
  - `slot_and_night()` boundary tests — pure function, no filesystem/env access.
  - `append` field-logic tests — invoke the real CLI as a subprocess, HOME redirected to a tmp dir
    per test (never the real ~/.claude).

Item 1c (`green_nights()`, the `streak` CLI, the auditor check) is NOT in scope here — this file
tests only what 1b builds.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys

import pytest

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - this machine's python3 is always 3.9+
    ZoneInfo = None

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(_HOOKS_DIR, "wheel_history.py")

sys.path.insert(0, _HOOKS_DIR)
import wheel_history  # noqa: E402


DENVER = ZoneInfo("America/Denver") if ZoneInfo else None


def _epoch_denver(year, month, day, hour, minute) -> float:
    """A local America/Denver wall-clock time, as a POSIX epoch float."""
    dt = datetime.datetime(year, month, day, hour, minute, tzinfo=DENVER)
    return dt.timestamp()


# ---------------------------------------------------------------------------
# slot_and_night boundaries
# ---------------------------------------------------------------------------


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
@pytest.mark.parametrize(
    "hour,minute,expected_slot,expected_night_offset_days",
    [
        (19, 59, "offschedule", None),
        (20, 0, "primary", 0),
        (23, 59, "primary", 0),
        (0, 0, "retry", -1),
        (7, 59, "retry", -1),
        (8, 0, "offschedule", None),
    ],
)
def test_slot_and_night_boundaries(hour, minute, expected_slot, expected_night_offset_days):
    epoch = _epoch_denver(2026, 9, 24, hour, minute)
    slot, night = wheel_history.slot_and_night(epoch, DENVER)
    assert slot == expected_slot
    if expected_night_offset_days is None:
        assert night is None
    else:
        expected_date = (
            datetime.date(2026, 9, 24) + datetime.timedelta(days=expected_night_offset_days)
        ).isoformat()
        assert night == expected_date


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
def test_slot_and_night_late_post_wake_fire_counts_as_retry_for_previous_night():
    """A late post-wake fire at 02:10 local (e.g. after a machine sleep past the 03:30 retry's own
    schedule) still lands in the retry window and counts for the PREVIOUS night, same as an
    on-time 03:30 retry would."""
    epoch = _epoch_denver(2026, 9, 24, 2, 10)
    slot, night = wheel_history.slot_and_night(epoch, DENVER)
    assert slot == "retry"
    assert night == "2026-09-23"


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
def test_slot_and_night_accepts_a_timezone_name_string():
    """Call sites (and this test file itself, for convenience) may pass a plain IANA zone name
    instead of constructing a ZoneInfo object themselves."""
    epoch = _epoch_denver(2026, 9, 24, 21, 0)
    slot, night = wheel_history.slot_and_night(epoch, "America/Denver")
    assert slot == "primary"
    assert night == "2026-09-24"


# ---------------------------------------------------------------------------
# append — subprocess-level field logic
# ---------------------------------------------------------------------------


class _History:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir(exist_ok=True)
        self.hb_dir = self.home / ".claude" / "schedules" / "heartbeats"
        self.hb_dir.mkdir(parents=True, exist_ok=True)
        self.env = dict(os.environ)
        self.env["HOME"] = str(self.home)
        # Scrub any wheel/oversight env a developer shell (or a stray /wheel session) might carry,
        # mirroring test_run_oversight_job.py's own _base_env() hygiene.
        for k in list(self.env):
            if k.startswith(("WHEEL_", "OVERSIGHT_")):
                del self.env[k]

    def write_heartbeat(self, job: str, **fields) -> "os.PathLike[str]":
        path = self.hb_dir / f"{job}.json"
        path.write_text(json.dumps(fields))
        return path

    def history_path(self, job: str):
        return self.hb_dir / "history" / f"{job}.jsonl"

    def history_lines(self, job: str) -> list[dict]:
        path = self.history_path(job)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def append(self, *, job: str, heartbeat=None, start_epoch="", start_iso="", extra_env=None):
        hb_path = heartbeat if heartbeat is not None else str(self.hb_dir / f"{job}.json")
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        argv = [
            sys.executable, _MODULE_PATH, "append",
            "--heartbeat", str(hb_path),
            "--job", job,
            "--start-epoch", str(start_epoch),
            "--start-iso", start_iso,
        ]
        return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=30)


def test_append_never_raises_on_missing_heartbeat_file(tmp_path):
    h = _History(tmp_path)
    proc = h.append(job="com.oversight.wheel.csa", heartbeat=str(tmp_path / "does-not-exist.json"))
    assert proc.returncode == 0
    assert h.history_lines("com.oversight.wheel.csa") == []


def test_append_never_raises_with_empty_heartbeat_and_job(tmp_path):
    """Mirrors the wrapper's own guard: an empty --heartbeat/--job (the shape a call with
    ${HEARTBEAT_FILE:-}/${JOB_LABEL:-} both unset would produce) writes nothing and raises no
    error -- exit 0 either way."""
    h = _History(tmp_path)
    argv = [sys.executable, _MODULE_PATH, "append", "--heartbeat", "", "--job", ""]
    proc = subprocess.run(argv, env=h.env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0


def test_append_writes_one_line_carrying_the_heartbeats_own_keys(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(
        job,
        started_at="2026-09-24T04:10:00Z",
        finished_at="2026-09-24T04:15:00Z",
        exit=0,
        status="ok",
        triage={"total": 3, "ok": 3},
        summary="did the job",
    )
    proc = h.append(job=job, start_epoch=_epoch_denver(2026, 9, 24, 22, 10) if DENVER else 0,
                     start_iso="2026-09-24T04:10:00Z", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    lines = h.history_lines(job)
    assert len(lines) == 1
    line = lines[0]
    assert line["status"] == "ok"
    assert line["exit"] == 0
    assert line["triage"] == {"total": 3, "ok": 3}
    assert line["summary"] == "did the job"


def test_append_creates_the_history_dir_if_missing(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="x", finished_at="y", exit=0, status="ok")
    assert not h.history_path(job).parent.exists()
    proc = h.append(job=job)
    assert proc.returncode == 0, proc.stderr
    assert h.history_path(job).parent.is_dir()


def test_append_is_append_only_not_overwrite(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    h.append(job=job)
    h.write_heartbeat(job, started_at="c", finished_at="d", exit=1, status="failed")
    h.append(job=job)
    lines = h.history_lines(job)
    assert len(lines) == 2
    assert lines[0]["status"] == "ok"
    assert lines[1]["status"] == "failed"


def test_append_manual_wheel_label_writes_its_own_file_and_is_labelled_manual(tmp_path):
    h = _History(tmp_path)
    job = "manual-wheel-csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a")
    assert proc.returncode == 0, proc.stderr
    lines = h.history_lines(job)
    assert len(lines) == 1
    assert lines[0]["launch"] == "manual"
    # its own file, distinct from the scheduled label's history file
    assert not h.history_path("com.oversight.wheel.csa").exists()


def test_append_scheduled_wheel_label_is_labelled_scheduled(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a")
    assert proc.returncode == 0, proc.stderr
    assert h.history_lines(job)[0]["launch"] == "scheduled"


def test_append_scheduled_non_wheel_job_is_also_labelled_scheduled(tmp_path):
    """A scheduled non-wheel job (e.g. com.oversight.csa.testarch) is not a `manual-*` label, so
    it gets launch: "scheduled" too -- the slice's own wording ("taken from the label, so
    scheduled non-wheel jobs are labelled correctly")."""
    h = _History(tmp_path)
    job = "com.oversight.csa.testarch"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a")
    assert proc.returncode == 0, proc.stderr
    assert h.history_lines(job)[0]["launch"] == "scheduled"


def test_append_non_wheel_job_never_gets_stale_slot_or_night_or_ready_json_mtime(tmp_path):
    """`stale` and `ready_json_mtime` apply to wheel labels only; slot/night apply to scheduled
    wheel labels only. A non-wheel job's line carries slot/night as null and no stale/
    ready_json_mtime keys at all."""
    h = _History(tmp_path)
    job = "com.oversight.csa.testarch"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a", extra_env={"WHEEL_SLUG": "csa"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    assert "stale" not in line
    assert "ready_json_mtime" not in line
    assert line["slot"] is None
    assert line["night"] is None


def test_append_stale_true_when_started_at_differs_from_start_iso(tmp_path):
    """A wheel label whose on-disk heartbeat `started_at` does not match this run's own
    --start-iso means a DIFFERENT run's heartbeat was read (a crashed write left the previous
    run's file) -- stale: true, and (per the green-night rule 1c will build) such a line must
    never count, though that counting logic is out of scope for this file."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="2026-09-20T04:10:00Z", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="2026-09-24T04:10:00Z")
    assert proc.returncode == 0, proc.stderr
    assert h.history_lines(job)[0]["stale"] is True


def test_append_stale_false_when_started_at_matches_start_iso(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="2026-09-24T04:10:00Z", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="2026-09-24T04:10:00Z")
    assert proc.returncode == 0, proc.stderr
    assert h.history_lines(job)[0]["stale"] is False


def test_append_ready_json_mtime_present_for_wheel_job_with_wheel_slug_set(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    ready_dir = h.home / ".claude" / "telemetry" / "wheel" / "csa"
    ready_dir.mkdir(parents=True, exist_ok=True)
    ready_path = ready_dir / "ready.json"
    ready_path.write_text("{}")
    mtime = 1_800_000_000.0  # a fixed, known mtime
    os.utime(ready_path, (mtime, mtime))
    proc = h.append(job=job, start_iso="a", extra_env={"WHEEL_SLUG": "csa"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    expected = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert line["ready_json_mtime"] == expected


def test_append_ready_json_mtime_absent_when_wheel_slug_unset(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a")  # no WHEEL_SLUG in env
    assert proc.returncode == 0, proc.stderr
    assert "ready_json_mtime" not in h.history_lines(job)[0]


def test_append_ready_json_mtime_absent_when_file_missing(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a", extra_env={"WHEEL_SLUG": "csa"})
    assert proc.returncode == 0, proc.stderr
    assert "ready_json_mtime" not in h.history_lines(job)[0]


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
def test_append_slot_and_night_populated_for_scheduled_wheel_label(tmp_path):
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    epoch = _epoch_denver(2026, 9, 24, 22, 10)
    proc = h.append(job=job, start_epoch=epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    assert line["slot"] == "primary"
    assert line["night"] == "2026-09-24"


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
def test_append_manual_wheel_label_never_gets_slot_or_night(tmp_path):
    """A manual-wheel-<slug> label (from /wheel) is never IS_SCHEDULED_WHEEL_JOB, so slot/night
    stay null for it even at a timestamp that would otherwise be "primary"."""
    h = _History(tmp_path)
    job = "manual-wheel-csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    epoch = _epoch_denver(2026, 9, 24, 22, 10)
    proc = h.append(job=job, start_epoch=epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    assert line["slot"] is None
    assert line["night"] is None


@pytest.mark.skipif(DENVER is None, reason="zoneinfo unavailable")
def test_append_offschedule_start_yields_offschedule_slot_and_null_night(tmp_path):
    """Blocker 1 (review round): "offschedule" is a recorded slot value, not a reason to null it
    out -- the slice's own wording is "anything else is offschedule", i.e. offschedule IS one of
    the three possible slot values. Only `night` is null for it."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    epoch = _epoch_denver(2026, 9, 24, 12, 0)  # noon local: offschedule
    proc = h.append(job=job, start_epoch=epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    assert line["slot"] == "offschedule"
    assert line["night"] is None


def test_append_dst_uses_the_start_epochs_own_local_offset_not_todays(tmp_path):
    """Finding 4 (review round): the local UTC offset must be derived from --start-epoch itself,
    never from "now" -- America/Denver is UTC-6 (MDT) in July and UTC-7 (MST) in December, so the
    SAME wall-clock hour in each month falls at a different UTC instant. A 22:10 MDT July start
    and a 22:10 MST December start must both classify as "primary" for their OWN local date (never
    shifted by a full hour into the wrong slot the way a fixed "now" offset could), and a 07:30 MST
    December start must be "retry" for the PREVIOUS local date."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"

    def _epoch_denver_naive(year, month, day, hour, minute) -> float:
        """A LOCAL America/Denver wall-clock time turned into an epoch by asking the OS itself
        (via a subprocess with TZ=America/Denver) to interpret the naive struct as local time --
        this must not use zoneinfo, since the whole point is exercising the C library's own DST
        rules exactly as _local_offset_tz's `datetime.fromtimestamp(...).astimezone()` does."""
        script = (
            "import calendar, time, os; time.tzset(); "
            f"print(time.mktime(({year}, {month}, {day}, {hour}, {minute}, 0, 0, 0, -1)))"
        )
        env = dict(h.env)
        env["TZ"] = "America/Denver"
        out = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return float(out.stdout.strip())

    # July: MDT, UTC-6. 22:10 local is primary, night = same date.
    july_epoch = _epoch_denver_naive(2026, 7, 15, 22, 10)
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_epoch=july_epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[-1]
    assert line["slot"] == "primary"
    assert line["night"] == "2026-07-15"

    # N1 (1b review nit, WS14-S1 item 1c, GH #4767): a July 20:30-local case too, right at the
    # PRIMARY window's own lower boundary -- the earlier July case above (22:10) sits mid-window
    # and would not by itself catch a "now"-offset bug that only shifts the computed time by a
    # partial hour near a boundary; 20:30 in MDT (UTC-6) is exactly the shape a wrong summer-vs-
    # winter offset could shift across the [20:00, 24:00) edge into "offschedule".
    july_edge_epoch = _epoch_denver_naive(2026, 7, 15, 20, 30)
    proc = h.append(job=job, start_epoch=july_edge_epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[-1]
    assert line["slot"] == "primary"
    assert line["night"] == "2026-07-15"

    # December: MST, UTC-7. 22:10 local is still primary, night = same date -- proving the offset
    # was re-derived for December's own rules, not carried over from July's -6.
    december_epoch = _epoch_denver_naive(2026, 12, 15, 22, 10)
    proc = h.append(job=job, start_epoch=december_epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[-1]
    assert line["slot"] == "primary"
    assert line["night"] == "2026-12-15"

    # A 07:30 MST December start is retry, for the PREVIOUS local date.
    december_retry_epoch = _epoch_denver_naive(2026, 12, 15, 7, 30)
    proc = h.append(job=job, start_epoch=december_retry_epoch, start_iso="a", extra_env={"TZ": "America/Denver"})
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[-1]
    assert line["slot"] == "retry"
    assert line["night"] == "2026-12-14"


def test_append_never_raises_on_malformed_start_epoch(tmp_path):
    """A non-numeric --start-epoch (should never happen in production, since the wrapper always
    passes ${WRAPPER_START_EPOCH:-}, but this must degrade to null slot/night, never crash)."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    argv = [
        sys.executable, _MODULE_PATH, "append",
        "--heartbeat", str(h.hb_dir / f"{job}.json"),
        "--job", job,
        "--start-epoch", "not-a-number",
        "--start-iso", "a",
    ]
    proc = subprocess.run(argv, env=h.env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    line = h.history_lines(job)[0]
    assert line["slot"] is None
    assert line["night"] is None


def test_append_torn_previous_line_gets_a_leading_newline_not_merged(tmp_path):
    """Finding 9 (review round): if the history file already ends WITHOUT a trailing newline (a
    previous appender was killed mid-write -- exactly the sigkills-self failure mode the wrapper
    tests exercise), the next append must prefix its own record with a leading newline, so the
    torn previous bytes can never merge with this record's JSON on the same physical line."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    history_path = h.history_path(job)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text('{"torn": "line with no trailing newline"}')  # deliberately no \n
    h.write_heartbeat(job, started_at="a", finished_at="b", exit=0, status="ok")
    proc = h.append(job=job, start_iso="a")
    assert proc.returncode == 0, proc.stderr
    raw = history_path.read_text()
    lines = [line for line in raw.splitlines() if line.strip()]
    assert len(lines) == 2, raw
    # Each line parses independently -- the torn line was never silently merged with the new one.
    torn = json.loads(lines[0])
    assert torn == {"torn": "line with no trailing newline"}
    appended = json.loads(lines[1])
    assert appended["status"] == "ok"


def test_append_concurrent_large_appends_never_interleave(tmp_path):
    """Finding 9 (review round): the single-os.write, O_APPEND design must hold under genuine
    concurrent writers -- two separate processes hammering the SAME history file with LARGE
    payloads (big enough that a naive multi-write approach would very likely interleave) must
    never produce a corrupted or merged line; every line must parse as valid, standalone JSON,
    and the total line count must equal the total number of appends issued."""
    h = _History(tmp_path)
    job = "com.oversight.wheel.csa"
    big = "x" * 70000
    per_writer = 30
    writers = 2

    def _writer_script(tag: str) -> str:
        return (
            "import subprocess, sys\n"
            f"for i in range({per_writer}):\n"
            f"    subprocess.run([sys.executable, {_MODULE_PATH!r}, 'append', "
            f"'--heartbeat', sys.argv[1], '--job', {job!r}, '--start-iso', 'z'])\n"
        )

    h.write_heartbeat(job, started_at="z", finished_at="b", exit=0, status="ok", summary=big)
    procs = [
        subprocess.Popen([sys.executable, "-c", _writer_script(tag), str(h.hb_dir / f"{job}.json")], env=h.env)
        for tag in ("a", "b")[:writers]
    ]
    for p in procs:
        assert p.wait(timeout=60) == 0

    lines = h.history_lines(job)
    assert len(lines) == per_writer * writers, len(lines)
    for line in lines:
        assert line["status"] == "ok"
        assert line["summary"] == big


# ---------------------------------------------------------------------------
# green_nights / streak (item 1c)
# ---------------------------------------------------------------------------

import plistlib  # noqa: E402


_CSA_WHEEL_PRIMARY_WEEKDAYS = (1, 2, 3, 4, 5)  # Mon-Fri, launchd Weekday convention
_CSA_WHEEL_RETRY_WEEKDAYS = (2, 3, 4, 5, 6)  # Tue-Sat 03:30, covers the preceding Mon-Fri night


def _write_csa_wheel_plist(launch_agents_dir, job="com.oversight.wheel.csa"):
    """A scratch plist mirroring the REAL com.oversight.wheel.csa.plist's own
    StartCalendarInterval shape: Mon-Fri 22:10 primary, Tue-Sat 03:30 retry."""
    interval = [{"Weekday": w, "Hour": 22, "Minute": 10} for w in _CSA_WHEEL_PRIMARY_WEEKDAYS]
    interval += [{"Weekday": w, "Hour": 3, "Minute": 30} for w in _CSA_WHEEL_RETRY_WEEKDAYS]
    path = os.path.join(launch_agents_dir, f"{job}.plist")
    with open(path, "wb") as fh:
        plistlib.dump({"StartCalendarInterval": interval}, fh)
    return path


class _GreenNights:
    """Scratch history_dir + launch_agents_dir fixture for green_nights()/streak(), independent of
    _History above (that fixture drives the `append` subprocess; this one drives green_nights()
    directly as a library call, and writes plist/history fixtures by hand)."""

    def __init__(self, tmp_path, job="com.oversight.wheel.csa"):
        self.job = job
        self.history_dir = tmp_path / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.launch_agents_dir = tmp_path / "LaunchAgents"
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        _write_csa_wheel_plist(str(self.launch_agents_dir), job)

    def write_lines(self, *records):
        path = self.history_dir / f"{self.job}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

    def append_raw_line(self, raw_text: str):
        """For a malformed-line test: writes exactly `raw_text` (already newline-free) as a line."""
        path = self.history_dir / f"{self.job}.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(raw_text + "\n")

    def evaluate(
        self,
        since: "datetime.date",
        today: "datetime.date | None" = None,
        now: "datetime.datetime | None" = None,
    ):
        return wheel_history.green_nights(
            self.job, since, history_dir=str(self.history_dir),
            launch_agents_dir=str(self.launch_agents_dir), today=today, now=now,
        )


def _ok_record(night, *, slot="primary", launch="scheduled", triage_total=5, triage_ok=5, **overrides):
    record = {
        "launch": launch,
        "status": "ok",
        "exit": 0,
        "slot": slot,
        "night": night,
        "triage": {"triage_batches": {"total": triage_total, "ok": triage_ok}},
    }
    record.update(overrides)
    return record


def test_green_nights_skip_only_night_is_not_green(tmp_path):
    """A second-slot-skip record (wrapper_skip present) never counts, per 1b's own contract."""
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)  # a Monday, a scheduled primary night
    g.write_lines({
        "launch": "scheduled", "status": "skipped-quota", "exit": 0,
        "slot": "primary", "night": night.isoformat(), "wrapper_skip": "second-slot",
    })
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"] == [{"night": "2026-09-21", "green": False, "pending": False, "slot": None, "reason": "not-green"}]
    assert result["streak"] == 0


def test_green_nights_line_before_since_is_ignored(tmp_path):
    """A green line dated before `since` appears in no night, raises no problem, and never
    extends the streak -- the count starts at `since` (S1-A2: from the first scheduled night
    after the history commit)."""
    g = _GreenNights(tmp_path)
    before = datetime.date(2026, 9, 25)  # Friday, before since
    since = datetime.date(2026, 9, 28)  # Monday
    g.write_lines(_ok_record(before.isoformat()), _ok_record(since.isoformat()))
    result = g.evaluate(since=since, today=since, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert [n["night"] for n in result["nights"]] == ["2026-09-28"]
    assert result["streak"] == 1
    assert not any("2026-09-25" in str(p) for p in result.get("problems", []))


def test_green_nights_stale_line_is_not_green(tmp_path):
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    g.write_lines(_ok_record(night.isoformat(), stale=True))
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"][0]["green"] is False
    assert result["streak"] == 0


def test_green_nights_triage_not_run_is_not_green(tmp_path):
    """An ok record whose triage.status is 'not-run' is not green -- the exact key a real run
    never writes (S1-A1's own resolved blocker), but a manufactured/legacy record might."""
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    record = _ok_record(night.isoformat())
    record["triage"] = {"status": "not-run"}
    g.write_lines(record)
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"][0]["green"] is False


def test_green_nights_primary_ok_with_triage_is_green(tmp_path):
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    g.write_lines(_ok_record(night.isoformat()))
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"] == [{"night": "2026-09-21", "green": True, "pending": False, "slot": "primary", "reason": None}]
    assert result["streak"] == 1


def test_green_nights_retry_slot_ok_is_green_and_labelled(tmp_path):
    """A retry-slot record whose own `night` field already names the primary night it covers
    (1b's own append-time contract) counts as green for that night, labelled `slot: retry`."""
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    g.write_lines(_ok_record(night.isoformat(), slot="retry"))
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"] == [{"night": "2026-09-21", "green": True, "pending": False, "slot": "retry", "reason": None}]
    assert result["streak"] == 1


def test_green_nights_manual_file_never_counts(tmp_path):
    """green_nights() is always called with the SCHEDULED label, so a manual-wheel-<slug> history
    file (a separate file per 1b) is never even read -- a manual record placed in the scheduled
    job's OWN history file (hypothetically, if mislabelled) would still need launch=="scheduled" to
    count; this test proves the manual `launch` value itself is excluded by the green rule."""
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    g.write_lines(_ok_record(night.isoformat(), launch="manual"))
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"][0]["green"] is False


def test_green_nights_ok_record_with_no_triage_key_is_reported_not_green(tmp_path):
    g = _GreenNights(tmp_path)
    night = datetime.date(2026, 9, 21)
    record = {
        "launch": "scheduled", "status": "ok", "exit": 0, "slot": "primary", "night": night.isoformat(),
    }
    g.write_lines(record)
    result = g.evaluate(since=night, today=night, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert result["nights"][0]["green"] is False
    assert any("no `triage` key" in p for p in result["problems"])


def test_green_nights_friday_to_monday_is_consecutive(tmp_path):
    """Sat/Sun are not scheduled nights for the CSA wheel (Mon-Fri primary only), so a green Friday
    followed by a green Monday is a streak of 2, not broken by the weekend gap."""
    g = _GreenNights(tmp_path)
    friday = datetime.date(2026, 9, 25)
    monday = datetime.date(2026, 9, 28)
    g.write_lines(_ok_record(friday.isoformat()), _ok_record(monday.isoformat()))
    result = g.evaluate(since=friday, today=monday, now=datetime.datetime(2027, 1, 1, 12, 0))
    nights = [n["night"] for n in result["nights"]]
    assert nights == ["2026-09-25", "2026-09-28"]  # Sat/Sun never appear
    assert all(n["green"] for n in result["nights"])
    assert result["streak"] == 2


def test_green_nights_scheduled_night_with_no_line_breaks_the_streak_and_is_reported(tmp_path):
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 21)
    wednesday = datetime.date(2026, 9, 23)
    g.write_lines(_ok_record(monday.isoformat()), _ok_record(wednesday.isoformat()))
    # Tuesday (2026-09-22) has no line at all.
    result = g.evaluate(since=monday, today=wednesday, now=datetime.datetime(2027, 1, 1, 12, 0))
    by_night = {n["night"]: n for n in result["nights"]}
    assert by_night["2026-09-21"]["green"] is True
    assert by_night["2026-09-22"]["green"] is False
    assert by_night["2026-09-23"]["green"] is True
    # The trailing streak only counts back to the most recent break -- Wednesday alone.
    assert result["streak"] == 1
    assert any("no history line for scheduled night 2026-09-22" in p for p in result["problems"])


def test_green_nights_malformed_line_is_reported_as_a_problem(tmp_path):
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 21)
    g.append_raw_line("{not valid json")
    result = g.evaluate(since=monday, today=monday, now=datetime.datetime(2027, 1, 1, 12, 0))
    assert any("malformed JSON line" in p for p in result["problems"])
    # The night itself still has no valid record, so it is also reported missing and not green.
    assert result["nights"][0]["green"] is False


def test_green_nights_schedule_unknown_when_plist_missing(tmp_path):
    """No plist at all -- a job label green_nights() has never heard of -- degrades to
    schedule_unknown, never a guess, and reports zero nights."""
    tmp = tmp_path / "unknown-job"
    tmp.mkdir()
    history_dir = tmp / "history"
    history_dir.mkdir()
    launch_agents_dir = tmp / "LaunchAgents"
    launch_agents_dir.mkdir()
    result = wheel_history.green_nights(
        "com.oversight.wheel.doesnotexist", datetime.date(2026, 9, 21),
        history_dir=str(history_dir), launch_agents_dir=str(launch_agents_dir),
        today=datetime.date(2026, 9, 21),
    )
    assert result["schedule_unknown"] is True
    assert result["nights"] == []
    assert result["streak"] == 0


def test_green_nights_now_pins_completeness_mon_tue_green_wed_pending(tmp_path):
    """The coordinator's own worked example (B1 fix): Mon 09-28 and Tue 09-29 green, read at
    Wed 09-30 12:00 -- both Mon/Tue are COMPLETE (their own retry windows, closing at 08:00 the
    NEXT day, have long passed by Wed noon) and green, so streak == 2; Wed itself is not yet
    complete (its own retry window doesn't close until Thu 08:00) and is reported pending -- never
    counted as a break."""
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 28)
    tuesday = datetime.date(2026, 9, 29)
    wednesday = datetime.date(2026, 9, 30)
    g.write_lines(_ok_record(monday.isoformat()), _ok_record(tuesday.isoformat()))
    result = g.evaluate(since=monday, today=wednesday, now=datetime.datetime(2026, 9, 30, 12, 0))
    by_night = {n["night"]: n for n in result["nights"]}
    assert by_night["2026-09-28"] == {"night": "2026-09-28", "green": True, "pending": False, "slot": "primary", "reason": None}
    assert by_night["2026-09-29"] == {"night": "2026-09-29", "green": True, "pending": False, "slot": "primary", "reason": None}
    assert by_night["2026-09-30"]["pending"] is True
    assert by_night["2026-09-30"]["green"] is False
    assert result["streak"] == 2
    assert result["problems"] == []  # the pending night contributes NO "no history line" problem


def test_green_nights_now_pending_night_with_missing_line_breaks_streak_once_complete(tmp_path):
    """The coordinator's second worked example: Tuesday has no line at all; reading at
    Wed 09-30 09:00 (AFTER Tuesday's own retry window closed at 08:00) means Tuesday is COMPLETE
    and missing -> not green -> breaks the streak. Wednesday itself, read at 09:00 the SAME day, is
    still pending (its own retry window doesn't close until Thursday 08:00)."""
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 28)
    wednesday = datetime.date(2026, 9, 30)
    g.write_lines(_ok_record(monday.isoformat()))  # Tuesday (2026-09-29): no line at all
    result = g.evaluate(since=monday, today=wednesday, now=datetime.datetime(2026, 9, 30, 9, 0))
    by_night = {n["night"]: n for n in result["nights"]}
    assert by_night["2026-09-28"]["green"] is True
    assert by_night["2026-09-29"] == {"night": "2026-09-29", "green": False, "pending": False, "slot": None, "reason": "no-line"}
    assert by_night["2026-09-30"]["pending"] is True
    # Walking backward: Wed is pending (skipped), Tue is complete+not-green -> streak breaks at 0.
    assert result["streak"] == 0
    assert any("no history line for scheduled night 2026-09-29" in p for p in result["problems"])
    # The pending Wednesday itself contributes no problem even though it has no line yet either.
    assert not any("2026-09-30" in p for p in result["problems"])


def test_green_nights_pending_night_before_retry_cutoff_same_day(tmp_path):
    """A night is still pending even LATE the same calendar day (e.g. 23:00), since its own retry
    window only closes at 08:00 the FOLLOWING day -- proves the cutoff is genuinely `night + 1 day
    at 08:00`, not simply `night's own date has passed` or `next calendar day has started`."""
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 28)
    g.write_lines()  # no lines at all
    result = g.evaluate(since=monday, today=monday, now=datetime.datetime(2026, 9, 28, 23, 0))
    assert result["nights"] == [{"night": "2026-09-28", "green": False, "pending": True, "slot": None, "reason": "pending"}]
    assert result["problems"] == []
    assert result["streak"] == 0


def test_green_nights_night_becomes_complete_exactly_at_the_08_00_cutoff(tmp_path):
    """Boundary: `night + 1 day` at exactly 08:00:00 local is COMPLETE (the coordinator's own
    wording, `<=`), not pending; 07:59:59 the same morning is still pending."""
    g = _GreenNights(tmp_path)
    monday = datetime.date(2026, 9, 28)
    g.write_lines(_ok_record(monday.isoformat()))
    still_pending = g.evaluate(since=monday, today=monday, now=datetime.datetime(2026, 9, 29, 7, 59, 59))
    assert still_pending["nights"][0]["pending"] is True
    now_complete = g.evaluate(since=monday, today=monday, now=datetime.datetime(2026, 9, 29, 8, 0, 0))
    assert now_complete["nights"][0]["pending"] is False
    assert now_complete["nights"][0]["green"] is True
    assert now_complete["streak"] == 1


def test_streak_cli_prints_verdicts_and_exits_zero(tmp_path, capsys, monkeypatch):
    """The `streak --job ... --since ...` CLI prints each night's verdict (including PENDING) and
    the streak, and exits 0 -- made fully deterministic (no reliance on the real clock) by
    monkeypatching `green_nights` itself with a canned, fixed result, then asserting `do_streak`'s
    OWN print-formatting against that exact canned shape."""
    import argparse as _argparse

    canned = {
        "job": "com.oversight.wheel.csa",
        "since": "2026-09-28",
        "nights": [
            {"night": "2026-09-28", "green": True, "pending": False, "slot": "primary", "reason": None},
            {"night": "2026-09-29", "green": False, "pending": False, "slot": None, "reason": "no-line"},
            {"night": "2026-09-30", "green": False, "pending": True, "slot": None, "reason": "pending"},
        ],
        "streak": 0,
        "problems": ["no history line for scheduled night 2026-09-29 (com.oversight.wheel.csa)"],
        "schedule_unknown": False,
    }
    calls = []

    def _fake_green_nights(job, since_date, **kwargs):
        calls.append((job, since_date, kwargs))
        return canned

    monkeypatch.setattr(wheel_history, "green_nights", _fake_green_nights)
    rc = wheel_history.do_streak(_argparse.Namespace(job="com.oversight.wheel.csa", since="2026-09-28"))
    assert rc == 0
    assert len(calls) == 1
    assert calls[0][0] == "com.oversight.wheel.csa"
    assert calls[0][1] == datetime.date(2026, 9, 28)

    out = capsys.readouterr().out
    assert "job: com.oversight.wheel.csa" in out
    assert "since: 2026-09-28" in out
    assert "2026-09-28: GREEN (primary)" in out
    assert "2026-09-29: not green [no-line]" in out
    assert "2026-09-30: PENDING (retry window not yet closed)" in out
    assert "streak: 0" in out
    assert "no history line for scheduled night 2026-09-29" in out


def test_streak_cli_bad_since_never_raises(tmp_path):
    proc = subprocess.run(
        [sys.executable, _MODULE_PATH, "streak", "--job", "com.oversight.wheel.csa", "--since", "not-a-date"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0
