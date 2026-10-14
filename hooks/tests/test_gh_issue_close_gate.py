"""Hermetic tests for hooks/gh_issue_close_gate.py.

Ports the PROVEN behavior of ~/.claude/scripts/gh_issue.sh's ``resolve`` guard:
an issue-close is REFUSED unless every referenced commit sha resolves to a real
commit in the current repo (fabricated-resolution guard). The bash test vectors
are the spec:

  * a REAL commit sha -> resolves -> ALLOW the close;
  * a FABRICATED sha  -> does not resolve -> BLOCK the close;
  * NO commit at all   -> BLOCK ("no close without a real fix").

These are exercised against a throwaway git repo (the `git_repo` fixture) with a
real commit and a fake sha — the exact "real + fake sha" spec — then expanded to
cover the pure decision function, command classification, ref extraction, the
LOG-ONLY-vs-enforce split, the CSA_DISABLE_HOOKS master-off, and every defensive
branch to >=90% line coverage.

Everything runs against the hermetic `sandbox` fixture ($HOME + _lib path
constants pointed into a tmp dir) so the operator's real ~/.claude is never
touched; the only git used is a local, offline throwaway repo.
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import _lib
import gh_issue_close_gate as gate
import pytest

# ===========================================================================
# Helpers.
# ===========================================================================


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = "t@t.t"
    env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_COMMITTER_EMAIL"] = "t@t.t"
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        check=True,
    )


def _has_real_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


@pytest.fixture
def repo_with_commit(git_repo):
    """A throwaway repo carrying exactly one real, empty commit.

    Returns (repo_path, real_sha, tree_sha). Skips the test if real git is
    unavailable (the fabricated `.git` fallback can't hold a commit object).
    """
    if not _has_real_git() or not (git_repo / ".git").is_dir():
        pytest.skip("real git unavailable for commit-resolution test")
    # git_repo already ran `git init`; make one empty commit.
    try:
        _git(git_repo, "commit", "-q", "--allow-empty", "-m", "first")
        real_sha = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
        tree_sha = _git(git_repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    except Exception:
        pytest.skip("could not create a commit in throwaway repo")
    return git_repo, real_sha, tree_sha


@pytest.fixture
def repo_with_branches(git_repo):
    """A throwaway repo with two diverging branches for ancestry checks.

    Returns (repo_path, prod_branch, shared_sha, staging_only_sha, unmerged_sha):

      * prod_branch      -- name of the repo's initial branch (whatever `git
                             init` picked — main or master), used as the "prod"
                             ref in tests so nothing here hardcodes a name.
      * shared_sha        -- committed on prod_branch BEFORE staging branched
                              off -> ancestor of BOTH prod_branch and staging.
      * staging_only_sha  -- staging's own extra commit, never merged back ->
                              ancestor of staging, NOT of prod_branch.
      * unmerged_sha       -- committed on a third branch merged nowhere ->
                              ancestor of NEITHER.

    Skips if real git is unavailable (mirrors repo_with_commit — the fabricated
    `.git` fallback can't hold real commits or branches).
    """
    if not _has_real_git() or not (git_repo / ".git").is_dir():
        pytest.skip("real git unavailable for ancestry test")
    try:
        _git(git_repo, "commit", "-q", "--allow-empty", "-m", "shared")
        shared_sha = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
        prod_branch = _git(git_repo, "symbolic-ref", "--short", "HEAD").stdout.strip()

        _git(git_repo, "checkout", "-q", "-b", "staging")
        _git(git_repo, "commit", "-q", "--allow-empty", "-m", "staging-only")
        staging_only_sha = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

        _git(git_repo, "checkout", "-q", "-b", "feature", prod_branch)
        _git(git_repo, "commit", "-q", "--allow-empty", "-m", "unmerged")
        unmerged_sha = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

        _git(git_repo, "checkout", "-q", prod_branch)
    except Exception:
        pytest.skip("could not build branch fixture in throwaway repo")
    return git_repo, prod_branch, shared_sha, staging_only_sha, unmerged_sha


FAKE_SHA = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


# ===========================================================================
# commit_resolves() — the ONLY function that shells to git. Real + fake sha.
# This is the direct port of `git cat-file -e "<sha>^{commit}"`.
# ===========================================================================


def test_commit_resolves_real_sha(repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    assert gate.commit_resolves(real_sha, str(repo)) is True


def test_commit_resolves_real_short_sha(repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    assert gate.commit_resolves(real_sha[:8], str(repo)) is True


def test_commit_resolves_fake_sha(repo_with_commit):
    repo, _real, _tree = repo_with_commit
    assert gate.commit_resolves(FAKE_SHA, str(repo)) is False


def test_commit_resolves_garbage_ref(repo_with_commit):
    repo, _real, _tree = repo_with_commit
    assert gate.commit_resolves("not-a-sha", str(repo)) is False


def test_commit_resolves_tree_is_not_a_commit(repo_with_commit):
    # A tree object peeled to ^{commit} does NOT resolve — the bash guard only
    # accepts real commits, so this is the correct fail-closed behavior.
    repo, _real, tree_sha = repo_with_commit
    assert gate.commit_resolves(tree_sha, str(repo)) is False


def test_commit_resolves_empty_sha_is_false():
    assert gate.commit_resolves("", "/tmp") is False


def test_commit_resolves_non_repo_dir_is_false(tmp_path):
    # A plain directory that is not a git repo -> git cat-file fails -> False.
    assert gate.commit_resolves(FAKE_SHA, str(tmp_path)) is False


def test_commit_resolves_swallows_subprocess_error(monkeypatch):
    # If subprocess.run itself raises (e.g. git missing), fail-closed to False.
    def boom(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(gate.subprocess, "run", boom)
    assert gate.commit_resolves(FAKE_SHA, "/tmp") is False


def test_commit_resolves_passes_none_cwd_when_repo_empty(monkeypatch):
    captured = {}

    class _Proc:
        returncode = 0

    def fake_run(argv, **kwargs):
        captured.update(kwargs)
        return _Proc()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    assert gate.commit_resolves("abc1234", "") is True
    assert captured["cwd"] is None  # empty repo string -> cwd=None


# ===========================================================================
# needs_block() — the pure guard, against the real + fake sha, resolver-injected.
# THE SPEC: block unless every referenced commit sha resolves in-repo.
# ===========================================================================


def test_needs_block_real_sha_allows(repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    block, reason = gate.needs_block([real_sha], str(repo))
    assert block is False
    assert reason == ""


def test_needs_block_fake_sha_blocks(repo_with_commit):
    repo, _real, _tree = repo_with_commit
    block, reason = gate.needs_block([FAKE_SHA], str(repo))
    assert block is True
    assert FAKE_SHA in reason
    assert "fabricated-resolution guard" in reason


def test_needs_block_real_and_fake_mixed_blocks_on_first_offender(repo_with_commit):
    # Bash `_die`s on the FIRST missing commit — with real THEN fake, it blocks
    # naming the fake; with fake THEN real, it blocks naming the fake first.
    repo, real_sha, _tree = repo_with_commit
    block, reason = gate.needs_block([real_sha, FAKE_SHA], str(repo))
    assert block is True
    assert FAKE_SHA in reason


def test_needs_block_all_real_allows(repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    block, _ = gate.needs_block([real_sha, real_sha[:8]], str(repo))
    assert block is False


def test_needs_block_no_commits_blocks():
    # No resolving commit at all -> BLOCK (bash: "no close without a real fix").
    block, reason = gate.needs_block([], "/any/repo")
    assert block is True
    assert "no resolving commit" in reason


def test_needs_block_only_empty_strings_blocks():
    # Falsy entries are filtered; an all-empty list is treated as "no commits".
    block, reason = gate.needs_block(["", None], "/any/repo")  # type: ignore[list-item]
    assert block is True
    assert "no resolving commit" in reason


def test_needs_block_injected_resolver_true_allows():
    block, reason = gate.needs_block(["abc"], "/r", resolver=lambda s, r: True)
    assert block is False
    assert reason == ""


def test_needs_block_injected_resolver_false_blocks():
    block, reason = gate.needs_block(["abc"], "/r", resolver=lambda s, r: False)
    assert block is True
    assert "abc" in reason


def test_needs_block_resolver_exception_is_fail_closed():
    def boom(_s, _r):
        raise RuntimeError("resolver blew up")

    block, reason = gate.needs_block(["abc"], "/r", resolver=boom)
    assert block is True
    assert "abc" in reason


def test_needs_block_default_resolver_used_when_none(monkeypatch):
    # resolver=None -> defaults to commit_resolves; monkeypatch it to observe.
    calls = []

    def fake(sha, repo):
        calls.append((sha, repo))
        return True

    monkeypatch.setattr(gate, "commit_resolves", fake)
    block, _ = gate.needs_block(["abc"], "/r", resolver=None)
    assert block is False
    assert calls == [("abc", "/r")]


# ===========================================================================
# _is_gh / gh_close_segments / is_issue_close — command classification.
# ===========================================================================


def test_is_gh_basename_match():
    assert gate._is_gh(["gh", "issue", "close", "5"]) is True
    assert gate._is_gh(["/opt/homebrew/bin/gh", "issue", "close"]) is True
    assert gate._is_gh(["git", "status"]) is False
    assert gate._is_gh(["ghost", "x"]) is False
    assert gate._is_gh([]) is False


@pytest.mark.parametrize(
    "command",
    [
        "gh issue close 42",
        "gh issue close 42 --comment done",
        "gh issue close 42 --reason completed",
        "/usr/local/bin/gh issue close 7",
        "gh  issue  close  9",  # extra whitespace
    ],
)
def test_is_issue_close_true(command):
    assert gate.is_issue_close(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "gh issue view 42",
        "gh issue comment 42 --body hi",
        "gh pr close 42",  # pr, not issue
        "gh issue list",
        "git commit -m 'close #42'",
        "echo gh issue close 42",  # argv0 is echo, not gh
        "ls -la",
        "",
    ],
)
def test_is_issue_close_false(command):
    assert gate.is_issue_close(command) is False


def test_gh_close_requires_issue_before_close_order():
    # 'gh close ... issue' (wrong order / different verb) must NOT match: we
    # require the `issue` token to precede `close`.
    assert gate.gh_close_segments("gh close issue 5") == []


def test_gh_close_segments_compound_command():
    # Only the gh-issue-close segment is surfaced from a compound command.
    segs = gate.gh_close_segments("git status && gh issue close 5 --comment x")
    assert len(segs) == 1
    assert segs[0][:3] == ["gh", "issue", "close"]


def test_gh_close_segments_multiple():
    segs = gate.gh_close_segments("gh issue close 1 ; gh issue close 2")
    assert len(segs) == 2


def test_gh_close_segments_env_prefix_stripped():
    # A leading ENV=val assignment before gh is stripped (via _strip_prefix).
    segs = gate.gh_close_segments("GH_TOKEN=x gh issue close 5")
    assert len(segs) == 1
    assert gate._is_gh(segs[0]) is True


def test_gh_close_segments_empty_command():
    assert gate.gh_close_segments("") == []


def test_gh_close_segments_untokenizable_segment_skipped():
    # An unbalanced-quote segment tokenizes to None -> skipped, no crash.
    assert gate.gh_close_segments("gh issue close 'unterminated") == []


def test_gh_close_segments_swallows_exception(monkeypatch):
    def boom(_s):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(_lib, "_split_segments", boom)
    assert gate.gh_close_segments("gh issue close 5") == []


# ===========================================================================
# extract_commit_refs — --commit flags + resolution-verb-adjacent shas.
# ===========================================================================


def test_extract_commit_flag_single():
    refs = gate.extract_commit_refs("gh_issue.sh resolve 5 --commit abc1234 --body-file f")
    assert refs == ["abc1234"]


def test_extract_commit_flag_multiple_dedup_order():
    cmd = "resolve 5 --commit abc1234 --commit def5678 --commit abc1234"
    assert gate.extract_commit_refs(cmd) == ["abc1234", "def5678"]


def test_extract_commit_flag_equals_form():
    assert gate.extract_commit_refs("--commit=abc1234 x") == ["abc1234"]


def test_extract_resolution_verb_sha_in_comment():
    cmd = 'gh issue close 42 --comment "Fixes #42 in 1a2b3c4d5e"'
    assert "1a2b3c4d5e" in gate.extract_commit_refs(cmd)


def test_extract_closes_colon_sha():
    cmd = 'gh issue close 7 --comment "Closes: 0badc0de123"'
    assert "0badc0de123" in gate.extract_commit_refs(cmd)


def test_extract_no_verb_no_bare_sha_harvested():
    # A bare hex-looking token with NO resolution verb nearby is NOT harvested
    # (so it can't become a phantom commit that blocks a legitimate close).
    cmd = 'gh issue close 42 --comment "see build abcdef1234"'
    assert gate.extract_commit_refs(cmd) == []


def test_extract_issue_number_not_treated_as_sha():
    # An all-decimal token next to a verb is an issue number, not a commit-ish.
    cmd = 'gh issue close 42 --comment "Fixes #42"'
    assert gate.extract_commit_refs(cmd) == []


def test_extract_short_hex_below_floor_ignored():
    # <7 hex chars is below the sha floor even with a verb present.
    cmd = 'gh issue close 5 --comment "fixed in abc12"'
    assert gate.extract_commit_refs(cmd) == []


def test_extract_flag_wins_even_without_verb():
    # --commit is ALWAYS a resolving commit regardless of surrounding verbs.
    assert gate.extract_commit_refs("--commit abcdef1") == ["abcdef1"]


def test_extract_empty_command():
    assert gate.extract_commit_refs("") == []


def test_extract_swallows_exception(monkeypatch):
    class BoomRe:
        def finditer(self, _s):
            raise RuntimeError("boom")

    monkeypatch.setattr(gate, "_COMMIT_FLAG_RE", BoomRe())
    assert gate.extract_commit_refs("--commit abc1234") == []


# ===========================================================================
# detect_deploy_claim() — vocabulary-based deploy-target claim detection.
# THE SPEC: a "deployed"/"in prod"/"IN-PROD" phrase -> "prod"; an "on staging"/
# "ON-STAGING" phrase -> "staging"; neither -> None (existing behavior only).
# ===========================================================================


@pytest.mark.parametrize(
    "text",
    [
        "deployed",
        "this fix is deployed",
        "confirmed in prod",
        "confirmed IN-PROD now",
        "in-prod",
        "shipped to prod",
        "shipped to production",
        "live in prod",
        "live in production",
    ],
)
def test_detect_deploy_claim_prod_phrasing(text):
    assert gate.detect_deploy_claim(text) == "prod"


@pytest.mark.parametrize(
    "text",
    [
        "on staging",
        "ON-STAGING",
        "confirmed on-staging",
        "merged to staging",
        "in staging",
        "staging-only",
        "staging only fix",
    ],
)
def test_detect_deploy_claim_staging_phrasing(text):
    assert gate.detect_deploy_claim(text) == "staging"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "won't fix, duplicate of #12",
        "closing as not a bug",
        "fixed locally, not pushed anywhere",
        "gh issue close 5 --comment 'no deploy claim here'",
    ],
)
def test_detect_deploy_claim_none_when_no_deploy_vocabulary(text):
    assert gate.detect_deploy_claim(text) is None


def test_detect_deploy_claim_staging_wins_over_bare_deployed_word():
    # "deployed to staging" contains the bare PROD word "deployed" but names
    # staging as the destination -- staging must win, or this would wrongly
    # demand prod-ref ancestry for a claim that never claimed prod at all.
    assert gate.detect_deploy_claim("deployed to staging") == "staging"
    assert gate.detect_deploy_claim("auto-deployed to staging, awaiting promote") == "staging"


def test_detect_deploy_claim_none_input_is_none():
    assert gate.detect_deploy_claim(None) is None  # type: ignore[arg-type]


def test_detect_deploy_claim_swallows_exception(monkeypatch):
    class BoomRe:
        def search(self, _s):
            raise RuntimeError("boom")

    monkeypatch.setattr(gate, "_STAGING_CLAIM_RE", BoomRe())
    assert gate.detect_deploy_claim("deployed") is None


# ===========================================================================
# BLOCKER 2 -- prod wins on conflict; COMBINATION COVERAGE 20 combination
# space (prod+staging together, prod+negation, staging+unset-ref).
# ===========================================================================


def test_detect_deploy_claim_prod_wins_when_both_present_blocker2_repro():
    # Exact repro string from the review: a real, distinct prod claim
    # ("Deployed to production") alongside a real, distinct staging mention
    # ("verified on staging") in the SAME text -- prod (the stronger/riskier
    # claim) must win, not whichever regex happens to run first.
    text = "Deployed to production. Also verified on staging."
    assert gate.detect_deploy_claim(text) == "prod"


@pytest.mark.parametrize(
    "text",
    [
        "Shipped to prod today; ran a smoke test on staging first.",
        "in prod now. also on-staging for regression.",
        "live in production; staging still has the old build.",
    ],
)
def test_detect_deploy_claim_prod_wins_over_staging_various_phrasings(text):
    assert gate.detect_deploy_claim(text) == "prod"


@pytest.mark.parametrize(
    "text",
    [
        "not deployed yet, will ship next release",
        "this was never deployed",
        "isn't deployed",
        "not yet deployed",
    ],
)
def test_detect_deploy_claim_negation_is_not_a_prod_claim(text):
    # CORRECTNESS 7: an honest statement that something is NOT deployed must
    # never be misread as a claim that it IS.
    assert gate.detect_deploy_claim(text) is None


def test_detect_deploy_claim_negation_does_not_swallow_a_real_prod_claim_elsewhere():
    # A negated "deployed" in one clause must not blind the classifier to a
    # genuinely distinct, affirmative prod claim elsewhere in the same text.
    text = "not deployed to staging -- it's actually deployed to production"
    assert gate.detect_deploy_claim(text) == "prod"


# ===========================================================================
# target_ref_for_claim() — CSA_PROD_REF / CSA_STAGING_REF resolution.
# ===========================================================================


def test_target_ref_for_claim_prod_default_when_unset(monkeypatch):
    monkeypatch.delenv("CSA_PROD_REF", raising=False)
    assert gate.target_ref_for_claim("prod") == "origin/main"


def test_target_ref_for_claim_staging_unset_is_none_not_a_vacuous_default(monkeypatch):
    # BLOCKER 2 (second half): staging has NO safe generic default -- "HEAD"
    # would make the ancestry check vacuously true for any commit already on
    # the current branch. Unset/empty -> None ("not actually checkable"), not
    # a default that silently always passes.
    monkeypatch.delenv("CSA_STAGING_REF", raising=False)
    assert gate.target_ref_for_claim("staging") is None


def test_target_ref_for_claim_prod_honors_env_override(monkeypatch):
    monkeypatch.setenv("CSA_PROD_REF", "origin/production")
    assert gate.target_ref_for_claim("prod") == "origin/production"


def test_target_ref_for_claim_staging_honors_env_override(monkeypatch):
    monkeypatch.setenv("CSA_STAGING_REF", "origin/staging")
    assert gate.target_ref_for_claim("staging") == "origin/staging"


def test_target_ref_for_claim_empty_env_falls_back_to_default(monkeypatch):
    # An env var explicitly set to "" is treated the same as unset.
    monkeypatch.setenv("CSA_PROD_REF", "")
    assert gate.target_ref_for_claim("prod") == "origin/main"


def test_target_ref_for_claim_swallows_exception(monkeypatch):
    # Only raise for the two keys this function reads -- a wholesale
    # os.environ swap breaks pytest's own internals (they read other env vars,
    # e.g. PY_COLORS, mid-test), so this fakes a *targeted* environ failure.
    real_environ = gate.os.environ

    class _BoomOnRefKeys(dict):
        def get(self, key, default=None):
            if key in ("CSA_STAGING_REF", "CSA_PROD_REF"):
                raise RuntimeError("boom")
            return real_environ.get(key, default)

    monkeypatch.setattr(gate.os, "environ", _BoomOnRefKeys())
    assert gate.target_ref_for_claim("staging") is None
    assert gate.target_ref_for_claim("prod") == "origin/main"


# ===========================================================================
# commit_is_ancestor() — the ONLY function that shells `git merge-base
# --is-ancestor`. Real ancestor / real non-ancestor / unresolvable ref.
# ===========================================================================


def test_commit_is_ancestor_shared_commit_is_ancestor_of_both_branches(repo_with_branches):
    repo, prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    assert gate.commit_is_ancestor(shared_sha, prod_branch, str(repo)) is True
    assert gate.commit_is_ancestor(shared_sha, "staging", str(repo)) is True


def test_commit_is_ancestor_staging_only_commit_is_not_ancestor_of_prod(repo_with_branches):
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    # Target ref resolves fine; the commit definitively never reached it.
    assert gate.commit_is_ancestor(staging_only_sha, prod_branch, str(repo)) is False


def test_commit_is_ancestor_staging_only_commit_is_ancestor_of_staging(repo_with_branches):
    repo, _prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    assert gate.commit_is_ancestor(staging_only_sha, "staging", str(repo)) is True


def test_commit_is_ancestor_unmerged_commit_is_not_ancestor_of_either(repo_with_branches):
    repo, prod_branch, _shared, _staging_only, unmerged_sha = repo_with_branches
    assert gate.commit_is_ancestor(unmerged_sha, prod_branch, str(repo)) is False
    assert gate.commit_is_ancestor(unmerged_sha, "staging", str(repo)) is False


def test_commit_is_ancestor_unresolvable_target_ref_is_none(repo_with_branches):
    # A misconfigured/missing ref (e.g. CSA_PROD_REF pointing at a remote that
    # doesn't exist here) must degrade to "indeterminate", not "not an ancestor".
    repo, _prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    assert gate.commit_is_ancestor(shared_sha, "origin/does-not-exist", str(repo)) is None


def test_commit_is_ancestor_unresolvable_sha_is_none(repo_with_branches):
    repo, prod_branch, _shared, _staging_only, _unmerged = repo_with_branches
    assert gate.commit_is_ancestor(FAKE_SHA, prod_branch, str(repo)) is None


def test_commit_is_ancestor_empty_sha_is_none():
    assert gate.commit_is_ancestor("", "origin/main", "/tmp") is None


def test_commit_is_ancestor_empty_target_ref_is_none():
    assert gate.commit_is_ancestor("abc1234", "", "/tmp") is None


def test_commit_is_ancestor_non_repo_dir_is_none(tmp_path):
    assert gate.commit_is_ancestor("abc1234", "origin/main", str(tmp_path)) is None


def test_commit_is_ancestor_swallows_subprocess_error(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(gate.subprocess, "run", boom)
    assert gate.commit_is_ancestor("abc1234", "origin/main", "/tmp") is None


# ===========================================================================
# needs_block_for_ancestry() — the pure ancestry guard, resolver-injected.
# ===========================================================================


def test_needs_block_for_ancestry_true_resolver_allows():
    block, reason = gate.needs_block_for_ancestry(
        ["abc1234"], "/r", "prod", "origin/main", ancestry_resolver=lambda s, t, r: True
    )
    assert block is False
    assert reason == ""


def test_needs_block_for_ancestry_false_resolver_blocks():
    block, reason = gate.needs_block_for_ancestry(
        ["abc1234"], "/r", "prod", "origin/main", ancestry_resolver=lambda s, t, r: False
    )
    assert block is True
    assert "abc1234" in reason
    assert "origin/main" in reason
    assert "prod" in reason


def test_needs_block_for_ancestry_none_resolver_degrades_open():
    # Indeterminate (misconfigured ref, git unusable, ...) -> allow, never block.
    block, reason = gate.needs_block_for_ancestry(
        ["abc1234"], "/r", "staging", "HEAD", ancestry_resolver=lambda s, t, r: None
    )
    assert block is False
    assert reason == ""


def test_needs_block_for_ancestry_empty_commits_allows():
    block, reason = gate.needs_block_for_ancestry(
        [], "/r", "prod", "origin/main", ancestry_resolver=lambda s, t, r: False
    )
    assert block is False
    assert reason == ""


def test_needs_block_for_ancestry_resolver_exception_degrades_open():
    # A blown-up ancestry resolver is treated as indeterminate (None), not a
    # definitive "not an ancestor" -- consistent with the fail-open contract
    # for a misconfigured/unusable ref check, distinct from needs_block()'s
    # fail-CLOSED contract for plain commit existence.
    def boom(_s, _t, _r):
        raise RuntimeError("resolver blew up")

    block, reason = gate.needs_block_for_ancestry(
        ["abc1234"], "/r", "prod", "origin/main", ancestry_resolver=boom
    )
    assert block is False
    assert reason == ""


def test_needs_block_for_ancestry_first_offender_named_on_mixed_list():
    calls = []

    def resolver(sha, target_ref, repo):
        calls.append(sha)
        return sha != "bad5678"

    block, reason = gate.needs_block_for_ancestry(
        ["good1234", "bad5678", "good9999"],
        "/r",
        "prod",
        "origin/main",
        ancestry_resolver=resolver,
    )
    assert block is True
    assert "bad5678" in reason
    assert calls == ["good1234", "bad5678"]  # stops at the first offender


def test_needs_block_for_ancestry_default_resolver_used_when_none(monkeypatch):
    calls = []

    def fake(sha, target_ref, repo):
        calls.append((sha, target_ref, repo))
        return True

    monkeypatch.setattr(gate, "commit_is_ancestor", fake)
    block, _ = gate.needs_block_for_ancestry(
        ["abc"], "/r", "prod", "origin/main", ancestry_resolver=None
    )
    assert block is False
    assert calls == [("abc", "origin/main", "/r")]


# ===========================================================================
# decide() — the pure top-level decision.
# ===========================================================================


def test_decide_non_bash_never_blocks(make_payload):
    ev = make_payload(tool_name="Task", command=None)
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert detail["reason"] == "not-bash"


def test_decide_bash_non_close_never_blocks(make_payload):
    ev = make_payload(tool_name="Bash", command="git status")
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail["reason"] == "not-issue-close"


def test_decide_close_with_real_sha_allows(make_payload, repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {real_sha}'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert detail["commits"] == [real_sha]


def test_decide_close_with_fake_sha_blocks(make_payload, repo_with_commit):
    repo, _real, _tree = repo_with_commit
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {FAKE_SHA}'",
        cwd=str(repo),
    )
    block, reason, _detail = gate.decide(ev)
    assert block is True
    assert FAKE_SHA in reason


def test_decide_close_with_no_commit_blocks(make_payload, repo_with_commit):
    repo, _real, _tree = repo_with_commit
    ev = make_payload(tool_name="Bash", command="gh issue close 5", cwd=str(repo))
    block, reason, _detail = gate.decide(ev)
    assert block is True
    assert "no resolving commit" in reason


def test_decide_injected_resolver(make_payload):
    ev = make_payload(tool_name="Bash", command="gh issue close 5 --commit abc1234")
    block, _r, _d = gate.decide(ev, resolver=lambda s, r: True)
    assert block is False
    block2, _r2, _d2 = gate.decide(ev, resolver=lambda s, r: False)
    assert block2 is True


def test_decide_detail_carries_repo_and_command(make_payload):
    ev = make_payload(
        tool_name="Bash",
        command="gh issue close 5 --commit abc1234",
        cwd="/my/repo",
    )
    _b, _r, detail = gate.decide(ev, resolver=lambda s, r: True)
    assert detail["repo"] == "/my/repo"
    assert detail["command"] == "gh issue close 5 --commit abc1234"
    assert detail["commits"] == ["abc1234"]


# ===========================================================================
# decide() — deploy-ancestry integration. A close's own text claiming a deploy
# target must have its cited commit(s) verify as a real ancestor of that
# target's ref, on top of the (already-passing) existence check above.
# ===========================================================================


def test_decide_no_deploy_claim_skips_ancestry_check_entirely(make_payload, repo_with_branches):
    # No deploy vocabulary at all -> behaves EXACTLY as before this feature:
    # existence-only. Cite the unmerged commit (would fail any ancestry check)
    # to prove ancestry is never even consulted here.
    repo, prod_branch, _shared, _staging_only, unmerged_sha = repo_with_branches
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {unmerged_sha}'",
        cwd=str(repo),
    )
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail["deploy_claim"] is None


def test_decide_prod_claim_with_ancestor_commit_allows(make_payload, repo_with_branches, monkeypatch):
    repo, prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    monkeypatch.setenv("CSA_PROD_REF", prod_branch)
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {shared_sha}, deployed to prod'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert reason == ""
    assert detail["deploy_claim"] == "prod"
    assert detail["target_ref"] == prod_branch


def test_decide_prod_claim_with_non_ancestor_commit_blocks(make_payload, repo_with_branches, monkeypatch):
    # staging_only_sha never reached prod_branch -- claiming "deployed" (prod)
    # citing it must be BLOCKED, not merely allowed because the sha exists.
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    monkeypatch.setenv("CSA_PROD_REF", prod_branch)
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {staging_only_sha}, deployed to prod'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is True
    assert staging_only_sha in reason
    assert prod_branch in reason
    assert detail["deploy_claim"] == "prod"


def test_decide_staging_claim_with_staging_ancestor_commit_allows(
    make_payload, repo_with_branches, monkeypatch
):
    # CSA_STAGING_REF explicitly configured (staging has no safe default --
    # see target_ref_for_claim); shared_sha IS an ancestor of that ref.
    monkeypatch.setenv("CSA_STAGING_REF", "staging")
    repo, _prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {shared_sha}, on staging'",
        cwd=str(repo),
    )
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail["deploy_claim"] == "staging"
    assert detail["target_ref"] == "staging"


def test_decide_staging_claim_with_unset_staging_ref_degrades_to_no_claim(
    make_payload, repo_with_branches, monkeypatch
):
    # BLOCKER 2 (second half): CSA_STAGING_REF unset -> the staging claim is
    # not actually checkable -> degrades to "no claim detected" (existence-
    # only), NEVER a vacuous always-true check against a HEAD default. The
    # proof is in `detail`: no "target_ref" key at all, and deploy_claim is
    # None -- the ancestry check never ran, it wasn't merely satisfied.
    monkeypatch.delenv("CSA_STAGING_REF", raising=False)
    repo, _prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {shared_sha}, on staging'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert reason == ""
    assert detail["deploy_claim"] is None
    assert "target_ref" not in detail


def test_decide_combined_prod_and_staging_claim_prod_wins_and_is_enforced(
    make_payload, repo_with_branches, monkeypatch
):
    # BLOCKER 2 end-to-end at decide(): both vocabularies present in the same
    # close text ("Deployed to production. Also verified on staging.") -- prod
    # must win the classification AND the ancestry check must actually run
    # against the PROD ref (not be skipped/vacuous), blocking a commit that
    # only ever reached staging.
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    monkeypatch.setenv("CSA_PROD_REF", prod_branch)
    monkeypatch.delenv("CSA_STAGING_REF", raising=False)
    ev = make_payload(
        tool_name="Bash",
        command=(
            f"gh issue close 5 --comment 'Fixes {staging_only_sha}. "
            "Deployed to production. Also verified on staging.'"
        ),
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert detail["deploy_claim"] == "prod"
    assert detail["target_ref"] == prod_branch
    assert block is True
    assert staging_only_sha in reason
    assert prod_branch in reason


def test_decide_staging_claim_distinguished_from_prod_claim(
    make_payload, repo_with_branches, monkeypatch
):
    # staging_only_sha is an ancestor of `staging` but NOT of prod_branch: an
    # "on staging" claim citing it must ALLOW (checked against the staging
    # ref), proving staging and prod claims are checked against DIFFERENT refs
    # rather than the ancestry check silently always using one or the other.
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    monkeypatch.setenv("CSA_PROD_REF", prod_branch)
    monkeypatch.setenv("CSA_STAGING_REF", "staging")

    staging_ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {staging_only_sha}, on staging'",
        cwd=str(repo),
    )
    block, _reason, detail = gate.decide(staging_ev)
    assert block is False
    assert detail["deploy_claim"] == "staging"

    prod_ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 6 --comment 'Fixes in {staging_only_sha}, deployed to prod'",
        cwd=str(repo),
    )
    block2, reason2, detail2 = gate.decide(prod_ev)
    assert block2 is True
    assert staging_only_sha in reason2
    assert detail2["deploy_claim"] == "prod"


def test_decide_prod_claim_missing_ref_convention_degrades_open(
    make_payload, repo_with_branches, monkeypatch
):
    # CSA_PROD_REF pointed at a ref that does not exist in this repo (a repo
    # with no such convention configured) -> indeterminate ancestry -> the
    # close is NOT blocked on ancestry grounds (existence still applies).
    repo, _prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    monkeypatch.setenv("CSA_PROD_REF", "origin/does-not-exist-here")
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {staging_only_sha}, deployed to prod'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert reason == ""
    assert detail["deploy_claim"] == "prod"


def test_decide_ancestry_check_never_runs_when_existence_already_blocks(make_payload, repo_with_branches):
    # A fabricated sha must be blocked by the EXISTING existence guard even
    # when the text also makes a deploy claim -- existence is primary.
    repo, prod_branch, _shared, _staging_only, _unmerged = repo_with_branches
    ev = make_payload(
        tool_name="Bash",
        command=f"gh issue close 5 --comment 'Fixes in {FAKE_SHA}, deployed to prod'",
        cwd=str(repo),
    )
    block, reason, detail = gate.decide(ev)
    assert block is True
    assert "not found in this repo" in reason  # the existence guard's message, not ancestry's
    assert "deploy_claim" not in detail  # never reached the ancestry stage


def test_decide_ancestry_injected_resolver(make_payload):
    ev = make_payload(
        tool_name="Bash",
        command="gh issue close 5 --commit abc1234 --comment 'deployed to prod'",
    )
    block, _r, _d = gate.decide(
        ev, resolver=lambda s, r: True, ancestry_resolver=lambda s, t, r: True
    )
    assert block is False
    block2, _r2, _d2 = gate.decide(
        ev, resolver=lambda s, r: True, ancestry_resolver=lambda s, t, r: False
    )
    assert block2 is True


# ===========================================================================
# main() — thin driver: emit/log, LOG-ONLY vs enforce, master-off, exit 0.
# ===========================================================================


def _run_main(monkeypatch, payload, capsys):
    """Feed `payload` (dict) to main() via stdin; return (rc, stdout)."""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = gate.main()
    out = capsys.readouterr().out
    return rc, out


def test_main_disabled_master_off_does_nothing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    clean_env.setenv("CSA_ENFORCE", "1")  # even with enforce, disable wins
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'in {FAKE_SHA}'"},
        "cwd": str(sandbox.home),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""  # no deny emitted
    assert not sandbox.log_file.exists()  # nothing logged


def test_main_not_close_allows_silently(sandbox, clean_env, monkeypatch, capsys):
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""


def test_main_log_only_when_not_enforcing(sandbox, clean_env, monkeypatch, capsys):
    # Not enforcing -> would-deny is LOGGED but NO deny object emitted (allowed).
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'Fixes {FAKE_SHA}'"},
        "cwd": str(sandbox.home),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""  # LOG-ONLY: no emission
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == gate.HOOK_NAME
    assert rec["decision"] == "would-deny"
    assert FAKE_SHA in rec["reason"]


def test_main_emits_deny_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'Fixes {FAKE_SHA}'"},
        "cwd": str(sandbox.home),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert FAKE_SHA in obj["systemMessage"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "deny"


def test_main_no_commit_close_blocks_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "gh issue close 5"},
        "cwd": str(sandbox.home),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no resolving commit" in obj["systemMessage"]


def test_main_real_sha_close_allowed_when_enforcing(
    sandbox, clean_env, monkeypatch, capsys, repo_with_commit
):
    # Even under enforcement, a close backed by a REAL commit is ALLOWED
    # (no emission, no deny log) — the guard only fires on fabrication.
    repo, real_sha, _tree = repo_with_commit
    clean_env.setenv("CSA_ENFORCE", "1")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'Fixes {real_sha}'"},
        "cwd": str(repo),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""  # allowed
    assert not sandbox.log_file.exists()


def test_main_deploy_claim_non_ancestor_blocks_when_enforcing(
    sandbox, clean_env, monkeypatch, capsys, repo_with_branches
):
    # A "deployed to prod" claim citing a commit that only ever reached
    # staging must be DENIED under enforcement -- the deploy-ancestry guard.
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_PROD_REF", prod_branch)
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {staging_only_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert staging_only_sha in obj["systemMessage"]
    assert prod_branch in obj["systemMessage"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "deny"


def test_main_deploy_claim_ancestor_allowed_when_enforcing(
    sandbox, clean_env, monkeypatch, capsys, repo_with_branches
):
    # Same claim, but citing a commit that genuinely reached prod -> ALLOWED.
    repo, prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_PROD_REF", prod_branch)
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {shared_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_main_deploy_claim_log_only_when_not_enforcing(
    sandbox, clean_env, monkeypatch, capsys, repo_with_branches
):
    # Not enforcing -> would-deny logged only, close still proceeds.
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    clean_env.setenv("CSA_PROD_REF", prod_branch)
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {staging_only_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""  # LOG-ONLY: no emission
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-deny"
    assert staging_only_sha in rec["reason"]


def test_main_deploy_claim_missing_ref_convention_allows_even_when_enforcing(
    sandbox, clean_env, monkeypatch, capsys, repo_with_branches
):
    # CSA_PROD_REF misconfigured/missing -> degrade OPEN even under
    # enforcement; a config gap must never false-block a legitimate close.
    repo, _prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_PROD_REF", "origin/does-not-exist-here")
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {staging_only_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_main_non_bash_allows(sandbox, clean_env, monkeypatch, capsys):
    payload = {"tool_name": "Task", "tool_input": {}}
    rc, out = _run_main(monkeypatch, payload, capsys)
    assert rc == 0
    assert out == ""


def test_main_empty_stdin_allows(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = gate.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


def test_main_garbage_stdin_allows(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("total garbage not json"))
    rc = gate.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


# ===========================================================================
# End-to-end via subprocess — the real script, real stdin, real git resolver.
# This exercises the __main__ path (sys.exit(main())) that unit tests skip.
# ===========================================================================


def _run_script(payload, cwd, env_extra=None):
    env = dict(os.environ)
    env.pop("CSA_DISABLE_HOOKS", None)
    env.pop("CSA_ENFORCE", None)
    if env_extra:
        env.update(env_extra)
    script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gh_issue_close_gate.py",
    )
    proc = subprocess.run(
        ["python3", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd),
        env=env,
    )
    return proc


def test_e2e_fake_sha_blocks_under_enforce(repo_with_commit):
    repo, _real, _tree = repo_with_commit
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'Fixes {FAKE_SHA}'"},
        "cwd": str(repo),
    }
    proc = _run_script(payload, repo, env_extra={"CSA_ENFORCE": "1"})
    assert proc.returncode == 0  # deny is JSON, not exit code
    obj = json.loads(proc.stdout)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_e2e_real_sha_allows_under_enforce(repo_with_commit):
    repo, real_sha, _tree = repo_with_commit
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"gh issue close 5 --comment 'Fixes {real_sha}'"},
        "cwd": str(repo),
    }
    proc = _run_script(payload, repo, env_extra={"CSA_ENFORCE": "1"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # allowed, no emission


def test_e2e_prod_claim_non_ancestor_blocks_under_enforce(repo_with_branches):
    repo, prod_branch, _shared, staging_only_sha, _unmerged = repo_with_branches
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {staging_only_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    proc = _run_script(
        payload, repo, env_extra={"CSA_ENFORCE": "1", "CSA_PROD_REF": prod_branch}
    )
    assert proc.returncode == 0  # deny is JSON, not exit code
    obj = json.loads(proc.stdout)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert staging_only_sha in obj["systemMessage"]


def test_e2e_prod_claim_ancestor_allows_under_enforce(repo_with_branches):
    repo, prod_branch, shared_sha, _staging_only, _unmerged = repo_with_branches
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": f"gh issue close 5 --comment 'Fixes {shared_sha}, deployed to prod'"
        },
        "cwd": str(repo),
    }
    proc = _run_script(
        payload, repo, env_extra={"CSA_ENFORCE": "1", "CSA_PROD_REF": prod_branch}
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # allowed, no emission


# ---------------------------------------------------------------------------
# Sanctioned NOT-PLANNED close path (2026-08-23, #4400). Four adversarial
# cases proven RED without the extension, plus the exemption's happy path.
# ---------------------------------------------------------------------------

_MARKER = "Disposition: stale-superseded — no activity, superseded by newer work"
_DUP_MARKER = "Disposition: duplicate-of #123 — same root cause"


def _np_close(n, extra=""):
    return f"gh issue close {n} --reason \"not planned\" --comment '{_MARKER}' {extra}".strip()


def test_not_planned_single_segment_allows(make_payload):
    ev = make_payload(tool_name="Bash", command=_np_close(7), cwd="/tmp")
    block, reason, detail = gate.decide(ev)
    assert block is False
    assert detail["reason"] == "not-planned-exempt"


def test_not_planned_bare_r_flag_allows(make_payload):
    cmd = f"gh issue close 7 -r \"not planned\" --comment '{_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail["reason"] == "not-planned-exempt"


def test_marker_in_sibling_segment_does_not_clear_other_close(make_payload):
    # Segment 1 has NO marker/reason and cites no commit -> must still BLOCK,
    # even though segment 2 is a fully sanctioned not-planned close.
    cmd = f"gh issue close 101 && {_np_close(102)}"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, reason, _detail = gate.decide(ev)
    assert block is True
    assert "no resolving commit" in reason


def test_marker_plus_deploy_claim_still_blocked(make_payload):
    # Condition (ii): a not-planned close whose own text claims deploy status
    # gets NO exemption -> falls through to the COMMIT guard (which fires
    # first, on zero cited commits) and blocks.
    cmd = (
        'gh issue close 7 --reason "not planned" '
        f"--comment '{_MARKER}. This was deployed to prod anyway.'"
    )
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, reason, _detail = gate.decide(ev)
    assert block is True
    assert "no resolving commit" in reason  # which guard fired is part of the contract


def test_marker_without_reason_flag_still_blocked(make_payload):
    # Condition (iii): the Disposition marker alone, without --reason/-r
    # "not planned", is NOT an exemption.
    cmd = f"gh issue close 7 --comment '{_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, _detail = gate.decide(ev)
    assert block is True


def test_duplicate_of_nonexistent_issue_blocked(make_payload):
    cmd = f"gh issue close 7 --reason \"not planned\" --comment '{_DUP_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, _detail = gate.decide(
        ev, issue_resolver=lambda n, repo: False
    )
    assert block is True


def test_duplicate_of_unresolvable_fails_open_with_note(make_payload):
    cmd = f"gh issue close 7 --reason \"not planned\" --comment '{_DUP_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, detail = gate.decide(
        ev, issue_resolver=lambda n, repo: None
    )
    assert block is False
    assert detail["reason"] == "not-planned-exempt"
    assert any("fail-open" in n for n in detail["notes"])


def test_duplicate_of_existing_issue_allows(make_payload):
    cmd = f"gh issue close 7 --reason \"not planned\" --comment '{_DUP_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, detail = gate.decide(
        ev, issue_resolver=lambda n, repo: True
    )
    assert block is False
    assert detail["reason"] == "not-planned-exempt"


def test_not_planned_with_commit_cited_uses_normal_guards(make_payload, repo_with_commit):
    # Condition (i): citing a commit routes through the ORIGINAL guard —
    # which allows when the sha is real (unchanged behavior, not the exemption).
    repo, real_sha, _tree = repo_with_commit
    cmd = (
        f"gh issue close 7 --reason \"not planned\" "
        f"--comment '{_MARKER}. Fixes in {real_sha}'"
    )
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail.get("reason") != "not-planned-exempt"


def test_reason_words_in_comment_body_do_not_exempt(make_payload):
    # R3-1 regression: quoting the flag inside a --comment body must NOT count
    # as condition (iii) — only a real --reason/-r argv token does.
    cmd = (
        "gh issue close 123 --comment "
        "\"Template: --reason 'not planned' / Disposition: wont-fix - superseded\""
    )
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, reason, detail = gate.decide(ev)
    assert block is True
    assert "no resolving commit" in reason
    assert detail.get("reason") != "not-planned-exempt"


def test_multi_segment_all_exempt_batch_allows(make_payload):
    # The production shape board-steward proposes: an approved batch of
    # sanctioned closes in one command.
    cmd = f"{_np_close(7)} && {_np_close(8)}"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, _reason, detail = gate.decide(ev)
    assert block is False
    assert detail["reason"] == "not-planned-exempt"


def test_reason_completed_with_marker_not_exempt(make_payload):
    # Only the literal "not planned" reason value qualifies — a completed-reason
    # close with a pasted marker must route through the normal guards.
    cmd = f"gh issue close 7 --reason completed --comment '{_MARKER}'"
    ev = make_payload(tool_name="Bash", command=cmd, cwd="/tmp")
    block, reason, _detail = gate.decide(ev)
    assert block is True
    assert "no resolving commit" in reason


def test_e2e_not_planned_exempt_allow_is_logged(tmp_path):
    # R3-3: every use of the sanctioned exemption must land in the enforcement
    # log — it is a bypass of the fabricated-resolution guard, and the log is
    # the only place a reviewer can later ask "how often, and why."
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": _np_close(9)},
        "cwd": str(tmp_path),
    }
    proc = _run_script(payload, tmp_path, env_extra={"HOME": str(tmp_path)})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # allowed, no deny emission
    log_file = tmp_path / ".claude" / ".enforcement" / "log.jsonl"
    assert log_file.exists(), "exempt allow was not logged"
    lines = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    hits = [entry for entry in lines if entry.get("decision") == "not-planned-exempt-allow"]
    assert hits, f"no not-planned-exempt-allow entry in {lines}"
    assert hits[0].get("reason") == "not-planned-exempt"
