#!/usr/bin/env python3
"""heartbeat_audit — REPORT-ONLY mechanical cross-check of the oversight wheel's
own liveness telemetry (#4400, AA-0003 in agentarch_recommendations.jsonl).

Before this module existed, no code outside the LLM sessions themselves could
detect that the oversight wheel had stopped — the daily job's own liveness
audit (daily_sweep.txt step A) is itself an LLM reading files and could, in
principle, fabricate a clean read the same way a killed run could fabricate a
finished_at timestamp it never reached. This module is the pure-Python,
non-LLM complement: it never trusts prose, only structure.

What it checks, all read-only, pure stdlib:
  1. EXPECTED job set: parsed from oversight_install.md's §2 markdown table
     (the `label` column). A parse failure is a LOUD, distinct finding
     (`table-parse-failed`) — it is never treated as "zero expected jobs",
     which would silently blind every other diff below.
  2. UNEXPECTED heartbeats: a heartbeat file whose stem is neither in that
     table nor prefixed `manual-` (the /sweep fallback's own convention,
     AA-0014) is drift worth a look.
  3. LOADED-NEVER-FIRED: a job present in both the table AND `launchctl list`
     but with zero heartbeat file ever written — the AA-0003 case this module
     exists for. Distinguished from "not yet due": this only fires once at
     least one full cadence period (from the §2 table's own cadence column,
     `cadence_seconds()`, plus GRACE_SECONDS) has elapsed since the job's
     plist was installed (its symlink's mtime under `~/Library/LaunchAgents/`
     — `_plist_install_epoch()`). A monthly job installed two days ago is not
     yet due and is NOT flagged; the same job still silent a month later is.
     When the cadence or install-time data needed for that comparison is
     unavailable, this degrades to the old, conservative behavior (flag
     immediately) rather than silently granting an exemption it cannot prove.
  3b. SILENT-JOB (AA-0050): a CALENDAR-EXACT complement to
     loaded-never-fired. That check's "not yet due" exemption uses
     `cadence_seconds()`'s WORST-CASE cadence text (a monthly job reads as
     "~31 days between fires" with no notion of which day of the month it
     actually fires on), so a job installed partway through a period can
     sail through it even once its own real scheduled minute has passed —
     exactly the case a week of silent `testarch`/`trustarch` firings
     exposed 2026-08-31: both were loaded and installed, cadence_seconds()
     still called them "not yet due", and no violation fired. This check
     reads each loaded/expected job's OWN plist `StartCalendarInterval`
     directly (`_read_plist_calendar_interval()`) and computes the most
     recent PAST minute any of its calendar rules actually matched
     (`most_recent_scheduled_fire()`); if that fire time is more than
     GRACE_SECONDS in the past and still no heartbeat file exists, it is
     flagged `silent-job` BY NAME — independent of, and in addition to,
     whatever loaded-never-fired concluded. Skipped (never a violation),
     never guessed, when the plist's own calendar rule can't be
     read/parsed. Also skipped when that most-recent calendar match itself
     predates the job's own plist install epoch (`_plist_install_epoch()`,
     the same data #3 already uses) — mirroring #3's own "not yet due"
     floor at the calendar-exact layer, since a job installed mid-period
     can otherwise be flagged citing a fire date from before the job
     existed (found 2026-09-07: trustarch/agentarch, both installed
     2026-09-03, cited against their PRIOR month's fire). When the install
     epoch is unavailable, this degrades to the old, conservative behavior
     (flag if overdue) rather than silently granting an exemption it
     cannot prove — same fallback direction as #3.
  3c. EXPECTED-BUT-UNLOADED (H1, THE ISSUE WHEEL hardening plan): a label
     whose §2 table `expected_state` column reads "loaded" but is absent
     from `loaded_labels` entirely — the mechanism that catches "someone
     unloaded the job (or it was never loaded) and nobody noticed."
     Distinct from #3/#3b above, both of which require the job to already
     BE loaded before asking whether it has gone quiet; this is the
     complementary case where the job isn't loaded in the first place. A
     pure set-difference — needs no cadence/install-time/`now_epoch` data,
     only `loaded_labels` itself being readable. A label with a missing,
     unparseable, or any non-"loaded" `expected_state` value is never
     flagged — "cannot determine" is never treated as "overdue", the same
     convention every other cadence-gated check in this module follows.
  4. Per-heartbeat structural validation: the six REQUIRED_KEYS from
     _preamble.txt's step 5 shape, the daily job's four typed keys (AA-0006 /
     AA-0010: last_rotation_dim, slot_ran, last_staging_revision,
     pin_suspect), UTC-Z timestamp format (AA-0011), and pin_suspect's type
     wherever any job's heartbeat carries it. An IN-FLIGHT START heartbeat
     (finished_at is null and summary starts "STARTED") is exempt from the
     finished_at-format check and the daily job's typed-key checks — neither
     exists yet at that point in the run, per _preamble.txt's own step order.
  5. STALE-START: an in-flight START heartbeat (see #4) whose started_at is
     older than its own job's cadence + GRACE_SECONDS (from the §2 table) is
     a violation naming the job — the run most likely died mid-flight without
     ever reaching its END write. Skipped, not flagged, when the cadence data
     needed to set the threshold is unavailable.
  5b. DANGLING-HEARTBEAT (AUDIT FINDING 2, 2026-09-03): a HARD, UNCONDITIONAL
     complement to #5 that closes a real gap in it — #5 only fires for a
     heartbeat matching the exact "STARTED ..." in-flight shape
     (`_is_inflight_start`). A heartbeat with `finished_at: null` whose
     summary does NOT match that shape (e.g. a run that died after
     overwriting summary, or any other null-finished_at shape) fell through
     to the generic, cadence-blind `bad-timestamp-format` line instead —
     which fires identically whether the run started 30 seconds ago or 2
     days ago, so a genuinely dead job read exactly like a routine format
     nit. This is the mechanism behind a real incident: steward sat dead for
     2 days while a daily sweep caught productqa's dead run but not
     steward's — surfacing a dangling heartbeat was a judgment call, not
     mechanical. Coverage (stated precisely — corrected 2026-09-03 review):
     this 5b check is the COMPLEMENT of `stale-start`. `stale-start` covers
     the in-flight "STARTED ..." summary shape; 5b covers every OTHER
     `finished_at: null` shape (summary overwritten, absent, malformed).
     Together the pair covers ALL dead heartbeats once `started_at` is older
     than the job's own cadence + GRACE_SECONDS: one line per dead job with
     days-dead in the message so it can never be mistaken for routine format
     noise — but neither branch alone is unconditional. Skipped (never
     flagged) only when the cadence or started_at data needed to prove
     staleness is itself unavailable — "cannot determine" is never treated
     as "overdue", the same convention every other cadence-gated check in
     this module follows.
  6. TIMESTAMP DIVERGENCE: this job's own `schedules/logs/<label>.{out,err}.log`
     file times (birthtime as a start proxy, mtime as a finish proxy) compared
     against the heartbeat's own claimed started_at/finished_at; a divergence
     beyond 5 minutes where the heartbeat is NEWER than its log evidence is
     flagged `timestamp-divergence` (possible fabricated timestamp — the
     failure mode AA-0011 names as already observed in production once); the
     opposite direction (heartbeat OLDER than its log) is flagged separately
     as `heartbeat-older-than-log` — most plausibly a rotated/re-touched log
     file, not a fabrication claim.
  7. RELATIVE-ARTIFACT-CLAIM (#5055, 2026-09-07 launchdir false-alarm
     incident; REALITY-GATED, fixed same day per a dual-Opus review B-1
     blocker): a FINISHED heartbeat (finished_at set, not an in-flight
     START) whose `summary` does NOT start with the wrapper's own
     "WRAPPER:" prefix and names a relative-or-`~`-anchored, path-shaped
     token (see `heartbeat_artifact_stamp.extract_path_claims`, imported
     here rather than reimplemented so the two modules can never drift on
     what counts as a candidate token) that ALSO RESOLVES to a file that
     ACTUALLY EXISTS (via `heartbeat_artifact_stamp.resolve_claim`, gated
     on `$HOME/.claude` only — this check has no per-job WorkingDirectory
     to try, unlike `stamp()` itself at write-time) is a violation. Root
     cause this closes: the launchdir weekly job's own write instruction
     names an ABSOLUTE artifact path, but nothing required its summary to
     name that path in a resolvable form — the live heartbeat on the day of
     the incident carried a bare relative-looking claim, which read as "the
     report is missing" to anything that couldn't resolve it.
     THE REALITY GATE IS LOAD-BEARING, not a nicety: extract_path_claims is
     SHAPE-only, so a heartbeat summary's ordinary PROSE ("Clusters C/E
     flagged", "dropped 2/5 items", "carried from 2026/09/01") is
     shape-indistinguishable from a genuine relative artifact claim. An
     earlier version of this check flagged on shape alone and would have
     raised a `relative-artifact-claim` violation against testarch's own
     "C/E" prose — a false positive with no real artifact behind it. Gating
     on "resolves to an existing file" is what confines this check to the
     actual incident class: a TRUE artifact reference named relatively.
     No `artifacts_verified`-based exemption is needed: once
     `heartbeat_artifact_stamp.stamp()` has run against a heartbeat, every
     REAL relative/`~` claim has already been rewritten to its absolute
     form in-place inside the summary text itself — so this check simply
     re-derives the same reality gate independently and flags whatever
     still resolves to a real file in relative form (stamp() never ran for
     this job, or ran against a different workdir than this check tries).
     An in-flight START heartbeat is exempt (mirrors every other check's own
     in-flight exemption above — a run that hasn't finished yet hasn't
     necessarily written its real, resolvable artifact claim).
  8. LOCK-REFUSED (H3, THE ISSUE WHEEL hardening plan, BLOCKER 2): a
     FINISHED heartbeat whose `exit` field is exactly 75 (EX_TEMPFAIL) —
     `run_oversight_job.sh`'s concurrency guard writes this when a
     wheel-slug lock acquisition is refused because another live run already
     holds it. Necessary context: that refusal heartbeat still carries a
     fresh, well-formed, non-null `finished_at` (REQUIRED_KEYS demands one),
     so every OTHER check above — none of which reads `exit` for liveness —
     reads it as an ordinary clean finish and resets the "last heartbeat"
     clock those checks use. Left unflagged, an orphaned lock could starve
     every future run of that slug indefinitely while this module kept
     reporting the job healthy. Flagged by exact name so it is never
     confused with a genuine clean finish. An in-flight START heartbeat is
     exempt (mirrors every other finished-only check above — a run that
     hasn't finished yet was never refused). A missing or non-int `exit`
     degrades to "cannot determine" (never flagged here — `missing-keys`/
     `bad-type` above already cover that shape by name), the same
     conservative convention every other check in this module follows.
  9. JOB-FAILED (THE ISSUE WHEEL plan, WS1-B.1 / Phase B item 1 — the
     observability-blind-spot fix): a FINISHED heartbeat is flagged
     `job-failed` when EITHER (a) it carries a structured `status` field
     (written by `run_oversight_job.sh` as of this commit, on every wrapper-
     owned exit path) equal to exactly `"failed"`, OR (b) `status` is ABSENT
     (a session-authored END heartbeat predates this field, or a job's own
     prompt never adopted it) AND (`exit` is a non-zero int OR `summary`
     starts with the wrapper's own `"WRAPPER:"` prefix — the diagnostic
     shape `run_oversight_job.sh` writes when the session died without a
     truthful END write, #4825/#4791). This is the fix for the exact gap
     named in the plan's F3: the Agency heartbeat that motivated this check
     carried `exit: 0` and a FRESH `finished_at` (so every liveness check
     above read it as healthy) while its `summary` alone said "claude
     process exited (code=0) without a truthful END heartbeat" — only the
     free-text summary carried the failure. `status` is the mechanical fix
     going forward; the `WRAPPER:`-prefix/non-zero-exit fallback is what
     lets this check also catch that exact historical shape and any other
     legacy heartbeat written before the `status` field existed. A `status`
     of `"ok"`, `"skipped-quota"`, `"skipped-disabled"` or `"skipped-throttle"`
     is NEVER flagged, regardless of `exit` or `summary` — those are the four
     sanctioned non-failure outcomes. `"skipped-disabled"` is the wheel
     wrapper's own kill-switch skip (GH #4767: DISABLED or
     DISABLED.wheel.<slug> present, claude never launched). `"skipped-throttle"`
     (#5922, follow-up to F6) is the pre-flight's own server-side-throttle
     skip — the CLI's `API Error: Server is temporarily limiting requests (not
     your usage limit)` line, distinct from `"skipped-quota"` precisely
     BECAUSE it is not quota exhaustion: the account's own usage limit is
     fine, the server is momentarily rate-limiting requests. It carries its
     own `consecutive_throttle_skips` counter (same carry-forward shape as
     `consecutive_quota_skips`, see `run_oversight_job.sh`). #5922 fix
     round, BLOCKER 1 (corrects this docstring's own prior claim that no
     threshold applied to it at all): a THROTTLE streak gets the SAME
     three-or-more-in-a-row treatment as a quota streak, just a different
     reason string, because a long, unbroken throttle streak is itself
     evidence worth a human noticing — sustained concurrent load against the
     account (another session, or a runaway fan-out sharing the same
     server-side rate limit) rather than the account's own quota being
     exhausted. See the code below for the exact reason string
     ("server-side throttle, not quota; check concurrent load").
     An in-flight START heartbeat is exempt (mirrors every other
     finished-only check above). THREE CONSECUTIVE `"skipped-quota"`
     heartbeats for one label also flag `job-failed`, with a reason string
     naming the streak: `run_oversight_job.sh`'s quota pre-flight (Phase C
     item 1) writes a `consecutive_quota_skips` counter into each
     `skipped-quota` heartbeat (carried forward from the PRIOR heartbeat
     when it was also a skip, reset to 1 otherwise — a prior `skipped-throttle`
     heartbeat is "any other prior status" for this purpose and resets the
     quota streak to 1, never extends it — see that script's own
     comment), so this check reads that counter directly off the CURRENT
     heartbeat rather than needing a separate state file: a single quota
     skip, or two in a row, is an ordinary, expected outcome and is NOT
     flagged; three or more in a row means the account's quota exhaustion
     has outlasted this job's own retry slot (see Phase C item 1's second
     StartCalendarInterval slot) and is worth a human noticing. The
     identical single-or-two-in-a-row-is-ordinary / three-or-more-flags rule
     applies to `consecutive_throttle_skips` for `"skipped-throttle"`, read
     directly off THIS heartbeat exactly the same way, and it is likewise
     reset to 1 by any prior status other than `"skipped-throttle"` itself
     (including `"skipped-quota"` — the two streaks are always independent,
     never carried into each other in either direction). A
     `consecutive_quota_skips`/`consecutive_throttle_skips` field that is
     missing, non-int, or <3 degrades to "not flagged" — the same
     conservative convention every other check in this module follows.
  10. UNEXPECTED-LOADED (THE ISSUE WHEEL plan, WS1-B.3 / Phase B item 3):
     the MIRROR of check #2c (`expected-but-unloaded`) in the opposite
     direction — a label present in `loaded_labels` (i.e. `launchctl list`
     shows it loaded right now) whose §2 table `expected_state` column is
     present but is NOT `"loaded"` (e.g. `"unloaded"`, the value every
     not-yet-activated wheel plist carries today). #2c only ever asks "is a
     job the table says should be loaded actually loaded" — it has no
     opposite check for "is a job the table says should NOT be loaded
     nonetheless loaded", which is exactly the shape of a rollout-state
     drift where a plist was `launchctl load`ed without ever updating the
     table (or vice-versa: the table was updated to `loaded` in anticipation
     of an install step that never actually ran, a DIFFERENT drift #2c
     itself already covers). A pure set-membership check, same shape and
     same degrade-direction as #2c: only ever evaluated for a label whose
     `expected_state` is present and NOT `"loaded"` — a label with a
     missing/unparseable `expected_state` value is never flagged either
     direction (the same "cannot determine, not a violation" convention
     every check in this module follows), and neither is a label entirely
     absent from the table (that is `unexpected-heartbeat`'s lane, not
     this one — this check only ever looks at rows the table itself
     defines).
  11. WHEEL-GRANT-CONTRADICTION (WS14-S1, item 1c, GH #4767): a GENERIC
     check, wheel labels only (`com.oversight.wheel.*` / `manual-wheel-*`).
     It fires when a job's `degraded_reason` — read from its LIVE heartbeat,
     or from any of its history lines (`schedules/heartbeats/history/
     <label>.jsonl`) from the last 48 hours — matches the shape
     `<tool>-tool-unavailable` for some `<tool>` that IS present (case-
     insensitively) in `wheel_launch_context.TOOLS` (a comma-separated
     string of granted tool names, split and compared case-insensitively).
     Root cause this closes: a session can find a genuinely GRANTED tool
     "unavailable" only through its own bug (e.g. probing with ToolSearch
     for a tool that is actually a DIRECT grant, never deferred — the exact
     09-27 #4767 root cause) — the tool being unavailable while the grant
     says otherwise is a CONTRADICTION worth a human's attention, distinct
     from every other finding class in this module, none of which reads
     `degraded_reason` at all. The last-48h HISTORY scan exists because the
     03:30 retry slot overwrites the primary slot's own live heartbeat file
     before the 05:10 daily audit ever runs, so a primary-slot contradiction
     would otherwise be invisible to a same-morning audit; scanning the
     history file (1b, item 1b) recovers it regardless of which slot's
     heartbeat is currently on disk. `wheel_launch_context.TOOLS` is read
     inside a try/except that NEVER raises (see `_gather`) — an import
     failure, a missing/renamed module, or any other error degrades this
     check to "grant set unknown, skip it entirely" rather than crashing
     the whole audit run. This is a REPORT-ONLY finding: it is never added
     to `run_watchdog.sh`'s own escalation set (see that script's own
     comment for the full non-escalating list).

Exit code: always 0 (report-only; a consumer parses the printed lines, never
the exit code). Never raises: a crashing self-check must not wedge a job.

This module owns exactly two files:
  ~/.claude/hooks/heartbeat_audit.py  (this file)
  ~/.claude/hooks/tests/test_heartbeat_audit.py
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

from heartbeat_artifact_stamp import extract_path_claims, resolve_claim

_HOME = os.path.expanduser("~")
DEFAULT_INSTALL_DOC = os.path.join(_HOME, ".claude", "knowledge", "oversight_install.md")
DEFAULT_HEARTBEATS_DIR = os.path.join(_HOME, ".claude", "schedules", "heartbeats")
DEFAULT_HISTORY_DIR = os.path.join(_HOME, ".claude", "schedules", "heartbeats", "history")
DEFAULT_LOGS_DIR = os.path.join(_HOME, ".claude", "schedules", "logs")
DEFAULT_LAUNCH_AGENTS_DIR = os.path.join(_HOME, "Library", "LaunchAgents")
DEFAULT_DAILY_JOB_LABEL = "com.oversight.csa.daily"
WHEEL_GRANT_CONTRADICTION_WINDOW_SECONDS = 48 * 3600.0  # WS14-S1 item 1c

REQUIRED_KEYS = ("job", "started_at", "finished_at", "exit", "cadence", "summary")
DAILY_TYPED_KEYS = ("last_rotation_dim", "slot_ran", "last_staging_revision", "pin_suspect")
_ROTATION_DIMS = {"health", "logs", "cost", "consistency"}
_UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_TABLE_HEADER_RE = re.compile(r"^\|\s*label\s*\|", re.IGNORECASE)
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
DIVERGENCE_THRESHOLD_SEC = 300.0  # 5 minutes, per AA-0011
GRACE_SECONDS = 6 * 3600.0  # matches daily_sweep.txt's own "cadence+grace(6h)" convention

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_CADENCE_TIME_PREFIX_RE = re.compile(r"^\d{1,2}:\d{2}\s+")
_CADENCE_OF_MONTH_RE = re.compile(r"of month", re.IGNORECASE)
_CADENCE_RANGE_RE = re.compile(r"^([A-Za-z]{3})\s*[-–—]\s*([A-Za-z]{3})$")
DAILY_CADENCE_SECONDS = 24 * 3600.0
MONTHLY_CADENCE_SECONDS = 31 * 24 * 3600.0  # worst-case month length; an upper bound, not exact


def parse_job_table(doc_text: str) -> list[tuple[str, str, str]]:
    """The §2 markdown table's (label, expected_state, cadence-text) triples,
    in table order.

    Table shape (H1, THE ISSUE WHEEL hardening plan): `| label |
    expected_state | StartCalendarInterval | repo (WorkingDirectory) |
    prompt file | does |` — `expected_state` sits at column 2 (`cells[1]`),
    immediately after `label`, never appended after `does` (that column
    routinely holds several thousand characters of prose per row, the worst
    place for a human editor to locate a short closed-value marker). Cadence
    is therefore `cells[2]`, one position later than before this column was
    inserted.

    Raises ValueError when no header row, no separator row, or zero data rows
    are found. Callers MUST treat that as a loud degraded state — an empty
    return here would read identically to "the wheel legitimately has zero
    jobs", which is exactly the silent-blind failure this module exists to
    avoid. Never returns {} on a parse failure; it raises instead.
    """
    lines = doc_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if _TABLE_HEADER_RE.match(line.strip()):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("no '| label |' table header found")
    sep_idx = header_idx + 1
    if sep_idx >= len(lines) or not _TABLE_SEP_RE.match(lines[sep_idx].strip()):
        raise ValueError("no markdown separator row found after the header")

    rows: list[tuple[str, str, str]] = []
    for line in lines[sep_idx + 1 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        label = cells[0].strip("`").strip()
        expected_state = cells[1].strip()
        cadence = cells[2].strip()
        if not label:
            continue
        rows.append((label, expected_state, cadence))
    if not rows:
        raise ValueError("table header/separator found but zero data rows parsed")
    return rows


def _max_gap_days(day_indices: set[int]) -> int:
    """Worst-case number of days between consecutive firings for a job that
    fires on this set of weekdays (0=Mon..6=Sun), wrapping week-to-week.

    Empty input degrades to 7 (a full week) rather than 0 — zero would mean
    "always due", which would make every loaded-never-fired exemption a
    no-op the first time this is called with bad data.
    """
    ordered = sorted(day_indices)
    if not ordered:
        return 7
    gaps = []
    for i, day in enumerate(ordered):
        nxt = ordered[(i + 1) % len(ordered)]
        gap = (nxt - day) % 7 or 7
        gaps.append(gap)
    return max(gaps)


_CADENCE_INTERVAL_RE = re.compile(
    r"^every\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b", re.IGNORECASE | re.ASCII
)


def cadence_seconds(cadence_text: str) -> float | None:
    """Approximate WORST-CASE seconds between two consecutive firings for a
    §2-table cadence cell: a StartCalendarInterval cell (e.g. "05:10 daily",
    "06:10 Tue,Fri", "22:10 Mon-Fri", "06:10 1st of month") or a launchd
    StartInterval cell ("every 120s", "every 5 min", "every 2h"). None when the text cannot be
    classified — callers must treat that as "cannot determine staleness",
    never as zero (which would flag everything immediately).
    """
    if not isinstance(cadence_text, str) or not cadence_text.strip():
        return None
    # A launchd `StartInterval` job (e.g. "every 120s", "every 5 min") has a
    # fixed period rather than a calendar slot; its worst-case gap is that
    # period. Checked first, before the calendar grammar below. A zero or
    # negative period is unclassifiable (None), never zero.
    interval = _CADENCE_INTERVAL_RE.match(cadence_text.strip())
    if interval:
        amount = int(interval.group(1))
        unit = interval.group(2).lower()
        if amount <= 0:
            return None
        if unit.startswith("h"):
            return float(amount * 3600)
        if unit.startswith("m"):
            return float(amount * 60)
        return float(amount)
    rest = _CADENCE_TIME_PREFIX_RE.sub("", cadence_text.strip(), count=1).strip()
    if not rest:
        return None
    if "daily" in rest.lower():
        return DAILY_CADENCE_SECONDS
    if _CADENCE_OF_MONTH_RE.search(rest):
        return MONTHLY_CADENCE_SECONDS

    range_match = _CADENCE_RANGE_RE.match(rest)
    if range_match:
        start, end = range_match.group(1).title(), range_match.group(2).title()
        if start not in _WEEKDAYS or end not in _WEEKDAYS:
            return None
        si, ei = _WEEKDAYS.index(start), _WEEKDAYS.index(end)
        days = set(range(si, ei + 1)) if si <= ei else set(range(si, 7)) | set(range(0, ei + 1))
        return _max_gap_days(days) * 24 * 3600.0

    tokens = [t.strip().title() for t in re.split(r"[,\s]+", rest) if t.strip()]
    if tokens and all(t in _WEEKDAYS for t in tokens):
        day_indices = {_WEEKDAYS.index(t) for t in tokens}
        return _max_gap_days(day_indices) * 24 * 3600.0
    return None


def _plist_install_epoch(label: str, launch_agents_dir: str) -> float | None:
    """The installed plist symlink's own mtime under `~/Library/LaunchAgents/`
    — a proxy for "when was this job (re)installed", per `ln -sf` giving the
    symlink a fresh mtime on every (re)install. `os.lstat` (never `os.stat`)
    so this reads the SYMLINK's own mtime, not the mtime of whatever it
    points at (the committed plist in `~/.claude/schedules/`, which reflects
    when it was last EDITED, not when it was last LOADED). None when the
    label has no plist there (not installed, wrong name, or unreadable) —
    callers must treat that as "install time unknown", not "installed now".
    """
    try:
        return os.lstat(os.path.join(launch_agents_dir, f"{label}.plist")).st_mtime
    except OSError:
        return None


# Bound on how far back most_recent_scheduled_fire() searches for a matching
# calendar rule before giving up (never guessing). 400 days comfortably
# covers a monthly job (worst case ~31 days between fires) plus slack for a
# Day=29/30/31 rule that only matches some months, without risking an
# unbounded loop on a malformed rule that never matches anything.
_CALENDAR_SEARCH_DAYS = 400


def _normalize_calendar_rules(interval: object) -> list[dict] | None:
    """A plist `StartCalendarInterval` value is either a single dict or a
    list of dicts (launchd ORs multiple dicts together — see `loop`'s
    five-weekday array). Returns a list of plain dicts (each possibly
    carrying `Month`/`Day`/`Weekday`/`Hour`/`Minute`, all optional per
    launchd's own semantics — an absent field matches every value), or
    None when `interval` is neither shape (missing key, wrong type, empty
    list) — callers must treat that as "cannot determine the schedule",
    never as "matches nothing"/"matches everything".
    """
    if isinstance(interval, dict):
        return [interval]
    if isinstance(interval, list) and interval and all(isinstance(d, dict) for d in interval):
        return interval
    return None


def _rule_matches(rule: dict, dt: datetime) -> bool:
    """True iff calendar dict `rule` matches datetime `dt` at minute
    granularity, per launchd's own StartCalendarInterval semantics: a field
    absent from `rule` matches every value; `Weekday` follows launchd's
    convention (0 and 7 both mean Sunday, 1..6 Mon..Sat) so it is compared
    via `dt.isoweekday() % 7` to accept either spelling of Sunday.

    Day+Weekday combined in ONE rule dict is OR, not AND (a launchd quirk,
    same as cron's day-of-month/day-of-week combination): when a single
    rule specifies BOTH, it fires when EITHER condition is met, not only
    when both are. Deliberately implemented (not left as a latent gap) even
    though no live plist in this repo currently combines them (checked
    2026-08-31, `~/.claude/schedules/com.oversight.csa.*.plist` — none do)
    — a future plist that does would otherwise silently under-fire every
    date this function's own contract claims to resolve exactly.
    """
    if "Month" in rule and rule["Month"] != dt.month:
        return False
    day_key_present = "Day" in rule
    weekday_key_present = "Weekday" in rule
    if day_key_present and weekday_key_present:
        day_ok = rule["Day"] == dt.day
        weekday_ok = (rule["Weekday"] % 7) == (dt.isoweekday() % 7)
        if not (day_ok or weekday_ok):
            return False
    else:
        if day_key_present and rule["Day"] != dt.day:
            return False
        if weekday_key_present:
            want = rule["Weekday"] % 7  # normalize 7->0 (both mean Sunday)
            if want != (dt.isoweekday() % 7):
                return False
    if "Hour" in rule and rule["Hour"] != dt.hour:
        return False
    if "Minute" in rule and rule["Minute"] != dt.minute:
        return False
    return True


def most_recent_scheduled_fire(interval: object, now_epoch: float) -> float | None:
    """The most recent PAST minute (epoch seconds, <= now_epoch) at which
    ANY rule in a plist's `StartCalendarInterval` value matches — i.e. the
    job's most recently due scheduled fire window.

    LOCAL-TIME CONTRACT (load-bearing — do not "fix" this back to UTC):
    launchd interprets every StartCalendarInterval field in the SYSTEM's
    local timezone, never UTC. This function computes entirely in LOCAL
    wall-clock time to match: `now_epoch` is read into a NAIVE datetime via
    `datetime.fromtimestamp(now_epoch)` with no `tz` argument (Python's
    documented "local time" reading), every candidate below is built from
    that same naive value, and the returned epoch comes from
    `candidate.timestamp()` on that naive value, which resolves back
    through the LOCAL zone. Reintroducing `tz=timezone.utc` here silently
    shifts every computed fire time by the system's UTC offset (a live bug,
    fixed 2026-08-31: 6h in MDT — the daily job, Hour=5/Minute=10, computed
    as the previous day's 23:10 instead of the real 05:10 local fire; a
    weekly/monthly job's error compounds up to a full day-boundary miss,
    e.g. `loop`'s worst case ~66h) — both a false-positive "fire" that
    hasn't happened yet and a false-negative miss of a real one are live
    against GRACE_SECONDS at that magnitude.

    Pure; NO plausibility prefilter — this is a full brute-force scan, not
    an optimized search: for each of the last `_CALENDAR_SEARCH_DAYS` days
    (today first), it checks every whole minute that day (1440 candidates)
    against every rule, from 23:59 down to 00:00, returning the first
    (latest) match; a `now_epoch` that lands early in the current day (so
    today has no match yet) simply falls through to the previous day, and
    so on back to the search bound. Worst case (no rule ever matches, e.g.
    a garbage Day=31-on-a-short-month-only rule) scans the full
    `_CALENDAR_SEARCH_DAYS` * 1440 minutes — measured ≤0.19s on this
    machine, acceptable for a report-only audit run at most a few times a
    day.

    Returns None when `interval` cannot be normalized into calendar rules
    (see `_normalize_calendar_rules`) or when `now_epoch` is not a real
    number, or when NO match is found within the search bound (a
    malformed rule, e.g. Day=31 on a schedule that never actually reaches
    day 31 within the window — vanishingly unlikely for a real launchd
    job, but never silently treated as "never fires"/"always fires").
    Never raises.
    """
    if not _is_finite_number(now_epoch):
        return None
    rules = _normalize_calendar_rules(interval)
    if not rules:
        return None
    try:
        # LOCAL time, deliberately -- launchd interprets StartCalendarInterval
        # in the SYSTEM's local timezone, never UTC (this was a live bug: the
        # prior tz=timezone.utc framing put every computed fire time off by
        # the system's UTC offset -- 6h in MDT, measured live: the daily job
        # (Hour=5,Minute=10) computed as 08-30 23:10 instead of the real
        # 08-31 05:10, and a monthly/weekly job's error compounds up to the
        # full day-boundary gap, e.g. loop's worst case ~66h -- both a
        # false-positive "fire" that hasn't actually happened yet and a
        # false-negative miss of a real one are live against GRACE_SECONDS,
        # e.g. the daily job's own 05:10 pre-step could false-alarm on a
        # sibling job 50 minutes after that job's OWN successful local fire).
        # A naive datetime built via fromtimestamp() with no tz argument is
        # the system's local wall-clock reading of now_epoch -- launchd's own
        # frame -- so every candidate built from it below is already in the
        # right zone, and `candidate.timestamp()` (called on that same naive
        # value) correctly resolves back through the LOCAL zone to a real
        # epoch, not through UTC.
        now_dt = datetime.fromtimestamp(now_epoch)
    except Exception:
        return None
    day = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(_CALENDAR_SEARCH_DAYS):
        for minute_of_day in range(24 * 60 - 1, -1, -1):
            candidate = day + timedelta(minutes=minute_of_day)
            if candidate > now_dt:
                continue
            for rule in rules:
                try:
                    if _rule_matches(rule, candidate):
                        return candidate.timestamp()
                except Exception:
                    continue
        day -= timedelta(days=1)
    return None


def _is_finite_number(v: object) -> bool:
    """True for a real, finite int/float (excludes bool, NaN, inf, None,
    strings). Shared guard so a malformed `now_epoch` degrades to "cannot
    determine", never a crash or a silently-wrong comparison."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        import math

        return math.isfinite(v)
    except Exception:
        return False


def _read_plist_calendar_interval(label: str, launch_agents_dir: str) -> object | None:
    """Read a job's own `StartCalendarInterval` value straight from its
    installed plist (following the `~/Library/LaunchAgents/` symlink to
    the committed `~/.claude/schedules/*.plist`, the same file launchd
    itself loaded) — the calendar-exact ground truth this module's own §2
    table cadence TEXT can only approximate. None when the plist is
    missing/unreadable/unparseable or carries no `StartCalendarInterval`
    key at all — callers must treat that as "schedule unknown", never as
    "fires every minute" (an empty/missing key is NOT a wildcard rule
    here, even though launchd itself would treat a truly EMPTY dict that
    way — a missing top-level key means this reader learned nothing, a
    materially different, less certain state).
    """
    path = os.path.join(launch_agents_dir, f"{label}.plist")
    try:
        with open(path, "rb") as fh:
            data = plistlib.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict) or "StartCalendarInterval" not in data:
        return None
    return data["StartCalendarInterval"]


def _read_heartbeats(heartbeats_dir: str) -> dict[str, dict | str]:
    """stem -> parsed JSON object, or stem -> "ERROR: ..." string on failure.

    Files starting with `_` are skipped (the shared `_disabled_window.jsonl`
    marker and any one-off `_install_probe.json` — neither is a per-job
    heartbeat; _preamble.txt states the audit's glob ignores the former, and
    this module extends the same skip to any underscore-prefixed file).
    A directory-level failure (unreadable heartbeats/ itself) is reported as
    the single key `__dir_error__` so the caller can distinguish "no jobs
    have ever fired" from "I could not even list the directory".
    """
    try:
        names = sorted(
            f for f in os.listdir(heartbeats_dir) if f.endswith(".json") and not f.startswith("_")
        )
    except Exception as exc:
        return {"__dir_error__": f"cannot list {heartbeats_dir}: {exc.__class__.__name__}"}

    out: dict[str, dict | str] = {}
    for fname in names:
        stem = fname[: -len(".json")]
        path = os.path.join(heartbeats_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            out[stem] = data if isinstance(data, dict) else f"ERROR: {fname} is not a JSON object"
        except Exception as exc:
            out[stem] = f"ERROR: {fname} unreadable/unparseable: {exc.__class__.__name__}"
    return out


_WHEEL_LABEL_RE = re.compile(r"^(com\.oversight\.wheel\.|manual-wheel-)")


def _is_wheel_label(label: str) -> bool:
    """True for a wheel job label — `com.oversight.wheel.*` (scheduled) or `manual-wheel-*`
    (`/wheel`) — the same two families 1b's own `_is_wheel_label` in `wheel_history.py` treats as
    wheel labels. Kept as an independent, local copy (never a cross-module import) so this
    module's own IO layer never depends on `wheel_history.py` importing successfully."""
    return bool(_WHEEL_LABEL_RE.match(label))


def _wheel_launch_context_tools() -> set[str] | None:
    """The lower-cased set of tool names in `wheel_launch_context.TOOLS`, or None on ANY failure
    (import error, missing attribute, non-string value, a renamed/moved module) — check #11
    (`wheel-grant-contradiction`) must degrade to "grant set unknown, skip this check entirely"
    rather than ever crash the whole audit run over an unrelated module's own drift. Read fresh on
    every call (this module is a short-lived report-only process; there is no benefit to caching
    across a single run, and caching would risk staleness across repeated test invocations that
    reload the module under different sys.path setups)."""
    try:
        import wheel_launch_context  # local import: keeps this module's own top-level import list

        raw = wheel_launch_context.TOOLS
        if not isinstance(raw, str):
            return None
        return {tool.strip().lower() for tool in raw.split(",") if tool.strip()}
    except Exception:
        return None


_TOOL_UNAVAILABLE_RE = re.compile(r"([A-Za-z0-9_]+)-tool-unavailable", re.IGNORECASE)


def _degraded_reason_contradicts_grant(degraded_reason: object, granted_tools_lower: set[str]) -> str | None:
    """Returns the offending tool name (as it appeared in `degraded_reason`) when
    `degraded_reason` names a `<tool>-tool-unavailable` shape for a tool that IS in
    `granted_tools_lower` (already lower-cased) — else None. `degraded_reason` may be a plain
    string or a `+`-joined multi-reason string (see `issue_wheel_queue.py`'s own convention); every
    reason segment is checked independently, so a compound reason still catches a contradiction in
    any one segment. A non-string `degraded_reason` (missing, null, wrong type) yields None —
    "cannot determine" is never treated as a contradiction, the module-wide convention."""
    if not isinstance(degraded_reason, str) or not degraded_reason:
        return None
    for segment in degraded_reason.split("+"):
        match = _TOOL_UNAVAILABLE_RE.search(segment.strip())
        if not match:
            continue
        tool = match.group(1)
        if tool.lower() in granted_tools_lower:
            return tool
    return None


def _read_recent_history_records(history_dir: str, label: str, now_epoch: float, window_seconds: float) -> list[dict]:
    """Every JSON-object record in `history_dir/<label>.jsonl` whose OWN `finished_at` (falling
    back to `started_at` when `finished_at` is absent/null — an in-flight or refused-early record
    may carry no finished_at) parses as a UTC timestamp within the last `window_seconds` of
    `now_epoch`. A record with neither a parseable `finished_at` nor `started_at` is still
    INCLUDED (never silently dropped) — check #11 only reads `degraded_reason` off it, which does
    not depend on timestamp recency being provable; excluding it would risk hiding a genuine
    contradiction behind an unrelated timestamp-parsing gap. Missing file, unreadable file, or a
    line that fails to parse as a JSON object are all silently skipped — this is a best-effort
    recovery read for a report-only check, never a hard requirement."""
    path = os.path.join(history_dir, f"{label}.jsonl")
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return out
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        ts_str = obj.get("finished_at") or obj.get("started_at")
        if isinstance(ts_str, str):
            ts_epoch = _parse_utc_z(ts_str)
            if ts_epoch is not None and (now_epoch - ts_epoch) > window_seconds:
                continue  # outside the window -- provably too old, skip
        out.append(obj)
    return out


def _parse_utc_z(ts_str: str) -> float | None:
    """Parses a `YYYY-MM-DDTHH:MM:SS(.ffffff)?Z` timestamp into a UTC epoch float, or None on any
    failure — never raises."""
    if not _UTC_TS_RE.match(ts_str):
        return None
    try:
        cleaned = ts_str[:-1] + "+00:00"  # swap trailing Z for an explicit offset
        return datetime.fromisoformat(cleaned).timestamp()
    except Exception:
        return None


def _log_times(logs_dir: str, label: str) -> tuple[float | None, float | None]:
    """(approx_start_epoch, approx_finish_epoch) from a job's own log files.

    Uses each file's own MTIME, never creation time: launchd (re)opens
    StandardErrorPath/StandardOutPath at every firing, so `.err.log`'s mtime
    (rarely touched again after that unless a real error occurs) is a
    reliable start proxy on every run — INCLUDING a job whose log files
    persist and accumulate content across many firings, where file creation
    time reflects only the very first firing ever. Measured live
    (2026-08-25): `com.oversight.csa.daily.err.log`'s creation time was a
    full day stale on its second real run, while its mtime matched the
    heartbeat's own started_at to within one second — creation time is not a
    safe start proxy for a log that outlives a single run; mtime is.
    `.out.log`'s mtime (written throughout the run) is the finish proxy.
    Falls back to whichever single file exists when only one does. (None,
    None) when neither log file exists for this label. macOS/Linux portable
    (mtime only — no `st_birthtime` dependency). Every wrapper-owned early
    exit in `run_oversight_job.sh` (kill switch, launch-context refusal,
    second-slot skip, quota skip, lock refusal, empty prompt) prints one
    `WRAPPER:` line to `.out.log` as it stamps `finished_at` (GH #4767), so
    the finish proxy is fresh for wrapper-written heartbeats too.
    """
    err_mtime = out_mtime = None
    try:
        err_mtime = os.stat(os.path.join(logs_dir, f"{label}.err.log")).st_mtime
    except OSError:
        pass
    try:
        out_mtime = os.stat(os.path.join(logs_dir, f"{label}.out.log")).st_mtime
    except OSError:
        pass
    if err_mtime is None and out_mtime is None:
        return (None, None)
    start = err_mtime if err_mtime is not None else out_mtime
    finish = out_mtime if out_mtime is not None else err_mtime
    return (start, finish)


def _launchctl_loaded_labels() -> set[str] | None:
    """Every currently-loaded label containing 'com.oversight', or None when
    `launchctl list` could not be read (non-macOS, command missing, timeout,
    non-zero exit). None is a distinct "unknown" state — callers must not
    treat it as "nothing is loaded".
    """
    try:
        proc = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    labels: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        label = parts[-1]
        if label == "Label":
            continue
        if "com.oversight" in label:
            labels.add(label)
    return labels


def _parse_epoch(ts: object) -> float | None:
    """Best-effort epoch-seconds for a heartbeat timestamp string, or None.

    Used only for the divergence check, so it is deliberately lenient: even a
    non-UTC-Z-conformant offset (already flagged separately by the format
    check) still parses here if `datetime.fromisoformat` can read it.
    """
    if not isinstance(ts, str) or not ts:
        return None
    try:
        normalized = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return datetime.fromisoformat(normalized).timestamp()
    except Exception:
        return None


def _is_manual(stem: str) -> bool:
    return stem.startswith("manual-")


def _is_inflight_start(data: dict) -> bool:
    """True for a START heartbeat still in flight: finished_at is null AND
    the summary is the literal "STARTED ..." shape _preamble.txt's step 3
    writes. Such a heartbeat legitimately lacks the END-only fields (a valid
    finished_at, and — for the daily job — its typed rotation keys), which
    would otherwise misfire as violations for a run that simply hasn't
    finished yet.
    """
    summary = data.get("summary")
    return data.get("finished_at") is None and isinstance(summary, str) and summary.startswith(
        "STARTED"
    )


def _divergence_line(stem: str, field: str, hb_epoch: float, log_epoch: float) -> str:
    """One timestamp-divergence-class violation line, directionally labeled.

    The heartbeat being NEWER than its own log evidence is the fabrication-
    shaped anomaly (`timestamp-divergence`); the heartbeat being OLDER than
    its log is a distinct, milder anomaly (`heartbeat-older-than-log`) —
    most plausibly a rotated/re-touched log file bumping the log's own mtime
    forward after the heartbeat was already written, not a fabricated claim.
    """
    minutes = abs(hb_epoch - log_epoch) / 60
    if hb_epoch < log_epoch:
        return (
            f"heartbeat-older-than-log: {stem}.json {field} is {minutes:.1f} min OLDER than "
            "its log file's own timestamp (> 5 min threshold) — likely a rotated/re-touched "
            "log file, not a fabricated timestamp"
        )
    return (
        f"timestamp-divergence: {stem}.json {field} diverges from its log file's own "
        f"timestamp by {minutes:.1f} min (> 5 min threshold) — possible fabricated timestamp"
    )


def check(
    table_labels: list[str] | None,
    table_parse_error: str | None,
    heartbeats: dict[str, dict | str],
    log_times: dict[str, tuple[float | None, float | None]],
    loaded_labels: set[str] | None,
    daily_job_label: str = DEFAULT_DAILY_JOB_LABEL,
    table_cadences: dict[str, str] | None = None,
    table_expected_states: dict[str, str] | None = None,
    plist_install_epochs: dict[str, float] | None = None,
    now_epoch: float | None = None,
    plist_calendar_intervals: dict[str, object] | None = None,
    wheel_granted_tools: set[str] | None = None,
    wheel_history_records: dict[str, list[dict]] | None = None,
) -> list[str]:
    """Decision function over pre-gathered inputs. See module docstring for
    the checks. NOTE (2026-09-07, B-1 review fix): check #7
    (relative-artifact-claim) is the ONE exception to "no IO" — it calls
    `heartbeat_artifact_stamp.resolve_claim`, which does a real
    `os.path.exists` filesystem read, to reality-gate a path-shaped token
    against ordinary prose (see check #7's own inline comment). Every other
    check below remains a pure function of its inputs. That one read is
    wrapped in its own try/except (skip-on-failure, never a crash).

    `table_cadences` (label -> the §2 table's raw cadence-text),
    `table_expected_states` (label -> the §2 table's `expected_state`
    column, e.g. "loaded" — see check #2c, `expected-but-unloaded`),
    `plist_install_epochs` (label -> its LaunchAgents symlink's mtime),
    `now_epoch` (the caller's own clock read, never read internally so this
    stays a pure function of its inputs), and `plist_calendar_intervals`
    (label -> its plist's own `StartCalendarInterval` value, see
    `_read_plist_calendar_interval`) gate the loaded-never-fired "not yet
    due" exemption, the CALENDAR-EXACT silent-job check, and the
    stale-start check. Missing any of these for a given job degrades to
    the conservative default for that check (see each check's own comment
    below) rather than guessing.

    `wheel_granted_tools` (the lower-cased `wheel_launch_context.TOOLS` set,
    or None if unreadable) and `wheel_history_records` (label -> its last-48h
    history records, wheel labels only) feed check #11
    (`wheel-grant-contradiction`) only.

    Never raises: any per-item failure degrades to a specific violation
    string rather than propagating.
    """
    out: list[str] = []
    table_cadences = table_cadences or {}
    table_expected_states = table_expected_states or {}
    plist_install_epochs = plist_install_epochs or {}
    plist_calendar_intervals = plist_calendar_intervals or {}
    wheel_history_records = wheel_history_records or {}

    dir_error = heartbeats.get("__dir_error__")
    if dir_error is not None:
        out.append(f"heartbeats-dir-unreadable: {dir_error}")
        if table_parse_error is not None:
            out.append(f"table-parse-failed: {table_parse_error}")
        return out

    if table_parse_error is not None:
        out.append(
            "table-parse-failed: "
            + table_parse_error
            + " — the expected-job-set diff (missing/unexpected heartbeats) is SKIPPED "
            "this run; per-heartbeat structural validation below still ran"
        )
        table_set: set[str] = set()
    else:
        table_set = set(table_labels or [])

    # 1. unexpected heartbeats: present, not in table, not manual-*.
    if table_parse_error is None:
        for stem in sorted(heartbeats):
            if stem in table_set or _is_manual(stem):
                continue
            out.append(
                f"unexpected-heartbeat: {stem}.json is not in oversight_install.md's §2 "
                "job table and is not a manual-* fallback heartbeat"
            )

    # 2. loaded-never-fired: loaded in launchctl, expected per the table, but
    #    no heartbeat file has ever been written for it — UNLESS at least one
    #    full cadence period hasn't yet elapsed since the plist was
    #    installed, in which case it simply isn't due yet. When the cadence
    #    or install-time data needed to prove "not yet due" is unavailable,
    #    this falls back to the old, conservative behavior: flag it.
    if loaded_labels is None:
        out.append(
            "launchctl-unavailable: could not read `launchctl list` — "
            "loaded-never-fired check UNVERIFIED this run"
        )
    else:
        for label in sorted(table_set & loaded_labels):
            if label in heartbeats:
                continue
            threshold = cadence_seconds(table_cadences.get(label, ""))
            install_epoch = plist_install_epochs.get(label)
            if threshold is not None and install_epoch is not None and now_epoch is not None:
                elapsed = now_epoch - install_epoch
                if elapsed < threshold + GRACE_SECONDS:
                    continue  # not yet due — no first firing expected yet
            out.append(
                f"loaded-never-fired: {label} is loaded in launchctl but has never "
                "written a heartbeat file"
            )

    # 2b. silent-job: CALENDAR-EXACT complement to loaded-never-fired above.
    #     loaded-never-fired's "not yet due" exemption relies on
    #     cadence_seconds()'s WORST-CASE approximation (e.g. a monthly job
    #     reads as "31 days between fires" with no notion of which day of
    #     the month it actually fires on) — a job installed a week ago can
    #     sail through that exemption even once its own actual scheduled
    #     minute (read straight from its plist's StartCalendarInterval) has
    #     genuinely passed. This check asks the more precise question
    #     directly: for a job loaded in launchctl and expected per the
    #     table, has ANY of its calendar rules matched a real minute in the
    #     past (beyond GRACE_SECONDS) with still no heartbeat file on
    #     disk — regardless of whether cadence_seconds() would have called
    #     it "due" yet? Named `silent-job` (distinct from
    #     `loaded-never-fired`) so a job that never wrote a heartbeat AND
    #     has a determinable overdue calendar fire is flagged by name even
    #     when the coarser exemption above stayed silent. Skipped entirely
    #     (never a violation) when the plist's own StartCalendarInterval
    #     can't be read/parsed — "cannot determine" is never treated as
    #     "overdue". ALSO skipped when the most-recent matching calendar
    #     minute predates this job's own plist install epoch (same floor
    #     loaded-never-fired already applies above, via elapsed-since-
    #     install) — a job installed mid-period is not overdue just
    #     because the calendar walk-back lands on a date before it
    #     existed. Degrades to the OLD, conservative "flag it" behavior
    #     when the install epoch itself is unavailable.
    if loaded_labels is not None:
        for label in sorted(table_set & loaded_labels):
            if label in heartbeats:
                continue
            interval = plist_calendar_intervals.get(label)
            if interval is None or now_epoch is None:
                continue
            fire_epoch = most_recent_scheduled_fire(interval, now_epoch)
            if fire_epoch is None:
                continue
            install_epoch = plist_install_epochs.get(label)
            if install_epoch is not None and fire_epoch < install_epoch:
                # The most recent matching calendar minute predates this
                # job's own (re)install — mirrors loaded-never-fired's
                # "not yet due" exemption above, which already applies this
                # floor via elapsed-since-install. A monthly job installed
                # two days ago has not reached its first real fire yet;
                # that is not a violation, not "cannot determine".
                continue
            overdue_by = now_epoch - fire_epoch
            if overdue_by > GRACE_SECONDS:
                out.append(
                    f"silent-job: {label} was scheduled to fire "
                    f"{overdue_by / 3600:.1f}h ago (per its own plist "
                    "StartCalendarInterval) but has never written a heartbeat file"
                )

    # 2c. expected-but-unloaded (H1, THE ISSUE WHEEL hardening plan): a label
    #     whose §2 table `expected_state` column reads "loaded" but is
    #     absent from `loaded_labels` — the mechanism that catches "someone
    #     unloaded the job (or it was never loaded to begin with) and nobody
    #     noticed." Distinct from `silent-job`/`loaded-never-fired`, which
    #     both require the job to already BE loaded (they read
    #     `table_set & loaded_labels`) and only then ask whether it has gone
    #     quiet — this check is the complementary case: the job isn't even
    #     loaded in the first place. A pure set-difference between
    #     `expected_state=='loaded'` labels and `loaded_labels` — unlike its
    #     siblings above, it needs no `now_epoch`/cadence/install-time data
    #     at all, so it is never gated on anything but `loaded_labels`
    #     itself being readable. Only ever evaluated for labels the table
    #     actually declares `expected_state: loaded` for — a label with a
    #     missing/unparseable/other `expected_state` value degrades to the
    #     same conservative "cannot determine, not a violation" direction
    #     every other check in this module already uses (never flagged
    #     here), matching the existing convention at the loaded-never-fired
    #     and silent-job checks above.
    if loaded_labels is not None:
        for label in sorted(table_set):
            if table_expected_states.get(label) != "loaded":
                continue
            if label in loaded_labels:
                continue
            out.append(
                f"expected-but-unloaded: {label} has expected_state 'loaded' in "
                "oversight_install.md's §2 job table but is not currently loaded "
                "in launchctl"
            )

    # 2d. unexpected-loaded (THE ISSUE WHEEL plan, WS1-B.3 / Phase B item 3):
    #     the MIRROR of 2c above — a label the table declares a NON-"loaded"
    #     expected_state for (e.g. "unloaded", the value every not-yet-
    #     activated wheel plist carries) that IS nonetheless present in
    #     `loaded_labels` right now. 2c only ever catches "table says loaded,
    #     launchctl says no"; this catches the opposite drift: "table says
    #     NOT loaded, launchctl says yes" — e.g. a plist `launchctl load`ed
    #     by hand without the table ever being updated to match. Same
    #     degrade convention as every sibling check: a label whose
    #     `expected_state` is missing/unparseable is never flagged either
    #     direction, and a label absent from the table entirely is
    #     `unexpected-heartbeat`'s lane, not this one.
    if loaded_labels is not None:
        for label in sorted(table_set):
            expected = table_expected_states.get(label)
            if not expected or expected == "loaded":
                continue
            if label not in loaded_labels:
                continue
            out.append(
                f"unexpected-loaded: {label} has expected_state {expected!r} in "
                "oversight_install.md's §2 job table but IS currently loaded "
                "in launchctl"
            )

    # 3. per-heartbeat structural validation.
    # Fix round item 6 (WS14-S1 item 1c, GH #4767): dedup set for check #11's live/history halves,
    # keyed on (job_label, started_at) -- declared here, before the loop, since check #11's live
    # half populates it and 11b (after the loop) reads it.
    _already_flagged_wheel_contradictions: set[tuple[str, str]] = set()
    for stem in sorted(heartbeats):
        data = heartbeats[stem]
        if not isinstance(data, dict):
            out.append(f"heartbeat-unreadable: {stem}.json: {data}")
            continue

        inflight = _is_inflight_start(data)

        missing = [k for k in REQUIRED_KEYS if k not in data]
        if missing:
            out.append(f"missing-keys: {stem}.json missing required key(s): {', '.join(missing)}")

        if "pin_suspect" in data and not isinstance(data["pin_suspect"], bool):
            out.append(
                f"bad-type: {stem}.json pin_suspect must be a JSON boolean, "
                f"got {type(data['pin_suspect']).__name__}"
            )

        job_label = data.get("job") if isinstance(data.get("job"), str) else stem
        if job_label == daily_job_label and not inflight:
            missing_daily = [k for k in DAILY_TYPED_KEYS if k not in data]
            if missing_daily:
                out.append(
                    f"missing-daily-keys: {stem}.json (daily job) missing typed key(s): "
                    + ", ".join(missing_daily)
                )
            else:
                dim = data.get("last_rotation_dim")
                if dim is not None and dim not in _ROTATION_DIMS:
                    out.append(
                        f"bad-value: {stem}.json last_rotation_dim={dim!r} not one of "
                        "health|logs|cost|consistency|null"
                    )
                slot = data.get("slot_ran")
                if slot is not None and slot not in _ROTATION_DIMS:
                    out.append(
                        f"bad-value: {stem}.json slot_ran={slot!r} not one of "
                        "health|logs|cost|consistency"
                    )
                rev = data.get("last_staging_revision")
                if rev is not None and not isinstance(rev, str):
                    out.append(
                        f"bad-type: {stem}.json last_staging_revision must be a string "
                        f"or null, got {type(rev).__name__}"
                    )

        for field in ("started_at", "finished_at"):
            if inflight and field == "finished_at":
                continue  # legitimately null while a START is in flight
            val = data.get(field)
            if not isinstance(val, str) or not _UTC_TS_RE.match(val):
                out.append(
                    f"bad-timestamp-format: {stem}.json field '{field}'={val!r} is not "
                    "UTC Z ISO-8601 (expected YYYY-MM-DDTHH:MM:SSZ)"
                )

        # 5. stale-start: an in-flight START older than its own cadence+grace.
        if inflight:
            cadence_text = table_cadences.get(job_label, "")
            threshold = cadence_seconds(cadence_text)
            hb_start = _parse_epoch(data.get("started_at"))
            if threshold is not None and now_epoch is not None and hb_start is not None:
                age = now_epoch - hb_start
                if age > threshold + GRACE_SECONDS:
                    out.append(
                        f"stale-start: {stem}.json ({job_label}) has been STARTED for "
                        f"{age / 3600:.1f}h, beyond its cadence+grace — the run most likely "
                        "died mid-flight without ever writing its END heartbeat"
                    )

        # 5b. dangling-heartbeat (AUDIT FINDING 2, 2026-09-03): a HARD, UNCONDITIONAL
        #     finding for ANY heartbeat with finished_at still null once its own
        #     started_at is older than its job's cadence+grace — regardless of the
        #     summary field's shape. `stale-start` above only fires for the narrow
        #     "STARTED ..." in-flight shape (`_is_inflight_start`); a job that died
        #     after overwriting its summary to something else (or any other
        #     finished_at:null shape that doesn't match that exact prefix) fell
        #     through to the generic, cadence-blind `bad-timestamp-format` line
        #     instead — indistinguishable from a heartbeat that started 30 seconds
        #     ago and simply hasn't finished yet. That is exactly the gap that let
        #     steward sit dead for 2 days while the daily sweep caught productqa but
        #     not steward: surfacing a dead job was a judgment call, not mechanical.
        #     PRECISION (corrected 2026-09-03 review — the earlier wording here
        #     claimed this fires "unconditionally, regardless of summary shape",
        #     which the `elif` below makes false): this branch is the COMPLEMENT of
        #     `stale-start` above. `stale-start` covers the in-flight "STARTED ..."
        #     summary shape; this 5b branch covers every OTHER finished_at:null
        #     shape (summary overwritten, absent, or malformed). Together the
        #     if/elif pair covers ALL dead heartbeats — one line per dead job, with
        #     days-dead in the message so it cannot be mistaken for a routine
        #     format nit — but neither branch alone is unconditional. Skipped
        #     (never guessed) only when
        #     the cadence or started_at data needed to prove staleness is itself
        #     unavailable — "cannot determine" is never treated as "overdue", same
        #     convention as every other cadence-gated check in this module.
        elif data.get("finished_at") is None:
            cadence_text = table_cadences.get(job_label, "")
            threshold = cadence_seconds(cadence_text)
            hb_start = _parse_epoch(data.get("started_at"))
            if threshold is not None and now_epoch is not None and hb_start is not None:
                age = now_epoch - hb_start
                if age > threshold + GRACE_SECONDS:
                    out.append(
                        f"dangling-heartbeat: {stem}.json ({job_label}) has finished_at:null "
                        f"and started {age / 86400:.1f}d ago — beyond its cadence+grace, so "
                        "this run most likely died mid-flight and never wrote its END "
                        "heartbeat; it will read as a completed run to anything that only "
                        "checks for the file's existence"
                    )

        log_start, log_finish = log_times.get(stem, (None, None))
        if log_start is not None:
            hb_start = _parse_epoch(data.get("started_at"))
            if hb_start is not None and abs(hb_start - log_start) > DIVERGENCE_THRESHOLD_SEC:
                out.append(_divergence_line(stem, "started_at", hb_start, log_start))
        if log_finish is not None:
            hb_finish = _parse_epoch(data.get("finished_at"))
            if hb_finish is not None and abs(hb_finish - log_finish) > DIVERGENCE_THRESHOLD_SEC:
                out.append(_divergence_line(stem, "finished_at", hb_finish, log_finish))

        # 7. relative-artifact-claim (#5055, 2026-09-07 launchdir false-alarm
        #    incident; REALITY-GATED, B-1 review fix same day): a FINISHED,
        #    non-"WRAPPER:" heartbeat whose summary names a relative-or-"~"
        #    path-shaped token that ALSO RESOLVES to a file that actually
        #    EXISTS is a violation. Uses the SAME extraction+resolution
        #    primitives heartbeat_artifact_stamp.stamp() uses — imported, never
        #    reimplemented, so the two can never drift on what counts as a real
        #    claim. The reality gate is load-bearing: extract_path_claims is
        #    SHAPE-only, so ordinary prose containing a slash ("Clusters C/E",
        #    "dropped 2/5") is shape-indistinguishable from a genuine artifact
        #    claim -- resolving against $HOME/.claude (this check has no
        #    per-job WorkingDirectory to try, unlike stamp() at write-time) and
        #    requiring a real, existing file is what confines this check to the
        #    actual launchdir-incident class, never testarch's own "C/E" prose.
        #    resolve_claim does real filesystem I/O (os.path.exists), which is
        #    the one place this otherwise-pure check() function touches disk;
        #    wrapped in its own try/except so a resolution failure degrades to
        #    "skip this claim", never a crash -- matching this module's
        #    documented "never raises" contract. In-flight START heartbeats are
        #    exempt, same as every other finished-only check above.
        if not inflight:
            summary_val = data.get("summary")
            if isinstance(summary_val, str) and not summary_val.startswith("WRAPPER:"):
                real_relative_claims = []
                for c in extract_path_claims(summary_val):
                    if c.startswith("/") or c.startswith("~"):
                        # Already anchored per _preamble.txt step 5's own
                        # wording (absolute OR ~/.claude/-anchored) --
                        # nothing to flag regardless of whether it resolves
                        # to a real file. A "~"-shaped prose token ("~8h")
                        # simply never resolves, so it never reaches the
                        # reality gate below either way; this branch is
                        # about the genuinely-anchored case, not a gate.
                        continue
                    try:
                        _resolved, exists = resolve_claim(c, None)
                    except Exception:
                        continue  # resolution failure -> skip, never crash
                    if exists:
                        real_relative_claims.append(c)
                if real_relative_claims:
                    out.append(
                        f"relative-artifact-claim: {stem}.json summary names relative "
                        f"artifact path(s) {real_relative_claims!r} that resolve to a "
                        "real file — must be absolute or ~/.claude/-anchored to be "
                        "resolvable without already knowing the job's write "
                        "instruction by heart"
                    )

        # 8. lock-refused (H3, THE ISSUE WHEEL hardening plan, BLOCKER 2):
        #    run_oversight_job.sh's concurrency guard writes exit: 75 with a
        #    FRESH, non-null finished_at when a wheel-slug lock acquisition is
        #    refused (another live run already holds it) — necessary, since
        #    REQUIRED_KEYS/timestamp-format validation above demands a
        #    well-formed finished_at on every non-in-flight heartbeat. But
        #    every liveness check in this module (silent-job,
        #    loaded-never-fired, dangling-heartbeat) keys ONLY on finished_at
        #    being set/recent — none of them read `exit` — so on its own a
        #    refused-run heartbeat is indistinguishable from a clean,
        #    just-finished run and resets the "last heartbeat" clock those
        #    checks use. Left unflagged, an orphaned lock could silently
        #    starve every future run of that slug for up to its alarm ceiling
        #    (or indefinitely under PID reuse) while this module kept
        #    reporting the job healthy. This check is the simplest correct
        #    fix: it needs no new inputs (the FINISHED heartbeat's own `exit`
        #    field is already read by REQUIRED_KEYS/missing-keys validation
        #    above) and no coordination with any other in-progress work — a
        #    pure, local, per-heartbeat structural check, the same shape as
        #    every other check in this function. An in-flight START heartbeat
        #    is exempt (mirrors every finished-only check above — a run that
        #    hasn't finished yet was never refused). `exit` missing or not an
        #    int degrades to "cannot determine, not a violation" — the same
        #    convention as every other check in this module — since
        #    `missing-keys`/`bad-type` above already covers a malformed
        #    `exit` field by name.
        if not inflight:
            exit_val = data.get("exit")
            if isinstance(exit_val, int) and not isinstance(exit_val, bool) and exit_val == 75:
                out.append(
                    f"lock-refused: {stem}.json ({job_label}) has exit: 75 — this run's "
                    "own wheel-slug lock acquisition was refused (another run already held "
                    "it) rather than completing normally. A fresh finished_at on a refused "
                    "run reads as a clean finish to every OTHER check in this module, so "
                    "this is flagged by name — repeated lock-refused heartbeats for the "
                    "same label mean its lock is not being released (a dead holder, or a "
                    "genuinely stuck run) and the slug is starved, not merely busy"
                )

        # 9. job-failed (THE ISSUE WHEEL plan, WS1-B.1 / Phase B item 1): see
        #    the module docstring's check #9 for the full rationale. A
        #    FINISHED heartbeat is flagged when its `status` field is
        #    exactly "failed", OR `status` is absent AND (a non-zero int
        #    `exit` OR a `summary` starting with the wrapper's own
        #    "WRAPPER:" prefix). `status` of "ok"/"skipped-quota"/
        #    "skipped-disabled"/"skipped-throttle" (the four sanctioned non-failure
        #    outcomes; skipped-disabled = the wheel wrapper's kill-switch skip,
        #    GH #4767; skipped-throttle = the pre-flight's server-side-throttle
        #    skip, #5922 -- never counted against the quota streak below)
        #    is never flagged regardless of exit/summary. An in-flight START
        #    heartbeat is exempt, same as every other finished-only check.
        if not inflight:
            status_val = data.get("status")
            summary_val = data.get("summary")
            summary_is_wrapper = (
                isinstance(summary_val, str) and summary_val.startswith("WRAPPER:")
            )
            exit_val = data.get("exit")
            exit_is_nonzero = (
                isinstance(exit_val, int)
                and not isinstance(exit_val, bool)
                and exit_val != 0
            )
            if status_val == "failed":
                out.append(
                    f"job-failed: {stem}.json ({job_label}) has status: \"failed\" — "
                    "this run's own wrapper reported a failed exit path"
                )
            elif status_val is None and (exit_is_nonzero or summary_is_wrapper):
                out.append(
                    f"job-failed: {stem}.json ({job_label}) has no `status` field and "
                    f"(exit={exit_val!r}, summary starts with 'WRAPPER:'={summary_is_wrapper}) "
                    "— a legacy or session-authored heartbeat that reads as a failure by "
                    "exit code or by the wrapper's own fail-fast diagnostic shape "
                    "(#4825/#4791), even though every OTHER liveness check above (which "
                    "key only on a fresh finished_at) would read it as a clean finish"
                )

            # Three consecutive skipped-quota heartbeats for one label mean
            # the account's quota exhaustion has outlasted this job's own
            # same-night retry slot (Phase C item 1's second
            # StartCalendarInterval) and is worth a human noticing — a
            # single skip, or two in a row, is ordinary and NOT flagged.
            # The streak is read directly off THIS heartbeat's own
            # `consecutive_quota_skips` field (written by
            # run_oversight_job.sh, carried forward across consecutive
            # skips) rather than a new state file — see that script's own
            # comment for why the heartbeat itself is sufficient.
            if status_val == "skipped-quota":
                streak = data.get("consecutive_quota_skips")
                if isinstance(streak, int) and not isinstance(streak, bool) and streak >= 3:
                    out.append(
                        f"job-failed: {stem}.json ({job_label}) has status: "
                        f'"skipped-quota" for {streak} consecutive runs — the account\'s '
                        "quota exhaustion has outlasted this job's own same-night retry "
                        "slot and needs a human to look"
                    )

            # #5922 fix round, BLOCKER 1: the mirror check for
            # `skipped-throttle`'s OWN streak counter. A throttle is not
            # quota exhaustion (the account's own usage limit is fine, the
            # server is momentarily rate-limiting requests), so this is
            # never folded into the `consecutive_quota_skips` check above —
            # but leaving a long throttle streak with NO check at all meant
            # a genuinely stuck condition (sustained concurrent load against
            # the account, e.g. another session or a runaway fan-out sharing
            # the same rate limit) alerted nobody, ever, no matter how long
            # it persisted. Same threshold and same "a single skip, or two
            # in a row, is ordinary" convention as the quota check, read off
            # `consecutive_throttle_skips` (written by run_oversight_job.sh,
            # carried forward across consecutive throttle skips, reset by
            # any other prior status including "skipped-quota").
            if status_val == "skipped-throttle":
                streak = data.get("consecutive_throttle_skips")
                if isinstance(streak, int) and not isinstance(streak, bool) and streak >= 3:
                    out.append(
                        f"job-failed: {stem}.json ({job_label}) has status: "
                        f'"skipped-throttle" for {streak} consecutive runs — server-side '
                        "throttle, not quota; check concurrent load (runtime CLAUDE.md §9)"
                    )

        # 11. wheel-grant-contradiction (WS14-S1, item 1c, GH #4767): see the
        #     module docstring's check #11 for the full rationale. Wheel
        #     labels only. Degrades to "skip entirely" when the grant set
        #     itself is unreadable (wheel_granted_tools is None) — a
        #     contradiction can never be PROVEN without knowing what was
        #     actually granted, so "cannot determine" is never flagged, the
        #     same convention every other check in this module follows.
        if wheel_granted_tools and _is_wheel_label(stem):
            live_tool = _degraded_reason_contradicts_grant(data.get("degraded_reason"), wheel_granted_tools)
            if live_tool is not None:
                out.append(
                    f"wheel-grant-contradiction: {stem}.json ({job_label}) reports "
                    f"degraded_reason naming '{live_tool}-tool-unavailable', but '{live_tool}' "
                    "IS present in wheel_launch_context.TOOLS -- a genuinely granted tool "
                    "reporting itself unavailable is a contradiction, not a real grant gap"
                )
                # Fix round item 6 (WS14-S1 item 1c, GH #4767): this exact run is ALSO very likely
                # to appear as its own history line (1b appends every wrapper exit) -- key on
                # `started_at` so the history-half loop below never re-flags the SAME run's
                # contradiction a second time. A non-string/missing started_at is never added (the
                # dedup key must be an unambiguous run identity, never a guess).
                live_started_at = data.get("started_at")
                if isinstance(live_started_at, str) and live_started_at:
                    _already_flagged_wheel_contradictions.add((job_label, live_started_at))

    # 11b. wheel-grant-contradiction, HISTORY half: the 03:30 retry slot
    #      overwrites the primary slot's live heartbeat file before the
    #      05:10 audit ever runs, so a primary-slot contradiction is
    #      otherwise invisible same-morning. Scan the last-48h history
    #      records for every wheel label independently of the live
    #      heartbeat loop above (a label may have zero live heartbeat at
    #      all — e.g. its file was just overwritten by a DIFFERENT slot —
    #      and still have a contradicting history line). Fix round item 6:
    #      a history record whose OWN `started_at` matches a run already
    #      flagged from the live heartbeat above is the SAME run's own
    #      history line (1b appends every wrapper exit, including the
    #      ordinary post-CLI finish that also becomes the live heartbeat) —
    #      skip it here so one real contradiction is never reported twice.
    if wheel_granted_tools:
        for label in sorted(wheel_history_records):
            for record in wheel_history_records[label]:
                history_tool = _degraded_reason_contradicts_grant(
                    record.get("degraded_reason"), wheel_granted_tools
                )
                if history_tool is not None:
                    record_started_at = record.get("started_at")
                    dedup_key = (label, record_started_at) if isinstance(record_started_at, str) else None
                    if dedup_key is not None and dedup_key in _already_flagged_wheel_contradictions:
                        continue
                    out.append(
                        f"wheel-grant-contradiction: {label} history (last 48h) reports "
                        f"degraded_reason naming '{history_tool}-tool-unavailable', but "
                        f"'{history_tool}' IS present in wheel_launch_context.TOOLS -- a "
                        "genuinely granted tool reporting itself unavailable is a "
                        "contradiction, not a real grant gap"
                    )

    return out


def _gather(
    install_doc_path: str,
    heartbeats_dir: str,
    logs_dir: str,
    launch_agents_dir: str = DEFAULT_LAUNCH_AGENTS_DIR,
    history_dir: str | None = None,
    now_epoch: float | None = None,
) -> tuple[
    list[str] | None,
    dict[str, str],
    dict[str, str],
    str | None,
    dict[str, dict | str],
    dict[str, tuple],
    dict[str, float],
    dict[str, object],
    set[str] | None,
    dict[str, list[dict]],
]:
    """The IO adapter: reads the real inputs `check()` needs.

    Returns (table_labels, table_cadences, table_expected_states,
    table_error, heartbeats, log_times, plist_install_epochs,
    plist_calendar_intervals, wheel_granted_tools, wheel_history_records).

    `wheel_granted_tools` (check #11, WS14-S1 item 1c): the lower-cased
    `wheel_launch_context.TOOLS` set, or None if unreadable — read here,
    inside `_wheel_launch_context_tools()`'s own try/except, so an import
    failure of an unrelated module can never crash this whole IO step.

    `wheel_history_records` (check #11): label -> its last-48h history
    records, for wheel labels only (`_is_wheel_label`) — every OTHER label
    maps to an empty list, so check #11 never has to special-case a missing
    key.
    """
    # N5, fix round (WS14-S1 item 1c, GH #4767): default history_dir from THIS CALL's own
    # heartbeats_dir, never from the module-level DEFAULT_HISTORY_DIR constant -- a caller passing
    # a fixture/test heartbeats_dir must never silently read the REAL machine's history directory
    # when it omits history_dir. DEFAULT_HISTORY_DIR remains the right answer only when
    # heartbeats_dir ALSO happens to be the real DEFAULT_HEARTBEATS_DIR (main()'s own call site).
    if history_dir is None:
        history_dir = os.path.join(heartbeats_dir, "history")

    table_labels: list[str] | None = None
    table_cadences: dict[str, str] = {}
    table_expected_states: dict[str, str] = {}
    table_error: str | None = None
    try:
        with open(install_doc_path, encoding="utf-8") as fh:
            doc_text = fh.read()
        rows = parse_job_table(doc_text)
        table_labels = [label for label, _expected_state, _cadence in rows]
        table_expected_states = {
            label: expected_state for label, expected_state, _cadence in rows
        }
        table_cadences = {label: cadence for label, _expected_state, cadence in rows}
    except Exception as exc:
        table_error = f"{install_doc_path}: {exc}"

    heartbeats = _read_heartbeats(heartbeats_dir)
    log_times = {stem: _log_times(logs_dir, stem) for stem in heartbeats if stem != "__dir_error__"}
    plist_install_epochs: dict[str, float] = {}
    plist_calendar_intervals: dict[str, object] = {}
    for label in table_labels or []:
        epoch = _plist_install_epoch(label, launch_agents_dir)
        if epoch is not None:
            plist_install_epochs[label] = epoch
        interval = _read_plist_calendar_interval(label, launch_agents_dir)
        if interval is not None:
            plist_calendar_intervals[label] = interval

    wheel_granted_tools = _wheel_launch_context_tools()

    resolved_now = now_epoch if now_epoch is not None else time.time()
    wheel_history_records: dict[str, list[dict]] = {}
    all_labels = set(table_labels or []) | {s for s in heartbeats if s != "__dir_error__"}
    for label in sorted(all_labels):
        if not _is_wheel_label(label):
            continue
        wheel_history_records[label] = _read_recent_history_records(
            history_dir, label, resolved_now, WHEEL_GRANT_CONTRADICTION_WINDOW_SECONDS
        )

    return (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        heartbeats,
        log_times,
        plist_install_epochs,
        plist_calendar_intervals,
        wheel_granted_tools,
        wheel_history_records,
    )


def main(argv: list[str] | None = None) -> int:
    """Report and exit 0 — ALWAYS 0; this module never blocks anything."""
    argv = list(sys.argv if argv is None else argv)
    install_doc = argv[1] if len(argv) > 1 else DEFAULT_INSTALL_DOC
    heartbeats_dir = argv[2] if len(argv) > 2 else DEFAULT_HEARTBEATS_DIR
    logs_dir = argv[3] if len(argv) > 3 else DEFAULT_LOGS_DIR
    launch_agents_dir = argv[4] if len(argv) > 4 else DEFAULT_LAUNCH_AGENTS_DIR
    try:
        now = time.time()
        (
            table_labels,
            table_cadences,
            table_expected_states,
            table_error,
            heartbeats,
            log_times,
            plist_install_epochs,
            plist_calendar_intervals,
            wheel_granted_tools,
            wheel_history_records,
        ) = _gather(install_doc, heartbeats_dir, logs_dir, launch_agents_dir, now_epoch=now)
        loaded_labels = _launchctl_loaded_labels()
        violations = check(
            table_labels,
            table_error,
            heartbeats,
            log_times,
            loaded_labels,
            table_cadences=table_cadences,
            table_expected_states=table_expected_states,
            plist_install_epochs=plist_install_epochs,
            now_epoch=now,
            plist_calendar_intervals=plist_calendar_intervals,
            wheel_granted_tools=wheel_granted_tools,
            wheel_history_records=wheel_history_records,
        )
    except Exception as exc:
        violations = [f"heartbeat-audit-crashed: {exc.__class__.__name__}: {exc}"]
    for line in violations:
        print(line)
    print(f"heartbeat_audit: {len(violations)} violation(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
