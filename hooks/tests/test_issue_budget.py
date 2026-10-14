"""Tests for scripts/issue_budget.py (#5827, master plan
WS1 Phase D — "Creation quality gate + promotion budget (observer-first)").

Runs the real, tracked script as a subprocess against a FAKE `gh` on PATH
(via ISSUE_BUDGET_GH_BIN, mirroring scripts/priority_backfill.py's own
PRIORITY_BACKFILL_GH_BIN convention) so this suite makes ZERO real GitHub
calls and never touches the real ~/.claude state. The script is read-only by
design (it promotes nothing), so there is no board-mutation safety contract
to test the way test_priority_backfill.py's B1 guard does for that script —
only that this script's own `gh issue list` invocation, JSON parsing, window
filtering, and budget arithmetic are correct.

Also exercises the PURE functions directly (compute_budget, filter_window,
count_by_state_reason) for fast, no-subprocess unit coverage of the formula
itself — the spec asserted here is the plan's own formula text, not whatever
the first implementation happened to compute.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REAL_SCRIPT = Path.home() / ".claude" / "scripts" / "issue_budget.py"

# --------------------------------------------------------------------------
# Direct import of the pure functions (read-only script; no write-safety
# contract to protect, unlike priority_backfill.py -- importing it directly
# is safe here).
# --------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location("issue_budget_under_test", REAL_SCRIPT)
ib = importlib.util.module_from_spec(_spec)
sys.modules["issue_budget_under_test"] = ib
_spec.loader.exec_module(ib)


# ---------------------------------------------------------------------------
# Pure unit tests — the formula itself.
# ---------------------------------------------------------------------------


class TestComputeBudget:
    def test_floor_applies_when_closes_are_low(self):
        # round(2/14) = 0 -> floor to MIN_DAILY_BUDGET (5).
        assert ib.compute_budget(2, window_days=14) == 5

    def test_floor_applies_at_zero_closes(self):
        assert ib.compute_budget(0, window_days=14) == 5

    def test_above_floor_rounds_to_nearest(self):
        # round(100/14) = round(7.14...) = 7.
        assert ib.compute_budget(100, window_days=14) == 7

    def test_exact_multiple(self):
        assert ib.compute_budget(70, window_days=14) == 5  # round(70/14)=5, at the floor exactly

    def test_high_volume_well_above_floor(self):
        assert ib.compute_budget(280, window_days=14) == 20

    def test_zero_window_days_raises(self):
        try:
            ib.compute_budget(10, window_days=0)
            assert False, "expected IssueBudgetError"
        except ib.IssueBudgetError:
            pass

    def test_negative_window_days_raises(self):
        try:
            ib.compute_budget(10, window_days=-1)
            assert False, "expected IssueBudgetError"
        except ib.IssueBudgetError:
            pass


class TestCountByStateReason:
    def test_completed_and_not_planned_split(self):
        issues = [
            {"number": 1, "stateReason": "COMPLETED"},
            {"number": 2, "stateReason": "COMPLETED"},
            {"number": 3, "stateReason": "NOT_PLANNED"},
        ]
        completed, not_planned, unknown = ib.count_by_state_reason(issues)
        assert (completed, not_planned, unknown) == (2, 1, 0)

    def test_unknown_reason_bucketed_separately_never_folded_in(self):
        issues = [
            {"number": 1, "stateReason": "COMPLETED"},
            {"number": 2, "stateReason": None},
            {"number": 3, "stateReason": "SOME_FUTURE_VALUE"},
            {"number": 4},  # key entirely absent
        ]
        completed, not_planned, unknown = ib.count_by_state_reason(issues)
        assert (completed, not_planned, unknown) == (1, 0, 3)

    def test_empty_list(self):
        assert ib.count_by_state_reason([]) == (0, 0, 0)

    def test_never_sums_not_planned_into_completed(self):
        issues = [{"stateReason": "NOT_PLANNED"} for _ in range(50)]
        completed, not_planned, unknown = ib.count_by_state_reason(issues)
        assert completed == 0
        assert not_planned == 50
        # And the budget computed from `completed` alone must floor, never
        # be inflated by the 50 not-planned closes.
        assert ib.compute_budget(completed, window_days=14) == 5


class TestFilterWindow:
    def test_within_window_included(self):
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        issues = [{"number": 1, "closedAt": "2026-09-15T00:00:00Z"}]
        out = ib.filter_window(issues, window_start=now - timedelta(days=14), window_end=now)
        assert len(out) == 1

    def test_outside_window_excluded(self):
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        issues = [{"number": 1, "closedAt": "2026-08-01T00:00:00Z"}]
        out = ib.filter_window(issues, window_start=now - timedelta(days=14), window_end=now)
        assert out == []

    def test_missing_closed_at_excluded_never_guessed(self):
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        issues = [{"number": 1}, {"number": 2, "closedAt": None}, {"number": 3, "closedAt": ""}]
        out = ib.filter_window(issues, window_start=now - timedelta(days=14), window_end=now)
        assert out == []

    def test_malformed_closed_at_excluded(self):
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        issues = [{"number": 1, "closedAt": "not-a-date"}]
        out = ib.filter_window(issues, window_start=now - timedelta(days=14), window_end=now)
        assert out == []

    def test_boundary_inclusive(self):
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        start = now - timedelta(days=14)
        issues = [
            {"number": 1, "closedAt": start.strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"number": 2, "closedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        out = ib.filter_window(issues, window_start=start, window_end=now)
        assert len(out) == 2


class TestValidateRepo:
    def test_valid_repo_passes(self):
        assert ib._validate_repo("acme/widgets") == "acme/widgets"

    def test_missing_slash_raises(self):
        try:
            ib._validate_repo("acme")
            assert False, "expected IssueBudgetError"
        except ib.IssueBudgetError:
            pass

    def test_empty_repo_raises(self):
        try:
            ib._validate_repo("")
            assert False, "expected IssueBudgetError"
        except ib.IssueBudgetError:
            pass

    def test_empty_owner_or_name_raises(self):
        for bad in ("/widgets", "acme/", "/"):
            try:
                ib._validate_repo(bad)
                assert False, f"expected IssueBudgetError for {bad!r}"
            except ib.IssueBudgetError:
                pass


# ---------------------------------------------------------------------------
# Subprocess end-to-end tests — real script, fake `gh`.
# ---------------------------------------------------------------------------

_FAKE_GH_TEMPLATE = r"""#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
log_path = os.environ.get("FAKE_GH_ARGV_LOG")
if log_path:
    with open(log_path, "a") as lf:
        lf.write(json.dumps(args) + "\n")
if args[:3] == ["issue", "list", "--repo"]:
    payload_path = os.environ["FAKE_ISSUES_JSON"]
    with open(payload_path) as f:
        print(f.read())
    sys.exit(0)
print(f"fake gh: unhandled args {args!r}", file=sys.stderr)
sys.exit(1)
"""


def _make_fake_gh(tmp_path: Path, issues: list[dict]) -> dict:
    gh = tmp_path / "fake_gh.py"
    gh.write_text(_FAKE_GH_TEMPLATE)
    gh.chmod(0o755)
    issues_json = tmp_path / "issues.json"
    issues_json.write_text(json.dumps(issues))
    argv_log = tmp_path / "gh_argv.log"
    argv_log.write_text("")
    env = dict(os.environ)
    # ISSUE_BUDGET_GH_BIN is the [GH_BIN, "issue", "list", ...] argv[0] the
    # real script builds -- point it directly at the fake script's own
    # shebang-exec path (it is chmod +x with a `#!/usr/bin/env python3`
    # shebang), never at the python interpreter itself.
    env["ISSUE_BUDGET_GH_BIN"] = str(gh)
    env["FAKE_ISSUES_JSON"] = str(issues_json)
    env["FAKE_GH_ARGV_LOG"] = str(argv_log)
    return env


def _argv_log_lines(env: dict) -> list[list[str]]:
    path = Path(env["FAKE_GH_ARGV_LOG"])
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _run(tmp_path: Path, issues: list[dict], *args: str) -> subprocess.CompletedProcess:
    env = _make_fake_gh(tmp_path, issues)
    return subprocess.run(
        [sys.executable, str(REAL_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _issue(num: int, days_ago: int, reason: str) -> dict:
    closed_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {"number": num, "closedAt": closed_at, "stateReason": reason}


def test_missing_repo_flag_is_argparse_error(tmp_path):
    env = _make_fake_gh(tmp_path, [])
    proc = subprocess.run(
        [sys.executable, str(REAL_SCRIPT)], capture_output=True, text=True, env=env, timeout=30
    )
    assert proc.returncode != 0
    assert "--repo" in proc.stderr


def test_invalid_repo_shape_refuses(tmp_path):
    proc = _run(tmp_path, [], "--repo", "not-a-valid-repo")
    assert proc.returncode == 1
    assert "OWNER/NAME" in proc.stderr


def test_low_volume_repo_floors_at_five(tmp_path):
    issues = [_issue(1, 2, "COMPLETED"), _issue(2, 5, "COMPLETED")]
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["daily_promote_budget"] == 5
    assert payload["completed_closes"] == 2
    assert payload["not_planned_closes"] == 0


def test_not_planned_closes_reported_but_never_counted_in_budget(tmp_path):
    issues = [_issue(n, 3, "NOT_PLANNED") for n in range(1, 51)]  # 50 not-planned
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["completed_closes"] == 0
    assert payload["not_planned_closes"] == 50
    assert payload["daily_promote_budget"] == 5  # floor, not inflated by 50 NOT_PLANNED


def test_high_volume_repo_computes_above_floor(tmp_path):
    # 280 completed closes over 14 days -> round(280/14) = 20.
    issues = [_issue(n, n % 14, "COMPLETED") for n in range(1, 281)]
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["daily_promote_budget"] == 20
    assert payload["completed_closes"] == 280


def test_closes_outside_window_excluded_from_count(tmp_path):
    issues = [_issue(1, 3, "COMPLETED"), _issue(2, 30, "COMPLETED")]  # one outside 14d window
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["completed_closes"] == 1


def test_text_output_names_both_counts_and_bypass_rule(tmp_path):
    issues = [_issue(1, 2, "COMPLETED"), _issue(2, 4, "NOT_PLANNED")]
    proc = _run(tmp_path, issues, "--repo", "acme/widgets")
    assert proc.returncode == 0, proc.stderr
    assert "daily_promote_budget" in proc.stdout
    assert "completed_closes" in proc.stdout
    assert "not_planned_closes" in proc.stdout
    assert "P0/P1 bypass" in proc.stdout
    assert "SELF-REFERENTIAL" in proc.stdout


def test_custom_window_days_respected(tmp_path):
    issues = [_issue(1, 3, "COMPLETED"), _issue(2, 10, "COMPLETED")]  # both within 30d
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--window-days", "30", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["window_days"] == 30
    assert payload["completed_closes"] == 2


def test_gh_failure_exits_nonzero_with_clear_message(tmp_path):
    gh = tmp_path / "failing_gh.py"
    gh.write_text(
        "#!/usr/bin/env python3\nimport sys\nprint('boom', file=sys.stderr)\nsys.exit(1)\n"
    )
    gh.chmod(0o755)
    env = dict(os.environ)
    env["ISSUE_BUDGET_GH_BIN"] = str(gh)
    proc = subprocess.run(
        [sys.executable, str(REAL_SCRIPT), "--repo", "acme/widgets"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 1
    assert "boom" in proc.stderr


def test_unparseable_json_exits_nonzero(tmp_path):
    gh = tmp_path / "garbage_gh.py"
    gh.write_text("#!/usr/bin/env python3\nprint('not json at all')\n")
    gh.chmod(0o755)
    env = dict(os.environ)
    env["ISSUE_BUDGET_GH_BIN"] = str(gh)
    proc = subprocess.run(
        [sys.executable, str(REAL_SCRIPT), "--repo", "acme/widgets"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 1
    assert "unparseable" in proc.stderr.lower()


def test_never_promotes_anything_no_write_flags_exist(tmp_path):
    # Structural guarantee: this script's argparse surface has no --apply /
    # --promote / any write-shaped flag at all.
    proc = subprocess.run(
        [sys.executable, str(REAL_SCRIPT), "--help"], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0
    for forbidden in ("--apply", "--promote", "--write", "--move"):
        assert forbidden not in proc.stdout


# ---------------------------------------------------------------------------
# Fix-round 1, finding 8: `gh issue list` sorts by CREATED, not CLOSED --
# pass `--search "sort:updated-desc"`, and refuse (never silently truncate)
# when the returned count hits `--limit` exactly.
# ---------------------------------------------------------------------------


def test_sort_updated_desc_search_flag_is_passed(tmp_path):
    env = _make_fake_gh(tmp_path, [_issue(1, 2, "COMPLETED")])
    proc = subprocess.run(
        [sys.executable, str(REAL_SCRIPT), "--repo", "acme/widgets"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    calls = _argv_log_lines(env)
    assert len(calls) == 1
    argv = calls[0]
    assert "--search" in argv
    assert argv[argv.index("--search") + 1] == "sort:updated-desc"


def test_hitting_the_limit_cap_exactly_refuses_never_silently_truncates(tmp_path):
    # limit defaults to 1000 in fetch_closed_issues; build exactly that many
    # fake closed issues so the fake gh returns a count == limit.
    issues = [_issue(n, n % 14, "COMPLETED") for n in range(1, 1001)]
    proc = _run(tmp_path, issues, "--repo", "acme/widgets")
    assert proc.returncode == 1
    assert "hitting the --limit" in proc.stderr
    assert "1000" in proc.stderr


def test_one_below_the_limit_cap_succeeds_normally(tmp_path):
    # PAIRED RECOVERY: one fewer than the cap succeeds normally -- proves
    # the refusal is genuinely keyed to "== limit", not an off-by-one that
    # would refuse everything.
    issues = [_issue(n, n % 14, "COMPLETED") for n in range(1, 1000)]
    proc = _run(tmp_path, issues, "--repo", "acme/widgets", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["completed_closes"] == 999
