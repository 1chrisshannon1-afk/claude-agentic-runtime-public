"""Tests for tools/gtm/exit_contract.py — the GTM mission convergence evaluator.

Assertion identifiers under test are ALWAYS the fully-qualified `GTM-CONV-01`, `GTM-CONV-02`,
`GTM-CONV-03` — never the bare `CONV-0N` form, which may be owned by an unrelated product repo's
own estimate-loop evaluator. This test file asserts against real evaluator output, not
tautologies — each test is written to be RED without the corresponding evaluator logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import exit_contract  # noqa: E402  (import after sys.path shim)
from exit_contract import (  # noqa: E402
    GTM_CONV_01,
    GTM_CONV_02,
    GTM_CONV_03,
    evaluate,
)

DEFAULT_MISSION_ID = "gtm_2026_09_05_test"

_EXIT_CONTRACT_PATH = Path(exit_contract.__file__).resolve()
_TOOLS_GTM_DIR = _EXIT_CONTRACT_PATH.parent
_SCRIPTS_DIR = _TOOLS_GTM_DIR.parent.parent / "scripts"
_REPO_MANIFEST = _SCRIPTS_DIR / "repo_manifest.py"


def _write_ledger(tmp_path, rows):
    path = os.path.join(tmp_path, "gtm_reviewed.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


def _row(
    round_no,
    artifact_id,
    judge,
    verdict,
    severity="minor",
    cause_key=None,
    evidence="marketing/website/templates/index.html:1-10 some evidence",
    mission_id=DEFAULT_MISSION_ID,
    ts="2026-09-05T00:00:00Z",
):
    row = {
        "mission_id": mission_id,
        "round": round_no,
        "artifact_id": artifact_id,
        "judge": judge,
        "verdict": verdict,
        "severity": severity,
        "ts": ts,
    }
    if cause_key is not None:
        row["cause_key"] = cause_key
    if verdict == "DISSENT":
        # DISSENT rows require resolvable evidence per the evidence-or-refuse rule; only omit it
        # deliberately in the dedicated rejection test below. The default evidence string here is
        # deliberately citation-shaped (a file path + locator) so it never trips the softer
        # DEGRADED-GROUNDING heuristic in tests that aren't exercising that assertion.
        row["evidence"] = evidence
    return row


@pytest.fixture
def tmp_ledger_dir(tmp_path):
    return str(tmp_path)


# ---------------------------------------------------------------------------
# GTM-CONV-01 — zero blocker-severity distinct recurring cause_keys (window=1)
# ---------------------------------------------------------------------------


def test_gtm_conv01_met_when_no_recurring_blocker_cause(tmp_ledger_dir):
    """A blocker dissent appearing for the first time in the current round is NOT yet
    "recurring" — GTM-CONV-01 should read MET."""
    rows = [
        _row(
            1, "spec-001", "brand-architect", "DISSENT", severity="blocker", cause_key="stale_copy"
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=1)
    assert result.evaluable
    assert result.assertions[GTM_CONV_01] is True


def test_gtm_conv01_not_met_when_blocker_cause_recurs_across_rounds(tmp_ledger_dir):
    """The SAME blocker-severity cause_key open in round 1 and still open (re-dissented) in
    round 2 is a recurring cause — GTM-CONV-01 must read NOT met."""
    rows = [
        _row(
            1, "spec-001", "brand-architect", "DISSENT", severity="blocker", cause_key="stale_copy"
        ),
        _row(
            2, "spec-001", "brand-architect", "DISSENT", severity="blocker", cause_key="stale_copy"
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=2)
    assert result.evaluable
    assert result.assertions[GTM_CONV_01] is False


# ---------------------------------------------------------------------------
# GTM-CONV-02 — zero fix-caused regressions
# ---------------------------------------------------------------------------


def test_gtm_conv02_met_when_no_regression(tmp_ledger_dir):
    """A pair that CONCURred in round 1 and stays silent (or CONCURs again) in round 2 has not
    regressed — GTM-CONV-02 should read MET."""
    rows = [
        _row(1, "spec-002", "conversion-architect", "CONCUR"),
        _row(2, "spec-002", "conversion-architect", "CONCUR"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=2)
    assert result.evaluable
    assert result.assertions[GTM_CONV_02] is True


def test_gtm_conv02_not_met_when_fix_wave_causes_new_dissent(tmp_ledger_dir):
    """A pair that CONCURred in round N-1 but gets a NEW DISSENT in round N (another artifact's
    fix broke something this judge had already accepted) is a fix-caused regression —
    GTM-CONV-02 must read NOT met."""
    rows = [
        _row(1, "spec-003", "seo-architect", "CONCUR"),
        _row(
            2, "spec-003", "seo-architect", "DISSENT", severity="major", cause_key="regressed_meta"
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=2)
    assert result.evaluable
    assert result.assertions[GTM_CONV_02] is False


# ---------------------------------------------------------------------------
# GTM-CONV-03 — every mandated judge verdicted every in-scope artifact AND zero open dissents
# ---------------------------------------------------------------------------


def test_gtm_conv03_met_when_all_judges_verdicted_and_no_open_dissents(tmp_ledger_dir):
    rows = [
        _row(1, "spec-004", "brand-architect", "CONCUR"),
        _row(1, "spec-004", "content-strategist", "CONCUR"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(
        ledger,
        mission_id=DEFAULT_MISSION_ID,
        current_round=1,
        mandated_judges={"brand-architect", "content-strategist"},
        artifact_ids={"spec-004"},
    )
    assert result.evaluable
    assert result.assertions[GTM_CONV_03] is True


def test_gtm_conv03_not_met_when_a_mandated_judge_never_verdicted_an_artifact(tmp_ledger_dir):
    """content-strategist never reviewed spec-004 in the current round — coverage is incomplete,
    GTM-CONV-03 must read NOT met even though the one recorded verdict is a clean CONCUR."""
    rows = [
        _row(1, "spec-004", "brand-architect", "CONCUR"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(
        ledger,
        mission_id=DEFAULT_MISSION_ID,
        current_round=1,
        mandated_judges={"brand-architect", "content-strategist"},
        artifact_ids={"spec-004"},
    )
    assert result.evaluable
    assert result.assertions[GTM_CONV_03] is False


# ---------------------------------------------------------------------------
# UNEVALUABLE — missing / empty / malformed-line ledgers (never a silent "met")
# ---------------------------------------------------------------------------


def test_uneval_missing_ledger_file(tmp_ledger_dir):
    missing_path = os.path.join(tmp_ledger_dir, "does_not_exist.jsonl")
    result = evaluate(missing_path, mission_id=DEFAULT_MISSION_ID)
    assert result.evaluable is False
    assert result.reason is not None
    assert "GTM convergence" not in result.summary_line()
    assert result.summary_line().startswith("UNEVALUABLE:")


def test_uneval_empty_ledger_file(tmp_ledger_dir):
    path = os.path.join(tmp_ledger_dir, "gtm_reviewed.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("")
    result = evaluate(path, mission_id=DEFAULT_MISSION_ID)
    assert result.evaluable is False
    assert result.summary_line().startswith("UNEVALUABLE:")


def test_uneval_malformed_line(tmp_ledger_dir):
    path = os.path.join(tmp_ledger_dir, "gtm_reviewed.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_row(1, "spec-005", "seo-architect", "CONCUR")) + "\n")
        f.write("{this is not valid json\n")
    result = evaluate(path, mission_id=DEFAULT_MISSION_ID)
    assert result.evaluable is False
    assert result.summary_line().startswith("UNEVALUABLE:")


# ---------------------------------------------------------------------------
# The #4893-shaped case — "met" over open dissents MUST fail
# ---------------------------------------------------------------------------


def test_4893_shaped_open_dissents_never_report_met(tmp_ledger_dir):
    """A ledger with real, still-open DISSENTs must NEVER evaluate as fully converged. This is
    the exact class of bug tracked as GH #4893 against a DIFFERENT, unrelated evaluator: it once
    reported "3 of 3 met" over a ledger holding 9 open dissents because it never actually read
    verdict fields. This evaluator's GTM-CONV-03 leg must report NOT met whenever any open
    dissent pair exists, and the overall met_count must therefore be less than 3."""
    rows = [
        _row(1, "spec-006", "brand-architect", "DISSENT", severity="major", cause_key="c1"),
        _row(1, "spec-007", "content-strategist", "DISSENT", severity="major", cause_key="c2"),
        _row(1, "spec-008", "seo-architect", "DISSENT", severity="minor", cause_key="c3"),
        _row(1, "spec-009", "conversion-architect", "DISSENT", severity="minor", cause_key="c4"),
        _row(1, "spec-010", "pricing-economist", "DISSENT", severity="minor", cause_key="c5"),
        _row(
            1,
            "spec-011",
            "paid-acquisition-strategist",
            "DISSENT",
            severity="minor",
            cause_key="c6",
        ),
        _row(1, "spec-012", "brand-architect", "DISSENT", severity="minor", cause_key="c7"),
        _row(1, "spec-013", "content-strategist", "DISSENT", severity="minor", cause_key="c8"),
        _row(1, "spec-014", "seo-architect", "DISSENT", severity="minor", cause_key="c9"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=1)
    assert result.evaluable
    assert result.assertions[GTM_CONV_03] is False, (
        "GTM-CONV-03 must be NOT met over 9 real open dissents — a 'met' verdict here is exactly "
        "the #4893-class false-positive bug this evaluator exists to prevent."
    )
    assert result.met_count < 3
    assert "3 of 3" not in result.summary_line()


# ---------------------------------------------------------------------------
# Mission isolation (Blocker 1) — the ledger is ONE SHARED FILE across every mission
# ---------------------------------------------------------------------------


def test_mission_isolation_clean_mission_unaffected_by_other_missions_open_dissent(tmp_ledger_dir):
    """A mission that has genuinely converged (all CONCUR) must report MET on every assertion
    even when the SAME ledger file also holds a completely unrelated mission's real open blocker
    dissent. Before the mission_id filter, an unrelated mission's rows leaked into every
    assertion helper and could flip this mission's verdict for no reason connected to its own
    artifacts."""
    rows = [
        # The mission under evaluation: clean, single round, all CONCUR.
        _row(1, "spec-020", "brand-architect", "CONCUR", mission_id="mission_a"),
        _row(1, "spec-020", "content-strategist", "CONCUR", mission_id="mission_a"),
        # A totally different, concurrent mission with a real, still-open blocker dissent.
        _row(
            1,
            "spec-999",
            "seo-architect",
            "DISSENT",
            severity="blocker",
            cause_key="unrelated_blocker",
            mission_id="mission_b",
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(
        ledger,
        mission_id="mission_a",
        current_round=1,
        mandated_judges={"brand-architect", "content-strategist"},
        artifact_ids={"spec-020"},
    )
    assert result.evaluable
    assert result.assertions[GTM_CONV_01] is True
    assert result.assertions[GTM_CONV_02] is True
    assert result.assertions[GTM_CONV_03] is True, (
        "mission_a has zero open dissents of its own — mission_b's unrelated open blocker must "
        "never leak into mission_a's GTM-CONV-03 verdict."
    )
    assert result.met_count == 3


def test_mission_isolation_cross_mission_pair_collision_never_closes_a_real_dissent(tmp_ledger_dir):
    """Two DIFFERENT missions can legitimately reuse the same literal (artifact_id, judge) pair
    values (round numbers, judge seat names, and sequential artifact ids are NOT globally unique
    across missions). If mission_id filtering were missing or broken, mission_x's real OPEN
    dissent for (spec-001, brand-architect) could be falsely closed by mission_y's CONCUR for the
    literal same pair values — a cross-mission false "met". Evaluating mission_x must still show
    the dissent OPEN."""
    rows = [
        # mission_x: an open blocker dissent for (spec-001, brand-architect), never resolved.
        _row(
            1,
            "spec-001",
            "brand-architect",
            "DISSENT",
            severity="blocker",
            cause_key="stale_copy",
            mission_id="mission_x",
        ),
        # mission_y: happens to reuse the exact same (artifact_id, judge) pair values, and
        # CONCURs on them — this must NOT be mistaken for a resolution of mission_x's dissent.
        _row(1, "spec-001", "brand-architect", "CONCUR", mission_id="mission_y"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)

    result_x = evaluate(ledger, mission_id="mission_x", current_round=1)
    assert result_x.evaluable
    assert result_x.assertions[GTM_CONV_03] is False, (
        "mission_x's real open dissent for (spec-001, brand-architect) must still read OPEN — "
        "mission_y's CONCUR on the same literal pair values must never close it."
    )

    result_y = evaluate(ledger, mission_id="mission_y", current_round=1)
    assert result_y.evaluable
    assert result_y.assertions[GTM_CONV_03] is True, (
        "mission_y's own ledger rows are a single clean CONCUR — it should read fully converged "
        "regardless of mission_x's unrelated open dissent on the same pair values."
    )


def test_mission_isolation_zero_rows_for_mission_id_is_uneval_not_silent_met(tmp_ledger_dir):
    """A ledger that parses cleanly but holds no rows at all for the requested mission_id must
    report UNEVALUABLE with a clear reason — never a silent "met" (there is nothing to evaluate)."""
    rows = [
        _row(1, "spec-001", "brand-architect", "CONCUR", mission_id="some_other_mission"),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id="mission_with_no_rows", current_round=1)
    assert result.evaluable is False
    assert result.summary_line().startswith("UNEVALUABLE:")
    assert "mission_with_no_rows" in result.reason


# ---------------------------------------------------------------------------
# DEGRADED-GROUNDING boundary — 50% vs 51% (reachable from the real evaluate() path)
# ---------------------------------------------------------------------------
#
# These tests go through the real `evaluate()` path end-to-end (never hand-built LedgerRow
# objects that bypass the parser), proving the flag is genuinely reachable.


def test_degraded_grounding_not_flagged_at_exactly_50_percent(tmp_ledger_dir):
    """Exactly 50% of the round's dissents carrying non-citation-shaped (but non-empty, parsed)
    evidence must NOT trip DEGRADED-GROUNDING — the rule is "MORE THAN 50%"."""
    rows = [
        _row(
            1,
            "a1",
            "j1",
            "DISSENT",
            severity="minor",
            cause_key=None,
            evidence="marketing/website/templates/index.html:12-14 stale claim",
        ),
        _row(
            1,
            "a2",
            "j2",
            "DISSENT",
            severity="minor",
            cause_key=None,
            evidence="this just feels off to me",
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=1)
    assert result.evaluable
    assert result.degraded_grounding_ratio == pytest.approx(0.5)
    assert result.degraded_grounding is False


def test_degraded_grounding_flagged_above_50_percent(tmp_ledger_dir):
    """Strictly more than 50% of the round's dissents carrying non-citation-shaped evidence DOES
    trip DEGRADED-GROUNDING, reached through the real parse + evaluate() path (never hand-built
    LedgerRow objects that skip the parser)."""
    rows = [
        _row(1, "a1", "j1", "DISSENT", severity="minor", cause_key=None, evidence="seems wrong"),
        _row(1, "a2", "j2", "DISSENT", severity="minor", cause_key=None, evidence="not convinced"),
        _row(
            1,
            "a3",
            "j3",
            "DISSENT",
            severity="minor",
            cause_key=None,
            evidence="marketing/website/templates/index.html:1-2 real citation",
        ),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=1)
    assert result.evaluable
    assert result.degraded_grounding_ratio == pytest.approx(2 / 3)
    assert result.degraded_grounding is True


# ---------------------------------------------------------------------------
# Evidence-less DISSENT parse rejection
# ---------------------------------------------------------------------------


def test_evidence_less_dissent_is_rejected_not_silently_valid(tmp_ledger_dir):
    """A ledger LINE carrying a DISSENT verdict with no `evidence` field must be rejected at
    parse time (UNEVALUABLE), never silently counted as a valid dissent row."""
    path = os.path.join(tmp_ledger_dir, "gtm_reviewed.jsonl")
    bad_row = {
        "mission_id": DEFAULT_MISSION_ID,
        "round": 1,
        "artifact_id": "spec-099",
        "judge": "brand-architect",
        "verdict": "DISSENT",
        "severity": "blocker",
        "cause_key": "some_cause",
        "ts": "2026-09-05T00:00:00Z",
        # deliberately no "evidence" field
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(bad_row) + "\n")
    result = evaluate(path, mission_id=DEFAULT_MISSION_ID)
    assert result.evaluable is False
    assert result.summary_line().startswith("UNEVALUABLE:")
    assert "evidence" in result.reason.lower()


# ---------------------------------------------------------------------------
# cause_key required for blocker-severity DISSENTs
# ---------------------------------------------------------------------------


def test_blocker_dissent_missing_cause_key_is_rejected_not_silently_valid(tmp_ledger_dir):
    """A blocker-severity DISSENT with no `cause_key` must be rejected at parse time
    (UNEVALUABLE), never silently accepted with a None cause_key. Without this, the row is
    invisible to GTM-CONV-01's recurrence check (which filters on `r.cause_key` truthiness),
    letting a real recurring blocker silently read as "not recurring"."""
    path = os.path.join(tmp_ledger_dir, "gtm_reviewed.jsonl")
    bad_row = {
        "mission_id": DEFAULT_MISSION_ID,
        "round": 1,
        "artifact_id": "spec-100",
        "judge": "brand-architect",
        "verdict": "DISSENT",
        "severity": "blocker",
        "evidence": "marketing/website/templates/index.html:1-2 real citation",
        "ts": "2026-09-05T00:00:00Z",
        # deliberately no "cause_key" field
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(bad_row) + "\n")
    result = evaluate(path, mission_id=DEFAULT_MISSION_ID)
    assert result.evaluable is False
    assert result.summary_line().startswith("UNEVALUABLE:")
    assert "cause_key" in result.reason.lower()


def test_major_or_minor_dissent_without_cause_key_still_allowed(tmp_ledger_dir):
    """Only blocker-severity DISSENTs require a cause_key — a major/minor DISSENT with no
    cause_key must still parse and evaluate cleanly, since GTM-CONV-01's recurrence check never
    depends on non-blocker rows."""
    rows = [
        _row(1, "spec-101", "seo-architect", "DISSENT", severity="major", cause_key=None),
    ]
    ledger = _write_ledger(tmp_ledger_dir, rows)
    result = evaluate(ledger, mission_id=DEFAULT_MISSION_ID, current_round=1)
    assert result.evaluable


# ---------------------------------------------------------------------------
# CLI --ledger default resolution via repo_manifest.py (new — WS1 repo-agnostic move)
# ---------------------------------------------------------------------------


def test_cli_no_ledger_and_no_manifest_fails_loud_with_manifest_or_key_missing(tmp_path):
    """With no `--ledger` given and a repo whose `.claude/oversight/manifest.json` does not
    exist (or lacks `gtm.missions_dir`), the CLI must exit non-zero and print
    `manifest-missing` or `key-missing` on stderr — never guess a path, never silently fall
    back to a product-repo literal.

    This is RED before the CLI's --ledger default-resolution change (main() had no `--ledger`
    flag and no manifest-shelling default at all — the old positional-arg CLI required
    ledger_path directly and never consulted repo_manifest.py) and GREEN after it. Exercised as
    a real subprocess so the exit code and stderr are the actual CLI contract, not an in-process
    approximation.
    """
    repo = tmp_path / "throwaway_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    # No .claude/oversight/manifest.json anywhere under repo -- deliberately absent.

    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(_TOOLS_GTM_DIR.parent.parent)

    result = subprocess.run(
        [
            sys.executable,
            str(_EXIT_CONTRACT_PATH),
            "--mission-id",
            DEFAULT_MISSION_ID,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "manifest-missing" in result.stderr or "key-missing" in result.stderr


# ---------------------------------------------------------------------------
# Blocker-case combinations added on top of the existing 19 (kept untouched above):
#
# (1) no --ledger, manifest resolves: the default ledger path must be anchored to the REPO
#     ROOT, never the caller's cwd — evaluated from a subdirectory of a repo whose
#     .claude/oversight/manifest.json names a real gtm.missions_dir with a valid one-mission
#     ledger, the CLI must evaluate that mission (stdout starts with "GTM convergence:"),
#     exit 0. Paired with a same-repo, repo-root recovery run producing the identical verdict
#     (the "leave the failure/edge state and reach the intended result" pairing).
# (2) exit codes: an UNEVALUABLE result (nonexistent mission id, or a missing/empty/malformed
#     ledger file passed via --ledger) prints "UNEVALUABLE:" on stdout and exits 2 -- paired
#     with a same-shape recovery run against a valid ledger/mission that exits 0. A resolver
#     failure (cwd not a git repo, or a git repo with no manifest / no gtm.missions_dir key, no
#     --ledger given) exits 3 with "not-a-repo" / "manifest-missing" / "key-missing" in stderr,
#     never a "GTM convergence:" success line -- paired with a recovery run from the SAME repo
#     once cwd is moved back to a properly-manifested root, which succeeds at exit 0.
#
# All helpers below build a real git repo + real .claude/oversight/manifest.json (built inline
# from a minimal dict literal -- never read from a sibling template file, so this suite never
# depends on this machine's home directory or on any file outside this test file) + a real
# one-mission ledger, and drive the CLI as a genuine subprocess (never mocking evaluate() or the
# resolver) so the observed exit code and stdout/stderr are the actual CLI contract, exactly like
# test_cli_no_ledger_and_no_manifest_fails_loud_with_manifest_or_key_missing above.
# ---------------------------------------------------------------------------


def _minimal_manifest(missions_dir_rel="docs/gtm_missions"):
    """Build the smallest manifest dict that satisfies repo_manifest.py's `_violations` checks
    for every field these tests actually touch: schema_version, product.{name,slug},
    github.repo, and gtm.{missions_dir,inbox_label}. Deliberately inline (no read of any sibling
    template/file) so this suite is fully self-contained and immune to that file moving or being
    unavailable on a different machine."""
    return {
        "schema_version": 1,
        "product": {"name": "ExampleApp", "slug": "exampleapp"},
        "github": {"repo": "your-org/your-repo"},
        "gtm": {"missions_dir": missions_dir_rel, "inbox_label": "dept:marketing"},
    }


def _build_manifested_repo(tmp_path, subdir_name="repo", missions_dir_rel="docs/gtm_missions"):
    """Create a real git repo at tmp_path/<subdir_name> with a valid
    .claude/oversight/manifest.json (built inline via `_minimal_manifest`, gtm.missions_dir
    pointed at a real created directory under the repo) and return the repo Path. Does not write
    any ledger rows -- callers add those via `_write_ledger_at`."""
    repo = tmp_path / subdir_name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    oversight_dir = repo / ".claude" / "oversight"
    oversight_dir.mkdir(parents=True)
    manifest = _minimal_manifest(missions_dir_rel)
    (repo / missions_dir_rel).mkdir(parents=True)
    (oversight_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return repo


def _write_ledger_at(missions_dir: Path, rows):
    path = missions_dir / "gtm_reviewed.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


def _run_cli(cwd, args, extra_env=None):
    """Run the exit_contract CLI as a real subprocess.

    (F1, hermeticity) The subprocess must never silently depend on the AMBIENT `CLAUDE_DIR`
    (or its absence) resolving to this machine's real `~/.claude` install -- that dependency is
    invisible under a plain `os.environ` inheritance and only surfaces as a failure under a
    different `HOME` (e.g. CI, or a sandboxed run with `HOME=/tmp/nowhere`), where
    `~/.claude/scripts/repo_manifest.py` does not exist at all. `CLAUDE_DIR` is defaulted here to
    this real runtime tree (`_TOOLS_GTM_DIR.parent.parent`, i.e. `~/.claude`) -- the same
    older convention already used by `test_cli_no_ledger_and_no_manifest_fails_loud_with_manifest_or_key_missing`
    above -- unless the caller's own `extra_env` supplies a `CLAUDE_DIR` override (e.g. the
    Group C "cwd not in any repo" / manifest-missing / key-missing tests, which deliberately
    point `CLAUDE_DIR` elsewhere or rely on this same default to reach a real `repo_manifest.py`)."""
    env = dict(os.environ)
    env.setdefault("CLAUDE_DIR", str(_TOOLS_GTM_DIR.parent.parent))
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(_EXIT_CONTRACT_PATH), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Group A -- default --ledger resolution must anchor to the repo root, not the caller's cwd
# ---------------------------------------------------------------------------


def test_default_ledger_resolves_from_one_level_subdirectory(tmp_path):
    """RED today (blocker case): running with --mission-id and NO --ledger from a
    subdirectory of a properly-manifested repo must still resolve the ledger relative to the
    REPO ROOT and evaluate the mission -- exit 0, stdout starting with "GTM convergence:"."""
    repo = _build_manifested_repo(tmp_path)
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-200", "brand-architect", "CONCUR", mission_id="gtm_default_resolve")],
    )
    sub = repo / "sub"
    sub.mkdir()

    result = _run_cli(sub, ["--mission-id", "gtm_default_resolve"])

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("GTM convergence:")


def test_default_ledger_resolves_from_nested_subdirectory(tmp_path):
    """Same blocker case, two directory levels deep, to rule out a fix that only anchors one
    level (e.g. a fix that walks up exactly one parent instead of to the real repo root)."""
    repo = _build_manifested_repo(tmp_path)
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-201", "seo-architect", "CONCUR", mission_id="gtm_default_resolve_nested")],
    )
    nested = repo / "sub" / "deeper"
    nested.mkdir(parents=True)

    result = _run_cli(nested, ["--mission-id", "gtm_default_resolve_nested"])

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("GTM convergence:")


def test_default_ledger_resolution_recovery_twin_from_repo_root(tmp_path):
    """Recoverability pairing for the two tests above: the SAME repo, evaluated from the repo
    ROOT itself (not a subdirectory), must also succeed at exit 0 with an identical verdict --
    proving the subdirectory cases above are a genuine cwd-independence fix, not an accidental
    side effect that happens to work only from some other directory."""
    repo = _build_manifested_repo(tmp_path)
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-202", "content-strategist", "CONCUR", mission_id="gtm_root_recovery")],
    )
    sub = repo / "sub"
    sub.mkdir()

    from_subdir = _run_cli(sub, ["--mission-id", "gtm_root_recovery"])
    from_root = _run_cli(repo, ["--mission-id", "gtm_root_recovery"])

    assert from_subdir.returncode == 0
    assert from_root.returncode == 0
    assert from_subdir.stdout == from_root.stdout, (
        "the default-ledger-resolved verdict must be identical whether the CLI is invoked from "
        "the repo root or from a subdirectory of the same repo"
    )


def test_default_ledger_resolution_with_nested_missions_dir_path(tmp_path):
    """The repo-root anchoring fix must correctly join a multi-segment relative
    gtm.missions_dir (e.g. "docs/gtm_missions", the runtime template's own default) against the
    repo root when invoked from a subdirectory -- not just a single-segment directory name,
    which could mask a fix that only handles the trivial case."""
    repo = _build_manifested_repo(tmp_path, missions_dir_rel="docs/gtm_missions/nested/deep")
    missions_dir = repo / "docs" / "gtm_missions" / "nested" / "deep"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-203", "pricing-economist", "CONCUR", mission_id="gtm_nested_path")],
    )
    sub = repo / "sub"
    sub.mkdir()

    result = _run_cli(sub, ["--mission-id", "gtm_nested_path"])

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("GTM convergence:")


def test_default_ledger_resolution_matches_explicit_ledger_invocation(tmp_path):
    """Cross-check: the verdict produced by default-ledger resolution (no --ledger, run from a
    subdirectory) must be identical to the verdict produced by an explicit --ledger pointing at
    the exact same file -- proving the resolution path feeds evaluate() the correct file rather
    than merely happening to exit 0 for an unrelated reason (e.g. silently landing on some other
    ledger or an empty one that coincidentally evaluates)."""
    repo = _build_manifested_repo(tmp_path)
    missions_dir = repo / "docs" / "gtm_missions"
    ledger_path = _write_ledger_at(
        missions_dir,
        [
            _row(1, "spec-204", "brand-architect", "DISSENT", severity="blocker", cause_key="x",
                 mission_id="gtm_cross_check"),
        ],
    )
    sub = repo / "sub"
    sub.mkdir()

    via_default = _run_cli(sub, ["--mission-id", "gtm_cross_check"])
    via_explicit = _run_cli(sub, ["--ledger", str(ledger_path), "--mission-id", "gtm_cross_check"])

    assert via_default.returncode == 0
    assert via_explicit.returncode == 0
    assert via_default.stdout == via_explicit.stdout


def test_default_ledger_resolution_honors_claude_dir_override_from_subdirectory(tmp_path):
    """CLAUDE_DIR (which the resolver uses to find repo_manifest.py) must still work correctly
    when combined with a cwd inside a subdirectory of the target repo -- the repo-root
    anchoring fix must not accidentally depend on CLAUDE_DIR pointing at the SAME tree as the
    product repo, since in real usage CLAUDE_DIR is the runtime root and the product repo is a
    completely separate tree."""
    repo = _build_manifested_repo(tmp_path)
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-205", "conversion-architect", "CONCUR", mission_id="gtm_claude_dir_env")],
    )
    sub = repo / "sub"
    sub.mkdir()

    result = _run_cli(
        sub,
        ["--mission-id", "gtm_claude_dir_env"],
        extra_env={"CLAUDE_DIR": str(_TOOLS_GTM_DIR.parent.parent)},
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("GTM convergence:")


# ---------------------------------------------------------------------------
# Group B -- exit codes for an un-evaluable result: UNEVALUABLE on stdout, exit 2
# ---------------------------------------------------------------------------


def test_cli_exit_code_2_for_nonexistent_mission_id(tmp_path):
    """RED today (blocker case): a nonexistent --mission-id against a real, valid ledger must
    print "UNEVALUABLE:" on stdout and exit with code 2 -- never exit 0, which would be
    indistinguishable from a genuine successful evaluation to any caller checking exit status
    alone."""
    ledger = _write_ledger_at(
        tmp_path,
        [_row(1, "spec-206", "seo-architect", "CONCUR", mission_id="gtm_real_mission")],
    )
    result = _run_cli(
        tmp_path, ["--ledger", str(ledger), "--mission-id", "does-not-exist-anywhere"]
    )

    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("UNEVALUABLE:")


def test_cli_exit_code_2_for_missing_ledger_file(tmp_path):
    """A --ledger path that does not exist on disk must also print "UNEVALUABLE:" on stdout and
    exit 2, the identical contract as the nonexistent-mission-id case."""
    missing_path = tmp_path / "does_not_exist_at_all.jsonl"
    result = _run_cli(tmp_path, ["--ledger", str(missing_path), "--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("UNEVALUABLE:")


def test_cli_exit_code_2_for_empty_ledger_file(tmp_path):
    """An empty --ledger file (exists, zero content) must also exit 2 with "UNEVALUABLE:" on
    stdout -- exercised through the real CLI subprocess, not just the in-process evaluate()
    path already covered by test_uneval_empty_ledger_file above."""
    path = tmp_path / "gtm_reviewed.jsonl"
    path.write_text("", encoding="utf-8")
    result = _run_cli(tmp_path, ["--ledger", str(path), "--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("UNEVALUABLE:")


def test_cli_exit_code_2_for_malformed_ledger_line(tmp_path):
    """A ledger file with one valid row followed by a line that fails JSON parsing must also
    exit 2 with "UNEVALUABLE:" on stdout, through the real CLI subprocess."""
    path = tmp_path / "gtm_reviewed.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_row(1, "spec-207", "seo-architect", "CONCUR")) + "\n")
        f.write("{not valid json\n")
    result = _run_cli(tmp_path, ["--ledger", str(path), "--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("UNEVALUABLE:")


def test_cli_exit_code_2_is_distinct_from_exit_code_0_success(tmp_path):
    """Direct contrast within one test: the exact same --ledger file evaluated with a real
    mission id exits 0, while evaluated with a nonexistent mission id exits 2 -- proving the
    non-zero exit is caused by the UNEVALUABLE condition itself, not some incidental difference
    between the two invocations (e.g. a different ledger, a different cwd)."""
    ledger = _write_ledger_at(
        tmp_path,
        [_row(1, "spec-208", "content-strategist", "CONCUR", mission_id="gtm_present_mission")],
    )

    ok_result = _run_cli(tmp_path, ["--ledger", str(ledger), "--mission-id", "gtm_present_mission"])
    bad_result = _run_cli(tmp_path, ["--ledger", str(ledger), "--mission-id", "gtm_absent_mission"])

    assert ok_result.returncode == 0
    assert ok_result.stdout.startswith("GTM convergence:")
    assert bad_result.returncode == 2
    assert bad_result.stdout.startswith("UNEVALUABLE:")


def test_recovery_from_uneval_exit_2_to_success_exit_0_same_ledger(tmp_path):
    """Required recoverability pairing for Group B: after hitting the UNEVALUABLE/exit-2 case
    (a nonexistent mission id), the operator can recover by re-running with a real --mission-id
    against the SAME --ledger file and reach a genuine exit-0 success -- the failure state is
    never a dead end."""
    ledger = _write_ledger_at(
        tmp_path,
        [_row(1, "spec-209", "brand-architect", "CONCUR", mission_id="gtm_recoverable_mission")],
    )

    failed = _run_cli(tmp_path, ["--ledger", str(ledger), "--mission-id", "gtm_missing_mission"])
    assert failed.returncode == 2
    assert failed.stdout.startswith("UNEVALUABLE:")

    recovered = _run_cli(
        tmp_path, ["--ledger", str(ledger), "--mission-id", "gtm_recoverable_mission"]
    )
    assert recovered.returncode == 0, f"stdout={recovered.stdout!r} stderr={recovered.stderr!r}"
    assert recovered.stdout.startswith("GTM convergence:")


# ---------------------------------------------------------------------------
# Group C -- resolver failure: exit 3, reason in stderr, never a false success
# ---------------------------------------------------------------------------


def test_cli_exit_code_3_when_cwd_is_not_a_git_repo(tmp_path):
    """RED today (blocker case): with no --ledger given and a cwd that is not inside any git
    repository at all, the CLI must exit 3 with "not-a-repo" in stderr -- never guess a path,
    never silently fall back to some default, never exit 0."""
    not_a_repo = tmp_path / "just_a_plain_directory"
    not_a_repo.mkdir()

    result = _run_cli(not_a_repo, ["--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 3, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "not-a-repo" in result.stderr
    assert "GTM convergence:" not in result.stdout


def test_cli_exit_code_3_when_manifest_missing(tmp_path):
    """A real git repo with no .claude/oversight/manifest.json at all must exit 3 with
    "manifest-missing" in stderr when no --ledger is given."""
    repo = tmp_path / "repo_no_manifest"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)

    result = _run_cli(repo, ["--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 3, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "manifest-missing" in result.stderr
    assert "GTM convergence:" not in result.stdout


def test_cli_exit_code_3_when_manifest_present_but_missing_gtm_key(tmp_path):
    """A real git repo with a manifest.json that has no `gtm` block at all (a plausible
    real-world manifest that predates the gtm.missions_dir key, or was authored for a repo with
    no GTM department) must exit 3 with "key-missing" in stderr when no --ledger is given --
    never silently treat a missing key as an empty/default missions_dir."""
    repo = tmp_path / "repo_no_gtm_key"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    oversight_dir = repo / ".claude" / "oversight"
    oversight_dir.mkdir(parents=True)
    manifest = _minimal_manifest()
    del manifest["gtm"]
    (oversight_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_cli(repo, ["--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 3, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "key-missing" in result.stderr
    assert "GTM convergence:" not in result.stdout


def test_recovery_from_resolver_failure_exit_3_to_success_exit_0_same_process_tree(tmp_path):
    """Required recoverability pairing for Group C: after hitting the resolver-failure/exit-3
    case (cwd not inside any repo), the operator can recover by re-running the identical CLI
    command from a properly-manifested repo (with a real ledger for the mission) and reach a
    genuine exit-0 success -- the resolver failure is never a dead end, and this also proves the
    exit-3 case was caused by the missing repo/manifest context, not by some other break in the
    CLI itself."""
    not_a_repo = tmp_path / "still_not_a_repo"
    not_a_repo.mkdir()
    failed = _run_cli(not_a_repo, ["--mission-id", "gtm_recovery_after_resolver_failure"])
    assert failed.returncode == 3
    assert "not-a-repo" in failed.stderr

    repo = _build_manifested_repo(tmp_path, subdir_name="repo_for_recovery")
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [
            _row(
                1,
                "spec-210",
                "paid-acquisition-strategist",
                "CONCUR",
                mission_id="gtm_recovery_after_resolver_failure",
            )
        ],
    )
    recovered = _run_cli(repo, ["--mission-id", "gtm_recovery_after_resolver_failure"])
    assert recovered.returncode == 0, f"stdout={recovered.stdout!r} stderr={recovered.stderr!r}"
    assert recovered.stdout.startswith("GTM convergence:")


def test_cli_exit_code_3_never_prints_uneval_prefix_on_stdout(tmp_path):
    """A resolver failure (exit 3) is a DIFFERENT failure mode from an UNEVALUABLE result
    (exit 2) -- it must never print "UNEVALUABLE:" on stdout, since evaluate() itself is never
    even reached when the ledger path cannot be resolved at all. Conflating the two would make a
    caller unable to distinguish "bad --mission-id/ledger content" from "no manifest/repo
    context" by output shape alone."""
    not_a_repo = tmp_path / "not_a_repo_for_prefix_check"
    not_a_repo.mkdir()

    result = _run_cli(not_a_repo, ["--mission-id", DEFAULT_MISSION_ID])

    assert result.returncode == 3
    assert "UNEVALUABLE:" not in result.stdout
    assert "GTM convergence:" not in result.stdout


def test_cli_exit_code_3_distinct_from_exit_code_2_for_same_mission_id(tmp_path):
    """Direct contrast: the identical --mission-id produces exit 2 (UNEVALUABLE) when a real,
    resolvable --ledger simply has no rows for it, but exit 3 (resolver failure) when no
    --ledger is given and cwd has no manifest at all -- these are genuinely different failure
    classes and must never collapse to the same exit code or output shape."""
    ledger = _write_ledger_at(
        tmp_path,
        [_row(1, "spec-211", "brand-architect", "CONCUR", mission_id="gtm_present_for_contrast")],
    )
    uneval_result = _run_cli(
        tmp_path, ["--ledger", str(ledger), "--mission-id", "gtm_absent_for_contrast"]
    )

    not_a_repo = tmp_path / "no_repo_for_contrast"
    not_a_repo.mkdir()
    resolver_failure_result = _run_cli(
        not_a_repo, ["--mission-id", "gtm_absent_for_contrast"]
    )

    assert uneval_result.returncode == 2
    assert uneval_result.stdout.startswith("UNEVALUABLE:")
    assert resolver_failure_result.returncode == 3
    assert resolver_failure_result.returncode != uneval_result.returncode
    assert "not-a-repo" in resolver_failure_result.stderr


def test_empty_missions_dir_value_is_key_missing_not_silent_cwd_fallback(tmp_path):
    """(B1, 2026-09-09) A manifest whose `gtm.missions_dir` is the EMPTY STRING (a distinct
    outcome from a missing key -- `repo_manifest.py get` exits 0 with empty stdout for a present-
    but-empty value) must be treated identically to a missing key by the CLI's default-ledger
    resolver: exit 3, `key-missing: gtm.missions_dir` in stderr, and NEVER fall through to a bare
    relative "gtm_reviewed.jsonl" that would silently resolve against the CALLER's cwd instead of
    the repo root. Without this guard, a ledger planted at `<repo>/sub/gtm_reviewed.jsonl` and a
    CLI invocation from `<repo>/sub` would silently read that file and print a (wrong, false)
    convergence verdict at exit 0 -- exactly the B1 failure class."""
    repo = _build_manifested_repo(tmp_path, missions_dir_rel="docs/gtm_missions")
    manifest_path = repo / ".claude" / "oversight" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["gtm"]["missions_dir"] = ""
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    sub = repo / "sub"
    sub.mkdir()
    _write_ledger_at(
        sub, [_row(1, "spec-300", "brand-architect", "CONCUR", mission_id="gtm_empty_missions_dir")]
    )

    result = _run_cli(sub, ["--mission-id", "gtm_empty_missions_dir"])

    assert result.returncode == 3, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "key-missing: gtm.missions_dir" in result.stderr
    assert not result.stdout.startswith("GTM convergence:")


def test_empty_missions_dir_recovery_twin_once_missions_dir_is_set(tmp_path):
    """Recoverability pairing for the empty-`missions_dir` case above: the SAME repo and ledger,
    with `gtm.missions_dir` set to a real relative directory (`sub`, the directory the ledger
    already lives in) instead of the empty string, must evaluate successfully -- exit 0, stdout
    starting with "GTM convergence:" -- proving the exit-3 case above was caused specifically by
    the empty value, not by some other break in the repo/ledger setup."""
    repo = _build_manifested_repo(tmp_path, missions_dir_rel="docs/gtm_missions")
    manifest_path = repo / ".claude" / "oversight" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["gtm"]["missions_dir"] = "sub"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    sub = repo / "sub"
    sub.mkdir()
    _write_ledger_at(
        sub, [_row(1, "spec-301", "content-strategist", "CONCUR", mission_id="gtm_missions_dir_set")]
    )

    result = _run_cli(sub, ["--mission-id", "gtm_missions_dir_set"])

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("GTM convergence:")


def test_resolver_subprocess_non_contract_exit_code_maps_to_exit_3_resolver_failed(tmp_path):
    """(B2) When `CLAUDE_DIR` points at a directory that has no `scripts/repo_manifest.py` at
    all, the resolver subprocess invocation itself fails at the OS/interpreter level (the Python
    interpreter's own "can't open file" exit, code 2) rather than via `repo_manifest.py`'s own
    contract exit codes (3 for not-a-repo/manifest-missing/key-missing, 4 for a malformed
    manifest). This is NOT the same failure class as an UNEVALUABLE ledger-content result (exit
    2) -- exit 2 is reserved for main()'s own ledger-content failure and must never be silently
    reused here just because the interpreter's exit code happens to also be 2. The CLI must
    distinguish this and exit 3 with `resolver-failed (2)` in stderr, never exit 2 and never a
    false success."""
    empty_claude_dir = tmp_path / "claude_dir_with_no_scripts"
    empty_claude_dir.mkdir()
    # Deliberately no "scripts/repo_manifest.py" under empty_claude_dir at all.

    not_a_repo_needed = tmp_path / "cwd_for_resolver_failed"
    not_a_repo_needed.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(not_a_repo_needed), check=True)

    result = _run_cli(
        not_a_repo_needed,
        ["--mission-id", DEFAULT_MISSION_ID],
        extra_env={"CLAUDE_DIR": str(empty_claude_dir)},
    )

    assert result.returncode == 3, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "resolver-failed (2)" in result.stderr
    assert not result.stdout.startswith("GTM convergence:")


def test_default_ledger_resolution_recovery_twin_after_not_a_repo_failure(tmp_path):
    """Recoverability pairing spanning Group A and Group C together: starting from a cwd with
    no repo context at all (exit 3), the operator can `cd` into a properly-manifested repo's
    SUBDIRECTORY (not just its root) and reach a genuine exit-0 evaluation for a real mission --
    confirming the subdirectory-anchoring fix (Group A) is what actually restores service after
    a resolver failure (Group C), not merely a coincidence of running from the repo root."""
    not_a_repo = tmp_path / "no_repo_before_recovery"
    not_a_repo.mkdir()
    failed = _run_cli(not_a_repo, ["--mission-id", "gtm_subdir_after_failure"])
    assert failed.returncode == 3

    repo = _build_manifested_repo(tmp_path, subdir_name="repo_for_subdir_recovery")
    missions_dir = repo / "docs" / "gtm_missions"
    _write_ledger_at(
        missions_dir,
        [_row(1, "spec-212", "trust-architect", "CONCUR", mission_id="gtm_subdir_after_failure")],
    )
    sub = repo / "sub"
    sub.mkdir()

    recovered = _run_cli(sub, ["--mission-id", "gtm_subdir_after_failure"])
    assert recovered.returncode == 0, f"stdout={recovered.stdout!r} stderr={recovered.stderr!r}"
    assert recovered.stdout.startswith("GTM convergence:")
