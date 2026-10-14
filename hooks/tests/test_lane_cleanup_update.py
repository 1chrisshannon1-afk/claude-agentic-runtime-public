"""Tests for `/lane-cleanup`'s `UPDATE` snippet (P12, the merge-slot update, 6.4).

Spec source: `~/.claude/plans/otherapp_lane_cutover_after_deploy.md`, the "#### P12 in full"
section (new 6.4 Update). The snippet under test is extracted VERBATIM from
`~/.claude/skills/lane-cleanup/SKILL.md`, between its `# BEGIN lane-cleanup UPDATE` and
`# END lane-cleanup UPDATE` sentinel comments, so the doc text and this test can never silently
drift apart: whatever ships in the skill is exactly what runs here.

Four cases, per the spec:
  1. a clean update prints `UPDATED`, the tree is clean, and the base is an ancestor of the lane tip;
  2. a conflicting base prints `CONFLICT`, with HEAD unchanged and no `MERGE_HEAD`;
  3. a second run (base already merged in) prints `SKIP`;
  4. a dirty lane prints `STOP`.

Sandbox conventions and fixtures are IMPORTED from `test_lane_sh.py` (fix-round item 21), not
copied: `stub_gh`, `_GH_OK`, `MANIFEST`, `_git`, `make_repo`, `lane`, `worktrees`, `branches`, and
the `env` fixture are that file's own definitions, byte-identical to what this file previously
duplicated. This means a lane opened here goes through the SAME `LANE_DIR`/`CLAUDE_DIR`-redirected,
stubbed-`gh` sandbox `test_lane_sh.py` already uses, and any future change to that sandbox's shape
(a new env var, a fixture field) is picked up here automatically instead of silently drifting. This
file itself never invokes `lane.sh` directly (only the imported `lane()` helper does, using
`test_lane_sh.py`'s own `LANE_SH`/`REPO_MANIFEST_PY` constants) -- its own only environment-overridable
path is `SKILL_MD` (`LANE_CLEANUP_SKILL_MD`), the file the `UPDATE` snippet is extracted from.

Falsifiability (CLAUDE.md §6): the conflict case is proven to actually exercise the `merge-tree`
guard, not merely pass vacuously, by running the UNGUARDED block (the guard's `if` removed, in a
SCRATCH COPY of the extracted text only -- the real SKILL.md is never touched) and showing it goes
RED (it stops reporting `CONFLICT` and instead attempts the merge, which fails differently). See
`test_conflict_case_is_falsifiable_guard_removed_goes_red`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Import shared fixtures/helpers from the sibling test module rather than
# duplicating them (fix-round item 21). Both files live in the same
# `hooks/tests/` directory, which pytest's rootdir-insertion already puts on
# `sys.path` when either is collected -- but this file is also runnable
# directly by `python3 -m pytest <this file>` on its own, so the directory is
# inserted explicitly here too rather than relying on collection order.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lane_sh as _lane_sh  # noqa: E402
from test_lane_sh import (  # noqa: E402
    MANIFEST,
    _git,
    branches,
    lane,
    make_repo,
    stub_gh,
    worktrees,
)
from test_lane_sh import _GH_OK  # noqa: E402

# Re-export the shared `env` pytest fixture so it is collected for this module.
# It is bound by assignment, not `from test_lane_sh import env`: this module's
# tests and helpers take `env` as a parameter, and a plain import would make
# every one of them a redefinition (F811) of an otherwise-unused import (F401).
env = _lane_sh.env

SKILL_MD = os.environ.get(
    "LANE_CLEANUP_SKILL_MD",
    str(Path.home() / ".claude" / "skills" / "lane-cleanup" / "SKILL.md"),
)

BEGIN_MARK = "# BEGIN lane-cleanup UPDATE"
END_MARK = "# END lane-cleanup UPDATE"


def _extract_update_block(skill_md_path: str) -> str:
    """Extract the UPDATE snippet's `bash <<'SH' ... SH` body from SKILL.md.

    Reads between the sentinel comments, strips the outer `bash <<'SH'` / `SH` wrapper (the test
    drives the inner script directly, substituting its own `<main>`/`<wt>`/`<branch>`/`<base_ref>`
    placeholders), and returns the raw shell body.
    """
    text = Path(skill_md_path).read_text(encoding="utf-8")
    start = text.index(BEGIN_MARK)
    end = text.index(END_MARK, start)
    block = text[start:end]
    lines = block.splitlines()
    # Drop the BEGIN marker line and the `bash <<'SH'` line; drop the trailing bare `SH` line.
    body_lines = []
    in_heredoc = False
    for ln in lines:
        if ln.strip() == BEGIN_MARK:
            continue
        if not in_heredoc and ln.strip() == "bash <<'SH'":
            in_heredoc = True
            continue
        if in_heredoc and ln.strip() == "SH":
            in_heredoc = False
            continue
        if in_heredoc:
            body_lines.append(ln)
    body = "\n".join(body_lines)
    assert "merge-tree" in body and "MERGE_HEAD" in body, (
        f"{skill_md_path} extraction found no real UPDATE body between the sentinels; "
        "this test would pass vacuously"
    )
    return body


UPDATE_BODY = _extract_update_block(SKILL_MD)

# The merge-tree discrimination block (rc alone cannot tell a genuine CONFLICT from an unrelated
# `merge-tree` failure -- both return rc 1 -- so the real script checks whether stdout's first line
# is a valid tree id). Shared between the two tests that mutate it, so they cannot silently drift
# apart from each other even if the extracted text changes.
MERGE_TREE_GUARD_BLOCK = (
    'out=$(git -C "$main" merge-tree --write-tree --name-only "$base" "refs/heads/$br"); mt_rc=$?\n'
    'tree=$(printf \'%s\\n\' "$out" | head -n1)\n'
    'if [ "$mt_rc" -ne 0 ]; then\n'
    '  case "$tree" in\n'
    '    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*)\n'
    '      echo "CONFLICT (nothing changed):"; printf \'%s\\n\' "$out" | sed -n \'2,/^$/p\'; exit 2 ;;\n'
    '    *)\n'
    '      echo "STOP merge-tree failed rc=$mt_rc"; printf \'%s\\n\' "$out"; exit 1 ;;\n'
    "  esac\n"
    "fi"
)


def _merge_head_path(wt: str) -> Path:
    """Resolve MERGE_HEAD's real path for a worktree. `<wt>/.git` is a FILE (a gitdir pointer),
    not a directory, so `MERGE_HEAD` never lives at `<wt>/.git/MERGE_HEAD`; it lives under the
    worktree's own private git-dir, which `git rev-parse --git-path` resolves correctly."""
    p = subprocess.run(["git", "-C", wt, "rev-parse", "--path-format=absolute",
                        "--git-path", "MERGE_HEAD"], capture_output=True, text=True, check=True)
    return Path(p.stdout.strip())


def _index_lock_path(wt: str) -> Path:
    """Resolve index.lock's real path for a worktree, the same way as `_merge_head_path` (a
    worktree's index.lock lives under its own private git-dir, never `<wt>/.git/index.lock`)."""
    p = subprocess.run(["git", "-C", wt, "rev-parse", "--path-format=absolute",
                        "--git-path", "index.lock"], capture_output=True, text=True, check=True)
    return Path(p.stdout.strip())


def _render(body: str, main: str, wt: str, branch: str, base_ref: str) -> str:
    """Substitute the doc's literal `<main>`/`<wt>`/`<branch>`/`<base_ref>` placeholders."""
    out = body
    for token, value in (
        ("<main>", main),
        ("<wt>", wt),
        ("<branch>", branch),
        ("<base_ref>", base_ref),
    ):
        out = out.replace(token, value)
    assert "<" not in out or "<(" in out, f"unsubstituted placeholder remains: {out!r}"
    return out


def run_update(env, main: str, wt: str, branch: str, base_ref: str) -> subprocess.CompletedProcess:
    script = _render(UPDATE_BODY, main, wt, branch, base_ref)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=main, env=env, capture_output=True, text=True,
    )


def _open_lane_and_move_base(env, repo, issue=42):
    """Open a lane against `issue`, then commit a NEW commit onto `origin/main`, simulating a
    merge slot that landed while the lane's PR was open. Returns `(wt, branch, base_ref)`.

    The base is moved via a SEPARATE clone of the upstream so it never touches `repo`'s own
    working tree or `origin/main` remote-tracking ref directly -- exactly mirroring how a real
    `origin/main` moves (another PR merges on GitHub), which `repo` then learns about only via a
    `git fetch` (the UPDATE script's own `git -C "$main" merge-base ...` reads run against
    whatever `origin/main` resolves to in `repo` right now -- so the fetch must happen before the
    script runs, exactly as 6.4's own R2 does in the real skill).
    """
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", str(issue))
    assert r.returncode == 0, r.stderr
    wt_name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / wt_name
    branch = [b for b in branches(repo) if b.startswith("issue/")][0]

    # Move origin/main forward via a throwaway clone (never repo's own worktree).
    upstream = repo.parent / "repo-upstream.git"
    clone_dir = repo.parent / "base-mover-clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone_dir)],
                   check=True, capture_output=True)
    (clone_dir / "base-moved.txt").write_text("moved\n")
    _git(clone_dir, "add", "base-moved.txt")
    _git(clone_dir, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "base moved forward")
    _git(clone_dir, "push", "-q", "origin", "main")

    _git(repo, "fetch", "-q", "origin", "main")
    return wt, branch, "origin/main"


# ---------------------------------------------------------------------------
# 1. a clean update prints UPDATED, tree clean, base is an ancestor
# ---------------------------------------------------------------------------


def test_clean_update_prints_updated_and_lands_the_base(env, tmp_path):
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)

    r = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "UPDATED" in r.stdout, r.stdout
    assert _git(wt, "status", "--porcelain").stdout == ""
    assert _git(repo, "merge-base", "--is-ancestor", "origin/main", branch).returncode == 0
    assert _merge_head_path(str(wt)).exists() is False


# ---------------------------------------------------------------------------
# 2. a conflicting base prints CONFLICT, HEAD unchanged, no MERGE_HEAD
# ---------------------------------------------------------------------------


def test_conflicting_base_prints_conflict_and_changes_nothing(env, tmp_path):
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt_name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / wt_name
    branch = [b for b in branches(repo) if b.startswith("issue/")][0]
    head_before = _git(wt, "rev-parse", "HEAD").stdout.strip()

    # The lane edits README.md...
    (wt / "README.md").write_text("lane changed this\n")
    _git(wt, "add", "README.md")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "lane edits README")
    head_before = _git(wt, "rev-parse", "HEAD").stdout.strip()

    # ...while the base moves forward with a CONFLICTING edit to the same line, via a separate clone.
    upstream = repo.parent / "repo-upstream.git"
    clone_dir = repo.parent / "base-mover-clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone_dir)],
                   check=True, capture_output=True)
    (clone_dir / "README.md").write_text("base changed this instead\n")
    _git(clone_dir, "add", "README.md")
    _git(clone_dir, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "base edits README differently")
    _git(clone_dir, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin", "main")

    r = run_update(env["env"], str(repo), str(wt), branch, "origin/main")
    assert r.returncode == 2, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    # Must be the GUARD's own verdict text ("CONFLICT (nothing changed):"), not merely the
    # substring "CONFLICT" -- git's own merge failure output also contains the word "CONFLICT"
    # (e.g. "CONFLICT (content): Merge conflict in README.md"), and an UNGUARDED script that lets
    # `git merge` itself hit the conflict, then aborts (the "ABORTED: the merge stopped although
    # merge-tree was clean" branch), leaves an IDENTICAL rc=2/HEAD-unchanged/no-MERGE_HEAD/clean-tree
    # signature -- exactly what made this assertion pass vacuously before it was tightened. The
    # guard's OWN wording is the only thing genuinely distinct between the two code paths.
    assert "CONFLICT (nothing changed)" in r.stdout, r.stdout
    assert "ABORTED" not in r.stdout, (
        "the merge-tree guard must stop BEFORE ever calling `git merge`, never reach the "
        "merge-then-abort branch: " + r.stdout
    )
    assert _git(wt, "rev-parse", "HEAD").stdout.strip() == head_before, (
        "HEAD must be unchanged after a CONFLICT: the merge is never attempted"
    )
    assert _merge_head_path(str(wt)).exists() is False
    assert _git(wt, "status", "--porcelain").stdout == ""


def test_conflict_case_is_falsifiable_guard_removed_goes_red(env, tmp_path):
    """Falsifiability (CLAUDE.md §6): prove the CONFLICT assertion actually depends on the
    `merge-tree` guard, by removing that guard from a SCRATCH COPY of the extracted body (never
    the real SKILL.md) and showing the same conflicting-base scenario no longer reports CONFLICT."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt_name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / wt_name
    branch = [b for b in branches(repo) if b.startswith("issue/")][0]

    (wt / "README.md").write_text("lane changed this\n")
    _git(wt, "add", "README.md")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "lane edits README")

    upstream = repo.parent / "repo-upstream.git"
    clone_dir = repo.parent / "base-mover-clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone_dir)],
                   check=True, capture_output=True)
    (clone_dir / "README.md").write_text("base changed this instead\n")
    _git(clone_dir, "add", "README.md")
    _git(clone_dir, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "base edits README differently")
    _git(clone_dir, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin", "main")

    # Mutate a SCRATCH COPY of the extracted body only: drop the whole merge-tree discrimination
    # block so the script always proceeds straight to `git merge`, regardless of merge-tree's own
    # exit code or output shape.
    assert MERGE_TREE_GUARD_BLOCK in UPDATE_BODY, "the guard text moved; update MERGE_TREE_GUARD_BLOCK"
    unguarded_body = UPDATE_BODY.replace(
        MERGE_TREE_GUARD_BLOCK,
        'out=$(git -C "$main" merge-tree --write-tree --name-only "$base" "refs/heads/$br" || true)',
    )
    assert unguarded_body != UPDATE_BODY

    script = _render(unguarded_body, str(repo), str(wt), branch, "origin/main")
    r = subprocess.run(["bash", "-c", script], cwd=str(repo), env=env["env"],
                        capture_output=True, text=True)
    # With the guard removed, the script no longer reports the script's OWN "CONFLICT (nothing
    # changed):" verdict for this scenario -- it falls through to the real `git merge` instead,
    # which fails on ITS OWN terms (git's own "CONFLICT (content): ..." text, distinct from the
    # guard's "CONFLICT (nothing changed):" message) and is then caught by the *next* `if`
    # (the "ABORTED: the merge stopped although merge-tree was clean" branch), which runs
    # `git merge --abort` and exits 2 -- a DIFFERENT stop reason than the guarded case reaches for
    # the identical input. That contrast -- the guard's own verdict text never appears, and the
    # script instead reaches the "merge-tree was clean" abort branch it is never supposed to reach
    # when the base and lane genuinely conflict -- is what proves the guarded assertion above (test
    # `test_conflicting_base_prints_conflict_and_changes_nothing`) is not vacuous: removing the
    # guard measurably changes which branch fires for the same conflicting-base scenario.
    assert "CONFLICT (nothing changed)" not in r.stdout, (
        f"the unguarded script still printed the guard's own verdict; the guard-removal mutation "
        f"did not change behavior, so the guarded test above would pass vacuously: {r.stdout!r}"
    )
    assert "ABORTED" in r.stdout and r.returncode == 2, (
        f"the unguarded script should reach the merge-tree-was-clean ABORTED branch instead "
        f"(a different stop reason than the guarded CONFLICT case): {r.stdout!r} rc={r.returncode}"
    )
    assert _merge_head_path(str(wt)).exists() is False, (
        "git merge --abort should have cleared MERGE_HEAD before this script exited"
    )


# ---------------------------------------------------------------------------
# 3. a second run (base already merged in) prints SKIP
# ---------------------------------------------------------------------------


def test_second_run_after_update_prints_skip(env, tmp_path):
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)

    r1 = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    assert r1.returncode == 0 and "UPDATED" in r1.stdout, r1.stdout

    r2 = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    assert r2.returncode == 0, f"stdout={r2.stdout!r} stderr={r2.stderr!r}"
    assert "SKIP" in r2.stdout, r2.stdout
    assert "UPDATED" not in r2.stdout


# ---------------------------------------------------------------------------
# 4. a dirty lane prints STOP
# ---------------------------------------------------------------------------


def test_dirty_lane_prints_stop(env, tmp_path):
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)
    (wt / "scratch.txt").write_text("uncommitted\n")

    r = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "STOP" in r.stdout, r.stdout
    assert "lane tree is not clean" in r.stdout
    # Nothing was touched beyond the caller's own scratch file.
    assert (wt / "scratch.txt").read_text() == "uncommitted\n"
    assert _merge_head_path(str(wt)).exists() is False


def test_lane_head_not_branch_prints_stop(env, tmp_path):
    """The paired precondition case: the lane's HEAD must equal `<branch>` itself. A caller that
    passes the wrong `<branch>` argument (a stale ledger read, a typo) is refused, never merged
    into the wrong ref."""
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)

    r = run_update(env["env"], str(repo), str(wt), "not-the-real-branch", base_ref)
    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "STOP" in r.stdout and "lane HEAD is not" in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# Fix-round item 17: a REAL merge commit (two parents), a MERGE_HEAD-present
# STOP, and a merge-tree-error STOP (distinct from CONFLICT).
# ---------------------------------------------------------------------------


def test_real_merge_commit_update_has_two_parents_and_stays_clean(env, tmp_path):
    """Item 17: the lane carries its OWN genuine commit (not just an
    untouched branch-from-base, as `_open_lane_and_move_base` alone would
    leave it) before the base moves. `UPDATE` must actually run a real merge
    (never a fast-forward), producing a merge commit with exactly two
    parents: the lane's own prior tip and the new base tip. Any linked paths
    (`lane.link_paths`) must still resolve correctly afterward -- the merge
    must not disturb them."""
    repo = make_repo(
        tmp_path,
        manifest={**MANIFEST, "lane": {**MANIFEST["lane"], "link_paths": ["scripts/hooks/pii_denylist.txt"]}},
    )
    hooks_dir = repo / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pii_denylist.txt").write_text("555-1234\n")
    _git(repo, "fetch", "-q", "origin", "main")
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt_name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / wt_name
    branch = [b for b in branches(repo) if b.startswith("issue/")][0]
    link = wt / "scripts" / "hooks" / "pii_denylist.txt"
    assert link.is_symlink(), "sanity: the lane must actually carry the link before the merge"

    lane_tip_before = _git(wt, "rev-parse", "HEAD").stdout.strip()

    # The lane makes its OWN genuine commit, touching a file the base never touches.
    (wt / "lane_only.txt").write_text("lane's own work\n")
    _git(wt, "add", "lane_only.txt")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "lane's own commit")
    lane_own_commit = _git(wt, "rev-parse", "HEAD").stdout.strip()
    assert lane_own_commit != lane_tip_before

    # The base moves forward via a separate clone, touching a DIFFERENT file (no conflict).
    upstream = repo.parent / "repo-upstream.git"
    clone_dir = repo.parent / "base-mover-clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone_dir)],
                   check=True, capture_output=True)
    (clone_dir / "base_only.txt").write_text("base's own work\n")
    _git(clone_dir, "add", "base_only.txt")
    _git(clone_dir, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "base's own commit")
    _git(clone_dir, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin", "main")
    base_tip = _git(repo, "rev-parse", "origin/main").stdout.strip()

    r = run_update(env["env"], str(repo), str(wt), branch, "origin/main")
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "UPDATED" in r.stdout, r.stdout

    new_tip = _git(wt, "rev-parse", "HEAD").stdout.strip()
    assert new_tip != lane_own_commit, "a real merge commit must exist, not a no-op"
    parents = _git(wt, "log", "-1", "--pretty=%P", new_tip).stdout.strip().split()
    assert len(parents) == 2, f"expected a two-parent merge commit, got parents={parents}"
    assert lane_own_commit in parents and base_tip in parents, (
        f"the merge commit's parents must be exactly the lane's own prior tip and the new base "
        f"tip: parents={parents}, lane_own_commit={lane_own_commit}, base_tip={base_tip}"
    )
    # Both files -- the lane's own and the base's own -- are present (a real, non-conflicting merge).
    assert (wt / "lane_only.txt").exists()
    assert (wt / "base_only.txt").exists()
    assert _git(wt, "status", "--porcelain").stdout == ""
    # The link is untouched by the merge.
    assert link.is_symlink()
    assert link.resolve() == (repo / "scripts" / "hooks" / "pii_denylist.txt").resolve()


def test_merge_head_already_present_prints_stop(env, tmp_path):
    """A stale `MERGE_HEAD` exists in the lane with an otherwise CLEAN working tree -- e.g. a
    process crashed after `git merge --abort` removed everything else but before it removed
    `MERGE_HEAD` itself, or some other leftover from a prior incomplete merge attempt.

    This is deliberately NOT built via an ordinary in-progress `git merge` (verified by direct
    execution: `git merge --no-commit`, and even a genuinely conflicting merge, both ALWAYS leave
    `git status --porcelain` non-empty -- a merge always stages or conflicts something -- so the
    real script's clean-tree check, which runs BEFORE the `MERGE_HEAD` check, would catch either of
    those first and this test would never actually reach the `MERGE_HEAD` check at all). The
    scenario that genuinely isolates it is a STALE `MERGE_HEAD` file with nothing else disturbed,
    which is realistic (a crash mid-abort, or manually-restored `.git` state) and is the only shape
    that reaches this specific check."""
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)
    assert _git(wt, "status", "--porcelain").stdout == "", "sanity: the lane starts clean"

    lane_head = _git(wt, "rev-parse", "HEAD").stdout.strip()
    mh_path = _merge_head_path(str(wt))
    mh_path.write_text(lane_head + "\n")
    assert _git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0, (
        "sanity: MERGE_HEAD must actually resolve"
    )
    assert _git(wt, "status", "--porcelain").stdout == "", (
        "sanity: a stale MERGE_HEAD alone must not dirty the tree -- if it does, this scenario no "
        "longer isolates the MERGE_HEAD check from the clean-tree check"
    )

    r = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "STOP" in r.stdout and "merge is already in progress" in r.stdout, r.stdout
    # UPDATE must not have touched the in-progress merge at all.
    assert _merge_head_path(str(wt)).exists(), "UPDATE must leave the existing MERGE_HEAD untouched"
    assert _git(wt, "status", "--porcelain").stdout == "", "UPDATE must not have dirtied the tree"


def test_merge_tree_error_prints_stop_not_conflict(env, tmp_path):
    """Item 4's paired negative: `git merge-tree` failing for a reason OTHER than an actual
    conflict (here forced by passing an UNRESOLVABLE base ref -- verified by direct execution to
    return the SAME rc as a genuine conflict, rc 1, which is exactly why exit code alone cannot be
    the discriminator; see the real UPDATE block's own comment) must print
    `STOP merge-tree failed rc=<rc>`, never the CONFLICT verdict (which would incorrectly tell the
    coordinator "two owners touched one file")."""
    repo = make_repo(tmp_path)
    wt, branch, _base_ref = _open_lane_and_move_base(env, repo)

    bogus_base = "refs/heads/this-ref-does-not-exist-at-all"
    r = run_update(env["env"], str(repo), str(wt), branch, bogus_base)
    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "STOP merge-tree failed rc=" in r.stdout, r.stdout
    assert "CONFLICT" not in r.stdout, (
        "an unresolvable-ref failure must never be reported as a CONFLICT: " + r.stdout
    )
    assert _merge_head_path(str(wt)).exists() is False
    assert _git(wt, "status", "--porcelain").stdout == ""


# ---------------------------------------------------------------------------
# Fix-round item 5: `merge --abort`'s own result is checked before the script
# reports ABORTED.
# ---------------------------------------------------------------------------


def test_abort_result_is_verified_before_reporting_aborted(env, tmp_path):
    """Item 5, the paired positive: the ordinary CONFLICT-then-abort path (a real `git merge`
    failure that `merge --abort` genuinely cleans up) must still reach `ABORTED`, proving the new
    abort-verification checks do not break the legitimate case they guard."""
    repo = make_repo(tmp_path)
    stub_gh(env, _GH_OK)
    r = lane(env, repo, "open", "42")
    assert r.returncode == 0, r.stderr
    wt_name = worktrees(repo)[0]
    wt = repo / ".claude" / "worktrees" / wt_name
    branch = [b for b in branches(repo) if b.startswith("issue/")][0]

    (wt / "README.md").write_text("lane changed this\n")
    _git(wt, "add", "README.md")
    _git(wt, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "lane edits README")

    upstream = repo.parent / "repo-upstream.git"
    clone_dir = repo.parent / "base-mover-clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone_dir)],
                   check=True, capture_output=True)
    (clone_dir / "README.md").write_text("base changed this instead\n")
    _git(clone_dir, "add", "README.md")
    _git(clone_dir, "-c", "user.email=t@x.invalid", "-c", "user.name=t",
         "commit", "-m", "base edits README differently")
    _git(clone_dir, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin", "main")

    # Directly exercise the merge/abort tail of UPDATE_BODY by mutating a scratch copy that skips
    # straight past the merge-tree guard (so the REAL `git merge` runs and REALLY conflicts) --
    # this is the same technique the guard-removal falsifiability test uses, reused here to reach
    # the abort-verification code with a genuine conflict rather than merge-tree's own pre-check.
    assert MERGE_TREE_GUARD_BLOCK in UPDATE_BODY
    body_skipping_precheck = UPDATE_BODY.replace(
        MERGE_TREE_GUARD_BLOCK, ": # merge-tree pre-check skipped for this test"
    )
    script = _render(body_skipping_precheck, str(repo), str(wt), branch, "origin/main")
    r = subprocess.run(["bash", "-c", script], cwd=str(repo), env=env["env"],
                        capture_output=True, text=True)
    assert r.returncode == 2, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "ABORTED" in r.stdout, r.stdout
    assert _merge_head_path(str(wt)).exists() is False, "a verified-successful abort leaves no MERGE_HEAD"
    assert _git(wt, "status", "--porcelain").stdout == "", "a verified-successful abort leaves a clean tree"


# ---------------------------------------------------------------------------
# Fix-round-2 item 5: a `git merge` that fails to start at all (no MERGE_HEAD,
# clean tree) must never reach `merge --abort` or be carded as an abort
# failure.
# ---------------------------------------------------------------------------

_NEVER_STARTED_GUARD = (
    'if ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null && [ -z "$(git -C "$wt" status --porcelain)" ]; then\n'
    '    echo "STOP merge did not start; nothing changed"; exit 1\n'
    "  fi\n"
)


def test_merge_that_never_starts_prints_stop_and_never_calls_abort(env, tmp_path):
    """Item 5: a pre-existing `index.lock` in the LANE's own git dir blocks `git merge` before it
    ever creates `MERGE_HEAD` or touches the working tree (verified by direct execution: rc 1, no
    `MERGE_HEAD`, `git status --porcelain` stays empty -- the exact shape the new check tests for).
    UPDATE must recognize this as "never started" and report `STOP merge did not start; nothing
    changed`, WITHOUT ever calling `git merge --abort` (there is nothing to abort, and calling it
    against a lock-blocked repo would fail for an unrelated reason, which would be misreported as
    an abort failure)."""
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)

    lock_path = _index_lock_path(str(wt))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("")
    try:
        r = run_update(env["env"], str(repo), str(wt), branch, base_ref)
    finally:
        if lock_path.exists():
            lock_path.unlink()

    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "STOP merge did not start; nothing changed" in r.stdout, r.stdout
    assert "ABORTED" not in r.stdout, r.stdout
    assert "abort" not in r.stdout.lower(), (
        f"an abort-path message must never appear for a merge that never started: {r.stdout!r}"
    )
    assert _merge_head_path(str(wt)).exists() is False
    assert _git(wt, "status", "--porcelain").stdout == ""


def test_never_started_check_is_falsifiable_guard_removed_goes_red(env, tmp_path):
    """Falsifiability (CLAUDE.md §6): prove the "never started" check actually matters, by removing
    it from a SCRATCH COPY of the extracted body (never the real SKILL.md) and showing the same
    `index.lock` scenario now falls through to `git merge --abort` instead -- which fails for an
    unrelated reason (there is no merge in progress to abort) and gets misreported as an abort
    failure, exactly the miscategorization the real check exists to prevent."""
    repo = make_repo(tmp_path)
    wt, branch, base_ref = _open_lane_and_move_base(env, repo)

    assert _NEVER_STARTED_GUARD in UPDATE_BODY, "the guard text moved; update _NEVER_STARTED_GUARD"
    unguarded_body = UPDATE_BODY.replace(_NEVER_STARTED_GUARD, "")
    assert unguarded_body != UPDATE_BODY

    lock_path = _index_lock_path(str(wt))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("")
    try:
        script = _render(unguarded_body, str(repo), str(wt), branch, base_ref)
        r = subprocess.run(["bash", "-c", script], cwd=str(repo), env=env["env"],
                            capture_output=True, text=True)
    finally:
        if lock_path.exists():
            lock_path.unlink()

    # With the guard removed, the script no longer reports "merge did not start" -- it falls
    # through to `git merge --abort`, which itself fails (nothing to abort) and is reported as
    # "STOP abort failed": a DIFFERENT, miscategorized outcome for the same input, proving the
    # guarded assertion above is not vacuous.
    assert "STOP merge did not start; nothing changed" not in r.stdout, (
        f"the unguarded script still reported the correct verdict; the guard-removal mutation did "
        f"not change behavior, so the guarded test above would pass vacuously: {r.stdout!r}"
    )
    assert "STOP abort failed" in r.stdout, (
        f"the unguarded script should reach the (miscategorized) abort-failure branch instead: "
        f"{r.stdout!r}"
    )
