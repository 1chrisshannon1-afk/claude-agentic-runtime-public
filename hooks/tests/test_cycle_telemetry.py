"""Hermetic tests for hooks/cycle_telemetry.py.

Every test passes explicit path overrides (cycles_dir / ledger_path /
pricing_path) into tmp_path, so nothing here ever touches the operator's real
~/.claude/telemetry or ~/.claude/.agent_budget/spend.jsonl. No network.

Falsifiability: see test_falsifiability_metrics_are_not_vacuous and
test_falsifiability_validation_catches_real_defects for the RED-before-GREEN
evidence this module's own docstrings/report demand — each stub-replaces the
real implementation with a version that trivially "passes" (returns a
constant / accepts anything) and shows the specific assertion that would have
let a broken implementation through, then confirms the shipped code does not.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable

import cycle_telemetry as ct
import jsonschema
import pytest

# ---------------------------------------------------------------------------
# Minimal valid record builder.
# ---------------------------------------------------------------------------


def _minimal_record(**overrides: object) -> dict:
    record = {
        "schema_version": 1,
        "system": "test-loop",
        "repo": "SomeRepo",
        "cycle_id": "cycle-001",
        "started_at": "2026-08-27T14:00:00Z",
        "ended_at": "2026-08-27T15:00:00Z",
        "dispatches": [],
        "calibration": {
            "plant_id": None,
            "planted_in": None,
            "slot": None,
            "caught_by": [],
            "missed_by": [],
        },
        "findings": [],
        "cost": {"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "no dispatches"},
        "notes": [],
    }
    record.update(overrides)
    return record


def _dispatch(**overrides: object) -> dict:
    d = {
        "agent_type": "finder",
        "label": "pass-1",
        "model": "claude-sonnet-5",
        "tokens_total": 1000,
        "cost_usd": 0.01,
        "tool_calls": 3,
        "duration_ms": 5000,
        "batch_size": 1,
        "batch_position": 1,
    }
    d.update(overrides)
    return d


def _finding(**overrides: object) -> dict:
    f = {
        "finding_id": "f1",
        "raised_by": ["finder"],
        "claim_symptom": "something looks wrong",
        "claim_cause": "because of X",
        "consolidator_decision": "ACCEPT",
        "verifier_verdict": "CONFIRMED",
        "verifier_cause_upheld": True,
        "already_tracked_as": None,
        "fights_ruling": None,
        "fix_status": "fixed",
    }
    f.update(overrides)
    return f


# ---------------------------------------------------------------------------
# validate_cycle — structural rules.
# ---------------------------------------------------------------------------


def test_minimal_record_is_valid() -> None:
    assert ct.validate_cycle(_minimal_record()) == []


def test_non_dict_record_is_invalid() -> None:
    assert ct.validate_cycle([1, 2, 3]) == ["cycle record must be a JSON object"]
    assert ct.validate_cycle(None) != []


def test_rejects_unknown_top_level_key() -> None:
    record = _minimal_record()
    record["totally_made_up_field"] = 1
    errs = ct.validate_cycle(record)
    assert any("unknown top-level key: totally_made_up_field" in e for e in errs)


def test_rejects_missing_required_top_level_key() -> None:
    record = _minimal_record()
    del record["cost"]
    errs = ct.validate_cycle(record)
    assert any("missing required top-level key: cost" in e for e in errs)


def test_rejects_wrong_schema_version() -> None:
    record = _minimal_record(schema_version=3)
    errs = ct.validate_cycle(record)
    assert any("schema_version must be one of" in e for e in errs)


def test_schema_version_1_and_2_are_both_valid() -> None:
    # v2 is purely additive over v1 -- both declared versions validate on
    # their own, with zero v2 fields present.
    assert ct.validate_cycle(_minimal_record(schema_version=1)) == []
    assert ct.validate_cycle(_minimal_record(schema_version=2)) == []


@pytest.mark.parametrize("bad_system", ["", "has spaces", "has/slash", "-leads-with-hyphen", 5, None])
def test_rejects_bad_system_slug(bad_system: object) -> None:
    record = _minimal_record(system=bad_system)
    errs = ct.validate_cycle(record)
    assert any("system" in e for e in errs)


def test_rejects_ended_before_started() -> None:
    record = _minimal_record(started_at="2026-08-27T15:00:00Z", ended_at="2026-08-27T14:00:00Z")
    errs = ct.validate_cycle(record)
    assert any("ended_at is before started_at" in e for e in errs)


def test_ended_at_null_means_in_progress_and_is_valid() -> None:
    record = _minimal_record(ended_at=None)
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# validate_cycle — dispatches.
# ---------------------------------------------------------------------------


def test_dispatch_rejects_unknown_key() -> None:
    d = _dispatch(unexpected_extra_field="x")
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("dispatches[0]" in e and "unknown key: unexpected_extra_field" in e for e in errs)


def test_dispatch_rejects_missing_key() -> None:
    d = _dispatch()
    del d["agent_type"]
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("missing required key: agent_type" in e for e in errs)


def test_dispatch_batch_position_must_not_exceed_batch_size() -> None:
    d = _dispatch(batch_size=2, batch_position=5)
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("batch_position must be <= batch_size" in e for e in errs)


def test_dispatch_negative_tokens_total_rejected() -> None:
    d = _dispatch(tokens_total=-5)
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("tokens_total must be >= 0" in e for e in errs)


def test_dispatch_model_can_be_null() -> None:
    d = _dispatch(model=None)
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_identity_fields_are_optional_and_accept_strings() -> None:
    """v2 -- BLOCKER 2's fix: a dispatch may optionally echo the ledger's own
    identity fields so resolve_cost() can match by identity, not just
    inference."""
    d = _dispatch(tool_use_id="toolu_abc", agent_id="a123", session="sess-1")
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_identity_fields_reject_non_string() -> None:
    d = _dispatch(session=12345)
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("session must be a string or null" in e for e in errs)


def test_dispatch_identity_fields_reject_empty_string() -> None:
    """BLOCKER 2's second door: an empty string must never validate as if it
    were 'no identity declared' -- only isinstance(v, str) was checked
    before, letting a present-but-blank identity silently pass field-type
    validation and then discard a sibling dispatch's real identity."""
    for field in ("tool_use_id", "agent_id", "session"):
        d = _dispatch(**{field: ""})
        record = _minimal_record(dispatches=[d])
        errs = ct.validate_cycle(record)
        assert any(f"{field} must be a non-empty string" in e for e in errs), errs


def test_dispatch_item_key_is_optional_and_accepts_a_string() -> None:
    """item_key (renamed from wave_item, THE ISSUE WHEEL rollout commit 8c --
    originally added for the retired Standing Delivery Wheel, 'sdw' system;
    the field itself is general-purpose, not SDW-specific) is an OPTIONAL
    free string join key back to a work item -- see schema.json's own
    description on this field. Mirrors tool_use_id/agent_id/session exactly."""
    d = _dispatch(item_key="4901")
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_item_key_can_be_a_fallback_row_token() -> None:
    """THE ISSUE WHEEL's own ITEM TOKEN convention for a fallback-mode row
    with no real issue number ('row-<index>') must also validate here."""
    d = _dispatch(item_key="row-3")
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_item_key_rejects_non_string() -> None:
    d = _dispatch(item_key=4901)
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("item_key must be a string or null" in e for e in errs)


def test_dispatch_item_key_rejects_empty_string() -> None:
    """Same 'empty string is a data defect' rule as tool_use_id/agent_id/
    session -- an empty item_key must never silently pass as 'not declared'."""
    d = _dispatch(item_key="")
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("item_key must be a non-empty string" in e for e in errs), errs


def test_dispatch_without_item_key_still_validates() -> None:
    """Purely additive: a dispatch with none of the identity fields (the
    overwhelming majority of pre-existing records) must be completely
    unaffected by this field's addition."""
    d = _dispatch()
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_scenarios_is_optional_and_accepts_a_string_list() -> None:
    """AA-0106: a real dispatch that reviewed many scenarios in one Task call
    records them here, never as N synthetic dispatches[] entries."""
    d = _dispatch(scenarios=["addition_half_bath_new_01", "bath_remodel_03"])
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_scenarios_rejects_non_list() -> None:
    d = _dispatch(scenarios="not-a-list")
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("scenarios must be a list of non-empty strings" in e for e in errs)


def test_dispatch_scenarios_rejects_empty_list() -> None:
    """Same 'declared-but-empty is a data defect' rule as item_key/identity
    fields -- an empty scenarios list must never silently pass as 'no
    scenarios', it must be omitted instead."""
    d = _dispatch(scenarios=[])
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("scenarios must be a non-empty list when present" in e for e in errs), errs


def test_dispatch_scenarios_rejects_non_string_item() -> None:
    d = _dispatch(scenarios=["ok", 5, ""])
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("scenarios[1] must be a non-empty string" in e for e in errs)
    assert any("scenarios[2] must be a non-empty string" in e for e in errs)


def test_dispatch_without_scenarios_still_validates() -> None:
    """Purely additive: a dispatch with no scenarios key (every pre-existing
    record) must be completely unaffected by this field's addition."""
    d = _dispatch()
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# validate_cycle — calibration.
# ---------------------------------------------------------------------------


def test_calibration_rejects_caught_by_when_no_plant() -> None:
    record = _minimal_record(
        calibration={
            "plant_id": None,
            "planted_in": None,
            "slot": None,
            "caught_by": [1],
            "missed_by": [],
        }
    )
    errs = ct.validate_cycle(record)
    assert any("caught_by/missed_by must be empty when plant_id is null" in e for e in errs)


def test_calibration_allows_plant_with_catches() -> None:
    record = _minimal_record(
        calibration={
            "plant_id": "p1",
            "planted_in": "finder",
            "slot": 1,
            "caught_by": [1],
            "missed_by": [2],
        }
    )
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# validate_cycle — findings (enum enforcement).
# ---------------------------------------------------------------------------


def test_finding_rejects_bad_consolidator_decision_enum() -> None:
    f = _finding(consolidator_decision="MAYBE")
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("consolidator_decision must be one of" in e for e in errs)


def test_finding_rejects_bad_verifier_verdict_enum() -> None:
    f = _finding(verifier_verdict="SORT_OF")
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("verifier_verdict must be one of" in e for e in errs)


def test_finding_verifier_verdict_null_is_allowed() -> None:
    f = _finding(verifier_verdict=None, verifier_cause_upheld=None)
    record = _minimal_record(findings=[f])
    assert ct.validate_cycle(record) == []


def test_finding_rejects_empty_raised_by() -> None:
    f = _finding(raised_by=[])
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("raised_by must be a non-empty list" in e for e in errs)


def test_finding_rejects_non_bool_cause_upheld() -> None:
    f = _finding(verifier_cause_upheld="yes")
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("verifier_cause_upheld must be a boolean or null" in e for e in errs)


# ---------------------------------------------------------------------------
# validate_cycle — cost block.
# ---------------------------------------------------------------------------


def test_cost_rejects_bad_source_enum() -> None:
    record = _minimal_record(cost={"source": "made_up", "total_tokens": None, "total_usd": None})
    errs = ct.validate_cycle(record)
    assert any("source must be one of" in e for e in errs)


def test_cost_unavailable_requires_null_totals() -> None:
    record = _minimal_record(
        cost={"source": "unavailable", "total_tokens": 5, "total_usd": None, "reason": "x"}
    )
    errs = ct.validate_cycle(record)
    assert any("source is 'unavailable' but total_tokens/total_usd is not null" in e for e in errs)


def test_cost_unavailable_requires_reason() -> None:
    record = _minimal_record(cost={"source": "unavailable", "total_tokens": None, "total_usd": None})
    errs = ct.validate_cycle(record)
    assert any("no 'reason' was given" in e for e in errs)


def test_cost_spend_ledger_null_total_usd_requires_reason() -> None:
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": None}
    )
    errs = ct.validate_cycle(record)
    assert any("total_usd is null under source spend_ledger but no 'reason'" in e for e in errs)


def test_cost_spend_ledger_null_total_tokens_requires_reason() -> None:
    """FALSIFY target -- BLOCKER 1: total_tokens must be held to the exact
    same 'null requires a reason' discipline as total_usd already is."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": None, "total_usd": 1.5}
    )
    errs = ct.validate_cycle(record)
    assert any("total_tokens is null under source spend_ledger but no 'reason'" in e for e in errs)


def test_cost_rejects_unknown_key() -> None:
    record = _minimal_record(
        cost={"source": "reported", "total_tokens": 1, "total_usd": 1.0, "bogus": True}
    )
    errs = ct.validate_cycle(record)
    assert any("unknown key: bogus" in e for e in errs)


def test_cost_reported_is_a_valid_source() -> None:
    record = _minimal_record(cost={"source": "reported", "total_tokens": 10, "total_usd": 1.5})
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# v2 additive migration — a v1 record (none of the new arrays/keys) must
# keep validating forever. FALSIFY target: a schema_version bump or a change
# to REQUIRED_TOP_KEYS that accidentally demands a v2 key would break this.
# ---------------------------------------------------------------------------


def test_v1_record_with_zero_v2_fields_still_validates() -> None:
    record = _minimal_record(
        dispatches=[_dispatch()],
        findings=[_finding()],
        cost={"source": "reported", "total_tokens": 10, "total_usd": 1.5},
    )
    assert "runs" not in record and "reviews" not in record
    assert ct.validate_cycle(record) == []


def test_real_shipped_leaked_and_blind_records_still_validate() -> None:
    """The two real v1-shaped cycle records this schema was built against
    must keep validating under the v2 validator, unmodified."""
    for name in ("B0-2026-08-28-leaked", "B0-2026-08-28-blind"):
        path = os.path.join(ct.CYCLES_DIR, "estimate-loop", f"{name}.json")
        if not os.path.exists(path):
            pytest.skip(f"real cycle record not present in this $HOME: {path}")
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        assert ct.validate_cycle(record) == [], f"{name} failed: {ct.validate_cycle(record)}"


# ---------------------------------------------------------------------------
# v2 — dispatches[].tokens_reported / .tokens_source.
# ---------------------------------------------------------------------------


def test_dispatch_tokens_reported_requires_tokens_source() -> None:
    """FALSIFY target: a number recorded with no provenance label is exactly
    the bug this field exists to prevent (v2 gap 9)."""
    d = _dispatch(tokens_total=None, tokens_reported=4_284_888)
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("tokens_reported is set but tokens_source is missing" in e for e in errs)


def test_dispatch_tokens_reported_with_source_is_valid() -> None:
    d = _dispatch(tokens_total=None, tokens_reported=4_284_888, tokens_source="harness_reported")
    record = _minimal_record(dispatches=[d])
    assert ct.validate_cycle(record) == []


def test_dispatch_tokens_source_rejects_bad_enum() -> None:
    d = _dispatch(tokens_reported=100, tokens_source="made_up_source")
    record = _minimal_record(dispatches=[d])
    errs = ct.validate_cycle(record)
    assert any("tokens_source must be one of" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — findings[].found_at_stage / .issue_refs.
# ---------------------------------------------------------------------------


def test_finding_found_at_stage_accepts_consolidation_origin() -> None:
    """The v2 gap this exists to close: a finding that a consolidator
    surfaced but that never reached a verifier must be representable."""
    f = _finding(
        verifier_verdict=None,
        verifier_cause_upheld=None,
        found_at_stage="consolidation",
        issue_refs=["#4535"],
    )
    record = _minimal_record(findings=[f])
    assert ct.validate_cycle(record) == []


def test_finding_found_at_stage_rejects_bad_enum() -> None:
    f = _finding(found_at_stage="made_up_stage")
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("found_at_stage must be one of" in e for e in errs)


def test_finding_issue_refs_must_be_non_empty_strings() -> None:
    f = _finding(issue_refs=["", "  "])
    record = _minimal_record(findings=[f])
    errs = ct.validate_cycle(record)
    assert any("issue_refs must be a list of non-empty strings" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — runs[].
# ---------------------------------------------------------------------------


def _run(**overrides: object) -> dict:
    r = {
        "run_id": "finder-pass",
        "purpose": "trade-agent finder pass",
        "agent_types": ["trade-tile"],
        "model": "claude-sonnet-5",
        "started_at": "2026-08-28T04:45:45Z",
        "ended_at": "2026-08-28T05:08:29Z",
        "dispatch_count": 27,
        "outcome": "68 raw problems raised",
    }
    r.update(overrides)
    return r


def test_run_minimal_is_valid() -> None:
    record = _minimal_record(runs=[_run()])
    assert ct.validate_cycle(record) == []


def test_run_rejects_empty_agent_types() -> None:
    record = _minimal_record(runs=[_run(agent_types=[])])
    errs = ct.validate_cycle(record)
    assert any("agent_types must be a non-empty list" in e for e in errs)


def test_run_a_run_that_found_nothing_still_records_a_non_empty_outcome() -> None:
    """FALSIFY target: a run recorded with no findings must still carry a
    real outcome string -- an empty outcome would silently look like the run
    never happened, which is the exact gap runs[] exists to close."""
    record = _minimal_record(runs=[_run(outcome="")])
    errs = ct.validate_cycle(record)
    assert any("outcome must be a non-empty string" in e for e in errs)


def test_run_ended_before_started_rejected() -> None:
    record = _minimal_record(
        runs=[_run(started_at="2026-08-28T05:00:00Z", ended_at="2026-08-28T04:00:00Z")]
    )
    errs = ct.validate_cycle(record)
    assert any("ended_at is before started_at" in e for e in errs)


def test_run_unknown_key_rejected() -> None:
    record = _minimal_record(runs=[_run(bogus="x")])
    errs = ct.validate_cycle(record)
    assert any("runs[0]: unknown key: bogus" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — reviews[] (the operator asked for this by name; v1 had none at all).
# ---------------------------------------------------------------------------


def _review(**overrides: object) -> dict:
    r = {
        "review_id": "rev-1",
        "reviewer": "code-reviewer",
        "model": "claude-opus-4-8",
        "target": "B0 fix round",
        "related_findings": ["b0-f03"],
        "round": 1,
        "blocker_count": 6,
        "findings": [
            {"description": "an unformatted file", "severity": "minor", "fixed": None},
        ],
        "upheld_decisions": ["b0-f05 PAINT REFUTED verdict upheld"],
        "overturned_decisions": [],
        "outcome": "blockers",
        "reviewed_at": None,
    }
    r.update(overrides)
    return r


def test_review_minimal_is_valid() -> None:
    record = _minimal_record(reviews=[_review()])
    assert ct.validate_cycle(record) == []


def test_review_blocker_count_must_match_outcome_clean() -> None:
    """FALSIFY target: an outcome of 'clean' with a nonzero blocker_count
    would let a review self-report success while its own data says otherwise
    -- the exact failure §10 calls out ('never self-record --clean with no
    review of any kind' is the human-process version of this same rule)."""
    record = _minimal_record(reviews=[_review(outcome="clean", blocker_count=6)])
    errs = ct.validate_cycle(record)
    assert any("outcome is 'clean' but blocker_count is not 0" in e for e in errs)


def test_review_blockers_outcome_requires_at_least_one_blocker() -> None:
    record = _minimal_record(reviews=[_review(outcome="blockers", blocker_count=0)])
    errs = ct.validate_cycle(record)
    assert any("outcome is 'blockers' but blocker_count is < 1" in e for e in errs)


def test_review_finding_rejects_bad_severity_enum() -> None:
    record = _minimal_record(
        reviews=[_review(findings=[{"description": "x", "severity": "catastrophic", "fixed": None}])]
    )
    errs = ct.validate_cycle(record)
    assert any("severity must be one of" in e for e in errs)


def test_review_finding_fixed_defaults_to_unknown_not_false() -> None:
    """fixed: None ('not yet re-confirmed') must be accepted -- a validator
    that required a boolean would force a premature true/false claim."""
    record = _minimal_record(
        reviews=[_review(findings=[{"description": "x", "severity": "blocker", "fixed": None}])]
    )
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# v2 — changes[].
# ---------------------------------------------------------------------------


def _change(**overrides: object) -> dict:
    c = {
        "change_id": "chg-1",
        "finding_id": "b0-f03",
        "commit_sha": "uncommitted",
        "files": ["Items.csv"],
        "lines_added": None,
        "lines_removed": None,
        "red_before_green": "required (worktree-isolated); not yet confirmed as of this record",
        "tests_added": [],
        "golden_net_drift": None,
        "reverted": False,
    }
    c.update(overrides)
    return c


def test_change_minimal_is_valid() -> None:
    record = _minimal_record(changes=[_change()])
    assert ct.validate_cycle(record) == []


def test_change_commit_sha_accepts_uncommitted_literal() -> None:
    record = _minimal_record(changes=[_change(commit_sha="uncommitted")])
    assert ct.validate_cycle(record) == []


def test_change_rejects_empty_commit_sha() -> None:
    record = _minimal_record(changes=[_change(commit_sha="")])
    errs = ct.validate_cycle(record)
    assert any("commit_sha must be a non-empty string" in e for e in errs)


def test_change_reverted_must_be_boolean() -> None:
    record = _minimal_record(changes=[_change(reverted="yes")])
    errs = ct.validate_cycle(record)
    assert any("reverted must be a boolean" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — decisions[] (operator rulings are first-class, never a note).
# ---------------------------------------------------------------------------


def _decision(**overrides: object) -> dict:
    d = {
        "decision_id": "dec-1",
        "decided_by": "OPERATOR",
        "what": "the drain body is PLUMBING's scope",
        "reasoning": "listen to the plumbers.",
        "supersedes": ["ruling-#6", "ruling-#56"],
        "action": "do not move AUTH_SHOWER_DRAIN_TILE to TILE",
        "decided_at": None,
    }
    d.update(overrides)
    return d


def test_decision_minimal_is_valid() -> None:
    record = _minimal_record(decisions=[_decision()])
    assert ct.validate_cycle(record) == []


def test_decision_rejects_empty_reasoning() -> None:
    """FALSIFY target: 'verbatim reasoning' is the entire point of gap 4 --
    an empty/whitespace reasoning string must be rejected, not silently
    accepted as 'reasoning was recorded'."""
    record = _minimal_record(decisions=[_decision(reasoning="   ")])
    errs = ct.validate_cycle(record)
    assert any("reasoning must be a non-empty string" in e for e in errs)


def test_decision_operator_is_just_a_free_string_value() -> None:
    # decided_by has no enum -- OPERATOR is data, not a special-cased literal.
    record = _minimal_record(decisions=[_decision(decided_by="general-contractor")])
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# v2 — issues_filed[].
# ---------------------------------------------------------------------------


def test_issue_filed_minimal_is_valid() -> None:
    record = _minimal_record(
        issues_filed=[
            {
                "issue_id": "#4535",
                "title": "grade.py silently substitutes 'standard'",
                "related_findings": ["b0-f10"],
                "filed_by": None,
                "filed_at": None,
                "status": None,
            }
        ]
    )
    assert ct.validate_cycle(record) == []


def test_issue_filed_rejects_empty_issue_id() -> None:
    record = _minimal_record(
        issues_filed=[
            {
                "issue_id": "",
                "title": "x",
                "related_findings": [],
                "filed_by": None,
                "filed_at": None,
                "status": None,
            }
        ]
    )
    errs = ct.validate_cycle(record)
    assert any("issue_id must be a non-empty string" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — evidence[] (at least one of file/quote/repro_command required).
# ---------------------------------------------------------------------------


def test_evidence_requires_at_least_one_of_file_quote_repro() -> None:
    record = _minimal_record(
        evidence=[
            {
                "evidence_id": "ev-1",
                "finding_id": None,
                "file": None,
                "line": None,
                "quote": None,
                "repro_command": None,
            }
        ]
    )
    errs = ct.validate_cycle(record)
    assert any("evidence must include at least one of" in e for e in errs)


def test_evidence_with_only_a_file_and_line_is_valid() -> None:
    record = _minimal_record(
        evidence=[
            {
                "evidence_id": "ev-1",
                "finding_id": "b0-f10",
                "file": "modules/estimate_engine_v3/estimate_generator/grade.py",
                "line": 190,
                "quote": None,
                "repro_command": None,
            }
        ]
    )
    assert ct.validate_cycle(record) == []


# ---------------------------------------------------------------------------
# v2 — corrections[] (the loop's own error record).
# ---------------------------------------------------------------------------


def test_correction_minimal_is_valid() -> None:
    record = _minimal_record(
        corrections=[
            {
                "correction_id": "corr-1",
                "what_was_claimed": "TILE caught the plant at rung1/rung5",
                "what_was_wrong": "the payload leaked the plant_id label",
                "how_found": "grepped the 27 raw reports for the leaked string",
                "invalidated": "the B0 pilot's headline calibration claim",
            }
        ]
    )
    assert ct.validate_cycle(record) == []


def test_correction_rejects_missing_how_found() -> None:
    record = _minimal_record(
        corrections=[
            {
                "correction_id": "corr-1",
                "what_was_claimed": "x",
                "what_was_wrong": "y",
                "how_found": "",
                "invalidated": None,
            }
        ]
    )
    errs = ct.validate_cycle(record)
    assert any("how_found must be a non-empty string" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — verdicts[] (raw per-scenario CONCUR/DISSENT rows).
# ---------------------------------------------------------------------------


def test_verdict_minimal_is_valid() -> None:
    record = _minimal_record(
        verdicts=[
            {
                "dispatch_label": "TILE:rung1",
                "scenario": "standard_replace__base",
                "verdict": "CONCUR",
                "confidence": 0.9,
                "problem_count": 0,
            }
        ]
    )
    assert ct.validate_cycle(record) == []


def test_verdict_rejects_bad_enum() -> None:
    record = _minimal_record(
        verdicts=[
            {
                "dispatch_label": "x",
                "scenario": "y",
                "verdict": "MAYBE",
                "confidence": None,
                "problem_count": None,
            }
        ]
    )
    errs = ct.validate_cycle(record)
    assert any("verdict must be one of" in e for e in errs)


def test_verdict_confidence_must_be_in_unit_range() -> None:
    record = _minimal_record(
        verdicts=[
            {
                "dispatch_label": "x",
                "scenario": "y",
                "verdict": "CONCUR",
                "confidence": 1.5,
                "problem_count": None,
            }
        ]
    )
    errs = ct.validate_cycle(record)
    assert any("confidence must be between 0 and 1" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — stages[] (blocked_reason required, non-empty, whenever blocked).
# ---------------------------------------------------------------------------


def test_stage_ran_is_valid_without_a_blocked_reason() -> None:
    record = _minimal_record(
        stages=[{"stage_id": "finder_pass", "name": "finder pass", "status": "ran", "blocked_reason": None}]
    )
    assert ct.validate_cycle(record) == []


def test_stage_blocked_requires_non_empty_reason() -> None:
    """FALSIFY target: a stage recorded as blocked with no reason is exactly
    the gap 11 case (e.g. 'the commit blocked by 6 review blockers') that
    must never render as an unexplained gap."""
    record = _minimal_record(
        stages=[{"stage_id": "commit", "name": "commit", "status": "blocked", "blocked_reason": None}]
    )
    errs = ct.validate_cycle(record)
    assert any("status is 'blocked' but no non-empty 'blocked_reason'" in e for e in errs)


def test_stage_blocked_with_reason_is_valid() -> None:
    record = _minimal_record(
        stages=[
            {
                "stage_id": "commit",
                "name": "commit",
                "status": "blocked",
                "blocked_reason": "6 unresolved review blockers",
            }
        ]
    )
    assert ct.validate_cycle(record) == []


def test_stage_rejects_bad_status_enum() -> None:
    record = _minimal_record(
        stages=[{"stage_id": "x", "name": "x", "status": "maybe", "blocked_reason": None}]
    )
    errs = ct.validate_cycle(record)
    assert any("status must be one of" in e for e in errs)


# ---------------------------------------------------------------------------
# v2 — calibration_runs[] (the GRID form of the legacy `calibration` block;
# added W4s, GH #4648, to express a plants-x-trades grader-calibration grid
# a single `calibration` object structurally cannot: one plant per record,
# unknown keys rejected, caught_by/missed_by forced empty whenever plant_id
# is null. A calibration_runs row with plant_id null is a CONTROL (clean
# package); one with plant_id set is a PLANT (a real seeded defect).
# ---------------------------------------------------------------------------


def _calibration_run(**overrides: object) -> dict:
    """A PLANT row builder: plant_id set, no false_alarm_finding_ids."""
    r = {
        "plant_id": "PLANT_mut1_scn1",
        "trade": "tile",
        "slot": 1,
        "batch_size": 4,
        "caught_by": ["tile"],
        "missed_by": [],
        "false_alarm_finding_ids": [],
    }
    r.update(overrides)
    return r


def _control_run(**overrides: object) -> dict:
    """A CONTROL row builder: plant_id null, no caught_by/missed_by."""
    r = {
        "plant_id": None,
        "trade": "tile",
        "slot": 2,
        "batch_size": 4,
        "caught_by": [],
        "missed_by": [],
        "false_alarm_finding_ids": [],
    }
    r.update(overrides)
    return r


def test_calibration_runs_accepts_well_formed_plants_and_controls() -> None:
    record = _minimal_record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            _calibration_run(trade="plumbing", caught_by=[], missed_by=["plumbing"]),
            _control_run(trade="tile"),
            _control_run(trade="plumbing", false_alarm_finding_ids=["f-fa-1"]),
        ]
    )
    assert ct.validate_cycle(record) == []


def test_calibration_run_rejects_unknown_key() -> None:
    run = _calibration_run()
    run["made_up_field"] = 1
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("unknown key: made_up_field" in e for e in errs)


def test_calibration_run_missing_required_key() -> None:
    run = _calibration_run()
    del run["trade"]
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("missing required key: trade" in e for e in errs)


def test_calibration_run_rejects_blank_trade() -> None:
    run = _calibration_run(trade="   ")
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("trade must be a non-empty string" in e for e in errs)


def test_calibration_run_rejects_bad_batch_size() -> None:
    run = _calibration_run(batch_size=0)
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("batch_size must be >= 1" in e for e in errs)


def test_calibration_run_rejects_control_with_caught_by() -> None:
    """The core structural gap this array closes for the OTHER direction --
    a control's caught_by must stay empty exactly like _validate_calibration
    already enforces for the legacy single block."""
    run = _control_run(caught_by=["tile"])
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any(
        "caught_by/missed_by must be empty when plant_id is null (a control row)" in e for e in errs
    )


def test_calibration_run_rejects_control_with_missed_by() -> None:
    run = _control_run(missed_by=["tile"])
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any(
        "caught_by/missed_by must be empty when plant_id is null (a control row)" in e for e in errs
    )


def test_calibration_run_rejects_plant_with_false_alarm_finding_ids() -> None:
    """THE gap this array was built to close: a clean control carrying a
    false-alarm finding must validate; a genuinely-seeded plant carrying one
    must NOT -- a finding against a real plant is a catch/miss, never a
    false alarm."""
    run = _calibration_run(false_alarm_finding_ids=["f-fa-2"])
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("false_alarm_finding_ids must be empty when plant_id is set" in e for e in errs)


def test_calibration_run_control_may_carry_false_alarm_finding_ids() -> None:
    """THE positive half of the gap this array closes: a clean control
    structurally CAN carry the false-alarm signal now."""
    run = _control_run(false_alarm_finding_ids=["f-fa-3", "f-fa-4"])
    record = _minimal_record(calibration_runs=[run])
    assert ct.validate_cycle(record) == []


def test_calibration_run_false_alarm_finding_ids_must_be_non_empty_strings() -> None:
    run = _control_run(false_alarm_finding_ids=[1, 2])
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("false_alarm_finding_ids must be a list of non-empty strings" in e for e in errs)


def test_calibration_run_rejects_bad_caught_by_type() -> None:
    run = _calibration_run(caught_by="tile")
    record = _minimal_record(calibration_runs=[run])
    errs = ct.validate_cycle(record)
    assert any("caught_by must be a list of strings/integers" in e for e in errs)


def test_record_without_calibration_runs_still_validates() -> None:
    """calibration_runs is truly OPTIONAL -- a record carrying only the
    legacy single `calibration` block (none of this new array) must keep
    validating exactly as before this array existed."""
    record = _minimal_record(dispatches=[_dispatch()], findings=[_finding()])
    assert "calibration_runs" not in record
    assert ct.validate_cycle(record) == []


def test_falsifiability_calibration_run_validator_would_pass_a_broken_stub() -> None:
    """Demonstrates the failure mode a real per-row validator must NOT have:
    a stub that always returns [] would let a control row secretly carrying
    caught_by (impossible — nothing was seeded in a control to catch) reach
    write_cycle() undetected, silently corrupting the very false-alarm
    signal this array exists to carry. Show the real validator does not."""

    def _always_valid_stub(_row: object) -> list[str]:
        return []

    broken_control = _control_run(caught_by=["tile"])
    assert _always_valid_stub(broken_control) == []  # the bug: stub says "fine"
    assert ct._validate_calibration_run(broken_control) != []  # real: not fine


# ---------------------------------------------------------------------------
# v2 — undispatched_verdict_rows (round-25 structural-conflict fix,
# 2026-09-07, ExampleApp): an OPTIONAL top-level OBJECT (like
# `calibration`/`cost`, not an array) holding honest accounting for a
# verdict row EXCLUDED from dispatches[] because it carries no real dispatch
# identity (e.g. a GC consolidation pass, never its own Task dispatch —
# fabricating one is forbidden, GH #5051). resolve_cost() itself is
# UNTOUCHED by this field; it exists purely so a producer can honestly
# report what it left out of dispatches[] to satisfy resolve_cost()'s
# pre-existing uniform-identity requirement.
# ---------------------------------------------------------------------------


def _undispatched(**overrides: object) -> dict:
    u = {"count": 2, "by_judge": {"gc": 2}}
    u.update(overrides)
    return u


def test_undispatched_verdict_rows_accepts_well_formed_object() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched())
    assert ct.validate_cycle(record) == []


def test_undispatched_verdict_rows_accepts_zero_count_empty_by_judge() -> None:
    """The honest 'nothing excluded' shape -- explicit zero/empty, never
    omitted just because there was nothing to report."""
    record = _minimal_record(undispatched_verdict_rows={"count": 0, "by_judge": {}})
    assert ct.validate_cycle(record) == []


def test_undispatched_verdict_rows_rejects_unknown_key() -> None:
    obj = _undispatched()
    obj["made_up_field"] = 1
    record = _minimal_record(undispatched_verdict_rows=obj)
    errs = ct.validate_cycle(record)
    assert any("unknown key: made_up_field" in e for e in errs)


def test_undispatched_verdict_rows_missing_count_key() -> None:
    obj = _undispatched()
    del obj["count"]
    record = _minimal_record(undispatched_verdict_rows=obj)
    errs = ct.validate_cycle(record)
    assert any("missing required key: count" in e for e in errs)


def test_undispatched_verdict_rows_missing_by_judge_key() -> None:
    obj = _undispatched()
    del obj["by_judge"]
    record = _minimal_record(undispatched_verdict_rows=obj)
    errs = ct.validate_cycle(record)
    assert any("missing required key: by_judge" in e for e in errs)


def test_undispatched_verdict_rows_rejects_negative_count() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(count=-1))
    errs = ct.validate_cycle(record)
    assert any("count must be a non-negative integer" in e for e in errs)


def test_undispatched_verdict_rows_rejects_non_integer_count() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(count="2"))
    errs = ct.validate_cycle(record)
    assert any("count must be a non-negative integer" in e for e in errs)


def test_undispatched_verdict_rows_rejects_bool_as_count() -> None:
    """bool is a subclass of int in Python -- the guard must explicitly
    reject it, mirroring every other integer-field guard in this module."""
    record = _minimal_record(undispatched_verdict_rows=_undispatched(count=True))
    errs = ct.validate_cycle(record)
    assert any("count must be a non-negative integer" in e for e in errs)


def test_undispatched_verdict_rows_rejects_by_judge_not_an_object() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(by_judge=["gc", 2]))
    errs = ct.validate_cycle(record)
    assert any("by_judge must be an object" in e for e in errs)


def test_undispatched_verdict_rows_rejects_negative_by_judge_value() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(by_judge={"gc": -1}))
    errs = ct.validate_cycle(record)
    assert any("by_judge['gc'] must be a non-negative integer" in e for e in errs)


def test_undispatched_verdict_rows_rejects_non_integer_by_judge_value() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(by_judge={"gc": "2"}))
    errs = ct.validate_cycle(record)
    assert any("by_judge['gc'] must be a non-negative integer" in e for e in errs)


def test_undispatched_verdict_rows_rejects_empty_string_judge_key() -> None:
    record = _minimal_record(undispatched_verdict_rows=_undispatched(by_judge={"": 2}))
    errs = ct.validate_cycle(record)
    assert any("by_judge keys must be non-empty strings" in e for e in errs)


def test_undispatched_verdict_rows_rejects_count_by_judge_sum_mismatch() -> None:
    """THE core cross-field rule this object exists to enforce: the
    breakdown and the total must agree -- a mismatch is exactly the kind of
    silent inconsistency this honest-accounting field must never tolerate."""
    record = _minimal_record(
        undispatched_verdict_rows={"count": 5, "by_judge": {"gc": 2, "tile": 1}}
    )
    errs = ct.validate_cycle(record)
    assert any("by_judge values sum to 3, which does not match count (5)" in e for e in errs)


def test_undispatched_verdict_rows_multi_judge_sum_matches() -> None:
    record = _minimal_record(
        undispatched_verdict_rows={"count": 4, "by_judge": {"gc": 3, "electrical": 1}}
    )
    assert ct.validate_cycle(record) == []


def test_record_without_undispatched_verdict_rows_still_validates() -> None:
    """Truly OPTIONAL, purely additive -- a record with no
    undispatched_verdict_rows key at all (every pre-2026-09-07 record) must
    keep validating unchanged."""
    record = _minimal_record(dispatches=[_dispatch()], findings=[_finding()])
    assert "undispatched_verdict_rows" not in record
    assert ct.validate_cycle(record) == []


def test_falsifiability_undispatched_verdict_rows_validator_would_pass_a_broken_stub() -> None:
    """A stub that always returns [] would let a count/by_judge mismatch
    (the exact silent-inconsistency defect this object exists to prevent)
    reach write_cycle() undetected. Show the real validator does not."""

    def _always_valid_stub(_obj: object) -> list[str]:
        return []

    broken = {"count": 99, "by_judge": {"gc": 1}}
    assert _always_valid_stub(broken) == []  # the bug: stub says "fine"
    assert ct._validate_undispatched_verdict_rows(broken) != []  # real: not fine


def test_schema_json_validates_a_record_with_undispatched_verdict_rows() -> None:
    """schema/code parity: a well-formed record carrying
    undispatched_verdict_rows must pass both the Python validator and
    jsonschema.validate() against schema.json."""
    record = _minimal_record(undispatched_verdict_rows=_undispatched())
    assert ct.validate_cycle(record) == []
    jsonschema.validate(instance=record, schema=_load_schema())


def test_schema_json_rejects_unknown_key_inside_undispatched_verdict_rows() -> None:
    obj = _undispatched()
    obj["made_up_field"] = 1
    record = _minimal_record(undispatched_verdict_rows=obj)

    code_errs = ct.validate_cycle(record)
    assert any("unknown key: made_up_field" in e for e in code_errs)

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(instance=record, schema=_load_schema())
    err = exc_info.value
    assert "made_up_field" in err.message
    assert list(err.absolute_path) == ["undispatched_verdict_rows"]


def test_schema_undispatched_verdict_rows_required_keys_match_code() -> None:
    """Required-keys parity fence, mirroring the calibration_run one above --
    schema.json's undispatched_verdict_rows.required list and
    cycle_telemetry.py's own REQUIRED_UNDISPATCHED_VERDICT_ROWS_KEYS are
    hand-maintained in two separate files with no shared source of truth."""
    schema = _load_schema()
    schema_required = set(schema["$defs"]["undispatched_verdict_rows"]["required"])
    assert schema_required == ct.REQUIRED_UNDISPATCHED_VERDICT_ROWS_KEYS


# ---------------------------------------------------------------------------
# v2 — unknown top-level key handling still fires alongside the new arrays.
# ---------------------------------------------------------------------------


def test_v2_arrays_do_not_open_the_door_to_arbitrary_top_level_keys() -> None:
    record = _minimal_record(runs=[_run()])
    record["totally_made_up_v2_field"] = 1
    errs = ct.validate_cycle(record)
    assert any("unknown top-level key: totally_made_up_v2_field" in e for e in errs)


def test_v2_array_must_be_a_list_not_a_dict() -> None:
    record = _minimal_record(runs={"not": "a list"})
    errs = ct.validate_cycle(record)
    assert any("runs must be a list" in e for e in errs)


# ---------------------------------------------------------------------------
# assert_valid_cycle / ValidationError.
# ---------------------------------------------------------------------------


def test_assert_valid_cycle_raises_validation_error_with_errors_attr() -> None:
    record = _minimal_record()
    del record["cost"]
    with pytest.raises(ct.ValidationError) as exc_info:
        ct.assert_valid_cycle(record)
    assert any("cost" in e for e in exc_info.value.errors)


def test_assert_valid_cycle_passes_silently_for_valid_record() -> None:
    ct.assert_valid_cycle(_minimal_record())  # must not raise


# ---------------------------------------------------------------------------
# write_cycle / read_cycle / read_cycles — FALSIFY: a malformed record must
# never reach disk.
# ---------------------------------------------------------------------------


def test_write_cycle_refuses_invalid_record_and_writes_nothing(tmp_path) -> None:
    cycles_dir = str(tmp_path / "cycles")
    record = _minimal_record()
    del record["notes"]  # now invalid
    with pytest.raises(ct.ValidationError):
        ct.write_cycle(record, cycles_dir=cycles_dir)
    # Nothing was persisted -- not the target file, not even the directory.
    target = os.path.join(cycles_dir, "test-loop", "cycle-001.json")
    assert not os.path.exists(target)


def test_write_read_roundtrip(tmp_path) -> None:
    cycles_dir = str(tmp_path / "cycles")
    record = _minimal_record()
    path = ct.write_cycle(record, cycles_dir=cycles_dir)
    assert os.path.exists(path)
    loaded = ct.read_cycle("test-loop", "cycle-001", cycles_dir=cycles_dir)
    assert loaded == record


def test_write_cycle_refuses_overwrite_by_default(tmp_path) -> None:
    cycles_dir = str(tmp_path / "cycles")
    record = _minimal_record()
    ct.write_cycle(record, cycles_dir=cycles_dir)
    with pytest.raises(FileExistsError):
        ct.write_cycle(record, cycles_dir=cycles_dir)
    # overwrite=True succeeds.
    record2 = _minimal_record(notes=["updated"])
    ct.write_cycle(record2, cycles_dir=cycles_dir, overwrite=True)
    assert ct.read_cycle("test-loop", "cycle-001", cycles_dir=cycles_dir)["notes"] == ["updated"]


def test_cycle_path_rejects_path_traversal_system() -> None:
    with pytest.raises(ValueError):
        ct.cycle_path("../../etc", "cycle-1")
    with pytest.raises(ValueError):
        ct.cycle_path("sys", "../../escape")


def test_read_cycles_across_multiple_systems(tmp_path) -> None:
    cycles_dir = str(tmp_path / "cycles")
    ct.write_cycle(_minimal_record(system="loop-a", cycle_id="c1"), cycles_dir=cycles_dir)
    ct.write_cycle(_minimal_record(system="loop-a", cycle_id="c2"), cycles_dir=cycles_dir)
    ct.write_cycle(_minimal_record(system="loop-b", cycle_id="c1"), cycles_dir=cycles_dir)

    assert ct.list_systems(cycles_dir=cycles_dir) == ["loop-a", "loop-b"]
    assert len(ct.read_cycles("loop-a", cycles_dir=cycles_dir)) == 2
    assert len(ct.read_cycles(cycles_dir=cycles_dir)) == 3
    assert ct.read_cycles("nonexistent-system", cycles_dir=cycles_dir) == []


def test_read_cycles_raises_by_default_on_corrupt_file(tmp_path) -> None:
    cycles_dir = tmp_path / "cycles" / "loop-a"
    cycles_dir.mkdir(parents=True)
    (cycles_dir / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        ct.read_cycles("loop-a", cycles_dir=str(tmp_path / "cycles"))
    # on_error="skip" tolerates it instead.
    assert ct.read_cycles("loop-a", cycles_dir=str(tmp_path / "cycles"), on_error="skip") == []


# ---------------------------------------------------------------------------
# Metrics — exact values against the shipped, hand-verified sample fixture.
# This is also the "real fixture exercises the library" requirement.
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_record() -> dict:
    path = os.path.join(ct.FIXTURES_DIR, "sample_cycle_record.json")
    if not os.path.exists(path):
        # "too much data is better than not enough, never silently drop" is
        # about DATA, not about crashing the whole suite when a clean $HOME
        # (no real ~/.claude/telemetry/fixtures/ at all) has none of it --
        # skip, matching how the suite already tolerates an absent ledger.
        pytest.skip(f"real sample fixture not present in this $HOME: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_sample_fixture_is_schema_valid(sample_record: dict) -> None:
    assert ct.validate_cycle(sample_record) == []


def test_sample_fixture_is_labelled_as_a_sample(sample_record: dict) -> None:
    assert any("SAMPLE FIXTURE" in n for n in sample_record["notes"])


def test_sample_fixture_symptom_precision_is_8_of_9(sample_record: dict) -> None:
    assert ct.symptom_precision(sample_record) == pytest.approx(8 / 9)


def test_sample_fixture_cause_precision_is_1_of_9(sample_record: dict) -> None:
    assert ct.cause_precision(sample_record) == pytest.approx(1 / 9)


def test_cause_precision_is_far_lower_than_symptom_precision(sample_record: dict) -> None:
    # The whole point of the metric: the gap must be visible, not averaged away.
    assert ct.cause_precision(sample_record) < ct.symptom_precision(sample_record) / 4


def test_sample_fixture_duplicate_rate_is_2_of_9(sample_record: dict) -> None:
    assert ct.duplicate_rate(sample_record) == pytest.approx(2 / 9)


def test_sample_fixture_ruling_conflict_rate_is_3_of_9(sample_record: dict) -> None:
    assert ct.ruling_conflict_rate(sample_record) == pytest.approx(3 / 9)


def test_sample_fixture_plant_caught_first_and_last_missed_middle(sample_record: dict) -> None:
    result = ct.plant_catch_by_slot(sample_record)
    assert result["1"]["caught"] == 1 and result["1"]["missed"] == 0
    assert result["3"]["caught"] == 1 and result["3"]["missed"] == 0
    assert result["2"]["caught"] == 0 and result["2"]["missed"] == 1


def test_sample_fixture_cost_block_is_schema_valid_and_ledger_sourced(sample_record: dict) -> None:
    """The sample fixture's baked-in cost.total_tokens/.total_usd are a
    hand-authored constant no library code ever produces or checks -- an
    earlier version of this test just asserted that constant back at itself
    (a lock-in test exercising zero library code, exactly what a library
    whose thesis is "never trust an unverified number" must not ship).
    Replaced with two real checks: (1) the fixture's baked cost block is
    itself schema-valid data under this library's own validator, and (2) the
    *actual number* asserted below is DERIVED by running resolve_cost() over
    a small, real, self-contained ledger this test constructs itself -- never
    a number copied from the fixture file."""
    cost = sample_record["cost"]
    assert cost["source"] == "spend_ledger"
    assert ct.validate_cycle(sample_record) == []


def test_resolve_cost_derives_its_own_total_from_a_small_synthetic_ledger(tmp_path) -> None:
    """DERIVES the priced total from resolve_cost() itself, over a ledger this
    test writes -- the actual replacement for the deleted lock-in assertion.
    Two dispatches, two matching ledger rows, a known pricing table: the
    expected dollar figure is computed here from the same formula
    price_tokens() uses, not copied from any fixture. Post-BLOCKER-1 (round
    3): both dispatches declare a tool_use_id the ledger corroborates, since
    a 'spend_ledger' verdict now requires uniform identity declaration."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="finder", tool_use_id="tu-finder-2"),
            _dispatch(agent_type="verifier", tool_use_id="tu-verifier-2"),
        ],
    )
    rows = [
        _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=2_000_000, model="m"),
        _ledger_row("2026-08-27T14:20:00Z", "verifier", tokens_total=1_500_000, model="m"),
    ]
    rows[0]["tool_use_id"] = "tu-finder-2"
    rows[1]["tool_use_id"] = "tu-verifier-2"
    ledger = _write_ledger(tmp_path, rows)
    rates = {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75}
    pricing = _write_pricing(tmp_path, {"m": rates})

    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)

    expected_tokens = sum(r["tokens_total"] for r in rows)
    expected_usd = sum(ct.price_tokens(r["tokens"], r["model"], {"per_million_tokens": {"m": rates}}) for r in rows)
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] == expected_tokens
    assert result["total_usd"] == pytest.approx(expected_usd)
    # Falsifiability: a lock-in test copied from a single run wouldn't notice
    # if the formula changed shape -- this one recomputes the expectation
    # from price_tokens() itself, so a formula change moves both sides
    # together and a REAL divergence (a resolve_cost bug) still fails it.
    assert expected_usd > 0


def test_sample_fixture_dispatch_tokens_are_the_smaller_harness_figure(sample_record: dict) -> None:
    # The harness-reported per-dispatch sum must NOT equal the authoritative
    # ledger total -- that mismatch is the entire "why cost.source matters"
    # lesson this fixture encodes.
    dispatch_sum = sum(d["tokens_total"] for d in sample_record["dispatches"])
    assert dispatch_sum < sample_record["cost"]["total_tokens"] / 10


# ---------------------------------------------------------------------------
# Metrics — None-on-empty conventions and simple hand-built cases.
# ---------------------------------------------------------------------------


def test_metrics_are_none_when_no_findings() -> None:
    record = _minimal_record()
    metrics = ct.compute_metrics(record)
    assert metrics["symptom_precision"] is None
    assert metrics["cause_precision"] is None
    assert metrics["duplicate_rate"] is None
    assert metrics["ruling_conflict_rate"] is None
    assert metrics["consolidation_ratio"] is None
    assert metrics["usd_per_confirmed_defect"] is None
    assert metrics["plant_catch_by_slot"] == {}


def test_symptom_precision_excludes_unverifiable_from_denominator() -> None:
    record = _minimal_record(
        findings=[
            _finding(finding_id="f1", verifier_verdict="CONFIRMED"),
            _finding(finding_id="f2", verifier_verdict="UNVERIFIABLE", verifier_cause_upheld=None),
        ]
    )
    # Only f1 is judged -> 1/1, not 1/2.
    assert ct.symptom_precision(record) == 1.0


def test_consolidation_ratio_reflects_converged_raisers() -> None:
    record = _minimal_record(
        findings=[
            _finding(finding_id="f1", raised_by=["a", "b", "c"]),
            _finding(finding_id="f2", raised_by=["d"]),
        ]
    )
    assert ct.consolidation_ratio(record) == pytest.approx(4 / 2)


def test_usd_per_confirmed_defect_none_when_cost_unpriced() -> None:
    record = _minimal_record(
        findings=[_finding()],
        cost={"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "x"},
    )
    assert ct.usd_per_confirmed_defect(record) is None


def test_usd_per_confirmed_defect_none_when_zero_confirmed() -> None:
    record = _minimal_record(
        findings=[_finding(verifier_verdict="REFUTED", verifier_cause_upheld=False)],
        cost={"source": "reported", "total_tokens": 10, "total_usd": 5.0},
    )
    assert ct.usd_per_confirmed_defect(record) is None


def test_aggregate_metrics_pools_counts_not_averages_ratios() -> None:
    # Cycle A: 1 finding, symptom-correct. Cycle B: 9 findings, all wrong.
    # Naive average-of-ratios would give (1.0 + 0.0)/2 == 0.5; pooled counts
    # give 1/10 == 0.1, which is the honest answer given the finding volume.
    a = _minimal_record(
        system="s", cycle_id="a", findings=[_finding(finding_id="f1", verifier_verdict="CONFIRMED")]
    )
    b_findings = [
        _finding(finding_id=f"g{i}", verifier_verdict="REFUTED", verifier_cause_upheld=False)
        for i in range(9)
    ]
    b = _minimal_record(system="s", cycle_id="b", findings=b_findings)
    agg = ct.aggregate_metrics([a, b])
    assert agg["symptom_precision"] == pytest.approx(1 / 10)
    assert agg["cycle_count"] == 2
    assert agg["finding_count"] == 10


def test_aggregate_metrics_empty_list() -> None:
    agg = ct.aggregate_metrics([])
    assert agg["cycle_count"] == 0
    assert agg["symptom_precision"] is None


def test_aggregate_metrics_never_crashes_on_a_non_numeric_total_usd(tmp_path) -> None:
    """Found while falsifying BLOCKER 4 in render_cycle_log.py (which now
    calls aggregate_metrics() directly on raw, possibly-unvalidated JSON): a
    hand-edited/corrupted record with cost.total_usd as a STRING used to
    raise TypeError summing a str into a float accumulator -- degrade to
    None instead, the same honest answer as a missing total_usd, never a
    crash for any caller of this library function."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": "5.00"},
        findings=[_finding(finding_id="f1", verifier_verdict="CONFIRMED")],
    )
    agg = ct.aggregate_metrics([record])
    assert agg["usd_per_confirmed_defect"] is None
    assert agg["cost_known_cycles"] == 0
    assert agg["cost_unknown_cycles"] == 1
    # Same guard on the single-record function.
    assert ct.usd_per_confirmed_defect(record) is None


def test_plant_catch_by_slot_pools_across_multiple_records() -> None:
    r1 = _minimal_record(
        cycle_id="c1",
        calibration={"plant_id": "p", "planted_in": "x", "slot": 1, "caught_by": [1], "missed_by": []},
    )
    r2 = _minimal_record(
        cycle_id="c2",
        calibration={"plant_id": "p", "planted_in": "x", "slot": 1, "caught_by": [], "missed_by": [1]},
    )
    pooled = ct.plant_catch_by_slot([r1, r2])
    assert pooled["1"] == {"caught": 1, "missed": 1, "rate": 0.5}


@pytest.mark.parametrize("field", ["caught_by", "missed_by"])
@pytest.mark.parametrize("malformed", [7, 3.5, "abc"])
def test_plant_catch_by_slot_never_crashes_or_fabricates_on_malformed_field(
    field: object, malformed: object
) -> None:
    """BLOCKER 2 (round 4): a malformed calibration.caught_by/missed_by (an
    int, a float, or a bare string instead of a list) must never reach a
    bare `for slot in cal.get(field) or []` -- an int/float raises
    TypeError ('int' object is not iterable), and a str silently ITERATES
    ITS OWN CHARACTERS, fabricating invented slots at a fabricated 100%
    catch rate (e.g. "abc" -> three invented slots {'a', 'b', 'c'}) -- the
    exact same defect class as round 1's already-fixed fabricated-0%-catch
    bug, just in the sibling field. Real repro shapes from the review:
    caught_by=7 -> TypeError; caught_by=3.5 -> TypeError; caught_by="abc" ->
    fabricates 3 slots at rate 1.0. Correct behavior: treat any non-list
    value the same as absent -- contribute nothing, never crash, never
    invent data."""
    rec = {"calibration": {"plant_id": "p1", field: malformed}}
    result = ct.plant_catch_by_slot(rec)  # must not raise
    assert result == {}, f"malformed {field}={malformed!r} must contribute nothing, got {result}"


# ---------------------------------------------------------------------------
# plant_catch_by_trade / false_alarm_by_trade — calibration_runs[]
# aggregators, siblings of plant_catch_by_slot that read the GRID array
# instead of the legacy single `calibration` block (W4s, GH #4648).
# ---------------------------------------------------------------------------


def test_plant_catch_by_trade_and_false_alarm_by_trade_from_a_mixed_grid() -> None:
    """One record carrying a mixed grid across two trades: each trade has a
    caught plant, a missed plant, and a control -- one control drew a false
    alarm, the other didn't. Both aggregators read the SAME
    calibration_runs[] array independently and must agree on per-trade
    counts computed from it."""
    record = _minimal_record(
        calibration_runs=[
            _calibration_run(trade="tile", slot=1, caught_by=["tile"], missed_by=[]),
            _calibration_run(trade="tile", slot=2, caught_by=[], missed_by=["tile"]),
            _control_run(trade="tile", slot=3, false_alarm_finding_ids=["f-1"]),
            _calibration_run(trade="plumbing", slot=1, caught_by=["plumbing"], missed_by=[]),
            _control_run(trade="plumbing", slot=2, false_alarm_finding_ids=[]),
        ]
    )
    catch = ct.plant_catch_by_trade(record)
    assert catch["tile"] == {"caught": 1, "missed": 1, "unreadable": 0, "rate": 0.5}
    assert catch["plumbing"] == {"caught": 1, "missed": 0, "unreadable": 0, "rate": 1.0}

    alarms = ct.false_alarm_by_trade(record)
    assert alarms["tile"] == {"controls": 1, "false_alarms": 1, "unreadable": 0, "rate": 1.0}
    assert alarms["plumbing"] == {"controls": 1, "false_alarms": 0, "unreadable": 0, "rate": 0.0}


def test_plant_catch_by_trade_skips_control_rows() -> None:
    record = _minimal_record(calibration_runs=[_control_run(trade="tile")])
    assert ct.plant_catch_by_trade(record) == {}


def test_false_alarm_by_trade_skips_plant_rows() -> None:
    record = _minimal_record(calibration_runs=[_calibration_run(trade="tile")])
    assert ct.false_alarm_by_trade(record) == {}


def test_plant_catch_by_trade_pools_across_multiple_records() -> None:
    r1 = _minimal_record(
        cycle_id="c1",
        calibration_runs=[_calibration_run(trade="tile", caught_by=["tile"], missed_by=[])],
    )
    r2 = _minimal_record(
        cycle_id="c2",
        calibration_runs=[_calibration_run(trade="tile", caught_by=[], missed_by=["tile"])],
    )
    pooled = ct.plant_catch_by_trade([r1, r2])
    assert pooled["tile"] == {"caught": 1, "missed": 1, "unreadable": 0, "rate": 0.5}


def test_false_alarm_by_trade_pools_across_multiple_records() -> None:
    r1 = _minimal_record(
        cycle_id="c1", calibration_runs=[_control_run(trade="tile", false_alarm_finding_ids=["f-1"])]
    )
    r2 = _minimal_record(
        cycle_id="c2", calibration_runs=[_control_run(trade="tile", false_alarm_finding_ids=[])]
    )
    pooled = ct.false_alarm_by_trade([r1, r2])
    assert pooled["tile"] == {"controls": 2, "false_alarms": 1, "unreadable": 0, "rate": 0.5}


def test_calibration_run_plant_with_empty_catches_and_misses_is_valid() -> None:
    """F5 coverage, docstring rewritten round-3 against INTENDED behavior
    (not "pin what the code does today" -- a lock-in framing): a plant row
    that was genuinely seeded (plant_id set) but recorded neither a catch
    nor a miss (caught_by == missed_by == []) MUST validate, by design --
    e.g. a batch whose finder pass never actually exercised the seeded slot
    this cycle at all. That is real, honest telemetry about what happened,
    not an error condition, and the schema must never force a caller to
    fabricate a catch or miss that never occurred just to satisfy
    validation. Only the OPPOSITE direction is a real rule: a control
    (plant_id null) declaring a catch/miss is the actual defect (nothing
    was seeded in it to catch or miss), never the reverse. Paired with
    test_render_document_shows_a_seeded_but_never_exercised_plant_honestly
    in test_render_cycle_log.py, proving this valid shape still surfaces
    honestly on the operator page (BLOCKER 1, round-3) rather than
    silently vanishing or triggering the "No calibration plants seeded"
    fallback."""
    run = _calibration_run(caught_by=[], missed_by=[])
    record = _minimal_record(calibration_runs=[run])
    assert ct.validate_cycle(record) == []


def test_plant_catch_by_trade_gives_no_bucket_for_a_plant_with_empty_catches_and_misses() -> None:
    """F5/F4: the aggregator-side half of the same case -- a validly-typed
    but entirely empty plant row carries ZERO readable signal, so under the
    never-fabricate contract it gets no bucket at all, exactly like a trade
    nobody ever recorded anything about."""
    record = _minimal_record(calibration_runs=[_calibration_run(caught_by=[], missed_by=[])])
    assert ct.plant_catch_by_trade(record) == {}


@pytest.mark.parametrize("field", ["caught_by", "missed_by"])
@pytest.mark.parametrize("malformed", [7, 3.5, "abc"])
def test_plant_catch_by_trade_marks_malformed_caught_or_missed_by_as_unreadable(
    field: object, malformed: object
) -> None:
    """B2 (round-2 review): a PRESENT-but-malformed caught_by/missed_by (an
    int/float/bare-string instead of a list) must NEVER be silently coerced
    to "0 catches"/"0 misses" -- that would manufacture a confident, wrong
    catch rate from data that was never actually readable (the exact
    fabricated-innocence class B2 found in false_alarm_by_trade). It must
    increment `unreadable` and contribute nothing to caught/missed/rate."""
    rec = {"calibration_runs": [{"plant_id": "p1", "trade": "tile", field: malformed}]}
    result = ct.plant_catch_by_trade(rec)  # must not raise
    assert result == {"tile": {"caught": 0, "missed": 0, "unreadable": 1, "rate": None}}


@pytest.mark.parametrize("malformed", [7, 3.5, "abc"])
def test_false_alarm_by_trade_marks_malformed_false_alarm_finding_ids_as_unreadable(
    malformed: object,
) -> None:
    """B2 (round-2 review) -- FABRICATED INNOCENCE fix: a control row whose
    false_alarm_finding_ids is present-but-malformed must NOT increment
    `controls` (which used to silently read as "1 control, 0 alarms" -- the
    maximally trust-favorable, and wrong, reading of unreadable data on the
    exact 'false alarms on controls' metric the C1 trust proposal reads).
    It increments `unreadable` instead, so the bucket reads {controls: 0,
    unreadable: 1, rate: None} -- never a confident 0.0."""
    rec = {
        "calibration_runs": [
            {"plant_id": None, "trade": "tile", "false_alarm_finding_ids": malformed}
        ]
    }
    result = ct.false_alarm_by_trade(rec)  # must not raise
    assert result == {"tile": {"controls": 0, "false_alarms": 0, "unreadable": 1, "rate": None}}


def test_falsifiability_false_alarm_by_trade_would_fabricate_innocence_if_it_defaulted_to_empty() -> None:
    """Demonstrates the EXACT B2 defect directly: a naive implementation
    that coerces a malformed false_alarm_finding_ids to [] (the same
    `x if isinstance(x, list) else []` pattern used everywhere else in this
    module for a genuinely-absent field) would report a fabricated,
    trust-favorable 0.0 false-alarm rate. Show the real implementation does
    not do this -- it must report `rate: None`, not `rate: 0.0`."""
    malformed_control = {"plant_id": None, "trade": "tile", "false_alarm_finding_ids": "not-a-list"}

    def _naive_coerce(row: dict) -> list:
        v = row.get("false_alarm_finding_ids")
        return v if isinstance(v, list) else []  # the bug: silently "0 alarms"

    assert _naive_coerce(malformed_control) == []  # the bug's own reasoning: "0, so rate 0.0"
    real = ct.false_alarm_by_trade({"calibration_runs": [malformed_control]})
    assert real["tile"]["rate"] is None  # real: honestly unreadable, never a confident 0.0
    assert real["tile"]["controls"] == 0


# ---------------------------------------------------------------------------
# BLOCKER 4 (round-3 review, GH #4648) -- the plant_id/trade DISCRIMINATOR
# fields must never fail trust-favorably either. Round-2's B2 fix covered
# the DATA fields (caught_by/missed_by/false_alarm_finding_ids); round-3
# extends the same posture to the fields that decide which aggregator a row
# even belongs to.
# ---------------------------------------------------------------------------


def test_plant_catch_by_trade_routes_absent_plant_id_to_unreadable() -> None:
    """A row that never declares plant_id AT ALL is neither a confirmed
    plant nor a confirmed control -- `dict.get("plant_id")` alone can't
    distinguish "absent" from "present and null", and round-2's `is None`
    test collapsed them, silently reading an absent key as a real control
    (skipped from this aggregator with zero record it was ever seen)."""
    rec = {"calibration_runs": [{"trade": "tile", "caught_by": ["tile"], "missed_by": []}]}
    assert ct.plant_catch_by_trade(rec) == {"tile": {"caught": 0, "missed": 0, "unreadable": 1, "rate": None}}


def test_false_alarm_by_trade_routes_absent_plant_id_to_unreadable() -> None:
    """The mirror case: an absent plant_id used to be read as "not a plant,
    so it must be null" was never actually checked here either -- round-2's
    `is not None` test treated ANY non-None value (or, via .get()'s default,
    an absent key reading as None) inconsistently. Absent must never be
    read as a confident control with a real 0-alarm rate."""
    rec = {
        "calibration_runs": [
            {"trade": "tile", "false_alarm_finding_ids": ["f-1"]}
        ]
    }
    result = ct.false_alarm_by_trade(rec)
    assert result == {"tile": {"controls": 0, "false_alarms": 0, "unreadable": 1, "rate": None}}


def test_false_alarm_by_trade_routes_wrong_type_plant_id_to_unreadable_not_a_silent_plant() -> None:
    """THE exact BLOCKER 4 repro: a wrong-TYPE plant_id (an int, say) used
    to be read by `is not None` as "not null, so this must be a plant" --
    false_alarm_by_trade then silently skipped the row entirely, and its
    false_alarm_finding_ids (here, a real finding) vanished with NO record
    it was ever seen. It must surface as `unreadable` instead."""
    rec = {
        "calibration_runs": [
            {"plant_id": 42, "trade": "tile", "false_alarm_finding_ids": ["f-1"]}
        ]
    }
    result = ct.false_alarm_by_trade(rec)
    assert result == {"tile": {"controls": 0, "false_alarms": 0, "unreadable": 1, "rate": None}}
    assert result["tile"]["false_alarms"] == 0  # never silently "vanished" -- surfaced as unreadable


def test_plant_catch_by_trade_routes_wrong_type_plant_id_to_unreadable_not_a_silent_control() -> None:
    """The other aggregator's mirror: a wrong-TYPE plant_id used to be read
    by `is None` as False (since 42 is not None), which round-2's code
    treated as "this IS a plant" -- accidentally correct by luck for THIS
    aggregator's old boolean, but for the wrong reason (never actually
    checking the type), and still never surfaced as unreadable when it
    ALSO carried malformed catch data."""
    rec = {"calibration_runs": [{"plant_id": 42, "trade": "tile", "caught_by": ["tile"], "missed_by": []}]}
    result = ct.plant_catch_by_trade(rec)
    assert result == {"tile": {"caught": 0, "missed": 0, "unreadable": 1, "rate": None}}


def test_plant_catch_by_trade_routes_unattributable_trade_to_named_bucket() -> None:
    """A row with a genuinely bad `trade` (missing or non-string) used to be
    dropped silently with zero record it was ever seen -- it must be filed
    under the literal "(unattributable)" bucket key instead, never vanish."""
    rec = {"calibration_runs": [{"plant_id": "p1", "caught_by": ["tile"], "missed_by": []}]}  # no trade key
    result = ct.plant_catch_by_trade(rec)
    assert result == {"(unattributable)": {"caught": 1, "missed": 0, "unreadable": 0, "rate": 1.0}}


def test_false_alarm_by_trade_routes_unattributable_trade_to_named_bucket() -> None:
    rec = {"calibration_runs": [{"plant_id": None, "trade": 42, "false_alarm_finding_ids": ["f-1"]}]}
    result = ct.false_alarm_by_trade(rec)
    assert result == {"(unattributable)": {"controls": 1, "false_alarms": 1, "unreadable": 0, "rate": 1.0}}


def test_plant_catch_by_trade_never_crashes_on_non_dict_record() -> None:
    assert ct.plant_catch_by_trade([3, "abc", None]) == {}


def test_false_alarm_by_trade_never_crashes_on_non_dict_record() -> None:
    assert ct.false_alarm_by_trade([3, "abc", None]) == {}


@pytest.mark.parametrize("bad_runs", ["abc", 5, {"not": "a list"}])
def test_plant_catch_by_trade_never_crashes_on_non_list_calibration_runs_container(bad_runs) -> None:
    assert ct.plant_catch_by_trade({"calibration_runs": bad_runs}) == {}


@pytest.mark.parametrize("bad_runs", ["abc", 5, {"not": "a list"}])
def test_false_alarm_by_trade_never_crashes_on_non_list_calibration_runs_container(bad_runs) -> None:
    assert ct.false_alarm_by_trade({"calibration_runs": bad_runs}) == {}


def test_compute_metrics_includes_plant_catch_by_trade_and_false_alarm_by_trade() -> None:
    record = _minimal_record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            _control_run(trade="tile", false_alarm_finding_ids=["f-1"]),
        ]
    )
    metrics = ct.compute_metrics(record)
    assert metrics["plant_catch_by_trade"]["tile"]["caught"] == 1
    assert metrics["false_alarm_by_trade"]["tile"]["false_alarms"] == 1


def test_compute_metrics_trade_aggregators_are_empty_dicts_with_no_calibration_runs() -> None:
    metrics = ct.compute_metrics(_minimal_record())
    assert metrics["plant_catch_by_trade"] == {}
    assert metrics["false_alarm_by_trade"] == {}


def test_aggregate_metrics_empty_list_includes_trade_aggregator_keys() -> None:
    agg = ct.aggregate_metrics([])
    assert agg["plant_catch_by_trade"] == {}
    assert agg["false_alarm_by_trade"] == {}


def test_aggregate_metrics_pools_calibration_runs_trade_aggregators() -> None:
    a = _minimal_record(
        system="s",
        cycle_id="a",
        calibration_runs=[_calibration_run(trade="tile", caught_by=["tile"], missed_by=[])],
    )
    b = _minimal_record(
        system="s",
        cycle_id="b",
        calibration_runs=[_control_run(trade="tile", false_alarm_finding_ids=["f-1"])],
    )
    agg = ct.aggregate_metrics([a, b])
    assert agg["plant_catch_by_trade"]["tile"]["caught"] == 1
    assert agg["false_alarm_by_trade"]["tile"]["false_alarms"] == 1


def test_cli_metrics_single_file_renders_calibration_runs_trade_sections(tmp_path, capsys) -> None:
    """Renderer smoke test: the text (non-JSON) CLI branch must format both
    new aggregators the same way plant_catch_by_slot already is, not fall
    through to _fmt_metric's generic (dict-unaware) branch."""
    record = _minimal_record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            _control_run(trade="tile", false_alarm_finding_ids=["f-1"]),
        ]
    )
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    rc = ct.main(["metrics", str(path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "plant_catch_by_trade:" in out
    assert "trade tile: caught=1 missed=0 unreadable=0 rate=1.0000" in out
    assert "false_alarm_by_trade:" in out
    assert "trade tile: controls=1 false_alarms=1 unreadable=0 rate=1.0000" in out


def test_cli_metrics_single_file_json_includes_trade_aggregators(tmp_path, capsys) -> None:
    record = _minimal_record(
        calibration_runs=[_calibration_run(trade="tile", caught_by=["tile"], missed_by=[])]
    )
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    rc = ct.main(["metrics", str(path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["plant_catch_by_trade"]["tile"]["caught"] == 1


# ---------------------------------------------------------------------------
# Pricing / read_ledger_rows.
# ---------------------------------------------------------------------------


def test_load_pricing_missing_file_returns_empty_table(tmp_path) -> None:
    pricing = ct.load_pricing(str(tmp_path / "nope.json"))
    assert pricing["per_million_tokens"] == {}


def test_price_tokens_unknown_model_returns_none() -> None:
    pricing = {"per_million_tokens": {"claude-sonnet-5": {"input": 3.0, "output": 15.0}}}
    assert ct.price_tokens({"input": 1_000_000}, "totally-unknown-model", pricing) is None
    assert ct.price_tokens({"input": 1_000_000}, None, pricing) is None


def test_price_tokens_returns_none_when_tokens_is_missing_or_empty() -> None:
    """FALSIFY target -- BLOCKER 1: a matched, priced-model row with NO token
    data at all (tokens: null, or an empty {}) must never be silently priced
    at $0.00 -- that is indistinguishable, to a reader, from "this really did
    cost nothing." Real, live ledger: 48 rows have tokens: null/tokens_total:
    null, 9 of them a priced model (claude-sonnet-5)."""
    pricing = {"per_million_tokens": {"m": {"input": 3.0, "output": 15.0}}}
    assert ct.price_tokens(None, "m", pricing) is None
    assert ct.price_tokens({}, "m", pricing) is None
    # A row with buckets present but explicitly zero IS legitimately priced
    # at $0 -- that is real data, not missing data.
    assert ct.price_tokens({"input": 0, "output": 0}, "m", pricing) == 0.0


def test_price_tokens_computes_expected_dollar_amount() -> None:
    pricing = {
        "per_million_tokens": {
            "m": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75}
        }
    }
    tokens = {"input": 1_000_000, "output": 1_000_000, "cache_read": 1_000_000, "cache_creation": 1_000_000}
    assert ct.price_tokens(tokens, "m", pricing) == pytest.approx(3.0 + 15.0 + 0.3 + 3.75)


def test_read_ledger_rows_skips_malformed_lines_and_tolerates_missing_file(tmp_path) -> None:
    ledger = tmp_path / "spend.jsonl"
    ledger.write_text(
        '{"ts": "2026-08-27T14:00:00Z", "agent_type": "finder"}\n'
        "not json at all\n"
        "\n"
        '{"ts": "2026-08-27T14:05:00Z", "agent_type": "finder"}\n',
        encoding="utf-8",
    )
    rows = ct.read_ledger_rows(str(ledger))
    assert len(rows) == 2
    assert ct.read_ledger_rows(str(tmp_path / "does-not-exist.jsonl")) == []


def test_real_shipped_pricing_file_parses() -> None:
    pricing = ct.load_pricing()
    assert isinstance(pricing["per_million_tokens"], dict)
    assert "claude-sonnet-5" in pricing["per_million_tokens"]


# ---------------------------------------------------------------------------
# resolve_cost — the correspondence-checked ledger resolver. FALSIFY target:
# it must REFUSE a non-corresponding slice (wrong window / wrong type / count
# mismatch), never guess.
# ---------------------------------------------------------------------------


def _ledger_row(ts: str, agent_type: str, tokens_total: int = 1000, model: str = "m") -> dict:
    return {
        "ts": ts,
        "agent_type": agent_type,
        "model": model,
        "tokens": {"input": tokens_total, "output": 0, "cache_read": 0, "cache_creation": 0},
        "tokens_total": tokens_total,
    }


def _write_ledger(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "spend.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return str(path)


def _write_pricing(tmp_path, table: dict) -> str:
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps({"per_million_tokens": table}), encoding="utf-8")
    return str(path)


def test_resolve_cost_happy_path_matches_and_prices(tmp_path) -> None:
    """Post-BLOCKER-1 (round 3): a 'spend_ledger' verdict requires a
    uniformly-declared identity field across every dispatch -- see the
    module's resolve_cost docstring DESIGN DECISION. Both dispatches declare
    a tool_use_id and the corresponding ledger rows corroborate it."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="finder", tool_use_id="tu-finder-1"),
            _dispatch(agent_type="verifier", tool_use_id="tu-verifier-1"),
        ],
    )
    row_finder = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1_000_000, model="m")
    row_finder["tool_use_id"] = "tu-finder-1"
    row_verifier = _ledger_row("2026-08-27T14:20:00Z", "verifier", tokens_total=1_000_000, model="m")
    row_verifier["tool_use_id"] = "tu-verifier-1"
    ledger = _write_ledger(tmp_path, [row_finder, row_verifier])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] == 2_000_000
    assert result["total_usd"] == pytest.approx(6.0)
    assert result["matched_rows"] == 2


def test_resolve_cost_resolves_an_aa_0106_shaped_multi_scenario_batch_cycle(tmp_path) -> None:
    """AA-0106 falsifier (the audit's own acceptance bar): a cycle record
    shaped the CORRECT way -- one dispatches[] entry per REAL Task dispatch,
    each carrying its batch of scenarios in dispatches[].scenarios rather
    than being multiplied into one synthetic entry per scenario -- resolves
    to cost.source == 'spend_ledger' with a non-null total_usd.

    Mirrors the real defect exactly: 11 real dispatches (10 trades + 1 GC),
    each judging many scenarios in one Task call (16-36 scenarios per
    dispatch in the real round-22 record this reproduces the shape of).
    Before AA-0106's fix, the producer emitted 206 dispatches[] entries (one
    per scenario) all echoing these same 11 tool_use_ids -- resolve_cost()
    correctly refused that (declared identity count e.g. 36 vs. 1 real
    ledger row). This test proves the CORRECT shape (11 entries, each
    carrying its scenario list as data, never multiplied into the array)
    resolves cleanly."""
    judges_and_scenario_counts = [
        ("trade-plumbing", 36),
        ("trade-electrical", 18),
        ("trade-carpentry", 18),
        ("trade-site", 18),
        ("trade-tile", 17),
        ("trade-paint", 16),
        ("trade-drywall", 16),
        ("trade-flooring", 17),
        ("trade-hvac", 16),
        ("trade-demo", 18),
        ("general-contractor", 16),
    ]
    dispatches = []
    ledger_rows = []
    for i, (agent_type, n_scenarios) in enumerate(judges_and_scenario_counts):
        tool_use_id = f"toolu_{i:02d}"
        scenarios = [f"{agent_type}:scenario_{j}" for j in range(n_scenarios)]
        dispatches.append(
            _dispatch(
                agent_type=agent_type,
                label=f"{agent_type}:trade_round_22 ({n_scenarios} scenarios)",
                tool_use_id=tool_use_id,
                scenarios=scenarios,
                batch_size=len(judges_and_scenario_counts),
                batch_position=i + 1,
            )
        )
        row = _ledger_row("2026-09-07T12:00:00Z", agent_type, tokens_total=10_000, model="m")
        row["tool_use_id"] = tool_use_id
        ledger_rows.append(row)

    cycle = _minimal_record(
        system="estimate-loop",
        cycle_id="trade_round_22",
        started_at="2026-09-07T11:58:57Z",
        ended_at="2026-09-07T12:29:26Z",
        dispatches=dispatches,
    )
    # This record must itself be schema-valid -- the whole point of the fix
    # is that the CORRECT shape both validates and resolves.
    assert ct.validate_cycle(cycle) == []

    ledger = _write_ledger(tmp_path, ledger_rows)
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)

    assert result["source"] == "spend_ledger"
    assert result["matched_rows"] == 11
    assert result["total_tokens"] == 11 * 10_000
    assert result["total_usd"] is not None
    assert result["total_usd"] == pytest.approx(11 * 10_000 * 3.0 / 1_000_000)


def test_resolve_cost_refuses_the_pre_fix_one_entry_per_scenario_shape(tmp_path) -> None:
    """Companion negative case, same falsifiability pairing as the test
    above: the OLD (defective) shape -- one dispatches[] entry per scenario,
    all sharing the same real tool_use_id -- must still be refused. This is
    what proves the fix is the SHAPE change, not a resolve_cost() weakening;
    resolve_cost() itself is untouched by AA-0106 and must keep refusing
    this exact pattern."""
    tool_use_id = "toolu_plumbing_round22"
    n_scenarios = 36
    dispatches = [
        _dispatch(agent_type="trade-plumbing", tool_use_id=tool_use_id, label=f"plumbing:scenario_{j}")
        for j in range(n_scenarios)
    ]
    cycle = _minimal_record(
        started_at="2026-09-07T11:58:57Z",
        ended_at="2026-09-07T12:29:26Z",
        dispatches=dispatches,
    )
    row = _ledger_row("2026-09-07T12:00:00Z", "trade-plumbing", tokens_total=10_000, model="m")
    row["tool_use_id"] = tool_use_id
    ledger = _write_ledger(tmp_path, [row])  # only ONE real ledger row exists
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert "do not correspond 1:1" in result["reason"]


def test_resolve_cost_refuses_non_corresponding_slice_wrong_window(tmp_path) -> None:
    """FALSIFY target: a ledger row far outside the cycle's window must be
    refused, not silently attributed."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    ledger = _write_ledger(
        tmp_path,
        [_ledger_row("2026-08-27T20:00:00Z", "finder")],  # 5 hours after the window
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger, tolerance_sec=60)
    assert result["source"] == "unavailable"
    assert result["total_tokens"] is None
    assert result["total_usd"] is None
    assert "no ledger rows found" in result["reason"]


def test_resolve_cost_refuses_agent_type_the_cycle_never_dispatched(tmp_path) -> None:
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    ledger = _write_ledger(
        tmp_path,
        [_ledger_row("2026-08-27T14:30:00Z", "some-unrelated-concurrent-agent")],
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"


def test_resolve_cost_refuses_count_mismatch(tmp_path) -> None:
    """FALSIFY target: cycle dispatched 'finder' ONCE; ledger shows it TWICE
    in the window -- must refuse rather than guess which row is real."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            _ledger_row("2026-08-27T14:10:00Z", "finder"),
            _ledger_row("2026-08-27T14:20:00Z", "finder"),
        ],
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert "count" in result["reason"].lower()


def test_resolve_cost_honest_when_ledger_never_saw_this_run(tmp_path) -> None:
    """A real, expected case per the spawning task: the run's dispatches may
    not be in the ledger at all."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    empty_ledger = _write_ledger(tmp_path, [])
    result = ct.resolve_cost(cycle, ledger_path=empty_ledger)
    assert result["source"] == "unavailable"
    assert result["total_tokens"] is None and result["total_usd"] is None


def test_resolve_cost_refuses_when_ended_at_missing(tmp_path) -> None:
    cycle = _minimal_record(ended_at=None, dispatches=[_dispatch()])
    result = ct.resolve_cost(cycle, ledger_path=str(tmp_path / "nope.jsonl"))
    assert result["source"] == "unavailable"
    assert "in progress" in result["reason"]


def test_resolve_cost_refuses_when_no_dispatches() -> None:
    cycle = _minimal_record(dispatches=[])
    result = ct.resolve_cost(cycle)
    assert result["source"] == "unavailable"


def test_resolve_cost_withholds_total_usd_when_model_unpriced(tmp_path) -> None:
    """Post-BLOCKER-1 (round 3): declares tool_use_id, matched by the ledger
    row, since a 'spend_ledger' verdict now requires uniform identity."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "finder", model="not-in-pricing-table")
    row["tool_use_id"] = "tu-1"
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] == 1000
    assert result["total_usd"] is None
    assert result["unpriced_models"] == ["not-in-pricing-table"]
    # This exact result must itself be schema-valid (round-trippable via --write).
    assert ct.validate_cycle(_minimal_record(cost=result)) == []


def test_resolve_cost_withholds_total_usd_when_matched_row_has_no_tokens_object_at_all(tmp_path) -> None:
    """FALSIFY target -- BLOCKER 1, required combination-table case #1: (count
    matches, model priced, tokens object ABSENT). Must withhold total_usd
    with a reason, exactly like an unpriced model does -- never report a
    confident $0.00 'ground truth' figure. Post-BLOCKER-1 (round 3): declares
    tool_use_id, matched by the ledger row."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            {
                "ts": "2026-08-27T14:10:00Z",
                "agent_type": "finder",
                "model": "m",
                "tokens": None,
                "tokens_total": None,
                "tool_use_id": "tu-1",
            }
        ],
    )
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result["total_usd"] is None
    assert result["total_usd"] != 0.0
    assert result["total_tokens"] is None
    assert result["reason"]
    assert ct.validate_cycle(_minimal_record(cost=result)) == []


def test_resolve_cost_withholds_total_tokens_when_tokens_total_absent(tmp_path) -> None:
    """FALSIFY target -- BLOCKER 1, required combination-table case #2:
    (count matches, model priced, tokens_total ABSENT specifically, but the
    tokens breakdown IS present). total_usd is still derivable from the
    breakdown; total_tokens must be withheld with a reason regardless.
    Post-BLOCKER-1 (round 3): declares tool_use_id, matched by the ledger
    row."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            {
                "ts": "2026-08-27T14:10:00Z",
                "agent_type": "finder",
                "model": "m",
                "tokens": {"input": 100, "output": 50, "cache_read": 0, "cache_creation": 0},
                "tokens_total": None,
                "tool_use_id": "tu-1",
            }
        ],
    )
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] is None
    assert result["total_usd"] is not None
    assert result["reason"]
    assert ct.validate_cycle(_minimal_record(cost=result)) == []


# ---------------------------------------------------------------------------
# resolve_cost — identity-aware matching (BLOCKER 2). FALSIFY target: without
# a declared identity, a same-agent_type row from a completely different,
# concurrent session must never be silently attributed just because the
# window+type+count signals happen to line up.
# ---------------------------------------------------------------------------


def test_resolve_cost_refuses_a_stray_row_from_a_different_session_when_identity_declared(tmp_path) -> None:
    """The exact incident BLOCKER 2 reproduced: this cycle's one real
    dispatch never reached the ledger; one unrelated row of the SAME
    agent_type from a different session happens to sit in the window.
    Window+type+count alone (1 expected == 1 found) would have confidently
    resolved this to a real, but WRONG, dollar figure. Declaring the
    dispatch's own session must refuse instead."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", session="MY-REAL-SESSION")],
    )
    stray_row = _ledger_row("2026-08-27T14:10:00Z", "finder")
    stray_row["session"] = "SOME-OTHER-SESSION"
    ledger = _write_ledger(tmp_path, [stray_row])
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert "session" in result["reason"]


def test_resolve_cost_matches_by_tool_use_id_when_declared(tmp_path) -> None:
    """Happy path for identity-aware matching: a declared tool_use_id that
    DOES correspond to a real ledger row must still resolve normally (the fix
    must not make identity a strictly-stricter-than-useful gate)."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="toolu_real_one")],
    )
    real_row = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1_000_000, model="m")
    real_row["tool_use_id"] = "toolu_real_one"
    stray_row = _ledger_row("2026-08-27T14:12:00Z", "finder", tokens_total=999_999_999, model="m")
    stray_row["tool_use_id"] = "toolu_unrelated"
    ledger = _write_ledger(tmp_path, [real_row, stray_row])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] == 1_000_000  # the unrelated tool_use_id's huge total must be excluded
    assert result["matched_rows"] == 1


def test_resolve_cost_refuses_unconditionally_with_no_declared_identity(tmp_path) -> None:
    """#8 RENAME + REWRITE (round 4): this test used to be named
    ..._span_multiple_sessions and its docstring described the DELETED
    round-2 heuristic ("candidates span more than one distinct ledger
    session"). Its assertion (`"session" in result["reason"]`) passed only
    COINCIDENTALLY, because the *current* refusal reason string happens to
    contain the word "session" as part of naming the identity fields
    (tool_use_id/agent_id/session) -- the multi-session framing was never
    what the real code actually checks anymore, and was never load-bearing
    for this assertion even before the rename.

    What this test ACTUALLY verifies, post round-3 redesign: resolve_cost()
    refuses UNCONDITIONALLY whenever no dispatch in the cycle declares any
    identity field at all -- regardless of whether the window+type+count
    candidates happen to span multiple sessions or all share one. The
    companion test right below this one proves the "multiple sessions"
    framing was never the real mechanism, by getting the IDENTICAL refusal
    reason from a single-session variant of the same no-identity input."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder"), _dispatch(agent_type="finder")],
    )
    row_a = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000)
    row_a["session"] = "SESSION-A"
    row_b = _ledger_row("2026-08-27T14:20:00Z", "finder", tokens_total=2000)
    row_b["session"] = "SESSION-B"
    ledger = _write_ledger(tmp_path, [row_a, row_b])
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert result["reason"] == (
        "no dispatch in this cycle uniformly declares an identity field "
        "(tool_use_id/agent_id/session) -- window+type+count alone cannot prove true "
        "correspondence to ledger rows (a single foreign session is mathematically "
        "indistinguishable from a single own session under that heuristic), so "
        "resolve_cost refuses rather than guess which rows belong to this cycle"
    )


def test_resolve_cost_refuses_unconditionally_with_no_declared_identity_single_session_too(
    tmp_path,
) -> None:
    """#8 companion (round 4): byte-for-byte the same no-identity cycle and
    candidate shape as the test above, except BOTH ledger rows now share
    ONE session -- proving the "spans multiple sessions" framing was never
    the actual mechanism. If a multi-session check were real and separate
    from the unconditional no-identity refusal, this single-session variant
    would behave differently (e.g. accept, since old round-2 code accepted
    exactly this shape). It gets the IDENTICAL refusal reason instead,
    because resolve_cost() no longer looks at session-count ambiguity at
    all when no identity is declared -- it refuses outright either way."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder"), _dispatch(agent_type="finder")],
    )
    row_a = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000)
    row_a["session"] = "SESSION-A"
    row_b = _ledger_row("2026-08-27T14:20:00Z", "finder", tokens_total=2000)
    row_b["session"] = "SESSION-A"  # same session as row_a -- the only change from the test above
    ledger = _write_ledger(tmp_path, [row_a, row_b])
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert result["reason"] == (
        "no dispatch in this cycle uniformly declares an identity field "
        "(tool_use_id/agent_id/session) -- window+type+count alone cannot prove true "
        "correspondence to ledger rows (a single foreign session is mathematically "
        "indistinguishable from a single own session under that heuristic), so "
        "resolve_cost refuses rather than guess which rows belong to this cycle"
    )


def test_resolve_cost_accepts_when_declared_identity_matches_the_only_candidate(tmp_path) -> None:
    """#7 REWRITE (round 3): the original version of this test --
    test_resolve_cost_accepts_single_session_candidates_with_no_identity_declared
    -- asserted ACCEPTANCE for an input byte-for-byte indistinguishable from
    BLOCKER 1's foreign-session repro (a single session present, but never
    declared by the cycle, is not proof it is the cycle's OWN session). Once
    BLOCKER 1 is fixed there is no such thing as a verified 'no identity'
    acceptance any more -- declaring the cycle's own session, which the
    ledger's one candidate row corroborates, is what VERIFIED correspondence
    actually looks like. See the paired refusal test immediately below for
    the exact same shape with an UNDECLARED (foreign) single session."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", session="MY-OWN-SESSION")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000, model="m")
    row["session"] = "MY-OWN-SESSION"
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"


def test_resolve_cost_refuses_single_candidate_from_a_foreign_undeclared_session(tmp_path) -> None:
    """#7's paired refusal test (round 3) -- BLOCKER 1's exact recurring
    repro: a single candidate row in-window/in-type is mathematically
    indistinguishable from a real match unless correspondence is actually
    verified. This cycle declares NO identity at all, so even though the one
    candidate row happens to be the only session present, resolve_cost must
    refuse -- the old 'single session, so it must be mine' heuristic is gone."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000, model="m")
    row["session"] = "SOME-FOREIGN-SESSION"
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "unavailable"
    assert "identity" in result["reason"]


def test_resolve_cost_refuses_single_null_session_candidate_with_no_identity_declared(tmp_path) -> None:
    """FALSIFY target -- BLOCKER 1's measured real-ledger repro: 48% of real
    ledger rows carry session: null, which emptied the OLD sessions_seen
    guard regardless of true ambiguity (a null session was silently excluded
    from the set, so a single null-session candidate read as 'zero sessions
    seen', i.e. never ambiguous, i.e. confidently accepted). Must refuse
    exactly like a single NAMED foreign session must -- there is no ledger
    session value, null or otherwise, that can substitute for a declared
    identity."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000, model="m")
    row["session"] = None
    ledger = _write_ledger(tmp_path, [row])
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert "identity" in result["reason"]


def test_resolve_cost_refuses_when_one_dispatch_identity_mismatches_even_if_sibling_declares_none(
    tmp_path,
) -> None:
    """FALSIFY target -- BLOCKER 2's exact repro: dispatch A declares a
    tool_use_id present nowhere in the ledger (a real, provable mismatch);
    dispatch B declares nothing. The old code discarded A's mismatch signal
    entirely because _dispatch_identity_counts() required EVERY dispatch to
    declare identity before it would even look -- the mismatch must now
    refuse the WHOLE cycle regardless of B's silence."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="finder", tool_use_id="MINE-A"),
            _dispatch(agent_type="finder"),
        ],
    )
    row_a = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000)
    row_a["session"] = "FOREIGN-1"
    row_b = _ledger_row("2026-08-27T14:12:00Z", "finder", tokens_total=1000)
    row_b["session"] = "FOREIGN-2"
    ledger = _write_ledger(tmp_path, [row_a, row_b])
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert "MINE-A" in result["reason"]
    assert "tool_use_id" in result["reason"]


def test_resolve_cost_refuses_empty_string_identity_as_a_data_defect_not_absence(tmp_path) -> None:
    """BLOCKER 2's second door: an empty-string identity must never be
    silently treated as 'no identity declared' -- even when resolve_cost()
    is called directly on an unvalidated record (the CLI's resolve-cost
    subcommand never calls validate_cycle first)."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="finder", tool_use_id=""),
            _dispatch(agent_type="finder", tool_use_id="toolu_real"),
        ],
    )
    result = ct.resolve_cost(cycle, ledger_path=str(tmp_path / "nope.jsonl"))
    assert result["source"] == "unavailable"
    assert "empty string" in result["reason"]
    assert "data defect" in result["reason"]


# ---------------------------------------------------------------------------
# resolve_cost — BLOCKER 1 (round 4): a malformed ledger ROW field (not a
# malformed dispatch field -- that side was already guarded) must never
# reach a bare hash/equality/`in` check unguarded. resolve_cost()'s own
# docstring promises it NEVER raises; read_ledger_rows()'s stated threat
# model already tolerates line-level malformation (a shared JSONL mid-append
# by another process) -- field-level malformation inside an otherwise valid
# JSON line must degrade the same way (contribute nothing / count as a
# mismatch), never crash.
# ---------------------------------------------------------------------------


def test_resolve_cost_never_raises_on_a_malformed_agent_type_field(tmp_path) -> None:
    """Repro: row {"agent_type": ["sentinel"]} used to raise TypeError:
    unhashable type: 'list' at the `row.get("agent_type") not in
    expected_types` membership check (expected_types is a set)."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel")],
    )
    ledger = _write_ledger(
        tmp_path, [{"ts": "2026-08-27T14:10:00Z", "agent_type": ["sentinel"]}]
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger)  # must not raise
    assert result["source"] == "unavailable"


def test_resolve_cost_never_raises_on_a_malformed_tool_use_id_ledger_field(tmp_path) -> None:
    """Repro: a cycle whose dispatches uniformly declare tool_use_id "T1"
    (satisfied exactly by two legit matching rows), plus a THIRD candidate
    row in the same window/agent_type whose tool_use_id is a list -- this
    third row slips past the step-4a partial-mismatch check unnoticed
    (isinstance(v, str) guard there just skips it, contributing 0, which
    doesn't disturb an already-exact match) and used to reach the final
    identity-narrowing line unguarded: `row.get(identity_field) in
    identity_counts` raised TypeError: unhashable type: 'list'."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="sentinel", tool_use_id="T1"),
            _dispatch(agent_type="sentinel", tool_use_id="T1"),
        ],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tool_use_id": "T1"},
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tool_use_id": "T1"},
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tool_use_id": ["other"]},
        ],
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger)  # must not raise
    assert result["source"] == "spend_ledger"
    assert result["matched_rows"] == 2  # the malformed 3rd row is excluded, never counted


def test_resolve_cost_never_raises_on_a_malformed_session_ledger_field(tmp_path) -> None:
    """Same shape as the tool_use_id repro above, but this time SESSION is
    the resolved identity_field (dispatches declare only session, never
    tool_use_id/agent_id, so session is the field that actually reaches the
    final narrowing line), and the malformed extra candidate row's session
    value is a dict (calibration/session data occasionally lands as a
    nested object by operator error) rather than a list -- both are equally
    unhashable at `row.get(identity_field) in identity_counts`."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="sentinel", session="S1"),
            _dispatch(agent_type="sentinel", session="S1"),
        ],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "session": "S1"},
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "session": "S1"},
            {"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "session": {"a": 1}},
        ],
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger)  # must not raise
    assert result["source"] == "spend_ledger"
    assert result["matched_rows"] == 2


# ---------------------------------------------------------------------------
# resolve_cost — tolerance_sec must be bounded (BLOCKER 2's third ask): a
# negative or unbounded tolerance directly widens the cross-session risk
# above.
# ---------------------------------------------------------------------------


def test_resolve_cost_refuses_negative_tolerance_sec() -> None:
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z", ended_at="2026-08-27T15:00:00Z", dispatches=[_dispatch()]
    )
    result = ct.resolve_cost(cycle, tolerance_sec=-1.0)
    assert result["source"] == "unavailable"
    assert "tolerance_sec" in result["reason"]


def test_resolve_cost_refuses_unbounded_tolerance_sec() -> None:
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z", ended_at="2026-08-27T15:00:00Z", dispatches=[_dispatch()]
    )
    result = ct.resolve_cost(cycle, tolerance_sec=ct.MAX_LEDGER_TOLERANCE_SEC + 1)
    assert result["source"] == "unavailable"
    assert "tolerance_sec" in result["reason"]


def test_resolve_cost_accepts_min_tolerance_sec_boundary(tmp_path) -> None:
    """#8: paired boundary-ACCEPTANCE test for the negative-tolerance
    refusal above -- MIN_LEDGER_TOLERANCE_SEC itself (the boundary value)
    must be accepted, not just values below it refused."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    row = _ledger_row("2026-08-27T14:30:00Z", "finder", tokens_total=1000, model="m")
    row["tool_use_id"] = "tu-1"
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(
        cycle, ledger_path=ledger, pricing_path=pricing, tolerance_sec=ct.MIN_LEDGER_TOLERANCE_SEC
    )
    assert result["source"] == "spend_ledger"


def test_resolve_cost_accepts_max_tolerance_sec_boundary(tmp_path) -> None:
    """#8: paired boundary-ACCEPTANCE test for the unbounded-tolerance
    refusal above -- MAX_LEDGER_TOLERANCE_SEC itself (the boundary value)
    must be accepted, not just values above it refused. The row sits inside
    the window only because of the full MAX tolerance being applied."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    row = _ledger_row("2026-08-27T15:59:00Z", "finder", tokens_total=1000, model="m")
    row["tool_use_id"] = "tu-1"
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(
        cycle, ledger_path=ledger, pricing_path=pricing, tolerance_sec=ct.MAX_LEDGER_TOLERANCE_SEC
    )
    assert result["source"] == "spend_ledger"


def test_cli_resolve_cost_rejects_negative_tolerance_sec(tmp_path) -> None:
    cycle = _minimal_record(dispatches=[_dispatch()])
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(cycle), encoding="utf-8")
    rc = ct.main(["resolve-cost", str(path), "--tolerance-sec", "-5"])
    assert rc == 2


def test_cli_resolve_cost_rejects_unbounded_tolerance_sec(tmp_path) -> None:
    cycle = _minimal_record(dispatches=[_dispatch()])
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(cycle), encoding="utf-8")
    rc = ct.main(["resolve-cost", str(path), "--tolerance-sec", "999999999"])
    assert rc == 2


def test_resolve_cost_result_is_always_schema_valid_as_a_cost_block(tmp_path) -> None:
    """Every branch of resolve_cost must produce something write_cycle() can
    actually persist without a second, separate stripping step."""
    scenarios = []
    cycle_no_dispatch = _minimal_record(dispatches=[])
    scenarios.append(ct.resolve_cost(cycle_no_dispatch))
    cycle_in_progress = _minimal_record(ended_at=None, dispatches=[_dispatch()])
    scenarios.append(ct.resolve_cost(cycle_in_progress, ledger_path=str(tmp_path / "x.jsonl")))
    cycle_no_match = _minimal_record(dispatches=[_dispatch(agent_type="finder")])
    scenarios.append(ct.resolve_cost(cycle_no_match, ledger_path=str(_write_ledger(tmp_path, []))))
    for cost_block in scenarios:
        assert ct.validate_cycle(_minimal_record(cost=cost_block)) == []


def test_real_shared_ledger_is_readable_if_present() -> None:
    """Structural sanity against the REAL, live, shared spend ledger --
    read-only, tolerant of it being empty/absent/actively growing (other
    agents may be appending concurrently), never asserting exact contents."""
    rows = ct.read_ledger_rows()  # default path: the real ~/.claude/.agent_budget/spend.jsonl
    for row in rows[:50]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def test_cli_validate_reports_pass_for_good_file(tmp_path, capsys) -> None:
    path = tmp_path / "good.json"
    path.write_text(json.dumps(_minimal_record()), encoding="utf-8")
    rc = ct.main(["validate", str(path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS" in out


def test_cli_validate_reports_fail_for_bad_file(tmp_path, capsys) -> None:
    record = _minimal_record()
    del record["notes"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    rc = ct.main(["validate", str(path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "notes" in out


def test_cli_validate_json_output(tmp_path, capsys) -> None:
    path = tmp_path / "good.json"
    path.write_text(json.dumps(_minimal_record()), encoding="utf-8")
    rc = ct.main(["validate", str(path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload[0]["valid"] is True


def test_cli_summarize_over_a_cycles_dir(tmp_path, capsys) -> None:
    cycles_dir = str(tmp_path / "cycles")
    ct.write_cycle(_minimal_record(system="loopz", cycle_id="c1"), cycles_dir=cycles_dir)
    rc = ct.main(["summarize", "--system", "loopz", "--cycles-dir", cycles_dir, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload[0]["system"] == "loopz"


def test_cli_metrics_single_file_json(tmp_path, capsys) -> None:
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(_minimal_record(findings=[_finding()])), encoding="utf-8")
    rc = ct.main(["metrics", str(path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["symptom_precision"] == 1.0


def test_cli_resolve_cost_write_persists_result(tmp_path) -> None:
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(cycle), encoding="utf-8")
    empty_ledger = _write_ledger(tmp_path, [])
    rc = ct.main(["resolve-cost", str(path), "--ledger", empty_ledger, "--write"])
    assert rc == 3  # honestly unavailable
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["cost"]["source"] == "unavailable"


def test_cli_resolve_cost_write_is_atomic_never_leaves_a_truncated_file(tmp_path, monkeypatch) -> None:
    """BLOCKER 3, part (b) (round 4): the CLI's resolve-cost --write path
    used to open the target path directly and write into it in place --
    a process killed mid-write (e.g. on a multibyte character) left a
    truncated, invalid-UTF-8 file on disk, which is EXACTLY the input that
    used to blank render_cycle_log.py's whole report (part (a) of this same
    blocker). Verify it now goes through the same temp-file + os.replace
    pattern write_cycle() already uses: simulate an interrupted write via
    monkeypatch and confirm the ORIGINAL file is left completely untouched
    (never partially overwritten), proving the write is atomic.

    Round 12, nit #7: this test used to assert that a stray, never-renamed
    temp file was LEFT BEHIND as its proof that a separate temp path (not
    `path` itself) was used. That was true before nit #7's fix added a
    `try/finally: os.unlink(tmp_path)` cleanup to this exact atomic-write
    pattern -- now the interrupted write's temp file is cleaned up rather
    than orphaned, so this test's proof mechanism changes: a wrapped
    `open()` captures the actual path written to (still proving a SEPARATE
    temp path was used, matching write_cycle()'s own `f"{path}.tmp-..."`
    naming), and a new assertion confirms no stray temp file is left on
    disk afterward -- the airtight-cleanup behavior nit #7 added."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder")],
    )
    path = tmp_path / "cycle.json"
    original_bytes = json.dumps(cycle).encode("utf-8")
    path.write_bytes(original_bytes)
    empty_ledger = _write_ledger(tmp_path, [])

    class _SimulatedKill(Exception):
        pass

    real_dump = json.dump

    def _flaky_dump(obj: object, fh: object, **kwargs: object) -> None:
        fh.write('{"schema_version": 2, "system": "l')  # partial write, then die
        raise _SimulatedKill("simulated process kill mid-write")

    real_open = open
    opened_paths: list[str] = []

    def _tracking_open(file: object, *args: object, **kwargs: object) -> object:
        opened_paths.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(json, "dump", _flaky_dump)
    monkeypatch.setattr("builtins.open", _tracking_open)
    try:
        with pytest.raises(_SimulatedKill):
            ct.main(["resolve-cost", str(path), "--ledger", empty_ledger, "--write"])
    finally:
        monkeypatch.setattr(json, "dump", real_dump)
        monkeypatch.setattr("builtins.open", real_open)

    # The ORIGINAL file must be completely untouched -- a non-atomic
    # in-place write would have left it truncated to the partial bytes
    # above; an atomic temp-file+os.replace write never touches it at all
    # until the replace, which the simulated kill happens before this test
    # ever lets it run.
    assert path.read_bytes() == original_bytes
    # The write really did go through a SEPARATE temp path (matching
    # write_cycle()'s own `f"{path}.tmp-..."` pattern) rather than opening
    # `path` itself directly -- captured via the wrapped `open()` above,
    # since the temp file itself is no longer left on disk to inspect
    # after nit #7's cleanup fix.
    tmp_opens = [p for p in opened_paths if p.startswith(str(path)) and ".tmp-" in p]
    assert len(tmp_opens) == 1, f"expected exactly one temp-path open, found {tmp_opens}"
    # And nit #7's cleanup actually fired: no stray temp file left behind.
    tmp_siblings = [p for p in tmp_path.iterdir() if p.name.startswith("cycle.json.tmp-")]
    assert tmp_siblings == [], f"expected the interrupted write's temp file to be cleaned up, found {tmp_siblings}"


def test_cli_unknown_subcommand_exits_2(capsys) -> None:
    rc = ct.main(["not-a-real-subcommand"])
    assert rc == 2


def test_cli_help_exits_0(capsys) -> None:
    rc = ct.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "cycle_telemetry" in out


def test_cli_validate_needs_a_target_raises_usage_error(capsys) -> None:
    rc = ct.main(["validate"])
    assert rc == 2


# ---------------------------------------------------------------------------
# Falsifiability — show these actually catch real defects, not just pass
# vacuously. Each test mutates a KNOWN-BAD value and shows the specific
# assertion an unfalsified/stubbed implementation would have missed.
# ---------------------------------------------------------------------------


def test_falsifiability_symptom_precision_distinguishes_from_cause_precision(sample_record: dict) -> None:
    """A broken implementation that (bug!) computed cause_precision using the
    SAME formula as symptom_precision would report 8/9 for both. Prove the
    real implementation does not collapse to that."""
    broken_cause_precision = ct.symptom_precision(sample_record)  # the bug under test
    real_cause_precision = ct.cause_precision(sample_record)
    assert real_cause_precision != pytest.approx(broken_cause_precision)
    assert real_cause_precision == pytest.approx(1 / 9)


def test_falsifiability_duplicate_rate_would_be_wrong_if_it_counted_all_findings(
    sample_record: dict,
) -> None:
    """A broken implementation that (bug!) always returned 1.0 (treating
    every finding as a duplicate) must be caught by the exact-value assertion
    -- not a loose 'is not None' check."""
    broken_always_all = 1.0
    real = ct.duplicate_rate(sample_record)
    assert real != pytest.approx(broken_always_all)
    assert real == pytest.approx(2 / 9)


def test_falsifiability_validate_cycle_would_pass_a_broken_stub(tmp_path) -> None:
    """Demonstrates the failure mode a real validator must NOT have: a stub
    validator that always returns [] (valid) would let a completely broken
    record reach write_cycle(). Show the real validator does not do this."""

    def _always_valid_stub(_record: object) -> list[str]:
        return []

    garbage = {"nonsense": True}
    assert _always_valid_stub(garbage) == []  # the bug: stub says "fine"
    assert ct.validate_cycle(garbage) != []  # the real implementation: not fine


def test_falsifiability_resolve_cost_would_be_wrong_if_it_ignored_count(tmp_path) -> None:
    """Demonstrates the exact bug the correspondence check exists to prevent:
    a resolver that only checked window+type (not count/identity) would
    happily sum BOTH duplicate rows below and report a (wrong, inflated)
    cost instead of refusing. Confirm the real resolver refuses instead.
    Round 3: the dispatch declares its own tool_use_id (required for a
    'spend_ledger' verdict post-BLOCKER-1) and BOTH ledger rows carry that
    same identity -- a duplicated identity is exactly as much of a
    correspondence violation as a duplicated window+type count was."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="dup-id")],  # cycle dispatched it ONCE
    )
    row_1 = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=1000)
    row_1["tool_use_id"] = "dup-id"
    row_2 = _ledger_row("2026-08-27T14:20:00Z", "finder", tokens_total=1000)
    row_2["tool_use_id"] = "dup-id"
    ledger = _write_ledger(tmp_path, [row_1, row_2])
    # The naive (buggy) window+type-only sum a lesser implementation would
    # have reported:
    naive_sum = 2000
    result = ct.resolve_cost(cycle, ledger_path=ledger)
    assert result["source"] == "unavailable"
    assert result.get("total_tokens") != naive_sum
    assert result["total_tokens"] is None


# ---------------------------------------------------------------------------
# ROUND 6 -- systematic `X or []` / `X or {}` truthiness bug (BLOCKER 2),
# its container-level twins (BLOCKERS 3/4/5), NaN/Infinity in the cost
# pipeline (BLOCKER 7), non-UTF-8 files reaching the CLI unguarded
# (BLOCKER 8), and falsifying 3 prior-round fixes that had zero test
# coverage (BLOCKER 6). Every case here was confirmed to genuinely crash
# (or silently misbehave) against the specific pre-fix production code
# before the corresponding fix was written -- see the round's scratch
# falsifiability harness for the RED-before-GREEN evidence this suite
# encodes as permanent regression tests.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_symptom_precision_never_crashes_on_malformed_findings_container(malformed) -> None:
    """BLOCKER 2 (round 6): `record.get("findings") or []` is truthy for a
    nonzero number or a non-empty string, letting a malformed scalar
    `findings` value straight through to `for f in findings: f.get(...)`."""
    assert ct.symptom_precision({"findings": malformed}) is None


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_cause_precision_never_crashes_on_malformed_findings_container(malformed) -> None:
    assert ct.cause_precision({"findings": malformed}) is None


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_duplicate_rate_never_crashes_on_malformed_findings_container(malformed) -> None:
    assert ct.duplicate_rate({"findings": malformed}) is None


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_ruling_conflict_rate_never_crashes_on_malformed_findings_container(malformed) -> None:
    assert ct.ruling_conflict_rate({"findings": malformed}) is None


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_consolidation_ratio_never_crashes_on_malformed_findings_container(malformed) -> None:
    """Distinct from the raised_by-item guard below: this is the findings
    CONTAINER itself (record["findings"]), not one finding's raised_by."""
    assert ct.consolidation_ratio({"findings": malformed}) is None


@pytest.mark.parametrize("bad_cost", [3, 3.5, "abcdef", True], ids=["int", "float", "str", "bool"])
def test_usd_per_confirmed_defect_never_crashes_on_malformed_cost_container(bad_cost) -> None:
    assert ct.usd_per_confirmed_defect({"cost": bad_cost, "findings": [_finding()]}) is None


@pytest.mark.parametrize(
    "malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"]
)
def test_usd_per_confirmed_defect_never_crashes_on_malformed_findings_container(malformed) -> None:
    rec = {"cost": {"total_usd": 10.0}, "findings": malformed}
    assert ct.usd_per_confirmed_defect(rec) is None


@pytest.mark.parametrize("bad_table", [3, 3.5, "abcdef", True], ids=["int", "float", "str", "bool"])
def test_price_tokens_never_crashes_on_malformed_per_million_tokens_container(bad_table) -> None:
    assert ct.price_tokens({"input": 100}, "claude", {"per_million_tokens": bad_table}) is None


@pytest.mark.parametrize("bad_pricing", [3, 3.5, "abcdef", None], ids=["int", "float", "str", "none"])
def test_price_tokens_never_crashes_on_malformed_pricing_argument_itself(bad_pricing) -> None:
    assert ct.price_tokens({"input": 100}, "claude", bad_pricing) is None


def test_aggregate_metrics_never_crashes_on_malformed_findings_containers() -> None:
    """BLOCKER 2 (round 6): aggregate_metrics' own `r.get("findings") or []`
    pooling loop, distinct from the per-record functions above."""
    records = [
        {"findings": 3.5},
        {"findings": "abc"},
        {"findings": [_finding(finding_id="f1", verifier_verdict="CONFIRMED")]},
    ]
    agg = ct.aggregate_metrics(records)
    assert agg["finding_count"] == 1


@pytest.mark.parametrize("bad_cost", [3, 3.5, "abcdef", True], ids=["int", "float", "str", "bool"])
def test_aggregate_metrics_never_crashes_on_malformed_cost_container(bad_cost) -> None:
    records = [{"cost": bad_cost, "findings": []}]
    agg = ct.aggregate_metrics(records)
    assert agg["cost_known_cycles"] == 0
    assert agg["cost_unknown_cycles"] == 1


@pytest.mark.parametrize("bad_record", [3, 3.5, "abcdef", None, [1, 2, 3]])
def test_aggregate_metrics_never_crashes_when_a_record_itself_is_not_a_dict(bad_record) -> None:
    """BLOCKER 4b (round 6): aggregate_metrics is called directly (not only
    via read_cycles), including by tests and by render_cycle_log.py, with
    whatever list of "records" a caller hands it -- a non-dict element must
    never crash the pooling loop."""
    agg = ct.aggregate_metrics([bad_record])
    assert agg["cycle_count"] == 1
    assert agg["finding_count"] == 0


@pytest.mark.parametrize("bad_dispatches", [3, 3.5, "abcdef", {}], ids=["int", "float", "str", "dict"])
def test_cli_summarize_never_crashes_on_malformed_dispatches_or_findings(tmp_path, bad_dispatches, capsys) -> None:
    """BLOCKER 2/4 (round 6): _cmd_summarize's row-building loop used the
    same `X.get(field) or []` pattern on dispatches/findings."""
    cycles_dir = tmp_path / "cycles" / "loop"
    cycles_dir.mkdir(parents=True)
    (cycles_dir / "c1.json").write_text(
        json.dumps({"schema_version": 1, "system": "loop", "cycle_id": "c1", "dispatches": bad_dispatches, "findings": 3}),
        encoding="utf-8",
    )
    rc = ct.main(["summarize", "--system", "loop", "--cycles-dir", str(tmp_path / "cycles"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload[0]["dispatch_count"] == 0
    assert payload[0]["finding_count"] == 0


# ---------------------------------------------------------------------------
# BLOCKER 3 (round 6) -- plant_catch_by_slot's calibration CONTAINER.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_calibration", ["abc", 5, [1]], ids=["str", "int", "list"])
def test_plant_catch_by_slot_never_crashes_on_non_dict_calibration_container(bad_calibration) -> None:
    """Distinct from the round-4 fix for calibration.caught_by/missed_by
    (the INNER fields): here the whole `calibration` value itself is not a
    dict at all, so `cal.get("plant_id")` used to crash with AttributeError
    before this ever reached the already-fixed inner-field guards."""
    result = ct.plant_catch_by_slot({"calibration": bad_calibration})
    assert result == {}


def test_plant_catch_by_slot_never_crashes_on_non_dict_record() -> None:
    result = ct.plant_catch_by_slot([3, "abc", None])
    assert result == {}


# ---------------------------------------------------------------------------
# BLOCKER 4 (round 6) -- read_cycles() must exclude a non-dict top-level
# JSON value from its returned list entirely, and every metric/summarize
# path must survive it too.
# ---------------------------------------------------------------------------


def test_read_cycles_excludes_a_non_dict_top_level_json_value(tmp_path) -> None:
    cycles_dir = tmp_path / "cycles" / "loop"
    cycles_dir.mkdir(parents=True)
    (cycles_dir / "good.json").write_text(json.dumps(_minimal_record(system="loop", cycle_id="good")), encoding="utf-8")
    (cycles_dir / "bad_list.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    (cycles_dir / "bad_scalar.json").write_text(json.dumps(42), encoding="utf-8")
    records = ct.read_cycles("loop", cycles_dir=str(tmp_path / "cycles"), on_error="skip")
    assert len(records) == 1
    assert records[0]["cycle_id"] == "good"


def test_read_cycles_raises_on_non_dict_top_level_value_when_on_error_raise(tmp_path) -> None:
    cycles_dir = tmp_path / "cycles" / "loop"
    cycles_dir.mkdir(parents=True)
    (cycles_dir / "bad.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        ct.read_cycles("loop", cycles_dir=str(tmp_path / "cycles"))


def test_cli_metrics_system_survives_a_bad_top_level_list_file(tmp_path, capsys) -> None:
    cycles_dir = tmp_path / "cycles" / "loop"
    cycles_dir.mkdir(parents=True)
    (cycles_dir / "good.json").write_text(
        json.dumps(_minimal_record(system="loop", cycle_id="good", findings=[_finding(verifier_verdict="CONFIRMED")])),
        encoding="utf-8",
    )
    (cycles_dir / "bad.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    rc = ct.main(["metrics", "--system", "loop", "--cycles-dir", str(tmp_path / "cycles"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["symptom_precision"] is None or isinstance(payload["symptom_precision"], float)


def test_cli_metrics_single_file_survives_malformed_calibration_and_findings(tmp_path, capsys) -> None:
    """BLOCKER 4's two single-file crash shapes: calibration: 'none' and
    findings: {'x': {}}, exercised through the real `metrics <path>` CLI."""
    path = tmp_path / "rec1.json"
    path.write_text(json.dumps({"schema_version": 1, "calibration": "none", "findings": []}), encoding="utf-8")
    rc = ct.main(["metrics", str(path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plant_catch_by_slot"] == {}

    path2 = tmp_path / "rec2.json"
    path2.write_text(json.dumps({"schema_version": 1, "findings": {"x": {}}}), encoding="utf-8")
    rc2 = ct.main(["metrics", str(path2), "--json"])
    assert rc2 == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["symptom_precision"] is None


# ---------------------------------------------------------------------------
# BLOCKER 5 (round 6) -- resolve_cost's dispatches CONTAINER (distinct from
# the round-4 fix for a malformed dispatch ITEM inside an otherwise-valid
# list, covered separately below under BLOCKER 6).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_dispatches", [3, 3.5, "abcdef", {}], ids=["int", "float", "str", "dict"])
def test_resolve_cost_never_raises_on_a_non_list_dispatches_container(bad_dispatches) -> None:
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=bad_dispatches,
    )
    result = ct.resolve_cost(cycle)  # must not raise
    assert result["source"] == "unavailable"


# ---------------------------------------------------------------------------
# BLOCKER 6 (round 6) -- 3 prior-round production fixes with ZERO test
# coverage, falsified against a reverted copy in the round's scratch
# harness before being locked in here. Two of the three live here
# (consolidation_ratio's raised_by guard, resolve_cost's dispatch-item
# guard); the third (render_cycle_log.py's normalize_record calibration
# coercion) is a render_cycle_log.py-owned function and lives in
# hooks/tests/test_render_cycle_log.py instead, to keep each module's
# tests in its own file.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("malformed", [3, 3.5, "abcdef", None, {}], ids=["int", "float", "str", "none", "dict"])
def test_consolidation_ratio_never_crashes_or_miscounts_on_malformed_raised_by(malformed) -> None:
    """Round 4's flagship fix (the isinstance(raised_by, list) guard) had
    ZERO test coverage until this round -- proven by reverting it in a
    scratch copy and confirming the full suite still passed. Every
    malformed value must contribute exactly 0 to the count; the specific
    failure mode this guards against is NOT just "does it crash" but "does
    it silently MISCOUNT" -- a naive `len(str_value)` fix would pass a
    crash-only test while still fabricating len("abcdef") == 6 raisers out
    of a single malformed string. Two independent findings, each with a
    distinct raised_by, isolate the contribution of each malformed value
    (a shared-findings-list version could hide a wrong-but-nonzero
    contribution inside a coincidentally-correct total)."""
    record = _minimal_record(
        findings=[
            _finding(finding_id="f1", raised_by=malformed),
            _finding(finding_id="f2", raised_by=["real-raiser"]),
        ]
    )
    # f2 alone contributes 1 raiser over 2 findings; if f1's malformed
    # raised_by contributed ANYTHING other than 0 (crash, or a silent
    # len()-of-characters miscount), this would not equal 0.5.
    assert ct.consolidation_ratio(record) == pytest.approx(0.5)


@pytest.mark.parametrize("bad_item", [3, "abc", None, 3.5], ids=["int", "str", "none", "float"])
def test_resolve_cost_never_raises_on_a_non_dict_dispatch_item(bad_item) -> None:
    """Distinct from BLOCKER 5's dispatches CONTAINER guard above: here the
    container IS a list, but one ITEM inside it is not a dict. This is the
    round-4 guard at the expected_counts-building loop
    (`d.get("agent_type") if isinstance(d, dict) else None`) -- also had
    ZERO test coverage until this round."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[bad_item, _dispatch(agent_type="sentinel")],
    )
    result = ct.resolve_cost(cycle)  # must not raise
    assert result["source"] == "unavailable"


# ---------------------------------------------------------------------------
# BLOCKER 7 (round 6) -- NaN/Infinity JSON constants in the cost pipeline:
# both crash one path and fabricate a confident "$inf" figure in another.
# ---------------------------------------------------------------------------


def test_is_number_rejects_nan_and_infinity() -> None:
    assert ct._is_number(float("nan")) is False
    assert ct._is_number(float("inf")) is False
    assert ct._is_number(float("-inf")) is False
    assert ct._is_number(1.5) is True
    assert ct._is_number(0) is True


def test_read_ledger_rows_skips_a_line_carrying_a_nan_token_count(tmp_path) -> None:
    """json.loads accepts a bare NaN/Infinity token by default even though
    neither is valid JSON -- read_ledger_rows' own docstring promises
    malformed lines are 'skipped, never raised'; a NaN/Infinity value must
    be treated the same as any other malformed line, not silently parsed
    into a non-finite float that a later consumer trusts."""
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tokens_total": NaN}\n'
        + json.dumps(_ledger_row("2026-08-27T14:10:00Z", "sentinel")) + "\n",
        encoding="utf-8",
    )
    rows = ct.read_ledger_rows(str(path))  # must not raise
    assert len(rows) == 1
    assert rows[0]["agent_type"] == "sentinel"
    assert "tokens_total" not in rows[0] or rows[0].get("tokens_total") != float("nan")


def test_read_ledger_rows_skips_a_line_carrying_an_infinity_value(tmp_path) -> None:
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tokens": {"input": Infinity}}\n',
        encoding="utf-8",
    )
    rows = ct.read_ledger_rows(str(path))  # must not raise
    assert rows == []


def test_resolve_cost_never_raises_on_a_nan_tokens_total_ledger_row(tmp_path) -> None:
    """Repro: a matched ledger row's tokens_total is NaN -- int(nan) used to
    raise ValueError. resolve_cost's own docstring promises correspondence
    checking, never a crash on malformed ledger data."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="tu-1")],
    )
    ledger_path = tmp_path / "spend.jsonl"
    ledger_path.write_text(
        '{"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tool_use_id": "tu-1", '
        '"tokens_total": NaN, "model": "m", "tokens": {"input": 100, "output": 0, '
        '"cache_read": 0, "cache_creation": 0}}\n',
        encoding="utf-8",
    )
    result = ct.resolve_cost(cycle, ledger_path=str(ledger_path))  # must not raise
    assert result["source"] == "unavailable"


def test_resolve_cost_never_fabricates_an_infinite_dollar_figure_from_an_infinity_token_count(tmp_path) -> None:
    """Repro: a matched ledger row's `tokens.input` is Infinity, and the
    model IS priced (a real pricing table entry, so price_tokens() actually
    reaches the multiplication step instead of bailing out early on an
    unknown model) -- resolve_cost used to happily return {'total_usd':
    inf, 'source': 'spend_ledger'} (validate_cycle() would then even PASS
    it, and a renderer would display "$inf ... ground truth"). Never a
    confident fabricated figure for malformed data -- withhold pricing
    instead."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="tu-1")],
    )
    ledger_path = tmp_path / "spend.jsonl"
    ledger_path.write_text(
        '{"ts": "2026-08-27T14:10:00Z", "agent_type": "sentinel", "tool_use_id": "tu-1", '
        '"tokens_total": 100, "model": "m", "tokens": {"input": Infinity, "output": 0, '
        '"cache_read": 0, "cache_creation": 0}}\n',
        encoding="utf-8",
    )
    pricing_path = _write_pricing(tmp_path, {"m": {"input": 3.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    result = ct.resolve_cost(cycle, ledger_path=str(ledger_path), pricing_path=pricing_path)  # must not raise
    total_usd = result.get("total_usd")
    assert not (isinstance(total_usd, float) and math.isinf(total_usd))
    assert result["source"] != "spend_ledger" or total_usd is None


def test_validate_cost_rejects_a_non_finite_total_usd() -> None:
    """_is_number()'s finiteness fix also closes validate_cycle()'s own
    door: a hand-edited record with total_usd=Infinity must fail
    validation, never pass through as a valid cost block."""
    errs = ct._validate_cost({"source": "spend_ledger", "total_tokens": 100, "total_usd": float("inf")})
    assert errs


# ---------------------------------------------------------------------------
# BLOCKER 8 (round 6) -- cycle_telemetry.py's OWN CLI (metrics, resolve-cost)
# must not crash on a non-UTF-8 file the same way render_cycle_log.py's
# renderer was already fixed to handle.
# ---------------------------------------------------------------------------


def _write_non_utf8_file(tmp_path) -> str:
    path = tmp_path / "bad.json"
    path.write_bytes(b'{"schema_version": 1, "system": "\xff\xfebad"}')
    return str(path)


def test_cli_metrics_reports_clean_error_on_non_utf8_file(tmp_path, capsys) -> None:
    path = _write_non_utf8_file(tmp_path)
    rc = ct.main(["metrics", path])  # must not raise
    assert rc == 1
    err = capsys.readouterr().err
    assert "failed to read" in err


def test_cli_resolve_cost_reports_clean_error_on_non_utf8_file(tmp_path, capsys) -> None:
    path = _write_non_utf8_file(tmp_path)
    rc = ct.main(["resolve-cost", path])  # must not raise
    assert rc == 1
    err = capsys.readouterr().err
    assert "failed to read" in err


def test_main_outer_except_tuple_catches_unicodedecodeerror_even_without_a_per_command_wrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UnicodeDecodeError is a ValueError subclass, NOT an OSError --
    confirm main()'s own OUTER safety net (not just the per-command wraps
    in _cmd_metrics/_cmd_resolve_cost) actually names it, by simulating a
    handler that raises it directly without any try/except of its own --
    exactly the gap a future new subcommand could reintroduce if it forgot
    to mirror _cmd_validate's per-file wrap pattern."""

    def _boom(argv: list[str]) -> int:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "simulated")

    monkeypatch.setattr(ct, "_cmd_metrics", _boom, raising=True)
    rc = ct.main(["metrics", "whatever"])  # must not raise
    assert rc == 1


# ---------------------------------------------------------------------------
# ROUND 8 -- meta-pattern: "fixed on one side, never swept the mirror."
# Reviewer's diagnosis: round 6 fixed one side of 3 symmetric pairs and never
# checked the structurally-identical other side. Fixes below consolidate
# into SHARED guarded helpers (is_finite_number, _in_enum) used by both
# sides of each pair, rather than more point patches.
# ---------------------------------------------------------------------------

# --- BLOCKER 1: finiteness must hold through the FULL pipeline, not just
# the top-level _is_number check -- overflow-during-computation, and a
# present-but-non-finite bucket silently zeroed instead of flagged unpriced.


def test_is_finite_number_is_the_shared_implementation_is_number_delegates_to() -> None:
    """Round 8: _is_number is now an alias for the public is_finite_number,
    not a second implementation -- this is what makes it possible for
    render_cycle_log.py to import and call the SAME function instead of
    re-implementing the check (which is exactly how round 6's fix ended up
    on only one side)."""
    assert ct._is_number is ct.is_finite_number
    assert ct.is_finite_number(float("nan")) is False
    assert ct.is_finite_number(float("inf")) is False
    assert ct.is_finite_number(float("-inf")) is False
    assert ct.is_finite_number(1.5) is True
    assert ct.is_finite_number(0) is True
    assert ct.is_finite_number(True) is False  # bool excluded, like every other numeric guard here


def test_price_tokens_refuses_rather_than_zeroes_a_present_non_finite_bucket() -> None:
    """Repro: tokens.input is NaN (present, numeric type, but not finite).
    The OLD behavior (`amt = amt if _is_number(amt) else 0`) silently
    zeroed this bucket and still priced the REST of the row as a confident
    figure -- dropping real (if malformed) usage on the floor without any
    signal. Round 8: a present-but-non-finite bucket makes the whole row
    unpriceable (None), the same as an unknown model, so the caller's
    existing unpriced_models bookkeeping catches it."""
    pricing = {"per_million_tokens": {"m": {"input": 1.0, "output": 1.0}}}
    priced = ct.price_tokens({"input": float("nan"), "output": 100}, "m", pricing)
    assert priced is None


def test_price_tokens_refuses_when_a_single_buckets_product_overflows_to_infinity() -> None:
    """Repro (the reviewer's exact scenario): an extreme-but-FINITE token
    count (amt=1e308, individually finite) times a FINITE rate (100,
    individually finite) overflows to +inf during Python's own float
    multiplication -- 'individual inputs finite, the computation is not'.
    Round 6's parse_constant guard only rejects the 3 literal JSON tokens
    NaN/Infinity/-Infinity; it can never catch overflow-through-arithmetic,
    since 1e308 parses as an ordinary finite-looking JSON number. price_tokens
    must assert finiteness on its OWN computed total before returning it."""
    pricing = {"per_million_tokens": {"m": {"input": 100.0, "output": 1.0}}}
    priced = ct.price_tokens({"input": 1e308, "output": 0}, "m", pricing)
    assert priced is None, "an extreme token count must never price as a confident dollar figure"


def test_resolve_cost_refuses_when_the_accumulated_total_overflows_across_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repro: EVERY individual matched row prices as a finite figure (each
    price_tokens() call returns a large-but-finite value), yet SUMMING them
    across rows overflows total_usd to +inf. price_tokens() being internally
    correct is not sufficient -- resolve_cost's own accumulation loop must
    also assert finiteness on the value it actually returns. Monkeypatched
    at the price_tokens() call site (white-box) since forcing two
    individually-finite-but-near-float-max price_tokens() results through
    the real amt*rate/1e6 formula is not reachable with realistic
    ledger/pricing magnitudes (the formula's own /1e6 keeps any single
    row's real output far below the threshold where TWO of them would
    overflow) -- this isolates resolve_cost's cross-row accumulation guard
    from price_tokens' own internal correctness, which is covered above."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[
            _dispatch(agent_type="sentinel", tool_use_id="tu-0"),
            _dispatch(agent_type="sentinel", tool_use_id="tu-1"),
        ],
    )
    ledger_path = _write_ledger(
        tmp_path,
        [
            {
                "ts": "2026-08-27T14:10:00Z",
                "agent_type": "sentinel",
                "tool_use_id": "tu-0",
                "model": "m",
                "tokens_total": 100,
                "tokens": {"input": 100, "output": 0, "cache_read": 0, "cache_creation": 0},
            },
            {
                "ts": "2026-08-27T14:11:00Z",
                "agent_type": "sentinel",
                "tool_use_id": "tu-1",
                "model": "m",
                "tokens_total": 100,
                "tokens": {"input": 100, "output": 0, "cache_read": 0, "cache_creation": 0},
            },
        ],
    )
    pricing_path = _write_pricing(tmp_path, {"m": {"input": 1.0, "output": 0, "cache_read": 0, "cache_creation": 0}})
    monkeypatch.setattr(ct, "price_tokens", lambda tokens, model, pricing: 1.6e308, raising=True)
    result = ct.resolve_cost(cycle, ledger_path=ledger_path, pricing_path=pricing_path)
    assert result["total_usd"] is None
    assert "overflowed" in result.get("reason", "")


def test_read_cycle_singular_rejects_a_non_finite_json_constant(tmp_path) -> None:
    """Mirror of read_ledger_rows'/read_cycles' own guard, applied to the
    SINGULAR read_cycle() too -- round 8's audit finding: read_cycle (one
    record) and read_cycles (many records) are exactly the "process one vs
    process many" pattern shape the reviewer flagged; the multi-file loader
    already had this guard, the singular one did not."""
    cycles_dir = tmp_path / "cycles"
    sys_dir = cycles_dir / "loop"
    sys_dir.mkdir(parents=True)
    (sys_dir / "c1.json").write_text('{"schema_version": 1, "total_usd": Infinity}', encoding="utf-8")
    with pytest.raises(ValueError):
        ct.read_cycle("loop", "c1", cycles_dir=str(cycles_dir))


def test_load_pricing_degrades_cleanly_on_a_non_finite_json_constant(tmp_path) -> None:
    path = tmp_path / "pricing.json"
    path.write_text('{"per_million_tokens": {"m": {"input": Infinity}}}', encoding="utf-8")
    table = ct.load_pricing(str(path))  # must not raise
    assert table["per_million_tokens"] == {}


def test_cmd_metrics_single_file_rejects_a_non_finite_json_constant(tmp_path, capsys) -> None:
    path = tmp_path / "rec.json"
    path.write_text('{"schema_version": 1, "total_usd": NaN}', encoding="utf-8")
    rc = ct.main(["metrics", str(path)])  # must not raise
    assert rc == 1
    assert "failed to read" in capsys.readouterr().err


# --- BLOCKER 2: an unhashable value at an enum-membership test must never
# crash validate_cycle() -- 10 sites, all now routed through _in_enum(), plus
# resolve_cost()'s dispatch-side agent_type mirror of the already-fixed
# ledger-row-side check.


@pytest.mark.parametrize(
    "field_path,bad_value",
    [
        ("dispatches", {"tokens_source": {"nested": "dict"}}),
        ("findings", {"consolidator_decision": ["a", "list"]}),
        ("findings", {"verifier_verdict": {"a": 1}}),
        ("findings", {"found_at_stage": ["x"]}),
        ("cost", {"source": {"a": 1}}),
        ("reviews_finding", {"severity": {"a": 1}}),
        ("reviews", {"outcome": ["a"]}),
        ("verdicts", {"verdict": {"a": 1}}),
        ("stages", {"status": ["a"]}),
        ("top", {"schema_version": {"a": 1}}),
    ],
    ids=[
        "dispatch.tokens_source",
        "finding.consolidator_decision",
        "finding.verifier_verdict",
        "finding.found_at_stage",
        "cost.source",
        "review_finding.severity",
        "review.outcome",
        "verdict.verdict",
        "stage.status",
        "top.schema_version",
    ],
)
def test_validate_cycle_never_crashes_on_an_unhashable_enum_field(field_path: str, bad_value: dict) -> None:
    """Repro for each of the 10 audited `X not in <set>` enum-membership
    checks in validate_cycle()'s helper tree: a dict/list value at that
    field used to raise `TypeError: unhashable type` instead of a clean
    validation error, breaking validate_cycle()'s own documented "never
    raises" contract. Every site now routes through the shared _in_enum()
    helper. Each case builds the SMALLEST record shape that reaches the
    given field."""
    record = _minimal_record()
    key, bad_field_value = next(iter(bad_value.items()))
    if field_path == "dispatches":
        record["dispatches"] = [_dispatch(**{key: bad_field_value})]
    elif field_path == "findings":
        record["findings"] = [_finding(**{key: bad_field_value})]
    elif field_path == "cost":
        record["cost"] = {**record["cost"], key: bad_field_value}
    elif field_path == "reviews_finding":
        record["reviews"] = [{"findings": [{key: bad_field_value}]}]
    elif field_path == "reviews":
        record["reviews"] = [{key: bad_field_value}]
    elif field_path == "verdicts":
        record["verdicts"] = [{key: bad_field_value}]
    elif field_path == "stages":
        record["stages"] = [{key: bad_field_value}]
    elif field_path == "top":
        record[key] = bad_field_value

    errs = ct.validate_cycle(record)  # must not raise
    assert errs, "a malformed enum value must produce a validation error, not silently pass"


def test_in_enum_helper_matches_the_normalize_record_pattern() -> None:
    assert ct._in_enum(1, {1, 2}) is True
    assert ct._in_enum("x", {"x", "y"}) is True
    assert ct._in_enum({"a": 1}, {"x", "y"}) is False
    assert ct._in_enum(["a"], {"x", "y"}) is False
    assert ct._in_enum(None, {"x", "y"}) is False


def test_resolve_cost_dispatch_side_agent_type_mirrors_the_ledger_row_side_guard() -> None:
    """Repro: dispatches[0].agent_type is a dict -- `at` was only checked
    for truthiness (`if at:`) before being used as a dict key
    (`expected_counts[at]`), so a non-empty dict/list agent_type crashed
    with `TypeError: unhashable type`. This is the EXACT MIRROR of the
    ledger-row-side `row_agent_type` check a few lines below in the same
    function, which was already correctly isinstance(str)-guarded (with 3
    dedicated tests) -- this is the dispatch side of that same function,
    never checked until round 8."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[{"agent_type": {"nested": "dict"}}],
    )
    result = ct.resolve_cost(cycle)  # must not raise
    assert result["source"] == "unavailable"


# --- BLOCKER 3: a CLI command must never crash on a non-dict top-level
# record -- the single-file path was never checked for the identical hazard
# round 6 fixed only on the --system (multi-file) path, and read_cycles'
# own sort key crashed on mixed-type started_at OUTSIDE its per-file
# try/except.


def test_cmd_metrics_single_file_survives_a_bad_top_level_list_file(tmp_path, capsys) -> None:
    """The single-file mirror of the ALREADY-EXISTING
    test_cli_metrics_system_survives_a_bad_top_level_list_file -- proof this
    exact test shape was written for one CLI path and never duplicated for
    the other."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    rc = ct.main(["metrics", str(path)])  # must not raise
    assert rc == 1
    assert "not a JSON object" in capsys.readouterr().err


def test_cmd_resolve_cost_single_file_survives_a_bad_top_level_scalar_file(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps("just a string"), encoding="utf-8")
    rc = ct.main(["resolve-cost", str(path)])  # must not raise
    assert rc == 1
    assert "not a JSON object" in capsys.readouterr().err


def test_read_cycles_does_not_crash_on_mixed_type_started_at_across_files(tmp_path) -> None:
    """Repro: two files under one system, one with started_at=5 (a truthy
    non-string) and one with a real string timestamp. The OLD sort key
    (`r.get("started_at") or ""`) only falls back on a FALSY value, so `5`
    passed straight through and crashed list.sort() with a str-vs-int
    TypeError OUTSIDE the per-file try/except that on_error="skip" is
    supposed to protect -- both summarize --cycles-dir and metrics --system
    crashed uncaught despite round 6's claimed fix for non-dict record
    exclusion (a different bug at a different line)."""
    sys_dir = tmp_path / "cycles" / "loop"
    sys_dir.mkdir(parents=True)
    (sys_dir / "c1.json").write_text(
        json.dumps(_minimal_record(cycle_id="c1", started_at=5)), encoding="utf-8"
    )
    (sys_dir / "c2.json").write_text(
        json.dumps(_minimal_record(cycle_id="c2", started_at="2026-08-27T14:00:00Z")), encoding="utf-8"
    )
    records = ct.read_cycles(None, cycles_dir=str(tmp_path / "cycles"), on_error="skip")  # must not raise
    assert {r["cycle_id"] for r in records} == {"c1", "c2"}


def test_cli_metrics_system_survives_mixed_type_started_at(tmp_path, capsys) -> None:
    """Same defect, exercised through the real `metrics --system` CLI
    entrypoint rather than calling read_cycles() directly."""
    sys_dir = tmp_path / "cycles" / "loop"
    sys_dir.mkdir(parents=True)
    (sys_dir / "c1.json").write_text(
        json.dumps(_minimal_record(cycle_id="c1", started_at=5)), encoding="utf-8"
    )
    (sys_dir / "c2.json").write_text(
        json.dumps(_minimal_record(cycle_id="c2", started_at="2026-08-27T14:00:00Z")), encoding="utf-8"
    )
    rc = ct.main(["metrics", "--system", "loop", "--cycles-dir", str(tmp_path / "cycles"), "--json"])
    assert rc == 0
    capsys.readouterr()


# --- Finding #8: iter_cycle_paths must tolerate an unreadable directory.


def test_iter_cycle_paths_tolerates_an_unreadable_system_directory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable subdirectory (PermissionError from os.listdir) must
    degrade to 'no files found there', not crash the whole scan -- every
    caller of iter_cycle_paths() (read_cycles, list_systems's sibling
    scans) assumes this same per-file/per-dir tolerance already given to a
    broken file."""
    base = tmp_path / "cycles"
    (base / "sysA").mkdir(parents=True)
    (base / "sysA" / "c1.json").write_text(json.dumps(_minimal_record()), encoding="utf-8")

    real_listdir = os.listdir

    def _boom(path: str) -> list[str]:
        if str(path).endswith("sysA"):
            raise PermissionError("simulated: cannot list sysA")
        return real_listdir(path)

    monkeypatch.setattr(ct.os, "listdir", _boom, raising=True)
    paths = ct.iter_cycle_paths(cycles_dir=str(base))  # must not raise
    assert paths == []


# --- Finding #9: a nested-list/dict calibration slot renders readably.


def test_plant_catch_by_slot_renders_a_nested_list_slot_readably() -> None:
    record = _minimal_record(
        calibration={
            "plant_id": "p1",
            "planted_in": "dispatch-1",
            "slot": None,
            "caught_by": [[1, 2]],
            "missed_by": [],
        }
    )
    out = ct.plant_catch_by_slot(record)
    assert list(out.keys()) == ["[1,2]"]


# ---------------------------------------------------------------------------
# Round 10.
# ---------------------------------------------------------------------------

# --- BLOCKER 1: price_tokens must refuse a PRESENT-but-wrong-TYPE bucket
# and a PRESENT-but-garbage rate, not just a present-but-non-finite NUMBER
# (round 8 only fixed the latter).


def test_price_tokens_refuses_a_present_string_typed_token_bucket() -> None:
    """Exact repro: a hand-edited ledger row with `tokens.output` as a
    STRING ("2000000") instead of a number. The OLD code's `else: amt =
    0.0` branch silently zeroed this bucket and still priced the REST of
    the row as a confident $3.00 (when the honest total, had output been
    read, is $33.00) -- an understated 'ground truth' figure, not a
    refusal."""
    pricing = {"per_million_tokens": {"m": {"input": 3.0, "output": 15.0}}}
    priced = ct.price_tokens({"input": 1_000_000, "output": "2000000"}, "m", pricing)
    assert priced is None


def test_price_tokens_refuses_a_present_list_typed_token_bucket() -> None:
    pricing = {"per_million_tokens": {"m": {"input": 1.0, "output": 1.0}}}
    priced = ct.price_tokens({"input": [1, 2], "output": 100}, "m", pricing)
    assert priced is None


def test_price_tokens_refuses_a_present_dict_typed_token_bucket() -> None:
    pricing = {"per_million_tokens": {"m": {"input": 1.0, "output": 1.0}}}
    priced = ct.price_tokens({"input": {"x": 1}, "output": 100}, "m", pricing)
    assert priced is None


def test_price_tokens_refuses_a_present_string_typed_pricing_rate() -> None:
    """Exact repro (the LIVE pricing.json vector): a single string typo in
    the operator-editable pricing table (`"cache_read": "0.3"` instead of
    `0.3`) used to silently zero that bucket's contribution rather than
    refusing the whole row -- a real ledger row shape (input 606, output
    85571, cache_read 42680592, cache_creation 419214) undercounts by 82%
    ($15.66 -> $2.86) while still being labelled 'priced from the spend
    ledger (ground truth)'."""
    pricing = {
        "per_million_tokens": {
            "m": {"input": 3.0, "output": 15.0, "cache_read": "0.3", "cache_creation": 1.5}
        }
    }
    tokens = {"input": 606, "output": 85571, "cache_read": 42680592, "cache_creation": 419214}
    priced = ct.price_tokens(tokens, "m", pricing)
    assert priced is None, "a string-typo'd rate must refuse the whole row, never silently zero it"


def test_price_tokens_refuses_an_explicit_none_pricing_rate() -> None:
    """Round 12, BLOCKER 4: this test's NAME has always asserted refusal,
    but its assertion used to lock in the OPPOSITE (wrong) behavior --
    `priced == pytest.approx(3.0)`, i.e. the row WAS priced, directly
    contradicting both the test's own name and `price_tokens`'s docstring,
    which has claimed refusal for an explicit `null` rate since round 10.
    An operator writing `"cache_read": null` into pricing.json (plausible
    when they don't yet know a rate) used to get back a confident dollar
    figure labeled "priced from the spend ledger (ground truth)" that
    silently EXCLUDED that entire token bucket's contribution -- verified
    live: 5,000,000 cache-read tokens at an explicit `null` rate silently
    zeroed out, row still priced at $0.033 instead of refused. A rate
    explicitly present as `null` is NOT the same as the key being
    genuinely absent (which correctly still defaults to 0 -- there is no
    data there to refuse, see the sibling "genuinely absent" test below) --
    `null` is a malformed/incomplete rate, exactly like a string-typo'd
    rate, and must refuse the whole row the same way."""
    pricing = {"per_million_tokens": {"m": {"input": 3.0, "output": None}}}
    priced = ct.price_tokens({"input": 1_000_000, "output": 100}, "m", pricing)
    assert priced is None, "an explicit null rate must refuse the whole row, never silently zero it"


def test_price_tokens_refuses_a_non_finite_pricing_rate() -> None:
    pricing = {"per_million_tokens": {"m": {"input": 3.0, "output": float("nan")}}}
    priced = ct.price_tokens({"input": 1_000_000, "output": 100}, "m", pricing)
    assert priced is None


def test_price_tokens_still_defaults_a_genuinely_absent_bucket_or_rate_to_zero() -> None:
    """Unchanged contract: a key that is genuinely ABSENT (never recorded,
    as opposed to present-but-garbage) still defaults to 0 on both the
    token-bucket side and the pricing-rate side -- there is no data there
    to refuse, so this is not the same failure mode as blocker 1."""
    pricing = {"per_million_tokens": {"m": {"input": 3.0}}}  # no "output" rate at all
    priced = ct.price_tokens({"input": 1_000_000}, "m", pricing)  # no "output" bucket at all
    assert priced == pytest.approx(3.0)


def test_resolve_cost_end_to_end_refuses_the_live_pricing_json_typo_vector(
    tmp_path,
) -> None:
    """End-to-end falsification of the reviewer's exact live vector through
    resolve_cost() itself (not just price_tokens() in isolation): a single
    string-typo'd rate in pricing.json must make resolve_cost() report the
    model as unpriced (total_usd withheld, with a reason), never a
    confident-but-wrong dollar figure."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="finder", tool_use_id="tu-1")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "finder", tokens_total=128797783, model="m")
    row["tool_use_id"] = "tu-1"
    row["tokens"] = {
        "input": 606,
        "output": 85571,
        "cache_read": 42680592,
        "cache_creation": 419214,
    }
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(
        tmp_path,
        {"m": {"input": 3.0, "output": 15.0, "cache_read": "0.3", "cache_creation": 1.5}},
    )
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["total_usd"] is None
    assert "m" in result.get("unpriced_models", [])
    assert result.get("reason")


# --- BLOCKER 2 (render_cycle_log's reviews sort key) is tested in
# test_render_cycle_log.py, the renderer's own test file.

# --- Finding #8: iter_cycle_paths's structural twin, list_systems, must
# tolerate an unreadable directory the same way.


def test_list_systems_tolerates_an_unreadable_cycles_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "cycles"
    base.mkdir()
    (base / "sysA").mkdir()

    real_listdir = os.listdir

    def _boom(path: str) -> list[str]:
        if os.path.abspath(str(path)) == os.path.abspath(str(base)):
            raise PermissionError("simulated: cannot list cycles dir")
        return real_listdir(path)

    monkeypatch.setattr(ct.os, "listdir", _boom, raising=True)
    assert ct.list_systems(cycles_dir=str(base)) == []  # must not raise


# --- BLOCKER 3: aggregate_metrics's own cross-record sum must be
# finiteness-checked, the sibling of price_tokens/resolve_cost/rollup_cost's
# already-guarded accumulators.


def test_aggregate_metrics_withholds_usd_per_confirmed_defect_if_the_pooled_sum_overflows() -> None:
    """Repro: two records that write_cycle() itself validates and persists
    cleanly (each total_usd=1e308, individually finite) -- summing them
    across records overflows to +inf. Must render as None, never a
    confident 'inf' ratio."""
    a = _minimal_record(
        system="s", cycle_id="a",
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": 1e308},
        findings=[_finding(finding_id="f1", verifier_verdict="CONFIRMED")],
    )
    b = _minimal_record(
        system="s", cycle_id="b",
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": 1e308},
        findings=[_finding(finding_id="f2", verifier_verdict="CONFIRMED")],
    )
    # Confirm these are genuinely persistable/valid records, matching the
    # reviewer's exact repro framing ("records write_cycle() itself
    # validates and persists cleanly").
    assert ct.validate_cycle(a) == []
    assert ct.validate_cycle(b) == []
    agg = ct.aggregate_metrics([a, b])
    assert agg["usd_per_confirmed_defect"] is None


def test_cli_metrics_system_never_prints_a_bare_inf_or_infinity_on_overflow(
    tmp_path, capsys
) -> None:
    """End-to-end CLI falsification of BLOCKER 3 (and BLOCKER 4's printer
    hardening): `metrics --system` over two persisted, individually-valid
    records whose total_usd sum overflows must never print a bare
    'inf'/'Infinity' -- text mode reads a clear placeholder, and JSON mode
    is still valid, parseable JSON."""
    cycles_dir = str(tmp_path / "cycles")
    for i in range(2):
        ct.write_cycle(
            _minimal_record(
                system="sys1",
                cycle_id=f"c{i}",
                cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": 1e308},
                findings=[_finding(finding_id=f"f{i}", verifier_verdict="CONFIRMED")],
            ),
            cycles_dir=cycles_dir,
        )
    rc = ct.main(["metrics", "--system", "sys1", "--cycles-dir", cycles_dir])
    out = capsys.readouterr().out
    assert rc == 0
    assert "inf" not in out.lower().split("usd_per_confirmed_defect:")[1].split("\n")[0]
    assert "usd_per_confirmed_defect: n/a" in out or "usd_per_confirmed_defect: invalid data" in out

    rc2 = ct.main(["metrics", "--system", "sys1", "--cycles-dir", cycles_dir, "--json"])
    payload_text = capsys.readouterr().out
    assert rc2 == 0
    payload = json.loads(payload_text)  # must be valid JSON -- no bare Infinity token
    assert payload["usd_per_confirmed_defect"] is None


# --- BLOCKER 4: the JSON parse boundary must also reject an overflowing
# float LITERAL (e.g. 1e999), not just the 3 bare NaN/Infinity/-Infinity
# constant tokens; and summarize must not print a bare inf/Infinity.


def test_reject_non_finite_json_float_raises_on_an_overflowing_literal() -> None:
    with pytest.raises(ValueError):
        ct.reject_non_finite_json_float("1e999")


def test_reject_non_finite_json_float_accepts_an_ordinary_finite_literal() -> None:
    assert ct.reject_non_finite_json_float("1.5") == 1.5
    assert ct.reject_non_finite_json_float("1e100") == 1e100


def test_json_loads_with_only_parse_constant_lets_an_overflowing_literal_through() -> None:
    """Documents the exact gap BLOCKER 4 closes: `parse_constant` ALONE
    (round 8's guard) does not fire for an ordinary-looking numeric literal
    that overflows during normal float parsing."""
    parsed = json.loads('{"total_usd": 1e999}', parse_constant=ct.reject_non_finite_json_constant)
    assert parsed["total_usd"] == float("inf")


def test_read_cycle_rejects_a_file_with_an_overflowing_float_literal(tmp_path) -> None:
    path = ct.write_cycle(_minimal_record(system="s", cycle_id="c1"), cycles_dir=str(tmp_path))
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace('"total_usd": null', '"total_usd": 1e999')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    with pytest.raises(ValueError):
        ct.read_cycle("s", "c1", cycles_dir=str(tmp_path))


def test_read_cycles_skips_a_file_with_an_overflowing_float_literal_via_on_error_skip(
    tmp_path,
) -> None:
    cycles_dir = tmp_path / "cycles"
    good_path = ct.write_cycle(_minimal_record(system="s", cycle_id="good"), cycles_dir=str(cycles_dir))
    bad_path = cycles_dir / "s" / "bad.json"
    bad_path.write_text(
        json.dumps(_minimal_record(system="s", cycle_id="bad")).replace(
            '"total_usd": null', '"total_usd": 1e999'
        ),
        encoding="utf-8",
    )
    records = ct.read_cycles("s", cycles_dir=str(cycles_dir), on_error="skip")
    assert len(records) == 1
    assert records[0]["cycle_id"] == "good"
    assert good_path  # sanity: helper actually wrote the good file


def test_read_ledger_rows_skips_a_line_with_an_overflowing_float_literal(tmp_path) -> None:
    ledger_path = tmp_path / "spend.jsonl"
    good = {"timestamp": "2026-08-27T14:00:00Z", "agent_type": "finder", "model": "m"}
    bad_line = '{"timestamp": "2026-08-27T14:00:00Z", "total_usd": 1e999}'
    ledger_path.write_text(json.dumps(good) + "\n" + bad_line + "\n", encoding="utf-8")
    rows = ct.read_ledger_rows(str(ledger_path))
    assert len(rows) == 1
    assert rows[0] == good


def test_load_pricing_rejects_a_file_with_an_overflowing_float_literal(tmp_path) -> None:
    """load_pricing()'s own except-Exception fallback (a malformed file ->
    the honest 'no pricing data' default) must catch a 1e999 literal too,
    now that the parse boundary raises for it."""
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text('{"per_million_tokens": {"m": {"input": 1e999}}}', encoding="utf-8")
    pricing = ct.load_pricing(str(pricing_path))
    assert pricing == {"version": None, "currency": "usd", "per_million_tokens": {}}


def test_cli_summarize_reports_clean_output_instead_of_bare_inf_or_infinity(
    tmp_path, capsys
) -> None:
    """Exact repro from the reviewer: `summarize --system sysZ` used to
    print `cost=spend_ledger:inf` (text) and `"total_usd": Infinity`
    (json, not even valid JSON) for a record whose total_usd overflowed.
    Now that the parse boundary itself rejects the overflowing literal,
    the record is excluded entirely by read_cycles' on_error="skip" -- the
    honest 'no cycle records found', never a confident inf."""
    cycles_dir = tmp_path / "cycles"
    (cycles_dir / "sysZ").mkdir(parents=True)
    bad_path = cycles_dir / "sysZ" / "c1.json"
    bad_path.write_text(
        json.dumps(_minimal_record(system="sysZ", cycle_id="c1")).replace(
            '"total_usd": null',
            '"total_usd": 1e999',
        ),
        encoding="utf-8",
    )
    rc = ct.main(["summarize", "--system", "sysZ", "--cycles-dir", str(cycles_dir)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "inf" not in out.lower()

    rc2 = ct.main(["summarize", "--system", "sysZ", "--cycles-dir", str(cycles_dir), "--json"])
    payload_text = capsys.readouterr().out
    assert rc2 == 0
    payload = json.loads(payload_text)  # must be valid JSON
    assert payload == []


def test_fmt_metric_reports_invalid_data_for_a_non_finite_float() -> None:
    assert ct._fmt_metric(float("inf")) == "invalid data"
    assert ct._fmt_metric(float("nan")) == "invalid data"
    assert ct._fmt_metric(float("-inf")) == "invalid data"
    assert ct._fmt_metric(1.5) == "1.5000"
    assert ct._fmt_metric(None) == "n/a"


def test_write_cycle_refuses_to_write_a_non_finite_total_usd(tmp_path) -> None:
    """Defense in depth: write_cycle()'s own json.dump now carries
    allow_nan=False. assert_valid_cycle() already refuses a non-finite
    total_usd before this line is ever reached, so this documents that the
    OUTER guard (validation) is what actually fires -- confirming the two
    layers agree, not that the json.dump layer is reachable in normal use."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": float("inf")}
    )
    with pytest.raises(ct.ValidationError):
        ct.write_cycle(record, cycles_dir=str(tmp_path))


# --- BLOCKER 5: a bad --system slug must be a clean USAGE error (exit 2),
# not a raw traceback.


def test_cli_metrics_bad_system_slug_exits_2_cleanly(tmp_path, capsys) -> None:
    rc = ct.main(["metrics", "--system", "bad slug", "--cycles-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "bad slug" in err


def test_cli_summarize_bad_system_slug_exits_2_cleanly(tmp_path, capsys) -> None:
    rc = ct.main(["summarize", "--system", "bad slug", "--cycles-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "bad slug" in err


def test_cli_validate_bad_system_slug_exits_2_cleanly(tmp_path, capsys) -> None:
    rc = ct.main(["validate", "--system", "bad slug", "--cycles-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "bad slug" in err


def test_cli_validate_all_with_bad_system_free_dir_still_exits_0(tmp_path, capsys) -> None:
    """Sanity: --all with a clean (no bad slugs, because there ARE no
    subdirectories) cycles dir is unaffected by the blocker-5 fix."""
    rc = ct.main(["validate", "--all", "--cycles-dir", str(tmp_path)])
    assert rc == 0


# --- #11: _in_enum must never let a JSON boolean stand in for an int enum
# member (bool is an int subclass in Python).


def test_in_enum_never_matches_a_bool_against_an_int_enum() -> None:
    assert ct._in_enum(True, {1, 2}) is False
    assert ct._in_enum(False, {0, 1}) is False
    assert ct._in_enum(1, {1, 2}) is True  # unchanged: a real int still matches


def test_validate_cycle_rejects_a_boolean_schema_version() -> None:
    record = _minimal_record(schema_version=True)
    errs = ct.validate_cycle(record)
    assert any("schema_version" in e for e in errs)


# --- Operation-type audit (json.dumps sweep): _slot_label's json.dumps now
# carries allow_nan=False for consistency with every other json.dumps(s)
# call site in this module -- confirm the existing str(slot) fallback still
# fires cleanly for a non-finite value nested inside a malformed slot.


def test_slot_label_falls_back_to_str_for_a_non_finite_nested_value() -> None:
    assert ct._slot_label([float("nan"), 1]) == str([float("nan"), 1])
    assert ct._slot_label({"a": float("inf")}) == str({"a": float("inf")})


def test_slot_label_still_renders_a_normal_nested_value_as_compact_json() -> None:
    assert ct._slot_label([1, 2]) == "[1,2]"


# ---------------------------------------------------------------------------
# Round 14.
# ---------------------------------------------------------------------------

# --- BLOCKER 1: is_finite_number() must reject an int too large to survive
# a finite float conversion (OverflowError), not just NaN/Infinity floats --
# schema-valid today, unusable by every downstream `float(x)` call site.

_HUGE_INT = 10**309  # 310 digits; float(_HUGE_INT) raises OverflowError
_LARGE_BUT_FINITE_INT = 10**300  # float() of this is a large but finite float


def test_is_finite_number_rejects_an_int_too_large_for_a_finite_float() -> None:
    assert ct.is_finite_number(_HUGE_INT) is False
    assert ct.is_finite_number(-_HUGE_INT) is False


def test_is_finite_number_still_accepts_a_large_but_finite_int() -> None:
    """Boundary check: a big int that DOES fit in a finite float (e.g.
    1e300) must still be accepted -- the fix targets overflow, not size."""
    assert ct.is_finite_number(_LARGE_BUT_FINITE_INT) is True


def test_falsifiability_is_finite_number_huge_int_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per CLAUDE.md's falsifiability rule: revert the int-overflow guard in
    a scratch stand-in and confirm the huge-int case goes back to True
    (the pre-fix, buggy behavior) -- proving the shipped guard is what
    actually flips the result, not an unrelated pre-existing check.

    Note (round 16, finding 5): the RED half below is an ILLUSTRATIVE
    stand-in (`pre_fix_is_finite_number`), not a literal revert-and-rerun
    of the real module -- only the GREEN assertion actually exercises the
    shipped `ct.is_finite_number`. Documentary, not a true revert proof."""

    def pre_fix_is_finite_number(x: object) -> bool:
        if isinstance(x, bool):
            return False
        if isinstance(x, int):
            return True  # the round-14 bug: no overflow guard
        if isinstance(x, float):
            return math.isfinite(x)
        return False

    assert pre_fix_is_finite_number(_HUGE_INT) is True  # RED: pre-fix behavior
    assert ct.is_finite_number(_HUGE_INT) is False  # GREEN: shipped behavior


def test_usd_per_confirmed_defect_never_crashes_on_a_too_large_total_usd() -> None:
    """Repro (the reviewer's exact scenario): total_usd=10**309 used to pass
    `_is_number` unconditionally, then `total_usd / len(confirmed)` raised
    `OverflowError: integer division result too large for a float` --
    an ArithmeticError, never caught anywhere in this call chain."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": _HUGE_INT},
        findings=[_finding(finding_id="f1", verifier_verdict="CONFIRMED")],
    )
    assert ct.usd_per_confirmed_defect(record) is None  # must not raise


def test_price_tokens_never_crashes_on_a_too_large_token_bucket() -> None:
    """Repro: tokens.input=10**309 used to pass the `any(is_finite_number(...))`
    presence check, then `float(amt_raw)` raised OverflowError."""
    pricing = {"per_million_tokens": {"m": {"input": 1.0, "output": 1.0}}}
    assert ct.price_tokens({"input": _HUGE_INT, "output": 100}, "m", pricing) is None


def test_resolve_cost_never_crashes_on_a_too_large_tokens_total_ledger_row(tmp_path) -> None:
    """Repro: a matched ledger row's tokens_total=10**309 used to pass
    `_is_number(tt)` unconditionally, then `int(tt)` accumulation itself is
    safe (int + int never overflows), but the row still reaches
    price_tokens/rollup paths elsewhere -- confirm the whole resolve_cost
    call survives end to end with such a row present."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="T1")],
    )
    ledger = _write_ledger(
        tmp_path,
        [
            {
                "ts": "2026-08-27T14:10:00Z",
                "agent_type": "sentinel",
                "tool_use_id": "T1",
                "tokens_total": _HUGE_INT,
                "model": "m",
                "tokens": {"input": 100, "output": 100},
            }
        ],
    )
    pricing = _write_pricing(tmp_path, {"m": {"input": 1.0, "output": 1.0}})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)  # must not raise
    assert result["source"] == "spend_ledger"
    assert result["total_tokens"] is None  # too-large value withheld, not fabricated


@pytest.mark.parametrize("kind_field", ["total_usd", "total_tokens"])
def test_validate_cycle_rejects_a_too_large_cost_field(kind_field: str) -> None:
    """Decision (b), round 14: validate_cycle() must refuse, at write time,
    a cost.total_usd/total_tokens too large to survive a finite float
    conversion -- the write path must never accept a value the read path
    (rollup_cost, resolve_cost, usd_per_confirmed_defect) can only treat as
    unusable anyway."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": 1.0, kind_field: _HUGE_INT}
    )
    errs = ct.validate_cycle(record)
    assert any(kind_field in e for e in errs)


@pytest.mark.parametrize("kind_field", ["cost_usd", "tokens_total"])
def test_validate_cycle_rejects_a_too_large_dispatch_field(kind_field: str) -> None:
    record = _minimal_record(dispatches=[_dispatch(**{kind_field: _HUGE_INT})])
    errs = ct.validate_cycle(record)
    assert any(kind_field in e for e in errs)


def test_validate_cycle_still_accepts_a_large_but_finite_cost_and_dispatch_field() -> None:
    """Sanity: the new write-time guard rejects OVERFLOW, not mere size --
    a large-but-finite value must still validate cleanly."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": _LARGE_BUT_FINITE_INT, "total_usd": 1.0},
        dispatches=[_dispatch(tokens_total=_LARGE_BUT_FINITE_INT)],
    )
    assert ct.validate_cycle(record) == []


def test_cli_metrics_end_to_end_never_crashes_on_a_too_large_total_usd(tmp_path, capsys) -> None:
    """End-to-end falsification via the REAL CLI entry point (not just a
    unit test of is_finite_number alone): a hand-edited cycle file on disk
    (bypassing write_cycle/validate_cycle, exactly like a pre-existing file
    written before this round's write-time guard existed) carries
    cost.total_usd=10**309 and one CONFIRMED finding. `metrics` reaches
    compute_metrics -> usd_per_confirmed_defect's division. Before the fix,
    this raised OverflowError uncaught by _cmd_metrics's try/except (which
    only wraps the file read) and uncaught by main()'s catch tuple (which
    lacks ArithmeticError), crashing the whole CLI instead of printing a
    clean report."""
    record = _minimal_record(
        cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": _HUGE_INT},
        findings=[_finding(finding_id="f1", verifier_verdict="CONFIRMED")],
    )
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    rc = ct.main(["metrics", str(path), "--json"])  # must not raise
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["usd_per_confirmed_defect"] is None


# --- BLOCKER 2: `model` reaches price_tokens()/resolve_cost() from an
# arbitrary, never-validated spend-ledger row -- an unhashable value (dict,
# list, set) must never crash either the dict-lookup door (price_tokens's
# own `.get(model)`) or the set-membership door (`unpriced_models.add(label)`).


@pytest.mark.parametrize(
    "bad_model",
    [{"nested": "dict"}, ["a", "list"], {"a", "set"}],
    ids=["dict", "list", "set"],
)
def test_price_tokens_refuses_an_unhashable_model_value(bad_model: object) -> None:
    """Repro: `.get(model)` at price_tokens's own dict-lookup line hashes
    its key -- an unhashable model (dict/list/set) raised
    `TypeError: unhashable type`, breaking price_tokens's own documented
    "never raises" contract."""
    pricing = {"per_million_tokens": {"m": {"input": 1.0}}}
    assert ct.price_tokens({"input": 100}, bad_model, pricing) is None  # must not raise


def test_falsifiability_price_tokens_unhashable_model_guard() -> None:
    """Per CLAUDE.md's falsifiability rule: reproduce the pre-fix crash
    directly against the documented old guard shape (`if not model`) to
    prove it really did let an unhashable value through to the dict-lookup
    line, then confirm the shipped price_tokens() no longer reaches it.

    Note (round 16, finding 5): `pre_fix_guard` is an ILLUSTRATIVE stand-in
    for the pre-fix code, not a literal revert-and-rerun of the real
    module -- only the GREEN assertion below exercises the shipped
    `ct.price_tokens`. Documentary, not a true revert proof."""
    bad_model = {"nested": "dict"}

    def pre_fix_guard(model: object) -> bool:
        return not model  # the round-14 bug: truthy dict/list never refused

    assert pre_fix_guard(bad_model) is False  # RED: old guard lets it through
    rates_table = {"m": {"input": 1.0}}
    with pytest.raises(TypeError, match="unhashable"):
        rates_table.get(bad_model)  # the actual pre-fix crash shape

    # GREEN: the shipped price_tokens() never reaches that line for this model.
    pricing = {"per_million_tokens": rates_table}
    assert ct.price_tokens({"input": 100}, bad_model, pricing) is None


@pytest.mark.parametrize(
    "bad_model",
    [{"nested": "dict"}, ["a", "list"]],
    ids=["dict", "list"],
)
def test_resolve_cost_never_raises_on_an_unhashable_model_ledger_field(bad_model: object, tmp_path) -> None:
    """Repro (second door): row.get("model") is a dict/list, tokens is a
    non-empty dict, so `priced = price_tokens(...)` is reached, returns None
    (once price_tokens itself is hardened) -- but `label = model if model
    else "..."` is still truthy for a non-empty dict/list, and
    `unpriced_models.add(label)` (a set()) raised `TypeError: unhashable
    type`, independent of whatever price_tokens itself returns."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="T1")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "sentinel")
    row["tool_use_id"] = "T1"
    row["model"] = bad_model
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {})
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)  # must not raise
    assert result["source"] == "spend_ledger"
    assert result["total_usd"] is None
    assert result.get("unpriced_models") == ["(no model recorded)"]


def test_falsifiability_resolve_cost_unhashable_model_second_door(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Per CLAUDE.md's falsifiability rule: prove the SECOND door is a real,
    independent crash site -- monkeypatch price_tokens to always return None
    (so the first door's own guard is irrelevant to this repro; the reviewer
    used this exact technique to find the second door). The bare-set RED
    assertion below reproduces the pre-fix label-building crash shape
    directly (`unpriced_models.add(label)` where label is the raw
    unhashable model); the GREEN assertion confirms resolve_cost's own
    model-normalization (added independently of price_tokens's guard) keeps
    that operation from ever being reached with an unhashable label."""
    monkeypatch.setattr(ct, "price_tokens", lambda tokens, model, pricing: None)
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="T1")],
    )
    row = _ledger_row("2026-08-27T14:10:00Z", "sentinel")
    row["tool_use_id"] = "T1"
    row["model"] = {"nested": "dict"}
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {})
    # RED (pre-fix shape): the raw label-building operation crashes on its own.
    with pytest.raises(TypeError, match="unhashable"):
        set().add({"nested": "dict"})
    # GREEN (shipped code): resolve_cost itself must not raise even with
    # price_tokens monkeypatched to always return None.
    result = ct.resolve_cost(cycle, ledger_path=ledger, pricing_path=pricing)
    assert result["source"] == "spend_ledger"
    assert result.get("unpriced_models") == ["(no model recorded)"]


def test_cli_resolve_cost_end_to_end_never_crashes_on_an_unhashable_model(tmp_path, capsys) -> None:
    """End-to-end falsification via the REAL CLI entry point: the
    `resolve-cost` subcommand reads a cycle file and a ledger file from
    disk, exactly the shape a live incident would take."""
    cycle = _minimal_record(
        started_at="2026-08-27T14:00:00Z",
        ended_at="2026-08-27T15:00:00Z",
        dispatches=[_dispatch(agent_type="sentinel", tool_use_id="T1")],
    )
    cycle_path = tmp_path / "cycle.json"
    cycle_path.write_text(json.dumps(cycle), encoding="utf-8")
    row = _ledger_row("2026-08-27T14:10:00Z", "sentinel")
    row["tool_use_id"] = "T1"
    row["model"] = {"nested": "dict"}
    ledger = _write_ledger(tmp_path, [row])
    pricing = _write_pricing(tmp_path, {})
    rc = ct.main(
        ["resolve-cost", str(cycle_path), "--ledger", ledger, "--pricing", pricing, "--json"]
    )  # must not raise
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["source"] == "spend_ledger"
    assert out.get("unpriced_models") == ["(no model recorded)"]


# ---------------------------------------------------------------------------
# Round 18 -- schema.json <-> validate_cycle() numeric-overflow-guard PARITY.
#
# Round 17 found two things: (1) schema.json's top-level `description` was a
# JSON array of strings, which fails Draft 2020-12's own meta-schema (a
# `description` must be a plain string) -- meaning jsonschema.validate(),
# the file's own documented entry point, raised SchemaError before it ever
# validated anything; (2) round 16 added a matching `maximum` to only 4 of
# the 10+ numeric fields validate_cycle() guards with is_finite_number()/
# _is_number()'s overflow check, leaving 6 more of the exact same class
# (dispatches[].{tool_calls,duration_ms,batch_size,batch_position,
# tokens_reported} and cost.window.tolerance_sec) schema-ACCEPT /
# code-REJECT. Root cause per that review: nothing anywhere tested
# schema.json against validate_cycle()'s ACTUAL behavior, so this class of
# drift was undetectable until an adversarial review happened to spot-check
# by hand.
#
# This section closes the MECHANISM, not just the 6 fields: every numeric
# field validate_cycle() guards with is_finite_number/_is_number is
# enumerated below (11 total -- found by grepping every call site of both
# names in cycle_telemetry.py and keeping only the ones reachable from
# validate_cycle()'s own call tree: _validate_dispatch, _validate_cost,
# _validate_verdict. Read-side helpers -- resolve_cost, price_tokens,
# usd_per_confirmed_defect, aggregate_metrics, the CLI's _fmt_metric --
# run AFTER write-time validation and are deliberately excluded; they are
# not schema-shaped data at all). A single parametrized test proves schema
# and code agree on the 10**309 boundary for every one of them, so a future
# change to is_finite_number's guarded field set that isn't mirrored into
# schema.json's `maximum`s fails THIS test, not a human spot-check.
# ---------------------------------------------------------------------------


def _load_schema() -> dict:
    schema_path = os.path.join(ct.TELEMETRY_DIR, "schema.json")
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def test_schema_json_is_valid_draft_2020_12() -> None:
    """Blocker 1 fence: schema.json must itself be a valid Draft 2020-12
    document. This is what catches a regression like round 17's -- a
    top-level `description` reverting from a string back to an array of
    strings -- mechanically, since check_schema() raises SchemaError on
    exactly that shape, rather than needing a human to notice."""
    jsonschema.Draft202012Validator.check_schema(_load_schema())


def test_schema_json_actually_validates_a_real_record() -> None:
    """Confirms jsonschema.validate() -- the documented entry point this
    file's own module docstring promises works "without importing Python"
    -- succeeds end to end on a real, valid record, not just that
    check_schema() alone passes (round 17's bug made check_schema() raise
    before validate() ever got that far for ANY record, valid or not)."""
    jsonschema.validate(instance=_minimal_record(), schema=_load_schema())


def test_schema_json_validates_a_record_with_calibration_runs() -> None:
    """schema/code parity for the new W4s array (GH #4648): a well-formed
    record carrying calibration_runs[] (a plant row and a control row) must
    pass BOTH the Python validator and jsonschema.validate() against
    schema.json -- schema.json's own additive-array shape (calibration_run
    def, additionalProperties: false) must actually match
    _validate_calibration_run's, not just exist."""
    record = _minimal_record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            _control_run(trade="tile", false_alarm_finding_ids=["f-1"]),
        ]
    )
    assert ct.validate_cycle(record) == []
    jsonschema.validate(instance=record, schema=_load_schema())


def test_schema_json_rejects_unknown_key_inside_a_calibration_run_row() -> None:
    """The other half of the parity check: an unknown key inside a
    calibration_runs[] ROW (not just at the top level) must be rejected by
    BOTH validators, proving schema.json's calibration_run def actually
    carries its own `additionalProperties: false` rather than silently
    accepting anything jsonschema.validate() doesn't itself object to.

    N6 (round-2 review): asserting only `pytest.raises(ValidationError)`
    would ALSO pass if the rejection came from some unrelated reason (e.g.
    the top-level `additionalProperties: false` catching an unrecognized
    top-level key) -- that would prove nothing about the ROW-level
    constraint specifically. Assert on the failure's own path/message so
    this test can only pass via the calibration_runs[0] row itself being
    rejected for its own unknown key."""
    run = _calibration_run()
    run["made_up_field"] = 1
    record = _minimal_record(calibration_runs=[run])

    code_errs = ct.validate_cycle(record)
    assert any("unknown key: made_up_field" in e for e in code_errs)

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(instance=record, schema=_load_schema())
    err = exc_info.value
    assert "made_up_field" in err.message
    assert list(err.absolute_path) == ["calibration_runs", 0]


def test_schema_calibration_run_required_keys_match_code() -> None:
    """A required-keys parity fence, mirroring the existing
    NUMERIC_GUARDED_FIELDS maximum-parity fence below -- schema.json's
    calibration_run.required list and cycle_telemetry.py's own
    REQUIRED_CALIBRATION_RUN_KEYS are hand-maintained in two separate files
    with no shared source of truth; emptying (or otherwise drifting) either
    one out of sync with the other must fail THIS test, preventing that
    exact class of hand-maintained-copy drift rather than relying on a
    human to notice."""
    schema = _load_schema()
    schema_required = set(schema["$defs"]["calibration_run"]["required"])
    assert schema_required == ct.REQUIRED_CALIBRATION_RUN_KEYS


def test_schema_json_declares_a_property_for_every_optional_top_key() -> None:
    """A second, broader fence than the one above: EVERY key in
    ct.OPTIONAL_TOP_KEYS must have a corresponding entry in schema.json's
    top-level `properties` -- catches the class of drift where code adds a
    new optional top-level array (as calibration_runs was) but schema.json
    is never given a matching property/$def, silently leaving it
    unrepresentable to any tool that reads schema.json instead of
    importing this module."""
    schema = _load_schema()
    assert ct.OPTIONAL_TOP_KEYS <= set(schema["properties"])


_HUGE = 10**309  # 310 digits; float(_HUGE) raises OverflowError -- see _HUGE_INT above


def _dispatch_field_record(field: str, value: object) -> dict:
    overrides: dict[str, object] = {field: value}
    if field == "tokens_reported":
        overrides["tokens_source"] = "harness_reported"
    return _minimal_record(dispatches=[_dispatch(**overrides)])


def _cost_field_record(field: str, value: object) -> dict:
    cost: dict[str, object] = {"source": "spend_ledger", "total_tokens": 100, "total_usd": 1.0}
    cost[field] = value
    return _minimal_record(cost=cost)


def _window_tolerance_record(value: object) -> dict:
    cost = {
        "source": "reported",
        "total_tokens": None,
        "total_usd": None,
        "window": {
            "start": "2026-08-27T14:00:00Z",
            "end": "2026-08-27T15:00:00Z",
            "tolerance_sec": value,
        },
    }
    return _minimal_record(cost=cost)


def _verdict_confidence_record(value: object) -> dict:
    return _minimal_record(
        verdicts=[
            {
                "dispatch_label": "x",
                "scenario": "y",
                "verdict": "CONCUR",
                "confidence": value,
                "problem_count": 0,
            }
        ]
    )


# Every numeric field validate_cycle() guards with is_finite_number/
# _is_number -- see the section docstring above for how this list was swept.
NUMERIC_GUARDED_FIELDS: dict[str, Callable[[object], dict]] = {
    "dispatches[].tokens_total": lambda v: _dispatch_field_record("tokens_total", v),
    "dispatches[].cost_usd": lambda v: _dispatch_field_record("cost_usd", v),
    "dispatches[].tool_calls": lambda v: _dispatch_field_record("tool_calls", v),
    "dispatches[].duration_ms": lambda v: _dispatch_field_record("duration_ms", v),
    "dispatches[].batch_size": lambda v: _dispatch_field_record("batch_size", v),
    "dispatches[].batch_position": lambda v: _dispatch_field_record("batch_position", v),
    "dispatches[].tokens_reported": lambda v: _dispatch_field_record("tokens_reported", v),
    "cost.total_tokens": lambda v: _cost_field_record("total_tokens", v),
    "cost.total_usd": lambda v: _cost_field_record("total_usd", v),
    "cost.window.tolerance_sec": lambda v: _window_tolerance_record(v),
    "verdicts[].confidence": lambda v: _verdict_confidence_record(v),
}


@pytest.mark.parametrize("field_path", sorted(NUMERIC_GUARDED_FIELDS))
def test_schema_and_code_agree_on_overflow_rejection(field_path: str) -> None:
    """THE parity test: for every numeric field validate_cycle() guards with
    is_finite_number/_is_number, schema.json's Draft202012Validator must
    REJECT a 10**309 value in that field if and only if validate_cycle()
    also rejects it. A field where only one of the two rejects is exactly
    the drift class rounds 16/17 found by hand instead of by a test."""
    validator = jsonschema.Draft202012Validator(_load_schema())
    record = NUMERIC_GUARDED_FIELDS[field_path](_HUGE)

    schema_rejects = not validator.is_valid(record)
    code_errs = ct.validate_cycle(record)
    code_rejects = code_errs != []

    assert schema_rejects == code_rejects, (
        f"{field_path}: schema_rejects={schema_rejects} code_rejects={code_rejects} "
        f"(code errors: {code_errs})"
    )
    # Both sides must actually reject -- this rules out the degenerate case
    # where the equality above is trivially satisfied by both silently
    # accepting the overflowing value.
    assert code_rejects is True
