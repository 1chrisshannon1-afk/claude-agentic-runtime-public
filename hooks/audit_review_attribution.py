#!/usr/bin/env python3
"""audit_review_attribution — offline join of the review ledger to the
dispatch-lease ledger (gate-optimization plan, Item 6b).

WHAT THIS IS, PRECISELY (read before touching anything)
---------------------------------------------------------
This closes the **AUDIT** gap only: "can we later tell a real sub-agent
review from a self-clear by the orchestrator." It does **not** close the
**ENFORCEMENT** gap: nothing here blocks a `--clean` recording at commit
time, and nothing here is wired into `pretooluse_bash.py`'s gate chain.
This module never writes anything, never denies anything, and is never
invoked as a hook. It is a standalone report, run by hand or from a future
scheduled audit job, exactly like `churn_report.py`.

Building true enforcement (e.g. gate 3b refusing an unattributed `clean`
entry) is explicitly OUT OF SCOPE for this item — see the gate-optimization
plan's own Item 6b section. Do not extend this module into one.

THE THREAT MODEL, AND WHY SESSION-ID STAMPING DOES NOT WORK
---------------------------------------------------------------
The gameable case this audit exists to catch: an orchestrating session
records `record_review.py --clean` itself, with no real `code-reviewer` /
`trust-architect` sub-agent ever having run — indistinguishable, from gate
3b's point of view, from a genuine review. `record_review.py` §10 of
CLAUDE.md already warns "never self-record --clean with no review of any
kind"; this module makes that norm auditable against CASUAL or ACCIDENTAL
mismatches — see LIMITATIONS below for exactly what it does NOT catch.

A session-id join was considered and rejected: `_lib.session_id`'s own
docstring states plainly that "a sub-agent's payload carries the SAME
session_id as its parent session (no separate identity)" — verified
directly against real `~/.claude/.agent_budget/spend.jsonl` rows, where
every sub-agent dispatch (agent_type in {implement, code-reviewer, ...})
made by one orchestrating session carries `session` identical to that
session's own id. A session-id join could therefore never distinguish "the
orchestrator recorded this itself" from "a real code-reviewer sub-agent
produced this outcome" — the two cases are IDENTICAL under a session-id
join, which is exactly why Item 6b instead joins on `agent_id`/
`tool_use_id`: both are minted PER DISPATCH (unique to one specific Task
invocation — see `agent_budget._build_claim_record`/
`classify_release_event`), a strictly finer granularity than session-id
that is at least CAPABLE, in principle, of telling a self-clear apart from
a real review. Per LIMITATIONS below, "capable in principle" is not the
same as "closed" — a `matched` verdict still does not, by itself, prove
which of the two actually happened.

LIMITATIONS — WHAT A `matched` VERDICT DOES NOT PROVE (2026-08-30, trust-
architect review round on Item 6b)
---------------------------------------------------------------
`agent_id`, `tool_use_id`, AND `rekey=` (added 2026-09-01, AA-0064 Item 8;
this note extended 2026-09-01 fix round 3, Finding 2) are ALL
SELF-REPORTED: the caller of `record_review.py --reviewer-agent-id ...
--reviewer-tool-use-id ...` (or `--rekey <key>`) simply types whatever
values it wants, and the ONLY place in this codebase that exposes a real,
obtainable `(agent_id, tool_use_id)` pair to cite is
`~/.claude/.agent_budget/spend.jsonl` itself — the exact ledger this
module joins against (verified: no env var or other surface exposes an
orchestrator's own dispatch identity anywhere in this codebase — `grep -rn
"CSA_AGENT_ID\\|CSA_TOOL_USE_ID" hooks/` finds nothing). A session with read
access to `spend.jsonl` (every session has this) can therefore copy ANY
real reviewer row's `(agent_id, tool_use_id)` pair verbatim into a
`--clean` recording it never earned, and that recording will show
`matched` — proven directly: forging 2 fabricated `clean` entries this way
produced two `matched` verdicts, zero flags, with no binding whatsoever to
the citing review's own repo/digest. `rekey=` is exactly as forgeable, and
this is only PARTIALLY closed (2026-09-01, fix rounds 3-4 — stated
precisely here so this section is never read as claiming more than it
does): a fabricated entry can cite ANY real clean key's own `(repo, key)`
as its `rekey=` regardless of whether it shares that entry's identity.
The DIFFERENT-identity variant IS closed — Finding 2's exact-pair
requirement (`audit_clean_entries` only exempts a star member whose OWN
identity pair equals its root's) plus the fix round 4 root-corroboration
requirement (the root itself must have been independently `matched`, never
merely another fabricated entry) together mean an invented identity gets
ZERO benefit from citing a real, corroborated root — it must corroborate
on its own merits like any other entry. The SAME-identity variant is NOT
closed and cannot be, at this module's level: a forger who copies a REAL,
GENUINELY-`matched` root's EXACT `(agent_id, tool_use_id)` pair, and cites
that SAME root's real key as `rekey=`, produces an entry this module
cannot distinguish from a legitimate mechanical carry-forward — both are,
from here, "a clean entry sharing a real corroborated reviewer's exact
identity, explained by a rekey= link to that same reviewer's own prior
review." This is the identical, pre-existing, already-documented
`matched`/`reused` limitation below (a forger with ordinary `spend.jsonl`
read access can always copy a real row's identity) — the rekey= mechanism
does not create a NEW hole here, it merely gives that same old hole one
more shape. Unavoidable without binding identity to something the caller
cannot self-report (out of scope for this item; see the module's own
framing above), not a bug this round left unfixed.

So: a `matched` verdict proves a CITABLE dispatch existed somewhere in
`spend.jsonl`'s ~5-6 day retention window — it does NOT prove that dispatch
reviewed THIS specific diff, or that the entry citing it is the dispatch's
own legitimate output rather than a copy-pasted identity. This closes the
audit gap only against CASUAL/ACCIDENTAL mismatches (a stale copy-paste
from an old review, a wrong repo, a typo) — never against a DELIBERATE
forger with ordinary read access to `spend.jsonl`, which is every session.
The `reused` bucket below (a pair cited by more than one `clean` entry)
catches the CHEAPEST version of that deliberate forgery — copying one real
row's identity more than once — but a forger who copies a DIFFERENT real
row's identity into each fabricated entry defeats even `reused`. Building
real enforcement against a motivated forger is explicitly out of scope for
this item (see the module's own framing above); this audit's job is to
make the norm violation VISIBLE and CHEAP TO DETECT for the common case,
not to make forgery cryptographically impossible.

RETENTION WINDOW CEILING: `spend.jsonl` only retains ~5-6 days of rows (its
own README documents no rotation to a longer history), and
`daily_spend_rollup.py`'s aggregation destroys `agent_id`/`tool_use_id`
permanently at roll-off (it aggregates by `(agent_type, model)` only, never
those two id fields). A `clean` entry older than ~5-6 days is therefore
PERMANENTLY, INDISTINGUISHABLY `unmatched` — the exact same verdict a
genuine forgery gets — because the row it could have matched against no
longer exists to check. Run this audit inside that window (see the daily
oversight job's own pre-step for how) or its findings for anything older
are structurally unusable, not just stale.

HOW THE JOIN WORKS
---------------------
`record_review.py` (Item 6b) optionally writes a compound
`reviewer=<type>#<agent_id>#<tool_use_id>` value (see
`record_review.compose_reviewer_field`/`parse_reviewer_value`) instead of a
bare reviewer-of-record TYPE string. For every `clean` entry in
`~/.claude/.review_state/last_reviewed` that carries this compound
identity, this module looks for a matching row in
`~/.claude/.agent_budget/spend.jsonl` — one whose `agent_id` AND
`tool_use_id` both match, whose `agent_type` is a real reviewer-of-record
type (`_REVIEWER_AGENT_TYPES`), and whose own `ts` falls within
`--window-seconds` (default 1800s / 30min) of the review's own `ts=`. A
`clean` entry is FLAGGED when:
  * it carries no identity at all (`no-identity` — every entry recorded
    before Item 6b shipped, and any `--clean` call that never supplied
    `--reviewer-agent-id`/`--reviewer-tool-use-id`), or
  * it carries an identity but no matching spend.jsonl row is found within
    the window (`unmatched` — the review record's own claimed dispatch
    cannot be corroborated), or
  * its `(agent_id, tool_use_id)` pair is cited by MORE THAN ONE `clean`
    entry across the whole ledger (`reused` — a legitimate review dispatch
    is used exactly once, so a repeated citation is the cheapest possible
    forgery: copy one real reviewer row's identity into a second `clean`
    entry. This OVERRIDES whatever `matched`/`unmatched` verdict the join
    above produced, for EVERY entry sharing that pair, not just the
    "second" one — see `_find_reused_pairs`/`audit_clean_entries`).
An entry with a matching row, whose identity is cited by exactly one
`clean` entry, is `matched` and NOT flagged. See LIMITATIONS above for what
`matched` does and does not prove.

REKEY EXEMPTION (2026-09-01, fix round 2 BLOCKER; generalized to STARS and
tightened to exact-pair-only in fix round 3, Findings 1 and 2):
`record_review.py --rekey` (AA-0064, Item 8) legitimately carries a prior
entry's exact `reviewer=<type>#<agent_id>#<tool_use_id>` identity forward
AND writes a `rekey=<key>` provenance field. As of fix round 3, that key is
ALWAYS the chain's ROOT (record_review.py's own root-resolution block
follows a cited prior's own `rekey=` one hop, refusing rather than walking
further) — so every legitimate carry-forward relationship is a STAR (every
member points directly at the same root), never a longer chain. Without
this module's own exemption, EVERY successful `--rekey` would flip both
itself and its root to `reused` (the re-cited pair), and a rekey entry's
own fresh `ts=` routinely falls outside `window_seconds` of the ORIGINAL
spend.jsonl dispatch its root cites, so it independently reads `unmatched`
too — this module would report forgery on every legitimate mechanical
carry-forward. `_root_star_groups`/`audit_clean_entries` exempt this shape
into a NEW, NOT-flagged verdict, `rekey-exempt` — see that function's own
docstring for the exact (narrow, forger-safe, EXACT-PAIR-ONLY per Finding
2) boundary. A LEGACY multi-hop chain written by the pre-fix writer, or a
fabricated mutual A<->B reference, forms NO star at all (see
`_root_star_groups`'s own one-hop/true-root boundary) and is deliberately
left flagged — the safe-direction over-flag, never silently exempted. This
is a CODE-level exemption, unlike the older warm-round `prev=`/`round=`
chain shape (CLAUDE.md §10), which this module's own daily-sweep caveat
still only documents as manual triage prose pending its own #4686
exemption — the rekey shape is new and fully under this module's own
control, so it did not need to wait.

`blockers:n` entries are parsed and available in the full `results` list
for completeness, but are NOT part of `flagged`/the headline counts — the
plan's own stated property is specifically about `clean` entries (a
self-clear is gameable exactly because it reports a CLEAN outcome with no
findings to check; a `blockers` entry is self-defeating to fake).

This is a PURE READER, mirroring churn_report.py's own contract: no LLM
call, no ledger write, no side effect of any kind. It reads at most two
files (`last_reviewed`, `spend.jsonl`) and computes everything else in
memory. A missing ledger is reported as `ABSENT`, never silently zeroed —
see `churn_report.py`'s own LEDGER READ FAILURES section for why (the same
`read_lines`/`read_jsonl` readers are reused here unchanged).

Usage:
    python3 ~/.claude/hooks/audit_review_attribution.py [--window-seconds N] [--only unmatched|reused|no-identity|superseded] [--json] [--help]
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import churn_report as cr  # noqa: E402  (reuse the proven ledger I/O + line tokenizer)
import record_review as rr  # noqa: E402  (reuse the outcome/field/reviewer-identity parsers)

DEFAULT_WINDOW_SECONDS = 1800  # 30 minutes

# MAJOR finding (2026-08-30 trust-architect review): a live run against real
# data printed 1,206 flagged lines with no cap, burying the actionable
# signal (unmatched/reused) under ~1,200 lines of expected `no-identity`
# noise from legacy pre-Item-6b entries. Mirrors churn_report.py's own
# `top_churn_paths`/`per_plan` render caps (`[:10]`/`[:15]`) — this module
# picks 10 to match the narrower of the two (the one that, like this list,
# is itself a "worst offenders" view rather than a full per-day series).
_MAX_FLAGGED_SHOWN = 10

# The flagged attribution categories a caller can filter the table (and
# JSON) down to via `--only`. Deliberately closed: an unrecognized value is
# a caller mistake worth rejecting loudly, not silently ignoring.
#
# `"superseded"` was added 2026-09-09 (#5133 F3/Blocker 1(b)):
# `superseded` entries are deliberately excluded from `flagged` (they are
# NOT a forgery signal — see `audit_clean_entries`'s own docstring), so
# before this they were invisible-by-construction: `corrects_from=` was
# already parsed by `parse_review_entry` (see that function's own docstring)
# but rendered nowhere, and `--only superseded` simply exited 2 as an
# unrecognized category. This is a genuinely different filter shape from
# the other three (which narrow `flagged`) -- `--only superseded` instead
# enumerates the full `results` list's superseded rows, since a superseded
# entry is BY DESIGN never a member of `flagged` — see `_filter_flagged`'s
# own docstring for how the two shapes are reconciled.
_VALID_ONLY_VALUES = frozenset({"unmatched", "reused", "no-identity", "superseded"})

LEDGER_LAST_REVIEWED = _lib.LAST_REVIEWED
LEDGER_SPEND = os.path.join(_lib.AGENT_BUDGET_DIR, "spend.jsonl")

# Reviewer-of-record agent TYPES for the commit-boundary review ledger this
# module audits (CLAUDE.md §10/§13: code-reviewer is the default
# reviewer-of-record; trust-architect SUBSTITUTES for it on trust-surface
# commits, never stacking). A spend.jsonl row whose agent_type is not one
# of these is never treated as corroborating a review, even if its
# agent_id/tool_use_id happen to match — e.g. an `implement` dispatch
# reusing an id by coincidence should never "corroborate" a review.
_REVIEWER_AGENT_TYPES = frozenset({"code-reviewer", "trust-architect"})

_HELP_TEXT = """Usage: python3 ~/.claude/hooks/audit_review_attribution.py [--window-seconds N] [--only unmatched|reused|no-identity|superseded] [--json] [--help]

  --window-seconds N   Max |review_ts - lease_ts| (seconds) for a spend.jsonl
                        row to corroborate a reviewer= identity (default: 1800).
  --only CATEGORY      Show only flagged entries of one category
                        (unmatched|reused|no-identity) — the text table caps
                        at 10 flagged entries by default; use this to see the
                        actionable classes (unmatched/reused) without legacy
                        no-identity noise burying them. Affects --json too.
                        `superseded` is a DIFFERENT shape (not itself a
                        flagged category): it enumerates every identity
                        that was corrected via `record_review.py
                        --correct-identity` (or otherwise superseded by a
                        later recording for the same key) — visible for
                        audit purposes even though a superseded entry is
                        never itself a forgery signal.
  --json                Emit the full report as JSON instead of a text table.
  --help                Show this message and exit.

Read-only, report-only. Closes the AUDIT gap ONLY against casual/accidental
mismatches (can we later tell a real sub-agent review from a self-clear) —
NOT against a deliberate forger with ordinary read access to spend.jsonl
(the only obtainable source of a valid agent_id/tool_use_id pair to forge
IS spend.jsonl itself), and NOT the ENFORCEMENT gap (nothing here blocks
anything at commit time). See the module docstring's LIMITATIONS section
for the full caveat, including the ~5-6 day spend.jsonl retention ceiling
beyond which a genuinely clean review and a forgery become indistinguishable.
"""


class ArgError(ValueError):
    """Raised by :func:`parse_args` on a bad CLI argument. Caught by main()."""


# ---------------------------------------------------------------------------
# Small pure time helper (mirrors churn_report._parse_ts's own contract —
# duplicated rather than reaching into that module's private function, to
# keep each module's own I/O layer independently owned).
# ---------------------------------------------------------------------------


def _parse_ts(ts: str | None) -> datetime | None:
    """Parse a `_lib._now()`-shaped `"%Y-%m-%dT%H:%M:%SZ"` timestamp, or
    None on any failure (missing, wrong type, wrong format)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# last_reviewed parsing — reuses churn_report's own repo/key tokenizer (the
# only place in this runtime that already knows a real repo root can
# contain a space) plus record_review's outcome/field/reviewer parsers,
# rather than re-deriving the ledger's line grammar a second time.
# ---------------------------------------------------------------------------


def parse_review_entry(line: str) -> dict | None:
    """One `last_reviewed` line -> the fields this audit needs, or None for
    a `battery:` line (not a review outcome — see `record_review.
    BATTERY_PREFIX`) or a whole-line-unparseable entry (no recognizable
    repo/key token at all — real ledger corruption, not this audit's
    concern; `churn_report.py`'s own catch-rate metric already surfaces
    that separately).

    Always carries: repo, key, status (rr.OUTCOME_*), blockers (int),
    ts (str | None), reviewer_type, reviewer_agent_id, reviewer_tool_use_id
    (all str | None — see `record_review.parse_reviewer_value`), rekey
    (str | None — the PRIOR `precommit:<digest>` key this entry carried its
    clean outcome forward from, present ONLY on a `record_review.py --rekey`
    entry, added 2026-09-01, AA-0064 fix round Item 8 / this module's own
    rekey-exemption fix — see `audit_clean_entries`), corrects_from (str |
    None — the OLD `reviewer=` value this entry supersedes, present ONLY on
    a `record_review.py --correct-identity` entry, added 2026-09-09, CSA
    #5133 / this module's own supersede-exemption fix — see
    `audit_clean_entries`), corrected_at (str | None — the UTC ISO8601
    timestamp of WHEN the correction itself happened, a SIBLING field to
    `corrects_from`, present under the identical condition — added
    2026-09-09, #5133 fix round Blocker 2: `ts=` on a corrected line
    stays the ORIGINAL entry's timestamp byte-for-byte, never the
    correction's own moment, so a `--window-seconds` join keyed to `ts=`
    alone would evaluate a stale-dated correction against the wrong window;
    a caller that cares WHEN the correction landed reads `corrected_at`
    instead of `ts` for a corrects_from-bearing entry), raw (the original
    line, for a human reading a flagged entry to go find it).
    """
    if line.startswith(rr.BATTERY_PREFIX):
        return None
    parsed = cr.parse_last_reviewed_line(line)
    if parsed is None:
        return None
    repo, key, rest = parsed
    status, blockers = rr.parse_outcome_token(rest)
    fields = rr.parse_ledger_fields(rest)
    identity = rr.parse_reviewer_value(fields.get("reviewer"))
    return {
        "repo": repo,
        "key": key,
        "status": status,
        "blockers": blockers,
        "ts": fields.get("ts"),
        "reviewer_type": identity["type"],
        "reviewer_agent_id": identity["agent_id"],
        "reviewer_tool_use_id": identity["tool_use_id"],
        "rekey": fields.get("rekey"),
        "corrects_from": fields.get("corrects_from"),
        "corrected_at": fields.get("corrected_at"),
        "raw": line,
    }


# ---------------------------------------------------------------------------
# The join itself.
# ---------------------------------------------------------------------------


def is_reviewer_typed(row: dict) -> bool:
    """True iff a spend.jsonl row's `agent_type` is a reviewer-of-record
    type this ledger's `clean`/`blockers` outcomes are meant to represent.
    Never raises: a missing/non-str `agent_type` is simply not a member."""
    return row.get("agent_type") in _REVIEWER_AGENT_TYPES


def find_matching_lease(
    spend_rows: list[dict],
    agent_id: str,
    tool_use_id: str,
    review_ts: str | None,
    window_seconds: int,
) -> dict | None:
    """The first spend.jsonl row matching `agent_id` AND `tool_use_id`,
    reviewer-typed, whose own `ts` is within `window_seconds` of
    `review_ts` — or None when no such row exists.

    A `review_ts` that fails to parse can never be corroborated (there is
    no window to check against) — this returns None rather than matching
    everything or nothing at random, so an entry with a broken/missing
    ts= is conservatively FLAGGED, not silently waved through. Never
    raises: a row whose own `ts` fails to parse is simply skipped as a
    candidate, not treated as a crash.
    """
    review_dt = _parse_ts(review_ts)
    if review_dt is None:
        return None
    for row in spend_rows:
        if row.get("agent_id") != agent_id:
            continue
        if row.get("tool_use_id") != tool_use_id:
            continue
        if not is_reviewer_typed(row):
            continue
        row_dt = _parse_ts(row.get("ts"))
        if row_dt is None:
            continue
        if abs((review_dt - row_dt).total_seconds()) <= window_seconds:
            return row
    return None


def _find_reused_pairs(results: list[dict]) -> set[tuple[str, str]]:
    """Every `(agent_id, tool_use_id)` pair cited by MORE THAN ONE `clean`
    entry in `results` (BLOCKER 1, 2026-08-30 trust-architect review): a
    real review dispatch is used exactly once, so a pair cited twice is the
    cheapest possible forgery this audit can catch without any enforcement
    machinery — copy one real reviewer row's identity into a second `clean`
    entry. Both entries in a pair (not just the "later" one) are equally
    suspect once the pair repeats, so this returns the PAIR, and the caller
    reclassifies every entry sharing it. Never raises."""
    seen: dict[tuple[str, str], int] = {}
    for r in results:
        agent_id, tool_use_id = r.get("reviewer_agent_id"), r.get("reviewer_tool_use_id")
        if agent_id and tool_use_id:
            key = (agent_id, tool_use_id)
            seen[key] = seen.get(key, 0) + 1
    return {key for key, count in seen.items() if count > 1}


def _root_star_groups(results: list[dict]) -> dict[int, set[int]]:
    """ROOT `results` index -> the full set of `results` indices forming
    that root's STAR (the root itself, plus every entry whose OWN `rekey=`
    field names it directly) — Finding 1's root-cause fix (2026-09-01 fix
    round 3): `record_review.py --rekey` now always resolves and cites a
    chain's TRUE ROOT (see that module's own root-resolution block), so a
    legitimate carry-forward chain is structurally always ONE HOP deep from
    every member straight to the same root — a star, never a longer chain.

    An entry R contributes to root TARGET's star ONLY when: R's `rekey=`
    resolves (via `(repo, key)`) to a REAL `clean` entry TARGET present in
    `results` (never R itself — proves R's claimed prior genuinely exists,
    not merely asserted), AND TARGET itself carries NO `rekey=` of its own
    (TARGET is a genuine root). This is a DELIBERATE, hard boundary — no
    general transitive walk is ever built: a LEGACY multi-hop chain written
    by the OLD (pre-fix) writer (e.g. C.rekey=B, B.rekey=A) has C naming a
    TARGET (B) that itself carries `rekey=` — B is not a root, so C is
    simply never added to any star. C keeps whatever verdict the ordinary
    join/reused-pair logic gives it, independent of the star mechanism
    entirely — the known, SAFE-DIRECTION over-flag for a pre-fix legacy
    chain (see the module docstring's REKEY EXEMPTION section). A `rekey=`
    naming a missing key, or a key whose entry is not `clean`, also
    produces no membership — `record_review.py --rekey` itself never
    writes such a value (BLOCKER 1/Item 5 of the AA-0064 fix round, and the
    root-resolution block's own `rekey-chain-broken` refusal, all refuse
    before ever recording), so a `rekey=` that fails to resolve here means
    either ledger corruption or a forger typing an arbitrary `rekey=`
    string directly; either way it gets no membership. Never raises."""
    clean_by_repo_key: dict[tuple[str, str], int] = {
        (r["repo"], r["key"]): i for i, r in enumerate(results)
    }
    groups: dict[int, set[int]] = {}
    for i, r in enumerate(results):
        rekey_value = r.get("rekey")
        if not rekey_value:
            continue
        target_idx = clean_by_repo_key.get((r.get("repo"), rekey_value))
        if target_idx is None or target_idx == i:
            continue  # missing/non-clean/self-referential prior -- no membership
        if results[target_idx].get("rekey"):
            continue  # target is not a true root -- legacy multi-hop, never grouped
        groups.setdefault(target_idx, {target_idx}).add(i)
    return groups


def audit_clean_entries(
    entries: list[dict], spend_rows: list[dict], window_seconds: int
) -> dict:
    """The full attribution audit over every `clean` entry in `entries`
    (as produced by `parse_review_entry`; non-clean entries are ignored
    here — see the module docstring for why `blockers` entries are out of
    scope for this specific property).

    Every clean entry gets exactly one `attribution`:
      * "matched"     — a corroborating spend.jsonl row was found, AND the
                         entry's identity is cited by no other `clean`
                         entry. NOT flagged. See the module docstring's
                         LIMITATIONS section for what this does and does
                         not prove.
      * "no-identity" — the entry carries no reviewer= identity at all
                         (legacy, or a --clean call with no
                         --reviewer-agent-id/--reviewer-tool-use-id).
                         FLAGGED.
      * "unmatched"   — the entry carries an identity but no corroborating
                         row was found within the window. FLAGGED.
      * "reused"      — the entry's `(agent_id, tool_use_id)` pair is also
                         cited by at least one OTHER `clean` entry —
                         OVERRIDES whatever "matched"/"unmatched" verdict
                         the join above produced. FLAGGED.
      * "rekey-exempt" — (2026-09-01 fix rounds 2-4) an `unmatched` or
                         `reused` verdict that is fully explained by a
                         valid `record_review.py --rekey` carry-forward
                         STAR (see `_root_star_groups`) — NOT flagged.
                         A star member's own "unmatched" is exempted once
                         its `rekey=` resolves to a real clean ROOT entry
                         (the mechanical digest-identity proof IS the
                         corroboration; a fresh spend.jsonl dispatch is not
                         expected) — Finding 2 (2026-09-01 fix round 3)
                         TIGHTENS this: exempted ONLY when the member's own
                         identity pair EQUALS the root's — a fabricated
                         entry citing an INVENTED identity plus a real
                         root's key gets NO exemption for its own identity,
                         which it never earned. Fix round 4 BLOCKER
                         TIGHTENS it further: exempted ONLY when the ROOT
                         ITSELF was independently corroborated against
                         spend.jsonl (its OWN pre-override attribution was
                         "matched") — a fabricated, UNCORROBORATED root
                         proves nothing about anything citing it, and
                         without this check two fully invented `clean`
                         entries (a fake root plus a same-pair rekey=
                         citing it) exempted each other with zero
                         spend.jsonl access needed at all. The PAIR-WIDE
                         "reused" override is undone for an ENTIRE star
                         ONLY when its shared identity pair is cited SOLELY
                         by star members — a third, unrelated citer of
                         that same pair (in or out of any star) leaves the
                         whole pair flagged `reused` for everyone, so a
                         real forger can never launder a copied identity by
                         attaching an unrelated legitimate rekey star to
                         it. A mutual A<->B reference (neither is a
                         genuine root — each names the OTHER, which itself
                         carries rekey=) forms NO star at all by this same
                         boundary, so both stay flagged if their pair
                         repeats — pinned behavior, not a gap.
      * "superseded"  — (2026-09-09, #5133; tightened in the SAME fix
                         round that added Blocker 1(a) below, F6) a `clean`
                         entry that is NOT the LAST entry on record for its
                         exact `(repo, key)` pair — i.e. a PLAIN RE-RECORD
                         of the same key (`_update_entry`'s in-place replace
                         path, or a no-op `already` recording) never
                         produces this two-line shape at all, and the only
                         writer that DOES append a genuinely second line for
                         an already-`clean` key is `record_review.py
                         --correct-identity` (a later `blockers:n`
                         re-review also supersedes an earlier `clean` line
                         for the same key, but that second line is excluded
                         from `total_clean`/this whole audit's clean-only
                         scope by the `status != OUTCOME_CLEAN` filter above
                         — it only ever affects whether the STALE `clean`
                         predecessor counts as superseded, never adds a
                         second scored `clean` row). NOT flagged, UNLESS
                         BLOCKER 1(a) (2026-09-09) reclassifies it to
                         `reused` — see that block's own comment for why: a
                         superseded entry whose own `(agent_id,
                         tool_use_id)` pair DIFFERS from its successor's
                         (the pair was genuinely RELEASED, not merely
                         re-typed byte-identically) still counts toward
                         `_find_reused_pairs`, closing the pair-freeing
                         identity-laundering hole a correction would
                         otherwise open (superseding a genuinely-reviewed
                         entry to a SECOND real pair used to silently drop
                         the original pair out of the reused-pair check,
                         freeing it for a forger to cite in an unrelated,
                         never-reviewed boundary). This is the direct
                         audit-side mirror of how every REAL consumer of
                         this ledger already reads it: `precommit_review_gate
                         .decide()` (via `rr.head_review_outcome`/
                         `_existing_outcome_token`) and
                         `find_clean_precommit_entry_for_paths` both resolve
                         "the LAST matching line wins" — an entry no
                         consumer ever looks at again for its CONTENT is not
                         meaningfully "unattributed," it is simply STALE
                         (its outcome/paths/digest are always dead history);
                         flagging it as a bare anomaly is exactly the
                         false-positive #5133 exists to fix (a corrected
                         typo would otherwise read as a permanent,
                         indistinguishable-from-forged anomaly) — but its
                         IDENTITY PAIR is a separate question Blocker 1(a)
                         answers independently, per above. Determined purely
                         by KEY ORDER (this entry's own `entries` index is
                         not the highest index sharing its `(repo, key)`),
                         never by inspecting `corrects_from=` — a later
                         entry for the same key supersedes the earlier one
                         regardless of WHY it was re-recorded, matching the
                         ledger's own unconditional last-wins reading. This
                         is checked FIRST, before the identity join, so a
                         superseded entry with an UNRELEASED (identical)
                         pair never contributes to `_find_reused_pairs`/the
                         star logic below at all — dead history citing an
                         identity must never cause a LIVE, later entry to be
                         flagged `reused` just because a stale predecessor
                         happened to share (or once mistyped) a pair; a
                         RELEASED pair is the one deliberate exception, see
                         Blocker 1(a).
    """
    # Index -> True iff `entries[index]` is the LAST entry (in file/append
    # order) sharing its exact (repo, key) pair — computed over the FULL
    # `entries` list (every status, not just clean) so a later `blockers`
    # re-review (or any other future recording) also correctly supersedes
    # an earlier `clean` line for the same key, not just a
    # --correct-identity line specifically. O(n) single backward pass,
    # never raises (a missing repo/key on a malformed entry simply never
    # matches anything, which is the safe direction — it stays un-superseded
    # and gets audited normally).
    _last_index_for_key: dict[tuple[str | None, str | None], int] = {}
    for idx, e in enumerate(entries):
        _last_index_for_key[(e.get("repo"), e.get("key"))] = idx
    is_last_for_key = [
        idx == _last_index_for_key.get((e.get("repo"), e.get("key")))
        for idx, e in enumerate(entries)
    ]

    results: list[dict] = []
    for idx, e in enumerate(entries):
        if e.get("status") != rr.OUTCOME_CLEAN:
            continue
        if not is_last_for_key[idx]:
            results.append({**e, "attribution": "superseded", "matched_row": None})
            continue
        agent_id = e.get("reviewer_agent_id")
        tool_use_id = e.get("reviewer_tool_use_id")
        if not (agent_id and tool_use_id):
            results.append({**e, "attribution": "no-identity", "matched_row": None})
            continue
        match = find_matching_lease(spend_rows, agent_id, tool_use_id, e.get("ts"), window_seconds)
        if match is None:
            results.append({**e, "attribution": "unmatched", "matched_row": None})
        else:
            results.append({**e, "attribution": "matched", "matched_row": match})

    # A `superseded` entry is dead history (see the docstring's own
    # "superseded" bullet) -- it must never contribute to the star/
    # reused-pair cross-checks below, or a stale predecessor sharing (or
    # once mistyping, then correcting) an identity pair could flag a LIVE,
    # later entry as "reused" purely because its own now-superseded line
    # still carries that pair. `_root_star_groups`'s `clean_by_repo_key`
    # dict comprehension already resolves to the LAST index for a given
    # (repo, key) by construction (later entries overwrite earlier ones in
    # iteration order), so it is unaffected either way; `_find_reused_pairs`
    # has no such de-dup and must be given the live subset explicitly.
    #
    # BLOCKER 1(a) (2026-09-09, trust-architect review round on #5133):
    # "dead history" is true of a superseded entry's OUTCOME/CONTENT, but not
    # unconditionally true of its identity PAIR. Executed abuse this closes:
    # a genuinely-reviewed boundary A (pair P1) gets "corrected" to a SECOND
    # real pair P2 -- passing every `--correct-identity` refusal, since
    # nothing in record_review.py stops a correction from citing a pair that
    # was never P1's own typo, just a different real dispatch -- and A's
    # original line becomes `superseded`, dropping OUT of `_find_reused_pairs`
    # entirely under the unconditional exclusion this comment used to
    # describe. That FREES P1: a forger can now cite P1 in a wholly
    # unrelated, never-reviewed boundary C and the audit reads fully clean
    # (pre-fix: it would have double-flagged `reused`, since P1 was cited by
    # both A and C). The sanctioned use case -- a warm-chain round correcting
    # a TYPO'D pair back to the byte-identical pair another live entry
    # already cites -- is the opposite shape: the superseded entry's pair and
    # its successor's pair are the SAME, so the pair was never "freed" by the
    # correction at all (the corrected entry inherits exactly the citation
    # count the original already had). The distinguishing signal is
    # therefore: did the entry's OWN pair change between the superseded line
    # and whatever superseded it? A pair that changed was released and must
    # stay flaggable; a pair that stayed identical (a re-typed byte-identical
    # correction) is harmless to drop, matching the pre-existing exemption's
    # own intent.
    #
    # Computed here (not folded into the loop above) because it needs the
    # SUCCESSOR's pair, which for a superseded entry always exists (by
    # definition: "superseded" means a later entry for the same (repo, key)
    # exists) and is cheaply found via the same `_last_index_for_key` map
    # already built for the supersede pass.
    def _released_superseded_indices() -> set[int]:
        released: set[int] = set()
        for idx, r in enumerate(results):
            if r["attribution"] != "superseded":
                continue
            successor_idx = _last_index_for_key.get((r.get("repo"), r.get("key")))
            if successor_idx is None or successor_idx == idx:
                continue  # structurally unreachable (see docstring), safe no-op
            own_pair = (r.get("reviewer_agent_id"), r.get("reviewer_tool_use_id"))
            successor_pair = (
                entries[successor_idx].get("reviewer_agent_id"),
                entries[successor_idx].get("reviewer_tool_use_id"),
            )
            if own_pair != successor_pair:
                released.add(idx)
        return released

    released_superseded = _released_superseded_indices()
    live_results = [
        r
        for i, r in enumerate(results)
        if r["attribution"] != "superseded" or i in released_superseded
    ]

    star_groups = _root_star_groups(results)  # root_idx -> {root_idx, member1, member2, ...}

    def _pair_of(idx: int) -> tuple[str | None, str | None]:
        r = results[idx]
        return (r.get("reviewer_agent_id"), r.get("reviewer_tool_use_id"))

    # BLOCKER (2026-09-01 fix round 4): snapshot every entry's PRE-"reused"
    # attribution (matched/unmatched/no-identity) BEFORE the reused-pair
    # override loop below ever runs, so both exemption stages can require
    # the star's ROOT to have been INDEPENDENTLY corroborated
    # (pre_reused[root_idx] == "matched") before exempting anything in that
    # star. Without this, TWO fabricated `clean` entries sharing an
    # INVENTED identity -- a fake root with no real spend.jsonl
    # corroboration at all, plus a same-pair rekey= citing it -- exempted
    # each other unconditionally: a NEW detection loss, and cheaper to
    # exploit than the module's pre-existing documented forgery hole (no
    # spend.jsonl access needed whatsoever, just two invented ledger
    # lines). A legitimate root is BY CONSTRUCTION a real dispatch with a
    # matching spend.jsonl entry; an aged-out-past-retention legitimate
    # root will over-flag its own star as a side effect -- the same
    # safe-direction tradeoff this module already takes everywhere else
    # (see LIMITATIONS), and the daily-sweep caveat already tells an
    # operator to hand-verify a still-flagged rekey= chain.
    pre_reused = [r["attribution"] for r in results]

    # Unconditional: a star member's own "unmatched" is explained by the
    # mechanical digest-identity proof its root's rekey= chain names --
    # Finding 2 (2026-09-01 fix round 3): ONLY when the member's own
    # identity pair equals the ROOT's exact pair. A member that cites a
    # real root's key but carries a DIFFERENT (invented, or explicitly
    # caller-overridden) identity is never exempted here -- it must
    # independently corroborate that different identity like any other
    # entry, exactly as if the rekey= field were absent. Fix round 4
    # BLOCKER: ALSO only when the ROOT itself was independently
    # corroborated (pre_reused == "matched") -- see the snapshot's own
    # comment above.
    for root_idx, members in star_groups.items():
        root_pair = _pair_of(root_idx)
        if not all(root_pair) or pre_reused[root_idx] != "matched":
            continue
        for m in members:
            if m == root_idx:
                continue
            if _pair_of(m) == root_pair and results[m]["attribution"] == "unmatched":
                results[m]["attribution"] = "rekey-exempt"

    # Both the reused-pair detector and the pair_citers map below are built
    # from `live_results` only (see this block's own opening comment) — a
    # `superseded` entry's identity pair must never count toward flagging a
    # LIVE entry as "reused", and the reclassification loop right after
    # skips superseded entries UNLESS they are in `released_superseded`
    # (BLOCKER 1(a) above) — an entry already correctly verdicted
    # "superseded" whose pair stayed IDENTICAL to its successor's must never
    # be overwritten to "reused" just because its own dead line happens to
    # share a pair with something else; one whose pair was RELEASED by the
    # correction is exactly the live/flaggable case this fix restores.
    reused_pairs = _find_reused_pairs(live_results)
    for i, r in enumerate(results):
        if r["attribution"] == "superseded" and i not in released_superseded:
            continue
        agent_id, tool_use_id = r.get("reviewer_agent_id"), r.get("reviewer_tool_use_id")
        if agent_id and tool_use_id and (agent_id, tool_use_id) in reused_pairs:
            r["attribution"] = "reused"

    # Conditional: undo the pair-wide "reused" override for an ENTIRE star
    # ONLY when its shared identity pair is cited SOLELY by star members
    # sharing that exact pair (never a general transitive closure — see the
    # docstring's "rekey-exempt" bullet and `_root_star_groups`'s own
    # one-hop-only boundary), AND the root was independently corroborated
    # (pre_reused == "matched" — fix round 4 BLOCKER, same rationale as the
    # unconditional stage above).
    pair_citers: dict[tuple[str, str], set[int]] = {}
    for i, r in enumerate(results):
        if r["attribution"] == "superseded" and i not in released_superseded:
            continue
        agent_id, tool_use_id = r.get("reviewer_agent_id"), r.get("reviewer_tool_use_id")
        if agent_id and tool_use_id:
            pair_citers.setdefault((agent_id, tool_use_id), set()).add(i)
    for root_idx, members in star_groups.items():
        root_pair = _pair_of(root_idx)
        if not all(root_pair) or pre_reused[root_idx] != "matched":
            continue
        same_pair_members = {m for m in members if _pair_of(m) == root_pair}
        if len(same_pair_members) < 2:
            continue  # nothing shared to exempt
        if pair_citers.get(root_pair, set()) <= same_pair_members:
            for m in same_pair_members:
                if results[m]["attribution"] == "reused":
                    results[m]["attribution"] = "rekey-exempt"

    flagged = [
        r for r in results if r["attribution"] not in ("matched", "rekey-exempt", "superseded")
    ]
    return {
        "total_clean": len(results),
        "matched": sum(1 for r in results if r["attribution"] == "matched"),
        "no_identity": sum(1 for r in results if r["attribution"] == "no-identity"),
        "unmatched": sum(1 for r in results if r["attribution"] == "unmatched"),
        "reused": sum(1 for r in results if r["attribution"] == "reused"),
        "rekey_exempt": sum(1 for r in results if r["attribution"] == "rekey-exempt"),
        "superseded": sum(1 for r in results if r["attribution"] == "superseded"),
        "flagged": flagged,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Report assembly — mirrors churn_report.py's absent/degraded/ok contract.
# ---------------------------------------------------------------------------


def invocation(argv: list[str]) -> str:
    return " ".join(["python3", "~/.claude/hooks/audit_review_attribution.py", *argv])


def _absent_section(ledger: str, command: str) -> dict:
    return {
        "status": "absent",
        "ledger": ledger,
        "read_error": None,
        "skipped_unparseable": 0,
        "as_of": None,
        "command": command,
    }


def _status_for(errors: dict) -> str:
    return "degraded" if errors.get("read_error") else "ok"


def _max_ts_of_lines(entries: list[dict]) -> str | None:
    values = [e.get("ts") for e in entries if _parse_ts(e.get("ts")) is not None]
    return max(values) if values else None


def build_report(
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    last_reviewed_path: str | None = None,
    spend_path: str | None = None,
    argv: list[str] | None = None,
    now: datetime | None = None,
) -> dict:
    """Build the full JSON-serializable report. Pure given its file inputs
    (both paths are parameters so tests never touch the real ~/.claude
    ledgers — mirrors `churn_report.build_report`'s own testability
    contract). A path left as None resolves to the module-level `LEDGER_*`
    constant AT CALL TIME (not import time), so a test can
    `monkeypatch.setattr(audit_review_attribution, "LEDGER_SPEND", ...)`
    and have it actually take effect.
    """
    if last_reviewed_path is None:
        last_reviewed_path = LEDGER_LAST_REVIEWED
    if spend_path is None:
        spend_path = LEDGER_SPEND
    if now is None:
        now = datetime.now(timezone.utc)
    command = invocation(argv or [])

    report: dict = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_seconds": window_seconds,
        "command": command,
    }

    lr_result = cr.read_lines(last_reviewed_path)
    spend_result = cr.read_jsonl(spend_path)

    if lr_result is None:
        report["last_reviewed"] = _absent_section(last_reviewed_path, command)
    else:
        lr_lines, lr_errors = lr_result
        entries = [parse_review_entry(ln) for ln in lr_lines]
        entries = [e for e in entries if e is not None]
        report["last_reviewed"] = {
            "status": _status_for(lr_errors),
            "ledger": last_reviewed_path,
            "read_error": lr_errors["read_error"],
            "skipped_unparseable": lr_errors["skipped_unparseable"],
            "as_of": _max_ts_of_lines(entries),
            "command": command,
        }

    if spend_result is None:
        report["spend"] = _absent_section(spend_path, command)
    else:
        spend_rows, spend_errors = spend_result
        report["spend"] = {
            "status": _status_for(spend_errors),
            "ledger": spend_path,
            "read_error": spend_errors["read_error"],
            "skipped_unparseable": spend_errors["skipped_unparseable"],
            "as_of": _max_ts_of_lines(spend_rows),
            "command": command,
        }

    if lr_result is None or spend_result is None:
        # Never compute the audit on a partial input set: an absent ledger
        # would silently read as "zero clean entries" / "zero candidate
        # rows," which is a false-clean, not a real "nothing to flag."
        report["clean_attribution"] = {
            "status": "absent",
            "reason": "last_reviewed and/or spend.jsonl ledger is absent",
            "total_clean": 0,
            "matched": 0,
            "no_identity": 0,
            "unmatched": 0,
            "reused": 0,
            "rekey_exempt": 0,
            "superseded": 0,
            "flagged": [],
        }
        return report

    audit = audit_clean_entries(entries, spend_rows, window_seconds)
    report["clean_attribution"] = {"status": "ok", **audit}
    return report


# ---------------------------------------------------------------------------
# Table rendering.
# ---------------------------------------------------------------------------


def _provenance(section: dict) -> str:
    if section.get("status") == "absent":
        return f"{section['ledger']}: ABSENT"
    if section.get("status") == "degraded":
        return (
            f"{section['ledger']}: DEGRADED (read_error={section.get('read_error')}, "
            f"skipped_unparseable={section.get('skipped_unparseable')})"
        )
    return f"{section['ledger']}: ok, as of {section.get('as_of') or 'unknown'}"


def _filter_flagged(audit: dict, only: str | None) -> list[dict]:
    """The entries to show for a given `--only` value, given the FULL
    `clean_attribution` audit dict (not just its `flagged` list).

    `only is None` -> `audit["flagged"]` unchanged (the original, unfiltered
    behavior). `only` one of `unmatched`/`reused`/`no-identity` -> `flagged`
    narrowed to that category, exactly as before this function's signature
    changed (Blocker 1(b), 2026-09-09, #5133).

    `only == "superseded"` is a GENUINELY DIFFERENT shape, not a narrowing
    of `flagged`: `audit_clean_entries` deliberately excludes every
    `superseded` entry from `flagged` (a superseded entry is dead history,
    never a forgery signal on its own — see that function's own docstring),
    so filtering `flagged` down to `attribution == "superseded"` would
    always yield an empty list, defeating the entire point of exposing this
    category (#5133 F3's own "an invisible-by-construction anomaly
    class" framing). Instead this sources from `audit["results"]` — the
    FULL clean-entry list, superseded members included — restricted to
    `attribution == "superseded"`, so `--only superseded` genuinely
    enumerates every identity-correction target (a `corrects_from=`-bearing
    successor's original, wrong-identity predecessor) rather than always
    printing "no flagged entries found." Never raises: a malformed/absent
    `results` key degrades to an empty list, same as any other missing-key
    read in this module.
    """
    flagged = audit.get("flagged", [])
    if not only:
        return flagged
    if only == "superseded":
        return [e for e in audit.get("results", []) if e.get("attribution") == "superseded"]
    return [e for e in flagged if e.get("attribution") == only]


def render_table(report: dict, only: str | None = None) -> str:
    lines: list[str] = []
    lines.append(f"=== review-attribution audit — generated {report['generated_at']} ===")
    lines.append(f"window_seconds={report['window_seconds']}  |  command: {report['command']}")
    lines.append("")
    lines.append(f"last_reviewed: {_provenance(report['last_reviewed'])}")
    lines.append(f"spend.jsonl:   {_provenance(report['spend'])}")

    audit = report["clean_attribution"]
    lines.append("")
    if audit["status"] == "absent":
        lines.append(f"CANNOT AUDIT: {audit['reason']}")
        return "\n".join(lines)

    lines.append(
        f"clean entries: total={audit['total_clean']} matched={audit['matched']} "
        f"no_identity={audit['no_identity']} unmatched={audit['unmatched']} "
        f"reused={audit['reused']} rekey_exempt={audit.get('rekey_exempt', 0)} "
        f"superseded={audit.get('superseded', 0)}"
    )
    # MAJOR finding (2026-08-30 review): the full flagged list can run into
    # the thousands (legacy no-identity noise) and burns the actionable
    # unmatched/reused signal underneath it. `--only` narrows BEFORE the
    # cap is applied; the cap always applies on top, so even a filtered
    # view stays scannable.
    shown = _filter_flagged(audit, only)
    if not shown:
        if only:
            lines.append(f"no flagged entries of category {only!r} found.")
        else:
            lines.append("no unattributed clean entries found.")
    else:
        # "FLAGGED" is a slight misnomer for `only == "superseded"` (those
        # entries are never in `audit["flagged"]` -- see `_filter_flagged`'s
        # own docstring) but the header still communicates "here are the N
        # entries matching your --only filter", which is accurate either way.
        header = f"FLAGGED ({len(shown)}"
        header += f" of category {only!r})" if only else ")"
        lines.append(header + ":")
        for entry in shown[:_MAX_FLAGGED_SHOWN]:
            row = (
                f"  [{entry['attribution']:<11}] repo={entry['repo']} key={entry['key']} "
                f"ts={entry.get('ts')} reviewer_type={entry.get('reviewer_type')}"
            )
            # `corrects_from=`/`corrected_at=` (#5133 F3/Blocker 1(b),
            # Blocker 2) are the OLD reviewer= identity a correction
            # superseded, and WHEN the correction itself happened --
            # surfaced only when present, so an ordinary (non-correction)
            # row's shape is unchanged for every existing consumer's
            # row-parsing habits.
            if entry.get("corrects_from"):
                row += f" corrects_from={entry['corrects_from']}"
            if entry.get("corrected_at"):
                row += f" corrected_at={entry['corrected_at']}"
            lines.append(row)
        if len(shown) > _MAX_FLAGGED_SHOWN:
            remaining = len(shown) - _MAX_FLAGGED_SHOWN
            lines.append(
                f"  ... and {remaining} more (use --json for the full list, "
                "or --only unmatched|reused|no-identity|superseded to narrow the table)."
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> tuple[int, bool, str | None]:
    """Parse `--window-seconds N` (default DEFAULT_WINDOW_SECONDS), `--json`,
    and `--only CATEGORY` (default None — no filter). Pure; raises ArgError
    on a bad value. `--help`/`-h` are handled by `main()` before this is
    called."""
    window_seconds = DEFAULT_WINDOW_SECONDS
    as_json = False
    only: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--window-seconds":
            i += 1
            if i >= len(argv):
                raise ArgError("--window-seconds needs a value")
            window_seconds = _parse_positive_int(argv[i])
        elif arg.startswith("--window-seconds="):
            window_seconds = _parse_positive_int(arg.split("=", 1)[1])
        elif arg == "--json":
            as_json = True
        elif arg == "--only":
            i += 1
            if i >= len(argv):
                raise ArgError("--only needs a value")
            only = _parse_only_value(argv[i])
        elif arg.startswith("--only="):
            only = _parse_only_value(arg.split("=", 1)[1])
        else:
            raise ArgError(f"unknown argument {arg!r}")
        i += 1
    return window_seconds, as_json, only


def _parse_only_value(raw: str) -> str:
    if raw not in _VALID_ONLY_VALUES:
        raise ArgError(f"--only must be one of {sorted(_VALID_ONLY_VALUES)}, got {raw!r}")
    return raw


def _parse_positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except Exception as exc:
        raise ArgError(f"--window-seconds needs an integer, got {raw!r}") from exc
    if value <= 0:
        raise ArgError(f"--window-seconds must be a positive integer, got {value}")
    return value


def main(argv: list[str] | None = None) -> int:
    """Read-only, report-only over the AUDIT itself: the exit code reflects
    only whether the CLI invocation was well-formed (2 on a bad argument,
    mirroring churn_report.py's own convention) — it never varies with how
    many entries were flagged. A nonzero exit keyed to findings would
    invite exactly the enforcement use this item explicitly declines to
    build; findings are visible only in the printed/JSON report, matching
    `churn_report.py`/`model_pin_parity.py`'s own report-only posture."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in raw_argv or "-h" in raw_argv:
        print(_HELP_TEXT)
        return 0
    try:
        window_seconds, as_json, only = parse_args(raw_argv)
    except ArgError as exc:
        print(f"audit_review_attribution: {exc}", file=sys.stderr)
        return 2
    report = build_report(window_seconds, argv=raw_argv)
    if as_json:
        if only and report["clean_attribution"].get("status") == "ok":
            report["clean_attribution"]["flagged"] = _filter_flagged(
                report["clean_attribution"], only
            )
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_table(report, only=only))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI entry
    sys.exit(main())
