#!/usr/bin/env python3
"""churn_report — the weekly (or any-window) telemetry artifact, read-only.

WHY THIS EXISTS
----------------
churn_phase0_measure.md's step 5. Every other optimization in this runtime is
judged by numbers the hook system already writes but never surfaces, and two
of those numbers were flatly wrong: `~/.claude/.enforcement/log.jsonl`'s
`enforce` field (fixed separately in `_lib.log`, step 4), and a naive count
of a day's ENTIRE log being reported as if it were that day's real denial
count. On 2026-08-24 the log held 1,040 lines; only 81 of them were real
`would-block` denials — counting every line gives a ~13x error (1,040 / 81 ≈
12.8). An earlier draft of this sentence blamed `contested-paths` being
conflated with `would-block` for that 13x; that was wrong — `contested-paths`
is a `reason` value that happened to appear 13 times that same day, an
unrelated coincidence of arithmetic, not the cause. This module fixes the
real class of error by reading the ledgers CORRECTLY — filtering by
`decision`, never counting every line — once, in one place, rather than
every future analysis re-deriving (and likely re-breaking) the same counts.

This is a PURE READER: no LLM call, no ledger write, no side effect of any
kind. It reads, at most, these four files and computes everything else in
memory:

  * ``~/.claude/.review_state/plan_reviews.jsonl``  — one JSON object/line:
    ``{ts, repo, plan, outcome, blockers}``.
  * ``~/.claude/.review_state/last_reviewed``        — plain text, one entry
    per line: ``"<repo_root> <key> [<outcome> [ts=... item=...]]"`` where
    `key` is either a bare git sha (legacy) or ``precommit:<digest>``
    (current era). Lines with no outcome suffix at all (the original bare
    two-field shape) and lines whose third field doesn't parse as an outcome
    token both degrade to UNKNOWN via ``record_review.parse_outcome_token``,
    reused verbatim here rather than reimplemented — but this module now
    tells the two kinds apart (see CATCH-RATE GROUPING RULE below).
  * ``~/.claude/.enforcement/log.jsonl``             — one JSON object/line,
    always carrying ``decision``. See DENIAL DECISION VALUES below for which
    values are a real denial and which are not.
  * ``~/.claude/.agent_budget/spend.jsonl``          — one JSON object/line
    per dispatch, the canonical schema from churn_phase0_measure.md step 2.
    May not exist yet (step 2 may not have landed) — an absent file prints
    ``ABSENT`` for its metrics, never zeros (a zero here would be a false
    "no spend happened" read, exactly the false-green class this phase
    exists to kill).

A missing ledger is reported as ``ABSENT`` for the metric(s) it feeds, never
silently treated as zero data. An ledger that EXISTS but could not be fully
read (permission error, I/O error mid-read) is reported as ``DEGRADED`` —
also never treated as zero data. See LEDGER READ FAILURES below; this is the
one status an ``ok`` zero must never masquerade as.

``--days N`` (default 7) is a RECENCY FILTER applied to the ledgers that are
naturally per-day event streams: the enforcement log (metrics 2 and 3) and
the spend ledger (metrics 5 and 6). It is deliberately NOT applied to plan
rounds (metric 1) or the code-review catch rate (metric 4): both are
lifetime/cumulative metrics by nature (a plan review or a HEAD review either
happened or it didn't; there is no daily reset), the plan's own ground-truth
numbers for both are quoted with no day qualifier, and — for catch rate
specifically — a large fraction of real (outcome-bearing) entries in
`last_reviewed` predate the ``ts=`` field entirely: 622 of 880
outcome-bearing entries (70.7%; 1,586 non-blank lines total, the remaining
706 being ``bare_legacy``), recomputed live 2026-08-25 with (line-wrapped
here, one command)::

    python3 -c "import churn_report as cr; \
    lines,_=cr.read_lines(cr.LEDGER_LAST_REVIEWED); \
    es=[cr.parse_catch_rate_entry(l) for l in lines]; \
    print(sum(1 for e in es if e['kind']=='entry' and e['ts'] is None))"

against the live ledger (the plan's own "611 of 1,576" figure was produced by
a naive ``split(maxsplit=2)`` parser that mis-splits the one real repo root
containing a space; this module's own ``parse_last_reviewed_line`` gives 622
on the identical rule — a day filter would silently corrupt this very
denominator). Sections 1 and 4 mark themselves ``"window": "lifetime"`` in
`--json` and print ``window: LIFETIME (--days does not apply)`` in their own
provenance line — never relying on a reader inferring it from the header
alone. Sections 2, 3, 5, and 6 mark themselves ``"window": "recency"``. An
entry whose own timestamp fails to parse is NEVER dropped by the day filter
either way (fail OPEN toward inclusion, matching this hook system's existing
ethos of never silently zeroing a real signal).

Every recency-windowed section's own ``as_of`` is deliberately computed from
the ledger's FULL, UNFILTERED line/row set (before ``--days`` or dedup is
applied), never from the windowed/deduped subset that feeds its metrics —
``as_of`` answers "how current is this ledger's data," a question about the
ledger itself, not about the window a caller happened to ask for. For the
spend ledger specifically (metrics 5/6) this also means ``as_of`` is taken
BEFORE `dedup_spend_lines` collapses a `tool_use_id` group: a newer
`unreleased` placeholder line that loses its dedup group to an older real
release must still be reflected in `as_of`, or the report would understate
how fresh the ledger actually is.

DENIAL DECISION VALUES (metric 2)
----------------------------------
Every top-level ``decision`` value ever seen carrying "this command/action
was denied or would have been" semantics, and whether metric 2 counts it:

  * ``would-block`` — COUNTED. Logged by the `PreToolUse:Bash` dispatcher
    chain (`pretooluse_bash.py`, plus `block_branch_ops`/
    `block_unscoped_commit` directly) on every gate 1-4 block, regardless of
    whether it was actually enforced; the line's own `enforce` field (fixed
    2026-08-25, step 4) says whether a real deny was emitted.
  * ``deny`` — COUNTED. The EXECUTED deny from `gh_issue_close_gate.py`
    (`gh issue close` calls only) when `enforcing()` is true. All 246
    `deny` lines in the live ledger (verified 2026-08-25) are from this one
    hook — it is a genuinely separate command-gating surface from
    `would-block`'s git-commit family, which is why it was previously
    missing from this metric entirely (the bug this section exists to fix).
  * ``would-deny`` — NOT counted. `gh_issue_close_gate`'s own LOG-ONLY
    sibling of `deny` (would have denied, but not enforcing): zero
    occurrences in the live ~80k-line ledger as of 2026-08-25 (enforcement
    has been globally on since before this hook shipped), but structurally
    excluded on the same basis as any not-actually-enforced signal — it
    never blocked a real close the way `deny` did.
  * ``block`` — NOT counted, and NOT one hook's name despite the plan's
    original wording: the retired Stop-hook `review_gate` used it (3,142
    lines, last emitted 2026-08-19, unregistered 2026-08-19 per
    CLAUDE.md §10) for a since-superseded review checkpoint; two unrelated,
    still-live diagnostic checkers — `check_safety_core_parity` (a repo
    hygiene/parity checker) and `sync_agent_rules` (a CLAUDE.md drift
    checker) — separately reuse the exact same string for their own
    "problem found, enforcing" signal, verified live as recently as
    2026-08-25. None of the three denies a git command the way
    `would-block`/`deny` do, so all three are excluded by name from this
    metric — but the name `block` is NOT a synonym for "retired," only for
    "not this metric's kind of denial."

GATE HOOK ALLOWLIST (metric 2, round-3 fix, 2026-08-25)
------------------------------------------------------------
`decision` alone is NOT sufficient to identify a real command/action denial,
even restricted to `would-block`/`deny`: `check_safety_core_parity.py` and
`sync_agent_rules.py` already had to be excluded by `decision` value (see
`block` above), but two OTHER modules — `mint_prod_session.py` (gates
minting a prod secret; logs `deny` under hook `mint_prod_session`) and
`block_prod_mutations.py` (gates a prod HTTP mutation; logs `deny` under hook
`block_prod_mutations`) — log a real, structurally identical `deny` under
`_DENIAL_DECISIONS` for a concern that is not the git-command-gating surface
this metric measures. Metric 2 therefore also restricts to a `hook`
allowlist, `_GATE_HOOKS`: `pretooluse_bash` (the dispatcher; its own
`would-block` records further carry `gate`, naming which of its eight gates
fired), `git_guard` (its retired precursor — 684 historical would-blocks
still live in the ledger under this name; omitting it would silently drop
them from every all-time total), `block_branch_ops`/`block_unscoped_commit`/
`check_staged_scope` (standalone entry points logging under their own
names), `gh_issue_close_gate` (the `deny` surface), and — added 2026-09-01
fix round — `pretooluse_task`/`model_pin_gate` (the separate
`PreToolUse:Task` dispatcher's own gate T1, `~/.claude/hooks/
model_pin_gate.py`, enforcing `knowledge/model_policy.json`'s `agent_pins`;
CLAUDE.md §7's own Task-dispatcher paragraph). A `would-block`/
`deny` entry whose `hook` is not in this allowlist — including a missing/
`None` `hook` field — is excluded from the metric and counted separately in
`excluded_non_gate_by_hook` (keyed by the offending hook name, or the
literal string `"<missing>"` for a missing/`None` hook), never silently
dropped with no trace: a future gate module this allowlist doesn't yet know
about shows up as a nonzero `excluded_non_gate_by_hook` entry instead of
disappearing. Verified live 2026-08-25: every one of the 6,182 `would-block`
and 252 `deny` lines in the real ledger already carries a `hook` in
`_GATE_HOOKS` — `mint_prod_session` and `block_prod_mutations` have not yet
logged a real deny on this machine — so today this filter is a no-op (6,434
in, 0 excluded); it exists for the day one of them does, or a new gate hook
ships without being added here.

CATCH-RATE GROUPING RULE (metric 4, step 3 of the plan)
--------------------------------------------------------
The ledger does not store a pathspec, only a repo root — so "grouped by
pathspec and time window" is approximated as grouped by (era, repo, UTC
calendar day of the entry's own ``ts=`` field). ``era`` is `"precommit"` when
the entry's key starts `precommit:` (the current gate-3b digest-keyed
regime) and `"legacy-sha"` otherwise (the retired sha-keyed regime it
replaced). The two eras are NOT blended into one rate: doing so hid a huge
gap (legacy-sha 150/162 blockers = 48.1%, from before gate 3b existed vs.
today's precommit regime, live 2026-08-25: ~26/536 ≈ 4.6%, drifting as new
reviews land) behind one meaningless 19.9%-ish number that was not a rate of
anything currently running. `total_blockers`/`total_clean`/`denominator`/
`rate` at the top level of this metric's payload are the PRECOMMIT-era
headline (the regime actually in force today); the full `by_era` breakdown
(both eras, each with its own `by_repo_and_day`) is always present alongside
it, and `all_eras_*` gives the blended lifetime totals for anyone who wants
them.

Within one (era, repo, day) bucket, a ``blockers:n`` entry followed later
that same day by a ``clean`` entry on the same repo represents one review
cycle that found something and was then fixed; the bucket's own
blockers/clean counts and per-bucket rate make that visible without needing
to detect the pairing explicitly. Entries with no ``ts=`` field fall into a
bucket keyed ``"unknown-date"`` per (era, repo), and are still counted
toward every rate (both per-bucket and overall) — excluding them would
corrupt the denominator, not just miss a nicety. The OVERALL rate is
``blockers-entries / (blockers-entries + clean-entries)``, over ENTRIES (a
``blockers:9`` line is one entry, not nine), never over the raw blocker
count `n`.

Every `last_reviewed` line that is NOT a real clean/blockers entry falls
into exactly one of THREE buckets, reported separately (never folded into
one "excluded_unknown" constant that can hide either kind of corruption
growing):

  * ``bare_legacy`` — the line parsed cleanly (a real repo, a real key) but
    carries no outcome suffix at all: the original two-field shape from
    before `record_review` recorded outcomes. A legitimate, if uninformative,
    entry.
  * ``unparseable`` — either the WHOLE line carried no recognizable key
    token (`parse_last_reviewed_line` returned `None` — no known repo at
    all), or a key/repo WAS found but the text after it didn't parse as a
    known outcome token (garbage, truncation, a future format this parser
    doesn't know yet). Both kinds are corruption, not "legitimately never
    reviewed," and both are bucketed under the synthetic repo
    `"unknown-repo"` (`unknown_repo_by_day`, keyed by day when a `ts=` is
    recoverable, else `"unknown-date"`) rather than silently vanishing —
    retiring what used to be dead code (a `repo or "unknown-repo"` fallback
    that could never actually fire, because every entry reaching it had
    already been filtered to UNKNOWN and dropped one line earlier).
  * ``battery`` — a `record_review.BATTERY_PREFIX`-prefixed mutation-battery
    result line (Item 6, gate-optimization plan §2/§7): NOT corruption and
    NOT a review outcome (it carries no repo_root/key at all -- a battery
    run isn't gating a specific commit). This branch is REQUIRED, not a
    nicety: such a line has no key token matching `_KEY_TOKEN_RE` by
    construction, so without a dedicated check `parse_last_reviewed_line`
    returns `None` for it and it would silently misclassify as
    `unparseable` -- a false corruption reading, since a live-ledger
    `unparseable` count of exactly 0 today is precisely the signal this
    metric exists to keep meaningful. Reported under its own `battery`
    count, never mixed into `bare_legacy`, `unparseable`, or
    `excluded_unknown`.

`excluded_unknown` (= `bare_legacy + unparseable`) is kept as a convenience
sum for callers that don't need the split; `battery` is deliberately NOT
part of that sum -- it was never eligible to be a review outcome in the
first place, so it is neither "excluded" nor corruption.

REASON GROUPING RULE (metric 2, free-text `deny` reasons)
------------------------------------------------------------
`gh_issue_close_gate`'s `deny` reasons are full sentences that embed a
commit sha, e.g. ``"commit '<sha>' is not an ancestor of 'master' — the
close claims prod status..."``. Grouping on the raw string explodes into one
bucket per sha for what is really the SAME denial repeated. `group_reason_text`
redacts any quoted 7-40-hex-char sha to the literal `'<sha>'` first (so two
denials citing different shas for the same guard collapse together), then
truncates at the first em dash (`—`) — the boilerplate/detail boundary this
hook's own messages use — to drop the per-event trailing detail. A reason
with no em dash is returned whole (redacted, untruncated). The grouped label
is what the by-day/by-reason table keys and sorts on; the FULL raw text is
never discarded — it is kept one level deeper (`{group_key: {raw_reason:
count}}`), so `--json` output always has it even though the text table only
prints the grouped totals.

SPEND DEDUP RULE (metrics 5 and 6, step 2's schema)
-----------------------------------------------------
Lines are deduplicated by ``tool_use_id``: when the same id appears more than
once (the reaper's ``unreleased: true`` placeholder plus a later real
release, or a double-release bug), the LAST non-``unreleased`` line wins (the
file is append-only, so list order is chronological); if EVERY line for an
id is ``unreleased: true`` (a claim reaped but never released), the LAST of
those wins instead of being dropped — a reaped-never-released dispatch is
still one dispatch, not zero. A ``null`` ``tool_use_id`` is NEVER
deduplicated against anything — each such line (only a
``reaped == "stopped-unjoined"`` reap ever has one) is its own record, keyed
by ``agent_id`` instead, and is counted under metric 6 (the join-bug
finding), not folded into the by-agent/by-model/by-day spend sums. A
``tool_use_id`` that is present but not a `str` (and not `None`) is itself
malformed data — it would be unhashable as a dict key and crash the group-by
— and is dropped from BOTH lists, counted instead in `malformed_fields`
under `"tool_use_id"` so it is never silently treated as either a real
dispatch or a stopped-unjoined reap.

The four token fields (``input``, ``output``, ``cache_read``,
``cache_creation``) are summed independently; ``tokens_total`` is summed AS
WRITTEN, never recomputed from the four fields here (recomputing it here
would silently paper over a bug in how the writer derived it). Every numeric
field is coerced through `_as_int`, which accepts a real `int` or an
integral `float` and rejects (counts as malformed, contributes 0) a `bool`
(an `int` subtype that is never an intended token/duration count here), a
non-integral `float`, or any other type — a spend line with a stray string
or a boolean in a numeric field is counted and rendered under
`malformed_fields`, never silently coerced to 0 or 1 with no trace.

REVIEW-ROUND CONVERGENCE RULE (metric 7, missions_observability_adoption_plan.md P1)
--------------------------------------------------------------------------------------
`record_review.py` has recorded `round=`/`prev=`/`warm=` fields on `last_reviewed`
entries since 2026-08-30/31 (CLAUDE.md §10's warm-round paragraph), but this module
never read them until now: 178 `round=` lines and 3 `warm=` lines live on this
machine as of 2026-09-04, all zero-effect on every metric above. Metric 7 closes
that gap, reading `LEDGER_LAST_REVIEWED` (metric 4's own ledger) for the chain data
and `LEDGER_ENFORCEMENT_LOG` (metrics 2/3's own ledger) for the refusal count.

A **chain** is a maximal run of `entry`-kind lines linked by `prev=<key>` tokens: an
entry whose `prev=` points at another entry's own ledger `key` is that entry's
predecessor in the same chain, and chain identity is scoped by `(repo, key)` — never
`key` alone, since the same digest key can legitimately recur across different
repos. A chain's FIRST recorded round may carry `round=N` with no `prev=` at all
(there was nothing before it to link to) — such an entry is its own chain root.
Every entry lacking `round=` entirely (the vast majority of the ledger — 178 of
~1,600+ non-blank lines) is simply not part of any chain and is excluded from this
metric, not counted as a degenerate one-round chain.

**TWO-PASS WINDOW RESOLUTION (not a single recency-filtered read):** chain LINKAGE
is resolved against the FULL, unwindowed ledger — a chain's predecessor may sit
outside the caller's `--days` window, and hard-dropping it from the walk would
silently understate a real chain (or hide a real "hit the cap, then went cold"
whose cap-completing round fell just outside the window). A SEPARATE windowed pass
determines which `(repo, key)` entries are actually in-window; a chain is reported
only if at least one of its members is in-window, but every metric computed FROM a
reported chain draws on its full (possibly cross-window) membership, with one
deliberate exception: `warm_histogram`/`warm_rows_total` count ONLY in-window warm
members (see `round_chain_metrics`'s own docstring for the asymmetry and why).
A `prev=` that cannot be resolved to any entry in the FULL ledger (a dangling or
foreign link, or a genuine `prev=` cycle — including a direct self-reference,
`prev=` equal to the entry's own key, found live in this machine's ledger) is
chain-END, exactly like `record_review._consecutive_warm_round_count`'s own
dangling-link handling — never an infinite walk, never a crash, and the entry
carrying that unresolvable `prev=` is still counted as the tail of its own
partial chain.

**rounds-per-boundary distribution:** for each REPORTED chain, the MAX `round=`
value seen across its FULL linked membership (including any out-of-window
predecessor pulled in only to resolve linkage) — one number per chain, one
boundary per chain (a "boundary" being one pending commit's worth of review
rounds, per CLAUDE.md §10). The histogram is `{round_value:
count_of_chains_whose_max_round_is_that_value}`. Because this uses full
membership, the max round= can legitimately span BEYOND the `--days` window
being reported — the histogram answers "how many rounds did this boundary really
take," never "how many rounds happened inside this window." This is disclosed at
every surface: this docstring, `round_chain_metrics`'s own docstring, the rendered
table (a line directly under the histogram), and `_HELP_TEXT`'s `--days`
description.

**warm-round distribution + cap-then-cold count:** per chain, the count of entries
carrying `warm=1`. A chain "hit the cap and went cold" when it contains a run of
`_MAX_CONSECUTIVE_WARM_ROUNDS` (2, mirrored from `record_review.py` rather than
reimplemented as a fresh literal) consecutive `warm=1` entries immediately followed
(in `prev=`-chain order, i.e. a later entry whose `prev=` cites the warm entry) by
a COLD (`warm` absent) entry — the observable shape of "two warm rounds, capped,
next round forced cold" that `record_review.py:2170-2196`'s refusal branch exists
to enforce. A chain that never reaches 2 consecutive warm entries, or whose last
recorded entry is itself still warm (no observed cold follow-up yet, mid-chain),
does not count here.

**warm-cap refusals:** `record_review.py`'s refusal branch (`:2170-2196`) logs via
`_lib.log(HOOK, "warm-cap-exceeded", target=..., prev=..., prior_warm=...)`
(`HOOK = "record_review"`) — which lands in `~/.claude/.enforcement/log.jsonl`,
the SAME ledger metrics 2/3 already read (`LEDGER_ENFORCEMENT_LOG`), not a new
sink. This is mechanically readable: count entries with
`decision == "warm-cap-exceeded"`, windowed by `--days` like every other
enforcement-log metric. (It is deliberately NOT restricted to metric 2's
`_GATE_HOOKS` allowlist — that allowlist exists to separate *command-denial*
concerns sharing the generic `would-block`/`deny` decision values from each
other; `warm-cap-exceeded` is already its own unambiguous decision value, logged
by exactly one hook, so no allowlist is needed to disambiguate it.)

**small-n rule:** below `_SMALL_N_THRESHOLD` (20) warm rows in the current window,
the report renders RAW COUNTS with the literal marker `n=<x>, not yet
interpretable` — never a percentage or rate computed from them. Today n=3
(lifetime; fewer still within a short `--days` window). This is a chosen constant
(CLAUDE.md §10's own two-warm-round cap discussion flags exactly this kind of
premature-percentage risk), stated here so it is not re-litigated per report.

Windowed by `--days` exactly like metrics 2/3/5/6 (every `round=`-carrying entry
observed on this machine to date also carries `ts=`, so the window is meaningful
here, unlike metric 4's `last_reviewed`-wide read where a majority of entries
predate `ts=` entirely).

FAN-OUT SESSION-HIGH RULE (metric 8, plan_lane_control_adoption_master_2026_09_20.md
§2.2/WS2.2)
--------------------------------------------------------------------------------------
`agent_budget.py`'s `note_fanout_dispatch` (a PURE OBSERVER — it never denies,
delays, or raises) logs exactly ONE `fanout-session-high` line per session, the
first time that session's admitted Task-dispatch count reaches
`CSA_FANOUT_THRESHOLD` (default 40), via `_lib.log("agent_budget",
"fanout-session-high", session=..., count=..., top_agent_types=[...])` — landing
in the SAME `LEDGER_ENFORCEMENT_LOG` metrics 2/3/7 already read, not a new
ledger. Metric 8 reads that decision value only (it is already unambiguous —
logged by exactly one hook — so, like `warm-cap-exceeded`, it is deliberately
NOT restricted to metric 2's `_GATE_HOOKS` allowlist, which exists only to
disambiguate the generic `would-block`/`deny` decision values shared across
several hooks).

Reported as: `sessions_over_threshold` — one row per flagged session
(`session`, `count`, `top_agent_types`, `day`) — and `sessions_over_threshold_by_day`
(count of flagged sessions per UTC day, the "sessions/day over the threshold"
figure the plan's own text names). `count_p50`/`count_p90`/`count_max` are the
distribution of the `count` field across every flagged session IN the current
`--days` window (never a raw dispatch count recomputed here — this metric
reads only what the observer already logged, exactly once per session, and
never re-derives a session's true total from spend.jsonl). `statistics.median`
gives p50 exactly; p90 uses
`statistics.quantiles(..., n=100, method="inclusive")[89]` — `inclusive`
deliberately, because the default `exclusive` extrapolates beyond the data
and can report a p90 higher than any observed session (see
`_percentile_90`'s own docstring for the measured cases). Matches this
module's existing `statistics`-only dependency — no numpy. Below 2 flagged sessions in the
window, `count_p50`/`count_p90` are `None` (a single point has no meaningful
percentile spread) and `count_max` is still reported (a max of one value is
well-defined) — mirroring metric 7's own small-n discipline of never
fabricating a statistic from too little data, though metric 8 uses a count-of-2
floor rather than metric 7's warm-rows-based `_SMALL_N_THRESHOLD` since a
"session flagged" event is intrinsically rare (one line per session, ever,
per crossing) rather than a per-round tally. Windowed by `--days` exactly like
metrics 2/3/5/6/7 (every `fanout-session-high` line carries a real `ts=`, via
the same `_lib.log` machinery every other enforcement-log row does).

LEDGER READ FAILURES (all four ledgers)
------------------------------------------
`read_jsonl`/`read_lines` return `(rows_or_lines, errors)` on success — even
a partial success — or `None` only when the path does not exist at all.
`errors` always carries `"skipped_unparseable"` (a count of individual lines
that could not be parsed but did not abort the read — e.g. a non-JSON line
in a `.jsonl` ledger) and `"read_error"` (`None` on a full, uninterrupted
read; otherwise `repr()` of the exception that aborted the read, such as a
`PermissionError` on an unreadable file). A section whose `read_error` is
not `None` is reported with `status: "degraded"`, rendered as
`DEGRADED (...)` — it NEVER reports `status: "ok"` with zeros, which is
indistinguishable from "the ledger legitimately has no data" and is exactly
the false-green class this module exists to prevent. A degraded section
still computes and shows whatever metrics its partial data supports; the
`degraded` marker is what tells a reader not to trust it as complete.

Usage:
    python3 ~/.claude/hooks/churn_report.py [--days N] [--json] [--help]
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import record_review as rr  # noqa: E402  (shared outcome-token parser)

DEFAULT_DAYS = 7

LEDGER_PLAN_REVIEWS = os.path.join(_lib.REVIEW_STATE_DIR, "plan_reviews.jsonl")
LEDGER_LAST_REVIEWED = _lib.LAST_REVIEWED
LEDGER_ENFORCEMENT_LOG = _lib.LOG_FILE
LEDGER_SPEND = os.path.join(_lib.AGENT_BUDGET_DIR, "spend.jsonl")

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}Z$")
_TS_SUFFIX_RE = re.compile(r"ts=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")
# A `battery:<ts> mut=<caught>/<total> stale=<n>` line's own bare timestamp,
# which sits directly after `rr.BATTERY_PREFIX` with no `ts=` key (unlike
# every other telemetry field this module parses) -- see
# `parse_catch_rate_entry`'s battery branch below.
_BATTERY_TS_RE = re.compile(r"^" + re.escape(rr.BATTERY_PREFIX) + r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")
# A last_reviewed "key" token: a bare git sha (7-40 hex chars) or a
# `precommit:<hex digest>` content key. Never matches "clean"/"blockers:n"
# (neither is pure-hex) or a real repo path segment on this machine (checked
# against every path in the real ledger 2026-08-25, including the one repo
# root that contains a space: "Desktop/other project").
_KEY_TOKEN_RE = re.compile(r"^(?:[0-9a-fA-F]{7,40}|precommit:[0-9a-fA-F]{4,64})$")
# A quoted commit sha embedded in a free-text denial reason (7-40 hex chars).
_QUOTED_SHA_RE = re.compile(r"'[0-9a-fA-F]{7,40}'")
_EM_DASH = "—"
# Real denial-bearing decision values this metric counts. See the module
# docstring's DENIAL DECISION VALUES section for every value and why.
_DENIAL_DECISIONS = ("would-block", "deny")
# Hooks that log a real COMMAND/ACTION denial. `pretooluse_bash` is the
# PreToolUse:Bash dispatcher (its would-block records carry `gate`, naming
# which of the six fired: block_branch_ops / file_claims / check_staged_scope
# / precommit_review_gate / gh_issue_close_gate); `git_guard` is its retired
# precursor (684 historical would-blocks — omit it and every all-time total
# silently loses them); the three standalone entry points log under their own
# names; `gh_issue_close_gate` is the `deny` surface.
_GATE_HOOKS = frozenset({
    "pretooluse_bash", "git_guard", "block_branch_ops",
    "block_unscoped_commit", "check_staged_scope", "gh_issue_close_gate",
    # pretooluse_task (the PreToolUse:Task dispatcher, gate T1 = model_pin_gate)
    # and model_pin_gate itself (its own would-block records when invoked
    # directly, e.g. manual/debug use of its main()) -- added 2026-09-01 fix
    # round (B6's "also fix" list): without these, every model-pin denial was
    # invisible to this metric's `_GATE_HOOKS` allowlist, undercounting real
    # command/action denials the exact way this allowlist exists to prevent.
    "pretooluse_task", "model_pin_gate",
    # protected_board_guard (gate 5b, added 2026-09-14, GH #5490) -- denies an
    # attempt to ADD an item to a protected GitHub Projects board, logging
    # `deny` under enforcement (`would-deny` log-only, same NOT-counted
    # posture as gh_issue_close_gate's own `would-deny` per the DENIAL
    # DECISION VALUES section above). Same reasoning as gh_issue_close_gate:
    # without this, every one of its executed `deny` decisions is invisible
    # to metric 2, silently undercounting real command denials.
    "protected_board_guard",
})
# The known writer defect (churn_tracker recording a shell redirect token as
# a "path"), fixed in churn_phase0_measure.md step 4 but not yet retroactively
# cleaned from historical log data. Annotated, never filtered, per the task.
# The full step-4 token set (N12): a bare "2>" was the only one caught live,
# but ">"/"<"/">>" are the same class of defect and would be silently
# unannotated if they ever appear.
_KNOWN_REDIRECT_TOKEN_DEFECT = frozenset({"2>", ">", "<", ">>"})
# Metric 7 -- mirrored from record_review._MAX_CONSECUTIVE_WARM_ROUNDS rather
# than reimplemented as a fresh literal: the cap a chain must hit (2
# consecutive warm=1 entries) before a following cold entry counts as
# "hit the cap and went cold." See the module docstring's REVIEW-ROUND
# CONVERGENCE RULE section.
_MAX_CONSECUTIVE_WARM_ROUNDS = 2
# Metric 7's warm-cap-refusal decision value, logged by record_review.py's
# refusal branch (`:2170-2196`) via `_lib.log(HOOK, "warm-cap-exceeded", ...)`
# into the SAME enforcement log metrics 2/3 already read -- not a new ledger.
_WARM_CAP_REFUSAL_DECISION = "warm-cap-exceeded"
# Metric 7's small-n rule: below this many warm rows in the current window,
# render raw counts with a "not yet interpretable" marker, never a percentage.
_SMALL_N_THRESHOLD = 20
# Metric 8's fan-out session-high decision value, logged by
# agent_budget.py's note_fanout_dispatch (WS2.2, PURE OBSERVER — never
# denies/delays/raises) into the SAME enforcement log metrics 2/3/7 already
# read -- not a new ledger. See the module docstring's FAN-OUT SESSION-HIGH
# RULE section.
_FANOUT_SESSION_HIGH_DECISION = "fanout-session-high"

_HELP_TEXT = """Usage: python3 ~/.claude/hooks/churn_report.py [--days N] [--json] [--help]

  --days N   Recency window (days) applied to metrics 2, 3, 5, 6, 7 only
             (default: 7). Metrics 1 (plan-review rounds) and 4 (code-review
             catch rate) are LIFETIME/cumulative and are NEVER filtered by
             --days -- see the module docstring's "--days N" section for why
             (a large fraction of real last_reviewed entries predate the
             ts= field entirely; a day filter would corrupt that
             denominator). Metric 7's rounds-per-boundary histogram is a
             partial exception: max round= spans a chain's full history
             (never truncated to the window), and a chain is listed if any
             of its rounds falls in the window -- see the module
             docstring's REVIEW-ROUND CONVERGENCE RULE section.
  --json     Emit the full report as JSON instead of a text table.
  --help     Show this message and exit.
"""


class ArgError(ValueError):
    """Raised by :func:`parse_args` on a bad CLI argument. Caught by main()."""


# ---------------------------------------------------------------------------
# Small pure time helpers.
# ---------------------------------------------------------------------------


def _parse_ts(ts: str | None) -> datetime | None:
    """Parse a `_lib._now()`-shaped timestamp, or None on any failure."""
    if not isinstance(ts, str):
        return None
    if not _TS_RE.match(ts):
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _day_of(ts: str | None) -> str | None:
    """The UTC calendar-day prefix of a well-formed ts, or None."""
    m = _TS_RE.match(ts) if isinstance(ts, str) else None
    return m.group(1) if m else None


def within_days(ts: str | None, days: int | None, now: datetime) -> bool:
    """True if `ts` is within the last `days` days of `now` (inclusive).

    `days is None` disables filtering entirely (always True). An unparseable
    `ts` is ALSO always True — this filter fails OPEN toward inclusion, so a
    ledger with a corrupt/missing timestamp is never silently dropped from a
    count it should be part of.
    """
    if days is None:
        return True
    dt = _parse_ts(ts)
    if dt is None:
        return True
    return dt >= now - timedelta(days=days)


def _max_ts(entries: list[dict], field: str = "ts") -> str | None:
    """The lexically (== chronologically, fixed-width ISO8601Z) largest
    well-formed timestamp found in `field` across `entries`, or None."""
    values = [e.get(field) for e in entries if _parse_ts(e.get(field)) is not None]
    return max(values) if values else None


def _as_int(v: object) -> tuple[int, bool]:
    """Coerce `v` to a plain int for a numeric spend field.

    Accepts a true `int` (never `bool`, an `int` subtype that is never an
    intended count here) or an integral `float` (`3.0` -> `3`). Returns
    `(value, malformed)`: `malformed` is True whenever `v` was PRESENT
    (not None) but could not be safely coerced — a bool, a non-integral
    float, a string, a list, ... — in which case `value` is `0` and the
    caller must count the occurrence rather than silently summing a wrong
    0 or 1 with no trace.
    """
    if v is None:
        return 0, False
    if isinstance(v, bool):
        return 0, True
    if isinstance(v, int):
        return v, False
    if isinstance(v, float) and v.is_integer():
        return int(v), False
    return 0, True


def group_reason_text(reason: str) -> str:
    """Collapse a free-text denial `reason` into a stable grouping key.

    See the module docstring's REASON GROUPING RULE. Redacts any quoted
    7-40-hex-char sha to `'<sha>'`, then truncates at the first em dash
    (`—`). A reason with neither is returned unchanged (stripped).
    """
    redacted = _QUOTED_SHA_RE.sub("'<sha>'", reason)
    idx = redacted.find(_EM_DASH)
    if idx == -1:
        return redacted.strip()
    return redacted[:idx].strip() or redacted.strip()


# ---------------------------------------------------------------------------
# Generic ledger I/O — the only impure layer. Absence is a distinct signal
# from "present but empty," and a mid-read failure is a distinct signal from
# both; callers must not conflate any of the three. See LEDGER READ FAILURES.
# ---------------------------------------------------------------------------


def read_jsonl(path: str) -> tuple[list[dict], dict] | None:
    """Read a JSONL file into (rows, errors), or None if path is absent.

    `errors` is always `{"skipped_unparseable": int, "read_error": str |
    None}`. A non-JSON line, or valid JSON that is not an object, increments
    `skipped_unparseable` and is dropped from `rows` — it does NOT abort the
    read. An exception that aborts the read entirely (e.g. a PermissionError
    opening a chmod-0 file) sets `read_error` to `repr(exc)`; `rows` and
    `skipped_unparseable` still reflect whatever was read before the abort —
    a partial read is reported as partial, never silently upgraded to "the
    whole file, and it was empty."
    """
    if not os.path.isfile(path):
        return None
    out: list[dict] = []
    skipped = 0
    read_error: str | None = None
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    skipped += 1
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
                else:
                    skipped += 1
    except Exception as exc:
        read_error = repr(exc)
    return out, {"skipped_unparseable": skipped, "read_error": read_error}


def read_lines(path: str) -> tuple[list[str], dict] | None:
    """Read a plain-text ledger into (non-blank stripped lines, errors), or
    None if absent. `errors` mirrors `read_jsonl`'s shape:
    `skipped_unparseable` is always 0 here (a plain-text ledger has no
    per-line structural parse step at THIS layer — an unparseable outcome
    within a line is metric 4's job, tracked separately as `"unparseable"`
    entries); `read_error` is None on a full read, else the aborting
    exception's `repr()`, with whatever lines were read before the abort
    still returned.
    """
    if not os.path.isfile(path):
        return None
    out: list[str] = []
    read_error: str | None = None
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    out.append(line.rstrip("\n"))
    except Exception as exc:
        read_error = repr(exc)
    return out, {"skipped_unparseable": 0, "read_error": read_error}


def _status_for(errors: dict) -> str:
    return "degraded" if errors.get("read_error") else "ok"


# ---------------------------------------------------------------------------
# Metric 1 — plan-review rounds per plan, with plateaus.
# ---------------------------------------------------------------------------


def plan_round_sequences(entries: list[dict]) -> dict[str, list[int]]:
    """Group plan_reviews.jsonl entries by `plan` path into a ts-ordered list
    of blocker counts (0 for a clean round). Pure. Entries are explicitly
    ts-sorted here regardless of the order they appear in `entries` — a
    ledger is append-only in principle, but a caller (or a fixture) may not
    hand them over in that order, and a round SEQUENCE is only meaningful in
    chronological order."""
    by_plan: dict[str, list[tuple[str, int]]] = {}
    for e in entries:
        plan = e.get("plan")
        if not isinstance(plan, str) or not plan:
            continue
        ts = e.get("ts") if isinstance(e.get("ts"), str) else ""
        blockers = e.get("blockers")
        if not isinstance(blockers, int):
            blockers = 0
        by_plan.setdefault(plan, []).append((ts, blockers))
    out: dict[str, list[int]] = {}
    for plan, rounds in by_plan.items():
        rounds.sort(key=lambda r: r[0])
        out[plan] = [b for _, b in rounds]
    return out


def detect_plateaus(counts: list[int]) -> tuple[int, int]:
    """A plateau is a maximal run of 2+ CONSECUTIVE, EQUAL, NON-ZERO values
    in `counts` (ts order). Returns (plateau_count, longest_run_length).

    Examples (from the spawning task, both verified by this implementation):
      [8, 8, 3, 3, 1, 1, 1, 1] -> (3, 4)   # three runs: len2, len2, len4
      [13, 0]                  -> (0, 0)   # no repeated value at all
      []                       -> (0, 0)   # no rounds at all
    A run touching 0 is never a plateau, however long — a clean review (0
    blockers) is the opposite of thrashing, never counted as it.

    PLATEAU RECONCILIATION (churn_phase0_measure.md item 3b, 2026-08-25):
    on the identical 86-row live snapshot the plan's own "24 same-count
    plateaus" and this function's count legitimately disagree, because they
    measure different things: the plan counted ADJACENT EQUAL PAIRS
    including zero-runs (pairs-any = 24); this function counts MAXIMAL
    NON-ZERO RUNS (runs-nonzero = 19). The full reconciliation table on that
    snapshot: pairs-any 24 / pairs-nonzero 23 / runs-any 20 / runs-nonzero
    19. Runs-nonzero is the intended metric — a `[3, 0, 0]` tail is
    convergence (the review went clean and stayed clean), not thrashing, and
    a pairs-based count would have counted its two adjacent zeros as one
    more "plateau." The plan's 24 is superseded by this reconciliation, not
    a bug in this function.
    """
    plateau_count = 0
    longest = 0
    i = 0
    n = len(counts)
    while i < n:
        j = i
        while j + 1 < n and counts[j + 1] == counts[i]:
            j += 1
        run_len = j - i + 1
        if counts[i] != 0 and run_len >= 2:
            plateau_count += 1
            longest = max(longest, run_len)
        i = j + 1
    return plateau_count, longest


def plan_round_metrics(entries: list[dict]) -> dict:
    """Full metric-1 payload: per-plan rounds/plateaus plus median/mean.

    `per_plan` is sorted WORST-FIRST: most rounds first (a plan needing many
    review rounds is the thrashing signal this metric exists to surface),
    ties broken by plan path for determinism.
    """
    sequences = plan_round_sequences(entries)
    per_plan = []
    total_plateaus = 0
    longest_run_overall = 0
    for plan, counts in sequences.items():
        plateau_count, longest_run = detect_plateaus(counts)
        per_plan.append(
            {
                "plan": plan,
                "rounds": len(counts),
                "plateau_count": plateau_count,
                "longest_run": longest_run,
            }
        )
        total_plateaus += plateau_count
        longest_run_overall = max(longest_run_overall, longest_run)
    round_counts = [p["rounds"] for p in per_plan]
    return {
        "plans": len(per_plan),
        "total_rounds": sum(round_counts),
        "median_rounds": statistics.median(round_counts) if round_counts else None,
        "mean_rounds": statistics.mean(round_counts) if round_counts else None,
        "total_plateaus": total_plateaus,
        "longest_plateau_run": longest_run_overall,
        "per_plan": sorted(per_plan, key=lambda p: (-p["rounds"], p["plan"])),
    }


# ---------------------------------------------------------------------------
# Metric 2 — real denials per day, by reason.
# ---------------------------------------------------------------------------


def denials_by_day_reason(entries: list[dict], days: int | None, now: datetime) -> dict:
    """Entries with `decision in {"would-block", "deny"}` AND `hook in
    _GATE_HOOKS` ONLY — every other decision value (task_gate, browser_pool,
    clean, churn-flagged, block, would-deny, ...) is a different thing (see
    the module docstring's DENIAL DECISION VALUES section), and a
    `would-block`/`deny` decision from a NON-gate hook (see GATE HOOK
    ALLOWLIST) is a different concern, not this metric's kind of command
    denial. Grouped by (UTC day, decision class, grouped reason); the raw
    reason text is kept nested one level deeper (see REASON GROUPING RULE) so
    `--json` output never loses it even though the grouped label is what the
    text table sorts and prints on. `excluded_non_gate_by_hook` counts every
    `would-block`/`deny` entry excluded by the hook allowlist, keyed by the
    offending `hook` value (or the literal `"<missing>"` for a missing/`None`
    hook) — surfaced, never silently dropped.
    """
    by_day: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    total = 0
    total_by_class: dict[str, int] = {cls: 0 for cls in _DENIAL_DECISIONS}
    excluded_non_gate_by_hook: dict[str, int] = {}
    for e in entries:
        decision = e.get("decision")
        if decision not in _DENIAL_DECISIONS:
            continue
        ts = e.get("ts")
        if not within_days(ts, days, now):
            continue
        hook = e.get("hook")
        if hook not in _GATE_HOOKS:
            key = hook if isinstance(hook, str) and hook else "<missing>"
            excluded_non_gate_by_hook[key] = excluded_non_gate_by_hook.get(key, 0) + 1
            continue
        day = _day_of(ts) or "unknown-date"
        reason = e.get("reason")
        reason = reason if isinstance(reason, str) and reason else "unknown"
        group_key = group_reason_text(reason)
        class_map = by_day.setdefault(day, {}).setdefault(decision, {})
        raw_map = class_map.setdefault(group_key, {})
        raw_map[reason] = raw_map.get(reason, 0) + 1
        total += 1
        total_by_class[decision] = total_by_class.get(decision, 0) + 1
    return {
        "total": total,
        "total_by_class": total_by_class,
        "by_day": by_day,
        "excluded_non_gate_by_hook": excluded_non_gate_by_hook,
    }


# ---------------------------------------------------------------------------
# Metric 3 — churn-flagged and contested-paths per day.
# ---------------------------------------------------------------------------


def churn_and_contested_by_day(entries: list[dict], days: int | None, now: datetime) -> dict:
    """`churn-flagged` is its own top-level `decision`; `contested-paths` is
    a `reason` under `decision == "would-block"` — see the module docstring.
    Both grouped by UTC day; top paths (by frequency, within the filtered
    window) reported for churn-flagged only, per the spawning task (the
    ledger's `contested-paths` entries carry `overlap_paths`, a LIST per
    entry, not the single `path` field churn-flagged carries, and the task
    only asked for top paths on churn-flagged)."""
    churn_by_day: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    contested_by_day: dict[str, int] = {}
    for e in entries:
        ts = e.get("ts")
        if not within_days(ts, days, now):
            continue
        day = _day_of(ts) or "unknown-date"
        decision = e.get("decision")
        if decision == "churn-flagged":
            churn_by_day[day] = churn_by_day.get(day, 0) + 1
            path = e.get("path")
            if isinstance(path, str) and path:
                path_counts[path] = path_counts.get(path, 0) + 1
        elif decision == "would-block" and e.get("reason") == "contested-paths":
            contested_by_day[day] = contested_by_day.get(day, 0) + 1
    top_paths = sorted(path_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return {
        "churn_flagged_by_day": churn_by_day,
        "churn_flagged_total": sum(churn_by_day.values()),
        "contested_paths_by_day": contested_by_day,
        "contested_paths_total": sum(contested_by_day.values()),
        "top_churn_paths": [{"path": p, "count": c} for p, c in top_paths],
    }


# ---------------------------------------------------------------------------
# Metric 4 — code-review catch rate from last_reviewed.
# ---------------------------------------------------------------------------


def parse_last_reviewed_line(line: str) -> tuple[str, str, str | None] | None:
    """Parse one `last_reviewed` line into (repo, key, rest), or None.

    Format: ``"<repo_root> <key> [<outcome> [ts=... item=...]]"``. `repo_root`
    is NOT safely splittable with a fixed field count: at least one real repo
    root on this machine contains a space ("Desktop/other project",
    verified 2026-08-25), so this scans tokens left-to-right for the first
    one that looks like a key (bare hex sha or `precommit:<hex>` — see
    `_KEY_TOKEN_RE`); everything before it is the repo path, rejoined with
    single spaces. `rest` is every token after the key, rejoined verbatim
    (the raw outcome token plus any trailing telemetry fields) — exactly the
    string `record_review.parse_outcome_token` expects — or None when
    nothing follows the key (a bare legacy 2-field line).
    """
    tokens = line.split()
    if len(tokens) < 2:
        return None
    key_idx = None
    for i in range(1, len(tokens)):
        if _KEY_TOKEN_RE.match(tokens[i]):
            key_idx = i
            break
    if key_idx is None:
        return None
    repo = " ".join(tokens[:key_idx])
    key = tokens[key_idx]
    rest_tokens = tokens[key_idx + 1 :]
    rest = " ".join(rest_tokens) if rest_tokens else None
    return (repo, key, rest)


def parse_catch_rate_entry(line: str) -> dict:
    """One `last_reviewed` line -> a dict describing it fully.

    Always carries `kind`, one of:
      * `"entry"`         — a real `clean`/`blockers:n` outcome. `status`,
        `blockers`, `era`, `repo`, `ts`, `day` are all meaningful.
      * `"bare_legacy"`   — parsed (real repo + key) but no outcome suffix.
      * `"unparseable"`   — either no key token found at all (no known
        `repo`), or a key WAS found but the trailing text didn't parse as a
        known outcome token. See the module docstring's CATCH-RATE GROUPING
        RULE for how `catch_rate_summary` buckets each kind. Even in the
        no-key-token case, the RAW line is still scanned for a recoverable
        `ts=` suffix (F6) — a garbled/truncated line can still carry a real
        timestamp, and the docstring's `unknown_repo_by_day` promises "keyed
        by day when a `ts=` is recoverable, else `unknown-date`"; without
        this scan a corrupt line with an intact `ts=` field would silently
        collapse into `unknown-date` instead.
      * `"battery"`       — a `record_review.BATTERY_PREFIX`-prefixed
        mutation-battery result line: not a review outcome and not
        corruption. MUST be checked BEFORE falling through to
        `parse_last_reviewed_line` — such a line has no `_KEY_TOKEN_RE`-
        matching token by construction (it carries no repo_root/key at all),
        so without this dedicated branch it would fall into `"unparseable"`
        and pollute the corruption count. `repo`/`key`/`era` stay `None`;
        `ts` is recovered from the bare (not `ts=`-prefixed) timestamp that
        immediately follows the prefix, via `_BATTERY_TS_RE`.

    `era` is `"precommit"` when the key starts `precommit:`, else
    `"legacy-sha"` — `None` when there is no key at all (the whole-line
    unparseable/battery cases).
    """
    if line.startswith(rr.BATTERY_PREFIX):
        m = _BATTERY_TS_RE.match(line)
        ts = m.group(1) if m else None
        return {
            "repo": None,
            "key": None,
            "era": None,
            "status": rr.OUTCOME_UNKNOWN,
            "kind": "battery",
            "blockers": 0,
            "ts": ts,
            "day": _day_of(ts),
        }
    parsed = parse_last_reviewed_line(line)
    if parsed is None:
        ts = None
        m = _TS_SUFFIX_RE.search(line)
        if m:
            ts = m.group(1)
        return {
            "repo": None,
            "key": None,
            "era": None,
            "status": rr.OUTCOME_UNKNOWN,
            "kind": "unparseable",
            "blockers": 0,
            "ts": ts,
            "day": _day_of(ts),
        }
    repo, key, rest = parsed
    era = "precommit" if key.startswith("precommit:") else "legacy-sha"
    if rest is None:
        return {
            "repo": repo,
            "key": key,
            "era": era,
            "status": rr.OUTCOME_UNKNOWN,
            "kind": "bare_legacy",
            "blockers": 0,
            "ts": None,
            "day": None,
        }
    status, n = rr.parse_outcome_token(rest)
    ts = None
    m = _TS_SUFFIX_RE.search(rest)
    if m:
        ts = m.group(1)
    kind = "entry" if status != rr.OUTCOME_UNKNOWN else "unparseable"
    return {
        "repo": repo,
        "key": key,
        "era": era,
        "status": status,
        "kind": kind,
        "blockers": n,
        "ts": ts,
        "day": _day_of(ts),
    }


def _empty_era_bucket() -> dict:
    return {
        "total_blockers": 0,
        "total_clean": 0,
        "denominator": 0,
        "rate": None,
        "by_repo_and_day": {},
    }


def catch_rate_summary(entries: list[dict]) -> dict:
    """Catch rate = blockers-ENTRIES / (blockers-entries + clean-entries),
    grouped by (era, repo, UTC day) per the module docstring's CATCH-RATE
    GROUPING RULE. The top-level `total_blockers`/`total_clean`/
    `denominator`/`rate`/`by_repo_and_day` are the PRECOMMIT-era headline
    (today's regime); `by_era` carries both eras in full, and `all_eras_*`
    gives the blended lifetime totals. `bare_legacy` and `unparseable` are
    reported separately (never folded into one constant); `unknown_repo_by_day`
    holds the unparseable-whole-line entries that have no real repo at all.
    `battery` (mutation-battery result lines) is counted separately again --
    it is neither corruption nor a review outcome, so it is excluded from
    `bare_legacy`/`unparseable`/`excluded_unknown` AND from every rate/
    denominator computed below.
    """
    bare_legacy = 0
    unparseable = 0
    battery = 0
    unknown_repo_by_day: dict[str, int] = {}
    by_era: dict[str, dict] = {}

    for e in entries:
        kind = e.get("kind")
        if kind == "bare_legacy":
            bare_legacy += 1
            continue
        if kind == "unparseable":
            unparseable += 1
            day = e.get("day") or "unknown-date"
            unknown_repo_by_day[day] = unknown_repo_by_day.get(day, 0) + 1
            continue
        if kind == "battery":
            battery += 1
            continue
        # kind == "entry": a real clean/blockers outcome with a real repo.
        era = e.get("era") or "legacy-sha"
        bucket = by_era.setdefault(era, _empty_era_bucket())
        repo = e["repo"]
        day = e.get("day") or "unknown-date"
        repo_days = bucket["by_repo_and_day"].setdefault(repo, {})
        cell = repo_days.setdefault(day, {"clean": 0, "blockers": 0})
        if e["status"] == rr.OUTCOME_CLEAN:
            bucket["total_clean"] += 1
            cell["clean"] += 1
        else:
            bucket["total_blockers"] += 1
            cell["blockers"] += 1

    for bucket in by_era.values():
        for repo_days in bucket["by_repo_and_day"].values():
            for cell in repo_days.values():
                # N13: `d` is always >= 1 here — a cell is only ever created
                # by the `setdefault` above in the SAME loop iteration that
                # immediately increments either "clean" or "blockers" by 1,
                # so the `else None` this ternary used to carry was dead,
                # unreachable code.
                d = cell["clean"] + cell["blockers"]
                cell["rate"] = cell["blockers"] / d
        denom = bucket["total_blockers"] + bucket["total_clean"]
        bucket["denominator"] = denom
        bucket["rate"] = (bucket["total_blockers"] / denom) if denom else None

    headline = by_era.get("precommit", _empty_era_bucket())
    all_blockers = sum(b["total_blockers"] for b in by_era.values())
    all_clean = sum(b["total_clean"] for b in by_era.values())
    all_denom = all_blockers + all_clean
    all_rate = (all_blockers / all_denom) if all_denom else None

    return {
        "bare_legacy": bare_legacy,
        "unparseable": unparseable,
        "excluded_unknown": bare_legacy + unparseable,
        "battery": battery,
        "unknown_repo_by_day": unknown_repo_by_day,
        "by_era": by_era,
        "headline_era": "precommit",
        "total_blockers": headline["total_blockers"],
        "total_clean": headline["total_clean"],
        "denominator": headline["denominator"],
        "rate": headline["rate"],
        "by_repo_and_day": headline["by_repo_and_day"],
        "all_eras_total_blockers": all_blockers,
        "all_eras_total_clean": all_clean,
        "all_eras_denominator": all_denom,
        "all_eras_rate": all_rate,
    }


# ---------------------------------------------------------------------------
# Metric 7 — review-round convergence (rounds/warm per prev=-linked chain,
# warm-cap refusals). See the module docstring's REVIEW-ROUND CONVERGENCE
# RULE section.
# ---------------------------------------------------------------------------


def parse_round_chain_entry(
    line: str, days: int | None, now: datetime, *, all_days: bool = False
) -> dict | None:
    """One `last_reviewed` line -> a chain-relevant dict, or None.

    Returns None for anything that is not a real, `round=`-carrying,
    in-window `entry`-kind line: a battery line, an unparseable/bare_legacy
    line, an `entry` line with no `round=` field at all (the vast majority
    of the ledger), or (unless `all_days=True`, see below) an
    in-window-excluded `ts=` (recency filter fails CLOSED here, unlike
    `within_days`'s own fail-OPEN default -- every `round=` line observed on
    this machine carries a well-formed `ts=`, so an entry with NO parseable
    `ts=` at all is not a real chain member for a windowed report and is
    excluded rather than guessed into the window; see `round_chain_metrics`
    for why this asymmetry is safe).

    `all_days=True` (blocker 4 fix) skips the `--days` filter entirely while
    still requiring a parseable `ts=` -- used ONLY to resolve chain LINKAGE
    against the full, unwindowed ledger (a chain's predecessor may sit
    outside the window; see `review_round_convergence`'s two-pass read for
    why windowing must apply at the CHAIN level, by its latest entry's `ts`,
    never by silently dropping a real predecessor from the walk).

    On a match: `{repo, key, prev, round, warm, ts}` — `repo` + `key`
    together are this entry's own ledger identity (blocker 1 fix: `key`
    alone collides across repos -- the live ledger already has
    `precommit:ae7f0e437e8750b9` recorded under three different repo roots,
    and a key-only index would silently merge their chains); `prev` is
    `None` when absent (a chain root) and is the RECORDED `--prev` spelling
    verbatim (`precommit:<hex>` or `sha:<hex>`) — never rewritten here (see
    `round_chain_metrics`'s lookup-only translation via
    `rr._ledger_lookup_key`); `round` is an `int` (malformed/non-integer
    `round=` text degrades this entry out of the metric entirely — never a
    fabricated round number); `warm` is `True` only when `warm=1` is
    present.
    """
    if line.startswith(rr.BATTERY_PREFIX):
        return None
    parsed = parse_last_reviewed_line(line)
    if parsed is None:
        return None
    repo, key, rest = parsed
    if rest is None:
        return None
    status, _n = rr.parse_outcome_token(rest)
    if status == rr.OUTCOME_UNKNOWN:
        return None
    fields = rr.parse_ledger_fields(rest)
    raw_round = fields.get("round")
    if raw_round is None:
        return None
    try:
        round_ = int(raw_round)
    except (TypeError, ValueError):
        return None
    ts = fields.get("ts")
    if _parse_ts(ts) is None:
        # Every `round=` line observed on this machine carries a well-formed
        # `ts=` (see the module docstring). A `round=` entry with no
        # parseable `ts=` is not something this metric has ever seen in
        # practice; excluding it from a windowed report is the safe default
        # (never guess a chain member into or out of a window it can't be
        # placed in) -- this is a deliberate exception to `within_days`'s
        # own fail-OPEN-toward-inclusion default, which exists for metrics
        # where a missing `ts=` is common and dropping the entry would
        # corrupt a real denominator (metric 4). Metric 7 has no such
        # denominator risk: an excluded entry here just means one fewer
        # chain link found, never a corrupted rate.
        return None
    if not all_days and not within_days(ts, days, now):
        return None
    return {
        "repo": repo,
        "key": key,
        "prev": fields.get("prev") or None,
        "round": round_,
        "warm": fields.get("warm") == "1",
        "ts": ts,
    }


def round_chain_metrics(
    chain_entries: list[dict], in_window_keys: set[tuple[str, str]] | None = None
) -> dict:
    """Group `chain_entries` (from `parse_round_chain_entry`) into
    `prev=`-linked chains and compute metric 7's rounds/warm distributions.

    A chain is identified by its ROOT **(repo, key)** pair (blocker 1 fix):
    starting from each entry, walk backward through `prev=` (mirroring
    `record_review._consecutive_warm_round_count`'s own backward walk,
    scoped to the SAME repo exactly like `record_review._existing_outcome_token`
    scopes its own ledger lookup by `repo_root`) until reaching an entry with
    no `prev=`, or a `prev=` this input doesn't contain (chain end — a
    dangling/foreign link, or the predecessor simply fell outside
    `chain_entries`; never an infinite loop, guarded by `seen`). A recorded
    `prev=` is resolved against the SAME-repo ledger key via
    `rr._ledger_lookup_key` at this lookup boundary ONLY (blocker 2 fix,
    mirroring `record_review._consecutive_warm_round_count`'s identical
    call) — a `sha:<hex>` `prev=` is translated to the bare `<hex>` the
    ledger actually stores for a plain (non-`--pre-commit`) recording
    (REGRESSION 2's fix, re-derived here rather than reimplemented); the
    RECORDED `prev` value on the returned entry is never rewritten, only the
    lookup key used to find its target. Every entry reachable from the same
    root is one chain, including a chain whose OWN first recorded round
    already carries `round=N` with no `prev=` — that entry is its own root.

    `chain_entries` may include entries from OUTSIDE the caller's `--days`
    window (see `parse_round_chain_entry`'s `all_days=True`) purely so a
    real predecessor is never missing from the walk (blocker 4). When
    `in_window_keys` is given (a set of `(repo, key)` pairs that were
    actually inside the window), a chain counts toward every returned
    metric ONLY if at least one of its members is in that set — an
    out-of-window predecessor pulled in just to complete the walk is never
    counted as its own chain, and `capped_then_cold_chains` in particular
    can now see a real cold follow-up that a hard per-entry window would
    have silently dropped (the false-negative this parameter exists to
    close). `in_window_keys=None` means "everything given is in-window"
    (the un-windowed caller, and every existing test that predates this
    parameter).

    Returns `{rounds_histogram, chains_total, warm_histogram,
    capped_then_cold_chains, chains_by_root}` — `chains_by_root` is keyed by
    the root `(repo, key)` tuple and kept (never surfaced in the rendered
    table) so callers needing the raw per-chain entry lists (tests,
    `--json` consumers) don't have to re-walk the chain themselves.

    DELIBERATE WINDOW ASYMMETRY between the two histograms: `rounds_histogram`
    uses a reported chain's FULL membership (including any out-of-window
    predecessor pulled in for linkage) — the max round= a boundary actually
    reached is a structural fact about that boundary, and truncating it to
    "whatever happened to fall in this window" would silently understate a
    chain's true round count, exactly the failure blocker 4 exists to fix.
    `warm_histogram` (and the aggregate `warm_rows_total`) count ONLY
    in-window members — both describe a SAMPLE of warm activity meant to
    match the small-n interpretability marker (`review_round_convergence`'s
    `small_n`/`warm_rows_total`), and the two must never silently disagree
    with each other (an out-of-window predecessor's warm=1 inflating one but
    not the other) — a chain reported because ONE member is in-window is not
    the same claim as "this many of its rounds were warm in this window."
    """
    by_id = {(e["repo"], e["key"]): e for e in chain_entries}

    def _root_of(repo: str, key: str) -> tuple[str, str]:
        current = (repo, key)
        seen: set[tuple[str, str]] = set()
        while True:
            if current in seen:
                return current  # a prev= cycle -- never loop forever
            seen.add(current)
            entry = by_id.get(current)
            if entry is None:
                return current
            prev = entry.get("prev")
            if not prev:
                return current
            prev_id = (current[0], rr._ledger_lookup_key(prev))
            if prev_id not in by_id:
                return current
            current = prev_id

    chains_by_root: dict[tuple[str, str], list[dict]] = {}
    for entry in chain_entries:
        root = _root_of(entry["repo"], entry["key"])
        chains_by_root.setdefault(root, []).append(entry)

    rounds_histogram: dict[int, int] = {}
    warm_histogram: dict[int, int] = {}
    capped_then_cold_chains = 0
    chains_total = 0

    for members in chains_by_root.values():
        if in_window_keys is not None and not any(
            (m["repo"], m["key"]) in in_window_keys for m in members
        ):
            continue
        chains_total += 1
        max_round = max(m["round"] for m in members)
        rounds_histogram[max_round] = rounds_histogram.get(max_round, 0) + 1

        # Only IN-WINDOW warm members are counted here -- a chain reported
        # because one member is in-window (blocker 4's cross-window linkage)
        # must not have its warm bucket inflated by an out-of-window
        # predecessor's warm=1, or this histogram's own total would silently
        # disagree with `warm_rows_total` (which is windowed the same way).
        warm_count = sum(
            1
            for m in members
            if m["warm"] and (in_window_keys is None or (m["repo"], m["key"]) in in_window_keys)
        )
        warm_histogram[warm_count] = warm_histogram.get(warm_count, 0) + 1

        # "hit the cap and went cold": walk members in TRUE chain order
        # (root-to-tip via prev= links, never a round= sort -- non-blocking
        # finding 3: round= ties break on ledger line order under a sort,
        # which is not necessarily true chain order) and find a run of
        # >= _MAX_CONSECUTIVE_WARM_ROUNDS consecutive warm=1 entries
        # immediately followed by a cold entry.
        by_member_id = {(m["repo"], m["key"]): m for m in members}
        # Root = the one member with no in-chain predecessor -- found via
        # the SAME cycle-safe walk `_root_of` uses (never a bare `next()`
        # over "no in-chain predecessor," which raises StopIteration on a
        # `prev=` SELF-reference: a real, live ledger defect found here
        # (two entries with `prev=` equal to their own key -- the exact
        # self-reference AA-0049's write-time guard exists to refuse, from
        # before that guard shipped). A self-referencing (or any cyclic)
        # single/multi-member group has no member with zero in-chain
        # predecessors by this definition; walking with a `seen` set picks
        # a stable start point instead of crashing.
        start = next(iter(by_member_id))
        current = start
        seen_root: set[tuple[str, str]] = set()
        while current not in seen_root:
            seen_root.add(current)
            prev = by_member_id[current].get("prev")
            if not prev:
                break
            prev_id = (current[0], rr._ledger_lookup_key(prev))
            if prev_id not in by_member_id:
                break
            current = prev_id
        root_id = current
        # Build tip-to-root prev links, then walk root-to-tip.
        ordered: list[dict] = []
        current_id: tuple[str, str] | None = root_id
        seen_ids: set[tuple[str, str]] = set()
        # Forward links: for each member, find who cites IT as prev=.
        cites: dict[tuple[str, str], tuple[str, str]] = {}
        for mid, member in by_member_id.items():
            prev = member.get("prev")
            if prev:
                prev_id = (mid[0], rr._ledger_lookup_key(prev))
                if prev_id in by_member_id:
                    cites[prev_id] = mid
        while current_id is not None and current_id not in seen_ids:
            seen_ids.add(current_id)
            ordered.append(by_member_id[current_id])
            current_id = cites.get(current_id)

        run = 0
        hit_cap_then_cold = False
        for member in ordered:
            if member["warm"]:
                run += 1
            else:
                if run >= _MAX_CONSECUTIVE_WARM_ROUNDS:
                    hit_cap_then_cold = True
                run = 0
        if hit_cap_then_cold:
            capped_then_cold_chains += 1

    return {
        "rounds_histogram": {str(k): v for k, v in sorted(rounds_histogram.items())},
        "chains_total": chains_total,
        "warm_histogram": {str(k): v for k, v in sorted(warm_histogram.items())},
        "warm_rows_total": sum(
            1
            for e in chain_entries
            if e["warm"] and (in_window_keys is None or (e["repo"], e["key"]) in in_window_keys)
        ),
        "capped_then_cold_chains": capped_then_cold_chains,
        "chains_by_root": chains_by_root,
    }


def warm_cap_refusals(entries: list[dict], days: int | None, now: datetime) -> int:
    """Count `decision == "warm-cap-exceeded"` entries in the enforcement
    log, windowed by `--days` exactly like metrics 2/3. Deliberately not
    restricted to metric 2's `_GATE_HOOKS` allowlist — see the module
    docstring's REVIEW-ROUND CONVERGENCE RULE section for why no allowlist
    is needed here."""
    count = 0
    for e in entries:
        if e.get("decision") != _WARM_CAP_REFUSAL_DECISION:
            continue
        if not within_days(e.get("ts"), days, now):
            continue
        count += 1
    return count


def review_round_convergence(
    last_reviewed_lines: list[str],
    log_entries: list[dict],
    days: int | None,
    now: datetime,
) -> dict:
    """Full metric-7 payload: chain distributions + warm-cap refusal count +
    the small-n interpretability marker.

    TWO-PASS READ (blocker 4 fix): chain LINKAGE is resolved against the
    FULL, unwindowed `last_reviewed_lines` (`all_days=True`) — a chain's
    predecessor may sit outside the `--days` window, and a hard per-entry
    window would silently truncate the walk, turning a real "hit the cap,
    then went cold" into a false negative (the in-window cold follow-up
    would see no warm history to complete). `in_window_keys` is the
    separate set of `(repo, key)` pairs that pass the ACTUAL `--days` filter
    (a second, windowed parse); `round_chain_metrics` uses it to decide
    which CHAINS are reported (a chain counts only if at least one member is
    in-window) without ever dropping an out-of-window predecessor from the
    walk itself. This is the "window at chain level" resolution the
    docstring's REVIEW-ROUND CONVERGENCE RULE section commits to, in
    preference to rendering a truncation caveat: the chain data volume here
    (hundreds of lines, not the enforcement log's tens of thousands) makes
    reading the ledger twice cheap, and "the reported number is sometimes
    wrong in the direction of undercounting" is a worse default than "read
    a little more data and get it right."

    `small_n` is True whenever `warm_rows_total < _SMALL_N_THRESHOLD` — the
    caller (render_table) renders raw counts with the literal
    `"n=<x>, not yet interpretable"` marker in that case, never a percentage
    computed from `warm_histogram`/`capped_then_cold_chains`.
    """
    all_entries = [
        parsed
        for line in last_reviewed_lines
        if (parsed := parse_round_chain_entry(line, None, now, all_days=True)) is not None
    ]
    in_window_keys = {
        (parsed["repo"], parsed["key"])
        for line in last_reviewed_lines
        if (parsed := parse_round_chain_entry(line, days, now)) is not None
    }
    chain_metrics = round_chain_metrics(all_entries, in_window_keys)
    chain_metrics.pop("chains_by_root")
    refusals = warm_cap_refusals(log_entries, days, now)
    warm_rows_total = chain_metrics["warm_rows_total"]
    return {
        **chain_metrics,
        "warm_cap_refusals": refusals,
        "small_n": warm_rows_total < _SMALL_N_THRESHOLD,
        "small_n_threshold": _SMALL_N_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Metric 8 — fan-out session-high (WS2.2). See the module docstring's
# FAN-OUT SESSION-HIGH RULE section.
# ---------------------------------------------------------------------------

_FANOUT_SMALL_N_FLOOR = 2  # below this many flagged sessions, no percentiles.


def _percentile_90(values: list[int]) -> float | None:
    """p90 over `values`, BOUNDED BY max(values).

    Uses `method="inclusive"`. The default `method="exclusive"`
    EXTRAPOLATES beyond the observed data, which for the small samples this
    metric sees produces a reported 90th percentile HIGHER than any session
    ever reached -- measured: `[42, 55, 91]` -> p90 **112.6** with max 91;
    `[10, 20]` -> 27.0 with max 20; `[40, 41, 42, 43, 100]` -> 122.8 with
    max 100. A report claiming a p90 no session attained is worse than no
    p90, and small n is the COMMON case here: the metric's own
    `_FANOUT_SMALL_N_FLOOR = 2` deliberately admits n=2.

    (The prior docstring called this "nearest-rank", which was wrong for
    either method -- `statistics.quantiles` interpolates in both.)

    Pure. Returns None for fewer than 2 values (quantiles requires at least
    2 data points) — the caller (fanout_session_high_summary) already
    applies its own small-n floor before calling this, but this guard keeps
    the helper safe to call standalone too.
    """
    if len(values) < 2:
        return None
    return statistics.quantiles(values, n=100, method="inclusive")[89]


def fanout_session_high_summary(entries: list[dict], days: int | None, now: datetime) -> dict:
    """Metric 8: sessions/day over WS2.2's fan-out threshold, plus the
    p50/p90/max distribution of their flagged `count`.

    Filters `entries` to `decision == _FANOUT_SESSION_HIGH_DECISION`
    (`agent_budget.note_fanout_dispatch`'s log line — see the module
    docstring's FAN-OUT SESSION-HIGH RULE section), windowed by `--days`
    exactly like metrics 2/3/5/6/7 (`within_days` fails OPEN toward
    inclusion on an unparseable `ts`, same as every other recency metric
    here). A malformed row -- missing/non-str `session`, or a `count` that
    is not a plain non-bool int -- is dropped from every list/statistic
    below and counted in `malformed`, never silently coerced into a 0 or a
    fabricated session id (mirrors `_as_int`'s own malformed-vs-silent-zero
    discipline elsewhere in this module).

    `sessions_over_threshold` is sorted count DESC (ties broken by session
    id) — the worst offenders first, matching metric 1's own
    worst-first convention. `top_agent_types` is carried through from the
    logged row VERBATIM (already computed once, at log time, by
    `record_fanout_dispatch` -- this metric never recomputes it from
    spend.jsonl).
    """
    rows: list[dict] = []
    malformed = 0
    by_day: dict[str, int] = {}
    for e in entries:
        if e.get("decision") != _FANOUT_SESSION_HIGH_DECISION:
            continue
        ts = e.get("ts")
        if not within_days(ts, days, now):
            continue
        session = e.get("session")
        count = e.get("count")
        valid_count = isinstance(count, int) and not isinstance(count, bool)
        if not (isinstance(session, str) and session) or not valid_count:
            malformed += 1
            continue
        top_agent_types = e.get("top_agent_types")
        if not isinstance(top_agent_types, list):
            top_agent_types = []
        day = _day_of(ts) or "unknown-date"
        rows.append(
            {
                "session": session,
                "count": count,
                "top_agent_types": top_agent_types,
                "day": day,
            }
        )
        by_day[day] = by_day.get(day, 0) + 1

    rows.sort(key=lambda r: (-r["count"], r["session"]))
    counts = [r["count"] for r in rows]
    small_n = len(counts) < _FANOUT_SMALL_N_FLOOR
    return {
        "sessions_over_threshold": rows,
        "sessions_over_threshold_total": len(rows),
        "sessions_over_threshold_by_day": by_day,
        "malformed": malformed,
        "small_n": small_n,
        "small_n_floor": _FANOUT_SMALL_N_FLOOR,
        "count_p50": None if small_n else statistics.median(counts),
        "count_p90": None if small_n else _percentile_90(counts),
        "count_max": max(counts) if counts else None,
    }


# ---------------------------------------------------------------------------
# Metrics 5 + 6 — spend by agent/model/day, and join-bug/reap findings.
# ---------------------------------------------------------------------------


def dedup_spend_lines(lines: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Split `lines` into (deduped-by-tool_use_id, null-tool_use_id-lines,
    malformed_tool_use_id_count).

    Lines sharing a non-null, str `tool_use_id` are collapsed to one: prefer
    any line NOT flagged `unreleased: true` (the reaper's placeholder) over
    one that is; the LAST such line wins (the file is append-only, so list
    order is chronological), covering both a double-release bug (several
    real releases for one id) and normal "placeholder then real release."
    If EVERY line for an id is `unreleased: true` (a claim reaped but never
    released), the LAST of those wins instead of the group being dropped —
    a reaped-never-released dispatch is still one dispatch, not zero. A
    `None` `tool_use_id` is NEVER deduplicated — each such line is returned
    as-is in the second list, one record per line, per the module
    docstring. A `tool_use_id` that is present but not a `str` is malformed
    (it would be unhashable as a dict key) — such a line is dropped from
    BOTH lists and counted in the returned int, never crashing and never
    silently miscounted as either a real dispatch or a stopped-unjoined
    reap.
    """
    groups: dict[str, list[dict]] = {}
    null_lines: list[dict] = []
    malformed_tid = 0
    for line in lines:
        tid = line.get("tool_use_id")
        if tid is None:
            null_lines.append(line)
            continue
        if not isinstance(tid, str):
            malformed_tid += 1
            continue
        groups.setdefault(tid, []).append(line)
    deduped: list[dict] = []
    for group in groups.values():
        preferred = [g for g in group if not g.get("unreleased")]
        chosen = preferred if preferred else group
        deduped.append(chosen[-1])
    return deduped, null_lines, malformed_tid


def _spend_bucket() -> dict[str, int]:
    return {
        "tokens_total": 0,
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "dispatches": 0,
        "duration_ms": 0,
    }


def spend_summary(deduped: list[dict]) -> dict:
    """Aggregate deduped spend lines by agent_type, model, and UTC day.

    `tokens_total` is summed exactly as each line wrote it — never
    recomputed from the four token fields here (see module docstring). The
    four token fields are always reported alongside the total, never
    replaced by it (cache_read dominates real spend; a bare total hides
    that). Every numeric field is coerced through `_as_int` (see module
    docstring's SPEND DEDUP RULE) — a non-dict `tokens`, or a field that is
    a bool/non-integral-float/string, is counted in `malformed_fields`
    rather than crashing or silently substituting a wrong 0/1.
    """
    by_agent: dict[str, dict[str, int]] = {}
    by_model: dict[str, dict[str, int]] = {}
    by_day: dict[str, dict[str, int]] = {}
    malformed_fields: dict[str, int] = {}

    def _mark(field: str) -> None:
        malformed_fields[field] = malformed_fields.get(field, 0) + 1

    for line in deduped:
        agent = line.get("agent_type") or "unknown"
        model = line.get("model") or "unknown"
        day = _day_of(line.get("ts")) or "unknown-date"

        raw_tokens = line.get("tokens")
        if isinstance(raw_tokens, dict):
            tokens = raw_tokens
        else:
            tokens = {}
            if raw_tokens is not None:
                _mark("tokens")

        tokens_total, malformed = _as_int(line.get("tokens_total"))
        if malformed:
            _mark("tokens_total")

        duration, malformed = _as_int(line.get("duration_ms"))
        if malformed:
            _mark("duration_ms")

        field_values: dict[str, int] = {}
        for field in ("input", "output", "cache_read", "cache_creation"):
            value, malformed = _as_int(tokens.get(field))
            if malformed:
                _mark(field)
            field_values[field] = value

        for store, key in ((by_agent, agent), (by_model, model), (by_day, day)):
            bucket = store.setdefault(key, _spend_bucket())
            bucket["tokens_total"] += tokens_total
            bucket["input"] += field_values["input"]
            bucket["output"] += field_values["output"]
            bucket["cache_read"] += field_values["cache_read"]
            bucket["cache_creation"] += field_values["cache_creation"]
            bucket["dispatches"] += 1
            bucket["duration_ms"] += duration

    return {
        "by_agent": by_agent,
        "by_model": by_model,
        "by_day": by_day,
        "malformed_fields": malformed_fields,
    }


def null_tool_use_id_breakdown(null_lines: list[dict], grand_total_tokens: int) -> list[dict]:
    """Per-`agent_type` breakdown of the UNJOINED ("stopped-unjoined" reap,
    null `tool_use_id`) population — F1 (2026-09-01 agentic-systems-
    architect audit): metric 5 used to report ONLY a bare count of these
    lines (`null_tool_use_id_lines`), hiding WHICH agent types the unjoined
    spend actually belongs to (the exact 26x-under-report failure mode
    #4498 measured, per `agent_budget.py`'s own docstring). Each row:
    `agent_type` (a missing/empty value buckets as "unknown", matching
    `spend_summary`'s own convention), `tokens` (summed via `_as_int` —
    malformed/non-numeric coerces to 0, never crashes), and
    `pct_of_total_tokens` — of `grand_total_tokens`, the FULL population
    (deduped + unjoined together), NOT just the unjoined subtotal, so these
    percentages are directly comparable to `by_agent`'s own tokens_total
    figures rather than a separate, harder-to-interpret denominator. Sorted
    by tokens desc, then agent_type asc for determinism. Pure function;
    never raises."""
    by_agent: dict[str, int] = {}
    for line in null_lines:
        agent = line.get("agent_type") or "unknown"
        tokens_total, _malformed = _as_int(line.get("tokens_total"))
        by_agent[agent] = by_agent.get(agent, 0) + tokens_total
    rows = [
        {
            "agent_type": agent,
            "tokens": tokens,
            "pct_of_total_tokens": (
                round(100.0 * tokens / grand_total_tokens, 2) if grand_total_tokens else 0.0
            ),
        }
        for agent, tokens in by_agent.items()
    ]
    rows.sort(key=lambda r: (-r["tokens"], r["agent_type"]))
    return rows


def reap_findings(lines: list[dict]) -> dict:
    """Counts of `reaped` stages and `late: true` lines across the FULL
    (non-deduped) line set — every reap/late line is its own finding
    regardless of `tool_use_id` dedup, which only ever governs the
    by-agent/model/day spend sums. A non-zero `stopped-unjoined` count is a
    real finding: it means a subagent completed but this code's own claim/
    stop join never matched it — a join bug, not a dispatch failure."""
    by_stage: dict[str, int] = {}
    late = 0
    for line in lines:
        stage = line.get("reaped")
        if isinstance(stage, str) and stage:
            by_stage[stage] = by_stage.get(stage, 0) + 1
        if line.get("late"):
            late += 1
    return {
        "by_stage": by_stage,
        "late": late,
        "stopped_unjoined": by_stage.get("stopped-unjoined", 0),
    }


# ---------------------------------------------------------------------------
# Report assembly.
# ---------------------------------------------------------------------------


def invocation(argv: list[str]) -> str:
    """The literal command that produced a report built with `argv`."""
    return " ".join(["python3", "~/.claude/hooks/churn_report.py", *argv])


def _absent_section(ledger: str, window: str, command: str, days: int | None = None) -> dict:
    """The fully-keyed `status: "absent"` payload for one section's ledger.

    Carries the SAME provenance keys an `"ok"`/`"degraded"` section for the
    same ledger would (`command`, `as_of`, `read_error`,
    `skipped_unparseable`, and — for a `"recency"`-window section only,
    matching the `"ok"` shape — `days`), all set to their absent-state
    values (`as_of`/`read_error` -> `None`, `skipped_unparseable` -> `0`).
    Without this, a caller (or `--json` consumer) doing `section["command"]`
    on an absent section would `KeyError` where an `"ok"` section of the same
    kind would not have.
    """
    out: dict = {
        "status": "absent",
        "ledger": ledger,
        "window": window,
        "read_error": None,
        "skipped_unparseable": 0,
        "as_of": None,
        "command": command,
    }
    if window == "recency":
        out["days"] = days
    return out


def build_report(
    days: int | None,
    now: datetime | None = None,
    plan_reviews_path: str | None = None,
    last_reviewed_path: str | None = None,
    enforcement_log_path: str | None = None,
    spend_path: str | None = None,
    argv: list[str] | None = None,
) -> dict:
    """Build the full, JSON-serializable report dict. Pure given its file
    inputs (all paths are parameters so tests never touch the real ~/.claude
    ledgers). Every one of the eight top-level metric keys is always present,
    each carrying `status: "ok"|"degraded"|"absent"` — a caller (or `--json`
    consumer) never has to guess whether a key was omitted because data was
    absent, or mistake a degraded (partially unreadable) ledger for a clean
    empty one. (`review_round_convergence`, metric 7, is `absent` whenever
    EITHER of its two underlying ledgers — `last_reviewed_path` and
    `enforcement_log_path` — is absent; it reads no ledger of its own.
    `fanout_session_high`, metric 8, shares metrics 2/3's own
    `enforcement_log_path` read and is `absent` under the identical
    condition as those two.)

    A path left as None resolves to the current module-level ``LEDGER_*``
    constant AT CALL TIME, not at import time — deliberately, so a test can
    ``monkeypatch.setattr(churn_report, "LEDGER_SPEND", ...)`` (mirroring
    every other hook module's `sandbox` fixture pattern) and have it actually
    take effect; a bound default parameter (``= LEDGER_SPEND``) would freeze
    the value at module-load time and silently ignore the monkeypatch.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if plan_reviews_path is None:
        plan_reviews_path = LEDGER_PLAN_REVIEWS
    if last_reviewed_path is None:
        last_reviewed_path = LEDGER_LAST_REVIEWED
    if enforcement_log_path is None:
        enforcement_log_path = LEDGER_ENFORCEMENT_LOG
    if spend_path is None:
        spend_path = LEDGER_SPEND
    command = invocation(argv or [])
    report: dict = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        "command": command,
    }

    # --- Metric 1: plan-review rounds (LIFETIME — --days never applies) ----
    plan_result = read_jsonl(plan_reviews_path)
    if plan_result is None:
        report["plan_review_rounds"] = _absent_section(plan_reviews_path, "lifetime", command)
    else:
        plan_entries, plan_errors = plan_result
        report["plan_review_rounds"] = {
            "status": _status_for(plan_errors),
            "ledger": plan_reviews_path,
            "window": "lifetime",
            "read_error": plan_errors["read_error"],
            "skipped_unparseable": plan_errors["skipped_unparseable"],
            "as_of": _max_ts(plan_entries),
            "command": command,
            **plan_round_metrics(plan_entries),
        }

    # --- Metrics 2 + 3 + 8: enforcement log (RECENCY window) ---------------
    log_result = read_jsonl(enforcement_log_path)
    if log_result is None:
        report["denials_by_reason"] = _absent_section(
            enforcement_log_path, "recency", command, days
        )
        report["churn_and_contested"] = _absent_section(
            enforcement_log_path, "recency", command, days
        )
        report["fanout_session_high"] = _absent_section(
            enforcement_log_path, "recency", command, days
        )
    else:
        log_entries, log_errors = log_result
        status = _status_for(log_errors)
        as_of = _max_ts(log_entries)
        report["denials_by_reason"] = {
            "status": status,
            "ledger": enforcement_log_path,
            "window": "recency",
            "read_error": log_errors["read_error"],
            "skipped_unparseable": log_errors["skipped_unparseable"],
            "as_of": as_of,
            "command": command,
            "days": days,
            **denials_by_day_reason(log_entries, days, now),
        }
        report["churn_and_contested"] = {
            "status": status,
            "ledger": enforcement_log_path,
            "window": "recency",
            "read_error": log_errors["read_error"],
            "skipped_unparseable": log_errors["skipped_unparseable"],
            "as_of": as_of,
            "command": command,
            "days": days,
            **churn_and_contested_by_day(log_entries, days, now),
        }
        # Metric 8 (WS2.2) — same ledger as metrics 2/3, no new read.
        report["fanout_session_high"] = {
            "status": status,
            "ledger": enforcement_log_path,
            "window": "recency",
            "read_error": log_errors["read_error"],
            "skipped_unparseable": log_errors["skipped_unparseable"],
            "as_of": as_of,
            "command": command,
            "days": days,
            **fanout_session_high_summary(log_entries, days, now),
        }

    # --- Metric 4: catch rate (LIFETIME — --days never applies) ------------
    lr_result = read_lines(last_reviewed_path)
    if lr_result is None:
        report["catch_rate"] = _absent_section(last_reviewed_path, "lifetime", command)
    else:
        lr_lines, lr_errors = lr_result
        cr_entries = [parse_catch_rate_entry(line) for line in lr_lines]
        report["catch_rate"] = {
            "status": _status_for(lr_errors),
            "ledger": last_reviewed_path,
            "window": "lifetime",
            "read_error": lr_errors["read_error"],
            "skipped_unparseable": lr_errors["skipped_unparseable"],
            "as_of": _max_ts(cr_entries),
            "command": command,
            **catch_rate_summary(cr_entries),
        }

    # --- Metric 7: review-round convergence (RECENCY window) ---------------
    # Reads BOTH ledgers metric 4 and metrics 2/3 already read (lr_result /
    # log_result, from above) -- never a third ledger read. Absent when
    # EITHER underlying ledger is absent (a chain needs both the round/prev
    # data from last_reviewed AND the refusal count from the enforcement
    # log to be a complete metric-7 report); degraded when either is
    # degraded, mirroring every other section's read_error convention.
    m7_combined_ledger = f"{last_reviewed_path} + {enforcement_log_path}"
    if lr_result is None or log_result is None:
        # Non-blocking finding 5: `ledger` names the SAME combined "a + b"
        # string the "ok" branch below uses (never a single-ledger name that
        # would make an `"ok"` and an `"absent"` section for this one metric
        # report a differently-shaped `ledger` value) -- `missing_ledger`
        # separately names WHICH of the two was actually absent, via its own
        # key, never folded into `ledger` itself.
        missing_ledger = last_reviewed_path if lr_result is None else enforcement_log_path
        m7_absent = _absent_section(m7_combined_ledger, "recency", command, days)
        m7_absent["missing_ledger"] = missing_ledger
        report["review_round_convergence"] = m7_absent
    else:
        lr_lines_m7, lr_errors_m7 = lr_result
        log_entries_m7, log_errors_m7 = log_result
        combined_errors = {
            "read_error": lr_errors_m7["read_error"] or log_errors_m7["read_error"],
            "skipped_unparseable": (
                lr_errors_m7["skipped_unparseable"] + log_errors_m7["skipped_unparseable"]
            ),
        }
        m7 = review_round_convergence(lr_lines_m7, log_entries_m7, days, now)
        m7_as_of_candidates = [
            {"ts": parse_catch_rate_entry(line).get("ts")} for line in lr_lines_m7
        ] + log_entries_m7
        report["review_round_convergence"] = {
            "status": _status_for(combined_errors),
            "ledger": m7_combined_ledger,
            "missing_ledger": None,
            "window": "recency",
            "read_error": combined_errors["read_error"],
            "skipped_unparseable": combined_errors["skipped_unparseable"],
            "as_of": _max_ts(m7_as_of_candidates),
            "command": command,
            "days": days,
            **m7,
        }

    # --- Metrics 5 + 6: spend ledger (RECENCY window) -----------------------
    spend_result = read_jsonl(spend_path)
    if spend_result is None:
        report["spend"] = _absent_section(spend_path, "recency", command, days)
        report["reap_findings"] = _absent_section(spend_path, "recency", command, days)
    else:
        spend_lines, spend_errors = spend_result
        status = _status_for(spend_errors)
        filtered = [ln for ln in spend_lines if within_days(ln.get("ts"), days, now)]
        deduped, null_lines, malformed_tid = dedup_spend_lines(filtered)
        summary = spend_summary(deduped)
        malformed_fields = dict(summary.pop("malformed_fields"))
        if malformed_tid:
            malformed_fields["tool_use_id"] = malformed_tid
        as_of = _max_ts(spend_lines)
        # F1 (2026-09-01 agentic-systems-architect audit): the unjoined
        # ("stopped-unjoined" reap, null tool_use_id) population used to be
        # a bare footnote count -- grand_total_tokens is the FULL population
        # (deduped + unjoined together) so null_tool_use_id_breakdown's own
        # pct_of_total_tokens is directly comparable to by_agent's figures.
        deduped_tokens_total = sum(b["tokens_total"] for b in summary["by_model"].values())
        null_tokens_total = sum(_as_int(ln.get("tokens_total"))[0] for ln in null_lines)
        grand_total_tokens = deduped_tokens_total + null_tokens_total
        report["spend"] = {
            "status": status,
            "ledger": spend_path,
            "window": "recency",
            "read_error": spend_errors["read_error"],
            "skipped_unparseable": spend_errors["skipped_unparseable"],
            "as_of": as_of,
            "command": command,
            "days": days,
            "dispatches": len(deduped),
            "null_tool_use_id_lines": len(null_lines),
            "null_tool_use_id_breakdown": null_tool_use_id_breakdown(null_lines, grand_total_tokens),
            "malformed_fields": malformed_fields,
            **summary,
        }
        report["reap_findings"] = {
            "status": status,
            "ledger": spend_path,
            "window": "recency",
            "read_error": spend_errors["read_error"],
            "skipped_unparseable": spend_errors["skipped_unparseable"],
            "as_of": as_of,
            "command": command,
            "days": days,
            **reap_findings(filtered),
        }

    return report


# ---------------------------------------------------------------------------
# Table rendering.
# ---------------------------------------------------------------------------


def _section(title: str) -> str:
    return f"\n--- {title} ---"


def _provenance(section: dict) -> str:
    if section.get("status") == "absent":
        missing = section.get("missing_ledger")
        suffix = f" (missing: {missing})" if missing else ""
        return f"{section['ledger']}: ABSENT{suffix}"
    if section.get("status") == "degraded":
        return (
            f"{section['ledger']}: DEGRADED (read_error={section.get('read_error')}, "
            f"skipped_unparseable={section.get('skipped_unparseable')}) — "
            f"as of {section.get('as_of') or 'unknown'} — {section.get('command')}"
        )
    extra = ""
    skipped = section.get("skipped_unparseable")
    if skipped:
        extra = f" (skipped_unparseable={skipped})"
    return f"as of {section.get('as_of') or 'unknown'} — {section.get('command')}{extra}"


def _window_note(section: dict) -> str | None:
    if section.get("window") == "lifetime":
        return "window: LIFETIME (--days does not apply)"
    return None


def render_table(report: dict) -> str:  # noqa: C901 - a linear report renderer
    """Render the full report as a plain-text table for terminal output."""
    lines: list[str] = []
    lines.append(f"=== churn report — generated {report['generated_at']} ===")
    lines.append(
        f"days window: {report['days']} (metrics 2,3,5,6,7 only)  |  command: {report['command']}"
    )

    p1 = report["plan_review_rounds"]
    lines.append(_section("1. Plan-review rounds per plan (plateaus flagged)"))
    lines.append(_provenance(p1))
    note = _window_note(p1)
    if note:
        lines.append(note)
    if p1.get("status") in ("ok", "degraded"):
        lines.append(
            f"plans={p1['plans']} total_rounds={p1['total_rounds']} "
            f"median_rounds={p1['median_rounds']} mean_rounds={p1['mean_rounds']:.2f}"
            if p1["plans"]
            else "plans=0 total_rounds=0"
        )
        lines.append(
            f"total_plateaus={p1['total_plateaus']} longest_plateau_run={p1['longest_plateau_run']}"
        )
        for row in p1["per_plan"][:15]:
            lines.append(
                f"  rounds={row['rounds']:<3} plateaus={row['plateau_count']:<2} "
                f"longest={row['longest_run']:<2} {row['plan']}"
            )

    p2 = report["denials_by_reason"]
    lines.append(
        _section(
            "2. Real denials per day, by reason "
            "(decision in {would-block, deny}, hook in gate allowlist)"
        )
    )
    lines.append(_provenance(p2))
    if p2.get("status") in ("ok", "degraded"):
        lines.append(f"total={p2['total']} total_by_class={p2['total_by_class']}")
        if p2.get("excluded_non_gate_by_hook"):
            lines.append(f"  excluded_non_gate_by_hook={p2['excluded_non_gate_by_hook']}")
        for day in sorted(p2["by_day"]):
            for decision_class in sorted(p2["by_day"][day]):
                group_map = p2["by_day"][day][decision_class]
                rows = [(sum(raws.values()), group_key) for group_key, raws in group_map.items()]
                for count, group_key in sorted(rows, key=lambda kv: (-kv[0], kv[1])):
                    lines.append(f"  {day}  {count:<5} [{decision_class}] {group_key}")

    p3 = report["churn_and_contested"]
    lines.append(_section("3. churn-flagged / contested-paths per day"))
    lines.append(_provenance(p3))
    if p3.get("status") in ("ok", "degraded"):
        lines.append(
            f"churn_flagged_total={p3['churn_flagged_total']} "
            f"contested_paths_total={p3['contested_paths_total']}"
        )
        for day in sorted(set(p3["churn_flagged_by_day"]) | set(p3["contested_paths_by_day"])):
            churn = p3["churn_flagged_by_day"].get(day, 0)
            contested = p3["contested_paths_by_day"].get(day, 0)
            lines.append(f"  {day}  churn-flagged={churn:<5} contested-paths={contested}")
        if p3["top_churn_paths"]:
            lines.append("  top churn-flagged paths:")
            for row in p3["top_churn_paths"]:
                annotation = (
                    "  (known writer defect, step 4)"
                    if row["path"] in _KNOWN_REDIRECT_TOKEN_DEFECT
                    else ""
                )
                lines.append(f"    {row['count']:<4} {row['path']}{annotation}")

    p4 = report["catch_rate"]
    lines.append(_section("4. Code-review catch rate (last_reviewed ledger, precommit headline)"))
    lines.append(_provenance(p4))
    note = _window_note(p4)
    if note:
        lines.append(note)
    if p4.get("status") in ("ok", "degraded"):
        rate = p4["rate"]
        rate_str = f"{rate:.3f}" if rate is not None else "n/a"
        lines.append(
            f"[precommit] blockers={p4['total_blockers']} clean={p4['total_clean']} "
            f"denominator={p4['denominator']} rate={rate_str}"
        )
        legacy = p4["by_era"].get("legacy-sha")
        if legacy:
            lrate = legacy["rate"]
            lrate_str = f"{lrate:.3f}" if lrate is not None else "n/a"
            lines.append(
                f"[legacy-sha, superseded] blockers={legacy['total_blockers']} "
                f"clean={legacy['total_clean']} denominator={legacy['denominator']} "
                f"rate={lrate_str}"
            )
        lines.append(
            f"bare_legacy={p4['bare_legacy']} unparseable={p4['unparseable']} "
            f"excluded_unknown={p4['excluded_unknown']} battery={p4.get('battery', 0)}"
        )
        # F10: per-repo lines for the precommit era, ALL of them, blockers
        # desc — day-level detail stays JSON-only (by_repo_and_day).
        repo_totals = []
        for repo, days_map in p4["by_repo_and_day"].items():
            blockers = sum(c["blockers"] for c in days_map.values())
            clean = sum(c["clean"] for c in days_map.values())
            repo_totals.append((blockers, clean, repo))
        repo_totals.sort(key=lambda t: (-t[0], t[2]))
        if repo_totals:
            lines.append("  precommit era, by repo (blockers desc):")
            for blockers, clean, repo in repo_totals:
                d = blockers + clean
                rate_repo = f"{(blockers / d):.3f}" if d else "n/a"
                lines.append(
                    f"    blockers={blockers:<4} clean={clean:<4} rate={rate_repo:<6} {repo}"
                )

    p5 = report["spend"]
    lines.append(_section("5. Spend by agent / model / day"))
    lines.append(_provenance(p5))
    if p5.get("status") in ("ok", "degraded"):
        lines.append(
            f"dispatches={p5['dispatches']} null_tool_use_id_lines={p5['null_tool_use_id_lines']}"
        )
        if p5["malformed_fields"]:
            lines.append(f"  malformed_fields={p5['malformed_fields']}")
        breakdown = p5.get("null_tool_use_id_breakdown") or []
        if breakdown:
            lines.append("  unjoined (stopped-unjoined reap, null tool_use_id) by agent:")
            for row in breakdown:
                lines.append(
                    f"    {row['agent_type']:<20} tokens={row['tokens']:<12} "
                    f"pct_of_total_tokens={row['pct_of_total_tokens']}"
                )
        lines.append("  by agent:")
        for agent, b in sorted(p5["by_agent"].items()):
            lines.append(
                f"    {agent:<20} dispatches={b['dispatches']:<4} "
                f"tokens_total={b['tokens_total']:<10} "
                f"input={b['input']} output={b['output']} "
                f"cache_read={b['cache_read']} cache_creation={b['cache_creation']} "
                f"duration_ms={b['duration_ms']}"
            )
        lines.append("  by model:")
        for model, b in sorted(p5["by_model"].items()):
            lines.append(
                f"    {model:<28} dispatches={b['dispatches']:<4} "
                f"tokens_total={b['tokens_total']}"
            )

    p6 = report["reap_findings"]
    lines.append(_section("6. Join-bug / reap findings"))
    lines.append(_provenance(p6))
    if p6.get("status") in ("ok", "degraded"):
        lines.append(f"by_stage={p6['by_stage']} late={p6['late']}")
        if p6["stopped_unjoined"]:
            lines.append(
                f"FINDING: {p6['stopped_unjoined']} stopped-unjoined dispatch(es) — a "
                "SubagentStop record never found a matching claim (a join bug in "
                "agent_budget.py, not a dispatch failure)."
            )

    p7 = report["review_round_convergence"]
    lines.append(_section("7. Review-round convergence (round=/warm=/prev= chains)"))
    lines.append(_provenance(p7))
    if p7.get("status") in ("ok", "degraded"):
        lines.append(f"chains_total={p7['chains_total']}")
        lines.append("  rounds-per-boundary (max round= per prev=-linked chain):")
        lines.append(
            "  (max round= spans a chain's full history; a chain is listed if any "
            "round falls in the window)"
        )
        if p7["rounds_histogram"]:
            for round_value in sorted(p7["rounds_histogram"], key=int):
                lines.append(f"    round={round_value:<3} chains={p7['rounds_histogram'][round_value]}")
        else:
            lines.append("    (no round=-carrying chains in this window)")

        if p7["small_n"]:
            lines.append(
                f"  warm-round distribution: n={p7['warm_rows_total']}, not yet interpretable"
            )
        else:
            lines.append(f"  warm-round distribution (n={p7['warm_rows_total']}):")
        if p7["warm_histogram"]:
            for warm_count in sorted(p7["warm_histogram"], key=int):
                lines.append(
                    f"    warm_rounds={warm_count:<2} chains={p7['warm_histogram'][warm_count]}"
                )
        lines.append(
            f"  chains that hit the {_MAX_CONSECUTIVE_WARM_ROUNDS}-warm cap and went cold: "
            f"{p7['capped_then_cold_chains']}"
        )
        lines.append(f"  warm-cap refusals (record_review.py:2170-2196): {p7['warm_cap_refusals']}")

    p8 = report["fanout_session_high"]
    lines.append(_section("8. Fan-out session-high (WS2.2 observer — never denies)"))
    lines.append(_provenance(p8))
    if p8.get("status") in ("ok", "degraded"):
        lines.append(f"sessions_over_threshold={p8['sessions_over_threshold_total']}")
        if p8.get("malformed"):
            lines.append(f"  malformed={p8['malformed']}")
        for day in sorted(p8["sessions_over_threshold_by_day"]):
            lines.append(f"  {day}  sessions_over_threshold={p8['sessions_over_threshold_by_day'][day]}")
        if p8["small_n"]:
            lines.append(
                f"  count distribution: n={p8['sessions_over_threshold_total']}, "
                "not yet interpretable"
            )
        else:
            p50 = p8["count_p50"]
            p90 = p8["count_p90"]
            lines.append(
                f"  count distribution: p50={p50:.1f} p90={p90:.1f} max={p8['count_max']}"
            )
        if p8["count_max"] is not None and p8["small_n"]:
            lines.append(f"  count_max={p8['count_max']}")
        if p8["sessions_over_threshold"]:
            lines.append("  flagged sessions (count desc):")
            for row in p8["sessions_over_threshold"][:15]:
                top = ", ".join(
                    f"{t.get('agent_type')}:{t.get('count')}" for t in row["top_agent_types"]
                )
                lines.append(f"    {row['day']}  count={row['count']:<4} {row['session']}  top=[{top}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> tuple[int | None, bool]:
    """Parse `--days N` (default DEFAULT_DAYS) and `--json`. Pure; raises
    ArgError on a bad value rather than exiting directly, so it is trivially
    testable. `--help`/`-h` are handled by `main()` before this is called."""
    days: int | None = DEFAULT_DAYS
    as_json = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--days":
            i += 1
            if i >= len(argv):
                raise ArgError("--days needs a value")
            days = _parse_days_value(argv[i])
        elif arg.startswith("--days="):
            days = _parse_days_value(arg.split("=", 1)[1])
        elif arg == "--json":
            as_json = True
        else:
            raise ArgError(f"unknown argument {arg!r}")
        i += 1
    return days, as_json


def _parse_days_value(raw: str) -> int:
    try:
        value = int(raw)
    except Exception as exc:
        raise ArgError(f"--days needs an integer, got {raw!r}") from exc
    if value <= 0:
        raise ArgError(f"--days must be a positive integer, got {value}")
    return value


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in raw_argv or "-h" in raw_argv:
        print(_HELP_TEXT)
        return 0
    try:
        days, as_json = parse_args(raw_argv)
    except ArgError as exc:
        print(f"churn_report: {exc}", file=sys.stderr)
        return 2
    report = build_report(days, argv=raw_argv)
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_table(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI entry
    sys.exit(main())
