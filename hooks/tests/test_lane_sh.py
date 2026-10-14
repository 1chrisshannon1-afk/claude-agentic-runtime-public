"""Tests for `~/.claude/scripts/lane.sh` (LANE CONTROL).

Spec source: `~/.claude/plans/handoff_lane_control_2026_09_23.md` + the adoption
master plan's §7.1/§7.2. These tests assert the INTENDED contract, never
whatever the script happens to do:

  1. A lane is opened only against an issue that PROVABLY exists and is in the
     repo's pick source. "Provably" is load-bearing -- see (2).
  2. `gh issue view` returns EXIT 1 BOTH for "no such issue" AND for "GitHub is
     unreachable" (measured on this machine 2026-09-23). The contract is
     asymmetric: fail CLOSED on a proven absence, WARN-AND-PROCEED on an
     unreachable API. A naive exit-code-only implementation inverts this on a
     network outage, so test 4 is the falsifiable inverse of test 3 and is the
     single most valuable test in this file.
  3. Caps (`lane.max_open`, `lane.max_abandoned`) are enforced before any
     mutation.
  4. EVERY refusal precedes EVERY mutation: a refused `open` leaves no
     worktree, no branch, and a byte-identical ledger.
  5. `reap` removes a lane only when ALL THREE of ancestry, clean-tree, and
     not-busy hold. An ERRORING `git status` is NOT clean (CLAUDE.md §2 names
     this trap); a non-ancestor tip is `needs-manual-reap`, never a forced
     delete.
  6. `--force` / `discard_changes` appear nowhere in any code path.
  7. `abandon` KEEPS the worktree.

Every refusal test is paired with a RECOVERY test: the refused thing succeeds
once the legitimate remedy is applied.

Conventions follow `test_gh_issue_create_dupe_search_failure.py`: the real
script runs against a stubbed `gh` on PATH recording argv to `$GH_LOG`, so no
network call is ever made. `LANE_SH` is honored so this suite can be pointed at
a scratch pre-change copy to prove the RED case genuinely fails without the
script (falsifiability). `LANE_DIR` and `CLAUDE_DIR` are redirected into a tmp
dir by an autouse fixture, so the real `~/.claude/.lanes/` ledger is never
touched. Repos are throwaway `git init` trees, never the real Agency or CSA.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

LANE_SH = os.environ.get(
    "LANE_SH", str(Path.home() / ".claude" / "scripts" / "lane.sh")
)
REPO_MANIFEST_PY = str(Path.home() / ".claude" / "scripts" / "repo_manifest.py")


# ---------------------------------------------------------------------------
# gh stubs
# ---------------------------------------------------------------------------

# Issue exists, and is in `Ready #1` on the board.
_GH_OK = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Ready #1"}]}'
  exit 0
fi
exit 0
"""

# Issue provably does not exist: gh's real stderr text, exit 1.
_GH_NO_SUCH = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "GraphQL: Could not resolve to an issue or pull request with the number of $3. (repository.issue)" >&2
  exit 1
fi
exit 0
"""

# GitHub unreachable: ALSO exit 1, but a different stderr text. The contract
# says WARN AND PROCEED here. This is the inverse of _GH_NO_SUCH and is what an
# exit-code-only implementation gets backwards.
_GH_UNREACHABLE = """#!/bin/bash
echo "$@" >> "$GH_LOG"
echo "error connecting to api.github.com" >&2
echo "check your internet connection or https://githubstatus.com" >&2
exit 1
"""

# Issue exists but is NOT in the pick source (e.g. sitting in Backlog).
_GH_NOT_PICKED = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Backlog"}]}'
  exit 0
fi
exit 0
"""

# ---------------------------------------------------------------------------
# label pick-source + issue-state gh stubs (D2/D3 §6)
# ---------------------------------------------------------------------------

# Issue OPEN, labeled `sprint:S1`. The label arm must never call `project`.
_GH_LABELED = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":[{"id":"LA_kwTest1","name":"sprint:S1","description":"Sprint 1","color":"5319E7"}]}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# Same as _GH_LABELED, but with a malformed (null) element ahead of the real
# match -- proves a malformed element is skipped, not fatal.
_GH_LABELED_WITH_NULL = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":[null,{"id":"LA_kwTest1","name":"sprint:S1","description":"Sprint 1","color":"5319E7"}]}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# Issue OPEN, but not labeled `sprint:S1` -- proves the match is exact and
# case-sensitive (carries `Sprint:S1` and `sprint:S2`, neither an exact match).
_GH_UNLABELED = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":[{"id":"LA_kwTest2","name":"Sprint:S1","description":"d","color":"E4622F"},{"id":"LA_kwTest3","name":"sprint:S2","description":"d","color":"84B6EB"}]}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# The labels call itself fails (network-shaped error) -- indeterminate.
_GH_LABELS_FAIL = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo "error connecting to api.github.com" >&2; exit 1 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# The labels call succeeds but the body is not JSON at all.
_GH_LABELS_GARBAGE = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo "not json"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# The labels call succeeds but `labels` is not a list.
_GH_LABELS_NOT_LIST = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":{}}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# The labels call succeeds but its only element is null (GAP 2's crash case,
# pinned: this is caught by the try wrapper before it can exit 1 as a false
# "not eligible").
_GH_LABELS_NULL_EL = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":[null]}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# Issue CLOSED, labeled sprint:S1 (labeled but not open -- issue-closed wins).
_GH_CLOSED_LABELED = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
    *" --json labels "*) echo '{"labels":[{"id":"LA_kwTest1","name":"sprint:S1","description":"Sprint 1","color":"5319E7"}]}'; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"CLOSED"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  exit 1
fi
exit 0
"""

# Issue CLOSED, project_status variant: `project` still answers Ready #1 like
# _GH_OK, so the refusal is provably from the state check, not R4.
_GH_CLOSED_READY = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"CLOSED"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Ready #1"}]}'
  exit 0
fi
exit 0
"""

# --json number,state reply is missing `state` entirely.
_GH_STATE_MISSING = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"'}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Ready #1"}]}'
  exit 0
fi
exit 0
"""

# --json number,state reply has a lowercase state.
_GH_STATE_LOWER = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"open"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Ready #1"}]}'
  exit 0
fi
exit 0
"""

# --json number,state reply is not JSON at all.
_GH_STATE_GARBAGE = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo "not json"
  exit 0
fi
if [ "$1" = "project" ]; then
  echo '{"items":[{"content":{"type":"Issue","repository":"acme/testrepo","number":'"$LANE_TEST_ISSUE"'},"status":"Ready #1"}]}'
  exit 0
fi
exit 0
"""

# State OPEN, but the `project` call itself fails (network-shaped error).
_GH_PROJECT_FAIL = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  echo "error connecting to api.github.com" >&2
  exit 1
fi
exit 0
"""


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path):
    """Hermetic environment: stub bin on PATH, tmp ledger, tmp CLAUDE_DIR."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    lane_dir = tmp_path / "lanes"
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    e = dict(os.environ)
    e.pop("LANE_BOARD_ITEM_LIMIT", None)  # an operator's export must not leak into tests
    e["PATH"] = f"{bindir}:{e['PATH']}"
    e["GH_LOG"] = str(tmp_path / "gh.log")
    e["LANE_DIR"] = str(lane_dir)
    e["CLAUDE_DIR"] = str(claude_dir)
    e["REPO_MANIFEST_PY"] = REPO_MANIFEST_PY
    e["LANE_TEST_ISSUE"] = "42"
    # Keep git deterministic and quiet inside the throwaway repos.
    e["GIT_AUTHOR_NAME"] = e["GIT_COMMITTER_NAME"] = "t"
    e["GIT_AUTHOR_EMAIL"] = e["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
    return {
        "env": e,
        "bindir": bindir,
        "lane_dir": lane_dir,
        "ledger": lane_dir / "lanes.jsonl",
        "tmp": tmp_path,
    }


def stub_gh(env, body):
    p = env["bindir"] / "gh"
    p.write_text(body)
    p.chmod(0o755)


MANIFEST = {
    "schema_version": 1,
    "product": {"name": "Test Repo", "slug": "testrepo"},
    "github": {
        "repo": "acme/testrepo",
        "project_number": 2,
        "project_owner": "acme",
    },
    "gtm": {"missions_dir": "missions", "inbox_label": "dept:marketing"},
    "lane": {
        "base_ref": "origin/main",
        "pr_target": "main",
        "branch_prefix": "issue",
        "pick_source": {
            "kind": "project_status",
            "project": 2,
            "owner": "acme",
            "status": "Ready #1",
        },
        "max_open": 3,
        "max_abandoned": 3,
    },
}


def lane_manifest(drop=(), **overrides):
    """MANIFEST with its `lane` block's keys dropped and/or overridden (a fresh dict)."""
    lane = {k: v for k, v in MANIFEST["lane"].items() if k not in drop}
    lane.update(overrides)
    return {**MANIFEST, "lane": lane}


LABEL_PS = {"kind": "label", "label": "sprint:S1"}


def make_repo(tmp_path, name="repo", manifest=MANIFEST):
    """A throwaway git repo with an `origin/main` remote-tracking ref.

    `origin` is a real local bare-ish clone source so `git fetch origin main`
    succeeds offline and `origin/main` genuinely resolves -- lane.sh's ancestry
    check is only meaningful against a real ref.
    """
    upstream = tmp_path / f"{name}-upstream.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(upstream)],
                   check=True, capture_output=True)
    repo = tmp_path / name
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n")
    (repo / "missions").mkdir()
    (repo / "missions" / ".keep").write_text("")
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    if manifest is not None:
        (oversight / "manifest.json").write_text(json.dumps(manifest, indent=2))
    _git(repo, "add", "README.md", "missions/.keep")
    _git(repo, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "init")
    _git(repo, "remote", "add", "origin", str(upstream))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin", "main")
    return repo


def _git(repo, *args):
    e = dict(os.environ)
    e.setdefault("GIT_AUTHOR_NAME", "t")
    e.setdefault("GIT_COMMITTER_NAME", "t")
    e.setdefault("GIT_AUTHOR_EMAIL", "t@example.invalid")
    e.setdefault("GIT_COMMITTER_EMAIL", "t@example.invalid")
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=e, check=False)


def lane(env, repo, *args):
    return subprocess.run(
        ["bash", LANE_SH, *args],
        cwd=str(repo), env=env["env"], capture_output=True, text=True,
    )


def call_lane_function(env, repo, wt, func, extra_setup=""):
    """Invoke a single internal `lane.sh` function directly (e.g.
    `link_extra_paths`) against a live `REPO_ROOT`/`REPO_MANIFEST`, without
    going through `open`/`reap`/etc.

    `lane.sh` ends in a bare `case "${1:-}" in ... esac` dispatch with no
    "return if sourced" guard, and every non-matching arm calls `exit 2` --
    sourcing the WHOLE file with no matching subcommand argument terminates
    the sourcing shell outright (`exit` inside a sourced script exits the
    parent shell, not just the source). So this sources only the portion of
    the file BEFORE that trailing dispatch (its function definitions), never
    the whole file, and then calls exactly the one function under test with
    `REPO_ROOT`/`REPO_MANIFEST` pre-set as `lane.sh`'s own `resolve_repo`/
    top-of-file would have set them.
    """
    src = Path(LANE_SH).read_text()
    marker = 'case "${1:-}" in'
    idx = src.index(marker)
    assert idx > 0, f"{LANE_SH} dispatch marker moved; update call_lane_function"
    funcs_only = src[:idx]
    script = (
        funcs_only
        + f'\nREPO_ROOT={str(repo)!r}\n'
        + f'REPO_MANIFEST={REPO_MANIFEST_PY!r}\n'
        + extra_setup
        + f'\n{func} {str(wt)!r}\n'
        + 'printf "%s\\n" "${LANE_EXTRA_LINKED[@]:-}"\n'
    )
    return subprocess.run(["bash", "-c", script], cwd=str(repo), env=env["env"],
                          capture_output=True, text=True)


def ledger_bytes(env):
    p = env["ledger"]
    return p.read_bytes() if p.exists() else b""


def worktrees(repo):
    d = repo / ".claude" / "worktrees"
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def branches(repo):
    out = _git(repo, "branch", "--format=%(refname:short)").stdout
    return sorted(x.strip() for x in out.splitlines() if x.strip())


# ---------------------------------------------------------------------------
# 1. no manifest -> refuse | recovery: manifest present -> proceeds
# ---------------------------------------------------------------------------


def test_no_manifest_refuses(env, tmp_path):
    repo = make_repo(tmp_path, manifest=None)
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "no-manifest" in r.stderr
    assert worktrees(repo) == []
    assert ledger_bytes(env) == before


def test_no_manifest_recovery_manifest_present_opens(env, tmp_path):
    repo = make_repo(tmp_path)  # manifest present
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert any(n.startswith("issue-42-") for n in worktrees(repo))


# ---------------------------------------------------------------------------
# 2. malformed issue number -> refuse | recovery: a valid one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["abc", "4.2", "-1", ""])
def test_bad_issue_number_refuses(env, tmp_path, bad):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", bad)
    assert r.returncode != 0
    assert "bad-issue" in r.stderr
    assert worktrees(repo) == []
    assert ledger_bytes(env) == before


def test_bad_issue_number_recovery_valid_number_opens(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# 3. no-such-issue -> FAIL CLOSED, nothing created
# ---------------------------------------------------------------------------


def test_no_such_issue_fails_closed_and_creates_nothing(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_NO_SUCH)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "999999999")
    assert r.returncode != 0
    assert "no-such-issue" in r.stderr
    assert "999999999" in r.stderr
    assert worktrees(repo) == []
    assert "issue/999999999" not in " ".join(branches(repo))
    assert ledger_bytes(env) == before


def test_no_such_issue_recovery_existing_issue_opens(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert any(n.startswith("issue-42-") for n in worktrees(repo))


# ---------------------------------------------------------------------------
# 4. github-unreachable -> WARN AND PROCEED (the falsifiable inverse of 3)
# ---------------------------------------------------------------------------


def test_github_unreachable_warns_and_proceeds(env, tmp_path):
    """Same exit code as test 3's stub, opposite required behavior.

    An implementation that keys off the exit status alone passes test 3 and
    FAILS this one. That is exactly why this pair exists.
    """
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_UNREACHABLE)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, f"unreachable GitHub must not block a lane: {r.stderr}"
    assert "github-unreachable" in r.stderr
    assert any(n.startswith("issue-42-") for n in worktrees(repo))


def test_github_unreachable_still_refuses_a_bad_issue_number(env, tmp_path):
    """The permissive path is narrow: it forgives an unverifiable issue, never
    a malformed one."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_UNREACHABLE)
    r = lane(env, repo, "open", "nope")
    assert r.returncode != 0
    assert "bad-issue" in r.stderr


# ---------------------------------------------------------------------------
# 5. not in pick source -> refuse | recovery: moved into it -> opens
# ---------------------------------------------------------------------------


def test_not_in_pick_source_refuses(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_NOT_PICKED)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "not-in-pick-source" in r.stderr
    assert worktrees(repo) == []
    assert ledger_bytes(env) == before


def test_pick_source_recovery_moved_to_ready_opens(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)  # the same issue, now in Ready #1
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


# 5b. Pick-source board reads (#5957). Live failure 2026-09-28: the board held
# 1,742 items, `gh project item-list --limit 800` never reached #5844 (in
# `Ready #1`), and `lane.sh open 5844` refused `not-in-pick-source`.

def _board_stub(body_py: str) -> str:
    """A gh stub whose `project item-list` output is computed by Python from
    the real argv (so --limit and --query are honoured, not ignored)."""
    return """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  case " $* " in
    *" --json title "*|*"-q .title"*) echo "Fix the thing"; exit 0 ;;
  esac
  echo '{"number":'"$3"',"state":"OPEN"}'
  exit 0
fi
if [ "$1" = "project" ]; then
  python3 - "$@" <<'PY'
import json, sys
args = sys.argv[1:]
limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 30
query = args[args.index("--query") + 1] if "--query" in args else None
""" + body_py + """
PY
  exit 0
fi
exit 0
"""


# A 1,742-item board shaped like the live one: #42 sits in Ready #1 at
# position 1,630; five other Ready items; everything else Backlog.
_BIG_BOARD = """
def it(num, status, repo="acme/testrepo", typ="Issue"):
    return {"content": {"type": typ, "repository": repo, "number": num}, "status": status}
board = []
for i in range(1, 1743):
    if i == 1630:
        board.append(it(42, "Ready #1"))
    elif i % 300 == 0:
        board.append(it(10000 + i, "Ready #1"))
    else:
        board.append(it(20000 + i, "Backlog"))
if query is not None:
    want = query.split(":", 1)[1].strip('"')
    board = [b for b in board if b["status"] == want]
print(json.dumps({"items": board[:limit], "totalCount": len(board)}))
"""


def test_ready_issue_deep_in_a_large_board_opens_cleanly(env, tmp_path):
    """#5844 simulated: RED on the pre-fix script (--limit 800, no filter)."""
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(_BIG_BOARD))
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "not-in-pick-source" not in r.stderr
    assert "pick-source-unreachable" not in (r.stderr + r.stdout)


def test_board_read_is_filtered_server_side_to_the_pick_source_status(env, tmp_path):
    """Guards the #5957 cost fix: with a small page limit, only a server-side
    `--query status:"Ready #1"` read reaches #42 without an inconclusive
    warning. Without the filter the stub returns 100 of 1,742 items."""
    repo = make_repo(tmp_path)
    env["env"]["LANE_BOARD_ITEM_LIMIT"] = "100"
    stub_gh(env, _board_stub(_BIG_BOARD))
    r = lane(env, repo, "open", "42")
    env["env"].pop("LANE_BOARD_ITEM_LIMIT")
    assert r.returncode == 0, r.stderr
    assert "inconclusive" not in r.stderr
    assert "pick-source-unreachable" not in (r.stderr + r.stdout)
    calls = [ln for ln in Path(env["env"]["GH_LOG"]).read_text().splitlines()
             if ln.startswith("project item-list")]
    assert calls and '--query status:"Ready #1"' in calls[0], calls


def test_repo_match_is_case_insensitive(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "ACME/TestRepo", '
        '"number": 42}, "status": "Ready #1"}], "totalCount": 1}))'))
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


def test_backlog_issue_in_a_large_board_still_refuses(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(_BIG_BOARD))
    r = lane(env, repo, "open", "20001")
    assert r.returncode != 0
    assert "not-in-pick-source" in r.stderr


def test_truncated_board_read_is_indeterminate_not_a_refusal(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "acme/testrepo", '
        '"number": 7}, "status": "Ready #1"}], "totalCount": 1742}))'))
    r = lane(env, repo, "open", "42")
    assert "not-in-pick-source" not in r.stderr
    assert "pick-source-unreachable" in (r.stderr + r.stdout)
    assert "read 1 of 1742 items" in r.stderr
    assert r.returncode == 0, r.stderr


def test_found_issue_in_a_cut_off_list_still_decides_by_status(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "acme/testrepo", '
        '"number": 42}, "status": "Backlog"}], "totalCount": 999}))'))
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "not-in-pick-source" in r.stderr


def test_reaching_the_limit_without_totalcount_is_indeterminate(env, tmp_path):
    repo = make_repo(tmp_path)
    env["env"]["LANE_BOARD_ITEM_LIMIT"] = "2"
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "acme/testrepo", '
        '"number": n}, "status": "Ready #1"} for n in (7, 8)][:limit]}))'))
    r = lane(env, repo, "open", "42")
    assert "not-in-pick-source" not in r.stderr
    assert "reached the limit 2" in r.stderr
    assert r.returncode == 0, r.stderr


def test_missing_or_non_numeric_totalcount_is_indeterminate(env, tmp_path):
    for total in ('None', '"lots"'):
        repo = make_repo(tmp_path, name=f"repo-{abs(hash(total))}")
        stub_gh(env, _board_stub(
            'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "acme/testrepo", '
            '"number": 7}, "status": "Ready #1"}], "totalCount": ' + total + '}))'))
        r = lane(env, repo, "open", "42")
        assert "not-in-pick-source" not in r.stderr, total
        assert "no numeric totalCount" in r.stderr, total


def test_foreign_repo_item_with_the_same_number_does_not_decide(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": ['
        '{"content": {"type": "Issue", "repository": "acme/otherrepo", "number": 42}, "status": "Ready #1"},'
        '{"content": {"type": "PullRequest", "repository": "acme/testrepo", "number": 42}, "status": "Ready #1"}'
        '], "totalCount": 2}))'))
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "not-in-pick-source" in r.stderr


def test_unexpected_board_json_shapes_are_indeterminate(env, tmp_path):
    for i, body in enumerate(('{"items": null}', '[1, 2]', '{"items": [3]}')):
        repo = make_repo(tmp_path, name=f"repo-shape-{i}")
        stub_gh(env, _board_stub(f"print({body!r})"))
        r = lane(env, repo, "open", "42")
        assert "not-in-pick-source" not in r.stderr, body
        assert "inconclusive" in r.stderr, body


def test_board_item_limit_override_and_fallback(env, tmp_path):
    for value, expected in (("500", "--limit 500"), ("abc", "--limit 10000"),
                            ("0", "--limit 10000"), ("007", "--limit 10000")):
        repo = make_repo(tmp_path, name=f"repo-limit-{value}")
        env["env"]["LANE_BOARD_ITEM_LIMIT"] = value
        Path(env["env"]["GH_LOG"]).write_text("")
        stub_gh(env, _board_stub(_BIG_BOARD))
        lane(env, repo, "open", "42")
        calls = [ln for ln in Path(env["env"]["GH_LOG"]).read_text().splitlines()
                 if ln.startswith("project item-list")]
        assert calls and expected in calls[0], (value, calls)
    env["env"].pop("LANE_BOARD_ITEM_LIMIT")


def test_complete_board_read_without_the_issue_still_refuses(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _board_stub(
        'print(json.dumps({"items": [{"content": {"type": "Issue", "repository": "acme/testrepo", '
        '"number": 7}, "status": "Ready #1"}], "totalCount": 1}))'))
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "not-in-pick-source" in r.stderr


# ---------------------------------------------------------------------------
# 6. cap on open lanes -> 4th refused | recovery: reap one -> opens
# ---------------------------------------------------------------------------


def _open_n(env, repo, numbers):
    for n in numbers:
        env["env"]["LANE_TEST_ISSUE"] = str(n)
        r = lane(env, repo, "open", str(n))
        assert r.returncode == 0, f"#{n}: {r.stderr}"


def test_fourth_open_lane_refused(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2, 3])
    before = ledger_bytes(env)
    env["env"]["LANE_TEST_ISSUE"] = "4"
    r = lane(env, repo, "open", "4")
    assert r.returncode != 0
    assert "cap-reached" in r.stderr
    assert not any(n.startswith("issue-4-") for n in worktrees(repo))
    assert ledger_bytes(env) == before


def test_cap_recovery_reap_one_then_fourth_opens(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2, 3])
    # Lane 1 was branched from origin/main and has no commits of its own, so
    # its tip IS an ancestor of origin/main: the legitimate reap path.
    r = lane(env, repo, "reap", "1")
    assert r.returncode == 0, r.stderr
    env["env"]["LANE_TEST_ISSUE"] = "4"
    r = lane(env, repo, "open", "4")
    assert r.returncode == 0, r.stderr
    assert any(n.startswith("issue-4-") for n in worktrees(repo))


# ---------------------------------------------------------------------------
# 7. abandoned backlog cap -> refuse | recovery: reap an abandoned one
# ---------------------------------------------------------------------------


def test_abandoned_backlog_refuses_new_open(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2, 3])
    for n in (1, 2, 3):
        assert lane(env, repo, "abandon", str(n)).returncode == 0
    before = ledger_bytes(env)
    env["env"]["LANE_TEST_ISSUE"] = "4"
    r = lane(env, repo, "open", "4")
    assert r.returncode != 0
    assert "abandoned-backlog" in r.stderr
    assert "operator prune card" in r.stderr
    assert ledger_bytes(env) == before


def test_abandoned_backlog_recovery_reap_abandoned_then_opens(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2, 3])
    for n in (1, 2, 3):
        assert lane(env, repo, "abandon", str(n)).returncode == 0
    r = lane(env, repo, "reap", "--abandoned", "1")
    assert r.returncode == 0, r.stderr
    env["env"]["LANE_TEST_ISSUE"] = "4"
    r = lane(env, repo, "open", "4")
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# 8. reap: non-ancestor tip -> refuse, worktree AND branch both survive
# ---------------------------------------------------------------------------


def test_reap_refuses_when_tip_is_not_an_ancestor_of_base(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    (wt / "work.txt").write_text("unlanded work\n")
    _git(wt, "add", "work.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "unlanded")

    r = lane(env, repo, "reap", "42")
    assert r.returncode != 0
    assert "needs-manual-reap" in r.stderr
    assert wt.is_dir(), "the worktree must survive a refused reap"
    assert any(b.startswith("issue/42-") for b in branches(repo)), \
        "the branch must survive a refused reap"
    assert (wt / "work.txt").read_text() == "unlanded work\n"


def test_reap_recovery_once_merged_to_base_it_reaps(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / name
    (wt / "work.txt").write_text("landed work\n")
    _git(wt, "add", "work.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "landed")
    branch = [b for b in branches(repo) if b.startswith("issue/42-")][0]
    # The legitimate remedy: the work actually lands on the base ref.
    _git(repo, "push", "-q", "origin", f"{branch}:main")
    _git(repo, "fetch", "-q", "origin", "main")

    r = lane(env, repo, "reap", "42")
    assert r.returncode == 0, r.stderr
    assert not wt.exists()
    assert not any(b.startswith("issue/42-") for b in branches(repo))


# ---------------------------------------------------------------------------
# 9. reap: dirty tree -> refuse | recovery: commit (and land) -> reaps
# ---------------------------------------------------------------------------


def test_reap_refuses_on_a_dirty_tree(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    (wt / "scratch.txt").write_text("uncommitted\n")

    r = lane(env, repo, "reap", "42")
    assert r.returncode != 0
    assert "dirty-tree" in r.stderr
    assert wt.is_dir()
    assert (wt / "scratch.txt").exists(), "a refused reap must not touch the tree"


def test_reap_dirty_recovery_commit_and_land_then_reaps(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    (wt / "scratch.txt").write_text("uncommitted\n")
    _git(wt, "add", "scratch.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "commit the scratch")
    branch = [b for b in branches(repo) if b.startswith("issue/42-")][0]
    _git(repo, "push", "-q", "origin", f"{branch}:main")
    _git(repo, "fetch", "-q", "origin", "main")

    r = lane(env, repo, "reap", "42")
    assert r.returncode == 0, r.stderr
    assert not wt.exists()


# ---------------------------------------------------------------------------
# 10. reap: a live process inside the lane -> refuse | recovery: it exits
# ---------------------------------------------------------------------------


def test_reap_refuses_while_a_process_holds_a_file_open(env, tmp_path):
    import shutil
    if not shutil.which("lsof"):
        pytest.skip("lsof unavailable")
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    # The held file must be COMMITTED, not untracked: the dirty-tree gate runs
    # before the busy gate, so an untracked scratch file would trip that one
    # instead and this test would silently stop exercising the busy gate at all.
    target = wt / "held.txt"
    target.write_text("x\n")
    _git(wt, "add", "held.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "held")
    branch = [b for b in branches(repo) if b.startswith("issue/42-")][0]
    _git(repo, "push", "-q", "origin", f"{branch}:main")
    _git(repo, "fetch", "-q", "origin", "main")
    # A child that holds the file open for the duration of the reap attempt.
    proc = subprocess.Popen(
        ["python3", "-c",
         f"f=open({str(target)!r}); import time; time.sleep(30)"],
    )
    try:
        import time
        time.sleep(1.5)  # let it actually open the fd
        r = lane(env, repo, "reap", "42")
        assert r.returncode != 0
        assert "lane-busy" in r.stderr
        assert wt.is_dir()
    finally:
        proc.kill()
        proc.wait()


def test_reap_busy_recovery_after_process_exits_it_reaps(env, tmp_path):
    import shutil
    if not shutil.which("lsof"):
        pytest.skip("lsof unavailable")
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    target = wt / "held.txt"
    target.write_text("x\n")
    _git(wt, "add", "held.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "held")
    branch = [b for b in branches(repo) if b.startswith("issue/42-")][0]
    _git(repo, "push", "-q", "origin", f"{branch}:main")
    _git(repo, "fetch", "-q", "origin", "main")
    proc = subprocess.Popen(
        ["python3", "-c",
         f"f=open({str(target)!r}); import time; time.sleep(1)"],
    )
    proc.wait()
    r = lane(env, repo, "reap", "42")
    assert r.returncode == 0, r.stderr
    assert not wt.exists()


# ---------------------------------------------------------------------------
# 11. reap: an ERRORING `git status` is NOT "clean"
# ---------------------------------------------------------------------------


def test_reap_refuses_when_git_status_errors(env, tmp_path):
    """A git error prints nothing on stdout. Reading "no output" as "clean" is
    the exact trap CLAUDE.md §2 names; the exit status must be checked."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    # Break the worktree's link to the object store: `git status` now exits
    # non-zero with empty stdout, exactly the shape of the trap.
    gitfile = wt / ".git"
    assert gitfile.exists()
    gitfile.unlink() if gitfile.is_file() else None
    gitfile.write_text("gitdir: /nonexistent/path/that/does/not/exist\n")

    r = lane(env, repo, "reap", "42")
    assert r.returncode != 0
    assert "status-unverifiable" in r.stderr
    assert wt.is_dir(), "an unverifiable status must not lead to removal"


def test_no_refusal_message_contains_an_unquoted_backtick(env, tmp_path):
    """REGRESSION (found 2026-09-23 by reading the rendered output, not the code).

    Inside a double-quoted bash string a backtick is COMMAND SUBSTITUTION, not
    quoting. Three refusal messages were written as "... `lane.sh status` ..."
    and "... `git status` failed ...", so building the message EXECUTED those
    commands: `git status` leaked its own stderr to the user and its (empty)
    output replaced the very words naming what failed, and the `lane.sh reap`
    one re-invoked this script recursively. A test that matches only the
    refusal CODE cannot see any of that -- which is exactly why the original
    suite missed it -- so this one asserts the human-readable text.
    """
    src = Path(LANE_SH).read_text()
    offenders = []
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#") or "`" not in line:
            continue
        # Backticks inside a heredoc body (python) or a comment are fine; a
        # backtick on a `refuse`/`warn`/`die`/`printf` line is a live
        # substitution in a message.
        if any(line.startswith(v) or f" {v} " in line
               for v in ("refuse", "warn", "die", "printf")):
            offenders.append((lineno, raw))
    assert not offenders, (
        "backtick = command substitution in a double-quoted message: %s" % offenders
    )


def test_status_unverifiable_message_names_git_status_literally(env, tmp_path):
    """The behavioral half: the rendered refusal must actually SAY what failed."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    gitfile = wt / ".git"
    if gitfile.is_file():
        gitfile.unlink()
    gitfile.write_text("gitdir: /nonexistent/path/that/does/not/exist\n")

    r = lane(env, repo, "reap", "42")
    assert r.returncode != 0
    assert "git status" in r.stderr, (
        f"the refusal must name the command that failed; got: {r.stderr!r}")
    assert "not a git repository" not in r.stderr, (
        "a substituted git command leaked its own stderr into the refusal")


def test_reap_status_recovery_healthy_git_reaps(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert _git(wt, "status", "--porcelain").returncode == 0
    r = lane(env, repo, "reap", "42")
    assert r.returncode == 0, r.stderr
    assert not wt.exists()


# ---------------------------------------------------------------------------
# 12. no code path emits --force / discard_changes
# ---------------------------------------------------------------------------


def test_script_source_never_forces():
    """No forbidden verb reaches a `git` INVOCATION.

    Scanned at the level of actual `git ...` command lines, with comments and
    quoted message text excluded -- the script legitimately mentions `--force`
    inside an error message explaining that it deliberately does NOT retry with
    it, and a naive substring grep over the whole file flags that prose.
    """
    import re

    src = Path(LANE_SH).read_text()
    # Falsifiability guard: a source-grep test passes vacuously against a stub
    # or an absent script (nothing to find), so it must first prove it is
    # reading a real lane.sh. Without this the test detects nothing at all.
    assert "worktree add" in src and "merge-base --is-ancestor" in src, (
        f"{LANE_SH} is not a real lane.sh; this grep would pass vacuously"
    )
    forbidden = ("--force", "discard_changes", "reset --hard",
                 "checkout", "stash", "clean -")
    offenders = []
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        # Drop quoted strings: messages, not commands.
        stripped = re.sub(r'"[^"]*"', '""', line)
        stripped = re.sub(r"'[^']*'", "''", stripped)
        if not re.search(r"\bgit\b", stripped):
            continue
        for bad in forbidden:
            if bad in stripped:
                offenders.append((lineno, bad, raw))
    assert not offenders, f"forbidden verb in a git invocation: {offenders}"


def test_force_is_only_ever_mentioned_in_an_explanatory_message():
    """The paired positive: the one `--force` in the file is prose saying the
    script refuses to use it. If that sentence is ever deleted along with the
    safety it documents, this test notices."""
    import re

    src = Path(LANE_SH).read_text()
    assert "worktree remove" in src, (
        f"{LANE_SH} is not a real lane.sh; this grep would pass vacuously"
    )
    code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    for ln in code_lines:
        if "--force" in ln:
            in_quotes = re.findall(r'"[^"]*"', ln)
            assert any("--force" in q for q in in_quotes), (
                f"--force appears outside a quoted message: {ln}"
            )


def test_reap_never_passes_force_to_git(env, tmp_path):
    """Argv-level proof, not just a grep: a `git` shim records every call."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    gitlog = env["tmp"] / "git.log"
    real_git = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
    shim = env["bindir"] / "git"
    shim.write_text(
        f'#!/bin/bash\necho "$@" >> {str(gitlog)!r}\nexec {real_git} "$@"\n'
    )
    shim.chmod(0o755)
    lane(env, repo, "reap", "42")
    calls = gitlog.read_text() if gitlog.exists() else ""
    assert "worktree remove" in calls, "the shim should have observed the removal"
    for line in calls.splitlines():
        if "worktree remove" in line or line.startswith("branch -D") or " branch -D" in line:
            assert "--force" not in line and " -f" not in line, line


# ---------------------------------------------------------------------------
# 13. abandon keeps the worktree
# ---------------------------------------------------------------------------


def test_abandon_keeps_the_worktree_on_disk(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    (wt / "wip.txt").write_text("work in progress\n")

    r = lane(env, repo, "abandon", "42")
    assert r.returncode == 0, r.stderr
    assert wt.is_dir(), "abandon means 'not now', never 'destroy'"
    assert (wt / "wip.txt").read_text() == "work in progress\n"
    assert any(b.startswith("issue/42-") for b in branches(repo))


def test_abandoned_lane_does_not_count_toward_the_open_cap(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2, 3])
    assert lane(env, repo, "abandon", "1").returncode == 0
    env["env"]["LANE_TEST_ISSUE"] = "4"
    r = lane(env, repo, "open", "4")
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# 14/15. ledger integrity
# ---------------------------------------------------------------------------


def test_every_refusal_leaves_the_ledger_byte_identical(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    before = ledger_bytes(env)
    assert before, "a successful open must have written a row"

    stub_gh(env, _GH_NO_SUCH)
    lane(env, repo, "open", "77")
    assert ledger_bytes(env) == before

    stub_gh(env, _GH_NOT_PICKED)
    env["env"]["LANE_TEST_ISSUE"] = "78"
    lane(env, repo, "open", "78")
    assert ledger_bytes(env) == before

    lane(env, repo, "open", "bad")
    assert ledger_bytes(env) == before


def test_ledger_rows_are_valid_json_and_append_only(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1, 2])
    lane(env, repo, "abandon", "1")
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert [r["event"] for r in rows] == ["open", "open", "abandoned"]
    for r in rows:
        assert set(r) >= {
            "ts", "event", "issue", "repo", "worktree", "branch",
            "pr_base", "pr", "session", "pid", "host",
        }
        assert os.path.isabs(r["worktree"]), "worktree path must be absolute"
        assert isinstance(r["issue"], int)


def test_owner_pid_is_the_session_not_the_short_lived_helper(env, tmp_path):
    """REGRESSION (found by the 2026-09-23 live proof run, before the fix).

    The row must record CLAUDE_PID -- the long-lived session -- not lane.sh's
    own `$$`. lane.sh exits within a second of writing the row, so recording
    its own pid makes that pid knowably dead immediately, and
    `lane_orphans.sh` then reports `dead-owner` for EVERY normally-opened
    lane. Same contract as hooks/file_claims.py::_owner_pid (#4670).
    """
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    env["env"]["CLAUDE_PID"] = str(os.getpid())  # this test process is alive
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert rows[0]["pid"] == os.getpid(), (
        "the owning session's pid must be recorded, not lane.sh's own"
    )


def test_owner_pid_is_null_when_the_session_pid_is_unknown(env, tmp_path):
    """The paired negative: an unresolvable CLAUDE_PID records NULL, never a
    knowably-dead fallback. A real-but-dead pid masquerades as a liveness
    signal; null honestly has none and every consumer fails open on it."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    env["env"].pop("CLAUDE_PID", None)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert rows[0]["pid"] is None


def test_concurrent_writers_do_not_interleave_rows(env, tmp_path):
    """Two lanes opened concurrently from different processes must each land
    exactly one intact row."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [1])  # ensure the ledger file exists
    procs = []
    for n in (2, 3):
        e = dict(env["env"])
        e["LANE_TEST_ISSUE"] = str(n)
        procs.append(subprocess.Popen(
            ["bash", LANE_SH, "open", str(n)],
            cwd=str(repo), env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ))
    for p in procs:
        p.wait()
    lines = [ln for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    for ln in lines:
        json.loads(ln)  # every line is an intact object, never a spliced pair
    assert len(lines) >= 2


# ---------------------------------------------------------------------------
# 16. a refused open is a true no-op at the git level
# ---------------------------------------------------------------------------


def test_refused_open_creates_no_branch_and_no_worktree_registration(env, tmp_path):
    """A refused open is a true no-op at the git level.

    POSITIVE CONTROL FIRST: a script that does nothing at all would also
    "create nothing", so this test would pass vacuously against an absent or
    stubbed lane.sh and prove exactly nothing. Asserting that a SUCCESSFUL open
    does register a branch and a worktree is what makes the negative half
    meaningful.
    """
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    baseline_branches = branches(repo)
    assert lane(env, repo, "open", "42").returncode == 0
    assert branches(repo) != baseline_branches, "control: a real open registers a branch"
    assert "issue-42-" in _git(repo, "worktree", "list").stdout, \
        "control: a real open registers a worktree"

    # Now the actual claim, measured against that live state.
    stub_gh(env, _GH_NO_SUCH)
    before_branches = branches(repo)
    before_wt = _git(repo, "worktree", "list").stdout
    lane(env, repo, "open", "999999999")
    assert branches(repo) == before_branches
    assert _git(repo, "worktree", "list").stdout == before_wt


# ---------------------------------------------------------------------------
# 17. lane.sh refuses to run from inside a lane
# ---------------------------------------------------------------------------


def test_open_from_inside_a_worktree_is_refused(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    env["env"]["LANE_TEST_ISSUE"] = "43"
    r = lane(env, wt, "open", "43")
    assert r.returncode != 0
    assert "nested-lane" in r.stderr


def test_open_from_the_main_checkout_recovery(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    _open_n(env, repo, [42])
    env["env"]["LANE_TEST_ISSUE"] = "43"
    r = lane(env, repo, "open", "43")
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# L5.5: lane.branch_prefix, closed-issue refusal, label pick source,
# pick-source shape validation, status BRANCH column, bad-args.
#
# "Zero trace" (per the spec) means: the ledger bytes are unchanged,
# worktrees(repo) == [], branches(repo) == ["main"], and, where stated, no
# $GH_LOG file exists at all (no `gh` call was ever made). Every test that
# asserts "no $GH_LOG" stubs a LOGGING gh first (never leaves the real `gh`
# reachable), so a genuinely-absent log file proves no call happened.
# ---------------------------------------------------------------------------


def test_issues_prefix_names_branch_and_ledger_but_not_worktree_dir(env, tmp_path):
    """Case 1."""
    repo = make_repo(tmp_path, manifest=lane_manifest(branch_prefix="issues"))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert branches(repo) == sorted(["issues/42-fix-the-thing", "main"])
    assert worktrees(repo) == ["issue-42-fix-the-thing"]
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert rows[-1]["branch"] == "issues/42-fix-the-thing"
    assert "branch   issues/42-fix-the-thing" in r.stdout


def test_issue_prefix_is_todays_csa_shape(env, tmp_path):
    """Case 2. The default MANIFEST now carries branch_prefix="issue", so the
    whole pre-existing suite (its issue/42-... assertions) doubles as this
    test, per the spec."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert any(b.startswith("issue/42-") for b in branches(repo))
    assert any(n.startswith("issue-42-") for n in worktrees(repo))
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert rows[-1]["branch"].startswith("issue/42-")


def test_missing_branch_prefix_refuses_with_zero_trace(env, tmp_path):
    """Case 3."""
    repo = make_repo(tmp_path, manifest=lane_manifest(drop=("branch_prefix",)))
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (manifest-key-missing) lane.branch_prefix" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


def test_missing_branch_prefix_recovery_key_added_opens(env, tmp_path):
    """Case 3 recovery: same repo, reproduce the refusal, then fix the manifest."""
    repo = make_repo(tmp_path, manifest=lane_manifest(drop=("branch_prefix",)))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (manifest-key-missing) lane.branch_prefix" in r.stderr

    (repo / ".claude" / "oversight" / "manifest.json").write_text(
        json.dumps(lane_manifest(branch_prefix="issues"), indent=2)
    )
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    "bad,shown",
    [
        ("Issue", "Issue"),
        ("-x", "-x"),
        ("a/b", "a/b"),
        ("issue/", "issue/"),
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (5, "5"),
    ],
)
def test_bad_branch_prefix_refuses_bad_manifest(env, tmp_path, bad, shown):
    """Case 4 (first half)."""
    repo = make_repo(tmp_path, manifest=lane_manifest(branch_prefix=bad))
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (bad-manifest) lane.branch_prefix" in r.stderr
    assert f"got '{shown}'" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


@pytest.mark.parametrize(
    "lc_all,bad",
    [
        ("en_US.UTF-8", "Issue"),
        ("en_US.UTF-8", "ISSUES"),
        ("en_US.UTF-8", "issué"),
        ("en_US.ISO8859-1", "Issue"),
        ("en_US.ISO8859-1", "ISSUES"),
        ("en_US.US-ASCII", "Issue"),
        ("en_US.US-ASCII", "ISSUES"),
    ],
)
def test_bad_branch_prefix_refuses_bad_manifest_under_locale(env, tmp_path, lc_all, bad):
    """Locale-independence regression (round-1 blocker; round-2 fix-round 2).

    The D1 check must not depend on the caller's collation locale. Neither a
    bash 3.2 `case` glob range NOR an `[[ =~ ]]` regex pattern that spells a
    POSIX bracket range (`[a-z]`) is safe: both follow LC_COLLATE. Under
    en_US.ISO8859-1 and en_US.US-ASCII specifically (single-byte locales
    with an explicitly-coded collation order), a range-based check ACCEPTS
    `Issue`/`ISSUES` -- opening a lane under a bad prefix with zero trace of
    the refusal. en_US.UTF-8 (this machine's AppleLocale) never triggered
    the range-widening itself, but stays covered here as the locale a normal
    Terminal/VS Code session actually exports. The fix is an explicit
    character LIST (`[abc...z]`), which enumerates each byte and has no
    range for collation order to reinterpret.
    """
    repo = make_repo(tmp_path, manifest=lane_manifest(branch_prefix=bad))
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    locale_env = dict(env["env"])
    locale_env["LANG"] = lc_all
    locale_env["LC_ALL"] = lc_all
    r = subprocess.run(
        ["bash", LANE_SH, "open", "42"],
        cwd=str(repo), env=locale_env, capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "REFUSED (bad-manifest) lane.branch_prefix" in r.stderr
    assert f"got '{bad}'" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


def test_empty_branch_prefix_is_manifest_key_missing(env, tmp_path):
    """Case 4 (second half)."""
    repo = make_repo(tmp_path, manifest=lane_manifest(branch_prefix=""))
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (manifest-key-missing)" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


def test_reap_abandon_status_follow_the_ledger_branch(env, tmp_path):
    """Case 5."""
    repo = make_repo(tmp_path, manifest=lane_manifest(branch_prefix="issues"))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr

    r = lane(env, repo, "status")
    assert r.returncode == 0, r.stderr
    assert "BRANCH" in r.stdout
    assert "issues/42-fix-the-thing" in r.stdout

    r = lane(env, repo, "abandon", "42")
    assert r.returncode == 0, r.stderr
    r = lane(env, repo, "status")
    assert r.returncode == 0, r.stderr
    assert "abandoned" in r.stdout
    assert "issues/42-fix-the-thing" in r.stdout

    r = lane(env, repo, "reap", "--abandoned", "42")
    assert r.returncode == 0, r.stderr
    assert branches(repo) == ["main"]
    assert worktrees(repo) == []
    rows = [json.loads(ln) for ln in env["ledger"].read_text().splitlines() if ln.strip()]
    assert rows[-1]["event"] == "reaped"
    assert rows[-1]["branch"] == "issues/42-fix-the-thing"


# --- case 6: label pick source + issue state -------------------------------


@pytest.mark.parametrize("stub", [_GH_LABELED, _GH_LABELED_WITH_NULL])
def test_label_present_opens_via_the_label_arm(env, tmp_path, stub):
    """Case 6a."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, stub)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    gh_log = (env["tmp"] / "gh.log").read_text()
    assert "issue view 42 --repo acme/testrepo --json labels" in gh_log
    assert not any(ln.startswith("project") for ln in gh_log.splitlines())
    assert "INDETERMINATE" not in r.stderr
    assert "pick-source-unreachable" not in r.stderr


def test_label_absent_refuses_not_in_pick_source(env, tmp_path):
    """Case 6b."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, _GH_UNLABELED)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (not-in-pick-source)" in r.stderr
    assert "'sprint:S1'" in r.stderr
    assert "case-sensitive" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert (env["tmp"] / "gh.log").exists()


def test_label_absent_recovery_label_added_opens(env, tmp_path):
    """Case 6b recovery: same repo, reproduce the refusal, then relabel."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, _GH_UNLABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (not-in-pick-source)" in r.stderr

    stub_gh(env, _GH_LABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    "stub",
    [_GH_LABELS_FAIL, _GH_LABELS_GARBAGE, _GH_LABELS_NOT_LIST, _GH_LABELS_NULL_EL],
)
def test_label_lookup_failure_is_indeterminate(env, tmp_path, stub):
    """Case 6c. Assert in the pinned order (revision 3)."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, stub)
    r = lane(env, repo, "open", "42")
    gh_log = (env["tmp"] / "gh.log").read_text()
    assert "--json labels" in gh_log  # (1)
    assert "unknown lane.pick_source.kind" not in r.stderr  # (2)
    assert r.returncode == 0, r.stderr  # (3)
    assert "lane: WARNING pick-source-unreachable:" in r.stderr  # (4)
    assert "(kind label)" in r.stderr  # (5)
    assert branches(repo) == sorted(["issues/42-fix-the-thing", "main"])  # (6)


@pytest.mark.parametrize(
    "pick_source",
    [
        {"kind": "label"},
        {"kind": "label", "label": ""},
        {"kind": "label", "label": None},
        {"kind": "label", "label": 5},
        {"kind": "label", "label": "  "},
    ],
)
def test_label_kind_without_a_label_is_bad_manifest(env, tmp_path, pick_source):
    """Case 6d."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=pick_source),
    )
    stub_gh(env, _GH_LABELED)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (bad-manifest) lane.pick_source.label must be a non-empty string" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


@pytest.mark.parametrize(
    "pick_source,stub",
    [
        (LABEL_PS, _GH_CLOSED_LABELED),
        (
            {"kind": "project_status", "project": 2, "owner": "acme", "status": "Ready #1"},
            _GH_CLOSED_READY,
        ),
    ],
)
def test_closed_issue_refuses_issue_closed(env, tmp_path, pick_source, stub):
    """Case 6e."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=pick_source),
    )
    stub_gh(env, stub)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (issue-closed)" in r.stderr
    assert "'CLOSED'" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    gh_log = (env["tmp"] / "gh.log").read_text()
    assert not any(
        ln.startswith("issue view") and "--json labels" in ln or ln.startswith("project")
        for ln in gh_log.splitlines()
    )


def test_closed_issue_recovery_open_issue_opens(env, tmp_path):
    """Case 6e recovery (also covers case 6f's recovery pairing): same label
    repo, reproduce the issue-closed refusal, then the issue is OPEN."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, _GH_CLOSED_LABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (issue-closed)" in r.stderr

    stub_gh(env, _GH_LABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    "stub,shown",
    [
        (_GH_STATE_MISSING, "<unparseable>"),
        (_GH_STATE_LOWER, "open"),
        (_GH_STATE_GARBAGE, "<unparseable>"),
    ],
)
def test_unparseable_or_unknown_state_refuses_issue_closed(env, tmp_path, stub, shown):
    """Case 6f."""
    repo = make_repo(tmp_path)  # default project_status pick source
    stub_gh(env, stub)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (issue-closed)" in r.stderr
    assert f"'{shown}'" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    gh_log = (env["tmp"] / "gh.log").read_text()
    assert not any(ln.startswith("project") for ln in gh_log.splitlines())


# --- case 7: pick-source shape validation -----------------------------------


@pytest.mark.parametrize(
    "pick_source",
    [
        {"kind": "board_column"},
        {"kind": "labels", "label": "sprint:S1"},
        {},
        "Ready #1",
        {"kind": "project_status", "owner": "acme", "status": "Ready #1"},
        {"kind": "project_status", "project": True, "owner": "acme", "status": "Ready #1"},
        {"kind": "project_status", "project": "2", "owner": "acme", "status": "Ready #1"},
        {"kind": "project_status", "project": 2, "status": "Ready #1"},
        {"kind": "project_status", "project": 2, "owner": "acme"},
        {"kind": "project_status", "project": 2, "owner": "  ", "status": "Ready #1"},
        {"kind": "project_status", "project": 2, "owner": "acme", "status": " "},
    ],
)
def test_unknown_or_malformed_pick_source_refuses_bad_manifest(env, tmp_path, pick_source):
    """Case 7."""
    repo = make_repo(tmp_path, manifest=lane_manifest(pick_source=pick_source))
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42")
    assert "REFUSED (bad-manifest) lane.pick_source" in r.stderr
    assert r.returncode != 0
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()
    if pick_source in ({"kind": "board_column"}, {"kind": "labels", "label": "sprint:S1"}):
        expected = "board_column" if pick_source.get("kind") == "board_column" else "labels"
        assert f"got '{expected}'" in r.stderr


def test_malformed_pick_source_recovery_fixed_manifest_opens(env, tmp_path):
    """Case 7 recovery: same repo, reproduce the refusal, then fix the manifest."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(pick_source={"kind": "labels", "label": "sprint:S1"}),
    )
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (bad-manifest) lane.pick_source" in r.stderr

    (repo / ".claude" / "oversight" / "manifest.json").write_text(
        json.dumps(lane_manifest(pick_source=LABEL_PS), indent=2)
    )
    stub_gh(env, _GH_LABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


def test_project_status_lookup_failure_is_indeterminate(env, tmp_path):
    """Case 7b."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_PROJECT_FAIL)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "lane: WARNING pick-source-unreachable:" in r.stderr
    assert "(kind project_status)" in r.stderr
    assert any(b.startswith("issue/42-") for b in branches(repo))


# --- case 9: the origin/main branch push gate -------------------------------

LANE_BRANCH_GATE_PY = os.environ.get("LANE_BRANCH_GATE_PY")


@pytest.mark.skipif(not LANE_BRANCH_GATE_PY, reason="LANE_BRANCH_GATE_PY not set")
def test_agency_prefix_passes_origin_main_branch_gate(env, tmp_path):
    """Case 9a."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(branch_prefix="issues", pick_source=LABEL_PS),
    )
    stub_gh(env, _GH_LABELED)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    e = dict(env["env"])
    e.pop("SKIP_BRANCH_CHECK", None)
    gate = subprocess.run(
        ["python3", LANE_BRANCH_GATE_PY], cwd=str(wt), env=e, capture_output=True, text=True,
    )
    assert gate.returncode == 0, gate.stderr


@pytest.mark.skipif(not LANE_BRANCH_GATE_PY, reason="LANE_BRANCH_GATE_PY not set")
def test_issue_prefix_fails_origin_main_branch_gate(env, tmp_path):
    """Case 9b. NOT falsifiable against the pre-change copy: it always passes
    the origin/main gate the same way, by construction."""
    repo = make_repo(tmp_path, manifest=MANIFEST)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    e = dict(env["env"])
    e.pop("SKIP_BRANCH_CHECK", None)
    gate = subprocess.run(
        ["python3", LANE_BRANCH_GATE_PY], cwd=str(wt), env=e, capture_output=True, text=True,
    )
    assert gate.returncode == 1
    assert "does not match" in gate.stderr


def test_reap_and_abandon_do_not_need_branch_prefix(env, tmp_path):
    """Case 10 (the B2 guard). Deliberately does NOT assert the branch at the
    `status` step; that's test 5's job."""
    repo = make_repo(tmp_path)  # default branch_prefix="issue"
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr

    (repo / ".claude" / "oversight" / "manifest.json").write_text(
        json.dumps(lane_manifest(drop=("branch_prefix",)), indent=2)
    )

    r = lane(env, repo, "status")
    assert r.returncode == 0, r.stderr
    assert "#42" in r.stdout
    assert "open" in r.stdout

    r = lane(env, repo, "abandon", "42")
    assert r.returncode == 0, r.stderr

    r = lane(env, repo, "reap", "--abandoned", "42")
    assert r.returncode == 0, r.stderr
    assert not any(b.startswith("issue/42-") for b in branches(repo))
    assert worktrees(repo) == []

    r = lane(env, repo, "open", "42")
    assert r.returncode != 0
    assert "REFUSED (manifest-key-missing)" in r.stderr


@pytest.mark.parametrize("tail", [("--repo", "acme/other"), ("extra",)])
def test_open_refuses_extra_arguments(env, tmp_path, tail):
    """Case 11 (D9)."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    before = ledger_bytes(env)
    r = lane(env, repo, "open", "42", *tail)
    assert r.returncode != 0
    assert "REFUSED (bad-args)" in r.stderr
    assert f"'{' '.join(tail)}'" in r.stderr
    assert worktrees(repo) == []
    assert branches(repo) == ["main"]
    assert ledger_bytes(env) == before
    assert not (env["tmp"] / "gh.log").exists()


def test_open_extra_arguments_recovery_single_argument_opens(env, tmp_path):
    """Case 11 recovery: same repo, reproduce the refusal, then a single argument."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42", "--repo", "acme/other")
    assert r.returncode != 0
    assert "REFUSED (bad-args)" in r.stderr

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# 12. lane.link_paths (P10) -- open also links a manifest-listed extra-path
#     set, the way it already links node_modules. Genuinely OPTIONAL: a
#     manifest with no `lane.link_paths` key opens exactly as today.
# ---------------------------------------------------------------------------


def _write_extra_path_fixtures(repo):
    """Creates the paths P10's Agency value names, in the MAIN tree, plus one
    that is deliberately left absent (pii_allowlist.txt) to exercise the
    skip-missing case.

    Deliberately UNTRACKED (never `git add`ed/committed) -- this mirrors the
    real Agency shape: `.venv_py313_ci` and the PII lists are gitignored
    (`.gitignore:249-250`, `agency/.gitignore:37`). A COMMITTED fixture would
    make `git worktree add` check it out fresh into every new worktree as a
    real (non-symlink) copy, which both defeats the point of P10 (there would
    be nothing to link) and would falsely make these tests pass without the
    link code ever running."""
    venv = repo / "agency" / "backend" / ".venv_py313_ci" / "bin"
    venv.mkdir(parents=True)
    (venv / "python3").write_text("#!/bin/sh\n")
    hooks = repo / "scripts" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pii_denylist.txt").write_text("555-1234\n")
    # pii_allowlist.txt is deliberately NOT created -- it is listed in the
    # manifest but absent from the main tree.
    _git(repo, "fetch", "-q", "origin", "main")


_LINK_PATHS = [
    "agency/backend/.venv_py313_ci",
    "scripts/hooks/pii_denylist.txt",
    "scripts/hooks/pii_allowlist.txt",  # absent from the main tree on purpose
]


def test_link_paths_links_each_listed_existing_path_and_stays_clean(env, tmp_path):
    """Case (a): with the key set, open links each listed EXISTING path, and
    each gets a bare exclude line so `git status --porcelain` in the lane
    stays empty."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]

    venv_link = wt / "agency" / "backend" / ".venv_py313_ci"
    denylist_link = wt / "scripts" / "hooks" / "pii_denylist.txt"
    allowlist_link = wt / "scripts" / "hooks" / "pii_allowlist.txt"

    assert venv_link.is_symlink(), "the CI venv must be linked, not created"
    assert venv_link.resolve() == (repo / "agency" / "backend" / ".venv_py313_ci").resolve()
    assert denylist_link.is_symlink()
    assert denylist_link.resolve() == (repo / "scripts" / "hooks" / "pii_denylist.txt").resolve()
    # The listed-but-absent entry is never created as a link or a real file.
    assert not allowlist_link.exists()
    assert not allowlist_link.is_symlink()

    exclude = (repo / ".git" / "info" / "exclude").read_text()
    # Bare lines, NO trailing slash -- a symlink is not a directory to git.
    assert "agency/backend/.venv_py313_ci\n" in exclude
    assert "agency/backend/.venv_py313_ci/\n" not in exclude
    assert "scripts/hooks/pii_denylist.txt\n" in exclude

    porcelain = _git(wt, "status", "--porcelain").stdout
    assert porcelain == "", f"lane must read clean with the links present: {porcelain!r}"


def test_link_paths_absent_key_opens_exactly_as_today(env, tmp_path):
    """Case (b): with the key ABSENT, open still works and links nothing
    extra -- proving the key is genuinely optional (this is CSA's shape
    today: no `lane.link_paths` at all)."""
    repo = make_repo(tmp_path, manifest=lane_manifest(drop=()))
    assert "link_paths" not in MANIFEST["lane"], "sanity: MANIFEST must not already carry the key"
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]

    assert not (wt / "agency").exists()
    assert not (wt / "scripts").exists()
    exclude = (repo / ".git" / "info" / "exclude").read_text()
    assert "node_modules\n" in exclude  # the pre-existing behaviour is intact
    # Nothing P10-specific was written -- no line from any of the paths this
    # test file uses as P10 fixtures appears (git's own sample-hooks
    # boilerplate comment lines in a fresh `.git/info/exclude` are allowed
    # and ignored; only real, non-comment pattern lines are checked).
    pattern_lines = [
        line for line in exclude.splitlines() if line and not line.startswith("#")
    ]
    assert pattern_lines == ["node_modules", "**/node_modules"]


def test_link_paths_missing_from_main_tree_is_skipped_not_fatal(env, tmp_path):
    """Case (c): a listed path missing in the main tree is skipped, with a
    warning, never fatal to the open."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=["scripts/hooks/does_not_exist.txt"]),
    )
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "does not exist" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert not (wt / "scripts").exists()


@pytest.mark.parametrize(
    "bad_entry",
    [
        "/etc/passwd",  # absolute
        "../outside.txt",  # ".." segment, leading
        "agency/../../outside.txt",  # ".." segment, embedded
        "agency/backend/..",  # ".." as a trailing segment
    ],
)
def test_link_paths_unsafe_entry_is_refused_and_skipped(env, tmp_path, bad_entry):
    """Case (d): an unsafe entry (absolute, or containing "..") is refused --
    reported and skipped, never linked, and never fatal to the open (the
    other, safe entries in the same list still link)."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=[bad_entry, "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "refused" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    # The safe entry alongside the unsafe one still links.
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()
    # Nothing named "outside.txt" or "passwd" appears anywhere under the
    # worktree -- the unsafe entry produced no link at all.
    found = list(wt.rglob("passwd")) + list(wt.rglob("outside.txt"))
    assert found == []


@pytest.mark.parametrize(
    "bad_entry,reason",
    [
        (".git", "is under .git"),
        (".git/config", "is under .git"),
        (".claude/worktrees", "is under .claude/worktrees"),
        (".claude/worktrees/some-lane", "is under .claude/worktrees"),
    ],
)
def test_link_paths_refuses_entries_under_git_or_worktrees(env, tmp_path, bad_entry, reason):
    """Fix-round item 11: an entry naming `.git` (or anything under it) or
    `.claude/worktrees` (or anything under it) must be refused, never linked.
    `.git` is the lane's own git internals (linking into it could corrupt
    them or shadow files git manages); `.claude/worktrees` is where every
    lane's own worktree lives (linking into it could cross-link one lane's
    content into another, or into itself)."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=[bad_entry, "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert reason in r.stderr, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    # The safe sibling entry still links regardless.
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()
    # The lane's own .git and .claude/worktrees are exactly what `git worktree
    # add` itself created -- neither a real directory NOR a symlink was added
    # or replaced there by link_extra_paths.
    assert not (wt / ".git").is_symlink(), "the lane's own .git must never become a symlink"
    assert not (wt / ".claude" / "worktrees").exists(), (
        "link_extra_paths must never create a nested .claude/worktrees inside the lane"
    )


def test_link_paths_already_present_symlink_to_same_target_is_recorded(env, tmp_path):
    """A re-run of `open` against an already-linked lane (or a listed path that
    happens to already be a symlink to the exact source this entry names) is
    recorded and excluded exactly as a freshly-created link would be -- this is
    the legitimate "already present" case the guard below must still allow."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    venv_link = wt / "agency" / "backend" / ".venv_py313_ci"
    assert venv_link.is_symlink()
    target_before = os.readlink(venv_link)

    # Re-run link_extra_paths again directly (simulating a second `open`-style
    # pass over an already-linked lane): the existing correct symlink must be
    # recorded (present in LANE_EXTRA_LINKED -> excluded), not skipped as
    # foreign content, and the symlink itself must be untouched.
    r2 = call_lane_function(env, repo, wt, "link_extra_paths")
    assert "agency/backend/.venv_py313_ci" in r2.stdout.splitlines(), r2.stdout + r2.stderr
    assert os.readlink(venv_link) == target_before, "an already-correct link must never be rewritten"


def test_link_paths_real_content_at_the_lane_path_is_never_recorded_or_excluded(env, tmp_path):
    """REGRESSION (fix-round blocker 3, ~lane.sh:720-725): the OLD 'already
    present' branch recorded ANY existing path at the lane's destination --
    including real tracked/untracked content that is NOT a symlink to the
    manifest's source at all -- and wrote a permanent exclude line for it.
    That silently hides genuinely new untracked content at that same path in
    the MAIN tree's own `.git/info/exclude` (ensure_exclude writes into
    REPO_ROOT's exclude file, not the lane's). The fix: real content at the
    lane's destination is warned about and skipped, never recorded, never
    excluded."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    denylist_link = wt / "scripts" / "hooks" / "pii_denylist.txt"
    assert denylist_link.is_symlink()

    # Replace the legitimate symlink with REAL content at the exact same path
    # (as if the lane's own branch genuinely tracks a file there), then
    # re-run link_extra_paths directly to simulate a second `open`-style pass.
    denylist_link.unlink()
    denylist_link.write_text("real tracked content, not a link\n")

    r2 = call_lane_function(env, repo, wt, "link_extra_paths")
    assert "scripts/hooks/pii_denylist.txt" not in r2.stdout.splitlines(), (
        "real content at the destination must NEVER be recorded as if it were "
        "our own link: " + r2.stdout
    )
    assert "already exists as real content" in r2.stderr, r2.stderr
    # The real content is left completely alone: never overwritten, never
    # deleted, never turned into a symlink.
    assert denylist_link.read_text() == "real tracked content, not a link\n"
    assert not denylist_link.is_symlink()


def test_link_paths_existing_symlink_to_a_different_target_is_never_recorded(env, tmp_path):
    """A symlink already sits at the lane's destination, but points somewhere
    OTHER than the manifest's own source -- e.g. a stale link from a prior,
    differently-configured run. It must be left alone, not recorded, and not
    given an exclude line (which would hide it from `git status` under a
    manifest-driven assumption that no longer holds)."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    denylist_link = wt / "scripts" / "hooks" / "pii_denylist.txt"
    assert denylist_link.is_symlink()

    other_target = repo.parent / "some_other_file.txt"
    other_target.write_text("unrelated\n")
    denylist_link.unlink()
    denylist_link.symlink_to(other_target)

    r2 = call_lane_function(env, repo, wt, "link_extra_paths")
    assert "scripts/hooks/pii_denylist.txt" not in r2.stdout.splitlines(), r2.stdout
    assert "existing symlink to a DIFFERENT target" in r2.stderr, r2.stderr
    assert os.readlink(denylist_link) == str(other_target), "the stale link must be left untouched"


def test_link_paths_absolute_entry_alone_refuses_without_failing_open(env, tmp_path):
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=["/etc/passwd"]))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "is absolute" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert list(wt.rglob("passwd")) == []


def test_link_paths_entry_resolving_outside_repo_root_is_refused(env, tmp_path):
    """A relative entry with no literal ".." can still resolve outside
    REPO_ROOT through a symlinked directory already present in the main
    tree -- R2's physical-path check catches that case too."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=["escape/passwd"]))
    outside = repo.parent / "outside_target"
    outside.mkdir()
    (outside / "passwd").write_text("nope\n")
    # `escape` is an untracked symlink in the main tree pointing OUTSIDE the
    # repo -- not committed (git does not need to track it for this check;
    # link_extra_paths inspects the live filesystem, not git history).
    (repo / "escape").symlink_to(outside)
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "resolves outside" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert not (wt / "escape").exists()
    assert not (wt / "escape").is_symlink()


def test_link_paths_leading_dot_slash_is_normalized_and_links(env, tmp_path):
    """`./x` is treated identically to `x`: the leading `./` is stripped before
    validation, so a manifest author's copy-pasted `./scripts/hooks/...`
    entry links exactly as the bare form would."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=["./scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    link = wt / "scripts" / "hooks" / "pii_denylist.txt"
    assert link.is_symlink()
    assert link.resolve() == (repo / "scripts" / "hooks" / "pii_denylist.txt").resolve()
    exclude = (repo / ".git" / "info" / "exclude").read_text()
    # Recorded (and excluded) under the NORMALIZED form, never with the
    # leading "./" still attached.
    assert "scripts/hooks/pii_denylist.txt\n" in exclude
    assert "./scripts/hooks/pii_denylist.txt\n" not in exclude


def test_link_paths_trailing_slash_is_normalized_and_links(env, tmp_path):
    """`x/` is treated identically to `x`: the trailing slash is stripped
    before validation, so a directory entry copy-pasted with a trailing
    slash (as `ls`/tab-completion commonly produce) still links."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=["agency/backend/.venv_py313_ci/"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    link = wt / "agency" / "backend" / ".venv_py313_ci"
    assert link.is_symlink()
    exclude = (repo / ".git" / "info" / "exclude").read_text()
    assert "agency/backend/.venv_py313_ci\n" in exclude
    assert "agency/backend/.venv_py313_ci/\n" not in exclude


@pytest.mark.parametrize("bad", ["*.txt", "scripts/hooks/*", "a?b", "a[bc]", "{a,b}"])
def test_link_paths_glob_characters_are_rejected(env, tmp_path, bad):
    """`lane.link_paths` names exact paths, never patterns: an entry
    containing a glob metacharacter is refused per-entry, never silently
    expanded, and never fatal to the open."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=[bad, "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    if any(c in bad for c in "*?[]"):
        assert "glob character" in r.stderr, r.stderr
    # The well-formed sibling entry still links regardless of the bad one.
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()


@pytest.mark.parametrize("bad", ["#comment", "!negated", "-flag"])
def test_link_paths_leading_hash_bang_or_dash_is_rejected(env, tmp_path, bad):
    """A leading `#`, `!` or `-` is refused: `#`/`!` change meaning inside the
    exclude file this entry is later written to, and `-` risks being read as
    an option by a tool that consumes the raw string (e.g. `grep`)."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=[bad, "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "starts with '#', '!' or '-'" in r.stderr, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()
    # Nothing named after the rejected entry's literal text was ever created.
    assert list(wt.rglob("comment")) == [] and list(wt.rglob("negated")) == []


def test_link_paths_embedded_whitespace_is_rejected(env, tmp_path):
    """An entry containing embedded whitespace can never be a single real
    path component; refused, never fatal."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=["scripts/hooks/pii denylist.txt",
                                            "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "contains whitespace" in r.stderr, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()


def test_link_paths_reverted_code_does_not_link_the_venv(env, tmp_path):
    """Falsifiability anchor for case (a) (fix-round item 19: the previous
    version of this test asserted `venv_link.is_symlink()` even when pointed
    at a REVERTED scratch copy of lane.sh with the P10 link/exclude code
    removed -- i.e. it was written to FAIL (a pytest FAILURE, not a passing
    assertion) exactly when its own env-gate condition was satisfied. A test
    that only ever passes against the CURRENT script and always reports a
    failure when actually run in "falsifiability mode" is not usable
    evidence; a real falsifiability check is a GREEN assertion about what the
    REVERTED code does. Fixed: assert the reverted script does NOT link (the
    true, positive behavior of the reverted code), which is itself the
    falsifiability evidence that case (a)'s own green assertion
    (`test_link_paths_links_each_listed_existing_path_and_stays_clean`)
    actually depends on the link code, not on something else."""
    reverted = os.environ.get("LANE_SH_REVERTED_FOR_TEST")
    if not reverted:
        pytest.skip("LANE_SH_REVERTED_FOR_TEST not set; falsifiability run only")
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = subprocess.run(
        ["bash", reverted, "open", "42"], cwd=str(repo), env=env["env"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    venv_link = wt / "agency" / "backend" / ".venv_py313_ci"
    # The reverted script (P10 link code removed) genuinely fails to link --
    # this PASSING assertion is the falsifiability evidence itself.
    assert not venv_link.is_symlink()
    assert not venv_link.exists()


def test_link_paths_reap_leaves_link_targets_in_main_tree_intact(env, tmp_path):
    """Case (e): reap/abandon removes the lane's own links (the whole
    worktree goes away with the branch's content landed), but the link
    TARGETS in the main tree are untouched -- reap must never follow a
    symlink to delete or mutate what it points at."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert (wt / "agency" / "backend" / ".venv_py313_ci").is_symlink()

    # Make the lane reapable: commit real work and land it on the base ref.
    (wt / "work.txt").write_text("landed work\n")
    _git(wt, "add", "work.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "landed")
    branch = [b for b in branches(repo) if b.startswith("issue/42-")][0]
    _git(repo, "push", "-q", "origin", f"{branch}:main")
    _git(repo, "fetch", "-q", "origin", "main")

    venv_target = repo / "agency" / "backend" / ".venv_py313_ci"
    denylist_target = repo / "scripts" / "hooks" / "pii_denylist.txt"
    venv_target_contents_before = (venv_target / "bin" / "python3").read_text()
    denylist_contents_before = denylist_target.read_text()

    r = lane(env, repo, "reap", "42")
    assert r.returncode == 0, r.stderr
    assert not wt.exists(), "the worktree (and its links) must be gone"

    # The MAIN TREE's real files are completely unaffected.
    assert venv_target.is_dir(), "reap must never delete the link's real target"
    assert (venv_target / "bin" / "python3").read_text() == venv_target_contents_before
    assert denylist_target.is_file()
    assert denylist_target.read_text() == denylist_contents_before


def test_link_paths_abandon_keeps_the_links_and_the_main_tree_targets(env, tmp_path):
    """Case (e), abandon variant: abandon KEEPS the worktree (by design,
    unchanged from node_modules' own behaviour) -- so the extra-path links
    stay present in the abandoned lane, and the main tree is untouched."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]

    r = lane(env, repo, "abandon", "42")
    assert r.returncode == 0, r.stderr
    assert wt.is_dir(), "abandon must keep the worktree on disk"
    assert (wt / "agency" / "backend" / ".venv_py313_ci").is_symlink()
    assert (repo / "agency" / "backend" / ".venv_py313_ci").is_dir()


def test_link_paths_non_json_scalar_is_treated_as_no_extra_paths(env, tmp_path):
    """A malformed `lane.link_paths` value never fails the open; it degrades
    to "link nothing extra", exactly like an absent key. `repo_manifest.py
    get --raw` prints a plain (unquoted) string value verbatim, so a bare
    string manifest value round-trips here as invalid JSON -- the "not valid
    JSON" branch, not "not a JSON array" (that branch is exercised by the
    object-valued case below, which round-trips as valid, non-array JSON)."""
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths="not-a-list"))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "not valid JSON" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert not (wt / "agency").exists()


def test_link_paths_json_object_value_is_treated_as_no_extra_paths(env, tmp_path):
    """A `lane.link_paths` that IS valid JSON but not an array (an object)
    also degrades to "link nothing extra", never fails the open."""
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths={"agency/backend/.venv_py313_ci": True}),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "not a JSON array" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert not (wt / "agency").exists()


def test_link_paths_non_string_entry_is_skipped_others_still_link(env, tmp_path):
    repo = make_repo(
        tmp_path,
        manifest=lane_manifest(link_paths=[42, "scripts/hooks/pii_denylist.txt"]),
    )
    _write_extra_path_fixtures(repo)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    assert "not a non-empty string" in r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert (wt / "scripts" / "hooks" / "pii_denylist.txt").is_symlink()


def test_link_paths_empty_list_opens_exactly_as_today(env, tmp_path):
    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=[]))
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]
    assert not (wt / "agency").exists()
    assert not (wt / "scripts").exists()


def test_link_paths_never_pip_installs(env, tmp_path):
    """Guardrail: the linked venv's bin is never invoked or written through by
    lane.sh itself -- `open` must not run pip (or python) against the linked
    venv at all. Static check on the script text plus a behavioural one: the
    linked venv's contents are byte-identical to the main tree's before and
    after open.

    The static half (fix-round item 20) is scanned at the level of actual
    COMMAND lines, with comments and quoted message text stripped first --
    the same discipline `test_script_source_never_forces` already uses for
    `--force`. A bare substring check over the whole file would be tripped by
    a future comment merely EXPLAINING that lane.sh deliberately never runs
    pip (exactly the kind of prose this file's own header/inline comments
    already contain elsewhere), which would be a false failure having nothing
    to do with an actual invocation.
    """
    import re

    src = Path(os.environ.get("LANE_SH", str(Path.home() / ".claude" / "scripts" / "lane.sh"))).read_text()
    # Falsifiability guard: prove this is reading a real lane.sh before
    # asserting an absence -- an absent-or-stub file also contains no "pip
    # install" line and would pass vacuously.
    assert "worktree add" in src and "link_extra_paths" in src, (
        f"{LANE_SH} is not a real lane.sh; this check would pass vacuously"
    )
    offenders = []
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        stripped = re.sub(r'"[^"]*"', '""', line)
        stripped = re.sub(r"'[^']*'", "''", stripped)
        if "pip install" in stripped or "pip3 install" in stripped:
            offenders.append((lineno, raw))
    assert not offenders, f"a real pip-install invocation was found: {offenders}"

    repo = make_repo(tmp_path, manifest=lane_manifest(link_paths=_LINK_PATHS))
    _write_extra_path_fixtures(repo)
    before = (repo / "agency" / "backend" / ".venv_py313_ci" / "bin" / "python3").read_text()
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    after = (repo / "agency" / "backend" / ".venv_py313_ci" / "bin" / "python3").read_text()
    assert before == after


# ---------------------------------------------------------------------------
# 13. link_node_modules -- finds every dependency root at the depth Agency keeps them
#     (OtherApp #6003: the search stopped at four levels and missed the two marketing
#     functions' roots, which sit five levels down, so G0.30/G0.31 failed in a lane)
# ---------------------------------------------------------------------------

_NODE_MODULES_ROOTS = [
    "node_modules",
    "agency/src/node_modules",
    "proposals/web-dev/otherapp/functions/node_modules",
    "proposals/web-dev/otherapp/functions-quinn/node_modules",
]


def _plant_node_modules(repo, rels):
    """Untracked fake dependency dirs in the MAIN tree, like the real gitignored ones."""
    for rel in rels:
        d = repo / rel
        d.mkdir(parents=True)
        (d / "SENTINEL.txt").write_text(rel)


def _links_under(root):
    """Every symlink below `root` as a posix-relative path, never following one."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in [*dirnames, *filenames]:
            p = Path(dirpath) / name
            if p.is_symlink():
                found.append(p.relative_to(root).as_posix())
    return sorted(found)


def test_open_links_node_modules_roots_five_levels_deep(env, tmp_path):
    """OtherApp #6003: the marketing functions' roots (`proposals/web-dev/otherapp/<dir>/node_modules`, five
    levels down) are linked into the lane like the shallower ones, and the lane still reads clean."""
    repo = make_repo(tmp_path)
    _plant_node_modules(repo, _NODE_MODULES_ROOTS)
    stub_gh(env, _GH_OK)

    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt = repo / ".claude" / "worktrees" / worktrees(repo)[0]

    for rel in _NODE_MODULES_ROOTS:
        link = wt / rel
        assert link.is_symlink(), f"{rel} must be linked into the lane, not created empty or left out"
        assert link.resolve() == (repo / rel).resolve()
        assert (link / "SENTINEL.txt").read_text() == rel
    porcelain = _git(wt, "status", "--porcelain").stdout
    assert porcelain == "", f"the links must not show up as untracked: {porcelain!r}"


def test_link_node_modules_links_real_roots_only_not_nested_or_worktree_ones(env, tmp_path):
    """Pair for the test above (a deeper search must not over-link, and must not walk a node_modules tree): a
    node_modules INSIDE another node_modules, or inside a `.claude/worktrees` checkout, is not a dependency root
    of the main tree. Only the real roots get a link, exactly once each."""
    repo = make_repo(tmp_path)
    _plant_node_modules(
        repo,
        [
            *_NODE_MODULES_ROOTS,
            "agency/node_modules/dep/node_modules",  # makes agency/node_modules a root; the inner one is nested
            "proposals/web-dev/otherapp/functions/node_modules/a/b/node_modules",
            ".claude/worktrees/other/node_modules",
            ".claude/worktrees/other/proposals/web-dev/otherapp/functions/node_modules",
        ],
    )
    wt = tmp_path / "scratch_wt"
    wt.mkdir()

    r = call_lane_function(env, repo, wt, "link_node_modules")
    assert r.returncode == 0, r.stderr

    assert _links_under(wt) == sorted([*_NODE_MODULES_ROOTS, "agency/node_modules"])
