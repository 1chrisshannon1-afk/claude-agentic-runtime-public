"""Hermetic, falsifiable tests for hooks/daily_spend_rollup.py.

Every test builds its own small fixture (plain in-memory row lists for the
pure `compute_daily_rollup`, or throwaway `tmp_path` files for `run`/`main`)
— the real ~/.claude/.agent_budget/spend.jsonl is never read here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import daily_spend_rollup as dsr


def _spend_row(**overrides: object) -> dict:
    base: dict = {
        "ts": "2026-08-29T10:00:00Z",
        "session": "s1",
        "agent_type": "code-reviewer",
        "model": "claude-opus-5[1m]",
        "tool_use_id": "tu1",
        "agent_id": "a1",
        "duration_ms": 1000,
        "tokens": {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4},
        "tokens_total": 10,
        "tokens_error": None,
        "late": False,
        "unreleased": False,
        "reaped": None,
        "join_state": "joined",
    }
    base.update(overrides)
    return base


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


# ===========================================================================
# _day_of / _as_int / default_target_date — small pure helpers.
# ===========================================================================


def test_day_of_extracts_utc_calendar_day():
    assert dsr._day_of("2026-08-29T23:59:59Z") == "2026-08-29"


def test_day_of_none_on_malformed_or_missing_ts():
    assert dsr._day_of(None) is None
    assert dsr._day_of("not-a-timestamp") is None
    assert dsr._day_of("2026-08-29") is None  # no time component -- not the ledger's shape


def test_as_int_accepts_int_and_integral_float():
    assert dsr._as_int(5) == (5, False)
    assert dsr._as_int(5.0) == (5, False)


def test_as_int_rejects_bool_and_non_integral_float_and_string():
    assert dsr._as_int(True) == (0, True)
    assert dsr._as_int(5.5) == (0, True)
    assert dsr._as_int("5") == (0, True)


def test_as_int_none_is_zero_not_malformed():
    assert dsr._as_int(None) == (0, False)


def test_default_target_date_is_utc_yesterday():
    now = datetime(2026, 8, 30, 3, 0, 0, tzinfo=timezone.utc)
    assert dsr.default_target_date(now) == "2026-08-29"


# ===========================================================================
# _check_date_arg — real calendar validation + refuse-today-or-future.
# ===========================================================================

_SOME_NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def test_check_date_arg_accepts_a_valid_past_date():
    assert dsr._check_date_arg("2026-08-29", False, _SOME_NOW) is None


def test_check_date_arg_rejects_calendar_invalid_date_not_just_shape():
    """A shape-only regex (\\d{4}-\\d{2}-\\d{2}) would have accepted this --
    real calendar validation (datetime.strptime) must not."""
    error = dsr._check_date_arg("2026-02-30", False, _SOME_NOW)  # Feb has no 30th
    assert error is not None
    assert "invalid --date" in error


def test_check_date_arg_rejects_today_without_override():
    error = dsr._check_date_arg("2026-08-30", False, _SOME_NOW)  # same day as _SOME_NOW
    assert error is not None
    assert "today or in the future" in error


def test_check_date_arg_rejects_a_future_date_without_override():
    error = dsr._check_date_arg("2026-09-01", False, _SOME_NOW)
    assert error is not None
    assert "today or in the future" in error


def test_check_date_arg_allows_today_with_override_flag():
    assert dsr._check_date_arg("2026-08-30", True, _SOME_NOW) is None


# ===========================================================================
# compute_daily_rollup — the pure aggregation function.
# ===========================================================================


def test_compute_daily_rollup_filters_to_exact_target_day():
    rows = [
        _spend_row(ts="2026-08-28T23:59:59Z", tool_use_id="tu-prev-day"),
        _spend_row(ts="2026-08-29T00:00:00Z", tool_use_id="tu-target-1"),
        _spend_row(ts="2026-08-29T23:59:59Z", tool_use_id="tu-target-2"),
        _spend_row(ts="2026-08-30T00:00:00Z", tool_use_id="tu-next-day"),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["date"] == "2026-08-29"
    assert result["dispatches"] == 2


def test_compute_daily_rollup_excludes_rows_with_no_parseable_ts():
    rows = [
        _spend_row(ts=None, tool_use_id="tu-no-ts"),
        _spend_row(ts="garbage", tool_use_id="tu-bad-ts"),
        _spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu-good"),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 1


def test_compute_daily_rollup_dispatch_count_and_tokens_total_go_red_without_the_fix():
    """The falsifiability anchor: a naive '4 fields * dispatch count' or a
    'just count rows' implementation produces a DIFFERENT number than the
    correct one here, not merely a missing one."""
    rows = [
        _spend_row(
            tool_use_id="tu1",
            tokens={"input": 10, "output": 20, "cache_read": 30, "cache_creation": 40},
            tokens_total=999999,  # deliberately wrong -- must never be trusted directly
        ),
        _spend_row(
            tool_use_id="tu2",
            tokens={"input": 1, "output": 1, "cache_read": 1, "cache_creation": 1},
            tokens_total=888888,
        ),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 2
    # 10+20+30+40=100, 1+1+1+1=4 -> 104, NOT 999999+888888
    assert result["tokens_total"] == 104


def test_compute_daily_rollup_groups_by_agent_type_and_model_pair():
    rows = [
        _spend_row(tool_use_id="tu1", agent_type="code-reviewer", model="claude-opus-5[1m]"),
        _spend_row(tool_use_id="tu2", agent_type="code-reviewer", model="claude-opus-5[1m]"),
        _spend_row(tool_use_id="tu3", agent_type="code-reviewer", model="claude-sonnet-5"),
        _spend_row(tool_use_id="tu4", agent_type="implement", model="claude-sonnet-5"),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    groups = {(g["agent_type"], g["model"]): g["dispatches"] for g in result["by_agent_model"]}
    assert groups == {
        ("code-reviewer", "claude-opus-5[1m]"): 2,
        ("code-reviewer", "claude-sonnet-5"): 1,
        ("implement", "claude-sonnet-5"): 1,
    }


def test_compute_daily_rollup_dedups_by_tool_use_id_prefers_non_unreleased():
    rows = [
        _spend_row(tool_use_id="tu1", unreleased=True, tokens_total=1),
        _spend_row(tool_use_id="tu1", unreleased=False, tokens_total=42),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    # Only ONE dispatch counted (the placeholder + real release collapse to
    # one), and the real (non-unreleased) line's tokens win.
    assert result["dispatches"] == 1
    assert result["tokens_total"] == 1 + 2 + 3 + 4  # from _spend_row's default tokens dict


def test_compute_daily_rollup_includes_null_tool_use_id_rows_in_totals():
    """DELIBERATE DIVERGENCE from churn_report.spend_summary (see module
    docstring): a null-tool_use_id "stopped-unjoined" reap carries real,
    already-spent tokens and must be counted, not dropped -- as long as it
    is not a duplicate of an already-counted dispatch (see the Blocker 1
    join-on-agent_id tests below, which cover the collision case). The
    null-tid row here uses a DISTINCT agent_id from the real-tid row
    specifically so this test isolates "are null-tid rows included at
    all" from "is the agent_id join correct.\""""
    rows = [
        _spend_row(tool_use_id="tu1", agent_id="a1", tokens_total=10),
        _spend_row(
            tool_use_id=None,
            agent_id="a2",
            model=None,
            session=None,
            duration_ms=None,
            reaped="stopped-unjoined",
            join_state="no-claim",
            tokens={"input": 5, "output": 5, "cache_read": 5, "cache_creation": 5},
        ),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 2
    assert result["null_tool_use_id_lines"] == 1
    assert result["joined_duplicate_lines"] == 0
    # 1+2+3+4 (tu1's default tokens) + 5+5+5+5 (the null-tid row) = 30
    assert result["tokens_total"] == 10 + 20


def test_compute_daily_rollup_null_tool_use_id_lines_never_deduplicated_against_each_other():
    rows = [
        _spend_row(tool_use_id=None, agent_type="x", reaped="stopped-unjoined"),
        _spend_row(tool_use_id=None, agent_type="x", reaped="stopped-unjoined"),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 2
    assert result["null_tool_use_id_lines"] == 2


def test_compute_daily_rollup_missing_agent_type_and_model_bucket_as_unknown():
    rows = [_spend_row(tool_use_id="tu1", agent_type=None, model=None)]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["by_agent_model"] == [
        {
            "agent_type": "unknown",
            "model": "unknown",
            "dispatches": 1,
            "tokens_total": 10,
            "input": 1,
            "output": 2,
            "cache_read": 3,
            "cache_creation": 4,
        }
    ]


def test_compute_daily_rollup_malformed_tool_use_id_counted_not_crashed():
    rows = [_spend_row(tool_use_id=123)]  # int, not str/None -- unhashable-as-key case
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 0
    assert result["malformed_fields"]["tool_use_id"] == 1


def test_compute_daily_rollup_malformed_token_field_contributes_zero_and_is_marked():
    rows = [
        _spend_row(
            tool_use_id="tu1",
            tokens={"input": "oops", "output": 2, "cache_read": 3, "cache_creation": 4},
        )
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["by_agent_model"][0]["input"] == 0
    assert result["malformed_fields"]["input"] == 1
    assert result["tokens_total"] == 2 + 3 + 4


def test_compute_daily_rollup_sorted_by_tokens_total_desc_then_name_asc():
    rows = [
        _spend_row(tool_use_id="tu1", agent_type="b", model="m", tokens_total=0,
                    tokens={"input": 1, "output": 0, "cache_read": 0, "cache_creation": 0}),
        _spend_row(tool_use_id="tu2", agent_type="a", model="m", tokens_total=0,
                    tokens={"input": 100, "output": 0, "cache_read": 0, "cache_creation": 0}),
        _spend_row(tool_use_id="tu3", agent_type="c", model="m", tokens_total=0,
                    tokens={"input": 1, "output": 0, "cache_read": 0, "cache_creation": 0}),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    ordered = [(g["agent_type"], g["tokens_total"]) for g in result["by_agent_model"]]
    # "a" (100) first, then "b"/"c" tied at 1 -> alphabetical.
    assert ordered == [("a", 100), ("b", 1), ("c", 1)]


def test_compute_daily_rollup_empty_day_is_zero_not_absent():
    result = dsr.compute_daily_rollup([_spend_row(ts="2026-08-01T00:00:00Z")], "2026-08-29")
    assert result == {
        "date": "2026-08-29",
        "dispatches": 0,
        "tokens_total": 0,
        "null_tool_use_id_lines": 0,
        "joined_duplicate_lines": 0,
        "malformed_fields": {},
        "by_agent_model": [],
    }


# ===========================================================================
# BLOCKER 1 (2026-08-30 review) — a null-tool_use_id row is NOT
# unconditionally unjoinable: it can share an agent_id with a deduped
# real-tool_use_id row (same dispatch, once as its real release and once
# again as a stale reap placeholder), and folding both in double-counts it.
# ===========================================================================


def test_compute_daily_rollup_drops_null_tid_row_sharing_agent_id_with_deduped_row():
    """The exact collision the review found with ZERO prior coverage: a
    null-tool_use_id reap placeholder whose agent_id matches a real,
    already-deduped dispatch must be dropped, not folded in a second time."""
    rows = [
        _spend_row(
            tool_use_id="tu1",
            agent_id="a-shared",
            tokens={"input": 10, "output": 20, "cache_read": 30, "cache_creation": 40},
        ),
        _spend_row(
            tool_use_id=None,
            agent_id="a-shared",
            reaped="stopped-unjoined",
            join_state="no-claim",
            model=None,
            tokens={"input": 5, "output": 5, "cache_read": 5, "cache_creation": 5},
        ),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    # Only the ONE real dispatch is counted -- the null-tid placeholder for
    # the SAME agent_id is dropped, not folded in as a second dispatch.
    assert result["dispatches"] == 1
    assert result["tokens_total"] == 10 + 20 + 30 + 40
    assert result["null_tool_use_id_lines"] == 0
    assert result["joined_duplicate_lines"] == 1


def test_compute_daily_rollup_keeps_null_tid_row_with_a_distinct_agent_id():
    """A null-tool_use_id row whose agent_id matches NOTHING already
    counted is a genuinely distinct dispatch and must still be folded in
    (the DELIBERATE DIVERGENCE this module exists for) -- Blocker 1's fix
    must not overcorrect into dropping every null-tid row."""
    rows = [
        _spend_row(tool_use_id="tu1", agent_id="a-real", tokens_total=10),
        _spend_row(
            tool_use_id=None,
            agent_id="a-distinct",
            model=None,
            reaped="stopped-unjoined",
            join_state="no-claim",
            tokens={"input": 5, "output": 5, "cache_read": 5, "cache_creation": 5},
        ),
    ]
    result = dsr.compute_daily_rollup(rows, "2026-08-29")
    assert result["dispatches"] == 2
    assert result["null_tool_use_id_lines"] == 1
    assert result["joined_duplicate_lines"] == 0
    assert result["tokens_total"] == 10 + 20  # tu1's default 1+2+3+4=10, plus 5*4=20


# ===========================================================================
# run() — the file I/O layer: append, idempotency, absent/error handling.
# ===========================================================================


def test_run_appends_one_line_to_a_fresh_rollup_file(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])

    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))

    assert exit_code == 0
    assert payload["outcome"] == "appended"
    lines = rollup_path.read_text().splitlines()
    assert len(lines) == 1
    recorded = json.loads(lines[0])
    assert recorded["date"] == "2026-08-29"
    assert recorded["dispatches"] == 1


def test_run_is_idempotent_never_double_appends_the_same_date(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])

    dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))
    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))

    assert exit_code == 0
    assert payload["outcome"] == "already-recorded"
    assert len(rollup_path.read_text().splitlines()) == 1  # still just one line


def test_run_never_overwrites_prior_days_lines_appends_only(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(
        spend_path,
        [
            _spend_row(ts="2026-08-28T10:00:00Z", tool_use_id="tu1"),
            _spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu2"),
        ],
    )

    dsr.run("2026-08-28", spend_path=str(spend_path), rollup_path=str(rollup_path))
    dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))

    dates = [json.loads(line)["date"] for line in rollup_path.read_text().splitlines()]
    assert dates == ["2026-08-28", "2026-08-29"]


def test_run_dry_run_never_writes_the_file(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])

    exit_code, payload = dsr.run(
        "2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path), dry_run=True
    )

    assert exit_code == 0
    assert payload["outcome"] == "dry-run"
    assert not rollup_path.exists()


def test_run_spend_absent_is_a_clean_zero_exit_not_an_error(tmp_path):
    exit_code, payload = dsr.run(
        "2026-08-29",
        spend_path=str(tmp_path / "no-such-spend.jsonl"),
        rollup_path=str(tmp_path / "daily_rollup.jsonl"),
    )
    assert exit_code == 0
    assert payload["outcome"] == "spend-absent"


def test_run_spend_read_error_is_a_nonzero_exit(tmp_path, monkeypatch):
    spend_path = tmp_path / "spend.jsonl"
    spend_path.write_text('{"ts": "2026-08-29T10:00:00Z"}\n')
    rollup_path = tmp_path / "daily_rollup.jsonl"

    import churn_report as cr

    real_read_jsonl = cr.read_jsonl

    def _boom(path):
        # Only the spend read fails here -- the rollup-path read (the
        # idempotency check) must stay clean so this test isolates
        # "spend-read-error", not "rollup-read-error" (see the dedicated
        # test for that one below).
        if str(path) == str(spend_path):
            return [], {"skipped_unparseable": 0, "read_error": "PermissionError()"}
        return real_read_jsonl(path)

    monkeypatch.setattr(cr, "read_jsonl", _boom)
    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))
    assert exit_code == 1
    assert payload["outcome"] == "spend-read-error"
    assert not rollup_path.exists()


def test_run_rollup_read_error_is_a_nonzero_exit_not_treated_as_no_dates(tmp_path, monkeypatch):
    """A read ERROR on daily_rollup.jsonl itself (the idempotency check's
    own source of truth) must exit 1, exactly like a spend.jsonl read
    error -- silently treating it as "no dates recorded yet" would let a
    retried run double-append a date that is merely unreadable right now."""
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])
    rollup_path = tmp_path / "daily_rollup.jsonl"
    rollup_path.write_text('{"date": "2026-08-28"}\n')

    import churn_report as cr

    def _boom(path):
        if str(path) == str(rollup_path):
            return [{"date": "2026-08-28"}], {
                "skipped_unparseable": 0,
                "read_error": "PermissionError()",
            }
        return [], {"skipped_unparseable": 0, "read_error": None}

    monkeypatch.setattr(cr, "read_jsonl", _boom)
    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))
    assert exit_code == 1
    assert payload["outcome"] == "rollup-read-error"
    # No new line was appended -- the file is untouched beyond its original content.
    assert rollup_path.read_text() == '{"date": "2026-08-28"}\n'


def test_run_write_path_uses_os_write_loop_not_buffered_append(tmp_path, monkeypatch):
    """BLOCKER 2 (2026-08-30 review): run()'s append must go through an
    os.open/O_APPEND + looped os.write() drain (mirrors
    agent_budget._append_jsonl, "N11, 08-25 round 3"), never a plain
    buffered `open(path, "a")` + `.write()`. A real rollup line can exceed
    Python's ~8KB text buffer (measured 8123 and 9808 bytes on real
    ledger data), so buffered append is guaranteed to issue multiple
    write() syscalls for a normal-sized line -- a mid-write kill (launchd
    sleep/logout) can then leave a permanently truncated line in this
    append-only, unrepairable file.

    Proven here (not just asserted) by monkeypatching `os.write` itself to
    simulate a genuine POSIX-permitted SHORT write (returns fewer bytes
    than requested) and confirming the real write path still lands the
    complete line, having looped to do so. This also directly falsifies a
    regression back to buffered `open(path, "a")`: buffered text-mode IO
    never calls the Python-level `os.write()` symbol at all (its raw
    stream write happens in C, bypassing this binding entirely), so a
    revert makes the short-write mock's call list stay empty and this
    test's `len(calls) > 1` assertion fail.
    """
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    # A large agent_type value pads the serialized line comfortably past
    # an 8KB buffer, matching the measured real-ledger line sizes.
    _write_jsonl(
        spend_path,
        [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1", agent_type="x" * 20000)],
    )

    real_write = os.write
    calls: list[int] = []

    def _short_write(fd, data):
        n = min(len(data), 4096)  # force a short count every call
        calls.append(n)
        return real_write(fd, bytes(data[:n]))

    monkeypatch.setattr(dsr.os, "write", _short_write)
    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))

    assert exit_code == 0
    assert payload["outcome"] == "appended"
    # The short-write mock was exercised more than once -- proves the
    # write path goes through a looped os.write(), not a buffered stream
    # that bypasses this symbol (and would silently trust one call).
    assert len(calls) > 1
    recorded = json.loads(rollup_path.read_text().splitlines()[0])
    assert recorded["date"] == "2026-08-29"
    assert recorded["by_agent_model"][0]["agent_type"] == "x" * 20000


def test_run_rollup_write_error_is_a_nonzero_exit(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])
    # Point the rollup path at a directory that can never be created as a
    # file's parent (a file, not a directory, sitting where a dir is needed).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    rollup_path = blocker / "daily_rollup.jsonl"

    exit_code, payload = dsr.run("2026-08-29", spend_path=str(spend_path), rollup_path=str(rollup_path))
    assert exit_code == 1
    assert payload["outcome"] == "rollup-write-error"


# ===========================================================================
# run_attribution_compaction — F1/P5 (2026-09-01 agentic-systems-architect
# audit): wires spend_attribution.py's own recovery into the daily sweep.
# Every test points meta_roots/output_roots/cache_path at empty tmp dirs so
# NOTHING here ever touches the real ~/.claude/projects tree or the real
# cache file -- purely hermetic, and RED-without-the-fix (the function
# itself is new).
# ===========================================================================


def _empty_roots(tmp_path):
    meta = tmp_path / "meta_roots"
    meta.mkdir()
    output = tmp_path / "output_roots"
    output.mkdir()
    return str(meta), str(output)


def test_run_attribution_compaction_writes_a_sidecar_never_touching_spend_jsonl(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    out_path = tmp_path / "spend_enriched.jsonl"
    cache_path = tmp_path / "cache.json"
    meta, output = _empty_roots(tmp_path)
    rows = [
        _spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1", agent_type="implement"),
        _spend_row(ts="2026-08-29T11:00:00Z", tool_use_id="tu2", agent_type=None, model=None),
    ]
    _write_jsonl(spend_path, rows)
    original_bytes = spend_path.read_bytes()

    exit_code, payload = dsr.run_attribution_compaction(
        spend_path=str(spend_path),
        out_path=str(out_path),
        meta_roots=meta,
        output_roots=output,
        cache_path=str(cache_path),
    )

    assert exit_code == 0
    assert payload["outcome"] == "attribution-compacted"
    assert out_path.exists()
    enriched_lines = out_path.read_text().strip().splitlines()
    assert len(enriched_lines) == 2
    for line in enriched_lines:
        enriched = json.loads(line)
        assert "attribution" in enriched  # the PROVENANCE CONTRACT block
    # spend.jsonl itself is untouched, byte-for-byte.
    assert spend_path.read_bytes() == original_bytes


def test_run_attribution_compaction_refreshes_the_shared_cache(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    out_path = tmp_path / "spend_enriched.jsonl"
    cache_path = tmp_path / "cache.json"
    meta, output = _empty_roots(tmp_path)
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])
    assert not cache_path.exists()

    exit_code, _payload = dsr.run_attribution_compaction(
        spend_path=str(spend_path),
        out_path=str(out_path),
        meta_roots=meta,
        output_roots=output,
        cache_path=str(cache_path),
    )
    assert exit_code == 0
    assert cache_path.exists()  # rebuild_index=True (default) wrote it


def test_run_attribution_compaction_degrades_on_unimportable_module(tmp_path, monkeypatch):
    import daily_spend_rollup as dsr_mod
    import sys as sys_mod

    monkeypatch.setitem(sys_mod.modules, "spend_attribution", None)
    exit_code, payload = dsr_mod.run_attribution_compaction(
        spend_path=str(tmp_path / "spend.jsonl"), out_path=str(tmp_path / "out.jsonl")
    )
    assert exit_code == 1
    assert payload["outcome"] == "attribution-import-error"


def test_run_attribution_compaction_degrades_on_write_failure(tmp_path):
    spend_path = tmp_path / "spend.jsonl"
    meta, output = _empty_roots(tmp_path)
    cache_path = tmp_path / "cache.json"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])
    # An out_path whose parent is a FILE (never a valid directory) forces
    # spend_attribution.py's own --out write to fail.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    bad_out = blocker / "spend_enriched.jsonl"

    exit_code, payload = dsr.run_attribution_compaction(
        spend_path=str(spend_path),
        out_path=str(bad_out),
        meta_roots=meta,
        output_roots=output,
        cache_path=str(cache_path),
    )
    assert exit_code == 1
    assert payload["outcome"] == "attribution-error"


# ===========================================================================
# main() — CLI wiring: default date, --json, exit codes.
# ===========================================================================


def test_main_defaults_date_to_yesterday_utc(tmp_path, monkeypatch):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])

    fixed_now = datetime(2026, 8, 30, 3, 0, 0, tzinfo=timezone.utc)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(dsr, "datetime", _FixedDatetime)

    exit_code = dsr.main(
        [
            "--spend-path", str(spend_path), "--rollup-path", str(rollup_path),
            "--skip-attribution-compaction",
        ]
    )
    assert exit_code == 0
    recorded = json.loads(rollup_path.read_text().splitlines()[0])
    assert recorded["date"] == "2026-08-29"


def test_main_rejects_a_malformed_date_argument(capsys):
    exit_code = dsr.main(["--date", "08/29/2026"])
    assert exit_code == 1
    assert "invalid --date" in capsys.readouterr().out


def test_main_rejects_a_calendar_invalid_date_argument(capsys):
    """Shape-valid (YYYY-MM-DD) but calendar-invalid -- the old regex-only
    check would have let this through."""
    exit_code = dsr.main(["--date", "2026-02-30"])
    assert exit_code == 1
    assert "invalid --date" in capsys.readouterr().out


def test_main_refuses_todays_date_without_override(tmp_path, capsys, monkeypatch):
    fixed_now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(dsr, "datetime", _FixedDatetime)

    rollup_path = tmp_path / "daily_rollup.jsonl"
    exit_code = dsr.main(["--date", "2026-08-30", "--rollup-path", str(rollup_path)])
    assert exit_code == 1
    assert "today or in the future" in capsys.readouterr().out
    assert not rollup_path.exists()


def test_main_allows_todays_date_with_allow_partial_day_override(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(dsr, "datetime", _FixedDatetime)

    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-30T10:00:00Z", tool_use_id="tu1")])

    exit_code = dsr.main(
        [
            "--date",
            "2026-08-30",
            "--allow-partial-day",
            "--spend-path",
            str(spend_path),
            "--rollup-path",
            str(rollup_path),
            "--skip-attribution-compaction",
        ]
    )
    assert exit_code == 0
    recorded = json.loads(rollup_path.read_text().splitlines()[0])
    assert recorded["date"] == "2026-08-30"


def test_main_json_flag_prints_full_payload(tmp_path, capsys):
    spend_path = tmp_path / "spend.jsonl"
    rollup_path = tmp_path / "daily_rollup.jsonl"
    enriched_path = tmp_path / "spend_enriched.jsonl"
    empty_meta = tmp_path / "meta_roots"
    empty_meta.mkdir()
    empty_output = tmp_path / "output_roots"
    empty_output.mkdir()
    cache_path = tmp_path / "attribution_cache.json"
    _write_jsonl(spend_path, [_spend_row(ts="2026-08-29T10:00:00Z", tool_use_id="tu1")])

    exit_code = dsr.main(
        [
            "--date",
            "2026-08-29",
            "--spend-path",
            str(spend_path),
            "--rollup-path",
            str(rollup_path),
            "--enriched-path",
            str(enriched_path),
            "--meta-roots",
            str(empty_meta),
            "--output-roots",
            str(empty_output),
            "--attribution-cache-path",
            str(cache_path),
            "--json",
        ]
    )
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "appended"
    # F1/P5: the attribution-compaction pass ran (hermetically) alongside
    # the rollup append, and its outcome rides along in the JSON payload.
    assert out["attribution_compaction"]["outcome"] == "attribution-compacted"
    assert enriched_path.exists()
    assert out["line"]["date"] == "2026-08-29"
