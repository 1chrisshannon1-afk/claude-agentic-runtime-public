"""Tests for wheel_batch_validate (THE ISSUE WHEEL, commit 1 of the rollout
per `~/.claude/plans/issue_wheel_consolidation.md` §4 P2).

Three things this suite must prove, per the plan's own three-part acceptance
assertion (§4 P2, "Its test asserts three things"):
  1. A record that satisfies its P1 verdict's required fields is translated
     to `aggregate.py`'s own groom-Verdict spelling (already_done -> fixed,
     not_doing -> superseded, duplicate -> duplicate, unclear ->
     needs_more_info) -- P1's verdict strings are NOT `aggregate.py`-legal
     as-is (`already_done` has no alias in `normalize_verdict` at all;
     confirmed live against the real `_CANONICAL_ALIASES`), so this
     translation is load-bearing, not cosmetic.
  2. A record that does NOT satisfy its verdict's required fields is
     rewritten to needs_more_info FIELD-PRESERVINGLY -- `number` (and every
     other original field) survives, because `aggregate.py`'s own
     `_load_batch_file` reads `number` FIRST and a record missing it aborts
     parsing of the WHOLE batch file.
  3. This validator's actual OUTPUT, fed into `aggregate.py`'s real
     `_load_batch_file`, does not raise -- the assertion that actually
     proves the whole-file-abort guarantee holds end-to-end, not just
     against this module's own assertions (which a broken "fresh dict"
     implementation could also satisfy in isolation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wheel_batch_validate as wbv  # noqa: E402

_CSA_REPO = Path.home() / "Desktop" / "ExampleApp"
_AGGREGATE_IMPORTABLE = (
    _CSA_REPO / "repo_tooling" / "scripts" / "backlog_groom" / "aggregate.py"
).exists()


def _run_cli(tmp_path: Path, records: list[object]) -> list[dict[str, object]]:
    in_path = tmp_path / "in.json"
    out_path = tmp_path / "out.json"
    in_path.write_text(json.dumps(records), encoding="utf-8")
    exit_code = wbv.main(["--in", str(in_path), "--out", str(out_path)])
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# already_done
# ---------------------------------------------------------------------------


def test_already_done_with_valid_hex_sha_translates_to_fixed() -> None:
    """Test 1 (plan §4 P2 acceptance assertion 10, part 1): a record that
    already satisfies its verdict's required fields must be translated to
    `aggregate.py`'s own groom-Verdict spelling -- 'fixed', not the P1
    spelling 'already_done', which `normalize_verdict` has no alias for at
    all and would raise ValueError on if passed through unchanged."""
    rec = {
        "number": 42,
        "verdict": "already_done",
        "rationale": "shipped in a prior sweep",
        "batch_id": "b1",
        "cited_fix_sha": "abc1234",
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "fixed"
    assert result["number"] == 42
    assert result["cited_fix_sha"] == "abc1234"
    assert result["rationale"] == "shipped in a prior sweep"


@pytest.mark.parametrize(
    "bad_sha",
    [None, "", "not-hex-zzzz", "HEAD", "HEAD~5", ":/search"],
)
def test_already_done_missing_or_invalid_sha_rewrites_to_needs_more_info(
    bad_sha: object,
) -> None:
    """Test 2: verdict=already_done with NO (or invalid) cited_fix_sha must
    be rewritten to needs_more_info, with `number` PRESERVED -- never
    'fixed', never dropped from the output."""
    rec: dict[str, object] = {
        "number": 42,
        "verdict": "already_done",
        "rationale": "claims it was fixed already",
        "batch_id": "b1",
    }
    if bad_sha is not None:
        rec["cited_fix_sha"] = bad_sha
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 42
    assert result["verdict"] == "needs_more_info"
    assert result["verdict"] != "fixed"
    assert "wheel_batch_validate:" in result["rationale"]
    assert result["batch_id"] == "b1"


def test_already_done_accepts_full_length_hex_sha() -> None:
    rec = {
        "number": 7,
        "verdict": "already_done",
        "rationale": "r",
        "batch_id": "b1",
        "cited_fix_sha": "a" * 40,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "fixed"


# ---------------------------------------------------------------------------
# End-to-end: this validator's OUTPUT must not abort aggregate.py's loader.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _AGGREGATE_IMPORTABLE,
    reason="CSA repo with backlog_groom/aggregate.py not found",
)
def test_rewritten_already_done_record_survives_aggregate_load_batch_file(
    tmp_path: Path,
) -> None:
    """Test 3 (not optional -- the first two tests alone would pass against
    a broken 'fresh dict' implementation too): feed this validator's OUTPUT
    for an invalid already_done record into aggregate.py's REAL
    `_load_batch_file` and assert it does not raise. This is the test that
    actually proves the whole-file-abort guarantee holds."""
    sys.path.insert(0, str(_CSA_REPO))
    from repo_tooling.scripts.backlog_groom.aggregate import _load_batch_file

    rec = {
        "number": 999,
        "verdict": "already_done",
        "rationale": "claims fixed, no sha given",
        "batch_id": "b1",
    }
    validated = wbv.validate_batch([dict(rec)])
    assert (
        validated[0]["number"] == 999
    )  # field-preservation, asserted again at this boundary

    out_path = tmp_path / "validated_batch.json"
    out_path.write_text(json.dumps(validated), encoding="utf-8")

    parsed = _load_batch_file(out_path)  # must NOT raise

    assert len(parsed) == 1
    assert parsed[0].number == 999
    assert parsed[0].verdict.value == "needs_more_info"


@pytest.mark.skipif(
    not _AGGREGATE_IMPORTABLE,
    reason="CSA repo with backlog_groom/aggregate.py not found",
)
def test_multi_record_batch_with_one_bad_record_all_survive_aggregate_load(
    tmp_path: Path,
) -> None:
    """The precise failure this validator exists to prevent: ONE bad record
    (no cited_fix_sha) must not zero out the whole batch. All records —
    including the ones that needed no rewrite — must survive
    `_load_batch_file` together."""
    sys.path.insert(0, str(_CSA_REPO))
    from repo_tooling.scripts.backlog_groom.aggregate import _load_batch_file

    raw_batch = [
        {
            "number": 1,
            "verdict": "unclear",
            "rationale": "needs a human",
            "batch_id": "b1",
        },
        {
            "number": 2,
            "verdict": "already_done",
            "rationale": "no sha given",
            "batch_id": "b1",
        },
        {
            "number": 3,
            "verdict": "already_done",
            "rationale": "shipped",
            "batch_id": "b1",
            "cited_fix_sha": "deadbee",
        },
    ]
    validated = wbv.validate_batch([dict(r) for r in raw_batch])
    out_path = tmp_path / "validated_batch.json"
    out_path.write_text(json.dumps(validated), encoding="utf-8")

    parsed = _load_batch_file(out_path)  # must NOT raise -- all 3 records present

    assert {p.number for p in parsed} == {1, 2, 3}
    by_number = {p.number: p for p in parsed}
    assert by_number[1].verdict.value == "needs_more_info"  # unclear -> needs_more_info
    assert by_number[2].verdict.value == "needs_more_info"  # rewritten (no sha)
    assert by_number[3].verdict.value == "fixed"  # translated (valid sha)


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


def test_duplicate_with_target_passes_through_unchanged() -> None:
    rec = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "same as #10",
        "batch_id": "b1",
        "duplicate_of": 10,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "duplicate"
    assert result["number"] == 5
    assert result["duplicate_of"] == 10


def test_duplicate_missing_target_rewrites_to_needs_more_info() -> None:
    rec = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "looks like a dup but not sure of what",
        "batch_id": "b1",
    }
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 5
    assert result["verdict"] == "needs_more_info"
    assert "wheel_batch_validate:" in result["rationale"]


@pytest.mark.parametrize("duplicate_of", ["10", 10])
def test_duplicate_with_int_coercible_target_passes(duplicate_of: object) -> None:
    """`aggregate.py`'s own `parse_batch_record` calls `int(duplicate_of)` --
    both a real int and an int-shaped string must pass this validator,
    matching what aggregate.py itself will accept without raising."""
    rec = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "same as #10",
        "batch_id": "b1",
        "duplicate_of": duplicate_of,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "duplicate"


@pytest.mark.parametrize("bad_duplicate_of", ["abc", False, True, [], {}])
def test_duplicate_with_non_int_coercible_target_rewrites_to_needs_more_info(
    bad_duplicate_of: object,
) -> None:
    """code-reviewer round-1 finding 4: `parse_batch_record` does
    `int(duplicate_of)`, which raises `ValueError` (aborting the WHOLE batch
    file) on a non-coercible value -- this validator must reject the same
    shapes aggregate.py would reject, including `bool` (Python's
    `isinstance(True, int)` quirk would otherwise silently let a JSON `true`/
    `false` pass as issue #1/#0)."""
    rec: dict[str, object] = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "looks like a dup",
        "batch_id": "b1",
        "duplicate_of": bad_duplicate_of,
    }
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 5
    assert result["verdict"] == "needs_more_info"


@pytest.mark.parametrize("bad_value", [[], ["#12", "#34"], {}])
def test_duplicate_of_list_or_dict_shape_is_dropped_not_left_on_the_rejected_record(
    bad_value: object,
) -> None:
    """code-reviewer round-2 blocker: a `duplicate_of` shape aggregate.py's
    UNCONDITIONAL `int(duplicate_of) if duplicate_of is not None else None`
    coercion would raise on (a list -- realistic when an LLM names two
    duplicate targets -- or a dict) must be DROPPED from the rejected
    record, not merely left in place. Demonstrated live pre-fix: this exact
    value survived to `parse_batch_record` and raised `TypeError`, aborting
    the whole batch a SECOND way even after verdict/rationale were
    correctly rewritten."""
    rec: dict[str, object] = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "looks like a dup",
        "batch_id": "b1",
        "duplicate_of": bad_value,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert "duplicate_of" not in result


def test_bad_duplicate_of_on_an_unrelated_verdict_is_also_sanitized() -> None:
    """The unconditional coercion in aggregate.py does not check verdict at
    all -- a bad `duplicate_of` sitting on an `unclear` record (verdict is
    irrelevant to the coercion) must be sanitized too, not just when THIS
    validator's own duplicate-specific check happens to fire."""
    rec: dict[str, object] = {
        "number": 6,
        "verdict": "unclear",
        "rationale": "not sure",
        "batch_id": "b1",
        "duplicate_of": [],
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert "duplicate_of" not in result


@pytest.mark.parametrize(
    "labels_field", ["suggested_add_labels", "suggested_remove_labels"]
)
def test_non_iterable_labels_field_is_dropped_when_record_is_rejected(
    labels_field: str,
) -> None:
    """Same unconditional-coercion class, for `suggested_add_labels`/
    `suggested_remove_labels` -- aggregate.py's bare `tuple(raw.get(...) or
    ())` raises `TypeError` on a non-iterable (e.g. a bare int)."""
    rec: dict[str, object] = {
        "number": 7,
        "verdict": "unclear",
        "rationale": "not sure",
        "batch_id": "b1",
        labels_field: 5,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert labels_field not in result


def test_valid_duplicate_of_survives_rejection_for_an_unrelated_reason() -> None:
    """The sanitizer must never destroy a GENUINELY valid duplicate_of just
    because the record was rejected for some other, unrelated reason."""
    rec: dict[str, object] = {
        "number": 8,
        "verdict": "duplicate",
        "rationale": "",  # missing rationale -- the actual rejection reason
        "batch_id": "b1",
        "duplicate_of": 42,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert result.get("duplicate_of") == 42  # untouched -- it was never the problem


@pytest.mark.skipif(
    not _AGGREGATE_IMPORTABLE,
    reason="CSA repo with backlog_groom/aggregate.py not found",
)
def test_bad_duplicate_of_shape_does_not_abort_aggregate_py_batch(
    tmp_path: Path,
) -> None:
    """End-to-end regression for code-reviewer round-2 blocker: run the
    validator's rejection of a list-shaped duplicate_of through
    aggregate.py's real `_load_batch_file` and confirm it does NOT raise.
    Pre-fix this raised TypeError, aborting the whole batch."""
    sys.path.insert(0, str(_CSA_REPO))
    from repo_tooling.scripts.backlog_groom.aggregate import _load_batch_file

    rec = {
        "number": 9002,
        "verdict": "duplicate",
        "rationale": "looks like a dup of two things",
        "batch_id": "b1",
        "duplicate_of": ["#12", "#34"],
    }
    validated = wbv.validate_batch([dict(rec)])
    assert validated[0]["verdict"] == "needs_more_info"

    out_path = tmp_path / "validated_batch.json"
    out_path.write_text(json.dumps(validated), encoding="utf-8")

    parsed = _load_batch_file(out_path)  # must NOT raise

    assert len(parsed) == 1
    assert parsed[0].number == 9002
    assert parsed[0].duplicate_of is None


def test_duplicate_bool_duplicate_of_never_silently_becomes_issue_0_or_1() -> None:
    """Direct regression for the bool-is-int Python quirk: feeding the
    validator's own rejection through aggregate.py must never produce a
    `duplicate_of` of 0 or 1 that nobody asked for. code-reviewer round 2
    finding: the bad `duplicate_of` value must not merely be left in place
    once the record is rejected -- `aggregate.py`'s `int(duplicate_of) if
    duplicate_of is not None else None` coerces it UNCONDITIONALLY,
    regardless of verdict, so a non-coercible value surviving the rewrite
    aborts the whole batch a second, independent way. The key is DROPPED,
    not merely left non-coerced."""
    rec = {
        "number": 5,
        "verdict": "duplicate",
        "rationale": "bogus",
        "batch_id": "b1",
        "duplicate_of": False,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert (
        "duplicate_of" not in result
    )  # dropped, never left in a coercion-breaking shape


# ---------------------------------------------------------------------------
# not_doing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "citation", ["#4307", "4307", "closed via #4307 and commit abc1234"]
)
def test_not_doing_with_issue_ref_citation_translates_to_superseded(
    citation: str,
) -> None:
    rec = {
        "number": 8,
        "verdict": "not_doing",
        "rationale": "superseded by a later decision",
        "batch_id": "b1",
        "superseded_by": citation,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "superseded"
    assert result["number"] == 8
    assert result["superseded_by"] == citation


def test_not_doing_with_doc_path_citation_translates_to_superseded() -> None:
    rec = {
        "number": 8,
        "verdict": "not_doing",
        "rationale": "documented elsewhere",
        "batch_id": "b1",
        "superseded_by": "_Config_Project/docs/domain/launch_readiness.html",
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "superseded"
    assert result["number"] == 8


@pytest.mark.parametrize(
    "bad_citation",
    [
        None,
        "",
        "the operator said so",
        "n/a",
        "False",
        "   ",
        # code-reviewer round-1 blocker 1: these all contain a bare decimal
        # digit somewhere, which the ORIGINAL `_ISSUE_REF_RE = r"#?(\d+)"`
        # + `.search()` wrongly treated as a checkable issue ref. Executed
        # live pre-fix: each of these validated to "superseded" and then
        # made aggregate.py's real `_load_batch_file` raise ValueError,
        # aborting the whole batch -- the exact failure this module exists
        # to prevent. None of these is a bare "#NNNN"/"NNNN" (which IS
        # checkable, see test_not_doing_with_issue_ref_citation_translates_
        # to_superseded above) or an embedded "#NNNN" (also checkable) --
        # they are free prose that merely happens to contain a digit.
        "superseded by the v3 rewrite in 2026",
        "decided against in the 2026 replan",
        "no longer needed after the 2545 costbook migration",
    ],
)
def test_not_doing_missing_or_uncheckable_citation_rewrites_to_needs_more_info(
    bad_citation: object,
) -> None:
    rec: dict[str, object] = {
        "number": 8,
        "verdict": "not_doing",
        "rationale": "claims superseded",
        "batch_id": "b1",
    }
    if bad_citation is not None:
        rec["superseded_by"] = bad_citation
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 8
    assert result["verdict"] == "needs_more_info"
    assert result["verdict"] != "superseded"


@pytest.mark.skipif(
    not _AGGREGATE_IMPORTABLE,
    reason="CSA repo with backlog_groom/aggregate.py not found",
)
def test_not_doing_free_prose_with_a_digit_does_not_abort_aggregate_py_batch(
    tmp_path: Path,
) -> None:
    """End-to-end regression for code-reviewer round-1 blocker 1: run the
    validator's OWN rejection of a digit-bearing-but-uncheckable citation
    through aggregate.py's real `_load_batch_file` and confirm it does NOT
    raise -- this is the assertion that actually proves the fix, not just
    that this validator's own return value looks right in isolation. Before
    this fix, the ORIGINAL regex validated this exact citation as
    "checkable", and aggregate.py's real `_load_batch_file` then raised
    `ValueError` on it, aborting the whole batch."""
    sys.path.insert(0, str(_CSA_REPO))
    from repo_tooling.scripts.backlog_groom.aggregate import _load_batch_file

    rec = {
        "number": 9001,
        "verdict": "not_doing",
        "rationale": "claims superseded",
        "batch_id": "b1",
        "superseded_by": "superseded by the v3 rewrite in 2026",
    }
    validated = wbv.validate_batch([dict(rec)])
    assert validated[0]["verdict"] == "needs_more_info"

    out_path = tmp_path / "validated_batch.json"
    out_path.write_text(json.dumps(validated), encoding="utf-8")

    parsed = _load_batch_file(out_path)  # must NOT raise

    assert len(parsed) == 1
    assert parsed[0].number == 9001
    assert parsed[0].verdict.value == "needs_more_info"


@pytest.mark.parametrize("sha", ["deadbeef", "abcdefa", "fedcbae", "0123456789abcdef"])
def test_not_doing_with_sha_citation_and_no_digit_translates_to_superseded(
    sha: str,
) -> None:
    """code-reviewer round-1 blocker 2: a raw hex sha citation with NO
    decimal digit in it (an all-letter-and-hex-digit-but-no-0-9 shape is
    actually impossible for real git shas in practice, but a sha like
    "deadbeef"/"abcdefa"/"fedcbae" that happens to contain zero ASCII digits
    0-9 -- i.e. every character is a-f -- must still be recognized as a
    checkable sha citation, matching aggregate.py's own `_citation_component`
    sha branch (`_SHA_RE.fullmatch`), which this validator previously had NO
    branch for at all and would silently reject."""
    rec = {
        "number": 8,
        "verdict": "not_doing",
        "rationale": "reverted in a later commit",
        "batch_id": "b1",
        "superseded_by": sha,
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "superseded"
    assert result["number"] == 8


# ---------------------------------------------------------------------------
# unclear
# ---------------------------------------------------------------------------


def test_unclear_with_rationale_and_batch_id_translates_to_needs_more_info() -> None:
    rec = {
        "number": 3,
        "verdict": "unclear",
        "rationale": "can't tell",
        "batch_id": "b1",
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"
    assert result["number"] == 3


def test_unclear_missing_rationale_rewrites_to_needs_more_info() -> None:
    rec = {"number": 3, "verdict": "unclear", "rationale": "", "batch_id": "b1"}
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 3
    assert result["verdict"] == "needs_more_info"


# ---------------------------------------------------------------------------
# Verdicts P1 is documented to never emit -- defensive rewrite.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict", ["needs_work", "operator_only", "bogus_verdict", ""]
)
def test_unrecognized_verdict_rewrites_to_needs_more_info_defensively(
    verdict: str,
) -> None:
    rec = {"number": 11, "verdict": verdict, "rationale": "r", "batch_id": "b1"}
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 11
    assert result["verdict"] == "needs_more_info"


def test_missing_verdict_field_entirely_rewrites_to_needs_more_info() -> None:
    rec: dict[str, object] = {"number": 11, "rationale": "r", "batch_id": "b1"}
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 11
    assert result["verdict"] == "needs_more_info"


# ---------------------------------------------------------------------------
# Universal field-preservation: batch_id / other original fields survive
# even through a rewrite, regardless of which verdict path triggered it.
# ---------------------------------------------------------------------------


def test_rewrite_preserves_arbitrary_extra_fields() -> None:
    rec = {
        "number": 21,
        "verdict": "already_done",
        "rationale": "r",
        "batch_id": "b1",
        "evidence_path": "some/path.md",
        "suggested_add_labels": ["area: billing"],
    }
    result = wbv.validate_record(dict(rec))
    assert result["verdict"] == "needs_more_info"  # no cited_fix_sha -> rewritten
    assert result["number"] == 21
    assert result["evidence_path"] == "some/path.md"
    assert result["suggested_add_labels"] == ["area: billing"]


def test_missing_batch_id_rewrites_to_needs_more_info() -> None:
    rec = {"number": 30, "verdict": "unclear", "rationale": "r"}
    result = wbv.validate_record(dict(rec))
    assert result["number"] == 30
    assert result["verdict"] == "needs_more_info"


# ---------------------------------------------------------------------------
# validate_batch / CLI -- never drops a record, always same-length output.
# ---------------------------------------------------------------------------


def test_validate_batch_never_drops_a_record() -> None:
    raw = [
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
        {"number": 3, "verdict": "bogus", "rationale": "r", "batch_id": "b1"},
    ]
    result = wbv.validate_batch([dict(r) for r in raw])
    assert len(result) == 3
    assert [r["number"] for r in result] == [1, 2, 3]


def test_validate_batch_drops_non_dict_records_loudly_not_silently() -> None:
    """A non-dict entry has no `number` to preserve, so it is DROPPED rather
    than kept as a numberless needs_more_info shell -- a numberless shell
    would abort aggregate.py's _load_batch_file (which reads raw["number"]
    first) just as badly as dropping it would, so keeping it in is not
    actually safer. The drop must never be silent, though -- `main()` reports
    the count explicitly (see test_cli_reports_dropped_non_dict_records)."""
    result = wbv.validate_batch(["not a dict", None, 42])
    assert result == []


def test_validate_batch_drops_only_non_dict_entries_keeps_real_records() -> None:
    """A mixed batch: non-dicts are dropped, real records (even malformed
    ones) survive as rewritten needs_more_info shells with their number
    preserved."""
    raw: list[Any] = [
        "not a dict",
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        None,
        {"number": 2, "verdict": "bogus", "rationale": "r", "batch_id": "b1"},
    ]
    result = wbv.validate_batch(raw)
    assert len(result) == 2
    assert [r["number"] for r in result] == [1, 2]


# ---------------------------------------------------------------------------
# `number` -- code-reviewer round 3: aggregate.py's `parse_batch_record`
# does `int(raw["number"])` UNCONDITIONALLY, before verdict or anything else
# runs. A record with no recoverable `number` cannot be sanitized (there is
# no safe fallback identity, unlike duplicate_of/labels) -- it must be
# DROPPED, exactly like a non-dict entry, not kept as a needs_more_info
# shell with a bad number.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_number", [None, [1], {"a": 1}, "abc", "3.7", "", [], {}])
def test_record_with_uncoercible_number_is_dropped(bad_number: object) -> None:
    rec: dict[str, object] = {
        "number": bad_number,
        "verdict": "unclear",
        "rationale": "r",
        "batch_id": "b1",
    }
    result = wbv.validate_record(dict(rec))
    assert result is None


def test_record_with_missing_number_key_entirely_is_dropped() -> None:
    rec = {"verdict": "unclear", "rationale": "r", "batch_id": "b1"}
    result = wbv.validate_record(dict(rec))
    assert result is None


@pytest.mark.parametrize("good_number", [1, "1", "  42  ", 4724])
def test_record_with_int_coercible_number_is_kept(good_number: object) -> None:
    rec = {
        "number": good_number,
        "verdict": "unclear",
        "rationale": "r",
        "batch_id": "b1",
    }
    result = wbv.validate_record(dict(rec))
    assert result is not None
    assert result["number"] == good_number  # preserved verbatim, never re-coerced


def test_validate_batch_drops_bad_number_records_but_keeps_siblings() -> None:
    """The precise failure this fix exists to prevent: one record with a
    bad `number` must not zero out the whole batch -- every OTHER record,
    including ones needing no rewrite, survives."""
    raw: list[Any] = [
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {
            "number": [9],
            "verdict": "unclear",
            "rationale": "bad number",
            "batch_id": "b",
        },
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
    ]
    result = wbv.validate_batch(raw)
    assert len(result) == 2
    assert [r["number"] for r in result] == [1, 2]


def test_cli_reports_dropped_bad_number_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()`'s drop count and reject-count alignment must account for the
    bad-number drop case too, not just non-dict entries (code-reviewer
    round 3: the original fix used a narrower isinstance(rec, dict) check
    here, which would have silently under-reported this case)."""
    records: list[object] = [
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {"number": "abc", "verdict": "unclear", "rationale": "bad", "batch_id": "b1"},
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
    ]
    result = _run_cli(tmp_path, records)
    assert len(result) == 2
    by_number = {r["number"]: r for r in result}
    assert by_number[1]["verdict"] == "needs_more_info"
    assert by_number[2]["verdict"] == "needs_more_info"  # no sha, correctly rejected
    captured = capsys.readouterr()
    assert "1 dropped" in captured.out
    assert "1 rejected" in captured.out  # only record 2, correctly aligned


@pytest.mark.skipif(
    not _AGGREGATE_IMPORTABLE,
    reason="CSA repo with backlog_groom/aggregate.py not found",
)
def test_bad_number_record_dropped_does_not_abort_aggregate_py_batch(
    tmp_path: Path,
) -> None:
    """End-to-end regression for code-reviewer round-3 blocker: a batch
    containing one record with an uncoercible `number` must not abort
    aggregate.py's real `_load_batch_file` for the whole file -- the bad
    record is dropped by this validator BEFORE aggregate.py ever sees it."""
    sys.path.insert(0, str(_CSA_REPO))
    from repo_tooling.scripts.backlog_groom.aggregate import _load_batch_file

    raw_batch: list[object] = [
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {"number": [9], "verdict": "unclear", "rationale": "bad", "batch_id": "b1"},
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
    ]
    validated = wbv.validate_batch([dict(r) for r in raw_batch])
    assert len(validated) == 2

    out_path = tmp_path / "validated_batch.json"
    out_path.write_text(json.dumps(validated), encoding="utf-8")

    parsed = _load_batch_file(out_path)  # must NOT raise

    assert {p.number for p in parsed} == {1, 2}


def test_cli_round_trips_a_mixed_batch(tmp_path: Path) -> None:
    records = [
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
        {
            "number": 3,
            "verdict": "duplicate",
            "rationale": "r",
            "batch_id": "b1",
            "duplicate_of": 99,
        },
    ]
    result = _run_cli(tmp_path, records)
    assert len(result) == 3
    by_number = {r["number"]: r for r in result}
    assert by_number[1]["verdict"] == "needs_more_info"  # unclear -> needs_more_info
    assert by_number[2]["verdict"] == "needs_more_info"  # no sha
    assert by_number[3]["verdict"] == "duplicate"


def test_cli_rejects_non_array_input(tmp_path: Path) -> None:
    in_path = tmp_path / "in.json"
    out_path = tmp_path / "out.json"
    in_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    exit_code = wbv.main(["--in", str(in_path), "--out", str(out_path)])
    assert exit_code == 1
    assert not out_path.exists()


def test_cli_reject_count_is_zero_for_a_valid_already_done_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression guard: `validate_record` mutates records IN PLACE, so a
    naive `original.get("verdict") != result.get("verdict")` comparison
    after the fact always reads True (they are literally the same object by
    then) -- a genuinely valid record must still report 0 rejected, not 1,
    in the CLI's summary line."""
    records = [
        {
            "number": 4724,
            "verdict": "already_done",
            "rationale": "shipped",
            "batch_id": "b1",
            "cited_fix_sha": "abc1234",
        }
    ]
    result = _run_cli(tmp_path, records)
    assert result[0]["verdict"] == "fixed"
    captured = capsys.readouterr()
    assert "0 rejected" in captured.out


def test_cli_reports_dropped_non_dict_records_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dropped non-dict record must never be silent -- `main()`'s own
    stdout reports the drop count explicitly, and the reject-count alignment
    must not be thrown off by the dropped position (a real regression risk
    once `validated` became shorter than `data`)."""
    records: list[object] = [
        "not a dict",
        {"number": 1, "verdict": "unclear", "rationale": "r", "batch_id": "b1"},
        {"number": 2, "verdict": "already_done", "rationale": "r", "batch_id": "b1"},
    ]
    result = _run_cli(tmp_path, records)
    assert len(result) == 2
    by_number = {r["number"]: r for r in result}
    assert by_number[1]["verdict"] == "needs_more_info"
    assert by_number[2]["verdict"] == "needs_more_info"  # no sha, correctly rejected
    captured = capsys.readouterr()
    assert "1 dropped" in captured.out
    assert (
        "1 rejected" in captured.out
    )  # only record 2, not miscounted against 1's slot


def test_cli_reject_count_is_one_for_an_invalid_already_done_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = [
        {
            "number": 4724,
            "verdict": "already_done",
            "rationale": "shipped",
            "batch_id": "b1",
        }
    ]
    result = _run_cli(tmp_path, records)
    assert result[0]["verdict"] == "needs_more_info"
    assert result[0]["number"] == 4724
    captured = capsys.readouterr()
    assert "1 rejected" in captured.out
