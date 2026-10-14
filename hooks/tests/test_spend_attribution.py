"""Hermetic tests for hooks/spend_attribution.py.

No `sandbox`/HOME patching needed for most tests: every discovery root and
cache path is an explicit parameter, mirroring cycle_budget.py's own
testability contract. Fixture trees are built under `tmp_path` so nothing
here ever reads this machine's real ~/.claude/projects or /tmp/claude-*
data.
"""

from __future__ import annotations

import json
import os
import time

import cycle_budget as cb
import pytest

import spend_attribution as sa

KNOWN_TYPES = frozenset({"implement", "code-reviewer", "trade-site"})


def _usd_sonnet(**token_fields: float) -> float:
    """Expected USD for `token_fields` at sonnet's live published rates.

    The tests below assert IDENTITY-RECOVERY and provenance behavior; the
    dollar figure is incidental fixture arithmetic, so it is derived from
    the live table rather than hardcoded (a hardcoded literal broke all
    three of these when Anthropic's rates changed on 2026-09-05, with no
    defect behind any of them). The published RATES themselves are pinned
    in test_cycle_budget.py::test_pricing_table_matches_published_rates --
    deliberately not re-asserted here, so there is exactly one place to
    update when pricing moves.
    """
    rates = cb.PRICING_USD_PER_MTOK["sonnet"]
    return sum(count * rates[field] / 1_000_000 for field, count in token_fields.items())


# ---------------------------------------------------------------------------
# Fixture builders.
# ---------------------------------------------------------------------------


def _write_meta(root, rel_path: str, agent_id: str, payload: dict) -> str:
    """Write a `agent-<id>.meta.json` at `root/rel_path/agent-<id>.meta.json`."""
    directory = root / rel_path
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"agent-{agent_id}.meta.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _write_output(root, rel_path: str, task_id: str, workflow_progress: list) -> str:
    """Write a `<task_id>.output` under `root/rel_path/tasks/`."""
    directory = root / rel_path / "tasks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{task_id}.output"
    payload = {
        "summary": "test",
        "agentCount": len(workflow_progress),
        "workflowProgress": workflow_progress,
        "totalTokens": sum(e.get("tokens", 0) for e in workflow_progress if e.get("type") == "workflow_agent"),
        "totalToolCalls": 0,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _ledger_row(**overrides) -> dict:
    base = {
        "ts": "2026-08-28T10:00:00Z",
        "session": None,
        "agent_type": "workflow-subagent",
        "model": None,
        "tool_use_id": None,
        "agent_id": "aabbccdd0011223344",
        "duration_ms": None,
        "tokens": {"input": 100, "output": 200, "cache_read": 0, "cache_creation": 0},
        "tokens_total": 300,
        "tokens_error": None,
        "late": False,
        "unreleased": True,
        "reaped": "stopped-unjoined",
        "join_state": "no-claim",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Placeholder / missing / meaningful helpers.
# ---------------------------------------------------------------------------


def test_placeholder_agent_types_constant():
    assert sa.PLACEHOLDER_AGENT_TYPES == frozenset({None, "", "workflow-subagent"})


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("agent_type", None, True),
        ("agent_type", "", True),
        ("agent_type", "workflow-subagent", True),
        ("agent_type", "implement", False),
        ("agent_type", "trade-site", False),
        ("model", None, True),
        ("model", "claude-sonnet-5", False),
        ("model", "", True),  # empty string is falsy -> None-equivalent for model too
    ],
)
def test_is_missing(field, value, expected):
    # BLOCKER 7 fix (2026-08-28): an empty-string `model` IS missing/
    # recoverable, exactly like `None` -- matching how `agent_type`'s
    # placeholder set already includes "" and how `_is_meaningful` already
    # treats "" as falsy for every field. A ledger row that already got
    # stuck with `model: ""` must be eligible for recovery, not permanently
    # locked in as "real, first-party data that can never be overridden".
    assert sa._is_missing(field, value) is expected


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("agent_type", "implement", True),
        ("agent_type", "workflow-subagent", False),
        ("agent_type", "", False),
        ("agent_type", None, False),
        ("model", "claude-sonnet-5", True),
        ("model", "", False),
        ("model", None, False),
    ],
)
def test_is_meaningful(field, value, expected):
    assert sa._is_meaningful(field, value) is expected


# ---------------------------------------------------------------------------
# Filename / path parsing.
# ---------------------------------------------------------------------------


def test_agent_id_from_meta_filename():
    assert sa._agent_id_from_meta_filename("/a/b/agent-abc123.meta.json") == "abc123"
    assert sa._agent_id_from_meta_filename("/a/b/not-a-meta-file.json") is None
    assert sa._agent_id_from_meta_filename("/a/b/agent-.meta.json") is None


def test_workflow_run_id_from_meta_path_workflow_dispatch():
    path = "/x/.claude/projects/proj/sess/subagents/workflows/wf_abc-123/agent-xyz.meta.json"
    assert sa._workflow_run_id_from_meta_path(path) == "wf_abc-123"


def test_workflow_run_id_from_meta_path_direct_dispatch():
    path = "/x/.claude/projects/proj/sess/subagents/agent-xyz.meta.json"
    assert sa._workflow_run_id_from_meta_path(path) is None


# ---------------------------------------------------------------------------
# _output_entry_score ordering (completeness, not collision).
# ---------------------------------------------------------------------------


def test_output_entry_score_prefers_done_and_full_model():
    sparse = {"state": "queued", "model": "opus"}
    complete = {"state": "done", "agentType": "ultracode", "model": "claude-opus-5[1m]", "label": "x"}
    assert sa._output_entry_score(complete) > sa._output_entry_score(sparse)


def test_output_entry_score_full_model_beats_family_word():
    family_only = {"state": "done", "model": "opus"}
    full_tag = {"state": "done", "model": "claude-opus-5[1m]"}
    assert sa._output_entry_score(full_tag) > sa._output_entry_score(family_only)


# ---------------------------------------------------------------------------
# _merge_identity preference rules.
# ---------------------------------------------------------------------------


def test_merge_identity_meta_wins_agent_type_output_wins_model():
    meta = {"agentType": "trade-site", "model": "sonnet", "_workflow_run_id": "wf_1"}
    out = {"agentType": "trade-site", "model": "claude-sonnet-5", "label": "l", "phaseTitle": "p", "tokens": 42}
    ident = sa._merge_identity(meta, out)
    assert ident.agent_type == "trade-site"
    assert ident.agent_type_source == "meta.json"
    assert ident.model == "claude-sonnet-5"  # full tag, NOT the family-only "sonnet"
    assert ident.model_source == "workflow_output"
    assert ident.label == "l"
    assert ident.phase == "p"
    assert ident.reported_tokens == 42
    assert ident.workflow_run_id == "wf_1"


def test_merge_identity_falls_back_to_meta_model_when_output_missing():
    meta = {"agentType": "implement", "model": "opus"}
    ident = sa._merge_identity(meta, None)
    assert ident.model == "opus"
    assert ident.model_source == "meta.json"


def test_merge_identity_falls_back_to_output_agent_type_when_meta_missing():
    out = {"agentType": "code-reviewer", "model": "claude-opus-5[1m]"}
    ident = sa._merge_identity(None, out)
    assert ident.agent_type == "code-reviewer"
    assert ident.agent_type_source == "workflow_output"


def test_merge_identity_both_none_yields_empty_identity():
    ident = sa._merge_identity(None, None)
    assert ident.agent_type is None
    assert ident.model is None
    assert ident.agent_type_source is None
    assert ident.model_source is None


def test_merge_identity_workflow_run_id_prefers_meta_source():
    meta = {"_workflow_run_id": "wf_durable"}
    out = {"_workflow_run_id": "task_ephemeral"}
    ident = sa._merge_identity(meta, out)
    assert ident.workflow_run_id == "wf_durable"


# ---------------------------------------------------------------------------
# Discovery from real (fixture) files on disk.
# ---------------------------------------------------------------------------


def test_load_meta_index_reads_real_files(tmp_path):
    meta_root = tmp_path / "projects"
    _write_meta(meta_root, "proj/sess/subagents/workflows/wf_1", "agent1", {"agentType": "implement"})
    _write_meta(meta_root, "proj/sess/subagents", "agent2", {"agentType": "code-reviewer", "model": "opus"})
    index = sa._load_meta_index([str(meta_root)])
    assert index["agent1"]["agentType"] == "implement"
    assert index["agent1"]["_workflow_run_id"] == "wf_1"
    assert index["agent2"]["model"] == "opus"
    assert index["agent2"]["_workflow_run_id"] is None


def test_load_meta_index_skips_malformed_and_non_dict_json(tmp_path):
    meta_root = tmp_path / "projects"
    directory = meta_root / "proj/sess/subagents"
    directory.mkdir(parents=True)
    (directory / "agent-bad1.meta.json").write_text("{not json", encoding="utf-8")
    (directory / "agent-bad2.meta.json").write_text("[1, 2, 3]", encoding="utf-8")
    (directory / "agent-good.meta.json").write_text(json.dumps({"agentType": "implement"}), encoding="utf-8")
    index = sa._load_meta_index([str(meta_root)])
    assert "bad1" not in index
    assert "bad2" not in index
    assert index["good"]["agentType"] == "implement"


def test_load_meta_index_missing_root_is_skipped():
    assert sa._load_meta_index(["/definitely/does/not/exist"]) == {}


def test_load_output_index_reads_workflow_agent_entries(tmp_path):
    output_root = tmp_path / "claude-501"
    _write_output(
        output_root,
        "proj/sess",
        "task1",
        [
            {"type": "workflow_phase", "index": 1, "title": "Fix"},
            {
                "type": "workflow_agent",
                "agentId": "agentA",
                "agentType": "implement",
                "model": "claude-sonnet-5",
                "state": "done",
                "label": "fix:x",
                "phaseTitle": "Fix",
                "tokens": 12345,
            },
        ],
    )
    index = sa._load_output_index([str(output_root)])
    assert index["agentA"]["model"] == "claude-sonnet-5"
    assert index["agentA"]["_workflow_run_id"] == "task1"


def test_load_output_index_skips_non_json_and_non_workflow_files(tmp_path):
    output_root = tmp_path / "claude-501"
    tasks_dir = output_root / "proj/sess/tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "plain.output").write_text("Logging in...\nPASS\n", encoding="utf-8")
    (tasks_dir / "transcript.output").write_text(
        '{"parentUuid": null, "type": "user"}\n{"extra": "data"}\n', encoding="utf-8"
    )
    (tasks_dir / "no_progress.output").write_text(json.dumps({"summary": "x"}), encoding="utf-8")
    index = sa._load_output_index([str(output_root)])
    assert index == {}


def test_load_output_index_prefers_more_complete_snapshot(tmp_path):
    output_root = tmp_path / "claude-501"
    _write_output(
        output_root,
        "proj/sess",
        "task_early",
        [{"type": "workflow_agent", "agentId": "dup", "model": "opus", "state": "running"}],
    )
    _write_output(
        output_root,
        "proj/sess2",
        "task_late",
        [
            {
                "type": "workflow_agent",
                "agentId": "dup",
                "agentType": "ultracode",
                "model": "claude-opus-5[1m]",
                "state": "done",
            }
        ],
    )
    index = sa._load_output_index([str(output_root)])
    assert index["dup"]["model"] == "claude-opus-5[1m]"
    assert index["dup"]["agentType"] == "ultracode"


def test_load_output_index_missing_root_is_skipped():
    assert sa._load_output_index(["/definitely/does/not/exist"]) == {}


def test_iter_output_files_depth_bound_pins_intentional_contract(tmp_path):
    """Missing coverage (round 18 review): `_iter_output_files()`'s
    round-16 depth-bounding fix (`spend_attribution.py:407-434`, replacing
    an unbounded recursive `**` glob with a fixed-depth
    `<root>/*/*/tasks/*.output` glob) had ZERO test coverage of its own --
    every existing `.output` fixture in this file happens to sit at
    exactly the assumed depth (`rel_path="proj/sess"`, two components),
    so reverting the fix to the old unbounded `**` glob left every
    existing test in this module green with no way to notice. This test
    PINS the depth bound as an intentional, load-bearing contract, not an
    accident of the fixtures: an `.output` file one directory DEEPER than
    the documented `<root>/<project>/<session>/tasks/<taskid>.output`
    shape must be silently skipped (never found, per this module's own
    fail-open-on-individual-file-problems design), while one at the
    documented depth must still be found. Falsified per this repo's
    CLAUDE.md §6: reverting `_iter_output_files()` to the old unbounded
    `os.path.join(root, "**", pattern)` / `recursive=True` glob in a
    scratch copy makes this test's own `deep-agent` assertion go RED
    (the deeper file IS found by an unbounded glob); restoring the
    fixed-depth glob makes it GREEN again."""
    output_root = tmp_path / "claude-501"
    _write_output(
        output_root,
        "proj/sess",
        "shallow_task",
        [{"type": "workflow_agent", "agentId": "shallow-agent", "model": "claude-sonnet-5", "state": "done"}],
    )
    _write_output(
        output_root,
        "proj/sess/extra",
        "deep_task",
        [{"type": "workflow_agent", "agentId": "deep-agent", "model": "claude-opus-5", "state": "done"}],
    )
    index = sa._load_output_index([str(output_root)])
    assert "shallow-agent" in index  # found at the documented depth
    assert "deep-agent" not in index  # one directory deeper -- correctly NOT found


def test_build_identity_index_uncached_merges_both_sources(tmp_path):
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents/workflows/wf_9", "onlymeta", {"agentType": "trust-architect"})
    _write_output(
        output_root,
        "proj/sess",
        "task9",
        [{"type": "workflow_agent", "agentId": "onlyoutput", "model": "claude-sonnet-5"}],
    )
    _write_meta(meta_root, "proj/sess/subagents/workflows/wf_9", "both", {"agentType": "implement"})
    _write_output(
        output_root,
        "proj/sess",
        "task9",
        [
            {"type": "workflow_agent", "agentId": "onlyoutput", "model": "claude-sonnet-5"},
            {"type": "workflow_agent", "agentId": "both", "agentType": "implement", "model": "claude-opus-5[1m]"},
        ],
    )
    index = sa.build_identity_index_uncached([str(meta_root)], [str(output_root)])
    assert index["onlymeta"].agent_type == "trust-architect"
    assert index["onlymeta"].model is None
    assert index["onlyoutput"].model == "claude-sonnet-5"
    assert index["onlyoutput"].agent_type is None
    assert index["both"].agent_type == "implement"
    assert index["both"].model == "claude-opus-5[1m]"


# ---------------------------------------------------------------------------
# FALSIFY 1 + 2: enrich_row provenance contract.
# ---------------------------------------------------------------------------


def test_falsify_unrecoverable_row_stays_unattributable_never_guessed():
    """A row whose agent_id has no entry anywhere in the index must NEVER
    end up with a fabricated model -- it stays None, marked unattributable."""
    row = _ledger_row(agent_id="totally-unknown-id", model=None)
    index: dict = {}
    enriched = sa.enrich_row(row, index)
    assert enriched["model"] is None
    assert enriched["attribution"]["model"]["provenance"] == "unattributable"
    assert enriched["attribution"]["model"]["source"] is None


def test_falsify_recovered_value_marked_recovered_not_original():
    """A row whose model WAS recovered must be marked 'recovered', never
    laundered as 'original' -- a caller MUST be able to tell the two apart."""
    row = _ledger_row(agent_id="agentX", model=None, agent_type="trade-site")
    index = {"agentX": sa.RecoveredIdentity(model="claude-sonnet-5", model_source="workflow_output")}
    enriched = sa.enrich_row(row, index)
    assert enriched["model"] == "claude-sonnet-5"
    block = enriched["attribution"]["model"]
    assert block["provenance"] == "recovered"
    assert block["provenance"] != "original"
    assert block["source"] == "workflow_output"
    assert block["original_value"] is None


def test_original_real_value_never_overridden():
    row = _ledger_row(agent_id="agentY", agent_type="implement", model="claude-sonnet-5")
    index = {"agentY": sa.RecoveredIdentity(agent_type="something-else", model="claude-opus-5[1m]")}
    enriched = sa.enrich_row(row, index)
    assert enriched["agent_type"] == "implement"
    assert enriched["model"] == "claude-sonnet-5"
    assert enriched["attribution"]["agent_type"]["provenance"] == "original"
    assert enriched["attribution"]["model"]["provenance"] == "original"


def test_placeholder_agent_type_recovered_to_real_type():
    row = _ledger_row(agent_id="agentZ", agent_type="workflow-subagent")
    index = {"agentZ": sa.RecoveredIdentity(agent_type="trade-site", agent_type_source="meta.json")}
    enriched = sa.enrich_row(row, index)
    assert enriched["agent_type"] == "trade-site"
    assert enriched["attribution"]["agent_type"]["provenance"] == "recovered"
    assert enriched["attribution"]["agent_type"]["original_value"] == "workflow-subagent"


def test_placeholder_recovering_to_another_placeholder_stays_unattributable():
    """Real, measured shape: some workflow-subagent dispatches are
    genuinely anonymous -- both sources agree "workflow-subagent" is
    accurate. That must NOT be reported as a false 'recovered'."""
    row = _ledger_row(agent_id="agentW", agent_type="workflow-subagent")
    index = {
        "agentW": sa.RecoveredIdentity(agent_type="workflow-subagent", agent_type_source="meta.json")
    }
    enriched = sa.enrich_row(row, index)
    assert enriched["agent_type"] == "workflow-subagent"
    assert enriched["attribution"]["agent_type"]["provenance"] == "unattributable"


def test_enrich_row_never_mutates_input():
    row = _ledger_row(agent_id="agentM", model=None)
    original_copy = dict(row)
    index = {"agentM": sa.RecoveredIdentity(model="claude-sonnet-5")}
    sa.enrich_row(row, index)
    assert row == original_copy


def test_enrich_row_attaches_label_phase_workflow_run_id_when_recovered():
    row = _ledger_row(agent_id="agentL", model=None)
    index = {
        "agentL": sa.RecoveredIdentity(
            model="claude-sonnet-5",
            label="fix:runtime-agents",
            phase="Fix",
            workflow_run_id="task123",
            reported_tokens=42,
        )
    }
    enriched = sa.enrich_row(row, index)
    assert enriched["attribution"]["label"] == "fix:runtime-agents"
    assert enriched["attribution"]["phase"] == "Fix"
    assert enriched["attribution"]["workflow_run_id"] == "task123"
    assert enriched["attribution"]["reported_tokens_untrusted"] == 42


# ---------------------------------------------------------------------------
# FALSIFY 3: no double-counting.
# ---------------------------------------------------------------------------


def test_falsify_workflow_reported_tokens_never_enter_ledger_totals():
    """The literal ask: workflowProgress's `tokens` is payload-shaped, NOT
    billed spend, and must never be summed into any total -- even when it
    wildly disagrees with the ledger's own tokens_total."""
    row = _ledger_row(agent_id="agentR", model=None, tokens_total=50_000_000)
    index = {
        "agentR": sa.RecoveredIdentity(
            model="claude-sonnet-5", reported_tokens=142_113  # ~350x smaller, deliberately mismatched
        )
    }
    report = sa.coverage_report([row], index)
    assert report["total_tokens"] == 50_000_000
    assert report["model"]["recovered"]["tokens"] == 50_000_000
    # The untrusted reported figure is visible ONLY under attribution, never
    # blended into any total.
    enriched = sa.enrich_row(row, index)
    assert enriched["attribution"]["reported_tokens_untrusted"] == 142_113
    assert 142_113 not in (report["total_tokens"], report["model"]["recovered"]["tokens"])


def test_falsify_duplicate_agent_id_rows_never_merged_but_tokens_collapsed():
    """BLOCKER 3 fix (2026-08-28): the real, measured ledger phenomenon --
    the SAME agent_id appears as two independent lines (a normal release +
    a LATER, LARGER cumulative stopped-unjoined reap of the SAME agent's
    still-running spend). `enrich_rows()` must NEVER merge/drop the rows
    themselves -- each stays its own row, own tokens_total, own identity
    (matching churn_report.dedup_spend_lines's own established
    null-tool_use_id-is-its-own-record rule) -- but `coverage_report()`'s
    aggregate TOTALS must count this real spend only ONCE (the larger,
    later reading), not sum both as if they were independent spend."""
    row1 = _ledger_row(
        agent_id="dup-agent",
        tool_use_id="toolu_1",
        model="claude-opus-5[1m]",
        agent_type="plan-reviewer",
        tokens_total=14_206_442,
        unreleased=False,
        reaped=None,
    )
    row2 = _ledger_row(
        agent_id="dup-agent",
        tool_use_id=None,
        model=None,
        agent_type="plan-reviewer",
        tokens_total=17_575_769,
        unreleased=True,
        reaped="stopped-unjoined",
    )
    index = {"dup-agent": sa.RecoveredIdentity(model="claude-opus-5[1m]", model_source="workflow_output")}
    enriched = sa.enrich_rows([row1, row2], index)
    assert len(enriched) == 2  # never merged into one row
    assert enriched[0]["tokens_total"] == 14_206_442  # each row's OWN field untouched
    assert enriched[1]["tokens_total"] == 17_575_769
    report = sa.coverage_report([row1, row2], index)
    # Collapsed: only the larger, later cumulative reading counts toward
    # any total -- summing both would double-count 14,206,442 real tokens.
    assert report["total_tokens"] == 17_575_769
    assert report["collapsed_duplicate_rows"] == 1


def test_enrich_rows_preserves_row_count_and_order():
    rows = [_ledger_row(agent_id=f"a{i}") for i in range(5)]
    enriched = sa.enrich_rows(rows, {})
    assert len(enriched) == 5
    assert [r["agent_id"] for r in enriched] == [f"a{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# FALSIFY BLOCKER 2: ledger-internal sibling-row identity join.
# ---------------------------------------------------------------------------


def test_falsify_sibling_row_in_same_ledger_recovers_model_with_no_external_metadata():
    """BLOCKER 2 (2026-08-28), the real, measured shape: 41/61 'unrecoverable'
    model rows share an agent_id with a PRICED SIBLING ROW already present
    in the SAME ledger -- with ZERO external meta.json/workflow_output
    metadata anywhere. `enrich_rows()`/`coverage_report()` must recover the
    model from that sibling row, not report a false structural dead end."""
    priced_sibling = _ledger_row(agent_id="dup-agent", tool_use_id="toolu_1", model="claude-opus-5[1m]")
    unpriced_reap = _ledger_row(agent_id="dup-agent", tool_use_id=None, model=None, reaped="stopped-unjoined")
    empty_index: dict = {}  # no external workflow metadata at all
    enriched = sa.enrich_rows([priced_sibling, unpriced_reap], empty_index)
    assert enriched[0]["model"] == "claude-opus-5[1m]"  # its own, untouched
    assert enriched[1]["model"] == "claude-opus-5[1m]"  # recovered from its sibling
    assert enriched[1]["attribution"]["model"]["provenance"] == "recovered"
    assert enriched[1]["attribution"]["model"]["source"] == "ledger_sibling"


def test_sibling_join_never_overrides_a_real_external_recovery():
    """The ledger-internal sibling source is strictly LOWEST priority: it
    must never override a meaningful value the external meta.json/
    workflow_output index already resolved."""
    row_a = _ledger_row(agent_id="shared-id", model="claude-haiku-4-5-20251001")
    row_b = _ledger_row(agent_id="shared-id", tool_use_id=None, model=None)
    index = {"shared-id": sa.RecoveredIdentity(model="claude-opus-5[1m]", model_source="workflow_output")}
    enriched = sa.enrich_rows([row_a, row_b], index)
    assert enriched[1]["model"] == "claude-opus-5[1m]"  # external index wins, not the sibling's haiku
    assert enriched[1]["attribution"]["model"]["source"] == "workflow_output"


def test_sibling_join_never_recovers_agent_type_from_another_placeholder():
    """Every sibling row is ALSO just 'workflow-subagent' -- the sibling
    source must contribute nothing, exactly like the two external sources
    already correctly do in this situation."""
    row_a = _ledger_row(agent_id="anon-id", agent_type="workflow-subagent")
    row_b = _ledger_row(agent_id="anon-id", tool_use_id=None, agent_type="workflow-subagent")
    enriched = sa.enrich_rows([row_a, row_b], {})
    assert enriched[1]["attribution"]["agent_type"]["provenance"] == "unattributable"


def test_falsify_contested_sibling_fact_never_resolved_by_file_order():
    """BLOCKER 4 (round 4, 2026-08-28), the reviewer's exact repro: three
    ledger lines share one agent_id -- a sonnet sibling, an opus sibling,
    and the (largest, model-null) row that needs to borrow a model from a
    sibling. Two DISTINCT real model values exist in the group (sonnet,
    opus) -- a CONTESTED fact. The borrowing row must resolve to the SAME
    outcome (unattributable, no fact contributed) regardless of which
    sibling appears first in the rows list -- round 3's "first value seen
    wins" rule produced a different, silently-confident dollar figure (5x
    apart) purely from file order."""
    sonnet_sibling = _ledger_row(agent_id="contested-agent", tool_use_id="tu1", model="claude-sonnet-5")
    opus_sibling = _ledger_row(agent_id="contested-agent", tool_use_id="tu2", model="claude-opus-5")
    borrower = _ledger_row(
        agent_id="contested-agent",
        tool_use_id="tu3",
        model=None,
        tokens={"input": 5_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
        tokens_total=5_000_000,
    )

    sonnet_first = sa.enrich_rows([sonnet_sibling, opus_sibling, borrower], {})
    opus_first = sa.enrich_rows([opus_sibling, sonnet_sibling, borrower], {})

    borrower_sonnet_first = next(r for r in sonnet_first if r["tool_use_id"] == "tu3")
    borrower_opus_first = next(r for r in opus_first if r["tool_use_id"] == "tu3")

    # Contested -- no fact contributed either way, so the borrower stays
    # unattributable in BOTH orders, never a confident (and order-dependent)
    # guess at either sibling's model.
    assert borrower_sonnet_first["attribution"]["model"]["provenance"] == "unattributable"
    assert borrower_opus_first["attribution"]["model"]["provenance"] == "unattributable"
    assert borrower_sonnet_first["model"] == borrower_opus_first["model"] is None


def test_coverage_report_uses_widened_sibling_index_too():
    """coverage_report() must ALSO benefit from the sibling join, not just
    enrich_rows() -- both entry points receive the full row set."""
    priced_sibling = _ledger_row(agent_id="dup-agent", tool_use_id="toolu_1", model="claude-sonnet-5")
    unpriced_reap = _ledger_row(agent_id="dup-agent", tool_use_id=None, model=None, tokens_total=0)
    report = sa.coverage_report([priced_sibling, unpriced_reap], {})
    assert report["model"]["recovered"]["rows"] == 1
    assert report["still_unpriceable"]["rows"] == 0


# ---------------------------------------------------------------------------
# FALSIFY BLOCKER 4: "priceable" means actually priceable, not merely present.
# ---------------------------------------------------------------------------


def test_falsify_recovered_unknown_family_not_counted_priceable():
    """BLOCKER 4 (2026-08-28), the real, measured shape: a row recovers a
    model string that IS present but normalizes to "unknown" (e.g. an
    internal code name like "claude-imaginary-9") -- cycle_budget.py cannot
    price a single token of it. coverage_report() must NOT count this row
    under priceable_after_recovery, and must surface it under the distinct
    recovered_but_unpriced_family bucket instead."""
    row = _ledger_row(agent_id="imaginary-agent", model=None, tokens_total=1000)
    index = {"imaginary-agent": sa.RecoveredIdentity(model="claude-imaginary-9", model_source="workflow_output")}
    report = sa.coverage_report([row], index)
    # Old (buggy) behavior would have counted this under priceable_after
    # purely because SOME model string is now present.
    assert report["priceable_after_recovery"]["rows"] == 0
    assert report["recovered_but_unpriced_family"]["rows"] == 1
    assert report["recovered_but_unpriced_family"]["tokens"] == 1000
    assert report["still_unpriceable"]["rows"] == 1


def test_is_priced_model_matches_cycle_budget_pricing_gate_exactly():
    import cycle_budget as cb

    assert sa._is_priced_model("claude-sonnet-5") is True
    assert sa._is_priced_model("claude-fable-5") is True
    assert sa._is_priced_model("claude-imaginary-9") is False
    assert sa._is_priced_model(None) is False
    for family in cb.PRICING_USD_PER_MTOK:
        assert sa._is_priced_model(family) is True


def test_priceable_before_recovery_also_uses_real_predicate():
    """An ORIGINAL (non-recovered) model that is present but unrecognized
    must not count as priceable_before_recovery either."""
    row = _ledger_row(agent_id="already-imaginary", model="claude-imaginary-9")
    report = sa.coverage_report([row], {})
    assert report["priceable_before_recovery"]["rows"] == 0


# ---------------------------------------------------------------------------
# coverage_report: residual honesty.
# ---------------------------------------------------------------------------


def test_coverage_report_reports_zero_residual_explicitly_not_omitted():
    row = _ledger_row(agent_id="known", model="claude-sonnet-5", agent_type="implement")
    report = sa.coverage_report([row], {})
    assert "still_unpriceable" in report
    assert report["still_unpriceable"]["rows"] == 0
    assert report["still_unpriceable"]["tokens"] == 0
    assert "reason" in report["still_unpriceable"]


def test_falsify_null_tokens_total_rows_disclosed_not_silently_absorbed():
    """BLOCKER 5 (round 11 review finding, round 12 fix, 2026-08-28): a row
    with a null/missing `tokens_total` used to contribute silently to every
    denominator/bucket in `coverage_report()` as 0.0 tokens, with zero
    visibility -- the same real, measured population (48 live-ledger rows)
    as BLOCKER 2's `cycle_budget.py` fix. `null_tokens_total_rows` must
    disclose this count, mirroring the `collapsed_duplicate_rows`
    disclosure right beside it, and must never be silently omitted even
    when the count is genuinely zero."""
    good_row = _ledger_row(agent_id="known", model="claude-sonnet-5", agent_type="implement", tokens_total=300)
    null_row = _ledger_row(agent_id="null-tt", model="claude-sonnet-5", agent_type="implement", tokens_total=None)
    report = sa.coverage_report([good_row, null_row], {})
    assert report["null_tokens_total_rows"] == 1

    # And explicitly present (never omitted) even when genuinely zero.
    clean_report = sa.coverage_report([good_row], {})
    assert clean_report["null_tokens_total_rows"] == 0


def test_coverage_report_buckets_sum_to_total_rows():
    rows = [
        _ledger_row(agent_id="a1", model="claude-sonnet-5"),
        _ledger_row(agent_id="a2", model=None),
        _ledger_row(agent_id="a3", model=None),
    ]
    index = {"a2": sa.RecoveredIdentity(model="claude-opus-5[1m]")}
    report = sa.coverage_report(rows, index)
    model_total = (
        report["model"]["original"]["rows"]
        + report["model"]["recovered"]["rows"]
        + report["model"]["unattributable"]["rows"]
    )
    assert model_total == report["total_rows"] == 3
    assert report["priceable_before_recovery"]["rows"] == 1
    assert report["priceable_after_recovery"]["rows"] == 2
    assert report["still_unpriceable"]["rows"] == 1


def test_coverage_report_empty_rows_no_division_by_zero():
    report = sa.coverage_report([], {})
    assert report["total_rows"] == 0
    assert report["total_tokens"] == 0
    assert report["model"]["original"]["pct_of_total_tokens"] == 0.0


# ---------------------------------------------------------------------------
# Caching.
# ---------------------------------------------------------------------------


def test_build_identity_index_writes_and_reuses_fresh_cache(tmp_path, monkeypatch):
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = str(tmp_path / "cache.json")

    index1 = sa.build_identity_index(
        meta_roots=[str(meta_root)], output_roots=[str(output_root)], cache_path=cache_path
    )
    assert index1["a1"].agent_type == "implement"
    assert os.path.isfile(cache_path)

    # Add a NEW meta file that a fresh scan would find -- but the cache is
    # still fresh, so build_identity_index must NOT pick it up.
    _write_meta(meta_root, "proj/sess/subagents", "a2", {"agentType": "code-reviewer"})
    index2 = sa.build_identity_index(
        meta_roots=[str(meta_root)],
        output_roots=[str(output_root)],
        cache_path=cache_path,
        max_age_seconds=3600,
    )
    assert "a2" not in index2  # fresh cache reused, no rescan


def test_build_identity_index_rebuilds_when_cache_stale(tmp_path):
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = str(tmp_path / "cache.json")
    sa.build_identity_index(meta_roots=[str(meta_root)], output_roots=[str(output_root)], cache_path=cache_path)

    _write_meta(meta_root, "proj/sess/subagents", "a2", {"agentType": "code-reviewer"})
    # Backdate the cache file so it reads as older than max_age_seconds.
    old_time = time.time() - 100
    os.utime(cache_path, (old_time, old_time))

    index2 = sa.build_identity_index(
        meta_roots=[str(meta_root)],
        output_roots=[str(output_root)],
        cache_path=cache_path,
        max_age_seconds=10,
    )
    assert "a2" in index2


def test_build_identity_index_force_rebuild_bypasses_fresh_cache(tmp_path):
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = str(tmp_path / "cache.json")
    sa.build_identity_index(meta_roots=[str(meta_root)], output_roots=[str(output_root)], cache_path=cache_path)

    _write_meta(meta_root, "proj/sess/subagents", "a2", {"agentType": "code-reviewer"})
    index2 = sa.build_identity_index(
        meta_roots=[str(meta_root)],
        output_roots=[str(output_root)],
        cache_path=cache_path,
        max_age_seconds=3600,
        force_rebuild=True,
    )
    assert "a2" in index2


def test_build_identity_index_corrupt_cache_triggers_rebuild(tmp_path):
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{not valid json", encoding="utf-8")

    index = sa.build_identity_index(
        meta_roots=[str(meta_root)], output_roots=[str(output_root)], cache_path=str(cache_path)
    )
    assert index["a1"].agent_type == "implement"


def test_load_cached_index_never_scans_filesystem(tmp_path):
    """The per-dispatch gate path's function: even with REAL recoverable
    data sitting in the discovery roots, load_cached_index must return {}
    when no cache file exists yet -- it must NEVER trigger a scan."""
    meta_root = tmp_path / "projects"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = str(tmp_path / "never_written.json")
    assert not os.path.isfile(cache_path)

    result = sa.load_cached_index(cache_path=cache_path)
    assert result == {}


def test_load_cached_index_ignores_staleness(tmp_path):
    """Unlike build_identity_index, load_cached_index has NO freshness
    check -- an old cache is still used rather than degrading to {}."""
    meta_root = tmp_path / "projects"
    output_root = tmp_path / "claude-501"
    _write_meta(meta_root, "proj/sess/subagents", "a1", {"agentType": "implement"})
    cache_path = str(tmp_path / "cache.json")
    sa.build_identity_index(meta_roots=[str(meta_root)], output_roots=[str(output_root)], cache_path=cache_path)
    old_time = time.time() - 100_000
    os.utime(cache_path, (old_time, old_time))

    result = sa.load_cached_index(cache_path=cache_path)
    assert result["a1"].agent_type == "implement"


def test_load_cached_index_corrupt_file_returns_empty(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("not json at all", encoding="utf-8")
    assert sa.load_cached_index(cache_path=str(cache_path)) == {}


def test_recovered_identity_round_trip_to_dict_from_dict():
    ident = sa.RecoveredIdentity(
        agent_type="implement",
        model="claude-sonnet-5",
        label="l",
        phase="p",
        workflow_run_id="wf_1",
        reported_tokens=99,
        agent_type_source="meta.json",
        model_source="workflow_output",
    )
    restored = sa.RecoveredIdentity.from_dict(ident.to_dict())
    assert restored == ident


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _write_ledger(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_cli_coverage_end_to_end(tmp_path):
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            _ledger_row(agent_id="a1", model="claude-sonnet-5", agent_type="implement"),
            _ledger_row(agent_id="a2", model=None, agent_type="workflow-subagent"),
        ],
    )
    meta_root = tmp_path / "projects"
    _write_meta(meta_root, "proj/sess/subagents", "a2", {"agentType": "trade-site", "model": "sonnet"})
    cache_path = str(tmp_path / "cache.json")

    code, payload = sa.run(
        [
            "coverage",
            "--ledger",
            str(ledger_path),
            "--meta-roots",
            str(meta_root),
            "--output-roots",
            str(tmp_path / "no-output-here"),
            "--cache-path",
            cache_path,
        ]
    )
    assert code == 0
    assert payload["total_rows"] == 2
    assert payload["model"]["recovered"]["rows"] == 1


def test_cli_enrich_writes_out_file(tmp_path):
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(ledger_path, [_ledger_row(agent_id="a1", model=None)])
    out_path = tmp_path / "enriched.jsonl"
    cache_path = str(tmp_path / "cache.json")

    code, payload = sa.run(
        [
            "enrich",
            "--ledger",
            str(ledger_path),
            "--meta-roots",
            str(tmp_path / "no-meta-here"),
            "--output-roots",
            str(tmp_path / "no-output-here"),
            "--cache-path",
            cache_path,
            "--out",
            str(out_path),
        ]
    )
    assert code == 0
    assert payload["written"] == 1
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    enriched = json.loads(lines[0])
    assert "attribution" in enriched


def test_cli_enrich_stdout_mode_returns_rows_payload(tmp_path):
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(ledger_path, [_ledger_row(agent_id="a1")])
    cache_path = str(tmp_path / "cache.json")
    code, payload = sa.run(
        [
            "enrich",
            "--ledger",
            str(ledger_path),
            "--meta-roots",
            str(tmp_path / "no-meta"),
            "--output-roots",
            str(tmp_path / "no-output"),
            "--cache-path",
            cache_path,
        ]
    )
    assert code == 0
    assert isinstance(payload["rows"], list) and len(payload["rows"]) == 1


def test_cli_missing_ledger_reports_zero_rows_not_an_error(tmp_path):
    code, payload = sa.run(
        [
            "coverage",
            "--ledger",
            str(tmp_path / "does-not-exist.jsonl"),
            "--meta-roots",
            str(tmp_path / "no-meta"),
            "--output-roots",
            str(tmp_path / "no-output"),
            "--cache-path",
            str(tmp_path / "cache.json"),
        ]
    )
    assert code == 0
    assert payload["total_rows"] == 0


def test_cli_argument_error():
    code, payload = sa.run(["not-a-real-command"])
    assert code == 2
    assert payload == {"error": "argument-error"}


# ---------------------------------------------------------------------------
# FALSIFY 4: cycle_budget.py integration -- fail-closed contract preserved.
# ---------------------------------------------------------------------------

WINDOW = dict(cycle_start_ts="2026-08-28T09:00:00Z", cycle_end_ts="2026-08-28T12:00:00Z")


def test_cycle_budget_still_unknown_with_unrecoverable_row_in_slice(tmp_path):
    """FALSIFY: even with identity_index populated, a matched row whose
    model recovery genuinely fails must still force status=unknown,
    allowed=False -- recovery cannot manufacture a confident price."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "implement",
                "model": None,  # unrecoverable: no entry in the index below
                "tool_use_id": "tu1",
                "agent_id": "unrecoverable-agent",
                "tokens": {"input": 100, "output": 100, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 200,
            }
        ],
    )
    identity_index: dict = {}  # nothing recoverable
    attribution = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        identity_index=identity_index,
        **WINDOW,
    )
    assert attribution.status == "unknown"
    assert attribution.reason == "unpriced-model-in-window"

    decision = cb.decide_cycle_budget(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=None,
        identity_index=identity_index,
        **WINDOW,
    )
    assert decision.allowed is False
    assert decision.status == "unknown"


def test_cycle_budget_recovery_prices_a_matched_row_that_would_otherwise_be_unknown(tmp_path):
    """The positive case: recovery legitimately WIDENS what's knowable --
    a matched row's null model, once recovered, is priced and the cycle's
    spend becomes known/allowed instead of forcing unknown."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "implement",
                "model": None,
                "tool_use_id": "tu1",
                "agent_id": "recoverable-agent",
                "tokens": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1_000_000,
            }
        ],
    )
    identity_index = {"recoverable-agent": sa.RecoveredIdentity(model="claude-sonnet-5")}
    decision = cb.decide_cycle_budget(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=1,
        identity_index=identity_index,
        **WINDOW,
    )
    assert decision.status == "known"
    assert decision.allowed is True
    assert decision.spent_usd == pytest.approx(_usd_sonnet(input=1_000_000))  # 1M input tokens, sonnet


def test_cycle_budget_recovery_reclassifies_excluded_placeholder_as_ambiguous(tmp_path):
    """The core motivating case (#4498): a null-session, generic
    "workflow-subagent" row is silently EXCLUDED today. Once its TRUE
    agent_type recovers to something this cycle declared, it must become
    AMBIGUOUS (forcing unknown) rather than staying silently excluded --
    widening caution, never weakening it."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "implement",
                "model": "claude-sonnet-5",
                "tool_use_id": "tu-known",
                "agent_id": "known-agent",
                "tokens": {"input": 1000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1000,
            },
            {
                "ts": "2026-08-28T10:05:00Z",
                "session": None,
                "agent_type": "workflow-subagent",
                "model": None,
                "tool_use_id": None,
                "agent_id": "anonymous-agent",
                "tokens": {"input": 500, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 500,
            },
        ],
    )

    # WITHOUT recovery: the anonymous row is EXCLUDED (agent_type
    # "workflow-subagent" is not in known_agent_types) -- spend looks known.
    baseline = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert baseline.status == "known"
    assert baseline.excluded_rows == 1

    # WITH recovery revealing the anonymous row is really "trade-site" (a
    # type this cycle DOES declare): it must now be AMBIGUOUS -> unknown.
    identity_index = {"anonymous-agent": sa.RecoveredIdentity(agent_type="trade-site")}
    recovered = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        identity_index=identity_index,
        **WINDOW,
    )
    assert recovered.status == "unknown"
    assert recovered.reason == "ambiguous-unjoined-rows-in-window"
    assert recovered.ambiguous_rows == 1


def test_falsify_cycle_budget_recovery_never_downgrades_ambiguous_to_excluded(tmp_path):
    """BLOCKER 2 (round 8, 2026-08-28), the missing MIRROR-IMAGE direction:
    the test above already covers placeholder-UNDECLARED -> recovered-
    DECLARED (correctly becomes ambiguous). This covers the reverse:
    placeholder-DECLARED -> recovered-UNDECLARED. A null-session row whose
    ORIGINAL agent_type is the placeholder "workflow-subagent" -- which the
    caller HAS declared in known_agent_types, exactly what a caller must do
    to catch its own unjoined rows at all -- is AMBIGUOUS pre-recovery. If
    `enrich_row()`'s overwrite of the row's agent_type to a REAL but
    UNDECLARED recovered value silently downgrades it to EXCLUDED, that
    directly contradicts this module's own written guarantee ("Recovery
    NEVER ... turns AMBIGUOUS into ... EXCLUDED"). It must stay AMBIGUOUS
    either way."""
    known_types_with_placeholder = frozenset(KNOWN_TYPES | {"workflow-subagent"})
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:05:00Z",
                "session": None,
                "agent_type": "workflow-subagent",  # placeholder -- but DECLARED by the caller
                "model": "claude-opus-5",
                "tool_use_id": None,
                "agent_id": "AID9",
                "tokens": {"input": 0, "output": 24_000_000, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 24_000_000,
            }
        ],
    )

    # WITHOUT recovery: ambiguous (its own declared placeholder type) ->
    # correctly forces unknown.
    baseline = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=known_types_with_placeholder,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert baseline.status == "unknown"
    assert baseline.reason == "ambiguous-unjoined-rows-in-window"
    assert baseline.ambiguous_rows == 1

    # WITH recovery, EITHER mechanism, resolving to a REAL but UNDECLARED
    # type -- must STILL be ambiguous, never silently excluded.
    identity_index = {
        "AID9": sa.RecoveredIdentity(agent_type="trade-electrical", agent_type_source="meta.json")
    }
    recovered = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=known_types_with_placeholder,
        expected_dispatch_count=None,
        identity_index=identity_index,
        **WINDOW,
    )
    assert recovered.status == "unknown"
    assert recovered.reason == "ambiguous-unjoined-rows-in-window"
    assert recovered.ambiguous_rows == 1
    assert recovered.excluded_rows == 0

    # Mechanism 2 -- the ledger-sibling join alone, no external cache
    # needed: a second row sharing the SAME agent_id, still session:null,
    # that carries the real "code-reviewer" type as first-party data.
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:05:00Z",
                "session": None,
                "agent_type": "workflow-subagent",
                "model": "claude-opus-5",
                "tool_use_id": None,
                "agent_id": "AID9",
                "tokens": {"input": 0, "output": 24_000_000, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 24_000_000,
            },
            {
                "ts": "2026-08-28T10:06:00Z",
                "session": None,
                "agent_type": "trade-electrical",  # real, first-party, undeclared -- widens via sibling join
                "model": "claude-opus-5",
                "tool_use_id": "tu-sibling",
                "agent_id": "AID9",
                "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 0,
            },
        ],
    )
    sibling_only = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=known_types_with_placeholder,
        expected_dispatch_count=None,
        identity_index={},  # no external cache -- pure ledger-sibling join
        **WINDOW,
    )
    assert sibling_only.status == "unknown"
    assert sibling_only.reason == "ambiguous-unjoined-rows-in-window"


def test_cycle_budget_recovered_placeholder_type_flips_denial_to_allowance_and_is_visible(tmp_path):
    """BLOCKER 5 + 6 (2026-08-28), the real reproduced combination: a
    MATCHED row (session already equals this cycle's own) with a
    PLACEHOLDER agent_type ("workflow-subagent") recovers, via the identity
    index, to a real DECLARED type with a priced model -- flipping what
    would otherwise be a real denial (unexpected-agent-type-for-session)
    into a real allowance. The caller must be able to SEE that this
    'known'/allowed verdict rests partly on an inferred, not measured,
    identity via `recovered_agent_type_rows`/`recovered_model_rows` --
    reading spend_attribution's own `attribution` provenance block, not the
    bare (already-overwritten) agent_type/model fields."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "workflow-subagent",  # placeholder -- the pre-fix row would DENY here
                "model": None,
                "tool_use_id": "tu1",
                "agent_id": "placeholder-agent",
                "tokens": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1_000_000,
            }
        ],
    )

    # WITHOUT recovery: agent_type "workflow-subagent" is not a declared
    # type for a MATCHED row -- a real, correct denial.
    baseline = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert baseline.status == "unknown"
    assert baseline.reason == "unexpected-agent-type-for-session"

    # WITH recovery: the SAME row's true identity is "implement" (a
    # declared type) with a priced model -- now known/allowed.
    identity_index = {
        "placeholder-agent": sa.RecoveredIdentity(
            agent_type="implement",
            agent_type_source="meta.json",
            model="claude-sonnet-5",
            model_source="workflow_output",
        )
    }
    decision = cb.decide_cycle_budget(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=1,
        identity_index=identity_index,
        **WINDOW,
    )
    assert decision.status == "known"
    assert decision.allowed is True  # the flip: denial -> allowance
    assert decision.spent_usd == pytest.approx(_usd_sonnet(input=1_000_000))
    # The provenance-visibility fix: a caller CAN tell this rests on
    # inference, without inspecting the bare (already-overwritten) fields.
    assert decision.attribution.recovered_agent_type_rows == 1
    assert decision.attribution.recovered_model_rows == 1
    assert decision.attribution.to_dict()["recovered_agent_type_rows"] == 1
    assert decision.attribution.to_dict()["recovered_model_rows"] == 1


def test_cycle_budget_recovery_to_undeclared_type_stays_denied_not_flipped(tmp_path):
    """BLOCKER 6's paired negative case: recovery to a type this cycle
    never declared must NOT flip a matched row into an allowance -- it must
    stay denied/unknown, exactly like an original (non-recovered)
    undeclared type would."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "workflow-subagent",
                "model": None,
                "tool_use_id": "tu1",
                "agent_id": "undeclared-agent",
                "tokens": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1_000_000,
            }
        ],
    )
    identity_index = {
        "undeclared-agent": sa.RecoveredIdentity(
            agent_type="trade-electrical",  # NOT in KNOWN_TYPES
            agent_type_source="meta.json",
            model="claude-sonnet-5",
            model_source="workflow_output",
        )
    }
    decision = cb.decide_cycle_budget(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=1,
        identity_index=identity_index,
        **WINDOW,
    )
    assert decision.allowed is False
    assert decision.status == "unknown"
    assert decision.attribution.reason == "unexpected-agent-type-for-session"
    assert decision.attribution.recovered_agent_type_rows == 1  # visible, but did NOT flip the verdict


def test_cycle_budget_no_identity_index_is_byte_for_byte_unchanged(tmp_path):
    """identity_index defaults to None -- must be IDENTICAL to calling
    without the parameter at all (pre-recovery behavior preserved exactly)."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "implement",
                "model": "claude-sonnet-5",
                "tool_use_id": "tu1",
                "agent_id": "agentA",
                "tokens": {"input": 1000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1000,
            }
        ],
    )
    without_param = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    with_none = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        identity_index=None,
        **WINDOW,
    )
    assert without_param.to_dict() == with_none.to_dict()


def test_cycle_budget_recovery_import_failure_degrades_silently(tmp_path, monkeypatch):
    """If spend_attribution somehow cannot be imported/enriched, cycle_budget
    must degrade to unrecovered rows -- never raise, never weaken the gate."""
    ledger_path = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger_path,
        [
            {
                "ts": "2026-08-28T10:00:00Z",
                "session": "sess-A",
                "agent_type": "implement",
                "model": "claude-sonnet-5",
                "tool_use_id": "tu1",
                "agent_id": "agentA",
                "tokens": {"input": 1000, "output": 0, "cache_read": 0, "cache_creation": 0},
                "tokens_total": 1000,
            }
        ],
    )
    # A malformed "index" (not a Mapping-like usable object) must not crash
    # attribute_cycle_spend -- _apply_identity_recovery catches everything.
    broken_index = object()
    attribution = cb.attribute_cycle_spend(
        str(ledger_path),
        system="test",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        identity_index=broken_index,  # type: ignore[arg-type]
        **WINDOW,
    )
    assert attribution.status == "known"
    assert attribution.spent_usd == pytest.approx(_usd_sonnet(input=1_000))


def test_apply_identity_recovery_returns_rows_unchanged_when_index_empty():
    """BLOCKER 9 (round 4): assert the documented PROPERTY (row count and
    order preserved, content byte-for-byte identical), not object identity
    -- a function that returned an equal COPY would be just as correct and
    would fail an `is` assertion for the wrong reason (a lock-in test on an
    implementation detail, not the actual contract)."""
    rows = [_ledger_row(agent_id="x"), _ledger_row(agent_id="y")]
    result = cb._apply_identity_recovery(rows, {})
    assert result == rows
    assert [r.get("agent_id") for r in result] == [r.get("agent_id") for r in rows]


def test_apply_identity_recovery_degrades_on_enrich_exception(monkeypatch):
    rows = [_ledger_row(agent_id="x")]

    class _Boom:
        def __bool__(self):
            return True

    class _FakeModule:
        @staticmethod
        def enrich_rows(_rows, _index):
            raise RuntimeError("boom")

    monkeypatch.setitem(__import__("sys").modules, "spend_attribution", _FakeModule())
    result = cb._apply_identity_recovery(rows, _Boom())
    assert result == rows
