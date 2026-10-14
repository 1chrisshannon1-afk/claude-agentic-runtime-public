#!/usr/bin/env python3
"""wheel_history.py — per-night wrapper history for run_oversight_job.sh (WS14-S1, item 1, 1b+1c).

Item 1b (#4767 / WS14-S1 slice, section "Item 1", paragraph 1b) is the `append` subcommand:
writing one history line per wrapper exit. Item 1c (paragraph 1c) is built HERE TOO: the
`green_nights()` evaluator and the `streak` CLI. The auditor check (`wheel-grant-contradiction`)
is also item 1c, but lives in `heartbeat_audit.py`, not this file.

WHAT WRITES A LINE. `run_oversight_job.sh`'s unified EXIT trap (`_wrapper_exit_cleanup`) calls
this script's `append` subcommand on every exit path — the kill switches, the wheel-slug-missing
guard, the lock refusals, the second-slot skip, the launch-context refusal, the quota/throttle
pre-flight skips, and the ordinary post-CLI finish — because they all `exit` through the same
trap. The call is guarded with `${HEARTBEAT_FILE:-}`/`${JOB_LABEL:-}` and always `|| true`: this
module never raises, and a failure here never changes the wrapper's own exit code.

ONE LINE PER WRAPPER EXIT, appended (never overwritten) to:

    <dirname(heartbeat)>/history/<job>.jsonl

The line is the heartbeat's own JSON object (job, started_at, finished_at, exit, cadence, status,
summary, and whatever else the heartbeat carries — `triage`, `hard_stop`, `wrapper_skip`, etc. —
so 1c's evaluator can read `status`/`exit`/`triage`/`wrapper_skip` straight off a history line
without a second lookup), plus these wrapper-added fields:

  launch              "manual" for a `manual-*` job label, "scheduled" for anything else — taken
                       from the label, so a scheduled non-wheel job (e.g. com.oversight.csa.daily)
                       is labelled "scheduled" too, not just the two wheel labels.
  stale               True, for WHEEL LABELS ONLY (com.oversight.wheel.* or manual-wheel-*), when
                       the heartbeat's own `started_at` does not match this run's `--start-iso`.
                       That mismatch means the heartbeat on disk was left by a DIFFERENT run (a
                       crashed write that skipped the trap, or one that reused a stale file before
                       this run's own START stamp landed) — never this run's own outcome. Absent
                       (not written at all) for a non-wheel label, since only a wheel session's own
                       `started_at` is written by this same wrapper machinery in the first place.
  ready_json_mtime    For wheel jobs only: the mtime (ISO-8601 UTC) of
                       ~/.claude/telemetry/wheel/$WHEEL_SLUG/ready.json, read via the inherited
                       WHEEL_SLUG env var. Absent if WHEEL_SLUG is unset or the file does not exist.
  slot                "primary" | "retry" | "offschedule" | None. Computed by `slot_and_night()`
                       from --start-epoch and the LOCAL timezone, but ONLY for a genuinely scheduled
                       wheel job label (com.oversight.wheel.*) — every other label (manual-wheel-*,
                       or any non-wheel job) gets slot=None, night=None.
  night               The scheduled night (YYYY-MM-DD, local calendar date) this run counts
                       against, or None. A "primary" run's night is its own local date; a "retry"
                       run's night is the PREVIOUS local date (it covers the primary slot that
                       preceded it). "offschedule" and None both carry night=None.

ITEM 1c (this revision, WS14-S1, GH #4767): `green_nights()` and the `streak` CLI. They read the
history files 1b writes (never write to them) and decide, per scheduled night, whether that night
was "green" by the rule below. See each function's own docstring for the exact rule.

Style matches wheel_sink.py: stdlib only, argparse, a never-raise top-level main().
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

try:
    from zoneinfo import ZoneInfo  # Python 3.9+, stdlib
except ImportError:  # pragma: no cover - this machine's python3 is always 3.9+
    ZoneInfo = None  # type: ignore[assignment,misc]

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)


# ---------------------------------------------------------------------------
# slot_and_night — pure function, no filesystem/env access
# ---------------------------------------------------------------------------


def slot_and_night(start_epoch: float, tz: "datetime.tzinfo | str") -> tuple[str, str | None]:
    """Classifies a wrapper start time into a (slot, night) pair.

    `tz` may be a `datetime.tzinfo` (e.g. `zoneinfo.ZoneInfo("America/Denver")`) or, for
    convenience at call sites and in tests, a plain IANA zone name string — resolved via
    `zoneinfo.ZoneInfo` here so callers never need their own import.

    Rule (slice text, item 1, paragraph 1b):
      - local time in [20:00, 24:00)  -> ("primary", that local date)
      - local time in [00:00, 08:00)  -> ("retry", the PREVIOUS local date)
      - anything else                 -> ("offschedule", None)

    Boundaries are half-open on the low end, per the slice's own boundary list (19:59 is
    offschedule, 20:00 is primary; 23:59 is primary, 00:00 is retry; 07:59 is retry, 08:00 is
    offschedule). A late post-wake fire (e.g. 02:10 local, after a machine sleep) still lands in
    the retry window and counts for the PREVIOUS night, exactly like an on-time 03:30 retry would.
    """
    if isinstance(tz, str):
        if ZoneInfo is None:  # pragma: no cover - unreachable on this machine's python3
            raise RuntimeError("zoneinfo is unavailable; pass a datetime.tzinfo instead of a name")
        tz = ZoneInfo(tz)
    local = datetime.datetime.fromtimestamp(start_epoch, tz=tz)
    hour = local.hour
    date_str = local.date().isoformat()
    if 20 <= hour < 24:
        return "primary", date_str
    if 0 <= hour < 8:
        previous = (local.date() - datetime.timedelta(days=1)).isoformat()
        return "retry", previous
    return "offschedule", None


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


def _local_offset_tz(start_epoch: float) -> datetime.tzinfo:
    """The local UTC offset AT THE GIVEN EPOCH, as an aware (fixed-offset) tzinfo.

    Finding 4 (review round): `datetime.now().astimezone().tzinfo` derives the offset from the
    CURRENT moment, not from `start_epoch` — wrong across a DST transition, since the local
    UTC offset for a July epoch and a December epoch differ (e.g. America/Denver is UTC-6 in
    July, UTC-7 in December). `datetime.fromtimestamp(start_epoch).astimezone()` instead
    interprets `start_epoch` as a naive local timestamp using the system's OWN zone rules for
    THAT moment, then attaches the correct aware offset for it — mirroring
    heartbeat_audit.py's own local-time contract, per the slice's item 1c note (1b only needs
    the same tz source, not that module itself)."""
    return datetime.datetime.fromtimestamp(start_epoch).astimezone().tzinfo


def _read_heartbeat(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _ready_json_mtime(home: str, wheel_slug: str) -> str | None:
    path = os.path.join(home, ".claude", "telemetry", "wheel", wheel_slug, "ready.json")
    try:
        st = os.stat(path)
    except OSError:
        return None
    dt = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_wheel_label(job: str) -> bool:
    return job.startswith("com.oversight.wheel.") or job.startswith("manual-wheel-")


def _is_scheduled_wheel_label(job: str) -> bool:
    return job.startswith("com.oversight.wheel.")


def do_append(args: argparse.Namespace) -> int:
    heartbeat = args.heartbeat
    job = args.job
    if not heartbeat or not job:
        # Guarded at the wrapper call site too (${HEARTBEAT_FILE:-}/${JOB_LABEL:-}), but this
        # module never trusts its caller alone: an empty value here means there is nothing
        # sensible to append (no file to read, no job to label the line with).
        sys.stderr.write("wheel_history: append: --heartbeat and --job are both required; nothing appended\n")
        return 0

    data = _read_heartbeat(heartbeat)
    if data is None:
        sys.stderr.write(f"wheel_history: append: could not read/parse heartbeat {heartbeat!r}; nothing appended\n")
        return 0

    record = dict(data)
    record["launch"] = "manual" if job.startswith("manual-") else "scheduled"

    if _is_wheel_label(job):
        start_iso = args.start_iso or ""
        heartbeat_started = data.get("started_at")
        record["stale"] = not (
            isinstance(heartbeat_started, str) and start_iso and heartbeat_started == start_iso
        )
        wheel_slug = os.environ.get("WHEEL_SLUG", "")
        if wheel_slug:
            home = os.environ.get("HOME", "")
            if home:
                mtime = _ready_json_mtime(home, wheel_slug)
                if mtime is not None:
                    record["ready_json_mtime"] = mtime

    slot: str | None = None
    night: str | None = None
    if _is_scheduled_wheel_label(job) and args.start_epoch:
        try:
            start_epoch = float(args.start_epoch)
        except ValueError:
            start_epoch = None
        if start_epoch is not None:
            try:
                computed_slot, computed_night = slot_and_night(start_epoch, _local_offset_tz(start_epoch))
            except Exception as exc:  # never raise out of append — record nothing rather than crash
                sys.stderr.write(f"wheel_history: append: slot_and_night failed ({exc}); slot/night left null\n")
            else:
                # Blocker 1 (review round): record the computed slot UNCONDITIONALLY, including
                # "offschedule" — the slice says "anything else is offschedule", i.e. offschedule
                # IS a valid recorded slot value, not a reason to null it out. Only `night` is None
                # for offschedule, and that already comes straight from slot_and_night() itself.
                slot, night = computed_slot, computed_night
    record["slot"] = slot
    record["night"] = night

    history_dir = os.path.join(os.path.dirname(heartbeat), "history")
    try:
        os.makedirs(history_dir, exist_ok=True)
        dest = os.path.join(history_dir, f"{job}.jsonl")
        _append_line(dest, json.dumps(record))
    except OSError as exc:
        sys.stderr.write(f"wheel_history: append: could not write history line ({exc})\n")
        return 0

    return 0


def _needs_leading_newline(dest: str) -> bool:
    """True if `dest` already has content that does NOT end with `\\n` (a previous writer's
    process was killed mid-write — the sigkills-self failure-mode tests exercise exactly this).
    A separate, read-only peek: kept apart from the O_WRONLY append fd in `_append_line` below,
    since a write-only fd cannot itself be read from (EBADF), and this check must never touch
    the append fd's own write-only contract."""
    try:
        with open(dest, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                return False
            fh.seek(-1, os.SEEK_END)
            return fh.read(1) != b"\n"
    except FileNotFoundError:
        return False


def _append_line(dest: str, payload: str) -> None:
    """Finding 9 (review round): write the record with a SINGLE `os.write` on an
    `O_WRONLY|O_APPEND|O_CREAT` fd, so two concurrent appenders (a primary and a retry slot
    firing close together, or a test's own concurrent-writer probe) can never interleave their
    bytes mid-line — `O_APPEND` makes each individual `write()` atomic with respect to the
    current end-of-file on POSIX, but only for ONE write call; two separate `write()`s (a
    line-then-newline, as a plain `open(..., "a")` + `.write()` could do depending on buffering)
    are not each other's atomicity boundary.

    Torn-line guard: if the file already has content and does NOT end with `\\n`, this record is
    prefixed with a leading `\\n` first (computed by `_needs_leading_newline` BEFORE the append fd
    is opened) — so a torn previous line can never silently merge with this record's own JSON on
    the same physical line."""
    leading_newline = "\n" if _needs_leading_newline(dest) else ""
    data = (leading_newline + payload + "\n").encode("utf-8")
    fd = os.open(dest, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# green_nights / streak — item 1c
# ---------------------------------------------------------------------------

# Local import kept lazy-free (module-level, not function-level) but wrapped so a missing/renamed
# heartbeat_audit.py degrades this module's streak features loudly rather than crashing the
# import of the whole file (the `append` subcommand must keep working even if this fails).
try:
    import heartbeat_audit as _heartbeat_audit
except Exception:  # pragma: no cover - heartbeat_audit.py is always present in this repo
    _heartbeat_audit = None  # type: ignore[assignment]


DEFAULT_HISTORY_DIR = os.path.join(os.path.expanduser("~"), ".claude", "schedules", "heartbeats", "history")
DEFAULT_LAUNCH_AGENTS_DIR = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents")

# The primary slot's local-hour window, matching slot_and_night()'s own [20, 24) rule above -- a
# "scheduled night" (for streak purposes) is a calendar date whose PRIMARY-slot rule fires, never
# a retry-slot-only date (item 1c's own wording: "nights = the weekdays whose rule time falls in
# the primary window").
_PRIMARY_HOUR_START = 20
_PRIMARY_HOUR_END = 24  # exclusive


def _read_history_lines(path: str) -> tuple[list[dict], list[str]]:
    """(records, malformed_line_descriptions). A missing file is simply zero records, zero
    problems -- never an error (mirrors every other never-raise read in this module). A line that
    fails to parse as a JSON object is reported by line number but never raises."""
    records: list[dict] = []
    problems: list[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except OSError:
        return records, problems
    for lineno, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            problems.append(f"{path}:{lineno}: malformed JSON line")
            continue
        if not isinstance(obj, dict):
            problems.append(f"{path}:{lineno}: line is not a JSON object")
            continue
        records.append(obj)
    return records, problems


def _triage_ran(data: dict) -> bool:
    """The ONE definition of "triage ran", used everywhere in this repo (S1-A1's own wording): the
    heartbeat's `triage` is an object, its `status` key (if present at all -- a real run's `triage`
    is the Workflow's own `totals` dict, which never carries a `status` key in the first place) is
    never the literal string `"not-run"`, and `triage_batches.total >= 1` and
    `triage_batches.ok >= 1`."""
    triage = data.get("triage")
    if not isinstance(triage, dict):
        return False
    if triage.get("status") == "not-run":
        return False
    batches = triage.get("triage_batches")
    if not isinstance(batches, dict):
        return False
    total = batches.get("total")
    ok = batches.get("ok")
    if not isinstance(total, int) or isinstance(total, bool) or total < 1:
        return False
    if not isinstance(ok, int) or isinstance(ok, bool) or ok < 1:
        return False
    return True


def _is_green_record(record: dict) -> bool:
    """The green-night rule (slice item 1, paragraph 1c), applied to a single history line:
      - launch == "scheduled" (a manual-* file is never even read by streak(), but this stays
        defensive in case a caller hands green_nights() a mixed record set directly);
      - no `wrapper_skip` key;
      - not `stale` (missing `stale` -- e.g. a non-wheel job's line -- is treated as "not stale",
        since `stale` is wheel-labels-only by 1b's own design; a wheel line that IS stale carries
        `stale: true` explicitly);
      - status == "ok" and exit == 0;
      - triage ran, per `_triage_ran()` above.
    A retry-slot record is eligible exactly the same way -- slot is not part of the green rule
    itself, only of which NIGHT the record counts against (already resolved by `night` at append
    time)."""
    if record.get("launch") != "scheduled":
        return False
    if "wrapper_skip" in record:
        return False
    if record.get("stale") is True:
        return False
    if record.get("status") != "ok":
        return False
    exit_val = record.get("exit")
    if not isinstance(exit_val, int) or isinstance(exit_val, bool) or exit_val != 0:
        return False
    return _triage_ran(record)


def _scheduled_weekdays_for_primary_slot(interval: object) -> set[int] | None:
    """The set of ISO weekdays (1=Mon..7=Sun, Python's `date.isoweekday()` convention) whose
    calendar rule fires with `Hour` inside the primary window [20, 24) -- i.e. the nights item 1c's
    streak counts against. A rule with NO `Hour` key at all is never counted here (its fire time is
    "any hour", which is not specifically a primary-slot night by this rule's own wording -- "the
    weekdays whose rule TIME falls in the primary window"). Returns None when `interval` cannot be
    normalized (see `heartbeat_audit._normalize_calendar_rules`) -- callers must treat that as
    "cannot determine the schedule", the same convention every other calendar-reading function in
    this repo follows.
    A rule with no `Weekday` key (e.g. a `Day`-of-month-only rule) contributes no weekday and is
    silently skipped -- the CSA/Agency wheel plists are Weekday-only rules, and a future Day-based
    rule degrades to "this rule names no scheduled night", never a crash."""
    if _heartbeat_audit is None:
        return None
    rules = _heartbeat_audit._normalize_calendar_rules(interval)  # noqa: SLF001 - shared internal, same repo
    if rules is None:
        return None
    weekdays: set[int] = set()
    for rule in rules:
        hour = rule.get("Hour")
        if not isinstance(hour, int) or isinstance(hour, bool):
            continue
        if not (_PRIMARY_HOUR_START <= hour < _PRIMARY_HOUR_END):
            continue
        weekday = rule.get("Weekday")
        if not isinstance(weekday, int) or isinstance(weekday, bool):
            continue
        # launchd: 0 and 7 both mean Sunday; normalize to Python's isoweekday() convention (1..7,
        # Monday=1..Sunday=7) exactly like heartbeat_audit._rule_matches does internally.
        iso_weekday = weekday % 7  # 0->0, 1..6 unchanged, 7->0
        iso_weekday = 7 if iso_weekday == 0 else iso_weekday
        weekdays.add(iso_weekday)
    return weekdays


def _scheduled_nights_between(
    weekdays: set[int], start_date: "datetime.date", end_date: "datetime.date"
) -> list["datetime.date"]:
    """Every calendar date in [start_date, end_date] (inclusive) whose ISO weekday is in
    `weekdays`, in ascending order. `end_date` is normally "today" (or the last night with a
    reportable line) -- a scheduled night in the future is never asked about."""
    if start_date > end_date:
        return []
    out: list["datetime.date"] = []
    current = start_date
    one_day = datetime.timedelta(days=1)
    while current <= end_date:
        if current.isoweekday() in weekdays:
            out.append(current)
        current += one_day
    return out


# A scheduled night is COMPLETE only once its own retry window has fully closed: the retry slot
# runs [00:00, 08:00) local on the CALENDAR DAY AFTER the night (see slot_and_night()'s own retry
# rule), so nothing about that night can be judged final until 08:00 local the next day. Before
# that, the night is still PENDING -- reported neither green nor a "missing" problem, and excluded
# from the streak walk entirely (a pending night neither breaks nor extends it).
_NIGHT_COMPLETE_HOUR = 8


def _night_is_complete(night_date: "datetime.date", now: "datetime.datetime") -> bool:
    """True once `night_date`'s own retry window has closed: `night_date + 1 day` at
    `_NIGHT_COMPLETE_HOUR:00` local, compared against `now` (both naive local datetimes -- this
    module's whole local-time convention, matching slot_and_night()'s own frame)."""
    cutoff_date = night_date + datetime.timedelta(days=1)
    cutoff = datetime.datetime.combine(cutoff_date, datetime.time(hour=_NIGHT_COMPLETE_HOUR))
    return now >= cutoff


def green_nights(
    job: str,
    since: "datetime.date",
    *,
    history_dir: "str | None" = None,
    launch_agents_dir: "str | None" = None,
    today: "datetime.date | None" = None,
    now: "datetime.datetime | None" = None,
) -> dict:
    """Evaluate every scheduled night for `job` from `since` (inclusive) through `today`
    (inclusive; defaults to `now`'s own local date), by the job's OWN plist calendar
    (`heartbeat_audit._read_plist_calendar_interval`, the calendar-exact ground truth -- never the
    §2 table's cadence TEXT).

    `now` (a naive local `datetime.datetime`; defaults to the real local `datetime.datetime.now()`)
    is the COMPLETENESS clock, independent of `today`'s own date-range role: a night is COMPLETE
    only once its own retry window has closed -- `night + 1 day` at `_NIGHT_COMPLETE_HOUR:00`
    (08:00) local `<= now` -- because the retry slot for a given night runs [00:00, 08:00) local on
    the CALENDAR DAY AFTER it (slot_and_night()'s own retry rule). Before that cutoff, tonight's (or
    an even more recent) scheduled night is still PENDING: it is reported as such, contributes NO
    "no history line" problem (there may genuinely be no line yet -- the run hasn't happened), and
    is EXCLUDED from the streak walk entirely (a pending night neither breaks nor extends the
    streak). This is B1's fix: the OLD behavior evaluated straight through `today` inclusive with no
    completeness notion, so tonight's own scheduled night read as "missing" (and broke the streak to
    0) from midnight until its 03:30 retry actually closed it out -- for most of every day.

    Returns a dict:
      {
        "job": job,
        "since": since.isoformat(),
        "nights": [
          {"night": "YYYY-MM-DD", "green": bool, "pending": bool, "slot": "primary"|"retry"|None,
           "reason": str | None},
          ...
        ],
        "streak": int,          # the length of the run of consecutive TRAILING green nights among
                                 # COMPLETE nights only, ending at the most recent COMPLETE
                                 # scheduled night (0 if that night is not green, all nights are
                                 # still pending, or there are no scheduled nights at all)
        "problems": [str, ...], # malformed lines, COMPLETE scheduled nights with no line, and
                                 # green-looking records missing `triage` -- see each check below
        "schedule_unknown": bool,  # True when the plist calendar could not be read at all; in
                                    # that case "nights" is always [] and streak is 0 -- never
                                    # guessed.
      }

    A `manual-*` history file is never read here regardless of `job`'s own value -- streak() (the
    CLI) always calls this with the SCHEDULED label (e.g. `com.oversight.wheel.csa`), which 1b
    writes to its own history file distinct from `manual-wheel-<slug>.jsonl`, so this is naturally
    satisfied by reading `<job>.jsonl` and never `manual-<job>.jsonl`.

    A COMPLETE scheduled night with NO qualifying record (no line for it at all, i.e. neither a
    `scheduled` record for that exact night nor a `retry`-slot record whose OWN `night` field names
    it -- see 1b's append-time contract: a retry run's `night` is already the PREVIOUS local date)
    is reported as a problem ("no history line for scheduled night ...") and is NOT green. A
    PENDING night with no line yet is never reported as a problem -- there may genuinely be nothing
    to find yet.

    A record that would otherwise be green by every OTHER field but carries no `triage` key at all
    (as opposed to one whose `triage` fails the rule) is additionally reported as a problem
    ("... has no `triage` key") -- the slice's own "Reported problems" bullet: "a green-looking
    record missing `triage`". Such a record itself is judged NOT green (missing triage means
    triage did not verifiably run).
    """
    now = now or datetime.datetime.now()
    today = today or now.date()
    since_date = since
    # Resolved at CALL time, not bind time -- a caller (or a test) that reassigns the module-level
    # DEFAULT_HISTORY_DIR/DEFAULT_LAUNCH_AGENTS_DIR constant sees that change take effect on the
    # very next call, matching every other DEFAULT_*-driven entry point in this repo
    # (heartbeat_audit.py's own main() re-reads its DEFAULT_* constants the same way).
    history_dir = history_dir if history_dir is not None else DEFAULT_HISTORY_DIR
    launch_agents_dir = launch_agents_dir if launch_agents_dir is not None else DEFAULT_LAUNCH_AGENTS_DIR

    out: dict = {
        "job": job,
        "since": since_date.isoformat(),
        "nights": [],
        "streak": 0,
        "problems": [],
        "schedule_unknown": False,
    }

    if _heartbeat_audit is None:
        out["schedule_unknown"] = True
        out["problems"].append("heartbeat_audit module unavailable; cannot read the plist calendar")
        return out

    interval = _heartbeat_audit._read_plist_calendar_interval(job, launch_agents_dir)  # noqa: SLF001
    if interval is None:
        out["schedule_unknown"] = True
        out["problems"].append(f"could not read/parse {job}'s StartCalendarInterval from its plist")
        return out

    weekdays = _scheduled_weekdays_for_primary_slot(interval)
    if not weekdays:
        out["schedule_unknown"] = True
        out["problems"].append(f"{job}'s plist names no primary-slot (Hour in [20,24)) weekday rule")
        return out

    scheduled_nights = _scheduled_nights_between(weekdays, since_date, today)

    history_path = os.path.join(history_dir, f"{job}.jsonl")
    records, malformed = _read_history_lines(history_path)
    out["problems"].extend(malformed)

    # Index candidate records by the NIGHT they count against (already resolved at append time by
    # slot_and_night(); a retry record's own `night` already names the PREVIOUS local date, so no
    # re-derivation is needed here). Multiple records for the same night (e.g. an offschedule blip
    # plus a real primary run) are all considered; the night is green if ANY qualifying record for
    # it is green -- a primary failure followed by a green retry still makes the night green.
    by_night: dict[str, list[dict]] = {}
    for record in records:
        night = record.get("night")
        if isinstance(night, str):
            by_night.setdefault(night, []).append(record)

    night_results: list[dict] = []
    for night_date in scheduled_nights:
        night_str = night_date.isoformat()
        complete = _night_is_complete(night_date, now)
        candidates = by_night.get(night_str, [])

        if not complete:
            # PENDING: never a problem (there may be nothing to find yet), never green, excluded
            # from the streak walk below. A pending night MAY still have a record already (e.g. the
            # primary already ran and reported ok before 08:00 the next day) -- that record's own
            # green-ness is not yet FINAL until the retry window closes (a currently-green primary
            # could still be joined or superseded by information the retry slot adds), so this
            # function deliberately does not pre-judge it; it is reported as pending regardless.
            night_results.append(
                {"night": night_str, "green": False, "pending": True, "slot": None, "reason": "pending"}
            )
            continue

        if not candidates:
            out["problems"].append(f"no history line for scheduled night {night_str} ({job})")
            night_results.append(
                {"night": night_str, "green": False, "pending": False, "slot": None, "reason": "no-line"}
            )
            continue

        green_record = None
        for record in candidates:
            if "triage" not in record and record.get("launch") == "scheduled" and "wrapper_skip" not in record \
                    and record.get("stale") is not True and record.get("status") == "ok" \
                    and isinstance(record.get("exit"), int) and not isinstance(record.get("exit"), bool) \
                    and record.get("exit") == 0:
                out["problems"].append(
                    f"{night_str} ({job}): a green-looking record (status ok, exit 0, no skip, "
                    "not stale) has no `triage` key at all"
                )
            if _is_green_record(record):
                green_record = record
                break

        if green_record is not None:
            night_results.append(
                {"night": night_str, "green": True, "pending": False, "slot": green_record.get("slot"), "reason": None}
            )
        else:
            night_results.append(
                {"night": night_str, "green": False, "pending": False, "slot": None, "reason": "not-green"}
            )

    out["nights"] = night_results

    streak = 0
    for entry in reversed(night_results):
        if entry["pending"]:
            continue  # excluded from the walk entirely -- neither breaks nor extends it
        if not entry["green"]:
            break
        streak += 1
    out["streak"] = streak

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # never raise SystemExit's traceback shape; print and exit 0
        sys.stderr.write(f"wheel_history: {message}\n")
        sys.exit(0)


def do_streak(args: argparse.Namespace) -> int:
    """`streak --job <label> --since <YYYY-MM-DD>`: prints the streak and each scheduled night's
    verdict (item 1c). Never raises -- a bad `--since` or an unreadable schedule prints a message
    and exits 0, the same never-raise convention as `append`."""
    job = args.job
    if not job:
        sys.stderr.write("wheel_history: streak: --job is required\n")
        return 0
    try:
        since_date = datetime.date.fromisoformat(args.since)
    except (TypeError, ValueError):
        sys.stderr.write(f"wheel_history: streak: --since must be YYYY-MM-DD, got {args.since!r}\n")
        return 0

    result = green_nights(job, since_date)

    print(f"job: {result['job']}")
    print(f"since: {result['since']}")
    if result["schedule_unknown"]:
        print("schedule: UNKNOWN (could not read the plist calendar)")
    for entry in result["nights"]:
        if entry.get("pending"):
            print(f"  {entry['night']}: PENDING (retry window not yet closed)")
            continue
        verdict = "GREEN" if entry["green"] else "not green"
        slot_note = f" ({entry['slot']})" if entry.get("slot") else ""
        reason_note = f" [{entry['reason']}]" if entry.get("reason") else ""
        print(f"  {entry['night']}: {verdict}{slot_note}{reason_note}")
    print(f"streak: {result['streak']}")
    if result["problems"]:
        print(f"problems ({len(result['problems'])}):")
        for problem in result["problems"]:
            print(f"  - {problem}")
    return 0


def parse(argv: list[str]) -> argparse.Namespace:
    p = _Parser(prog="wheel_history.py", description="Per-night wrapper history appender (GH #4767)")
    sub = p.add_subparsers(dest="kind", required=True, parser_class=_Parser)
    ap = sub.add_parser("append")
    ap.add_argument("--heartbeat", default="")
    ap.add_argument("--job", default="")
    ap.add_argument("--start-epoch", default="")
    ap.add_argument("--start-iso", default="")

    sp = sub.add_parser("streak")
    sp.add_argument("--job", default="")
    sp.add_argument("--since", default="")

    return p.parse_args(argv)


HANDLERS = {
    "append": do_append,
    "streak": do_streak,
}


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse(sys.argv[1:] if argv is None else argv)
        return HANDLERS[args.kind](args)
    except SystemExit:
        raise
    except Exception as exc:  # never-raise design: any failure is one stderr line, exit 0
        sys.stderr.write(f"wheel_history: unexpected error: {exc}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
