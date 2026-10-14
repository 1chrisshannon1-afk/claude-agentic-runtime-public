"""Tests for scripts/priority_backfill.py (plan_lane_control_adoption_master_2026_09_20.md
§2 Phase A / finding F12, plus two fix rounds: round 1 (B1 per-write logging, B2 cross-repo
safety, B3 resumable reverse, B4 partial-comment-failure handling) and round 2 (B1: never
mutate the live tracked script from a test; B2: authorship-aware reverse against a
deliberate human edit; robustness items 3-9).

SAFETY CONTRACT (round-2 B1 — the reason this file's own header comment now leads with it):
No test in this module EVER opens `~/.claude/scripts/priority_backfill.py` for writing. The
ONE test that needs to run a deliberately-broken copy of the script to prove a falsifiability
claim (`test_transition_failure_is_real_red_without_the_raise`) copies the REAL script to a
throwaway `tmp_path` location FIRST, mutates ONLY that copy, and runs the copy as the
subprocess — the real, tracked file is never opened for writing by this test file at all. A
session-scoped fixture (`_verify_real_script_unchanged`) hashes the real script at collection
time and re-hashes it at the end of the test session, failing loudly if anything in this
process ever touched it — a structural guarantee, not just a promise in a docstring.

Runs the real script (or, for the one test above, a private copy of it) as a subprocess against
a FAKE `gh` and a FAKE `gh_issue.sh` on PATH via env overrides (PRIORITY_BACKFILL_GH_BIN,
PRIORITY_BACKFILL_GH_ISSUE_SH) so nothing ever reaches GitHub. CLAUDE_DIR is also repointed at a
tmp dir so ~/.claude/.board_state is never touched by a test run.

Tests assert the SPEC (this script's own module docstring / the plan's Phase A.2 mapping table /
the fix-round blockers), not whatever the first implementation happened to print.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REAL_SCRIPT = Path.home() / ".claude" / "scripts" / "priority_backfill.py"

DEFAULT_REPO = "acme/widgets"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Round-2 B1: a session-scoped guard that fails loudly if the REAL tracked
# script's bytes ever change during this test session, for any reason. Taken
# at collection time (session start) and compared again at session end.
# --------------------------------------------------------------------------

_REAL_SCRIPT_SHA_AT_START = _sha256(REAL_SCRIPT)


@pytest.fixture(scope="session", autouse=True)
def _verify_real_script_unchanged():
    yield
    after = _sha256(REAL_SCRIPT)
    assert after == _REAL_SCRIPT_SHA_AT_START, (
        "priority_backfill.py's REAL tracked bytes changed during this test session — "
        "no test in this module may ever write to the real script file (round-2 B1). "
        f"before={_REAL_SCRIPT_SHA_AT_START} after={after}"
    )


# --------------------------------------------------------------------------
# Fake `gh` — serves every read call priority_backfill.py makes:
#   gh issue list --repo ... --state open --json number
#   gh project item-list <N> --owner ...
#   gh repo view --json nameWithOwner            (B2 CWD-repo check)
#   gh project view <N> --owner ... --format json          (restore-to-empty)
#   gh project field-list <N> --owner ... --format json    (restore-to-empty)
#   gh project item-edit --id ... --field-id ... --project-id ... --clear
# --------------------------------------------------------------------------

# Serves `gh issue view <n> --json id,url` and `gh api graphql ...` (the
# rateLimit budget query AND the per-issue LIVE FIELD CHECK query --from-plan/
# reverse now use instead of a full `gh project item-list` board read).
# Written in Python (via $FAKE_GH_PYTHON, set to sys.executable -- the same
# interpreter running pytest, so it is always present) rather than bash+jq,
# since answering a GraphQL query correctly from the same
# FAKE_GH_PROJECT_ITEMS_JSON fixture the rest of this harness already uses
# is squarely JSON-shape logic. Reads FAKE_GH_RATE_LIMIT_REMAINING (a
# counter file, decremented once per call so a test can observe the
# before/after cost line) and FAKE_GH_RATE_LIMIT_FAIL (if set, the budget
# query itself fails, simulating BUDGET AWARENESS's fail-closed path).
_GH_GRAPHQL_HELPER = """
import json, os, re, sys

def _load(path):
    with open(path) as f:
        return json.load(f)

args = sys.argv[1:]

if args[:2] == ["issue", "view"]:
    num = int(args[2])
    # `state` mirrors FAKE_GH_OPEN_ISSUES_JSON -- the SAME fixture the
    # legacy (full-read) path already uses for its own open/closed
    # distinction via `gh issue list --state open` (a flat list of
    # {"number": n} objects — see _make_env), so a test that marks an issue
    # open/closed via `open_numbers=` gets consistent behavior on BOTH the
    # legacy path and the --from-plan / reverse live-check path.
    open_numbers = {r["number"] for r in _load(os.environ["FAKE_GH_OPEN_ISSUES_JSON"])}
    state = "OPEN" if num in open_numbers else "CLOSED"
    # Issue not on the board fixture at all is still resolvable by number
    # (a real `gh issue view` works for any open issue, board membership is
    # a separate question) -- synthesize a stable node id from the number
    # either way.
    print(json.dumps({"id": f"ISSUE_NODE_{num}", "url": f"https://github.com/x/{num}", "state": state}))
    sys.exit(0)

if args[:2] == ["api", "graphql"]:
    kv = {}
    i = 0
    while i < len(args):
        if args[i] == "-f" and i + 1 < len(args):
            k, _, v = args[i + 1].partition("=")
            kv[k] = v
            i += 2
        else:
            i += 1
    query = kv.get("query", "")

    counter_path = os.environ.get("FAKE_GH_RATE_LIMIT_COUNTER")
    if counter_path:
        # flock-guarded read-modify-write: the REAL GitHub rateLimit
        # endpoint is atomic server-side; this fake must not introduce its
        # OWN torn-read/lost-update race (observed as a flaky test failure
        # when two real subprocesses race this file concurrently -- see
        # test_b4_two_real_concurrent_processes_never_double_write) as an
        # artifact of the test harness rather than of the real script.
        import fcntl as _fcntl
        with open(counter_path, "r+") as f:
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
            remaining = int(f.read().strip())
            remaining -= 1
            f.seek(0)
            f.truncate()
            f.write(str(remaining))
            f.flush()
            _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
    else:
        remaining = int(os.environ.get("FAKE_GH_RATE_LIMIT_REMAINING", "5000"))

    if "rateLimit" in query:
        if os.environ.get("FAKE_GH_RATE_LIMIT_FAIL"):
            print("fake gh: forced rate-limit query failure", file=sys.stderr)
            sys.exit(1)
        print(json.dumps({"data": {"rateLimit": {"remaining": remaining, "resetAt": "2026-09-21T00:00:00Z"}}}))
        sys.exit(0)

    # The LIVE FIELD CHECK query: node id -> projectItems -> fieldValueByName.
    node_id = kv.get("id", "")
    field = kv.get("field", "")
    m = re.match(r"ISSUE_NODE_(\\d+)", node_id)
    if not m:
        print(json.dumps({"data": {"node": None}}))
        sys.exit(0)
    num = int(m.group(1))
    items = _load(os.environ["FAKE_GH_PROJECT_ITEMS_JSON"]).get("items", [])
    nodes = []
    for it in items:
        content = it.get("content", {})
        if content.get("number") != num:
            continue
        repo_url = it.get("repository", "")
        proj_id = "PVT_project1"
        if field == "Priority":
            val = it.get("priority")
            fv = {"name": val} if val is not None else None
        elif field == "Status":
            val = it.get("status")
            fv = {"name": val} if val is not None else None
        else:
            fv = None
        nodes.append({"id": it.get("id"), "project": {"id": proj_id}, "fieldValueByName": fv})
    print(json.dumps({"data": {"node": {"projectItems": {"nodes": nodes}}}}))
    sys.exit(0)

print(f"fake gh graphql helper: unhandled args: {args}", file=sys.stderr)
sys.exit(1)
"""

_GH_STUB = """#!/bin/bash
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  cat "$FAKE_GH_OPEN_ISSUES_JSON"
  exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  "$FAKE_GH_PYTHON" "$FAKE_GH_GRAPHQL_HELPER" "$@"
  exit $?
fi
if [ "$1" = "api" ] && [ "$2" = "graphql" ]; then
  "$FAKE_GH_PYTHON" "$FAKE_GH_GRAPHQL_HELPER" "$@"
  exit $?
fi
if [ "$1" = "project" ] && [ "$2" = "item-list" ]; then
  cat "$FAKE_GH_PROJECT_ITEMS_JSON"
  exit 0
fi
if [ "$1" = "repo" ] && [ "$2" = "view" ]; then
  echo "{\\"nameWithOwner\\": \\"$FAKE_GH_CWD_REPO\\"}"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "view" ]; then
  echo "{\\"id\\": \\"PVT_project1\\"}"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "field-list" ]; then
  echo "{\\"fields\\": [{\\"name\\": \\"Priority\\", \\"id\\": \\"FIELD_priority\\"}, {\\"name\\": \\"Status\\", \\"id\\": \\"FIELD_status\\"}]}"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "item-edit" ]; then
  echo "item-edit $*" >> "$GH_ISSUE_LOG"
  if [ -n "${FAIL_ON_CLEAR_ITEM:-}" ]; then
    for a in "$@"; do
      if [ "$a" = "$FAIL_ON_CLEAR_ITEM" ]; then
        echo "fake gh: forced item-edit failure for $FAIL_ON_CLEAR_ITEM" >&2
        exit 1
      fi
    done
  fi
  exit 0
fi
echo "fake gh: unhandled args: $*" >&2
exit 1
"""

# Fake gh_issue.sh: records every invocation to a log file. Distinguishes
# transition vs. comment failures via TWO separate env vars rather than
# matching any argument equal to the issue number (the original stub's bug:
# a comment call also carries the issue number as an argument, so a single
# FAIL_ON_ISSUE var tripped on the comment call even when the intent was to
# fail the transition).
_GH_ISSUE_SH_STUB = """#!/bin/bash
echo "$@" >> "$GH_ISSUE_LOG"
if [ "$1" = "transition" ] && [ -n "${FAIL_ON_TRANSITION_ISSUE:-}" ] && [ "$2" = "$FAIL_ON_TRANSITION_ISSUE" ]; then
  echo "fake gh_issue.sh: forced transition failure for issue $FAIL_ON_TRANSITION_ISSUE" >&2
  exit 1
fi
if [ "$1" = "comment" ] && [ -n "${FAIL_ON_COMMENT_ISSUE:-}" ] && [ "$2" = "$FAIL_ON_COMMENT_ISSUE" ]; then
  echo "fake gh_issue.sh: forced comment failure for issue $FAIL_ON_COMMENT_ISSUE" >&2
  exit 1
fi
if [ "$1" = "comment" ] && [ -n "${FAIL_ON_COMMENT_ISSUE_ONCE:-}" ] && [ "$2" = "$FAIL_ON_COMMENT_ISSUE_ONCE" ]; then
  if [ ! -f "$GH_ISSUE_LOG.comment_once_tripped" ]; then
    touch "$GH_ISSUE_LOG.comment_once_tripped"
    echo "fake gh_issue.sh: forced ONE-TIME comment failure for issue $FAIL_ON_COMMENT_ISSUE_ONCE" >&2
    exit 1
  fi
fi
exit 0
"""


def _make_env(
    tmp_path: Path,
    *,
    items: list[dict],
    open_numbers: list[int],
    repo: str = DEFAULT_REPO,
    cwd_repo: str | None = None,
    fail_on_transition_issue: str | None = None,
    fail_on_comment_issue: str | None = None,
    fail_on_comment_issue_once: str | None = None,
    fail_on_clear_item: str | None = None,
    rate_limit_remaining: int = 5000,
    rate_limit_fail: bool = False,
) -> dict:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)

    gh = bindir / "gh"
    gh.write_text(_GH_STUB)
    gh.chmod(0o755)

    gh_issue = bindir / "gh_issue.sh"
    gh_issue.write_text(_GH_ISSUE_SH_STUB)
    gh_issue.chmod(0o755)

    graphql_helper = tmp_path / "gh_graphql_helper.py"
    graphql_helper.write_text(_GH_GRAPHQL_HELPER)

    open_json = tmp_path / "open_issues.json"
    open_json.write_text(json.dumps([{"number": n} for n in open_numbers]))

    items_json = tmp_path / "project_items.json"
    items_json.write_text(json.dumps({"items": items}))

    rate_limit_counter = tmp_path / "rate_limit_counter.txt"
    rate_limit_counter.write_text(str(rate_limit_remaining))

    claude_dir = tmp_path / "claude_home"
    claude_dir.mkdir(exist_ok=True)

    gh_issue_log = tmp_path / "gh_issue.log"
    gh_issue_log.write_text("")

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["PRIORITY_BACKFILL_GH_BIN"] = str(gh)
    env["PRIORITY_BACKFILL_GH_ISSUE_SH"] = str(gh_issue)
    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(open_json)
    env["FAKE_GH_PROJECT_ITEMS_JSON"] = str(items_json)
    env["FAKE_GH_CWD_REPO"] = cwd_repo if cwd_repo is not None else repo
    env["GH_ISSUE_LOG"] = str(gh_issue_log)
    env["CLAUDE_DIR"] = str(claude_dir)
    env["FAKE_GH_PYTHON"] = sys.executable
    env["FAKE_GH_GRAPHQL_HELPER"] = str(graphql_helper)
    env["FAKE_GH_RATE_LIMIT_COUNTER"] = str(rate_limit_counter)
    for var, val in (
        ("FAIL_ON_TRANSITION_ISSUE", fail_on_transition_issue),
        ("FAIL_ON_COMMENT_ISSUE", fail_on_comment_issue),
        ("FAIL_ON_COMMENT_ISSUE_ONCE", fail_on_comment_issue_once),
        ("FAIL_ON_CLEAR_ITEM", fail_on_clear_item),
    ):
        if val:
            env[var] = val
        else:
            env.pop(var, None)
    if rate_limit_fail:
        env["FAKE_GH_RATE_LIMIT_FAIL"] = "1"
    else:
        env.pop("FAKE_GH_RATE_LIMIT_FAIL", None)
    return env


def _item(
    number: int | None,
    *,
    status: str = "Backlog",
    labels: list | None = None,
    priority: str | None = None,
    item_type: str = "Issue",
    repo: str = DEFAULT_REPO,
    item_id: str | None = None,
) -> dict:
    content: dict = {"type": item_type, "title": f"issue {number}"}
    if number is not None:
        content["number"] = number
    d = {
        "id": item_id or f"PVTI_{number}",
        "content": content,
        "repository": f"https://github.com/{repo}",
        "status": status,
        "labels": labels if labels is not None else [],
    }
    if priority is not None:
        d["priority"] = priority
    return d


def _run(tmp_path: Path, args: list[str], env: dict, *, script: Path = REAL_SCRIPT, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Runs `script` (the real tracked script by default) as a subprocess.
    `script` is an explicit parameter — round-2 B1 — so the ONE test that
    needs a deliberately-broken copy can pass a path INSIDE tmp_path and
    never touch the real file."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        timeout=30,
    )


def _bf_args(extra: list[str], repo: str = DEFAULT_REPO) -> list[str]:
    return ["backfill-priority", "--owner", "acme", "--repo", repo, "--project", "1", "--delay", "0", *extra]


def _rr_args(extra: list[str], repo: str = DEFAULT_REPO) -> list[str]:
    return ["reset-ready", "--owner", "acme", "--repo", repo, "--project", "1", "--delay", "0", *extra]


def _plan_args(for_subcommand: str, extra: list[str] | None = None, repo: str = DEFAULT_REPO) -> list[str]:
    return ["plan", "--for", for_subcommand, "--owner", "acme", "--repo", repo, "--project", "1", *(extra or [])]


def _read_log(tmp_path: Path) -> list[str]:
    return (tmp_path / "gh_issue.log").read_text().splitlines()


def _board_state_files(env: dict, *, pattern: str = "*.jsonl") -> list[Path]:
    d = Path(env["CLAUDE_DIR"]) / ".board_state"
    if not d.is_dir():
        return []
    return sorted(d.glob(pattern))


def _log_rows(env: dict, subcommand: str) -> list[dict]:
    files = _board_state_files(env, pattern=f"{subcommand}_*.jsonl")
    rows = []
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _set_items(tmp_path_for_fixture: Path, items: list[dict]) -> None:
    """Overwrite the project_items.json fixture in place -- used to simulate
    "the live board now reflects a prior write" or "a human edited the
    board" between two subprocess calls in the same test."""
    (tmp_path_for_fixture / "project_items.json").write_text(json.dumps({"items": items}))


# --------------------------------------------------------------------------
# backfill-priority: the mapping table
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "labels,expected_value,expected_disposition",
    [
        (["priority: P0"], "P0", "mapped"),
        (["priority: P1"], "P1", "mapped"),
        (["priority: P2"], "P2", "mapped"),
        (["priority: P3"], "P3", "mapped"),
        (["P1"], "P1", "mapped"),
        (["P2"], "P2", "mapped"),
        (["priority: critical"], "P0", "mapped"),
    ],
)
def test_mapping_table_direct_and_bare_labels(tmp_path, labels, expected_value, expected_disposition):
    items = [_item(101, labels=labels)]
    env = _make_env(tmp_path, items=items, open_numbers=[101])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert f"#101 Priority = {expected_value} ({expected_disposition})" in proc.stdout


def test_p4_is_a_floor_fold_to_p3_not_an_error(tmp_path):
    items = [_item(202, labels=["priority: P4"])]
    env = _make_env(tmp_path, items=items, open_numbers=[202])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "#202 Priority = P3 (floor-fold)" in proc.stdout


def test_bare_p4_also_floor_folds(tmp_path):
    items = [_item(203, labels=["P4"])]
    env = _make_env(tmp_path, items=items, open_numbers=[203])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "#203 Priority = P3 (floor-fold)" in proc.stdout


def test_conflicting_priority_labels_take_the_higher_priority(tmp_path):
    items = [_item(303, labels=["priority: P2", "priority: P0"])]
    env = _make_env(tmp_path, items=items, open_numbers=[303])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "#303 Priority = P0 (conflict)" in proc.stdout


def test_conflict_where_higher_value_comes_from_critical(tmp_path):
    items = [_item(304, labels=["priority: critical", "priority: P3"])]
    env = _make_env(tmp_path, items=items, open_numbers=[304])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "#304 Priority = P0 (conflict)" in proc.stdout


def test_unrecognized_priority_label_is_left_untouched_and_listed(tmp_path):
    items = [_item(404, labels=["priority: urgent-ish"])]
    env = _make_env(tmp_path, items=items, open_numbers=[404])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("404" in line for line in log_lines)
    assert "unmapped" in proc.stdout.lower()
    assert "404" in proc.stdout


def test_issue_with_field_already_set_is_skipped_regardless_of_labels(tmp_path):
    items = [_item(505, labels=["priority: P0"], priority="P2")]
    env = _make_env(tmp_path, items=items, open_numbers=[505])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("505" in line for line in log_lines)
    assert "candidates with a Priority write to make: 0" in proc.stdout


def test_empty_string_priority_is_treated_as_present_and_skipped(tmp_path):
    items = [_item(506, labels=["priority: P1"], priority="")]
    env = _make_env(tmp_path, items=items, open_numbers=[506])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("506" in line for line in log_lines)
    assert "candidates with a Priority write to make: 0" in proc.stdout


def test_pull_request_items_are_never_touched(tmp_path):
    items = [_item(606, labels=["priority: P1"], item_type="PullRequest")]
    env = _make_env(tmp_path, items=items, open_numbers=[606])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("606" in line for line in log_lines)


def test_closed_pull_request_is_never_touched(tmp_path):
    items = [_item(607, labels=["priority: P1"], item_type="PullRequest")]
    env = _make_env(tmp_path, items=items, open_numbers=[])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("607" in line for line in log_lines)


def test_draft_issue_with_no_number_is_skipped(tmp_path):
    items = [_item(None, labels=["priority: P1"], item_type="DraftIssue")]
    env = _make_env(tmp_path, items=items, open_numbers=[])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "candidates with a Priority write to make: 0" in proc.stdout


def test_closed_issue_is_never_touched(tmp_path):
    items = [_item(707, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("707" in line for line in log_lines)


def test_closed_issue_in_ready_2_is_never_touched_by_reset_ready(tmp_path):
    items = [_item(6200, status="Ready #2")]
    env = _make_env(tmp_path, items=items, open_numbers=[])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("6200" in line for line in log_lines)


def test_labels_as_object_shape_are_normalized(tmp_path):
    items = [_item(608, labels=[{"name": "priority: P1"}])]
    env = _make_env(tmp_path, items=items, open_numbers=[608])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "#608 Priority = P1 (mapped)" in proc.stdout


# --------------------------------------------------------------------------
# gh_issue.sh's hardcoded "Status" auto-comment gets a Priority correction
# --------------------------------------------------------------------------


def test_priority_write_posts_corrective_comment_naming_priority(tmp_path):
    items = [_item(808, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[808])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    transition_lines = [line for line in log_lines if line.startswith("transition 808")]
    comment_lines = [line for line in log_lines if line.startswith("comment 808")]
    assert len(transition_lines) == 1
    assert "--field Priority" in transition_lines[0]
    assert len(comment_lines) == 1, "expected exactly one corrective comment call for #808"


# --------------------------------------------------------------------------
# dry-run vs --apply vs --dry-run explicit
# --------------------------------------------------------------------------


def test_dry_run_writes_nothing_and_creates_no_log(tmp_path):
    items = [_item(909, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[909])
    proc = _run(tmp_path, _bf_args([]), env)
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout
    log_lines = _read_log(tmp_path)
    assert log_lines == []
    assert _board_state_files(env) == []


def test_explicit_dry_run_flag_behaves_identically(tmp_path):
    items = [_item(911, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[911])
    proc = _run(tmp_path, _bf_args(["--dry-run"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout
    assert _read_log(tmp_path) == []


def test_apply_and_dry_run_are_mutually_exclusive_exits_1_not_2(tmp_path):
    # round-2 item 6: argparse's native exit 2 is normalized to 1.
    items = [_item(912, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[912])
    proc = _run(tmp_path, _bf_args(["--apply", "--dry-run"]), env)
    assert proc.returncode == 1
    assert "not allowed" in proc.stderr.lower() or "mutually exclusive" in proc.stderr.lower() or "argument" in proc.stderr.lower()


def test_missing_required_flag_exits_1_not_2(tmp_path):
    items = [_item(913, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[913])
    proc = _run(tmp_path, ["backfill-priority", "--owner", "acme", "--project", "1"], env)  # no --repo
    assert proc.returncode == 1
    assert proc.returncode != 2


def test_apply_writes_a_log_row_before_the_first_mutation(tmp_path):
    items = [_item(910, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[910])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    rows = _log_rows(env, "backfill-priority")
    intent_rows = [r for r in rows if "old_value" in r]
    outcome_rows = [r for r in rows if "outcome" in r]
    assert len(intent_rows) == 1
    assert intent_rows[0]["issue"] == 910
    assert intent_rows[0]["field"] == "Priority"
    assert intent_rows[0]["new_value"] == "P1"
    assert intent_rows[0]["old_value"] is None
    assert len(outcome_rows) == 1
    assert outcome_rows[0]["outcome"] == "ok"
    assert "ts" in intent_rows[0] and "ts" in outcome_rows[0]


# --------------------------------------------------------------------------
# the 40-cap and "remaining" reporting
# --------------------------------------------------------------------------


def test_limit_caps_mutations_and_reports_remaining(tmp_path):
    items = [_item(1000 + i, labels=["priority: P2"]) for i in range(5)]
    numbers = [it["content"]["number"] for it in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    proc = _run(tmp_path, _bf_args(["--apply", "--limit", "3"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    written_issues = {line.split()[1] for line in log_lines if line.startswith("transition")}
    assert len(written_issues) == 3
    assert "applied 3 write(s); 2 remaining" in proc.stdout
    assert "PACING" in proc.stdout  # item 7: reminder printed when rows remain


def test_limit_hard_max_is_40(tmp_path):
    items = [_item(2000, labels=["priority: P2"])]
    env = _make_env(tmp_path, items=items, open_numbers=[2000])
    proc = _run(tmp_path, _bf_args(["--apply", "--limit", "41"]), env)
    assert proc.returncode != 0
    assert "40" in proc.stderr


def test_limit_exactly_40_is_accepted(tmp_path):
    items = [_item(2001, labels=["priority: P2"])]
    env = _make_env(tmp_path, items=items, open_numbers=[2001])
    proc = _run(tmp_path, _bf_args(["--apply", "--limit", "40"]), env)
    assert proc.returncode == 0, proc.stderr


def test_limit_zero_exits_nonzero(tmp_path):
    items = [_item(2002, labels=["priority: P2"])]
    env = _make_env(tmp_path, items=items, open_numbers=[2002])
    proc = _run(tmp_path, _bf_args(["--apply", "--limit", "0"]), env)
    assert proc.returncode != 0


def test_ascending_issue_number_ordering(tmp_path):
    items = [
        _item(3003, labels=["priority: P2"]),
        _item(3001, labels=["priority: P2"]),
        _item(3002, labels=["priority: P2"]),
    ]
    numbers = [3001, 3002, 3003]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    proc = _run(tmp_path, _bf_args(["--apply", "--limit", "2"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    transitioned = [line.split()[1] for line in log_lines if line.startswith("transition")]
    assert transitioned == ["3001", "3002"]


# --------------------------------------------------------------------------
# B1 — per-write logging survives a mid-batch abort correctly
# --------------------------------------------------------------------------


def test_mid_batch_abort_log_describes_exactly_what_happened(tmp_path):
    items = [
        _item(4001, labels=["priority: P1"]),
        _item(4002, labels=["priority: P1"]),
        _item(4003, labels=["priority: P1"]),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[4001, 4002, 4003], fail_on_transition_issue="4002")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode != 0

    rows = _log_rows(env, "backfill-priority")
    by_issue = {}
    for r in rows:
        by_issue.setdefault(r["issue"], []).append(r)

    assert any(r.get("outcome") == "ok" for r in by_issue.get(4001, []))
    assert any(r.get("outcome") == "transition-failed" for r in by_issue.get(4002, []))
    assert 4003 not in by_issue

    items_after = [
        _item(4001, labels=["priority: P1"], priority="P1"),
        _item(4002, labels=["priority: P1"]),
        _item(4003, labels=["priority: P1"]),
    ]
    _set_items(tmp_path, items_after)

    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    assert "4001" in proc2.stdout
    assert "reversible write rows (outcome ok/comment-failed/comment-repaired): 1" in proc2.stdout


# --------------------------------------------------------------------------
# B4 — partial comment failure
# --------------------------------------------------------------------------


def test_transition_failure_stops_run_exit_1_logs_transition_failed(tmp_path):
    items = [
        _item(4101, labels=["priority: P1"]),
        _item(4102, labels=["priority: P1"]),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[4101, 4102], fail_on_transition_issue="4101")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 1
    rows = _log_rows(env, "backfill-priority")
    outcomes = {r["issue"]: r.get("outcome") for r in rows if "outcome" in r}
    assert outcomes.get(4101) == "transition-failed"
    assert 4102 not in outcomes
    log_lines = _read_log(tmp_path)
    assert not any("4102" in line for line in log_lines)


def test_transition_failure_is_real_red_without_the_raise(tmp_path):
    """Round-2 B1: proves the paired test above is real WITHOUT ever writing
    to the real tracked script. Copies the real script to a throwaway
    location under tmp_path, mutates ONLY that copy (deletes the `raise` in
    write_field), runs the COPY as the subprocess, and confirms it goes RED
    (the failure it's supposed to catch no longer causes a failure). The
    real file at ~/.claude/scripts/priority_backfill.py is never opened for
    writing anywhere in this test."""
    private_copy = tmp_path / "priority_backfill_mutated_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)

    src = private_copy.read_text()
    old = '''    proc = _run(cmd)
    if proc.returncode != 0:
        raise BoardBackfillError(
            f"gh_issue.sh transition failed for #{issue_num} "
            f"(field={field!r} value={status_value!r}): {proc.stderr.strip()}"
        )'''
    assert old in src, "write_field's raise block not found in the real script -- test can't prove RED"
    mutated = src.replace(old, "    proc = _run(cmd)\n    pass  # BUG: raise deleted for falsifiability check")
    assert mutated != src
    private_copy.write_text(mutated)  # writes ONLY the tmp_path copy

    items = [
        _item(4101, labels=["priority: P1"]),
        _item(4102, labels=["priority: P1"]),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[4101, 4102], fail_on_transition_issue="4101")
    proc = _run(tmp_path, _bf_args(["--apply"]), env, script=private_copy)
    # With the raise deleted, the run no longer stops -- both issues get
    # written, so returncode is 0 and 4102 IS attempted -- both assertions in
    # the real test above would go RED here.
    assert proc.returncode == 0
    assert any("4102" in line for line in _read_log(tmp_path))

    # Confirm the REAL script's bytes are untouched by this test specifically
    # (belt-and-suspenders on top of the session-scoped fixture above).
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


def test_no_test_in_this_module_opens_the_real_script_for_writing():
    """Static self-check (round-2 B1's explicit report requirement): scan
    this test file's own source, EXCLUDING comment lines and this function's
    own body (which necessarily names the patterns in prose to describe
    them), for any write-mode file open of the REAL script path. The only
    path constant allowed to appear next to a write verb is `private_copy`/a
    tmp_path-derived Path, never REAL_SCRIPT."""
    import re as _re

    this_file_lines = Path(__file__).read_text().splitlines()
    # Substring patterns that always mean "REAL_SCRIPT is the WRITE target".
    forbidden_substrings = (
        "REAL_SCRIPT.write_text(",
        "REAL_SCRIPT.write_bytes(",
        'open(REAL_SCRIPT, "w"',
        "open(REAL_SCRIPT, 'w'",
    )
    # `shutil.copy2(<src>, REAL_SCRIPT)` -- REAL_SCRIPT as the DESTINATION
    # (2nd positional) is the dangerous shape; `copy2(REAL_SCRIPT, <dst>)`
    # (REAL_SCRIPT as the SOURCE, 1st positional) is an ordinary, safe read
    # and must never be flagged.
    copy2_dest_re = _re.compile(r"copy2\([^,()]+,\s*REAL_SCRIPT\)")

    in_this_function = False
    violations: list[str] = []
    for line in this_file_lines:
        if line.startswith("def test_no_test_in_this_module_opens_the_real_script_for_writing"):
            in_this_function = True
            continue
        if in_this_function and line.startswith("def "):
            in_this_function = False
        if in_this_function:
            continue  # this function's own body legitimately names the patterns in prose
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # a comment naming the pattern is not code that does it
        for pattern in forbidden_substrings:
            if pattern in line:
                violations.append(f"{pattern!r} in line: {line!r}")
        if copy2_dest_re.search(line):
            violations.append(f"copy2(..., REAL_SCRIPT) in line: {line!r}")
    assert violations == [], f"forbidden write-to-real-script pattern(s) found: {violations}"


def test_comment_failure_partial_exit_3_logs_comment_failed(tmp_path):
    items = [_item(4201, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[4201], fail_on_comment_issue="4201")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 3
    assert "PARTIAL" in proc.stderr
    assert "4201" in proc.stderr
    rows = _log_rows(env, "backfill-priority")
    outcomes = {r["issue"]: r.get("outcome") for r in rows if "outcome" in r}
    assert outcomes.get(4201) == "comment-failed"
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 4201") for line in log_lines)


def test_comment_failure_is_repaired_on_next_run_without_rerunning_transition(tmp_path):
    items = [_item(4202, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[4202], fail_on_comment_issue_once="4202")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 3

    items_after = [_item(4202, labels=["priority: P1"], priority="P1")]
    _set_items(tmp_path, items_after)

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, _bf_args(["--apply"]), env)
    assert "repaired 1 prior comment-failed row(s): [4202]" in proc2.stdout
    log_lines = _read_log(tmp_path)
    transition_calls = [line for line in log_lines if line.startswith("transition 4202")]
    assert transition_calls == [], "the transition must NEVER be re-run for a comment-failed row"
    comment_calls = [line for line in log_lines if line.startswith("comment 4202")]
    assert len(comment_calls) == 1

    rows = _log_rows(env, "backfill-priority")
    outcomes = [r for r in rows if r.get("issue") == 4202 and "outcome" in r]
    assert outcomes[-1]["outcome"] == "comment-repaired"


def test_comment_repair_scoped_to_this_boards_owner_repo_project_item_8(tmp_path):
    # round-2 item 8: a comment-failed row for a DIFFERENT (owner, repo,
    # project) must never be repaired by an invocation against THIS board,
    # even though the bare issue number collides. Board B's issue 9301
    # already carries a Priority value (nothing for backfill-priority to
    # write there itself), isolating the repair-pass behavior specifically
    # from an unrelated, legitimate new write on board B.
    items_board_a = [_item(9301, labels=["priority: P1"], repo="acme/board-a")]
    env = _make_env(tmp_path, items=items_board_a, open_numbers=[9301], repo="acme/board-a", fail_on_comment_issue_once="9301")
    proc = _run(tmp_path, _bf_args(["--apply"], repo="acme/board-a"), env)
    assert proc.returncode == 3

    # Now run against a DIFFERENT repo/board with the same-numbered issue --
    # already has its Priority field set, so it is not itself a candidate.
    items_board_b = [_item(9301, labels=["priority: P2"], repo="acme/board-b", priority="P2")]
    _set_items(tmp_path, items_board_b)
    env_b = dict(env)
    env_b["FAKE_GH_CWD_REPO"] = "acme/board-b"
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, _bf_args(["--apply"], repo="acme/board-b"), env_b)
    assert proc2.returncode == 0, proc2.stderr
    assert "candidates with a Priority write to make: 0" in proc2.stdout
    assert "repaired" not in proc2.stdout or "repaired 0" in proc2.stdout
    log_lines = _read_log(tmp_path)
    comment_calls = [line for line in log_lines if line.startswith("comment 9301")]
    assert comment_calls == [], "must never repair a comment-failed row belonging to a different board"


def test_cwd_check_runs_before_repair_pass_item_8(tmp_path):
    # round-2 item 8: assert_cwd_matches_repo must run BEFORE the repair
    # pass -- a mismatched CWD refuses the whole run, including repair.
    items = [_item(9302, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9302], cwd_repo="acme/OTHER")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode != 0
    assert "does not match" in proc.stderr
    log_lines = _read_log(tmp_path)
    assert log_lines == []  # not even a comment-repair attempt


# --------------------------------------------------------------------------
# B2 — cross-repo safety (backfill/reset-ready keying)
# --------------------------------------------------------------------------


def test_foreign_repo_item_is_skipped_and_listed(tmp_path):
    items = [
        _item(5101, labels=["priority: P1"], repo="acme/widgets"),
        _item(5101, labels=["priority: P1"], repo="acme/other-repo", item_id="PVTI_other_5101"),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[5101], repo="acme/widgets")
    proc = _run(tmp_path, _bf_args(["--apply"], repo="acme/widgets"), env)
    assert proc.returncode == 0, proc.stderr
    assert "foreign-repo (skipped, not in --repo acme/widgets): 1" in proc.stdout
    assert "5101 (acme/other-repo)" in proc.stdout
    log_lines = _read_log(tmp_path)
    transition_calls = [line for line in log_lines if line.startswith("transition 5101")]
    assert len(transition_calls) == 1


def test_cwd_repo_mismatch_refuses_before_any_write(tmp_path):
    items = [_item(5102, labels=["priority: P1"], repo="acme/widgets")]
    env = _make_env(tmp_path, items=items, open_numbers=[5102], repo="acme/widgets", cwd_repo="acme/DIFFERENT-repo")
    proc = _run(tmp_path, _bf_args(["--apply"], repo="acme/widgets"), env)
    assert proc.returncode != 0
    assert "does not match" in proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("5102" in line for line in log_lines)
    assert _board_state_files(env, pattern="backfill-priority_*.jsonl") == []


def test_cwd_repo_match_allows_writes(tmp_path):
    items = [_item(5103, labels=["priority: P1"], repo="acme/widgets")]
    env = _make_env(tmp_path, items=items, open_numbers=[5103], repo="acme/widgets", cwd_repo="acme/widgets")
    proc = _run(tmp_path, _bf_args(["--apply"], repo="acme/widgets"), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 5103") for line in log_lines)


# --------------------------------------------------------------------------
# reset-ready
# --------------------------------------------------------------------------


def test_reset_ready_touches_only_ready_1_and_ready_2(tmp_path):
    items = [
        _item(5001, status="Ready #1"),
        _item(5002, status="Ready #2"),
        _item(5003, status="Backlog"),
        _item(5004, status="In progress"),
        _item(5005, status="Done"),
        _item(5006, status="In review"),
    ]
    numbers = [i["content"]["number"] for i in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    transitioned = sorted(int(line.split()[1]) for line in log_lines if line.startswith("transition"))
    assert transitioned == [5001, 5002]
    for line in log_lines:
        if line.startswith("transition"):
            assert "Backlog" in line


def test_reset_ready_dry_run_default(tmp_path):
    items = [_item(6001, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[6001])
    proc = _run(tmp_path, _rr_args([]), env)
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_reset_ready_closed_item_is_never_touched(tmp_path):
    items = [_item(6100, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any("6100" in line for line in log_lines)


# --------------------------------------------------------------------------
# reverse — B2 round 2: three-way classification against the live board
# --------------------------------------------------------------------------


def test_reverse_restores_old_values_when_live_equals_new(tmp_path):
    sub = tmp_path / "reverse_case"
    sub.mkdir()
    items = [_item(7002, status="Ready #1")]
    env = _make_env(sub, items=items, open_numbers=[7002])
    proc = _run(sub, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    files = _board_state_files(env, pattern="reset-ready_*.jsonl")
    assert len(files) == 1
    reset_log = files[0]

    _set_items(sub, [_item(7002, status="Backlog")])  # live == new_value

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(sub, ["reverse", "--log", str(reset_log), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    transition_lines = [line for line in log_lines if line.startswith("transition 7002")]
    assert len(transition_lines) == 1
    assert "Ready #1" in transition_lines[0]


def test_reverse_skips_already_reversed_when_live_equals_old(tmp_path):
    items = [_item(7010, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[7010])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(7010, status="Ready #1")])  # live == old_value already

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any(line.startswith("transition") for line in log_lines)
    assert "already reversed" in proc2.stdout


def test_reverse_refuses_changed_since_write_without_force(tmp_path):
    # B2 round 2 -- the operator's own scenario: backfill wrote P1, the
    # operator hand-set P0; reverse must NOT clear/overwrite it.
    items = [_item(7020, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[7020])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # The operator hand-set the live board to P0 (neither old_value=None nor new_value=P1).
    _set_items(tmp_path, [_item(7020, labels=["priority: P1"], priority="P0")])

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr  # nothing to do is not an error
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any(line.startswith("transition") or line.startswith("item-edit") for line in log_lines), (
        "a deliberate human edit must never be clobbered by reverse"
    )
    assert "changed-since-write" in proc2.stdout
    assert "7020" in proc2.stdout


def test_reverse_changed_since_write_reset_ready_scenario(tmp_path):
    # The paired reset-ready scenario from the fix-round message: #888 moved
    # to Backlog, operator moved it to "In progress", reverse must refuse.
    items = [_item(888, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[888])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(888, status="In progress")])  # operator's own move

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any(line.startswith("transition") for line in log_lines)
    assert "changed-since-write" in proc2.stdout
    assert "888" in proc2.stdout


def test_reverse_force_changed_overwrites_named_issue_only(tmp_path):
    items = [
        _item(7030, labels=["priority: P1"]),
        _item(7031, labels=["priority: P1"]),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[7030, 7031])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # Both issues changed since write; --force-changed names only 7030.
    _set_items(
        tmp_path,
        [
            _item(7030, labels=["priority: P1"], priority="P0"),
            _item(7031, labels=["priority: P1"], priority="P2"),
        ],
    )

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(
        tmp_path,
        ["reverse", "--log", str(log_file), "--apply", "--delay", "0", "--force-changed", "7030"],
        env,
    )
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    clear_calls = [line for line in log_lines if line.startswith("item-edit") and "--clear" in line]
    assert len(clear_calls) == 1
    assert "PVTI_7030" in clear_calls[0]
    assert "7031" not in " ".join(clear_calls)
    assert "still refused" in proc2.stdout
    assert "7031" in proc2.stdout.split("still refused")[-1]


def test_reverse_dry_run_default(tmp_path):
    items = [_item(8001, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[8001])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(8001, status="Backlog")])

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0"], env)  # no --apply
    assert proc2.returncode == 0, proc2.stderr
    assert "DRY RUN" in proc2.stdout
    assert Path(env["GH_ISSUE_LOG"]).read_text().splitlines() == []


def test_reverse_missing_log_file_fails(tmp_path):
    items = [_item(9001, status="Backlog")]
    env = _make_env(tmp_path, items=items, open_numbers=[9001])
    proc = _run(tmp_path, ["reverse", "--log", str(tmp_path / "does_not_exist.jsonl"), "--apply", "--delay", "0"], env)
    assert proc.returncode != 0
    assert "not found" in proc.stderr.lower()


def test_reverse_log_recovery_pairing_present_log_reverses(tmp_path):
    items = [_item(9002, status="Ready #2")]
    env = _make_env(tmp_path, items=items, open_numbers=[9002])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]
    _set_items(tmp_path, [_item(9002, status="Backlog")])
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0"], env)  # dry-run
    assert proc2.returncode == 0, proc2.stderr
    assert "9002" in proc2.stdout


def test_reverse_restore_to_empty_via_clear(tmp_path):
    items = [_item(9101, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9101])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    Path(env["GH_ISSUE_LOG"]).write_text("")
    _set_items(tmp_path, [_item(9101, labels=["priority: P1"], priority="P1")])

    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    clear_calls = [line for line in log_lines if line.startswith("item-edit") and "--clear" in line]
    assert len(clear_calls) == 1
    assert "PVTI_9101" in clear_calls[0]
    transition_calls = [line for line in log_lines if line.startswith("transition 9101")]
    assert transition_calls == []
    assert "cleared #9101" in proc2.stdout


def test_reverse_clear_uses_live_item_id_not_stale_logged_id_item_5(tmp_path):
    # round-2 item 5: the live board's item id must be used, never the id
    # recorded in the log -- simulate the item having a DIFFERENT id live
    # (as if it were recreated/moved) and confirm the CLEAR call uses it.
    items = [_item(9102, labels=["priority: P1"], item_id="PVTI_original_9102")]
    env = _make_env(tmp_path, items=items, open_numbers=[9102])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # The logged item_id is PVTI_original_9102, but the LIVE board now shows a DIFFERENT id.
    _set_items(tmp_path, [_item(9102, labels=["priority: P1"], priority="P1", item_id="PVTI_LIVE_DIFFERENT_9102")])

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    clear_calls = [line for line in log_lines if line.startswith("item-edit") and "--clear" in line]
    assert len(clear_calls) == 1
    assert "PVTI_LIVE_DIFFERENT_9102" in clear_calls[0]
    assert "PVTI_original_9102" not in clear_calls[0]


def test_reverse_clear_refuses_when_issue_absent_from_live_board_item_5(tmp_path):
    items = [_item(9103, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9103])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # The issue is now ABSENT from the live board entirely.
    _set_items(tmp_path, [])
    env2 = dict(env)
    env2["FAKE_GH_OPEN_ISSUES_JSON"] = env["FAKE_GH_OPEN_ISSUES_JSON"]

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env2)
    # An item missing from the live board is an "I don't know" read, not an
    # observed value: cmd_reverse pulls the row out as `unreadable` (reason
    # not-found) BEFORE classifying it, so it is never mistaken for an observed
    # None that equals old_value, and no clear is attempted on a nonexistent
    # item. Reporting it is not an error.
    assert proc2.returncode == 0, proc2.stderr
    assert "unreadable" in proc2.stdout, proc2.stdout
    assert "not-found" in proc2.stdout, proc2.stdout
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any(line.startswith("item-edit") for line in log_lines)


def test_restore_to_empty_refuses_non_priority_field_item_4(tmp_path):
    # round-2 item 4: a hand-made log row with field=Status and
    # old_value=null must be REFUSED, never cleared.
    claude_dir = tmp_path / "claude_home"
    claude_dir.mkdir(exist_ok=True)
    board_state = claude_dir / ".board_state"
    board_state.mkdir(parents=True)
    log_file = board_state / "hand_made.jsonl"
    row = {
        "ts": "2026-01-01T00:00:00Z",
        "subcommand": "reset-ready",
        "issue": 9104,
        "field": "Status",
        "old_value": None,  # malformed / hand-edited -- Status should never have a null old_value
        "new_value": "Backlog",
        "owner": "acme",
        "repo": DEFAULT_REPO,
        "project": 1,
    }
    outcome = {"ts": "2026-01-01T00:00:01Z", "subcommand": "reset-ready", "issue": 9104, "field": "Status", "new_value": "Backlog", "outcome": "ok"}
    log_file.write_text(json.dumps(row) + "\n" + json.dumps(outcome) + "\n")

    items = [_item(9104, status="Backlog", item_id="PVTI_9104")]
    env = _make_env(tmp_path, items=items, open_numbers=[9104])
    env["CLAUDE_DIR"] = str(claude_dir)

    proc = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc.returncode != 0
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("item-edit") for line in log_lines), "nothing must ever be cleared for a non-Priority field"


def test_reverse_resumes_across_two_runs_over_a_50_row_log(tmp_path):
    items = [_item(10000 + i, status="Ready #1") for i in range(50)]
    numbers = [it["content"]["number"] for it in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    proc = _run(tmp_path, _rr_args(["--apply", "--limit", "40"]), env)
    assert proc.returncode == 0, proc.stderr
    moved_items = [_item(10000 + i, status="Backlog" if i < 40 else "Ready #1") for i in range(50)]
    _set_items(tmp_path, moved_items)
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--limit", "40", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    restored_first_run = sorted(int(line.split()[1]) for line in log_lines if line.startswith("transition"))
    assert len(restored_first_run) == 40

    fully_reset_items = [_item(10000 + i, status="Ready #1") for i in range(50)]
    _set_items(tmp_path, fully_reset_items)

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc3 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--limit", "40", "--delay", "0"], env)
    assert proc3.returncode == 0, proc3.stderr
    log_lines2 = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any(line.startswith("transition") for line in log_lines2)
    assert "already reversed" in proc3.stdout


def test_reverse_indeterminate_row_reported_not_silently_dropped_item_3(tmp_path):
    # round-2 item 3: a write-intent row with NO outcome row at all.
    claude_dir = tmp_path / "claude_home"
    claude_dir.mkdir(exist_ok=True)
    board_state = claude_dir / ".board_state"
    board_state.mkdir(parents=True)
    log_file = board_state / "hand_made_indeterminate.jsonl"
    row = {
        "ts": "2026-01-01T00:00:00Z",
        "subcommand": "backfill-priority",
        "issue": 9201,
        "item_id": "PVTI_9201",
        "field": "Priority",
        "old_value": None,
        "new_value": "P1",
        "owner": "acme",
        "repo": DEFAULT_REPO,
        "project": 1,
    }
    # NO matching outcome row -- simulates a crash between the log write and
    # the outcome write.
    log_file.write_text(json.dumps(row) + "\n")

    items = [_item(9201, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9201])
    env["CLAUDE_DIR"] = str(claude_dir)

    proc = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0"], env)  # dry-run
    assert proc.returncode == 0, proc.stderr
    assert "no recorded outcome" in proc.stdout
    assert "9201" in proc.stdout
    assert "reversible write rows (outcome ok/comment-failed/comment-repaired): 0" in proc.stdout


def test_reverse_include_indeterminate_classifies_against_live_board_item_3(tmp_path):
    claude_dir = tmp_path / "claude_home"
    claude_dir.mkdir(exist_ok=True)
    board_state = claude_dir / ".board_state"
    board_state.mkdir(parents=True)
    log_file = board_state / "hand_made_indeterminate2.jsonl"
    row = {
        "ts": "2026-01-01T00:00:00Z",
        "subcommand": "backfill-priority",
        "issue": 9202,
        "item_id": "PVTI_9202",
        "field": "Priority",
        "old_value": None,
        "new_value": "P1",
        "owner": "acme",
        "repo": DEFAULT_REPO,
        "project": 1,
    }
    log_file.write_text(json.dumps(row) + "\n")

    # Live board shows the write DID land (priority=P1).
    items = [_item(9202, labels=["priority: P1"], priority="P1")]
    env = _make_env(tmp_path, items=items, open_numbers=[9202])
    env["CLAUDE_DIR"] = str(claude_dir)

    proc = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0", "--include-indeterminate"], env)
    assert proc.returncode == 0, proc.stderr
    assert "9202" in proc.stdout
    # It should now show up as something to restore (treated as written).
    assert "remaining to restore: 1" in proc.stdout


def test_reverse_comment_repaired_as_latest_outcome_is_reversible(tmp_path):
    # item 10/11: a `comment-repaired` row as the LATEST outcome must still
    # be treated as reversible (the underlying field write did succeed).
    items = [_item(9203, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9203], fail_on_comment_issue_once="9203")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 3

    _set_items(tmp_path, [_item(9203, labels=["priority: P1"], priority="P1")])
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, _bf_args(["--apply"]), env)
    assert "repaired 1 prior comment-failed row(s): [9203]" in proc2.stdout

    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]
    rows = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    outcomes = [r for r in rows if r.get("issue") == 9203 and "outcome" in r]
    assert outcomes[-1]["outcome"] == "comment-repaired"

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc3 = _run(tmp_path, ["reverse", "--log", str(log_file), "--delay", "0"], env)  # dry-run
    assert proc3.returncode == 0, proc3.stderr
    assert "reversible write rows (outcome ok/comment-failed/comment-repaired): 1" in proc3.stdout
    assert "9203" in proc3.stdout


def test_reverse_clear_failure_mid_batch_stops_exit_1_logs_outcome(tmp_path):
    items = [
        _item(9301, labels=["priority: P1"]),
        _item(9302, labels=["priority: P1"]),
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[9301, 9302])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    _set_items(
        tmp_path,
        [
            _item(9301, labels=["priority: P1"], priority="P1"),
            _item(9302, labels=["priority: P1"], priority="P1"),
        ],
    )

    env2 = dict(env)
    env2["FAIL_ON_CLEAR_ITEM"] = "PVTI_9301"
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env2)
    assert proc2.returncode == 1

    rows = _log_rows(env, "reverse")
    outcomes = {r["issue"]: r.get("outcome") for r in rows if "outcome" in r}
    assert outcomes.get(9301) == "transition-failed"
    assert 9302 not in outcomes  # the run stopped before reaching 9302
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert not any("9302" in line for line in log_lines if line.startswith("item-edit"))


def test_reverse_clear_failure_recovers_on_rerun(tmp_path):
    items = [_item(9303, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[9303])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    _set_items(tmp_path, [_item(9303, labels=["priority: P1"], priority="P1")])

    env2 = dict(env)
    env2["FAIL_ON_CLEAR_ITEM"] = "PVTI_9303"
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env2)
    assert proc2.returncode == 1

    # Re-run WITHOUT the forced failure -- paired recovery test.
    env3 = dict(env)
    env3.pop("FAIL_ON_CLEAR_ITEM", None)
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc3 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env3)
    assert proc3.returncode == 0, proc3.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    clear_calls = [line for line in log_lines if line.startswith("item-edit") and "--clear" in line]
    assert len(clear_calls) == 1


def test_double_reverse_refused_with_clear_message(tmp_path):
    # item 10: reversing a `reverse` log is pinned as REFUSED.
    items = [_item(9401, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[9401])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    forward_log = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(9401, status="Backlog")])
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(forward_log), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr

    reverse_log = _board_state_files(env, pattern="reverse_*.jsonl")[0]
    proc3 = _run(tmp_path, ["reverse", "--log", str(reverse_log), "--delay", "0"], env)
    assert proc3.returncode != 0
    assert "reverse" in proc3.stderr.lower()
    assert "refus" in proc3.stderr.lower()


# --------------------------------------------------------------------------
# truncation refusal
# --------------------------------------------------------------------------


def test_truncation_at_2000_open_issues_refuses(tmp_path):
    items = [_item(20000, labels=["priority: P1"])]
    open_numbers = list(range(1, 2001))
    env = _make_env(tmp_path, items=items, open_numbers=open_numbers)
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode != 0
    assert "truncat" in proc.stderr.lower() or "limit" in proc.stderr.lower()
    log_lines = _read_log(tmp_path)
    assert log_lines == []


# --------------------------------------------------------------------------
# rate-limit read abort, exit 4, zero writes
# --------------------------------------------------------------------------


def test_rate_limited_read_aborts_exit_4_zero_writes(tmp_path):
    items = [_item(30000, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[30000])
    (tmp_path / "open_issues.json").write_text("unknown owner type")
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 4
    log_lines = _read_log(tmp_path)
    assert log_lines == []
    assert _board_state_files(env, pattern="backfill-priority_*.jsonl") == []


# --------------------------------------------------------------------------
# item 12: fixed brittle assertion -- direct check the floor-fold issue is
# absent from the unmapped-labels output.
# --------------------------------------------------------------------------


def test_floor_fold_issue_is_absent_from_unmapped_list(tmp_path):
    items = [_item(40001, labels=["priority: P4"])]
    env = _make_env(tmp_path, items=items, open_numbers=[40001])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "unmapped (priority-looking label, left untouched): 0" in proc.stdout


# --------------------------------------------------------------------------
# comment-body temp file lives outside .board_state/
# --------------------------------------------------------------------------


def test_comment_body_temp_file_never_written_inside_board_state(tmp_path):
    items = [_item(50001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[50001])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    board_state = Path(env["CLAUDE_DIR"]) / ".board_state"
    leftover_tmp = list(board_state.glob("*.tmp")) + list(board_state.glob(".comment_body_*"))
    assert leftover_tmp == []


# --------------------------------------------------------------------------
# item 9: planned_*.jsonl carries a per-run id and is flushed
# --------------------------------------------------------------------------


def test_planned_preview_carries_run_id(tmp_path):
    items = [_item(60001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[60001])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    planned_files = _board_state_files(env, pattern="planned_backfill-priority_*.jsonl")
    assert len(planned_files) == 1
    rows = [json.loads(line) for line in planned_files[0].read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert "run_id" in rows[0] and rows[0]["run_id"]


# --------------------------------------------------------------------------
# unit tests for the pure decision function (no subprocess needed)
# --------------------------------------------------------------------------


def test_classify_reverse_row_pure_function():
    import importlib.util

    spec = importlib.util.spec_from_file_location("priority_backfill_readonly", REAL_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # READS the real script; never writes to it

    assert mod.classify_reverse_row(live_value="P1", old_value=None, new_value="P1") == mod.DECISION_REVERSE
    assert mod.classify_reverse_row(live_value=None, old_value=None, new_value="P1") == mod.DECISION_ALREADY_REVERSED
    assert mod.classify_reverse_row(live_value="P0", old_value=None, new_value="P1") == mod.DECISION_CHANGED_SINCE_WRITE
    assert mod.classify_reverse_row(live_value="Backlog", old_value="Ready #1", new_value="Backlog") == mod.DECISION_REVERSE
    assert mod.classify_reverse_row(live_value="In progress", old_value="Ready #1", new_value="Backlog") == mod.DECISION_CHANGED_SINCE_WRITE
    assert mod.classify_reverse_row(live_value="Ready #1", old_value="Ready #1", new_value="Backlog") == mod.DECISION_ALREADY_REVERSED


# --------------------------------------------------------------------------
# plan / --from-plan (example-org #5827 — stop re-reading the whole
# board on every pass). A separate call-log (distinct from GH_ISSUE_LOG,
# which only ever recorded gh_issue.sh calls) records every `gh` invocation
# itself, so a test can assert directly on "how many times was `gh project
# item-list` called", the load-bearing assertion for this whole feature.
# --------------------------------------------------------------------------


def _make_env_with_gh_call_log(tmp_path: Path, **kwargs) -> tuple[dict, Path]:
    """Same as _make_env, but additionally records EVERY `gh` invocation
    (not just gh_issue.sh calls) to its own log file, via a thin wrapper
    inserted ahead of the real fake-gh binary on PATH."""
    env = _make_env(tmp_path, **kwargs)
    real_gh = Path(env["PRIORITY_BACKFILL_GH_BIN"])
    gh_call_log = tmp_path / "gh_calls.log"
    gh_call_log.write_text("")
    wrapper_dir = tmp_path / "bin_wrapper"
    wrapper_dir.mkdir(exist_ok=True)
    wrapper = wrapper_dir / "gh"
    wrapper.write_text(f"""#!/bin/bash
echo "$@" >> "{gh_call_log}"
exec "{real_gh}" "$@"
""")
    wrapper.chmod(0o755)
    env["PATH"] = f"{wrapper_dir}:{env['PATH']}"
    env["PRIORITY_BACKFILL_GH_BIN"] = str(wrapper)
    return env, gh_call_log


def _gh_calls(log_path: Path) -> list[str]:
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_plan_backfill_priority_writes_header_and_candidate_rows(tmp_path):
    items = [_item(70001, labels=["priority: P1"]), _item(70002, labels=["priority: P4"])]
    env = _make_env(tmp_path, items=items, open_numbers=[70001, 70002])
    proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert proc.returncode == 0, proc.stderr
    assert "NOTHING was written to GitHub" in proc.stdout

    plan_files = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")
    assert len(plan_files) == 1
    lines = [json.loads(line) for line in plan_files[0].read_text().splitlines() if line.strip()]
    header, rows = lines[0], lines[1:]
    assert header["kind"] == "plan-header"
    assert header["for"] == "backfill-priority"
    assert header["owner"] == "acme"
    assert header["repo"] == DEFAULT_REPO
    assert header["project"] == 1
    assert "created_at" in header
    assert header["counts"]["writes"] == 2
    assert len(rows) == 2
    by_issue = {r["issue"]: r for r in rows}
    assert by_issue[70001]["new_value"] == "P1"
    assert by_issue[70001]["old_value"] is None
    assert by_issue[70002]["new_value"] == "P3"
    assert by_issue[70002]["disposition"] == "floor-fold"

    # Nothing was actually written to the (fake) board.
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_plan_reset_ready_writes_header_and_candidate_rows(tmp_path):
    items = [_item(70101, status="Ready #1"), _item(70102, status="Ready #2"), _item(70103, status="Backlog")]
    numbers = [70101, 70102, 70103]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    proc = _run(tmp_path, _plan_args("reset-ready"), env)
    assert proc.returncode == 0, proc.stderr

    plan_files = _board_state_files(env, pattern="plan_reset-ready_*.jsonl")
    assert len(plan_files) == 1
    lines = [json.loads(line) for line in plan_files[0].read_text().splitlines() if line.strip()]
    header, rows = lines[0], lines[1:]
    assert header["for"] == "reset-ready"
    assert len(rows) == 2
    by_issue = {r["issue"]: r for r in rows}
    assert by_issue[70101]["field"] == "Status"
    assert by_issue[70101]["old_value"] == "Ready #1"
    assert by_issue[70101]["new_value"] == "Backlog"
    log_lines = _read_log(tmp_path)
    assert log_lines == []


# --------------------------------------------------------------------------
# --from-plan makes ZERO `gh project item-list` calls (the whole point).
# Falsifiability: shown RED on a scratch copy that reverts the mechanism,
# never by breaking the live script.
# --------------------------------------------------------------------------


def test_from_plan_makes_zero_project_item_list_calls(tmp_path):
    items = [_item(71001, labels=["priority: P1"])]
    env, gh_calls = _make_env_with_gh_call_log(tmp_path, items=items, open_numbers=[71001])

    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # `plan` itself legitimately calls project item-list once -- clear the
    # call log before the --from-plan run, which is the one under test.
    gh_calls.write_text("")

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    calls = _gh_calls(gh_calls)
    assert not any(c.startswith("project item-list") for c in calls), (
        f"--from-plan must never call `gh project item-list`; calls were: {calls}"
    )
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 71001") for line in log_lines)


def test_from_plan_zero_item_list_calls_is_real_red_without_the_mechanism(tmp_path):
    """Falsifiability for the test above: on a PRIVATE COPY of the real
    script (never the tracked file), delete the `--from-plan` short-circuit
    so cmd_backfill_priority ALWAYS calls fetch_project_items, then confirm
    the paired test's own assertion goes RED. Single-file scratch copy only
    — never cp -R, never mutates the live script (round-2 B1 discipline)."""
    private_copy = tmp_path / "priority_backfill_no_from_plan_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)

    src = private_copy.read_text()
    old = '''    if args.from_plan:
        return _run_backfill_from_plan(args, owner=owner, project=project, repo=repo, limit=limit, delay=delay)

    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FULL_READ'''
    assert old in src, "the --from-plan short-circuit was not found in the real script -- test can't prove RED"
    mutated = src.replace(
        old,
        "    # BUG: --from-plan short-circuit deleted for falsifiability check\n"
        "    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FULL_READ",
    )
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(71002, labels=["priority: P1"])]
    env, gh_calls = _make_env_with_gh_call_log(tmp_path, items=items, open_numbers=[71002])

    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env, script=private_copy)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    gh_calls.write_text("")
    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env, script=private_copy)
    assert proc.returncode == 0, proc.stderr
    # With the short-circuit deleted, --from-plan is ignored and the mutated
    # copy falls through to a full board read -- the paired test's own
    # assertion ("no project item-list call") now goes RED here.
    calls = _gh_calls(gh_calls)
    assert any(c.startswith("project item-list") for c in calls), (
        "falsifiability check failed: expected the mutated copy to fall back to a full board read"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


# --------------------------------------------------------------------------
# changed-since-plan skip, paired with the unchanged-row-still-writes case
# --------------------------------------------------------------------------


def test_from_plan_skips_candidate_changed_since_plan_was_cut(tmp_path):
    items = [_item(72001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[72001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Someone (a human, another agent) hand-set Priority=P0 on the live
    # board after the plan was cut -- the plan still expects old_value=None.
    _set_items(tmp_path, [_item(72001, labels=["priority: P1"], priority="P0")])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    assert "skipped-changed-since-plan" in proc.stdout
    assert "72001" in proc.stdout
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("transition 72001") for line in log_lines), (
        "a candidate whose live value no longer matches the plan must NEVER be written"
    )
    rows = _log_rows(env, "backfill-priority")
    outcomes = [r for r in rows if r.get("issue") == 72001 and "outcome" in r]
    assert outcomes[-1]["outcome"] == "skipped-changed-since-plan"
    assert outcomes[-1]["live_value"] == "P0"


def test_changed_since_plan_skip_is_real_red_without_the_live_check(tmp_path):
    """Falsifiability for test_from_plan_skips_candidate_changed_since_plan_was_cut:
    on a PRIVATE COPY of the real script, make the live-value comparison
    always treat the plan's old_value as matching (i.e. delete the actual
    inequality check), and confirm the paired test's own assertions go RED
    -- the write proceeds even though the board changed underneath the plan.
    Single-file scratch copy only; never mutates the live tracked script."""
    private_copy = tmp_path / "priority_backfill_no_live_check_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)

    src = private_copy.read_text()
    old = "    if live.value != row.get(\"old_value\"):\n        return SKIP_CHANGED_SINCE_PLAN"
    assert old in src, "the live-value comparison was not found in the real script -- test can't prove RED"
    mutated = src.replace(old, "    if False:  # BUG: live-value comparison deleted for falsifiability check\n        return SKIP_CHANGED_SINCE_PLAN")
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(72001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[72001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env, script=private_copy)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    _set_items(tmp_path, [_item(72001, labels=["priority: P1"], priority="P0")])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env, script=private_copy)
    # With the comparison short-circuited to False, the write proceeds
    # despite the board having changed since the plan was cut -- the paired
    # test's "must NEVER be written" assertion goes RED here.
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 72001") for line in log_lines), (
        "falsifiability check failed: expected the mutated copy to write despite the live-value mismatch"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


def test_from_plan_writes_when_live_value_still_matches_plan(tmp_path):
    # The paired recovery case: an UNCHANGED row (live still matches the
    # plan's old_value) still gets written exactly as a normal --apply would.
    items = [_item(72002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[72002])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Board is untouched -- Priority is still empty, matching the plan.
    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    assert "wrote #72002 Priority = P1" in proc.stdout
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 72002") for line in log_lines)
    rows = _log_rows(env, "backfill-priority")
    outcomes = [r for r in rows if r.get("issue") == 72002 and "outcome" in r]
    assert outcomes[-1]["outcome"] == "ok"


def test_from_plan_reset_ready_skips_when_status_moved_since_plan(tmp_path):
    items = [_item(72003, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[72003])
    plan_proc = _run(tmp_path, _plan_args("reset-ready"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_reset-ready_*.jsonl")[0]

    # The operator moved it to "In progress" before this pass ran.
    _set_items(tmp_path, [_item(72003, status="In progress")])

    proc = _run(tmp_path, _rr_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    assert "skipped-changed-since-plan" in proc.stdout
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("transition 72003") for line in log_lines)


# --------------------------------------------------------------------------
# resume across passes: pass 1 writes N, pass 2 starts after N, nothing
# written twice
# --------------------------------------------------------------------------


def test_from_plan_resumes_across_passes_without_double_writing(tmp_path):
    items = [_item(73000 + i, labels=["priority: P2"]) for i in range(5)]
    numbers = [it["content"]["number"] for it in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc1 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file), "--limit", "3"]), env)
    assert proc1.returncode == 0, proc1.stderr
    written_pass1 = sorted(int(line.split()[1]) for line in _read_log(tmp_path) if line.startswith("transition"))
    assert len(written_pass1) == 3

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file), "--limit", "3"]), env)
    assert proc2.returncode == 0, proc2.stderr
    written_pass2 = sorted(int(line.split()[1]) for line in _read_log(tmp_path) if line.startswith("transition"))
    assert len(written_pass2) == 2, "pass 2 must pick up exactly the 2 remaining candidates"
    assert set(written_pass1).isdisjoint(written_pass2), "nothing may be written twice across passes"
    assert set(written_pass1) | set(written_pass2) == set(numbers)

    # A third pass has nothing left to do.
    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc3 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc3.returncode == 0, proc3.stderr
    assert "nothing left to do" in proc3.stdout
    assert _read_log(tmp_path) == []


# --------------------------------------------------------------------------
# intent-without-outcome (indeterminate) is skipped and listed
# --------------------------------------------------------------------------


def test_from_plan_skips_and_lists_indeterminate_candidate(tmp_path):
    items = [_item(74001, labels=["priority: P1"]), _item(74002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[74001, 74002])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Hand-craft a write-intent row for #74001 with NO outcome row -- as if a
    # prior run crashed between the log write and the outcome write.
    lp = _board_state_files(env, pattern="backfill-priority_*.jsonl")
    log_file = lp[0] if lp else (Path(env["CLAUDE_DIR"]) / ".board_state" / "backfill-priority_2026-01-01.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    intent_row = {
        "ts": "2026-01-01T00:00:00Z",
        "subcommand": "backfill-priority",
        "issue": 74001,
        "item_id": "PVTI_74001",
        "field": "Priority",
        "old_value": None,
        "new_value": "P1",
        "owner": "acme",
        "repo": DEFAULT_REPO,
        "project": 1,
    }
    with log_file.open("a") as fh:
        fh.write(json.dumps(intent_row) + "\n")

    proc = _run(tmp_path, _bf_args(["--from-plan", str(plan_file)]), env)  # dry-run
    assert proc.returncode == 0, proc.stderr
    assert "indeterminate" in proc.stdout
    assert "74001" in proc.stdout.split("indeterminate")[1].split("\n")[0]
    # 74002 is unaffected and still offered (queued for this pass's live check).
    assert "candidates queued for this pass's live checks" in proc.stdout
    assert "would set #74002" in proc.stdout


# --------------------------------------------------------------------------
# stale plan (>24h) refused, with the recovery (a fresh plan works)
# --------------------------------------------------------------------------


def test_from_plan_refuses_stale_plan_older_than_24h(tmp_path):
    items = [_item(75001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[75001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Rewrite the header's created_at to 25 hours ago.
    lines = plan_file.read_text().splitlines()
    header = json.loads(lines[0])
    header["created_at"] = "2020-01-01T00:00:00Z"
    plan_file.write_text(json.dumps(header) + "\n" + "\n".join(lines[1:]) + "\n")

    proc = _run(tmp_path, _bf_args(["--from-plan", str(plan_file)]), env)
    assert proc.returncode == 1
    assert "24" in proc.stderr and "hour" in proc.stderr.lower()
    assert "re-run" in proc.stderr.lower() or "plan" in proc.stderr.lower()


def test_from_plan_stale_plan_recovers_with_a_fresh_plan(tmp_path):
    items = [_item(75002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[75002])
    fresh_plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert fresh_plan_proc.returncode == 0, fresh_plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    assert "wrote #75002" in proc.stdout


# --------------------------------------------------------------------------
# header mismatch refused
# --------------------------------------------------------------------------


def test_from_plan_refuses_wrong_for_subcommand(tmp_path):
    items = [_item(76001, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[76001])
    plan_proc = _run(tmp_path, _plan_args("reset-ready"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_reset-ready_*.jsonl")[0]

    # Try to run backfill-priority against a reset-ready plan.
    proc = _run(tmp_path, _bf_args(["--from-plan", str(plan_file)]), env)
    assert proc.returncode == 1
    assert "reset-ready" in proc.stderr and "backfill-priority" in proc.stderr


def test_from_plan_refuses_owner_repo_project_mismatch(tmp_path):
    items = [_item(76002, labels=["priority: P1"], repo="acme/widgets")]
    env = _make_env(tmp_path, items=items, open_numbers=[76002], repo="acme/widgets")
    plan_proc = _run(tmp_path, _plan_args("backfill-priority", repo="acme/widgets"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--from-plan", str(plan_file)], repo="acme/OTHER-repo"), env)
    assert proc.returncode == 1
    assert "does not match" in proc.stderr


# --------------------------------------------------------------------------
# --min-budget refusal, paired with a sufficient-budget run
# --------------------------------------------------------------------------


def test_min_budget_refuses_when_remaining_too_low(tmp_path):
    items = [_item(77001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[77001], rate_limit_remaining=100)
    proc = _run(tmp_path, _bf_args(["--apply", "--min-budget", "2500"]), env)
    assert proc.returncode == 4
    # The fake rateLimit query decrements its counter by one on each call
    # (mirroring the real endpoint's own point cost), so "remaining=99" (not
    # the fixture's initial 100) is what the script actually observes.
    assert "remaining=99" in proc.stderr
    assert "2500" in proc.stderr
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_min_budget_allows_when_remaining_sufficient(tmp_path):
    items = [_item(77002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[77002], rate_limit_remaining=5000)
    proc = _run(tmp_path, _bf_args(["--apply", "--min-budget", "2500"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "wrote #77002" in proc.stdout


# --------------------------------------------------------------------------
# budget query failure -> exit 4, no writes
# --------------------------------------------------------------------------


def test_budget_query_failure_is_fail_closed_exit_4_no_writes(tmp_path):
    items = [_item(78001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[78001], rate_limit_fail=True)
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 4
    log_lines = _read_log(tmp_path)
    assert log_lines == []
    assert _board_state_files(env, pattern="backfill-priority_*.jsonl") == []


# --------------------------------------------------------------------------
# GraphQL cost line printed
# --------------------------------------------------------------------------


def test_graphql_cost_line_is_printed(tmp_path):
    items = [_item(79001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[79001])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "GraphQL cost of this run:" in proc.stdout
    assert "points" in proc.stdout


def test_graphql_cost_line_printed_on_from_plan_run_too(tmp_path):
    items = [_item(79002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[79002])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    assert "GraphQL cost of this run:" in proc.stdout


# --------------------------------------------------------------------------
# 40-write hard cap still holds under --from-plan
# --------------------------------------------------------------------------


def test_from_plan_hard_cap_of_40_still_enforced(tmp_path):
    items = [_item(80000 + i, labels=["priority: P2"]) for i in range(5)]
    numbers = [it["content"]["number"] for it in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file), "--limit", "41"]), env)
    assert proc.returncode != 0
    assert "40" in proc.stderr


# --------------------------------------------------------------------------
# reverse now uses the per-issue live field check instead of a full board
# read -- identical classification results to the full-board-read path,
# proven directly against the full pre-existing reverse test matrix above
# (those tests already exercise reverse end-to-end and all still pass
# unmodified), plus an explicit zero-item-list-call assertion here.
# --------------------------------------------------------------------------


def test_reverse_makes_zero_project_item_list_calls(tmp_path):
    items = [_item(81001, status="Ready #1")]
    env, gh_calls = _make_env_with_gh_call_log(tmp_path, items=items, open_numbers=[81001])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(81001, status="Backlog")])
    gh_calls.write_text("")

    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    calls = _gh_calls(gh_calls)
    assert not any(c.startswith("project item-list") for c in calls), (
        f"reverse must never call `gh project item-list`; calls were: {calls}"
    )
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert any(line.startswith("transition 81001") for line in log_lines)


# --------------------------------------------------------------------------
# FIX ROUND (2026-09-20) -- B1-B5, all EXECUTED live by the opus reviewer
# under this test module's own fake-gh harness. Root cause: the live check
# used to collapse "field genuinely empty" and "I don't know" (not found /
# not open / truncated / errors / item id changed) into the SAME (None,
# None) result, which a Priority row's old_value=None compares equal to.
# --------------------------------------------------------------------------


def _plan_header(path: Path) -> dict:
    return json.loads(path.read_text().splitlines()[0])


def _rewrite_plan_rows(path: Path, new_rows: list[dict], *, keep_header: bool = True) -> None:
    """Test helper: overwrite a plan file's candidate rows (everything after
    line 1) with `new_rows`, keeping the ORIGINAL header (so a test can
    prove the rows_sha256/row-validation checks fire on tampered rows under
    an otherwise-legitimate header) unless keep_header=False."""
    lines = path.read_text().splitlines()
    header = lines[0] if keep_header else json.dumps({**json.loads(lines[0])})
    new_lines = [header] + [json.dumps(r) for r in new_rows]
    path.write_text("\n".join(new_lines) + "\n")


# --------------------------------------------------------------------------
# B1 -- --from-plan must never write to an issue that left the board
# --------------------------------------------------------------------------


def test_b1_from_plan_skips_issue_removed_from_board_since_plan(tmp_path):
    items = [_item(90001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[90001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Issue removed from the project entirely (no matching project item at
    # all) -- but still an open issue (so the OPEN-state check alone would
    # not have caught this).
    _set_items(tmp_path, [])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("transition 90001") for line in log_lines), (
        "an issue no longer on the board must NEVER be written -- 'not found' is not 'empty'"
    )
    assert "skipped-not-on-board" in proc.stdout
    rows = _log_rows(env, "backfill-priority")
    outcomes = [r for r in rows if r.get("issue") == 90001 and "outcome" in r]
    assert outcomes[-1]["outcome"] == "skipped-not-on-board"


def test_b1_recovery_from_plan_writes_when_issue_genuinely_still_on_board(tmp_path):
    # Paired recovery: an issue genuinely still on the board, still empty,
    # still open -- writes normally.
    items = [_item(90002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[90002])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 90002") for line in log_lines)


def test_b1_is_real_red_without_the_found_check(tmp_path):
    """Falsifiability: on a private copy, short-circuit LiveField.found to
    always True so a not-found item is treated as found=True with value=None
    (the pre-fix collapse), and confirm the paired test's assertion goes RED."""
    private_copy = tmp_path / "priority_backfill_b1_red_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)
    src = private_copy.read_text()
    old = "    if live.truncated:\n        return SKIP_TRUNCATED\n    if not live.found:\n        return SKIP_NOT_ON_BOARD"
    assert old in src, "the found-check was not found in the real script -- test can't prove RED"
    mutated = src.replace(
        old,
        "    if live.truncated:\n        return SKIP_TRUNCATED\n    if False:  # BUG: found-check deleted for falsifiability\n        return SKIP_NOT_ON_BOARD",
    )
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(90003, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[90003])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env, script=private_copy)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    _set_items(tmp_path, [])  # issue removed from the board

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env, script=private_copy)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 90003") for line in log_lines), (
        "falsifiability check failed: expected the mutated copy to write to a removed issue"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


# --------------------------------------------------------------------------
# B2 -- --from-plan must never write to a CLOSED issue (both subcommands)
# --------------------------------------------------------------------------


def test_b2_backfill_from_plan_skips_issue_closed_since_plan(tmp_path):
    items = [_item(91001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[91001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Issue closed since the plan was cut -- still on the board (still
    # matches old_value=None) but no longer OPEN.
    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("transition 91001") for line in log_lines), (
        "a closed issue must NEVER be written by backfill-priority --from-plan"
    )
    assert "skipped-not-open" in proc.stdout


def test_b2_reset_ready_from_plan_skips_issue_closed_since_plan(tmp_path):
    items = [_item(91002, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[91002])
    plan_proc = _run(tmp_path, _plan_args("reset-ready"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_reset-ready_*.jsonl")[0]

    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed2.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))

    proc = _run(tmp_path, _rr_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert not any(line.startswith("transition 91002") for line in log_lines), (
        "a closed issue must NEVER be moved by reset-ready --from-plan"
    )
    assert "skipped-not-open" in proc.stdout


def test_b2_recovery_from_plan_writes_when_issue_still_open(tmp_path):
    items = [_item(91003, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[91003])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 91003") for line in log_lines)


def test_b2_is_real_red_without_the_open_check(tmp_path):
    """Falsifiability: short-circuit the is_open check so a closed issue is
    never caught, and confirm the paired test's assertion goes RED."""
    private_copy = tmp_path / "priority_backfill_b2_red_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)
    src = private_copy.read_text()
    old = (
        "    if live.is_open is not True:\n"
        "        # None means \"could not be determined\" (LiveField's contract): never assume open.\n"
        "        return SKIP_NOT_OPEN"
    )
    assert old in src, "the is_open check was not found in the real script -- test can't prove RED"
    mutated = src.replace(old, "    if False:  # BUG: is_open check deleted for falsifiability\n        return SKIP_NOT_OPEN")
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(91004, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[91004])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env, script=private_copy)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed3.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env, script=private_copy)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 91004") for line in log_lines), (
        "falsifiability check failed: expected the mutated copy to write to a closed issue"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


def test_b2_reverse_still_reverses_a_since_closed_issue(tmp_path):
    # Spec: undo must not be blocked merely because the issue was closed
    # afterwards -- classify_reverse_row still decides purely from the value.
    items = [_item(91005, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[91005])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # The write landed (Priority=P1); the issue is now ALSO closed.
    _set_items(tmp_path, [_item(91005, labels=["priority: P1"], priority="P1")])
    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed4.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    clear_calls = [line for line in log_lines if line.startswith("item-edit") and "--clear" in line]
    assert len(clear_calls) == 1, "reverse must still restore a since-closed issue's field"


# --------------------------------------------------------------------------
# B3 -- a tampered plan file must never write an arbitrary value to an
# arbitrary field on an arbitrary issue
# --------------------------------------------------------------------------


def test_b3_tampered_field_name_refuses_whole_file(tmp_path):
    items = [_item(92001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    tampered_row = {"repo": DEFAULT_REPO, "issue": 92001, "item_id": "PVTI_92001", "field": "Estimate", "old_value": None, "new_value": "999", "disposition": None}
    _rewrite_plan_rows(plan_file, [tampered_row])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode != 0
    log_lines = _read_log(tmp_path)
    assert log_lines == [], "a tampered field name must refuse the WHOLE file with zero gh_issue.sh calls"


def test_b3_tampered_issue_number_refuses_whole_file(tmp_path):
    items = [_item(92002, labels=["priority: P1"]), _item(1, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92002, 1])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    tampered_row = {"repo": DEFAULT_REPO, "issue": 1, "item_id": "PVTI_1", "field": "Priority", "old_value": None, "new_value": "P0", "disposition": None}
    _rewrite_plan_rows(plan_file, [tampered_row])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode != 0
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_b3_tampered_new_value_not_a_real_option_refuses_whole_file(tmp_path):
    items = [_item(92003, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92003])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    tampered_row = {"repo": DEFAULT_REPO, "issue": 92003, "item_id": "PVTI_92003", "field": "Priority", "old_value": None, "new_value": "P9-NOT-A-REAL-OPTION", "disposition": None}
    _rewrite_plan_rows(plan_file, [tampered_row])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode != 0
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_b3_tampered_repo_ignored_on_row_refuses_whole_file(tmp_path):
    items = [_item(92004, labels=["priority: P1"], repo="acme/widgets")]
    env = _make_env(tmp_path, items=items, open_numbers=[92004], repo="acme/widgets")
    plan_proc = _run(tmp_path, _plan_args("backfill-priority", repo="acme/widgets"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    tampered_row = {"repo": "attacker/other-repo", "issue": 92004, "item_id": "PVTI_92004", "field": "Priority", "old_value": None, "new_value": "P1", "disposition": None}
    _rewrite_plan_rows(plan_file, [tampered_row])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)], repo="acme/widgets"), env)
    assert proc.returncode != 0
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_b3_duplicate_repo_issue_pair_refuses_whole_file(tmp_path):
    items = [_item(92005, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92005])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    row = {"repo": DEFAULT_REPO, "issue": 92005, "item_id": "PVTI_92005", "field": "Priority", "old_value": None, "new_value": "P1", "disposition": "mapped"}
    _rewrite_plan_rows(plan_file, [row, dict(row)])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode != 0
    assert "duplicate" in proc.stderr.lower()


def test_b3_tampered_rows_hash_mismatch_refuses_whole_file(tmp_path):
    # Even a VALID-looking row is refused if it wasn't in the plan at hash
    # time -- proves the rows_sha256 check, not just row validation.
    items = [_item(92006, labels=["priority: P1"]), _item(92007, labels=["priority: P2"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92006, 92007])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Swap in a row for a DIFFERENT (but otherwise well-formed) issue.
    row = {"repo": DEFAULT_REPO, "issue": 92007, "item_id": "PVTI_92007", "field": "Priority", "old_value": None, "new_value": "P2", "disposition": "mapped"}
    _rewrite_plan_rows(plan_file, [row])

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode != 0
    assert "rows_sha256" in proc.stderr
    log_lines = _read_log(tmp_path)
    assert log_lines == []


def test_b3_recovery_untampered_plan_runs(tmp_path):
    items = [_item(92008, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92008])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 92008") for line in log_lines)


def test_b3_is_real_red_without_row_validation(tmp_path):
    """Falsifiability: on a private copy, make _validate_plan_row a no-op,
    and confirm a tampered field name is no longer refused."""
    private_copy = tmp_path / "priority_backfill_b3_red_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)
    src = private_copy.read_text()
    old = 'def _validate_plan_row(row: dict[str, Any], *, index: int, for_subcommand: str, repo: str) -> None:'
    assert old in src, "_validate_plan_row was not found in the real script -- test can't prove RED"
    # Insert an early return right after the docstring's closing marker for
    # the function -- simplest reliable RED: monkeypatch via a module-level
    # override appended at end of file (never touches the real script).
    marker = '\nif __name__ == "__main__":'
    assert marker in src
    mutated = src.replace(
        marker,
        '\ndef _validate_plan_row(row, *, index, for_subcommand, repo):\n    return  # BUG: validation disabled for falsifiability check\n\n\n' + marker.strip(),
    )
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(92009, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[92009])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env, script=private_copy)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    tampered_row = {"repo": DEFAULT_REPO, "issue": 92009, "item_id": "PVTI_92009", "field": "Estimate", "old_value": None, "new_value": "999", "disposition": None}
    _rewrite_plan_rows(plan_file, [tampered_row])

    # Also needs the rows_sha256 to match, or the hash check (still active)
    # would catch it independently -- recompute and patch the header so
    # ONLY row validation is under test.
    import hashlib as _hashlib
    canonical = json.dumps(
        {"repo": tampered_row["repo"], "issue": tampered_row["issue"], "item_id": tampered_row["item_id"], "field": tampered_row["field"], "old_value": tampered_row["old_value"], "new_value": tampered_row["new_value"]},
        sort_keys=True,
    )
    new_hash = _hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    lines = plan_file.read_text().splitlines()
    header = json.loads(lines[0])
    header["rows_sha256"] = new_hash
    plan_file.write_text(json.dumps(header) + "\n" + json.dumps(tampered_row) + "\n")

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env, script=private_copy)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 92009") for line in log_lines), (
        "falsifiability check failed: expected the mutated copy to write an arbitrary field"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


# --------------------------------------------------------------------------
# B4 -- two concurrent --apply runs must never double-write or breach the cap
# --------------------------------------------------------------------------


def test_b4_second_concurrent_apply_refused_zero_writes(tmp_path):
    import fcntl as _fcntl

    items = [_item(93001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[93001])

    claude_dir = Path(env["CLAUDE_DIR"])
    lock_path = claude_dir / ".board_state" / f".lock_acme_{DEFAULT_REPO.replace('/', '_')}_1"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    held_fh = lock_path.open("a+")
    _fcntl.flock(held_fh.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    try:
        proc = _run(tmp_path, _bf_args(["--apply"]), env)
        assert proc.returncode != 0
        assert "another --apply pass is already running" in proc.stderr
        log_lines = _read_log(tmp_path)
        assert log_lines == [], "a lock-refused run must perform ZERO writes"
    finally:
        held_fh.close()


def test_b4_recovery_apply_runs_after_lock_released(tmp_path):
    import fcntl as _fcntl

    items = [_item(93002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[93002])

    claude_dir = Path(env["CLAUDE_DIR"])
    lock_path = claude_dir / ".board_state" / f".lock_acme_{DEFAULT_REPO.replace('/', '_')}_1"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    held_fh = lock_path.open("a+")
    _fcntl.flock(held_fh.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    held_fh.close()  # release -- OS drops the lock on close

    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 93002") for line in log_lines)


def test_b4_two_real_concurrent_processes_never_double_write(tmp_path):
    # The reviewer's own 2-process scenario: two REAL subprocess --apply
    # runs launched close together against the same plan/board, --limit 6,
    # 6 candidates -- must produce exactly 6 writes total, none twice.
    items = [_item(93100 + i, labels=["priority: P2"]) for i in range(6)]
    numbers = [it["content"]["number"] for it in items]
    env = _make_env(tmp_path, items=items, open_numbers=numbers)

    procs = [
        subprocess.Popen(
            [sys.executable, str(REAL_SCRIPT), *_bf_args(["--apply", "--limit", "6"])],
            cwd=str(tmp_path),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    for p in procs:
        p.communicate(timeout=30)

    log_lines = _read_log(tmp_path)
    written_issues = [line.split()[1] for line in log_lines if line.startswith("transition")]
    assert len(written_issues) == len(set(written_issues)), (
        f"an issue was written more than once across two concurrent passes: {written_issues}"
    )
    assert len(written_issues) <= 6
    # At least one of the two processes must have been refused the lock
    # (since a fresh non-blocking flock on the very first --apply of a test
    # is never pre-held, but the two subprocesses race for it -- exactly one
    # winner is expected in practice; this asserts the INVARIANT that
    # matters -- no double-write and no over-cap -- rather than which one won).
    returncodes = {p.returncode for p in procs}
    assert returncodes == {0, 1}  # exactly one winner and one refusal -- never both refused, never both raced


# --------------------------------------------------------------------------
# B5 -- reverse of a reset-ready log must not hard-fail on a board with no
# Priority field
# --------------------------------------------------------------------------


_GH_STUB_NO_PRIORITY_FIELD = _GH_STUB.replace(
    '{\\"fields\\": [{\\"name\\": \\"Priority\\", \\"id\\": \\"FIELD_priority\\"}, {\\"name\\": \\"Status\\", \\"id\\": \\"FIELD_status\\"}]}',
    '{\\"fields\\": [{\\"name\\": \\"Status\\", \\"id\\": \\"FIELD_status\\"}]}',
)


def _make_env_no_priority_field(tmp_path: Path, **kwargs) -> dict:
    """Same as _make_env, but the fake `gh project field-list` response
    carries NO Priority field at all -- B5's regression scenario."""
    env = _make_env(tmp_path, **kwargs)
    gh = Path(env["PRIORITY_BACKFILL_GH_BIN"])
    gh.write_text(_GH_STUB_NO_PRIORITY_FIELD)
    gh.chmod(0o755)
    return env


def test_b5_reverse_reset_ready_log_succeeds_on_board_without_priority_field(tmp_path):
    items = [_item(94001, status="Ready #1")]
    env = _make_env_no_priority_field(tmp_path, items=items, open_numbers=[94001])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(94001, status="Backlog")])
    Path(env["GH_ISSUE_LOG"]).write_text("")

    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env)
    assert proc2.returncode == 0, f"reverse of a reset-ready log must succeed on a board with no Priority field: {proc2.stderr}"
    log_lines = Path(env["GH_ISSUE_LOG"]).read_text().splitlines()
    assert any(line.startswith("transition 94001") for line in log_lines)


def test_b5_paired_reverse_backfill_log_fails_clearly_when_field_genuinely_needed(tmp_path):
    # Paired: reversing a BACKFILL log (whose old_value is empty, so
    # `reverse` needs restore_to_empty's Priority FIELD id, unlike the
    # reset-ready case above) on a board that genuinely has NO Priority
    # field must still fail clearly -- the B5 split (project-id-only vs.
    # project+field) must not have made this silently succeed too. The
    # backfill-priority --apply run itself is done on a board WITH a
    # Priority field (this harness's normal fixture) so the write lands;
    # only the SUBSEQUENT reverse runs against the Priority-less board.
    items = [_item(94002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[94002])
    proc = _run(tmp_path, _bf_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="backfill-priority_*.jsonl")[0]

    # Now point the fake gh at a board with NO Priority field for the
    # reverse run -- restore_to_empty's field-id resolution must fail.
    env_no_priority = _make_env_no_priority_field(tmp_path, items=[_item(94002, labels=["priority: P1"], priority="P1")], open_numbers=[94002])
    env_no_priority["CLAUDE_DIR"] = env["CLAUDE_DIR"]  # same board-state dir, so the log is visible

    Path(env["GH_ISSUE_LOG"]).write_text("")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env_no_priority)
    assert proc2.returncode != 0, "reversing a backfill log genuinely needs the Priority field id and must fail clearly when it's absent"


def test_b5_is_real_red_without_the_split(tmp_path):
    """Falsifiability: on a private copy, revert cmd_reverse's project-id
    resolution back to the combined (project+field) resolver, and confirm
    the paired test goes RED (reverse of a reset-ready log fails)."""
    private_copy = tmp_path / "priority_backfill_b5_red_copy.py"
    shutil.copy2(REAL_SCRIPT, private_copy)
    src = private_copy.read_text()
    old = "    project_node_id = _resolve_project_id(owner, project)\n\n    def _live_lookup(issue_num: int, field: str) -> LiveField:"
    assert old in src, "the project-only resolver call was not found in the real script -- test can't prove RED"
    mutated = src.replace(
        old,
        "    project_node_id, _unused = _resolve_project_and_field_ids(owner, project, PRIORITY_FIELD)  # BUG: reverted to combined resolver\n\n    def _live_lookup(issue_num: int, field: str) -> LiveField:",
    )
    assert mutated != src
    private_copy.write_text(mutated)

    items = [_item(94003, status="Ready #1")]
    env = _make_env_no_priority_field(tmp_path, items=items, open_numbers=[94003])
    proc = _run(tmp_path, _rr_args(["--apply"]), env, script=private_copy)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(94003, status="Backlog")])
    Path(env["GH_ISSUE_LOG"]).write_text("")

    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env, script=private_copy)
    assert proc2.returncode != 0, (
        "falsifiability check failed: expected the mutated (reverted) copy to fail reversing a "
        "reset-ready log on a board with no Priority field"
    )
    assert _sha256(REAL_SCRIPT) == _REAL_SCRIPT_SHA_AT_START


# --------------------------------------------------------------------------
# Non-blocking item 6 -- permanently-skipped rule
# --------------------------------------------------------------------------


def test_item6_candidate_reoffered_once_then_permanently_skipped(tmp_path):
    items = [_item(95001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[95001])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    # Issue closed for every pass -- always skipped-not-open.
    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed_item6.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))

    proc1 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc1.returncode == 0, proc1.stderr
    assert "skipped-not-open" in proc1.stdout
    assert "permanently skipped" not in proc1.stdout

    proc2 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc2.returncode == 0, proc2.stderr
    assert "skipped-not-open" in proc2.stdout
    assert "permanently skipped" not in proc2.stdout

    proc3 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc3.returncode == 0, proc3.stderr
    assert "permanently skipped" in proc3.stdout
    assert "95001" in proc3.stdout
    # No THIRD live-check attempt -- nothing new logged on pass 3.
    assert "nothing left to do" in proc3.stdout or "candidates queued for this pass's live checks (up to --limit=40 writes): 0" in proc3.stdout


def test_item6_recovery_reopened_issue_still_writes_within_the_two_reoffers(tmp_path):
    items = [_item(95002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[95002])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_closed_item6b.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([]))
    proc1 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc1.returncode == 0, proc1.stderr
    assert "skipped-not-open" in proc1.stdout

    # Issue reopened before the second pass -- still within the re-offer window.
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([{"number": 95002}]))
    proc2 = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file)]), env)
    assert proc2.returncode == 0, proc2.stderr
    log_lines = _read_log(tmp_path)
    assert any(line.startswith("transition 95002") for line in log_lines)


def test_item6_skips_never_count_against_limit_writes_fill_the_slot(tmp_path):
    # A plan with skip-then-write candidates: --limit=1 must still produce
    # exactly 1 WRITE even though a skip is checked first, never treating
    # the skip itself as consuming the --limit slot.
    items = [
        _item(95101, labels=["priority: P1"]),  # will be closed -> skip
        _item(95102, labels=["priority: P1"]),  # stays open -> should write
    ]
    env = _make_env(tmp_path, items=items, open_numbers=[95101, 95102])
    plan_proc = _run(tmp_path, _plan_args("backfill-priority"), env)
    assert plan_proc.returncode == 0, plan_proc.stderr
    plan_file = _board_state_files(env, pattern="plan_backfill-priority_*.jsonl")[0]

    env["FAKE_GH_OPEN_ISSUES_JSON"] = str(tmp_path / "open_issues_partial.json")
    Path(env["FAKE_GH_OPEN_ISSUES_JSON"]).write_text(json.dumps([{"number": 95102}]))

    proc = _run(tmp_path, _bf_args(["--apply", "--from-plan", str(plan_file), "--limit", "1"]), env)
    assert proc.returncode == 0, proc.stderr
    log_lines = _read_log(tmp_path)
    written = [line.split()[1] for line in log_lines if line.startswith("transition")]
    assert written == ["95102"], "the --limit=1 write slot must go to the genuinely writable candidate, not be consumed by the skip"


# --------------------------------------------------------------------------
# Non-blocking item 8 -- reverse's --min-budget default is 300, not 2500
# --------------------------------------------------------------------------


def test_item8_reverse_default_min_budget_is_300_not_2500(tmp_path):
    # Setup write uses a SUFFICIENT budget (5000, the harness default) so
    # the reset-ready --apply setup step itself is unaffected by the
    # budget under test below -- only `reverse`'s own default is exercised.
    items = [_item(96001, status="Ready #1")]
    env = _make_env(tmp_path, items=items, open_numbers=[96001])
    proc = _run(tmp_path, _rr_args(["--apply"]), env)
    assert proc.returncode == 0, proc.stderr
    log_file = _board_state_files(env, pattern="reset-ready_*.jsonl")[0]

    _set_items(tmp_path, [_item(96001, status="Backlog")])
    Path(env["GH_ISSUE_LOG"]).write_text("")

    # 1000 remaining would refuse the OLD 2500 full-read default but must
    # PASS the new 300 from-plan-shaped default reverse now uses.
    env2 = dict(env)
    env2["FAKE_GH_RATE_LIMIT_COUNTER"] = str(tmp_path / "rl2.txt")
    Path(env2["FAKE_GH_RATE_LIMIT_COUNTER"]).write_text("1000")
    proc2 = _run(tmp_path, ["reverse", "--log", str(log_file), "--apply", "--delay", "0"], env2)
    assert proc2.returncode == 0, proc2.stderr


# --------------------------------------------------------------------------
# Non-blocking item 9 -- dead code removed (no test needed to prove removal;
# confirmed instead via the module docstring / consumer check in the report)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Non-blocking item 10 -- --min-budget 0 waives with an explicit line;
# negatives rejected
# --------------------------------------------------------------------------


def test_item10_min_budget_zero_waives_with_explicit_line(tmp_path):
    items = [_item(97001, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[97001], rate_limit_remaining=0)
    proc = _run(tmp_path, _bf_args(["--apply", "--min-budget", "0"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "budget gate WAIVED (--min-budget 0)" in proc.stdout


def test_item10_min_budget_negative_rejected_at_parser(tmp_path):
    items = [_item(97002, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[97002])
    proc = _run(tmp_path, _bf_args(["--apply", "--min-budget", "-1"]), env)
    assert proc.returncode == 1
    assert proc.returncode != 2


def test_item10_recovery_positive_min_budget_unaffected(tmp_path):
    items = [_item(97003, labels=["priority: P1"])]
    env = _make_env(tmp_path, items=items, open_numbers=[97003])
    proc = _run(tmp_path, _bf_args(["--apply", "--min-budget", "1"]), env)
    assert proc.returncode == 0, proc.stderr
    assert "WAIVED" not in proc.stdout


# --------------------------------------------------------------------------
# unit tests for the pure classification functions (no subprocess needed)
# --------------------------------------------------------------------------


def _load_real_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("priority_backfill_readonly2", REAL_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # READS the real script; never writes to it
    return mod


def test_classify_live_check_pure_function():
    mod = _load_real_module()
    LiveField = mod.LiveField

    # genuinely empty, open, on-board, not truncated -> safe to write (None)
    row = {"old_value": None, "item_id": "PVTI_1"}
    assert mod._classify_live_check(row, LiveField(found=True, item_id="PVTI_1", value=None, is_open=True, truncated=False)) is None

    # not found at all
    assert mod._classify_live_check(row, LiveField(found=False, item_id=None, value=None, is_open=True, truncated=False)) == mod.SKIP_NOT_ON_BOARD

    # truncated page
    assert mod._classify_live_check(row, LiveField(found=False, item_id=None, value=None, is_open=True, truncated=True)) == mod.SKIP_TRUNCATED

    # closed
    assert mod._classify_live_check(row, LiveField(found=True, item_id="PVTI_1", value=None, is_open=False, truncated=False)) == mod.SKIP_NOT_OPEN

    # open-state UNKNOWN (LiveField's contract: None means "could not be determined" and is
    # treated like False by every caller -- never assume open). Round-2 review finding 1: the
    # classifier used `is False`, so None fell through to a write; unreachable from the only
    # producer today, but a latent re-opening of blocker 2 for any future LiveField source.
    assert mod._classify_live_check(row, LiveField(found=True, item_id="PVTI_1", value=None, is_open=None, truncated=False)) == mod.SKIP_NOT_OPEN

    # item id changed
    assert mod._classify_live_check(row, LiveField(found=True, item_id="PVTI_DIFFERENT", value=None, is_open=True, truncated=False)) == mod.SKIP_ITEM_ID_CHANGED

    # value differs
    row2 = {"old_value": None, "item_id": None}
    assert mod._classify_live_check(row2, LiveField(found=True, item_id="PVTI_2", value="P0", is_open=True, truncated=False)) == mod.SKIP_CHANGED_SINCE_PLAN
