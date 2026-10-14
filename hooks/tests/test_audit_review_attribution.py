"""Hermetic, falsifiable tests for hooks/audit_review_attribution.py
(gate-optimization plan, Item 6b).

Every test builds its own small fixture ledger under `tmp_path` — the real
~/.claude ledgers are never read here (mirrors test_churn_report.py's own
contract). The two tests under "THE REQUIRED FALSIFIABILITY TEST" are the
whole point of this item: a `clean` entry whose reviewer= identity has NO
matching spend.jsonl row is flagged, and the identical shape WITH a
matching row is not — both directions proven, not just the positive case.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import audit_review_attribution as ara
import pytest
import record_review as rr

_NOW = datetime(2026, 8, 30, 22, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixture builders.
# ---------------------------------------------------------------------------


def _lr_line(
    repo: str,
    key: str,
    *,
    status: str = "clean",
    ts: str | None = "2026-08-30T21:00:00Z",
    reviewer: str | None = None,
    rekey: str | None = None,
    corrects_from: str | None = None,
    corrected_at: str | None = None,
) -> str:
    """One raw `last_reviewed` line, built the same way `record_review.py`
    itself would write it (ts=/reviewer=/rekey=/corrects_from=/
    corrected_at= as trailing k=v telemetry — `rekey=` added 2026-09-01,
    fix round 2; `corrects_from=`/`corrected_at=` added 2026-09-09, CSA
    #5133 — matching `record_review.py --rekey`/`--correct-identity`'s own
    `_entry_suffix`/`_rebuild_corrected_token` field order)."""
    line = f"{repo} {key} {status}"
    if ts:
        line += f" ts={ts}"
    if reviewer:
        line += f" reviewer={reviewer}"
    if rekey:
        line += f" rekey={rekey}"
    if corrects_from:
        line += f" corrects_from={corrects_from}"
    if corrected_at:
        line += f" corrected_at={corrected_at}"
    return line


def _spend_row(**overrides: object) -> dict:
    base: dict = {
        "ts": "2026-08-30T21:00:05Z",
        "session": "s1",
        "agent_type": "code-reviewer",
        "model": "claude-opus-5[1m]",
        "tool_use_id": "toolu_ABC",
        "agent_id": "aa2a7f1545215c433",
        "duration_ms": 600000,
        "tokens": {"input": 100, "output": 200, "cache_read": 300, "cache_creation": 400},
        "tokens_total": 1000,
        "tokens_error": None,
        "late": False,
        "unreleased": False,
        "reaped": None,
    }
    base.update(overrides)
    return base


def _write_lines(path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


_IDENTITY = rr.compose_reviewer_field("code-reviewer", "aa2a7f1545215c433", "toolu_ABC")


# ===========================================================================
# parse_review_entry
# ===========================================================================


class TestParseReviewEntry:
    def test_battery_line_returns_none(self):
        assert ara.parse_review_entry(f"{rr.BATTERY_PREFIX}2026-08-30T10:00:00Z mut=1/2 stale=0") is None

    def test_whole_line_unparseable_returns_none(self):
        assert ara.parse_review_entry("this is not a real ledger line at all") is None

    def test_bare_legacy_line_has_unknown_status(self):
        entry = ara.parse_review_entry("/repo deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        assert entry is not None
        assert entry["status"] == rr.OUTCOME_UNKNOWN

    def test_clean_entry_with_no_reviewer_has_no_identity(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean")
        entry = ara.parse_review_entry(line)
        assert entry["status"] == rr.OUTCOME_CLEAN
        assert entry["reviewer_type"] is None
        assert entry["reviewer_agent_id"] is None
        assert entry["reviewer_tool_use_id"] is None

    def test_clean_entry_with_bare_reviewer_type_has_no_identity(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean", reviewer="trust-architect")
        entry = ara.parse_review_entry(line)
        assert entry["reviewer_type"] == "trust-architect"
        assert entry["reviewer_agent_id"] is None
        assert entry["reviewer_tool_use_id"] is None

    def test_clean_entry_with_compound_reviewer_has_full_identity(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY)
        entry = ara.parse_review_entry(line)
        assert entry["reviewer_type"] == "code-reviewer"
        assert entry["reviewer_agent_id"] == "aa2a7f1545215c433"
        assert entry["reviewer_tool_use_id"] == "toolu_ABC"

    def test_blockers_entry_parses_with_blockers_status(self):
        line = _lr_line("/repo", "precommit:abc123", status="blockers:2")
        entry = ara.parse_review_entry(line)
        assert entry["status"] == rr.OUTCOME_BLOCKERS
        assert entry["blockers"] == 2

    def test_rekey_field_is_surfaced_when_present(self):
        # 2026-09-01 fix round 2: RED without this -- parse_review_entry
        # dropped rekey= entirely, silently, before the exemption fix.
        line = _lr_line(
            "/repo", "precommit:bbb222", status="clean", reviewer=_IDENTITY,
            rekey="precommit:aaa111",
        )
        entry = ara.parse_review_entry(line)
        assert entry["rekey"] == "precommit:aaa111"

    def test_rekey_field_is_none_when_absent(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY)
        entry = ara.parse_review_entry(line)
        assert entry["rekey"] is None

    def test_corrects_from_field_is_surfaced_when_present(self):
        line = _lr_line(
            "/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY,
            corrects_from="code-reviewer#a#toolu_WRONG",
        )
        entry = ara.parse_review_entry(line)
        assert entry["corrects_from"] == "code-reviewer#a#toolu_WRONG"

    def test_corrects_from_field_is_none_when_absent(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY)
        entry = ara.parse_review_entry(line)
        assert entry["corrects_from"] is None

    def test_corrected_at_field_is_surfaced_when_present(self):
        # BLOCKER 2 (2026-09-09 fix round): RED without this -- pre-fix
        # parse_review_entry dropped corrected_at= entirely, silently.
        line = _lr_line(
            "/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY,
            corrects_from="code-reviewer#a#toolu_WRONG",
            corrected_at="2026-09-09T12:00:00Z",
        )
        entry = ara.parse_review_entry(line)
        assert entry["corrected_at"] == "2026-09-09T12:00:00Z"

    def test_corrected_at_field_is_none_when_absent(self):
        line = _lr_line("/repo", "precommit:abc123", status="clean", reviewer=_IDENTITY)
        entry = ara.parse_review_entry(line)
        assert entry["corrected_at"] is None


# ===========================================================================
# is_reviewer_typed
# ===========================================================================


class TestIsReviewerTyped:
    def test_code_reviewer_is_reviewer_typed(self):
        assert ara.is_reviewer_typed({"agent_type": "code-reviewer"}) is True

    def test_trust_architect_is_reviewer_typed(self):
        assert ara.is_reviewer_typed({"agent_type": "trust-architect"}) is True

    def test_implement_is_not_reviewer_typed(self):
        assert ara.is_reviewer_typed({"agent_type": "implement"}) is False

    def test_missing_agent_type_is_not_reviewer_typed(self):
        assert ara.is_reviewer_typed({}) is False


# ===========================================================================
# find_matching_lease — the join primitive, both directions.
# ===========================================================================


class TestFindMatchingLease:
    def test_matches_when_ids_type_and_window_all_agree(self):
        rows = [_spend_row()]
        match = ara.find_matching_lease(
            rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800
        )
        assert match is not None
        assert match["tool_use_id"] == "toolu_ABC"

    def test_no_rows_at_all_is_no_match(self):
        assert ara.find_matching_lease([], "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800) is None

    def test_wrong_agent_id_is_no_match(self):
        rows = [_spend_row(agent_id="different_id_here")]
        assert (
            ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800)
            is None
        )

    def test_wrong_tool_use_id_is_no_match(self):
        rows = [_spend_row(tool_use_id="toolu_OTHER")]
        assert (
            ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800)
            is None
        )

    def test_non_reviewer_agent_type_is_no_match_even_with_matching_ids(self):
        rows = [_spend_row(agent_type="implement")]
        assert (
            ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800)
            is None
        )

    def test_outside_window_is_no_match(self):
        rows = [_spend_row(ts="2026-08-30T18:00:00Z")]  # 3 hours before the review ts
        assert (
            ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800)
            is None
        )

    def test_inside_widened_window_matches(self):
        rows = [_spend_row(ts="2026-08-30T20:00:00Z")]  # 1 hour before
        assert (
            ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 7200)
            is not None
        )

    def test_unparseable_review_ts_is_no_match(self):
        rows = [_spend_row()]
        assert ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", None, 1800) is None
        assert ara.find_matching_lease(rows, "aa2a7f1545215c433", "toolu_ABC", "garbage", 1800) is None

    def test_unparseable_row_ts_is_skipped_not_a_crash(self):
        rows = [_spend_row(ts="garbage"), _spend_row(ts="2026-08-30T21:00:05Z")]
        match = ara.find_matching_lease(
            rows, "aa2a7f1545215c433", "toolu_ABC", "2026-08-30T21:00:00Z", 1800
        )
        assert match is not None
        assert match["ts"] == "2026-08-30T21:00:05Z"


# ===========================================================================
# audit_clean_entries
# ===========================================================================


class TestAuditCleanEntries:
    def test_matched_entry_is_not_flagged(self):
        entries = [ara.parse_review_entry(_lr_line("/repo", "precommit:abcd", reviewer=_IDENTITY))]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["matched"] == 1
        assert result["flagged"] == []

    def test_unmatched_entry_with_identity_is_flagged(self):
        entries = [ara.parse_review_entry(_lr_line("/repo", "precommit:abcd", reviewer=_IDENTITY))]
        result = ara.audit_clean_entries(entries, [], 1800)  # no spend rows at all
        assert result["unmatched"] == 1
        assert result["matched"] == 0
        assert len(result["flagged"]) == 1
        assert result["flagged"][0]["attribution"] == "unmatched"

    def test_no_identity_entry_is_flagged(self):
        entries = [ara.parse_review_entry(_lr_line("/repo", "precommit:abcd"))]
        rows = [_spend_row()]  # a real row exists, but nothing to join on
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["no_identity"] == 1
        assert result["matched"] == 0
        assert result["flagged"][0]["attribution"] == "no-identity"

    def test_blockers_entries_are_excluded_entirely(self):
        entries = [ara.parse_review_entry(_lr_line("/repo", "precommit:abcd", status="blockers:1"))]
        result = ara.audit_clean_entries(entries, [], 1800)
        assert result["total_clean"] == 0
        assert result["flagged"] == []

    def test_mixed_batch_counts_are_all_independent(self):
        entries = [
            ara.parse_review_entry(_lr_line("/r1", "precommit:a111", reviewer=_IDENTITY)),
            ara.parse_review_entry(_lr_line("/r2", "precommit:a222")),
            ara.parse_review_entry(_lr_line("/r3", "precommit:a333", status="blockers:3")),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["total_clean"] == 2  # r1 (clean, matched) + r2 (clean, no-identity)
        assert result["matched"] == 1
        assert result["no_identity"] == 1
        assert result["unmatched"] == 0
        assert result["reused"] == 0


# ===========================================================================
# The "superseded" attribution (#5133): a clean entry that is NOT the
# LAST entry for its exact (repo, key) pair -- the audit-side mirror of a
# record_review.py --correct-identity correction (or any other later
# recording for the same key). Falsifiability: the FIRST test below asserts
# the PRE-FIX behavior (both entries independently scored, the stale one
# genuinely flagged unmatched) as its own RED baseline, then the exemption
# test proves the fix turns that same shape into a non-flagged verdict.
# ===========================================================================


_WRONG_IDENTITY = rr.compose_reviewer_field("code-reviewer", "aa2a7f1545215c433", "toolu_WRONG")


class TestSupersededExemption:
    def test_red_baseline_two_independent_entries_for_the_same_key_both_scored(self):
        """Proves the underlying shape genuinely produces TWO scored rows
        today (before any superseded-aware logic runs) -- i.e. this is a
        real collision to resolve, not an assumed one. Both entries here
        cite DIFFERENT identities (one real/matched, one fabricated/
        unmatched) so this assertion is unambiguous regardless of the
        superseded exemption's own behavior."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_WRONG_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z",
                    corrects_from=_WRONG_IDENTITY,
                )
            ),
        ]
        rows = [_spend_row()]  # corroborates ONLY the corrected (_IDENTITY) entry
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["total_clean"] == 2  # both rows genuinely exist as clean entries

    def test_superseded_entry_is_not_flagged(self):
        """GREEN: the earlier (wrong-identity) entry for the SAME key is
        exempted as 'superseded' once a later entry for that exact key
        exists -- it is dead history no real gate consumer ever reads
        again, never a permanent forgery-shaped anomaly."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_WRONG_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z",
                    corrects_from=_WRONG_IDENTITY,
                )
            ),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["superseded"] == 1
        assert result["matched"] == 1
        assert result["flagged"] == []
        attributions = {(r["repo"], r["key"], r["ts"]): r["attribution"] for r in result["results"]}
        assert attributions[("/repo", "precommit:abc123", "2026-08-30T21:00:00Z")] == "superseded"
        assert attributions[("/repo", "precommit:abc123", "2026-08-30T21:05:00Z")] == "matched"

    def test_a_correction_never_causes_a_live_entry_to_be_flagged_reused(self):
        """A superseded entry's identity pair must never count toward the
        cross-entry reused-pair check -- without this, a stale predecessor
        citing (or mistyping into) a real pair could false-flag a LEGITIMATE
        later entry sharing that same pair as 'reused', when in truth only
        ONE live entry ever cites it."""
        entries = [
            # The wrong original -- superseded once the correction lands.
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            # The correction -- cites the SAME real identity the original
            # ALSO happened to cite (a corrected typo that lands on the
            # already-correct value some other real entry uses is the
            # sharpest version of this scenario).
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z",
                    corrects_from=_WRONG_IDENTITY,
                )
            ),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["reused"] == 0
        assert result["matched"] == 1
        assert result["superseded"] == 1
        assert result["flagged"] == []

    def test_last_entry_for_the_key_is_never_marked_superseded(self):
        """The only entry for a key (no later recording at all) is scored
        normally -- 'superseded' only ever applies to a non-final entry."""
        entries = [
            ara.parse_review_entry(_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["superseded"] == 0
        assert result["matched"] == 1

    def test_different_keys_never_supersede_each_other(self):
        """Superseded-ness is scoped to the EXACT (repo, key) pair -- two
        DIFFERENT digests for the same repo (the ordinary case: two
        unrelated commits reviewed back to back) must never be treated as
        one superseding the other."""
        entries = [
            ara.parse_review_entry(_lr_line("/repo", "precommit:aaa111", reviewer=_WRONG_IDENTITY)),
            ara.parse_review_entry(_lr_line("/repo", "precommit:bbb222", reviewer=_IDENTITY)),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["superseded"] == 0
        assert result["unmatched"] == 1  # the wrong-identity one, on its own merits
        assert result["matched"] == 1

    def test_different_repos_never_supersede_each_other(self):
        """Same digest, different repo -- also never superseding (repo is
        part of the key, exactly like everywhere else in this module)."""
        entries = [
            ara.parse_review_entry(_lr_line("/repo1", "precommit:abc123", reviewer=_WRONG_IDENTITY)),
            ara.parse_review_entry(_lr_line("/repo2", "precommit:abc123", reviewer=_IDENTITY)),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["superseded"] == 0

    def test_a_later_blockers_entry_also_supersedes_an_earlier_clean_one(self):
        """Superseded-ness is determined purely by KEY ORDER across the FULL
        entries list (every status, not just clean) -- a later re-review
        that found blockers also correctly supersedes an earlier stale
        clean line for the very same key, not just a --correct-identity
        line specifically."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", status="blockers:2", ts="2026-08-30T21:05:00Z")
            ),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["total_clean"] == 1  # the blockers entry is excluded from clean scope entirely
        assert result["superseded"] == 1
        assert result["flagged"] == []

    def test_three_entries_for_one_key_only_the_last_is_live(self):
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_WRONG_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123",
                    reviewer=rr.compose_reviewer_field("code-reviewer", "bbbbbbbbbbbbbbbbb", "toolu_ALSO_WRONG"),
                    ts="2026-08-30T21:02:00Z", corrects_from=_WRONG_IDENTITY,
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z",
                    corrects_from="code-reviewer#bbbbbbbbbbbbbbbbb#toolu_ALSO_WRONG",
                )
            ),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["superseded"] == 2
        assert result["matched"] == 1
        assert result["flagged"] == []


# ===========================================================================
# BLOCKER 1(a) (2026-09-09, trust-architect review round on #5133):
# pair-freeing identity laundering. Executed attack: boundary A is genuinely
# reviewed by pair P1; the attacker "corrects" A's identity to a SECOND real
# pair P2 (passing every --correct-identity refusal -- P2 is a real,
# corroborable pair, just not the one that reviewed A). A's original line
# becomes `superseded` and, PRE-FIX, dropped OUT of `_find_reused_pairs`
# unconditionally -- freeing P1 for the attacker to cite in an unrelated,
# NEVER-reviewed boundary C. Pre-fix: C reads `matched` (or worse, the whole
# audit reads fully clean). Post-fix: P1 is still bound (its own pair
# differs from its successor's), so C is correctly flagged `reused`
# alongside the (also-reused) superseded A.
# ===========================================================================


class TestPairFreeingIdentityLaundering:
    def test_freed_pair_is_flagged_reused_when_cited_by_an_unrelated_forged_entry(self):
        """GREEN: the fix. Boundary A (P1, real, corroborated) is
        "corrected" to a SECOND real pair P2 -- A's original line becomes
        `superseded`. Boundary C, NEVER reviewed, forges P1 directly. Post-
        fix: A's released pair (P1) still counts toward `_find_reused_pairs`,
        so BOTH A (reclassified from `superseded` to `reused`) and C
        (`reused`) are flagged -- closing the exploit this section exists
        for (pre-fix: C alone read `matched`, zero flags anywhere -- see
        the falsifiability revert-and-rerun in this task's own report for
        the RED confirmation, since asserting pre-fix behavior inline here
        would just re-encode the bug as a second, contradictory test)."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:aaa111", reviewer=_WRONG_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=_IDENTITY,
                )
            ),
            # C: a NEVER-reviewed boundary, forged by citing the freed P1
            # (_IDENTITY) directly.
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:ccc333", reviewer=_IDENTITY, ts="2026-08-30T22:00:00Z")
            ),
        ]
        rows = [_spend_row()]  # corroborates ONLY _IDENTITY (P1)
        result = ara.audit_clean_entries(entries, rows, 1800)
        # Key by (key, ts) -- precommit:aaa111 has TWO rows (the released A
        # and its successor B), so keying by `key` alone would collapse
        # them and silently check the wrong one.
        attributions = {(r["key"], r["ts"]): r["attribution"] for r in result["results"]}
        # A itself: no longer silently exempted -- its pair was RELEASED
        # (its successor B carries a DIFFERENT pair, _WRONG_IDENTITY), so it
        # is reclassified from "superseded" to "reused".
        assert attributions[("precommit:aaa111", "2026-08-30T21:00:00Z")] == "reused"
        # B (the successor, holding the live/current identity for the key)
        # is unaffected -- its own pair (_WRONG_IDENTITY) is cited nowhere
        # else, so it corroborates (or not) purely on its own merits.
        assert attributions[("precommit:aaa111", "2026-08-30T21:05:00Z")] == "unmatched"
        # C: forging the freed P1 directly -- this is the exploit shape.
        assert attributions[("precommit:ccc333", "2026-08-30T22:00:00Z")] == "reused"
        assert result["superseded"] == 0
        assert result["reused"] == 2
        assert len(result["flagged"]) == 3  # A(reused) + B(unmatched) + C(reused)
        flagged_pairs = {(r["key"], r["ts"]) for r in result["flagged"]}
        assert flagged_pairs == {
            ("precommit:aaa111", "2026-08-30T21:00:00Z"),
            ("precommit:aaa111", "2026-08-30T21:05:00Z"),
            ("precommit:ccc333", "2026-08-30T22:00:00Z"),
        }

    def test_sanctioned_typo_fix_use_case_stays_unflagged_pair_unchanged(self):
        """Negative control -- the PRIMARY sanctioned use case must be
        completely unaffected by this fix: a warm-chain round legitimately
        re-cites the round-1 pair, and a --correct-identity call fixing a
        TYPO'D entry back to that SAME already-correct pair must stay
        exempt (superseded, not reused) -- this is
        `test_a_correction_never_causes_a_live_entry_to_be_flagged_reused`
        re-asserted here for locality, since it is the exact negative space
        Blocker 1(a) must not regress."""
        entries = [
            # The wrong original -- superseded once the correction lands.
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            # The correction -- cites the SAME real identity the original
            # ALSO happened to cite (byte-identical pair -- never released).
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:abc123", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z",
                    corrects_from=_WRONG_IDENTITY,
                )
            ),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["reused"] == 0
        assert result["superseded"] == 1
        assert result["matched"] == 1
        assert result["flagged"] == []

    def test_released_pair_with_no_third_party_citer_stays_superseded_not_reused(self):
        """A released pair that is NOT cited by anything else must stay
        `superseded` (not spuriously flagged `reused` just because the fix
        now tracks it) -- the fix only widens WHAT `_find_reused_pairs`
        considers, it never makes a genuinely single-cited pair look
        duplicated. The successor B is given ITS OWN corroborating
        spend.jsonl row so its (independently correct) `matched` verdict
        isolates the released-pair question from an unrelated "B itself
        has no corroboration" confound."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/repo", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo", "precommit:aaa111", reviewer=_WRONG_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=_IDENTITY,
                )
            ),
        ]
        rows = [_spend_row(), _spend_row(tool_use_id="toolu_WRONG", ts="2026-08-30T21:05:05Z")]
        result = ara.audit_clean_entries(entries, rows, 1800)
        attributions = {(r["key"], r["ts"]): r["attribution"] for r in result["results"]}
        assert attributions[("precommit:aaa111", "2026-08-30T21:00:00Z")] == "superseded"
        assert attributions[("precommit:aaa111", "2026-08-30T21:05:00Z")] == "matched"
        assert result["reused"] == 0
        assert result["flagged"] == []


# ===========================================================================
# _find_reused_pairs / the "reused" attribution bucket — BLOCKER 1
# (2026-08-30 trust-architect review): the cheapest forgery is copying ONE
# real reviewer row's (agent_id, tool_use_id) into a SECOND `clean` entry —
# both showed `matched`, zero flags, before this bucket existed.
# ===========================================================================


class TestFindReusedPairs:
    def test_no_duplicates_returns_empty_set(self):
        results = [
            {"reviewer_agent_id": "a1", "reviewer_tool_use_id": "t1"},
            {"reviewer_agent_id": "a2", "reviewer_tool_use_id": "t2"},
        ]
        assert ara._find_reused_pairs(results) == set()

    def test_duplicate_pair_is_returned(self):
        results = [
            {"reviewer_agent_id": "a1", "reviewer_tool_use_id": "t1"},
            {"reviewer_agent_id": "a1", "reviewer_tool_use_id": "t1"},
        ]
        assert ara._find_reused_pairs(results) == {("a1", "t1")}

    def test_entries_with_no_identity_are_never_counted(self):
        results = [
            {"reviewer_agent_id": None, "reviewer_tool_use_id": None},
            {"reviewer_agent_id": None, "reviewer_tool_use_id": None},
        ]
        assert ara._find_reused_pairs(results) == set()


class TestAuditCleanEntriesReusedBucket:
    def test_same_pair_cited_twice_both_flagged_reused_not_matched(self):
        """THE EXACT DEMONSTRATED FORGERY: two `clean` entries citing the
        identical (agent_id, tool_use_id) pair copied from one real
        spend.jsonl row. Before the reused bucket existed both showed
        `matched`, zero flags. Both must now be `reused`, not `matched`."""
        entries = [
            ara.parse_review_entry(
                _lr_line("/r1", "precommit:a111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z")
            ),
            ara.parse_review_entry(
                _lr_line("/r2", "precommit:a222", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z")
            ),
        ]
        rows = [_spend_row()]  # the ONE real dispatch both fabricated entries cite
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["matched"] == 0
        assert result["reused"] == 2
        assert len(result["flagged"]) == 2
        assert all(r["attribution"] == "reused" for r in result["flagged"])

    def test_pair_cited_once_stays_matched(self):
        """The negative twin: a pair cited by exactly one clean entry is
        genuinely `matched`, never `reused` — this suite cannot pass by a
        stub that always flags everything as reused."""
        entries = [
            ara.parse_review_entry(_lr_line("/r1", "precommit:a111", reviewer=_IDENTITY)),
        ]
        rows = [_spend_row()]
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["matched"] == 1
        assert result["reused"] == 0
        assert result["flagged"] == []

    def test_reused_overrides_unmatched_too(self):
        """A reused pair that ALSO fails to corroborate against spend.jsonl
        is still classified reused (the more specific finding), not
        unmatched."""
        entries = [
            ara.parse_review_entry(_lr_line("/r1", "precommit:a111", reviewer=_IDENTITY)),
            ara.parse_review_entry(_lr_line("/r2", "precommit:a222", reviewer=_IDENTITY)),
        ]
        result = ara.audit_clean_entries(entries, [], 1800)  # no spend rows -- nothing corroborates
        assert result["unmatched"] == 0
        assert result["reused"] == 2


class TestRekeyExemption:
    """2026-09-01 fix round 2 BLOCKER: record_review.py --rekey (AA-0064
    Item 8) legitimately re-cites the prior entry's exact identity pair AND
    writes rekey=<prior-key>. Without the exemption below, every successful
    --rekey would be misreported as forgery (reused) by this auditor, and
    daily_sweep's step E would relay it as a finding on the unattended
    sweep. Falsifiability: every test here goes RED against the unfixed
    auditor (verified in a scratch copy — see the fix-round report)."""

    def test_legitimate_rekey_pair_is_exempt_not_reused(self):
        """The core positive case: a TARGET reviewed and corroborated
        normally, then a SOURCE --rekey entry carrying the SAME identity
        forward, with rekey= naming TARGET's own key. Neither may end up
        `reused` -- BOTH resolve to a non-flagged verdict (matched or the
        new rekey-exempt)."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z",  # 2h later -- outside the default 1800s window
                    rekey="precommit:aaa111",
                )
            ),
        ]
        rows = [_spend_row()]  # only corroborates the TARGET's own ts, not SOURCE's
        result = ara.audit_clean_entries(entries, rows, 1800)
        assert result["reused"] == 0
        assert result["unmatched"] == 0
        assert len(result["flagged"]) == 0
        attributions = {r["key"]: r["attribution"] for r in result["results"]}
        assert attributions["precommit:aaa111"] in ("matched", "rekey-exempt")
        assert attributions["precommit:bbb222"] in ("matched", "rekey-exempt")
        assert result["rekey_exempt"] >= 1

    def test_rekey_pointing_at_a_missing_prior_still_flagged(self):
        """A rekey= naming a key that does not resolve to any real clean
        entry (missing prior, or ledger corruption) gets NO exemption --
        record_review.py --rekey itself never writes such a value (BLOCKER
        1/Item 5 of the AA-0064 fix round both refuse before recording), so
        this shape is never trusted."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    rekey="precommit:doesnotexist0",
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [], 1800)  # nothing corroborates
        assert result["unmatched"] == 1
        assert result["rekey_exempt"] == 0
        assert len(result["flagged"]) == 1
        assert result["flagged"][0]["attribution"] == "unmatched"

    def test_genuinely_forged_duplicate_pair_without_rekey_still_reused(self):
        """The detector must not lose its real catch: two clean entries
        citing the identical (agent_id, tool_use_id) pair, NEITHER carrying
        a rekey= link, is exactly BLOCKER 1's original forgery shape and
        must stay reused, unaffected by the rekey exemption existing."""
        entries = [
            ara.parse_review_entry(_lr_line("/r1", "precommit:a111", reviewer=_IDENTITY)),
            ara.parse_review_entry(_lr_line("/r2", "precommit:a222", reviewer=_IDENTITY)),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["reused"] == 2
        assert result["rekey_exempt"] == 0
        assert all(r["attribution"] == "reused" for r in result["flagged"])

    def test_rekey_exemption_never_launders_a_third_party_forger_sharing_the_pair(self):
        """A legitimate rekey chain (SOURCE -> TARGET) whose shared identity
        pair is ALSO cited by a THIRD, unrelated clean entry (a genuine
        forger copying the same pair) must NOT let the forger hide behind
        the legitimate chain -- the whole pair stays reused for everyone
        citing it, including the otherwise-legitimate SOURCE/TARGET."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                )
            ),
            ara.parse_review_entry(
                _lr_line("/repo2", "precommit:ccc333", reviewer=_IDENTITY)  # the forger
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["rekey_exempt"] == 0
        assert result["reused"] == 3
        assert all(r["attribution"] == "reused" for r in result["flagged"])


class TestRekeyStarShape:
    """Finding 1 (2026-09-01 fix round 3): record_review.py --rekey now
    always resolves and cites a chain's ROOT (never an intermediate),
    turning a chain into a star. The auditor's own exemption is generalized
    from a 2-entry pair to the full star -- but ONLY when every member
    resolves DIRECTLY to a genuine root (one hop, never a transitive walk)."""

    def test_star_three_members_all_exempt_zero_flagged(self):
        """(a) star A + B(rekey=A) + C(rekey=A) -> all three exempt,
        flagged=0. Falsifiability: RED against the OLD sole-citers rule
        (which only ever considered a 2-entry {source, target} pair, never
        a 3+-member star)."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:ccc333", reviewer=_IDENTITY,
                    ts="2026-08-31T01:00:00Z", rekey="precommit:aaa111",
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["reused"] == 0
        assert len(result["flagged"]) == 0
        assert result["rekey_exempt"] >= 2

    def test_star_plus_third_party_citer_without_rekey_all_flagged(self):
        """(b) star + third-party citer WITHOUT rekey= -> ALL flagged
        (laundering still dead) -- a forger cannot hide behind a legitimate
        star by reusing its identity pair from outside the star."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:ccc333", reviewer=_IDENTITY,
                    ts="2026-08-31T01:00:00Z", rekey="precommit:aaa111",
                )
            ),
            ara.parse_review_entry(
                _lr_line("/repo2", "precommit:ddd444", reviewer=_IDENTITY)  # the forger, no rekey=
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["rekey_exempt"] == 0
        assert result["reused"] == 4
        assert len(result["flagged"]) == 4

    def test_legacy_multihop_chain_stays_flagged_known_over_flag(self):
        """(c) legacy 2-hop chain (C.rekey=B, B.rekey=A) written by the OLD
        (pre-root-resolution) writer -> expected FLAGGED -- pinned as the
        known, SAFE-DIRECTION over-flag shape. B is not a genuine root (it
        carries its own rekey=), so C is never grouped into any star at
        all, and B's own citation of the shared pair (alongside A and C)
        leaves the whole pair un-exemptable."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:ccc333", reviewer=_IDENTITY,
                    ts="2026-08-31T01:00:00Z", rekey="precommit:bbb222",  # legacy: cites B, not root A
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["reused"] == 3
        assert result["rekey_exempt"] == 0
        assert all(r["attribution"] == "reused" for r in result["flagged"])

    def test_fabricated_root_with_no_corroboration_never_exempts_its_star(self):
        """BLOCKER (2026-09-01 fix round 4): the reviewer's exact repro --
        TWO fabricated `clean` entries sharing an INVENTED identity (never
        earned, no real spend.jsonl row anywhere), with the second carrying
        rekey=<the first's key>. Pre-fix, the star exemption checked only
        pair-matching and citer-exclusivity, never whether the ROOT itself
        was independently corroborated -- both entries exempted each other
        with ZERO spend.jsonl access needed, cheaper than the module's
        pre-existing documented forgery hole (which at least requires
        copying a REAL row's identity). BOTH must stay flagged.

        Falsifiability: this assertion is the exact shape the reviewer
        measured going GREEN (0 flagged) on the unfixed code -- verified in
        a scratch copy (see the fix-round report) that reverting the
        pre_reused root-corroboration check makes this assertion fail
        (result comes back rekey_exempt=2, flagged=0) while the fixed code
        here correctly reports both entries reused/flagged.
        """
        invented_identity = rr.compose_reviewer_field(
            "code-reviewer", "invented_root_id", "toolu_INVENTEDROOT"
        )
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=invented_identity,
                    ts="2026-08-30T21:00:00Z",
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=invented_identity,
                    ts="2026-08-30T21:05:00Z", rekey="precommit:aaa111",
                )
            ),
        ]
        # No spend.jsonl row anywhere for the invented identity -- neither
        # entry ever happened for real.
        result = ara.audit_clean_entries(entries, [], 1800)
        verdicts = {r["attribution"] for r in result["results"]}
        assert verdicts == {"reused"}
        assert result["rekey_exempt"] == 0
        assert len(result["flagged"]) == 2
        assert all(r["attribution"] == "reused" for r in result["flagged"])


class TestRekeyCombinations:
    """Finding 4 (2026-09-01 fix round 3): combination pins the reviewer
    verified by hand. (d) prior-with-blockers is a WRITER-level concern and
    lives in test_precommit_review_gate.py instead (this file has no git
    repo fixtures) -- see
    test_rekey_root_resolution_refuses_when_prior_is_blockers_not_clean
    there."""

    def test_f_cross_repo_rekey_never_resolves(self):
        """(f) cross-repo: a fabricated entry in repo X citing a key that is
        REAL and clean but belongs to a DIFFERENT repo Y must never resolve
        -- the (repo, key) tuple lookup is repo-scoped by construction. Uses
        a DISTINCT identity for the repoX entry so the assertion isolates
        the cross-repo rekey question from the (unrelated, independently
        correct) pair-reuse-across-repos detection -- see
        test_rekey_exemption_never_launders_a_third_party_forger_sharing_the_pair
        for that separate property."""
        other_identity = rr.compose_reviewer_field("code-reviewer", "xrepo1", "toolu_XREPO")
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repoY", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repoX", "precommit:bbb222", reviewer=other_identity,
                    ts="2026-08-30T21:01:00Z", rekey="precommit:aaa111",  # names repoY's key, wrong repo
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        by_key = {r["key"]: r for r in result["results"]}
        assert by_key["precommit:bbb222"]["attribution"] == "unmatched"
        assert result["rekey_exempt"] == 0

    def test_g_self_reference_never_resolves(self):
        """(g) an entry whose rekey= names its OWN key must never resolve
        as a link to itself."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY,
                    rekey="precommit:aaa111",  # self-reference
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["rekey_exempt"] == 0
        # The entry's own ordinary join result stands -- it independently
        # matches its own real spend.jsonl row here, self-reference or not.
        assert result["results"][0]["attribution"] == "matched"

    def test_i_mutual_reference_both_flagged(self):
        """(i) mutual A<->B: A.rekey=B and B.rekey=A. Neither is a genuine
        root (each names the OTHER, which itself carries rekey=), so
        _root_star_groups forms NO star for either -- both stay flagged if
        their identity pair repeats, exactly like the legacy-chain shape.
        Structurally impossible for the real writer to ever produce (an
        already-written entry can never be modified to add a rekey= after
        the fact -- BLOCKER 1 refuses any write onto an existing key), so
        this is a purely adversarial/fabricated-ledger scenario -- pinned
        here as the auditor's own safe, non-exemptable default."""
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY,
                    ts="2026-08-30T21:00:00Z", rekey="precommit:bbb222",
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", rekey="precommit:aaa111",
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        assert result["rekey_exempt"] == 0
        assert result["reused"] == 2
        assert all(r["attribution"] == "reused" for r in result["flagged"])

    def test_rekey_source_with_a_different_reviewer_identity_is_not_exempt(self):
        """Finding 2 (2026-09-01 fix round 3): an entry whose rekey= names
        a real clean root but whose OWN identity pair DIFFERS from the
        root's gets NO exemption -- the mechanical digest-identity proof
        only vouches for the identity it actually names. This is also the
        reviewer's measured attack variant, framed adversarially in the
        next test (fabricated entry, invented identity, rekey=<real clean
        key>) -- same code path, same fix. RED without Finding 2's fix (the
        pre-fix unconditional branch exempted this regardless of pair
        match)."""
        other_identity = rr.compose_reviewer_field("trust-architect", "zz9", "toolu_ZZZ")
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=other_identity,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                )
            ),
        ]
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        by_key = {r["key"]: r for r in result["results"]}
        assert by_key["precommit:bbb222"]["attribution"] == "unmatched"
        assert by_key["precommit:aaa111"]["attribution"] == "matched"
        assert result["rekey_exempt"] == 0

    def test_finding2_attack_variant_fabricated_entry_invented_identity_stays_flagged(self):
        """Finding 2's own required falsifiability test: a FABRICATED entry
        citing an INVENTED (never-earned) identity, with rekey=<a real
        clean key>, must stay FLAGGED -- the cheapest forgery variant the
        unconditional exemption could otherwise create (claim "I'm a
        legitimate rekey of X" without ever having X's identity). Falsified
        RED against the unfixed (pre-Finding-2) branch in a scratch copy."""
        forged_identity = rr.compose_reviewer_field("code-reviewer", "invented999", "toolu_FAKE")
        entries = [
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                )
            ),
            ara.parse_review_entry(
                _lr_line(
                    "/repo1", "precommit:fab999", reviewer=forged_identity,
                    ts="2026-08-30T21:01:00Z", rekey="precommit:aaa111",
                )
            ),
        ]
        # No spend.jsonl row anywhere for the invented identity -- it truly
        # never happened.
        result = ara.audit_clean_entries(entries, [_spend_row()], 1800)
        by_key = {r["key"]: r for r in result["results"]}
        assert by_key["precommit:fab999"]["attribution"] == "unmatched"
        assert by_key["precommit:fab999"] in result["flagged"]
        assert result["rekey_exempt"] == 0


# ===========================================================================
# THE REQUIRED FALSIFIABILITY TEST — build_report, both directions.
#
# This is the exact property the plan's Item 6b names as mandatory: "a
# clean ledger entry whose reviewer=/agent_id has NO matching lease row in
# spend.jsonl within the review's time window IS flagged," proven alongside
# its negative twin (a matching row present -> NOT flagged) so this suite
# cannot pass by accident (a stub that always flags, or never flags, would
# fail exactly one of these two).
# ===========================================================================


class TestBuildReportFalsifiability:
    def test_clean_entry_with_no_matching_lease_row_is_flagged(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [])  # no spend rows at all -- nothing can corroborate this

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["status"] == "ok"
        assert audit["matched"] == 0
        assert audit["unmatched"] == 1
        assert len(audit["flagged"]) == 1
        assert audit["flagged"][0]["attribution"] == "unmatched"
        assert audit["flagged"][0]["reviewer_agent_id"] == "aa2a7f1545215c433"

    def test_clean_entry_with_matching_lease_row_is_not_flagged(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [_spend_row()])  # the SAME agent_id/tool_use_id, reviewer-typed

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["status"] == "ok"
        assert audit["matched"] == 1
        assert audit["unmatched"] == 0
        assert audit["flagged"] == []

    def test_two_clean_entries_citing_the_same_real_identity_are_both_flagged_reused(
        self, tmp_path
    ):
        """BLOCKER 1's required falsifiability property, at the build_report
        level: the reviewer's exact demonstrated forgery scenario -- two
        `clean` ledger entries citing the SAME real (agent_id, tool_use_id)
        pair copied from one genuine spend.jsonl row. Before the reused
        bucket, both showed `matched` and neither was flagged."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(
            lr_path,
            [
                _lr_line("/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"),
                _lr_line("/repo2", "precommit:bbb222", reviewer=_IDENTITY, ts="2026-08-30T21:05:00Z"),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])  # the ONE real dispatch both entries cite

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["matched"] == 0
        assert audit["reused"] == 2
        assert len(audit["flagged"]) == 2
        assert all(e["attribution"] == "reused" for e in audit["flagged"])

    def test_real_rekey_ledger_fixture_is_matched_or_exempt_zero_reused(self, tmp_path):
        """The coordinator's own re-run target: a REAL rekey ledger fixture
        (a TARGET entry, corroborated normally, plus a SOURCE --rekey entry
        naming it) must produce matched/exempt, 0 reused -- at the SAME
        build_report level daily_sweep step E actually consumes."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:aaa111", reviewer=_IDENTITY, ts="2026-08-30T21:00:00Z"
                ),
                _lr_line(
                    "/repo1", "precommit:bbb222", reviewer=_IDENTITY,
                    ts="2026-08-30T23:00:00Z", rekey="precommit:aaa111",
                ),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["reused"] == 0
        assert audit["flagged"] == []
        assert all(e["attribution"] in ("matched", "rekey-exempt") for e in audit["results"])

    def test_matching_row_of_the_wrong_agent_type_still_flags(self, tmp_path):
        """The negative fixture is not just "any row exists" -- it must be
        reviewer-typed too, or this test would be trivially satisfiable by
        an unrelated dispatch that happens to share nothing meaningful."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [_spend_row(agent_type="implement")])

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["matched"] == 0
        assert audit["unmatched"] == 1

    def test_real_correct_identity_ledger_fixture_is_matched_or_superseded_zero_flagged(
        self, tmp_path
    ):
        """The #5133 reproduction, at the build_report level: a
        wrong-identity original entry plus a record_review.py
        --correct-identity correction for the exact same key must produce
        matched + superseded, ZERO flagged -- at the SAME level the daily
        audit sweep actually consumes. This is the exact ledger shape
        `record_review.py --correct-identity` produces (proven directly
        against the live write path in test_record_review.py's own
        `test_correct_identity_happy_path_appends_not_overwrites`)."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        wrong_identity = rr.compose_reviewer_field(
            "code-reviewer", "aa2a7f1545215c433", "toolu_WRONG"
        )
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=wrong_identity,
                    ts="2026-08-30T21:00:00Z",
                ),
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=wrong_identity,
                ),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])  # corroborates the CORRECTED identity only

        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        audit = report["clean_attribution"]
        assert audit["flagged"] == []
        assert audit["matched"] == 1
        assert audit["superseded"] == 1
        assert all(e["attribution"] in ("matched", "superseded") for e in audit["results"])


# ===========================================================================
# build_report — absent ledgers, provenance.
# ===========================================================================


class TestBuildReportAbsentLedgers:
    def test_both_absent(self, tmp_path):
        report = ara.build_report(
            last_reviewed_path=str(tmp_path / "nope1"),
            spend_path=str(tmp_path / "nope2"),
            now=_NOW,
        )
        assert report["last_reviewed"]["status"] == "absent"
        assert report["spend"]["status"] == "absent"
        assert report["clean_attribution"]["status"] == "absent"
        assert report["clean_attribution"]["flagged"] == []

    def test_last_reviewed_absent_spend_present_still_absent_audit(self, tmp_path):
        spend_path = tmp_path / "spend.jsonl"
        _write_jsonl(spend_path, [_spend_row()])
        report = ara.build_report(
            last_reviewed_path=str(tmp_path / "nope"), spend_path=str(spend_path), now=_NOW
        )
        # A partial ledger set must never silently compute "0 flagged" --
        # it must be explicit that no real audit ran.
        assert report["clean_attribution"]["status"] == "absent"

    def test_empty_last_reviewed_and_spend_is_ok_zero_clean(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [])
        _write_jsonl(spend_path, [])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        assert report["clean_attribution"]["status"] == "ok"
        assert report["clean_attribution"]["total_clean"] == 0
        assert report["clean_attribution"]["flagged"] == []


# ===========================================================================
# render_table — smoke tests, never crash on any report shape.
# ===========================================================================


class TestRenderTable:
    def test_renders_flagged_entries_without_crashing(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report)
        assert "FLAGGED (1)" in text
        assert "unmatched" in text

    def test_renders_absent_ledgers_without_crashing(self, tmp_path):
        report = ara.build_report(
            last_reviewed_path=str(tmp_path / "nope1"),
            spend_path=str(tmp_path / "nope2"),
            now=_NOW,
        )
        text = ara.render_table(report)
        assert "CANNOT AUDIT" in text

    def test_renders_no_flagged_entries_without_crashing(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [_spend_row()])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report)
        assert "no unattributed clean entries found." in text

    def test_renders_a_superseded_correction_ledger_without_crashing(self, tmp_path):
        """A --correct-identity-shaped ledger (a superseded entry + its live
        successor) renders cleanly, with zero flagged entries, and the
        superseded= count visible in the summary line."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        wrong_identity = rr.compose_reviewer_field(
            "code-reviewer", "aa2a7f1545215c433", "toolu_WRONG"
        )
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=wrong_identity,
                    ts="2026-08-30T21:00:00Z",
                ),
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=wrong_identity,
                ),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report)
        assert "superseded=1" in text
        assert "no unattributed clean entries found." in text

    def test_only_superseded_enumerates_the_superseded_entry(self, tmp_path):
        """Blocker 1(b)/F3: `--only superseded` is a genuinely different
        shape from the other three `--only` categories -- it enumerates
        `results`, not `flagged` (a superseded entry is never IN `flagged`
        at all). Before this fix, `--only superseded` exited 2
        (unrecognized value). Note `corrects_from=`/`corrected_at=` live on
        the SUCCESSOR (live) entry, not the superseded entry itself -- see
        `test_renders_corrects_from_and_corrected_at_when_only_is_unset`
        for that half."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        wrong_identity = rr.compose_reviewer_field(
            "code-reviewer", "aa2a7f1545215c433", "toolu_WRONG"
        )
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=wrong_identity,
                    ts="2026-08-30T21:00:00Z",
                ),
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=wrong_identity,
                    corrected_at="2026-09-09T12:00:00Z",
                ),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report, only="superseded")
        assert "FLAGGED (1 of category 'superseded')" in text
        assert "[superseded " in text
        assert "reviewer_type=code-reviewer" in text

        # Blocker 1(b): the JSON path narrows identically, via main().
        json_shown = ara._filter_flagged(report["clean_attribution"], "superseded")
        assert len(json_shown) == 1
        assert json_shown[0]["attribution"] == "superseded"
        assert json_shown[0]["key"] == "precommit:abc123"
        assert json_shown[0]["ts"] == "2026-08-30T21:00:00Z"  # the STALE original entry

    def test_only_superseded_with_no_superseded_entries_prints_none_found(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo1", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [_spend_row()])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report, only="superseded")
        assert "no flagged entries of category 'superseded' found." in text

    def test_renders_corrects_from_and_corrected_at_on_a_live_flagged_row(self, tmp_path):
        """`corrects_from=`/`corrected_at=` render on a genuinely FLAGGED
        (not superseded) row too: a corrected entry whose new identity is
        itself unmatched (e.g. the corrected pair aged out of spend.jsonl's
        retention window) still carries both fields forward -- proving the
        row-rendering feature, not just the --only superseded enumeration
        path exercised above."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        wrong_identity = rr.compose_reviewer_field(
            "code-reviewer", "aa2a7f1545215c433", "toolu_WRONG"
        )
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=wrong_identity,
                    ts="2026-08-30T21:00:00Z",
                ),
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=wrong_identity,
                    corrected_at="2026-09-09T12:00:00Z",
                ),
            ],
        )
        _write_jsonl(spend_path, [])  # nothing corroborates -- the live entry is unmatched
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report)
        assert "[unmatched " in text
        assert f"corrects_from={wrong_identity}" in text
        assert "corrected_at=2026-09-09T12:00:00Z" in text


# ===========================================================================
# render_table cap + --only filter — MAJOR finding (2026-08-30 review): a
# live run against real data printed 1,206 flagged lines with no cap.
# ===========================================================================


def _many_no_identity_clean_entries(n: int) -> list[dict]:
    return [
        ara.parse_review_entry(_lr_line(f"/repo{i}", f"precommit:{i:08x}"))
        for i in range(n)
    ]


class TestRenderTableCapAndFilter:
    def test_flagged_list_is_capped_at_max_shown(self, tmp_path):
        entries = _many_no_identity_clean_entries(ara._MAX_FLAGGED_SHOWN + 5)
        audit = ara.audit_clean_entries(entries, [], 1800)
        section = {
            "status": "ok", "ledger": "x", "read_error": None,
            "skipped_unparseable": 0, "as_of": None, "command": "x",
        }
        report = {
            "generated_at": "2026-08-30T22:00:00Z",
            "window_seconds": 1800,
            "command": "x",
            "last_reviewed": section,
            "spend": dict(section),
            "clean_attribution": {"status": "ok", **audit},
        }

        text = ara.render_table(report)
        shown_lines = [ln for ln in text.splitlines() if ln.startswith("  [")]
        assert len(shown_lines) == ara._MAX_FLAGGED_SHOWN
        assert "... and 5 more" in text

    def test_only_filter_narrows_to_one_category(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(
            lr_path,
            [
                _lr_line("/repo1", "precommit:aaaa", reviewer=_IDENTITY),  # unmatched
                _lr_line("/repo2", "precommit:bbbb"),  # no-identity
            ],
        )
        _write_jsonl(spend_path, [])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report, only="unmatched")
        assert "unmatched" in text
        assert "no-identity" not in text
        assert "FLAGGED (1 of category 'unmatched')" in text

    def test_only_filter_with_no_matches_prints_none_found(self, tmp_path):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo1", "precommit:aaaa")])  # no-identity only
        _write_jsonl(spend_path, [])
        report = ara.build_report(
            last_reviewed_path=str(lr_path), spend_path=str(spend_path), now=_NOW
        )
        text = ara.render_table(report, only="reused")
        assert "no flagged entries of category 'reused' found." in text


# ===========================================================================
# CLI — parse_args / main.
# ===========================================================================


class TestParseArgs:
    def test_default_window(self):
        assert ara.parse_args([]) == (ara.DEFAULT_WINDOW_SECONDS, False, None)

    def test_window_space_form(self):
        assert ara.parse_args(["--window-seconds", "60"]) == (60, False, None)

    def test_window_equals_form(self):
        assert ara.parse_args(["--window-seconds=60"]) == (60, False, None)

    def test_json_flag(self):
        assert ara.parse_args(["--json"]) == (ara.DEFAULT_WINDOW_SECONDS, True, None)

    def test_zero_window_raises(self):
        with pytest.raises(ara.ArgError):
            ara.parse_args(["--window-seconds", "0"])

    def test_non_integer_window_raises(self):
        with pytest.raises(ara.ArgError):
            ara.parse_args(["--window-seconds", "abc"])

    def test_unknown_argument_raises(self):
        with pytest.raises(ara.ArgError):
            ara.parse_args(["--bogus"])

    def test_only_space_form(self):
        assert ara.parse_args(["--only", "unmatched"]) == (ara.DEFAULT_WINDOW_SECONDS, False, "unmatched")

    def test_only_equals_form(self):
        assert ara.parse_args(["--only=reused"]) == (ara.DEFAULT_WINDOW_SECONDS, False, "reused")

    def test_only_no_identity_value_accepted(self):
        assert ara.parse_args(["--only", "no-identity"])[2] == "no-identity"

    def test_only_superseded_value_accepted(self):
        # Blocker 1(b)/F3 (2026-09-09, #5133): --only superseded used
        # to raise ArgError (exit 2) -- "superseded" was not in
        # _VALID_ONLY_VALUES at all.
        assert ara.parse_args(["--only", "superseded"])[2] == "superseded"

    def test_only_invalid_value_raises(self):
        with pytest.raises(ara.ArgError):
            ara.parse_args(["--only", "matched"])  # "matched" is not a flagged category

    def test_only_missing_value_raises(self):
        with pytest.raises(ara.ArgError):
            ara.parse_args(["--only"])


class TestMain:
    def test_help_returns_zero(self, capsys):
        assert ara.main(["--help"]) == 0
        assert "Usage" in capsys.readouterr().out

    def test_bad_argument_returns_two(self, capsys):
        assert ara.main(["--bogus"]) == 2

    def test_main_never_exits_nonzero_on_flagged_findings(self, tmp_path, monkeypatch, capsys):
        """Report-only, not enforcement: even a report full of flagged
        unattributed clean entries must exit 0 -- this module gates
        nothing at commit time (explicit framing constraint, Item 6b)."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [_lr_line("/repo", "precommit:abc123", reviewer=_IDENTITY)])
        _write_jsonl(spend_path, [])
        monkeypatch.setattr(ara, "LEDGER_LAST_REVIEWED", str(lr_path))
        monkeypatch.setattr(ara, "LEDGER_SPEND", str(spend_path))
        rc = ara.main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "FLAGGED" in out

    def test_main_json_output_is_valid_json(self, tmp_path, monkeypatch, capsys):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(lr_path, [])
        _write_jsonl(spend_path, [])
        monkeypatch.setattr(ara, "LEDGER_LAST_REVIEWED", str(lr_path))
        monkeypatch.setattr(ara, "LEDGER_SPEND", str(spend_path))
        rc = ara.main(["--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert "clean_attribution" in payload

    def test_main_only_flag_narrows_json_flagged_list(self, tmp_path, monkeypatch, capsys):
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        _write_lines(
            lr_path,
            [
                _lr_line("/repo1", "precommit:aaaa", reviewer=_IDENTITY),  # unmatched
                _lr_line("/repo2", "precommit:bbbb"),  # no-identity
            ],
        )
        _write_jsonl(spend_path, [])
        monkeypatch.setattr(ara, "LEDGER_LAST_REVIEWED", str(lr_path))
        monkeypatch.setattr(ara, "LEDGER_SPEND", str(spend_path))
        rc = ara.main(["--json", "--only", "unmatched"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        flagged = payload["clean_attribution"]["flagged"]
        assert len(flagged) == 1
        assert flagged[0]["attribution"] == "unmatched"

    def test_main_invalid_only_value_returns_two(self, capsys):
        assert ara.main(["--only", "matched"]) == 2

    def test_main_only_superseded_narrows_json_to_the_superseded_entry(
        self, tmp_path, monkeypatch, capsys
    ):
        """Blocker 1(b)/F3, at the full main() CLI level: `--only
        superseded` no longer exits 2, and narrows the JSON `flagged` list
        to the superseded (identity-correction) entry — the STALE
        original, keyed by its own (earlier) ts=. `corrects_from=`/
        `corrected_at=` live on the successor entry, not this one; that
        half is covered by
        `TestRenderTable.test_renders_corrects_from_and_corrected_at_on_a_live_flagged_row`."""
        lr_path = tmp_path / "last_reviewed"
        spend_path = tmp_path / "spend.jsonl"
        wrong_identity = rr.compose_reviewer_field(
            "code-reviewer", "aa2a7f1545215c433", "toolu_WRONG"
        )
        _write_lines(
            lr_path,
            [
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=wrong_identity,
                    ts="2026-08-30T21:00:00Z",
                ),
                _lr_line(
                    "/repo1", "precommit:abc123", reviewer=_IDENTITY,
                    ts="2026-08-30T21:05:00Z", corrects_from=wrong_identity,
                    corrected_at="2026-09-09T12:00:00Z",
                ),
            ],
        )
        _write_jsonl(spend_path, [_spend_row()])
        monkeypatch.setattr(ara, "LEDGER_LAST_REVIEWED", str(lr_path))
        monkeypatch.setattr(ara, "LEDGER_SPEND", str(spend_path))
        rc = ara.main(["--json", "--only", "superseded"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        flagged = payload["clean_attribution"]["flagged"]
        assert len(flagged) == 1
        assert flagged[0]["attribution"] == "superseded"
        assert flagged[0]["ts"] == "2026-08-30T21:00:00Z"
        assert flagged[0]["reviewer_type"] == "code-reviewer"
