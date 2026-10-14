"""Tests for claude_md_rule_net — the WS3 CLAUDE.md refactor regression net.

Spec source: the module docstring and the master plan §4 / WS3 "3.4
Regression net". Each test names the defect it catches.

The most important test here is the POSITIVE CONTROL. The plan's own words:
"in a single-file scratch copy, delete one known rule and confirm the diff
flags it — a net never seen failing proves nothing."
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import claude_md_rule_net as net  # noqa: E402


# Mirrors the REAL artifact's five-column shape:
#   | id | section | rule | condition | verbatim |
# An earlier version of this fixture had four columns, so the rule text
# landed in the wrong cell and every anchor came back empty -- the tests
# failed against correct code. A fixture that does not match the real
# artifact tests nothing.
_INVENTORY = """# inventory

| id | section | rule | condition | verbatim |
|---|---|---|---|---|
| R-01-01 | 01 | Never run `git stash` in a shared tree. | always | YES |
| R-01-02 | 01 | Prefer `--mode=ci-parity` for local CI. | when running CI | no |
| R-02-01 | 02 | A rule row with no code span at all, only prose. | always | no |
"""


def _mk(tmp_path, claude_body: str, inventory: str = _INVENTORY, reloc: dict | None = None):
    root = tmp_path
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text(claude_body)
    inv = root / "knowledge" / "claude_md_rule_inventory_abc123.md"
    inv.write_text(inventory)
    for rel, body in (reloc or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(root / "CLAUDE.md"), str(inv), str(root)


def test_the_positive_control_passes(tmp_path):
    """THE test. The plan mandates it: a net never seen failing proves
    nothing. This asserts the net DOES flag a deliberately deleted rule."""
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nNever run `git stash` in a shared tree.\nUse `--mode=ci-parity`.\n",
    )
    ok, msg = net.self_test(md, inv, root)
    assert ok, msg


def test_a_deleted_rule_is_flagged(tmp_path):
    """The net's core job, asserted directly rather than only via self_test.

    Uses the NON-verbatim rule deliberately. The verbatim one anchors on
    `git stash`, a phrase that genuinely appears across this repo's real
    knowledge/ files, so deleting it yields `verbatim-changed` (left the
    contract, found elsewhere) rather than `rule-missing` — a correct
    verdict that this test would have mis-read as a failure. Asserting the
    wrong rule name against right behaviour is its own defect class."""
    md, inv, root = _mk(tmp_path, "## 1. Rules\nNever run `git stash` in a shared tree.\n")
    findings = net.check(md, inv, root)
    ids = {f["id"] for f in findings if f["rule"] == "rule-missing"}
    assert "R-01-02" in ids, findings


def test_the_relocation_corpus_is_scoped_to_the_given_root(tmp_path):
    """Anti-leak. `_mk` builds an isolated root, and every check MUST read
    its relocation corpus from THAT root -- never from the real ~/.claude.
    Both anchors in the fixture (`git stash`, `--mode=ci-parity`) genuinely
    appear across this repo's knowledge/ files, so a root-scoping bug would
    silently mark every deleted rule as merely 'relocated' and the net would
    report nothing while appearing to work."""
    md, inv, root = _mk(tmp_path, "## 1. Rules\n(both rules deleted)\n")
    corpus = net._relocation_corpus(root)
    assert "git stash" not in corpus, "relocation corpus leaked outside the given root"
    findings = net.check(md, inv, root)
    missing = {f["id"] for f in findings if f["rule"] == "rule-missing"}
    assert {"R-01-01", "R-01-02"} <= missing, findings


def test_an_intact_file_is_clean(tmp_path):
    """PAIRED RECOVERY: a file carrying every anchored rule reports nothing.
    Without this the net could 'pass' by flagging everything always."""
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nNever run `git stash` in a shared tree.\nUse `--mode=ci-parity`.\n",
    )
    assert net.check(md, inv, root) == []


def test_a_relocated_rule_is_not_missing(tmp_path):
    """The plan's method is RELOCATE, never delete. A non-verbatim rule
    moved into knowledge/ is present, not missing — flagging it would make
    the net fight the refactor it exists to protect."""
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nNever run `git stash` in a shared tree.\n",
        reloc={"knowledge/review_gate_incident_history.md": "historically we used `--mode=ci-parity` here\n"},
    )
    findings = net.check(md, inv, root)
    assert [f["id"] for f in findings if f["rule"] == "rule-missing"] == [], findings


def test_a_relocated_VERBATIM_rule_is_flagged(tmp_path):
    """§3.2's load-bearing set is read MECHANICALLY, in place. Moving one
    out of the contract is a behaviour change even though the prose still
    exists somewhere — this is the distinction the whole verbatim column
    exists to encode."""
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nUse `--mode=ci-parity`.\n",
        reloc={"knowledge/review_gate_incident_history.md": "we used to say: never run `git stash` in a shared tree\n"},
    )
    findings = net.check(md, inv, root)
    assert [f["id"] for f in findings if f["rule"] == "verbatim-changed"] == ["R-01-01"], findings


def test_section_renumbering_is_flagged(tmp_path):
    """~234 inbound `CLAUDE.md §N` citations depend on the numbering; §3.1
    forbids changing it. Only checked when a HEAD text is supplied."""
    body_before = "## 1. A\nNever run `git stash` in a shared tree.\n## 2. B\nUse `--mode=ci-parity`.\n"
    body_after = "## 1. A\nNever run `git stash` in a shared tree.\n## 3. B\nUse `--mode=ci-parity`.\n"
    md, inv, root = _mk(tmp_path, body_after)
    findings = net.check(md, inv, root, head_text=body_before)
    assert [f["rule"] for f in findings if f["rule"] == "section-renumbered"] == [
        "section-renumbered"
    ], findings


def test_unchanged_numbering_is_not_flagged(tmp_path):
    """PAIRED RECOVERY for the case above."""
    body = "## 1. A\nNever run `git stash` in a shared tree.\n## 2. B\nUse `--mode=ci-parity`.\n"
    md, inv, root = _mk(tmp_path, body)
    findings = net.check(md, inv, root, head_text=body)
    assert not [f for f in findings if f["rule"] == "section-renumbered"], findings


def test_a_row_with_no_code_span_is_skipped_not_invented(tmp_path):
    """An inventory row states the rule in the CATALOGUER'S words, so a row
    with no literal token has no searchable anchor. Skipping it is honest;
    inventing a prose-window anchor produced 74 false findings against an
    UNMODIFIED file in an earlier cut of this module."""
    rows = net.parse_inventory(
        str(_mk(tmp_path, "## 1. x\n")[1])
    )
    assert "R-02-01" not in {r["id"] for r in rows}, rows
    assert {"R-01-01", "R-01-02"} <= {r["id"] for r in rows}, rows


def test_an_unreadable_inventory_reports_rather_than_raises(tmp_path):
    """A net must degrade to a report, never take down its caller."""
    md, _, root = _mk(tmp_path, "## 1. x\n")
    findings = net.check(md, str(tmp_path / "nope.md"), root)
    assert [f["rule"] for f in findings] == ["inventory-unreadable"], findings


def test_strict_flag_controls_exit_code(tmp_path):
    """Report-only by default; --strict is opt-in, so the net can be wired
    somewhere unattended without becoming a blocker."""
    md, inv, root = _mk(tmp_path, "## 1. Rules\nUse `--mode=ci-parity`.\n")
    assert net.main(["--root", root, "--file", md, "--inventory", inv]) == 0
    assert net.main(["--root", root, "--file", md, "--inventory", inv, "--strict"]) == 1


def test_the_positive_control_FAILS_when_the_net_is_broken(tmp_path, monkeypatch):
    """NEGATIVE CONTROL FOR THE POSITIVE CONTROL.

    If `check` stops reporting `rule-missing`, `self_test` MUST return False
    — otherwise the control is a rubber stamp and every "positive control
    PASSED" line it prints is worthless.

    This gap was real: mutating self_test's success predicate to `hit = True
    or [...]` made it return PASSED unconditionally with all 11 tests still
    green. `test_the_positive_control_passes` asserts only `ok is True`, so
    it cannot tell a working control from a stubbed one. That is the exact
    "a net never seen failing proves nothing" failure, one level up.
    """
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nNever run `git stash` in a shared tree.\nUse `--mode=ci-parity`.\n",
    )
    monkeypatch.setattr(net, "check", lambda *a, **k: [])
    ok, msg = net.self_test(md, inv, root)
    assert not ok, f"self_test passed against a net that reports nothing: {msg}"


def test_inventory_coverage_reports_the_blind_spot(tmp_path):
    """The ratio must be REAL, not cosmetic. A row with no backticked token
    is unanchorable and silently skipped; the count of those IS the blind
    spot, and `main()` prints it with every verdict so a clean run is never
    read as 'no rule was lost'."""
    md, inv, root = _mk(tmp_path, "## 1. x\n")
    anchored, total = net.inventory_coverage(inv)
    assert total == 3, (anchored, total)   # three R- rows in the fixture
    assert anchored == 2, (anchored, total)  # R-02-01 has no code span
    assert total - anchored == 1


def test_uppercase_section_keys_are_parsed(tmp_path):
    """`R-PRE-*` rows (the preamble section) use an UPPERCASE key. A
    lowercase-only pattern dropped all 26 of them before anchoring ever ran
    — a blind spot inside the blind spot, found only by reconciling a
    reported 260 against a parsed 234."""
    inv = tmp_path / "knowledge" / "claude_md_rule_inventory_abc123.md"
    inv.parent.mkdir(parents=True, exist_ok=True)
    inv.write_text(
        "| id | section | rule | condition | verbatim |\n"
        "|---|---|---|---|---|\n"
        "| R-PRE-01 | PRE | Never run `git stash` in a shared tree. | always | YES |\n"
    )
    rows = net.parse_inventory(str(inv))
    assert [r["id"] for r in rows] == ["R-PRE-01"], rows


def test_an_UNDECLARED_file_does_not_mask_a_deletion(tmp_path):
    """Relocation is DECLARED, not inferred.

    This was two recursive globs over `knowledge/` and `docs/subsystems/`,
    so a rule whose anchor happened to be quoted ANYWHERE in those trees was
    silently marked "relocated" rather than "missing" — 3.8MB of masking
    surface where only ~39KB is real relocation targets, a 99% over-reach.
    Distinctive phrases are quoted all over the documentation, which is why
    requiring corpus-absence once found no self-test victim at all.

    Here `knowledge/some_other_doc.md` quotes the rule but is NOT a declared
    target, so the deletion must still be reported.
    """
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nUse `--mode=ci-parity`.\n",
        reloc={"knowledge/some_other_doc.md": "aside: never run `git stash` in a shared tree\n"},
    )
    findings = net.check(md, inv, root)
    assert [f["id"] for f in findings if f["rule"] == "rule-missing"] == ["R-01-01"], findings


def test_a_DECLARED_target_still_counts_as_relocation(tmp_path):
    """PAIRED RECOVERY: narrowing must not break the sanctioned method.
    The same content in a DECLARED target is a relocation, not a loss —
    otherwise every legitimate trim would report a wall of false findings,
    and the rational response to a noisy net is to stop reading it."""
    md, inv, root = _mk(
        tmp_path,
        "## 1. Rules\nUse `--mode=ci-parity`.\n",
        reloc={
            "knowledge/review_gate_incident_history.md": (
                "aside: never run `git stash` in a shared tree\n"
            )
        },
    )
    findings = net.check(md, inv, root)
    assert [f["id"] for f in findings if f["rule"] == "rule-missing"] == [], findings


def test_every_DECLARED_relocation_target_exists_on_disk():
    """The list is hand-maintained paths; `_relocation_corpus` skips an
    unreadable one SILENTLY — correctly, since a target named before its
    trim lands is normal during a multi-commit refactor. So nothing else
    would catch a TYPO or an upstream RENAME: masking dies for that file and
    the suite stays green.

    Measured: mutating any of the three names NOT hardcoded in another test
    left 16/16 passing. `worktree_integration_flow.md` has already been
    retitled once (2026-09-16), so the rename case is not hypothetical.
    """
    # The checkout this suite runs from (hooks/tests/ -> two levels up), not
    # `~/.claude`: from a clone that is not the live runtime the home-directory
    # copy is some other tree. In the deployed layout the two are the same.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    missing = [
        rel for rel in net._RELOCATION_FILES
        if not os.path.isfile(os.path.join(root, rel))
    ]
    # The rule inventory (the artifact the targets are relocations FROM) is a
    # runtime-only file. A checkout WITH it must have every declared target --
    # that is the typo/rename case this test exists to catch, so it is never
    # skipped there. A bundle without the inventory has no rule net to protect,
    # so a target that is simply not shipped there is not a defect: skip, with
    # the reason (when every target happens to be present the assertion below
    # still runs).
    knowledge_dir = os.path.join(root, "knowledge")
    inventory_shipped = os.path.isdir(knowledge_dir) and any(
        name.startswith("claude_md_rule_inventory_") for name in os.listdir(knowledge_dir)
    )
    if missing and not inventory_shipped:
        pytest.skip(
            f"relocation target(s) {missing} not shipped in this checkout, and "
            "no knowledge/claude_md_rule_inventory_*.md is present either: the "
            "CLAUDE.md rule net's corpus is a runtime-only set"
        )
    assert not missing, (
        f"declared relocation target(s) not on disk: {missing} — fix the typo, "
        f"or drop the entry if the file was intentionally removed"
    )
