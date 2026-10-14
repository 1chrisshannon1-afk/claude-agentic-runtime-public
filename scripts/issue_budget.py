#!/usr/bin/env python3
"""issue_budget.py — the daily promotion budget for `Backlog` -> `Ready #2`
(#5827, master plan WS1 Phase D — "Creation quality gate +
promotion budget (observer-first)").

READ-ONLY, product-agnostic. Computes:

    daily_promote_budget = max(5, round(completed_closes_trailing_14d / 14))

counting ONLY closes whose GitHub `stateReason` is `COMPLETED` — verified
live by board-steward (2026-09-20): `gh_issue.sh resolve` closes bare (no
`--reason`), which GitHub records as `stateReason: COMPLETED`; `gh_issue.sh
dispose` closes with `--reason "not planned"`, recorded as `stateReason:
NOT_PLANNED`. `NOT_PLANNED` closes are counted and reported SEPARATELY and
are NEVER summed into the budget — a not-planned close reflects triage
throughput, not delivery throughput, and Phase D's formula is deliberately
scoped to the latter (see the plan's own "self-referential... budget <-
closes <- what was promoted" caution below).

THIS SCRIPT DOES NOT PROMOTE ANYTHING. It only computes and prints the
budget; Phase E's event-driven Ready refill pass (a LATER, separate
workstream — `scripts/ready_depth.sh` + board-steward dispatch) is the
consumer that actually moves issues `Backlog`/`Ready #2` -> `Ready #1`
against this budget. P0/P1 bypass the budget entirely (Phase D's own rule)
— also enforced by the REFILL pass, never here; this script has no opinion
about which issues get promoted, only how many.

SELF-REFERENTIAL CAUTION (plan's own words, carried into this script's
output so a caller can never miss it): the formula is self-referential —
budget <- closes <- what was promoted in the first place. A bad week (few
closes) compounds into a smaller budget the following day, which can itself
suppress throughput further. The `max(5, ...)` floor bounds the downward
spiral but does not eliminate it. The plan's architect re-scores the formula
at the 30-day mark; this script does not attempt that judgment itself, it
only surfaces the two raw counts so that re-scoring is possible.

Usage:
    python3 issue_budget.py --repo OWNER/NAME [--json] [--window-days N]

Requires: `gh` (authenticated) on PATH. Makes exactly ONE `gh issue list`
call (paginated internally by `gh` itself via `--json` + `-L`), no GraphQL,
no writes — this is a cheap, everyday-safe read.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Overridable for tests (mirrors scripts/priority_backfill.py's own
# PRIORITY_BACKFILL_GH_BIN convention) so a test can point this at a fake gh
# on disk without any PATH manipulation, and so nothing in this module ever
# reaches the real GitHub CLI during a test run.
GH_BIN = os.environ.get("ISSUE_BUDGET_GH_BIN", "gh")

# The formula's own floor — see module docstring. Never configurable via a
# flag: Phase D names this value explicitly in the plan text itself, and a
# silently-overridable floor would make "the budget is always at least 5"
# no longer a fact a reader of the plan could rely on.
MIN_DAILY_BUDGET = 5

DEFAULT_WINDOW_DAYS = 14

# The two `stateReason` values GitHub's Issues API actually returns for a
# CLOSED issue (a third, `REOPENED`, only ever appears transiently and never
# on a currently-closed issue, so it is not handled as a distinct bucket
# here — an issue carrying it would already be OPEN again). Any other/absent
# value is reported under `unknown` rather than silently folded into either
# bucket, so a schema drift on GitHub's side is visible instead of quietly
# miscounted.
STATE_REASON_COMPLETED = "COMPLETED"
STATE_REASON_NOT_PLANNED = "NOT_PLANNED"


class IssueBudgetError(RuntimeError):
    """Raised for any unrecoverable failure (gh missing/failed, unparseable
    JSON, a malformed repo spec). Every raise site in this module attaches a
    clear, actionable message — this script has no automatic retry/backoff
    of its own; a caller (a human, or the Phase E refill pass) decides
    whether to retry."""


@dataclass(frozen=True)
class CloseCounts:
    """The two raw counts the budget formula (and its self-referential
    caution) are built from, plus the window they were measured over."""

    completed: int
    not_planned: int
    unknown: int
    window_days: int
    window_start_iso: str
    window_end_iso: str

    @property
    def total_closed(self) -> int:
        return self.completed + self.not_planned + self.unknown


def _run_gh(cmd: list[str]) -> subprocess.CompletedProcess:
    """Thin subprocess wrapper — mirrors priority_backfill.py's own `_run`
    convention (capture both streams as text, a generous but bounded
    timeout). Never raises itself; the caller inspects `.returncode`."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise IssueBudgetError(
            f"'{GH_BIN}' not found on PATH — the GitHub CLI is required. ({exc})"
        ) from None
    except subprocess.TimeoutExpired as exc:
        raise IssueBudgetError(f"gh command timed out after 120s: {cmd!r} ({exc})") from None


def _validate_repo(repo: str) -> str:
    """`repo` must be `OWNER/NAME` — a single `/`, both sides non-empty.
    Never guesses a default; this script is product-agnostic (mirrors
    protected_board_guard.py's own registry-driven, never-hardcoded-a-repo
    design posture, applied here to a CLI flag instead of a registry)."""
    repo = (repo or "").strip()
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise IssueBudgetError(
            f"--repo must be OWNER/NAME (got {repo!r}) — this script never assumes a default repo."
        )
    return repo


def fetch_closed_issues(repo: str, *, window_days: int, limit: int = 1000) -> list[dict]:
    """One `gh issue list --state closed --json number,closedAt,stateReason`
    call, scoped to `repo`, capped at `limit` results.

    ASSUMPTION, stated explicitly (fix-round 1, finding 8): plain `gh issue
    list --state closed` sorts results by CREATION time, not by CLOSE time
    — for a repo whose oldest-created issues were NOT the most recently
    closed (the common case for a long-lived backlog), the newest-CLOSED
    issues can sort anywhere in that list, not necessarily first. Passing
    `--search "sort:updated-desc"` (GitHub's search-qualifier sort, the
    closest proxy `gh issue list` exposes to "most recently closed first" —
    a closed issue's `updated` timestamp IS its close event in the common
    case, since closing an issue updates it) makes the SUBSET this call
    actually returns the one most likely to contain every close inside the
    trailing `window_days` window, rather than an arbitrary creation-order
    slice that could miss recent closes entirely if `limit` is hit.

    `limit` bounds how much gh has to fetch/paginate so a repo with an
    implausibly high close rate cannot make this call unboundedly
    expensive — but a result count that hits `limit` exactly is a SIGNAL,
    not a safe truncation: it means this call cannot rule out that MORE
    closes exist beyond what was fetched, which would silently SHRINK the
    computed budget (fewer completed_closes counted than actually
    occurred) rather than erring toward the safer, larger number. Raises
    IssueBudgetError when the returned count equals `limit` exactly, rather
    than silently proceeding on a truncated view — a caller hitting this
    should pass a larger `limit` (there is no CLI flag for it in v1; see
    `main`'s own TODO-free scope) or narrow `--window-days`.

    Raises IssueBudgetError on any gh failure or unparseable output. Never
    writes anything.
    """
    proc = _run_gh(
        [
            GH_BIN,
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "closed",
            "--search",
            "sort:updated-desc",
            "--json",
            "number,closedAt,stateReason",
            "--limit",
            str(limit),
        ]
    )
    if proc.returncode != 0:
        raise IssueBudgetError(
            f"gh issue list --state closed failed for {repo!r}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise IssueBudgetError(
            f"gh issue list returned unparseable JSON for {repo!r}: {exc}"
        ) from None
    if not isinstance(data, list):
        raise IssueBudgetError(
            f"gh issue list returned a non-list JSON shape for {repo!r}: {type(data).__name__}"
        )
    if len(data) >= limit:
        raise IssueBudgetError(
            f"gh issue list returned {len(data)} closed issues for {repo!r}, hitting the "
            f"--limit {limit} cap exactly — this call cannot rule out more closes existing "
            "beyond what was fetched, which would silently SHRINK the computed budget rather "
            "than erring toward the safer, larger number. Re-run with a narrower --window-days, "
            "or raise this script's fetch_closed_issues(limit=...) for a repo with a "
            "genuinely high close rate."
        )
    return data


def _parse_closed_at(value) -> datetime | None:
    """Parse a GitHub `closedAt` ISO-8601 timestamp (`...Z` suffix) into an
    aware UTC datetime, or None for anything unparseable/absent — an issue
    with no/garbled `closedAt` is excluded from the window rather than
    guessed at (see `filter_window`'s own docstring for why that is the
    safe direction here)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # `datetime.fromisoformat` (3.11+) accepts a trailing "Z" directly;
        # this runtime's own dev-runtime dossier does not pin a Python
        # minor version for this script, so normalize "Z" -> "+00:00"
        # explicitly for portability to older 3.x `fromisoformat`.
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_window(
    issues: list[dict], *, window_start: datetime, window_end: datetime
) -> list[dict]:
    """The subset of `issues` (as returned by :func:`fetch_closed_issues`)
    whose `closedAt` falls in `[window_start, window_end]` (inclusive both
    ends). An issue with no parseable `closedAt` is EXCLUDED — never counted
    toward either bucket — since a close with an unknown timestamp cannot be
    attributed to any trailing window without guessing, and guessing here
    risks silently inflating the budget on bad data. Pure; no I/O."""
    out = []
    for issue in issues:
        closed_at = _parse_closed_at(issue.get("closedAt") if isinstance(issue, dict) else None)
        if closed_at is None:
            continue
        if window_start <= closed_at <= window_end:
            out.append(issue)
    return out


def count_by_state_reason(issues: list[dict]) -> tuple[int, int, int]:
    """(completed, not_planned, unknown) counts over `issues` — pure, no I/O.
    `stateReason` is read case-sensitively (GitHub's own API always returns
    the upper-snake-case form; a lowercase/differently-cased value is a
    schema surprise, folded into `unknown` rather than silently matched)."""
    completed = 0
    not_planned = 0
    unknown = 0
    for issue in issues:
        reason = issue.get("stateReason") if isinstance(issue, dict) else None
        if reason == STATE_REASON_COMPLETED:
            completed += 1
        elif reason == STATE_REASON_NOT_PLANNED:
            not_planned += 1
        else:
            unknown += 1
    return completed, not_planned, unknown


def compute_budget(completed_closes: int, *, window_days: int = DEFAULT_WINDOW_DAYS) -> int:
    """`max(MIN_DAILY_BUDGET, round(completed_closes / window_days))` — the
    Phase D formula, verbatim. Pure; `window_days` must be positive (a
    caller passing 0 would divide by zero — guarded explicitly rather than
    trusting every call site, since this is the one function whose output IS
    the budget an operator/refill-pass reads).

    NOTE (fix-round 1, finding 9): Python's `round()` is BANKER'S ROUNDING
    (round-half-to-even), not the "round half up" a reader might assume —
    `round(63/14)` = `round(4.5)` = `4` (rounds DOWN to the even neighbor),
    while `round(91/14)` = `round(6.5)` = `6` (also down, already even).
    This is correct-as-specified (the plan states the formula as
    `round(...)`, not `round-half-up(...)`) and produces at most a ±1
    promotion-per-day discrepancy from a naive "always round .5 up" reading
    — never a larger drift, and never a direction that defeats the
    `max(5, ...)` floor's own purpose."""
    if window_days <= 0:
        raise IssueBudgetError(f"window_days must be positive (got {window_days})")
    return max(MIN_DAILY_BUDGET, round(completed_closes / window_days))


def compute_close_counts(
    repo: str, *, window_days: int = DEFAULT_WINDOW_DAYS, now: datetime | None = None
) -> CloseCounts:
    """The full read + filter + count pipeline for `repo`. `now` is
    injectable for tests (defaults to the real current UTC time) — the ONLY
    non-pure input to this whole module, isolated here so every function
    above it stays a pure, directly-testable unit."""
    if now is None:
        now = datetime.now(timezone.utc)
    window_end = now
    window_start = now - timedelta(days=window_days)
    raw = fetch_closed_issues(repo, window_days=window_days)
    windowed = filter_window(raw, window_start=window_start, window_end=window_end)
    completed, not_planned, unknown = count_by_state_reason(windowed)
    return CloseCounts(
        completed=completed,
        not_planned=not_planned,
        unknown=unknown,
        window_days=window_days,
        window_start_iso=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end_iso=window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


_BYPASS_NOTE = (
    "P0/P1 bypass this budget entirely (Phase D's own rule) — enforced by the "
    "refill pass that consumes this number, never by this script."
)
_SELF_REFERENTIAL_NOTE = (
    "SELF-REFERENTIAL CAUTION: this formula is budget <- closes <- what was "
    "promoted in the first place. A bad week compounds into a smaller budget "
    "the next day; the max(5, ...) floor bounds this but does not eliminate "
    "it. Re-score at the 30-day mark (plan owner: architect) rather than "
    "trusting this number to self-correct."
)


def render_text(counts: CloseCounts, budget: int) -> str:
    lines = [
        f"daily_promote_budget = {budget}",
        f"  window            = {counts.window_days}d "
        f"({counts.window_start_iso} .. {counts.window_end_iso})",
        f"  completed_closes  = {counts.completed}  (stateReason=COMPLETED — counted toward budget)",
        f"  not_planned_closes= {counts.not_planned}  (stateReason=NOT_PLANNED — reported only, "
        "never summed into the budget)",
    ]
    if counts.unknown:
        lines.append(
            f"  unknown_closes    = {counts.unknown}  (no/unrecognized stateReason — "
            "excluded from both buckets)"
        )
    lines.append(f"  {_BYPASS_NOTE}")
    lines.append(f"  {_SELF_REFERENTIAL_NOTE}")
    return "\n".join(lines)


def render_json(counts: CloseCounts, budget: int) -> str:
    payload = {
        "daily_promote_budget": budget,
        "min_daily_budget": MIN_DAILY_BUDGET,
        "window_days": counts.window_days,
        "window_start": counts.window_start_iso,
        "window_end": counts.window_end_iso,
        "completed_closes": counts.completed,
        "not_planned_closes": counts.not_planned,
        "unknown_closes": counts.unknown,
        "p0_p1_bypass": True,
        "notes": {
            "bypass": _BYPASS_NOTE,
            "self_referential_caution": _SELF_REFERENTIAL_NOTE,
        },
    }
    return json.dumps(payload, indent=2)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only: computes the Backlog -> Ready #2 daily promotion budget "
            "(#5827, master plan WS1 Phase D). Never promotes "
            "anything itself."
        )
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="OWNER/NAME — required, never assumed (this script is product-agnostic).",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"trailing window in days (default {DEFAULT_WINDOW_DAYS}, per the Phase D formula).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human-readable text report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        repo = _validate_repo(args.repo)
        counts = compute_close_counts(repo, window_days=args.window_days)
        budget = compute_budget(counts.completed, window_days=counts.window_days)
    except IssueBudgetError as exc:
        print(f"issue_budget: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(render_json(counts, budget))
    else:
        print(render_text(counts, budget))
    return 0


if __name__ == "__main__":
    sys.exit(main())
