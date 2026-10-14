"""Tests for model_pin_parity (report-only pin-vs-policy check, #4400).

Falsifiability: the unpinned-fixture case is the RED-without-the-module proof —
an agent with no pin MUST surface as a violation in the report output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import model_pin_parity as mpp  # noqa: E402


def _mk(tmp_path: Path, agents: dict[str, str | None], pins: dict[str, str]):
    adir = tmp_path / "agents"
    adir.mkdir()
    for name, model in agents.items():
        fm = "---\nname: {n}\ndescription: x\n".format(n=name)
        if model is not None:
            fm += f"model: {model}\n"
        fm += "tools: Read\n---\n\nbody model: opus is prose, not a pin.\n"
        (adir / f"{name}.md").write_text(fm)
    policy = tmp_path / "model_policy.json"
    policy.write_text(json.dumps({"agent_pins": pins}))
    return str(adir), str(policy)


def test_clean_roster_zero_violations(tmp_path):
    adir, policy = _mk(
        tmp_path,
        {"alpha": "sonnet", "beta": "opus"},
        {"alpha": "sonnet", "beta": "opus"},
    )
    assert mpp.check(adir, policy, sanctioned_opus={"beta"}, sanctioned_fable=set()) == []


def test_unpinned_agent_is_red(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": None}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert len(v) == 1 and v[0].startswith("missing-pin: alpha.md")


def test_pin_mismatch_detected(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": "opus"}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert len(v) == 1 and "pin-mismatch" in v[0] and "'opus'" in v[0]


def test_unlisted_and_phantom_both_detected(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"ghost": "haiku"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    kinds = sorted(line.split(":", 1)[0] for line in v)
    assert kinds == ["phantom-policy-entry", "unlisted-agent"]


def test_prose_model_string_is_not_a_pin(tmp_path):
    # frontmatter_model must only read the frontmatter block.
    adir, policy = _mk(tmp_path, {"alpha": None}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert v and v[0].startswith("missing-pin")


def test_unreadable_policy_is_one_violation(tmp_path):
    adir, _ = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    v = mpp.check(adir, str(tmp_path / "nope.json"))
    assert len(v) == 1 and v[0].startswith("policy-unreadable")


def test_main_reports_and_always_exits_zero(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": None}, {"alpha": "sonnet"})
    proc = subprocess.run(
        [sys.executable, str(Path(mpp.__file__)), adir, policy],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0  # report-only: NEVER a nonzero exit
    assert "missing-pin" in proc.stdout
    # subprocess main() compares against the REAL OPUS_AGENTS (not injectable
    # over the CLI), so only the fixture finding + summary format are asserted.
    assert "violation(s)" in proc.stdout


def test_module_never_imports_blocking_emitters():
    # Design constraint from the plan review: report-only means the module
    # must not even reference the Stop/PreToolUse blocking emitters.
    src = Path(mpp.__file__).read_text()
    body = src.split('"""', 2)[2]  # strip the module docstring (which names them)
    assert "emit_stop_block" not in body
    assert "emit_pretooluse_deny" not in body


def test_live_runtime_roster_is_parity_clean():
    # The real roster + real policy must be in parity at commit time. This is
    # the standing guard that keeps the two moving together.
    violations = mpp.check(mpp.DEFAULT_AGENTS_DIR, mpp.DEFAULT_POLICY_PATH)
    assert violations == []


def test_sanction_drift_both_directions(tmp_path):
    adir, policy = _mk(
        tmp_path,
        {"alpha": "opus", "beta": "opus"},
        {"alpha": "opus", "beta": "opus"},
    )
    # policy pins alpha+beta opus; sanction covers beta+gamma -> two drifts.
    v = mpp.check(adir, policy, sanctioned_opus={"beta", "gamma"}, sanctioned_fable=set())
    drift = [line for line in v if line.startswith("sanction-drift")]
    assert len(drift) == 2
    assert any("'alpha'" in line and "does not sanction" in line for line in drift)
    assert any("'gamma'" in line and "does not pin it opus" in line for line in drift)


# ---------------------------------------------------------------------------
# fable-sanction-drift (2026-09-19, operator directive: marketing-director
# permanently pinned fable -- plan-reviewer was ALSO pinned the same day but
# narrowed back out the same day, BLOCKER B1, since it is dispatched bare by
# THE ISSUE WHEEL's own unattended nightly schedule; plan-reviewer was later
# restored to the standing pin on 2026-09-20, card [87]. Both seats' standing
# fable pins are RETIRED as of 2026-09-24, operator directive repinning them
# to opus -- sync_agent_rules.FABLE_AGENTS is empty today) -- the identical
# two-machine-readable-copies discipline as sanction-drift above, narrowed
# to the fable subset; these tests exercise the check generically via
# synthetic fixtures, so they remain valid for any FUTURE standing fable pin.
# ---------------------------------------------------------------------------


def test_fable_sanction_drift_accepts_a_real_fable_pin(tmp_path):
    """A fable pin on a seat that IS in FABLE_AGENTS is clean -- no
    fable-sanction-drift, and (since FABLE_AGENTS is a narrowing subset of
    OPUS_AGENTS) no sanction-drift either when the seat is also
    opus-sanctioned."""
    adir, policy = _mk(
        tmp_path,
        {"alpha": "fable", "beta": "opus"},
        {"alpha": "fable", "beta": "opus"},
    )
    v = mpp.check(
        adir,
        policy,
        sanctioned_opus={"alpha", "beta"},
        sanctioned_fable={"alpha"},
    )
    assert not any(line.startswith("fable-sanction-drift") for line in v)
    assert not any(line.startswith("sanction-drift") for line in v)


def test_fable_sanction_drift_flags_an_unsanctioned_fable_pin(tmp_path):
    """The falsifiability case the task asks for directly: a fable pin on a
    seat NOT in FABLE_AGENTS must be flagged, never silently accepted as a
    second, parallel sanctioning mechanism."""
    adir, policy = _mk(
        tmp_path,
        {"rogue": "fable"},
        {"rogue": "fable"},
    )
    v = mpp.check(
        adir,
        policy,
        sanctioned_opus={"rogue"},
        sanctioned_fable=set(),
    )
    drift = [line for line in v if line.startswith("fable-sanction-drift")]
    assert len(drift) == 1
    assert "'rogue'" in drift[0] and "does not sanction it" in drift[0]


def test_fable_sanction_drift_flags_missing_pin_for_sanctioned_seat(tmp_path):
    """The other direction: FABLE_AGENTS sanctions a name the policy does not
    actually pin fable (policy drifted back down, or was never updated)."""
    adir, policy = _mk(
        tmp_path,
        {"alpha": "opus"},
        {"alpha": "opus"},
    )
    v = mpp.check(
        adir,
        policy,
        sanctioned_opus={"alpha"},
        sanctioned_fable={"alpha"},
    )
    drift = [line for line in v if line.startswith("fable-sanction-drift")]
    assert len(drift) == 1
    assert "'alpha'" in drift[0] and "does not pin it fable" in drift[0]


def test_fable_pin_on_opus_agents_member_does_not_trip_sanction_drift(tmp_path):
    """FABLE_AGENTS is a NARROWING subset of OPUS_AGENTS (fable is
    opus-tier-and-above, never a departure) -- a name sanctioned opus AND
    pinned "fable" must not ALSO be flagged sanction-drift just because
    "fable" != "opus" literally. Reproduces the real marketing-director
    shape: in OPUS_AGENTS, pinned "fable"."""
    adir, policy = _mk(
        tmp_path,
        {"alpha": "fable"},
        {"alpha": "fable"},
    )
    v = mpp.check(
        adir,
        policy,
        sanctioned_opus={"alpha"},
        sanctioned_fable={"alpha"},
    )
    assert not any(line.startswith("sanction-drift") for line in v)


def test_live_fable_pins_are_parity_clean():
    """The real roster + real policy's fable pins must be in parity at
    commit time -- the standing guard keeping FABLE_AGENTS and the policy's
    fable agent_pins entries moving together, mirroring
    test_live_runtime_roster_is_parity_clean above."""
    violations = mpp.check(mpp.DEFAULT_AGENTS_DIR, mpp.DEFAULT_POLICY_PATH)
    fable_drift = [line for line in violations if line.startswith("fable-sanction-drift")]
    assert fable_drift == []


def test_name_mismatch_detected(tmp_path):
    adir, policy = _mk(tmp_path, {}, {"real-name": "sonnet"})
    (Path(adir) / "filestem.md").write_text(
        "---\nname: real-name\ndescription: x\nmodel: sonnet\ntools: Read\n---\nbody\n"
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert any(line.startswith("name-mismatch: filestem.md") for line in v)
    # the pin itself matches via the NAME key, so no unlisted/mismatch noise
    assert not any(line.startswith(("unlisted-agent", "pin-mismatch")) for line in v)


# ---------------------------------------------------------------------------
# contract-roster-drift (#4436, agentic-systems-architect
# plan item 7): every sanctioned-Opus EXTENSION agent (OPUS_AGENTS minus the
# two §10 review-boundary agents) must appear in CLAUDE.md's §13 table.
# ---------------------------------------------------------------------------

_CONTRACT_FIXTURE_WITH_ROW = """\
# Fixture contract

## 13. The oversight roster — N standing agents

Some prose.

| agent | lane | trigger |
|---|---|---|
| launch-director (opus) | ranks work | weekly |
| board-steward (sonnet) | tracker truth | 2x/wk |
| test-architect (opus) | test-net review | monthly |
| trust-architect (opus) | security review | monthly |
| agentic-systems-architect (opus) | agentic-systems audit | monthly |

Trailing prose.

---

## 14. Not part of the roster section
"""

_CONTRACT_FIXTURE_MISSING_ROW = _CONTRACT_FIXTURE_WITH_ROW.replace(
    "| agentic-systems-architect (opus) | agentic-systems audit | monthly |\n", ""
)

_EXTENSION_OPUS_AGENTS = {
    "plan-reviewer",
    "code-reviewer",
    "launch-director",
    "test-architect",
    "trust-architect",
    "agentic-systems-architect",
}
_REVIEW_AGENTS = {"plan-reviewer", "code-reviewer"}


def test_contract_roster_drift_red_when_row_missing():
    # RED without the fix: the §13 row for the new agent is absent from the
    # fixture contract -> exactly one contract-roster-drift finding, naming it.
    v = mpp.contract_roster_drift(
        _CONTRACT_FIXTURE_MISSING_ROW, _EXTENSION_OPUS_AGENTS, _REVIEW_AGENTS
    )
    assert len(v) == 1
    assert v[0].startswith("contract-roster-drift: 'agentic-systems-architect'")


def test_contract_roster_drift_green_when_row_present():
    # GREEN with the fix: the row is present -> zero findings.
    v = mpp.contract_roster_drift(
        _CONTRACT_FIXTURE_WITH_ROW, _EXTENSION_OPUS_AGENTS, _REVIEW_AGENTS
    )
    assert v == []


def test_contract_roster_drift_never_flags_review_boundary_agents():
    # False-positive regression: plan-reviewer/code-reviewer are §10 agents,
    # deliberately absent from the §13 table, and must never be flagged even
    # though they are opus-pinned and even when the table is otherwise empty.
    empty_section = "## 13. The oversight roster\n\n| agent | lane | trigger |\n|---|---|---|\n\n---\n"
    v = mpp.contract_roster_drift(empty_section, _EXTENSION_OPUS_AGENTS, _REVIEW_AGENTS)
    kinds = {line.split("'")[1] for line in v}
    assert "plan-reviewer" not in kinds
    assert "code-reviewer" not in kinds
    # every non-review extension agent IS flagged when the table is empty
    assert kinds == {
        "launch-director",
        "test-architect",
        "trust-architect",
        "agentic-systems-architect",
    }


def test_contract_roster_drift_no_section_13_flags_everything():
    v = mpp.contract_roster_drift("no heading here at all", {"launch-director"}, set())
    assert len(v) == 1 and "launch-director" in v[0]


# The public bundle's thin CLAUDE.md announces itself with this exact first-level
# heading. It is the ONLY thing the skip below keys on.
_THIN_CONTRACT_MARKER = "# Operating Contract (thin)"


def _full_live_contract_text() -> str:
    """The live contract's text, or a skip when it is the THIN public contract.

    Both live-contract integration tests parse the §10 sanctioned-Opus bullet
    and the §13 roster table out of ``DEFAULT_CONTRACT_PATH`` (~/.claude/CLAUDE.md).
    Only the full runtime contract carries them; the public bundle ships a thin
    CLAUDE.md (the long-form contract is OPERATING_CONTRACT.md, which has no §13
    roster table either), so there the parse finds nothing and every sanctioned
    agent looks "missing" -- a structural gap, not drift. The thin file is
    detected by its OWN marker heading (``_THIN_CONTRACT_MARKER``), never by the
    absence of a ``## 13.`` heading: keyed on the heading, a renamed or deleted
    §13 in the FULL contract would silently skip the very drift check meant to
    catch it. A full contract with no §13 therefore reaches the assertions and
    goes RED. This is a skip CONDITION, not the ``live_machine`` marker: that
    marker is deselected by the runtime's documented default run, which would
    silently drop these parity pins from the daily suite. A missing contract
    file also still raises, as before.
    """
    with open(mpp.DEFAULT_CONTRACT_PATH, encoding="utf-8") as fh:
        contract_text = fh.read()
    if any(line.startswith(_THIN_CONTRACT_MARKER) for line in contract_text.splitlines()):
        pytest.skip(
            f"{mpp.DEFAULT_CONTRACT_PATH} is the thin public contract (it carries "
            f"{_THIN_CONTRACT_MARKER!r}), so there is no §10/§13 table to compare. "
            "Follow-up: have model_pin_parity.py fall back to OPERATING_CONTRACT.md "
            "for a thin CLAUDE.md, and give that file the §10/§13 tables."
        )
    return contract_text


def test_live_contract_roster_is_drift_clean():
    # Integration proof: the REAL CLAUDE.md + REAL sync_agent_rules constants
    # must be in parity at commit time -- this is what goes RED if the §13 row
    # for agentic-systems-architect is ever removed from the live contract.
    import sync_agent_rules as sar

    contract_text = _full_live_contract_text()
    violations = mpp.contract_roster_drift(
        contract_text, set(sar.OPUS_AGENTS), set(sar.CONTRACT_REVIEW_AGENTS)
    )
    assert violations == []


def test_check_wires_contract_roster_drift_via_contract_path(tmp_path):
    # Integration proof at the check() level: a contract_path fixture missing
    # the row surfaces through the full check() call, not just the pure fn.
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    fixture = tmp_path / "CLAUDE.md"
    fixture.write_text(_CONTRACT_FIXTURE_MISSING_ROW)
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), contract_path=str(fixture))
    assert any(line.startswith("contract-roster-drift") for line in v)


def test_check_with_none_contract_path_never_reads_default_contract(
    tmp_path, monkeypatch
):
    # Hermeticity proof (B3, #4436 fix round): check() with
    # contract_path=None (the default used by every pre-existing tmp_path
    # fixture test) must never open DEFAULT_CONTRACT_PATH. Point the default
    # at a path that DOES exist but is missing the agentic-systems-architect
    # §13 row -- if check() still fell back to it (the pre-fix behavior), the
    # missing row would leak a spurious contract-roster-drift violation into
    # this otherwise-clean fixture. It must not.
    broken_contract = tmp_path / "broken_claude.md"
    broken_contract.write_text(_CONTRACT_FIXTURE_MISSING_ROW)
    monkeypatch.setattr(mpp, "DEFAULT_CONTRACT_PATH", str(broken_contract))
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert v == []


# ---------------------------------------------------------------------------
# _extract_section_13 scoping regression (F4, #4436 fix
# round): with the function mutated to `return contract_text`, every one of
# the 18 pre-existing tests above still passes -- none of them actually
# exercises the §13-only SCOPING, only presence/absence of a row somewhere in
# a small fixture. These two tests close that gap.
# ---------------------------------------------------------------------------

_CONTRACT_FIXTURE_ROW_AFTER_TERMINATOR = """\
# Fixture contract

## 13. The oversight roster -- N standing agents

Some prose.

| agent | lane | trigger |
|---|---|---|
| launch-director (opus) | ranks work | weekly |
| board-steward (sonnet) | tracker truth | 2x/wk |
| test-architect (opus) | test-net review | monthly |
| trust-architect (opus) | security review | monthly |

Trailing prose.

---

## 14. Not part of the roster section

| agent | lane | trigger |
|---|---|---|
| agentic-systems-architect (opus) | agentic-systems audit | monthly |
"""


def test_contract_roster_drift_row_after_terminator_still_flags():
    # The real §13 table (before the terminating `---`) does NOT contain the
    # agentic-systems-architect row; a look-alike row exists later in the
    # document, inside `## 14.`, AFTER §13's terminator. Correct scoping
    # (stop at the first `---` following the `## 13.` heading) must never see
    # that later row, so drift is still (correctly) reported. A mutant that
    # returns the whole `contract_text` unscoped (`return contract_text`)
    # would find the look-alike row anywhere in the document and wrongly
    # report zero violations here -- this is the RED-without-scoping proof.
    v = mpp.contract_roster_drift(
        _CONTRACT_FIXTURE_ROW_AFTER_TERMINATOR, _EXTENSION_OPUS_AGENTS, _REVIEW_AGENTS
    )
    assert len(v) == 1
    assert v[0].startswith("contract-roster-drift: 'agentic-systems-architect'")


_CONTRACT_FIXTURE_STRAY_DASH_ABOVE_TABLE = """\
# Fixture contract

## 13. The oversight roster -- N standing agents

Some prose.

---

| agent | lane | trigger |
|---|---|---|
| launch-director (opus) | ranks work | weekly |
| board-steward (sonnet) | tracker truth | 2x/wk |
| test-architect (opus) | test-net review | monthly |
| trust-architect (opus) | security review | monthly |
| agentic-systems-architect (opus) | agentic-systems audit | monthly |

Trailing prose.

---

## 14. Not part of the roster section
"""


def test_contract_roster_drift_stray_dash_above_table_flags_all_fail_noisy():
    """Documents the INTENDED behavior of a bare `---` terminator (the plan's
    own wording: 'heading to the next `---`'): a stray `---` placed inside
    §13 ABOVE the real table truncates `_extract_section_13`'s return value
    before the table is ever reached, so every sanctioned extension agent
    reads as missing from the (truncated-empty) table. This is deliberately
    fail-noisy -- over-reporting every agent as drifted -- never a silent
    false-clean, which is the failure mode that would actually hide a real
    drift. Not a defect to fix; asserted here so a future change to the
    terminator rule has to consciously decide to keep or change this
    tradeoff, not discover it by accident."""
    v = mpp.contract_roster_drift(
        _CONTRACT_FIXTURE_STRAY_DASH_ABOVE_TABLE, _EXTENSION_OPUS_AGENTS, _REVIEW_AGENTS
    )
    flagged = {line.split("'")[1] for line in v}
    assert flagged == _EXTENSION_OPUS_AGENTS - _REVIEW_AGENTS


# ---------------------------------------------------------------------------
# Ledger-schema / ORACLE-label parity between the agent def and the primer
# (N13, #4436 fix round): the recommendation ledger's
# ten-field schema and the two `ORACLE:` labels are intentionally duplicated
# across both files; this asserts the two copies actually agree.
# ---------------------------------------------------------------------------

# The full field ENUMERATION, asserted as one string: per-field substring
# checks ("id" in text) are satisfied vacuously by common English words and
# can essentially never fail (round-3 review, #4436).
_LEDGER_ENUMERATION = (
    "id, issued_at, claim, metric, metric_command, baseline_value, "
    "target_direction, status: open|moved|withdrawn, checked_at, checked_value"
)
_ORACLE_LABELS = ("churn_report.py", "direct-ledger")


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def test_agent_def_and_primer_ledger_schema_and_oracle_labels_match():
    root = Path(mpp.__file__).resolve().parents[1]
    agent_def = _normalize_ws(
        (root / "agents" / "agentic-systems-architect.md").read_text()
    )
    primer = _normalize_ws(
        (root / "knowledge" / "agentic_systems_architect_primer.md").read_text()
    )
    assert _LEDGER_ENUMERATION in agent_def, (
        "ledger field enumeration missing from agent def"
    )
    assert _LEDGER_ENUMERATION in primer, "ledger field enumeration missing from primer"
    for label in _ORACLE_LABELS:
        assert f"ORACLE: {label}" in agent_def, (
            f"ORACLE: {label} missing from agent def"
        )
        assert f"ORACLE: {label}" in primer, f"ORACLE: {label} missing from primer"
    # The metric_command guard is canonical in the PRIMER (§16); the agent def
    # points at it rather than carrying a second copy that could drift.
    #
    # This direction was INVERTED by 908c05b (2026-09-08), which relocated the
    # full spec into the primer and left the agent def citing it. The assertion
    # below still demanded the old direction and had been failing ever since --
    # 13 days of a red parity test that read as "the guard was deleted" when the
    # guard had in fact moved and grown a real executable enforcer
    # (hooks/validate_agentarch_ledger.py).
    #
    # FOUR directions are pinned, so neither a relocation nor a duplicate
    # can pass silently:
    #   1+2. the spec and its pointer term live in the primer;
    #   3.   the agent def CITES it -- asserted via the literal "primer §16",
    #        NOT the bare term `metric_command`, which is vacuous here:
    #        _LEDGER_ENUMERATION (line ~462) itself contains the substring
    #        "metric_command" and is already asserted in agent_def above, so
    #        a `"metric_command" in agent_def` check is implied by that and
    #        can never independently fail. Deleting the whole delegation
    #        paragraph left it GREEN. "§16" alone is also insufficient --
    #        other §16 references survive that deletion.
    #   4.   the agent def does NOT carry a second copy. Without this the
    #        inversion loses the very property the original comment existed
    #        for: both files could hold full copies and drift apart.
    assert "shlex.split" in primer, "flag-allowlist guard missing from primer"
    assert "flag-allowlist" in primer, "guard pointer missing from primer"
    assert "primer §16" in agent_def, (
        "agent def no longer cites primer §16, the spec it delegates the guard to"
    )
    assert "shlex.split" not in agent_def, (
        "agent def carries a second copy of the guard spec; primer §16 is canonical"
    )


# ---------------------------------------------------------------------------
# unpinned-live-agent-type / unsanctioned-fable-dispatch (AA-0063, 2026-09-01
# agentic-systems-architect audit / gate-optimization plan waste-elimination
# P2): cross-reference the REAL spend ledger against the on-disk roster +
# policy pins.
# ---------------------------------------------------------------------------

import datetime as _datetime  # noqa: E402


def _spend_row(**overrides: object) -> dict:
    base: dict = {
        "ts": "2026-09-01T10:00:00Z",
        "agent_type": "mystery-type",
        "model": "claude-sonnet-5",
    }
    base.update(overrides)
    return base


_NOW = _datetime.datetime(2026, 9, 1, 12, 0, 0, tzinfo=_datetime.timezone.utc)


def test_live_agent_types_excludes_none_and_empty_but_keeps_workflow_subagent():
    rows = [
        _spend_row(agent_type=None),
        _spend_row(agent_type=""),
        _spend_row(agent_type="workflow-subagent"),
        _spend_row(agent_type="general-purpose"),
    ]
    types = mpp.live_agent_types(rows, _NOW)
    assert types == {"workflow-subagent", "general-purpose"}


def test_live_agent_types_excludes_rows_outside_the_window():
    old = _spend_row(agent_type="stale-type", ts="2026-07-01T00:00:00Z")
    fresh = _spend_row(agent_type="fresh-type", ts="2026-08-30T00:00:00Z")
    types = mpp.live_agent_types([old, fresh], _NOW, days=30)
    assert types == {"fresh-type"}


def test_unpinned_live_agent_type_flags_new_type_red_without_governance():
    # RED without the fix: a real dispatch with no file and no pin surfaces.
    v = mpp.unpinned_live_agent_types({"mystery-type"}, known_files=set(), pins={})
    assert len(v) == 1
    assert v[0].startswith("unpinned-live-agent-type: 'mystery-type'")


def test_unpinned_live_agent_type_skips_known_pin():
    v = mpp.unpinned_live_agent_types(
        {"general-purpose"}, known_files=set(), pins={"general-purpose": "sonnet"}
    )
    assert v == []


def test_unpinned_live_agent_type_skips_known_file():
    v = mpp.unpinned_live_agent_types({"implement"}, known_files={"implement"}, pins={})
    assert v == []


def test_unsanctioned_fable_dispatch_flags_and_counts_grouped_by_type():
    rows = [
        _spend_row(agent_type="general-purpose", model="claude-fable-5"),
        _spend_row(agent_type="general-purpose", model="claude-fable-5"),
        _spend_row(agent_type="general-purpose", model="claude-sonnet-5"),
    ]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {"general-purpose": "sonnet"})
    assert len(v) == 1
    assert "'general-purpose'" in v[0] and "2 spend row(s)" in v[0]


def test_unsanctioned_fable_dispatch_not_flagged_when_pin_is_fable():
    rows = [_spend_row(agent_type="fable-agent", model="claude-fable-5")]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {"fable-agent": "fable"})
    assert v == []


def test_unsanctioned_fable_dispatch_excludes_rows_outside_window():
    rows = [
        _spend_row(agent_type="x", model="claude-fable-5", ts="2026-01-01T00:00:00Z")
    ]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {})
    assert v == []


def test_unsanctioned_fable_dispatch_catches_context_window_suffixed_variant():
    # Item 10 (2026-09-01 fix round): an exact-literal match on "claude-fable-5"
    # silently let a suffixed variant like "claude-fable-5[1m]" slip through
    # uncounted. RED without the prefix-match fix.
    rows = [_spend_row(agent_type="general-purpose", model="claude-fable-5[1m]")]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {"general-purpose": "sonnet"})
    assert len(v) == 1
    assert "claude-fable-5[1m]" in v[0]


def test_unsanctioned_fable_dispatch_lists_multiple_variants_seen_for_one_type():
    rows = [
        _spend_row(agent_type="general-purpose", model="claude-fable-5"),
        _spend_row(agent_type="general-purpose", model="claude-fable-5[1m]"),
    ]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {"general-purpose": "sonnet"})
    assert len(v) == 1
    assert "claude-fable-5" in v[0] and "claude-fable-5[1m]" in v[0]
    assert "2 spend row(s)" in v[0]


def test_unsanctioned_fable_dispatch_never_matches_an_unrelated_model():
    rows = [_spend_row(agent_type="x", model="claude-sonnet-5")]
    v = mpp.unsanctioned_fable_dispatches(rows, _NOW, 30, {})
    assert v == []


def test_check_wires_spend_checks_via_spend_path(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(
        json.dumps(_spend_row(agent_type="mystery-type"))
        + "\n"
        + json.dumps(_spend_row(agent_type="mystery-type", model="claude-fable-5"))
        + "\n"
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), spend_path=str(spend), now=_NOW)
    kinds = sorted(line.split(":", 1)[0] for line in v)
    assert kinds == ["unpinned-live-agent-type", "unsanctioned-fable-dispatch"]


def test_check_with_none_spend_path_never_reads_default_spend(tmp_path, monkeypatch):
    # Hermeticity proof (mirrors the contract_path equivalent above): check()
    # with spend_path=None (every pre-existing tmp_path fixture test) must
    # never open DEFAULT_SPEND_PATH. Point the default at a ledger that DOES
    # exist and DOES carry an unpinned type -- if check() still fell back to
    # it, that finding would leak into this otherwise-clean fixture. It must
    # not.
    broken_spend = tmp_path / "broken_spend.jsonl"
    broken_spend.write_text(json.dumps(_spend_row(agent_type="mystery-type")) + "\n")
    monkeypatch.setattr(mpp, "DEFAULT_SPEND_PATH", str(broken_spend))
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert v == []


def test_catchall_pins_never_trip_phantom_policy_entry(tmp_path):
    # RED without the CATCHALL_TYPES_WITHOUT_FILES exemption: pinning a
    # catch-all type with no on-disk file (AA-0063's entire point) would
    # otherwise trip the pre-existing phantom-policy-entry check.
    adir, policy = _mk(
        tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet", "general-purpose": "sonnet"}
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert v == []


def test_catchall_exemption_does_not_hide_a_genuinely_stale_pin(tmp_path):
    # A real (non-catch-all) pin whose file was deleted is still reported.
    adir, policy = _mk(
        tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet", "ghost-agent": "sonnet"}
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set())
    assert len(v) == 1
    assert v[0].startswith("phantom-policy-entry: agent_pins['ghost-agent']")


def test_live_spend_cross_reference_runs_clean_against_real_pinned_types():
    # Integration proof: the real ledger's six AA-0063 catch-all types must
    # not surface as unpinned now that they carry a real policy pin.
    # Item 21 (2026-09-01 fix round): a POSITIVE precondition, so this test
    # can never pass VACUOUSLY -- if none of the six types happen to appear
    # in the live 30-day window at all, "not flagged" would be trivially
    # true and prove nothing; skip with a reason instead of a false green.
    rows = mpp._load_spend_rows(mpp.DEFAULT_SPEND_PATH)
    now = _datetime.datetime.now(_datetime.timezone.utc)
    live_types = mpp.live_agent_types(rows, now)
    present = live_types & mpp.CATCHALL_TYPES_WITHOUT_FILES
    if not present:
        pytest.skip(
            "no AA-0063 catch-all agent_type appears in the live 30-day spend window"
        )
    v = mpp.check(
        mpp.DEFAULT_AGENTS_DIR,
        mpp.DEFAULT_POLICY_PATH,
        spend_path=mpp.DEFAULT_SPEND_PATH,
    )
    for name in present:
        assert not any(
            f"'{name}'" in line for line in v if line.startswith("unpinned-live-agent-type")
        )


# ---------------------------------------------------------------------------
# Item 9 (2026-09-01 fix round): a live-dispatching product-domain agent
# type that is sanctioned to be governed in ITS OWN repo (CLAUDE.md's
# preamble carve-out, Phase 2 not yet executed) must never be flagged as
# unpinned here -- the violation text would be factually wrong for it.
# Client built-ins (Explore/Plan) have no home to pin at all, on this
# client, and must also never be flagged.
# ---------------------------------------------------------------------------


def test_load_repo_registry_expands_and_skips_malformed_entries(tmp_path):
    registry = tmp_path / "repo_registry.json"
    registry.write_text(
        json.dumps(
            {
                "repos": {
                    "good": {"root": "~/Desktop/SomeRepo"},
                    "no_root": {},
                    "not_a_dict": "oops",
                }
            }
        )
    )
    result = mpp._load_repo_registry(str(registry))
    assert result == {"good": os.path.expanduser("~/Desktop/SomeRepo")}


def test_load_repo_registry_missing_file_is_empty_not_an_error(tmp_path):
    assert mpp._load_repo_registry(str(tmp_path / "nope.json")) == {}


def test_registered_repo_agent_names_reads_frontmatter_name_and_stem_fallback(tmp_path):
    repo_root = tmp_path / "someproduct"
    agents_dir = repo_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "trade-plumbing.md").write_text(
        "---\nname: trade-plumbing\ndescription: x\nmodel: sonnet\ntools: Read\n---\nbody\n"
    )
    (agents_dir / "nofm.md").write_text("no frontmatter at all\n")
    registry = tmp_path / "repo_registry.json"
    registry.write_text(
        json.dumps({"repos": {"someproduct": {"root": str(repo_root)}}})
    )
    names = mpp.registered_repo_agent_names(str(registry))
    assert names == {"trade-plumbing", "nofm"}


def test_registered_repo_agent_names_missing_agents_dir_is_empty(tmp_path):
    repo_root = tmp_path / "someproduct"
    repo_root.mkdir()
    registry = tmp_path / "repo_registry.json"
    registry.write_text(
        json.dumps({"repos": {"someproduct": {"root": str(repo_root)}}})
    )
    assert mpp.registered_repo_agent_names(str(registry)) == set()


def test_unpinned_live_agent_type_exempts_names_in_exempt_set():
    v = mpp.unpinned_live_agent_types(
        {"trade-plumbing", "mystery-type"},
        known_files=set(),
        pins={},
        exempt={"trade-plumbing"},
    )
    assert len(v) == 1
    assert v[0].startswith("unpinned-live-agent-type: 'mystery-type'")


def test_check_exempts_registered_repo_agent_type_via_repo_registry_path(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    repo_root = tmp_path / "someproduct"
    agents_dir = repo_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "trade-plumbing.md").write_text(
        "---\nname: trade-plumbing\ndescription: x\nmodel: sonnet\ntools: Read\n---\nbody\n"
    )
    registry = tmp_path / "repo_registry.json"
    registry.write_text(
        json.dumps({"repos": {"someproduct": {"root": str(repo_root)}}})
    )
    spend = tmp_path / "spend.jsonl"
    spend.write_text(json.dumps(_spend_row(agent_type="trade-plumbing")) + "\n")

    v = mpp.check(
        adir,
        policy,
        sanctioned_opus=set(), sanctioned_fable=set(),
        spend_path=str(spend),
        now=_NOW,
        repo_registry_path=str(registry),
    )
    assert v == []


def test_check_without_repo_registry_path_still_flags_the_type(tmp_path):
    # repo_registry_path=None (the default) means the exemption is never
    # consulted -- confirms it's genuinely opt-in, like contract_path.
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(json.dumps(_spend_row(agent_type="trade-plumbing")) + "\n")
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), spend_path=str(spend), now=_NOW)
    assert len(v) == 1
    assert v[0].startswith("unpinned-live-agent-type: 'trade-plumbing'")


def test_check_exempts_client_builtin_explore_and_plan(tmp_path):
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(
        json.dumps(_spend_row(agent_type="Explore"))
        + "\n"
        + json.dumps(_spend_row(agent_type="Plan"))
        + "\n"
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), spend_path=str(spend), now=_NOW)
    assert v == []


def test_check_exempts_client_builtin_claude(tmp_path):
    # Nit 4 (2026-09-01 fix round 2): the fourth catch-all CLAUDE.md §1
    # names alongside Explore/Plan.
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(json.dumps(_spend_row(agent_type="claude")) + "\n")
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), spend_path=str(spend), now=_NOW)
    assert v == []


def test_live_pin_parity_read_only_drops_to_roughly_the_fable_finding():
    # Item 9's own falsification target: the live cross-reference used to
    # measure 19 violations (18 product-domain/client-builtin false
    # positives + 1 real fable finding); after the fix it must drop to a
    # small number dominated by the real fable finding, never the old 19.
    v = mpp.check(
        mpp.DEFAULT_AGENTS_DIR,
        mpp.DEFAULT_POLICY_PATH,
        spend_path=mpp.DEFAULT_SPEND_PATH,
        repo_registry_path=mpp.DEFAULT_REPO_REGISTRY_PATH,
    )
    unpinned = [line for line in v if line.startswith("unpinned-live-agent-type")]
    assert len(unpinned) < 5, f"expected the false-positive drop, got: {unpinned}"


def test_check_reports_missing_sync_agent_rules_constants_not_unreadable(
    tmp_path, monkeypatch
):
    # Round-4 (#4436): a renamed OPUS_AGENTS is an
    # AttributeError — the drift this module exists to detect — and must be
    # reported as "constants missing", never mislabeled "CLAUDE.md unreadable".
    # Extended 2026-09-19: FABLE_AGENTS is a THIRD consumer of exactly the
    # same class of drift (a renamed/missing constant), so this test also
    # deletes it to keep the fable-sanction-drift block hermetic — without
    # this, monkeypatch.delattr would raise AttributeError on an already-
    # missing constant instead of exercising the "constants missing" path.
    # (Historical note: at the time this test was written, the live
    # FABLE_AGENTS held marketing-director and plan-reviewer; both seats'
    # standing fable pins are RETIRED as of 2026-09-24 and FABLE_AGENTS is
    # now empty, but this test's own fixture policy/roster are fully
    # synthetic and were never affected by that live-state fact either way.)
    import sync_agent_rules

    contract = tmp_path / "claude.md"
    contract.write_text("## 13. roster\n\n---\n")
    monkeypatch.delattr(sync_agent_rules, "OPUS_AGENTS")
    monkeypatch.delattr(sync_agent_rules, "FABLE_AGENTS")
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    v = mpp.check(adir, policy, contract_path=str(contract))
    # ALL THREE consumers of the constants degrade by name — the sanction
    # block (which also read OPUS_AGENTS unguarded until this test caught
    # it), the fable-sanction-drift block, and the contract block — and none
    # mislabels it "unreadable".
    assert v == [
        "sanction-drift: sync_agent_rules constants missing — cannot compare",
        "fable-sanction-drift: sync_agent_rules constants missing — cannot compare",
        "contract-roster-drift: sync_agent_rules constants missing — cannot compare",
    ]


# ---------------------------------------------------------------------------
# pin-tier-mismatch (item 6, model-pin-enforcement build): a spend row whose
# real model normalizes to a family different from its agent_type's RESOLVED
# pin, in either direction, cross-referenced against grants.jsonl.
# ---------------------------------------------------------------------------


def test_normalize_model_family_maps_real_literals():
    assert mpp._normalize_model_family("claude-sonnet-5") == "sonnet"
    assert mpp._normalize_model_family("claude-opus-5[1m]") == "opus"
    assert mpp._normalize_model_family("claude-haiku-4-5-20251001") == "haiku"
    assert mpp._normalize_model_family("claude-fable-5") == "fable"
    assert mpp._normalize_model_family("claude-fable-5[1m]") == "fable"
    assert mpp._normalize_model_family("something-unrecognized") == "unknown"
    assert mpp._normalize_model_family(None) == "unknown"


def test_pin_tier_mismatch_flags_below_pin_dispatch():
    rows = [_spend_row(agent_type="code-reviewer", model="claude-sonnet-5")]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    assert len(v) == 1
    assert "'code-reviewer'" in v[0]
    assert "below its 'opus' pin" in v[0]
    assert "claude-sonnet-5" in v[0]


def test_pin_tier_mismatch_flags_above_pin_dispatch():
    rows = [_spend_row(agent_type="explore", model="claude-opus-5")]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"explore": "sonnet"}, {}, set())
    assert len(v) == 1
    assert "above its 'sonnet' pin" in v[0]


def test_pin_tier_mismatch_prefers_frontmatter_pin_over_policy():
    # The policy says sonnet, but the agent's OWN file pins opus -- the
    # live gate (model_pin_gate.resolved_pin) trusts the frontmatter, so
    # this report must resolve the SAME pin or it would silently disagree
    # with what actually got enforced.
    rows = [_spend_row(agent_type="drifted-agent", model="claude-sonnet-5")]
    v = mpp.pin_tier_mismatches(
        rows, _NOW, 30, {"drifted-agent": "sonnet"}, {"drifted-agent": "opus"}, set()
    )
    assert len(v) == 1
    assert "below its 'opus' pin" in v[0]


def test_pin_tier_mismatch_suppressed_by_matching_grant():
    rows = [_spend_row(agent_type="code-reviewer", model="claude-sonnet-5")]
    v = mpp.pin_tier_mismatches(
        rows, _NOW, 30, {"code-reviewer": "opus"}, {}, {("code-reviewer", "sonnet")}
    )
    assert v == []


def test_pin_tier_mismatch_grant_for_a_different_agent_never_suppresses():
    rows = [_spend_row(agent_type="code-reviewer", model="claude-sonnet-5")]
    v = mpp.pin_tier_mismatches(
        rows, _NOW, 30, {"code-reviewer": "opus"}, {}, {("some-other-agent", "sonnet")}
    )
    assert len(v) == 1


def test_pin_tier_mismatch_matching_model_never_flags():
    rows = [_spend_row(agent_type="code-reviewer", model="claude-opus-5")]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    assert v == []


def test_pin_tier_mismatch_unrecognized_model_never_flags():
    rows = [_spend_row(agent_type="code-reviewer", model="some-experimental-model")]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    assert v == []


def test_pin_tier_mismatch_no_pin_at_all_never_flags():
    rows = [_spend_row(agent_type="kb-verifier", model="claude-sonnet-5")]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {}, {}, set())
    assert v == []


def test_pin_tier_mismatch_excludes_rows_outside_window():
    rows = [
        _spend_row(
            agent_type="code-reviewer",
            model="claude-sonnet-5",
            ts="2026-01-01T00:00:00Z",
        )
    ]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    assert v == []


def test_pin_tier_mismatch_groups_multiple_raw_models_and_counts():
    rows = [
        _spend_row(agent_type="code-reviewer", model="claude-sonnet-5"),
        _spend_row(agent_type="code-reviewer", model="claude-haiku-4-5-20251001"),
    ]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    # sonnet and haiku are two DIFFERENT resolved families -> two lines.
    assert len(v) == 2
    joined = "\n".join(v)
    assert "claude-sonnet-5" in joined and "claude-haiku-4-5-20251001" in joined


# --- WS2.1 step 5: MODEL_OBSERVED_SINCE lookback split ----------------------


def test_row_is_post_land_true_on_and_after_since():
    assert mpp._row_is_post_land(_spend_row(ts="2026-09-21T00:00:00Z"), "2026-09-21")
    assert mpp._row_is_post_land(_spend_row(ts="2026-09-22T00:00:00Z"), "2026-09-21")


def test_row_is_post_land_false_before_since():
    assert not mpp._row_is_post_land(_spend_row(ts="2026-09-20T23:59:59Z"), "2026-09-21")


def test_row_is_post_land_false_on_missing_or_non_string_ts():
    assert not mpp._row_is_post_land({}, "2026-09-21")
    assert not mpp._row_is_post_land({"ts": None}, "2026-09-21")
    assert not mpp._row_is_post_land({"ts": 12345}, "2026-09-21")


def test_row_is_post_land_false_on_malformed_ts_shape():
    # Fix round N1: a raw string compare (no shape check) makes each of
    # these sort ABOVE "2026-09-21" and wrongly count as post-land --
    # contradicting the function's own documented conservative direction.
    assert not mpp._row_is_post_land({"ts": "garbage"}, "2026-09-21")
    assert not mpp._row_is_post_land({"ts": "9999"}, "2026-09-21")
    assert not mpp._row_is_post_land({"ts": "2026/09/21"}, "2026-09-21")


def test_pin_tier_mismatch_since_none_preserves_pre_split_behavior():
    # Default (since=None): every existing call site/test is unaffected --
    # a pre-land row still renders as bare "pin-tier-mismatch:", never split.
    rows = [
        _spend_row(agent_type="code-reviewer", model="claude-sonnet-5", ts="2026-09-01T00:00:00Z")
    ]
    v = mpp.pin_tier_mismatches(rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set())
    assert len(v) == 1
    assert v[0].startswith("pin-tier-mismatch:")
    assert "lookback" not in v[0]


def test_pin_tier_mismatch_since_splits_post_land_from_lookback():
    now = _datetime.datetime(2026, 9, 25, 12, 0, 0, tzinfo=_datetime.timezone.utc)
    rows = [
        _spend_row(agent_type="code-reviewer", model="claude-sonnet-5", ts="2026-09-10T00:00:00Z"),
        _spend_row(agent_type="explore", model="claude-opus-5", ts="2026-09-22T00:00:00Z"),
    ]
    v = mpp.pin_tier_mismatches(
        rows,
        now,
        30,
        {"code-reviewer": "opus", "explore": "sonnet"},
        {},
        set(),
        since="2026-09-21",
    )
    lookback = [ln for ln in v if ln.startswith("pin-tier-mismatch-lookback:")]
    post_land = [
        ln for ln in v if ln.startswith("pin-tier-mismatch:") and "lookback" not in ln
    ]
    assert len(lookback) == 1 and "'code-reviewer'" in lookback[0]
    assert len(post_land) == 1 and "'explore'" in post_land[0]


def test_pin_tier_mismatch_since_all_lookback_when_all_rows_predate_it():
    rows = [
        _spend_row(agent_type="code-reviewer", model="claude-sonnet-5", ts="2026-09-01T00:00:00Z")
    ]
    v = mpp.pin_tier_mismatches(
        rows, _NOW, 30, {"code-reviewer": "opus"}, {}, set(), since="2026-09-21"
    )
    assert len(v) == 1
    assert v[0].startswith("pin-tier-mismatch-lookback:")


def test_load_grants_reads_agent_type_model_pairs(tmp_path):
    d = tmp_path / ".model_exceptions"
    d.mkdir()
    (d / "grants.jsonl").write_text(
        json.dumps(
            {
                "agent_type": "code-reviewer",
                "model": "sonnet",
                "reason": "trivial-tier-confirmatory",
            }
        )
        + "\n"
        + json.dumps(
            {
                "agent_type": "explore",
                "model": "opus",
                "reason": "escalation-hard-debugging",
            }
        )
        + "\n"
    )
    granted = mpp._load_grants(str(d))
    assert granted == {("code-reviewer", "sonnet"), ("explore", "opus")}


def test_load_grants_missing_file_is_empty_set(tmp_path):
    assert mpp._load_grants(str(tmp_path / "does_not_exist")) == set()


def test_load_grants_malformed_line_is_skipped(tmp_path):
    d = tmp_path / ".model_exceptions"
    d.mkdir()
    (d / "grants.jsonl").write_text(
        "not json at all\n"
        + json.dumps({"agent_type": "code-reviewer", "model": "sonnet"})
        + "\n"
    )
    assert mpp._load_grants(str(d)) == {("code-reviewer", "sonnet")}


def test_check_wires_pin_tier_mismatch_via_exceptions_dir(tmp_path):
    # WS2.1 step 5: check() unconditionally passes since=MODEL_OBSERVED_SINCE
    # to pin_tier_mismatches now, so a row must be dated ON/AFTER that land
    # date to be judged as a real (non-lookback) violation here -- `now` is
    # advanced to match so the row also stays inside the 30-day window.
    adir, policy = _mk(tmp_path, {"code-reviewer": "opus"}, {"code-reviewer": "opus"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(
        json.dumps(
            _spend_row(
                agent_type="code-reviewer",
                model="claude-sonnet-5",
                ts="2026-09-22T10:00:00Z",
            )
        )
        + "\n"
    )
    post_land_now = _datetime.datetime(2026, 9, 25, 12, 0, 0, tzinfo=_datetime.timezone.utc)
    v = mpp.check(
        adir,
        policy,
        spend_path=str(spend),
        exceptions_dir=str(tmp_path / ".model_exceptions"),
        now=post_land_now,
    )
    assert any(line.startswith("pin-tier-mismatch:") for line in v)
    assert not any(line.startswith("pin-tier-mismatch-lookback:") for line in v)


def test_check_pin_tier_mismatch_pre_land_row_reported_as_lookback(tmp_path):
    # WS2.1 step 5 exit criterion: "0 violations among rows dated after the
    # land date... it reports 18 today, all lookback artifacts." A row
    # dated BEFORE MODEL_OBSERVED_SINCE must be reported as
    # pin-tier-mismatch-lookback, never as a bare (actionable)
    # pin-tier-mismatch line, through the real check() wiring.
    adir, policy = _mk(tmp_path, {"code-reviewer": "opus"}, {"code-reviewer": "opus"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(
        json.dumps(_spend_row(agent_type="code-reviewer", model="claude-sonnet-5"))
        + "\n"  # default ts is 2026-09-01, before MODEL_OBSERVED_SINCE
    )
    v = mpp.check(
        adir,
        policy,
        spend_path=str(spend),
        exceptions_dir=str(tmp_path / ".model_exceptions"),
        now=_NOW,
    )
    assert any(line.startswith("pin-tier-mismatch-lookback:") for line in v)
    assert not any(
        line.startswith("pin-tier-mismatch:") and not line.startswith("pin-tier-mismatch-lookback:")
        for line in v
    )


def test_check_pin_tier_mismatch_mixed_old_and_new_rows_split_correctly(tmp_path):
    # Falsifiability spec: "a mixed old/new row fixture -> post-land rows
    # judged, pre-land rows listed as lookback" -- both in the SAME check()
    # call, on two DIFFERENT agent_types so each line is unambiguous.
    adir, policy = _mk(
        tmp_path,
        {"code-reviewer": "opus", "explore": "sonnet"},
        {"code-reviewer": "opus", "explore": "sonnet"},
    )
    spend = tmp_path / "spend.jsonl"
    old_row = _spend_row(
        agent_type="code-reviewer", model="claude-sonnet-5", ts="2026-09-10T00:00:00Z"
    )
    new_row = _spend_row(
        agent_type="explore", model="claude-opus-5", ts="2026-09-22T00:00:00Z"
    )
    spend.write_text(json.dumps(old_row) + "\n" + json.dumps(new_row) + "\n")
    now = _datetime.datetime(2026, 9, 25, 12, 0, 0, tzinfo=_datetime.timezone.utc)
    v = mpp.check(
        adir,
        policy,
        spend_path=str(spend),
        exceptions_dir=str(tmp_path / ".model_exceptions"),
        now=now,
    )
    lookback = [ln for ln in v if ln.startswith("pin-tier-mismatch-lookback:")]
    post_land = [
        ln
        for ln in v
        if ln.startswith("pin-tier-mismatch:") and not ln.startswith("pin-tier-mismatch-lookback:")
    ]
    assert any("'code-reviewer'" in ln for ln in lookback)
    assert any("'explore'" in ln for ln in post_land)
    assert not any("'code-reviewer'" in ln for ln in post_land)
    assert not any("'explore'" in ln for ln in lookback)


def test_check_skips_pin_tier_mismatch_when_exceptions_dir_not_supplied(tmp_path):
    # Hermeticity contract: spend_path alone must never pull in a live-path
    # default for exceptions_dir -- pin-tier-mismatch is inert without it,
    # exactly like repo_registry_path is inert without spend_path.
    adir, policy = _mk(tmp_path, {"code-reviewer": "opus"}, {"code-reviewer": "opus"})
    spend = tmp_path / "spend.jsonl"
    spend.write_text(
        json.dumps(_spend_row(agent_type="code-reviewer", model="claude-sonnet-5"))
        + "\n"
    )
    v = mpp.check(adir, policy, spend_path=str(spend), now=_NOW)
    assert not any(line.startswith("pin-tier-mismatch:") for line in v)


# --- contract_section10_drift (ASA audit fix 2, 2026-09-05) -------------------

_S10_FIXTURE_WITH_NAME = (
    "## 10. Review cadence\n\n"
    "- **Sanctioned-Opus extension.** The roster adds agents: `launch-director`,\n"
    "  `test-architect`, `trust-architect`, `agentic-systems-architect`, and\n"
    "  `marketing-director` (department orchestrator).\n\n"
    "## 11. Conventions\n"
)

_S10_FIXTURE_MISSING_NAME = (
    "## 10. Review cadence\n\n"
    "- **Sanctioned-Opus extension.** The roster adds agents: `launch-director`,\n"
    "  `test-architect`, `trust-architect`, and `agentic-systems-architect`.\n\n"
    "## 11. Conventions\n"
)


def test_section10_drift_red_when_name_absent():
    # RED without the fix: marketing-director sanctioned in the tuple but not
    # named in s10's bullet -> exactly one finding, naming it. This is the
    # literal real drift of 2026-09-04/05 that the table-only check missed.
    v = mpp.contract_section10_drift(
        _S10_FIXTURE_MISSING_NAME,
        _EXTENSION_OPUS_AGENTS | {"marketing-director"},
        _REVIEW_AGENTS,
    )
    assert len(v) == 1
    assert "'marketing-director'" in v[0]
    assert "§10" in v[0]


def test_section10_drift_green_when_name_present():
    v = mpp.contract_section10_drift(
        _S10_FIXTURE_WITH_NAME,
        _EXTENSION_OPUS_AGENTS | {"marketing-director"},
        _REVIEW_AGENTS,
    )
    assert v == []


def test_section10_drift_never_flags_review_boundary_agents():
    # plan-reviewer/code-reviewer are the s10 review-boundary agents, excluded
    # from the extension set by construction; never flagged even on an empty s10.
    v = mpp.contract_section10_drift(
        "## 10. Review cadence\n\n## 11. Conventions\n",
        _EXTENSION_OPUS_AGENTS,
        _REVIEW_AGENTS,
    )
    kinds = {line.split("'")[1] for line in v}
    assert "plan-reviewer" not in kinds and "code-reviewer" not in kinds
    assert kinds == _EXTENSION_OPUS_AGENTS - _REVIEW_AGENTS


def test_section10_drift_no_heading_flags_everything():
    # Fail-loud on a contract with no s10 heading, mirroring the missing-s13
    # behavior -- a silently-skipped half would repeat the exact predicate-
    # weaker-than-its-name failure this check exists to close.
    v = mpp.contract_section10_drift("no heading", {"launch-director"}, set())
    assert len(v) == 1 and "launch-director" in v[0]


def test_section10_extraction_stops_at_next_heading():
    # A BACKTICKED name AFTER s10 must not satisfy the s10 requirement --
    # extraction terminates at the next '## ' heading. The post-s10 mention
    # here is deliberately backticked (`launch-director`), the exact token the
    # predicate searches for: under a whole-document-scoping mutation
    # (_extract_section_10 returning contract_text) this test goes RED,
    # which an earlier unbackticked table-row fixture did not (HIGH-tier
    # review mutation proof, 2026-09-05 -- the table-row form passed for the
    # wrong reason). Live stake: code-quality-architect has backticked
    # mentions outside s10, so unscoped matching would silently accept its
    # removal from the s10 bullet.
    text = (
        "## 10. Review cadence\n\nno names here\n\n"
        "## 13. Roster\n\nprose naming `launch-director` outside section 10\n"
        "| agent | lane |\n|---|---|\n| launch-director (opus) | x |\n"
    )
    v = mpp.contract_section10_drift(text, {"launch-director"}, set())
    assert len(v) == 1 and "launch-director" in v[0]


def test_check_wires_contract_section10_drift_via_contract_path(tmp_path):
    # Mirror of test_check_wires_contract_roster_drift_via_contract_path,
    # added after a mutation proof (HIGH-tier review, 2026-09-05) showed that
    # deleting ONLY the check()-level out.extend(contract_section10_drift(...))
    # call site left all six s10 unit tests green -- the pure function was
    # intact while the check was functionally dead ("guard exists, guard
    # never fires", the exact class check_safety_core_parity.py exists to
    # prevent). A s10-shaped finding can ONLY surface through that call site.
    adir, policy = _mk(tmp_path, {"alpha": "sonnet"}, {"alpha": "sonnet"})
    fixture = tmp_path / "CLAUDE.md"
    fixture.write_text(
        "## 10. Review cadence\n\nno sanctioned names here\n\n## 11. Conventions\n"
    )
    v = mpp.check(adir, policy, sanctioned_opus=set(), sanctioned_fable=set(), contract_path=str(fixture))
    assert any("§10's sanctioned-Opus bullet" in line for line in v)


def test_live_contract_section10_is_drift_clean():
    # Integration proof against the REAL contract + REAL constants -- goes RED
    # if any future sanctioned-Opus agent lands in OPUS_AGENTS without being
    # named in s10's bullet (the 2026-09-05 marketing-director gap, F1).
    import sync_agent_rules as sar

    contract_text = _full_live_contract_text()
    violations = mpp.contract_section10_drift(
        contract_text, set(sar.OPUS_AGENTS), set(sar.CONTRACT_REVIEW_AGENTS)
    )
    assert violations == []
