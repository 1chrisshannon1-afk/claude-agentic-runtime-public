"""Hermetic tests for scripts/render_cycle_log.py (BLOCKER 5, round 3).

Before this file, the 1,723-line operator-facing renderer had ZERO tests --
and two live, undetected defects (BLOCKER 3's metric-drift, BLOCKER 4's
uncaught-exception crash, the latter a RECURRENCE of something round 1
already flagged) sat in that untested code. Every test here passes an
explicit `--cycles-dir`/tmp_path, so nothing touches the operator's real
~/.claude/telemetry. No network.

This file lives in hooks/tests/ (this repo's one test root) even though the
module under test lives in scripts/ -- both dirs are added to sys.path below
so `import render_cycle_log` and `import cycle_telemetry` work regardless of
pytest's rootdir/cwd, the same pattern hooks/tests/conftest.py already uses
for `_lib`.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import cycle_telemetry as ct  # noqa: E402  (import after sys.path shim)
import render_cycle_log as r  # noqa: E402  (import after sys.path shim)

# ---------------------------------------------------------------------------
# Minimal record builders -- deliberately independent of
# hooks/tests/test_cycle_telemetry.py's builders, since this file exercises
# the RENDERER's own tolerance for partial/malformed data, not the library's
# schema validator.
# ---------------------------------------------------------------------------


def _record(**overrides: object) -> dict:
    record: dict = {
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
    d: dict = {
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
    f: dict = {
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


def _write_record(cycles_dir: Path, system: str, cycle_id: str, record: dict) -> Path:
    sys_dir = cycles_dir / system
    sys_dir.mkdir(parents=True, exist_ok=True)
    path = sys_dir / f"{cycle_id}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# (a) Metric parity against cycle_telemetry -- BLOCKER 3. Locks the whole
# "renderer silently reimplements and drifts" failure class shut permanently:
# analyze() now calls ct.aggregate_metrics() directly, so parity is
# structural, not coincidental -- but these tests exist so a FUTURE
# reintroduction of a local reimplementation (e.g. "inlining for speed")
# fails loudly instead of silently drifting a third time.
# ---------------------------------------------------------------------------


def test_usd_per_confirmed_defect_matches_library_and_restricts_to_priced_records(tmp_path: Path) -> None:
    """The exact measured divergence: library computes 1.0, the OLD renderer
    computed 0.667 on this SAME two-record corpus, because the old renderer's
    version divided total priced cost by ALL findings across ALL cycles
    (including an unpriced cycle's findings) instead of restricting both
    numerator and denominator to PRICED records only -- this module's own
    "missing is not zero" rule, violated on its own headline ratio."""
    cycles_dir = tmp_path / "cycles"
    priced = _record(
        system="sys1",
        cycle_id="c1",
        cost={"source": "spend_ledger", "total_tokens": 1000, "total_usd": 2.0},
        findings=[_finding(finding_id="f1"), _finding(finding_id="f2")],
    )
    unpriced = _record(
        system="sys1",
        cycle_id="c2",
        cost={"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "never ran"},
        findings=[_finding(finding_id="f3")],
    )
    _write_record(cycles_dir, "sys1", "c1", priced)
    _write_record(cycles_dir, "sys1", "c2", unpriced)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    analysis = r.analyze(records)

    expected = ct.aggregate_metrics([priced, unpriced])["usd_per_confirmed_defect"]
    assert expected == pytest.approx(1.0)
    assert analysis.usd_per_confirmed_defect == pytest.approx(expected)

    # The OLD renderer's buggy formula, reproduced here ONLY to prove the
    # real code no longer matches it: total priced usd / ALL confirmed
    # findings across ALL cycles (2.0 / 3 = 0.667).
    old_buggy_value = 2.0 / 3
    assert analysis.usd_per_confirmed_defect != pytest.approx(old_buggy_value)


def test_symptom_precision_matches_library_on_an_unrecognized_verdict(tmp_path: Path) -> None:
    """The exact measured divergence: library 0.5, OLD renderer 1.0, because
    the old renderer's closed-enum DETERMINATE_VERDICTS silently dropped the
    unrecognized verdict from its denominator instead of counting it as
    indeterminate-but-judged (REFUTED-equivalent) like the library does."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        findings=[
            _finding(finding_id="f1", verifier_verdict="CONFIRMED"),
            _finding(finding_id="f2", verifier_verdict="TOTALLY_UNRECOGNIZED_VALUE"),
        ],
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    analysis = r.analyze(records)

    expected = ct.aggregate_metrics([record])["symptom_precision"]
    assert expected == pytest.approx(0.5)
    assert analysis.symptom_precision == pytest.approx(expected)
    assert analysis.symptom_precision != pytest.approx(1.0)


def test_consolidation_ratio_matches_library_on_empty_raised_by(tmp_path: Path) -> None:
    """The exact measured divergence: library 0.0, OLD renderer None, because
    the old renderer special-cased a zero raiser-total sum as "no data" (None)
    instead of a real, computable 0.0 ratio."""
    cycles_dir = tmp_path / "cycles"
    record = _record(findings=[_finding(finding_id="f1", raised_by=[])])
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    analysis = r.analyze(records)

    expected = ct.aggregate_metrics([record])["consolidation_ratio"]
    assert expected == pytest.approx(0.0)
    assert analysis.consolidation_ratio == pytest.approx(0.0)
    assert analysis.consolidation_ratio is not None


def test_metric_parity_over_a_mixed_corpus(tmp_path: Path) -> None:
    """General parity sweep: every shared metric this renderer displays must
    equal cycle_telemetry's own aggregate_metrics() over the identical raw
    records, across a corpus that exercises duplicates, ruling conflicts,
    cause judgments, and calibration plants together (not just one metric in
    isolation, the way the three tests above each do)."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        findings=[
            _finding(finding_id="f1", verifier_verdict="CONFIRMED", verifier_cause_upheld=True),
            _finding(finding_id="f2", verifier_verdict="REFUTED", verifier_cause_upheld=False),
            _finding(
                finding_id="f3",
                verifier_verdict="ALREADY_TRACKED_ELSEWHERE",
                already_tracked_as="f1",
                fights_ruling="yes it does",
                raised_by=["finder", "verifier"],
            ),
        ],
        calibration={
            "plant_id": "plant-1",
            "planted_in": "finder",
            "slot": "1",
            "caught_by": ["1"],
            "missed_by": [],
        },
        cost={"source": "spend_ledger", "total_tokens": 500, "total_usd": 3.0},
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    analysis = r.analyze(records)
    expected = ct.aggregate_metrics([record])

    assert analysis.symptom_precision == pytest.approx(expected["symptom_precision"])
    assert analysis.cause_precision == pytest.approx(expected["cause_precision"])
    assert analysis.duplicate_rate == pytest.approx(expected["duplicate_rate"])
    assert analysis.ruling_conflict_rate == pytest.approx(expected["ruling_conflict_rate"])
    assert analysis.consolidation_ratio == pytest.approx(expected["consolidation_ratio"])
    assert analysis.usd_per_confirmed_defect == pytest.approx(expected["usd_per_confirmed_defect"])
    assert analysis.plant_catch_by_slot == expected["plant_catch_by_slot"]


# ---------------------------------------------------------------------------
# (b) Malformed-field crash cases -- BLOCKER 4. fmt_pct/fmt_usd must never
# raise on a type they weren't expecting; main() must never crash with
# nothing written, even for a type of malformation neither of those two
# guards anticipated.
# ---------------------------------------------------------------------------


def test_fmt_pct_and_fmt_usd_never_raise_on_a_malformed_value() -> None:
    """Direct falsification of BLOCKER 4's crash: these used to raise
    ValueError/TypeError on a non-numeric value (only fmt_int_or_dash was
    type-guarded before this fix)."""
    assert r.fmt_pct("high") == "invalid data"
    assert r.fmt_usd("1.50") == "invalid data"
    assert r.fmt_ratio("lots") == "invalid data"
    # Still-correct behavior for the values these functions were designed for.
    assert r.fmt_pct(None) == "n/a"
    assert r.fmt_usd(None) == "no cost data"
    assert r.fmt_pct(0.5) == "50%"
    assert r.fmt_usd(1.5) == "$1.50"


def test_render_document_survives_malformed_dispatch_cost_usd(tmp_path: Path) -> None:
    """BLOCKER 4's exact repro #1: dispatches[0].cost_usd = "1.50" (a
    realistic hand-edited/corrupted record) must render a visible
    placeholder rather than crashing render_document() -- the module's own
    docstring says it must survive exactly this."""
    cycles_dir = tmp_path / "cycles"
    record = _record(dispatches=[_dispatch(cost_usd="1.50")])
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    doc = r.render_document(records, issues, cycles_dir)  # must not raise
    assert "invalid data" in doc


def test_render_document_survives_malformed_verdict_confidence(tmp_path: Path) -> None:
    """BLOCKER 4's exact repro #2: verdicts[0].confidence = "high"."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        verdicts=[
            {
                "dispatch_label": "pass-1",
                "scenario": "s1",
                "verdict": "CONCUR",
                "confidence": "high",
                "problem_count": 1,
            }
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    doc = r.render_document(records, issues, cycles_dir)  # must not raise
    assert "invalid data" in doc


def test_main_writes_a_page_even_when_an_unanticipated_exception_escapes_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 4's broader ask (round 3): wrap the top-level render call in
    main() so ANY unanticipated exception -- not just the format-layer
    guards' anticipated fields -- still writes a page.

    BLOCKER 5 (round 4) FIX: this test's original triggering input, a
    top-level `cost.total_usd = "5.00"`, was claimed to raise a real
    exception in cycle_telemetry's aggregate_metrics(). It never actually
    exercised the safety net -- round 3's OWN sibling fix (the `_is_number`
    guard cycle_telemetry.py's aggregate_metrics() already applies before
    summing total_usd) made that exact input render SUCCESSFULLY, not crash.
    The test still passed anyway because its assertion
    (`"render error" in written.lower() or "<html" in written.lower()`) is
    satisfied by ANY successful render too -- every rendered page contains
    "<html". That made it pass vacuously with the safety net entirely
    removed, which is what "falsifiable" means it must not do.

    The fix here is two-fold: (1) force a REAL, still-live exception with
    monkeypatch rather than relying on a specific malformed-JSON shape
    happening to still crash after every other per-field guard in this
    module and cycle_telemetry.py is hardened -- a synthetic, unconditional
    exception can never be accidentally "fixed" out from under this test by
    an unrelated guard added elsewhere; (2) assert on the error page's own
    specific marker text ("cycle log failed to render", verified against
    render_error_page()'s actual literal heading), never the generic
    "<html" substring every successful render also contains.
    """
    cycles_dir = tmp_path / "cycles"
    record = _record()
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    out_path = tmp_path / "out.html"

    def _boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("synthetic unanticipated exception (BLOCKER 5, round 4)")

    monkeypatch.setattr(r, "render_document", _boom)

    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])

    assert rc == 0  # documented "Exits 0 always" contract
    assert out_path.exists()
    written = out_path.read_text(encoding="utf-8")
    assert written  # never empty
    # The actual error-page marker -- NOT the generic "<html" substring,
    # which a successful, non-error render also contains.
    assert "cycle log failed to render" in written.lower()
    assert "synthetic unanticipated exception" in written  # the real traceback is on the page


def test_one_non_utf8_file_is_isolated_not_a_whole_report_blank(tmp_path: Path) -> None:
    """BLOCKER 3 (round 4): load_cycle_records()'s `path.read_text(encoding
    ="utf-8")` used to be wrapped in `except OSError` only --
    UnicodeDecodeError is a ValueError subclass, NOT an OSError, so it
    escaped straight past that guard to main()'s outer safety net and
    blanked the ENTIRE multi-system report with the generic error page,
    instead of being isolated as a per-file LoadIssue the way every other
    malformed file already is. Real repro: one cycle file truncated
    mid-multibyte-character (exactly what a process killed mid-write, e.g.
    the CLI's resolve-cost --write path before its own atomic-write fix,
    would leave on disk)."""
    cycles_dir = tmp_path / "cycles"
    bad_dir = cycles_dir / "loop"
    bad_dir.mkdir(parents=True)
    (bad_dir / "x.json").write_bytes(b'{"schema_version": 2, "system": "\xff\xfebad"}')

    good_dir = cycles_dir / "other"
    good_dir.mkdir(parents=True)
    good_record = _record(system="other", cycle_id="y")
    (good_dir / "y.json").write_text(json.dumps(good_record), encoding="utf-8")

    records, issues = r.load_cycle_records(cycles_dir)  # must not raise
    assert len(records) == 1
    assert records[0].system == "other"
    assert len(issues) == 1
    assert "x.json" in issues[0].path
    assert "could not read file" in issues[0].reason

    # And the full main() pipeline must reflect the SAME isolation, not the
    # generic whole-report error page -- this is the actual operator-facing
    # promise blocker 3 exists to keep.
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    written = out_path.read_text(encoding="utf-8")
    assert "cycle log failed to render" not in written.lower()
    assert "other" in written  # the good system's record still rendered


def test_esc_sanitizes_a_lone_surrogate_instead_of_passing_it_through(tmp_path: Path) -> None:
    """Round 12, BLOCKER 1 (root cause): `html.escape()` does not touch a
    lone Unicode surrogate at all -- `esc()` used to return it completely
    unchanged, deferring the problem to UTF-8 encode time (main crash
    below). Sanitizing HERE, at the one chokepoint every piece of
    record-derived text flows through, means the surrogate is rendered as
    readable text instead of ever reaching an encode boundary unsanitized."""
    lone_surrogate = "bad" + chr(0xD800) + "char"
    escaped = r.esc(lone_surrogate)
    assert "\\ud800" in escaped  # readable backslash-escaped text, not a raw code point
    assert chr(0xD800) not in escaped  # the actual unencodable code point is gone
    # And the sanitized text is genuinely UTF-8 encodable now -- this is
    # the property that prevents the destructive write-time crash below.
    escaped.encode("utf-8")


def test_a_lone_surrogate_in_a_cycle_record_does_not_crash_or_destroy_a_prior_good_report(
    tmp_path: Path,
) -> None:
    """Round 12, BLOCKER 1 -- THE MOST SEVERE DEFECT IN THIS MODULE'S
    HISTORY: a lone Unicode surrogate (e.g. a byte-mangled terminal capture
    landing in `claim_symptom`) is valid JSON, survives `json.loads`
    untouched, and passed straight through `html.escape()` unchanged --
    so the FIRST place it ever caused a problem was
    `out_path.write_text(html_doc, encoding="utf-8")`, which raises
    `UnicodeEncodeError` (a `ValueError` subclass, NOT an `OSError` -- the
    exact mirror image of round 4/6's decode-side fix) INSIDE a call that
    had ALREADY TRUNCATED the destination file to empty. A report that was
    previously valid and complete was destroyed, not merely left un-updated
    -- and the offending record wasn't even listed as excluded, since it
    parsed and normalized just fine.

    This test asserts all four things the review demanded, in order of
    severity: (1) the render does not crash; (2) a PRE-EXISTING good report
    at the same output path is NOT destroyed by a subsequent poisoned
    render -- the single most important assertion here, given the
    destructive nature of this bug; (3) the clean record from a different
    system survives in the output; (4) the surrogate itself renders as
    readable text rather than vanishing or crashing.
    """
    cycles_dir = tmp_path / "cycles"
    poison_record = _record(system="sysA", cycle_id="poison-1")
    poison_record["findings"] = [_finding(claim_symptom="bad" + chr(0xD800) + "char")]
    clean_record = _record(system="sysB", cycle_id="clean-1")
    clean_record["findings"] = [_finding(claim_symptom="a perfectly ordinary finding")]

    # First, render a report with ONLY the clean record -- this is the
    # "previously-good, previously-written" report the destructive bug
    # would otherwise wipe out.
    _write_record(cycles_dir, "sysB", "clean-1", clean_record)
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    good_report = out_path.read_text(encoding="utf-8")
    assert good_report  # a real, non-empty, previously-good report
    assert "a perfectly ordinary finding" in good_report

    # Now add the poisoned record alongside the clean one and re-render to
    # the SAME output path.
    _write_record(cycles_dir, "sysA", "poison-1", poison_record)
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])

    # (1) no crash -- this module's own "Exits 0 always" contract.
    assert rc == 0

    written = out_path.read_text(encoding="utf-8")

    # (2) THE critical assertion: the previously-good report must NOT be
    # destroyed/truncated by the poisoned re-render.
    assert written != ""
    assert len(written) >= len(good_report)

    # (3) the clean record's data survived being rendered alongside the
    # poisoned one.
    assert "a perfectly ordinary finding" in written

    # (4) the surrogate itself renders as readable text, not silently
    # dropped and not left as a raw unencodable code point.
    assert "\\ud800" in written
    assert chr(0xD800) not in written
    # And the poisoned record was not silently excluded either -- it
    # normalized and rendered like any other record, exactly as the
    # review's "not even listed in the excluded panel" observation implies
    # it always did (the bug was never in loading/normalizing it).
    assert "cycle log failed to render" not in written.lower()

    # Round-trip sanity: the written file is itself valid, encodable UTF-8.
    written.encode("utf-8")


# ---------------------------------------------------------------------------
# (c) XSS lock -- the prior security fix (render_script's "</script" escape)
# must stay shut mechanically, not just by comment.
# ---------------------------------------------------------------------------


def test_system_slug_xss_payload_produces_exactly_one_real_script_close_tag(tmp_path: Path) -> None:
    payload_system = "</script><script>alert(1)</script>"
    cycles_dir = tmp_path / "cycles"
    record = _record(system=payload_system)
    # write_record sanitizes the directory name via Path, so use the raw
    # dir_system as a SEPARATE, safe directory name -- the payload lives in
    # the record's own "system" FIELD (normalize_record honours the field
    # over the directory name when they differ), which is the actual attack
    # surface render_script() escapes.
    _write_record(cycles_dir, "dir-name-safe", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    assert records[0].system == payload_system

    doc = r.render_document(records, issues, cycles_dir)
    # Exactly two REAL closing </script> tags: this document's own two
    # legitimate <script> blocks (render_script's filter/chip JS, added by
    # W-EL: render_print_script's "Print all cycles" force-open/restore
    # JS) -- neither of which contains the payload's own dynamic system
    # slug. The payload's literal "</script" must have been neutralized
    # (escaped to </script or HTML-escaped to &lt;/script), never appear as
    # a real tag a browser's HTML parser would treat as a script boundary.
    assert doc.count("</script>") == 2


# ---------------------------------------------------------------------------
# (d) 0 / 1 / many records render correctly.
# ---------------------------------------------------------------------------


def test_zero_records_renders_empty_state(tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    cycles_dir.mkdir()
    records, issues = r.load_cycle_records(cycles_dir)
    assert records == [] and issues == []
    doc = r.render_document(records, issues, cycles_dir)
    assert "No cycle records yet" in doc


def test_one_record_renders_its_own_system_section(tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    record = _record(system="solo-system", cycle_id="only-cycle")
    _write_record(cycles_dir, "solo-system", "only-cycle", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert len(records) == 1
    doc = r.render_document(records, issues, cycles_dir)
    assert "solo-system" in doc
    assert "only-cycle" in doc


def test_many_records_across_multiple_systems_all_render(tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    for i in range(3):
        _write_record(
            cycles_dir,
            "system-a",
            f"cycle-{i}",
            _record(system="system-a", cycle_id=f"cycle-{i}", started_at=f"2026-08-2{i}T14:00:00Z", ended_at=f"2026-08-2{i}T15:00:00Z"),
        )
    for i in range(2):
        _write_record(
            cycles_dir,
            "system-b",
            f"cycle-{i}",
            _record(system="system-b", cycle_id=f"cycle-{i}", started_at=f"2026-08-2{i}T14:00:00Z", ended_at=f"2026-08-2{i}T15:00:00Z"),
        )
    records, issues = r.load_cycle_records(cycles_dir)
    assert len(records) == 5
    assert issues == []
    doc = r.render_document(records, issues, cycles_dir)
    for i in range(3):
        assert f"cycle-{i}" in doc
    assert "system-a" in doc
    assert "system-b" in doc
    analysis_a = r.analyze(r.filter_by_system(records, ["system-a"]))
    assert analysis_a.n_cycles == 3
    analysis_b = r.analyze(r.filter_by_system(records, ["system-b"]))
    assert analysis_b.n_cycles == 2


def test_render_system_details_calls_aggregate_metrics_n_plus_one_times_not_2n_plus_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 12, nit #10 (renamed with the render_system_section ->
    render_system_details rewrite; call-count contract unchanged):
    `render_system_details` already computes a per-record `analyze([r])`
    for its trend series (N calls) plus one whole-system `analyze(ordered)`
    for the summary (1 call) -- N+1 calls to `ct.aggregate_metrics()` in
    total, when called directly with no `precomputed` argument (as this
    test does). `render_cycle_details` used to ALSO call `analyze([r])`
    again for each record internally, making the real total roughly 2N+1
    -- exactly double the necessary work for no correctness benefit
    (`aggregate_metrics()` is pure and deterministic). This test counts
    real calls to `ct.aggregate_metrics` and asserts the fixed N+1 total
    for a 4-record system, falsifying a reintroduction of the redundant
    per-card recomputation."""
    cycles_dir = tmp_path / "cycles"
    n = 4
    for i in range(n):
        _write_record(
            cycles_dir,
            "system-a",
            f"cycle-{i}",
            _record(system="system-a", cycle_id=f"cycle-{i}"),
        )
    records, issues = r.load_cycle_records(cycles_dir)
    assert len(records) == n

    call_count = 0
    real_aggregate = ct.aggregate_metrics

    def _counting_aggregate(*args: object, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        return real_aggregate(*args, **kwargs)

    monkeypatch.setattr(ct, "aggregate_metrics", _counting_aggregate)
    r.render_system_details("system-a", records)
    assert call_count == n + 1, f"expected {n + 1} aggregate_metrics calls (N per-cycle + 1 whole-system), got {call_count}"


# ---------------------------------------------------------------------------
# (e) Byte-for-byte determinism across two renders of the same input.
# ---------------------------------------------------------------------------


def test_rendering_the_same_input_twice_is_byte_for_byte_identical(tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    _write_record(
        cycles_dir,
        "system-a",
        "cycle-1",
        _record(
            system="system-a",
            cycle_id="cycle-1",
            dispatches=[_dispatch(label="a"), _dispatch(label="b", agent_type="verifier")],
            findings=[_finding(finding_id="f1"), _finding(finding_id="f2", verifier_verdict="REFUTED")],
        ),
    )
    _write_record(
        cycles_dir,
        "system-b",
        "cycle-2",
        _record(system="system-b", cycle_id="cycle-2"),
    )

    records1, issues1 = r.load_cycle_records(cycles_dir)
    doc1 = r.render_document(records1, issues1, cycles_dir)
    records2, issues2 = r.load_cycle_records(cycles_dir)
    doc2 = r.render_document(records2, issues2, cycles_dir)

    assert doc1 == doc2


def test_main_writes_byte_for_byte_identical_output_across_two_runs(tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "test-loop", "cycle-001", _record())
    out1 = tmp_path / "out1.html"
    out2 = tmp_path / "out2.html"

    rc1 = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out1)])
    rc2 = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out2)])

    assert rc1 == 0 and rc2 == 0
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ROUND 6 -- BLOCKER 1: normalize_record's "Never raises" contract broken by
# an unhashable schema_version; BLOCKER 2: the systematic `X or []`
# truthiness bug across every render_* table function; BLOCKER 6b: a
# prior-round fix with zero test coverage; BLOCKER 9: the "exits 0 always"
# contract broken on an unwritable output path; BLOCKER 12: docstring is
# tested only implicitly (a doc change, not a behavior change -- no test
# needed beyond what already exercises v2 schema support elsewhere in this
# file).
# ---------------------------------------------------------------------------


def test_normalize_record_never_raises_on_an_unhashable_schema_version() -> None:
    """BLOCKER 1 (round 6): `schema_version not in SCHEMA_VERSIONS_SUPPORTED`
    does a hash lookup -- an unhashable schema_version (a dict or list) used
    to raise TypeError: unhashable type, breaking this function's own
    'Never raises' docstring promise."""
    for bad_schema_version in [{"v": 2}, [1, 2], {1, 2}]:
        out, system, cycle_id, notes = r.normalize_record(
            {"schema_version": bad_schema_version, "system": "loop", "cycle_id": "c1"},
            "x.json",
            "loop",
        )
        assert any("schema_version" in n for n in notes)


def test_load_cycle_records_isolates_a_bad_file_next_to_a_good_one_from_a_different_system(
    tmp_path: Path,
) -> None:
    """Full repro from the review: a good record from system 'other' sits
    alongside a bad record (unhashable schema_version) -- before this
    round's fix, the WHOLE report blanked (both systems lost) and the bad
    file wasn't even listed as excluded. Confirm the good system's data
    survives; the bad record survives too (schema_version is a soft
    quality-note per this function's existing, unchanged policy for an
    unsupported-but-parseable schema_version -- see normalize_record's own
    comment), and it visibly carries that note rather than being silently
    dropped with no trace."""
    cycles_dir = tmp_path / "cycles"
    other_dir = cycles_dir / "other"
    other_dir.mkdir(parents=True)
    (other_dir / "good.json").write_text(
        json.dumps(_record(system="other", cycle_id="good-1")), encoding="utf-8"
    )
    (other_dir / "bad.json").write_text(
        json.dumps({"schema_version": {"v": 2}, "system": "other", "cycle_id": "bad-1"}),
        encoding="utf-8",
    )

    records, issues = r.load_cycle_records(cycles_dir)  # must not raise
    by_id = {rec.cycle_id: rec for rec in records}
    assert set(by_id) == {"good-1", "bad-1"}
    assert by_id["good-1"].quality_notes == ()
    assert any("schema_version" in n for n in by_id["bad-1"].quality_notes)
    assert issues == []

    # The full main() pipeline reflects the same survival, not a blank page.
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    written = out_path.read_text(encoding="utf-8")
    assert "cycle log failed to render" not in written.lower()
    assert "good-1" in written
    assert "bad-1" in written


def test_load_cycle_records_isolates_a_deeply_nested_json_file_that_raises_recursionerror(
    tmp_path: Path,
) -> None:
    """Round 12, BLOCKER 2: `load_cycle_records`'s per-file JSON-parse guard
    used to catch only `except ValueError` -- narrower than its structural
    twin `ct.read_cycles` (`hooks/cycle_telemetry.py`), which correctly
    catches `except Exception`. A JSON file nested ~10,000+ levels deep
    makes `json.loads` raise `RecursionError`, which is NOT a `ValueError`
    -- it escaped this guard entirely, propagated up through main()'s
    outer safety net, and blanked the WHOLE multi-system report (the
    clean record from a completely different system was lost too, with no
    per-file LoadIssue to explain why -- "0 loaded, 0 excluded"). This is
    the exact "structural twin has the weaker guard" shape round 10
    already fixed once for `list_systems` vs `iter_cycle_paths` -- a new
    instance of the same failure class."""
    cycles_dir = tmp_path / "cycles"
    deep_dir = cycles_dir / "deep-system"
    deep_dir.mkdir(parents=True)
    nested = "0"
    for _ in range(20000):
        nested = "[" + nested + "]"
    (deep_dir / "deep.json").write_text(nested, encoding="utf-8")

    clean_dir = cycles_dir / "clean-system"
    clean_dir.mkdir(parents=True)
    clean_record = _record(system="clean-system", cycle_id="clean-1")
    (clean_dir / "clean.json").write_text(json.dumps(clean_record), encoding="utf-8")

    records, issues = r.load_cycle_records(cycles_dir)  # must not raise
    assert len(records) == 1
    assert records[0].system == "clean-system"
    assert len(issues) == 1
    assert "deep.json" in issues[0].path

    # The full main() pipeline reflects the same isolation, not a
    # whole-report blank-out.
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    written = out_path.read_text(encoding="utf-8")
    assert "cycle log failed to render" not in written.lower()
    assert "clean-system" in written


def test_load_cycle_records_isolates_a_normalize_record_exception_as_a_load_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defense-in-depth: load_cycle_records() wraps its normalize_record()
    call so that if some FUTURE edit to normalize_record ever reintroduces
    a crash on a different malformed field, one bad file still degrades to
    a per-file LoadIssue rather than blanking the whole report -- this is
    the safety net BEHIND blocker 1's root-cause fix, not a substitute for
    it (the root cause is fixed and tested above; this proves the net
    exists too)."""
    cycles_dir = tmp_path / "cycles"
    other_dir = cycles_dir / "other"
    other_dir.mkdir(parents=True)
    (other_dir / "good.json").write_text(
        json.dumps(_record(system="other", cycle_id="good-1")), encoding="utf-8"
    )
    (other_dir / "bad.json").write_text(
        json.dumps(_record(system="other", cycle_id="bad-1")), encoding="utf-8"
    )

    real_normalize = r.normalize_record

    def _boom(raw, path, dir_system):
        if "bad.json" in path:
            raise RuntimeError("simulated future regression")
        return real_normalize(raw, path, dir_system)

    monkeypatch.setattr(r, "normalize_record", _boom)
    records, issues = r.load_cycle_records(cycles_dir)  # must not raise
    assert {rec.cycle_id for rec in records} == {"good-1"}
    assert len(issues) == 1
    assert "bad.json" in issues[0].path
    assert "simulated future regression" in issues[0].reason


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores directory permission bits; chmod 0o000 would not actually block access",
)
def test_discover_cycle_files_reports_an_unreadable_system_directory_as_a_load_issue(
    tmp_path: Path,
) -> None:
    """Round 12, BLOCKER 3: `discover_cycle_files`'s prior docstring argued
    that a `PermissionError` from `Path.glob()` on an unreadable
    subdirectory would escape to main()'s outer safety net and show the
    operator a real permissions problem. That premise is FALSE on this
    Python version -- `Path.glob()` does not raise on an unreadable
    subdirectory at all, it silently SKIPS it. Repro: chmod one system's
    directory to 0o000 -- before this fix, that system's data vanished
    with zero trace and the provenance line ("N loaded, K excluded") still
    read as a complete, honest accounting. This test confirms the
    unreadable system now surfaces as a visible LoadIssue instead."""
    cycles_dir = tmp_path / "cycles"
    readable_dir = cycles_dir / "sysReadable"
    readable_dir.mkdir(parents=True)
    (readable_dir / "r1.json").write_text(
        json.dumps(_record(system="sysReadable", cycle_id="r1")), encoding="utf-8"
    )
    blocked_dir = cycles_dir / "sysBlocked"
    blocked_dir.mkdir(parents=True)
    (blocked_dir / "b1.json").write_text(
        json.dumps(_record(system="sysBlocked", cycle_id="b1")), encoding="utf-8"
    )
    os.chmod(blocked_dir, 0o000)
    try:
        records, issues = r.load_cycle_records(cycles_dir)  # must not raise
        assert {rec.system for rec in records} == {"sysReadable"}
        assert len(issues) == 1
        assert "sysBlocked" in issues[0].path
        assert "not readable" in issues[0].reason.lower()

        # The full main() pipeline reflects the same visibility, not a
        # silent, trace-free omission.
        out_path = tmp_path / "out.html"
        rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
        assert rc == 0
        written = out_path.read_text(encoding="utf-8")
        assert "cycle log failed to render" not in written.lower()
        assert "sysReadable" in written
        assert "sysBlocked" in written  # visible as an excluded/issue entry, not silently gone
    finally:
        os.chmod(blocked_dir, 0o755)  # restore so tmp_path cleanup can remove it


def test_render_dispatch_summary_sort_key_excludes_bool_batch_position() -> None:
    """Round 12, nit #8: `render_dispatch_summary`'s sort key used to do its
    own inline `isinstance(d.get("batch_position"), (int, float))` check
    instead of routing through this codebase's shared finiteness helper
    (`_is_number`) the way its sibling `_review_sort_key` already does for
    `round` -- and `bool` is an `int` subclass in Python, so that inline
    check silently ADMITTED a `bool` value as a real batch_position (sorted
    as 0/1), unlike `_review_sort_key`, which correctly excludes `bool`.
    This never crashed (a bool sorts fine as an int), but it is observably
    the WRONG sort position: a dispatch with `batch_position: True` used to
    sort as if it were position 1, ahead of a dispatch that explicitly
    recorded position 0 -- after this fix it is treated as missing
    (falls back to 0) and ties with the real position-0 dispatch, broken
    by label, exactly matching how every other malformed-scalar field in
    this module is treated."""
    dispatches = [
        _dispatch(label="AAA", batch_position=True),  # malformed: bool, not a real position
        _dispatch(label="BBB", batch_position=0),
        _dispatch(label="CCC", batch_position=2),
    ]
    html_out = r.render_dispatch_summary(dispatches)
    # Fixed behavior: "AAA" (bool, excluded -> falls back to 0) ties with
    # "BBB" (real 0) and wins the tie-break alphabetically, so it renders
    # BEFORE "BBB" -- the buggy inline-isinstance version would have sorted
    # "BBB" (real key 0) before "AAA" (bool admitted as key 1).
    assert html_out.index("AAA") < html_out.index("BBB") < html_out.index("CCC")


# ---------------------------------------------------------------------------
# BLOCKER 2 -- the systematic `X or []` truthiness bug across every render_*
# table function that reads a per-item array field. Each field is tested
# with a representative set of malformed scalar values (mirroring the
# review's own 882-case directed fuzz at a reasonable, targeted scale).
# ---------------------------------------------------------------------------

_MALFORMED_ARRAY_VALUES = [3, 3.5, "abcdef", True]
_MALFORMED_ARRAY_IDS = ["int", "float", "str", "bool"]


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_findings_table_never_crashes_on_malformed_raised_by(bad: object) -> None:
    r.render_findings_table([{"finding_id": "f1", "raised_by": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_findings_table_never_crashes_on_malformed_issue_refs(bad: object) -> None:
    r.render_findings_table([{"finding_id": "f1", "issue_refs": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_runs_table_never_crashes_on_malformed_agent_types(bad: object) -> None:
    r.render_runs_table([{"run_id": "r1", "agent_types": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_reviews_table_never_crashes_on_malformed_related_findings(bad: object) -> None:
    r.render_reviews_table([{"review_id": "rv1", "related_findings": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_reviews_table_never_crashes_on_malformed_nested_findings(bad: object) -> None:
    r.render_reviews_table([{"review_id": "rv1", "findings": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_reviews_table_never_crashes_on_malformed_upheld_decisions(bad: object) -> None:
    r.render_reviews_table([{"review_id": "rv1", "upheld_decisions": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_reviews_table_never_crashes_on_malformed_overturned_decisions(bad: object) -> None:
    r.render_reviews_table([{"review_id": "rv1", "overturned_decisions": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_changes_table_never_crashes_on_malformed_files(bad: object) -> None:
    r.render_changes_table([{"change_id": "c1", "files": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_changes_table_never_crashes_on_malformed_tests_added(bad: object) -> None:
    r.render_changes_table([{"change_id": "c1", "tests_added": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_decisions_table_never_crashes_on_malformed_supersedes(bad: object) -> None:
    r.render_decisions_table([{"decision_id": "d1", "supersedes": bad}])  # must not raise


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_render_issues_filed_table_never_crashes_on_malformed_related_findings(bad: object) -> None:
    r.render_issues_filed_table([{"issue_id": "i1", "related_findings": bad}])  # must not raise


@pytest.mark.parametrize("bad_dispatches", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_dispatch_reported_tokens_never_crashes_on_malformed_dispatches_container(
    tmp_path: Path, bad_dispatches: object
) -> None:
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "loop", "c1", _record(system="loop", cycle_id="c1", dispatches=bad_dispatches))
    records, _issues = r.load_cycle_records(cycles_dir)
    assert r.dispatch_reported_tokens(records) is None


@pytest.mark.parametrize("bad", _MALFORMED_ARRAY_VALUES, ids=_MALFORMED_ARRAY_IDS)
def test_all_findings_never_crashes_on_malformed_findings_container(bad: object, tmp_path: Path) -> None:
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "loop", "c1", _record(system="loop", cycle_id="c1", findings=bad))
    records, _issues = r.load_cycle_records(cycles_dir)
    assert r.all_findings(records) == []


def test_render_cycle_details_survives_every_v2_array_being_malformed(tmp_path: Path) -> None:
    """End-to-end: a record whose v2 arrays are ALL malformed scalars must
    still render as one cycle's nested <details>, not crash the whole
    document."""
    cycles_dir = tmp_path / "cycles"
    bad_record = _record(
        system="loop",
        cycle_id="c1",
        findings=3.5,
        dispatches="abc",
        notes=True,
        runs=3,
        reviews=3.5,
        changes="abc",
        decisions=True,
        issues_filed=3,
        evidence=3.5,
        corrections="abc",
        verdicts=True,
        stages=3,
    )
    _write_record(cycles_dir, "loop", "c1", bad_record)
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])  # must not raise
    assert rc == 0
    written = out_path.read_text(encoding="utf-8")
    assert "cycle log failed to render" not in written.lower()
    assert "c1" in written


# ---------------------------------------------------------------------------
# BLOCKER 6b -- normalize_record()'s calibration coercion (round 4,
# justified as "every downstream caller benefits") had ZERO test coverage
# until this round.
# ---------------------------------------------------------------------------


def test_normalize_record_coerces_malformed_calibration_caught_by_and_missed_by() -> None:
    raw = {
        "schema_version": 1,
        "calibration": {"plant_id": "p1", "caught_by": "abc", "missed_by": 5},
    }
    out, _system, _cycle_id, notes = r.normalize_record(raw, "x.json", "loop")
    assert out["calibration"]["caught_by"] == []
    assert out["calibration"]["missed_by"] == []
    assert any("caught_by" in n for n in notes)
    assert any("missed_by" in n for n in notes)


# ---------------------------------------------------------------------------
# undispatched_verdict_rows (round-25 structural-conflict fix, 2026-09-07):
# an OBJECT-shaped optional top-level key, coerced by its own dedicated
# block in normalize_record() (mirroring the `cost` block directly above
# it), never by the generic V2_LIST_FIELDS loop.
# ---------------------------------------------------------------------------


def test_normalize_record_keeps_a_well_formed_undispatched_verdict_rows() -> None:
    raw = {
        "schema_version": 2,
        "undispatched_verdict_rows": {"count": 29, "by_judge": {"gc": 29}},
    }
    out, _system, _cycle_id, notes = r.normalize_record(raw, "x.json", "loop")
    assert out["undispatched_verdict_rows"] == {"count": 29, "by_judge": {"gc": 29}}
    assert not any("undispatched_verdict_rows" in n for n in notes)


def test_normalize_record_ignores_a_non_object_undispatched_verdict_rows() -> None:
    raw = {"schema_version": 2, "undispatched_verdict_rows": ["not", "an", "object"]}
    out, _system, _cycle_id, notes = r.normalize_record(raw, "x.json", "loop")
    assert out["undispatched_verdict_rows"] is None
    assert any("'undispatched_verdict_rows' was not an object" in n for n in notes)


def test_normalize_record_defaults_undispatched_verdict_rows_to_none_when_absent() -> None:
    raw = {"schema_version": 1}
    out, _system, _cycle_id, notes = r.normalize_record(raw, "x.json", "loop")
    assert out["undispatched_verdict_rows"] is None
    assert not any("undispatched_verdict_rows" in n for n in notes)


# ---------------------------------------------------------------------------
# BLOCKER 9 -- the "exits 0 always" contract must hold even when the OUTPUT
# path itself is unwritable (mkdir/write_text used to sit outside the try
# block a prior round added for the load+render pipeline).
# ---------------------------------------------------------------------------


def test_main_returns_0_and_reports_to_stderr_when_output_path_is_unwritable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cycles_dir = tmp_path / "cycles"
    cycles_dir.mkdir()
    # Create a FILE where the output's parent directory needs to go, so
    # `out_path.parent.mkdir(parents=True)` fails with a real OSError.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file")
    out_path = blocker / "out.html"

    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])  # must not raise

    assert rc == 0
    err = capsys.readouterr().err
    assert "could not write" in err


# ---------------------------------------------------------------------------
# ROUND 8 -- meta-pattern: "fixed on one side, never swept the mirror."
# Round 6's finiteness fix landed only in cycle_telemetry.py's own _is_number;
# this file's SEPARATE _is_number and its rollup_cost()'s two inline
# isinstance checks were never guarded, so a NaN/Infinity total_usd rendered
# as a confident "$inf ... ground truth" figure on the operator page.
# ---------------------------------------------------------------------------


def test_is_number_delegates_to_the_one_shared_cycle_telemetry_implementation() -> None:
    """Round 8: this file's own `_is_number` is no longer a second, separate
    implementation -- it calls cycle_telemetry.is_finite_number() directly,
    so the two files' number-checking logic can never drift apart on the
    finiteness axis again."""
    assert r._is_number(float("nan")) is False
    assert r._is_number(float("inf")) is False
    assert r._is_number(float("-inf")) is False
    assert r._is_number(1.5) is True
    assert r._is_number(True) is False


def test_fmt_usd_never_renders_a_confident_dollar_figure_for_infinity() -> None:
    """The reviewer's exact repro: a cycle record with total_usd: Infinity
    used to render 'total priced cost: $inf' labeled 'ground truth' on the
    operator page. fmt_usd must never render a bare '$inf'/'$nan' string."""
    for bad in (float("inf"), float("-inf"), float("nan")):
        rendered = r.fmt_usd(bad)
        assert rendered not in ("$inf", "$-inf", "$nan"), f"{bad!r} rendered as {rendered!r}"
        assert rendered == "invalid data"


def test_render_document_survives_an_infinite_total_usd_cost_record(tmp_path: Path) -> None:
    """End-to-end repro through the real load+render pipeline: a cycle
    record with cost.total_usd: Infinity must never surface a confident
    '$inf' figure anywhere in the rendered operator page. Given this
    round's load_cycle_records() parse-boundary fix, the file is now
    rejected as invalid JSON at load time (a LoadIssue, isolated from every
    other system's data) rather than loaded with a non-finite value that a
    downstream formatter must then separately catch -- either way, the
    operator page must never show a confident "$inf" figure."""
    cycles_dir = tmp_path / "cycles"
    record = _record(cost={"source": "spend_ledger", "total_tokens": 1000, "total_usd": float("inf")})
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert len(issues) == 1
    assert "invalid JSON" in issues[0].reason
    doc = r.render_document(records, issues, cycles_dir)  # must not raise
    assert "$inf" not in doc.lower()
    # The LoadIssue's own error TEXT honestly names "infinity" as the
    # rejected constant -- that's a correct, non-fabricated diagnostic, not
    # a confident dollar figure. Assert no dollar-prefixed rendering of it.
    assert "$-inf" not in doc.lower()


def test_load_cycle_records_rejects_a_bare_infinity_json_constant(tmp_path: Path) -> None:
    """Repro: a cycle file's top-level JSON carries a bare `Infinity` token
    (valid to Python's json module, invalid JSON) at total_usd. Round 6's
    parse_constant guard was applied only to cycle_telemetry.py's own
    read_ledger_rows() -- this file's SEPARATE `load_cycle_records`
    `json.loads(text)` call had no guard at all, so this parsed cleanly
    into a non-finite float that only fmt_usd's OWN guard (fixed above)
    happened to catch downstream. Reject it at the parse boundary instead,
    the same as every other malformed file, isolated as a per-file
    LoadIssue rather than a silently-accepted non-finite value."""
    cycles_dir = tmp_path / "cycles"
    bad_dir = cycles_dir / "loop"
    bad_dir.mkdir(parents=True)
    (bad_dir / "x.json").write_text(
        '{"schema_version": 1, "system": "loop", "cycle_id": "x", '
        '"started_at": "2026-08-27T14:00:00Z", "ended_at": "2026-08-27T15:00:00Z", '
        '"dispatches": [], "calibration": {"plant_id": null, "planted_in": null, '
        '"slot": null, "caught_by": [], "missed_by": []}, "findings": [], '
        '"cost": {"source": "spend_ledger", "total_tokens": 1000, "total_usd": Infinity}, '
        '"notes": []}',
        encoding="utf-8",
    )
    good_dir = cycles_dir / "other"
    good_dir.mkdir(parents=True)
    _write_record(cycles_dir, "other", "y", _record(system="other", cycle_id="y"))

    records, issues = r.load_cycle_records(cycles_dir)  # must not raise
    assert len(records) == 1
    assert records[0].system == "other"
    assert len(issues) == 1
    assert "x.json" in issues[0].path
    assert "invalid JSON" in issues[0].reason


def test_rollup_cost_never_counts_a_non_finite_total_usd_as_priced() -> None:
    """Repro against rollup_cost()'s own two inline isinstance checks
    directly (as opposed to through fmt_usd, covered above) -- a
    spend_ledger-sourced record with total_usd: Infinity used to be counted
    as `n_ledger_priced` and summed straight into the rollup's total_usd,
    fabricating a confident "$inf" pooled figure even though every
    downstream formatter was already guarded."""
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"cost": {"source": "spend_ledger", "total_usd": float("inf"), "total_tokens": 100}},
        quality_notes=(),
    )
    rollup = r.rollup_cost([rec])
    assert rollup.total_usd is None
    assert rollup.n_ledger_priced == 0
    assert rollup.n_ledger_unpriced == 1


def test_rollup_cost_never_counts_a_non_finite_total_tokens() -> None:
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"cost": {"source": "spend_ledger", "total_usd": 1.0, "total_tokens": float("nan")}},
        quality_notes=(),
    )
    rollup = r.rollup_cost([rec])
    assert rollup.total_tokens is None


def test_rollup_cost_withholds_the_pooled_total_if_the_accumulated_sum_overflows() -> None:
    """Defense-in-depth mirror of resolve_cost()'s own cross-row
    accumulation guard: each individual record's total_usd is finite on its
    own, but summing many of them across the whole rollup overflows to
    +inf -- never surface that as a confident pooled figure either."""
    records = [
        r.CycleRecord(
            path=f"x{i}.json",
            system="loop",
            cycle_id=f"c{i}",
            raw={"cost": {"source": "spend_ledger", "total_usd": 1.6e308, "total_tokens": 100}},
            quality_notes=(),
        )
        for i in range(2)
    ]
    rollup = r.rollup_cost(records)
    assert rollup.total_usd is None


# ---------------------------------------------------------------------------
# Round 10.
# ---------------------------------------------------------------------------

# --- BLOCKER 2: render_reviews_table's own sort key must be type-safe,
# the identical hazard shape round 8 already fixed on read_cycles()'s sort
# key (BLOCKER 3 there).


def test_render_reviews_table_survives_a_mixed_int_and_string_round() -> None:
    """Exact repro: one record's reviews list has a real int round (1) and
    a malformed string round ("two"). The OLD `r.get("round") or 0` sort
    key crashed `sorted()` with a str-vs-int TypeError the instant these
    two sat next to each other -- must now render both rows instead."""
    reviews = [{"review_id": "rv1", "round": 1}, {"review_id": "rv1", "round": "two"}]
    out = r.render_reviews_table(reviews)  # must not raise
    assert "rv1" in out


def test_render_reviews_table_sort_key_treats_a_bool_round_as_zero() -> None:
    """bool is an int subclass -- the sort key must not accidentally treat
    True/False as meaningful round numbers (round 1 vs round True should
    not silently collide)."""
    key = r._review_sort_key({"review_id": "rv1", "round": True})
    assert key == ("rv1", 0)


def test_main_does_not_blank_the_whole_report_when_one_records_reviews_are_malformed(
    tmp_path: Path,
) -> None:
    """End-to-end falsification of the reviewer's exact scenario: a record
    in sysA has a reviews list with mixed int/string round values. Before
    the fix, this crashed render_document() entirely, and main()'s outer
    except handler replaced the WHOLE report -- including a perfectly good
    record from the completely unrelated sysB -- with the generic error
    page. After the fix, both systems' data must still render."""
    cycles_dir = tmp_path / "cycles"
    _write_record(
        cycles_dir,
        "sysA",
        "c1",
        _record(
            system="sysA",
            cycle_id="c1",
            reviews=[{"review_id": "rv1", "round": 1}, {"review_id": "rv1", "round": "two"}],
        ),
    )
    _write_record(cycles_dir, "sysB", "c1", _record(system="sysB", cycle_id="c1"))
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    html_doc = out_path.read_text(encoding="utf-8")
    assert "render error" not in html_doc.lower()
    assert "sysA" in html_doc
    assert "sysB" in html_doc


# --- Finding #8: dispatch_reported_tokens must route its per-item check
# through the shared is_finite_number helper and guard its own accumulated
# sum; fmt_int_or_dash must never print the literal 'inf'/'nan'.


def test_dispatch_reported_tokens_excludes_a_non_finite_tokens_total() -> None:
    """Constructs CycleRecord directly (like
    test_rollup_cost_never_counts_a_non_finite_total_tokens above) rather
    than round-tripping through a written file -- a bare `Infinity` value
    can never survive load_cycle_records()'s own parse boundary (BLOCKER 4)
    to reach here in normal operation, but dispatch_reported_tokens() must
    still be correct in isolation as a matter of defense in depth, the same
    reasoning rollup_cost's sibling test already applies."""
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"dispatches": [{"tokens_total": float("inf")}, {"tokens_total": 500}]},
        quality_notes=(),
    )
    # A non-finite per-item value must never be summed as if it were real --
    # the honest total counts only the real (finite) contribution.
    assert r.dispatch_reported_tokens([rec]) == 500


def test_dispatch_reported_tokens_withholds_the_total_if_the_accumulated_sum_overflows() -> None:
    """The 3rd un-consolidated accumulator in this file (rollup_cost and
    aggregate_metrics both already got this guard): every individual
    tokens_total is finite on its own, but summing many overflows to +inf."""
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"dispatches": [{"tokens_total": 1e308}, {"tokens_total": 1e308}]},
        quality_notes=(),
    )
    assert r.dispatch_reported_tokens([rec]) is None


def test_fmt_int_or_dash_never_prints_the_literal_inf_or_nan() -> None:
    assert r.fmt_int_or_dash(float("inf")) == "invalid data"
    assert r.fmt_int_or_dash(float("nan")) == "invalid data"
    assert r.fmt_int_or_dash(float("-inf")) == "invalid data"
    assert r.fmt_int_or_dash(5) == "5"
    assert r.fmt_int_or_dash(5.0) == "5"
    assert r.fmt_int_or_dash(None) == "—"
    assert r.fmt_int_or_dash("not a number") == "—"
    assert r.fmt_int_or_dash(True) == "—"  # bool never reads as a real int/float count


# ---------------------------------------------------------------------------
# Round 14, BLOCKER 1: is_finite_number() (imported from cycle_telemetry as
# `ct.is_finite_number`, delegated to by this file's own `_is_number`) must
# reject an int too large to survive a finite float conversion
# (OverflowError) -- schema-valid today, and every `float(x)`-converting
# formatter/accumulator in THIS file inherits the same crash unless the one
# shared upstream check is fixed.
# ---------------------------------------------------------------------------

_HUGE_INT = 10**309  # 310 digits; float(_HUGE_INT) raises OverflowError
_LARGE_BUT_FINITE_INT = 10**300  # float() of this is a large but finite float -- mirrors test_cycle_telemetry.py's own constant of the same name/value


def test_is_number_rejects_an_int_too_large_for_a_finite_float() -> None:
    assert r._is_number(_HUGE_INT) is False
    assert ct.is_finite_number(_HUGE_INT) is False


def test_fmt_usd_never_crashes_on_a_too_large_total() -> None:
    assert r.fmt_usd(_HUGE_INT) == "invalid data"


def test_fmt_tokens_never_crashes_on_a_too_large_total() -> None:
    assert r.fmt_tokens(_HUGE_INT) == "invalid data"


def test_fmt_pct_never_crashes_on_a_too_large_value() -> None:
    assert r.fmt_pct(_HUGE_INT) == "invalid data"


def test_fmt_ratio_never_crashes_on_a_too_large_value() -> None:
    assert r.fmt_ratio(_HUGE_INT) == "invalid data"


def test_fmt_int_or_dash_now_treats_a_too_large_int_as_invalid_data() -> None:
    """DECISION (round 14, reviewer's point (a)): before the is_finite_number
    fix, fmt_int_or_dash rendered a too-large int CORRECTLY as a big comma-
    formatted number, because it never converts to float (`f"{value:,}"` on
    an int never overflows). The fix flips this specific case to "invalid
    data", the same placeholder every other formatter in this file already
    uses for a value it cannot safely process. This is the intended,
    deliberate tradeoff: a value nothing else in the system can process
    (validate_cycle now refuses it at write time too, see
    test_cycle_telemetry.py's round-14 write-time tests) should not get a
    bespoke "safe" rendering path here just because THIS one formatter
    happens not to need a float conversion for smaller ints."""
    assert r.fmt_int_or_dash(_HUGE_INT) == "invalid data"


def test_fmt_int_or_dash_still_renders_a_large_but_finite_int_normally() -> None:
    """Paired positive to the overflow test above (round 16, finding 3): the
    round-14 guard must reject OVERFLOW specifically, not mere size -- a
    large-but-finite int (well under is_finite_number's rejection
    threshold) must still render as a real, comma-formatted number, never
    'invalid data'. Without this, nothing pins that a legitimate large
    tokens_total/tool_calls count doesn't get swept into the same
    'invalid data' bucket as a genuinely broken value."""
    assert ct.is_finite_number(_LARGE_BUT_FINITE_INT) is True  # sanity: not the overflow case
    assert r.fmt_int_or_dash(_LARGE_BUT_FINITE_INT) == f"{_LARGE_BUT_FINITE_INT:,}"


def test_rollup_cost_never_crashes_on_a_too_large_total_usd() -> None:
    """Repro: cost.total_usd=10**309 used to pass `usd_is_number` (via
    `_is_number`/`is_finite_number`) unconditionally, then `total_usd +=
    float(usd)` raised OverflowError."""
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"cost": {"source": "spend_ledger", "total_usd": _HUGE_INT, "total_tokens": 100}},
        quality_notes=(),
    )
    rollup = r.rollup_cost([rec])  # must not raise
    assert rollup.total_usd is None
    assert rollup.n_ledger_priced == 0
    assert rollup.n_ledger_unpriced == 1


def test_rollup_cost_never_crashes_on_a_too_large_total_tokens() -> None:
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"cost": {"source": "spend_ledger", "total_usd": 1.0, "total_tokens": _HUGE_INT}},
        quality_notes=(),
    )
    rollup = r.rollup_cost([rec])  # must not raise
    assert rollup.total_tokens is None


def test_dispatch_reported_tokens_never_crashes_on_a_too_large_tokens_total() -> None:
    """Repro: dispatches[].tokens_total=10**309 used to pass
    `ct.is_finite_number(t)` unconditionally, then `total += float(t)`
    raised OverflowError."""
    rec = r.CycleRecord(
        path="x.json",
        system="loop",
        cycle_id="c1",
        raw={"dispatches": [{"tokens_total": _HUGE_INT}, {"tokens_total": 500}]},
        quality_notes=(),
    )
    assert r.dispatch_reported_tokens([rec]) == 500  # must not raise


def test_falsifiability_render_huge_int_guard() -> None:
    """Per CLAUDE.md's falsifiability rule: reproduce the pre-fix upstream
    check directly (no int-overflow guard) and confirm it really did let
    the huge int through as "a number", which is what every formatter/
    accumulator above relied on to avoid the float() conversion crash.

    Note (round 16, finding 5): `pre_fix_is_number` is an ILLUSTRATIVE
    stand-in for the pre-fix code, not a literal revert-and-rerun of the
    real module -- only the GREEN assertion below exercises the shipped
    `r._is_number`. Documentary, not a true revert proof."""

    def pre_fix_is_number(x: object) -> bool:
        if isinstance(x, bool):
            return False
        if isinstance(x, int):
            return True  # the round-14 bug
        if isinstance(x, float):
            return math.isfinite(x)
        return False

    assert pre_fix_is_number(_HUGE_INT) is True  # RED: pre-fix behavior
    assert r._is_number(_HUGE_INT) is False  # GREEN: shipped behavior


def test_main_does_not_blank_the_whole_report_when_one_records_total_usd_is_too_large(
    tmp_path: Path,
) -> None:
    """End-to-end falsification via the REAL CLI entry point (main()), not
    just a unit test of is_finite_number/_is_number alone: sysA's cost.total_usd
    is 10**309 (schema-valid JSON, loads cleanly -- json.loads has no digit
    limit anywhere near 310 digits). Before the fix, rendering sysA's cost
    provenance line crashed render_document() entirely, and main()'s outer
    except handler replaced the WHOLE report -- including sysB's perfectly
    good, completely unrelated data -- with the generic error page."""
    cycles_dir = tmp_path / "cycles"
    _write_record(
        cycles_dir,
        "sysA",
        "c1",
        _record(
            system="sysA",
            cycle_id="c1",
            cost={"source": "spend_ledger", "total_tokens": 100, "total_usd": _HUGE_INT},
        ),
    )
    _write_record(cycles_dir, "sysB", "c1", _record(system="sysB", cycle_id="c1"))
    out_path = tmp_path / "out.html"
    rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path)])
    assert rc == 0
    html_doc = out_path.read_text(encoding="utf-8")
    assert "render error" not in html_doc.lower()
    assert "sysA" in html_doc
    assert "sysB" in html_doc


# ---------------------------------------------------------------------------
# B1 (round-2 review, GH #4648) -- calibration_runs[] GRID rendering. Real,
# shipped defect: a valid record with real plant/control rows rendered the
# confidently false "No calibration plants seeded in this view," in the file
# whose own docstring calls MISSING IS NOT ZERO the rule that matters most.
# CORRECTED (round-3): round-2's comment here additionally blamed this on
# V2_LIST_FIELDS being stuck at nine entries -- FALSIFIED by round-3 review.
# normalize_record() does `out = dict(raw)` (a full shallow copy, no
# whitelisting), so calibration_runs was never stripped or hidden from
# ct.aggregate_metrics() regardless of V2_LIST_FIELDS membership. The actual
# root cause was Analysis/render_system_summary carrying NO grid wiring at
# all (no plant_catch_by_trade/false_alarm_by_trade fields, no grid-table
# branch) -- see render_system_summary's own fix. V2_LIST_FIELDS membership
# is still correct and still tested (test_v2_list_fields_matches_optional_top_keys
# below), but only for what it actually buys calibration_runs -- defensive
# list-coercion and the "ignored" quality note every other v2 array gets --
# never as the cause of this specific regression.
# ---------------------------------------------------------------------------


def _calibration_run(**overrides: object) -> dict:
    run: dict = {
        "plant_id": "PLANT_mut1_scn1",
        "trade": "tile",
        "slot": 1,
        "batch_size": 4,
        "caught_by": ["tile"],
        "missed_by": [],
        "false_alarm_finding_ids": [],
    }
    run.update(overrides)
    return run


def _control_run(**overrides: object) -> dict:
    run: dict = {
        "plant_id": None,
        "trade": "tile",
        "slot": 2,
        "batch_size": 4,
        "caught_by": [],
        "missed_by": [],
        "false_alarm_finding_ids": [],
    }
    run.update(overrides)
    return run


def _grid_table_body(doc: str) -> str:
    """Scope a substring assertion to the calibration_runs grid table's own
    <tbody> (round-3 review, item 8) -- a bare "1/2"/"50%" check against the
    WHOLE document can coincidentally match unrelated content elsewhere
    (trend-card values, other tables, sparkline labels), silently passing
    for the wrong reason. Raises (loudly, by design) if the grid table
    itself is absent."""
    start = doc.index("calibration_runs grid")
    tbody_start = doc.index("<tbody>", start) + len("<tbody>")
    tbody_end = doc.index("</tbody>", tbody_start)
    return doc[tbody_start:tbody_end]


def test_v2_list_fields_matches_optional_top_keys() -> None:
    """A fence, not a regression-repro: V2_LIST_FIELDS is a hand-maintained
    copy of the LIST-shaped members of ct.OPTIONAL_TOP_KEYS (normalize_record()
    coerces each of these array fields -- non-dict rows dropped, an "ignored"
    quality note added -- the same way). This does NOT reproduce the live B1
    "No calibration plants seeded" regression (that bug's actual cause was
    render_system_summary having no grid wiring at all, independent of this
    tuple -- see the section comment above and render_system_summary's own
    fix). This test exists purely to prevent FUTURE drift of the
    defensive-coercion behavior, never as evidence about what already
    shipped.

    round-25 structural-conflict fix (2026-09-07): `undispatched_verdict_rows`
    is an OBJECT-shaped optional top-level key (like `calibration`/`cost`,
    not a list), so it is deliberately excluded from V2_LIST_FIELDS and
    handled by its own dedicated object-coercion block in
    normalize_record() instead -- see r.V2_OBJECT_FIELDS. The real invariant
    is that EVERY optional top-level key is accounted for by one of the two
    coercion mechanisms, list or object."""
    assert set(r.V2_LIST_FIELDS) | set(r.V2_OBJECT_FIELDS) == set(ct.OPTIONAL_TOP_KEYS)
    # The two sets must also be disjoint -- a key claiming BOTH shapes would
    # be a real ambiguity, not a redundancy.
    assert not (set(r.V2_LIST_FIELDS) & set(r.V2_OBJECT_FIELDS))


def test_render_document_shows_the_grid_honestly_for_two_plants_and_a_control(
    tmp_path: Path,
) -> None:
    """THE B1 falsification target, end to end through the real CLI entry
    point: a record with 2 plants + 1 control in calibration_runs[] (and NO
    legacy `calibration` plant) must never render "No calibration plants
    seeded" -- it must render the honest per-trade grid table instead."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            _calibration_run(trade="tile", slot=1, caught_by=["tile"], missed_by=[]),
            _calibration_run(trade="tile", slot=2, caught_by=[], missed_by=["tile"]),
            _control_run(trade="tile", slot=3, false_alarm_finding_ids=["f-1"]),
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    assert "calibration_runs grid" in doc
    table = _grid_table_body(doc)  # item 8: scope numeric asserts to the table's own tbody
    assert "tile" in table
    # caught=1, missed=1, rate 50% -- from plant_catch_by_trade.
    assert "1/2" in table
    assert "50%" in table
    # controls=1, false_alarms=1 -- from false_alarm_by_trade.
    assert "1 / 1 controls" in table
    assert "100%" in table


def test_render_document_grid_and_legacy_calibration_coexist(tmp_path: Path) -> None:
    """A record can carry BOTH the legacy single `calibration` plant AND a
    calibration_runs grid -- neither table suppresses the other, and the
    "no plants seeded" fallback must not fire when either one has data."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration={
            "plant_id": "legacy-plant",
            "planted_in": "finder",
            "slot": "1",
            "caught_by": ["1"],
            "missed_by": [],
        },
        calibration_runs=[_calibration_run(trade="plumbing")],
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    assert "slot (dispatch batch position)" in doc  # legacy table still renders
    assert "calibration_runs grid" in doc  # grid table also renders
    assert "plumbing" in doc


def test_render_document_still_shows_no_plants_message_with_neither_source(
    tmp_path: Path,
) -> None:
    """The fallback message must still fire when BOTH the legacy calibration
    block and calibration_runs are genuinely empty -- B1's fix narrows the
    condition, it does not remove it."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "test-loop", "cycle-001", _record())
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)
    assert "No calibration plants seeded in this view" in doc


def test_render_document_shows_a_seeded_but_never_exercised_plant_honestly(
    tmp_path: Path,
) -> None:
    """BLOCKER 1 (round-3, GH #4648) falsification pair for
    test_calibration_run_plant_with_empty_catches_and_misses_is_valid
    (test_cycle_telemetry.py): a VALID record whose only calibration_runs
    row is a genuinely seeded plant that recorded zero catches/misses must
    still show up on the page -- as a real grid row for its trade, with an
    honest em-dash cell (no bucket exists for it in plant_catch_by_trade,
    per F4) -- never as a silently-vanished trade, and never the "No
    calibration plants seeded" fallback (which would be confidently wrong:
    a plant WAS seeded)."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[_calibration_run(trade="tile", caught_by=[], missed_by=[])]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    table = _grid_table_body(doc)
    assert "tile" in table
    assert "&mdash;" in table  # honest em-dash cell -- no bucket, never a fabricated 0/0


def test_render_document_grid_row_count_line_when_no_bucket_and_legacy_absent(
    tmp_path: Path,
) -> None:
    """Item 9, cell (legacy=0 / rows>0 / buckets=0): no legacy calibration
    plant, calibration_run_rows > 0, but BOTH aggregators produce zero
    buckets AND no trade name is even readable (trade itself is missing) --
    the F4 zero-signal path never touches a bucket regardless of trade
    readability, so calibration_run_trades also stays empty. Must render
    the honest row-count LINE (never a table with nothing to show, and
    never the "No calibration plants seeded" fallback, which would falsely
    claim nothing was seeded at all)."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            {
                "plant_id": "p1",
                "slot": 1,
                "batch_size": 1,
                "caught_by": [],
                "missed_by": [],
                "false_alarm_finding_ids": [],
                # no "trade" key at all -- unattributable, and F4 means this
                # plant row never touches ANY bucket (empty caught/missed).
            }
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    assert "calibration_runs grid" not in doc  # no table -- nothing to key rows on
    assert "1 calibration_runs row recorded" in doc
    assert "could be attributed to a trade" in doc


def test_render_document_grid_row_count_line_coexists_with_legacy_plant(
    tmp_path: Path,
) -> None:
    """Item 9, cell (legacy=1 / rows>0 / buckets=0): SAME zero-attributable
    grid as above, but WITH a real legacy `calibration` plant present too --
    the legacy per-slot table renders (legacy=1), and the grid's own honest
    row-count line renders alongside it, independently -- neither section
    suppresses or is suppressed by the other, and the "No calibration
    plants seeded" fallback never fires (there IS a legacy plant)."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration={
            "plant_id": "legacy-plant",
            "planted_in": "finder",
            "slot": "1",
            "caught_by": ["1"],
            "missed_by": [],
        },
        calibration_runs=[
            {
                "plant_id": "p1",
                "slot": 1,
                "batch_size": 1,
                "caught_by": [],
                "missed_by": [],
                "false_alarm_finding_ids": [],
            }
        ],
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    assert "slot (dispatch batch position)" in doc  # legacy table renders
    assert "calibration_runs grid" not in doc  # grid table itself absent (no attributable trade)
    assert "1 calibration_runs row recorded" in doc  # grid's honest line renders anyway


def test_render_document_grid_shows_mixed_readable_and_unreadable_signal(
    tmp_path: Path,
) -> None:
    """Item 3, end to end: a good, fully-readable plant row beside a
    SECOND row for the SAME trade whose plant_id is the wrong type (a real
    discriminator failure) -- the grid cell for that trade must show BOTH
    the real 1/1 catch ratio AND the unreadable count, never one hiding
    the other."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            {"plant_id": 42, "trade": "tile", "caught_by": ["tile"], "missed_by": []},
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)
    table = _grid_table_body(doc)

    assert "tile" in table
    assert "1/1" in table
    assert "100%" in table
    assert "1 unreadable" in table


def test_render_document_bad_trade_with_real_signal_renders_unattributable_row(
    tmp_path: Path,
) -> None:
    """Item 5: a control row with a genuinely bad `trade` (non-string) but
    REAL, readable false-alarm signal must render as its own
    "(unattributable)" table row carrying that real signal -- named
    distinctly from a zero-signal trade's honest em-dash row (the
    "(unattributable)" bucket is never confused with, or suppressed by,
    the "no bucket at all" em-dash case)."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            {"plant_id": None, "trade": 42, "false_alarm_finding_ids": ["f-1"]},
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)
    table = _grid_table_body(doc)

    assert "(unattributable)" in table
    assert "1 / 1 controls" in table
    assert "100%" in table


def test_fmt_catch_cell_direct() -> None:
    """Item 9, "the two empty-list cells": direct, isolated coverage of
    _fmt_catch_cell's boundary between "no bucket at all" (None -> em-dash),
    a genuinely clean/readable bucket (a real ratio, never suppressed), and
    an unreadable-only bucket (0/0 suppressed, unreadable count named)."""
    assert r._fmt_catch_cell(None) == "&mdash;"
    clean = r._fmt_catch_cell({"caught": 1, "missed": 1, "unreadable": 0, "rate": 0.5})
    assert "1/2" in clean and "50%" in clean
    unreadable_only = r._fmt_catch_cell({"caught": 0, "missed": 0, "unreadable": 2, "rate": None})
    assert "0/0" not in unreadable_only
    assert "2 unreadable" in unreadable_only
    # Item 3: the MIXED case -- real readable signal AND unreadable rows on
    # the SAME bucket (e.g. one clean plant row plus one row with a
    # malformed/discriminator-unreadable catch on the same trade). The real
    # ratio must render normally, with the unreadable count appended, never
    # suppressed (suppression is only for observed == 0).
    mixed = r._fmt_catch_cell({"caught": 1, "missed": 0, "unreadable": 1, "rate": 1.0})
    assert "1/1" in mixed
    assert "100%" in mixed
    assert "1 unreadable" in mixed


def test_fmt_alarm_cell_direct() -> None:
    """Item 9, "the two empty-list cells": the false_alarm_by_trade sibling
    -- critically, a REAL control bucket with a genuinely empty (but
    validly-typed) false_alarm_finding_ids list (controls=1, false_alarms=0)
    is a real, confident 0 and must NOT be suppressed -- only a
    zero-READABLE-controls bucket (controls=0) is."""
    assert r._fmt_alarm_cell(None) == "&mdash;"
    clean_zero = r._fmt_alarm_cell({"controls": 1, "false_alarms": 0, "unreadable": 0, "rate": 0.0})
    assert "0 / 1 controls" in clean_zero
    assert "0%" in clean_zero
    unreadable_only = r._fmt_alarm_cell({"controls": 0, "false_alarms": 0, "unreadable": 3, "rate": None})
    assert "0 / 0" not in unreadable_only
    assert "3 unreadable" in unreadable_only
    # Item 3: the MIXED case -- see test_fmt_catch_cell_direct's own note.
    mixed = r._fmt_alarm_cell({"controls": 1, "false_alarms": 1, "unreadable": 1, "rate": 1.0})
    assert "1 / 1 controls" in mixed
    assert "100%" in mixed
    assert "1 unreadable" in mixed


def test_analyze_exposes_plant_catch_by_trade_and_false_alarm_by_trade(tmp_path: Path) -> None:
    """Metric parity (mirrors the existing plant_catch_by_slot parity test
    above): analyze()'s new fields must equal ct.aggregate_metrics()'s own
    values for the same records, never a locally reimplemented copy."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            _calibration_run(trade="tile", caught_by=["tile"], missed_by=[]),
            _control_run(trade="tile", false_alarm_finding_ids=["f-1"]),
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    analysis = r.analyze(records)
    expected = ct.aggregate_metrics([record])
    assert analysis.plant_catch_by_trade == expected["plant_catch_by_trade"]
    assert analysis.false_alarm_by_trade == expected["false_alarm_by_trade"]


def test_render_document_surfaces_unreadable_grid_data_never_a_confident_zero(
    tmp_path: Path,
) -> None:
    """B2's posture must be visible end to end, not just at the library
    layer: a control row with a malformed false_alarm_finding_ids must
    render its `unreadable` count, never silently read as "0 controls, 0
    false alarms" the way the pre-B2 implementation did."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration_runs=[
            {
                "plant_id": None,
                "trade": "tile",
                "slot": 1,
                "batch_size": 1,
                "caught_by": [],
                "missed_by": [],
                "false_alarm_finding_ids": "not-a-list",
            }
        ]
    )
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)
    table = _grid_table_body(doc)
    # Round-3, item 7: assert the PROPERTY (unreadable surfaced, never a
    # confident-looking 0/0 fraction), not the exact wording -- _fmt_alarm_cell
    # now suppresses the "0 / 0 controls" fraction entirely when there are
    # zero READABLE controls, naming the unreadable count directly instead.
    assert "unreadable" in table
    assert "0 / 0" not in table


def test_render_document_legacy_plant_with_zero_calibration_run_rows(
    tmp_path: Path,
) -> None:
    """Item 4: a HERMETIC (fixture-built, no live/gitignored-file
    dependency) cover of "legacy plant present, calibration_run_rows == 0"
    -- until now this exact combination was only exercised by
    test_real_shipped_b0_records_still_render_without_the_grid_section,
    which pytest.skips whenever the two live B0 files aren't present (e.g.
    a fresh clone), leaving this combination uncovered in that run."""
    cycles_dir = tmp_path / "cycles"
    record = _record(
        calibration={
            "plant_id": "legacy-plant",
            "planted_in": "finder",
            "slot": "1",
            "caught_by": ["1"],
            "missed_by": [],
        }
    )
    assert "calibration_runs" not in record
    _write_record(cycles_dir, "test-loop", "cycle-001", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []

    doc = r.render_document(records, issues, cycles_dir)

    assert "No calibration plants seeded" not in doc
    assert "slot (dispatch batch position)" in doc  # legacy table renders
    assert "calibration_runs grid" not in doc  # grid section entirely absent


# ---------------------------------------------------------------------------
# Additivity re-verification (GH #4648): the two REAL shipped B0 records
# (v1-shaped, no calibration_runs at all) must render with the grid section
# entirely absent and their legacy per-slot table present, unaffected by
# calibration_runs existing. NOT a byte-identity claim across all records --
# this test's own two fixtures never reach the no-calibration fallback line
# (they carry legacy plant data), so it cannot and does not cover that
# line's own deliberate rewording. This is the renderer-side sibling of
# cycle_telemetry.py's own test_real_shipped_leaked_and_blind_records_still_validate.
# ---------------------------------------------------------------------------


def test_real_shipped_b0_records_still_render_without_the_grid_section(tmp_path: Path) -> None:
    """The two real B0 fixtures carry a legacy `calibration` plant (with
    real caught_by/missed_by) and NO calibration_runs -- confirms the grid
    section stays entirely absent for them (calibration_run_rows == 0 --
    see render_system_summary's additivity join) and the per-slot table
    (their actual data) still renders exactly as before.

    Round-3, item 15: narrowed to isolated COPIES of exactly the two named
    B0 files under tmp_path, never the live ~/.claude/telemetry/cycles/
    directory wholesale -- reading the real directory directly means this
    test's outcome depends on whatever else happens to exist there (now or
    in the future), which is exactly the kind of hidden, non-hermetic
    dependency this file's own module docstring says every test here must
    avoid."""
    real_cycles_dir = Path(ct.CYCLES_DIR)
    names = ("B0-2026-08-28-leaked", "B0-2026-08-28-blind")
    src_paths = [real_cycles_dir / "estimate-loop" / f"{n}.json" for n in names]
    if not all(p.exists() for p in src_paths):
        pytest.skip("real B0 cycle records not present in this $HOME")

    cycles_dir = tmp_path / "cycles"
    for name, src in zip(names, src_paths):
        record = json.loads(src.read_text(encoding="utf-8"))
        _write_record(cycles_dir, "estimate-loop", name, record)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    doc = r.render_document(records, issues, cycles_dir)
    assert "No calibration plants seeded" not in doc  # they DO have a legacy plant
    assert "calibration_runs grid" not in doc  # but never the new grid section
    assert "slot (dispatch batch position)" in doc  # the legacy per-slot table


# ---------------------------------------------------------------------------
# Redesign (2026-09): compact executive summary + nested collapsible
# <details> structure, replacing the always-flat, always-fully-rendered
# page. Each test below states, in its own docstring, the falsifiability
# check performed by hand against the PRE-redesign renderer (a real,
# untouched `git show HEAD:scripts/render_cycle_log.py` scratch copy from
# immediately before this change -- never the live module under test) --
# every one of these assertions was confirmed RED against that old
# renderer's own output before being confirmed GREEN here, per CLAUDE.md
# §6. The scratch-copy renders are not repeated inside this test file
# (they would require vendoring a second copy of the whole module into the
# test tree); this docstring records the manual verification instead, the
# same way test_falsifiability_render_huge_int_guard above documents an
# illustrative-not-literal pre-fix stand-in.
# ---------------------------------------------------------------------------


def test_executive_summary_renders_one_row_per_system_with_a_10_second_glance(tmp_path: Path) -> None:
    """The compact top-of-page table (design requirement 1): one row per
    system naming its latest cycle id/date and headline findings count.
    FALSIFIABILITY: the OLD renderer (pre-redesign scratch copy) has no
    such heading or table anywhere in its output at all -- RED there,
    GREEN here."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "cycle-1", _record(system="sysA", cycle_id="cycle-1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert "What happened, at a glance" in doc
    assert "exec-summary" in doc
    assert "sysA" in doc
    assert "cycle-1" in doc


def test_cost_headline_renders_exactly_unknown_source_unavailable_never_a_bare_number(
    tmp_path: Path,
) -> None:
    """Design requirement 1: cost with no priced data renders EXACTLY
    'UNKNOWN' plus '(source: unavailable)' -- never a number, never blank,
    never a bare '$0'. FALSIFIABILITY: the OLD renderer's cost line for
    this same unpriced record reads 'total priced cost: no cost data' --
    it never emits the literal string 'UNKNOWN' anywhere; confirmed absent
    there (RED) and present here (GREEN)."""
    cycles_dir = tmp_path / "cycles"
    _write_record(
        cycles_dir,
        "sysA",
        "cycle-1",
        _record(
            system="sysA",
            cycle_id="cycle-1",
            cost={"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "never ran"},
        ),
    )
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert "UNKNOWN" in doc
    assert "(source: unavailable)" in doc
    # The legend's own prose legitimately mentions "$0" as a NEGATIVE
    # example ("never $0"); scope the real assertion to the executive
    # summary's own cost cell rather than the whole document, so this
    # can't collide with that unrelated, correct usage.
    exec_summary = doc[doc.index("exec-summary") : doc.index("</table>", doc.index("exec-summary"))]
    assert "$0" not in exec_summary
    # cost_headline() itself, in isolation -- the exact unit this renders
    # through everywhere a headline cost figure appears.
    unpriced = r.CostRollup(
        total_usd=None, total_tokens=None, n_ledger_priced=0, n_ledger_unpriced=0,
        n_reported_priced=0, n_reported_unpriced=0, n_missing=1,
    )
    assert r.cost_headline(unpriced) == 'UNKNOWN <span class="reasoning">(source: unavailable)</span>'


def test_cost_headline_renders_a_real_priced_figure_with_its_source_when_available() -> None:
    """Paired positive to the UNKNOWN case above -- a genuinely priced,
    fully-ground-truth cost must render the real dollar figure, never
    'UNKNOWN', and must still name its source in the same breath."""
    priced = r.CostRollup(
        total_usd=12.5, total_tokens=1000, n_ledger_priced=1, n_ledger_unpriced=0,
        n_reported_priced=0, n_reported_unpriced=0, n_missing=0,
    )
    rendered = r.cost_headline(priced)
    assert "UNKNOWN" not in rendered
    assert "$12.50" in rendered
    assert "ground truth" in rendered


def test_missing_repo_renders_no_repo_recorded_never_blank_or_zero(tmp_path: Path) -> None:
    """Design requirement 4 (MISSING IS NOT ZERO, plain-English label): a
    cycle record with no 'repo' field at all must render the honest
    'no repo recorded' text, never an empty string and never a fabricated
    placeholder that could be mistaken for real data. FALSIFIABILITY: the
    OLD renderer's cycle-card header already carried this exact same
    fallback text (`repo = _safe_str(raw.get('repo')) or 'no repo
    recorded'` is preserved verbatim from the old render_cycle_card into
    the new render_cycle_details) -- so this specific string was ALREADY
    green pre-redesign; what's newly asserted here is that the redesign's
    nested <details> structure didn't drop it. Confirmed by direct
    inspection of both the old and new function bodies for this line."""
    cycles_dir = tmp_path / "cycles"
    record = _record(system="sysA", cycle_id="cycle-1")
    del record["repo"]
    _write_record(cycles_dir, "sysA", "cycle-1", record)
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert "no repo recorded" in doc


def test_missing_started_at_renders_an_em_dash_never_a_fabricated_timestamp(tmp_path: Path) -> None:
    """A cycle record with no 'started_at'/'ended_at' at all must render
    fmt_ts's honest placeholder ('—'), never blank and never a fabricated
    date. Scoped to the cycle's own <summary> line via its cycle_id anchor
    so this can't coincidentally match an unrelated em-dash elsewhere on
    the page."""
    cycles_dir = tmp_path / "cycles"
    record = _record(system="sysA", cycle_id="cycle-nodates")
    del record["started_at"]
    del record["ended_at"]
    _write_record(cycles_dir, "sysA", "cycle-nodates", record)
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    idx = doc.index("cycle-nodates")
    window = doc[idx : idx + 400]
    assert "—" in window


def test_wrap_sub_expander_count_none_renders_not_recorded_never_a_fabricated_zero() -> None:
    """Direct unit coverage of wrap_sub_expander's own MISSING IS NOT ZERO
    contract: count=None (a list that was never recorded at all, as
    opposed to recorded-but-empty) must render the literal 'not recorded'
    text, never '0'. FALSIFIABILITY: the OLD renderer's render_cycle_card
    had no per-list count/gist concept at all (it always rendered every
    table in full, with no summary count anywhere) -- the literal string
    'not recorded' in this exact sub-expander-summary sense does not occur
    in its output; confirmed absent there (RED) and present here (GREEN)."""
    html_out = r.wrap_sub_expander("Runs", None, "", "<p>body</p>")
    assert "not recorded" in html_out
    assert ">0<" not in html_out


def test_wrap_sub_expander_count_zero_renders_a_compact_line_not_a_full_expander() -> None:
    """A genuinely empty (recorded, zero rows) list collapses to a single
    compact line rather than a full, always-visible-when-expanded
    <details> with nothing inside -- the mechanism that keeps a cycle with
    ten empty v2 arrays short on the page."""
    html_out = r.wrap_sub_expander("Runs", 0, "", "<p>body</p>")
    assert "<details" not in html_out
    assert "none recorded for this cycle" in html_out


def test_no_details_defaults_open_anywhere(tmp_path: Path) -> None:
    """B-ASSERT-9 (operator amendment, 2026-09-05: "all expanders should
    default closed... no <details open> anywhere"). This test REPLACES a
    predecessor that asserted the opposite (the newest-activity system,
    and within it the newest cycle, opened by default) -- that behavior is
    now explicitly removed page-wide, including for the newest-activity
    system and its newest cycle, which is exactly the case this corpus
    exercises (it used to be the ONE case that opened).

    FALSIFIABILITY: proven RED by temporarily reintroducing the removed
    open-by-default behavior in a scratch copy (never the shared module --
    see test_falsifiability_no_details_open_anywhere_would_catch_a_reintroduced_default
    below, which does exactly this via a monkeypatched open_attr) and
    GREEN against the real, fixed module here."""
    cycles_dir = tmp_path / "cycles"
    # sys-old: TWO cycles, both older than anything in sys-new -- same
    # corpus shape the predecessor test used, so a newest-system/newest-
    # cycle default-open regression (were it ever reintroduced) would still
    # be caught by this exact fixture.
    _write_record(
        cycles_dir, "sys-old", "c1",
        _record(system="sys-old", cycle_id="c1", started_at="2019-01-01T00:00:00Z", ended_at="2019-01-01T01:00:00Z"),
    )
    _write_record(
        cycles_dir, "sys-old", "c2",
        _record(system="sys-old", cycle_id="c2", started_at="2020-01-01T00:00:00Z", ended_at="2020-01-01T01:00:00Z"),
    )
    _write_record(
        cycles_dir, "sys-new", "c1",
        _record(system="sys-new", cycle_id="c1", started_at="2026-01-01T00:00:00Z", ended_at="2026-01-01T01:00:00Z"),
    )
    _write_record(
        cycles_dir, "sys-new", "c2",
        _record(system="sys-new", cycle_id="c2", started_at="2026-06-01T00:00:00Z", ended_at="2026-06-01T01:00:00Z"),
    )
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    sys_tags = re.findall(r'<details class="sys-expander"[^>]*>', doc)
    assert len(sys_tags) == 2
    assert all(" open" not in t for t in sys_tags)

    cyc_tags = re.findall(r'<details class="cycle-expander" data-search="([^"]*)"([^>]*)>', doc)
    assert len(cyc_tags) == 4
    assert all(" open" not in attrs for _, attrs in cyc_tags)

    # Page-wide: not one single <details ...open...> anywhere in the
    # rendered document (legend/issues/sub-expanders included).
    assert re.search(r"<details\b[^>]*\bopen\b", doc) is None


def test_no_details_defaults_open_against_the_real_telemetry_dir() -> None:
    """B-ASSERT-9, second half: the same zero-open assertion against
    whatever the operator's OWN real ~/.claude/telemetry/cycles corpus
    currently holds, not just a synthetic fixture -- catching a regression
    that only manifests on real, larger, messier data. Skips cleanly (never
    fails) when this machine has no real telemetry yet, matching this
    suite's existing machine-local-data posture elsewhere in this file."""
    cycles_dir = r.DEFAULT_CYCLES_DIR
    if not cycles_dir.is_dir():
        pytest.skip(f"no real cycle records on this machine: {cycles_dir}")
    records, issues = r.load_cycle_records(cycles_dir)
    if not records:
        pytest.skip(f"real cycles dir exists but has no loadable records: {cycles_dir}")
    doc = r.render_document(records, issues, cycles_dir)
    assert re.search(r"<details\b[^>]*\bopen\b", doc) is None


def test_falsifiability_no_details_open_anywhere_would_catch_a_reintroduced_default(
    tmp_path: Path,
) -> None:
    """Proves the assertion in test_no_details_defaults_open_anywhere is
    not vacuous: monkeypatching render_system_details' own open_attr
    computation back to the removed "most-recent-system opens" behavior
    (without touching the shared module file on disk -- CLAUDE.md §6) makes
    the exact same zero-open check fail RED; the unmodified module (used
    everywhere else in this file) passes it GREEN."""
    import importlib

    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)

    doc_fixed = r.render_document(records, issues, cycles_dir)
    assert re.search(r"<details\b[^>]*\bopen\b", doc_fixed) is None  # GREEN, real module

    src_path = Path(r.__file__)
    src = src_path.read_text(encoding="utf-8")
    reintroduced = src.replace(
        'return f"""\n<details class="sys-expander" data-section="{esc(system)}">',
        'open_attr = " open"\n    return f"""\n<details class="sys-expander" data-section="{esc(system)}"{open_attr}>',
        1,
    )
    assert reintroduced != src  # sanity: the patch target text actually matched

    scratch_module_path = tmp_path / "render_cycle_log_scratch_reintroduced.py"
    scratch_module_path.write_text(reintroduced, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("render_cycle_log_scratch_reintroduced", scratch_module_path)
    scratch = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scratch
    try:
        spec.loader.exec_module(scratch)
        doc_red = scratch.render_document(records, issues, cycles_dir)
        assert re.search(r"<details\b[^>]*\bopen\b", doc_red) is not None  # RED, reintroduced module
    finally:
        del sys.modules[spec.name]


def test_trend_chart_svg_present_inside_a_systems_details(tmp_path: Path) -> None:
    """Design requirement 3: a per-system trend chart (findings + distinct
    causes per cycle) renders as an inline, self-contained SVG -- no
    external assets, per the runtime deliverable rule. FALSIFIABILITY: the
    OLD renderer has no multi-series trend-chart SVG at all (only a
    line+dot 'spark' per metric, never labelled findings/causes together)
    -- 'class=\"chart\"'/'trend chart' do not occur in its output;
    confirmed absent there (RED) and present here (GREEN)."""
    cycles_dir = tmp_path / "cycles"
    for i in range(3):
        _write_record(
            cycles_dir,
            "sysA",
            f"c{i}",
            _record(
                system="sysA",
                cycle_id=f"c{i}",
                findings=[_finding(finding_id=f"f{i}", claim_cause=f"cause-{i}")],
            ),
        )
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert '<svg class="chart"' in doc
    assert 'aria-label="trend chart"' in doc
    assert "findings per cycle" in doc
    assert "distinct causes per cycle" in doc


def test_trend_chart_svg_degrades_to_a_text_note_with_fewer_than_two_cycles(tmp_path: Path) -> None:
    """A system with only one cycle has nothing to draw a trend LINE
    across -- must degrade to an honest text note, never a broken or
    single-point SVG that looks like real data."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert "Not enough cycles yet to draw a trend chart." in doc
    assert '<svg class="chart"' not in doc


def test_bar_sparkline_svg_present_in_the_executive_summary_row(tmp_path: Path) -> None:
    """Design requirement 3: the executive summary row's per-system
    findings-per-cycle bar sparkline. A missing per-cycle value renders a
    distinct, title-flagged 'not recorded' bar rather than a real 0-height
    bar that could be mistaken for a cycle that genuinely found nothing."""
    assert "no cycles yet" in r.render_bar_sparkline([])
    with_gap = r.render_bar_sparkline([2.0, None, 4.0])
    assert "not recorded" in with_gap
    assert 'class="spark-bar-missing"' in with_gap

    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    _write_record(cycles_dir, "sysA", "c2", _record(system="sysA", cycle_id="c2", started_at="2026-01-02T00:00:00Z", ended_at="2026-01-02T01:00:00Z"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)
    assert '<svg class="spark-bars"' in doc


def test_empty_sections_collapse_and_raw_record_is_a_path_pointer_not_a_blob(
    tmp_path: Path,
) -> None:
    """Renamed (coordinator review item 3) from a name that claimed a size
    COMPARISON this test never actually made. What it actually asserts,
    both real mechanisms the design brief specifies for a shorter
    collapsed page --
    (a) a cycle whose v2 arrays are all genuinely empty collapses to
    compact one-line notes rather than ten empty <details> tables, and
    (b) the raw record (coordinator review item 2: DROPPED entirely, the
    predecessor renderer never showed raw JSON at all, so there was
    nothing to "demote" -- verified by direct inspection of its render
    functions) is now a single honest one-line pointer to the real,
    complete, never-deleted file on disk, never a JSON dump of any size."""
    cycles_dir = tmp_path / "cycles"
    # Each finding's claim_symptom is DISTINCT (unique marker text per
    # finding) so a real duplicate (a second, raw-JSON copy of the same
    # content) is unambiguously detectable -- 50 identical strings would
    # legitimately appear 50 times in the real structured table alone,
    # which would make "appears more than once" meaningless as a
    # duplication signal.
    big_findings = [
        _finding(finding_id=f"f{i}", claim_symptom=f"UNIQUE_MARKER_{i}_" + "x" * 190) for i in range(50)
    ]
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1", findings=big_findings))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    # (a) mechanism: compact empty-section lines exist and outnumber full
    # sub-expanders for a cycle with 10 genuinely-empty v2 arrays.
    assert doc.count("none recorded for this cycle") >= 8

    # (b) mechanism: no raw JSON blob anywhere on the page (never truncated
    # inline, because it is never inlined at all) -- just the honest
    # on-disk path. Each finding's own unique marker text appears EXACTLY
    # once (in the real structured findings table) -- if a second, raw-
    # JSON rendering of the same record existed anywhere on the page, that
    # marker would appear twice.
    assert "KB elided" not in doc
    assert "Full record:" in doc
    assert '"claim_symptom"' not in doc  # no raw JSON key ever rendered
    assert doc.count("UNIQUE_MARKER_7_") == 1


def test_gist_helpers_summarize_without_crashing_on_empty_and_malformed_input() -> None:
    """Direct unit coverage of the gist helpers backing every sub-expander
    <summary> line -- must never raise, and must say something honest
    ('none this cycle') rather than an empty string when there is nothing
    to summarize."""
    assert r._findings_gist([]) == "none this cycle"
    assert "confirmed" in r._findings_gist([_finding(verifier_verdict="CONFIRMED")])
    assert r._dispatches_gist([]) == "none this cycle"
    assert r._generic_gist([], "run_id") == "none this cycle"
    assert r._generic_gist([{"run_id": "r1"}, {"run_id": "r2"}], "run_id") == "r1, r2"


# ---------------------------------------------------------------------------
# Coordinator review (post-redesign), BLOCKER: injection via wrap_sub_expander's
# `gist` parameter. `_dispatches_gist` builds its preview directly from a
# record-derived field (agent_type) with zero escaping, and the OLD
# wrap_sub_expander interpolated `gist` raw into its <summary> -- a crafted
# agent_type containing live markup rendered unescaped on the page (proven
# end-to-end: <img onerror=...> survived into the written HTML). Fixed at
# the ONE real boundary every gist flows through (wrap_sub_expander itself
# now escapes `gist` exactly once); `_generic_gist`'s own now-redundant
# per-id esc() call was removed so nothing double-escapes.
# ---------------------------------------------------------------------------


def test_crafted_agent_type_renders_escaped_never_as_live_html(tmp_path: Path) -> None:
    """The exact reported repro: an `<img src=x onerror=...>` payload in a
    dispatch's `agent_type` must never survive into the rendered page as
    real markup -- it must render as escaped, inert text. FALSIFIABILITY:
    confirmed RED against the pre-fix boundary (wrap_sub_expander
    interpolating `gist` without esc()) via a scratch copy with that one
    line reverted -- the raw payload string was found present, unescaped,
    in that render's output; confirmed GREEN against the shipped fix
    below, where it is absent (only the escaped form appears)."""
    cycles_dir = tmp_path / "cycles"
    payload = "<img src=x onerror=alert(1)>"
    record = _record(
        system="sysA",
        cycle_id="cycle-1",
        dispatches=[_dispatch(agent_type=payload)],
    )
    _write_record(cycles_dir, "sysA", "cycle-1", record)
    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    doc = r.render_document(records, issues, cycles_dir)

    assert payload not in doc
    assert "&lt;img src=x onerror=alert(1)&gt;" in doc
    # And no double-escaping crept in either (the boundary fix removed a
    # redundant per-id esc() call elsewhere -- confirm the single-escape
    # contract holds for the ids _generic_gist still handles).
    assert "&amp;lt;" not in doc


def test_dispatches_gist_returns_plain_unescaped_text_escaping_happens_once_at_the_boundary() -> None:
    """Direct unit proof of the fix's shape: `_dispatches_gist` itself
    returns PLAIN text (the escaping boundary is wrap_sub_expander, not
    this helper) -- a caller that skipped wrap_sub_expander and printed
    this value directly would need to escape it itself, exactly once."""
    payload = "<img src=x onerror=alert(1)>"
    gist = r._dispatches_gist([_dispatch(agent_type=payload)])
    assert gist == payload  # plain, unescaped -- the helper's own contract
    # wrap_sub_expander is where this actually gets neutralized for the page:
    wrapped = r.wrap_sub_expander("Dispatches", 1, gist, "<p>body</p>")
    assert payload not in wrapped
    assert "&lt;img src=x onerror=alert(1)&gt;" in wrapped


def test_generic_gist_returns_plain_unescaped_text_no_double_escaping_at_the_boundary() -> None:
    """`_generic_gist`'s own per-id esc() call was removed as part of the
    boundary fix -- it must return plain text now, and wrap_sub_expander
    must still neutralize it exactly once (never twice, which would
    render literal `&amp;lt;` instead of `&lt;`)."""
    payload = "<script>alert(1)</script>"
    gist = r._generic_gist([{"run_id": payload}], "run_id")
    assert gist == payload  # plain, unescaped
    wrapped = r.wrap_sub_expander("Runs", 1, gist, "<p>body</p>")
    assert payload not in wrapped
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in wrapped
    assert "&amp;lt;" not in wrapped  # never double-escaped


# ---------------------------------------------------------------------------
# Coordinator review, item 4: MISSING IS NOT ZERO on the executive summary's
# own headline cell. A cycle record with no `findings` key at all must
# render "not recorded", never a fabricated "0 (0 new, 0 recurring)" --
# captured via CycleRecord.has_findings, set at load_cycle_records()'s own
# loading boundary (straight off the pre-normalization parsed dict), never
# by touching normalize_record/analyze/CycleRecord's parity-critical shape.
# ---------------------------------------------------------------------------


def test_cycle_record_has_findings_reflects_the_source_json_not_the_coerced_shape(
    tmp_path: Path,
) -> None:
    """Direct proof that `has_findings` is captured from the RAW,
    pre-normalization dict -- a record with no `findings` key at all must
    read has_findings=False, even though `record.raw["findings"]` (after
    normalize_record's own, unchanged coercion) is `[]` either way."""
    cycles_dir = tmp_path / "cycles"
    no_findings = _record(system="sysA", cycle_id="c1")
    del no_findings["findings"]
    _write_record(cycles_dir, "sysA", "c1", no_findings)

    empty_findings = _record(system="sysA", cycle_id="c2", findings=[])
    _write_record(cycles_dir, "sysA", "c2", empty_findings)

    records, issues = r.load_cycle_records(cycles_dir)
    assert issues == []
    by_id = {rec.cycle_id: rec for rec in records}

    assert by_id["c1"].has_findings is False
    assert by_id["c2"].has_findings is True
    # Both coerce to the SAME [] in .raw -- confirming this is genuinely
    # a load-time presence signal, not something analyze()/normalize_record
    # could have derived from .raw alone after the fact.
    assert by_id["c1"].raw["findings"] == []
    assert by_id["c2"].raw["findings"] == []


def test_cycle_record_default_has_findings_is_true_for_direct_construction() -> None:
    """A direct `CycleRecord(...)` construction (as every pre-existing test
    elsewhere in this file does, never supplying `has_findings`) must keep
    assuming findings ARE present -- the new field's default must never
    silently reinterpret every pre-existing test fixture as "not
    recorded"."""
    rec = r.CycleRecord(path="x.json", system="s", cycle_id="c1", raw={}, quality_notes=())
    assert rec.has_findings is True


def test_executive_summary_renders_not_recorded_never_a_fabricated_zero_when_findings_absent(
    tmp_path: Path,
) -> None:
    """End-to-end falsification target: a cycle record with no `findings`
    key at all must render 'not recorded' in the executive summary's
    headline cell, never '0 (0 new, 0 recurring)'. FALSIFIABILITY:
    confirmed by direct inspection that the pre-fix code (which read
    `latest_analysis.n_findings` unconditionally, with no has_findings
    check) would have rendered a real, non-None 0 here -- there was
    nothing this test could distinguish before load_cycle_records started
    populating has_findings, since `Analysis.n_findings` is identically 0
    for both 'absent' and 'recorded, empty' under the (unchanged, still
    correct) parity path."""
    cycles_dir = tmp_path / "cycles"
    no_findings = _record(system="sysA", cycle_id="c1")
    del no_findings["findings"]
    _write_record(cycles_dir, "sysA", "c1", no_findings)
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    exec_block = doc[doc.index('<div class="exec-summary panel">') : doc.index("</table>", doc.index("exec-summary panel"))]
    assert "not recorded" in exec_block
    assert "0 new" not in exec_block
    assert "0 recurring" not in exec_block
    # And the bar sparkline's previously-dead "missing" branch is now
    # genuinely reachable from real (well, realistically-shaped) data.
    assert 'class="spark-bar-missing"' in doc


def test_executive_summary_still_renders_real_zero_findings_honestly_when_recorded(
    tmp_path: Path,
) -> None:
    """Paired positive: a cycle that genuinely recorded an EMPTY findings
    list (a real, confident 0 -- the loop ran and found nothing) must
    still render the real "0 (0 new, 0 recurring)" text, never demoted to
    "not recorded" just because the count happens to be zero."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1", findings=[]))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    exec_block = doc[doc.index('<div class="exec-summary panel">') : doc.index("</table>", doc.index("exec-summary panel"))]
    assert "0 new" in exec_block
    assert "0 recurring" in exec_block
    assert "not recorded" not in exec_block


def test_trend_chart_findings_series_also_shows_a_gap_never_a_fabricated_zero(
    tmp_path: Path,
) -> None:
    """The identical MISSING IS NOT ZERO fix applied to the system trend
    chart's own findings-per-cycle series (render_system_details), not
    just the executive summary headline -- a cycle with no findings key
    plots as a real gap (a None point the chart line skips over), not a
    fabricated zero data point."""
    cycles_dir = tmp_path / "cycles"
    present = _record(
        system="sysA",
        cycle_id="c1",
        started_at="2026-01-01T00:00:00Z",
        ended_at="2026-01-01T01:00:00Z",
        findings=[_finding(finding_id="f1")],
    )
    _write_record(cycles_dir, "sysA", "c1", present)
    absent = _record(system="sysA", cycle_id="c2", started_at="2026-01-02T00:00:00Z", ended_at="2026-01-02T01:00:00Z")
    del absent["findings"]
    _write_record(cycles_dir, "sysA", "c2", absent)
    records, issues = r.load_cycle_records(cycles_dir)
    ordered = sorted(records, key=lambda rc: rc.sort_key())
    assert [rc.cycle_id for rc in ordered] == ["c1", "c2"]  # c1 (earlier) sorts first
    per_cycle = [r.analyze([rc]) for rc in ordered]
    findings_count_series = [
        float(a.n_findings) if rc.has_findings else None for rc, a in zip(ordered, per_cycle)
    ]
    assert findings_count_series == [1.0, None]


# ---------------------------------------------------------------------------
# (e) W-EL (Operator Hub absorption, runtime half): --hub-link, the print
# stylesheet + Export PDF + "Print all cycles" toggle, and the window-scroll-
# only rule (no inner overflow/max-height on content containers).
# ---------------------------------------------------------------------------


def test_hub_link_renders_a_prominent_link_when_the_flag_is_passed(tmp_path: Path) -> None:
    """--hub-link <href> renders a "← Operator Hub" link at the top of the
    page. FALSIFIABILITY: the flag renders nothing today without this
    change (render_document has no hub_link parameter at all) -- confirmed
    RED via the paired absent-flag test below (same render_document call,
    no hub_link kwarg, asserting the link text is ABSENT), and GREEN here
    with the kwarg supplied."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir, hub_link="../../operator_hub.html#engine-loop")

    assert "Operator Hub" in doc
    assert 'href="../../operator_hub.html#engine-loop"' in doc
    assert 'class="hub-link-row"' in doc


def test_hub_link_absent_flag_renders_no_link_byte_identical_region(tmp_path: Path) -> None:
    """No --hub-link flag (hub_link=None, the default) must render
    byte-identical to a build with no hub-link region at all -- never a
    stray empty wrapper div, per this module's own "no repo path and no
    product name appears anywhere in this file" contract (a generic
    renderer must degrade to nothing, not a placeholder, when the caller
    supplies nothing)."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)

    doc_default = r.render_document(records, issues, cycles_dir)
    doc_explicit_none = r.render_document(records, issues, cycles_dir, hub_link=None)
    doc_empty_string = r.render_document(records, issues, cycles_dir, hub_link="")

    assert "Operator Hub" not in doc_default
    assert 'class="hub-link-row"' not in doc_default
    # Explicit None and the omitted-kwarg default must be identical (never
    # a divergent code path depending on how "no link" was expressed) --
    # and an empty string is treated the same as None (a falsy href is
    # never rendered as a real, empty-href link).
    assert doc_default == doc_explicit_none == doc_empty_string


def test_never_hardcodes_a_product_repo_path_for_the_hub_link(tmp_path: Path) -> None:
    """This module's own module docstring promise ("no repo path and no
    product name appears anywhere in this file") extends to the new
    hub_link feature: the href is caller-supplied data, rendered verbatim
    (HTML-escaped) via esc() -- never a literal ExampleApp/CSA path
    baked into the renderer itself."""
    src = Path(r.__file__).read_text(encoding="utf-8")
    assert "ExampleApp" not in src
    assert "operator_hub.html" not in src


def test_main_refuses_a_javascript_scheme_hub_link(tmp_path: Path) -> None:
    """NIT 6 (cold review round 1): --hub-link is operator-typed today, but
    a javascript: scheme href is refused outright as cheap insurance --
    case-insensitive, and after stripping leading whitespace (a pasted
    value with a leading space/tab must not slip past a naive startswith
    check)."""
    cycles_dir = tmp_path / "cycles"
    cycles_dir.mkdir()
    for payload in (
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "  javascript:alert(1)",
        "\tJAVASCRIPT:alert(1)",
    ):
        with pytest.raises(SystemExit) as exc_info:
            r.main(["--cycles-dir", str(cycles_dir), "--hub-link", payload])
        assert exc_info.value.code != 0


def test_main_accepts_a_normal_hub_link_href(tmp_path: Path) -> None:
    """Paired with the refusal test above (CLAUDE.md §6: a redirect/refusal
    assertion needs a paired recovery assertion) -- an ordinary relative or
    fragment href is accepted and rendered normally, never caught by the
    javascript: guard's own string matching."""
    cycles_dir = tmp_path / "cycles"
    cycles_dir.mkdir()
    out_path = tmp_path / "out.html"
    for ok_href in (
        "../../operator_hub.html#engine-loop",
        "https://example.com/hub",
        "#anchor-only",
        "",
    ):
        rc = r.main(["--cycles-dir", str(cycles_dir), "--out", str(out_path), "--hub-link", ok_href])
        assert rc == 0


def test_print_stylesheet_present_with_hide_chrome_and_page_break_rules(tmp_path: Path) -> None:
    """B-ASSERT-11: a real @media print stylesheet exists that (1) hides
    the search/filter chrome (.controls) and the Export PDF button's own
    wrapper (.print-controls) and (2) applies page-break hygiene
    (break-inside:avoid on small atomic boxes/table rows, break-before:page
    via a sibling-combinator on system sections -- see the two dedicated
    tests below for the cold-review-round-1 fixes to both halves of this).
    Regex-anchored to selector -> declaration pairs, not bare substrings (a
    bare-substring probe was proven vacuous in a sibling repo this week --
    e.g. asserting 'overflow:auto' merely occurs anywhere on the page would
    pass even if it were on an unrelated, harmless selector; anchoring the
    selector to its own declaration block is what makes this a real
    assertion about WHICH rule carries WHICH property)."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    print_block_match = re.search(r"@media print\s*\{(.*?)\n\}\n", doc, re.DOTALL)
    assert print_block_match is not None, "no @media print block found in the rendered <style>"
    print_block = print_block_match.group(1)

    # Hides the search/filter chrome and the export button's own wrapper.
    hide_rule = re.search(
        r"\.controls,\s*\.print-controls,\s*\.hub-link-row\s*\{[^}]*display\s*:\s*none\s*!important",
        print_block,
    )
    assert hide_rule is not None, "no selector->declaration rule hiding .controls/.print-controls in @media print"

    # Page-break hygiene: break-inside:avoid on the small atomic boxes and
    # table rows (BLOCKER 2 fix, cold review round 1 -- the three
    # *-expander selectors are asserted ABSENT from this group by the
    # dedicated test below, since a large-container "avoid" is
    # unsatisfiable and engine-undefined under print).
    avoid_rule = re.search(
        r"\.panel,\s*\.stat,\s*\.trend-card,\s*tr\s*\{[^}]*break-inside\s*:\s*avoid",
        print_block,
    )
    assert avoid_rule is not None, "no break-inside:avoid rule on .panel/.stat/.trend-card/tr in @media print"


def test_break_inside_avoid_never_applies_to_the_large_expander_containers(tmp_path: Path) -> None:
    """BLOCKER 2 (cold review round 1): break-inside:avoid is an
    unsatisfiable constraint on details.sys-expander/cycle-expander/
    sub-expander -- the real sys-expander alone serializes to 706,953
    bytes (97% of the document), and print engines treat an unsatisfiable
    avoid as undefined (ignored at best, blank runs at worst). Assert,
    directly against the emitted CSS text (both directions RED-provable),
    that none of the three large-container selectors ever appears inside
    a break-inside:avoid declaration group, while confirming they still
    get the harmless box-shadow:none reset."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    print_block_match = re.search(r"@media print\s*\{(.*?)\n\}\n", doc, re.DOTALL)
    assert print_block_match is not None
    print_block = print_block_match.group(1)

    large_container_selectors = (
        "details.sys-expander",
        "details.cycle-expander",
        "details.sub-expander",
    )

    # Every declaration GROUP (selector-list{...}) that contains
    # break-inside -- find each one, then assert none of its selector list
    # names a large container. This is direction 1: RED if a future edit
    # reintroduces one of the three selectors into any avoid group; GREEN
    # today because none of them do.
    for group_match in re.finditer(r"([^{}]+)\{([^}]*)\}", print_block):
        selectors, declarations = group_match.groups()
        if "break-inside" not in declarations:
            continue
        for bad_selector in large_container_selectors:
            assert bad_selector not in selectors, (
                f"{bad_selector!r} found in a break-inside:avoid declaration group: {selectors!r}"
            )

    # Direction 2 (never vacuous): the three selectors DO appear together
    # somewhere in the print block, just in a box-shadow-only group, not
    # dropped from the print stylesheet entirely.
    box_shadow_rule = re.search(
        r"\.panel,\s*details\.sys-expander,\s*details\.cycle-expander,\s*details\.sub-expander,\s*"
        r"\.stat,\s*\.trend-card\s*\{[^}]*box-shadow\s*:\s*none",
        print_block,
    )
    assert box_shadow_rule is not None, "the three expander selectors should still get the box-shadow:none reset"
    assert "break-inside" not in box_shadow_rule.group(0)


def test_falsifiability_break_inside_avoid_check_would_catch_the_original_defect() -> None:
    """Proves the check above is not vacuous: reconstructing the ORIGINAL
    (pre-fix) declaration group -- which grouped the three large
    *-expander selectors together WITH break-inside:avoid -- through the
    identical scan used by the test above confirms it WOULD have failed."""
    original_defective_block = (
        '.panel, .cycle, details.sys-expander, details.cycle-expander, details.sub-expander,\n'
        '  .stat, .trend-card{box-shadow:none!important;break-inside:avoid;page-break-inside:avoid}\n'
    )
    large_container_selectors = (
        "details.sys-expander",
        "details.cycle-expander",
        "details.sub-expander",
    )
    found_violation = False
    for group_match in re.finditer(r"([^{}]+)\{([^}]*)\}", original_defective_block):
        selectors, declarations = group_match.groups()
        if "break-inside" not in declarations:
            continue
        for bad_selector in large_container_selectors:
            if bad_selector in selectors:
                found_violation = True
    assert found_violation, "the original defective block should have tripped this exact check"


def test_page_break_before_uses_a_sibling_combinator_and_excludes_the_first_system(
    tmp_path: Path,
) -> None:
    """BLOCKER 1 (cold review round 1): the previous suppression selector
    (`details.sys-expander:first-of-type`) matched ZERO elements on the
    real page -- :first-of-type is per-TAG-NAME among ALL <details>
    siblings, and render_legend()'s `<details class="legend">` is the real
    first `<details>` inside `.wrap`, so the unsuppressed
    `break-before:page` fired on the FIRST system too, opening every
    export with a blank/near-empty first page.

    This test drives the REAL rendered CSS through an actual CSS selector
    engine (soupsieve, via BeautifulSoup) against a REAL two-system
    synthetic fixture, rather than trusting a regex reading of the
    selector text -- the same class of check the cold review used to catch
    the original defect (a regex could easily assert "the string
    'break-before:page' appears" without ever proving WHICH elements it
    actually matches)."""
    bs4 = pytest.importorskip("bs4")
    soupsieve = pytest.importorskip("soupsieve")

    cycles_dir = tmp_path / "cycles"
    _write_record(
        cycles_dir, "sys-a", "c1",
        _record(system="sys-a", cycle_id="c1", started_at="2026-01-01T00:00:00Z", ended_at="2026-01-01T01:00:00Z"),
    )
    _write_record(
        cycles_dir, "sys-b", "c1",
        _record(system="sys-b", cycle_id="c1", started_at="2026-02-01T00:00:00Z", ended_at="2026-02-01T01:00:00Z"),
    )
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    print_block_match = re.search(r"@media print\s*\{(.*?)\n\}\n", doc, re.DOTALL)
    assert print_block_match is not None
    print_block = print_block_match.group(1)

    break_rule = re.search(
        r"details\.sys-expander ~ details\.sys-expander\s*\{[^}]*break-before\s*:\s*page",
        print_block,
    )
    assert break_rule is not None, "no sibling-combinator break-before:page rule on details.sys-expander"
    # And the old, defective (zero-match) suppression selector must be
    # gone entirely as an actual CSS RULE -- not just superseded, deleted.
    # (Anchored to "selector{" so this doesn't collide with the fix's own
    # explanatory CSS comment, which legitimately mentions the retired
    # selector by name as part of the emitted <style> text.)
    assert re.search(r":first-of-type\s*\{", print_block) is None

    soup = bs4.BeautifulSoup(doc, "html.parser")
    wrap = soup.select_one(".wrap")
    assert wrap is not None
    matched = soupsieve.select("details.sys-expander ~ details.sys-expander", wrap)
    all_sys_expanders = soupsieve.select("details.sys-expander", wrap)
    assert len(all_sys_expanders) == 2, "fixture should render exactly 2 sys-expanders"
    # The sibling-combinator selector matches exactly the SECOND (and any
    # later) sys-expander -- never the first one, and never zero.
    assert len(matched) == 1
    assert matched[0] is all_sys_expanders[1]
    assert all_sys_expanders[0] not in matched


def test_falsifiability_first_of_type_selector_matches_zero_real_elements() -> None:
    """Proves BLOCKER 1's root-cause claim directly: the ORIGINAL
    suppression selector (`details.sys-expander:first-of-type`) matches
    ZERO elements ANYWHERE on a real rendered page (not just among the
    top-level sections) -- :first-of-type is evaluated per-PARENT among
    same-tag-name children, and no <details class="sys-expander"> is ever
    its parent's first <details> child: render_legend()'s own
    `<details class="legend">` is `.wrap`'s own first `<details>` child
    (the specific case the fix's docstring names), and every OTHER
    <details> parent in this document (each sys-expander's sys-body, each
    cycle-expander) also has a non-sys-expander <details> -- or nothing --
    as its own first child. Run via the real soupsieve engine against
    actual rendered HTML, not a hand-reasoned claim about CSS semantics."""
    bs4 = pytest.importorskip("bs4")
    soupsieve = pytest.importorskip("soupsieve")

    doc = _minimal_two_system_doc_for_selector_probe()
    soup = bs4.BeautifulSoup(doc, "html.parser")
    wrap = soup.select_one(".wrap")
    assert wrap is not None

    zero_match_selector = "details.sys-expander:first-of-type"
    matched = soupsieve.select(zero_match_selector, wrap)
    assert matched == [], (
        f"{zero_match_selector!r} should match ZERO elements (root cause of BLOCKER 1) -- "
        f"found {len(matched)}"
    )

    # And render_legend()'s own <details class="legend"> IS .wrap's own
    # first DIRECT-CHILD <details> -- the specific instance the fix's
    # docstring names as "the real details:first-of-type inside .wrap."
    # (:first-of-type itself is per-parent, not page-wide -- soupsieve
    # confirms 5 total matches across every <details>-containing parent in
    # this two-cycle fixture, one per parent context; direct children of
    # .wrap is the scope that maps onto the CSS rule's actual intent.)
    wrap_children_first_of_type = [
        el for el in soupsieve.select("details:first-of-type", wrap) if el.parent is wrap
    ]
    assert len(wrap_children_first_of_type) == 1
    assert "legend" in (wrap_children_first_of_type[0].get("class") or [])


def _minimal_two_system_doc_for_selector_probe() -> str:
    """Shared helper for the two soupsieve-driven tests above -- avoids
    hitting the filesystem twice for what is purely a markup-structure
    probe (no metric/content assertions), via a fresh tmp dir each call so
    parallel test runs never collide on the same path."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cycles_dir = Path(tmp) / "cycles"
        _write_record(
            cycles_dir, "sys-a", "c1",
            _record(system="sys-a", cycle_id="c1", started_at="2026-01-01T00:00:00Z", ended_at="2026-01-01T01:00:00Z"),
        )
        _write_record(
            cycles_dir, "sys-b", "c1",
            _record(system="sys-b", cycle_id="c1", started_at="2026-02-01T00:00:00Z", ended_at="2026-02-01T01:00:00Z"),
        )
        records, issues = r.load_cycle_records(cycles_dir)
        return r.render_document(records, issues, cycles_dir)


def test_export_pdf_button_present_on_every_generated_page(tmp_path: Path) -> None:
    """B-ASSERT-11: "every hub page and satellite carries an Export PDF
    button" -- exercised on both the populated-records path and the
    zero-records empty-state path (the button must not disappear just
    because there is nothing to show yet)."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc_populated = r.render_document(records, issues, cycles_dir)
    assert re.search(r'<button[^>]*onclick="window\.print\(\)"[^>]*>\s*Export PDF\s*</button>', doc_populated)

    empty_cycles_dir = tmp_path / "empty-cycles"
    doc_empty = r.render_document([], [], empty_cycles_dir)
    assert re.search(r'<button[^>]*onclick="window\.print\(\)"[^>]*>\s*Export PDF\s*</button>', doc_empty)


def test_print_all_toggle_force_open_restore_js_present_with_double_fire_guard(
    tmp_path: Path,
) -> None:
    """B-ASSERT-11's "Print all cycles" toggle: a visible checkbox plus
    beforeprint/afterprint handlers that force every <details> open for
    the print pass and restore each element's own prior open/closed state
    afterward, guarded against a double beforeprint fire (some browsers
    can fire it more than once per print-dialog interaction without an
    intervening afterprint) -- the "own implementation, same guard SHAPE"
    pattern this wave's instructions call for, not a copy of the CSA hub's
    file."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    assert '<input type="checkbox" id="print-all-cycles">' in doc
    assert "Print all cycles" in doc

    # beforeprint handler: guarded (checks a reentrancy flag before doing
    # anything) and force-opens every <details> only when the toggle is
    # checked.
    before_fn_match = re.search(
        r"function _printAllBeforePrint\(\)\s*\{(.*?)\n\}\n", doc, re.DOTALL
    )
    assert before_fn_match is not None
    before_body = before_fn_match.group(1)
    assert "print-all-cycles" in before_body
    assert re.search(r"if\s*\(\s*_printAllReopenState\s*\)\s*return\s*;", before_body)
    assert "setAttribute('open'" in before_body

    # afterprint handler: restores each element's own prior state (never a
    # blanket "close everything").
    after_fn_match = re.search(r"function _printAllAfterPrint\(\)\s*\{(.*?)\n\}\n", doc, re.DOTALL)
    assert after_fn_match is not None
    after_body = after_fn_match.group(1)
    assert "removeAttribute('open')" in after_body
    assert "_printAllReopenState=null" in after_body.replace(" ", "")

    # Both handlers actually registered against the real print events.
    assert "addEventListener('beforeprint',_printAllBeforePrint)" in doc
    assert "addEventListener('afterprint',_printAllAfterPrint)" in doc


def test_no_overflow_auto_scroll_or_max_height_on_content_containers(tmp_path: Path) -> None:
    """B-ASSERT-10: window-scroll only -- no internal scrolling anywhere.
    Grep the rendered CSS for overflow:auto/scroll and max-height caps on
    content containers; the ONE sanctioned exception is `.table-scroll`'s
    `overflow-x:auto` for genuinely-wide tables (horizontal only, and it
    carries no max-height / no overflow-y), which must still expand
    vertically without limit. FALSIFIABILITY: proven RED against the prior
    (pre-fix) render_error_page's own inline
    `overflow:auto; white-space:pre-wrap` rule -- see
    test_falsifiability_render_error_page_would_have_failed_this_check
    below, which reintroduces exactly that removed style in a scratch copy
    and confirms THIS SAME regex fails to find it clean."""
    cycles_dir = tmp_path / "cycles"
    _write_record(cycles_dir, "sysA", "c1", _record(system="sysA", cycle_id="c1"))
    records, issues = r.load_cycle_records(cycles_dir)
    doc = r.render_document(records, issues, cycles_dir)

    # No `overflow-y` at all, anywhere.
    assert "overflow-y" not in doc.replace(" ", "")

    # Every `overflow:auto` or `overflow:scroll` occurrence (any spacing)
    # must be immediately preceded by `overflow-x` (the sanctioned wide-
    # table exception), never a bare `overflow` (which defaults to
    # shorthand covering both axes) and never `overflow-y`.
    compact = re.sub(r"\s+", "", doc)
    for match in re.finditer(r"overflow(-x)?:(auto|scroll)", compact):
        assert match.group(1) == "-x", (
            f"non-horizontal-only overflow:auto/scroll found: "
            f"{compact[max(0, match.start() - 20):match.end() + 5]!r}"
        )

    # No max-height cap on any content container.
    assert "max-height" not in compact


def test_falsifiability_render_error_page_would_have_failed_this_check() -> None:
    """Proves the prior check in the test above is not vacuous: the
    render_error_page() traceback <pre> USED to carry `overflow:auto` (an
    inner-scrolling content container, removed by this same change) --
    reconstructing that exact removed style inline and running it through
    the identical regex from the test above confirms it WOULD have failed
    the "every overflow:auto is -x only" assertion, i.e. the check is
    actually sensitive to the defect it exists to catch."""
    removed_style = 'background:#f3f4f6; padding:12px; overflow:auto; white-space:pre-wrap'
    compact = re.sub(r"\s+", "", removed_style)
    found_non_x_overflow = False
    for match in re.finditer(r"overflow(-x)?:(auto|scroll)", compact):
        if match.group(1) != "-x":
            found_non_x_overflow = True
    assert found_non_x_overflow, "the removed style should have tripped the non -x overflow check"

    # And the CURRENT render_error_page output no longer contains it.
    current = r.render_error_page(Path("/nonexistent"), ValueError("boom"))
    compact_current = re.sub(r"\s+", "", current)
    for match in re.finditer(r"overflow(-x)?:(auto|scroll)", compact_current):
        assert match.group(1) == "-x"


# ---------------------------------------------------------------------------
# Fragment-embedding API (CSS constant / scoped_css / render_fragment) --
# added 2026-09-07 so a product repo's hub generator can INLINE this page's
# entire content as a tab panel (operator directive: "i want the entire other
# tracker in this page ... bring everything in") instead of linking out to
# ~/.claude/telemetry/cycle_log.html. Mirrors the already-embedded
# render_agent_telemetry.py render_html(body_only=True)/scoped_css() pair.
# Falsified before implementation: every test below was run against the
# pre-change module first and went RED (AttributeError: no render_fragment /
# scoped_css / CSS), per the falsifiability discipline in ~/.claude/CLAUDE.md
# section 6.
# ---------------------------------------------------------------------------


def _fragment_corpus(tmp_path: Path) -> Path:
    """Two cycles in one system, with enough v1+v2 content that every major
    fragment region (exec summary, trend chart, per-system details, filter
    controls, footer) actually renders."""
    cycles = tmp_path / "cycles"
    _write_record(
        cycles,
        "sysA",
        "c1",
        _record(
            system="sysA",
            cycle_id="c1",
            dispatches=[_dispatch()],
            findings=[_finding()],
        ),
    )
    _write_record(
        cycles,
        "sysA",
        "c2",
        _record(
            system="sysA",
            cycle_id="c2",
            started_at="2026-08-28T14:00:00Z",
            ended_at="2026-08-28T15:00:00Z",
            findings=[_finding(finding_id="f2", verifier_verdict="REFUTED")],
        ),
    )
    return cycles


def test_render_fragment_carries_full_content_without_page_chrome(tmp_path: Path) -> None:
    """(a) The fragment carries EVERYTHING the full page carries -- exec
    summary, legend, per-system details, filter controls, footer -- and NONE
    of the page chrome the host hub already provides (document wrapper,
    <style>, hub-link row, print machinery)."""
    frag = r.render_fragment(_fragment_corpus(tmp_path))
    # Everything rides along:
    assert "What happened, at a glance" in frag, "executive summary missing from fragment"
    assert "What am I looking at? (definitions)" in frag, "legend missing from fragment"
    assert 'details class="sys-expander"' in frag, "per-system details section missing"
    assert 'data-section="sysA"' in frag
    assert "Rendered by <code>~/.claude/scripts/render_cycle_log.py</code>" in frag, "footer missing"
    assert 'id="q"' in frag and 'id="sys-chips"' in frag, "interactive filter controls missing"
    assert "file(s) found" in frag, "provenance line missing"
    # ...but none of the page chrome the host supplies:
    assert "<html" not in frag
    assert "<style" not in frag
    assert "hub-link-row" not in frag
    assert "print-all-cycles" not in frag
    assert "beforeprint" not in frag and "afterprint" not in frag
    assert "</body>" not in frag and "</html>" not in frag
    # Self-balanced: opens and closes its own container, balanced tags.
    assert frag.startswith('<div class="cycle-log">')
    assert frag.rstrip().endswith("</div>")
    assert frag.count("<div") == frag.count("</div>")
    assert frag.count("<details") == frag.count("</details>")


def test_render_fragment_demotes_the_title_to_h3_never_an_h1(tmp_path: Path) -> None:
    """(b) The hub page must keep exactly ONE h1 (its own) -- a 9-h1
    accessibility defect was found and fixed on that page once already, and
    the hub tab renders its own h2 above this fragment."""
    frag = r.render_fragment(_fragment_corpus(tmp_path))
    assert "<h1" not in frag
    assert "<h3>Self-Correcting Loop — Cycle Log</h3>" in frag


def test_render_fragment_scopes_the_filter_script_to_its_own_container(tmp_path: Path) -> None:
    """The interactive filter script rides along, but its class-based
    document-wide querySelectorAll calls are rooted at the fragment
    container so the script can never touch host elements outside it. The
    standalone page keeps its original document-wide form."""
    frag = r.render_fragment(_fragment_corpus(tmp_path))
    assert "<script>" in frag  # the filter script itself is kept
    assert "document.querySelector('.cycle-log')" in frag
    assert "document.querySelectorAll(" not in frag
    # The full page is unchanged: document-wide queries, no container root.
    cycles = _fragment_corpus(tmp_path / "full")
    records, issues = r.load_cycle_records(cycles)
    doc = r.render_document(records, issues, cycles)
    assert "document.querySelectorAll('details.sys-expander')" in doc


def test_scoped_css_prefixes_selectors_drops_print_and_rewrites_root_and_body() -> None:
    """(c) Every top-level rule is confined under the scope, the @media
    print block is dropped entirely (the hub has its own print machinery
    plus a falsifiability guard a second block would defeat), and
    :root/html/body -- which carry the custom properties -- are rewritten to
    the scope element itself so var() still resolves inside the fragment."""
    css = r.scoped_css()
    assert "@media print" not in css
    # Spot-assert known selectors got the prefix:
    assert ".cycle-log .exec-table" in css
    assert ".cycle-log .badge.good" in css
    assert ".cycle-log details.sys-expander" in css
    assert ".cycle-log .footer" in css
    # :root rewritten to the scope itself -- the light palette tokens:
    assert re.search(r"^\.cycle-log\{--bg:", css, re.M), ":root not rewritten to the scope"
    # ...and the dark-mode :root override too, inside its (kept) @media:
    assert "@media (prefers-color-scheme: dark){.cycle-log{--bg:" in css.replace("\n", "")
    # No unscoped :root/html/body selector survives anywhere:
    for line in css.splitlines():
        if not line.strip():
            continue
        assert line.startswith(".cycle-log") or line.startswith("@media"), (
            f"unscoped top-level CSS line escaped the scope: {line[:80]!r}"
        )
    # A caller-supplied scope is honoured, not hardcoded:
    assert "#hub-cycles .badge" in r.scoped_css("#hub-cycles")


def test_render_fragment_empty_cycles_dir_renders_the_honest_empty_state(tmp_path: Path) -> None:
    """(d) An absent/empty cycles dir renders the honest empty-state
    fragment -- same MISSING IS NOT ZERO posture as the full page -- and
    never raises."""
    for candidate in (tmp_path / "does-not-exist", tmp_path / "empty"):
        if candidate.name == "empty":
            candidate.mkdir()
        frag = r.render_fragment(candidate)
        assert "No cycle records yet" in frag
        assert frag.startswith('<div class="cycle-log">')
        assert "<h1" not in frag
        assert "<style" not in frag
        assert "beforeprint" not in frag


def test_render_fragment_degrades_to_an_error_fragment_never_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unanticipated exception degrades exactly the way
    render_error_page does for the full page: a returned error FRAGMENT
    (still no document wrapper, still no h1), never a raise -- the hub
    build must never die on telemetry problems."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic fragment failure")

    monkeypatch.setattr(r, "load_cycle_records", _boom)
    frag = r.render_fragment(tmp_path / "cycles")
    assert "failed to render" in frag
    assert "synthetic fragment failure" in frag
    assert "<html" not in frag and "<style" not in frag and "<h1" not in frag
    assert frag.startswith('<div class="cycle-log">')
    assert frag.count("<div") == frag.count("</div>")


def test_full_page_path_keeps_its_inline_style_block_after_the_css_refactor(tmp_path: Path) -> None:
    """(e) Regression guard on the CSS refactor: the standalone page still
    inlines the full stylesheet -- including its OWN @media print block and
    print machinery -- and the module-level CSS constant is exactly what
    render_head interpolates."""
    cycles = _fragment_corpus(tmp_path)
    records, issues = r.load_cycle_records(cycles)
    doc = r.render_document(records, issues, cycles)
    assert "<style>" in doc and "</style>" in doc
    assert ":root{" in doc
    assert "@media print" in doc
    assert "<h1>Self-Correcting Loop — Cycle Log</h1>" in doc
    assert "print-all-cycles" in doc and "beforeprint" in doc
    assert r.CSS in doc, "render_head no longer interpolates the module-level CSS constant"
    # The empty-records page keeps the same head too.
    empty_doc = r.render_document([], [], tmp_path / "nope")
    assert r.CSS in empty_doc and "@media print" in empty_doc
