"""Tests for the WS5.8(c) seed install doc (`templates/knowledge/oversight_install.md`,
runtime_bundle_repo_agnostic_plan.md §WS5.8(c)).

The seed is authored in parallel by an implementer. Its §2 job table must
carry the exact header/separator shape `heartbeat_audit.py:parse_job_table`
expects and exactly ONE data row -- label `com.oversight.example.daily`,
expected_state `unloaded`, cadence `05:10 daily` -- so that a fresh clone's
very first audit run never produces a `table-parse-failed` finding (the
`ValueError` a zero-row table raises BY DESIGN) and never produces a real
finding about the example job itself (its `unloaded` expected_state must
keep `expected-but-unloaded` quiet).

These tests assert against BOTH an inline literal of the intended table
(so they are meaningful before the seed file lands) and the real seed file
once it exists (skipped with a reason until then).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import heartbeat_audit as ha  # noqa: E402

_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "templates" / "knowledge" / "oversight_install.md"
)

_EXPECTED_ROW = ("com.oversight.example.daily", "unloaded", "05:10 daily")

# The inline literal of the seed's §2 table, per the plan's own exact spec:
# header + separator matching parse_job_table's expectations, and exactly
# ONE data row for com.oversight.example.daily / unloaded / 05:10 daily.
_INLINE_SEED_TABLE = """# Oversight install (seed)

## 2. The jobs (label · expected_state · cadence · repo · prompt file · does)

| label | expected_state | StartCalendarInterval | repo | prompt file | does |
|---|---|---|---|---|---|
| com.oversight.example.daily | unloaded | 05:10 daily | __ABSOLUTE_PATH_TO_YOUR_REPO__ | `daily_sweep.txt` | SEED ROW — flip expected_state to `loaded` when you load this job; add one row per job you install |
"""

# A "comment row" shape -- documenting why the seed must NEVER contain one:
# any `|`-leading line with >= 3 cells parses as a genuine data row, so an
# HTML-comment-style row would silently become a bogus extra job.
_COMMENT_ROW_LINE = "| <!-- comment --> | | | | | |"


def _seed_text_or_skip() -> str:
    # The seed ships in the same commit as this test: a missing/renamed/mis-pathed seed is a
    # FAILURE (the shipped artifact is what these tests bind), never a silent skip.
    assert _SEED_PATH.is_file(), f"seed missing at {_SEED_PATH} — it must ship with this test"
    return _SEED_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. parse_job_table(seed_text) -> exactly the one expected row.
# --------------------------------------------------------------------------


def test_inline_seed_table_parses_to_exactly_one_expected_row():
    rows = ha.parse_job_table(_INLINE_SEED_TABLE)
    assert rows == [_EXPECTED_ROW]


def test_real_seed_file_parses_to_exactly_one_expected_row():
    text = _seed_text_or_skip()
    rows = ha.parse_job_table(text)
    assert rows == [_EXPECTED_ROW]


# --------------------------------------------------------------------------
# 2. RED baseline: a header+separator table with ZERO data rows raises
#    ValueError, by design -- the exact failure mode the seed must avoid.
# --------------------------------------------------------------------------


def test_zero_data_row_table_raises_value_error_zero_data_rows():
    doc = "| label | expected_state | cadence |\n|---|---|---|\n\nprose after, no rows\n"
    with pytest.raises(ValueError, match="zero data rows"):
        ha.parse_job_table(doc)


# --------------------------------------------------------------------------
# 3. Full audit run against the seed: empty heartbeats dir + empty
#    loaded_labels -> no finding names the example label, and no
#    table-parse-failed finding. Paired recovery twin: flipping the row's
#    expected_state to "loaded" (with the label still absent from
#    loaded_labels) DOES fire expected-but-unloaded -- proving the check is
#    genuinely live and it is the seed's "unloaded" value, not some
#    unrelated suppression, that keeps it quiet.
# --------------------------------------------------------------------------


def _run_audit(table_text: str, *, loaded_labels: set[str]) -> list[str]:
    """Mirrors check()'s real call shape for an empty heartbeats dir: no
    per-heartbeat structural findings are possible since `heartbeats` is
    empty, so this isolates exactly the expected-job-set/expected-but-
    unloaded checks the seed's own row must stay quiet against.
    """
    rows = ha.parse_job_table(table_text)
    table_labels = [r[0] for r in rows]
    table_cadences = {label: cadence for label, _state, cadence in rows}
    table_expected_states = {label: state for label, state, _cadence in rows}
    return ha.check(
        table_labels,
        None,  # table_parse_error
        {},  # heartbeats: empty dir
        {},  # log_times
        loaded_labels,
        table_cadences=table_cadences,
        table_expected_states=table_expected_states,
    )


def test_inline_seed_empty_heartbeats_and_unloaded_yields_no_finding_and_no_parse_failure():
    violations = _run_audit(_INLINE_SEED_TABLE, loaded_labels=set())
    assert not any("com.oversight.example.daily" in line for line in violations)
    assert not any(line.startswith("table-parse-failed") for line in violations)


def test_real_seed_empty_heartbeats_and_unloaded_yields_no_finding_and_no_parse_failure():
    text = _seed_text_or_skip()
    violations = _run_audit(text, loaded_labels=set())
    assert not any("com.oversight.example.daily" in line for line in violations)
    assert not any(line.startswith("table-parse-failed") for line in violations)


def test_recovery_twin_flipping_expected_state_to_loaded_fires_expected_but_unloaded():
    # Same table shape as the seed, but with expected_state flipped to
    # "loaded" while the label is still absent from loaded_labels -- this is
    # the falsifiability pair for test 3 above: it proves the check is
    # genuinely live, and that it is specifically the seed's "unloaded"
    # value keeping it quiet, not some blanket suppression of the example
    # label or an inert check.
    loaded_table = _INLINE_SEED_TABLE.replace(
        "| com.oversight.example.daily | unloaded |",
        "| com.oversight.example.daily | loaded |",
    )
    assert loaded_table != _INLINE_SEED_TABLE  # the replace actually took effect

    violations = _run_audit(loaded_table, loaded_labels=set())
    hits = [line for line in violations if line.startswith("expected-but-unloaded")]
    assert len(hits) == 1
    assert "com.oversight.example.daily" in hits[0]


def test_recovery_twin_real_seed_flipped_to_loaded_fires_expected_but_unloaded():
    text = _seed_text_or_skip()
    if "| com.oversight.example.daily | unloaded |" not in text:
        pytest.skip(
            "real seed's example row does not match the expected "
            "'| com.oversight.example.daily | unloaded |' literal cell shape"
        )
    loaded_text = text.replace(
        "| com.oversight.example.daily | unloaded |",
        "| com.oversight.example.daily | loaded |",
    )
    violations = _run_audit(loaded_text, loaded_labels=set())
    hits = [line for line in violations if line.startswith("expected-but-unloaded")]
    assert len(hits) == 1
    assert "com.oversight.example.daily" in hits[0]


# --------------------------------------------------------------------------
# 4. A "comment row" parses as a bogus DATA row -- documenting exactly why
#    the seed must never contain one (any `|`-leading line with >= 3 cells
#    is data, full stop; there is no comment syntax in this table format).
# --------------------------------------------------------------------------


def test_comment_row_shape_parses_as_a_bogus_data_row():
    doc = (
        "| label | expected_state | cadence |\n"
        "|---|---|---|\n"
        "| com.oversight.example.daily | unloaded | 05:10 daily |\n"
        f"{_COMMENT_ROW_LINE}\n"
    )
    rows = ha.parse_job_table(doc)
    labels = [r[0] for r in rows]
    # The comment-shaped line parsed as a real row -- its "label" cell is
    # the literal HTML comment text, not empty/skipped. This is the
    # concrete demonstration of why the seed's own table must carry no such
    # row: it would silently register as an extra bogus expected job.
    assert "<!-- comment -->" in labels
    assert len(rows) == 2
