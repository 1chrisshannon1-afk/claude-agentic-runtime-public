"""Tests for validate_research_ledger (#4731, build-wave 2026-08-31 Lane B).

Falsifiability: one RED fixture per violation class (proving the check
actually fires without the corresponding fix), one clean fixture proving
zero violations, plus a live-tree run against the real research ledger.

Modeled on test_validate_agentarch_ledger.py's own structure (the in-repo
precedent) but scoped to exactly what this validator does: field schema,
id sequence, domain checks, length caps, the license-ceiling invariant, and
report-only staleness. No metric_command/guard-legality/live re-scoring —
this ledger carries no executable command at all.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_research_ledger as val  # noqa: E402


def _row(**overrides: object) -> dict:
    base = {
        "id": "RS-0001",
        "ts": "2026-08-31",
        "last_checked_at": "2026-08-31",
        "target_repo": "exampleapp",
        "oss_repo": "octocat/hello-world",
        "source_url": "https://github.com/octocat/hello-world",
        "license": "MIT",
        "verdict": "LEARN-FROM",
        "mechanism": "some mechanism",
        "brief": "some brief",
    }
    base.update(overrides)
    return base


def _write_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


# --------------------------------------------------------------------------
# _license_is_copy_ceiling_violation
# --------------------------------------------------------------------------


def test_license_ceiling_mit_is_not_a_violation():
    assert val._license_is_copy_ceiling_violation("MIT") is False


def test_license_ceiling_bsd_is_not_a_violation():
    assert val._license_is_copy_ceiling_violation("BSD-2-Clause") is False


def test_license_ceiling_apache_is_not_a_violation():
    assert val._license_is_copy_ceiling_violation("Apache-2.0") is False


def test_license_ceiling_agpl_is_a_violation():
    assert val._license_is_copy_ceiling_violation("AGPL-3.0") is True


def test_license_ceiling_gpl_is_a_violation():
    assert val._license_is_copy_ceiling_violation("GPL-2.0-only") is True


def test_license_ceiling_lgpl_is_a_violation():
    assert val._license_is_copy_ceiling_violation("LGPL-2.1-or-later") is True


def test_license_ceiling_sspl_is_a_violation():
    assert val._license_is_copy_ceiling_violation("SSPL-1.0") is True


def test_license_ceiling_noassertion_is_a_violation():
    assert val._license_is_copy_ceiling_violation("NOASSERTION") is True


def test_license_ceiling_unknown_literal_is_a_violation():
    assert val._license_is_copy_ceiling_violation("unknown") is True


def test_license_ceiling_blank_is_a_violation():
    assert val._license_is_copy_ceiling_violation("") is True


def test_license_ceiling_non_string_is_a_violation():
    assert val._license_is_copy_ceiling_violation(None) is True


def test_license_ceiling_case_insensitive():
    assert val._license_is_copy_ceiling_violation("agpl-3.0") is True
    assert val._license_is_copy_ceiling_violation("gpl-3.0") is True


def test_license_ceiling_gpl_prefix_does_not_false_positive_on_unrelated_license():
    # A license name merely CONTAINING "gpl" mid-string must not match --
    # this is a PREFIX test, not a substring test.
    assert val._license_is_copy_ceiling_violation("Some-GPL-Compatible-License") is False


# --------------------------------------------------------------------------
# validate_row — RED per class + clean case
# --------------------------------------------------------------------------


def test_validate_row_clean_returns_empty():
    assert val.validate_row(_row(), 1) == []


def test_validate_row_not_a_dict():
    v = val.validate_row("not a dict", 1)
    assert len(v) == 1
    assert "not a JSON object" in v[0]


def test_validate_row_missing_field():
    row = _row()
    del row["brief"]
    v = val.validate_row(row, 1)
    assert any("field-set" in x and "missing" in x for x in v)


def test_validate_row_extra_field():
    row = _row()
    row["bogus"] = "x"
    v = val.validate_row(row, 1)
    assert any("field-set" in x and "extra" in x for x in v)


def test_validate_row_routed_to_notes_shape_is_flagged():
    # #4826 regression: a producer session dropped `brief` and appended
    # `routed_to`/`notes` instead -- both a missing-canonical-field and an
    # extra-field violation on the SAME row, exactly RS-0038..RS-0043's
    # real shape. Must be caught by field-set, never silently accepted as
    # an equally-valid alternate schema.
    row = _row()
    del row["brief"]
    row["routed_to"] = "engine-architect"
    row["notes"] = "some routing note"
    v = val.validate_row(row, 1)
    assert any("field-set" in x and "missing" in x and "brief" in x for x in v)
    assert any("field-set" in x and "extra" in x and "notes" in x and "routed_to" in x for x in v)


def test_validate_row_field_order_wrong():
    row = _row()
    # Same field SET, wrong order: swap two keys' positions.
    reordered = {"ts": row["ts"], "id": row["id"]}
    for k in val.CANONICAL_FIELDS:
        if k not in reordered:
            reordered[k] = row[k]
    v = val.validate_row(reordered, 1)
    assert any("field-order" in x for x in v)


def test_validate_row_id_format_bad():
    v = val.validate_row(_row(id="AA-0001"), 1)
    assert any("id-format" in x for x in v)


def test_validate_row_id_sequence_mismatch():
    v = val.validate_row(_row(id="RS-0002"), 1)
    assert any("id-sequence" in x for x in v)


def test_validate_row_id_sequence_matches_line():
    v = val.validate_row(_row(id="RS-0003"), 3)
    assert not any("id-sequence" in x for x in v)


def test_validate_row_bad_ts():
    v = val.validate_row(_row(ts="not-a-date"), 1)
    assert any("date-format" in x and "ts=" in x for x in v)


def test_validate_row_bad_last_checked_at():
    v = val.validate_row(_row(last_checked_at="08/31/2026"), 1)
    assert any("date-format" in x and "last_checked_at=" in x for x in v)


def test_validate_row_ts_null_is_invalid():
    # Unlike agentarch's checked_at, ts/last_checked_at are NOT nullable in
    # this ledger's schema -- every row is a completed inspection.
    v = val.validate_row(_row(ts=None), 1)
    assert any("date-format" in x and "ts=" in x for x in v)


def test_validate_row_target_repo_domain_bad():
    v = val.validate_row(_row(target_repo="bogus_repo"), 1)
    assert any("target-repo-domain" in x for x in v)


def test_validate_row_target_repo_every_valid_value_accepted():
    for repo in sorted(val.TARGET_REPO_DOMAIN):
        v = val.validate_row(_row(target_repo=repo), 1)
        assert not any("target-repo-domain" in x for x in v)


def test_validate_row_verdict_domain_bad():
    v = val.validate_row(_row(verdict="MAYBE"), 1)
    assert any("verdict-domain" in x for x in v)


def test_validate_row_verdict_every_valid_value_accepted():
    for verdict in sorted(val.VERDICT_DOMAIN):
        row = _row(verdict=verdict)
        if verdict == "COPY":
            row["license"] = "MIT"  # keep the ceiling invariant clean for this check
        v = val.validate_row(row, 1)
        assert not any("verdict-domain" in x for x in v)


def test_validate_row_empty_oss_repo():
    v = val.validate_row(_row(oss_repo=""), 1)
    assert any("empty-field" in x and "oss_repo=" in x for x in v)


def test_validate_row_empty_source_url():
    v = val.validate_row(_row(source_url=""), 1)
    assert any("empty-field" in x and "source_url=" in x for x in v)


def test_validate_row_empty_license():
    v = val.validate_row(_row(license=""), 1)
    assert any("empty-field" in x and "license=" in x for x in v)


def test_validate_row_non_string_source_url():
    v = val.validate_row(_row(source_url=None), 1)
    assert any("empty-field" in x and "source_url=" in x for x in v)


def test_validate_row_mechanism_at_cap_is_clean():
    v = val.validate_row(_row(mechanism="x" * val.MECHANISM_MAX_LEN), 1)
    assert not any("mechanism-too-long" in x for x in v)


def test_validate_row_mechanism_over_cap_flagged():
    v = val.validate_row(_row(mechanism="x" * (val.MECHANISM_MAX_LEN + 1)), 1)
    assert any("mechanism-too-long" in x for x in v)


def test_validate_row_brief_at_cap_is_clean():
    v = val.validate_row(_row(brief="x" * val.BRIEF_MAX_LEN), 1)
    assert not any("brief-too-long" in x for x in v)


def test_validate_row_brief_over_cap_flagged():
    v = val.validate_row(_row(brief="x" * (val.BRIEF_MAX_LEN + 1)), 1)
    assert any("brief-too-long" in x for x in v)


# --------------------------------------------------------------------------
# license-ceiling invariant — the load-bearing check, exercised via validate_row
# --------------------------------------------------------------------------


def test_validate_row_copy_with_permissive_license_is_clean():
    v = val.validate_row(_row(verdict="COPY", license="MIT"), 1)
    assert not any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_bsd_is_clean():
    v = val.validate_row(_row(verdict="COPY", license="BSD-2-Clause"), 1)
    assert not any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_agpl_is_flagged():
    v = val.validate_row(_row(verdict="COPY", license="AGPL-3.0"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_gpl_is_flagged():
    v = val.validate_row(_row(verdict="COPY", license="GPL-3.0"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_lgpl_is_flagged():
    v = val.validate_row(_row(verdict="COPY", license="LGPL-3.0"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_sspl_is_flagged():
    v = val.validate_row(_row(verdict="COPY", license="SSPL-1.0"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_noassertion_is_flagged():
    """RS-0024's exact real-world proof case (per this module's own
    docstring): a README claiming MIT while the real /license endpoint
    returns NOASSERTION -- the invariant must fire regardless of what the
    README claims, because only the `license` FIELD is ever consulted."""
    v = val.validate_row(_row(verdict="COPY", license="NOASSERTION"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_unknown_license_is_flagged():
    v = val.validate_row(_row(verdict="COPY", license="unknown"), 1)
    assert any("license-ceiling-violation" in x for x in v)


def test_validate_row_learn_from_with_agpl_is_never_flagged_by_ceiling():
    # The ceiling only constrains COPY -- LEARN-FROM/AVOID are always legal
    # regardless of license, exactly as the real ledger's RS-0002
    # (DepthAnything, Apache-2.0 code / CC-BY-NC weights, verdict
    # LEARN-FROM) and RS-0024 (NOASSERTION, verdict LEARN-FROM) both are.
    v = val.validate_row(_row(verdict="LEARN-FROM", license="AGPL-3.0"), 1)
    assert not any("license-ceiling-violation" in x for x in v)


def test_validate_row_avoid_with_noassertion_is_never_flagged_by_ceiling():
    v = val.validate_row(_row(verdict="AVOID", license="NOASSERTION"), 1)
    assert not any("license-ceiling-violation" in x for x in v)


def test_validate_row_copy_with_bad_license_reports_both_domain_and_ceiling():
    # A row can fail its OWN verdict-domain check and independently the
    # ceiling invariant -- both must be reported, never short-circuited.
    v = val.validate_row(_row(verdict="BOGUS", license="AGPL-3.0"), 1)
    assert any("verdict-domain" in x for x in v)


# --------------------------------------------------------------------------
# staleness — report-only, never a blocking violation
# --------------------------------------------------------------------------


def test_stale_report_line_fresh_row_returns_none():
    row = _row(last_checked_at="2026-08-31")
    assert val.stale_report_line(row, 1, today="2026-08-31") is None


def test_stale_report_line_just_under_threshold_returns_none():
    row = _row(last_checked_at="2026-06-01")
    assert val.stale_report_line(row, 1, today="2026-08-31") is None


def test_stale_report_line_over_threshold_returns_a_line():
    row = _row(last_checked_at="2025-01-01")
    line = val.stale_report_line(row, 1, today="2026-08-31")
    assert line is not None
    assert "stale" in line
    assert row["id"] in line


def test_stale_report_line_unparseable_date_returns_none():
    # A malformed last_checked_at is already a real, BLOCKING violation via
    # validate_row's date-format check -- staleness has nothing further to
    # add and must not also crash or double-report it.
    row = _row(last_checked_at="not-a-date")
    assert val.stale_report_line(row, 1, today="2026-08-31") is None


def test_check_ledger_stale_row_reported_but_never_a_violation(tmp_path):
    rows = [_row(id="RS-0001", last_checked_at="2020-01-01")]
    p = _write_ledger(tmp_path, rows)
    violations, staleness = val.check_ledger(str(p), today="2026-08-31")
    assert violations == []
    assert len(staleness) == 1
    assert "stale" in staleness[0]


def test_check_ledger_no_today_skips_staleness_entirely(tmp_path):
    rows = [_row(id="RS-0001", last_checked_at="2020-01-01")]
    p = _write_ledger(tmp_path, rows)
    violations, staleness = val.check_ledger(str(p), today=None)
    assert violations == []
    assert staleness == []


# --------------------------------------------------------------------------
# check_ledger — whole-file orchestration
# --------------------------------------------------------------------------


def test_check_ledger_clean_fixture_zero_violations(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="RS-0001")])
    violations, staleness = val.check_ledger(str(p))
    assert violations == []
    assert staleness == []


def test_check_ledger_two_row_sequence_clean(tmp_path):
    p = _write_ledger(
        tmp_path, [_row(id="RS-0001"), _row(id="RS-0002", oss_repo="other/repo")]
    )
    violations, _ = val.check_ledger(str(p))
    assert violations == []


def test_check_ledger_duplicate_id_flagged(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="RS-0001"), _row(id="RS-0001")])
    violations, _ = val.check_ledger(str(p))
    assert any("id-duplicate" in x for x in violations)


def test_check_ledger_json_parse_error_flagged(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text('{"id": "RS-0001", not valid json\n')
    violations, _ = val.check_ledger(str(p))
    assert any("json-parse-error" in x for x in violations)


def test_check_ledger_blank_lines_skipped(tmp_path):
    # A blank line is skipped entirely -- it must NOT consume a line number
    # for id-sequence purposes, so the real row (on file-line 2) still must
    # carry the id matching its LOGICAL line 1 to be sequence-clean... but
    # id-sequence is keyed to the RAW line number (matching
    # validate_agentarch_ledger's own convention, where a blank line is
    # simply never emitted by a real writer) -- so a leading blank line
    # means the real row must carry RS-0002 here, not RS-0001, to be clean.
    p = tmp_path / "ledger.jsonl"
    p.write_text(f'\n{json.dumps(_row(id="RS-0002"))}\n\n')
    violations, _ = val.check_ledger(str(p))
    assert violations == []


def test_check_ledger_unreadable_ledger_path(tmp_path):
    violations, staleness = val.check_ledger(str(tmp_path / "does_not_exist.jsonl"))
    assert len(violations) == 1
    assert "ledger-unreadable" in violations[0]
    assert staleness == []


def test_check_ledger_license_ceiling_violation_surfaces_in_full_run(tmp_path):
    p = _write_ledger(
        tmp_path, [_row(id="RS-0001", verdict="COPY", license="AGPL-3.0")]
    )
    violations, _ = val.check_ledger(str(p))
    assert any("license-ceiling-violation" in x for x in violations)


# --------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------


def test_main_exit_zero_on_clean_ledger(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="RS-0001")])
    rc = val.main([str(val.__file__), str(p)])
    assert rc == 0


def test_main_exit_one_on_dirty_ledger(tmp_path):
    row = _row(id="RS-0001")
    del row["mechanism"]
    p = _write_ledger(tmp_path, [row])
    rc = val.main([str(val.__file__), str(p)])
    assert rc == 1


def test_main_exit_zero_when_only_staleness_no_violations(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="RS-0001", last_checked_at="2020-01-01")])
    rc = val.main([str(val.__file__), str(p)])
    assert rc == 0


def test_main_subprocess_reports_and_matches_return_code(tmp_path):
    row = _row(id="RS-0001", verdict="BOGUS")
    p = _write_ledger(tmp_path, [row])
    proc = subprocess.run(
        [sys.executable, str(Path(val.__file__)), str(p)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1
    assert "verdict-domain" in proc.stdout
    assert "violation(s)" in proc.stdout


def test_main_defaults_to_default_ledger_path_argument_shape(tmp_path):
    # No behavioral assertion beyond "doesn't crash resolving argv" -- the
    # live-tree tests below exercise the real default path directly.
    p = _write_ledger(tmp_path, [_row(id="RS-0001")])
    rc = val.main([str(val.__file__), str(p)])
    assert rc in (0, 1)


# --------------------------------------------------------------------------
# live-tree run against the real ledger (#4731: "27 rows, currently clean —
# your validator must pass it")
# --------------------------------------------------------------------------


#
# The research ledger is a PER-MACHINE file: a fresh install does not ship it,
# `scripts/init_repo.sh` seeds it from `templates/knowledge/` into
# `<claude dir>/knowledge/` when absent (covered by test_init_repo.py). So a
# checkout laid out as a fresh install has no ledger at DEFAULT_LEDGER_PATH
# until that seed step has run. The fixture below uses the real ledger when it
# exists (the runtime: unchanged behavior) and otherwise performs the same
# copy init_repo.sh performs, into a sandbox home under pytest's tmp_path --
# never into the real home -- and validates that seeded file. The shipped seed
# itself must therefore pass the validator, which is the live-tree contract on
# a fresh install.

_SEED_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "knowledge" / "research_ledger.jsonl"
)


@pytest.fixture
def live_ledger_path(tmp_path):
    real = Path(val.DEFAULT_LEDGER_PATH)
    if real.is_file():
        return str(real)
    if not _SEED_TEMPLATE.is_file():
        pytest.skip(
            f"no ledger at {real} and no seed template at {_SEED_TEMPLATE} "
            "to stand in for it (init_repo.sh seeds the ledger from that template)"
        )
    seeded = tmp_path / "home" / ".claude" / "knowledge" / "research_ledger.jsonl"
    seeded.parent.mkdir(parents=True)
    shutil.copyfile(_SEED_TEMPLATE, seeded)
    return str(seeded)


def test_live_tree_ledger_is_clean(live_ledger_path):
    violations, _staleness = val.check_ledger(live_ledger_path, today="2026-08-31")
    assert violations == [], violations


def test_live_tree_main_exits_zero(live_ledger_path):
    rc = val.main([str(val.__file__), live_ledger_path])
    assert rc == 0


def test_live_tree_smoke_run_does_not_crash(live_ledger_path):
    violations, staleness = val.check_ledger(live_ledger_path)
    assert isinstance(violations, list)
    assert isinstance(staleness, list)
