"""Tests for `~/.claude/scripts/lane_orphans.sh` (read-only lane reconciliation).

Spec source: the adoption master plan §7.4 + §9 rule 3. What these assert:

  1. It WRITES NOTHING, EVER -- proven by hashing the whole tree (and the
     ledger) before and after a run that produces findings. This is the
     script's entire safety argument, so it is tested directly rather than
     inferred from reading the source.
  2. Exit 0 when clean, exit 1 when there are findings.
  3. All four finding classes are detected: orphan-worktree, orphan-row,
     dead-owner, over-cap.
  4. `dead-owner` is REPORTED, never reaped -- the worktree is still on disk
     after the run. A pid being gone says nothing about whether its CONTENT
     landed, which is the only question that licenses a removal.
  5. The `^issue-[0-9]+-` anchor does NOT match a legacy, non-lane worktree
     name. CSA has 236 such checkouts; matching loosely would bury the real
     signal under them.

Hermetic throughout: throwaway `git init` repos and a tmp ledger, never the
real Agency/CSA trees or `~/.claude/.lanes/`. `LANE_ORPHANS_SH` is honored so
the suite can be pointed at a scratch pre-change copy to prove RED.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

LANE_ORPHANS_SH = os.environ.get(
    "LANE_ORPHANS_SH", str(Path.home() / ".claude" / "scripts" / "lane_orphans.sh")
)
REPO_MANIFEST_PY = str(Path.home() / ".claude" / "scripts" / "repo_manifest.py")

MANIFEST = {
    "schema_version": 1,
    "product": {"name": "Test Repo", "slug": "testrepo"},
    "github": {"repo": "acme/testrepo", "project_number": 2,
               "project_owner": "acme"},
    "gtm": {"missions_dir": "missions", "inbox_label": "dept:marketing"},
    "lane": {
        "base_ref": "origin/main",
        "pr_target": "main",
        "branch_prefix": "issue",
        "pick_source": {"kind": "project_status", "project": 2,
                        "owner": "acme", "status": "Ready #1"},
        "max_open": 3,
        "max_abandoned": 3,
    },
}


@pytest.fixture
def env(tmp_path):
    lane_dir = tmp_path / "lanes"
    lane_dir.mkdir()
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    e = dict(os.environ)
    e["LANE_DIR"] = str(lane_dir)
    e["CLAUDE_DIR"] = str(claude_dir)
    e["REPO_MANIFEST_PY"] = REPO_MANIFEST_PY
    return {"env": e, "lane_dir": lane_dir,
            "ledger": lane_dir / "lanes.jsonl", "tmp": tmp_path}


def make_repo(tmp_path, name="repo"):
    repo = tmp_path / name
    subprocess.run(["git", "init", "-b", "main", str(repo)],
                   check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n")
    (repo / "missions").mkdir()
    (repo / "missions" / ".keep").write_text("")
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    (oversight / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    subprocess.run(["git", "-C", str(repo), "add", "README.md", "missions/.keep"],
                   check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@x.invalid",
         "-c", "user.name=t", "commit", "-m", "init"],
        check=True, capture_output=True)
    (repo / ".claude" / "worktrees").mkdir()
    return repo


def write_ledger(env, rows):
    env["ledger"].write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))


def row(issue, repo, wt, event="open", pid=None, branch=None, host=None):
    return {
        "ts": "2026-09-23T00:00:00+0000",
        "event": event,
        "issue": issue,
        "repo": str(repo),
        "worktree": str(wt),
        "branch": branch or f"issue/{issue}-x",
        "pr_base": "main",
        "pr": None,
        "session": None,
        "pid": pid if pid is not None else os.getpid(),
        "host": host if host is not None else socket.gethostname(),
    }


def run(env, repo):
    return subprocess.run(["bash", LANE_ORPHANS_SH], cwd=str(repo),
                          env=env["env"], capture_output=True, text=True)


def tree_hash(root: Path) -> str:
    """Content+structure hash of everything under `root`."""
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        rel = str(path.relative_to(root)).encode()
        h.update(rel)
        if path.is_symlink():
            h.update(b"L" + os.readlink(path).encode())
        elif path.is_file():
            h.update(b"F")
            h.update(path.read_bytes())
        elif path.is_dir():
            h.update(b"D")
    return h.hexdigest()


def make_lane_dir(repo, issue, name=None):
    d = repo / ".claude" / "worktrees" / (name or f"issue-{issue}-thing")
    d.mkdir(parents=True)
    (d / "file.txt").write_text("content\n")
    return d


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


def test_exits_zero_when_clean_with_no_lanes_at_all(env, tmp_path):
    repo = make_repo(tmp_path)
    r = run(env, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clean" in r.stdout


def test_exits_zero_when_every_row_matches_a_worktree(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 42)
    write_ledger(env, [row(42, repo, wt)])
    r = run(env, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clean" in r.stdout


# ---------------------------------------------------------------------------
# orphan-worktree  (refusal-equivalent: a finding) + its clean pair
# ---------------------------------------------------------------------------


def test_orphan_worktree_is_reported(env, tmp_path):
    repo = make_repo(tmp_path)
    make_lane_dir(repo, 77)  # on disk, no ledger row
    r = run(env, repo)
    assert r.returncode == 1
    assert "orphan-worktree" in r.stdout
    assert "#77" in r.stdout


def test_orphan_worktree_recovery_row_present_is_clean(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 77)
    write_ledger(env, [row(77, repo, wt)])
    r = run(env, repo)
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------------------------
# orphan-row + its clean pair
# ---------------------------------------------------------------------------


def test_orphan_row_is_reported(env, tmp_path):
    repo = make_repo(tmp_path)
    ghost = repo / ".claude" / "worktrees" / "issue-88-gone"
    write_ledger(env, [row(88, repo, ghost)])  # row, no directory
    r = run(env, repo)
    assert r.returncode == 1
    assert "orphan-row" in r.stdout
    assert "#88" in r.stdout


def test_orphan_row_recovery_directory_present_is_clean(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 88, name="issue-88-gone")
    write_ledger(env, [row(88, repo, wt)])
    r = run(env, repo)
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------------------------
# dead-owner — REPORTED, NEVER REAPED
# ---------------------------------------------------------------------------


def _dead_pid():
    """A pid that has certainly exited."""
    p = subprocess.Popen(["python3", "-c", "pass"])
    p.wait()
    return p.pid


def test_dead_owner_is_reported(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 99)
    write_ledger(env, [row(99, repo, wt, pid=_dead_pid())])
    r = run(env, repo)
    assert r.returncode == 1
    assert "dead-owner" in r.stdout


def test_dead_owner_worktree_is_never_removed(env, tmp_path):
    """The whole point of the class: a dead pid licenses a REPORT, not a reap."""
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 99)
    write_ledger(env, [row(99, repo, wt, pid=_dead_pid())])
    before = tree_hash(wt)
    r = run(env, repo)
    assert r.returncode == 1
    assert wt.is_dir(), "dead-owner must never cause a removal"
    assert (wt / "file.txt").read_text() == "content\n"
    assert tree_hash(wt) == before


def test_live_owner_is_not_reported_as_dead(env, tmp_path):
    """Paired recovery: the same shape with a LIVE pid produces no finding."""
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 99)
    write_ledger(env, [row(99, repo, wt, pid=os.getpid())])
    r = run(env, repo)
    assert r.returncode == 0, r.stdout
    assert "dead-owner" not in r.stdout


def test_a_null_pid_is_not_reported_as_dead(env, tmp_path):
    """REGRESSION pair to lane.sh's owner-pid fix (2026-09-23).

    `lane.sh` writes `"pid": null` when the owning session's pid is
    unresolvable -- "liveness genuinely unknown". An unknown owner must fail
    OPEN, never be reported as a dead one.
    """
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 99)
    r = row(99, repo, wt)
    r["pid"] = None
    write_ledger(env, [r])
    out = run(env, repo)
    assert "dead-owner" not in out.stdout
    assert out.returncode == 0, out.stdout


def test_a_normally_opened_lane_is_not_reported_as_dead_owner(env, tmp_path):
    """End-to-end guard on the defect the live proof run exposed: opening a
    lane through lane.sh itself, with a live session pid, must leave
    lane_orphans.sh CLEAN. Before the fix this reported dead-owner every
    single time, because the row carried lane.sh's own already-exited pid."""
    lane_sh = os.environ.get(
        "LANE_SH", str(Path.home() / ".claude" / "scripts" / "lane.sh"))
    if not os.path.exists(lane_sh):
        pytest.skip("lane.sh unavailable")
    repo = make_repo(tmp_path)
    # lane.sh needs a real origin/main to branch from.
    up = tmp_path / "up.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(up)],
                   check=True, capture_output=True)
    e = dict(env["env"])
    e.update(GIT_AUTHOR_NAME="t", GIT_COMMITTER_NAME="t",
             GIT_AUTHOR_EMAIL="t@x.invalid", GIT_COMMITTER_EMAIL="t@x.invalid")
    for args in (["remote", "add", "origin", str(up)],
                 ["push", "-q", "origin", "main"],
                 ["fetch", "-q", "origin", "main"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True, env=e)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(
        '#!/bin/bash\n'
        'if [ "$1" = "issue" ] && [ "$2" = "view" ]; then\n'
        '  case " $* " in *" --json title "*|*"-q .title"*) echo "thing"; exit 0 ;; esac\n'
        '  echo "{\\"number\\":$3,\\"state\\":\\"OPEN\\"}"; exit 0\n'
        'fi\n'
        'if [ "$1" = "project" ]; then\n'
        '  echo "{\\"items\\":[{\\"content\\":{\\"number\\":42},\\"status\\":\\"Ready #1\\"}]}"; exit 0\n'
        'fi\nexit 0\n')
    gh.chmod(0o755)
    e["PATH"] = f"{bindir}:{e['PATH']}"
    e["GH_LOG"] = str(tmp_path / "gh.log")
    e["CLAUDE_PID"] = str(os.getpid())  # a genuinely live owning session
    opened = subprocess.run(["bash", lane_sh, "open", "42"], cwd=str(repo),
                            env=e, capture_output=True, text=True)
    assert opened.returncode == 0, opened.stderr

    out = subprocess.run(["bash", LANE_ORPHANS_SH], cwd=str(repo), env=e,
                         capture_output=True, text=True)
    assert "dead-owner" not in out.stdout, (
        f"a freshly-opened lane must not read as dead-owner: {out.stdout}")
    assert out.returncode == 0, out.stdout


def test_a_pid_on_another_host_is_not_judged(env, tmp_path):
    """Another machine's pid namespace is unknowable from here; guessing would
    manufacture a false death."""
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 99)
    write_ledger(env, [row(99, repo, wt, pid=_dead_pid(), host="some-other-box")])
    r = run(env, repo)
    assert "dead-owner" not in r.stdout
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------------------------
# over-cap + its clean pair
# ---------------------------------------------------------------------------


def test_over_cap_is_reported(env, tmp_path):
    repo = make_repo(tmp_path)
    rows = []
    for n in (1, 2, 3, 4):
        rows.append(row(n, repo, make_lane_dir(repo, n)))
    write_ledger(env, rows)  # 4 open vs lane.max_open = 3
    r = run(env, repo)
    assert r.returncode == 1
    assert "over-cap" in r.stdout
    assert "lane.max_open=3" in r.stdout


def test_at_cap_is_not_over_cap(env, tmp_path):
    repo = make_repo(tmp_path)
    rows = [row(n, repo, make_lane_dir(repo, n)) for n in (1, 2, 3)]
    write_ledger(env, rows)
    r = run(env, repo)
    assert r.returncode == 0, r.stdout
    assert "over-cap" not in r.stdout


def test_abandoned_over_cap_is_reported_separately(env, tmp_path):
    repo = make_repo(tmp_path)
    rows = [row(n, repo, make_lane_dir(repo, n), event="abandoned")
            for n in (1, 2, 3, 4)]
    write_ledger(env, rows)
    r = run(env, repo)
    assert r.returncode == 1
    assert "lane.max_abandoned=3" in r.stdout


# ---------------------------------------------------------------------------
# the ^issue-N- anchor (CSA's 236 legacy checkouts)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("legacy", [
    "wf_something",
    "agent-abc123",
    "feature-issue-42-thing",   # 'issue-' present but NOT at the start
    "issues-42-thing",          # near-miss on the literal
    "issue-abc-thing",          # no number after 'issue-'
])
def test_legacy_worktree_names_are_not_reported_as_orphans(env, tmp_path, legacy):
    repo = make_repo(tmp_path)
    d = repo / ".claude" / "worktrees" / legacy
    d.mkdir(parents=True)
    (d / "x.txt").write_text("legacy\n")
    r = run(env, repo)
    assert r.returncode == 0, f"{legacy} was wrongly reported: {r.stdout}"
    assert "orphan-worktree" not in r.stdout


def test_a_real_lane_name_IS_reported(env, tmp_path):
    """The paired positive: the anchor is narrow, not broken."""
    repo = make_repo(tmp_path)
    d = repo / ".claude" / "worktrees" / "issue-42-real-lane"
    d.mkdir(parents=True)
    r = run(env, repo)
    assert r.returncode == 1
    assert "orphan-worktree" in r.stdout


# ---------------------------------------------------------------------------
# WRITES NOTHING, EVER
# ---------------------------------------------------------------------------


def test_writes_nothing_even_when_it_has_findings(env, tmp_path):
    repo = make_repo(tmp_path)
    # Every finding class at once, so the write-free property is proven on the
    # busiest path rather than the quiet one.
    live = make_lane_dir(repo, 1)
    orphan_dir = make_lane_dir(repo, 2)          # -> orphan-worktree
    ghost = repo / ".claude" / "worktrees" / "issue-3-ghost"  # -> orphan-row
    dead = make_lane_dir(repo, 4)                # -> dead-owner
    write_ledger(env, [
        row(1, repo, live),
        row(3, repo, ghost),
        row(4, repo, dead, pid=_dead_pid()),
    ])
    assert orphan_dir.is_dir()

    repo_before = tree_hash(repo)
    ledger_before = env["ledger"].read_bytes()
    lanes_before = tree_hash(env["lane_dir"])

    r = run(env, repo)
    assert r.returncode == 1
    assert "orphan-worktree" in r.stdout
    assert "orphan-row" in r.stdout
    assert "dead-owner" in r.stdout
    assert "changed nothing" in r.stdout

    assert tree_hash(repo) == repo_before, "lane_orphans.sh must not touch the repo"
    assert env["ledger"].read_bytes() == ledger_before, "must not touch the ledger"
    assert tree_hash(env["lane_dir"]) == lanes_before


def test_writes_nothing_on_the_clean_path_either(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 42)
    write_ledger(env, [row(42, repo, wt)])
    before = tree_hash(repo)
    ledger_before = env["ledger"].read_bytes()
    r = run(env, repo)
    assert r.returncode == 0
    assert tree_hash(repo) == before
    assert env["ledger"].read_bytes() == ledger_before


def test_source_contains_no_removal_verb():
    src = Path(LANE_ORPHANS_SH).read_text()
    # Falsifiability guard: a grep for absent strings passes vacuously against
    # a stub or an absent file, so prove first that this IS lane_orphans.sh.
    assert "orphan-worktree" in src and "dead-owner" in src, (
        f"{LANE_ORPHANS_SH} is not a real lane_orphans.sh; grep would be vacuous"
    )
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    for bad in ("rmtree", "os.remove", "os.unlink", "worktree remove",
                "branch -D", "rm -rf", "--force"):
        assert bad not in code, f"lane_orphans.sh must never {bad}"


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------


def test_a_corrupt_ledger_line_does_not_wedge_the_report(env, tmp_path):
    repo = make_repo(tmp_path)
    wt = make_lane_dir(repo, 42)
    env["ledger"].write_text(
        "{not json at all\n"
        + json.dumps(row(42, repo, wt), separators=(",", ":")) + "\n")
    r = run(env, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_rows_from_another_repo_are_ignored(env, tmp_path):
    repo = make_repo(tmp_path)
    other = make_repo(tmp_path, name="other")
    write_ledger(env, [row(55, other, other / ".claude" / "worktrees" / "issue-55-x")])
    r = run(env, repo)
    assert r.returncode == 0, r.stdout
    assert "#55" not in r.stdout
