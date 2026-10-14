"""cycle_telemetry — repo-agnostic telemetry for self-correcting agent-loop cycles.

A "cycle record" is one run of any self-correcting agent loop, in ANY repo (a
"loop" here means: finders raise findings, a consolidator dedups/rules on them,
a verifier checks them, fixes land or don't). This module is the ONLY place
that knows the record's shape, validates it, stores/reads it, and computes the
pure derived metrics over it. It never contains a repo name, a product path, or
any loop-specific logic — "system" and "repo" are opaque data supplied by the
caller, never branched on here.

Canonical on-disk location for a real cycle record:
    ~/.claude/telemetry/cycles/<system>/<cycle_id>.json

Schema (schema_version 1 or 2 — see "SCHEMA VERSIONING" below) — see
~/.claude/telemetry/schema.json for the formal (JSON-Schema-shaped) contract
and ~/.claude/telemetry/README.md for what each field and derived metric
MEANS. The v1 shape (still fully valid on its own):

{
  "schema_version": 1,
  "system": "<slug>",             # which loop; data, never hardcoded here
  "repo": "<repo name or null>",  # data, never a path
  "cycle_id": "<slug>",
  "started_at": "<ISO8601Z>", "ended_at": "<ISO8601Z or null>",
  "dispatches": [ {agent_type, label, model, tokens_total, cost_usd,
                    tool_calls, duration_ms, batch_size, batch_position} ],
  "calibration": {plant_id, planted_in, slot, caught_by: [], missed_by: []},
  "findings": [ {finding_id, raised_by: [], claim_symptom, claim_cause,
                  consolidator_decision, verifier_verdict,
                  verifier_cause_upheld, already_tracked_as, fights_ruling,
                  fix_status} ],
  "cost": {source, total_tokens, total_usd, ...optional resolver metadata},
  "notes": []
}

SCHEMA VERSIONING — v2 is a PURELY ADDITIVE extension of v1. Every v1 record
(schema_version 1, none of the keys below present) still validates and still
renders, unchanged, forever — see test_v1_record_still_validates_under_v2 and
the two "still validates"/"still renders" checks the spawning task required.
v2 adds ten OPTIONAL top-level arrays (absent entirely on a v1 record) plus a
handful of optional per-item keys on dispatches/findings. The original nine
were built to close eleven measured completeness gaps
(~/.claude/plans/cycle_log_schema_v2_gaps.md) in what a cycle record could
express — "must know about every run ... literally everything" was the
operator's own standard, and v1 captured roughly 40% of it; the tenth,
calibration_runs, was added later (2026-08-29, GH #4648) under this same
additive contract (see its own entry below):

  "runs": [ {run_id, purpose, agent_types: [], model, started_at, ended_at,
              dispatch_count, outcome} ],
    # EVERY agent run this cycle made, not just the finder pass that produces
    # dispatches[] — a run that found nothing still happened and still cost
    # money. agent_types/purpose/outcome are always non-empty strings even
    # when the only honest content is "occurred; no further detail captured".

  "reviews": [ {review_id, reviewer, model, target, related_findings: [],
                 round, blocker_count, findings: [ {description, severity,
                 fixed} ], upheld_decisions: [], overturned_decisions: [],
                 outcome, reviewed_at} ],
    # Code/plan review boundaries (the operator asked for this by name — v1
    # had NO review record at all). "findings" are per-blocker items; "fixed"
    # is nullable (null = not yet re-confirmed, never assumed true).

  "changes": [ {change_id, finding_id, commit_sha, files: [], lines_added,
                 lines_removed, red_before_green, tests_added: [],
                 golden_net_drift, reverted} ],
    # What actually changed as a result of a finding — commit_sha accepts
    # the literal string "uncommitted"; red_before_green is the falsifiability
    # evidence text (never just a bare "fixed" status string, v1's whole gap).

  "decisions": [ {decision_id, decided_by, what, reasoning, supersedes: [],
                   action, decided_at} ],
    # Who decided what and WHY, verbatim — decided_by is a free string so an
    # OPERATOR ruling is first-class data here, never a note buried in prose.

  "issues_filed": [ {issue_id, title, related_findings: [], filed_by,
                       filed_at, status} ],
    # GitHub (or any tracker) issues filed as a result of this cycle, both
    # directions linkable via findings[].issue_refs (see below).

  "evidence": [ {evidence_id, finding_id, file, line, quote, repro_command} ],
    # At least one of file/quote/repro_command required per item — the
    # file:line citations and repro commands raisers/verifiers actually used,
    # discarded entirely in v1.

  "corrections": [ {correction_id, what_was_claimed, what_was_wrong,
                      how_found, invalidated} ],
    # The loop's own error record: a retraction of a prior claim. Arguably the
    # most valuable series in the whole log; v1 only had this as free-text notes.

  "verdicts": [ {dispatch_label, scenario, verdict: "CONCUR"|"DISSENT",
                   confidence, problem_count} ],
    # Raw per-scenario verdicts BEFORE consolidation collapses them into
    # findings[] — an empty list here is not "nothing happened", it can also
    # mean the raw rows were never persisted; say so in notes[] when that's why.

  "stages": [ {stage_id, name, status: "ran"|"skipped"|"blocked",
                blocked_reason} ],
    # Which pipeline stages ran/were skipped/were blocked this cycle, and why
    # (blocked_reason is REQUIRED, non-empty, whenever status is "blocked").

  "calibration_runs": [ {plant_id, trade, slot, batch_size, caught_by: [],
                           missed_by: [], false_alarm_finding_ids: []} ],
    # ADDED 2026-08-29 (W4s, GH #4648) as a TENTH optional top-level array,
    # under this same additive v2 contract -- not part of the original
    # nine-array/eleven-gap batch above. This is the GRID form of the
    # legacy single `calibration` block: a grader-calibration grid
    # dispatches many plant AND clean-control rows in one run, which a
    # single top-level `calibration` object structurally cannot express
    # (one plant per record; unknown keys rejected; caught_by/missed_by
    # forced empty whenever plant_id is null -- see _validate_calibration).
    # A row with plant_id null is a CONTROL: caught_by/missed_by must stay
    # empty (nothing was seeded to catch or miss) but
    # false_alarm_finding_ids MAY be non-empty -- a blocker/DISSENT finding
    # raised against a clean control package IS the false-alarm signal
    # this array exists to carry. A row with plant_id set is a PLANT: the
    # mirror-image rule applies -- false_alarm_finding_ids must stay empty
    # (a finding against a genuinely-seeded plant is a catch or a miss,
    # never a false alarm). The legacy `calibration` object, its
    # validator, and plant_catch_by_slot() are all UNCHANGED by this --
    # calibration_runs is a sibling array, never a replacement.

  "undispatched_verdict_rows": {"count": <int>, "by_judge": {"<judge>": <int>}},
    # ADDED 2026-09-07 (round-25 structural-conflict fix, ExampleApp).
    # An OBJECT (like `calibration`/`cost`, not an array like the ten above),
    # OPTIONAL, mirroring `dispatches[].scenarios`'s own additive precedent
    # (AA-0106): honest visibility for a verdict row that carries NO
    # dispatch identity and therefore was excluded from `dispatches[]`
    # entirely, rather than forcing `dispatches[]` to either fabricate an
    # identity for it or admit an identity-less entry that would poison
    # resolve_cost()'s uniform-coverage requirement for every OTHER, real
    # dispatch in the same cycle. The canonical source: a loop's own GC
    # consolidation pass judges many scenarios within one already-open
    # dispatch turn, never as its own separate Task call -- it has no
    # `tool_use_id`/`agent_id`/`session` of its own to report, and
    # fabricating one is forbidden (see GH #5051: a fabricated/misattributed
    # GC identity is a RECORDING DEFECT this field is not a workaround for).
    # `dispatches[]` now holds ONLY rows that genuinely carry identity --
    # real dispatches, full stop -- so resolve_cost()'s identity-uniformity
    # rule is never asked to consider a row that never had a dispatch of
    # its own; `undispatched_verdict_rows` is where the honest count of
    # everything left out goes, so nothing about a cycle's true verdict
    # coverage is hidden. `count` is the total number of excluded rows;
    # `by_judge` breaks that count down per judge -- e.g. a TRADE
    # (non-GC) row landing here means that judge's dispatch identity was
    # never recorded (a recording miss, not a design choice) and is
    # visible here rather than silently absent from both dispatches[] and
    # this accounting. Every verdict a row here represents still appears,
    # unchanged, in verdicts[]/findings[] -- this field only affects how
    # the SAME row is (or is not) counted as a real dispatch.

Plus, additive per-item extensions to the v1 shapes:
  * dispatches[].tokens_reported / .tokens_source — the harness's own
    (possibly untrustworthy) token figure, RECORDED rather than deleted, with
    its provenance labelled. v1's finder pass nulled tokens_total on all 27
    dispatches to avoid laundering a ~26x-low harness figure into a trusted
    field — the right fix is to keep the untrusted number AND label it, never
    to delete data. tokens_source is required (non-null) whenever
    tokens_reported is set.
  * findings[].found_at_stage — accepts "consolidation" (and "finder" /
    "verifier" / "review") so a finding that a consolidator surfaced but that
    never reached a verifier is representable at all — v1 could only model
    findings that went through the verifier.
  * findings[].issue_refs — issue id(s) filed as a direct result of this
    finding (the finding-side half of the issues_filed[] link).
  * dispatches[].tool_use_id / .agent_id / .session — the spend ledger's own
    identity fields, optionally echoed onto a dispatch so resolve_cost() can
    match ledger rows by IDENTITY instead of only inferred window+type+count
    signals. All three optional and independent; see resolve_cost()'s own
    docstring for the matching precedence and the exact incident (a
    same-agent_type row from a concurrent, unrelated session, "right answer
    wrong evidence, pure luck") this closes.
  * dispatches[].scenarios — an OPTIONAL list of the individual units of work
    (e.g. scenario ids) ONE REAL DISPATCH covered, for a caller whose
    dispatch batches many scenarios into a single sub-agent call (AA-0106,
    2026-09-07). The contract this field enforces: ONE dispatches[] entry
    per REAL Task dispatch, always — never one entry per scenario. A
    producer that instead multiplied a dispatch into N synthetic entries
    (one per scenario, all echoing the same tool_use_id) is exactly the
    defect AA-0106 found: resolve_cost()'s step-4a 1:1 identity check
    correctly refuses such a record, because a declared identity count of N
    can never correspond 1:1 to the single real ledger row that tool_use_id
    actually has. Present or absent independently of every other optional
    dispatch field.

Design rules (see the spawning task / README for the full rationale):
  * validate on write — a malformed record fails LOUDLY, never persists silently.
  * unknown keys anywhere in the shape are a validation error, not a warning —
    this now means the CLOSED set of v1 keys plus the ten v2 arrays above
    (the original nine plus calibration_runs) and their two per-item
    extensions; anything else is still rejected.
  * cost MUST come from the spend ledger when it claims source "spend_ledger" —
    resolve_cost() REFUSES to attribute ledger rows to a cycle whose window,
    agent-type set, per-type row COUNT, or dispatch IDENTITY does not
    correspond exactly. Identity (tool_use_id / agent_id / session) is
    REQUIRED, not optional — round 3 deleted the "no identity declared, but
    the candidates all happen to share one session" fallback outright, with
    no session-count exception: resolve_cost() refuses unconditionally
    whenever no identity field is uniformly declared across every dispatch,
    whether the candidate rows span one session or many, because a single
    foreign session is mathematically indistinguishable from a single own
    session under window+type+count alone. A refusal is reported as
    cost.source == "unavailable" with a human-readable "reason" — never a
    guess.
  * pricing is DATA (telemetry/pricing.json), never a number in this file.
  * every new array is OPTIONAL and every new sub-field is nullable-or-optional
    for exactly one reason: a v1 record must keep validating forever, and a
    caller that only has PARTIAL v2 data (e.g. it knows the reviews but not the
    verdicts) must still be able to write a valid record — "too much data is
    better than not enough," never "all v2 fields or none."

Structure: pure validation/metric/pricing helpers (trivially unit-testable),
thin I/O wrappers around them, and a small argv-driven CLI at the bottom.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Paths — computed from HOME, never a product-repo path. Every path is also
# accepted as an explicit override argument on the functions that use it, so
# callers (and tests) never need to monkeypatch these module constants.
# ---------------------------------------------------------------------------

HOME = os.path.expanduser("~")
CLAUDE_DIR = os.path.join(HOME, ".claude")
TELEMETRY_DIR = os.path.join(CLAUDE_DIR, "telemetry")
CYCLES_DIR = os.path.join(TELEMETRY_DIR, "cycles")
FIXTURES_DIR = os.path.join(TELEMETRY_DIR, "fixtures")
PRICING_FILE = os.path.join(TELEMETRY_DIR, "pricing.json")
SPEND_LEDGER = os.path.join(CLAUDE_DIR, ".agent_budget", "spend.jsonl")

SCHEMA_VERSION = 2  # the latest/preferred version a new record should declare
# Both versions are fully valid forever — v2 is purely additive over v1 (see
# the module docstring's "SCHEMA VERSIONING" section). A record's declared
# version is descriptive metadata, not a gate on which optional v2 keys it may
# carry: nothing stops a schema_version:1 record from also carrying v2 arrays,
# since every one of them is optional regardless of declared version.
ALLOWED_SCHEMA_VERSIONS = {1, 2}

# A slug: must start with a letter/digit, then letters/digits/underscore/
# hyphen/dot. No '/' anywhere, so a single slug can never escape its parent
# directory when used to build a filesystem path (no need for a separate
# ".." check — a path component without '/' cannot traverse directories).
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

CONSOLIDATOR_DECISIONS = {"ACCEPT", "REJECT", "CONTESTED", "GC_DEFAULT", "HINT_WORTHY"}
VERIFIER_VERDICTS = {
    "CONFIRMED",
    "PARTIALLY_CONFIRMED",
    "REFUTED",
    "ALREADY_TRACKED_ELSEWHERE",
    "UNVERIFIABLE",
}
# "unavailable" extends the contract's documented "spend_ledger|reported" pair
# for the honest-refusal path (see resolve_cost) — a cost block MUST be able to
# say "I don't know" rather than guess. See README "cost.source values".
COST_SOURCES = {"spend_ledger", "reported", "unavailable"}

# v2 enums.
FOUND_AT_STAGES = {"finder", "consolidation", "verifier", "review"}
DISPATCH_TOKENS_SOURCES = {"harness_reported", "spend_ledger", "estimated", "unavailable"}
REVIEW_SEVERITIES = {"blocker", "major", "minor", "nit"}
REVIEW_OUTCOMES = {"clean", "blockers"}
STAGE_STATUSES = {"ran", "skipped", "blocked"}
VERDICT_VALUES = {"CONCUR", "DISSENT"}

REQUIRED_TOP_KEYS = {
    "schema_version",
    "system",
    "repo",
    "cycle_id",
    "started_at",
    "ended_at",
    "dispatches",
    "calibration",
    "findings",
    "cost",
    "notes",
}
# v2: ten additional top-level arrays (the original nine plus calibration_runs,
# added 2026-08-29/GH #4648), every one OPTIONAL (a v1 record has none of them
# and stays valid). See the module docstring for what each holds.
# undispatched_verdict_rows (added 2026-09-07, round-25 structural-conflict
# fix) is an eleventh optional top-level key, but an OBJECT like `calibration`/
# `cost`, not an array -- see the module docstring's own entry for it.
OPTIONAL_TOP_KEYS = {
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
    "undispatched_verdict_rows",
}
REQUIRED_DISPATCH_KEYS = {
    "agent_type",
    "label",
    "model",
    "tokens_total",
    "cost_usd",
    "tool_calls",
    "duration_ms",
    "batch_size",
    "batch_position",
}
# v2: the untrusted harness-reported token figure, kept and labelled rather
# than deleted (see the module docstring). Both optional; tokens_source is
# required (non-null) whenever tokens_reported is set.
# tool_use_id / agent_id / session are the LEDGER's own identity fields,
# optionally echoed onto a dispatch so resolve_cost() can match candidate
# ledger rows by IDENTITY instead of only window+type+count (see
# resolve_cost's docstring -- this closes the "right dollar figure, wrong
# run's rows, pure luck" correspondence gap). All three are optional and
# independent of one another.
# item_key (renamed from wave_item, THE ISSUE WHEEL rollout commit 8c,
# 2026-09-09 -- originally added for the retired Standing Delivery Wheel,
# "sdw" system; the field itself is general-purpose, not SDW-specific, so
# it survives that system's retirement under a name that says what it does
# rather than who first needed it. See telemetry/README.md's "Known system
# values in use" section): an OPTIONAL free-string join key back to a work
# item (conventionally "<issue>" -- THE ISSUE WHEEL's own ITEM TOKEN,
# schedules/prompts/issue_wheel.txt's LANE RECIPE, is issue-number-only; the
# "row-<index>" fallback form for an item with no real issue number was the
# retired finishing loop's own convention, not carried forward). This is
# what makes a cycle's per-item cost measurable rather than only per-cycle:
# AA-0093 measured 75% of spend rows as
# unjoinable to any real unit of work; tool_use_id/agent_id/session already
# let resolve_cost() find the RIGHT dispatch, but nothing before this field
# let a caller ask "how much did item #4901 cost" without re-deriving it
# from dispatch ORDER (fragile -- batch_position already exists for
# within-batch ordering and is not a stable cross-cycle item key).
# Independent of every other optional dispatch field; never required,
# exactly like the other four.
#
# scenarios (AA-0106, added 2026-09-07): an OPTIONAL list of the individual
# units of work (e.g. scenario ids) ONE REAL DISPATCH actually covered, for a
# caller whose dispatch batches many scenarios into a single sub-agent call
# (the GC/trade review loop's own shape: one judge, one Task call, many
# scenarios judged in that one turn). This field exists to close the exact
# defect AA-0106 found: a producer that instead emitted ONE dispatches[]
# entry PER SCENARIO -- multiplying 11 real dispatches into 206 synthetic
# ones, every synthetic entry echoing the SAME real tool_use_id -- which
# resolve_cost()'s step-4a 1:1 identity check (correctly) refused outright,
# because a declared identity count of e.g. 36 could never correspond 1:1 to
# the single real ledger row that tool_use_id actually has. The correct
# contract is ONE dispatches[] entry per REAL dispatch, full stop; the
# per-scenario detail belongs in THIS field, never multiplied into the
# array itself. Independent of every other optional dispatch field; never
# required. An empty list is a data defect, same "declared-but-empty is not
# absent" rule item_key/tool_use_id/agent_id/session already use -- omit
# the key entirely for a dispatch this doesn't apply to, never scenarios: [].
OPTIONAL_DISPATCH_KEYS = {
    "tokens_reported",
    "tokens_source",
    "tool_use_id",
    "agent_id",
    "session",
    "item_key",
    "scenarios",
}
REQUIRED_CALIBRATION_KEYS = {"plant_id", "planted_in", "slot", "caught_by", "missed_by"}
# undispatched_verdict_rows (2026-09-07): both keys required whenever the
# object itself is present -- there is no honest partial shape (a `count`
# with no breakdown, or a breakdown with no total, is strictly less useful
# than either being absent entirely; see the module docstring's own entry).
REQUIRED_UNDISPATCHED_VERDICT_ROWS_KEYS = {"count", "by_judge"}
REQUIRED_FINDING_KEYS = {
    "finding_id",
    "raised_by",
    "claim_symptom",
    "claim_cause",
    "consolidator_decision",
    "verifier_verdict",
    "verifier_cause_upheld",
    "already_tracked_as",
    "fights_ruling",
    "fix_status",
}
# v2: origin-stage tag (accepts a consolidation-only origin, v1's gap 5) and
# issue linkage. Both optional.
OPTIONAL_FINDING_KEYS = {"found_at_stage", "issue_refs"}
REQUIRED_COST_KEYS = {"source", "total_tokens", "total_usd"}
# Optional metadata a resolver (or a human) may attach to a cost block. Kept
# to a fixed whitelist so a typo in an extra key still fails loudly.
OPTIONAL_COST_KEYS = {"reason", "window", "matched_rows", "unpriced_models"}

# v2 sub-object shapes (all top-level arrays holding these are optional).
REQUIRED_RUN_KEYS = {
    "run_id",
    "purpose",
    "agent_types",
    "model",
    "started_at",
    "ended_at",
    "dispatch_count",
    "outcome",
}
REQUIRED_REVIEW_KEYS = {
    "review_id",
    "reviewer",
    "model",
    "target",
    "related_findings",
    "round",
    "blocker_count",
    "findings",
    "upheld_decisions",
    "overturned_decisions",
    "outcome",
    "reviewed_at",
}
REQUIRED_REVIEW_FINDING_KEYS = {"description", "severity", "fixed"}
REQUIRED_CHANGE_KEYS = {
    "change_id",
    "finding_id",
    "commit_sha",
    "files",
    "lines_added",
    "lines_removed",
    "red_before_green",
    "tests_added",
    "golden_net_drift",
    "reverted",
}
REQUIRED_DECISION_KEYS = {
    "decision_id",
    "decided_by",
    "what",
    "reasoning",
    "supersedes",
    "action",
    "decided_at",
}
REQUIRED_ISSUE_FILED_KEYS = {
    "issue_id",
    "title",
    "related_findings",
    "filed_by",
    "filed_at",
    "status",
}
REQUIRED_EVIDENCE_KEYS = {"evidence_id", "finding_id", "file", "line", "quote", "repro_command"}
REQUIRED_CORRECTION_KEYS = {
    "correction_id",
    "what_was_claimed",
    "what_was_wrong",
    "how_found",
    "invalidated",
}
REQUIRED_VERDICT_KEYS = {"dispatch_label", "scenario", "verdict", "confidence", "problem_count"}
REQUIRED_STAGE_KEYS = {"stage_id", "name", "status", "blocked_reason"}
# calibration_runs[] -- the grid form of the legacy single `calibration`
# block (see the module docstring's "calibration_runs" entry). Every row
# carries all seven keys; plant_id is the only nullable one (null = a
# clean control row).
REQUIRED_CALIBRATION_RUN_KEYS = {
    "plant_id",
    "trade",
    "slot",
    "batch_size",
    "caught_by",
    "missed_by",
    "false_alarm_finding_ids",
}

DEFAULT_LEDGER_TOLERANCE_SEC = 600.0  # +/- 10 min clock-skew allowance
# A tolerance window directly widens the chance of matching an unrelated,
# concurrent run's ledger rows (see resolve_cost's "wrong session" incident
# this module exists to prevent) -- bounded to a sane positive range so a
# caller (CLI or programmatic) cannot pass a negative value (which produces a
# nonsensical inverted window) or an unbounded one (which silently trades
# correspondence precision for convenience).
MIN_LEDGER_TOLERANCE_SEC = 0.0
MAX_LEDGER_TOLERANCE_SEC = 3600.0  # 1 hour -- generous clock-skew slack, not a blank check


class ValidationError(ValueError):
    """Raised when a cycle record fails validate_cycle(). Carries .errors."""

    def __init__(self, errors: list[str]) -> None:
        self.errors: list[str] = list(errors)
        message = "; ".join(self.errors) if self.errors else "invalid cycle record"
        super().__init__(message)


class LedgerCorrespondenceError(ValueError):
    """Reserved for callers who want a hard failure instead of resolve_cost's
    honest {"source": "unavailable", ...} return. resolve_cost() itself never
    raises this — it always returns a dict — but a caller that wants
    "raise instead of returning an unavailable cost" can do:
        result = resolve_cost(cycle)
        if result["source"] == "unavailable":
            raise LedgerCorrespondenceError(result["reason"])
    """


# ---------------------------------------------------------------------------
# Small type helpers (bool is a subclass of int in Python — exclude it
# explicitly everywhere a "number" or "integer" field is checked).
# ---------------------------------------------------------------------------


def is_finite_number(x: Any) -> bool:
    """The ONE canonical finiteness check for a numeric field in this
    telemetry system — True for an int or a FINITE float; False for bool,
    and False for NaN/Infinity/-Infinity. Every one of this module's "never
    fabricate a confident cost figure" call sites (usd_per_confirmed_defect,
    price_tokens, _validate_cost, the ledger token accumulator) reads this
    single function, so treating a non-finite float as "not a number" here
    is what keeps a NaN/Infinity value out of the ENTIRE cost pipeline —
    Python's json module accepts bare NaN/Infinity tokens by default, so an
    otherwise-well-formed JSON value can carry one without ever raising a
    parse error (BLOCKER 7).

    Exposed WITHOUT a leading underscore (round 8, BLOCKER 1) specifically
    so render_cycle_log.py can import and call THIS implementation directly
    instead of re-implementing it — round 6's finiteness fix landed only in
    this module's then-private, then-only copy of the check, leaving
    render_cycle_log.py's separate `_is_number` and its `rollup_cost`'s two
    inline `isinstance(x, (int, float))` checks unguarded, so a
    NaN/Infinity `total_usd` rendered as a confident "$inf ... ground
    truth" figure on the operator page. A single shared implementation is
    what makes that class of bug impossible to reintroduce on just one side
    a second time."""
    if isinstance(x, bool):
        return False
    if isinstance(x, int):
        # Round 14, BLOCKER 1: an int with enough digits to exceed a C
        # double's finite range (e.g. 10**309 -- already over at 310
        # digits, well under Python's separately-guarded 4300-digit
        # int-to-str parse limit) used to return True here unconditionally.
        # It is schema-valid and round-trips through write_cycle()'s own
        # supported API, so every downstream `float(x)` conversion this
        # function's docstring promises to protect (fmt_usd, fmt_tokens,
        # rollup_cost, price_tokens, aggregate_metrics, price_tokens...)
        # then raised `OverflowError` -- an `ArithmeticError`, not a
        # `ValueError`/`OSError`, so it escaped every guard in this module
        # AND render_cycle_log.py, including main()'s own catch tuple,
        # blanking the ENTIRE operator report over one malformed field.
        # Refuse it exactly like NaN/Infinity: present as a real number,
        # just not one this system can safely carry through a float
        # conversion.
        try:
            return math.isfinite(float(x))
        except OverflowError:
            return False
    if isinstance(x, float):
        return math.isfinite(x)
    return False


# Internal alias: every existing call site in this module already spells it
# `_is_number` (10+ sites) — keep that name working rather than touching
# every call site for a pure rename with no behavior change.
_is_number = is_finite_number


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _in_enum(value: Any, allowed: set) -> bool:
    """The ONE canonical "is this value one of a fixed set of allowed
    strings/ints" check for an enum-like field, e.g. `cost.source` against
    COST_SOURCES. `value not in allowed_set` computes `hash(value)` before
    it can ever compare -- a dict or list value (a realistic malformed/
    hand-edited field) raises `TypeError: unhashable type`, not a clean
    validation error, breaking validate_cycle()'s own documented "never
    raises" contract for any caller wrapping it in `except ValidationError`.

    Round 8, BLOCKER 2: this generalizes the isinstance-guard pattern
    normalize_record() already used correctly for its own schema_version
    check (`isinstance(v, (int, str)) and v in allowed`) into ONE shared
    helper, then applies it at EVERY enum-membership test in
    validate_cycle()'s helper functions (10 sites, audited exhaustively via
    a full grep of this function tree for `not in <set>`) -- round 6 fixed
    this exact hazard shape only for normalize_record()'s single
    schema_version check, never generalized it, so the identical crash sat
    live at nine sibling call sites plus validate_cycle()'s OWN
    schema_version check (a separate implementation from
    normalize_record()'s, despite checking the same field name). Spelled
    exactly `isinstance(value, (str, int)) and value in allowed` -- the
    same formula normalize_record() already uses -- rather than also
    excluding bool (bool is a str/int-adjacent edge case none of the 10
    enum fields below has ever needed to special-case; keeping this helper
    identical to the one proven-correct pattern avoids introducing a new,
    untested distinction).

    Round 10, #11: `bool` IS a subclass of `int` in Python, so
    `isinstance(True, (str, int))` is True and `True in {1, 2}` is also
    True (since `hash(True) == hash(1)` and `True == 1`) -- `_in_enum(True,
    {1, 2})` used to return True, meaning a JSON boolean `true` in a
    field's raw value would incorrectly validate as matching the int enum
    member `1` (e.g. `"schema_version": true` matching version 1).
    Currently harmless in practice (schema_version is the only int-valued
    enum this helper checks today, and it happens to also independently
    reject non-int values elsewhere) -- closed now anyway, since this is
    the single shared helper every enum check in this module goes through,
    and a JSON boolean should never silently stand in for an int."""
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int)) and value in allowed


def _safe_list(value: Any) -> list[Any]:
    """Coerce a value that should be a list into one. `3.5 or []` is TRUE
    (a nonzero float is truthy) and skips the `or []` fallback entirely, so
    a bare `X.get(field) or []` lets a malformed scalar straight through to
    whatever iterates it next -- this is the single root cause behind a
    directed fuzz finding 58 whole-report blanks across this module and
    render_cycle_log.py's sibling copy of this same helper (BLOCKER 2).
    Treat anything that isn't already a list as absent, full stop."""
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    """Same rationale as _safe_list(), for a field that should be a dict."""
    return value if isinstance(value, dict) else {}


def _safe_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    """Like _safe_list(), but also drops any list ITEM that isn't itself a
    dict -- for fields whose entries are always read via `.get()` downstream
    (findings, dispatches). A malformed item (a bare string/number where an
    object was expected) is silently excluded rather than crashing the
    first `.get()` call that touches it."""
    return [x for x in _safe_list(value) if isinstance(x, dict)]


def _parse_iso8601z(value: Any) -> datetime | None:
    """Parse an ISO8601 'Z' timestamp into an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _slug_errors(value: Any, field: str) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{field} must be a non-empty string"]
    if not SLUG_RE.match(value):
        return [
            f"{field} must match {SLUG_RE.pattern!r} (letters/digits/._- only, "
            f"no spaces or path separators), got {value!r}"
        ]
    return []


def _require_safe_component(value: str, field: str) -> str:
    """Like _slug_errors but raises — used by path builders on raw input that
    may not have gone through validate_cycle (e.g. read_cycle(sys, cid))."""
    errs = _slug_errors(value, field)
    if errs:
        raise ValueError("; ".join(errs))
    return value


def _truthy_ruling(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    return False


# ---------------------------------------------------------------------------
# Validation — pure. validate_cycle() never raises; it returns a list of
# human-readable error strings (empty == valid). assert_valid_cycle() is the
# "fail loudly" wrapper write_cycle() uses.
# ---------------------------------------------------------------------------


def _validate_dispatch(d: Any) -> list[str]:
    if not isinstance(d, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(d.keys())
    for k in sorted(REQUIRED_DISPATCH_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_DISPATCH_KEYS - OPTIONAL_DISPATCH_KEYS):
        errs.append(f"unknown key: {k}")

    if "agent_type" in d:
        at = d.get("agent_type")
        if not isinstance(at, str) or not at.strip():
            errs.append("agent_type must be a non-empty string")
    if "label" in d and not isinstance(d.get("label"), str):
        errs.append("label must be a string")
    if "model" in d:
        model = d.get("model")
        if model is not None and not isinstance(model, str):
            errs.append("model must be a string or null")

    for field, kind in (
        ("tokens_total", "integer"),
        ("tokens_reported", "integer"),
        ("tool_calls", "integer"),
        ("batch_size", "integer"),
        ("batch_position", "integer"),
        ("cost_usd", "number"),
        ("duration_ms", "number"),
    ):
        if field not in d:
            continue
        v = d.get(field)
        if v is None:
            continue
        # Round 14, BLOCKER 1 (decision b): an "integer" field is rejected
        # not only when it isn't a real int, but also when it IS one that
        # cannot survive a finite float conversion (e.g. 10**309) -- the
        # same overflow guard `is_finite_number` now applies to a "number"
        # field, so validate_cycle() never accepts, at write time, a value
        # the read path (rollup_cost, dispatch_reported_tokens,
        # resolve_cost) can only treat as unusable anyway. `_is_int` still
        # gates the actual type (int, not bool/float/str).
        ok = (_is_int(v) and is_finite_number(v)) if kind == "integer" else _is_number(v)
        if not ok:
            # Round 16, finding 4: a real int (bool excluded) that only
            # failed because it is too large to survive a finite float
            # conversion gets its own message -- "must be a{n} {kind}"
            # is actively misleading for a value that already IS one.
            # Every other rejection reason (wrong type entirely, e.g. a
            # string or a NaN/Infinity float) keeps the original wording.
            if _is_int(v) and not is_finite_number(v):
                errs.append(
                    f"{field} must be a{'n' if kind == 'integer' else ''} {kind} "
                    "small enough to convert to a finite float"
                )
            else:
                errs.append(f"{field} must be a{'n' if kind == 'integer' else ''} {kind} or null")
        elif v < 0:
            errs.append(f"{field} must be >= 0")

    if "tokens_source" in d:
        ts = d.get("tokens_source")
        if ts is not None and not _in_enum(ts, DISPATCH_TOKENS_SOURCES):
            errs.append(
                f"tokens_source must be one of {sorted(DISPATCH_TOKENS_SOURCES)} or null, got {ts!r}"
            )
    for field in ("tool_use_id", "agent_id", "session", "item_key"):
        if field in d:
            v = d.get(field)
            if v is not None and not isinstance(v, str):
                errs.append(f"{field} must be a string or null")
            elif isinstance(v, str) and not v:
                # BLOCKER 2 (round 3): an empty string is a DATA DEFECT, not
                # "no identity declared" -- a present-but-blank identity must
                # never silently downgrade a cycle to no-identity and discard
                # a sibling dispatch's real identity (the "second door" the
                # review found: only isinstance(v, str) was checked before).
                errs.append(
                    f"{field} must be a non-empty string when present (an empty string is a "
                    "data defect, not 'no identity declared' -- omit the key or use null instead)"
                )
    # A recorded-but-untrusted token figure with no provenance label defeats
    # the entire point of keeping it instead of nulling it out (v2 gap 9).
    if d.get("tokens_reported") is not None and not d.get("tokens_source"):
        errs.append(
            "tokens_reported is set but tokens_source is missing/null -- a token "
            "figure without a labelled provenance is exactly what this field exists to prevent"
        )

    if "scenarios" in d:
        # AA-0106: the individual units of work one real dispatch covered.
        # A list of non-empty strings, or omitted entirely -- never present
        # as an empty list (same "declared-but-empty is a data defect" rule
        # every other optional dispatch field already follows) and never a
        # non-list value.
        sc = d.get("scenarios")
        if not isinstance(sc, list):
            errs.append("scenarios must be a list of non-empty strings")
        elif not sc:
            errs.append(
                "scenarios must be a non-empty list when present (an empty list is a "
                "data defect, not 'no scenarios' -- omit the key instead)"
            )
        else:
            for i, item in enumerate(sc):
                if not isinstance(item, str) or not item:
                    errs.append(f"scenarios[{i}] must be a non-empty string")

    bs, bp = d.get("batch_size"), d.get("batch_position")
    if _is_int(bs) and _is_int(bp):
        if bs < 1:
            errs.append("batch_size must be >= 1")
        if bp < 1:
            errs.append("batch_position must be >= 1")
        if bs >= 1 and bp >= 1 and bp > bs:
            errs.append("batch_position must be <= batch_size")
    return errs


def _validate_calibration(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(c.keys())
    for k in sorted(REQUIRED_CALIBRATION_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_CALIBRATION_KEYS):
        errs.append(f"unknown key: {k}")

    plant_id = c.get("plant_id")
    if "plant_id" in c and plant_id is not None and not isinstance(plant_id, str):
        errs.append("plant_id must be a string or null")
    if "planted_in" in c:
        pi = c.get("planted_in")
        if pi is not None and not isinstance(pi, str):
            errs.append("planted_in must be a string or null")
    if "slot" in c:
        slot = c.get("slot")
        if slot is not None and (isinstance(slot, bool) or not isinstance(slot, (str, int))):
            errs.append("slot must be a string, integer, or null")

    for field in ("caught_by", "missed_by"):
        if field not in c:
            continue
        v = c.get(field)
        if not isinstance(v, list) or not all(
            isinstance(x, (str, int)) and not isinstance(x, bool) for x in v
        ):
            errs.append(f"{field} must be a list of strings/integers")

    caught_by = c.get("caught_by") if isinstance(c.get("caught_by"), list) else []
    missed_by = c.get("missed_by") if isinstance(c.get("missed_by"), list) else []
    if plant_id is None and (caught_by or missed_by):
        errs.append("caught_by/missed_by must be empty when plant_id is null")
    return errs


def _validate_undispatched_verdict_rows(u: Any) -> list[str]:
    """Validates the OPTIONAL top-level `undispatched_verdict_rows` object
    (added 2026-09-07 -- see the module docstring's own entry). `count` must
    be a non-negative integer; `by_judge` must be a mapping of non-empty
    judge-label strings to non-negative integers, and (the one cross-field
    rule this shape has) its values must SUM to exactly `count` -- a
    mismatch here means the breakdown and the total disagree, which is
    exactly the kind of silent inconsistency this honest-accounting field
    exists to prevent, not merely record."""
    if not isinstance(u, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(u.keys())
    for k in sorted(REQUIRED_UNDISPATCHED_VERDICT_ROWS_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_UNDISPATCHED_VERDICT_ROWS_KEYS):
        errs.append(f"unknown key: {k}")

    count = u.get("count")
    count_ok = isinstance(count, int) and not isinstance(count, bool) and count >= 0
    if "count" in u and not count_ok:
        errs.append("count must be a non-negative integer")

    by_judge = u.get("by_judge")
    by_judge_ok = isinstance(by_judge, dict)
    if "by_judge" in u:
        if not by_judge_ok:
            errs.append("by_judge must be an object")
        else:
            for judge_key, judge_count in by_judge.items():
                if not isinstance(judge_key, str) or not judge_key.strip():
                    errs.append("by_judge keys must be non-empty strings")
                if (
                    not isinstance(judge_count, int)
                    or isinstance(judge_count, bool)
                    or judge_count < 0
                ):
                    errs.append(f"by_judge[{judge_key!r}] must be a non-negative integer")

    if count_ok and by_judge_ok:
        judge_sum = sum(
            v
            for v in by_judge.values()
            if isinstance(v, int) and not isinstance(v, bool) and v >= 0
        )
        if judge_sum != count:
            errs.append(
                f"by_judge values sum to {judge_sum}, which does not match count ({count})"
            )
    return errs


def _validate_finding(f: Any) -> list[str]:
    if not isinstance(f, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(f.keys())
    for k in sorted(REQUIRED_FINDING_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_FINDING_KEYS - OPTIONAL_FINDING_KEYS):
        errs.append(f"unknown key: {k}")

    if "finding_id" in f:
        fid = f.get("finding_id")
        if not isinstance(fid, str) or not fid.strip():
            errs.append("finding_id must be a non-empty string")
    if "raised_by" in f:
        rb = f.get("raised_by")
        if (
            not isinstance(rb, list)
            or not rb
            or not all(isinstance(x, str) and x.strip() for x in rb)
        ):
            errs.append("raised_by must be a non-empty list of non-empty strings")
    for field in ("claim_symptom", "claim_cause"):
        if field not in f:
            continue
        v = f.get(field)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{field} must be a non-empty string")

    if "consolidator_decision" in f:
        cd = f.get("consolidator_decision")
        if not _in_enum(cd, CONSOLIDATOR_DECISIONS):
            errs.append(
                f"consolidator_decision must be one of {sorted(CONSOLIDATOR_DECISIONS)}, "
                f"got {cd!r}"
            )
    if "verifier_verdict" in f:
        vv = f.get("verifier_verdict")
        if vv is not None and not _in_enum(vv, VERIFIER_VERDICTS):
            errs.append(
                f"verifier_verdict must be one of {sorted(VERIFIER_VERDICTS)} or null, "
                f"got {vv!r}"
            )
    if "verifier_cause_upheld" in f:
        vcu = f.get("verifier_cause_upheld")
        if vcu is not None and not isinstance(vcu, bool):
            errs.append("verifier_cause_upheld must be a boolean or null")
    if "already_tracked_as" in f:
        ata = f.get("already_tracked_as")
        if ata is not None and not isinstance(ata, str):
            errs.append("already_tracked_as must be a string or null")
    if "fights_ruling" in f:
        fr = f.get("fights_ruling")
        if fr is not None and not isinstance(fr, (bool, str)):
            errs.append("fights_ruling must be a boolean, string, or null")
    if "fix_status" in f:
        fs = f.get("fix_status")
        if fs is not None and (not isinstance(fs, str) or not fs.strip()):
            errs.append("fix_status must be a non-empty string or null")
    if "found_at_stage" in f:
        fas = f.get("found_at_stage")
        if fas is not None and not _in_enum(fas, FOUND_AT_STAGES):
            errs.append(
                f"found_at_stage must be one of {sorted(FOUND_AT_STAGES)} or null, got {fas!r}"
            )
    if "issue_refs" in f:
        ir = f.get("issue_refs")
        if not isinstance(ir, list) or not all(isinstance(x, str) and x.strip() for x in ir):
            errs.append("issue_refs must be a list of non-empty strings")
    return errs


def _validate_cost(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(c.keys())
    for k in sorted(REQUIRED_COST_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_COST_KEYS - OPTIONAL_COST_KEYS):
        errs.append(f"unknown key: {k}")

    source = c.get("source")
    if "source" in c and not _in_enum(source, COST_SOURCES):
        errs.append(f"source must be one of {sorted(COST_SOURCES)}, got {source!r}")

    total_tokens = c.get("total_tokens")
    if "total_tokens" in c and total_tokens is not None:
        # Round 14, BLOCKER 1 (decision b): mirror the same overflow-safety
        # guard as the "int" fields in _validate_dispatch -- an int too
        # large to survive a finite float conversion (e.g. 10**309) is
        # schema-valid today and unusable by every downstream reader.
        if not (_is_int(total_tokens) and is_finite_number(total_tokens)):
            # Round 16, finding 4: a real int that only failed because it
            # overflows a finite float gets a message that says so, rather
            # than the generic "must be an integer" -- it already is one.
            if _is_int(total_tokens) and not is_finite_number(total_tokens):
                errs.append("total_tokens must be an integer small enough to convert to a finite float")
            else:
                errs.append("total_tokens must be an integer or null")
        elif total_tokens < 0:
            errs.append("total_tokens must be >= 0")

    total_usd = c.get("total_usd")
    if "total_usd" in c and total_usd is not None:
        if not _is_number(total_usd):
            # Round 18, cheap nit: mirror total_tokens's overflow-specific
            # wording above -- a real int (bool excluded) that only failed
            # because it is too large to survive a finite float conversion
            # (e.g. 10**309) gets a message that says so, rather than the
            # generic "must be a number or null" -- it already is one.
            if _is_int(total_usd) and not is_finite_number(total_usd):
                errs.append("total_usd must be a number small enough to convert to a finite float")
            else:
                errs.append("total_usd must be a number or null")
        elif total_usd < 0:
            errs.append("total_usd must be >= 0")

    if source == "unavailable":
        if total_tokens is not None or total_usd is not None:
            errs.append("source is 'unavailable' but total_tokens/total_usd is not null")
        if not c.get("reason"):
            errs.append("source is 'unavailable' but no 'reason' was given")
    if source == "spend_ledger" and total_usd is None and not c.get("reason"):
        errs.append("total_usd is null under source spend_ledger but no 'reason' was given")
    if source == "spend_ledger" and total_tokens is None and not c.get("reason"):
        errs.append("total_tokens is null under source spend_ledger but no 'reason' was given")

    if "reason" in c and c["reason"] is not None and not isinstance(c["reason"], str):
        errs.append("reason must be a string")

    if "window" in c and c["window"] is not None:
        w = c["window"]
        if not isinstance(w, dict) or set(w.keys()) != {"start", "end", "tolerance_sec"}:
            errs.append("window must be an object with exactly start/end/tolerance_sec")
        else:
            if not isinstance(w.get("start"), str):
                errs.append("window.start must be a string")
            if not isinstance(w.get("end"), str):
                errs.append("window.end must be a string")
            if not _is_number(w.get("tolerance_sec")):
                errs.append("window.tolerance_sec must be a number")

    if "matched_rows" in c and c["matched_rows"] is not None and not _is_int(c["matched_rows"]):
        errs.append("matched_rows must be an integer or null")

    if "unpriced_models" in c and c["unpriced_models"] is not None:
        um = c["unpriced_models"]
        if not isinstance(um, list) or not all(isinstance(x, str) for x in um):
            errs.append("unpriced_models must be a list of strings")

    return errs


# ---------------------------------------------------------------------------
# v2 sub-object validators — every array holding these at the top level is
# OPTIONAL (see OPTIONAL_TOP_KEYS); each function here only runs at all when
# the caller's record actually has the corresponding key.
# ---------------------------------------------------------------------------


def _validate_run(r: Any) -> list[str]:
    if not isinstance(r, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(r.keys())
    for k in sorted(REQUIRED_RUN_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_RUN_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("run_id", "purpose", "outcome"):
        if field in r:
            v = r.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "agent_types" in r:
        v = r.get("agent_types")
        if (
            not isinstance(v, list)
            or not v
            or not all(isinstance(x, str) and x.strip() for x in v)
        ):
            errs.append("agent_types must be a non-empty list of non-empty strings")
    if "model" in r:
        v = r.get("model")
        if v is not None and not isinstance(v, str):
            errs.append("model must be a string or null")
    if "dispatch_count" in r:
        v = r.get("dispatch_count")
        if v is not None:
            if not _is_int(v):
                errs.append("dispatch_count must be an integer or null")
            elif v < 0:
                errs.append("dispatch_count must be >= 0")

    start_dt = end_dt = None
    if "started_at" in r:
        v = r.get("started_at")
        if v is not None:
            start_dt = _parse_iso8601z(v)
            if start_dt is None:
                errs.append("started_at must be an ISO8601 'Z' timestamp string or null")
    if "ended_at" in r:
        v = r.get("ended_at")
        if v is not None:
            end_dt = _parse_iso8601z(v)
            if end_dt is None:
                errs.append("ended_at must be an ISO8601 'Z' timestamp string or null")
    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        errs.append("ended_at is before started_at")
    return errs


def _validate_review_finding(f: Any) -> list[str]:
    if not isinstance(f, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(f.keys())
    for k in sorted(REQUIRED_REVIEW_FINDING_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_REVIEW_FINDING_KEYS):
        errs.append(f"unknown key: {k}")

    if "description" in f:
        v = f.get("description")
        if not isinstance(v, str) or not v.strip():
            errs.append("description must be a non-empty string")
    if "severity" in f:
        v = f.get("severity")
        if not _in_enum(v, REVIEW_SEVERITIES):
            errs.append(f"severity must be one of {sorted(REVIEW_SEVERITIES)}, got {v!r}")
    if "fixed" in f:
        v = f.get("fixed")
        if v is not None and not isinstance(v, bool):
            errs.append("fixed must be a boolean or null")
    return errs


def _validate_review(r: Any) -> list[str]:
    if not isinstance(r, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(r.keys())
    for k in sorted(REQUIRED_REVIEW_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_REVIEW_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("review_id", "reviewer", "target"):
        if field in r:
            v = r.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "model" in r:
        v = r.get("model")
        if v is not None and not isinstance(v, str):
            errs.append("model must be a string or null")
    if "related_findings" in r:
        v = r.get("related_findings")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("related_findings must be a list of non-empty strings")

    round_ = r.get("round")
    if "round" in r and (not _is_int(round_) or round_ < 1):
        errs.append("round must be an integer >= 1")
    blocker_count = r.get("blocker_count")
    if "blocker_count" in r and (not _is_int(blocker_count) or blocker_count < 0):
        errs.append("blocker_count must be an integer >= 0")

    if "findings" in r:
        findings = r.get("findings")
        if not isinstance(findings, list):
            errs.append("findings must be a list")
        else:
            for i, rf in enumerate(findings):
                errs.extend(f"findings[{i}]: {e}" for e in _validate_review_finding(rf))

    for field in ("upheld_decisions", "overturned_decisions"):
        if field in r:
            v = r.get(field)
            if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                errs.append(f"{field} must be a list of non-empty strings")

    outcome = r.get("outcome")
    if "outcome" in r and not _in_enum(outcome, REVIEW_OUTCOMES):
        errs.append(f"outcome must be one of {sorted(REVIEW_OUTCOMES)}, got {outcome!r}")
    if "reviewed_at" in r:
        v = r.get("reviewed_at")
        if v is not None and _parse_iso8601z(v) is None:
            errs.append("reviewed_at must be an ISO8601 'Z' timestamp string or null")

    if outcome == "clean" and _is_int(blocker_count) and blocker_count != 0:
        errs.append("outcome is 'clean' but blocker_count is not 0")
    if outcome == "blockers" and _is_int(blocker_count) and blocker_count < 1:
        errs.append("outcome is 'blockers' but blocker_count is < 1")
    return errs


def _validate_change(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(c.keys())
    for k in sorted(REQUIRED_CHANGE_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_CHANGE_KEYS):
        errs.append(f"unknown key: {k}")

    if "change_id" in c:
        v = c.get("change_id")
        if not isinstance(v, str) or not v.strip():
            errs.append("change_id must be a non-empty string")
    if "finding_id" in c:
        v = c.get("finding_id")
        if v is not None and not isinstance(v, str):
            errs.append("finding_id must be a string or null")
    if "commit_sha" in c:
        v = c.get("commit_sha")
        if not isinstance(v, str) or not v.strip():
            errs.append(
                "commit_sha must be a non-empty string (use 'uncommitted' if nothing has landed)"
            )
    if "files" in c:
        v = c.get("files")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("files must be a list of non-empty strings")
    for field in ("lines_added", "lines_removed"):
        if field in c:
            v = c.get(field)
            if v is not None:
                if not _is_int(v):
                    errs.append(f"{field} must be an integer or null")
                elif v < 0:
                    errs.append(f"{field} must be >= 0")
    if "red_before_green" in c:
        v = c.get("red_before_green")
        if not isinstance(v, str) or not v.strip():
            errs.append(
                "red_before_green must be a non-empty string "
                "(falsifiability evidence, or 'unverified')"
            )
    if "tests_added" in c:
        v = c.get("tests_added")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("tests_added must be a list of non-empty strings")
    if "golden_net_drift" in c:
        v = c.get("golden_net_drift")
        if v is not None and not isinstance(v, str):
            errs.append("golden_net_drift must be a string or null")
    if "reverted" in c:
        v = c.get("reverted")
        if not isinstance(v, bool):
            errs.append("reverted must be a boolean")
    return errs


def _validate_decision(d: Any) -> list[str]:
    if not isinstance(d, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(d.keys())
    for k in sorted(REQUIRED_DECISION_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_DECISION_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("decision_id", "decided_by", "what", "reasoning", "action"):
        if field in d:
            v = d.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "supersedes" in d:
        v = d.get("supersedes")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("supersedes must be a list of non-empty strings")
    if "decided_at" in d:
        v = d.get("decided_at")
        if v is not None and _parse_iso8601z(v) is None:
            errs.append("decided_at must be an ISO8601 'Z' timestamp string or null")
    return errs


def _validate_issue_filed(i: Any) -> list[str]:
    if not isinstance(i, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(i.keys())
    for k in sorted(REQUIRED_ISSUE_FILED_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_ISSUE_FILED_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("issue_id", "title"):
        if field in i:
            v = i.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "related_findings" in i:
        v = i.get("related_findings")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("related_findings must be a list of non-empty strings")
    for field in ("filed_by", "status"):
        if field in i:
            v = i.get(field)
            if v is not None and not isinstance(v, str):
                errs.append(f"{field} must be a string or null")
    if "filed_at" in i:
        v = i.get("filed_at")
        if v is not None and _parse_iso8601z(v) is None:
            errs.append("filed_at must be an ISO8601 'Z' timestamp string or null")
    return errs


def _validate_evidence(e: Any) -> list[str]:
    if not isinstance(e, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(e.keys())
    for k in sorted(REQUIRED_EVIDENCE_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_EVIDENCE_KEYS):
        errs.append(f"unknown key: {k}")

    if "evidence_id" in e:
        v = e.get("evidence_id")
        if not isinstance(v, str) or not v.strip():
            errs.append("evidence_id must be a non-empty string")
    for field in ("finding_id", "file", "quote", "repro_command"):
        if field in e:
            v = e.get(field)
            if v is not None and not isinstance(v, str):
                errs.append(f"{field} must be a string or null")
    if "line" in e:
        v = e.get("line")
        if v is not None:
            if not _is_int(v):
                errs.append("line must be an integer or null")
            elif v < 1:
                errs.append("line must be >= 1")
    if not (e.get("file") or e.get("quote") or e.get("repro_command")):
        errs.append("evidence must include at least one of: file, quote, repro_command")
    return errs


def _validate_correction(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(c.keys())
    for k in sorted(REQUIRED_CORRECTION_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_CORRECTION_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("correction_id", "what_was_claimed", "what_was_wrong", "how_found"):
        if field in c:
            v = c.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "invalidated" in c:
        v = c.get("invalidated")
        if v is not None and not isinstance(v, str):
            errs.append("invalidated must be a string or null")
    return errs


def _validate_verdict(v_obj: Any) -> list[str]:
    if not isinstance(v_obj, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(v_obj.keys())
    for k in sorted(REQUIRED_VERDICT_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_VERDICT_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("dispatch_label", "scenario"):
        if field in v_obj:
            v = v_obj.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    if "verdict" in v_obj:
        v = v_obj.get("verdict")
        if not _in_enum(v, VERDICT_VALUES):
            errs.append(f"verdict must be one of {sorted(VERDICT_VALUES)}, got {v!r}")
    if "confidence" in v_obj:
        v = v_obj.get("confidence")
        if v is not None:
            if not _is_number(v):
                errs.append("confidence must be a number or null")
            elif not (0.0 <= v <= 1.0):
                errs.append("confidence must be between 0 and 1")
    if "problem_count" in v_obj:
        v = v_obj.get("problem_count")
        if v is not None:
            if not _is_int(v):
                errs.append("problem_count must be an integer or null")
            elif v < 0:
                errs.append("problem_count must be >= 0")
    return errs


def _validate_stage(s: Any) -> list[str]:
    if not isinstance(s, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(s.keys())
    for k in sorted(REQUIRED_STAGE_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_STAGE_KEYS):
        errs.append(f"unknown key: {k}")

    for field in ("stage_id", "name"):
        if field in s:
            v = s.get(field)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{field} must be a non-empty string")
    status = s.get("status")
    if "status" in s and not _in_enum(status, STAGE_STATUSES):
        errs.append(f"status must be one of {sorted(STAGE_STATUSES)}, got {status!r}")
    blocked_reason = s.get("blocked_reason")
    if "blocked_reason" in s and blocked_reason is not None and not isinstance(blocked_reason, str):
        errs.append("blocked_reason must be a string or null")
    if status == "blocked" and not (isinstance(blocked_reason, str) and blocked_reason.strip()):
        errs.append("status is 'blocked' but no non-empty 'blocked_reason' was given")
    return errs


def _validate_calibration_run(r: Any) -> list[str]:
    """One row of calibration_runs[] -- mirrors _validate_calibration's
    strictness (unknown keys rejected, every field type-checked) plus the
    two null-plant rules the grid needs that a single `calibration` object
    can't express at all:

      * plant_id is null (a CONTROL row): caught_by/missed_by must stay
        empty -- nothing was seeded to catch or miss, identical to
        _validate_calibration's existing rule -- but false_alarm_finding_ids
        MAY be non-empty (that's the whole point of this array: a clean
        control can now carry the false-alarm signal a bare `calibration`
        block structurally cannot).
      * plant_id is set (a PLANT row): the mirror-image rule --
        false_alarm_finding_ids must stay empty, since a finding against a
        genuinely-seeded plant is a catch or a miss, never a false alarm."""
    if not isinstance(r, dict):
        return ["must be an object"]
    errs: list[str] = []
    keys = set(r.keys())
    for k in sorted(REQUIRED_CALIBRATION_RUN_KEYS - keys):
        errs.append(f"missing required key: {k}")
    for k in sorted(keys - REQUIRED_CALIBRATION_RUN_KEYS):
        errs.append(f"unknown key: {k}")

    plant_id = r.get("plant_id")
    if "plant_id" in r and plant_id is not None and not isinstance(plant_id, str):
        errs.append("plant_id must be a string or null")
    if "trade" in r:
        trade = r.get("trade")
        if not isinstance(trade, str) or not trade.strip():
            errs.append("trade must be a non-empty string")
    if "slot" in r:
        slot = r.get("slot")
        if slot is not None and (isinstance(slot, bool) or not isinstance(slot, (str, int))):
            errs.append("slot must be a string, integer, or null")
    if "batch_size" in r:
        bs = r.get("batch_size")
        if bs is not None:
            if not (_is_int(bs) and is_finite_number(bs)):
                errs.append("batch_size must be an integer or null")
            elif bs < 1:
                errs.append("batch_size must be >= 1")

    for field in ("caught_by", "missed_by"):
        if field not in r:
            continue
        v = r.get(field)
        if not isinstance(v, list) or not all(
            isinstance(x, (str, int)) and not isinstance(x, bool) for x in v
        ):
            errs.append(f"{field} must be a list of strings/integers")
    if "false_alarm_finding_ids" in r:
        v = r.get("false_alarm_finding_ids")
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append("false_alarm_finding_ids must be a list of non-empty strings")

    caught_by = r.get("caught_by") if isinstance(r.get("caught_by"), list) else []
    missed_by = r.get("missed_by") if isinstance(r.get("missed_by"), list) else []
    false_alarms = (
        r.get("false_alarm_finding_ids")
        if isinstance(r.get("false_alarm_finding_ids"), list)
        else []
    )
    if plant_id is None:
        if caught_by or missed_by:
            errs.append("caught_by/missed_by must be empty when plant_id is null (a control row)")
    else:
        if false_alarms:
            errs.append(
                "false_alarm_finding_ids must be empty when plant_id is set (a plant row) -- "
                "a finding against a seeded plant is a catch/miss, never a false alarm"
            )
    return errs


def validate_cycle(record: Any) -> list[str]:
    """Validate a cycle record against the schema. Returns error strings
    (empty list == valid). Rejects unknown keys, wrong enum values, and
    missing required fields at every level — never silently tolerant."""
    if not isinstance(record, dict):
        return ["cycle record must be a JSON object"]

    errs: list[str] = []
    keys = set(record.keys())
    for k in sorted(REQUIRED_TOP_KEYS - keys):
        errs.append(f"missing required top-level key: {k}")
    for k in sorted(keys - REQUIRED_TOP_KEYS - OPTIONAL_TOP_KEYS):
        errs.append(f"unknown top-level key: {k}")

    if "schema_version" in record and not _in_enum(record.get("schema_version"), ALLOWED_SCHEMA_VERSIONS):
        errs.append(
            f"schema_version must be one of {sorted(ALLOWED_SCHEMA_VERSIONS)}, "
            f"got {record.get('schema_version')!r}"
        )

    if "system" in record:
        errs.extend(_slug_errors(record.get("system"), "system"))
    if "repo" in record:
        repo = record.get("repo")
        if repo is not None and (not isinstance(repo, str) or not repo.strip()):
            errs.append("repo must be a non-empty string or null")
    if "cycle_id" in record:
        errs.extend(_slug_errors(record.get("cycle_id"), "cycle_id"))

    start_dt = end_dt = None
    if "started_at" in record:
        started_at = record.get("started_at")
        start_dt = _parse_iso8601z(started_at)
        if start_dt is None:
            errs.append("started_at must be an ISO8601 'Z' timestamp string")
    if "ended_at" in record:
        ended_at = record.get("ended_at")
        if ended_at is not None:
            end_dt = _parse_iso8601z(ended_at)
            if end_dt is None:
                errs.append(
                    "ended_at must be an ISO8601 'Z' timestamp string or null "
                    "(null = cycle still in progress)"
                )
    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        errs.append("ended_at is before started_at")

    if "dispatches" in record:
        dispatches = record.get("dispatches")
        if not isinstance(dispatches, list):
            errs.append("dispatches must be a list")
        else:
            for i, d in enumerate(dispatches):
                errs.extend(f"dispatches[{i}]: {e}" for e in _validate_dispatch(d))

    if "calibration" in record:
        errs.extend(f"calibration: {e}" for e in _validate_calibration(record.get("calibration")))

    if "findings" in record:
        findings = record.get("findings")
        if not isinstance(findings, list):
            errs.append("findings must be a list")
        else:
            for i, f in enumerate(findings):
                errs.extend(f"findings[{i}]: {e}" for e in _validate_finding(f))

    if "cost" in record:
        errs.extend(f"cost: {e}" for e in _validate_cost(record.get("cost")))

    if "undispatched_verdict_rows" in record:
        errs.extend(
            f"undispatched_verdict_rows: {e}"
            for e in _validate_undispatched_verdict_rows(record.get("undispatched_verdict_rows"))
        )

    if "notes" in record:
        notes = record.get("notes")
        if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
            errs.append("notes must be a list of strings")

    # v2 optional top-level arrays — every one absent on a v1 record, so this
    # loop is a no-op for anything written against the v1 shape.
    for top_key, validator in (
        ("runs", _validate_run),
        ("reviews", _validate_review),
        ("changes", _validate_change),
        ("decisions", _validate_decision),
        ("issues_filed", _validate_issue_filed),
        ("evidence", _validate_evidence),
        ("corrections", _validate_correction),
        ("verdicts", _validate_verdict),
        ("stages", _validate_stage),
        ("calibration_runs", _validate_calibration_run),
    ):
        if top_key not in record:
            continue
        items = record.get(top_key)
        if not isinstance(items, list):
            errs.append(f"{top_key} must be a list")
            continue
        for i, item in enumerate(items):
            errs.extend(f"{top_key}[{i}]: {e}" for e in validator(item))

    return errs


def assert_valid_cycle(record: Any) -> None:
    """Raise ValidationError if record fails validate_cycle()."""
    errs = validate_cycle(record)
    if errs:
        raise ValidationError(errs)


# ---------------------------------------------------------------------------
# Storage — one JSON file per cycle at cycles/<system>/<cycle_id>.json.
# ---------------------------------------------------------------------------


def cycle_path(system: str, cycle_id: str, *, cycles_dir: str | None = None) -> str:
    system = _require_safe_component(system, "system")
    cycle_id = _require_safe_component(cycle_id, "cycle_id")
    base = CYCLES_DIR if cycles_dir is None else cycles_dir
    return os.path.join(base, system, f"{cycle_id}.json")


def write_cycle(record: dict, *, overwrite: bool = False, cycles_dir: str | None = None) -> str:
    """Validate then write a cycle record. Refuses to persist an invalid
    record (raises ValidationError) and refuses to clobber an existing file
    unless overwrite=True. Writes atomically (temp file + os.replace)."""
    assert_valid_cycle(record)
    path = cycle_path(record["system"], record["cycle_id"], cycles_dir=cycles_dir)
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(
            f"cycle record already exists: {path} (pass overwrite=True to replace it)"
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp-{os.getpid()}-{int(time.time() * 1000)}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            # Round 10, BLOCKER 4: allow_nan=False for the same reason every
            # other JSON write in this module now has it -- assert_valid_cycle()
            # above already refuses a non-finite total_usd/total_tokens, so this
            # is defense in depth, not a path exercised in normal operation.
            json.dump(record, fh, indent=2, sort_keys=True, allow_nan=False)
            fh.write("\n")
        os.replace(tmp_path, path)
    finally:
        # Round 12, nit #7: if `json.dump` raises (e.g. the `allow_nan=False`
        # defense-in-depth above) or `os.replace` fails, the temp file used
        # to be orphaned on disk instead of cleaned up. Currently
        # unreachable in practice (assert_valid_cycle() already validates
        # the record before this point), but this makes the atomic-write
        # pattern airtight rather than merely "safe by coincidence." A
        # successful os.replace() has already moved tmp_path to path, so
        # this is a no-op in the normal case; best-effort only, so a
        # cleanup failure never masks the real underlying error.
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return path


def read_cycle(system: str, cycle_id: str, *, cycles_dir: str | None = None) -> dict:
    """Round 8, BLOCKER 1: guarded with the same `reject_non_finite_json_constant`
    parse boundary as read_cycles()/read_ledger_rows() -- a bare NaN/
    Infinity/-Infinity constant in a single cycle file is rejected here
    too, rather than only when read through the multi-file loader."""
    path = cycle_path(system, cycle_id, cycles_dir=cycles_dir)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_constant=reject_non_finite_json_constant, parse_float=reject_non_finite_json_float)


def _listdir_tolerant(path: str) -> list[str]:
    """`os.listdir`, tolerating an unreadable directory (e.g. a
    PermissionError on a system directory this process can't read) as "no
    files found there" rather than letting it escape uncaught -- every
    caller of iter_cycle_paths() assumes a broken subdirectory degrades to
    an empty scan of it, the same tolerance already given to a broken file
    (round 8, finding #8)."""
    try:
        return os.listdir(path)
    except OSError as exc:
        logging.getLogger(__name__).warning("could not list directory %s: %s", path, exc)
        return []


def iter_cycle_paths(system: str | None = None, *, cycles_dir: str | None = None) -> list[str]:
    base = CYCLES_DIR if cycles_dir is None else cycles_dir
    if not os.path.isdir(base):
        return []
    if system is not None:
        system = _require_safe_component(system, "system")
        systems = [system]
    else:
        systems = sorted(d for d in _listdir_tolerant(base) if os.path.isdir(os.path.join(base, d)))
    paths: list[str] = []
    for sysname in systems:
        sys_dir = os.path.join(base, sysname)
        if not os.path.isdir(sys_dir):
            continue
        for name in sorted(_listdir_tolerant(sys_dir)):
            if name.endswith(".json"):
                paths.append(os.path.join(sys_dir, name))
    return paths


def read_cycles(
    system: str | None = None,
    *,
    cycles_dir: str | None = None,
    on_error: str = "raise",
) -> list[dict]:
    """Read every cycle record for one system, or all systems if system=None.

    on_error="raise" (default) surfaces a broken file immediately; "skip"
    silently omits it (used by the CLI's `validate` command, which wants to
    report broken files rather than crash on the first one). A file whose
    top-level JSON value parses fine but ISN'T an object (a bare list, a
    scalar) is treated exactly like any other malformed file (BLOCKER 4,
    round 6) -- this function's whole job is to hand back valid cycle
    records, so a non-dict value is EXCLUDED from the returned list, never
    appended and left for some downstream `.get()` call to crash on. A
    bare NaN/Infinity/-Infinity JSON constant is likewise rejected at the
    parse boundary (round 8, BLOCKER 1) -- the same guard read_ledger_rows()
    already applies to spend.jsonl.

    The final sort is keyed ONLY on a `started_at` that is actually a
    string (round 8, BLOCKER 3): the record-EXCLUSION logic above already
    protects this loop's own `.get()` calls, but the sort key runs on
    already-included dict records and used to read `r.get("started_at") or
    ""` -- `or ""` only falls back on a FALSY value, so a present-but-wrong
    -type `started_at` (e.g. `5`, a truthy non-string) passed straight
    through and crashed `list.sort()` with a `str`-vs-`int` TypeError the
    instant it sat next to one real string timestamp -- escaping
    on_error="skip"'s own stated per-file tolerance entirely, since this
    line runs once, after every file has already been read."""
    if on_error not in ("raise", "skip"):
        raise ValueError("on_error must be 'raise' or 'skip'")
    records: list[dict] = []
    for path in iter_cycle_paths(system, cycles_dir=cycles_dir):
        try:
            with open(path, encoding="utf-8") as fh:
                parsed = json.load(fh, parse_constant=reject_non_finite_json_constant, parse_float=reject_non_finite_json_float)
        except Exception as exc:
            if on_error == "raise":
                raise ValueError(f"failed to read cycle record {path}: {exc}") from exc
            continue
        if not isinstance(parsed, dict):
            if on_error == "raise":
                raise ValueError(
                    f"cycle record {path} is not a JSON object (got {type(parsed).__name__})"
                )
            continue
        records.append(parsed)

    def _sort_key(r: dict) -> str:
        started_at = r.get("started_at")
        return started_at if isinstance(started_at, str) else ""

    records.sort(key=_sort_key)
    return records


def list_systems(*, cycles_dir: str | None = None) -> list[str]:
    """Round 10, BLOCKER 6: this is the structural twin of iter_cycle_paths()
    above -- both list the system-name directories under the same
    `cycles_dir` base -- but iter_cycle_paths() already got the
    `_listdir_tolerant` treatment (round 8) while this sibling still called
    bare `os.listdir` directly, so an unreadable base directory (e.g. a
    PermissionError) raised uncaught here while the other function
    correctly returned []."""
    base = CYCLES_DIR if cycles_dir is None else cycles_dir
    if not os.path.isdir(base):
        return []
    return sorted(d for d in _listdir_tolerant(base) if os.path.isdir(os.path.join(base, d)))


# ---------------------------------------------------------------------------
# Derived metrics — pure functions, no LLM, no network. See README.md for
# what each one MEANS and why cause_precision is the one that matters most.
# ---------------------------------------------------------------------------


def symptom_precision(record: dict) -> float | None:
    """Fraction of verified findings whose SYMPTOM claim was real (verdict in
    CONFIRMED/PARTIALLY_CONFIRMED/ALREADY_TRACKED_ELSEWHERE), out of every
    finding the verifier actually judged (excludes UNVERIFIABLE and
    not-yet-verified findings from the denominator — you can't score a
    judgment that was never made). None if nothing has been verified yet."""
    findings = _safe_list_of_dicts(record.get("findings"))
    verified = [f for f in findings if f.get("verifier_verdict") not in (None, "UNVERIFIABLE")]
    if not verified:
        return None
    correct = [
        f
        for f in verified
        if f.get("verifier_verdict") in ("CONFIRMED", "PARTIALLY_CONFIRMED", "ALREADY_TRACKED_ELSEWHERE")
    ]
    return len(correct) / len(verified)


def cause_precision(record: dict) -> float | None:
    """Fraction of judged findings where the RAISER's stated root cause was
    actually upheld by the verifier (verifier_cause_upheld is True), out of
    every finding where that judgment was made at all. This is the metric
    that matters most: a finder can be right about *something being wrong*
    (high symptom_precision) while being wrong about *why* almost every time
    (low cause_precision) — the difference between "found a real bug" and
    "found a real bug and correctly diagnosed it," which is what a fix
    actually needs. None if no cause judgment has been recorded yet."""
    findings = _safe_list_of_dicts(record.get("findings"))
    judged = [f for f in findings if f.get("verifier_cause_upheld") is not None]
    if not judged:
        return None
    upheld = [f for f in judged if f.get("verifier_cause_upheld") is True]
    return len(upheld) / len(judged)


def duplicate_rate(record: dict) -> float | None:
    """Fraction of ALL raised findings that turned out to be re-hits on an
    already-tracked issue (already_tracked_as set, or verdict
    ALREADY_TRACKED_ELSEWHERE). None if there were no findings at all."""
    findings = _safe_list_of_dicts(record.get("findings"))
    if not findings:
        return None
    dup = [
        f
        for f in findings
        if f.get("already_tracked_as") is not None
        or f.get("verifier_verdict") == "ALREADY_TRACKED_ELSEWHERE"
    ]
    return len(dup) / len(findings)


def ruling_conflict_rate(record: dict) -> float | None:
    """Fraction of ALL raised findings that contradict an already-ratified
    ruling (fights_ruling truthy). None if there were no findings at all."""
    findings = _safe_list_of_dicts(record.get("findings"))
    if not findings:
        return None
    conflict = [f for f in findings if _truthy_ruling(f.get("fights_ruling"))]
    return len(conflict) / len(findings)


def consolidation_ratio(record: dict) -> float | None:
    """Average number of independent raisers collapsed into each final
    (post-consolidation) finding record: sum(len(raised_by)) / len(findings).
    1.0 means no two raisers ever converged on the same finding; higher means
    the consolidator is doing real deduplication work merging independent
    reports of the same real issue. None if there were no findings at all."""
    findings = _safe_list_of_dicts(record.get("findings"))
    if not findings:
        return None
    # Round 4 (surfaced while building blocker 5's replacement test): a
    # malformed raised_by (e.g. a bare number, not a list) must never reach
    # len() directly -- `3.5 or []` is truthy and skips the `or []`
    # fallback entirely, so len(3.5) raised TypeError; a non-empty string
    # would instead have silently len()'d its characters, an under-the-
    # radar wrong-count fabrication of the same class blocker 2 fixed for
    # calibration.caught_by. Coerce to [] on anything that isn't a list.
    total_raises = sum(
        len(f.get("raised_by")) if isinstance(f.get("raised_by"), list) else 0 for f in findings
    )
    return total_raises / len(findings)


def usd_per_confirmed_defect(record: dict) -> float | None:
    """cost.total_usd divided by the count of findings the verifier confirmed
    as real (CONFIRMED or PARTIALLY_CONFIRMED — duplicates and refutations do
    not count as a "defect" for this ratio; see duplicate_rate for that).
    None if cost is unpriced (total_usd is null) or there are zero confirmed
    defects (division by zero is undefined, not infinite). None also (never
    a raised TypeError) if total_usd is present but not actually numeric --
    a hand-edited or otherwise-corrupted record that was never validated by
    validate_cycle() is exactly the case this defends against; "unknown" is
    the honest answer for malformed data, same as "missing"."""
    cost = _safe_dict(record.get("cost"))
    total_usd = cost.get("total_usd")
    if total_usd is None or not _is_number(total_usd):
        return None
    findings = _safe_list_of_dicts(record.get("findings"))
    confirmed = [f for f in findings if f.get("verifier_verdict") in ("CONFIRMED", "PARTIALLY_CONFIRMED")]
    if not confirmed:
        return None
    return total_usd / len(confirmed)


def _slot_label(slot: Any) -> str:
    """A readable label for one calibration slot identifier. A slot is
    normally a plain string/int (a dispatch's batch position) -- `str()` of
    those is already readable. Finding #9 (round 8): a malformed record
    with a NESTED list/dict slot value (e.g. `caught_by: [[1, 2]]`) rendered
    via bare `str(slot)` as an unreadable Python-repr literal like "[1, 2]"
    on the operator page -- not a fabrication (it's an honest rendering of
    the raw value), but poor UX. `json.dumps` gives a compact, consistent,
    still-honest rendering for the non-primitive case without inventing any
    interpretation of what the value means."""
    if isinstance(slot, (list, dict)):
        try:
            # Round 10 operation-type audit: allow_nan=False for consistency
            # with every other json.dumps(s) call site in this module -- a
            # non-finite float nested inside a malformed slot value now
            # falls through to the existing str(slot) fallback below
            # (already exercised by the TypeError/ValueError except) rather
            # than embedding a bare `Infinity` token in this label.
            return json.dumps(slot, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError):
            return str(slot)
    return str(slot)


def plant_catch_by_slot(records: dict | list[dict]) -> dict[str, dict[str, float | int | None]]:
    """Calibration catch/miss counts grouped by slot, pooled across however
    many records are passed (a single record works too — pass one dict or a
    one-element list). Each slot identifier from calibration.caught_by /
    .missed_by becomes a key; skips any record with no plant seeded
    (calibration.plant_id is null). Returns {slot: {"caught", "missed",
    "rate"}}; rate is caught/(caught+missed), or None if a slot has zero
    observations (unreachable in practice since a slot only appears here by
    being observed, kept for symmetry with the other metrics' None-on-empty
    convention)."""
    if isinstance(records, dict):
        records = [records]
    out: dict[str, dict[str, float | int | None]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        # BLOCKER 3 (round 6): the CONTAINER itself, not just its inner
        # caught_by/missed_by fields fixed in round 4 below, must be
        # coerced too -- `"abc" or {}` and `5 or {}` are both truthy, so a
        # non-dict calibration value used to reach `cal.get("plant_id")`
        # unguarded and crash with AttributeError.
        cal = _safe_dict(rec.get("calibration"))
        if cal.get("plant_id") is None:
            continue
        # BLOCKER 2 (round 4): a malformed caught_by/missed_by (int/float/str
        # instead of a list) must never be iterated directly -- an int/float
        # raises TypeError, and a str silently iterates its characters,
        # FABRICATING invented slots at a fabricated 100% catch rate. Coerce
        # to [] on anything that isn't already a list, exactly like the
        # already-correct pattern in validate_cycle() at ~:548-549.
        caught_by = cal.get("caught_by") if isinstance(cal.get("caught_by"), list) else []
        missed_by = cal.get("missed_by") if isinstance(cal.get("missed_by"), list) else []
        for slot in caught_by:
            bucket = out.setdefault(_slot_label(slot), {"caught": 0, "missed": 0, "rate": None})
            bucket["caught"] = int(bucket["caught"] or 0) + 1
        for slot in missed_by:
            bucket = out.setdefault(_slot_label(slot), {"caught": 0, "missed": 0, "rate": None})
            bucket["missed"] = int(bucket["missed"] or 0) + 1
    for bucket in out.values():
        total = int(bucket["caught"] or 0) + int(bucket["missed"] or 0)
        bucket["rate"] = (bucket["caught"] / total) if total else None
    return out


def _calibration_run_discriminator(run: dict) -> str:
    """Classify one calibration_runs[] row's plant_id as "control" (key
    present, explicitly null -- a deliberate, real declaration), "plant"
    (key present, a string), or "unreadable" (the key is ABSENT entirely, or
    present with a value that is neither a string nor null -- `dict.get()`
    alone can't distinguish "absent" from "present and null," since both
    return None, so this checks membership first). An "unreadable" row is
    counted in BOTH plant_catch_by_trade's and false_alarm_by_trade's
    `unreadable` column for the same trade, by design -- neither aggregator
    can rule out that the row belonged to it, so an operator summing the two
    columns across both aggregators for one trade will double-count that
    row; the two `unreadable` counts are each honest on their own, never a
    partition of a single total."""
    if "plant_id" not in run:
        return "unreadable"
    pid = run["plant_id"]
    if pid is None:
        return "control"
    if isinstance(pid, str):
        return "plant"
    return "unreadable"


def plant_catch_by_trade(records: dict | list[dict]) -> dict[str, dict[str, float | int | None]]:
    """Calibration catch/miss counts grouped by TRADE, pooled across however
    many records are passed (a single record works too — pass one dict or a
    one-element list). Reads calibration_runs[] (never the legacy single
    `calibration` block plant_catch_by_slot() reads — the two are
    independent siblings, per the module docstring). Each PLANT row
    contributes its caught_by/missed_by counts to its own `trade` key; a
    genuine CONTROL row is skipped entirely -- nothing was seeded in it to
    catch or miss, and it is false_alarm_by_trade's concern instead. Returns
    {trade: {"caught", "missed", "unreadable", "rate"}}, plus a literal
    `"(unattributable)"` key when at least one row's `trade` itself could
    not be read.

    Never-fabricate contract (matches plant_catch_by_slot's own): a trade
    with ZERO readable signal -- every plant row for it had empty (and
    validly-typed) caught_by AND missed_by -- gets NO bucket at all. A
    PRESENT-but-malformed caught_by/missed_by, or an unreadable plant_id/
    trade discriminator (see _calibration_run_discriminator), is never
    silently coerced to "0 catches"/"0 misses" or dropped -- it increments
    `unreadable` and contributes nothing else to that row. An unreadable
    row is counted in BOTH this function's and false_alarm_by_trade's
    `unreadable` column for the same trade -- summing the two columns
    double-counts it; see _calibration_run_discriminator's own docstring.

    Deliberate ASYMMETRY with false_alarm_by_trade: a plant row's empty
    caught_by/missed_by pair means genuinely nothing happened (no bucket at
    all here); a control row's empty false_alarm_finding_ids means the
    OPPOSITE there -- a real "checked, drew nothing" observation that DOES
    create a bucket. A plant row's catches/misses are additional events
    that may or may not occur; a control row's mere existence (dispatched,
    evaluated) is itself the observation.

    `rate` is caught/(caught+missed), or None whenever a bucket's readable
    total is zero (a bucket that exists ONLY via unreadable rows) -- this
    None branch is reachable here (unlike plant_catch_by_slot's, since a
    slot key there can only ever be created BY a readable observation)."""
    if isinstance(records, dict):
        records = [records]
    out: dict[str, dict[str, float | int | None]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for run in _safe_list_of_dicts(rec.get("calibration_runs")):
            trade = run.get("trade")
            trade_ok = isinstance(trade, str) and bool(trade.strip())
            bucket_key = trade if trade_ok else "(unattributable)"

            plant_state = _calibration_run_discriminator(run)
            if plant_state == "control":
                continue  # a real control -- false_alarm_by_trade's concern, not this one
            if plant_state == "unreadable":
                bucket = out.setdefault(
                    bucket_key, {"caught": 0, "missed": 0, "unreadable": 0, "rate": None}
                )
                bucket["unreadable"] = int(bucket["unreadable"] or 0) + 1
                continue

            # plant_state == "plant"
            caught_by_raw = run.get("caught_by")
            missed_by_raw = run.get("missed_by")
            caught_ok = isinstance(caught_by_raw, list)
            missed_ok = isinstance(missed_by_raw, list)
            if not caught_ok or not missed_ok:
                bucket = out.setdefault(
                    bucket_key, {"caught": 0, "missed": 0, "unreadable": 0, "rate": None}
                )
                bucket["unreadable"] = int(bucket["unreadable"] or 0) + 1
                continue
            if not caught_by_raw and not missed_by_raw:
                continue  # legitimately empty -- zero readable signal, no bucket touched
            bucket = out.setdefault(
                bucket_key, {"caught": 0, "missed": 0, "unreadable": 0, "rate": None}
            )
            bucket["caught"] = int(bucket["caught"] or 0) + len(caught_by_raw)
            bucket["missed"] = int(bucket["missed"] or 0) + len(missed_by_raw)
    for bucket in out.values():
        total = int(bucket["caught"] or 0) + int(bucket["missed"] or 0)
        bucket["rate"] = (bucket["caught"] / total) if total else None
    return out


def false_alarm_by_trade(records: dict | list[dict]) -> dict[str, dict[str, float | int | None]]:
    """Per-trade false-alarm counts from calibration_runs[]'s CONTROL rows —
    a blocker/DISSENT finding filed against a clean control package IS the
    false-alarm signal (see the module docstring's calibration_runs entry,
    and C1's "false alarm" definition in the grader quality plan). A genuine
    PLANT row is skipped entirely — plant_catch_by_trade's concern, not this
    one. Pooled across however many records are passed. Returns {trade:
    {"controls", "false_alarms", "unreadable", "rate"}}, plus a literal
    `"(unattributable)"` key (see plant_catch_by_trade's matching docstring
    section and _calibration_run_discriminator) when at least one row's
    `trade` itself could not be read.

    FABRICATED INNOCENCE, never: a control row whose false_alarm_finding_ids
    is PRESENT but malformed (not a list) does NOT increment `controls` or
    `false_alarms` -- that would land a confident-looking but false 0-alarm
    reading on the exact "0 false alarms on controls" metric a trust
    decision might read directly. It increments `unreadable` instead, so
    the bucket honestly reads {"controls": 0, "unreadable": 1, "rate":
    None}. The same posture applies to the plant_id/trade discriminator
    (see _calibration_run_discriminator) -- an unreadable one is never
    silently read as a confident control. An unreadable row is counted in
    BOTH this function's and plant_catch_by_trade's `unreadable` column for
    the same trade -- summing the two columns double-counts it.

    Deliberate ASYMMETRY with plant_catch_by_trade (see its own docstring):
    an empty (but validly-typed) `false_alarm_finding_ids` on a genuine
    control row is a REAL "checked, found nothing" observation and DOES
    create/increment a bucket's `controls` count -- unlike a plant row's
    empty caught_by/missed_by, which is zero signal there (no bucket at
    all). A control's mere existence is the observation; a plant's
    catches/misses are additional events that may or may not occur.

    `rate` is false_alarms/controls, or None when a bucket exists (via
    control rows observed, readable or not) but has zero READABLE controls
    to divide by. Deliberately UNBOUNDED above 1.0: a single control that
    draws more than one finding (or several controls for the same trade
    each drawing one) both raise `false_alarms` faster than `controls`,
    and that is a real, meaningful signal (repeated false alarms against
    the same trade), never clamped or treated as a data error."""
    if isinstance(records, dict):
        records = [records]
    out: dict[str, dict[str, float | int | None]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for run in _safe_list_of_dicts(rec.get("calibration_runs")):
            trade = run.get("trade")
            trade_ok = isinstance(trade, str) and bool(trade.strip())
            bucket_key = trade if trade_ok else "(unattributable)"

            plant_state = _calibration_run_discriminator(run)
            if plant_state == "plant":
                continue  # a real plant -- plant_catch_by_trade's concern, not this one
            if plant_state == "unreadable":
                bucket = out.setdefault(
                    bucket_key, {"controls": 0, "false_alarms": 0, "unreadable": 0, "rate": None}
                )
                bucket["unreadable"] = int(bucket["unreadable"] or 0) + 1
                continue

            # plant_state == "control"
            bucket = out.setdefault(
                bucket_key, {"controls": 0, "false_alarms": 0, "unreadable": 0, "rate": None}
            )
            false_alarms_raw = run.get("false_alarm_finding_ids")
            if not isinstance(false_alarms_raw, list):
                bucket["unreadable"] = int(bucket["unreadable"] or 0) + 1
                continue
            bucket["controls"] = int(bucket["controls"] or 0) + 1
            bucket["false_alarms"] = int(bucket["false_alarms"] or 0) + len(false_alarms_raw)
    for bucket in out.values():
        controls = int(bucket["controls"] or 0)
        bucket["rate"] = (bucket["false_alarms"] / controls) if controls else None
    return out


def compute_metrics(record: dict) -> dict[str, Any]:
    """All derived metrics for a single cycle record, bundled."""
    return {
        "symptom_precision": symptom_precision(record),
        "cause_precision": cause_precision(record),
        "duplicate_rate": duplicate_rate(record),
        "ruling_conflict_rate": ruling_conflict_rate(record),
        "consolidation_ratio": consolidation_ratio(record),
        "usd_per_confirmed_defect": usd_per_confirmed_defect(record),
        "plant_catch_by_slot": plant_catch_by_slot(record),
        "plant_catch_by_trade": plant_catch_by_trade(record),
        "false_alarm_by_trade": false_alarm_by_trade(record),
    }


def aggregate_metrics(records: list[dict]) -> dict[str, Any]:
    """Metrics pooled across many cycle records (e.g. a whole system's
    history). Pools raw counts before dividing rather than averaging each
    cycle's own ratio — averaging ratios directly is vulnerable to Simpson's
    paradox when cycles have very different finding counts."""
    if not records:
        return {
            "cycle_count": 0,
            "finding_count": 0,
            "symptom_precision": None,
            "cause_precision": None,
            "duplicate_rate": None,
            "ruling_conflict_rate": None,
            "consolidation_ratio": None,
            "usd_per_confirmed_defect": None,
            "cost_known_cycles": 0,
            "cost_unknown_cycles": 0,
            "plant_catch_by_slot": {},
            "plant_catch_by_trade": {},
            "false_alarm_by_trade": {},
        }
    # BLOCKER 4 (round 6): a record itself may not even be a dict (e.g. a
    # cycle FILE whose top-level JSON value is a bare list or scalar --
    # read_cycles() now excludes those before they ever reach here, but this
    # function is also called directly, including from tests, with whatever
    # list of "records" a caller hands it) -- guard every per-record access
    # with isinstance(r, dict) rather than assuming the container's shape.
    all_findings: list[dict] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        all_findings.extend(_safe_list_of_dicts(r.get("findings")))
    pooled = {"findings": all_findings}

    # A record's cost.total_usd is trusted only when it is actually numeric
    # -- a hand-edited/corrupted record that was never through
    # validate_cycle() (e.g. read directly off disk by a CLI/renderer) must
    # degrade this ratio to None, never raise a TypeError trying to sum a
    # string into a float accumulator.
    priced = [
        r for r in records if isinstance(r, dict) and _is_number(_safe_dict(r.get("cost")).get("total_usd"))
    ]
    if priced:
        total_usd = sum((r["cost"]["total_usd"]) for r in priced)
        confirmed_total = sum(
            len(
                [
                    f
                    for f in _safe_list_of_dicts(r.get("findings"))
                    if f.get("verifier_verdict") in ("CONFIRMED", "PARTIALLY_CONFIRMED")
                ]
            )
            for r in priced
        )
        # Round 10, BLOCKER 3: each individual `total_usd` summed above was
        # already finiteness-checked by the `priced` filter above, but the
        # ACCUMULATED sum across many records can still overflow to +/-inf
        # even when every individual contribution was finite (the same
        # overflow shape price_tokens/resolve_cost/rollup_cost already
        # guard) -- never surface that as a confident 'inf' ratio.
        if not is_finite_number(total_usd):
            usd_per_defect = None
        else:
            usd_per_defect = (total_usd / confirmed_total) if confirmed_total else None
    else:
        usd_per_defect = None

    return {
        "cycle_count": len(records),
        "finding_count": len(all_findings),
        "symptom_precision": symptom_precision(pooled),
        "cause_precision": cause_precision(pooled),
        "duplicate_rate": duplicate_rate(pooled),
        "ruling_conflict_rate": ruling_conflict_rate(pooled),
        "consolidation_ratio": consolidation_ratio(pooled),
        "usd_per_confirmed_defect": usd_per_defect,
        "cost_known_cycles": len(priced),
        "cost_unknown_cycles": len(records) - len(priced),
        "plant_catch_by_slot": plant_catch_by_slot(records),
        "plant_catch_by_trade": plant_catch_by_trade(records),
        "false_alarm_by_trade": false_alarm_by_trade(records),
    }


# ---------------------------------------------------------------------------
# Cost resolution — pricing is DATA (telemetry/pricing.json), never a number
# hardcoded here. resolve_cost() is the correspondence-checked ledger reader:
# it REFUSES (returns source="unavailable") rather than guess whenever a
# cycle's dispatches don't correspond exactly (by time window, agent-type
# set, per-type row COUNT, AND dispatch IDENTITY -- never a looser 3-signal
# check; identity is REQUIRED, not an optional fourth check) to what the
# ledger shows in that window.
# ---------------------------------------------------------------------------


def load_pricing(pricing_path: str | None = None) -> dict:
    """Load the operator-editable pricing table. Missing/unreadable/malformed
    file degrades to an empty table (every model then prices as unknown) —
    never raises, since a pricing-file outage must not crash a caller that
    only wanted token counts."""
    path = PRICING_FILE if pricing_path is None else pricing_path
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh, parse_constant=reject_non_finite_json_constant, parse_float=reject_non_finite_json_float)
    except Exception:
        return {"version": None, "currency": "usd", "per_million_tokens": {}}
    if not isinstance(data, dict):
        return {"version": None, "currency": "usd", "per_million_tokens": {}}
    if not isinstance(data.get("per_million_tokens"), dict):
        data = dict(data)
        data["per_million_tokens"] = {}
    return data


def price_tokens(tokens: dict, model: str | None, pricing: dict) -> float | None:
    """Price one row's token usage against the pricing table. Returns None
    (never 0 or a guess) if the model is missing/unknown/unpriced, OR if
    `tokens` itself is missing/not-a-dict/empty/has no priceable bucket
    present as a real number.

    A ledger row can legitimately carry `tokens: null, tokens_total: null`
    (no usage data was ever recorded for it) -- summing zero across every
    bucket and calling that "priced at $0.00" is exactly the fabrication this
    module exists to prevent (a real incident: 9 real, priced-model ledger
    rows with no token data at all rendered as a confident "$0.00 ...
    ground truth" figure). Only a row with at least one bucket genuinely
    present as a number is ever priced, even if that number is 0.

    Round 8, BLOCKER 1: a bucket value that IS present as a number
    (int/float) but not FINITE (NaN, Infinity, -Infinity) is refused as
    UNPRICEABLE (returns None, same as an unknown model), never silently
    treated as 0 -- zeroing it would drop the real (if malformed) usage on
    the floor and let the REST of the row still price as a confident
    figure. The ACCUMULATED total is also finiteness-checked before being
    returned: an individual bucket can be a large-but-finite value (e.g.
    1e308 tokens) that only overflows to +/-inf once multiplied by a rate
    and summed across buckets -- round 6's guard only checked each INPUT,
    never the value actually returned, so this exact overflow shape still
    fabricated a confident 'inf' dollar figure.

    Round 10, BLOCKER 1: round 8 only refused a bucket that was present as
    a non-finite NUMBER (NaN/Infinity/-Infinity). A bucket present as any
    OTHER non-numeric value -- a string (e.g. an operator-hand-edited
    ledger row with `"output": "2000000"`), a list, a dict -- fell through
    the `else: amt = 0.0` branch and was silently zeroed, letting the rest
    of the row still price as a confident, understated "ground truth"
    figure. The rate side of the pricing table had the identical hole: a
    rate present in `pricing.json` as a string (a single hand-edit typo,
    e.g. `"cache_read": "0.3"` instead of `0.3`) or an explicit `null`
    silently zeroed that bucket's contribution instead of refusing the
    whole row. Both sides now distinguish "key genuinely absent" (still
    defaults to 0 -- correct, there is no data to refuse) from "key present
    but not a real, finite number" (refuses -- returns None -- because a
    malformed field is not the same as a missing one)."""
    if not isinstance(model, str) or not model:
        # Round 14, BLOCKER 2: `model` reaches this function from an
        # arbitrary, never-validated spend-ledger row (see resolve_cost's
        # own docstring) -- the old `if not model` check alone lets a
        # non-empty dict/list/set through (truthy), and `.get(model)`
        # immediately below HASHES its key, raising `TypeError: unhashable
        # type` and breaking this function's own documented "never raises"
        # contract. Refuse any non-string model exactly like an
        # empty/missing one, mirroring the isinstance(str) guard
        # `agent_type` already uses at its own dict-key/membership-test
        # call sites in resolve_cost().
        return None
    rates = _safe_dict(_safe_dict(pricing).get("per_million_tokens")).get(model)
    if not isinstance(rates, dict):
        return None
    if not isinstance(tokens, dict) or not tokens:
        return None
    if not any(is_finite_number(tokens.get(key)) for key in ("input", "output", "cache_read", "cache_creation")):
        return None
    total = 0.0
    for key in ("input", "output", "cache_read", "cache_creation"):
        amt_present = key in tokens
        amt_raw = tokens.get(key, 0)
        if amt_raw is None:
            amt = 0.0
        elif isinstance(amt_raw, (int, float)) and not isinstance(amt_raw, bool):
            if not is_finite_number(amt_raw):
                # Present as a real number, but not finite -- unpriceable,
                # never silently zeroed (round 8, BLOCKER 1).
                return None
            amt = float(amt_raw)
        elif amt_present:
            # Present, but not a real number at all (a string, list,
            # dict...) -- unpriceable, never silently zeroed (round 10,
            # BLOCKER 1).
            return None
        else:
            amt = 0.0
        rate_present = key in rates
        rate_raw = rates.get(key, 0)
        if is_finite_number(rate_raw):
            rate = float(rate_raw)
        elif rate_present:
            # Rate present in the pricing table, but not a real finite
            # number -- a string typo (e.g. `"cache_read": "0.3"`),
            # NaN/Infinity, OR an explicit `null` (round 12, BLOCKER 4: an
            # explicit `null` used to fall through to `rate = 0.0` here,
            # silently zeroing that bucket's contribution instead of
            # refusing the whole row -- the exact same understatement class
            # already fixed for a string-typo rate in round 10, just via
            # `None` instead of a string. `rates.get(key, 0)` only ever
            # returns `None` when the key IS present with an explicit
            # `null` value -- a genuinely absent key defaults to `0`
            # instead, which correctly falls through to the `else` branch
            # below, not here) -- unpriceable, never silently zeroed.
            return None
        else:
            rate = 0.0
        total += (amt * rate) / 1_000_000.0
    if not is_finite_number(total):
        return None
    return total


def reject_non_finite_json_constant(name: str) -> Any:
    """`json.loads`/`json.load`'s `parse_constant` hook: called instead of a
    normal numeric parse for the bare tokens `NaN` / `Infinity` /
    `-Infinity`, which Python's json module accepts by default even though
    none of them is valid JSON. Raising here makes the enclosing
    `json.load(s)` raise too, so a line/file carrying one is skipped by the
    caller's existing malformed-input handling -- exactly the same
    treatment as any other malformed input, never a value that quietly
    becomes a non-finite float (BLOCKER 7: a NaN/Infinity value both
    crashes one code path and fabricates a confident "$inf" figure in
    another; rejecting it at the JSON-parsing boundary itself closes both
    without teaching every downstream reader about this one input shape).

    Round 8, BLOCKER 1: exposed WITHOUT a leading underscore, and applied
    to EVERY json.load(s) call in this module that parses a cycle record or
    the pricing table (read_cycle, read_cycles, _load_record_file,
    load_pricing) -- not just read_ledger_rows's own call, which is the
    only one round 6 actually guarded -- and to render_cycle_log.py's own
    separate `load_cycle_records` parse, its structurally identical mirror
    in the other file."""
    raise ValueError(f"non-finite JSON constant: {name}")


# Internal alias, kept for the docstrings above that already reference the
# old private name.
_reject_non_finite_json_constant = reject_non_finite_json_constant


def reject_non_finite_json_float(text: str) -> float:
    """`json.loads`/`json.load`'s `parse_float` hook -- the SIBLING guard
    `reject_non_finite_json_constant` above is missing (round 10, BLOCKER
    4). `parse_constant` only ever fires for the three bare literal tokens
    `NaN` / `Infinity` / `-Infinity`; it does NOT fire for an ordinary-
    looking numeric literal like `1e999` that OVERFLOWS to +/-inf during
    Python's own `float()` conversion -- that is a normal float parse, not
    a "constant" in the JSON spec's sense, so `json.loads('{"total_usd":
    1e999}')` silently yields `inf` without ever calling `parse_constant`.
    Every downstream reader of this data happens to catch that via an
    `is_finite_number()` check somewhere -- but relying on every future
    call site to remember that is exactly the "teach every downstream
    reader" trap `parse_constant` above was built to avoid; the actual fix
    is closing the SAME parse boundary for BOTH shapes a non-finite value
    can arrive by (a literal token, or an overflowing literal).

    Parses the text exactly as `float()` would, then raises if the result
    isn't finite -- same contract as `reject_non_finite_json_constant`:
    the caller's existing malformed-input handling (a skipped line, a
    rejected file, main()'s outer except) treats it exactly like any other
    malformed input, never a value that quietly becomes a non-finite
    float. Applied ALONGSIDE `parse_constant=` at every one of this
    module's json.load(s) call sites, plus render_cycle_log.py's own
    mirror parse."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON float literal: {text}")
    return value


def read_ledger_rows(ledger_path: str | None = None) -> list[dict]:
    """Read spend.jsonl, tolerating malformed/partial lines (skipped, never
    raised — a shared JSONL can be mid-append by another process). Missing
    file returns an empty list, since "the ledger doesn't exist yet" and "the
    ledger has nothing for you" are both honestly "no data", not an error.

    A line carrying a bare `NaN`/`Infinity`/`-Infinity` JSON constant is
    treated as malformed and skipped (BLOCKER 7) -- see
    _reject_non_finite_json_constant()."""
    path = SPEND_LEDGER if ledger_path is None else ledger_path
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line, parse_constant=_reject_non_finite_json_constant, parse_float=reject_non_finite_json_float)
                except Exception:
                    continue
                if isinstance(d, dict):
                    rows.append(d)
    except FileNotFoundError:
        return []
    return rows


IDENTITY_FIELDS = ("tool_use_id", "agent_id", "session")


def _dispatch_identity_counts(dispatches: list[dict], field: str) -> dict[str, int] | None:
    """Per-value counts of `field` (tool_use_id / agent_id / session) across
    every dispatch, ONLY if every single dispatch carries a non-empty string
    for it (full/uniform coverage). This is the STRONGEST case: `field`
    alone is sufficient to narrow ledger candidates down to exactly this
    cycle's rows. Returns None on any partial/absent coverage -- see
    _declared_identity_counts() for the partial-coverage mismatch check that
    runs regardless of whether coverage is uniform (BLOCKER 2, round 3)."""
    counts: dict[str, int] = {}
    for d in dispatches:
        if not isinstance(d, dict):
            return None
        v = d.get(field)
        if not isinstance(v, str) or not v:
            return None
        counts[v] = counts.get(v, 0) + 1
    return counts


def _declared_identity_counts(dispatches: list[dict], field: str) -> dict[str, int]:
    """Per-value counts of `field` across only the dispatches that actually
    declare a non-empty string for it -- PARTIAL coverage included, unlike
    _dispatch_identity_counts() above. This exists to catch BLOCKER 2's exact
    defect: a dispatch that declares an identity the ledger cannot
    corroborate must refuse the whole cycle even when a sibling dispatch
    declares no identity at all -- a declared-but-unmatched identity is
    POSITIVE EVIDENCE of non-correspondence, never something a sibling's
    silence should be allowed to override. Called independently for every
    field, before deciding whether any field has full/uniform coverage."""
    counts: dict[str, int] = {}
    for d in dispatches:
        if not isinstance(d, dict):
            continue
        v = d.get(field)
        if isinstance(v, str) and v:
            counts[v] = counts.get(v, 0) + 1
    return counts


def resolve_cost(
    cycle: dict,
    *,
    ledger_path: str | None = None,
    pricing_path: str | None = None,
    tolerance_sec: float = DEFAULT_LEDGER_TOLERANCE_SEC,
) -> dict[str, Any]:
    """Attribute real spend-ledger rows to `cycle`, or honestly refuse.

    Correspondence is checked on FOUR signals, matching the cycle's own
    dispatches list exactly:
      1. time window  — ledger rows must fall within
         [started_at - tolerance, ended_at + tolerance];
      2. agent-type set — a row's agent_type must be one the cycle actually
         dispatched;
      3. per-type row count — the number of matching ledger rows for each
         agent_type must equal the number of dispatches of that type the
         cycle recorded; any mismatch is refused rather than guessed at.
      4. IDENTITY — REQUIRED for a "spend_ledger" verdict (round-3 redesign;
         see "DESIGN DECISION" below). A dispatch may carry the ledger's own
         tool_use_id / agent_id / session field (see OPTIONAL_DISPATCH_KEYS).

         4a. Any dispatch that DOES declare an identity value in ANY of the
             three fields must correspond 1:1 to matching ledger rows —
             checked independently per field, per declared value, BEFORE
             anything else. A declared-but-unmatched identity refuses the
             WHOLE cycle immediately, even when a sibling dispatch declared
             no identity at all (BLOCKER 2: partial declaration can only
             make the result MORE strict, never fall back to weaker
             window+type+count matching).
         4b. Once no declared identity is found to mismatch, resolve_cost
             requires FULL, uniform coverage of one identity field across
             EVERY dispatch in the cycle to actually narrow candidates and
             return "spend_ledger". Uniform coverage is checked in
             precedence order tool_use_id > agent_id > session (the more
             specific field wins when more than one is uniformly present).

             HONEST CAVEAT (round 4): the three fields are not equally
             strong. Only tool_use_id is genuinely CYCLE-unique (one
             dispatch, one tool call). agent_id and, coarsest of all,
             session only establish that the matched ledger rows came from
             the SAME session as this cycle's dispatches — not that they
             came from THIS cycle specifically. A session can run more than
             one cycle; session-tier identity cannot distinguish between
             them. It still closes the actual incident this redesign exists
             for (a FOREIGN session's spend never gets attributed), but a
             caller reading "spend_ledger" attributed via session-tier
             identity should not read that as cycle-level proof the way a
             tool_use_id match is.
         4c. If NO dispatch in the cycle declares ANY identity field at all
             (or coverage never reaches uniform on any one field), resolve_cost
             REFUSES outright — it no longer accepts a heuristic "the
             window+type+count candidates all happen to share one session"
             fallback (BLOCKER 1, round 3: measured on the real ledger, 48%
             of rows carry session: null, which silently emptied that old
             guard regardless of true ambiguity — and even on a clean
             ledger, a single FOREIGN session is mathematically
             indistinguishable from a single OWN session under
             window+type+count alone, so accepting it was never actually
             safe, populated ledger or not).

    DESIGN DECISION (BLOCKER 1, round 3 — option (a) chosen over labelling an
    unverified guess as a lesser "inferred" source): window+type+count alone
    can never establish TRUE correspondence, only a plausible one, yet every
    existing and future caller of resolve_cost() already treats a
    "spend_ledger" verdict as ground truth (see the module docstring's cost
    rules and render_cycle_log.py's cost_provenance_line, which renders it
    as literally "ground truth"). Weakening what "spend_ledger" means (option
    b) would make that existing trust wrong for every future caller, silently,
    forever. Requiring identity declaration instead keeps "spend_ledger"
    meaning what it has always meant, and pushes the actual fix to where it
    belongs — dispatch instrumentation echoing the ledger's own tool_use_id
    (already wired as an OPTIONAL field in schema v2) — rather than adding a
    permanently-lesser trust tier every downstream reader must now also
    special-case. No caller was found that requires the old heuristic-only
    acceptance path; if one is found later, it should declare identity, not
    receive a silently-weaker "spend_ledger".

    A cycle whose dispatches never show up in the ledger at all (a real,
    expected case — see the module docstring) resolves to source
    "unavailable" with a "reason", not a crash and not a fabricated total.
    A dispatch that declares an identity field as an EMPTY STRING (a data
    defect, not "no identity" — see BLOCKER 2's second door) also refuses
    outright with a reason naming the offending field, rather than silently
    treating the blank as absent; validate_cycle() rejects this at write
    time too, but resolve_cost() guards it independently since it is called
    on raw, possibly-unvalidated JSON (e.g. the CLI's resolve-cost
    subcommand never calls validate_cycle first).

    `tolerance_sec` is bounded to [MIN_LEDGER_TOLERANCE_SEC,
    MAX_LEDGER_TOLERANCE_SEC] — an unbounded or negative tolerance directly
    widens the risk this function exists to close, so it is refused (as
    "unavailable", never raised) rather than silently honoured.
    """
    if not (MIN_LEDGER_TOLERANCE_SEC <= tolerance_sec <= MAX_LEDGER_TOLERANCE_SEC):
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": (
                f"tolerance_sec must be between {MIN_LEDGER_TOLERANCE_SEC} and "
                f"{MAX_LEDGER_TOLERANCE_SEC} seconds, got {tolerance_sec!r}"
            ),
        }

    # BLOCKER 5 (round 6): `3 or []` is truthy (a nonzero int is truthy),
    # so a scalar `dispatches` (e.g. a hand-edited record with
    # dispatches: 3) used to reach `enumerate(dispatches)` below unguarded
    # and raise TypeError: 'int' object is not iterable -- resolve_cost()'s
    # own docstring promises this function never raises. _safe_list()
    # treats anything that isn't already a list as absent, same as "zero
    # dispatches recorded".
    dispatches = _safe_list(cycle.get("dispatches"))
    if not dispatches:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": "cycle recorded zero dispatches; nothing to attribute cost to",
        }

    # BLOCKER 2 (round 3), second door: an empty-string identity is a DATA
    # DEFECT, never "no identity declared". validate_cycle() now rejects this
    # at write time, but resolve_cost() is also called directly on raw,
    # possibly-unvalidated JSON (the CLI's resolve-cost subcommand never
    # calls validate_cycle first) -- guard it here too rather than letting a
    # blank silently read as absent and discard a sibling dispatch's real
    # identity.
    for i, d in enumerate(dispatches):
        if not isinstance(d, dict):
            continue
        for field in IDENTITY_FIELDS:
            if isinstance(d.get(field), str) and d.get(field) == "":
                return {
                    "source": "unavailable",
                    "total_tokens": None,
                    "total_usd": None,
                    "reason": (
                        f"dispatches[{i}].{field} is an empty string -- an empty identity is a "
                        "data defect, not 'no identity declared'; this record was never "
                        "validated (validate_cycle()/write_cycle() reject this) -- fix the "
                        "record rather than resolving cost against it"
                    ),
                }

    started_raw = cycle.get("started_at")
    ended_raw = cycle.get("ended_at")
    if not ended_raw:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": "cycle has no ended_at yet (still in progress); cannot bound a ledger window",
        }

    start_dt = _parse_iso8601z(started_raw) if started_raw else None
    end_dt = _parse_iso8601z(ended_raw)
    if start_dt is None or end_dt is None:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": "started_at/ended_at is not a parseable ISO8601 'Z' timestamp",
        }

    window_start = start_dt - timedelta(seconds=tolerance_sec)
    window_end = end_dt + timedelta(seconds=tolerance_sec)

    expected_counts: dict[str, int] = {}
    for d in dispatches:
        at = d.get("agent_type") if isinstance(d, dict) else None
        # Round 8, BLOCKER 2: `at` was only checked for truthiness before
        # being used as a dict key -- a dict/list agent_type (a realistic
        # malformed field) is truthy when non-empty and crashes
        # `expected_counts[at]` with `TypeError: unhashable type`. This is
        # the EXACT MIRROR of the ledger-row side's `row_agent_type` check
        # a few lines below (already correctly `isinstance(..., str)`
        # guarded, with 3 dedicated tests) -- round 6/an earlier round fixed
        # that side and never checked the dispatch side of this same
        # function for the identical hazard.
        if isinstance(at, str) and at:
            expected_counts[at] = expected_counts.get(at, 0) + 1
    if not expected_counts:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": "no dispatch in this cycle carries an agent_type; nothing to match in the ledger",
        }
    expected_types = set(expected_counts)

    rows = read_ledger_rows(ledger_path)
    candidates = []
    for row in rows:
        ts = _parse_iso8601z(row.get("ts"))
        if ts is None or not (window_start <= ts <= window_end):
            continue
        row_agent_type = row.get("agent_type")
        if not isinstance(row_agent_type, str) or row_agent_type not in expected_types:
            continue
        candidates.append(row)

    window_meta = {
        "start": started_raw,
        "end": ended_raw,
        "tolerance_sec": float(tolerance_sec),
    }

    if not candidates:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": (
                "no ledger rows found inside the cycle window for its dispatched "
                f"agent_type(s) {sorted(expected_types)} -- this run's spend may "
                "not be in the ledger at all"
            ),
            "window": window_meta,
        }

    # Identity resolution (signal 4, round-3 redesign -- see resolve_cost's
    # own docstring "DESIGN DECISION" section for the full rationale).
    #
    # Step 4a (BLOCKER 2): check EVERY identity field independently for a
    # PARTIAL-coverage mismatch first, before deciding whether any field has
    # full/uniform coverage. A declared-but-unmatched identity refuses the
    # whole cycle immediately -- this must run even when no field ever
    # reaches uniform coverage, so a sibling dispatch's silence can never
    # discard another dispatch's real mismatch signal.
    for field in IDENTITY_FIELDS:
        declared_counts = _declared_identity_counts(dispatches, field)
        if not declared_counts:
            continue
        found_counts: dict[str, int] = {}
        for row in candidates:
            v = row.get(field)
            if isinstance(v, str) and v in declared_counts:
                found_counts[v] = found_counts.get(v, 0) + 1
        identity_mismatches = {
            v: {"expected": declared_counts[v], "found": found_counts.get(v, 0)}
            for v in declared_counts
            if found_counts.get(v, 0) != declared_counts[v]
        }
        if identity_mismatches:
            return {
                "source": "unavailable",
                "total_tokens": None,
                "total_usd": None,
                "reason": (
                    f"this cycle declared dispatch {field!r} identities that do not correspond "
                    f"1:1 to ledger rows in window ({identity_mismatches}) -- a declared identity "
                    "the ledger cannot corroborate is refused outright, even when another "
                    "dispatch in this cycle declared no identity at all"
                ),
                "window": window_meta,
            }

    # Step 4b/4c (BLOCKER 1): only a FULL, uniform identity field across
    # every dispatch is sufficient to narrow candidates and return
    # "spend_ledger" -- there is no more "no identity, but the candidates
    # all happen to share one session" fallback (see the docstring's DESIGN
    # DECISION). Precedence: the more specific field wins when more than one
    # is uniformly present.
    identity_field: str | None = None
    identity_counts: dict[str, int] | None = None
    for field in IDENTITY_FIELDS:
        counts = _dispatch_identity_counts(dispatches, field)
        if counts:
            identity_field, identity_counts = field, counts
            break

    if identity_field is None or identity_counts is None:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": (
                "no dispatch in this cycle uniformly declares an identity field "
                f"({'/'.join(IDENTITY_FIELDS)}) -- window+type+count alone cannot prove true "
                "correspondence to ledger rows (a single foreign session is mathematically "
                "indistinguishable from a single own session under that heuristic), so "
                "resolve_cost refuses rather than guess which rows belong to this cycle"
            ),
            "window": window_meta,
        }

    # Step 4a already proved every declared value of `identity_field` (being
    # uniformly declared, it was checked above too) matches exactly, so this
    # narrowing is exact, not another chance to diverge.
    candidates = [
        row
        for row in candidates
        if isinstance(row.get(identity_field), str) and row.get(identity_field) in identity_counts
    ]

    candidate_counts: dict[str, int] = {}
    for row in candidates:
        at = row["agent_type"]
        candidate_counts[at] = candidate_counts.get(at, 0) + 1

    mismatches = {
        at: {"expected": expected_counts[at], "found": candidate_counts.get(at, 0)}
        for at in expected_types
        if candidate_counts.get(at, 0) != expected_counts[at]
    }
    if mismatches:
        return {
            "source": "unavailable",
            "total_tokens": None,
            "total_usd": None,
            "reason": (
                "ledger row count does not match this cycle's own dispatch count "
                f"for at least one agent_type ({mismatches}) -- refusing to guess "
                "which rows belong to this cycle"
            ),
            "window": window_meta,
        }

    pricing = load_pricing(pricing_path)
    total_tokens = 0
    total_usd = 0.0
    unpriced_models: set[str] = set()
    missing_tokens_total = False
    for row in candidates:
        tt = row.get("tokens_total")
        if _is_number(tt):
            total_tokens += int(tt)
        else:
            missing_tokens_total = True
        model = row.get("model")
        if not isinstance(model, str):
            # Round 14, BLOCKER 2 (second door): `label = model if model
            # else "..."` below is truthy for a non-empty dict/list, and
            # unpriced_models is a set() -- adding an unhashable label
            # raises TypeError, breaking resolve_cost's own "never raises"
            # contract EVEN when price_tokens() itself has already been
            # hardened against the identical malformed value (confirmed:
            # monkeypatching price_tokens to always return None still hits
            # this crash, since it is unreachable from inside that
            # function). `row.get("model")` comes from an arbitrary,
            # never-validated spend-ledger row, so treat any non-string
            # value the same as "no model recorded" here too, mirroring
            # price_tokens's own isinstance(str) guard above.
            model = None
        tokens = row.get("tokens") if isinstance(row.get("tokens"), dict) else None
        priced = price_tokens(tokens, model, pricing) if tokens is not None else None
        if priced is None:
            label = model if model else "(no model recorded)"
            if not (isinstance(tokens, dict) and tokens):
                label = f"{label} (row has no token data at all)"
            unpriced_models.add(label)
        else:
            total_usd += priced

    # Round 8, BLOCKER 1: finiteness is asserted on the ACCUMULATED total
    # here too, not just on each row -- price_tokens() already refuses (via
    # returning None) any row whose OWN total overflows, but each
    # individual row's priced figure can still be a large-but-finite value
    # that only overflows to +/-inf once summed ACROSS many rows. Without
    # this check, a cycle whose every row prices as finite could still
    # resolve to a confident "$inf ... ground truth" total_usd.
    total_overflowed = not unpriced_models and not is_finite_number(total_usd)

    result: dict[str, Any] = {
        "source": "spend_ledger",
        "total_tokens": None if missing_tokens_total else total_tokens,
        "total_usd": None if (unpriced_models or total_overflowed) else round(total_usd, 6),
        "matched_rows": len(candidates),
        "window": window_meta,
    }
    reasons: list[str] = []
    if unpriced_models:
        result["unpriced_models"] = sorted(unpriced_models)
        reasons.append(
            "total_usd is withheld because at least one matched row could not be priced "
            "(unknown/unpriced model, or the row carries no token data at all)"
        )
    if total_overflowed:
        reasons.append(
            "total_usd is withheld because the accumulated total overflowed to a non-finite "
            "value even though every individual matched row priced as finite"
        )
    if missing_tokens_total:
        reasons.append(
            "total_tokens is withheld because at least one matched row has a missing or "
            "non-numeric tokens_total"
        )
    if reasons:
        result["reason"] = " | ".join(reasons)
    return result


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

_HELP_TEXT = """cycle_telemetry — repo-agnostic self-correcting-loop cycle telemetry.

Usage:
  cycle_telemetry.py validate <path> [<path> ...]
  cycle_telemetry.py validate --system SYSTEM [--cycles-dir DIR]
  cycle_telemetry.py validate --all [--cycles-dir DIR]
  cycle_telemetry.py summarize [--system SYSTEM] [--cycles-dir DIR] [--json]
  cycle_telemetry.py metrics <path> [--json]
  cycle_telemetry.py metrics --system SYSTEM [--cycles-dir DIR] [--json]
  cycle_telemetry.py resolve-cost <path> [--ledger PATH] [--pricing PATH]
                                   [--tolerance-sec N] [--write] [--json]

validate   exit 0 if every record is schema-valid, else 1.
metrics    a single <path> prints that cycle's own metrics; --system prints
           the metrics pooled across every cycle recorded for that system.
resolve-cost  attributes real ledger spend to one cycle file; --write persists
              the result into that file's "cost" field (validated on write).
              exit 0 = resolved, 3 = honestly unavailable, 2 = usage error.
"""


class ArgError(Exception):
    pass


def _load_record_file(path: str) -> Any:
    """Load one raw JSON record file for the CLI. Returns whatever the
    top-level JSON value actually is -- a bare list/number/string is
    handed straight back too (this is the SAME shape read_cycles() rejects
    via its own isinstance(parsed, dict) check for the --system path;
    every single-file CLI caller of this function must apply the identical
    check itself -- see _cmd_metrics/_cmd_resolve_cost, round 8 BLOCKER 3).
    A bare NaN/Infinity/-Infinity JSON constant is rejected at the parse
    boundary like every other json.load(s) call in this module."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_constant=reject_non_finite_json_constant, parse_float=reject_non_finite_json_float)


def _fmt_metric(value: Any) -> str:
    """Round 10, BLOCKER 4: this used to format ANY float with `f"{value:.4f}"`
    -- Python's own format spec happily renders a non-finite float as the
    literal text `inf`/`nan`/`-inf`, so a metric that reached here as
    +/-inf (e.g. `summarize`'s per-row cost, `metrics`' plant-catch rates)
    printed a bare 'inf' on the operator's terminal with no indication it
    was ever anything other than a real number. Every OTHER numeric
    formatter in this file/its sibling renderer already refuses a
    non-finite value with a clear placeholder (`is_finite_number`'s own
    stated purpose) -- this was the one CLI-facing formatter that didn't."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if not is_finite_number(value):
            return "invalid data"
        return f"{value:.4f}"
    return json.dumps(value, allow_nan=False)


def _cmd_validate(argv: list[str]) -> int:
    paths: list[str] = []
    system: str | None = None
    all_systems = False
    cycles_dir: str | None = None
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--system":
            i += 1
            if i >= len(argv):
                raise ArgError("--system needs a value")
            system = argv[i]
        elif a == "--all":
            all_systems = True
        elif a == "--cycles-dir":
            i += 1
            if i >= len(argv):
                raise ArgError("--cycles-dir needs a value")
            cycles_dir = argv[i]
        elif a == "--json":
            as_json = True
        elif a.startswith("--"):
            raise ArgError(f"unknown option {a!r}")
        else:
            paths.append(a)
        i += 1

    targets: list[tuple[str, Any]] = []
    if paths:
        for p in paths:
            try:
                targets.append((p, _load_record_file(p)))
            except Exception as exc:
                targets.append((p, exc))
    elif system is not None or all_systems:
        # Round 10, BLOCKER 5: iter_cycle_paths() raises a bare ValueError
        # for an unsafe/malformed --system slug (via _require_safe_component)
        # -- a CLI-supplied bad argument is a USAGE error (this module's own
        # documented contract: exit 2), not the "something failed while
        # reading a file" class main()'s outer except handler treats as
        # exit 1. Translated to ArgError at the one place a raw --system
        # value first reaches a raising call, rather than widening main()'s
        # catch-all to also swallow ValueError from callers that legitimately
        # want it as a data error.
        try:
            paths_to_check = iter_cycle_paths(system, cycles_dir=cycles_dir)
        except ValueError as exc:
            raise ArgError(str(exc)) from exc
        for p in paths_to_check:
            try:
                targets.append((p, _load_record_file(p)))
            except Exception as exc:
                targets.append((p, exc))
    else:
        raise ArgError("validate needs a path, --system SYSTEM, or --all")

    results = []
    ok = True
    for path, record in targets:
        if isinstance(record, Exception):
            results.append({"path": path, "valid": False, "errors": [str(record)]})
            ok = False
            continue
        errs = validate_cycle(record)
        results.append({"path": path, "valid": not errs, "errors": errs})
        if errs:
            ok = False

    if as_json:
        print(json.dumps(results, indent=2, sort_keys=True, allow_nan=False))
    else:
        for r in results:
            status = "PASS" if r["valid"] else "FAIL"
            print(f"{status}  {r['path']}")
            for e in r["errors"]:
                print(f"       - {e}")
    return 0 if ok else 1


def _cmd_summarize(argv: list[str]) -> int:
    system: str | None = None
    cycles_dir: str | None = None
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--system":
            i += 1
            if i >= len(argv):
                raise ArgError("--system needs a value")
            system = argv[i]
        elif a == "--cycles-dir":
            i += 1
            if i >= len(argv):
                raise ArgError("--cycles-dir needs a value")
            cycles_dir = argv[i]
        elif a == "--json":
            as_json = True
        else:
            raise ArgError(f"unknown argument {a!r}")
        i += 1

    # Round 10, BLOCKER 5: see the matching comment in _cmd_validate --
    # a bad --system slug is a USAGE error (exit 2), not a data/IO error.
    try:
        records = read_cycles(system, cycles_dir=cycles_dir, on_error="skip")
    except ValueError as exc:
        raise ArgError(str(exc)) from exc
    rows = []
    for r in records:
        cost = _safe_dict(r.get("cost"))
        rows.append(
            {
                "system": r.get("system"),
                "cycle_id": r.get("cycle_id"),
                "started_at": r.get("started_at"),
                "ended_at": r.get("ended_at"),
                "dispatch_count": len(_safe_list(r.get("dispatches"))),
                "finding_count": len(_safe_list(r.get("findings"))),
                "cost_source": cost.get("source"),
                "total_usd": cost.get("total_usd"),
            }
        )

    if as_json:
        # Round 10, BLOCKER 4: `allow_nan=False` makes json.dumps refuse to
        # silently emit the invalid-JSON `Infinity`/`NaN` tokens for a
        # non-finite value that reached here -- the parse boundary above
        # already rejects those on the way IN (reject_non_finite_json_float/
        # _constant), so this is defense in depth for any value that
        # arrives some other way, not a path exercised in normal operation.
        try:
            print(json.dumps(rows, indent=2, sort_keys=True, allow_nan=False))
        except ValueError as exc:
            print(f"cycle_telemetry summarize: {exc}", file=sys.stderr)
            return 1
        return 0
    if not rows:
        print("(no cycle records found)")
        return 0
    for row in rows:
        print(
            f"{row['system']}/{row['cycle_id']}  "
            f"dispatches={row['dispatch_count']} findings={row['finding_count']} "
            f"cost={row['cost_source']}:{_fmt_metric(row['total_usd'])}"
        )
    return 0


def _cmd_metrics(argv: list[str]) -> int:
    path: str | None = None
    system: str | None = None
    cycles_dir: str | None = None
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--system":
            i += 1
            if i >= len(argv):
                raise ArgError("--system needs a value")
            system = argv[i]
        elif a == "--cycles-dir":
            i += 1
            if i >= len(argv):
                raise ArgError("--cycles-dir needs a value")
            cycles_dir = argv[i]
        elif a == "--json":
            as_json = True
        elif a.startswith("--"):
            raise ArgError(f"unknown option {a!r}")
        else:
            path = a
        i += 1

    if path is not None:
        # BLOCKER 8 (round 6): mirror _cmd_validate's per-file try/except --
        # a non-UTF-8 file raises UnicodeDecodeError (a ValueError subclass,
        # NOT an OSError) from `_load_record_file`'s plain `open(...,
        # encoding="utf-8")`, which used to escape uncaught all the way out
        # of main() as a raw traceback instead of a clean per-file message.
        try:
            record = _load_record_file(path)
        except Exception as exc:
            print(f"cycle_telemetry metrics: failed to read {path}: {exc}", file=sys.stderr)
            return 1
        # Round 8, BLOCKER 3: mirror the identical guard round 6 added to
        # read_cycles()'s --system (multi-file) path -- a bare top-level
        # list/number/string reaches compute_metrics()'s `.get()` calls
        # unguarded and raises AttributeError here, since this single-file
        # path never went through read_cycles() at all.
        if not isinstance(record, dict):
            print(
                f"cycle_telemetry metrics: {path} is not a JSON object "
                f"(got {type(record).__name__})",
                file=sys.stderr,
            )
            return 1
        metrics = compute_metrics(record)
    elif system is not None:
        # Round 10, BLOCKER 5: see the matching comment in _cmd_validate --
        # a bad --system slug is a USAGE error (exit 2), not a data/IO error.
        try:
            records = read_cycles(system, cycles_dir=cycles_dir, on_error="skip")
        except ValueError as exc:
            raise ArgError(str(exc)) from exc
        metrics = aggregate_metrics(records)
    else:
        raise ArgError("metrics needs a path or --system SYSTEM")

    if as_json:
        # Round 10, BLOCKER 4: see the matching comment in _cmd_summarize --
        # `allow_nan=False` is defense in depth; the parse boundary and the
        # aggregate_metrics()/usd_per_confirmed_defect() finiteness guards
        # already keep a non-finite value from reaching here in normal use.
        try:
            print(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False))
        except ValueError as exc:
            print(f"cycle_telemetry metrics: {exc}", file=sys.stderr)
            return 1
    else:
        for key, value in metrics.items():
            if key == "plant_catch_by_slot":
                print(f"{key}:")
                for slot, counts in value.items():
                    print(
                        f"  slot {slot}: caught={counts['caught']} missed={counts['missed']} "
                        f"rate={_fmt_metric(counts['rate'])}"
                    )
            elif key == "plant_catch_by_trade":
                print(f"{key}:")
                for trade, counts in value.items():
                    print(
                        f"  trade {trade}: caught={counts['caught']} missed={counts['missed']} "
                        f"unreadable={counts['unreadable']} rate={_fmt_metric(counts['rate'])}"
                    )
            elif key == "false_alarm_by_trade":
                print(f"{key}:")
                for trade, counts in value.items():
                    print(
                        f"  trade {trade}: controls={counts['controls']} "
                        f"false_alarms={counts['false_alarms']} unreadable={counts['unreadable']} "
                        f"rate={_fmt_metric(counts['rate'])}"
                    )
            else:
                print(f"{key}: {_fmt_metric(value)}")
    return 0


def _cmd_resolve_cost(argv: list[str]) -> int:
    path: str | None = None
    ledger_path: str | None = None
    pricing_path: str | None = None
    tolerance_sec = DEFAULT_LEDGER_TOLERANCE_SEC
    write = False
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ledger":
            i += 1
            if i >= len(argv):
                raise ArgError("--ledger needs a value")
            ledger_path = argv[i]
        elif a == "--pricing":
            i += 1
            if i >= len(argv):
                raise ArgError("--pricing needs a value")
            pricing_path = argv[i]
        elif a == "--tolerance-sec":
            i += 1
            if i >= len(argv):
                raise ArgError("--tolerance-sec needs a value")
            try:
                tolerance_sec = float(argv[i])
            except Exception as exc:
                raise ArgError(f"--tolerance-sec needs a number, got {argv[i]!r}") from exc
            if not (MIN_LEDGER_TOLERANCE_SEC <= tolerance_sec <= MAX_LEDGER_TOLERANCE_SEC):
                raise ArgError(
                    f"--tolerance-sec must be between {MIN_LEDGER_TOLERANCE_SEC} and "
                    f"{MAX_LEDGER_TOLERANCE_SEC}, got {tolerance_sec!r}"
                )
        elif a == "--write":
            write = True
        elif a == "--json":
            as_json = True
        elif a.startswith("--"):
            raise ArgError(f"unknown option {a!r}")
        else:
            path = a
        i += 1

    if path is None:
        raise ArgError("resolve-cost needs a <path>")

    # BLOCKER 8 (round 6): same fix as _cmd_metrics -- a non-UTF-8 file used
    # to raise an uncaught UnicodeDecodeError here.
    try:
        cycle = _load_record_file(path)
    except Exception as exc:
        print(f"cycle_telemetry resolve-cost: failed to read {path}: {exc}", file=sys.stderr)
        return 1
    # Round 8, BLOCKER 3: identical guard to _cmd_metrics's -- a bare
    # top-level list/number/string reaches resolve_cost()'s `.get()` calls
    # (and, with --write, `cycle["cost"] = result`) unguarded.
    if not isinstance(cycle, dict):
        print(
            f"cycle_telemetry resolve-cost: {path} is not a JSON object "
            f"(got {type(cycle).__name__})",
            file=sys.stderr,
        )
        return 1
    result = resolve_cost(
        cycle, ledger_path=ledger_path, pricing_path=pricing_path, tolerance_sec=tolerance_sec
    )

    if write:
        cycle["cost"] = result
        assert_valid_cycle(cycle)
        # BLOCKER 3 (round 4): write atomically (temp file + os.replace),
        # the same pattern write_cycle() already uses at ~:1195-1199. A
        # non-atomic in-place write left a truncated/invalid-UTF-8 file on
        # disk if the process was killed mid-write (e.g. on a multibyte
        # character) -- exactly the input that broke the whole render page
        # in render_cycle_log.py before that side of this fix landed.
        tmp_path = f"{path}.tmp-{os.getpid()}-{int(time.time() * 1000)}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(cycle, fh, indent=2, sort_keys=True, allow_nan=False)
                fh.write("\n")
            os.replace(tmp_path, path)
        finally:
            # Round 12, nit #7: same orphaned-temp-file cleanup as
            # write_cycle()'s matching atomic-write pattern above.
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if as_json:
        # Round 10, BLOCKER 4: see the matching comment in _cmd_summarize --
        # `allow_nan=False` is defense in depth; resolve_cost()'s own
        # accumulated-finiteness guard already keeps a non-finite total_usd
        # from reaching here in normal use.
        try:
            print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        except ValueError as exc:
            print(f"cycle_telemetry resolve-cost: {exc}", file=sys.stderr)
            return 1
    else:
        print(f"source: {result['source']}")
        print(f"total_tokens: {_fmt_metric(result.get('total_tokens'))}")
        print(f"total_usd: {_fmt_metric(result.get('total_usd'))}")
        if result.get("reason"):
            print(f"reason: {result['reason']}")

    return 0 if result["source"] != "unavailable" else 3


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv or raw_argv[0] in ("--help", "-h", "help"):
        print(_HELP_TEXT)
        return 0

    cmd, rest = raw_argv[0], raw_argv[1:]
    handlers = {
        "validate": _cmd_validate,
        "summarize": _cmd_summarize,
        "metrics": _cmd_metrics,
        "resolve-cost": _cmd_resolve_cost,
    }
    handler = handlers.get(cmd)
    if handler is None:
        print(f"cycle_telemetry: unknown subcommand {cmd!r}", file=sys.stderr)
        print(_HELP_TEXT, file=sys.stderr)
        return 2
    try:
        return handler(rest)
    except ArgError as exc:
        print(f"cycle_telemetry {cmd}: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is a ValueError subclass, NOT an OSError --
        # BLOCKER 8 (round 6): a non-UTF-8 file used to escape this tuple
        # entirely and exit with a raw traceback. Widened here as the
        # outer safety net; _cmd_metrics/_cmd_resolve_cost also wrap their
        # own file loads directly (see there) for a clean per-file message
        # rather than relying on this catch-all alone.
        print(f"cycle_telemetry {cmd}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - thin CLI entry
    sys.exit(main())
