"""Hermetic, falsifiable tests for hooks/churn_report.py.

Every test builds its own small fixture ledger under `tmp_path` (or passes
plain in-memory lists/dicts straight to the pure functions) — the real
~/.claude ledgers are NEVER read here, per the spawning task. Each test is
built to go RED when its own metric's logic is stubbed out; where that
matters most (the metric-2/3 decision-vs-reason distinction, the metric-4
denominator/era split, the "read tokens_total as written" rule, and the
type-corrupt spend-line crash paths) the fixture is deliberately shaped so a
naive/wrong implementation produces a DIFFERENT number (or an exception)
than the correct one, not just a missing one.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import churn_report as cr
import pytest
import record_review as rr

_NOW = datetime(2026, 8, 25, 16, 0, 0, tzinfo=timezone.utc)


def _plan_entry(ts: str, repo: str, plan: str, blockers: int) -> dict:
    return {
        "ts": ts,
        "repo": repo,
        "plan": plan,
        "outcome": "clean" if blockers == 0 else "blockers",
        "blockers": blockers,
    }


def _log_line(ts: str, decision: str, hook: str = "pretooluse_bash", **fields: object) -> dict:
    # `hook` defaults to a REAL gate-allowlist name (BLOCKER 2): metric 2
    # (`denials_by_day_reason`) now restricts `would-block`/`deny` entries to
    # `cr._GATE_HOOKS`, so a fixture built with the old placeholder hook
    # ("x", in no allowlist) would silently zero out every existing metric-2
    # fixture in this file rather than actually exercising the metric.
    return {"ts": ts, "hook": hook, "decision": decision, "enforce": True, **fields}


def _spend_line(**overrides: object) -> dict:
    base: dict = {
        "ts": "2026-08-25T10:00:00Z",
        "session": "s1",
        "agent_type": "engine-architect",
        "model": "claude-sonnet-5",
        "tool_use_id": "tu1",
        "agent_id": "a1",
        "duration_ms": 1000,
        "tokens": {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4},
        "tokens_total": 10,
        "tokens_error": None,
        "late": False,
        "unreleased": False,
        "reaped": None,
    }
    base.update(overrides)
    return base


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


# ===========================================================================
# Metric 1 — plan-review rounds + plateaus.
# ===========================================================================


def test_detect_plateaus_example_with_three_plateaus():
    assert cr.detect_plateaus([8, 8, 3, 3, 1, 1, 1, 1]) == (3, 4)


def test_detect_plateaus_no_repeat_is_zero_plateaus():
    assert cr.detect_plateaus([13, 0]) == (0, 0)


def test_detect_plateaus_never_counts_a_zero_run():
    # A long run of CLEAN (0) rounds is the opposite of thrashing.
    assert cr.detect_plateaus([0, 0, 0, 0]) == (0, 0)


def test_detect_plateaus_empty_list_is_zero_zero():
    # F12: no rounds at all must not crash and must not fabricate a plateau.
    assert cr.detect_plateaus([]) == (0, 0)


def test_plan_round_metrics_single_round_plan_has_no_plateau():
    # F12: 7 of 31 live plans have exactly one round. One round can never
    # form a run of 2+, so plateau_count/longest_run must both be 0.
    entries = [_plan_entry("2026-08-20T10:00:00Z", "/r", "solo-plan", blockers=3)]
    metrics = cr.plan_round_metrics(entries)
    row = metrics["per_plan"][0]
    assert row["rounds"] == 1
    assert row["plateau_count"] == 0
    assert row["longest_run"] == 0


def test_plan_round_metrics_median_and_mean_on_known_set():
    entries = []
    counts_by_plan = {"p1": 1, "p2": 1, "p3": 2, "p4": 3, "p5": 5}
    for plan, n in counts_by_plan.items():
        for i in range(n):
            entries.append(_plan_entry(f"2026-08-2{i}T10:00:00Z", "/r", plan, blockers=0))
    metrics = cr.plan_round_metrics(entries)
    assert metrics["plans"] == 5
    assert metrics["total_rounds"] == 12
    assert metrics["median_rounds"] == 2
    assert metrics["mean_rounds"] == pytest.approx(2.4)


def test_plan_round_metrics_plateau_through_full_pipeline():
    seq = [8, 8, 3, 3, 1, 1, 1, 1]
    entries = [
        _plan_entry(f"2026-08-20T{i:02d}:00:00Z", "/r", "planX", blockers=b)
        for i, b in enumerate(seq)
    ]
    metrics = cr.plan_round_metrics(entries)
    row = metrics["per_plan"][0]
    assert row["plan"] == "planX"
    assert row["rounds"] == 8
    assert row["plateau_count"] == 3
    assert row["longest_run"] == 4
    assert metrics["total_plateaus"] == 3
    assert metrics["longest_plateau_run"] == 4


def test_plan_round_metrics_empty_ledger():
    metrics = cr.plan_round_metrics([])
    assert metrics["plans"] == 0
    assert metrics["median_rounds"] is None
    assert metrics["mean_rounds"] is None


def test_plan_round_metrics_worst_plan_first():
    # C7: per_plan must be sorted MOST-rounds-first. A mutant that sorts
    # ascending (or drops the sort) would put the 1-round plan first.
    entries = [
        _plan_entry("2026-08-01T10:00:00Z", "/r", "quiet-plan", blockers=0),
        _plan_entry("2026-08-10T10:00:00Z", "/r", "thrash-plan", blockers=5),
        _plan_entry("2026-08-11T10:00:00Z", "/r", "thrash-plan", blockers=3),
        _plan_entry("2026-08-12T10:00:00Z", "/r", "thrash-plan", blockers=1),
        _plan_entry("2026-08-05T10:00:00Z", "/r", "mid-plan", blockers=0),
        _plan_entry("2026-08-06T10:00:00Z", "/r", "mid-plan", blockers=0),
    ]
    metrics = cr.plan_round_metrics(entries)
    assert metrics["per_plan"][0]["plan"] == "thrash-plan"
    assert metrics["per_plan"][0]["rounds"] == 3
    assert metrics["per_plan"][-1]["plan"] == "quiet-plan"


def test_plan_round_sequences_sorts_by_ts_regardless_of_append_order():
    # C8: entries appended OUT of ts order must still yield a chronologically
    # ordered counts sequence. Appended order here is 3, 1, 2 (blockers
    # 1, 8, 3) but ts order is 1, 2, 3 (blockers 8, 3, 1).
    entries = [
        _plan_entry("2026-08-20T12:00:00Z", "/r", "planY", blockers=1),  # 3rd by ts
        _plan_entry("2026-08-20T10:00:00Z", "/r", "planY", blockers=8),  # 1st by ts
        _plan_entry("2026-08-20T11:00:00Z", "/r", "planY", blockers=3),  # 2nd by ts
    ]
    sequences = cr.plan_round_sequences(entries)
    assert sequences["planY"] == [8, 3, 1]


# ===========================================================================
# Metric 2 — real denials per day, by reason.
# ===========================================================================


def test_denials_by_day_reason_counts_only_denial_decisions_not_every_line():
    # 10 lines total, of which exactly 2 are `would-block`. A stub that
    # counts every line (ignores `decision`) would report 10, not 2 — the
    # measured ~13x error class this module exists to prevent.
    entries = [_log_line("2026-08-24T09:00:00Z", "ok") for _ in range(8)]
    entries.append(_log_line("2026-08-24T10:00:00Z", "would-block", reason="bulk-add"))
    entries.append(_log_line("2026-08-24T11:00:00Z", "would-block", reason="bulk-add"))
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 2
    assert result["by_day"]["2026-08-24"]["would-block"]["bulk-add"] == {"bulk-add": 2}


def test_denials_by_day_reason_total_by_class_zero_inits_absent_class():
    # F5: a window with ONLY would-block entries must still report deny: 0,
    # never omit the key -- a mutant that starts total_by_class as {}
    # (instead of `{cls: 0 for cls in _DENIAL_DECISIONS}`) would only ever
    # show classes actually seen in this window.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-24T09:05:00Z", "would-block", reason="bulk-add"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total_by_class"] == {"would-block": 2, "deny": 0}


def test_denials_by_day_reason_groups_by_day_and_reason_separately():
    entries = [
        _log_line("2026-08-23T09:00:00Z", "would-block", reason="state-verb:stash"),
        _log_line("2026-08-23T10:00:00Z", "would-block", reason="state-verb:stash"),
        _log_line("2026-08-23T11:00:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-24T09:00:00Z", "would-block", reason="bulk-add"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 4
    day23 = result["by_day"]["2026-08-23"]["would-block"]
    assert day23["state-verb:stash"] == {"state-verb:stash": 2}
    assert day23["bulk-add"] == {"bulk-add": 1}
    day24 = result["by_day"]["2026-08-24"]["would-block"]
    assert day24["bulk-add"] == {"bulk-add": 1}


def test_denials_by_day_reason_respects_days_window():
    entries = [
        _log_line("2026-08-10T09:00:00Z", "would-block", reason="bulk-add"),  # too old
        _log_line("2026-08-24T09:00:00Z", "would-block", reason="bulk-add"),  # in window
    ]
    result = cr.denials_by_day_reason(entries, days=7, now=_NOW)
    assert result["total"] == 1


def test_denials_by_day_reason_counts_deny_alongside_would_block():
    # B4: the EXECUTED deny from gh_issue_close_gate is decision == "deny",
    # a completely separate top-level value from "would-block". A stub
    # that only checks decision == "would-block" reports total == 2, not 5,
    # and never populates the "deny" class at all.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-24T09:05:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-24T10:00:00Z", "deny", reason="commit 'a1' not found"),
        _log_line("2026-08-24T10:05:00Z", "deny", reason="commit 'b2' not found"),
        _log_line("2026-08-24T10:10:00Z", "deny", reason="commit 'c3' not found"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 5
    assert result["total_by_class"] == {"would-block": 2, "deny": 3}
    assert "deny" in result["by_day"]["2026-08-24"]


def test_denials_by_day_reason_excludes_block_and_would_deny():
    # F5/docstring: "block" (retired review_gate / unrelated diagnostic
    # checkers) and "would-deny" (gh_issue_close_gate's LOG-ONLY sibling of
    # deny) are NOT real denials for this metric.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "block", reason="stop-hook-drift"),
        _log_line("2026-08-24T09:05:00Z", "would-deny", reason="not-enforcing"),
        _log_line("2026-08-24T09:10:00Z", "would-block", reason="bulk-add"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 1
    assert result["total_by_class"]["would-block"] == 1


def test_group_reason_text_collapses_sha_and_truncates_at_em_dash():
    # F16: two denials citing DIFFERENT shas for the SAME guard collapse to
    # the identical group key; a message with no sha/dash is unchanged.
    sha_a = "d90967dc9cbf7b081f6dc05cfd3c1acddda7d822"
    sha_b = "eceb7a18613c8bebf4e8100044b515c7d92717c9"
    r1 = f"commit '{sha_a}' is not an ancestor of 'master' — detail A"
    r2 = f"commit '{sha_b}' is not an ancestor of 'master' — detail B"
    r3 = "commit '<other-guard-sha>' not found in this repo — refusing to close"
    plain = "bulk-add"
    g1, g2, g3 = cr.group_reason_text(r1), cr.group_reason_text(r2), cr.group_reason_text(r3)
    assert g1 == g2
    # N9: g3 (r3 UNMODIFIED -- "<other-guard-sha>" isn't hex, so nothing gets
    # redacted) must differ from g1/g2's real-sha-redacted group -- proving
    # this without a real sha present is a distinct case from the next
    # assertion, which swaps in an actual hex sha for r3 and checks THAT.
    assert g3 != g1
    assert g1 != cr.group_reason_text(r3.replace("<other-guard-sha>", "0123456789abcdef"))
    assert cr.group_reason_text(plain) == "bulk-add"


def test_denials_by_day_reason_keeps_full_raw_text_under_grouped_key():
    # F16: --json output must never lose the raw reason text even though the
    # grouped label is what the table sorts on.
    r1 = "commit 'd90967dc9cbf7b081f6dc05cfd3c1acddda7d822' is not an ancestor of 'x' — a"
    r2 = "commit 'eceb7a18613c8bebf4e8100044b515c7d92717c9' is not an ancestor of 'x' — b"
    entries = [
        _log_line("2026-08-24T09:00:00Z", "deny", reason=r1),
        _log_line("2026-08-24T09:05:00Z", "deny", reason=r2),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    group_key = cr.group_reason_text(r1)
    raws = result["by_day"]["2026-08-24"]["deny"][group_key]
    assert raws == {r1: 1, r2: 1}
    assert sum(raws.values()) == 2


# ===========================================================================
# BLOCKER 1/2 (round-3 review) -- metric 2's `hook` gate allowlist.
# `decision in {would-block, deny}` alone is NOT sufficient; entries must
# also carry `hook in cr._GATE_HOOKS`. Full cross-product below.
# ===========================================================================


def test_denials_by_day_reason_would_block_from_gate_hook_is_counted():
    # (would-block, gate hook) -> COUNTED.
    entries = [_log_line("2026-08-24T09:00:00Z", "would-block", hook="pretooluse_bash")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 1
    assert result["total_by_class"]["would-block"] == 1
    assert result["excluded_non_gate_by_hook"] == {}


def test_denials_by_day_reason_would_block_from_check_safety_core_parity_excluded():
    # (would-block, check_safety_core_parity) -> EXCLUDED + surfaced. This
    # hook reuses "block"-shaped decisions for its own repo-hygiene signal
    # (see DENIAL DECISION VALUES / GATE HOOK ALLOWLIST in the module
    # docstring) and is not part of the command-gating surface metric 2
    # measures, even on the rare line where its `decision` happens to be
    # `would-block`.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "would-block", hook="check_safety_core_parity"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 0
    assert result["total_by_class"] == {"would-block": 0, "deny": 0}
    assert result["excluded_non_gate_by_hook"] == {"check_safety_core_parity": 1}


def test_denials_by_day_reason_would_block_from_sync_agent_rules_excluded():
    # (would-block, sync_agent_rules) -> EXCLUDED + surfaced.
    entries = [_log_line("2026-08-24T09:00:00Z", "would-block", hook="sync_agent_rules")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 0
    assert result["excluded_non_gate_by_hook"] == {"sync_agent_rules": 1}


def test_denials_by_day_reason_deny_from_gh_issue_close_gate_is_counted():
    # (deny, gh_issue_close_gate) -> COUNTED.
    entries = [_log_line("2026-08-24T09:00:00Z", "deny", hook="gh_issue_close_gate")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 1
    assert result["total_by_class"]["deny"] == 1
    assert result["excluded_non_gate_by_hook"] == {}


def test_denials_by_day_reason_deny_from_protected_board_guard_is_counted():
    # (deny, protected_board_guard) -> COUNTED. Gate 5b, added 2026-09-14
    # (GH #5490) -- same command-gating surface as gh_issue_close_gate above;
    # without this hook in `_GATE_HOOKS`, its `deny` decisions were invisible
    # to this metric, silently undercounting real command denials.
    entries = [_log_line("2026-08-24T09:00:00Z", "deny", hook="protected_board_guard")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 1
    assert result["total_by_class"]["deny"] == 1
    assert result["excluded_non_gate_by_hook"] == {}


def test_denials_by_day_reason_deny_from_mint_prod_session_excluded():
    # (deny, mint_prod_session) -> EXCLUDED + surfaced. This gates minting a
    # PROD secret, a completely different concern from a git-command denial,
    # even though it also logs `deny`.
    entries = [_log_line("2026-08-24T09:00:00Z", "deny", hook="mint_prod_session")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 0
    assert result["excluded_non_gate_by_hook"] == {"mint_prod_session": 1}


def test_denials_by_day_reason_deny_from_block_prod_mutations_excluded():
    # (deny, block_prod_mutations) -> EXCLUDED + surfaced. Gates a PROD HTTP
    # mutation, not a git command.
    entries = [_log_line("2026-08-24T09:00:00Z", "deny", hook="block_prod_mutations")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 0
    assert result["excluded_non_gate_by_hook"] == {"block_prod_mutations": 1}


def test_denials_by_day_reason_would_block_missing_hook_excluded_under_missing_token():
    # (would-block, hook missing) -> EXCLUDED + surfaced under "<missing>",
    # fail-closed: a line with no `hook` field at all must never be silently
    # counted as if it came from a known gate.
    entries = [{"ts": "2026-08-24T09:00:00Z", "decision": "would-block", "reason": "x"}]
    assert "hook" not in entries[0]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 0
    assert result["excluded_non_gate_by_hook"] == {"<missing>": 1}


def test_denials_by_day_reason_would_block_none_hook_excluded_under_missing_token():
    # Same as above but `hook` is explicitly `None` rather than absent --
    # both must collapse to the same "<missing>" bucket.
    entries = [_log_line("2026-08-24T09:00:00Z", "would-block", hook=None)]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["excluded_non_gate_by_hook"] == {"<missing>": 1}


def test_denials_by_day_reason_gate_filter_kills_the_pre_fix_no_filter_stub():
    # Adversarial: proves this is a REAL restriction, not a no-op. A stub
    # that only checks `decision` (the pre-fix behavior BLOCKER 1/2 exists to
    # fix) would report total=3 here; the correct, hook-filtered answer is 1.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "would-block", hook="pretooluse_bash"),
        _log_line("2026-08-24T09:05:00Z", "would-block", hook="check_safety_core_parity"),
        _log_line("2026-08-24T09:10:00Z", "deny", hook="mint_prod_session"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert result["total"] == 1
    assert result["excluded_non_gate_by_hook"] == {
        "check_safety_core_parity": 1,
        "mint_prod_session": 1,
    }


def test_denials_by_day_reason_excluded_non_gate_key_always_present_when_zero():
    # JSON consistency: even when nothing is excluded, the key exists (as an
    # empty dict), never omitted -- a `--json` consumer never needs a
    # `.get("excluded_non_gate_by_hook", {})` guard.
    entries = [_log_line("2026-08-24T09:00:00Z", "would-block")]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    assert "excluded_non_gate_by_hook" in result
    assert result["excluded_non_gate_by_hook"] == {}


def test_render_table_surfaces_excluded_non_gate_by_hook():
    entries = [
        _log_line("2026-08-24T09:00:00Z", "would-block", hook="pretooluse_bash"),
        _log_line("2026-08-24T09:05:00Z", "would-block", hook="sync_agent_rules"),
    ]
    result = cr.denials_by_day_reason(entries, days=None, now=_NOW)
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {
            "status": "ok",
            "ledger": "l",
            "window": "recency",
            "read_error": None,
            "skipped_unparseable": 0,
            "as_of": None,
            "command": "x",
            "days": 7,
            **result,
        },
        "churn_and_contested": {"status": "absent", "ledger": "l", "window": "recency"},
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {"status": "absent", "ledger": "l", "window": "recency"},
    }
    text = cr.render_table(report)
    assert "excluded_non_gate_by_hook={'sync_agent_rules': 1}" in text


# ===========================================================================
# Metric 3 — churn-flagged and contested-paths per day.
# ===========================================================================


def test_churn_and_contested_reads_correct_decision_shapes():
    # `contested-paths` is NEVER a top-level `decision` in the real ledger —
    # it is a `reason` field under `decision == "would-block"`. A naive
    # implementation that checks `decision == "contested-paths"` directly
    # (matching the plan's own imprecise wording) would report 0 here, not 2.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "churn-flagged", path="a.py"),
        _log_line("2026-08-24T09:05:00Z", "churn-flagged", path="a.py"),
        _log_line("2026-08-24T09:10:00Z", "churn-flagged", path="b.py"),
        _log_line("2026-08-24T10:00:00Z", "would-block", reason="contested-paths"),
        _log_line("2026-08-24T11:00:00Z", "would-block", reason="contested-paths"),
        _log_line("2026-08-24T12:00:00Z", "would-block", reason="bulk-add"),
    ]
    result = cr.churn_and_contested_by_day(entries, days=None, now=_NOW)
    assert result["churn_flagged_total"] == 3
    assert result["contested_paths_total"] == 2
    assert result["churn_flagged_by_day"] == {"2026-08-24": 3}
    assert result["contested_paths_by_day"] == {"2026-08-24": 2}
    assert result["top_churn_paths"][0] == {"path": "a.py", "count": 2}


def test_churn_and_contested_respects_days_window():
    entries = [
        _log_line("2026-08-01T09:00:00Z", "churn-flagged", path="old.py"),
        _log_line("2026-08-24T09:00:00Z", "churn-flagged", path="new.py"),
    ]
    result = cr.churn_and_contested_by_day(entries, days=7, now=_NOW)
    assert result["churn_flagged_total"] == 1
    assert result["top_churn_paths"] == [{"path": "new.py", "count": 1}]


def test_churn_and_contested_top_paths_capped_at_ten():
    # F7: 11 distinct churn-flagged paths (one occurrence each) -- top 10
    # only, never all 11. A mutant slicing `[:1]` instead of `[:10]` also
    # fails this (len 1 != 10), so this test catches both a dropped cap and
    # an over-tight one.
    entries = [
        _log_line(f"2026-08-24T09:{i:02d}:00Z", "churn-flagged", path=f"path{i}.py")
        for i in range(11)
    ]
    result = cr.churn_and_contested_by_day(entries, days=None, now=_NOW)
    assert len(result["top_churn_paths"]) == 10


def test_churn_and_contested_contested_paths_requires_would_block_decision():
    # F7: `contested-paths` as a `reason` under a NON-would-block `decision`
    # (a `deny`, or an unrelated `ok`) must NOT be counted -- only
    # `would-block`'s own contested-paths gate produces this reason for
    # real; a mutant that drops the `decision == "would-block"` guard and
    # checks the reason alone would report 3 here, not 1.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "deny", reason="contested-paths"),
        _log_line("2026-08-24T09:05:00Z", "ok", reason="contested-paths"),
        _log_line("2026-08-24T09:10:00Z", "would-block", reason="contested-paths"),
    ]
    result = cr.churn_and_contested_by_day(entries, days=None, now=_NOW)
    assert result["contested_paths_total"] == 1


def test_render_table_churn_total_and_contested_total_are_not_swappable():
    # C6: distinct values in the render so a swapped-field mutant is caught.
    entries = [
        _log_line("2026-08-24T09:00:00Z", "churn-flagged", path="a.py"),
        _log_line("2026-08-24T09:05:00Z", "churn-flagged", path="a.py"),
        _log_line("2026-08-24T09:10:00Z", "churn-flagged", path="b.py"),
        _log_line("2026-08-24T10:00:00Z", "would-block", reason="contested-paths"),
    ]
    result = cr.churn_and_contested_by_day(entries, days=None, now=_NOW)
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {
            "status": "ok",
            "ledger": "l",
            "window": "recency",
            "read_error": None,
            "skipped_unparseable": 0,
            "as_of": None,
            "command": "x",
            "days": 7,
            **result,
        },
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {"status": "absent", "ledger": "l", "window": "recency"},
    }
    text = cr.render_table(report)
    assert "churn_flagged_total=3 contested_paths_total=1" in text


def test_render_table_annotates_known_redirect_token_defect():
    # F17: the "2>" path is a known writer defect (fixed in step 4) — never
    # filtered, but annotated wherever it appears.
    entries = [_log_line(f"2026-08-24T09:0{i}:00Z", "churn-flagged", path="2>") for i in range(3)]
    result = cr.churn_and_contested_by_day(entries, days=None, now=_NOW)
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {
            "status": "ok",
            "ledger": "l",
            "window": "recency",
            "read_error": None,
            "skipped_unparseable": 0,
            "as_of": None,
            "command": "x",
            "days": 7,
            **result,
        },
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {"status": "absent", "ledger": "l", "window": "recency"},
    }
    assert result["top_churn_paths"][0]["path"] == "2>"
    text = cr.render_table(report)
    assert "2>" in text
    assert "known writer defect, step 4" in text


# ===========================================================================
# Metric 4 — code-review catch rate.
# ===========================================================================


def test_parse_last_reviewed_line_handles_space_in_repo_path():
    # A real repo root on this machine contains a space (verified 2026-08-25
    # against the live ledger); a naive `split(maxsplit=2)` misparses it.
    line = "/Users/x/Desktop/other project 18c8a0bb737da4d8da89d1afb540bf2bcea9ea82 blockers:6"
    parsed = cr.parse_last_reviewed_line(line)
    assert parsed == (
        "/Users/x/Desktop/other project",
        "18c8a0bb737da4d8da89d1afb540bf2bcea9ea82",
        "blockers:6",
    )


def test_parse_last_reviewed_line_bare_legacy_line_has_no_rest():
    parsed = cr.parse_last_reviewed_line("/repo/a aaaaaaaaaaaaaaaa1111")
    assert parsed == ("/repo/a", "aaaaaaaaaaaaaaaa1111", None)


def test_parse_catch_rate_entry_classifies_era_from_key_prefix():
    precommit = cr.parse_catch_rate_entry("/repo/a precommit:aa11bb22cc33 clean")
    legacy = cr.parse_catch_rate_entry("/repo/a aaaaaaaaaaaaaaaa1111 clean")
    assert precommit["era"] == "precommit"
    assert precommit["kind"] == "entry"
    assert legacy["era"] == "legacy-sha"
    assert legacy["kind"] == "entry"


def test_parse_catch_rate_entry_kinds_bare_legacy_and_unparseable():
    bare = cr.parse_catch_rate_entry("/repo/a precommit:aa11bb22cc33")
    garbage_outcome = cr.parse_catch_rate_entry("/repo/a precommit:aa11bb22cc33 notarealoutcome")
    whole_line_garbage = cr.parse_catch_rate_entry("this is not a valid ledger line at all")
    assert bare["kind"] == "bare_legacy"
    assert garbage_outcome["kind"] == "unparseable"
    assert whole_line_garbage["kind"] == "unparseable"
    assert whole_line_garbage["repo"] is None
    assert whole_line_garbage["era"] is None


def test_parse_catch_rate_entry_whole_line_unparseable_recovers_ts_suffix():
    # F6: a whole-line-unparseable entry (no key token at all, so `parsed is
    # None`) that still carries a recoverable `ts=` suffix must bucket to
    # that REAL day, per the module docstring's "keyed by day when a `ts=`
    # is recoverable, else `unknown-date`" -- a mutant that never scans the
    # raw `line` for `ts=` in this branch collapses every such entry into
    # `unknown-date` regardless of what the raw text actually carries.
    line = "garbled truncated line, no key token at all ts=2026-08-24T09:00:00Z trailing junk"
    entry = cr.parse_catch_rate_entry(line)
    assert entry["kind"] == "unparseable"
    assert entry["repo"] is None
    assert entry["ts"] == "2026-08-24T09:00:00Z"
    assert entry["day"] == "2026-08-24"


def test_parse_catch_rate_entry_whole_line_unparseable_no_ts_stays_none():
    # The complementary case: no `ts=` anywhere in the raw line -> day stays
    # None (bucketed as "unknown-date" downstream), never fabricated.
    entry = cr.parse_catch_rate_entry("no key token and no ts field here at all")
    assert entry["kind"] == "unparseable"
    assert entry["ts"] is None
    assert entry["day"] is None


def test_catch_rate_summary_unparseable_with_recoverable_ts_buckets_to_real_day():
    # F6 at the catch_rate_summary level: a mutant collapsing the recovered
    # ts= into "unknown-date" anyway (or never recovering it) is caught by
    # the day key here, not just by the entry-level ts/day fields above.
    lines = [
        "/repo/a precommit:aa11 clean",
        "garbled truncated line no key token ts=2026-08-24T09:00:00Z",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    assert summary["unparseable"] == 1
    assert summary["unknown_repo_by_day"] == {"2026-08-24": 1}


def test_catch_rate_summary_excludes_unknown_from_denominator():
    # Exactly the fixture shape the spawning task specifies: clean,
    # blockers:2, blockers:3, one bare line, one malformed line -> rate on 3
    # entries (2 blockers-entries / (2+1) clean+blockers), 2 excluded, split
    # 1 bare_legacy / 1 unparseable (F7).
    lines = [
        "/repo/a precommit:aaaaaaaaaaaaaaaa1111 clean",
        "/repo/a precommit:bbbbbbbbbbbbbbbb2222 blockers:2",
        "/repo/a precommit:cccccccccccccccc3333 blockers:3",
        "/repo/a precommit:dddddddddddddddd4444",  # bare: no outcome at all
        "/repo/a precommit:eeeeeeeeeeeeeeee5555 notarealoutcome",  # garbage outcome
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    assert summary["total_blockers"] == 2
    assert summary["total_clean"] == 1
    assert summary["denominator"] == 3
    assert summary["excluded_unknown"] == 2
    assert summary["bare_legacy"] == 1
    assert summary["unparseable"] == 1
    assert summary["rate"] == pytest.approx(2 / 3)


def test_catch_rate_summary_counts_entries_not_finding_counts():
    # blockers:9 is ONE entry, not nine, in the numerator.
    lines = [
        "/repo/a precommit:aaaaaaaaaaaaaaaa1111 blockers:9",
        "/repo/a precommit:bbbbbbbbbbbbbbbb2222 clean",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    assert summary["total_blockers"] == 1
    assert summary["denominator"] == 2
    assert summary["rate"] == pytest.approx(0.5)


def test_catch_rate_summary_groups_by_repo_and_day():
    lines = [
        "/repo/a precommit:aaaaaaaaaaaaaaaa1111 blockers:2 ts=2026-08-24T09:00:00Z",
        "/repo/a precommit:bbbbbbbbbbbbbbbb2222 clean ts=2026-08-24T10:00:00Z",
        "/repo/b precommit:cccccccccccccccc3333 clean ts=2026-08-24T11:00:00Z",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    bucket_a = summary["by_repo_and_day"]["/repo/a"]["2026-08-24"]
    assert bucket_a == {"clean": 1, "blockers": 1, "rate": 0.5}
    bucket_b = summary["by_repo_and_day"]["/repo/b"]["2026-08-24"]
    assert bucket_b == {"clean": 1, "blockers": 0, "rate": 0.0}


def test_catch_rate_summary_missing_ts_buckets_as_unknown_date_but_still_counts():
    lines = [
        "/repo/a precommit:aaaaaaaaaaaaaaaa1111 blockers:1",
        "/repo/a precommit:bbbbbbbbbbbbbbbb2222 clean",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    # No ts= suffix on either line -> bucketed as unknown-date, NOT dropped.
    assert summary["denominator"] == 2
    assert "unknown-date" in summary["by_repo_and_day"]["/repo/a"]


def test_catch_rate_summary_splits_precommit_and_legacy_eras_headline_is_precommit():
    # F9: eras must never blend into one rate. Precommit-era numbers are the
    # top-level headline; legacy-sha lives separately under by_era.
    lines = [
        "/repo/a precommit:aa11 clean",
        "/repo/a precommit:bb22 clean",
        "/repo/a precommit:cc33 blockers:1",
        "/repo/a 1111111111111111aaaa blockers:1",  # legacy-sha
        "/repo/a 2222222222222222bbbb blockers:1",  # legacy-sha
        "/repo/a 3333333333333333cccc clean",  # legacy-sha
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    assert summary["headline_era"] == "precommit"
    assert summary["total_blockers"] == 1
    assert summary["total_clean"] == 2
    assert summary["by_era"]["precommit"]["denominator"] == 3
    legacy = summary["by_era"]["legacy-sha"]
    assert legacy["total_blockers"] == 2
    assert legacy["total_clean"] == 1
    assert legacy["rate"] == pytest.approx(2 / 3)
    # A blended rate would be 3/6 = 0.5, matching NEITHER era's real rate —
    # asserting the headline is NOT the blend catches a blending mutant.
    assert summary["rate"] != pytest.approx(0.5)
    assert summary["all_eras_total_blockers"] == 3
    assert summary["all_eras_total_clean"] == 3
    assert summary["all_eras_rate"] == pytest.approx(0.5)


def test_catch_rate_summary_unparseable_whole_line_buckets_under_unknown_repo():
    # F7: retiring the dead `or "unknown-repo"` branch — a truly unparseable
    # line (no key token at all) is now visible under unknown_repo_by_day
    # rather than vanishing, while still excluded from the rate.
    lines = [
        "/repo/a precommit:aa11 clean",
        "not a valid ledger line whatsoever no key token here",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    assert summary["unparseable"] == 1
    assert summary["unknown_repo_by_day"] == {"unknown-date": 1}
    assert summary["denominator"] == 1


# ---------------------------------------------------------------------------
# BLOCKER 1 (trust-architect review, 2026-08-30): a `battery:`-prefixed
# mutation-battery result line has no repo_root/key shape at all, so it must
# NEVER be misclassified as `unparseable` corruption by the SECOND
# production reader of this ledger (record_review.py is the writer).
# ---------------------------------------------------------------------------


def test_parse_catch_rate_entry_classifies_battery_line_as_battery_not_corruption():
    line = rr._battery_entry("26/27", "1")
    assert line is not None
    entry = cr.parse_catch_rate_entry(line)
    assert entry["kind"] == "battery"
    assert entry["kind"] != "unparseable"
    assert entry["repo"] is None
    assert entry["era"] is None
    assert entry["ts"] is not None


def test_parse_catch_rate_entry_battery_line_recovers_bare_timestamp():
    # The battery line's timestamp is NOT `ts=`-prefixed (unlike every other
    # telemetry field this parser reads) -- it sits directly after
    # `rr.BATTERY_PREFIX`. A mutant that only ever looks for `ts=` would
    # silently leave `ts`/`day` as None here.
    line = "battery:2026-08-24T09:00:00Z mut=26/27 stale=0"
    entry = cr.parse_catch_rate_entry(line)
    assert entry["kind"] == "battery"
    assert entry["ts"] == "2026-08-24T09:00:00Z"
    assert entry["day"] == "2026-08-24"


def test_catch_rate_summary_battery_lines_never_counted_as_corruption():
    # The exact regression the reviewer proved live: before this fix, a
    # battery: line has no `_KEY_TOKEN_RE` match, so `parse_last_reviewed_line`
    # returns None and the entry fell into `unparseable` (a false corruption
    # reading against a live ledger whose real `unparseable` count is 0).
    lines = [
        "/repo/a precommit:aa11 clean",
        "/repo/a precommit:bb22 blockers:1",
        rr._battery_entry("26/27", "1"),
        rr._battery_entry("10/10", "0"),
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    # The two battery lines must NEVER show up as corruption...
    assert summary["unparseable"] == 0
    assert summary["bare_legacy"] == 0
    assert summary["excluded_unknown"] == 0
    assert summary["unknown_repo_by_day"] == {}
    # ...but ARE counted, under their own dedicated bucket.
    assert summary["battery"] == 2
    # And the real clean/blockers entries' rate is entirely unaffected by
    # the battery lines sitting in the same ledger.
    assert summary["total_blockers"] == 1
    assert summary["total_clean"] == 1
    assert summary["denominator"] == 2
    assert summary["rate"] == pytest.approx(0.5)


def test_render_table_metric4_blockers_and_clean_are_not_swappable():
    # C5: distinct blockers/clean counts in the render so a swapped-field
    # mutant is caught.
    lines = [
        "/repo/a precommit:aa11 clean",
        "/repo/a precommit:bb22 clean",
        "/repo/a precommit:cc33 clean",
        "/repo/a precommit:dd44 clean",
        "/repo/a precommit:ee55 clean",
        "/repo/a precommit:ff66 blockers:1",
        "/repo/a precommit:ab77 blockers:1",
    ]
    entries = [cr.parse_catch_rate_entry(line) for line in lines]
    summary = cr.catch_rate_summary(entries)
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {"status": "absent", "ledger": "l", "window": "recency"},
        "catch_rate": {
            "status": "ok",
            "ledger": "lr",
            "window": "lifetime",
            "read_error": None,
            "skipped_unparseable": 0,
            "as_of": None,
            "command": "x",
            **summary,
        },
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {"status": "absent", "ledger": "l", "window": "recency"},
    }
    text = cr.render_table(report)
    assert "blockers=2 clean=5" in text


# ===========================================================================
# Metrics 5 + 6 — spend dedup, summary, and reap findings.
# ===========================================================================


def test_spend_dedup_prefers_the_non_unreleased_line():
    lines = [
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=0),
        _spend_line(tool_use_id="tu1", unreleased=False, reaped=None, tokens_total=500),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert nulls == []
    assert malformed == 0
    assert len(deduped) == 1
    assert deduped[0]["tokens_total"] == 500
    assert deduped[0]["unreleased"] is False


def test_spend_dedup_real_release_first_then_placeholder_after_still_wins():
    # F3: mutant `chosen = group` (skips the `preferred`/non-unreleased
    # filter entirely, always taking the raw group's LAST line) is caught
    # ONLY when the raw append order does NOT already put the real release
    # last -- the test above has the placeholder FIRST, real release SECOND,
    # so the raw-last item happens to already be correct even under that
    # mutant. This is the mirror ordering (real release FIRST, the reaper's
    # `unreleased` placeholder appended AFTER, per the SPEND DEDUP RULE
    # docstring's actual rule): the real, non-unreleased line must still win
    # even though it is NOT the raw-last line -- `chosen = group` would
    # instead pick the trailing placeholder (tokens_total=0).
    lines = [
        _spend_line(tool_use_id="tu1", unreleased=False, reaped=None, tokens_total=500),
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=0),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert nulls == []
    assert malformed == 0
    assert len(deduped) == 1
    assert deduped[0]["tokens_total"] == 500
    assert deduped[0]["unreleased"] is False


def test_dedup_grid_non_null_group_of_1_all_unreleased():
    # Dedup dimension grid, cell 1: a single still-pending reap placeholder
    # is the ONLY record for its id -- it must still surface as one line,
    # not be dropped for having no non-unreleased sibling.
    lines = [_spend_line(tool_use_id="tu1", unreleased=True, reaped="launched")]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert len(deduped) == 1
    assert deduped[0]["unreleased"] is True
    assert nulls == []
    assert malformed == 0


def test_dedup_grid_non_null_group_of_2plus_all_unreleased_picks_last():
    # Dedup dimension grid, cell 2: C2 -- every line for an id is
    # unreleased (reaped-never-released, written more than once) -> still
    # ONE dispatch, and it is the LAST one written (chronological).
    lines = [
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=1),
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=2),
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=3),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert len(deduped) == 1
    assert deduped[0]["tokens_total"] == 3
    assert deduped[0]["unreleased"] is True


def test_dedup_grid_non_null_group_of_2plus_none_unreleased_picks_last():
    # Dedup dimension grid, cell 3: C1 -- a double-release bug (several REAL
    # releases for one id) must collapse to the LAST one written, not the
    # first and not a random one.
    lines = [
        _spend_line(tool_use_id="tu1", unreleased=False, reaped=None, tokens_total=100),
        _spend_line(tool_use_id="tu1", unreleased=False, reaped=None, tokens_total=200),
        _spend_line(tool_use_id="tu1", unreleased=False, reaped=None, tokens_total=300),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert len(deduped) == 1
    assert deduped[0]["tokens_total"] == 300


def test_dedup_grid_late_line_wins_over_unreleased_placeholder():
    # Dedup dimension grid, cell 4: `late: true` must not interfere with the
    # non-unreleased-wins preference -- a late-but-real release still beats
    # the reaper's placeholder.
    lines = [
        _spend_line(tool_use_id="tu1", unreleased=True, reaped="launched", tokens_total=0),
        _spend_line(
            tool_use_id="tu1", unreleased=False, reaped=None, late=True, tokens_total=777
        ),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert len(deduped) == 1
    assert deduped[0]["tokens_total"] == 777
    assert deduped[0]["late"] is True


def test_spend_null_tool_use_id_never_deduped_keyed_by_agent_id():
    lines = [
        _spend_line(tool_use_id=None, agent_id="agentA", reaped="stopped-unjoined"),
        _spend_line(tool_use_id=None, agent_id="agentB", reaped="stopped-unjoined"),
    ]
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert deduped == []
    assert len(nulls) == 2
    assert malformed == 0
    findings = cr.reap_findings(lines)
    assert findings["stopped_unjoined"] == 2
    assert findings["by_stage"] == {"stopped-unjoined": 2}


def test_spend_summary_sums_token_fields_separately_never_recomputes_total():
    lines = [
        _spend_line(
            tool_use_id="tu1",
            agent_type="a",
            model="m",
            tokens={"input": 1, "output": 1, "cache_read": 1, "cache_creation": 1},
            tokens_total=999,  # deliberately NOT the real sum (4) of the fields above
        ),
        _spend_line(
            tool_use_id="tu2",
            agent_type="a",
            model="m",
            tokens={"input": 2, "output": 2, "cache_read": 2, "cache_creation": 2},
            tokens_total=888,
        ),
    ]
    deduped, _nulls, _malformed = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)
    bucket = summary["by_agent"]["a"]
    # Read as written (999 + 888), never recomputed from the four fields
    # (which would sum to 8, not 1887) -- proves tokens_total isn't rederived.
    assert bucket["tokens_total"] == 999 + 888
    assert bucket["input"] == 3
    assert bucket["output"] == 3
    assert bucket["cache_read"] == 3
    assert bucket["cache_creation"] == 3
    assert bucket["dispatches"] == 2
    assert summary["malformed_fields"] == {}


def test_spend_summary_by_model_and_by_day_also_populated():
    lines = [
        _spend_line(
            tool_use_id="tu1",
            agent_type="agentX",
            model="claude-haiku",
            ts="2026-08-24T09:00:00Z",
            tokens_total=10,
        ),
        _spend_line(
            tool_use_id="tu2",
            agent_type="agentY",
            model="claude-haiku",
            ts="2026-08-24T10:00:00Z",
            tokens_total=20,
        ),
    ]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)
    assert summary["by_model"]["claude-haiku"]["tokens_total"] == 30
    assert summary["by_model"]["claude-haiku"]["dispatches"] == 2
    assert summary["by_day"]["2026-08-24"]["tokens_total"] == 30


def test_reap_findings_counts_late_and_stages_independently():
    lines = [
        _spend_line(tool_use_id="tu1", reaped="claimed"),
        _spend_line(tool_use_id="tu2", reaped="launched"),
        _spend_line(tool_use_id="tu3", reaped=None, late=True),
    ]
    findings = cr.reap_findings(lines)
    assert findings["by_stage"] == {"claimed": 1, "launched": 1}
    assert findings["late"] == 1
    assert findings["stopped_unjoined"] == 0


# ---------------------------------------------------------------------------
# null_tool_use_id_breakdown — F1 (2026-09-01 agentic-systems-architect
# audit): metric 5's unjoined population, broken out by agent_type instead
# of only a footnote count.
# ---------------------------------------------------------------------------


def test_null_tool_use_id_breakdown_groups_by_agent_type_and_sums_tokens():
    null_lines = [
        _spend_line(tool_use_id=None, agent_type="implement", tokens_total=100),
        _spend_line(tool_use_id=None, agent_type="implement", tokens_total=50),
        _spend_line(tool_use_id=None, agent_type="code-reviewer", tokens_total=25),
    ]
    rows = cr.null_tool_use_id_breakdown(null_lines, grand_total_tokens=1000)
    assert rows == [
        {"agent_type": "implement", "tokens": 150, "pct_of_total_tokens": 15.0},
        {"agent_type": "code-reviewer", "tokens": 25, "pct_of_total_tokens": 2.5},
    ]


def test_null_tool_use_id_breakdown_missing_agent_type_buckets_as_unknown():
    null_lines = [_spend_line(tool_use_id=None, agent_type=None, tokens_total=10)]
    rows = cr.null_tool_use_id_breakdown(null_lines, grand_total_tokens=10)
    assert rows == [{"agent_type": "unknown", "tokens": 10, "pct_of_total_tokens": 100.0}]


def test_null_tool_use_id_breakdown_malformed_tokens_total_contributes_zero():
    null_lines = [_spend_line(tool_use_id=None, agent_type="x", tokens_total="not-a-number")]
    rows = cr.null_tool_use_id_breakdown(null_lines, grand_total_tokens=100)
    assert rows == [{"agent_type": "x", "tokens": 0, "pct_of_total_tokens": 0.0}]


def test_null_tool_use_id_breakdown_empty_input_is_empty_list():
    assert cr.null_tool_use_id_breakdown([], grand_total_tokens=0) == []


def test_null_tool_use_id_breakdown_zero_grand_total_never_divides_by_zero():
    null_lines = [_spend_line(tool_use_id=None, agent_type="x", tokens_total=5)]
    rows = cr.null_tool_use_id_breakdown(null_lines, grand_total_tokens=0)
    assert rows == [{"agent_type": "x", "tokens": 5, "pct_of_total_tokens": 0.0}]


def test_null_tool_use_id_breakdown_sorted_by_tokens_desc_then_name_asc():
    null_lines = [
        _spend_line(tool_use_id=None, agent_type="b", tokens_total=10),
        _spend_line(tool_use_id=None, agent_type="a", tokens_total=10),
        _spend_line(tool_use_id=None, agent_type="c", tokens_total=99),
    ]
    rows = cr.null_tool_use_id_breakdown(null_lines, grand_total_tokens=1000)
    assert [r["agent_type"] for r in rows] == ["c", "a", "b"]


def test_build_report_spend_includes_null_tool_use_id_breakdown_grand_total_across_both_populations(
    tmp_path,
):
    """RED without the fix: build_report's spend section carries no
    null_tool_use_id_breakdown key at all. GREEN: it exists, and its
    percentages are of the FULL population (deduped + unjoined), not just
    the unjoined subtotal."""
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    lr_path = tmp_path / "last_reviewed"
    lr_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(
        spend_path,
        [
            _spend_line(tool_use_id="tu1", agent_type="implement", tokens_total=100),
            _spend_line(tool_use_id=None, agent_id="aX", agent_type="general-purpose", tokens_total=900),
        ],
    )
    report = cr.build_report(
        days=None,
        now=datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc),
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(lr_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    breakdown = report["spend"]["null_tool_use_id_breakdown"]
    assert breakdown == [{"agent_type": "general-purpose", "tokens": 900, "pct_of_total_tokens": 90.0}]


def test_render_table_prints_the_unjoined_breakdown_table(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    lr_path = tmp_path / "last_reviewed"
    lr_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(
        spend_path,
        [_spend_line(tool_use_id=None, agent_id="aX", agent_type="general-purpose", tokens_total=900)],
    )
    report = cr.build_report(
        days=None,
        now=datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc),
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(lr_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    table = cr.render_table(report)
    assert "unjoined (stopped-unjoined reap, null tool_use_id) by agent:" in table
    assert "general-purpose" in table


def test_build_report_days_filters_the_spend_ledger(tmp_path):
    # C4: --days must actually filter metric 5/6's input.
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(
        spend_path,
        [
            _spend_line(tool_use_id="old", ts="2026-08-01T09:00:00Z"),
            _spend_line(tool_use_id="new", ts="2026-08-24T09:00:00Z"),
        ],
    )
    report_7 = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report_7["spend"]["dispatches"] == 1
    report_all = cr.build_report(
        days=60,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report_all["spend"]["dispatches"] == 2


def test_build_report_spend_as_of_is_unfiltered_not_deduped(tmp_path):
    # F4: `as_of` is a DATA-CURRENCY signal, computed from the ledger's full
    # unfiltered `spend_lines` -- never from the windowed/deduped subset that
    # feeds the metrics. Fixture: tu1's real release is written at
    # 2026-08-24T10:00, then the reaper's `unreleased` placeholder is
    # appended LATER at 2026-08-25T15:00 (the placeholder LOSES the dedup --
    # `dedup_spend_lines` prefers the non-unreleased line -- so it never
    # appears in `deduped`). Hand-derived: the raw ledger's true max ts is
    # the placeholder's 2026-08-25T15:00; `deduped`'s own max ts is only the
    # real release's 2026-08-24T10:00. A mutant swapping `_max_ts(spend_lines)`
    # for `_max_ts(deduped)` would report the STALER 08-24 value instead; a
    # mutant swapping `_max_ts` itself for a function that always returns
    # None would report `None` instead of either.
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(
        spend_path,
        [
            _spend_line(
                tool_use_id="tu1", unreleased=False, reaped=None, ts="2026-08-24T10:00:00Z"
            ),
            _spend_line(
                tool_use_id="tu1", unreleased=True, reaped="launched", ts="2026-08-25T15:00:00Z"
            ),
        ],
    )
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["spend"]["dispatches"] == 1  # the placeholder lost the dedup
    assert report["spend"]["as_of"] == "2026-08-25T15:00:00Z"  # but as_of still sees it


# ===========================================================================
# Metric 7 -- review-round convergence (round=/warm=/prev= chains).
# ===========================================================================


def _lr_line(
    key: str,
    outcome: str = "clean",
    *,
    ts: str = "2026-08-25T10:00:00Z",
    round_: int | None = None,
    prev: str | None = None,
    warm: bool = False,
    repo: str = "/repo/a",
) -> str:
    """Build one `last_reviewed` line carrying whatever telemetry fields
    metric 7 cares about, mirroring the real shape `_entry_suffix` writes
    (outcome token, then ts=, then round=/prev=/warm= in that append-only
    order)."""
    parts = [repo, key, outcome, f"ts={ts}"]
    if round_ is not None:
        parts.append(f"round={round_}")
    if prev is not None:
        parts.append(f"prev={prev}")
    if warm:
        parts.append("warm=1")
    return " ".join(parts)


def _refusal_line(ts: str, prev: str = "precommit:aaaa", prior_warm: int = 2) -> dict:
    return {
        "ts": ts,
        "hook": "record_review",
        "decision": "warm-cap-exceeded",
        "enforce": True,
        "target": "/repo/a",
        "prev": prev,
        "prior_warm": prior_warm,
    }


def _chain_entry(
    repo: str, key: str, round_: int, *, prev: str | None = None, warm: bool = False, ts: str = "t"
) -> dict:
    """A chain_entries-shaped dict (repo, key, prev, round, warm, ts) — the
    shape `parse_round_chain_entry` returns, used directly by
    `round_chain_metrics` unit tests that don't need real ledger-line
    parsing."""
    return {"repo": repo, "key": key, "prev": prev, "round": round_, "warm": warm, "ts": ts}


def test_parse_round_chain_entry_ignores_lines_with_no_round_field():
    # The vast majority of the ledger has no round= at all -- must not be
    # counted as a degenerate one-round chain.
    line = _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z")
    assert cr.parse_round_chain_entry(line, days=None, now=_NOW) is None


def test_parse_round_chain_entry_extracts_repo_key_round_prev_warm():
    # Blocker 1: `repo` must be threaded through, not discarded -- chain
    # identity is (repo, key), never key alone.
    line = _lr_line(
        "precommit:bb22",
        ts="2026-08-25T10:00:00Z",
        round_=2,
        prev="precommit:aa11",
        warm=True,
        repo="/repo/a",
    )
    parsed = cr.parse_round_chain_entry(line, days=None, now=_NOW)
    assert parsed == {
        "repo": "/repo/a",
        "key": "precommit:bb22",
        "prev": "precommit:aa11",
        "round": 2,
        "warm": True,
        "ts": "2026-08-25T10:00:00Z",
    }


def test_parse_round_chain_entry_root_has_no_prev():
    # A chain's first recorded round may carry round=N with no prev= at all.
    line = _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1)
    parsed = cr.parse_round_chain_entry(line, days=None, now=_NOW)
    assert parsed["prev"] is None
    assert parsed["round"] == 1


def test_parse_round_chain_entry_battery_line_is_not_a_chain_member():
    line = f"{rr.BATTERY_PREFIX}2026-08-25T10:00:00Z mut=3/4 stale=1"
    assert cr.parse_round_chain_entry(line, days=None, now=_NOW) is None


def test_parse_round_chain_entry_malformed_round_value_excluded_not_crashed():
    line = _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z") + " round=notanumber"
    assert cr.parse_round_chain_entry(line, days=None, now=_NOW) is None


def test_parse_round_chain_entry_excluded_outside_days_window():
    line = _lr_line("precommit:aa11", ts="2026-08-01T10:00:00Z", round_=1)
    assert cr.parse_round_chain_entry(line, days=7, now=_NOW) is None
    assert cr.parse_round_chain_entry(line, days=60, now=_NOW) is not None


def test_parse_round_chain_entry_all_days_ignores_the_days_filter():
    # Blocker 4's linkage pass: all_days=True must still require a
    # parseable ts= but must NEVER apply the --days window.
    line = _lr_line("precommit:aa11", ts="2026-08-01T10:00:00Z", round_=1)
    assert cr.parse_round_chain_entry(line, days=7, now=_NOW, all_days=True) is not None


def test_round_chain_metrics_single_chain_max_round_and_histogram():
    # A 3-round chain: root (round=1, no prev), then round=2 -> prev root's
    # key, then round=3 -> prev round=2's key. Max round for this chain is 3.
    entries = [
        _chain_entry("/repo/a", "k1", 1),
        _chain_entry("/repo/a", "k2", 2, prev="k1"),
        _chain_entry("/repo/a", "k3", 3, prev="k2"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 1
    assert metrics["rounds_histogram"] == {"3": 1}


def test_round_chain_metrics_two_independent_chains_separate_histogram_buckets():
    entries = [
        _chain_entry("/repo/a", "a1", 1),
        _chain_entry("/repo/a", "a2", 2, prev="a1"),
        _chain_entry("/repo/a", "b1", 1),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 2
    # chain a maxes at round 2, chain b maxes at round 1 -- one chain each.
    assert metrics["rounds_histogram"] == {"1": 1, "2": 1}


def test_round_chain_metrics_same_key_different_repos_are_two_chains():
    # BLOCKER 1: the live ledger already has precommit:ae7f0e437e8750b9
    # recorded under three different repo roots. A key-only index would
    # collapse two unrelated repos' chains into one and fabricate a max
    # round from entries that never belonged to the same boundary.
    entries = [
        _chain_entry("/repo/a", "precommit:aaaa", 1),
        _chain_entry("/repo/b", "precommit:aaaa", 5),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 2
    assert metrics["rounds_histogram"] == {"1": 1, "5": 1}  # never {"5": 2} or a merged max


def test_round_chain_metrics_prev_never_crosses_repos():
    # A prev= citing the same bare key in a DIFFERENT repo must not link --
    # chain walk is repo-scoped exactly like record_review's own ledger
    # lookup (repo_root-scoped) is.
    entries = [
        _chain_entry("/repo/a", "precommit:aaaa", 1),
        _chain_entry("/repo/b", "precommit:bbbb", 2, prev="precommit:aaaa"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 2
    assert metrics["rounds_histogram"] == {"1": 1, "2": 1}


def test_round_chain_metrics_sha_prev_resolves_against_bare_sha_key():
    # BLOCKER 2: a plain (non---pre-commit) recording's `decide()` writes a
    # BARE sha key (no prefix), but --prev is always recorded with the
    # sha: prefix. Without rr._ledger_lookup_key's translation at the
    # lookup boundary, this prev= would never resolve (REGRESSION 2,
    # reintroduced) -- both entries would wrongly read as separate chains.
    entries = [
        _chain_entry("/repo/a", "abc123abc123abc1", 1),  # bare sha, no prefix
        _chain_entry("/repo/a", "def456def456def4", 2, prev="sha:abc123abc123abc1"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 1
    assert metrics["rounds_histogram"] == {"2": 1}


def test_round_chain_metrics_dangling_prev_is_chain_end_not_a_crash():
    # prev= cites a key not present in this input -- treated as chain end,
    # never an infinite loop or KeyError. Finding 8: the dangling key is a
    # well-formed precommit:<hex> (exactly what a real predecessor whose
    # entry fell outside the window would look like), never a fabricated
    # non-ledger-shaped string.
    entries = [
        _chain_entry("/repo/a", "precommit:bb22", 2, prev="precommit:aa11"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 1
    assert metrics["rounds_histogram"] == {"2": 1}


def test_round_chain_metrics_self_referencing_prev_never_crashes():
    # Found live against the real ledger while re-verifying blockers 1/2/4
    # (two real entries there carry prev= equal to their OWN key -- the
    # exact self-reference AA-0049's record_review.py write-time guard
    # exists to refuse, apparently predating that guard). A bare `next()`
    # search for "the member with no in-chain predecessor" raises
    # StopIteration here, since the one member's own prev= resolves to
    # itself and IS present in the chain -- never a real root by that
    # naive definition. Must degrade to a stable single-member chain, never
    # crash the whole report.
    entries = [
        _chain_entry("/repo/a", "precommit:selfref", 3, prev="precommit:selfref"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 1
    assert metrics["rounds_histogram"] == {"3": 1}
    assert metrics["capped_then_cold_chains"] == 0


def test_review_round_convergence_self_referencing_prev_never_crashes_end_to_end():
    # A real hex-shaped key (matching _KEY_TOKEN_RE) -- unlike the pure
    # round_chain_metrics unit test above, this goes through the actual
    # last_reviewed line parser, so the key must be ledger-shaped.
    lines = [
        _lr_line(
            "precommit:1234567890abcdef",
            ts="2026-08-25T10:00:00Z",
            round_=4,
            prev="precommit:1234567890abcdef",
        )
    ]
    result = cr.review_round_convergence(lines, [], days=None, now=_NOW)
    assert result["chains_total"] == 1
    assert result["rounds_histogram"] == {"4": 1}


def test_round_chain_metrics_two_cycle_terminates_and_degrades_to_two_chains():
    # Reviewer's live probe: A.prev=B, B.prev=A -- a genuine 2-entry cycle
    # (neither entry is reachable as "the" root by the naive definition).
    # Must terminate (never hang) and degrade to two SEPARATE single-member
    # chains -- each entry becomes its own root because `_root_of`'s `seen`
    # guard breaks the cycle at whichever entry it started walking from,
    # never merging the two into one fabricated chain.
    entries = [
        _chain_entry("/repo/a", "precommit:aaaa1111", 1, prev="precommit:bbbb2222"),
        _chain_entry("/repo/a", "precommit:bbbb2222", 2, prev="precommit:aaaa1111"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["chains_total"] == 2
    assert metrics["rounds_histogram"] == {"1": 1, "2": 1}
    assert metrics["capped_then_cold_chains"] == 0
    assert set(metrics["chains_by_root"].keys()) == {
        ("/repo/a", "precommit:aaaa1111"),
        ("/repo/a", "precommit:bbbb2222"),
    }


def test_round_chain_metrics_warm_histogram_counts_warm_rows_per_chain():
    entries = [
        _chain_entry("/repo/a", "k1", 1),
        _chain_entry("/repo/a", "k2", 2, prev="k1", warm=True),
        _chain_entry("/repo/a", "k3", 3, prev="k2", warm=True),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["warm_histogram"] == {"2": 1}  # one chain, 2 warm rows
    assert metrics["warm_rows_total"] == 2


def test_round_chain_metrics_capped_then_cold_chain_is_counted():
    # Two consecutive warm rounds (2, cap) followed by a cold round 3 --
    # exactly the shape record_review.py's refusal branch exists to force.
    entries = [
        _chain_entry("/repo/a", "k1", 1, warm=True),
        _chain_entry("/repo/a", "k2", 2, prev="k1", warm=True),
        _chain_entry("/repo/a", "k3", 3, prev="k2"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["capped_then_cold_chains"] == 1


def test_round_chain_metrics_below_cap_never_counts_as_capped_then_cold():
    # Only ONE warm round, then cold -- never hit the 2-warm cap at all.
    entries = [
        _chain_entry("/repo/a", "k1", 1, warm=True),
        _chain_entry("/repo/a", "k2", 2, prev="k1"),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["capped_then_cold_chains"] == 0


def test_round_chain_metrics_still_warm_mid_chain_not_counted_as_capped_then_cold():
    # A chain that hit 2 consecutive warm rounds but has NOT (yet) been
    # followed by an observed cold round in this window must not be counted
    # -- there is no cold follow-up to observe.
    entries = [
        _chain_entry("/repo/a", "k1", 1, warm=True),
        _chain_entry("/repo/a", "k2", 2, prev="k1", warm=True),
    ]
    metrics = cr.round_chain_metrics(entries)
    assert metrics["capped_then_cold_chains"] == 0


def test_round_chain_metrics_capped_then_cold_is_order_independent_of_round_ties():
    # Non-blocking finding 3: capped_then_cold must be computed from TRUE
    # chain order (root-to-tip via prev= links), never a `sorted(by round=)`
    # -- three same-round entries must not let ledger-line order (a stable
    # sort's tie-break) decide the verdict. Real chain order here (via
    # prev=) is k1(warm) -> k2(warm) -> k3(cold), same round=1 on all three
    # (a degenerate but legal ledger shape to stress the tie-break).
    forward = [
        _chain_entry("/repo/a", "k1", 1, warm=True),
        _chain_entry("/repo/a", "k2", 1, prev="k1", warm=True),
        _chain_entry("/repo/a", "k3", 1, prev="k2", warm=False),
    ]
    reversed_input = list(reversed(forward))
    metrics_forward = cr.round_chain_metrics(forward)
    metrics_reversed = cr.round_chain_metrics(reversed_input)
    assert metrics_forward["capped_then_cold_chains"] == 1
    assert metrics_reversed["capped_then_cold_chains"] == 1
    assert metrics_forward["capped_then_cold_chains"] == metrics_reversed["capped_then_cold_chains"]


def test_round_chain_metrics_in_window_keys_excludes_chain_not_touching_window():
    # A chain entirely outside in_window_keys must not be counted at all --
    # in_window_keys decides which CHAINS are reported, never which entries
    # are used to resolve linkage.
    entries = [
        _chain_entry("/repo/a", "k1", 1),
        _chain_entry("/repo/a", "k2", 2, prev="k1"),
    ]
    metrics = cr.round_chain_metrics(entries, in_window_keys=set())
    assert metrics["chains_total"] == 0
    assert metrics["rounds_histogram"] == {}


def test_round_chain_metrics_in_window_keys_out_of_window_predecessor_still_completes_walk():
    # BLOCKER 4: an out-of-window predecessor must still be used to resolve
    # the chain link (so a real "hit the cap, then cold" is found), but the
    # chain is only reported because ITS OTHER member (k2) is in-window --
    # k1 alone is never counted as its own separate chain.
    entries = [
        _chain_entry("/repo/a", "k1", 1, warm=True),  # out-of-window predecessor
        _chain_entry("/repo/a", "k2", 2, prev="k1", warm=True),
        _chain_entry("/repo/a", "k3", 3, prev="k2"),  # in-window cold follow-up
    ]
    in_window = {("/repo/a", "k3")}
    metrics = cr.round_chain_metrics(entries, in_window_keys=in_window)
    assert metrics["chains_total"] == 1  # one chain, not two
    assert metrics["capped_then_cold_chains"] == 1  # the cap-then-cold IS visible
    assert metrics["warm_rows_total"] == 0  # k1/k2's warm rows are out-of-window
    # rounds_histogram uses FULL chain membership (the boundary really did
    # reach round 3) -- deliberately asymmetric with warm_rows_total, which
    # is windowed. warm_histogram must stay CONSISTENT with warm_rows_total
    # (both windowed) rather than the (larger) full-membership warm count.
    assert metrics["rounds_histogram"] == {"3": 1}
    assert metrics["warm_histogram"] == {"0": 1}


def test_warm_cap_refusals_counts_only_the_refusal_decision():
    entries = [
        _refusal_line("2026-08-25T09:00:00Z"),
        _refusal_line("2026-08-25T09:05:00Z"),
        _log_line("2026-08-25T09:10:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-25T09:15:00Z", "clean"),
    ]
    assert cr.warm_cap_refusals(entries, days=None, now=_NOW) == 2


def test_warm_cap_refusals_windowed_by_days():
    entries = [
        _refusal_line("2026-08-01T09:00:00Z"),
        _refusal_line("2026-08-25T09:00:00Z"),
    ]
    assert cr.warm_cap_refusals(entries, days=7, now=_NOW) == 1
    assert cr.warm_cap_refusals(entries, days=60, now=_NOW) == 2


def test_warm_cap_refusals_not_restricted_to_gate_hooks_allowlist():
    # Deliberately NOT filtered by cr._GATE_HOOKS (metric 2's own concern) --
    # warm-cap-exceeded is its own unambiguous decision value from exactly
    # one hook, so a hook value outside _GATE_HOOKS must still count.
    entries = [_refusal_line("2026-08-25T09:00:00Z")]
    assert entries[0]["hook"] not in cr._GATE_HOOKS
    assert cr.warm_cap_refusals(entries, days=None, now=_NOW) == 1


def test_review_round_convergence_small_n_marker_below_threshold():
    lines = [_lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1, warm=True)]
    result = cr.review_round_convergence(lines, [], days=None, now=_NOW)
    assert result["warm_rows_total"] == 1
    assert result["small_n"] is True
    assert result["small_n_threshold"] == cr._SMALL_N_THRESHOLD


def test_review_round_convergence_small_n_false_at_or_above_threshold():
    lines = [
        _lr_line(f"precommit:{i:04x}", ts="2026-08-25T10:00:00Z", round_=1, warm=True)
        for i in range(cr._SMALL_N_THRESHOLD)
    ]
    result = cr.review_round_convergence(lines, [], days=None, now=_NOW)
    assert result["warm_rows_total"] == cr._SMALL_N_THRESHOLD
    assert result["small_n"] is False


def test_review_round_convergence_full_payload_shape():
    lines = [
        _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1),
        _lr_line("precommit:bb22", ts="2026-08-25T11:00:00Z", round_=2, prev="precommit:aa11"),
    ]
    log_entries = [_refusal_line("2026-08-25T09:00:00Z")]
    result = cr.review_round_convergence(lines, log_entries, days=None, now=_NOW)
    assert result["chains_total"] == 1
    assert result["rounds_histogram"] == {"2": 1}
    assert result["warm_cap_refusals"] == 1
    assert "chains_by_root" not in result  # internal detail, never surfaced


def test_review_round_convergence_two_repos_sharing_a_key_are_two_chains():
    # BLOCKER 1, at the integration level per the review's own reproduction:
    # two repos sharing the SAME key ("aaaa") must report chains_total == 2,
    # never a merged chains_total == 1 with a fabricated max round.
    lines = [
        _lr_line("precommit:aaaa", ts="2026-08-25T10:00:00Z", round_=1, repo="/repo/one"),
        _lr_line("precommit:aaaa", ts="2026-08-25T10:00:00Z", round_=5, repo="/repo/two"),
    ]
    result = cr.review_round_convergence(lines, [], days=None, now=_NOW)
    assert result["chains_total"] == 2
    assert result["rounds_histogram"] == {"1": 1, "5": 1}


def test_review_round_convergence_sha_prefixed_prev_links_to_bare_sha_key():
    # BLOCKER 2, at the integration level: a plain (non---pre-commit)
    # recording's real ledger key is a BARE sha with no prefix, but its
    # citer's prev= is always recorded sha:-prefixed. Without translating at
    # the lookup boundary this never resolves -- REGRESSION 2, reintroduced.
    lines = [
        _lr_line("abc123abc123abc1", ts="2026-08-25T10:00:00Z", round_=1),
        _lr_line(
            "def456def456def4",
            ts="2026-08-25T11:00:00Z",
            round_=2,
            prev="sha:abc123abc123abc1",
        ),
    ]
    result = cr.review_round_convergence(lines, [], days=None, now=_NOW)
    assert result["chains_total"] == 1
    assert result["rounds_histogram"] == {"2": 1}


def test_review_round_convergence_window_never_false_negatives_capped_then_cold():
    # BLOCKER 4, at the integration level: the predecessor (round 1, warm)
    # sits OUTSIDE the --days=1 window; the cap-completing round 2 (warm)
    # and the cold round 3 follow-up are both inside it. A hard per-entry
    # window would drop round 1 entirely and never see 2 consecutive warm
    # rounds -- a false negative on capped_then_cold_chains.
    lines = [
        _lr_line(
            "precommit:aa11", ts="2026-08-01T10:00:00Z", round_=1, warm=True
        ),  # out of a 1-day window
        _lr_line(
            "precommit:bb22",
            ts="2026-08-25T10:00:00Z",
            round_=2,
            prev="precommit:aa11",
            warm=True,
        ),
        _lr_line(
            "precommit:cc33", ts="2026-08-25T11:00:00Z", round_=3, prev="precommit:bb22"
        ),
    ]
    result = cr.review_round_convergence(lines, [], days=1, now=_NOW)
    assert result["capped_then_cold_chains"] == 1
    assert result["chains_total"] == 1  # the round-1-only chain is never double-counted


def test_build_report_review_round_convergence_ok_status_and_windowed(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text(
        _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1)
        + "\n"
        + _lr_line("precommit:cc33", ts="2026-08-01T10:00:00Z", round_=1)
        + "\n"
    )
    log_path = tmp_path / "log.jsonl"
    _write_jsonl(
        log_path,
        [
            _refusal_line("2026-08-25T09:00:00Z"),
            _refusal_line("2026-08-01T09:00:00Z"),
        ],
    )
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report_7 = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    m7 = report_7["review_round_convergence"]
    assert m7["status"] == "ok"
    assert m7["window"] == "recency"
    assert m7["days"] == 7
    assert m7["chains_total"] == 1  # k_old excluded by the 7-day window
    assert m7["warm_cap_refusals"] == 1  # the 08-01 refusal excluded too

    report_all = cr.build_report(
        days=60,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    m7_all = report_all["review_round_convergence"]
    assert m7_all["chains_total"] == 2
    assert m7_all["warm_cap_refusals"] == 2


def test_build_report_review_round_convergence_absent_when_last_reviewed_absent(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"  # never created -> ABSENT
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["review_round_convergence"]["status"] == "absent"
    assert "chains_total" not in report["review_round_convergence"]
    # Finding 5: `ledger` must be the SAME combined "a + b" string the "ok"
    # branch uses, never a single-ledger name -- `missing_ledger` separately
    # names which one was actually absent.
    assert report["review_round_convergence"]["ledger"] == f"{last_reviewed_path} + {log_path}"
    assert report["review_round_convergence"]["missing_ledger"] == str(last_reviewed_path)


def test_build_report_review_round_convergence_absent_when_enforcement_log_absent(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"  # never created -> ABSENT
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["review_round_convergence"]["status"] == "absent"
    assert report["review_round_convergence"]["ledger"] == f"{last_reviewed_path} + {log_path}"
    assert report["review_round_convergence"]["missing_ledger"] == str(log_path)


def test_build_report_review_round_convergence_ok_has_null_missing_ledger(tmp_path):
    # Shape consistency: the "ok" branch carries the SAME `missing_ledger`
    # key (always None there) so a caller never has to special-case which
    # status a section has before reading that key.
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["review_round_convergence"]["status"] == "ok"
    assert report["review_round_convergence"]["missing_ledger"] is None


def test_render_table_metric7_histogram_and_small_n_marker(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text(
        _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1, warm=True) + "\n"
    )
    log_path = tmp_path / "log.jsonl"
    _write_jsonl(log_path, [_refusal_line("2026-08-25T09:00:00Z")])
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    text = cr.render_table(report)
    assert "7. Review-round convergence" in text
    assert "round=1   chains=1" in text
    assert "n=1, not yet interpretable" in text
    assert "warm-cap refusals" in text
    assert "1" in text.split("warm-cap refusals")[1].splitlines()[0]


def test_render_table_metric7_absent_status_rendered():
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {"status": "absent", "ledger": "l", "window": "recency"},
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {
            "status": "absent",
            "ledger": "l + log",
            "missing_ledger": "l",
            "window": "recency",
        },
        "fanout_session_high": {"status": "absent", "ledger": "l", "window": "recency"},
    }
    text = cr.render_table(report)
    assert "l + log: ABSENT" in text
    assert "missing: l" in text


def test_json_round_trip_includes_review_round_convergence(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text(
        _lr_line("precommit:aa11", ts="2026-08-25T10:00:00Z", round_=1) + "\n"
    )
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
        argv=["--days", "7", "--json"],
    )
    round_tripped = json.loads(json.dumps(report))
    assert round_tripped["review_round_convergence"]["status"] == "ok"
    assert round_tripped["review_round_convergence"]["chains_total"] == 1


# ===========================================================================
# B2 -- five crash fixtures on type-corrupt spend lines, no exception.
# ===========================================================================


def test_crash_fixture_1_tokens_field_is_not_a_dict():
    lines = [_spend_line(tool_use_id="tu1", tokens="not-a-dict")]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)  # must not raise AttributeError
    assert summary["by_agent"]["engine-architect"]["input"] == 0
    assert summary["malformed_fields"]["tokens"] == 1


def test_crash_fixture_2_tokens_input_is_a_string():
    lines = [_spend_line(tool_use_id="tu1", tokens={"input": "5"})]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)  # must not raise TypeError (int += str)
    assert summary["by_agent"]["engine-architect"]["input"] == 0
    assert summary["malformed_fields"]["input"] == 1


def test_crash_fixture_3_tokens_output_is_a_string():
    lines = [_spend_line(tool_use_id="tu1", tokens={"output": "5"})]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)  # must not raise TypeError (int += str)
    assert summary["by_agent"]["engine-architect"]["output"] == 0
    assert summary["malformed_fields"]["output"] == 1


def test_crash_fixture_4_tokens_cache_read_is_a_string():
    lines = [_spend_line(tool_use_id="tu1", tokens={"cache_read": "5"})]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)  # must not raise TypeError (int += str)
    assert summary["by_agent"]["engine-architect"]["cache_read"] == 0
    assert summary["malformed_fields"]["cache_read"] == 1


def test_crash_fixture_5_tool_use_id_is_unhashable():
    lines = [_spend_line(tool_use_id=["not", "hashable"])]
    # must not raise TypeError: unhashable type: 'list'
    deduped, nulls, malformed = cr.dedup_spend_lines(lines)
    assert deduped == []
    assert nulls == []
    assert malformed == 1


def test_silent_loss_fix_float_tokens_total_is_coerced_not_dropped():
    # B2's "related silent loss": a float tokens_total used to become 0.
    lines = [_spend_line(tool_use_id="tu1", tokens_total=42.0)]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)
    assert summary["by_agent"]["engine-architect"]["tokens_total"] == 42
    assert summary["malformed_fields"] == {}


def test_silent_loss_fix_bool_tokens_total_flagged_not_silently_one():
    # B2's "related silent loss": a bool tokens_total used to silently
    # become 1 (True is an int subtype). Must now be flagged malformed and
    # contribute 0, never a silent 1.
    lines = [_spend_line(tool_use_id="tu1", tokens_total=True)]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)
    assert summary["by_agent"]["engine-architect"]["tokens_total"] == 0
    assert summary["malformed_fields"]["tokens_total"] == 1


def test_silent_loss_fix_non_integral_float_flagged_malformed():
    lines = [_spend_line(tool_use_id="tu1", tokens_total=3.5)]
    deduped, _, _ = cr.dedup_spend_lines(lines)
    summary = cr.spend_summary(deduped)
    assert summary["by_agent"]["engine-architect"]["tokens_total"] == 0
    assert summary["malformed_fields"]["tokens_total"] == 1


def test_as_int_accepts_plain_int_and_integral_float_rejects_bool_and_str():
    assert cr._as_int(5) == (5, False)
    assert cr._as_int(5.0) == (5, False)
    assert cr._as_int(None) == (0, False)
    assert cr._as_int(True) == (0, True)
    assert cr._as_int(False) == (0, True)
    assert cr._as_int(3.5) == (0, True)
    assert cr._as_int("5") == (0, True)
    assert cr._as_int([1]) == (0, True)


# ===========================================================================
# B1 -- unreadable / mid-read-failed ledgers must never report "ok" zeros.
# ===========================================================================


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_read_jsonl_chmod0_ledger_is_degraded_not_ok(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_text('{"decision": "would-block"}\n')
    os.chmod(path, 0o000)
    try:
        result = cr.read_jsonl(str(path))
    finally:
        os.chmod(path, 0o644)
    assert result is not None
    rows, errors = result
    assert rows == []
    assert errors["read_error"] is not None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_read_lines_chmod0_ledger_is_degraded_not_ok(tmp_path):
    path = tmp_path / "last_reviewed"
    path.write_text("/repo/a precommit:aa11 clean\n")
    os.chmod(path, 0o000)
    try:
        result = cr.read_lines(str(path))
    finally:
        os.chmod(path, 0o644)
    assert result is not None
    lines, errors = result
    assert lines == []
    assert errors["read_error"] is not None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_build_report_chmod0_ledger_status_is_never_ok(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text('{"ts": "2026-08-24T09:00:00Z", "plan": "p", "blockers": 1}\n')
    os.chmod(plan_path, 0o000)
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")
    try:
        report = cr.build_report(
            days=7,
            now=_NOW,
            plan_reviews_path=str(plan_path),
            last_reviewed_path=str(last_reviewed_path),
            enforcement_log_path=str(log_path),
            spend_path=str(spend_path),
        )
    finally:
        os.chmod(plan_path, 0o644)
    assert report["plan_review_rounds"]["status"] == "degraded"
    assert report["plan_review_rounds"]["status"] != "ok"
    assert report["plan_review_rounds"]["read_error"] is not None
    rendered = cr.render_table(report)
    assert "DEGRADED" in rendered


def test_read_jsonl_counts_skipped_unparseable_lines_without_aborting(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_text('{"decision": "would-block"}\nnot json at all\n["a", "list", "not", "dict"]\n')
    result = cr.read_jsonl(str(path))
    rows, errors = result
    assert len(rows) == 1
    assert errors["skipped_unparseable"] == 2
    assert errors["read_error"] is None


def test_read_jsonl_absent_file_is_none():
    assert cr.read_jsonl("/definitely/not/a/real/path/xyz.jsonl") is None


def test_read_lines_absent_file_is_none():
    assert cr.read_lines("/definitely/not/a/real/path/xyz") is None


# ===========================================================================
# B3 -- lifetime metrics must never appear to be under the days window.
# ===========================================================================


def test_render_table_header_scopes_days_window_to_recency_metrics(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(missing_dir / "pr.jsonl"),
        last_reviewed_path=str(missing_dir / "lr"),
        enforcement_log_path=str(missing_dir / "log.jsonl"),
        spend_path=str(missing_dir / "spend.jsonl"),
    )
    text = cr.render_table(report)
    assert "days window: 7 (metrics 2,3,5,6,7 only)" in text


def test_render_table_lifetime_sections_state_window_is_lifetime(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    _write_jsonl(plan_path, [_plan_entry("2026-08-20T10:00:00Z", "/r", "p1", 0)])
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("/repo/a precommit:aa11 clean\n")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["plan_review_rounds"]["window"] == "lifetime"
    assert report["catch_rate"]["window"] == "lifetime"
    assert report["denials_by_reason"]["window"] == "recency"
    assert report["spend"]["window"] == "recency"
    text = cr.render_table(report)
    assert text.count("window: LIFETIME (--days does not apply)") == 2


# ===========================================================================
# Ledger absence -> ABSENT, never zeros. Plus --days recency semantics.
# ===========================================================================


def test_within_days_fails_open_on_unparseable_and_none_days():
    # _NOW is 2026-08-25T16:00:00Z; a 1-day window's cutoff is 08-24T16:00.
    assert cr.within_days("2026-08-25T10:00:00Z", 1, _NOW) is True
    assert cr.within_days("2026-08-17T12:00:00Z", 1, _NOW) is False
    assert cr.within_days(None, 1, _NOW) is True
    assert cr.within_days("garbage", 1, _NOW) is True
    assert cr.within_days("2026-01-01T00:00:00Z", None, _NOW) is True


def test_build_report_absent_spend_reports_absent_status_not_zeros(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text("")
    spend_path = tmp_path / "spend.jsonl"  # never created -> ABSENT

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["spend"]["status"] == "absent"
    assert report["spend"]["ledger"] == str(spend_path)
    assert "dispatches" not in report["spend"]
    assert report["reap_findings"]["status"] == "absent"

    rendered = cr.render_table(report)
    assert f"{spend_path}: ABSENT" in rendered


def test_build_report_all_ledgers_absent_still_has_every_metric_key(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(missing_dir / "pr.jsonl"),
        last_reviewed_path=str(missing_dir / "lr"),
        enforcement_log_path=str(missing_dir / "log.jsonl"),
        spend_path=str(missing_dir / "spend.jsonl"),
    )
    for key in (
        "plan_review_rounds",
        "denials_by_reason",
        "churn_and_contested",
        "catch_rate",
        "spend",
        "reap_findings",
    ):
        assert report[key]["status"] == "absent"


def test_absent_sections_carry_the_full_provenance_key_set(tmp_path):
    # JSON consistency: an "absent" section must carry the SAME provenance
    # keys an "ok" section would (`command`, `as_of`, `read_error`,
    # `skipped_unparseable`, and `days` for recency-window sections) -- a
    # caller doing `section["command"]` (or any of the others) must never
    # KeyError just because the ledger happened to be missing.
    missing_dir = tmp_path / "nonexistent"
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(missing_dir / "pr.jsonl"),
        last_reviewed_path=str(missing_dir / "lr"),
        enforcement_log_path=str(missing_dir / "log.jsonl"),
        spend_path=str(missing_dir / "spend.jsonl"),
    )
    for key in (
        "plan_review_rounds",
        "denials_by_reason",
        "churn_and_contested",
        "catch_rate",
        "spend",
        "reap_findings",
    ):
        section = report[key]
        assert section["status"] == "absent"
        assert section["command"] == report["command"]  # never KeyErrors
        assert section["as_of"] is None
        assert section["read_error"] is None
        assert section["skipped_unparseable"] == 0
    for key in ("denials_by_reason", "churn_and_contested", "spend", "reap_findings"):
        assert report[key]["window"] == "recency"
        assert report[key]["days"] == 7
    for key in ("plan_review_rounds", "catch_rate"):
        assert report[key]["window"] == "lifetime"
        assert "days" not in report[key]  # matches the "ok"-shape omission


# ===========================================================================
# --json round trip.
# ===========================================================================


def test_json_round_trip_contains_every_metric_key(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    _write_jsonl(plan_path, [_plan_entry("2026-08-20T10:00:00Z", "/r", "p1", 0)])
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("/repo/a precommit:aa11 clean ts=2026-08-24T09:00:00Z\n")
    log_path = tmp_path / "log.jsonl"
    _write_jsonl(
        log_path,
        [
            _log_line("2026-08-24T09:00:00Z", "would-block", reason="bulk-add"),
            _log_line("2026-08-24T09:05:00Z", "churn-flagged", path="a.py"),
        ],
    )
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(spend_path, [_spend_line()])

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
        argv=["--days", "7", "--json"],
    )
    round_tripped = json.loads(json.dumps(report))
    for key in (
        "plan_review_rounds",
        "denials_by_reason",
        "churn_and_contested",
        "catch_rate",
        "spend",
        "reap_findings",
    ):
        assert key in round_tripped
    assert round_tripped["plan_review_rounds"]["status"] == "ok"
    assert round_tripped["spend"]["status"] == "ok"
    assert round_tripped["command"] == "python3 ~/.claude/hooks/churn_report.py --days 7 --json"


# ===========================================================================
# render_table smoke + FINDING line.
# ===========================================================================


def test_render_table_emits_finding_line_for_stopped_unjoined(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(
        spend_path,
        [
            _spend_line(
                tool_use_id=None,
                agent_id="a1",
                reaped="stopped-unjoined",
                tokens=None,
                tokens_total=0,
                duration_ms=None,
            )
        ],
    )
    missing_dir = tmp_path / "nonexistent"
    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(missing_dir / "pr.jsonl"),
        last_reviewed_path=str(missing_dir / "lr"),
        enforcement_log_path=str(missing_dir / "log.jsonl"),
        spend_path=str(spend_path),
    )
    text = cr.render_table(report)
    assert "FINDING" in text
    assert "stopped-unjoined" in text


# ===========================================================================
# CLI arg parsing + main() end-to-end (module ledger globals monkeypatched).
# ===========================================================================


def test_parse_args_defaults_and_json_flag():
    days, as_json = cr.parse_args([])
    assert days == cr.DEFAULT_DAYS
    assert as_json is False


def test_parse_args_days_flag_and_equals_form():
    days, as_json = cr.parse_args(["--days", "14", "--json"])
    assert days == 14
    assert as_json is True
    days2, _ = cr.parse_args(["--days=3"])
    assert days2 == 3


def test_parse_args_rejects_bad_input():
    with pytest.raises(cr.ArgError):
        cr.parse_args(["--days", "notanumber"])
    with pytest.raises(cr.ArgError):
        cr.parse_args(["--days", "0"])
    with pytest.raises(cr.ArgError):
        cr.parse_args(["--unknown-flag"])


def test_main_help_flag_prints_usage_and_lifetime_note(capsys):
    rc = cr.main(["--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "--days N" in out
    assert "LIFETIME" in out
    rc2 = cr.main(["-h"])
    assert rc2 == 0


def test_main_end_to_end_json_and_table(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cr, "LEDGER_PLAN_REVIEWS", str(tmp_path / "pr.jsonl"))
    monkeypatch.setattr(cr, "LEDGER_LAST_REVIEWED", str(tmp_path / "lr"))
    monkeypatch.setattr(cr, "LEDGER_ENFORCEMENT_LOG", str(tmp_path / "log.jsonl"))
    monkeypatch.setattr(cr, "LEDGER_SPEND", str(tmp_path / "spend.jsonl"))

    rc = cr.main(["--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plan_review_rounds"]["status"] == "absent"
    assert payload["plan_review_rounds"]["ledger"] == str(tmp_path / "pr.jsonl")

    rc2 = cr.main([])
    assert rc2 == 0
    text = capsys.readouterr().out
    assert "churn report" in text
    assert str(tmp_path / "spend.jsonl") in text


def test_main_bad_argument_returns_2(capsys):
    rc = cr.main(["--bogus"])
    assert rc == 2
    assert "churn_report:" in capsys.readouterr().err


# ===========================================================================
# Sanity: this module reuses record_review's outcome parser, never its own.
# ===========================================================================


def test_parse_outcome_token_is_reused_verbatim():
    assert rr.parse_outcome_token("clean") == (rr.OUTCOME_CLEAN, 0)
    assert rr.parse_outcome_token("blockers:3") == (rr.OUTCOME_BLOCKERS, 3)


# ===========================================================================
# Metric 8 — fan-out session-high (WS2.2,
# plan_lane_control_adoption_master_2026_09_20.md §2.2). Reads the same
# enforcement-log ledger as metrics 2/3/7, filtered to
# decision == "fanout-session-high" (agent_budget.note_fanout_dispatch's
# own PURE OBSERVER log line — see that module's WS2.2 section). Never a
# gate; report-only.
# ===========================================================================


def _fanout_line(ts, session, count, top_agent_types=None, **extra):
    return _log_line(
        ts,
        "fanout-session-high",
        hook="agent_budget",
        session=session,
        count=count,
        top_agent_types=top_agent_types
        if top_agent_types is not None
        else [{"agent_type": "explore", "count": count}],
        **extra,
    )


def test_fanout_session_high_summary_counts_only_its_own_decision_value():
    entries = [
        _fanout_line("2026-08-25T09:00:00Z", "sessA", 40),
        _log_line("2026-08-25T09:05:00Z", "would-block", reason="bulk-add"),
        _log_line("2026-08-25T09:10:00Z", "clean"),
        _log_line("2026-08-25T09:15:00Z", "task_gate"),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["sessions_over_threshold_total"] == 1
    assert result["sessions_over_threshold"][0]["session"] == "sessA"
    assert result["sessions_over_threshold"][0]["count"] == 40


def test_fanout_session_high_summary_not_restricted_to_gate_hooks_allowlist():
    # Mirrors warm_cap_refusals's own rule: fanout-session-high is its own
    # unambiguous decision value from exactly one hook (agent_budget), so a
    # hook value outside metric 2's _GATE_HOOKS allowlist must still count.
    entries = [_fanout_line("2026-08-25T09:00:00Z", "sessA", 40)]
    assert entries[0]["hook"] not in cr._GATE_HOOKS
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["sessions_over_threshold_total"] == 1


def test_fanout_session_high_summary_windowed_by_days():
    entries = [
        _fanout_line("2026-08-01T09:00:00Z", "sessOld", 40),
        _fanout_line("2026-08-25T09:00:00Z", "sessNew", 40),
    ]
    result_narrow = cr.fanout_session_high_summary(entries, days=7, now=_NOW)
    assert result_narrow["sessions_over_threshold_total"] == 1
    assert result_narrow["sessions_over_threshold"][0]["session"] == "sessNew"
    result_wide = cr.fanout_session_high_summary(entries, days=60, now=_NOW)
    assert result_wide["sessions_over_threshold_total"] == 2


def test_fanout_session_high_summary_by_day_grouping():
    entries = [
        _fanout_line("2026-08-24T09:00:00Z", "sessA", 40),
        _fanout_line("2026-08-24T10:00:00Z", "sessB", 42),
        _fanout_line("2026-08-25T09:00:00Z", "sessC", 40),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["sessions_over_threshold_by_day"] == {
        "2026-08-24": 2,
        "2026-08-25": 1,
    }


def test_fanout_session_high_summary_sorted_worst_first():
    entries = [
        _fanout_line("2026-08-25T09:00:00Z", "sessLow", 40),
        _fanout_line("2026-08-25T09:05:00Z", "sessHigh", 90),
        _fanout_line("2026-08-25T09:10:00Z", "sessMid", 55),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    sessions = [r["session"] for r in result["sessions_over_threshold"]]
    assert sessions == ["sessHigh", "sessMid", "sessLow"]  # count desc


def test_fanout_session_high_summary_malformed_rows_excluded_and_counted():
    entries = [
        _fanout_line("2026-08-25T09:00:00Z", "sessOK", 40),
        _log_line("2026-08-25T09:05:00Z", "fanout-session-high", hook="agent_budget", count=40),  # no session
        _log_line(
            "2026-08-25T09:10:00Z",
            "fanout-session-high",
            hook="agent_budget",
            session="sessBadCount",
            count="forty",  # not a real int
        ),
        _log_line(
            "2026-08-25T09:15:00Z",
            "fanout-session-high",
            hook="agent_budget",
            session="sessBoolCount",
            count=True,  # bool is never a real count, even though isinstance(True, int)
        ),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["sessions_over_threshold_total"] == 1
    assert result["malformed"] == 3


def test_fanout_session_high_summary_top_agent_types_carried_through_verbatim():
    entries = [
        _fanout_line(
            "2026-08-25T09:00:00Z",
            "sessA",
            40,
            top_agent_types=[
                {"agent_type": "implement", "count": 20},
                {"agent_type": "explore", "count": 15},
                {"agent_type": "git-ops", "count": 5},
            ],
        )
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["sessions_over_threshold"][0]["top_agent_types"] == [
        {"agent_type": "implement", "count": 20},
        {"agent_type": "explore", "count": 15},
        {"agent_type": "git-ops", "count": 5},
    ]


def test_fanout_session_high_summary_small_n_below_floor_no_percentiles():
    entries = [_fanout_line("2026-08-25T09:00:00Z", "sessOnly", 40)]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["small_n"] is True
    assert result["count_p50"] is None
    assert result["count_p90"] is None
    assert result["count_max"] == 40  # max is still meaningful for n=1


def test_fanout_session_high_summary_percentiles_at_or_above_floor():
    entries = [
        _fanout_line("2026-08-25T09:00:00Z", "sessA", 40),
        _fanout_line("2026-08-25T09:05:00Z", "sessB", 60),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    assert result["small_n"] is False
    assert result["count_p50"] == 50  # median of [40, 60]
    assert result["count_max"] == 60
    # count_p90 was the ONLY reported field left unasserted, and it was the
    # one that was wrong -- the same shape as the helper-level defect, one
    # level up. Proved by mutation: hardwiring "count_p90": 999999 in the
    # summary left 158 tests green. Asserting the helper alone does not
    # protect the field the report actually prints.
    assert result["count_p90"] == 58.0  # inclusive p90 of [40, 60]
    assert result["count_p90"] <= result["count_max"]


def test_fanout_session_high_summary_empty_input():
    result = cr.fanout_session_high_summary([], days=None, now=_NOW)
    assert result["sessions_over_threshold_total"] == 0
    assert result["sessions_over_threshold"] == []
    assert result["sessions_over_threshold_by_day"] == {}
    assert result["malformed"] == 0
    assert result["small_n"] is True
    assert result["count_p50"] is None
    assert result["count_p90"] is None
    assert result["count_max"] is None


def test_fanout_session_high_absent_when_enforcement_log_missing(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"  # never created -> absent
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["fanout_session_high"]["status"] == "absent"


def test_fanout_session_high_ok_through_build_report(tmp_path):
    plan_path = tmp_path / "plan_reviews.jsonl"
    plan_path.write_text("")
    last_reviewed_path = tmp_path / "last_reviewed"
    last_reviewed_path.write_text("")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text(json.dumps(_fanout_line("2026-08-25T09:00:00Z", "sessA", 40)) + "\n")
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text("")

    report = cr.build_report(
        days=7,
        now=_NOW,
        plan_reviews_path=str(plan_path),
        last_reviewed_path=str(last_reviewed_path),
        enforcement_log_path=str(log_path),
        spend_path=str(spend_path),
    )
    assert report["fanout_session_high"]["status"] == "ok"
    assert report["fanout_session_high"]["sessions_over_threshold_total"] == 1


def test_render_table_metric8_shows_session_over_threshold_and_percentiles():
    entries = [
        _fanout_line("2026-08-25T09:00:00Z", "sessA", 40),
        _fanout_line("2026-08-25T09:05:00Z", "sessB", 60),
    ]
    result = cr.fanout_session_high_summary(entries, days=None, now=_NOW)
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {"status": "absent", "ledger": "l", "window": "recency"},
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {
            "status": "ok",
            "ledger": "l",
            "window": "recency",
            "read_error": None,
            "skipped_unparseable": 0,
            "as_of": "2026-08-25T09:05:00Z",
            "command": "x",
            "days": 7,
            **result,
        },
    }
    text = cr.render_table(report)
    assert "sessions_over_threshold=2" in text
    assert "p50=50.0" in text
    assert "sessA" in text
    assert "sessB" in text


def test_render_table_metric8_absent_status_rendered():
    # Distinguishing marker: a UNIQUE ledger name for metric 8 alone
    # ("only-metric-8-ledger"), never shared with any other section's
    # "absent" fixture in this test — a render_table that never reaches
    # metric 8 at all (the pre-fix shape) cannot produce this string, so
    # this assertion is not satisfiable by accident the way a shared
    # "l: ABSENT" string would be.
    report = {
        "generated_at": "2026-08-25T16:00:00Z",
        "days": 7,
        "command": "x",
        "plan_review_rounds": {"status": "absent", "ledger": "p", "window": "lifetime"},
        "denials_by_reason": {"status": "absent", "ledger": "l", "window": "recency"},
        "churn_and_contested": {"status": "absent", "ledger": "l", "window": "recency"},
        "catch_rate": {"status": "absent", "ledger": "l", "window": "lifetime"},
        "spend": {"status": "absent", "ledger": "s", "window": "recency"},
        "reap_findings": {"status": "absent", "ledger": "s", "window": "recency"},
        "review_round_convergence": {"status": "absent", "ledger": "l", "window": "recency"},
        "fanout_session_high": {
            "status": "absent",
            "ledger": "only-metric-8-ledger",
            "window": "recency",
        },
    }
    text = cr.render_table(report)
    assert "8. Fan-out session-high" in text
    assert "only-metric-8-ledger: ABSENT" in text


def test_percentile_90_never_exceeds_the_observed_max():
    """p90 must be BOUNDED by the data. `statistics.quantiles`' default
    `method="exclusive"` EXTRAPOLATES: measured [42,55,91] -> 112.6 against
    a max of 91, [10,20] -> 27.0 against 20. A report claiming a 90th
    percentile no session ever reached is misleading, and small n is the
    COMMON case here (the metric's own floor admits n=2).

    This value was the one left untested while every other field was
    asserted -- which is why the wrong one was the one that shipped.
    """
    for values in ([42, 55, 91], [10, 20], [40, 41, 42, 43, 100], [1, 1, 1, 99]):
        p90 = cr._percentile_90(values)
        assert p90 is not None
        assert p90 <= max(values), (values, p90, max(values))
        assert p90 >= min(values), (values, p90, min(values))


def test_percentile_90_still_returns_none_below_two_values():
    """PAIRED RECOVERY: the small-n guard is unchanged by the method fix."""
    assert cr._percentile_90([]) is None
    assert cr._percentile_90([7]) is None
