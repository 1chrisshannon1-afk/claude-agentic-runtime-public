"""Hermetic, falsifiable tests for hooks/delivery_report.py.

Every test builds its own small fixture (synthetic ledgers under `tmp_path`,
or plain in-memory lists/dicts passed straight to the pure functions, or a
stubbed `git_log_fn`) -- the real ~/.claude ledgers and the real git checkout
are NEVER read here, per the spawning task. No test shells out to a real
`git log`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import delivery_report as dr

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


def _write_lines(path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


# ===========================================================================
# Metric 1 -- commits/day per registered repo.
# ===========================================================================


def test_load_repo_registry_reads_slug_to_expanded_root(tmp_path):
    reg = tmp_path / "repo_registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "repos": {"myapp": {"root": "~/Desktop/MyApp"}}}))
    out = dr.load_repo_registry(str(reg))
    assert "myapp" in out
    assert out["myapp"].endswith("/Desktop/MyApp")
    assert "~" not in out["myapp"]


def test_load_repo_registry_missing_file_degrades_to_empty_dict():
    assert dr.load_repo_registry("/nonexistent/registry.json") == {}


def test_load_repo_registry_skips_entry_with_no_root_string():
    import os

    # A malformed entry (root missing / not a string) must be skipped, not crash.
    tmp = os.path.join(os.path.dirname(__file__), "_scratch_registry.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"repos": {"bad": {}, "good": {"root": "/tmp/good"}}}, fh)
    try:
        out = dr.load_repo_registry(tmp)
        assert "bad" not in out
        assert out["good"] == "/tmp/good"
    finally:
        os.remove(tmp)


def test_commits_per_day_counts_and_averages():
    registry = {"appone": "/repos/appone"}

    def fake_git_log(root, days, now):
        assert root == "/repos/appone"
        return ["2026-09-01", "2026-09-01", "2026-09-02", "2026-09-03"]

    result = dr.commits_per_day(registry, days=4, now=_NOW, git_log_fn=fake_git_log)
    assert result["by_repo"]["appone"]["commits"] == 4
    assert result["by_repo"]["appone"]["commits_per_day"] == 1.0
    assert result["total_commits"] == 4
    assert result["repo_errors"] == {}


def test_commits_per_day_reports_repo_error_never_silently_drops_it():
    registry = {"broken": "/no/such/repo"}

    def fake_git_log(root, days, now):
        return None  # not a readable checkout

    result = dr.commits_per_day(registry, days=7, now=_NOW, git_log_fn=fake_git_log)
    assert result["by_repo"] == {}
    assert "broken" in result["repo_errors"]
    assert result["total_commits"] == 0


def test_commits_per_day_zero_commits_is_zero_not_absent():
    registry = {"quiet": "/repos/quiet"}

    def fake_git_log(root, days, now):
        return []

    result = dr.commits_per_day(registry, days=7, now=_NOW, git_log_fn=fake_git_log)
    assert result["by_repo"]["quiet"]["commits"] == 0
    assert result["by_repo"]["quiet"]["commits_per_day"] == 0.0


def test_build_report_commits_absent_when_no_repos_registered(tmp_path):
    reg = tmp_path / "repo_registry.json"
    reg.write_text(json.dumps({"repos": {}}))
    report = dr.build_report(days=7, now=_NOW, registry_path=str(reg))
    assert report["commits_per_day"]["status"] == "absent"


# ===========================================================================
# Metric 2 -- review rounds per boundary.
# ===========================================================================


def _lr_line(repo: str, key: str, outcome: str, ts: str, round_n: int, prev: str | None = None) -> str:
    fields = f"ts={ts} round={round_n}"
    if prev:
        fields += f" prev={prev}"
    return f"{repo} {key} {outcome} {fields}"


def test_review_rounds_single_round_boundaries_average_to_one():
    lines = [
        _lr_line("/r", "precommit:aaa", "clean", "2026-09-01T10:00:00Z", 1),
        _lr_line("/r", "precommit:bbb", "clean", "2026-09-02T10:00:00Z", 1),
    ]
    result = dr.review_rounds_per_boundary(lines, days=7, now=_NOW)
    assert result["boundaries"] == 2
    assert result["mean_rounds"] == 1.0
    assert result["max_rounds"] == 1


def test_review_rounds_chain_via_prev_counts_as_one_boundary_at_max_round():
    # A 3-round fix chain: round1 -> round2 (prev=round1) -> round3 (prev=round2).
    lines = [
        _lr_line("/r", "precommit:aaa", "blockers:2", "2026-09-01T10:00:00Z", 1),
        _lr_line("/r", "precommit:bbb", "blockers:1", "2026-09-01T11:00:00Z", 2, prev="precommit:aaa"),
        _lr_line("/r", "precommit:ccc", "clean", "2026-09-01T12:00:00Z", 3, prev="precommit:bbb"),
    ]
    result = dr.review_rounds_per_boundary(lines, days=7, now=_NOW)
    # All three lines collapse to ONE boundary (one chain), at its max round (3) --
    # a naive implementation that counted every line as its own boundary would
    # report boundaries=3, mean_rounds=2.0 instead. This assertion is what goes
    # RED under that naive (wrong) implementation.
    assert result["boundaries"] == 1
    assert result["mean_rounds"] == 3.0
    assert result["max_rounds"] == 3


def test_review_rounds_mixes_single_and_multi_round_boundaries():
    lines = [
        _lr_line("/r", "precommit:x1", "clean", "2026-09-01T10:00:00Z", 1),
        _lr_line("/r", "precommit:y1", "blockers:1", "2026-09-01T10:00:00Z", 1),
        _lr_line("/r", "precommit:y2", "clean", "2026-09-01T11:00:00Z", 2, prev="precommit:y1"),
    ]
    result = dr.review_rounds_per_boundary(lines, days=7, now=_NOW)
    assert result["boundaries"] == 2
    assert result["mean_rounds"] == 1.5  # (1 + 2) / 2
    assert result["max_rounds"] == 2


def test_review_rounds_no_entries_in_window_is_none_not_zero():
    lines = [_lr_line("/r", "precommit:old", "clean", "2026-01-01T00:00:00Z", 1)]
    result = dr.review_rounds_per_boundary(lines, days=7, now=_NOW)
    assert result["boundaries"] == 0
    assert result["mean_rounds"] is None
    assert result["max_rounds"] is None


def test_review_rounds_entry_missing_ts_is_never_dropped_fails_open():
    # No ts= field at all (legacy shape) -- must still be counted, mirroring
    # churn_report.within_days's "unparseable ts is always True" contract.
    lines = ["/r precommit:legacy clean"]
    result = dr.review_rounds_per_boundary(lines, days=7, now=_NOW)
    assert result["boundaries"] == 1


def test_build_report_review_rounds_absent_when_ledger_missing(tmp_path):
    report = dr.build_report(days=7, now=_NOW, last_reviewed_path=str(tmp_path / "nope"))
    assert report["review_rounds"]["status"] == "absent"


# ===========================================================================
# Metric 3 -- gate-denial trend by day.
# ===========================================================================


def _log_line(ts: str, decision: str, hook: str = "pretooluse_bash") -> dict:
    return {"ts": ts, "hook": hook, "decision": decision, "enforce": True}


def test_gate_denials_by_day_counts_only_real_gate_hooks():
    rows = [
        _log_line("2026-09-01T10:00:00Z", "would-block", hook="pretooluse_bash"),
        _log_line("2026-09-01T11:00:00Z", "would-block", hook="pretooluse_bash"),
        _log_line("2026-09-02T10:00:00Z", "deny", hook="gh_issue_close_gate"),
        # Not a gate hook -- must be excluded, not counted.
        _log_line("2026-09-02T10:05:00Z", "would-block", hook="some_other_thing"),
        # Not a denial decision -- must be excluded.
        _log_line("2026-09-02T10:06:00Z", "allow", hook="pretooluse_bash"),
    ]
    result = dr.gate_denials_by_day(rows, days=7, now=_NOW)
    assert result["by_day"] == {"2026-09-01": 2, "2026-09-02": 1}
    assert result["total_denials"] == 3


def test_gate_denials_by_day_respects_window():
    rows = [
        _log_line("2026-08-01T10:00:00Z", "would-block"),  # outside a 7-day window
        _log_line("2026-09-03T10:00:00Z", "would-block"),
    ]
    result = dr.gate_denials_by_day(rows, days=7, now=_NOW)
    assert result["total_denials"] == 1


def test_build_report_gate_denials_absent_when_log_missing(tmp_path):
    report = dr.build_report(days=7, now=_NOW, enforcement_log_path=str(tmp_path / "nope"))
    assert report["gate_denials"]["status"] == "absent"


# ===========================================================================
# Metric 4 -- dispatch volume (spend.jsonl unioned with daily_rollup.jsonl).
# ===========================================================================


def _spend_line(ts: str) -> dict:
    return {"ts": ts, "agent_type": "implement", "tokens_total": 10}


def _rollup_line(date: str, dispatches: int) -> dict:
    return {"date": date, "dispatches": dispatches, "tokens_total": 1000}


def test_dispatch_volume_rollup_wins_over_spend_on_same_day():
    # spend.jsonl only has 2 rows visible for 2026-09-01 (its retention window
    # rolled the rest off), but the rollup recorded the real total (830) for
    # that day -- the rollup's number must win, not the truncated spend count.
    spend_rows = [_spend_line("2026-09-01T10:00:00Z"), _spend_line("2026-09-01T11:00:00Z")]
    rollup_rows = [_rollup_line("2026-09-01", 830)]
    result = dr.dispatch_volume(spend_rows, rollup_rows, days=7, now=_NOW)
    assert result["by_day"]["2026-09-01"] == 830
    assert "2026-09-01" in result["days_from_rollup"]


def test_dispatch_volume_spend_only_day_counted_when_no_rollup_row():
    spend_rows = [_spend_line("2026-09-03T10:00:00Z"), _spend_line("2026-09-03T11:00:00Z")]
    result = dr.dispatch_volume(spend_rows, [], days=7, now=_NOW)
    assert result["by_day"]["2026-09-03"] == 2
    assert "2026-09-03" in result["days_from_spend_only"]


def test_dispatch_volume_total_and_mean():
    rollup_rows = [_rollup_line("2026-09-01", 100), _rollup_line("2026-09-02", 200)]
    result = dr.dispatch_volume([], rollup_rows, days=7, now=_NOW)
    assert result["total_dispatches"] == 300
    assert result["mean_per_day"] == round(300 / 7, 2)


def test_build_report_dispatch_volume_absent_when_both_ledgers_missing(tmp_path):
    report = dr.build_report(
        days=7,
        now=_NOW,
        spend_path=str(tmp_path / "nope1"),
        daily_rollup_path=str(tmp_path / "nope2"),
    )
    assert report["dispatch_volume"]["status"] == "absent"


# ===========================================================================
# End-to-end build_report / CLI.
# ===========================================================================


def test_build_report_every_metric_key_present_when_all_ledgers_absent(tmp_path):
    report = dr.build_report(
        days=7,
        now=_NOW,
        registry_path=str(tmp_path / "reg.json"),
        last_reviewed_path=str(tmp_path / "lr"),
        enforcement_log_path=str(tmp_path / "log"),
        spend_path=str(tmp_path / "spend"),
        daily_rollup_path=str(tmp_path / "rollup"),
    )
    for key in ("commits_per_day", "review_rounds", "gate_denials", "dispatch_volume"):
        assert key in report
        assert report[key]["status"] == "absent"


def test_build_report_end_to_end_with_real_fixture_files(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"repos": {"app": {"root": str(tmp_path / "app_repo")}}}))
    (tmp_path / "app_repo").mkdir()

    lr = tmp_path / "last_reviewed"
    _write_lines(lr, [_lr_line("/r", "precommit:one", "clean", "2026-09-02T10:00:00Z", 1)])

    log = tmp_path / "log.jsonl"
    _write_jsonl(log, [_log_line("2026-09-02T10:00:00Z", "would-block")])

    spend = tmp_path / "spend.jsonl"
    _write_jsonl(spend, [_spend_line("2026-09-03T10:00:00Z")])

    rollup = tmp_path / "rollup.jsonl"
    _write_jsonl(rollup, [_rollup_line("2026-09-01", 42)])

    def fake_git_log(root, days, now):
        return ["2026-09-01"]

    report = dr.build_report(
        days=7,
        now=_NOW,
        registry_path=str(reg),
        last_reviewed_path=str(lr),
        enforcement_log_path=str(log),
        spend_path=str(spend),
        daily_rollup_path=str(rollup),
        git_log_fn=fake_git_log,
    )
    assert report["commits_per_day"]["status"] == "ok"
    assert report["commits_per_day"]["total_commits"] == 1
    assert report["review_rounds"]["status"] == "ok"
    assert report["review_rounds"]["boundaries"] == 1
    assert report["gate_denials"]["status"] == "ok"
    assert report["gate_denials"]["total_denials"] == 1
    assert report["dispatch_volume"]["status"] == "ok"
    assert report["dispatch_volume"]["total_dispatches"] == 43  # 1 (spend) + 42 (rollup)

    # render_table must not raise on a fully-populated report, and must
    # mention every metric section by name.
    table = dr.render_table(report)
    assert "commits/day" in table
    assert "review rounds" in table
    assert "gate denials" in table
    assert "dispatch volume" in table


def test_build_report_never_writes_any_ledger(tmp_path):
    # Read-only contract: build_report must not create/modify any of the
    # files it's pointed at, even ones that don't yet exist.
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"repos": {}}))
    lr = tmp_path / "lr_absent"
    log = tmp_path / "log_absent"
    spend = tmp_path / "spend_absent"
    rollup = tmp_path / "rollup_absent"
    dr.build_report(
        days=7,
        now=_NOW,
        registry_path=str(reg),
        last_reviewed_path=str(lr),
        enforcement_log_path=str(log),
        spend_path=str(spend),
        daily_rollup_path=str(rollup),
    )
    assert not lr.exists()
    assert not log.exists()
    assert not spend.exists()
    assert not rollup.exists()


def test_parse_args_defaults_and_days_override():
    days, as_json = dr.parse_args([])
    assert days == dr.DEFAULT_DAYS
    assert as_json is False
    days, as_json = dr.parse_args(["--days", "30", "--json"])
    assert days == 30
    assert as_json is True


def test_parse_args_rejects_non_positive_days():
    import pytest

    with pytest.raises(dr.ArgError):
        dr.parse_args(["--days", "0"])


def test_main_json_output_is_valid_json(tmp_path, capsys):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"repos": {}}))

    real_registry = dr.REPO_REGISTRY_PATH
    try:
        dr.REPO_REGISTRY_PATH = str(reg)
        rc = dr.main(["--json"])
    finally:
        dr.REPO_REGISTRY_PATH = real_registry
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "commits_per_day" in parsed
