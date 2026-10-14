#!/usr/bin/env python3
"""render_cycle_log — the living HTML log for any self-correcting agent loop.

WHAT THIS IS
------------
A pure RENDERER. It reads "cycle records" — one JSON file per run of any
self-correcting agent loop, in any repo — and produces a single
self-contained HTML file that lets a non-technical operator open it and
follow the story of the loop: what was claimed, what survived verification,
what was rejected and on what grounds, what got fixed, what it cost, and
whether the system is getting better or worse over time.

This module owns NOTHING but rendering. It does not dispatch agents and does
not write telemetry. It DOES import `cycle_telemetry` (via a sys.path shim to
its sibling `hooks/` directory) and calls that library's own metric
functions directly for every metric the two modules share — REVERSED from an
earlier design that deliberately reimplemented each metric here "so it never
breaks if that library's shape changes mid-build." That independence sounded
safe but was not: two independent implementations of the same rule drift,
silently, with no error to catch it — measured twice in review (the
`usd_per_confirmed_defect` denominator including unpriced-cycle findings,
`consolidation_ratio` disagreeing with the library on an empty `raised_by`,
and a closed-enum `symptom_precision` silently dropping an unrecognized
verdict from its denominator instead of counting it as indeterminate like the
library does). A parsing/shape defect in a cycle record is now caught the
same way either module reads it — this renderer's OWN job (reading
malformed/partial JSON without crashing) is unaffected, since normalize_record()
still coerces every field to the shape both this file and cycle_telemetry's
functions expect before either one sees it.

FALSIFIABILITY: `hooks/tests/test_render_cycle_log.py`'s metric-parity test
class exists specifically to make a future re-divergence between this file
and cycle_telemetry fail loudly rather than silently, in case a later change
reintroduces a locally-reimplemented copy of a shared metric.

CANONICAL LOCATION OF THE DATA IT READS
----------------------------------------
    ~/.claude/telemetry/cycles/<system>/<cycle_id>.json

`<system>` is a free-form slug ("estimate-loop", "otherapp-denial-loop",
whatever a given repo's loop calls itself) — NEVER hardcoded here. This
renderer discovers every system that has emitted at least one record and
renders them all, side by side. No repo path and no product name appears
anywhere in this file.

SCHEMA (schema_version 1 OR 2 — BLOCKER 12, round 6: this docstring used to
describe v1 only, long after v2 support actually landed; see
SCHEMA_VERSIONS_SUPPORTED and V2_LIST_FIELDS below, and
cycle_telemetry.py's own module docstring for the formal contract) — every
field below is OPTIONAL from this reader's point of view, because a record
written by a loop mid-development, or hand-edited, or truncated by a crash,
is exactly the case this renderer must survive:

    {
      "schema_version": 1 or 2,
      "system": "<slug>", "repo": "<repo name or null>", "cycle_id": "<slug>",
      "started_at": "<ISO8601Z>", "ended_at": "<ISO8601Z>",
      "dispatches": [ {agent_type, label, model, tokens_total, cost_usd,
                        tool_calls, duration_ms, batch_size, batch_position} ],
      "calibration": {plant_id, planted_in, slot, caught_by: [], missed_by: []},
      "findings": [ {finding_id, raised_by: [], claim_symptom, claim_cause,
                      consolidator_decision, verifier_verdict,
                      verifier_cause_upheld, already_tracked_as,
                      fights_ruling, fix_status} ],
      "cost": {"source": "spend_ledger|reported|unavailable",
                "total_tokens", "total_usd", "reason"},
      "notes": [],
      # v2 is purely ADDITIVE over v1 -- every array below is OPTIONAL and
      # absent entirely on a v1 record (see V2_LIST_FIELDS):
      "runs": [], "reviews": [], "changes": [], "decisions": [],
      "issues_filed": [], "evidence": [], "corrections": [], "verdicts": [],
      "stages": [],
      # calibration_runs -- added 2026-08-29, GH #4648. The GRID form of
      # "calibration" above: many plant AND clean-control rows in one
      # record, expressing a plants-x-trades grader-calibration grid the
      # single "calibration" object cannot. Never replaces it.
      "calibration_runs": [ {plant_id, trade, slot, batch_size, caught_by: [],
                              missed_by: [], false_alarm_finding_ids: []} ]
    }

`cost.source` is a closed 3-way contract, never just two values: "spend_ledger"
(ground truth, priced from the real billed ledger), "reported" (the harness's
own less-reliable per-dispatch figure), or "unavailable" (this cycle's cost
could not be honestly priced at all -- total_tokens/total_usd MUST both be
null and `reason` explains why). A cost/token figure is only ever rendered
with its source labelled, per "THE ONE RULE THAT MATTERS MOST" below.

THE ONE RULE THAT MATTERS MOST: MISSING IS NOT ZERO
-----------------------------------------------------
A prior run of a loop like this reported cost from the harness's own
per-dispatch "tokens" field; the real billed figure (from the spend ledger)
was ~26x higher. That was a confidently wrong number, believed once already.
So: a cost/token total that has no data behind it is rendered as "no cost
data recorded" — in the exact same visual weight as a real number, never as
a bare "$0" or "0" that a skimming reader could mistake for "this cycle was
free." Every totalled cost/token figure on the page names which cycles fed
it and how many were priced from the ground-truth spend ledger versus the
harness's own less-reliable "reported" figure versus not priced at all.

DERIVED METRICS (pure computation, no LLM call, all computed here from the
raw JSON — never trust a pre-computed field the loop itself may have gotten
wrong):
  * symptom_precision  — of findings the verifier could actually adjudicate
    (CONFIRMED / PARTIALLY_CONFIRMED / REFUTED / ALREADY_TRACKED_ELSEWHERE),
    the fraction where something real was actually there (i.e. NOT REFUTED).
  * cause_precision    — of findings where the verifier actually judged the
    raiser's STATED CAUSE (verifier_cause_upheld is not null), the fraction
    upheld. This is the metric that mattered most in the incident that
    motivated this whole system: raisers were right about the symptom 8/9
    times and right about the cause 1/9 times, found only because a human
    read nine reports by hand.
  * duplicate_rate     — fraction of findings that turned out to already be
    tracked elsewhere (already_tracked_as is set).
  * ruling_conflict_rate — fraction of findings that fight a standing ruling
    (fights_ruling is set).
  * consolidation_ratio — average number of raw raiser reports collapsed
    into one finding (sum(len(raised_by)) / count(findings)); None when no
    raiser attribution was recorded at all (not the same as a real 0).
  * plant_catch_by_slot — for calibration plants, catch rate grouped by slot
    across cycles.
  * plant_catch_by_trade / false_alarm_by_trade — added 2026-08-29, GH #4648.
    The calibration_runs[] GRID siblings of plant_catch_by_slot: catch rate
    grouped by TRADE (from plant rows) and false-alarm rate grouped by trade
    (from clean control rows). Both mark a present-but-malformed
    caught_by/missed_by/false_alarm_finding_ids as `unreadable` rather than
    silently reading it as 0 -- a confident 0 there would be exactly the
    kind of wrong number this whole module exists to prevent. The
    false-alarm rate is deliberately UNBOUNDED above 100% (a control that
    draws more than one finding raises false_alarms faster than controls).
  * usd_per_confirmed_defect — total cost (ground-truth-first; see above) /
    count of CONFIRMED-or-PARTIALLY_CONFIRMED findings. None when there is
    no priced cost at all, never a division that silently treats missing
    cost as $0.

USAGE
-----
    python3 ~/.claude/scripts/render_cycle_log.py
    python3 ~/.claude/scripts/render_cycle_log.py --cycles-dir <dir> --out <file>
    python3 ~/.claude/scripts/render_cycle_log.py --system estimate-loop
    python3 ~/.claude/scripts/render_cycle_log.py --open   # also `open`s it (macOS)

Exits 0 always (a rendering problem is shown ON the page, never a crash —
this is a read-only reporting tool and must never wedge an operator's
attempt to see what happened).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

# Import the shared cycle_telemetry library regardless of the caller's cwd or
# pytest rootdir -- this file lives in scripts/, cycle_telemetry.py lives in
# the sibling hooks/ directory (BLOCKER 3: see the module docstring above for
# why this renderer now imports it directly instead of reimplementing its
# metrics).
_HOOKS_DIR = str(Path(__file__).resolve().parent.parent / "hooks")
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it under pytest
    sys.path.insert(0, _HOOKS_DIR)

import cycle_telemetry as ct  # noqa: E402  (import after sys.path shim)

DEFAULT_CYCLES_DIR = Path.home() / ".claude" / "telemetry" / "cycles"
DEFAULT_OUTPUT = Path.home() / ".claude" / "telemetry" / "cycle_log.html"

# v2 is purely additive over v1 (see cycle_telemetry.py's module docstring) --
# both versions render identically well; a record declaring either is fully
# supported, never flagged as a quality-note surprise.
SCHEMA_VERSIONS_SUPPORTED = {1, 2}

# v2 optional top-level arrays this renderer knows how to display. Every one
# is OPTIONAL on a record (a v1 record has none of them) -- see README.md's
# "Schema v2" section and cycle_telemetry.py's module docstring for what each
# array means and which completeness gap it closes.
V2_LIST_FIELDS = (
    "runs",
    "reviews",
    "changes",
    "decisions",
    "issues_filed",
    "evidence",
    "corrections",
    "verdicts",
    "stages",
    "calibration_runs",
)
# This tuple is a hand-maintained COPY of the LIST-shaped members of
# cycle_telemetry.OPTIONAL_TOP_KEYS -- it deliberately excludes
# `undispatched_verdict_rows` (added 2026-09-07, round-25 structural-conflict
# fix), which is an OBJECT like `calibration`/`cost`, not a list, and gets
# its own dedicated object-coercion block in normalize_record() instead (see
# that block, right after the `cost` one). What V2_LIST_FIELDS membership
# buys calibration_runs: the same defensive list-coercion (non-dict rows
# dropped) and "ignored" quality note every other v2 array already gets,
# NOTHING MORE -- normalize_record() does `out = dict(raw)`, a full shallow
# copy with no whitelisting, so an unlisted key is never stripped or hidden
# from ct.aggregate_metrics() (it reads CycleRecord.raw directly regardless
# of this tuple's membership). This tuple, PLUS the object-shaped optional
# keys handled by their own dedicated blocks (currently just
# `undispatched_verdict_rows`; `calibration`/`cost` are v1, not v2, but
# follow the identical pattern), must together equal OPTIONAL_TOP_KEYS to
# prevent FUTURE drift of this defensive coercion.
# test_render_cycle_log.py asserts
# set(V2_LIST_FIELDS) | V2_OBJECT_FIELDS == set(ct.OPTIONAL_TOP_KEYS).
V2_OBJECT_FIELDS = frozenset({"undispatched_verdict_rows"})

# NOTE (BLOCKER 3): the closed-enum verdict sets that USED to live here
# (DETERMINATE_VERDICTS / SYMPTOM_REAL_VERDICTS / CONFIRMED_VERDICTS) drove
# hand-reimplemented copies of symptom_precision()/usd_per_confirmed_defect()
# that silently diverged from cycle_telemetry's own definitions -- removed
# together with those functions; see analyze() below, which now calls
# ct.aggregate_metrics() directly. KNOWN_CONSOLIDATOR_DECISIONS /
# KNOWN_VERIFIER_VERDICTS / VERDICT_VALUES_KNOWN below are unrelated (display
# badge "known vs unrecognized value" styling only) and are unaffected.

KNOWN_CONSOLIDATOR_DECISIONS = {"ACCEPT", "REJECT", "CONTESTED", "GC_DEFAULT", "HINT_WORTHY"}
KNOWN_VERIFIER_VERDICTS = {
    "CONFIRMED",
    "PARTIALLY_CONFIRMED",
    "REFUTED",
    "ALREADY_TRACKED_ELSEWHERE",
    "UNVERIFIABLE",
}
VERDICT_VALUES_KNOWN = {"CONCUR", "DISSENT"}


# --------------------------------------------------------------------------
# Loading — defensive by construction. A malformed FILE (can't parse as
# JSON, or isn't an object) is excluded and reported separately. A malformed
# FIELD inside an otherwise-valid record is coerced to its expected shape
# and the coercion is recorded as a quality note attached to that record, so
# nothing is silently dropped without a trace on the page.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadIssue:
    """A cycle FILE that could not be treated as a cycle record at all."""

    path: str
    reason: str


@dataclass(frozen=True)
class CycleRecord:
    """One successfully-parsed cycle record plus its load-time provenance.

    `has_findings` (coordinator review, item 4): captures whether the
    SOURCE JSON actually carried a `findings` key shaped as a list, before
    `normalize_record()`'s own coercion collapses "key absent" and "key
    present as `[]`" into the same `raw["findings"] == []` -- a
    deliberate, documented property of that function (see its own
    docstring) that the parity-critical `analyze()`/`aggregate_metrics()`
    path must keep relying on (an absent key and a genuinely empty list
    are computed identically for every metric, and must stay that way to
    match `cycle_telemetry.py`'s own contract). This field is populated
    ONLY at `load_cycle_records()`'s own loading boundary, straight off
    the pre-normalization parsed dict, and is read ONLY by rendering code
    (the executive summary's headline cell) -- it never feeds `raw`,
    never feeds a metric, and normalize_record/analyze are unaware it
    exists. Defaults to True (findings assumed present) so every
    pre-existing direct `CycleRecord(...)` construction elsewhere in this
    module/its tests -- which never supplies this field -- keeps its
    original, unaffected rendering behavior rather than being silently
    reinterpreted as "not recorded"."""

    path: str
    system: str
    cycle_id: str
    raw: dict[str, Any]
    quality_notes: tuple[str, ...]
    has_findings: bool = True

    def sort_key(self) -> tuple[str, str, str]:
        started = self.raw.get("started_at")
        ended = self.raw.get("ended_at")
        anchor = started if isinstance(started, str) and started else (
            ended if isinstance(ended, str) and ended else ""
        )
        return (anchor, self.cycle_id, self.path)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    """Like _safe_list(), but also drops any list ITEM that isn't itself a
    dict -- for a field whose entries are always read via `.get()`
    downstream (e.g. a review's own nested `findings` array)."""
    return [x for x in _safe_list(value) if isinstance(x, dict)]


def _safe_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def normalize_record(raw: dict[str, Any], path: str, dir_system: str) -> tuple[dict[str, Any], str, str, list[str]]:
    """Coerce one parsed JSON object into the shapes downstream code assumes.

    Returns (normalized_raw, system, cycle_id, quality_notes). Never raises.
    """
    notes: list[str] = []
    out = dict(raw)

    schema_version = out.get("schema_version")
    # BLOCKER 1 (round 6): `X in a_set` does a hash lookup -- an unhashable
    # schema_version (a dict or a list, e.g. a hand-corrupted record) makes
    # the membership test itself raise TypeError: unhashable type, which
    # this function's own "Never raises" contract explicitly promises never
    # happens. schema_version is only ever meaningfully an int or a string;
    # anything else is unsupported (and unhashable-safe to check) without
    # ever reaching the `in` operator.
    if not isinstance(schema_version, (int, str)) or schema_version not in SCHEMA_VERSIONS_SUPPORTED:
        notes.append(
            f"schema_version is {schema_version!r} (this renderer supports "
            f"{sorted(SCHEMA_VERSIONS_SUPPORTED)}); rendered best-effort."
        )

    raw_system = _safe_str(out.get("system"))
    if raw_system is None:
        system = dir_system
        notes.append(f"'system' field missing; inferred from directory name ({dir_system!r}).")
    elif raw_system != dir_system:
        system = raw_system
        notes.append(
            f"'system' field ({raw_system!r}) differs from its directory ({dir_system!r}); "
            "using the field's own value."
        )
    else:
        system = raw_system
    out["system"] = system

    raw_cycle_id = _safe_str(out.get("cycle_id"))
    if raw_cycle_id is None:
        cycle_id = Path(path).stem
        notes.append(f"'cycle_id' field missing; inferred from filename ({cycle_id!r}).")
    else:
        cycle_id = raw_cycle_id
    out["cycle_id"] = cycle_id

    dispatches_raw = out.get("dispatches")
    dispatches = [d for d in _safe_list(dispatches_raw) if isinstance(d, dict)]
    if dispatches_raw is not None and len(dispatches) != len(_safe_list(dispatches_raw)):
        notes.append("some 'dispatches' entries were not objects; ignored.")
    elif dispatches_raw is not None and not isinstance(dispatches_raw, list):
        notes.append("'dispatches' was not a list; ignored.")
    out["dispatches"] = dispatches

    findings_raw = out.get("findings")
    findings = [f for f in _safe_list(findings_raw) if isinstance(f, dict)]
    if findings_raw is not None and len(findings) != len(_safe_list(findings_raw)):
        notes.append("some 'findings' entries were not objects; ignored.")
    elif findings_raw is not None and not isinstance(findings_raw, list):
        notes.append("'findings' was not a list; ignored.")
    out["findings"] = findings

    calibration_raw = out.get("calibration")
    if calibration_raw is not None and not isinstance(calibration_raw, dict):
        notes.append("'calibration' was not an object; ignored.")
        out["calibration"] = None
    elif calibration_raw is not None:
        # BLOCKER 2 (round 4): coerce calibration's own caught_by/missed_by
        # here too, at the root of every caller's input -- an int/float
        # crashes ct.plant_catch_by_slot() and a str fabricates invented
        # slots by iterating its characters (see cycle_telemetry.py's own
        # fix in that function for the full defect description). Fixing it
        # here means every downstream caller of normalize_record's output
        # gets already-clean data, not just plant_catch_by_slot.
        calibration = dict(calibration_raw)
        for field in ("caught_by", "missed_by"):
            field_raw = calibration.get(field)
            if field_raw is not None and not isinstance(field_raw, list):
                notes.append(f"'calibration.{field}' was not a list; ignored.")
            calibration[field] = field_raw if isinstance(field_raw, list) else []
        out["calibration"] = calibration
    else:
        out["calibration"] = calibration_raw

    cost_raw = out.get("cost")
    if cost_raw is not None and not isinstance(cost_raw, dict):
        notes.append("'cost' was not an object; ignored (treated as no cost data).")
        out["cost"] = None
    else:
        out["cost"] = cost_raw

    # undispatched_verdict_rows (round-25 structural-conflict fix, 2026-09-07)
    # is an OPTIONAL top-level OBJECT, like calibration/cost above -- NOT a
    # list, so it is deliberately excluded from V2_LIST_FIELDS's generic
    # list-coercion loop below (see that tuple's own docstring: it is a
    # hand-maintained copy of ct.OPTIONAL_TOP_KEYS restricted to the
    # LIST-shaped members). Same defensive shape as the cost block directly
    # above: not a dict -> ignored (None), never fabricated.
    undispatched_raw = out.get("undispatched_verdict_rows")
    if undispatched_raw is not None and not isinstance(undispatched_raw, dict):
        notes.append("'undispatched_verdict_rows' was not an object; ignored.")
        out["undispatched_verdict_rows"] = None
    else:
        out["undispatched_verdict_rows"] = undispatched_raw

    notes_raw = out.get("notes")
    out["notes"] = [n for n in _safe_list(notes_raw) if isinstance(n, str)]

    # v2 optional arrays -- absent entirely on a v1 record, in which case
    # this is a no-op (out[field] stays an empty list). Note this coercion
    # collapses "field key absent from the JSON" and "field present as an
    # explicit empty list" into the same []  -- neither this function nor
    # any downstream renderer currently distinguishes those two on a
    # per-array basis for findings/dispatches/runs/etc.; every one of them
    # renders "none recorded for this cycle" for both cases alike. Only
    # calibration's own legacy-vs-grid presence (see render_system_summary)
    # and a genuinely missing SCALAR field (fmt_ts/fmt_usd/etc., which never
    # coerce a missing value into a fabricated 0) draw that distinction
    # today.
    for field in V2_LIST_FIELDS:
        field_raw = out.get(field)
        items = [x for x in _safe_list(field_raw) if isinstance(x, dict)]
        if field_raw is not None and len(items) != len(_safe_list(field_raw)):
            notes.append(f"some '{field}' entries were not objects; ignored.")
        elif field_raw is not None and not isinstance(field_raw, list):
            notes.append(f"'{field}' was not a list; ignored.")
        out[field] = items

    return out, system, cycle_id, notes


def discover_cycle_files(cycles_dir: Path) -> tuple[list[Path], list[LoadIssue]]:
    """Round 12, BLOCKER 3 -- FIX + correction of a prior round's factually
    false docstring. Round 10's own docstring here argued that leaving a
    hypothetical `PermissionError` from `Path.glob()` uncaught was a
    deliberate choice, reasoning that main()'s outer safety net would then
    show the real permissions problem to the operator instead of it being
    silently swallowed. That premise is FALSE on this Python version:
    `Path.glob()` does not raise on an unreadable subdirectory at all -- it
    silently SKIPS it, with no exception, no log line, nothing. Verified:
    chmod'ing one system's subdirectory to 0o000 makes this function return
    ONLY the other, readable system's files, with zero indication anything
    was skipped. So the ACTUAL prior behavior was exactly the "silently
    swallow a real directory-permissions problem" outcome that docstring
    claimed to avoid -- worse, even, than this module's own already-correct
    pattern elsewhere (`ct._listdir_tolerant`, which at least logs a
    warning), and a direct violation of this module's headline design
    principle ("MISSING IS NOT ZERO"): the operator-facing provenance line
    ("N file(s) found, M loaded, K excluded") looked like a complete
    accounting while silently omitting an entire system's worth of data.

    The fix is the third option the prior docstring's false dichotomy
    (silently swallow vs. let it crash uncaught) never considered: make an
    unreadable subdirectory VISIBLE as a proper `LoadIssue`, the same
    mechanism every other malformed input already uses to stay honest on
    the report page. `Path.glob()` gives no signal to hook this onto, so
    each immediate subdirectory of `cycles_dir` is checked explicitly with
    `os.access(..., os.R_OK | os.X_OK)` (read to list entries, execute to
    traverse into it) before it is globbed; a subdirectory that fails this
    check is reported as a `LoadIssue` instead of silently contributing
    zero files with no trace."""
    if not cycles_dir.is_dir():
        return [], []
    files: list[Path] = []
    issues: list[LoadIssue] = []
    for entry in sorted(cycles_dir.iterdir(), key=lambda p: str(p)):
        if not entry.is_dir():
            continue
        if not os.access(entry, os.R_OK | os.X_OK):
            issues.append(
                LoadIssue(
                    str(entry),
                    "system directory is not readable (permission denied) -- "
                    "its cycle files, if any, could not be discovered",
                )
            )
            continue
        files.extend(entry.glob("*.json"))
    return sorted(files, key=lambda p: str(p)), issues


def load_cycle_records(cycles_dir: Path) -> tuple[list[CycleRecord], list[LoadIssue]]:
    records: list[CycleRecord] = []
    discovered_files, issues = discover_cycle_files(cycles_dir)
    for path in discovered_files:
        dir_system = path.parent.name
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # BLOCKER 3 (round 4): UnicodeDecodeError is a ValueError
            # subclass, NOT an OSError -- one truncated/invalid-UTF-8 file
            # (e.g. left behind by a process killed mid-write) used to
            # escape this try/except entirely, blank the WHOLE report via
            # main()'s outer except, and hide every OTHER system's data
            # too. Isolate it as a per-file LoadIssue like any other
            # malformed file, same as read_ledger_rows()'s stated
            # threat model for line-level malformation.
            issues.append(LoadIssue(str(path), f"could not read file: {exc}"))
            continue
        try:
            # Round 8, BLOCKER 1: a bare NaN/Infinity/-Infinity JSON
            # constant is rejected at this parse boundary, exactly like
            # cycle_telemetry.py's own read_ledger_rows/read_cycles/
            # read_cycle/_load_record_file/load_pricing all now do -- round
            # 6's fix for this exact hazard shape landed only in that
            # module, never in this file's separate `load_cycle_records`,
            # so a cycle record here with `"total_usd": Infinity` used to
            # parse cleanly and render as a confident "$inf" figure.
            # `reject_non_finite_json_constant` raises plain ValueError
            # (json.JSONDecodeError is itself a ValueError subclass), so
            # catching ValueError here covers both failure shapes.
            # Round 10, BLOCKER 4: `parse_constant` alone only catches the
            # bare NaN/Infinity/-Infinity literal TOKENS -- it does not
            # fire for an ordinary-looking numeric literal like `1e999`
            # that overflows to +/-inf during normal float parsing.
            # `reject_non_finite_json_float` closes that sibling gap at
            # the same parse boundary.
            parsed = json.loads(
                text,
                parse_constant=ct.reject_non_finite_json_constant,
                parse_float=ct.reject_non_finite_json_float,
            )
        except Exception as exc:
            # Round 12, BLOCKER 2: this used to catch only `ValueError`
            # (which covers a normal `json.JSONDecodeError`), narrower than
            # its structural twin `ct.read_cycles` (which correctly catches
            # `except Exception`, see that function's own docstring). A
            # deeply-nested JSON file (~20,000+ levels -- accidental or
            # malicious) makes `json.loads` raise `RecursionError`, which is
            # NOT a `ValueError` -- it escaped this guard entirely, blanked
            # the WHOLE multi-system report via main()'s outer safety net,
            # and silently lost every OTHER system's perfectly good record
            # too, with no per-file LoadIssue to explain why. Matching
            # `read_cycles`' already-correct `except Exception` here closes
            # the same "structural twin has the weaker guard" gap round 10
            # already fixed once for `list_systems` vs `iter_cycle_paths`.
            issues.append(LoadIssue(str(path), f"invalid JSON: {exc}"))
            continue
        if not isinstance(parsed, dict):
            issues.append(LoadIssue(str(path), "top-level JSON value is not an object"))
            continue
        # BLOCKER 1 (round 6): normalize_record()'s own docstring promises
        # "Never raises", and its schema_version check is now fixed at the
        # root cause above -- this try/except is the safety net BEHIND that
        # promise, not a substitute for it: if some future edit to
        # normalize_record ever reintroduces a crash on some other
        # malformed field, one bad file must still degrade to a per-file
        # LoadIssue, never blank the WHOLE multi-system report (which is
        # exactly what happened before this round: one bad file sitting
        # next to a perfectly good record from a different system wiped
        # both out, and the bad file wasn't even listed as excluded).
        # Coordinator review, item 4: capture whether `findings` was
        # genuinely present (as a list) on the SOURCE dict, straight off
        # `parsed` -- BEFORE `normalize_record()`'s own coercion collapses
        # "key absent" and "key present as []" into the identical `[]`.
        # This is read-only presence detection, mirrors normalize_record's
        # own `isinstance(..., list)` check on the very same field without
        # calling into or altering that function at all.
        has_findings = isinstance(parsed.get("findings"), list)
        try:
            normalized, system, cycle_id, notes = normalize_record(parsed, str(path), dir_system)
        except Exception as exc:
            issues.append(LoadIssue(str(path), f"could not normalize record: {exc}"))
            continue
        records.append(
            CycleRecord(
                path=str(path),
                system=system,
                cycle_id=cycle_id,
                raw=normalized,
                quality_notes=tuple(notes),
                has_findings=has_findings,
            )
        )
    return records, issues


def filter_by_system(records: list[CycleRecord], systems: Sequence[str] | None) -> list[CycleRecord]:
    if not systems:
        return records
    wanted = set(systems)
    return [r for r in records if r.system in wanted]


def filter_issues_by_system(issues: list[LoadIssue], systems: Sequence[str] | None) -> list[LoadIssue]:
    """A malformed file still lives under <cycles_dir>/<system>/... even though
    it never parsed far enough to report its own 'system' field, so a
    --system filter is honoured for it too via its directory name — without
    this, filtering to one system would still show another system's broken
    files in the "excluded" panel, which is confusing, not honest.

    Round 12, BLOCKER 3: `discover_cycle_files` now also emits a LoadIssue
    for an unreadable SYSTEM DIRECTORY itself (`.path` is the directory,
    e.g. `.../cycles/sysBlocked`), not a file beneath one
    (`.../cycles/sysA/bad.json`) -- so `Path(i.path).parent.name` alone
    would check the wrong path component for that shape (it would read
    "cycles", the cycles_dir's own name, never the system name), silently
    hiding a permission-denied system from exactly the `--system` filter an
    operator would use to investigate it. Checking both the path's own
    name and its parent's name covers a directory-shaped issue and a
    file-shaped issue with the same rule."""
    if not systems:
        return issues
    wanted = set(systems)
    return [i for i in issues if Path(i.path).name in wanted or Path(i.path).parent.name in wanted]


# --------------------------------------------------------------------------
# Pure metric computation — no LLM, no I/O, fully unit-testable in isolation.
# --------------------------------------------------------------------------


def all_findings(records: Sequence[CycleRecord]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in records:
        out.extend(_safe_list_of_dicts(r.raw.get("findings")))
    return out


# BLOCKER 3 fix: symptom_precision / cause_precision / duplicate_rate /
# ruling_conflict_rate / consolidation_ratio / plant_catch_by_slot /
# usd_per_confirmed_defect used to each be reimplemented here, hand-synced
# against cycle_telemetry's own definitions via "MUST match ...exactly"
# comments -- and drifted anyway, twice, undetected until this review. They
# are now computed via a single call to ct.aggregate_metrics() in analyze()
# below, which pools raw cycle-record dicts (CycleRecord.raw, already
# normalized by normalize_record()) exactly the way cycle_telemetry's own
# CLI and aggregate views do. See hooks/tests/test_render_cycle_log.py's
# metric-parity test class, which locks this shut against re-drifting.


@dataclass(frozen=True)
class CostRollup:
    """Aggregated cost across a set of records — always source-labelled.

    total_usd / total_tokens are None (never 0) when nothing priced any of
    the included cycles.

    BLOCKER 5 fix: resolve_cost() can legitimately emit source="spend_ledger"
    with total_usd=None (an unpriced model, or -- since the sibling fix in
    cycle_telemetry.py -- a matched row with no usable token data at all).
    Counting that cycle as "priced (ground truth)" while its (missing) dollar
    figure is silently excluded from the total is exactly the misleading
    blend this splits apart: n_ledger_priced / n_ledger_unpriced (and the
    identical split for "reported") always sum to the number of records
    passed in that carried that source, so a reader can tell the headline
    total is PARTIAL rather than assuming every "ledger-sourced" cycle
    contributed a real number to it.
    """

    total_usd: float | None
    total_tokens: float | None
    n_ledger_priced: int
    n_ledger_unpriced: int
    n_reported_priced: int
    n_reported_unpriced: int
    n_missing: int

    @property
    def n_ledger(self) -> int:
        return self.n_ledger_priced + self.n_ledger_unpriced

    @property
    def n_reported(self) -> int:
        return self.n_reported_priced + self.n_reported_unpriced

    @property
    def n_priced(self) -> int:
        return self.n_ledger_priced + self.n_reported_priced

    @property
    def fully_ground_truth(self) -> bool:
        return (
            self.n_priced > 0
            and self.n_reported == 0
            and self.n_missing == 0
            and self.n_ledger_unpriced == 0
        )


def rollup_cost(records: Sequence[CycleRecord]) -> CostRollup:
    total_usd = 0.0
    total_tokens = 0.0
    has_usd = False
    has_tokens = False
    n_ledger_priced = n_ledger_unpriced = 0
    n_reported_priced = n_reported_unpriced = 0
    n_missing = 0
    for r in records:
        cost = r.raw.get("cost")
        if not isinstance(cost, dict) or not cost:
            n_missing += 1
            continue
        source = cost.get("source")
        usd = cost.get("total_usd")
        tok = cost.get("total_tokens")
        # Round 8, BLOCKER 1: both of these used to be SEPARATE inline
        # `isinstance(x, (int, float)) and not isinstance(x, bool)` checks
        # -- neither excluded NaN/Infinity/-Infinity, so a cost record
        # carrying `total_usd: Infinity` counted as "priced" here and then
        # summed straight into `total_usd`, fabricating a confident "$inf"
        # rollup even though _is_number()/fmt_usd() elsewhere in this same
        # file were already finiteness-guarded. Routed through the ONE
        # shared helper instead of a third reimplementation.
        usd_is_number = _is_number(usd)
        # BLOCKER 5: bucket by source AND whether total_usd is an actual
        # number -- a source of "spend_ledger"/"reported" with a null
        # total_usd (resolve_cost's own honest unpriced-model/no-token-data
        # path) must never be counted alongside a genuinely priced cycle.
        if source == "spend_ledger":
            if usd_is_number:
                n_ledger_priced += 1
            else:
                n_ledger_unpriced += 1
        elif source == "reported":
            if usd_is_number:
                n_reported_priced += 1
            else:
                n_reported_unpriced += 1
        else:
            n_missing += 1
            continue
        if usd_is_number:
            total_usd += float(usd)
            has_usd = True
        if _is_number(tok):
            total_tokens += float(tok)
            has_tokens = True
    # Round 8, BLOCKER 1 (defense in depth): each individual usd/tok value
    # summed above was already finiteness-checked, but the ACCUMULATED
    # total across many records could still overflow to +/-inf even when
    # every individual contribution was finite (the same overflow shape
    # resolve_cost() now guards explicitly) -- never surface that as a
    # confident rollup figure either.
    if not ct.is_finite_number(total_usd):
        total_usd, has_usd = 0.0, False
    if not ct.is_finite_number(total_tokens):
        total_tokens, has_tokens = 0.0, False
    return CostRollup(
        total_usd=total_usd if has_usd else None,
        total_tokens=total_tokens if has_tokens else None,
        n_ledger_priced=n_ledger_priced,
        n_ledger_unpriced=n_ledger_unpriced,
        n_reported_priced=n_reported_priced,
        n_reported_unpriced=n_reported_unpriced,
        n_missing=n_missing,
    )


def dispatch_reported_tokens(records: Sequence[CycleRecord]) -> float | None:
    """Sum of dispatches[].tokens_total — the harness's OWN figure, known
    (per the incident that motivated this system) to be far below the real
    billed spend. Rendered separately from CostRollup and always labelled as
    such. None (not 0) when no dispatch in the set carried the field.

    Round 10, #8: the per-item check used to be a SEPARATE inline
    `isinstance(t, (int, float)) and not isinstance(t, bool)` -- the exact
    unguarded pattern round 8's BLOCKER 1 already replaced everywhere else
    in this file with the shared `ct.is_finite_number()`, so a
    `tokens_total: Infinity` on one dispatch counted as "a number" here and
    summed straight into `total`, and this function's own ACCUMULATED sum
    across many dispatches was never finiteness-checked either -- the 3rd
    un-consolidated accumulator in this file (rollup_cost and
    aggregate_metrics both already got this guard)."""
    total = 0.0
    saw_any = False
    for r in records:
        for d in _safe_list_of_dicts(r.raw.get("dispatches")):
            t = d.get("tokens_total")
            if ct.is_finite_number(t):
                total += float(t)
                saw_any = True
    if not ct.is_finite_number(total):
        return None
    return total if saw_any else None


def count_by(values: Sequence[Any], key: str | None = None) -> dict[str, int]:
    """Bucket-count arbitrary (possibly unexpected) string values, never
    assuming a closed enum — a value this renderer doesn't recognize is
    still counted and shown, under its own literal label, rather than
    dropped."""
    counts: dict[str, int] = {}
    for v in values:
        label = _safe_str(v) or "(not set)"
        counts[label] = counts.get(label, 0) + 1
    return counts


@dataclass(frozen=True)
class Analysis:
    n_cycles: int
    n_findings: int
    symptom_precision: float | None
    cause_precision: float | None
    duplicate_rate: float | None
    ruling_conflict_rate: float | None
    consolidation_ratio: float | None
    cost: CostRollup
    usd_per_confirmed_defect: float | None
    dispatch_count: int
    dispatch_tokens_reported: float | None
    verdict_counts: dict[str, int]
    decision_counts: dict[str, int]
    fix_status_counts: dict[str, int]
    plant_catch_by_slot: dict[str, dict[str, float | int | None]]
    plant_catch_by_trade: dict[str, dict[str, float | int | None]]
    false_alarm_by_trade: dict[str, dict[str, float | int | None]]
    # The aggregator outputs above are necessarily LOSSY -- a never-
    # fabricate contract means a plant row with zero readable catch/miss
    # signal never gets a bucket at all, so relying on the two dicts above
    # alone to decide "does a grid exist" silently drops that trade off the
    # page. These two fields are the RAW ground truth, read directly from
    # calibration_runs[] rows, not derived from either aggregator:
    # calibration_run_rows is a plain count (used to decide whether the grid
    # section should render at all, even when both aggregators above are
    # empty), and calibration_run_trades is every distinct, readably-named
    # trade seen in any row (used so a zero-signal trade still gets its own
    # table row, shown honestly with an em-dash, rather than vanishing).
    calibration_run_rows: int
    calibration_run_trades: tuple[str, ...]


def analyze(records: Sequence[CycleRecord]) -> Analysis:
    """BLOCKER 3 fix: every metric cycle_telemetry itself defines is computed
    by calling ct.aggregate_metrics() directly over this view's raw cycle
    records, rather than a second, hand-synced implementation -- see the
    module docstring and the block comment above where those reimplementations
    used to live. `records_raw` uses CycleRecord.raw, which normalize_record()
    has already coerced to the shapes both this file and cycle_telemetry's own
    functions expect (findings/dispatches/etc. as lists of dicts, cost/
    calibration as dicts-or-None), so aggregate_metrics() sees exactly the
    same defensively-normalized data this renderer would otherwise have
    walked by hand."""
    findings = all_findings(records)
    cost = rollup_cost(records)
    dispatch_count = sum(len(_safe_list(r.raw.get("dispatches"))) for r in records)
    records_raw = [r.raw for r in records]
    agg = ct.aggregate_metrics(records_raw)
    # Structural facts read directly off the raw calibration_runs[] rows --
    # a plain count and a plain trade-name set, neither one a "metric" with
    # a formula that could drift between two implementations (the same
    # reasoning dispatch_count above already applies), so computed here
    # directly rather than routed through cycle_telemetry.py. Both use
    # _safe_list_of_dicts (not the bare _safe_list dispatch_count uses
    # above) so a non-dict garbage entry in calibration_runs is excluded
    # from the row count exactly like it already is from the trade set and
    # from every aggregator's own row-reading -- see Analysis's own field
    # comments for why these two are necessary alongside the (necessarily
    # lossy) aggregator outputs.
    calibration_run_rows = sum(len(_safe_list_of_dicts(r.raw.get("calibration_runs"))) for r in records)
    calibration_run_trades = tuple(
        sorted(
            {
                row.get("trade")
                for r in records
                for row in _safe_list_of_dicts(r.raw.get("calibration_runs"))
                if isinstance(row.get("trade"), str) and row.get("trade").strip()
            }
        )
    )
    return Analysis(
        n_cycles=len(records),
        n_findings=len(findings),
        symptom_precision=agg["symptom_precision"],
        cause_precision=agg["cause_precision"],
        duplicate_rate=agg["duplicate_rate"],
        ruling_conflict_rate=agg["ruling_conflict_rate"],
        consolidation_ratio=agg["consolidation_ratio"],
        cost=cost,
        usd_per_confirmed_defect=agg["usd_per_confirmed_defect"],
        dispatch_count=dispatch_count,
        dispatch_tokens_reported=dispatch_reported_tokens(records),
        verdict_counts=count_by(f.get("verifier_verdict") for f in findings),
        decision_counts=count_by(f.get("consolidator_decision") for f in findings),
        fix_status_counts=count_by(f.get("fix_status") for f in findings),
        plant_catch_by_slot=agg["plant_catch_by_slot"],
        plant_catch_by_trade=agg["plant_catch_by_trade"],
        false_alarm_by_trade=agg["false_alarm_by_trade"],
        calibration_run_rows=calibration_run_rows,
        calibration_run_trades=calibration_run_trades,
    )


# --------------------------------------------------------------------------
# Formatting helpers — every one of these is where "missing reads as
# missing" actually gets enforced at render time.
# --------------------------------------------------------------------------


def _utf8_safe(text: str) -> str:
    """Round 12, BLOCKER 1: a lone Unicode surrogate (e.g. `"\\ud800"`) is
    valid JSON, survives `json.loads` untouched, and (via `esc`, below)
    passes straight through `html.escape` unchanged -- it is not a
    `<`/`>`/`&`/quote character `html.escape` knows how to handle, and
    Python's `str` type happily holds it in memory. The FIRST time it
    actually becomes a problem is at UTF-8 ENCODE time
    (`str.encode`/`write_text`/`print`), which raises `UnicodeEncodeError`
    -- a `ValueError` subclass, NOT an `OSError` -- the exact mirror image
    of round 4/6's decode-side "UnicodeDecodeError is a ValueError, not an
    OSError" fix, just never checked on this, the encode side, until now.
    Left unhandled, that raise happens INSIDE `out_path.write_text(...)`,
    which has already truncated the destination file to empty before the
    encode error is raised -- so one poisoned record does not just fail to
    render, it DESTROYS a previously-good, previously-written report file
    with no trace of what was lost. Since this renderer's whole contract
    is to survive and DISPLAY malformed data (never merely avoid crashing
    on it), every string that reaches either the HTML page (via `esc`,
    below) or an operator-facing stdout/stderr `print` is routed through
    this helper first: any lone surrogate is sanitized into readable
    backslash-escaped text (`\\ud800`) instead of an unencodable code
    point. `encode("utf-8", "backslashreplace")` only ever touches
    characters UTF-8 cannot represent (lone surrogates), so a normal
    string is round-tripped byte-for-byte unchanged."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-8", "backslashreplace").decode("utf-8")
    return text


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(_utf8_safe(str(value)), quote=True)


def _is_number(value: Any) -> bool:
    """Round 8, BLOCKER 1: this used to be a SEPARATE, unguarded
    implementation (`isinstance(value, (int, float)) and not
    isinstance(value, bool)`) -- it accepted a NaN/Infinity/-Infinity float
    as "a number", so a cycle record carrying `total_usd: Infinity`
    rendered as `fmt_usd` -> "$inf" labeled "priced from the spend ledger
    (ground truth)" on the operator page. Round 6's finiteness fix landed
    only in cycle_telemetry.py's own (then-private) `_is_number`, never
    here -- this now delegates to that SAME shared implementation instead
    of re-checking anything itself, so the two files' number-checking logic
    can never again drift apart on this exact axis."""
    return ct.is_finite_number(value)


def fmt_pct(value: Any) -> str:
    """BLOCKER 4: type-guarded like fmt_int_or_dash already was -- a
    malformed record (e.g. verdicts[0].confidence = "high", a realistic
    hand-edited/corrupted field the module's own docstring says this
    renderer must survive) must render a visible placeholder, never raise."""
    if value is None:
        return "n/a"
    if not _is_number(value):
        return "invalid data"
    return f"{value * 100:.0f}%"


def fmt_ratio(value: Any) -> str:
    if value is None:
        return "n/a"
    if not _is_number(value):
        return "invalid data"
    return f"{value:.2f}×"


def fmt_usd(value: Any) -> str:
    """BLOCKER 4: type-guarded like fmt_int_or_dash already was -- a
    malformed record (e.g. dispatches[0].cost_usd = "1.50", a realistic
    hand-edited/corrupted field) must render a visible placeholder, never
    raise ValueError out of an f-string format spec."""
    if value is None:
        return "no cost data"
    if not _is_number(value):
        return "invalid data"
    return f"${value:,.2f}"


def fmt_tokens(value: Any) -> str:
    if value is None:
        return "no token data"
    if not _is_number(value):
        return "invalid data"
    return f"{value:,.0f}"


def fmt_int_or_dash(value: Any) -> str:
    """Round 10, #8: this used to return the literal string 'inf'/'nan' for
    a non-finite float (e.g. tokens_total/tool_calls/duration_ms/round/
    blocker_count = Infinity) -- Python's own `f"{value:,.0f}"` format spec
    happily renders a non-finite float as that text, printing it directly
    on the operator page as if it were a real count. `is_finite_number`'s
    own docstring says this file's number-checking "can never again drift
    apart" from cycle_telemetry.py's -- this was the one formatter still
    doing its own separate, un-consolidated isinstance check instead of
    routing through the shared helper. A present-but-garbage value (a
    non-finite float) now reads "invalid data", matching this file's
    existing placeholder for the same class of malformed field elsewhere
    (fmt_pct/fmt_usd/fmt_tokens); a genuinely missing/wrong-type value
    still reads "—", unchanged."""
    if isinstance(value, bool):
        return "—"
    if isinstance(value, (int, float)):
        if not ct.is_finite_number(value):
            return "invalid data"
        return f"{value:,.0f}" if isinstance(value, float) else f"{value:,}"
    return "—"


def fmt_ts(value: Any) -> str:
    return esc(value) if isinstance(value, str) and value else "—"


def fmt_bool_or_null(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "not evaluated"


def cost_provenance_line(cost: CostRollup) -> str:
    parts: list[str] = []
    if cost.n_ledger_priced:
        parts.append(f"{cost.n_ledger_priced} priced from the spend ledger (ground truth)")
    if cost.n_ledger_unpriced:
        # BLOCKER 5: this cycle IS ledger-sourced but resolve_cost() withheld
        # a dollar figure (unpriced model, or a matched row with no usable
        # token data) -- it must never be silently folded into the "priced"
        # count above, and the reader must be told the total below excludes it.
        parts.append(
            f"{cost.n_ledger_unpriced} ledger-sourced but NOT priced (excluded from the total below)"
        )
    if cost.n_reported_priced:
        parts.append(
            f"{cost.n_reported_priced} priced from the harness's own 'reported' figure (less reliable)"
        )
    if cost.n_reported_unpriced:
        parts.append(
            f"{cost.n_reported_unpriced} 'reported'-sourced but with no dollar total (excluded from the total below)"
        )
    if cost.n_missing:
        parts.append(f"{cost.n_missing} with no cost data recorded at all")
    if not parts:
        return "no cycles in this view"
    return "; ".join(parts)


BADGE_CLASS: dict[str, str] = {
    "CONFIRMED": "badge good",
    "PARTIALLY_CONFIRMED": "badge warn",
    "REFUTED": "badge bad",
    "ALREADY_TRACKED_ELSEWHERE": "badge neutral",
    "UNVERIFIABLE": "badge unknown",
    "ACCEPT": "badge good",
    "REJECT": "badge bad",
    "CONTESTED": "badge warn",
    "GC_DEFAULT": "badge neutral",
    "HINT_WORTHY": "badge info",
    "CONCUR": "badge good",
    "DISSENT": "badge warn",
}


def badge(value: Any, known: set[str] | None = None) -> str:
    label = _safe_str(value)
    if label is None:
        return '<span class="badge unknown">not set</span>'
    cls = BADGE_CLASS.get(label, "badge plain")
    if known is not None and label not in known:
        return f'<span class="{cls}" title="unrecognized value">{esc(label)} ?</span>'
    return f'<span class="{cls}">{esc(label)}</span>'


def fix_status_badge(value: Any) -> str:
    label = _safe_str(value)
    if label is None:
        return '<span class="badge unknown">not set</span>'
    low = label.lower()
    if "fixed" in low or "resolved" in low or "done" in low:
        cls = "badge good"
    elif "wontfix" in low or "reject" in low or "declined" in low:
        cls = "badge bad"
    elif "block" in low:
        cls = "badge warn"
    else:
        cls = "badge plain"
    return f'<span class="{cls}">{esc(label)}</span>'


# --------------------------------------------------------------------------
# Sparklines — tiny inline SVGs, no canvas/JS, degrade to a text note when
# there isn't enough data to draw a line.
# --------------------------------------------------------------------------


def render_sparkline(values: Sequence[float | None], width: int = 120, height: int = 28) -> str:
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(points) < 2:
        return '<span class="spark-empty">not enough cycles yet</span>'
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    x_span = (max(xs) - min(xs)) or 1
    pad = 3
    coords = []
    for x, y in points:
        px = pad + (x - min(xs)) / x_span * (width - 2 * pad)
        py = height - pad - (y - lo) / span * (height - 2 * pad)
        coords.append(f"{px:.1f},{py:.1f}")
    dots = "".join(
        f'<circle cx="{c.split(",")[0]}" cy="{c.split(",")[1]}" r="2" class="spark-dot"/>' for c in coords
    )
    polyline = " ".join(coords)
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="trend sparkline">'
        f'<polyline points="{polyline}" class="spark-line" fill="none"/>{dots}</svg>'
    )


def trend_arrow(prev: float | None, curr: float | None, higher_is_better: bool | None) -> str:
    """Compare the two most recent non-None values. higher_is_better=None
    means the direction is shown but never colour-judged (ambiguous
    metric)."""
    if prev is None or curr is None:
        return '<span class="trend flat" title="not enough cycles yet">—</span>'
    if abs(curr - prev) < 1e-9:
        return '<span class="trend flat">→ steady</span>'
    up = curr > prev
    arrow = "↑" if up else "↓"
    if higher_is_better is None:
        cls = "flat"
    else:
        good = up if higher_is_better else (not up)
        cls = "good" if good else "bad"
    return f'<span class="trend {cls}">{arrow} {"up" if up else "down"} vs prior cycle</span>'


def last_two_non_none(values: Sequence[float | None]) -> tuple[float | None, float | None]:
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return (None, None)
    return present[-2], present[-1]


def render_bar_sparkline(
    values: Sequence[int | float | None], width: int = 90, height: int = 22
) -> str:
    """A per-system findings-per-cycle bar chart for the executive summary
    row -- deliberately a DIFFERENT shape from render_sparkline's line+dot
    (that one is used inside a system's own trend cards, this one is the
    compact glance-value for the top-of-page strip). A cycle with no
    recorded value (None) renders as an explicit gap (zero-height, but
    title-flagged "not recorded"), never silently coerced to a real 0 bar --
    the same MISSING IS NOT ZERO rule this whole module lives by, applied to
    a chart instead of a table cell."""
    if not values:
        return '<span class="spark-empty">no cycles yet</span>'
    present = [v for v in values if v is not None]
    hi = max(present) if present else 1
    hi = hi or 1
    n = len(values)
    pad = 2
    gap = 1.5
    bar_w = max((width - 2 * pad) / n - gap, 1.0)
    bars = []
    for i, v in enumerate(values):
        x = pad + i * (bar_w + gap)
        if v is None:
            bars.append(
                f'<rect x="{x:.1f}" y="{height - pad - 1:.1f}" width="{bar_w:.1f}" height="1" '
                f'class="spark-bar-missing"><title>cycle {i + 1}: not recorded</title></rect>'
            )
            continue
        bar_h = max((float(v) / hi) * (height - 2 * pad), 1.0)
        y = height - pad - bar_h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'class="spark-bar"><title>cycle {i + 1}: {v:g}</title></rect>'
        )
    return (
        f'<svg class="spark-bars" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="findings per cycle">{"".join(bars)}</svg>'
    )


def render_trend_chart_svg(
    series: Sequence[tuple[str, Sequence[float | None], str]],
    width: int = 420,
    height: int = 120,
) -> str:
    """A slightly larger multi-series line chart for inside a system's
    details -- `series` is [(label, values, css_class), ...], all sharing
    the same x-axis (cycle index, oldest first). Each point carries a
    `<title>` for its exact value on hover (minimal axis labelling per the
    design brief: just min/max on the y-axis, first/last cycle index on the
    x-axis -- this is a glance chart, not a full analytics widget).
    Degrades to a text note when no series has at least 2 real points."""
    n = max((len(vals) for _, vals, _ in series), default=0)
    any_plottable = any(len([v for v in vals if v is not None]) >= 2 for _, vals, _ in series)
    if n < 2 or not any_plottable:
        return '<p class="reasoning">Not enough cycles yet to draw a trend chart.</p>'

    all_present = [v for _, vals, _ in series for v in vals if v is not None]
    if not all_present:
        return '<p class="reasoning">Not enough cycles yet to draw a trend chart.</p>'
    lo, hi = min(0.0, min(all_present)), max(all_present)
    span = (hi - lo) or 1.0
    pad_l, pad_r, pad_t, pad_b = 28, 8, 8, 18
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x_span = (n - 1) or 1

    def px(i: int) -> float:
        return pad_l + (i / x_span) * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - ((v - lo) / span) * plot_h

    parts: list[str] = []
    # Minimal y-axis labels: top (max) and bottom (0 or min) only.
    parts.append(
        f'<text x="2" y="{pad_t + 4:.0f}" class="chart-axis-label">{hi:g}</text>'
        f'<text x="2" y="{pad_t + plot_h:.0f}" class="chart-axis-label">{lo:g}</text>'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h:.0f}" class="chart-axis"/>'
        f'<line x1="{pad_l}" y1="{pad_t + plot_h:.0f}" x2="{width - pad_r}" y2="{pad_t + plot_h:.0f}" class="chart-axis"/>'
        f'<text x="{pad_l}" y="{height - 2}" class="chart-axis-label">cycle 1</text>'
        f'<text x="{width - pad_r - 40}" y="{height - 2}" class="chart-axis-label">cycle {n}</text>'
    )
    for label, vals, css_class in series:
        points = [(i, v) for i, v in enumerate(vals) if v is not None]
        if len(points) < 2:
            continue
        coords = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in points)
        # The per-dot hover title deliberately omits the series label --
        # the legend beneath the chart already names each series once, so
        # repeating it here 1x per data point (n * len(series) times) is
        # pure redundant bytes with no reader-facing information lost by
        # dropping it.
        dots = "".join(
            f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="2.4" class="chart-dot {css_class}">'
            f"<title>cycle {i + 1}: {v:g}</title></circle>"
            for i, v in points
        )
        parts.append(f'<polyline points="{coords}" class="chart-line {css_class}" fill="none"/>{dots}')
    legend = "".join(
        f'<span class="chart-legend-item"><span class="chart-legend-dot {css_class}"></span>{esc(label)}</span>'
        for label, vals, css_class in series
        if len([v for v in vals if v is not None]) >= 1
    )
    svg = (
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="trend chart">{"".join(parts)}</svg>'
    )
    return f'<div class="chart-wrap">{svg}<div class="chart-legend">{legend}</div></div>'


def cost_headline(cost: CostRollup) -> str:
    """The one, single rendering of "how much did this cost" that this page
    ever shows in a headline/summary position -- EXACTLY "UNKNOWN (source:
    unavailable)" when nothing priced any of the included cycles, never a
    bare number, never a blank cell, and never $0 (which a skimming reader
    could mistake for "this was free"). When something WAS priced, the
    figure is shown with its provenance in the same breath, never bare."""
    if cost.total_usd is None:
        return 'UNKNOWN <span class="reasoning">(source: unavailable)</span>'
    if cost.fully_ground_truth:
        return f"{fmt_usd(cost.total_usd)} <span class=\"reasoning\">(source: spend ledger, ground truth)</span>"
    return f"{fmt_usd(cost.total_usd)} <span class=\"reasoning\">(source: {esc(cost_provenance_line(cost))})</span>"


# --------------------------------------------------------------------------
# HTML rendering
# --------------------------------------------------------------------------


def wrap_sub_expander(
    label: str,
    count: int | None,
    gist: str,
    body_html: str,
    count_text: str | None = None,
    title: str | None = None,
) -> str:
    """One nested, collapsed `<details>` for a per-cycle list (findings,
    dispatches, runs, ...) whose `<summary>` carries the count and a
    one-line gist -- this is the mechanism that keeps a cycle card short
    when collapsed. `count=None` with no `count_text` override renders
    "not recorded" (a v1 record has no `runs`/`reviews`/etc. array),
    rendered distinctly from a recorded-but-empty `count=0` -- MISSING IS
    NOT ZERO applies to a list's own presence, not only to its individual
    fields. A caller whose section genuinely has no single "how many"
    concept (e.g. calibration, which mixes a legacy single-plant block with
    a per-trade grid) passes an explicit `count_text` instead of forcing
    either a fabricated number or the misleading "not recorded" label onto
    data that DOES exist.

    A genuinely empty list (`count == 0`) has no body worth expanding into
    -- rendered as a single compact line instead of a full `<details>`, so
    a cycle with nothing to report in ten of these eleven sections (a
    common shape in this corpus) doesn't pay for ten empty expanders'
    worth of markup. `title` is an optional longer explanation shown on
    hover rather than always inline, keeping a verbose label's full context
    available without repeating it in the visible (and rendered-byte) text
    on every single cycle."""
    if count == 0 and count_text is None:
        title_attr = f' title="{esc(title)}"' if title else ""
        return f'<p class="reasoning"{title_attr}>{esc(label)}: none recorded for this cycle.</p>'
    if count_text is None:
        count_text = "not recorded" if count is None else f"{count}"
    # BLOCKER (injection, coordinator review): `gist` is built by the
    # `_*_gist` helpers directly from record-derived strings (agent_type,
    # cause text, ids) -- it is caller content, not markup, and must be
    # escaped HERE, at this one boundary every gist flows through, rather
    # than trusting (or worse, re-trusting) each caller to have escaped it
    # already. `_generic_gist`'s own per-id `esc()` call is removed as part
    # of this same fix -- escaping twice at two different layers is exactly
    # how a FUTURE caller reintroduces this same defect by copying the
    # (now redundant-looking) per-caller pattern instead of relying on the
    # one real boundary.
    gist_html = f'<span class="gist">{esc(gist)}</span>' if gist else ""
    title_attr = f' title="{esc(title)}"' if title else ""
    return (
        f'<details class="sub-expander">'
        f"<summary{title_attr}>{esc(label)} ({esc(count_text)}){gist_html}</summary>"
        f'<div class="sub-expander-body">{body_html}</div>'
        f"</details>"
    )


def render_raw_record_pointer(record: CycleRecord) -> str:
    """Coordinator review (item 2): the predecessor renderer never showed
    raw JSON inline at all -- every field of a cycle record already lives
    in one of this cycle's own structured sub-expanders above (findings,
    dispatches, runs, ...), verified against the pre-redesign renderer
    directly (zero numeric tokens are lost by NOT inlining the raw blob).
    An earlier revision of this file inlined a truncated copy of the raw
    JSON anyway, justified by a now-corrected false claim that the
    predecessor did this "at full size" -- it never did, so there was
    nothing to demote. The honest, minimal replacement: one line naming
    the exact on-disk path an operator can open directly for the real,
    complete, never-deleted file -- no duplicated content, no truncation
    math to get wrong."""
    return f'<p class="reasoning">Full record: <code>{esc(record.path)}</code></p>'


def render_legend() -> str:
    return """
<details class="legend">
<summary>What am I looking at? (definitions)</summary>
<div class="legend-body">
<p><b>A cycle</b> is one run of a self-correcting loop: agents dispatch, raise findings, a
consolidator decides what to act on, a verifier checks the claims, fixes land or don't.</p>
<ul>
<li><b>symptom precision</b> — of findings the verifier could actually judge, the share where
something real was actually wrong (not REFUTED).</li>
<li><b>cause precision</b> — of findings where the verifier judged the raiser's stated ROOT CAUSE
(not just the symptom), the share where that cause claim held up. This is usually far lower than
symptom precision — that gap is the entire reason this page exists.</li>
<li><b>duplicate rate</b> — share of findings that turned out to already be tracked elsewhere.</li>
<li><b>ruling conflict rate</b> — share of findings that fight a standing decision/ruling.</li>
<li><b>consolidation ratio</b> — average number of raw raiser reports collapsed into one finding
(higher = more agents independently spotted the same thing before it became one finding).</li>
<li><b>$ / confirmed defect</b> — total priced cost divided by findings the verifier actually
confirmed. Shown as "no cost data" (never $0) when nothing in view was priced.</li>
<li><b>plant catch rate</b> — for cycles with a deliberately seeded ("planted") defect, how often
each individual slot (typically a dispatch's batch position) that was exposed to it actually
caught it, broken out per slot identifier. A cycle with no plant seeded at all contributes
nothing here — it is never shown as a fabricated 0%.</li>
</ul>
<p><b>Verdicts:</b>
<span class="badge good">CONFIRMED</span> real and matches the claim ·
<span class="badge warn">PARTIALLY_CONFIRMED</span> real but not exactly as claimed ·
<span class="badge bad">REFUTED</span> not real ·
<span class="badge neutral">ALREADY_TRACKED_ELSEWHERE</span> a duplicate of a known issue ·
<span class="badge unknown">UNVERIFIABLE</span> the verifier couldn't tell.</p>
<p><b>Consolidator decisions:</b>
<span class="badge good">ACCEPT</span> ·
<span class="badge bad">REJECT</span> ·
<span class="badge warn">CONTESTED</span> raisers disagreed ·
<span class="badge neutral">GC_DEFAULT</span> fell through to a default ruling ·
<span class="badge info">HINT_WORTHY</span> not actioned but kept as a hint for next cycle.</p>
<p><b>Cost source:</b> "spend ledger" is the real billed figure (ground truth); "reported" is the
harness's own per-agent figure, which has been measured to undercount real spend by roughly 26×
in at least one incident — never treat it as equivalent to the ledger.</p>
</div>
</details>
"""


# --------------------------------------------------------------------------
# The page stylesheet -- ONE module-level constant shared by BOTH render
# paths: render_head() interpolates it verbatim into the standalone page's
# <style> block (byte-identical to the pre-refactor inline form), and
# scoped_css() rewrites it for fragment embedding (every selector confined
# under a host-supplied scope, @media print dropped). Extracted 2026-09-07
# for the fragment-embedding API (see render_fragment below), mirroring
# render_agent_telemetry.py's proven CSS-constant + scoped_css() pair.
#
# THEME-BRIDGE NOTE (for any host that later re-points these custom
# properties at its own tokens): the fragment keeps its own palette -- no
# theme bridge is built here -- but if a host ever layers one on top (the
# way gen_operator_hub.py's _TELEMETRY_THEME_OVERRIDE_CSS does for the
# sibling agent-telemetry panel), it must alias through DIFFERENTLY-NAMED
# intermediate properties on a WRAPPER element: a same-name self-reference
# like `--bg:var(--bg)` on one selector resolves to nothing per
# css-variables-1 (that exact bug shipped on the sibling panel and was
# caught in review -- see _TELEMETRY_THEME_OVERRIDE_CSS's own comment in
# that generator).
# --------------------------------------------------------------------------

# The container class render_fragment() wraps itself in, and the default
# scope scoped_css() confines the stylesheet under -- the two must name the
# same class, and render_script(fragment=True) roots its queries at it too.
FRAGMENT_CONTAINER_CLASS = "cycle-log"

CSS = """:root{
  --bg:#f5f6f8; --panel:#ffffff; --border:#e1e4e9; --text:#1b1f27; --dim:#5b6472; --faint:#8992a1;
  --accent:#3457d5; --accent-soft:#eaeefd;
  --good:#1a7f4e; --good-soft:#e6f6ee;
  --warn:#b4740e; --warn-soft:#fdf1de;
  --bad:#b93a3a; --bad-soft:#fbeaea;
  --info:#2b7fb0; --info-soft:#e4f2fa;
  --neutral:#5b6472; --neutral-soft:#eef0f3;
  --unknown:#8992a1; --unknown-soft:#f1f2f4;
  --shadow:0 1px 2px rgba(20,24,33,.04),0 6px 20px rgba(20,24,33,.05);
}
@media (prefers-color-scheme: dark) {
  :root{
    --bg:#14161c; --panel:#1b1e26; --border:#2d313d; --text:#e7e9ee; --dim:#a2a9b6; --faint:#6c7381;
    --accent:#7d9bff; --accent-soft:#232a45;
    --good:#4bce95; --good-soft:#16281f;
    --warn:#e0a83f; --warn-soft:#2c2313;
    --bad:#e2726f; --bad-soft:#2c1717;
    --info:#6fc1e8; --info-soft:#122a35;
    --neutral:#a2a9b6; --neutral-soft:#232630;
    --unknown:#6c7381; --unknown-soft:#20222b;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.35);
  }
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:28px 20px 100px}
.hub-link-row{margin:0 0 10px}
.hub-link{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;font-weight:650;
  color:var(--accent);text-decoration:none;background:var(--accent-soft);
  border-radius:999px;padding:6px 14px}
.hub-link:hover{text-decoration:underline}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:0}
h3{font-size:15.5px;margin:0}
.sub{color:var(--dim);font-size:14px;max-width:900px}
.provenance{color:var(--faint);font-size:12.5px;margin-top:8px}
.stat-row{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:10px 16px;min-width:110px;box-shadow:var(--shadow)}
.stat .n{font-size:20px;font-weight:700}
.stat .l{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.04em}
.controls{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 0 14px;
  border-bottom:1px solid var(--border);margin-bottom:22px;display:flex;flex-direction:column;gap:10px}
.controls input{width:100%;padding:9px 13px;border-radius:10px;border:1px solid var(--border);
  background:var(--panel);color:var(--text);font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--border);background:var(--panel);color:var(--dim);padding:5px 11px;
  border-radius:999px;font-size:12.5px;cursor:pointer;user-select:none}
.chip.active{background:var(--accent);border-color:var(--accent);color:#fff}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;box-shadow:var(--shadow);margin-bottom:18px}
.notice{background:var(--warn-soft);color:var(--warn);border:1px solid var(--border);
  border-radius:12px;padding:12px 16px;margin-bottom:18px;font-size:13.5px}
.empty-state{background:var(--panel);border:1px dashed var(--border);border-radius:14px;
  padding:34px 24px;text-align:center;color:var(--dim)}
.empty-state code{background:var(--accent-soft);color:var(--accent);padding:2px 6px;border-radius:6px}
.system-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.count{font-size:12.5px;color:var(--faint)}
.trend-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;margin:12px 0 18px}
.trend-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:10px 12px;box-shadow:var(--shadow)}
.trend-card .label{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.03em}
.trend-card .value{font-size:19px;font-weight:700;margin:2px 0}
.trend{font-size:12px}
.trend.good{color:var(--good)}
.trend.bad{color:var(--bad)}
.trend.flat{color:var(--faint)}
.spark{display:block;margin-top:4px}
.spark-line{stroke:var(--accent);stroke-width:1.6}
.spark-dot{fill:var(--accent)}
.spark-empty{font-size:11px;color:var(--faint)}
.spark-bars{display:block}
.spark-bar{fill:var(--accent)}
.spark-bar-missing{fill:var(--faint);opacity:.5}
.chart-wrap{margin-top:8px}
.chart{display:block;max-width:100%}
.chart-axis{stroke:var(--border);stroke-width:1}
.chart-axis-label{font-size:9px;fill:var(--faint)}
.chart-line.findings{stroke:var(--accent);stroke-width:1.8}
.chart-line.causes{stroke:var(--warn);stroke-width:1.8}
.chart-dot.findings{fill:var(--accent)}
.chart-dot.causes{fill:var(--warn)}
.chart-legend{display:flex;gap:14px;margin-top:4px;font-size:11.5px;color:var(--dim)}
.chart-legend-item{display:inline-flex;align-items:center;gap:5px}
.chart-legend-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.chart-legend-dot.findings{background:var(--accent)}
.chart-legend-dot.causes{background:var(--warn)}
/* Executive summary strip -- the 10-second read at the top of the page. */
.exec-summary{margin-bottom:22px}
.exec-table{width:100%;border-collapse:collapse}
.exec-table th,.exec-table td{padding:9px 12px;border-bottom:1px solid var(--border);
  white-space:nowrap;vertical-align:middle}
.exec-table th{background:var(--neutral-soft);color:var(--dim);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:.03em;text-align:left}
.exec-table tr:last-child td{border-bottom:none}
.exec-system{font-weight:650}
.exec-cost{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.exec-jump{font-size:11.5px;color:var(--accent);text-decoration:none;margin-left:8px}
/* Nested expanders -- collapsed by default is the whole point of this
   redesign. B-ASSERT-9 (operator amendment, 2026-09-05): ALL expanders
   render closed by default, page-wide -- zero elements carry the "open"
   attribute anywhere on this page, including the newest-activity system
   and cycle that used to default open. */
details.sys-expander{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:10px 14px;margin-bottom:14px;box-shadow:var(--shadow)}
details.sys-expander>summary{cursor:pointer;list-style:none;display:flex;align-items:baseline;
  gap:10px;flex-wrap:wrap}
details.sys-expander>summary::-webkit-details-marker{display:none}
details.sys-expander>summary::before{content:"▸";color:var(--faint);margin-right:2px}
details.sys-expander[open]>summary::before{content:"▾"}
details.sys-body{margin-top:12px}
details.cycle-expander{border:1px solid var(--border);border-radius:12px;padding:10px 14px 8px;
  margin-bottom:10px;background:var(--bg)}
details.cycle-expander>summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;
  gap:10px;flex-wrap:wrap;align-items:baseline}
details.cycle-expander>summary::-webkit-details-marker{display:none}
details.cycle-expander .cycle-summary-left{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
details.cycle-expander .cycle-summary-left::before{content:"▸";color:var(--faint)}
details.cycle-expander[open] .cycle-summary-left::before{content:"▾"}
details.sub-expander{border:1px dashed var(--border);border-radius:8px;padding:6px 10px;
  margin:8px 0;background:var(--panel)}
details.sub-expander>summary{cursor:pointer;font-size:13px;color:var(--dim);font-weight:600}
details.sub-expander>summary .gist{font-weight:400;color:var(--faint);margin-left:6px}
.sub-expander-body{margin-top:6px}
.not-recorded{color:var(--faint);font-style:italic}
.section-note{color:var(--dim);font-size:12.5px;margin:0 0 8px}
.cycle-head{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.cycle-id{font-weight:650;font-size:15px}
.cycle-times{color:var(--faint);font-size:12.5px}
.quality-notes{margin-top:6px}
.quality-notes .badge{margin:2px 4px 2px 0}
.cycle-notes{background:var(--accent-soft);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  padding:8px 12px;margin:10px 0;font-size:13.5px}
.cycle-notes ul{margin:4px 0 0;padding-left:18px}
.mini-stats{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0;font-size:13px;color:var(--dim)}
.mini-stats b{color:var(--text)}
.table-scroll{overflow-x:auto;max-width:100%;border-radius:10px;border:1px solid var(--border)}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:640px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
td.wrap-cell{white-space:normal;min-width:200px;max-width:340px}
th{background:var(--neutral-soft);color:var(--dim);font-weight:600;font-size:11.5px;
  text-transform:uppercase;letter-spacing:.03em;position:sticky;top:0}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;
  white-space:nowrap}
.badge.good{background:var(--good-soft);color:var(--good)}
.badge.warn{background:var(--warn-soft);color:var(--warn)}
.badge.bad{background:var(--bad-soft);color:var(--bad)}
.badge.neutral{background:var(--neutral-soft);color:var(--neutral)}
.badge.info{background:var(--info-soft);color:var(--info)}
.badge.unknown{background:var(--unknown-soft);color:var(--unknown);font-style:italic}
.badge.plain{background:var(--panel);color:var(--dim);border:1px solid var(--border)}
.reasoning{font-size:12.5px;color:var(--dim)}
.reasoning b{color:var(--text)}
.footer{color:var(--faint);font-size:12px;margin-top:30px;border-top:1px solid var(--border);padding-top:14px}
.legend{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 16px;
  margin-bottom:22px;font-size:13px}
.legend summary{cursor:pointer;font-weight:600}
.legend-body{margin-top:8px;color:var(--dim)}
.legend-body ul{padding-left:18px}
.legend-body li{margin-bottom:5px}
.hidden{display:none!important}
details.issues summary{cursor:pointer;color:var(--bad);font-weight:600}
.issue-row{font-size:12.5px;color:var(--dim);padding:3px 0;border-bottom:1px dashed var(--border)}
/* Export PDF (B-ASSERT-11, Q2 interim default = scoped print). The button
   and "Print all cycles" toggle are chrome -- hidden in print, same as the
   filter/chip controls. */
.print-controls{display:flex;align-items:center;gap:12px;margin:0 0 16px;flex-wrap:wrap}
.print-btn{border:1px solid var(--accent);background:var(--accent);color:#fff;font-size:13px;
  font-weight:650;padding:8px 16px;border-radius:999px;cursor:pointer}
.print-btn:hover{opacity:.9}
.print-all-toggle{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--dim);
  cursor:pointer;user-select:none}
@media print {
  /* Chrome hidden on paper: search/filter controls and the export button
     itself -- B-ASSERT-11's "hides nav/tab chrome" + this wave's own
     "hides the search/filter chrome and the button itself." */
  .controls, .print-controls, .hub-link-row {display:none!important}
  /* Scoped print (Q2 interim default): print renders whatever <details>
     the operator has left OPEN plus the always-visible summary content
     (exec summary, legend, provenance) -- a closed <details> naturally
     prints collapsed, which is the whole point of leaning on the
     browser's own default engine behavior here rather than forcing
     anything open. The "Print all cycles" toggle (JS below) is the one
     sanctioned way to force everything open before printing. */
  body{background:#fff;color:#000}
  a{color:#000!important;text-decoration:none}
  /* BLOCKER 2 fix (cold review round 1): break-inside:avoid is an
     unsatisfiable constraint on the three *-expander selectors -- the
     real sys-expander alone serializes to 706,953 bytes (97% of the
     document), and an "avoid" that can never be satisfied is
     engine-undefined under print (ignored at best, blank runs at worst).
     box-shadow:none stays for all of them (a pure cosmetic reset, never a
     layout constraint); break-inside:avoid is now scoped to the genuinely
     small, atomic boxes only (a stat tile, a trend card, a generic panel,
     one table row) that CAN actually satisfy the constraint on one page. */
  .panel, details.sys-expander, details.cycle-expander, details.sub-expander,
  .stat, .trend-card{box-shadow:none!important}
  .panel, .stat, .trend-card, tr{break-inside:avoid;page-break-inside:avoid}
  .table-scroll{overflow:visible!important}
  /* BLOCKER 1 fix (cold review round 1): the previous suppression rule
     (`details.sys-expander:first-of-type`) matched ZERO elements --
     :first-of-type is per-TAG-NAME among siblings, and render_legend()'s
     `<details class="legend">` is the real details:first-of-type inside
     .wrap (soupsieve-verified 0 matches on the real page), so the
     unsuppressed break-before:page fired on the FIRST system too, opening
     every export with a blank/near-empty first page. The sibling
     combinator scopes the break correctly regardless of what other
     <details> (legend, issues panel, ...) happen to precede the first
     sys-expander: a sys-expander only forces a page break when it has a
     PRECEDING sys-expander sibling, which is never true for the first one. */
  details.sys-expander ~ details.sys-expander{break-before:page;page-break-before:always}
  .footer{break-before:auto;page-break-before:auto}
}"""


def render_head(title: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">
"""


def scoped_css(scope: str = ".cycle-log") -> str:
    """This module's CSS with every rule confined to `scope`.

    Fragment-embedding support (2026-09-07): an embedded fragment must not
    restyle its host. This stylesheet's selectors include deliberately
    generic ones (`*`, `html,body`, `body`, bare `table`/`th`/`td`/`h1`..
    `h3`), which are correct for the standalone page and would wreck a host
    page if injected raw. The default scope matches the container class
    `render_fragment()` wraps itself in.

    PROVENANCE: the scoping walk below is a copy of
    render_agent_telemetry.py's proven `scoped_css()` (already embedded in
    the same Operator Hub tab this API targets) rather than an import of it
    -- importing that module executes its own import-time sys.path
    insertions, a side effect this module must not inherit. Two deliberate
    deviations from that original: (1) `@media print` is ALWAYS dropped
    (no `drop_print` parameter) -- the host hub has its own print machinery
    plus a falsifiability guard that a second print block would silently
    defeat; (2) CSS comments are stripped before the walk -- THIS module's
    stylesheet carries block comments containing commas, which would
    corrupt the comma-split in `scope_selector` (the sibling module's CSS
    has no comments in selector position, so its copy never needed this).

    `:root`/`html`/`body` selectors are rewritten to the scope element
    itself so the custom-property palette still cascades over the fragment
    (a prefixed `.cycle-log :root` would match NOTHING and every var()
    would resolve to nothing). See the THEME-BRIDGE NOTE above the CSS
    constant before layering any host-token bridge on top of this.
    """

    def scope_selector(sel: str) -> str:
        parts = []
        for p in sel.split(","):
            p = " ".join(p.split())
            if not p:
                continue
            # `:root`/`html`/`body` carry the custom-property definitions.
            # Prefixing them yields `.cycle-log :root`, which matches
            # NOTHING -- every var() would resolve to nothing and the panel
            # would render unstyled. Retarget them onto the scope element so
            # the variables still cascade to the fragment, and only there.
            if p in (":root", "html", "body"):
                parts.append(scope)
            elif p.startswith(scope):
                parts.append(p)
            else:
                parts.append(f"{scope} {p}")
        return ", ".join(parts)

    def walk(css: str) -> str:
        # Brace-aware, because a naive `}`-split cannot represent a nested
        # at-rule: `@media {...}` would swallow its first inner rule into
        # the prelude and leave the braces unbalanced.
        out: list[str] = []
        i, n = 0, len(css)
        while i < n:
            brace = css.find("{", i)
            if brace == -1:
                break
            prelude = " ".join(css[i:brace].split())
            depth, j = 1, brace + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            inner = css[brace + 1 : j - 1]
            if prelude.startswith("@"):
                # `@media print` is a PAGE-LEVEL concern that belongs to the
                # host document, not to an embedded fragment -- always
                # dropped here (see the docstring). The standalone page
                # keeps its block untouched via render_head's verbatim
                # interpolation of the CSS constant.
                if prelude.rstrip("{ ").strip() == "@media print":
                    i = j
                    continue
                # Keep the at-rule prelude verbatim; scope the rules INSIDE
                # it by recursing. @keyframes is the exception -- its inner
                # blocks are percentage stops, not selectors. (This
                # stylesheet has none today; the guard keeps a future one
                # from being mangled.)
                body = inner if prelude.startswith("@keyframes") else walk(inner)
                out.append(f"{prelude}{{{body}}}")
            elif prelude:
                out.append(f"{scope_selector(prelude)}{{{' '.join(inner.split())}}}")
            i = j
        return "\n".join(out)

    # Strip block comments FIRST -- see the docstring's deviation (2): this
    # stylesheet's comments contain commas, which would otherwise be split
    # as selector boundaries. Comments are non-functional in the embedded
    # form; the standalone page keeps them via render_head.
    return walk(re.sub(r"/\*.*?\*/", "", CSS, flags=re.S))


def render_empty_state(cycles_dir: Path) -> str:
    return f"""
<div class="empty-state">
<h2 style="margin-bottom:8px">No cycle records yet</h2>
<p>This page renders every run any self-correcting loop has logged to<br>
<code>{esc(str(cycles_dir))}/&lt;system&gt;/&lt;cycle_id&gt;.json</code>.</p>
<p>Nothing has written a record there yet — once a loop runs and logs a cycle, re-run this
renderer and its story will appear here.</p>
</div>
"""


def render_malformed_panel(issues: list[LoadIssue]) -> str:
    if not issues:
        return ""
    rows = "".join(
        f'<div class="issue-row"><code>{esc(i.path)}</code> — {esc(i.reason)}</div>' for i in issues
    )
    return f"""
<details class="issues panel">
<summary>{len(issues)} file(s) could not be read as cycle records (excluded below, not silently dropped)</summary>
<div style="margin-top:8px">{rows}</div>
</details>
"""


def render_stat(label: str, value: str) -> str:
    return f'<div class="stat"><div class="n">{value}</div><div class="l">{esc(label)}</div></div>'


def render_trend_card(label: str, value_text: str, values: Sequence[float | None], higher_is_better: bool | None) -> str:
    prev, curr = last_two_non_none(values)
    return f"""
<div class="trend-card">
  <div class="label">{esc(label)}</div>
  <div class="value">{value_text}</div>
  {render_sparkline(values)}
  {trend_arrow(prev, curr, higher_is_better)}
</div>
"""


def _fmt_catch_cell(d: dict[str, float | int | None] | None) -> str:
    """One <td> body for a plant_catch_by_trade bucket. `d` is None for TWO
    distinct reasons (both render the same honest em-dash, never a
    fabricated 0/0): (1) this trade never appears in plant_catch_by_trade
    at all because it only ever showed up as a control in
    false_alarm_by_trade, or (2) the trade appears in calibration_run_rows
    (a real row named it) but every plant row for it had zero readable
    signal (empty, validly-typed caught_by AND missed_by) --
    render_system_summary's grid-table row set includes this trade anyway
    (see calibration_run_trades), so this cell must render something
    honest rather than the row silently vanishing. `unreadable` is shown
    explicitly whenever nonzero -- a malformed caught_by/missed_by, OR an
    unreadable plant_id/trade discriminator, must never quietly vanish
    into "0 observed"."""
    if not d:
        return "&mdash;"
    caught = int(d.get("caught") or 0)
    missed = int(d.get("missed") or 0)
    observed = caught + missed
    unreadable = int(d.get("unreadable") or 0)
    if observed == 0 and unreadable:
        # "0/0" reads as a confident "checked, saw nothing" observation --
        # suppress the fraction entirely when there is no READABLE
        # catch/miss at all, and name the unreadable count directly
        # instead, rather than a fraction that LOOKS clean sitting next to
        # a small parenthetical most skimming readers would miss.
        return f'<span class="reasoning">{unreadable} unreadable, no readable catch/miss</span>'
    text = f"{caught}/{observed} &middot; {fmt_pct(d.get('rate'))}"
    if unreadable:
        text += f" <span class=\"reasoning\">({unreadable} unreadable)</span>"
    return text


def _fmt_alarm_cell(d: dict[str, float | int | None] | None) -> str:
    """One <td> body for a false_alarm_by_trade bucket -- see
    _fmt_catch_cell above for the None/`unreadable` rationale (both of its
    two causes apply here too: a trade that only ever showed up as a plant,
    or one whose only calibration_runs rows were control rows with an
    unreadable discriminator and therefore no readable control count at
    all). The rate here is deliberately UNBOUNDED above 100% (a control that
    draws more than one finding, or several controls each drawing one, both
    raise false_alarms faster than controls) -- fmt_pct does not clamp it,
    and this cell must not either."""
    if not d:
        return "&mdash;"
    controls = int(d.get("controls") or 0)
    false_alarms = int(d.get("false_alarms") or 0)
    unreadable = int(d.get("unreadable") or 0)
    if controls == 0 and unreadable:
        # Same suppression as _fmt_catch_cell -- "0 / 0 controls" reads as
        # a confident, checked-and-clean observation; with zero READABLE
        # controls, name the unreadable count directly instead of a
        # fraction that looks clean at a glance.
        return f'<span class="reasoning">{unreadable} unreadable, no readable controls</span>'
    text = f"{false_alarms} / {controls} controls &middot; {fmt_pct(d.get('rate'))}"
    if unreadable:
        text += f" <span class=\"reasoning\">({unreadable} unreadable)</span>"
    return text


def render_system_summary(system: str, analysis: Analysis) -> str:
    cost = analysis.cost
    stats = "".join(
        [
            render_stat("cycles", str(analysis.n_cycles)),
            render_stat("findings", str(analysis.n_findings)),
            render_stat("dispatches", str(analysis.dispatch_count)),
            render_stat("symptom precision", fmt_pct(analysis.symptom_precision)),
            render_stat("cause precision", fmt_pct(analysis.cause_precision)),
            render_stat("$ / confirmed defect", fmt_usd(analysis.usd_per_confirmed_defect)),
        ]
    )
    plant_rows = ""
    if analysis.plant_catch_by_slot:
        body = "".join(
            f"<tr><td>{esc(slot)}</td><td>{d['caught']}/{d['caught'] + d['missed']}</td>"
            # #9 (round 4): use plant_catch_by_slot()'s own already-computed
            # `rate` instead of hand-recomputing it here -- numerically
            # identical today, but a hand-synced duplicate of a value the
            # library already returns is exactly the "drifts silently"
            # pattern this module's own history (BLOCKER 3, round 3) warns
            # about.
            f"<td>{fmt_pct(d['rate'])}</td></tr>"
            for slot, d in sorted(analysis.plant_catch_by_slot.items())
        )
        plant_rows = f"""
<div class="table-scroll" style="margin-top:10px">
<table>
<thead><tr><th>slot (dispatch batch position)</th><th>caught / observed</th><th>catch rate</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""

    # The GRID form of calibration (calibration_runs[]) rendered honestly,
    # as its own table -- a record can carry a full plants-x-trades grid
    # with zero legacy `calibration` data. Existence and the table's row
    # SET are keyed on analysis.calibration_run_rows / .calibration_run_trades
    # (the RAW ground truth read directly off calibration_runs[] rows,
    # computed in analyze() -- see Analysis's own field comments), never on
    # plant_catch_by_trade/false_alarm_by_trade's output alone: those two
    # are necessarily LOSSY by design (a plant row with genuinely zero
    # readable catch/miss signal gets no bucket at all), so keying grid
    # existence on them would silently drop a real, valid,
    # seeded-but-never-exercised plant off the page, or drop a zero-signal
    # trade out of a mixed grid entirely. The two aggregators are still the
    # SAME two library functions cycle_telemetry.py's own CLI `metrics`
    # renderer uses for the actual catch/alarm NUMBERS -- only the "does a
    # grid exist, and which trades does it name" decision is independent of
    # them.
    grid_rows = ""
    if analysis.calibration_run_rows:
        trades = sorted(
            set(analysis.plant_catch_by_trade)
            | set(analysis.false_alarm_by_trade)
            | set(analysis.calibration_run_trades)
        )
        if trades:
            body = "".join(
                f"<tr><td>{esc(trade)}</td>"
                f"<td>{_fmt_catch_cell(analysis.plant_catch_by_trade.get(trade))}</td>"
                f"<td>{_fmt_alarm_cell(analysis.false_alarm_by_trade.get(trade))}</td></tr>"
                for trade in trades
            )
            grid_rows = f"""
<div class="table-scroll" style="margin-top:10px">
<table>
<thead><tr><th>trade (calibration_runs grid)</th><th>plants: caught / observed &middot; rate</th><th>controls: false alarms / controls &middot; rate</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""
        else:
            # Rows exist, but NEITHER aggregator produced a bucket AND no
            # row's `trade` was itself readable (calibration_run_trades is
            # only populated from a readably-named trade) -- there is
            # nothing to key a table row on at all. An honest LINE naming
            # the row count, never a silently-empty (or absent) table.
            row_word = "row" if analysis.calibration_run_rows == 1 else "rows"
            grid_rows = (
                '<p class="reasoning" style="margin-top:10px">'
                f"{analysis.calibration_run_rows} calibration_runs {row_word} recorded, "
                "but no readable catch/miss/false-alarm observation could be attributed "
                "to a trade."
                "</p>"
            )

    if not plant_rows and not analysis.calibration_run_rows and analysis.n_cycles:
        # BLOCKER 4 (round 4): missing calibration -- neither the legacy
        # single `calibration` block NOR ANY calibration_runs row exists at
        # all -- must never render as a fabricated 0% catch rate. Only
        # reached when BOTH sources are genuinely empty (calibration_run_rows
        # == 0 here implies grid_rows is already "" by construction above),
        # never when either one has real data the other happens to lack.
        plant_rows = (
            '<p class="reasoning" style="margin-top:10px">'
            "No calibration plants seeded in this view "
            "(neither the legacy calibration block nor a calibration_runs grid)."
            "</p>"
        )
    # Join without a hardcoded blank-line separator -- an f-string with a
    # bare `{grid_rows}` on its own line would leave a stray blank line
    # whenever grid_rows is "".
    calibration_html = "".join(part for part in (plant_rows, grid_rows) if part)
    # No single "count" concept spans both the legacy single-plant block and
    # the calibration_runs grid honestly -- rather than fabricate one by
    # summing two different things, this sub-expander's summary carries no
    # count at all (wrap_sub_expander's own count=None -> "not recorded"
    # text would be misleading here too, since data DOES exist; the gist
    # text alone communicates presence).
    calibration_section = (
        wrap_sub_expander(
            "Calibration (plants & controls)",
            None,
            "seeded plant / control data recorded for this view",
            calibration_html,
            count_text="recorded",
        )
        if calibration_html
        else ""
    )
    return f"""
<div class="panel">
<div class="stat-row">{stats}</div>
<div class="mini-stats">
<div>cost so far: <b>{cost_headline(cost)}</b> ({fmt_tokens(cost.total_tokens)} priced tokens)</div>
<div>harness-reported dispatch tokens (not billed spend, a separate figure): <b>{fmt_tokens(analysis.dispatch_tokens_reported)}</b></div>
</div>
{calibration_section}
</div>
"""


def render_findings_table(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return '<p class="reasoning">No findings recorded for this cycle.</p>'
    findings_sorted = sorted(findings, key=lambda f: _safe_str(f.get("finding_id")) or "")
    rows = []
    for f in findings_sorted:
        raised_by = _safe_list(f.get("raised_by"))
        raised_by_text = ", ".join(esc(x) for x in raised_by) if raised_by else "—"
        reasoning_bits = []
        if f.get("already_tracked_as"):
            reasoning_bits.append(f"duplicate of <b>{esc(f['already_tracked_as'])}</b>")
        if f.get("fights_ruling"):
            reasoning_bits.append(f"fights ruling <b>{esc(f['fights_ruling'])}</b>")
        reasoning = " · ".join(reasoning_bits) if reasoning_bits else "—"
        found_at_stage = f.get("found_at_stage")
        issue_refs = _safe_list(f.get("issue_refs"))
        issue_refs_text = ", ".join(esc(x) for x in issue_refs) if issue_refs else "—"
        rows.append(
            "<tr>"
            f"<td>{esc(f.get('finding_id')) or '—'}</td>"
            f"<td class='wrap-cell'>{raised_by_text}</td>"
            f"<td class='wrap-cell'>{esc(f.get('claim_symptom')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(f.get('claim_cause')) or '—'}</td>"
            f"<td>{badge(f.get('consolidator_decision'), KNOWN_CONSOLIDATOR_DECISIONS)}</td>"
            f"<td>{badge(f.get('verifier_verdict'), KNOWN_VERIFIER_VERDICTS)}</td>"
            f"<td>{fmt_bool_or_null(f.get('verifier_cause_upheld'))}</td>"
            f"<td>{fix_status_badge(f.get('fix_status'))}</td>"
            f"<td>{esc(found_at_stage) or '—'}</td>"
            f"<td class='wrap-cell'>{issue_refs_text}</td>"
            f"<td class='wrap-cell reasoning'>{reasoning}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>finding</th><th>raised by</th><th>claimed symptom</th><th>claimed cause</th>
<th>consolidator</th><th>verifier verdict</th><th>cause upheld</th><th>fix status</th>
<th>found at</th><th>issues filed</th><th>why</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_dispatch_summary(dispatches: list[dict[str, Any]]) -> str:
    if not dispatches:
        return '<p class="reasoning">No dispatches recorded for this cycle.</p>'
    rows = []
    for d in sorted(
        dispatches,
        # Round 12, nit #8: this was the one sort key across both files
        # still doing its own inline `isinstance(..., (int, float))` check
        # instead of routing through this codebase's already-established
        # shared finiteness/type-safety helper (`_is_number`, delegating to
        # `ct.is_finite_number`) -- its sibling `_review_sort_key` already
        # correctly excludes `bool` (a `bool` is an `int` subclass in
        # Python, so a plain `isinstance(..., (int, float))` check silently
        # admits it); `_is_number` excludes both `bool` AND a non-finite
        # float (NaN/Infinity), which a bare isinstance check cannot. A NaN
        # in a sort key comparison never actually raises in Python, so this
        # was never reachable as a crash -- purely closing the same
        # un-consolidated-check pattern eliminated everywhere else.
        key=lambda d: (d.get("batch_position") if _is_number(d.get("batch_position")) else 0, _safe_str(d.get("label")) or ""),
    ):
        tokens_reported = d.get("tokens_reported")
        tokens_source = d.get("tokens_source")
        if tokens_reported is not None:
            reported_cell = (
                f"{fmt_int_or_dash(tokens_reported)} "
                f"<span class='reasoning'>({esc(tokens_source) if tokens_source else 'unlabelled — should not happen'})</span>"
            )
        else:
            reported_cell = "—"
        rows.append(
            "<tr>"
            f"<td>{esc(d.get('agent_type')) or '—'}</td>"
            f"<td>{esc(d.get('label')) or '—'}</td>"
            f"<td>{esc(d.get('model')) or '—'}</td>"
            f"<td>{fmt_int_or_dash(d.get('tokens_total'))}</td>"
            f"<td>{reported_cell}</td>"
            f"<td>{fmt_usd(d.get('cost_usd')) if d.get('cost_usd') is not None else '—'}</td>"
            f"<td>{fmt_int_or_dash(d.get('tool_calls'))}</td>"
            f"<td>{fmt_int_or_dash(d.get('duration_ms'))}</td>"
            f"<td>{fmt_int_or_dash(d.get('batch_position'))}/{fmt_int_or_dash(d.get('batch_size'))}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>agent type</th><th>label</th><th>model</th><th>tokens_total (harness-reported, not billed spend)</th>
<th>tokens_reported (harness-reported, labelled provenance)</th>
<th>cost (per-dispatch, if recorded)</th><th>tool calls</th><th>duration (ms)</th><th>batch pos/size</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def _empty_note(label: str) -> str:
    return f'<p class="reasoning">No {label} recorded for this cycle.</p>'


def render_runs_table(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return _empty_note("runs")
    rows = []
    for r in sorted(runs, key=lambda r: _safe_str(r.get("run_id")) or ""):
        agent_types = _safe_list(r.get("agent_types"))
        rows.append(
            "<tr>"
            f"<td>{esc(r.get('run_id')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(r.get('purpose')) or '—'}</td>"
            f"<td class='wrap-cell'>{', '.join(esc(a) for a in agent_types) or '—'}</td>"
            f"<td>{esc(r.get('model')) or '—'}</td>"
            f"<td>{fmt_ts(r.get('started_at'))} → {fmt_ts(r.get('ended_at'))}</td>"
            f"<td>{fmt_int_or_dash(r.get('dispatch_count'))}</td>"
            f"<td class='wrap-cell'>{esc(r.get('outcome')) or '—'}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>run</th><th>purpose</th><th>agent types</th><th>model</th><th>window</th>
<th>dispatches</th><th>outcome</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def _review_sort_key(r: dict[str, Any]) -> tuple[str, int]:
    """Round 10, BLOCKER 2: this used to be `r.get("round") or 0` -- `or 0`
    only falls back on a FALSY value, so a present-but-wrong-type `round`
    (e.g. the string `"two"`, a realistic hand-edited/corrupted field)
    passed straight through and crashed `sorted()` with a `str`-vs-`int`
    TypeError the instant it sat next to one real int round in the SAME
    record's reviews list -- this is round 8's `read_cycles()` sort-key
    fix (BLOCKER 3 there), structurally identical, on this file's own
    sibling sort key. The crash escaped all the way to main()'s outer
    except handler and blanked the WHOLE multi-system report, including
    every record from a completely unrelated system, with the offending
    file never even listed in the "excluded" panel -- so this key must be
    type-safe on its own, the same way `_safe_str(...) or ""` already is
    for `review_id`."""
    round_ = r.get("round")
    round_key = round_ if isinstance(round_, int) and not isinstance(round_, bool) else 0
    return (_safe_str(r.get("review_id")) or "", round_key)


def render_reviews_table(reviews: list[dict[str, Any]]) -> str:
    if not reviews:
        return _empty_note("reviews")
    blocks = []
    for r in sorted(reviews, key=_review_sort_key):
        outcome = r.get("outcome")
        outcome_cls = "badge bad" if outcome == "blockers" else ("badge good" if outcome == "clean" else "badge unknown")
        finding_rows = "".join(
            "<tr>"
            f"<td class='wrap-cell'>{esc(rf.get('description')) or '—'}</td>"
            f"<td>{esc(rf.get('severity')) or '—'}</td>"
            f"<td>{fmt_bool_or_null(rf.get('fixed'))}</td>"
            "</tr>"
            for rf in _safe_list_of_dicts(r.get("findings"))
        )
        findings_table = (
            f"""<div class="table-scroll" style="margin-top:6px">
<table><thead><tr><th>blocker</th><th>severity</th><th>fixed</th></tr></thead>
<tbody>{finding_rows}</tbody></table></div>"""
            if finding_rows
            else '<p class="reasoning">No individual findings recorded on this review.</p>'
        )
        upheld = _safe_list(r.get("upheld_decisions"))
        overturned = _safe_list(r.get("overturned_decisions"))
        related = _safe_list(r.get("related_findings"))
        blocks.append(
            f"""
<div class="panel" style="margin-bottom:10px">
  <div class="mini-stats">
    <div>review <b>{esc(r.get('review_id')) or '—'}</b> round <b>{fmt_int_or_dash(r.get('round'))}</b></div>
    <div>reviewer: <b>{esc(r.get('reviewer')) or '—'}</b> ({esc(r.get('model')) or 'model unknown'})</div>
    <div>target: <b>{esc(r.get('target')) or '—'}</b></div>
    <div>reviewed_at: <b>{fmt_ts(r.get('reviewed_at'))}</b></div>
    <div>blockers: <b>{fmt_int_or_dash(r.get('blocker_count'))}</b></div>
    <div>outcome: <span class="{outcome_cls}">{esc(outcome) or 'not set'}</span></div>
  </div>
  {f"<div class='reasoning'>related findings: {', '.join(esc(x) for x in related)}</div>" if related else ""}
  {findings_table}
  {f"<div class='reasoning' style='margin-top:6px'>upheld: {'; '.join(esc(x) for x in upheld)}</div>" if upheld else ""}
  {f"<div class='reasoning'>overturned: {'; '.join(esc(x) for x in overturned)}</div>" if overturned else ""}
</div>
"""
        )
    return "".join(blocks)


def render_changes_table(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return _empty_note("changes")
    rows = []
    for c in sorted(changes, key=lambda c: _safe_str(c.get("change_id")) or ""):
        files = _safe_list(c.get("files"))
        tests = _safe_list(c.get("tests_added"))
        reverted = c.get("reverted")
        rows.append(
            "<tr>"
            f"<td>{esc(c.get('change_id')) or '—'}</td>"
            f"<td>{esc(c.get('finding_id')) or '—'}</td>"
            f"<td><code>{esc(c.get('commit_sha')) or '—'}</code></td>"
            f"<td class='wrap-cell'>{', '.join(esc(x) for x in files) or '—'}</td>"
            f"<td>+{fmt_int_or_dash(c.get('lines_added'))}/-{fmt_int_or_dash(c.get('lines_removed'))}</td>"
            f"<td class='wrap-cell'>{esc(c.get('red_before_green')) or '—'}</td>"
            f"<td class='wrap-cell'>{', '.join(esc(x) for x in tests) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(c.get('golden_net_drift')) or '—'}</td>"
            f"<td>{'yes' if reverted else 'no'}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>change</th><th>finding</th><th>commit</th><th>files</th><th>lines +/-</th>
<th>red-before-green evidence</th><th>tests added</th><th>golden-net drift</th><th>reverted</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_decisions_table(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return _empty_note("decisions")
    rows = []
    for d in sorted(decisions, key=lambda d: _safe_str(d.get("decision_id")) or ""):
        decided_by = _safe_str(d.get("decided_by")) or "—"
        decided_by_cell = (
            f'<span class="badge info">{esc(decided_by)}</span>'
            if decided_by.upper() == "OPERATOR"
            else esc(decided_by)
        )
        supersedes = _safe_list(d.get("supersedes"))
        rows.append(
            "<tr>"
            f"<td>{esc(d.get('decision_id')) or '—'}</td>"
            f"<td>{decided_by_cell}</td>"
            f"<td class='wrap-cell'>{esc(d.get('what')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(d.get('reasoning')) or '—'}</td>"
            f"<td class='wrap-cell'>{', '.join(esc(x) for x in supersedes) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(d.get('action')) or '—'}</td>"
            f"<td>{fmt_ts(d.get('decided_at'))}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>decision</th><th>decided by</th><th>what</th><th>reasoning (verbatim)</th>
<th>supersedes</th><th>action</th><th>decided at</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_issues_filed_table(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return _empty_note("issues filed")
    rows = []
    for i in sorted(issues, key=lambda i: _safe_str(i.get("issue_id")) or ""):
        related = _safe_list(i.get("related_findings"))
        rows.append(
            "<tr>"
            f"<td>{esc(i.get('issue_id')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(i.get('title')) or '—'}</td>"
            f"<td class='wrap-cell'>{', '.join(esc(x) for x in related) or '—'}</td>"
            f"<td>{esc(i.get('filed_by')) or '—'}</td>"
            f"<td>{fmt_ts(i.get('filed_at'))}</td>"
            f"<td>{esc(i.get('status')) or '—'}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>issue</th><th>title</th><th>related findings</th><th>filed by</th><th>filed at</th><th>status</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return _empty_note("evidence")
    rows = []
    for e in sorted(evidence, key=lambda e: _safe_str(e.get("evidence_id")) or ""):
        loc = esc(e.get("file")) or "—"
        if e.get("line") is not None:
            loc += f":{fmt_int_or_dash(e.get('line'))}"
        rows.append(
            "<tr>"
            f"<td>{esc(e.get('evidence_id')) or '—'}</td>"
            f"<td>{esc(e.get('finding_id')) or '—'}</td>"
            f"<td><code>{loc}</code></td>"
            f"<td class='wrap-cell'>{esc(e.get('quote')) or '—'}</td>"
            f"<td class='wrap-cell'><code>{esc(e.get('repro_command')) or '—'}</code></td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>evidence</th><th>finding</th><th>file:line</th><th>quote</th><th>repro command</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_corrections_table(corrections: list[dict[str, Any]]) -> str:
    if not corrections:
        return _empty_note("corrections")
    rows = []
    for c in sorted(corrections, key=lambda c: _safe_str(c.get("correction_id")) or ""):
        rows.append(
            "<tr>"
            f"<td>{esc(c.get('correction_id')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(c.get('what_was_claimed')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(c.get('what_was_wrong')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(c.get('how_found')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(c.get('invalidated')) or '—'}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>correction</th><th>what was claimed</th><th>what was wrong</th><th>how found</th><th>invalidated</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_verdicts_table(verdicts: list[dict[str, Any]]) -> str:
    if not verdicts:
        return _empty_note("raw per-scenario verdicts")
    rows = []
    for v in sorted(
        verdicts, key=lambda v: (_safe_str(v.get("dispatch_label")) or "", _safe_str(v.get("scenario")) or "")
    ):
        rows.append(
            "<tr>"
            f"<td>{esc(v.get('dispatch_label')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(v.get('scenario')) or '—'}</td>"
            f"<td>{badge(v.get('verdict'), VERDICT_VALUES_KNOWN)}</td>"
            f"<td>{fmt_pct(v.get('confidence')) if v.get('confidence') is not None else '—'}</td>"
            f"<td>{fmt_int_or_dash(v.get('problem_count'))}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr>
<th>dispatch</th><th>scenario</th><th>verdict</th><th>confidence</th><th>problems raised</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def render_stages_table(stages: list[dict[str, Any]]) -> str:
    if not stages:
        return _empty_note("pipeline stages")
    rows = []
    for s in sorted(stages, key=lambda s: _safe_str(s.get("stage_id")) or ""):
        status = _safe_str(s.get("status"))
        status_cls = {"ran": "badge good", "skipped": "badge neutral", "blocked": "badge bad"}.get(
            status or "", "badge unknown"
        )
        rows.append(
            "<tr>"
            f"<td>{esc(s.get('stage_id')) or '—'}</td>"
            f"<td class='wrap-cell'>{esc(s.get('name')) or '—'}</td>"
            f"<td><span class='{status_cls}'>{esc(status) or 'not set'}</span></td>"
            f"<td class='wrap-cell'>{esc(s.get('blocked_reason')) or '—'}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="table-scroll">
<table>
<thead><tr><th>stage</th><th>name</th><th>status</th><th>blocked reason</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>
"""


def _findings_gist(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "none this cycle"
    verdicts = count_by(f.get("verifier_verdict") for f in findings)
    confirmed = verdicts.get("CONFIRMED", 0) + verdicts.get("PARTIALLY_CONFIRMED", 0)
    refuted = verdicts.get("REFUTED", 0)
    unset = verdicts.get("(not set)", 0)
    bits = [f"{confirmed} confirmed"]
    if refuted:
        bits.append(f"{refuted} refuted")
    if unset:
        bits.append(f"{unset} not yet verified")
    return ", ".join(bits)


def _dispatches_gist(dispatches: list[dict[str, Any]]) -> str:
    if not dispatches:
        return "none this cycle"
    agents = sorted({_safe_str(d.get("agent_type")) or "(not set)" for d in dispatches})
    preview = ", ".join(agents[:3])
    if len(agents) > 3:
        preview += f", +{len(agents) - 3} more"
    return preview


def _generic_gist(rows: list[dict[str, Any]], id_key: str) -> str:
    """Returns PLAIN text -- never pre-escaped. Every gist this module
    builds is escaped exactly once, at `wrap_sub_expander`'s own boundary
    (see its docstring); a helper that also escaped here would double-
    escape (`&amp;lt;` instead of `&lt;`) once that boundary fix landed."""
    if not rows:
        return "none this cycle"
    ids = [str(r.get(id_key)) for r in rows[:3] if r.get(id_key)]
    preview = ", ".join(ids)
    if len(rows) > 3:
        preview += f", +{len(rows) - 3} more"
    return preview


def render_cycle_details(record: CycleRecord, analysis: Analysis | None = None) -> str:
    """One nested, collapsible `<details>` per cycle -- REPLACES the old
    flat, always-fully-rendered `render_cycle_card`. B-ASSERT-9 (operator
    amendment, 2026-09-05, "all expanders should default closed"): this
    used to open the newest cycle in a system by default via an `open_`
    parameter; that parameter is now DELETED (cold review round 1,
    regression 3) rather than kept-but-unused -- it had exactly one call
    site, always hardcoded `False`, zero external consumers, and no test
    ever varied it, so keeping it "for API compatibility" was a dead
    surface one edit away from silently drifting out of sync again, the
    same trap this whole wave just removed the behavior FOR. Every cycle
    now always renders closed. Every list inside (findings, dispatches,
    runs, ...) is a further nested `<details>` whose `<summary>` carries a
    count and a one-line gist, so a collapsed cycle costs almost nothing
    on the page and an operator only pays for what they actually expand.

    `analysis` reuse and its performance rationale are unchanged from the
    old `render_cycle_card` (see git history) -- `render_system_details`
    still computes one `analyze([r])` per record for its trend series and
    passes it straight in here, so this function never redundantly
    recomputes `ct.aggregate_metrics()` a second time per cycle."""
    raw = record.raw
    if analysis is None:
        analysis = analyze([record])
    quality_badges = "".join(f'<span class="badge unknown">{esc(n)}</span>' for n in record.quality_notes)
    notes = _safe_list(raw.get("notes"))
    notes_html = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        notes_html = f'<div class="cycle-notes"><b>Notes / reasoning for this cycle:</b><ul>{items}</ul></div>'
    repo = _safe_str(raw.get("repo")) or "no repo recorded"

    findings = _safe_list_of_dicts(raw.get("findings"))
    dispatches = _safe_list_of_dicts(raw.get("dispatches"))
    runs = _safe_list_of_dicts(raw.get("runs"))
    reviews = _safe_list_of_dicts(raw.get("reviews"))
    changes = _safe_list_of_dicts(raw.get("changes"))
    decisions = _safe_list_of_dicts(raw.get("decisions"))
    issues_filed = _safe_list_of_dicts(raw.get("issues_filed"))
    evidence = _safe_list_of_dicts(raw.get("evidence"))
    corrections = _safe_list_of_dicts(raw.get("corrections"))
    verdicts = _safe_list_of_dicts(raw.get("verdicts"))
    stages = _safe_list_of_dicts(raw.get("stages"))

    sub_sections = "".join(
        [
            wrap_sub_expander(
                "What the last cycle found",
                len(findings),
                _findings_gist(findings),
                render_findings_table(findings),
            ),
            wrap_sub_expander(
                "Dispatches",
                len(dispatches),
                _dispatches_gist(dispatches),
                render_dispatch_summary(dispatches),
            ),
            wrap_sub_expander(
                "Runs",
                len(runs),
                _generic_gist(runs, "run_id"),
                render_runs_table(runs),
                title="Every agent run this cycle made, not just the finder-pass dispatches above.",
            ),
            wrap_sub_expander(
                "Reviews", len(reviews), _generic_gist(reviews, "review_id"), render_reviews_table(reviews)
            ),
            wrap_sub_expander(
                "Changes", len(changes), _generic_gist(changes, "change_id"), render_changes_table(changes)
            ),
            wrap_sub_expander(
                "Decisions",
                len(decisions),
                _generic_gist(decisions, "decision_id"),
                render_decisions_table(decisions),
                title="Operator rulings are first-class decisions here.",
            ),
            wrap_sub_expander(
                "Issues filed",
                len(issues_filed),
                _generic_gist(issues_filed, "issue_id"),
                render_issues_filed_table(issues_filed),
            ),
            wrap_sub_expander(
                "Evidence", len(evidence), _generic_gist(evidence, "evidence_id"), render_evidence_table(evidence)
            ),
            wrap_sub_expander(
                "Corrections",
                len(corrections),
                _generic_gist(corrections, "correction_id"),
                render_corrections_table(corrections),
                title="The loop's own recorded error/correction history.",
            ),
            wrap_sub_expander(
                "Raw per-scenario verdicts",
                len(verdicts),
                _generic_gist(verdicts, "dispatch_label"),
                render_verdicts_table(verdicts),
            ),
            wrap_sub_expander(
                "Pipeline stages", len(stages), _generic_gist(stages, "stage_id"), render_stages_table(stages)
            ),
            render_raw_record_pointer(record),
        ]
    )

    gist = _findings_gist(findings)
    return f"""
<details class="cycle-expander" data-search="{esc(' '.join([record.cycle_id, record.system, repo]).lower())}">
<summary>
  <span class="cycle-summary-left">
    <span class="cycle-id">{esc(record.cycle_id)}</span>
    <span class="reasoning">({esc(repo)})</span>
    <span class="reasoning">{fmt_ts(raw.get('started_at'))} → {fmt_ts(raw.get('ended_at'))}</span>
    <span class="reasoning">{esc(gist)}</span>
  </span>
  <span class="reasoning">cost: {cost_headline(analysis.cost)}</span>
</summary>
{f'<div class="quality-notes">{quality_badges}</div>' if quality_badges else ''}
{notes_html}
<div class="mini-stats">
<div>findings: <b>{analysis.n_findings}</b></div>
<div>symptom precision: <b>{fmt_pct(analysis.symptom_precision)}</b></div>
<div>cause precision: <b>{fmt_pct(analysis.cause_precision)}</b></div>
<div>duplicate rate: <b>{fmt_pct(analysis.duplicate_rate)}</b></div>
<div>ruling conflicts: <b>{fmt_pct(analysis.ruling_conflict_rate)}</b></div>
<div>consolidation: <b>{fmt_ratio(analysis.consolidation_ratio)}</b></div>
</div>
{sub_sections}
</details>
"""


def _distinct_causes(findings: list[dict[str, Any]]) -> int:
    """A per-cycle count of distinct claimed causes -- used only for the
    trend chart's second series. A finding with no claim_cause recorded
    contributes nothing to the distinct set (never counted as a fabricated
    "cause"). Returns a plain int (never rendered as text itself), so no
    escaping applies here -- the raw claim_cause strings are only ever
    used as dict-membership keys to count distinct values, never emitted."""
    return len({f.get("claim_cause") for f in findings if _safe_str(f.get("claim_cause"))})


def render_system_details(
    system: str,
    records: list[CycleRecord],
    precomputed: tuple[list[CycleRecord], Analysis, list[Analysis]] | None = None,
) -> str:
    """One outer, collapsible `<details>` per system -- REPLACES the old
    always-expanded `<section>`. Every system collapses to its one-line
    `<summary>` (name + cycle count), keeping the whole page short until
    an operator actually wants to look at it. B-ASSERT-9 (operator
    amendment, 2026-09-05, "all expanders should default closed"): this
    used to open the most-recently-active system by default via an
    `open_` parameter; that parameter is now DELETED (cold review round 1,
    regression 3), not kept-but-unused -- see render_cycle_details' own
    docstring for the identical rationale (one hardcoded call site, zero
    external consumers, no test varied it).

    `precomputed`, when supplied by `render_document` (which needs the
    identical ordered-records/whole-system-Analysis/per-cycle-Analysis
    triple for `render_executive_summary` too), skips recomputing it here
    -- avoids doubling `ct.aggregate_metrics()` calls across the document.
    A direct caller (this function's own unit test) that omits it gets the
    original N+1-calls-per-system behavior unchanged."""
    if precomputed is not None:
        ordered, analysis, per_cycle = precomputed
    else:
        ordered = sorted(records, key=lambda r: r.sort_key())
        analysis = analyze(ordered)
        per_cycle = [analyze([r]) for r in ordered]
    symptom_series = [a.symptom_precision for a in per_cycle]
    cause_series = [a.cause_precision for a in per_cycle]
    dup_series = [a.duplicate_rate for a in per_cycle]
    conflict_series = [a.ruling_conflict_rate for a in per_cycle]
    cost_series = [a.usd_per_confirmed_defect for a in per_cycle]
    consolidation_series = [a.consolidation_ratio for a in per_cycle]
    # MISSING IS NOT ZERO (same fix as render_executive_summary's headline
    # cell, coordinator review item 4): a cycle whose source JSON never
    # carried a `findings` key at all must plot as a real gap here too,
    # never a fabricated 0 -- `r.has_findings` is the presence signal
    # normalize_record's own (unchanged) coercion cannot preserve.
    findings_count_series: list[float | None] = [
        float(a.n_findings) if r.has_findings else None for r, a in zip(ordered, per_cycle)
    ]
    distinct_cause_series: list[float | None] = [
        float(_distinct_causes(_safe_list_of_dicts(r.raw.get("findings")))) if r.has_findings else None
        for r in ordered
    ]

    trend_cards = "".join(
        [
            render_trend_card("symptom precision", fmt_pct(analysis.symptom_precision), symptom_series, True),
            render_trend_card("cause precision", fmt_pct(analysis.cause_precision), cause_series, True),
            render_trend_card("duplicate rate", fmt_pct(analysis.duplicate_rate), dup_series, False),
            render_trend_card("ruling conflict rate", fmt_pct(analysis.ruling_conflict_rate), conflict_series, False),
            render_trend_card("consolidation ratio", fmt_ratio(analysis.consolidation_ratio), consolidation_series, None),
            render_trend_card("$ / confirmed defect", fmt_usd(analysis.usd_per_confirmed_defect), cost_series, False),
        ]
    )

    trend_chart = render_trend_chart_svg(
        [
            ("findings per cycle", findings_count_series, "findings"),
            ("distinct causes per cycle", distinct_cause_series, "causes"),
        ]
    )

    # Round 12, nit #10 (carried forward): reuse the `per_cycle` analysis
    # already computed above for the trend series, instead of letting
    # render_cycle_details() redundantly recompute the identical
    # `analyze([r])` a second time per record.
    #
    # B-ASSERT-9 (operator amendment, 2026-09-05): "all expanders should
    # default closed -- no <details open> anywhere." This used to open the
    # newest cycle in each system by default; that selection logic (and
    # render_cycle_details' own now-deleted `open_` parameter) is gone --
    # every cycle-expander always renders closed, same as every
    # sys-expander below.
    cycle_details = "".join(
        render_cycle_details(r, a) for r, a in reversed(list(zip(ordered, per_cycle)))
    )

    return f"""
<details class="sys-expander" data-section="{esc(system)}">
<summary>
  <h2 style="display:inline;font-size:17px">{esc(system)}</h2>
  <span class="count">{len(ordered)} cycle(s)</span>
</summary>
<div class="sys-body">
{render_system_summary(system, analysis)}
<h3 style="margin:4px 0 8px">Trend across cycles</h3>
{trend_chart}
<div class="trend-grid">{trend_cards}</div>
<h3 style="margin:14px 0 8px">Cycles (newest first)</h3>
{cycle_details}
</div>
</details>
"""


def render_script(systems: list[str], fragment: bool = False) -> str:
    # `fragment=True` (the render_fragment embedding path, 2026-09-07) roots
    # the two class-based document-wide querySelectorAll calls at the
    # fragment's own container instead of `document`, so the filter script
    # can never touch a HOST page's elements that happen to share a class
    # name (`.sys-expander`/`.cycle-expander` are generic enough that a hub
    # page could legitimately grow one). The getElementById lookups (`q`,
    # `sys-chips`) stay document-wide deliberately -- those ids were
    # verified collision-free against the target hub page, and ids are
    # unique per document by contract. `fragment=False` (the default)
    # renders byte-identically to the pre-parameter output.
    #
    # `sec.querySelectorAll('details.cycle-expander')` inside the loop is
    # already rooted at each sys-expander element and needs no change.
    # `systems` is agent-controlled data (a record's own "system" field, or a
    # cycles-dir directory name) -- never validated against the schema's own
    # SLUG_RE by this renderer, which deliberately tolerates malformed data
    # rather than crashing on it. json.dumps() safely escapes quotes/
    # backslashes/control characters, but a raw '<' still passes through a
    # JSON string verbatim -- a slug containing a literal "</script" would
    # still close the surrounding <script> tag at the HTML-parser level even
    # though the JSON itself is well-formed. Escaping every '<' to its
    # unicode escape closes that specific breakout with no other change in
    # meaning (JS/JSON string content is identical either way).
    # Round 12, nit #9: this was the one `json.dumps` call across both
    # files (out of 14 total) missing `allow_nan=False` -- it currently
    # only ever serializes strings (system slugs), so it can't emit a NaN
    # token today, but adding the flag keeps the operation-type sweep
    # genuinely uniform and removes a future footgun if `systems` is ever
    # changed to carry a non-string value.
    options_json = json.dumps([[s, s] for s in ["all", *systems]], allow_nan=False).replace("<", "\\u003c")
    if fragment:
        root_decl = f"const _clRoot=document.querySelector('.{FRAGMENT_CONTAINER_CLASS}')||document;\n"
        sys_query = "_clRoot.querySelectorAll('details.sys-expander')"
    else:
        root_decl = ""
        sys_query = "document.querySelectorAll('details.sys-expander')"
    return f"""
<script>
{root_decl}const sysOptions={options_json};
let activeSystem='all';
function mkChips(){{
  const el=document.getElementById('sys-chips');
  sysOptions.forEach(([key,label],i)=>{{
    const c=document.createElement('div');
    c.className='chip'+(i===0?' active':'');
    c.textContent=label;
    c.onclick=()=>{{activeSystem=key;[...el.children].forEach(x=>x.classList.toggle('active',x===c));render();}};
    el.appendChild(c);
  }});
}}
function render(){{
  const q=document.getElementById('q').value.trim().toLowerCase();
  {sys_query}.forEach(sec=>{{
    const show=activeSystem==='all'||sec.dataset.section===activeSystem;
    sec.classList.toggle('hidden',!show);
    if(!show)return;
    sec.querySelectorAll('details.cycle-expander').forEach(c=>{{
      const ok=!q||(c.dataset.search||'').includes(q);
      c.classList.toggle('hidden',!ok);
      // A filter match should be visible even if this cycle is not the
      // newest-open one by default -- force it open while a real filter is
      // active, and let it collapse back to the default state once the
      // filter is cleared.
      if(q){{ if(ok) c.setAttribute('open',''); }}
    }});
  }});
}}
mkChips();
document.getElementById('q').addEventListener('input',render);
</script>
"""


def render_print_controls() -> str:
    """Export PDF (B-ASSERT-11, Q2 interim default = scoped print): a
    window.print() button plus a visible "Print all cycles" toggle that
    opts INTO the literal expand-all print behavior. Both are page chrome
    -- hidden in @media print via render_head()'s own print stylesheet
    (`.print-controls{{display:none!important}}`), same treatment as the
    search/filter `.controls` block.

    SCOPED semantics (the default, toggle off): a closed <details> prints
    collapsed and an open one prints expanded -- this is the browser's own
    default rendering of <details> across print/screen, so leaving the
    toggle off costs this renderer nothing extra; it simply never forces
    anything open or closed before printing. Toggling "Print all cycles"
    on activates render_print_script()'s beforeprint/afterprint handlers,
    which force every <details> open for the print pass and restore each
    one's own prior open/closed state afterward -- never a permanent
    change to what is showing on screen."""
    return """
<div class="print-controls">
<button type="button" class="print-btn" onclick="window.print()">Export PDF</button>
<label class="print-all-toggle">
<input type="checkbox" id="print-all-cycles">
Print all cycles (expand everything for this export; leave unchecked to print only what you have open)
</label>
</div>
"""


def render_print_script() -> str:
    """The "Print all cycles" force-open/restore handlers (B-ASSERT-11).
    Written independently of the CSA hub's own analogous pattern (per this
    wave's own instruction: same double-fire-guard SHAPE, own
    implementation, no cross-repo file read) -- `_printAllReopenState`
    guards against `beforeprint` firing twice in a row without an
    intervening `afterprint` (some browsers can fire it more than once per
    print dialog interaction), the same reentrancy concern a `if
    (_reopenState) return;` guard addresses in that sibling design. Only
    engages when the "Print all cycles" checkbox is checked; unchecked, the
    scoped-print default (render_print_controls' own docstring) applies
    with zero JS involvement -- a closed <details> prints collapsed
    because that is simply how the browser prints <details> normally."""
    return """
<script>
let _printAllReopenState=null;
function _printAllBeforePrint(){
  const cb=document.getElementById('print-all-cycles');
  if(!cb||!cb.checked)return;
  if(_printAllReopenState)return;
  const all=[...document.querySelectorAll('details')];
  _printAllReopenState=all.map(d=>d.hasAttribute('open'));
  all.forEach(d=>d.setAttribute('open',''));
}
function _printAllAfterPrint(){
  if(!_printAllReopenState)return;
  const all=[...document.querySelectorAll('details')];
  all.forEach((d,i)=>{ if(!_printAllReopenState[i]) d.removeAttribute('open'); });
  _printAllReopenState=null;
}
window.addEventListener('beforeprint',_printAllBeforePrint);
window.addEventListener('afterprint',_printAllAfterPrint);
</script>
"""


def _system_activity_key(records: list[CycleRecord]) -> tuple[str, str, str]:
    """The most recent cycle's own sort_key() -- used to decide which
    system leads the executive summary table and the newest-activity-first
    system ordering (B-ASSERT-9, 2026-09-05: no longer used to decide which
    system's <details> opens by default -- every sys-expander now renders
    closed regardless of recency)."""
    return max((r.sort_key() for r in records), default=("", "", ""))


def render_executive_summary(
    by_system: dict[str, list[CycleRecord]],
    systems_ordered: list[str],
    system_analyses: dict[str, tuple[list[CycleRecord], Analysis, list[Analysis]]],
) -> str:
    """The compact, 10-second-read table at the top of the page: one row
    per system with its latest cycle id/date, headline counts, a trend
    arrow vs the prior cycle (only when both values exist), a per-cycle
    findings bar sparkline, and cost rendered through `cost_headline` --
    never a bare number, never blank, exactly 'UNKNOWN (source:
    unavailable)' when nothing priced it.

    `system_analyses` is precomputed ONCE by `render_document` (per system:
    its own ordered records, whole-system Analysis, and per-cycle Analysis
    list) and passed in here rather than recomputed -- `render_system_details`
    needs the identical three things for its own trend cards/chart, so
    computing them twice (once here, once there) would double
    `ct.aggregate_metrics()` calls across the whole document for no
    correctness benefit, the same reasoning `render_cycle_details` already
    applies one level down."""
    rows: list[str] = []
    for system in systems_ordered:
        ordered, whole_system_analysis, per_cycle = system_analyses[system]
        latest = ordered[-1]
        latest_analysis = per_cycle[-1]
        # Coordinator review, item 4 (MISSING IS NOT ZERO on the headline):
        # `Analysis.n_findings` is `len(raw["findings"])`, and
        # `normalize_record()` coerces a genuinely ABSENT `findings` key to
        # the same `[]` a real, recorded-but-empty list would produce --
        # by design, for the parity-critical metric path (never changed
        # here). Rendering `a.n_findings` directly as this series' value
        # would silently render "0 findings" for a cycle that never
        # recorded findings AT ALL. `r.has_findings` (captured at load
        # time, straight off the source JSON, before that coercion) is the
        # ONLY thing that can tell the two cases apart -- None here is a
        # real "not recorded," never a fabricated zero-height bar.
        findings_series: list[float | None] = [
            float(a.n_findings) if r.has_findings else None for r, a in zip(ordered, per_cycle)
        ]

        prev_findings, curr_findings = last_two_non_none(findings_series)
        # Findings count is deliberately never colour-judged (None) -- more
        # findings this cycle is not intrinsically "worse" (it could mean a
        # more thorough pass), so this arrow shows direction only.
        trend = trend_arrow(prev_findings, curr_findings, None)

        started_at = fmt_ts(latest.raw.get("started_at"))

        if not latest.has_findings:
            findings_cell = '<span class="not-recorded" title="findings not recorded">not recorded</span>'
        else:
            verdicts = count_by(f.get("verifier_verdict") for f in _safe_list_of_dicts(latest.raw.get("findings")))
            already_tracked = verdicts.get("ALREADY_TRACKED_ELSEWHERE", 0)
            new_count = latest_analysis.n_findings - already_tracked
            findings_cell = (
                f"{latest_analysis.n_findings} "
                f'<span class="reasoning">({new_count} new, {already_tracked} recurring)</span>'
            )

        rows.append(
            "<tr>"
            f'<td class="exec-system">{esc(system)} '
            f'<a class="exec-jump" href="#sys-{esc(system)}">jump ↓</a></td>'
            f"<td>{esc(latest.cycle_id)}<br><span class=\"reasoning\">{started_at}</span></td>"
            f"<td>{findings_cell}</td>"
            f"<td>{trend}</td>"
            f"<td>{render_bar_sparkline(findings_series)}</td>"
            f'<td class="exec-cost">{cost_headline(whole_system_analysis.cost)}</td>'
            "</tr>"
        )
    body = "".join(rows)
    return f"""
<div class="exec-summary panel">
<h2 style="margin-bottom:8px">What happened, at a glance</h2>
<div class="table-scroll">
<table class="exec-table">
<thead><tr>
<th>system</th><th>latest cycle</th><th>findings (latest)</th><th>vs prior cycle</th>
<th>findings per cycle</th><th>cost (all cycles)</th>
</tr></thead>
<tbody>{body}</tbody>
</table>
</div>
<p class="section-note" style="margin-top:8px">Everything below this line is collapsed by default —
expand a system, then a cycle, then a list, to see more. Nothing here is deleted or hidden
permanently; it is just not rendered until you ask for it.</p>
</div>
"""


def _render_main_parts(
    records: list[CycleRecord],
    issues: list[LoadIssue],
    cycles_dir: Path,
    fragment: bool = False,
) -> list[str]:
    """The page CONTENT shared verbatim by both render paths -- extracted
    from render_document (2026-09-07, fragment-embedding API) so the
    embedded fragment can never drift from the standalone page, the same
    single-body principle render_agent_telemetry.py's `body_only` follows.

    `fragment=False` reproduces render_document's original part list for
    this region byte-for-byte. `fragment=True` differs in exactly three
    ways, each host-driven: the title renders as an <h3> (the host hub
    keeps the page's single <h1>, and its tab already carries its own
    <h2> above this); render_print_controls()/render_print_script() are
    omitted (the host has its own print machinery, and a second
    beforeprint/afterprint pair could double-fire against the guard that
    machinery was proven under); and render_script() roots its class-wide
    queries at the fragment container (see its own comment)."""
    title = "Self-Correcting Loop — Cycle Log"
    parts: list[str] = []
    if fragment:
        parts.append(f"<h3>{esc(title)}</h3>")
    else:
        parts.append(f"<h1>{esc(title)}</h1>")
    parts.append(
        '<p class="sub">What every self-correcting agent loop on this machine has claimed, '
        "verified, rejected, fixed, and cost — one row of history per cycle, across every "
        "system that has logged one.</p>"
    )

    n_files = len(discover_cycle_files(cycles_dir)[0]) if cycles_dir.is_dir() else 0
    span = ""
    starts = [r.raw.get("started_at") for r in records if isinstance(r.raw.get("started_at"), str)]
    ends = [r.raw.get("ended_at") for r in records if isinstance(r.raw.get("ended_at"), str)]
    if starts and ends:
        span = f" · data spans {esc(min(starts))} → {esc(max(ends))}"
    parts.append(
        f'<div class="provenance">source: <code>{esc(str(cycles_dir))}</code> · '
        f"{n_files} file(s) found, {len(records)} loaded, {len(issues)} excluded (malformed)"
        f"{span}</div>"
    )

    parts.append(render_malformed_panel(issues))
    if not fragment:
        parts.append(render_print_controls())

    if not records:
        parts.append(render_empty_state(cycles_dir))
        parts.append(render_legend())
        if not fragment:
            parts.append(render_print_script())
        return parts

    by_system: dict[str, list[CycleRecord]] = {}
    for r in records:
        by_system.setdefault(r.system, []).append(r)

    # Systems ordered NEWEST-ACTIVITY-FIRST -- this drives the executive
    # summary row order (newest activity leads the table). Ties (e.g. two
    # systems with no timestamps at all) break on the system slug for
    # determinism.
    #
    # B-ASSERT-9 (operator amendment, 2026-09-05): this ordering USED to
    # also decide which system's <details> opened by default ("newest-
    # activity system open by default"). That behavior, and the `open_`
    # parameter that drove it, are both REMOVED -- every sys-expander now
    # renders closed regardless of recency, unconditionally.
    systems_by_activity = sorted(
        by_system.keys(),
        key=lambda s: (_system_activity_key(by_system[s]), s),
        reverse=True,
    )

    # Computed ONCE per system and reused by both the executive summary and
    # each system's own details section -- see render_executive_summary's
    # and render_system_details' own docstrings for why this avoids
    # doubling ct.aggregate_metrics() calls across the whole document.
    system_analyses: dict[str, tuple[list[CycleRecord], Analysis, list[Analysis]]] = {}
    for system in systems_by_activity:
        ordered = sorted(by_system[system], key=lambda r: r.sort_key())
        system_analyses[system] = (ordered, analyze(ordered), [analyze([r]) for r in ordered])

    parts.append(render_executive_summary(by_system, systems_by_activity, system_analyses))

    parts.append(
        '<div class="controls">'
        '<input id="q" type="text" placeholder="Filter cycles by id, system, or repo…">'
        '<div class="chips" id="sys-chips"></div>'
        "</div>"
    )

    parts.append(render_legend())

    for system in systems_by_activity:
        parts.append(f'<a id="sys-{esc(system)}"></a>')
        parts.append(
            render_system_details(
                system,
                by_system[system],
                precomputed=system_analyses[system],
            )
        )

    parts.append(
        '<div class="footer">Rendered by <code>~/.claude/scripts/render_cycle_log.py</code> — a pure '
        "reader of the JSON cycle records above; it computes every metric on this page itself and "
        "never trusts a pre-computed number from the loop that produced the data.</div>"
    )
    parts.append(render_script(systems_by_activity, fragment=fragment))
    if not fragment:
        parts.append(render_print_script())
    return parts


def render_document(
    records: list[CycleRecord],
    issues: list[LoadIssue],
    cycles_dir: Path,
    hub_link: str | None = None,
) -> str:
    """`hub_link` (wave W-EL): an optional href to a caller-supplied
    "operator hub" page. This module never hardcodes a product path (see
    the module docstring's "no repo path and no product name appears
    anywhere in this file") -- any repo that wants a "back to my hub" link
    at the top of its own copy of this page passes its own relative/
    absolute href via `--hub-link`; the renderer never assumes a specific
    hub location or even that one exists. `None` (the default, no flag
    passed) renders byte-identical to the pre-W-EL output for this region."""
    title = "Self-Correcting Loop — Cycle Log"
    parts = [render_head(title)]
    hub_link_html = ""
    if hub_link:
        hub_link_html = (
            f'<div class="hub-link-row"><a class="hub-link" href="{esc(hub_link)}">'
            "← Operator Hub</a></div>"
        )
    parts.append(hub_link_html)
    parts.extend(_render_main_parts(records, issues, cycles_dir, fragment=False))
    parts.append("</div></body></html>")
    return "\n".join(p for p in parts if p)


def render_fragment(cycles_dir: Path) -> str:
    """The ENTIRE cycle-log page content as an embeddable HTML fragment --
    the render_document twin for hosts that inline this page instead of
    linking out to it (operator directive 2026-09-07: "i want the entire
    other tracker in this page ... bring everything in"). Mirrors
    render_agent_telemetry.py's render_html(body_only=True), which is
    already embedded in the same Operator Hub tab this API targets.

    Loads the records itself (same load path as main()) and returns
    everything the standalone page shows -- executive summary, provenance,
    malformed-files panel, filter controls, legend, every per-system
    details section (findings/dispatches/runs/reviews/changes/decisions/
    issues-filed/evidence/corrections/verdicts/stages tables, trend cards,
    sparklines), and the footer -- wrapped in one self-balanced
    `<div class="cycle-log">` container. Excluded, deliberately: the
    doctype/<html>/<head>/<style> wrapper (the host injects `scoped_css()`
    itself, once), the hub-link row (the fragment IS in the hub), and
    render_print_controls()/render_print_script() (the host's own print
    machinery covers the page; a second beforeprint/afterprint pair could
    double-fire against the guard that machinery was proven under). The
    title is demoted to an <h3> so the host page keeps its single <h1>.

    Never raises -- an empty/absent cycles_dir renders the honest
    empty-state fragment, and an unanticipated exception degrades to
    render_error_fragment() exactly the way main() degrades to
    render_error_page(): the host's build must never die on telemetry
    problems."""
    try:
        records, issues = load_cycle_records(cycles_dir)
        parts = [f'<div class="{FRAGMENT_CONTAINER_CLASS}">']
        parts.extend(_render_main_parts(records, issues, cycles_dir, fragment=True))
        parts.append("</div>")
        joined = "\n".join(p for p in parts if p)
        # TRAILING-WHITESPACE BACKSTOP (2026-09-07): some render helpers emit
        # lines with trailing spaces. Harmless on the standalone page, but an
        # embedding host whose repo runs a trim-trailing-whitespace pre-commit
        # hook gets its committed artifact auto-trimmed and therefore
        # PERMANENTLY mismatched with every fresh render -- the exact defect
        # class render_agent_telemetry.render_html() already guards against
        # with this same per-line rstrip. Fragment mode only; the standalone
        # page path stays byte-identical to its pre-fragment baselines.
        return "\n".join(line.rstrip() for line in joined.splitlines())
    except Exception as exc:  # noqa: BLE001 - intentional last-resort safety net, mirrors main()
        return render_error_fragment(cycles_dir, exc)


def render_error_fragment(cycles_dir: Path, exc: BaseException) -> str:
    """render_error_page's fragment twin (see that function's docstring for
    the safety-net contract): still no document wrapper, still no <h1>
    (the host page keeps its own), palette drawn from the scoped custom
    properties with hard fallbacks so it stays legible even if the host
    never injected scoped_css(). Never raises itself."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"""<div class="{FRAGMENT_CONTAINER_CLASS}">
<h3 style="color:var(--bad,#b93a3a)">Cycle log failed to render</h3>
<p>Reading <code>{esc(str(cycles_dir))}</code> raised an exception this renderer's own
per-field guards did not anticipate. This fragment is the renderer's documented crash-safety
net (the host page must never die on telemetry problems) — report the trace below so the
specific malformed field can be added to the renderer's guards.</p>
<pre style="background:var(--neutral-soft,#f3f4f6); padding:12px; overflow-wrap:break-word; white-space:pre-wrap">{esc(tb)}</pre>
</div>
"""


def render_error_page(cycles_dir: Path, exc: BaseException) -> str:
    """BLOCKER 4's last-resort safety net: an exception that escapes every
    per-field guard elsewhere in this file (a malformed value this renderer's
    authors didn't anticipate) must still produce a WRITTEN, viewable file --
    never a bare crash with nothing on disk, which is what the module's own
    "Exits 0 always ... a rendering problem is shown ON the page, never a
    crash" docstring promise actually requires. Never raises itself."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Cycle Log — render error</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 16px; color:#111;">
<h1 style="color:#b91c1c">Cycle log failed to render</h1>
<p>Reading <code>{esc(str(cycles_dir))}</code> raised an exception this renderer's own
per-field guards did not anticipate. This page is the renderer's documented crash-safety
net (it must always write something, never crash with nothing on disk) — report the trace
below so the specific malformed field can be added to the renderer's guards.</p>
<pre style="background:#f3f4f6; padding:12px; overflow-wrap:break-word; white-space:pre-wrap">{esc(tb)}</pre>
</body></html>
"""


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--cycles-dir",
        type=Path,
        default=DEFAULT_CYCLES_DIR,
        help=f"Directory to scan for <system>/<cycle_id>.json records (default: {DEFAULT_CYCLES_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the rendered HTML (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--system",
        action="append",
        default=None,
        help="Limit rendering to this system slug (repeatable). Default: all systems found.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the rendered file with the OS 'open' command after writing it.",
    )
    parser.add_argument(
        "--hub-link",
        default=None,
        help=(
            "Optional href to render as a prominent '← Operator Hub' link at the top of "
            "the page. Caller-supplied only -- this renderer never hardcodes a product path. "
            "Omit for byte-identical output to a build with no hub link."
        ),
    )
    args = parser.parse_args(argv)

    # NIT 6 (cold review round 1): --hub-link is operator-typed today, but
    # a `javascript:` href is cheap insurance to refuse outright -- this is
    # a CLI-argument-validation failure, not a data-rendering problem, so
    # it uses argparse's own error path (parser.error(), exit 2) rather
    # than this module's "exits 0 always" render-pipeline contract, which
    # is about surviving malformed CYCLE DATA, never about validating the
    # operator's own command-line input.
    if args.hub_link and args.hub_link.strip().lower().startswith("javascript:"):
        parser.error("--hub-link refuses a javascript: scheme href")

    cycles_dir: Path = args.cycles_dir
    out_path: Path = args.out

    # BLOCKER 4: wrap the whole load+analyze+render pipeline so ANY
    # unanticipated exception -- not just the specific fmt_pct/fmt_usd cases
    # already guarded above -- still results in a written page, never a bare
    # crash. This is the module's own documented "Exits 0 always" contract.
    try:
        records, issues = load_cycle_records(cycles_dir)
        records = filter_by_system(records, args.system)
        issues = filter_issues_by_system(issues, args.system)
        html_doc = render_document(records, issues, cycles_dir, hub_link=args.hub_link)
    except Exception as exc:  # noqa: BLE001 - intentional last-resort safety net
        records, issues = [], []
        html_doc = render_error_page(cycles_dir, exc)

    # BLOCKER 9 (round 6): this module's own "exits 0 always" contract
    # (BLOCKER 4 above, and this file's docstring) covers the LOAD/render
    # pipeline, but the write itself sat OUTSIDE that try block -- an
    # unwritable output path (permissions, a missing parent the caller
    # can't create, a full disk) raised an uncaught PermissionError/OSError
    # here and exited non-zero, breaking the same promise for the one step
    # that happens after render succeeds. Wrap the write, report the
    # failure to stderr, and still return 0.
    # Round 12, BLOCKER 1 (defense-in-depth): the root cause -- a lone
    # surrogate slipping into the written HTML at all -- is fixed at
    # `esc()`/`_utf8_safe()` above, so `html_doc` itself should never
    # actually trigger this anymore. This except clause is widened anyway
    # (matching round 4/6's decode-side pattern) so any OTHER path that
    # reaches this write with unencodable text still degrades to a
    # reported failure instead of an uncaught crash + truncated file.
    wrote_output = False
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_doc, encoding="utf-8")
        wrote_output = True
    except (OSError, UnicodeEncodeError) as exc:
        print(f"could not write {out_path}: {exc}", file=sys.stderr)

    systems = sorted({r.system for r in records})
    if wrote_output:
        print(f"wrote {out_path}")
    print(f"  cycles dir : {cycles_dir}")
    print(f"  systems    : {_utf8_safe(', '.join(systems)) if systems else '(none found)'}")
    print(f"  records    : {len(records)} loaded, {len(issues)} excluded (malformed)")
    if wrote_output:
        print(f"  open with  : open {out_path}")

    if args.open and wrote_output:
        try:
            subprocess.run(["open", str(out_path)], check=False)
        except OSError as exc:
            print(f"  (could not auto-open: {exc})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
