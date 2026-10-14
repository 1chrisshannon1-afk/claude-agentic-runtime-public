"""GTM mission convergence evaluator — GTM-CONV-01/02/03.

Mechanically decides whether a GTM (go-to-market marketing/sales department) mission's current
round has converged, by reading the dissent ledger the `marketing-director` agent writes (the
repo manifest's `gtm.missions_dir` (`python3 ~/.claude/scripts/repo_manifest.py get
gtm.missions_dir`), file `gtm_reviewed.jsonl`; schema documented in
`~/.claude/tools/gtm/MISSION_SCHEMA.md`) — never by trusting an agent's own claim of consensus.

**NOT the estimate loop's evaluator.** This module lives at `~/.claude/tools/gtm/exit_contract.py`
deliberately outside any product repo's own estimate-engine test tree — a product repo may carry
its own, separate ESTIMATE loop evaluator, with different semantics under the same-looking short
assertion names (bare `CONV-01`/`CONV-02`/`CONV-03`). Assertion identifiers in THIS module are
always the fully-qualified `GTM-CONV-01`, `GTM-CONV-02`, `GTM-CONV-03` — the bare `CONV-0N` form is
FORBIDDEN in every GTM-department artifact (module output, docstrings, test names) because an
estimate loop may already own that bare namespace with unrelated meaning in its own repo. Do not
reuse code from that module either; the two ledgers have different shapes and different
convergence rules.

## The three assertions

- **GTM-CONV-01** — zero blocker-severity DISTINCT RECURRING `cause_key`s in the window (window=1:
  just the current round). "Recurring" means the same `cause_key` appears as an open blocker-
  severity DISSENT in more than one round within the window; since the window is fixed at 1 for
  this evaluator, this reduces to: zero blocker-severity cause_keys with more than one open
  DISSENT row *for different artifact_id/judge pairs* inside the current round, OR — more simply
  and more usefully — zero blocker-severity OPEN dissents at all whose cause_key recurs across
  rounds up to and including the current one. See `_zero_recurring_blocker_causes` for the exact
  computation and the rationale for treating "recurring" as "seen as an open blocker in more than
  one round the ledger has data for, up to the current round."
- **GTM-CONV-02** — zero fix-caused regressions: no `(artifact_id, judge)` pair that recorded
  CONCUR in round N-1 has a NEW DISSENT recorded against it in round N.
- **GTM-CONV-03** — every mandated judge returned a verdict for every in-scope artifact in the
  current round, AND zero OPEN DISSENT pairs remain across the whole ledger for this mission (an
  open pair = a DISSENT with no LATER CONCUR for the same `(artifact_id, judge)` pair). This is
  the assertion the #4893-shaped bug (a DIFFERENT evaluator, for an estimate loop, once reported
  "3 of 3 met" over a ledger with 9 open dissents because it never read verdict fields) is named
  after — this evaluator MUST fail this leg whenever any open dissent exists, unconditionally.

## Failure semantics — UNEVALUABLE, never a silent "met"

A missing ledger file, an empty ledger file, a ledger containing any line that fails to parse
as valid JSON, is missing a required field, carries a DISSENT verdict with no resolvable
`evidence` field, carries a blocker-severity DISSENT with no `cause_key`, or — once parsed — has
ZERO rows for the requested `mission_id`, makes the WHOLE evaluation `UNEVALUABLE: <reason>` —
never a silent "met" for any assertion. This is the load-bearing anti-regression case this module
exists to prevent (see the #4893 class in `~/.claude/tools/gtm/MISSION_SCHEMA.md`).

## Mission isolation — the ledger is ONE SHARED FILE across every mission

`gtm_reviewed.jsonl` accumulates rows for every GTM mission the department has ever run, appended
in a single shared file (per `MISSION_SCHEMA.md`'s "Dissent ledger" section) — never one file per
mission. `evaluate()` therefore REQUIRES a `mission_id` argument and filters every row to that
mission_id immediately after parsing, before any assertion helper runs. `round`, `judge`, and
`artifact_id` are NOT globally unique across missions, so without this filter a wholly unrelated
concurrent or historical mission's rows could silently flip this mission's convergence verdict —
exactly the #4893 failure class this module exists to prevent, just via a different mechanism
(cross-mission contamination rather than ignoring verdict fields).

## Ledger path resolution (CLI only)

The CLI (`main`, below) takes the ledger path as `--ledger <path>`, never a positional argument
and never a hardcoded product-repo default. When `--ledger` is omitted, the CLI resolves it at
runtime by shelling out to `python3 ~/.claude/scripts/repo_manifest.py get gtm.missions_dir` (from
the caller's cwd) and appending `gtm_reviewed.jsonl` — never a literal path baked into this module.
A manifest-resolution failure (no manifest, no `gtm.missions_dir` key, cwd not inside a repo) is
fail-loud: the CLI prints the resolver's own stderr and exits non-zero rather than guessing a
path. `evaluate()` itself is unaffected by any of this — it always takes an explicit `ledger_path`
string and never resolves anything on its own; only `main()`'s argument parsing knows about the
manifest.

**Cwd independence (B1, 2026-09-09):** `repo_manifest.py get` already anchors a path-typed key
like `gtm.missions_dir` to the repo root, not the caller's cwd, before returning it — so the
resolved ledger path is correct regardless of which directory inside the repo the CLI is invoked
from. `_resolve_default_ledger_path` additionally re-anchors the returned value itself to `git
rev-parse --show-toplevel` if it is ever not already absolute, as a belt-and-braces guard against
a caller whose resolver path returns a still-relative value.

## Exit codes (CLI only; `evaluate()` itself never exits the process)

- **0** — the ledger was evaluated. This is returned regardless of how many of the 3 assertions
  were met — check the printed `GTM convergence: N of 3 assertions met` line for the actual
  verdict; exit 0 is "the evaluator ran," never "convergence was reached."
- **2** — `UNEVALUABLE`: the ledger was missing, empty, contained a malformed line, or held zero
  rows for the given `--mission-id`. The reason is printed to stdout (as `UNEVALUABLE: <reason>`,
  same as always) AND to stderr, so an un-evaluable verdict can never be mistaken for success by a
  caller that only checks the exit status.
- **3** — resolver/manifest failure: no manifest, a missing `gtm.missions_dir` key (including an
  empty/whitespace-only value — B1, 2026-09-09, see `_resolve_default_ledger_path`), cwd not
  inside a git repository, or the `repo_manifest.py` resolver itself could not be run. Distinct
  from exit 2 — this is a failure to even locate the ledger, not a failure of ledger content.
  **Exit-code mapping from the resolver subprocess (B2, 2026-09-09):** `repo_manifest.py get`'s
  own contract only ever exits 3 or 4 on failure (see that script's `_resolve_repo`/`cmd_get`).
  Only those two codes are relayed verbatim (with the resolver's own stderr). Every other
  non-zero code the subprocess could produce — a missing/unexecutable script (the interpreter's
  own "can't open file" exit 2), a killed/signaled process, 127, or anything else that is not the
  resolver's own contract — is mapped to exit 3 here, with stderr `resolver-failed (<original
  code>): <stderr tail>`. This mapping exists specifically so a missing `repo_manifest.py` (which
  makes the interpreter exit 2) can never be relayed as this CLI's own exit 2, which is reserved
  for UNEVALUABLE (a ledger-content failure) and must never be confused with a resolver failure.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Assertion identifiers — ALWAYS fully-qualified. Never emit the bare `CONV-0N` form anywhere in
# this module's output, docstrings, or the tests that exercise it.
GTM_CONV_01 = "GTM-CONV-01"
GTM_CONV_02 = "GTM-CONV-02"
GTM_CONV_03 = "GTM-CONV-03"
ASSERTION_IDS = (GTM_CONV_01, GTM_CONV_02, GTM_CONV_03)

VALID_VERDICTS = {"CONCUR", "DISSENT"}
VALID_SEVERITIES = {"blocker", "major", "minor"}
REQUIRED_FIELDS = ("mission_id", "round", "artifact_id", "judge", "verdict", "severity", "ts")

DEGRADED_GROUNDING_THRESHOLD = 0.50  # >50% of DISSENTs with unresolvable-shaped evidence → DEGRADED

# "Looks like a real citation" heuristic (README's own worked example:
# "marketing/website/templates/index.html:384-546 cites the pre-09-04 ladder"). This is
# DELIBERATELY a separate, softer test from `_is_resolvable_evidence` (which only guards the
# hard parse-time reject of a truly empty evidence field). A DISSENT's `evidence` string is
# non-empty-resolvable (passes the parser) but may still be UNRESOLVABLE-SHAPED for
# DEGRADED-GROUNDING purposes when it reads as unattributed prose rather than something a human
# could actually go open and check — e.g. "this looks wrong" is non-empty but points at nothing
# checkable. A citation is considered "resolvable-shaped" when it contains at least one of:
#   - a URL (http:// or https://)
#   - a file-path-with-locator shape: a path segment containing "/" or a dotted extension,
#     optionally followed by ":<line>" or ":<line>-<line>" (matches the README's own example)
#   - a quoted excerpt attributed to a named source (a quoted span followed by an em/en-dash or
#     hyphen and a trailing source name, e.g. `"exact excerpt" - source_name`)
_URL_RE = re.compile(r"https?://\S+")
_FILE_LOCATOR_RE = re.compile(
    r"""
    (?:                                   # a plausible path segment
        [\w.\-]+/[\w./\-]+                # has at least one path separator, e.g. dir/file.ext
        | [\w\-]+\.[A-Za-z]{1,10}         # or a bare dotted filename, e.g. index.html
    )
    (?::\d+(?:-\d+)?)?                    # optional :line or :line-line locator
    """,
    re.VERBOSE,
)
_QUOTED_ATTRIBUTED_RE = re.compile(r"""["“][^"”]{3,}["”]\s*[-–—]\s*\S+""")


def _looks_like_resolvable_citation(evidence: str) -> bool:
    """Softer DEGRADED-GROUNDING heuristic — see module-level comment above. Called only on
    evidence strings that already passed `_is_resolvable_evidence` (i.e. are non-empty)."""
    return bool(
        _URL_RE.search(evidence)
        or _FILE_LOCATOR_RE.search(evidence)
        or _QUOTED_ATTRIBUTED_RE.search(evidence)
    )


class LedgerError(Exception):
    """Raised internally when the ledger cannot be evaluated; caught by evaluate() and turned
    into an UNEVALUABLE result. Never escapes to a caller as an uncaught exception during normal
    evaluate() use."""


@dataclass
class LedgerRow:
    mission_id: str
    round: int
    artifact_id: str
    judge: str
    verdict: str
    severity: str
    ts: str
    cause_key: str | None = None
    evidence: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    evaluable: bool
    reason: str | None = None  # set when evaluable is False (the UNEVALUABLE reason)
    assertions: dict[str, bool] = field(default_factory=dict)  # GTM-CONV-0N -> met?
    degraded_grounding: bool = False
    degraded_grounding_ratio: float | None = None
    met_count: int = 0

    def summary_line(self) -> str:
        if not self.evaluable:
            return f"UNEVALUABLE: {self.reason}"
        return f"GTM convergence: {self.met_count} of {len(ASSERTION_IDS)} assertions met"


def _parse_ledger_lines(lines: list[str]) -> list[LedgerRow]:
    """Parse every non-blank line as a ledger row. Raises LedgerError on the first problem found
    (malformed JSON, missing required field, invalid verdict/severity, a DISSENT with no
    resolvable evidence field, or a blocker-severity DISSENT with no `cause_key`) — this module
    never silently skips a bad line and continues as if the ledger were clean; a malformed line
    makes the whole evaluation UNEVALUABLE.
    """
    rows: list[LedgerRow] = []
    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"ledger line {i} is not valid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise LedgerError(f"ledger line {i} is not a JSON object")
        missing = [f for f in REQUIRED_FIELDS if f not in obj]
        if missing:
            raise LedgerError(f"ledger line {i} missing required field(s): {', '.join(missing)}")
        verdict = obj["verdict"]
        if verdict not in VALID_VERDICTS:
            raise LedgerError(f"ledger line {i} has invalid verdict {verdict!r}")
        severity = obj["severity"]
        if severity not in VALID_SEVERITIES:
            raise LedgerError(f"ledger line {i} has invalid severity {severity!r}")
        evidence = obj.get("evidence")
        # Evidence-or-refuse (the schema's binding rule): a DISSENT with no resolvable evidence
        # field is rejected at parse time — never silently counted as a valid dissent.
        if verdict == "DISSENT" and not _is_resolvable_evidence(evidence):
            raise LedgerError(
                f"ledger line {i} is a DISSENT with no resolvable evidence field "
                "(evidence must be a non-empty string)"
            )
        cause_key = obj.get("cause_key")
        # cause_key-or-refuse for blocker-severity DISSENTs only: GTM-CONV-01's recurrence check
        # (_zero_recurring_blocker_causes) can only ever see a blocker as "recurring" via its
        # cause_key — a blocker DISSENT with no cause_key is invisible to that check and would
        # silently downgrade a real recurring blocker to a false "not recurring". Major/minor
        # severities and CONCUR verdicts are unaffected; they never feed that check.
        if (
            verdict == "DISSENT"
            and severity == "blocker"
            and not (isinstance(cause_key, str) and cause_key.strip())
        ):
            raise LedgerError(
                f"ledger line {i} is a blocker-severity DISSENT with no cause_key "
                "(required so GTM-CONV-01's recurrence check can see it)"
            )
        try:
            round_no = int(obj["round"])
        except (TypeError, ValueError) as exc:
            raise LedgerError(f"ledger line {i} has a non-integer round: {obj['round']!r}") from exc
        rows.append(
            LedgerRow(
                mission_id=str(obj["mission_id"]),
                round=round_no,
                artifact_id=str(obj["artifact_id"]),
                judge=str(obj["judge"]),
                verdict=verdict,
                severity=severity,
                ts=str(obj["ts"]),
                cause_key=cause_key,
                evidence=evidence,
                raw=obj,
            )
        )
    if not rows:
        raise LedgerError("ledger contains no parseable rows (empty after parsing)")
    return rows


def _is_resolvable_evidence(evidence: Any) -> bool:
    return isinstance(evidence, str) and evidence.strip() != ""


def _load_ledger_rows(ledger_path: str) -> list[LedgerRow]:
    if not os.path.exists(ledger_path):
        raise LedgerError(f"ledger file does not exist: {ledger_path}")
    with open(ledger_path, encoding="utf-8") as f:
        content = f.read()
    if content.strip() == "":
        raise LedgerError(f"ledger file is empty: {ledger_path}")
    return _parse_ledger_lines(content.splitlines())


def _open_dissent_pairs(rows: list[LedgerRow]) -> set[tuple[str, str]]:
    """Return the set of (artifact_id, judge) pairs whose LATEST row (by round, then ledger
    order within a round) is a DISSENT — i.e. currently open. A pair with no later CONCUR after
    its most recent DISSENT is open; a pair whose latest row is CONCUR is closed (whether or not
    it ever dissented earlier)."""
    latest_by_pair: dict[tuple[str, str], LedgerRow] = {}
    # Rely on stable input ordering (ledger append order) as the tiebreak within a round; sort
    # primarily by round so a later round's row always wins over an earlier one regardless of
    # file order.
    for idx, row in enumerate(rows):
        key = (row.artifact_id, row.judge)
        row._order = idx  # type: ignore[attr-defined]
        existing = latest_by_pair.get(key)
        if existing is None:
            latest_by_pair[key] = row
        else:
            existing_order = getattr(existing, "_order", -1)
            if (row.round, idx) >= (existing.round, existing_order):
                latest_by_pair[key] = row
    return {key for key, row in latest_by_pair.items() if row.verdict == "DISSENT"}


def _zero_recurring_blocker_causes(rows: list[LedgerRow], current_round: int) -> bool:
    """GTM-CONV-01: zero blocker-severity DISTINCT RECURRING cause_keys, window=1 (the current
    round only, but "recurring" is judged against the ledger's round history up to and including
    the current round — a cause_key that was open-blocker in an earlier round AND is still an
    open blocker dissent in the current round is "recurring"; a cause_key appearing as a blocker
    for the first time in the current round is not yet "recurring").

    Concretely: for every cause_key that has an OPEN (per _open_dissent_pairs, evaluated against
    rows up to `current_round`) blocker-severity dissent as of the current round, check whether
    that same cause_key also had an open blocker-severity dissent in some STRICTLY EARLIER round.
    If any cause_key satisfies both, GTM-CONV-01 is NOT met (a recurring blocker exists in the
    window). A cause_key with no recorded value (None) never counts as "the same" as another None
    — an un-clustered finding cannot recur by construction.
    """
    rows_upto = [r for r in rows if r.round <= current_round]
    open_pairs = _open_dissent_pairs(rows_upto)
    open_blocker_rows = [
        r
        for r in rows_upto
        if (r.artifact_id, r.judge) in open_pairs
        and r.verdict == "DISSENT"
        and r.severity == "blocker"
    ]
    # For each open blocker pair, take its OWN latest DISSENT row's round (the round the currently
    # open blocker was most recently reasserted) and cause_key.
    latest_open_blocker_by_pair: dict[tuple[str, str], LedgerRow] = {}
    for idx, row in enumerate(open_blocker_rows):
        key = (row.artifact_id, row.judge)
        row._order = idx  # type: ignore[attr-defined]
        existing = latest_open_blocker_by_pair.get(key)
        if existing is None or (row.round, idx) > (existing.round, getattr(existing, "_order", -1)):
            latest_open_blocker_by_pair[key] = row

    # Now, for cause_key recurrence: gather, per cause_key, the set of rounds in which it appeared
    # as an open-as-of-current-round blocker dissent (using the pair-level latest row's round as
    # "when this pair's open blocker was last asserted" is not enough alone — recurrence means the
    # SAME cause_key was already flagged blocker in an earlier round too, possibly via a different
    # artifact/judge pair or the same pair re-dissenting).
    cause_rounds: dict[str, set[int]] = {}
    for r in rows_upto:
        if r.verdict == "DISSENT" and r.severity == "blocker" and r.cause_key:
            cause_rounds.setdefault(r.cause_key, set()).add(r.round)

    currently_open_causes = {
        r.cause_key for r in latest_open_blocker_by_pair.values() if r.cause_key
    }
    for cause_key in currently_open_causes:
        rounds_seen = cause_rounds.get(cause_key, set())
        earlier_rounds = {rd for rd in rounds_seen if rd < current_round}
        if earlier_rounds:
            return False  # recurring blocker cause_key found
    return True


def _zero_fix_caused_regressions(rows: list[LedgerRow], current_round: int) -> bool:
    """GTM-CONV-02: no (artifact_id, judge) pair that recorded CONCUR in round N-1 has a NEW
    DISSENT recorded against it in round N (N = current_round)."""
    prev_round = current_round - 1
    if prev_round < 1:
        return True  # no prior round exists; nothing could have regressed
    concurred_prev: set[tuple[str, str]] = {
        (r.artifact_id, r.judge) for r in rows if r.round == prev_round and r.verdict == "CONCUR"
    }
    dissented_current: set[tuple[str, str]] = {
        (r.artifact_id, r.judge)
        for r in rows
        if r.round == current_round and r.verdict == "DISSENT"
    }
    regressions = concurred_prev & dissented_current
    return len(regressions) == 0


def _mandated_judges_and_zero_open(
    rows: list[LedgerRow],
    current_round: int,
    mandated_judges: set[str] | None,
    artifact_ids: set[str] | None,
) -> bool:
    """GTM-CONV-03: every mandated judge returned a verdict for every in-scope artifact in the
    current round, AND zero open DISSENT pairs remain anywhere in the ledger.

    If `mandated_judges` or `artifact_ids` is None/empty, that half of the check is skipped (the
    caller did not specify a scope) — but the zero-open-dissents half ALWAYS applies regardless,
    since it is the #4893-shaped guarantee and must never be bypassable by omitting scope
    parameters.
    """
    if mandated_judges and artifact_ids:
        current_round_rows = [r for r in rows if r.round == current_round]
        covered: set[tuple[str, str]] = {(r.artifact_id, r.judge) for r in current_round_rows}
        for artifact_id in artifact_ids:
            for judge in mandated_judges:
                if (artifact_id, judge) not in covered:
                    return False

    open_pairs = _open_dissent_pairs(rows)
    return len(open_pairs) == 0


def _degraded_grounding(rows: list[LedgerRow], current_round: int) -> tuple[bool, float | None]:
    """Compute the DEGRADED-GROUNDING flag for the current round: a round is DEGRADED-GROUNDING
    when strictly more than 50% of its DISSENT rows carry evidence that is non-empty (so it
    passed the hard parse-time evidence-or-refuse gate) but does not look like a resolvable
    citation — see `_looks_like_resolvable_citation` for the exact shape test (a URL, a
    file-path-with-locator, or a quoted excerpt attributed to a named source).

    This is DELIBERATELY a two-tier evidence bar: "a DISSENT with no resolvable evidence is
    refused at parse time" refers to the HARD floor — a truly empty/blank evidence field, still
    enforced unchanged by `_parse_ledger_lines`. "A round with >50% of DISSENTs lacking resolvable
    evidence is marked DEGRADED-GROUNDING" refers to this SOFTER bar — evidence that exists and
    parses fine, but reads as unattributed prose ("this looks off") rather than something a reader
    could actually go open and check. Because the hard floor and the soft bar are different tests,
    a normally parsed ledger (via `_parse_ledger_lines`, which never accepts empty evidence) can
    still genuinely trip this flag on the soft bar."""
    current_round_dissents = [
        r for r in rows if r.round == current_round and r.verdict == "DISSENT"
    ]
    if not current_round_dissents:
        return False, None
    unresolvable = sum(
        1
        for r in current_round_dissents
        if not (_is_resolvable_evidence(r.evidence) and _looks_like_resolvable_citation(r.evidence))
    )
    ratio = unresolvable / len(current_round_dissents)
    return ratio > DEGRADED_GROUNDING_THRESHOLD, ratio


def evaluate(
    ledger_path: str,
    mission_id: str,
    current_round: int | None = None,
    mandated_judges: set[str] | None = None,
    artifact_ids: set[str] | None = None,
) -> EvaluationResult:
    """Evaluate GTM-CONV-01/02/03 against the ledger at `ledger_path`, for the single mission
    identified by `mission_id`.

    **`mission_id` is REQUIRED, not optional.** The ledger at `ledger_path` is a SINGLE SHARED
    FILE across every GTM mission the department has ever run (per `MISSION_SCHEMA.md`'s
    "Dissent ledger" section) — rows for unrelated concurrent or historical missions live in the
    same file, interleaved by append order. Every row is filtered to `row.mission_id ==
    mission_id` immediately after parsing and BEFORE any of the four assertion helpers ever sees
    the row list — none of `_open_dissent_pairs`, `_zero_recurring_blocker_causes`,
    `_zero_fix_caused_regressions`, `_mandated_judges_and_zero_open`, or `_degraded_grounding` may
    ever be handed a row belonging to a different mission. `round`, `judge`, and `artifact_id`
    values are NOT globally unique across missions (a judge name is a shared seat name; an
    artifact_id like "spec-004" is plausibly sequential per-mission) — without this filter, a
    wholly unrelated mission's rows can silently flip this mission's convergence verdict in
    either direction, exactly the #4893-class failure this module exists to prevent.

    `current_round` defaults to the highest round number present in the (already
    mission-filtered) ledger rows. `mandated_judges` and `artifact_ids` scope GTM-CONV-03's
    per-artifact/per-judge coverage check (see `_mandated_judges_and_zero_open`); the
    zero-open-dissents half of GTM-CONV-03 always applies regardless of whether these are
    supplied.

    Returns an EvaluationResult with `evaluable=False` and a `reason` string (never a silent
    "met") on any missing/empty/malformed ledger, OR when the ledger parses cleanly but contains
    zero rows for the given `mission_id`.
    """
    try:
        all_rows = _load_ledger_rows(ledger_path)
    except LedgerError as exc:
        return EvaluationResult(evaluable=False, reason=str(exc))

    rows = [r for r in all_rows if r.mission_id == mission_id]
    if not rows:
        return EvaluationResult(evaluable=False, reason=f"no rows for mission {mission_id}")

    if current_round is None:
        current_round = max(r.round for r in rows)

    conv01 = _zero_recurring_blocker_causes(rows, current_round)
    conv02 = _zero_fix_caused_regressions(rows, current_round)
    conv03 = _mandated_judges_and_zero_open(rows, current_round, mandated_judges, artifact_ids)

    degraded, ratio = _degraded_grounding(rows, current_round)

    assertions = {GTM_CONV_01: conv01, GTM_CONV_02: conv02, GTM_CONV_03: conv03}
    met_count = sum(1 for v in assertions.values() if v)

    return EvaluationResult(
        evaluable=True,
        assertions=assertions,
        degraded_grounding=degraded,
        degraded_grounding_ratio=ratio,
        met_count=met_count,
    )


def _resolve_default_ledger_path() -> str:
    """Resolve the default `--ledger` path by shelling out to `repo_manifest.py get
    gtm.missions_dir` from the caller's cwd, then appending `gtm_reviewed.jsonl`.

    Never guesses or hardcodes a product-repo path. On any resolution failure (no manifest, no
    `gtm.missions_dir` key — including an empty/whitespace-only value, B1, see below — cwd not
    inside a repo, script missing), this prints a diagnostic to this process's stderr and exits
    with code 3 — fail loud, never a silent fallback. Only the resolver subprocess's own
    contract codes (3, 4) are relayed as-is with its own stderr; any other resolver-subprocess
    exit (B2, see below) is remapped to 3 with a `resolver-failed (<code>): <stderr tail>`
    message rather than being relayed verbatim.

    **Belt-and-braces cwd guard (B1, 2026-09-09):** `repo_manifest.py get` anchors a path-typed
    manifest key (`gtm.missions_dir` included) to the resolved repo root before printing it, so
    the normal path is already cwd-independent. This guard exists only for the case where the
    resolver's stdout is, for whatever reason, still relative when this process reads it (e.g. an
    older/patched resolver, or a caller pointing `CLAUDE_DIR` at a shim) — silently trusting a
    relative value here would re-anchor it against *this process's* cwd instead of the repo root,
    reproducing exactly the bug this guard is closing. If the returned path is not absolute, it is
    anchored to `git rev-parse --show-toplevel` (list-form subprocess, no shell, explicit
    `cwd=os.getcwd()` and `timeout=30` — F3, 2026-09-09, symmetric with `repo_manifest.py`'s own
    `_resolve_repo`) run from the caller's cwd; if THAT also fails (cwd not inside a repo, or the
    git invocation times out), this exits with code 3 and reason `not-a-repo` (or `not-a-repo (git
    timeout)` on a timeout) rather than silently resolving against cwd.
    """
    claude_dir = Path(os.environ.get("CLAUDE_DIR") or "~/.claude").expanduser()
    resolver = claude_dir / "scripts" / "repo_manifest.py"
    try:
        result = subprocess.run(
            [sys.executable, str(resolver), "get", "gtm.missions_dir"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        print(f"manifest-missing: could not run {resolver}: {exc}", file=sys.stderr)
        sys.exit(3)
    if result.returncode != 0:
        # `repo_manifest.py get` only ever exits 3 (not-a-repo / manifest-missing / key-missing)
        # or 4 (its own contract; see that script's `_resolve_repo`/`cmd_get`) on a genuine
        # resolution failure. Anything else — a missing/unexecutable script (the interpreter's
        # own "can't open file" exit 2), a signal, 127, or any other code — is NOT the resolver
        # reporting its contract; it is this CLI's own subprocess invocation failing in some way
        # the resolver never speaks. Exit 2 is reserved for UNEVALUABLE (main()'s own ledger-
        # content failure) and must never be silently relayed here as if it meant that. Map every
        # non-contract code to exit 3 with a distinguishing stderr message; only relay the
        # resolver's own stderr verbatim when it actually used one of its own contract codes.
        if result.returncode in (3, 4):
            sys.stderr.write(result.stderr)
            sys.exit(result.returncode)
        stderr_tail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
        print(
            f"resolver-failed ({result.returncode}): {stderr_tail}",
            file=sys.stderr,
        )
        sys.exit(3)
    missions_dir = result.stdout.strip()
    if not missions_dir:
        # `repo_manifest.py get` exits 0 with an empty stdout when the manifest key resolves to
        # an empty (or whitespace-only) string — a distinct outcome from `key-missing` (which
        # exits non-zero and is already handled above). An empty value is never a usable ledger
        # directory; falling through to a relative "gtm_reviewed.jsonl" would resolve against
        # THIS process's cwd rather than the repo root, exactly the B1 bug (a caller running from
        # `<repo>/sub` with a planted ledger there silently evaluated the wrong file and reported
        # a false convergence verdict). Treat it identically to a missing key.
        print("key-missing: gtm.missions_dir (empty)", file=sys.stderr)
        sys.exit(3)
    if not os.path.isabs(missions_dir):
        try:
            toplevel = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            print("not-a-repo (git timeout): git rev-parse did not return within 30s", file=sys.stderr)
            sys.exit(3)
        except OSError as exc:
            print(f"not-a-repo: could not run git rev-parse: {exc}", file=sys.stderr)
            sys.exit(3)
        if toplevel.returncode != 0 or not toplevel.stdout.strip():
            print("not-a-repo: cwd is not inside a git repository", file=sys.stderr)
            sys.exit(3)
        missions_dir = str(Path(toplevel.stdout.strip()) / missions_dir)
    return str(Path(missions_dir) / "gtm_reviewed.jsonl")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "GTM mission convergence evaluator (GTM-CONV-01/02/03). "
            "Exit codes: 0 = evaluated (regardless of how many of the 3 assertions were met — "
            "see the printed summary line for the actual verdict); 2 = UNEVALUABLE (missing, "
            "empty, or malformed ledger, or zero rows for the given --mission-id — never "
            "mistakable for a successful evaluation by a caller checking exit status alone); "
            "3 = resolver/manifest failure (no manifest, missing gtm.missions_dir key, cwd not "
            "inside a repo, or the repo_manifest.py resolver itself could not run)."
        )
    )
    parser.add_argument(
        "--ledger",
        default=None,
        help=(
            "Path to gtm_reviewed.jsonl. When omitted, resolved at runtime from the repo "
            "manifest's gtm.missions_dir (python3 ~/.claude/scripts/repo_manifest.py get "
            "gtm.missions_dir) — never a hardcoded product-repo default."
        ),
    )
    parser.add_argument(
        "--mission-id",
        required=True,
        help=(
            "Mission id to evaluate (REQUIRED — the ledger is a single shared file across all "
            "GTM missions; rows for other mission_ids are always excluded)."
        ),
    )
    parser.add_argument(
        "--round", type=int, default=None, help="Round to evaluate (default: max round in ledger)"
    )
    args = parser.parse_args(argv)

    ledger_path = args.ledger if args.ledger is not None else _resolve_default_ledger_path()

    result = evaluate(ledger_path, mission_id=args.mission_id, current_round=args.round)
    print(result.summary_line())
    if not result.evaluable:
        # UNEVALUABLE must never be mistakable for success by a caller checking exit status
        # alone — the reason already printed to stdout above (summary_line()) is repeated here
        # to stderr so a caller that only captures stderr on failure still sees it.
        print(f"UNEVALUABLE: {result.reason}", file=sys.stderr)
        return 2
    if result.degraded_grounding:
        print(
            f"DEGRADED-GROUNDING: {result.degraded_grounding_ratio:.0%} of this round's DISSENTs "
            "lack resolvable evidence"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
