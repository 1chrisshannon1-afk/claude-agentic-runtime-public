"""Hermetic tests for hooks/record_review.py.

Ports every behavior of the proven bash source ``~/.claude/scripts/mark_reviewed.sh``
as an explicit vector, then expands: pure-decision coverage for each status, the
idempotency guard, the ledger-writer's mkdir/chmod/failure paths, main()'s
enforced-vs-LOG-ONLY split, the CSA_DISABLE_HOOKS master-OFF, target-resolution
precedence, and the flag->clear cycle that pairs record_review with the
review/task-completion gate.

All tests run against the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir), so the operator's real ~/.claude/.review_state is never touched.
Git is exercised only against throwaway, offline repos created per-test.
"""

from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys

import pytest
import precommit_review_gate as prg
import record_review as rr

# GH #5886 fix-round-4: resolved at COLLECTION time (feeds class-level
# @pytest.mark.parametrize decorators below) via getattr with a safe
# fallback -- a bare `prg._PATHSPEC_ENV_VARS` reference here would raise
# AttributeError and abort collection of this ENTIRE test file when loaded
# against a module that predates this feature (e.g. HEAD's own
# precommit_review_gate.py, used as a RED-verification baseline), masking
# every other test's pass/fail result in that run behind one opaque
# collection error.
_PATHSPEC_ENV_VARS_FOR_TESTS = getattr(prg, "_PATHSPEC_ENV_VARS", ())

# ===========================================================================
# Helpers — throwaway, offline git repos.
# ===========================================================================


def _run_git(repo, *args):
    """Run git in `repo`, offline, with a throwaway identity. Raises on failure."""
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "T"
    env["GIT_AUTHOR_EMAIL"] = "t@example.invalid"
    env["GIT_COMMITTER_NAME"] = "T"
    env["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=15,
        env=env,
    )


def _git_out(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    return proc.stdout.strip()


def _have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


_requires_git = pytest.mark.skipif(not _have_git(), reason="git not available")


@pytest.fixture
def committed_repo(tmp_path):
    """A throwaway git repo with exactly one real commit (so HEAD resolves)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "committed"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    (repo / "f.txt").write_text("hello\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "initial")
    return repo


@pytest.fixture
def empty_repo(tmp_path):
    """A throwaway git repo with NO commits (HEAD does not resolve)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "empty"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    return repo


# ===========================================================================
# PORTED VECTORS — decide(): the mark_reviewed.sh spec, case for case.
# ===========================================================================


@_requires_git
def test_decide_records_fresh_head(sandbox, clean_env, committed_repo):
    """PORT: committed repo with a fresh HEAD -> record, entry == "<root> <sha>"."""
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    d = rr.decide(str(committed_repo))
    assert d.status == rr.STATUS_RECORD
    assert d.head == head
    assert d.repo_root == root
    assert d.entry == f"{root} {head}"
    # message mirrors the bash confirmation with the 12-char short sha.
    assert d.head[:12] in d.message
    assert "recorded review of HEAD" in d.message


@_requires_git
def test_decide_not_a_git_repo(sandbox, clean_env, tmp_path):
    """PORT: a plain dir that is not a git repo -> not-a-repo no-op message."""
    plain = tmp_path / "plain"
    plain.mkdir()
    d = rr.decide(str(plain))
    assert d.status == rr.STATUS_NOT_REPO
    assert "is not a git repo" in d.message
    assert d.entry == ""


def test_decide_not_a_directory(sandbox, clean_env, tmp_path):
    """PORT: target that is not a directory -> not-a-dir no-op message."""
    missing = tmp_path / "does-not-exist"
    d = rr.decide(str(missing))
    assert d.status == rr.STATUS_NOT_DIR
    assert "not a directory" in d.message
    assert d.entry == ""


def test_decide_empty_target_is_not_a_dir(sandbox, clean_env):
    """An empty target string is treated as not-a-dir (guards os.path.isdir(''))."""
    d = rr.decide("")
    assert d.status == rr.STATUS_NOT_DIR


@_requires_git
def test_decide_repo_without_head(sandbox, clean_env, empty_repo):
    """PORT: git repo with no commit yet -> no-head no-op message."""
    d = rr.decide(str(empty_repo))
    assert d.status == rr.STATUS_NO_HEAD
    assert "no HEAD commit yet" in d.message
    assert d.entry == ""
    # repo_root still resolves even though HEAD doesn't.
    assert d.repo_root != ""


@_requires_git
def test_decide_idempotent_when_already_recorded(sandbox, clean_env, committed_repo):
    """PORT: a HEAD already present in last_reviewed -> already (no duplicate)."""
    d1 = rr.decide(str(committed_repo))
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo))
    assert d2.status == rr.STATUS_ALREADY
    assert "already recorded" in d2.message
    assert d2.entry == d1.entry


# ===========================================================================
# OUTCOME-AWARE decide() — RECORD / ALREADY / UPDATE across every outcome
# combination (Part 1 of the churn/review-outcome task).
# ===========================================================================


@_requires_git
def test_decide_record_with_clean_outcome(sandbox, clean_env, committed_repo):
    d = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    assert d.status == rr.STATUS_RECORD
    assert d.outcome == "clean"
    assert " clean ts=" in d.entry  # outcome first, ts appended (#4400)
    assert "clean" in d.message


@_requires_git
def test_decide_record_with_blockers_outcome(sandbox, clean_env, committed_repo):
    d = rr.decide(str(committed_repo), outcome=rr.OUTCOME_BLOCKERS, blockers=3)
    assert d.status == rr.STATUS_RECORD
    assert d.outcome == "blockers:3"
    assert " blockers:3 ts=" in d.entry  # outcome first, ts appended (#4400)
    assert "3 unresolved blocker" in d.message


@_requires_git
def test_decide_record_unspecified_outcome_is_legacy_two_field_line(sandbox, clean_env, committed_repo):
    """No outcome passed at all -> the exact old two-field line, byte-for-byte."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    d = rr.decide(str(committed_repo))
    assert d.status == rr.STATUS_RECORD
    assert d.entry == f"{root} {head}"
    assert d.outcome == ""


@_requires_git
def test_decide_already_same_outcome_twice_is_true_noop(sandbox, clean_env, committed_repo):
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    assert d2.status == rr.STATUS_ALREADY
    assert d2.outcome == "clean"


@_requires_git
def test_decide_unspecified_never_downgrades_a_known_outcome(sandbox, clean_env, committed_repo):
    """A plain, unspecified-outcome call must NOT overwrite an existing KNOWN
    outcome (clean/blockers) with "unknown" — never a silent downgrade."""
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo))  # no outcome passed
    assert d2.status == rr.STATUS_ALREADY
    assert d2.outcome == "clean"  # still clean, not downgraded


@_requires_git
def test_decide_update_from_unknown_to_clean(sandbox, clean_env, committed_repo):
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(f"{root} {head}\n")  # legacy/unspecified line
    d = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    assert d.status == rr.STATUS_UPDATE
    assert d.outcome == "clean"
    assert d.entry.startswith(f"{root} {head} clean ts=")


@_requires_git
def test_decide_update_from_blockers_to_clean(sandbox, clean_env, committed_repo):
    """A re-review after fixes reports clean -> updates the recorded outcome."""
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_BLOCKERS, blockers=2)
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    assert d2.status == rr.STATUS_UPDATE
    assert d2.outcome == "clean"
    assert "updated review outcome" in d2.message


@_requires_git
def test_decide_update_from_clean_to_blockers(sandbox, clean_env, committed_repo):
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN)
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_BLOCKERS, blockers=5)
    assert d2.status == rr.STATUS_UPDATE
    assert d2.outcome == "blockers:5"


@_requires_git
def test_decide_update_different_blocker_counts(sandbox, clean_env, committed_repo):
    """Even the SAME outcome status with a DIFFERENT count is a real update."""
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_BLOCKERS, blockers=2)
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_BLOCKERS, blockers=5)
    assert d2.status == rr.STATUS_UPDATE
    assert d2.outcome == "blockers:5"


# ===========================================================================
# EXPANDED — decide() edge cases.
# ===========================================================================


@_requires_git
def test_decide_resolves_from_subdirectory(sandbox, clean_env, committed_repo):
    """decide() from a nested subdir still records the repo TOPLEVEL, not the subdir."""
    nested = committed_repo / "a" / "b"
    nested.mkdir(parents=True)
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    d = rr.decide(str(nested))
    assert d.status == rr.STATUS_RECORD
    assert d.repo_root == root  # toplevel, not the nested dir


def test_decide_swallows_internal_error(sandbox, clean_env, monkeypatch):
    """decide() degrades to a no-op if an unexpected error escapes isdir()."""

    def boom(_p):
        raise RuntimeError("stat exploded")

    monkeypatch.setattr(rr.os.path, "isdir", boom)
    d = rr.decide("/whatever")
    assert d.status == rr.STATUS_NOT_REPO
    assert "internal error" in d.message


@_requires_git
def test_decide_prefix_plus_space_is_the_outcome_suffix_grammar(sandbox, clean_env, committed_repo):
    """A line that STARTS with the entry + a space is the outcome-suffix grammar
    this module now writes (e.g. "<entry> clean") — NOT a fresh/unrecorded HEAD.
    Even unrecognized trailing text (never written by this module, but tolerated
    on read) still counts as "already recorded" with an unknown outcome, so a
    fresh unspecified call is ALREADY, not a duplicate RECORD.
    """
    d1 = rr.decide(str(committed_repo))
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + " GARBAGE\n")
    d2 = rr.decide(str(committed_repo))
    assert d2.status == rr.STATUS_ALREADY
    assert d2.outcome == "GARBAGE"


@_requires_git
def test_decide_new_item6_fields_are_keyword_only(sandbox, clean_env, committed_repo):
    """FINDING 8 (2026-08-30 review): the 2026-08-30 Item 6 Part B fields
    (tier/tier_declared/reviewer/model/round_/paths/prev/vf) must be
    keyword-only, matching `_entry_suffix`'s own `*`-guarded convention --
    passing `tier` positionally (the first of the new fields, right after
    the pre-existing `item`) must raise TypeError, never silently bind to
    the wrong parameter."""
    with pytest.raises(TypeError):
        rr.decide(str(committed_repo), None, None, None, None, "high")


# ===========================================================================
# _existing_outcome_token / parse_outcome_token / head_review_outcome —
# direct unit coverage of the outcome-aware ledger read.
# ===========================================================================


def test_existing_outcome_token_missing_ledger(sandbox, clean_env):
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r", "x") is None


def test_existing_outcome_token_not_present(sandbox, clean_env):
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/one aaa\n/r/two bbb\n")
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/three", "ccc") is None


def test_existing_outcome_token_bare_legacy_line_is_empty_string(sandbox, clean_env):
    """The OLD two-field "<root> <sha>" shape -> "" (present, no outcome info)."""
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/two bbb\n")
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/two", "bbb") == ""


def test_existing_outcome_token_clean_suffix(sandbox, clean_env):
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/two bbb clean\n")
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/two", "bbb") == "clean"


def test_existing_outcome_token_blockers_suffix(sandbox, clean_env):
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/two bbb blockers:3\n")
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/two", "bbb") == "blockers:3"


def test_existing_outcome_token_last_matching_line_wins(sandbox, clean_env):
    """Duplicate lines for the same repo+head (a legacy/foreign-written ledger)
    -> the LAST one wins, matching decide()'s own idempotency semantics."""
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/two bbb blockers:3\n/r/two bbb clean\n")
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/two", "bbb") == "clean"


def test_existing_outcome_token_swallows_read_error(sandbox, clean_env, monkeypatch):
    """A read failure on the ledger is swallowed -> treated as not-recorded (None)."""
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/r/x sha\n")

    real_open = open

    def boom_open(path, *a, **k):
        if str(path) == str(sandbox.last_reviewed):
            raise OSError("cannot read")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    assert rr._existing_outcome_token(str(sandbox.last_reviewed), "/r/x", "sha") is None


class TestParseOutcomeToken:
    def test_none_is_unknown(self):
        assert rr.parse_outcome_token(None) == (rr.OUTCOME_UNKNOWN, 0)

    def test_empty_string_is_unknown(self):
        assert rr.parse_outcome_token("") == (rr.OUTCOME_UNKNOWN, 0)

    def test_clean(self):
        assert rr.parse_outcome_token("clean") == (rr.OUTCOME_CLEAN, 0)

    def test_blockers_n(self):
        assert rr.parse_outcome_token("blockers:5") == (rr.OUTCOME_BLOCKERS, 5)

    def test_blockers_zero_is_unknown_not_blockers(self):
        """blockers:0 is nonsensical as a "blockers found" token; degrade to
        unknown rather than reporting a zero-count blockers outcome."""
        assert rr.parse_outcome_token("blockers:0") == (rr.OUTCOME_UNKNOWN, 0)

    def test_blockers_malformed_count_is_unknown(self):
        assert rr.parse_outcome_token("blockers:abc") == (rr.OUTCOME_UNKNOWN, 0)

    def test_unrecognized_token_is_unknown(self):
        assert rr.parse_outcome_token("something-else") == (rr.OUTCOME_UNKNOWN, 0)


class TestHeadReviewOutcome:
    def test_never_recorded_is_none(self, sandbox, clean_env):
        assert rr.head_review_outcome(str(sandbox.last_reviewed), "/r", "x") is None

    def test_legacy_line_is_unknown(self, sandbox, clean_env):
        sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
        sandbox.last_reviewed.write_text("/r sha\n")
        assert rr.head_review_outcome(str(sandbox.last_reviewed), "/r", "sha") == (
            rr.OUTCOME_UNKNOWN,
            0,
        )

    def test_clean_line(self, sandbox, clean_env):
        sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
        sandbox.last_reviewed.write_text("/r sha clean\n")
        assert rr.head_review_outcome(str(sandbox.last_reviewed), "/r", "sha") == (
            rr.OUTCOME_CLEAN,
            0,
        )

    def test_blockers_line(self, sandbox, clean_env):
        sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
        sandbox.last_reviewed.write_text("/r sha blockers:2\n")
        assert rr.head_review_outcome(str(sandbox.last_reviewed), "/r", "sha") == (
            rr.OUTCOME_BLOCKERS,
            2,
        )


class TestOutcomeTokenAndPhrase:
    def test_outcome_token_clean(self):
        assert rr._outcome_token(rr.OUTCOME_CLEAN, None) == "clean"

    def test_outcome_token_blockers_with_count(self):
        assert rr._outcome_token(rr.OUTCOME_BLOCKERS, 4) == "blockers:4"

    def test_outcome_token_blockers_missing_count_defaults_to_one(self):
        assert rr._outcome_token(rr.OUTCOME_BLOCKERS, None) == "blockers:1"

    def test_outcome_token_blockers_non_positive_count_defaults_to_one(self):
        assert rr._outcome_token(rr.OUTCOME_BLOCKERS, 0) == "blockers:1"
        assert rr._outcome_token(rr.OUTCOME_BLOCKERS, -3) == "blockers:1"

    def test_outcome_token_none_when_unspecified(self):
        assert rr._outcome_token(None, None) is None

    def test_outcome_token_none_for_unrecognized_outcome(self):
        assert rr._outcome_token("bogus", 3) is None

    def test_outcome_phrase_clean(self):
        assert "clean" in rr._outcome_phrase("clean")

    def test_outcome_phrase_blockers(self):
        assert rr._outcome_phrase("blockers:7") == "7 unresolved blocker(s)"

    def test_outcome_phrase_unknown(self):
        assert rr._outcome_phrase("") == "outcome unknown"


# ===========================================================================
# _append_entry — mkdir -p, chmod 0700, append semantics, failure paths.
# ===========================================================================


def test_append_entry_creates_dir_0700_and_writes(sandbox, clean_env):
    assert not sandbox.review_state_dir.exists()
    ok = rr._append_entry("/repo sha1")
    assert ok is True
    assert sandbox.last_reviewed.read_text() == "/repo sha1\n"
    mode = stat.S_IMODE(os.stat(sandbox.review_state_dir).st_mode)
    assert mode == 0o700


def test_append_entry_appends_not_truncates(sandbox, clean_env):
    rr._append_entry("/repo sha1")
    rr._append_entry("/repo sha2")
    assert sandbox.last_reviewed.read_text() == "/repo sha1\n/repo sha2\n"


def test_append_entry_swallows_mkdir_failure(sandbox, clean_env, monkeypatch):
    def boom(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(rr.os, "makedirs", boom)
    assert rr._append_entry("/repo sha") is False


def test_append_entry_swallows_chmod_failure_still_writes(sandbox, clean_env, monkeypatch):
    """chmod is best-effort: if it fails, the entry is still written (returns True)."""

    def boom(*a, **k):
        raise OSError("chmod denied")

    monkeypatch.setattr(rr.os, "chmod", boom)
    assert rr._append_entry("/repo sha") is True
    assert sandbox.last_reviewed.read_text() == "/repo sha\n"


def test_append_entry_swallows_open_failure(sandbox, clean_env, monkeypatch):
    real_open = open

    def boom_open(path, *a, **k):
        if str(path) == str(sandbox.last_reviewed):
            raise OSError("cannot open")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    assert rr._append_entry("/repo sha") is False


# ===========================================================================
# _update_entry — atomic replace-in-place for a DIFFERENT recorded outcome.
# ===========================================================================


def test_update_entry_creates_dir_0700_and_writes(sandbox, clean_env):
    assert not sandbox.review_state_dir.exists()
    ok = rr._update_entry("/repo", "sha1", "/repo sha1 clean")
    assert ok is True
    assert sandbox.last_reviewed.read_text() == "/repo sha1 clean\n"
    mode = stat.S_IMODE(os.stat(sandbox.review_state_dir).st_mode)
    assert mode == 0o700


def test_update_entry_replaces_only_the_matching_head_preserves_others(sandbox, clean_env):
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/repo shaA\n/repo shaB blockers:2\n/other shaC clean\n")
    ok = rr._update_entry("/repo", "shaB", "/repo shaB clean")
    assert ok is True
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    # shaA and the other repo's line are untouched; shaB's line is replaced and
    # moved to the end (append-updated semantics).
    assert lines == ["/repo shaA", "/other shaC clean", "/repo shaB clean"]


def test_update_entry_on_empty_ledger_just_writes_the_new_line(sandbox, clean_env):
    ok = rr._update_entry("/repo", "sha1", "/repo sha1 clean")
    assert ok is True
    assert sandbox.last_reviewed.read_text() == "/repo sha1 clean\n"


def test_update_entry_swallows_mkdir_failure(sandbox, clean_env, monkeypatch):
    def boom(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(rr.os, "makedirs", boom)
    assert rr._update_entry("/repo", "sha", "/repo sha clean") is False


def test_update_entry_swallows_chmod_failure_still_writes(sandbox, clean_env, monkeypatch):
    def boom(*a, **k):
        raise OSError("chmod denied")

    monkeypatch.setattr(rr.os, "chmod", boom)
    assert rr._update_entry("/repo", "sha", "/repo sha clean") is True
    assert sandbox.last_reviewed.read_text() == "/repo sha clean\n"


def test_update_entry_swallows_write_failure_and_cleans_tmp(sandbox, clean_env, monkeypatch):
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    real_open = open

    def boom_open(path, *a, **k):
        if str(path).startswith(str(sandbox.last_reviewed) + ".tmp"):
            raise OSError("disk full")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    assert rr._update_entry("/repo", "sha", "/repo sha clean") is False
    # No stray tmp files left behind.
    assert list(sandbox.review_state_dir.glob("*.tmp.*")) == []


# ===========================================================================
# REGRESSION 5 — _update_entry's read-then-replace and _append_entry's write
# are BOTH now serialized on the SAME admission_lock, so a concurrent
# session's write can never land inside the other's critical section and be
# silently lost. Mirrors agent_budget's own admission_lock contention tests
# (a nested acquisition on the SAME dir fails open -> False).
# ===========================================================================


def test_update_entry_serializes_on_the_same_lock_file_claims_uses(sandbox, clean_env, monkeypatch):
    # A concurrent holder of REVIEW_STATE_DIR's admission lock (mirrors what
    # a real concurrent _append_entry/_update_entry call would hold while
    # inside its own critical section) makes _update_entry fail CLOSED
    # (skip, return False) rather than race unprotected against it.
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")  # keep the nested wait fast
    with rr.ab.admission_lock(str(sandbox.review_state_dir), timeout_s=0.5) as held:
        assert held is True
        assert rr._update_entry("/repo", "sha1", "/repo sha1 clean") is False
    # Nothing was written while contended.
    assert not sandbox.last_reviewed.exists()
    # Lock released -> a subsequent call succeeds normally.
    assert rr._update_entry("/repo", "sha1", "/repo sha1 clean") is True
    assert sandbox.last_reviewed.read_text() == "/repo sha1 clean\n"


def test_append_entry_serializes_on_the_same_lock_file_claims_uses(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    with rr.ab.admission_lock(str(sandbox.review_state_dir), timeout_s=0.5) as held:
        assert held is True
        assert rr._append_entry("/repo sha1") is False
    assert not sandbox.last_reviewed.exists()
    assert rr._append_entry("/repo sha1") is True
    assert sandbox.last_reviewed.read_text() == "/repo sha1\n"


def test_update_entry_cannot_lose_a_concurrent_append_landing_mid_rmw(sandbox, clean_env, monkeypatch):
    # The EXACT race REGRESSION 5 describes, reproduced deterministically: a
    # concurrent _append_entry is driven from INSIDE _update_entry's own
    # locked critical section (simulating "lands between the read and the
    # replace") by monkeypatching os.replace to run it first. Before the fix
    # (no lock, or _append_entry not sharing it) this landed on the
    # about-to-be-discarded old inode and was lost; now _append_entry blocks
    # on the SAME lock until _update_entry's os.replace has actually run.
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("/repo shaA\n")
    real_replace = rr.os.replace
    appended = {}

    def spy_replace(src, dst):
        # We're still INSIDE _update_entry's lock here. A concurrent
        # _append_entry attempted right now must fail closed (lock held),
        # never interleave with this replace.
        appended["result"] = rr._append_entry("/repo shaB")
        real_replace(src, dst)

    monkeypatch.setattr(rr.os, "replace", spy_replace)
    ok = rr._update_entry("/repo", "shaA", "/repo shaA clean")
    assert ok is True
    assert appended["result"] is False  # the concurrent append was shut out, not lost silently
    # The ledger reflects ONLY the update; nothing was silently dropped
    # in a half-applied state, and a retried append now succeeds cleanly:
    assert sandbox.last_reviewed.read_text() == "/repo shaA clean\n"
    assert rr._append_entry("/repo shaB") is True
    assert sandbox.last_reviewed.read_text() == "/repo shaA clean\n/repo shaB\n"


def test_update_entry_fails_open_message_logged_as_update_failed(sandbox, clean_env, committed_repo, monkeypatch):
    # main()'s existing "update-failed" log path (already covered for a
    # generic _update_entry failure) now also covers the LOCK-CONTENDED
    # failure mode specifically -- prove main() surfaces it the same way.
    monkeypatch.setenv("CSA_ENFORCE", "1")
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    # Seed a known outcome first (a real, unlocked write).
    seed_payload = {"cwd": str(committed_repo), "blockers": 1}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(seed_payload)))
    assert rr.main(["record_review.py"]) == 0
    assert "blockers:1" in sandbox.last_reviewed.read_text()

    # Now contend the lock and attempt a DIFFERENT (clean) outcome -> STATUS_UPDATE.
    with rr.ab.admission_lock(str(sandbox.review_state_dir), timeout_s=0.5):
        update_payload = {"cwd": str(committed_repo), "clean": True}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(update_payload)))
        rc = rr.main(["record_review.py"])
    assert rc == 0
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "update-failed"
    # The ledger still holds the ORIGINAL outcome -- the contended update
    # never silently clobbered it.
    assert "blockers:1" in sandbox.last_reviewed.read_text()


# ===========================================================================
# Outcome resolution — _outcome_from_argv / _outcome_from_event / _resolve_outcome.
# ===========================================================================


class TestOutcomeFromArgv:
    def test_no_flags_is_unspecified(self):
        assert rr._outcome_from_argv([]) == (None, None)
        assert rr._outcome_from_argv(["/some/dir"]) == (None, None)

    def test_clean_flag(self):
        assert rr._outcome_from_argv(["--clean"]) == (rr.OUTCOME_CLEAN, None)

    def test_blockers_space_form(self):
        assert rr._outcome_from_argv(["--blockers", "4"]) == (rr.OUTCOME_BLOCKERS, 4)

    def test_blockers_equals_form(self):
        assert rr._outcome_from_argv(["--blockers=4"]) == (rr.OUTCOME_BLOCKERS, 4)

    def test_blockers_zero_is_clean(self):
        assert rr._outcome_from_argv(["--blockers", "0"]) == (rr.OUTCOME_CLEAN, 0)

    def test_blockers_negative_is_clean(self):
        assert rr._outcome_from_argv(["--blockers", "-1"]) == (rr.OUTCOME_CLEAN, -1)

    def test_blockers_malformed_value_ignored(self):
        assert rr._outcome_from_argv(["--blockers", "not-a-number"]) == (None, None)

    def test_blockers_missing_value_ignored(self):
        assert rr._outcome_from_argv(["--blockers"]) == (None, None)

    def test_flags_interleaved_with_a_positional_dir(self):
        assert rr._outcome_from_argv(["/some/dir", "--clean"]) == (rr.OUTCOME_CLEAN, None)
        assert rr._outcome_from_argv(["--blockers", "2", "/some/dir"]) == (rr.OUTCOME_BLOCKERS, 2)

    def test_last_flag_wins_when_both_present(self):
        assert rr._outcome_from_argv(["--clean", "--blockers", "3"]) == (rr.OUTCOME_BLOCKERS, 3)


class TestOutcomeFromEvent:
    def test_no_fields(self):
        assert rr._outcome_from_event({}) == (None, None)

    def test_clean_true(self):
        assert rr._outcome_from_event({"clean": True}) == (rr.OUTCOME_CLEAN, None)

    def test_clean_false_is_ignored(self):
        assert rr._outcome_from_event({"clean": False}) == (None, None)

    def test_blockers_field(self):
        assert rr._outcome_from_event({"blockers": 3}) == (rr.OUTCOME_BLOCKERS, 3)

    def test_blockers_zero_is_clean(self):
        assert rr._outcome_from_event({"blockers": 0}) == (rr.OUTCOME_CLEAN, 0)

    def test_blockers_non_numeric_swallowed(self):
        assert rr._outcome_from_event({"blockers": "not-a-number"}) == (None, None)

    def test_get_raising_degrades_to_unspecified(self):
        class Boom:
            def get(self, *a, **k):
                raise RuntimeError("no get")

        assert rr._outcome_from_event(Boom()) == (None, None)


class TestResolveOutcome:
    def test_cli_wins_over_event(self):
        argv = ["record_review.py", "--clean"]
        ev = {"blockers": 5}
        assert rr._resolve_outcome(argv, ev) == (rr.OUTCOME_CLEAN, None)

    def test_falls_back_to_event_when_cli_has_no_outcome(self):
        argv = ["record_review.py", "/some/dir"]
        ev = {"blockers": 2}
        assert rr._resolve_outcome(argv, ev) == (rr.OUTCOME_BLOCKERS, 2)

    def test_neither_present_is_unspecified(self):
        assert rr._resolve_outcome(["record_review.py"], {}) == (None, None)


# ===========================================================================
# _positional_target — outcome-flag-tolerant positional-dir resolution.
# ===========================================================================


class TestPositionalTarget:
    def test_plain_dir(self):
        assert rr._positional_target(["record_review.py", "/x"]) == "/x"

    def test_no_args_is_none(self):
        assert rr._positional_target(["record_review.py"]) is None

    def test_empty_string_arg_is_not_positional(self):
        assert rr._positional_target(["record_review.py", ""]) is None

    def test_skips_clean_flag(self):
        assert rr._positional_target(["record_review.py", "--clean", "/x"]) == "/x"

    def test_skips_blockers_space_form(self):
        assert rr._positional_target(["record_review.py", "--blockers", "2", "/x"]) == "/x"

    def test_skips_blockers_equals_form(self):
        assert rr._positional_target(["record_review.py", "--blockers=2", "/x"]) == "/x"

    def test_dir_before_flags(self):
        assert rr._positional_target(["record_review.py", "/x", "--clean"]) == "/x"

    def test_only_flags_no_dir_is_none(self):
        assert rr._positional_target(["record_review.py", "--clean", "--blockers", "2"]) is None


# ===========================================================================
# _target_from_event — precedence: explicit CLI arg over event cwd.
# ===========================================================================


def test_target_prefers_cli_arg(sandbox, clean_env):
    ev = {"cwd": "/from/event"}
    assert rr._target_from_event(ev, ["record_review.py", "/from/arg"]) == "/from/arg"


def test_target_falls_back_to_event_cwd(sandbox, clean_env):
    ev = {"cwd": "/from/event"}
    assert rr._target_from_event(ev, ["record_review.py"]) == "/from/event"


def test_target_event_project_dir(sandbox, clean_env):
    ev = {"project_dir": "/proj"}
    assert rr._target_from_event(ev, ["record_review.py"]) == "/proj"


def test_target_no_arg_no_event_uses_getcwd(sandbox, clean_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert rr._target_from_event({}, ["record_review.py"]) == os.getcwd()


def test_target_empty_arg_ignored(sandbox, clean_env):
    ev = {"cwd": "/from/event"}
    # An empty-string argv[1] must NOT win over the event cwd.
    assert rr._target_from_event(ev, ["record_review.py", ""]) == "/from/event"


# ===========================================================================
# main() — enforced vs LOG-ONLY, master-OFF, informational no-ops, exit 0.
# ===========================================================================


def _feed_stdin(monkeypatch, ev):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(ev)))


def _last_log(sandbox):
    lines = sandbox.log_file.read_text().strip().splitlines()
    return json.loads(lines[-1])


@_requires_git
def test_main_enforcing_writes_ledger(sandbox, clean_env, committed_repo, monkeypatch, capsys):
    """enforcing ON -> main() writes the "<root> <sha>" line and logs 'recorded'."""
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    assert sandbox.last_reviewed.read_text() == f"{root} {head}\n"
    rec = _last_log(sandbox)
    assert rec["hook"] == "record_review"
    assert rec["decision"] == "recorded"
    assert rec["head"] == head
    # the confirmation line went to stdout for the human.
    assert "recorded review of HEAD" in capsys.readouterr().out


@_requires_git
def test_main_log_only_when_not_enforcing(sandbox, clean_env, committed_repo, monkeypatch, capsys):
    """enforcing OFF -> LOG-ONLY: the ledger is NOT written; decision is would-record.

    The caller is told plainly that nothing was recorded (stderr line + non-zero
    exit), and is NEVER shown the "recorded review of HEAD" confirmation: printing
    that while the commit gate keeps denying left a stranger unable to tell why."""
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py"])
    assert rc == 1
    assert not sandbox.last_reviewed.exists()
    rec = _last_log(sandbox)
    assert rec["decision"] == "would-record"
    assert rec["enforce"] is False
    captured = capsys.readouterr()
    assert (
        "NOT recorded (log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"
        in captured.err
    )
    assert "recorded review of HEAD" not in captured.out
    assert "recorded review of HEAD" not in captured.err


@_requires_git
def test_main_log_only_refusal_is_recoverable_by_enabling_enforcement(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """Pair of the log-only refusal above: the SAME call, once enforcement is on, records
    the review, exits 0, prints the confirmation on stdout and nothing on stderr."""
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    assert rr.main(["record_review.py", "--clean"]) == 1
    assert not sandbox.last_reviewed.exists()
    capsys.readouterr()

    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py", "--clean"])
    captured = capsys.readouterr()
    assert rc == 0
    assert " clean ts=" in sandbox.last_reviewed.read_text().strip()
    assert "recorded review of HEAD" in captured.out
    assert "NOT recorded" not in captured.err
    assert "NOT recorded" not in captured.out


@_requires_git
def test_cli_log_only_record_exits_nonzero_with_stderr_message(tmp_path, committed_repo):
    """End to end through the real entry point (`sys.exit(main())`): with no enforcement
    marker anywhere, the process exit status is non-zero and stderr says why."""
    home = tmp_path / "cli_home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("CSA_")}
    env["HOME"] = str(home)
    proc = subprocess.run(
        [sys.executable, rr.__file__, str(committed_repo), "--clean"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 1, proc.stderr
    assert (
        "NOT recorded (log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"
        in proc.stderr
    )
    assert "recorded review of HEAD" not in proc.stdout
    assert not (home / ".claude" / ".review_state" / "last_reviewed").exists()


@_requires_git
def test_main_master_off_is_total_noop(sandbox, clean_env, committed_repo, monkeypatch, capsys):
    """CSA_DISABLE_HOOKS=1 -> no write, no log, no stdout, exit 0."""
    clean_env.setenv("CSA_ENFORCE", "1")  # would otherwise write
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")  # master OFF wins
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert not sandbox.log_file.exists()
    assert capsys.readouterr().out == ""


@_requires_git
def test_main_idempotent_already_logs_already(sandbox, clean_env, committed_repo, monkeypatch):
    """A second enforced run for the same HEAD does not duplicate; logs 'already'."""
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rr.main(["record_review.py"])
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rr.main(["record_review.py"])
    # Exactly ONE ledger line despite two runs.
    assert len(sandbox.last_reviewed.read_text().strip().splitlines()) == 1
    assert _last_log(sandbox)["decision"] == "already"


@_requires_git
def test_main_log_only_already_recorded_head_exits_zero(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """LOG-ONLY with a HEAD already on record with the SAME outcome: no requested write was
    skipped (there is nothing to write), so the exit stays 0, the existing 'already recorded'
    line is printed, and no 'NOT recorded' hint appears. Guards against an over-broad
    'exit 1 whenever enforcement is off'."""
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    assert rr.main(["record_review.py", "--clean"]) == 0
    before = sandbox.last_reviewed.read_text()
    clean_env.delenv("CSA_ENFORCE", raising=False)
    capsys.readouterr()

    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py", "--clean"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "already recorded as reviewed" in captured.out
    assert "NOT recorded" not in captured.out + captured.err
    assert sandbox.last_reviewed.read_text() == before
    rec = _last_log(sandbox)
    assert rec["decision"] == "already"
    assert rec["enforce"] is False


@_requires_git
def test_main_not_a_repo_logs_status(sandbox, clean_env, tmp_path, monkeypatch, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    _feed_stdin(monkeypatch, {"cwd": str(plain)})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == rr.STATUS_NOT_REPO
    assert "is not a git repo" in capsys.readouterr().out


@_requires_git
def test_main_no_head_logs_status(sandbox, clean_env, empty_repo, monkeypatch):
    _feed_stdin(monkeypatch, {"cwd": str(empty_repo)})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == rr.STATUS_NO_HEAD


def test_main_not_a_dir_logs_status(sandbox, clean_env, tmp_path, monkeypatch):
    _feed_stdin(monkeypatch, {"cwd": str(tmp_path / "nope")})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == rr.STATUS_NOT_DIR


@_requires_git
def test_main_record_write_failure_logs_record_failed(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """If enforcing and the ledger write fails, main() logs 'record-failed'."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr(rr, "_append_entry", lambda entry: False)
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "record-failed"


@_requires_git
def test_main_enforced_lock_failure_message_is_unchanged(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """The ENFORCED branch is untouched by the log-only message fix: a lock failure still
    prints its own 'NOT recorded -- the ledger lock was unavailable' line on stdout and exits 0,
    and carries no log-only hint."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr(rr, "_append_entry", lambda entry: False)
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "NOT recorded — the ledger lock was unavailable" in captured.out
    assert "log-only mode" not in captured.out + captured.err


@_requires_git
def test_main_enforcing_records_clean_via_cli_flag(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py", "--clean"])
    assert rc == 0
    assert " clean ts=" in sandbox.last_reviewed.read_text().strip()
    assert _last_log(sandbox)["outcome"] == "clean"


@_requires_git
def test_main_enforcing_records_blockers_via_event_payload(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "blockers": 4})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert " blockers:4 ts=" in sandbox.last_reviewed.read_text().strip()
    assert _last_log(sandbox)["outcome"] == "blockers:4"


@_requires_git
def test_main_log_only_would_record_carries_outcome(sandbox, clean_env, committed_repo, monkeypatch):
    """Even LOG-ONLY (not enforcing), the resolved outcome shows up in the log
    line — the outcome is part of the decision, not an enforcement-time detail.
    (The process still exits non-zero: nothing was recorded.)"""
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rc = rr.main(["record_review.py", "--blockers", "2"])
    assert rc == 1
    assert not sandbox.last_reviewed.exists()  # LOG-ONLY: no write
    rec = _last_log(sandbox)
    assert rec["decision"] == "would-record"
    assert rec["outcome"] == "blockers:2"


@_requires_git
def test_main_enforcing_updates_outcome_on_re_review(sandbox, clean_env, committed_repo, monkeypatch):
    """A re-review reporting a DIFFERENT outcome for the SAME HEAD updates the
    ledger line in place (STATUS_UPDATE), logging 'updated'."""
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "blockers": 2})
    rr.main(["record_review.py"])
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "clean": True})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # updated in place, not duplicated
    assert " clean ts=" in lines[0]
    assert _last_log(sandbox)["decision"] == "updated"
    assert _last_log(sandbox)["outcome"] == "clean"


@_requires_git
def test_main_log_only_update_is_would_update(sandbox, clean_env, committed_repo, monkeypatch, capsys):
    """LOG-ONLY: an outcome change for an already-recorded HEAD logs
    'would-update', does NOT touch the ledger, and tells the caller on stderr
    (non-zero exit) that nothing was updated."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "blockers": 2})
    rr.main(["record_review.py"])
    clean_env.delenv("CSA_ENFORCE", raising=False)
    capsys.readouterr()
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "clean": True})
    rc = rr.main(["record_review.py"])
    captured = capsys.readouterr()
    assert rc == 1
    assert (
        "NOT updated (log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"
        in captured.err
    )
    assert "updated review outcome" not in captured.out
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # untouched by the log-only update
    assert lines[0].startswith(f"{root} {head} blockers:2")
    assert _last_log(sandbox)["decision"] == "would-update"
    assert _last_log(sandbox)["outcome"] == "clean"


@_requires_git
def test_main_update_write_failure_logs_update_failed(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "blockers": 2})
    rr.main(["record_review.py"])
    monkeypatch.setattr(rr, "_update_entry", lambda *a, **k: False)
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "clean": True})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "update-failed"


@_requires_git
def test_main_idempotent_same_outcome_logs_already_with_outcome(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "clean": True})
    rr.main(["record_review.py"])
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo), "clean": True})
    rc = rr.main(["record_review.py"])
    assert rc == 0
    assert len(sandbox.last_reviewed.read_text().strip().splitlines()) == 1
    rec = _last_log(sandbox)
    assert rec["decision"] == "already"
    assert rec["outcome"] == "clean"


@_requires_git
def test_main_cli_arg_overrides_event_cwd(sandbox, clean_env, committed_repo, monkeypatch):
    """The explicit CLI dir arg wins over the payload cwd."""
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"cwd": "/nonexistent/event/dir"})
    rc = rr.main(["record_review.py", str(committed_repo)])
    assert rc == 0
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    assert head in sandbox.last_reviewed.read_text()


def test_main_swallows_read_event_error(sandbox, clean_env, monkeypatch, tmp_path):
    """read_event raising is swallowed; main() proceeds with getcwd() and exits 0."""

    def boom():
        raise RuntimeError("stdin exploded")

    monkeypatch.setattr(rr._lib, "read_event", boom)
    monkeypatch.chdir(tmp_path)  # a non-repo cwd -> clean no-op
    rc = rr.main(["record_review.py"])
    assert rc == 0


def test_main_never_emits_deny_or_block(sandbox, clean_env, tmp_path, monkeypatch, capsys):
    """Recording is not a gate: stdout must never be a PreToolUse deny / Stop block."""
    _feed_stdin(monkeypatch, {"cwd": str(tmp_path)})
    rr.main(["record_review.py"])
    out = capsys.readouterr().out.strip()
    # Whatever prints must NOT be a hook-protocol JSON decision object.
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            obj = json.loads(line)
            assert "permissionDecision" not in obj
            assert obj.get("decision") != "block"


# ===========================================================================
# THE PAIRING — flag -> clear cycle with the review / task-completion gate.
#
# The gate matches an unreviewed HEAD with  grep -Fq -- "<repo_root> <head>"
# against last_reviewed. record_review writes exactly that line. This test
# reproduces the whole cycle WITHOUT depending on the gate module existing yet,
# by modeling the gate's exact predicate:
#     would_block(repo, head) := "<repo> <head>" NOT present in last_reviewed
# ===========================================================================


def _gate_would_block(repo_root, head):
    """Model the review/task-completion gate's block predicate.

    The gate blocks (warns) iff repo_root+head has NO entry at all in
    last_reviewed — mirrors task_completion_gate.head_reviewed's substring
    match / record_review's own outcome-aware presence check.
    """
    return rr._existing_outcome_token(str(rr._lib.LAST_REVIEWED), repo_root, head) is None


@_requires_git
def test_pairing_commit_then_gate_blocks_then_record_clears(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Full cycle: commit -> gate would-block -> record_review -> gate clears."""
    clean_env.setenv("CSA_ENFORCE", "1")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    head = _git_out(committed_repo, "rev-parse", "HEAD")

    # 1) Fresh commit, nothing recorded yet: the gate WOULD block.
    assert _gate_would_block(root, head) is True

    # 2) record_review runs (enforced) and writes the ledger line.
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    assert rr.main(["record_review.py"]) == 0

    # 3) The gate now CLEARS — the exact line it greps for is present.
    assert _gate_would_block(root, head) is False
    assert sandbox.last_reviewed.read_text() == f"{root} {head}\n"


@_requires_git
def test_pairing_new_commit_reblocks_until_rerecorded(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A NEW commit after recording moves HEAD, so the gate blocks again until re-recorded."""
    clean_env.setenv("CSA_ENFORCE", "1")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")

    # Record the first HEAD.
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rr.main(["record_review.py"])
    head1 = _git_out(committed_repo, "rev-parse", "HEAD")
    assert _gate_would_block(root, head1) is False

    # New commit -> HEAD advances; the OLD record no longer covers it.
    (committed_repo / "g.txt").write_text("more\n")
    _run_git(committed_repo, "add", "g.txt")
    _run_git(committed_repo, "commit", "-q", "-m", "second")
    head2 = _git_out(committed_repo, "rev-parse", "HEAD")
    assert head2 != head1
    assert _gate_would_block(root, head2) is True  # blocked again

    # Re-record clears the new HEAD.
    _feed_stdin(monkeypatch, {"cwd": str(committed_repo)})
    rr.main(["record_review.py"])
    assert _gate_would_block(root, head2) is False


# ===========================================================================
# _git plumbing helper — direct failure-path coverage (no network).
# ===========================================================================


def test_git_helper_returns_empty_on_nonzero(sandbox, clean_env, tmp_path):
    """A non-repo dir -> rev-parse fails -> "" (never raises)."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert rr._git(str(plain), "rev-parse", "--show-toplevel") == ""


def test_git_helper_swallows_subprocess_exception(sandbox, clean_env, monkeypatch):
    """subprocess.run raising (e.g. git missing) -> "" (never raises)."""

    def boom(*a, **k):
        raise FileNotFoundError("no git")

    monkeypatch.setattr(rr.subprocess, "run", boom)
    assert rr._git("/x", "rev-parse", "HEAD") == ""


# ---------------------------------------------------------------------------
# 2026-08-23 (#4400): appended telemetry fields (ts= / item=) — backward
# compatibility is the load-bearing contract (this ledger feeds gate 3b).
# ---------------------------------------------------------------------------


def test_legacy_bare_and_outcome_lines_still_resolve(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/a abc123\n/repo/b def456 clean\n/repo/c 789abc blockers:2\n"
    )
    assert rr.head_review_outcome(str(ledger), "/repo/a", "abc123") == (
        rr.OUTCOME_UNKNOWN,
        0,
    )
    assert rr.head_review_outcome(str(ledger), "/repo/b", "def456") == (
        rr.OUTCOME_CLEAN,
        0,
    )
    assert rr.head_review_outcome(str(ledger), "/repo/c", "789abc") == (
        rr.OUTCOME_BLOCKERS,
        2,
    )


def test_new_suffixed_lines_parse_outcome_from_first_token(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/d 111aaa clean ts=2026-08-23T12:00:00Z item=gh-4400\n"
        "/repo/e 222bbb blockers:3 ts=2026-08-23T12:01:00Z\n"
    )
    assert rr.head_review_outcome(str(ledger), "/repo/d", "111aaa") == (
        rr.OUTCOME_CLEAN,
        0,
    )
    assert rr.head_review_outcome(str(ledger), "/repo/e", "222bbb") == (
        rr.OUTCOME_BLOCKERS,
        3,
    )


def test_entry_suffix_shape_and_item_sanitization():
    s = rr._entry_suffix("gh #4400/board sweep!")
    assert s.startswith(" ts=")
    assert " item=" in s
    item = s.split(" item=", 1)[1]
    assert " " not in item and "!" not in item


def test_entry_suffix_reviewer_does_not_truncate_long_compound_identity():
    # FINDING 7 (minor, 2026-08-30 review): a real compound identity can run
    # up to 242 chars (80 type + "#" + 80 agent_id + "#" + 80 tool_use_id) --
    # the general _safe_field default of maxlen=80 would silently truncate
    # straight through it, corrupting the identity with no error at all.
    long_type = "t" * 80
    long_agent_id = "a" * 80
    long_tool_use_id = "u" * 80
    composed = rr.compose_reviewer_field(long_type, long_agent_id, long_tool_use_id)
    assert len(composed) == rr._MAX_REVIEWER_FIELD_LEN == 242

    s = rr._entry_suffix(reviewer=composed)
    assert f" reviewer={composed}" in s  # NOT truncated

    # And the un-truncated value still round-trips to the full identity.
    parsed = rr.parse_reviewer_value(composed)
    assert parsed == {
        "type": long_type, "agent_id": long_agent_id, "tool_use_id": long_tool_use_id,
    }


@_requires_git
def test_same_outcome_reissue_is_idempotent_despite_differing_ts(sandbox, clean_env, committed_repo):
    d1 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN, item="x")
    assert d1.status == rr.STATUS_RECORD
    assert " ts=" in d1.entry and " item=x" in d1.entry
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(d1.entry + "\n")
    d2 = rr.decide(str(committed_repo), outcome=rr.OUTCOME_CLEAN, item="x")
    assert d2.status == rr.STATUS_ALREADY
    assert d2.outcome == "clean"


def test_whitespace_only_suffix_degrades_to_unknown_never_raises(tmp_path):
    # R3-2 regression: a malformed line with a whitespace-only suffix must map
    # to UNKNOWN, never raise (a raise here silently fail-opens gate 3b).
    assert rr.parse_outcome_token("   ") == (rr.OUTCOME_UNKNOWN, 0)
    ledger = tmp_path / "last_reviewed"
    ledger.write_text("/repo/w abc999  \n")  # trailing spaces -> suffix ' '
    assert rr.head_review_outcome(str(ledger), "/repo/w", "abc999") == (
        rr.OUTCOME_UNKNOWN,
        0,
    )


# ===========================================================================
# 2026-08-30 (gate-optimization plan, Item 6) — PART A: the root-cause
# argv-parsing fix. _positional_target now LOUDLY rejects both failure
# shapes (an unrecognized --flag, an implausible positional) instead of
# silently resolving to a bogus "target directory" that decide() then
# quietly no-ops on -- the exact shape already happening 114 times in the
# live enforcement log (106 --help, 3 other unrecognized flags, 5
# sha/path-shaped mistargets).
# ===========================================================================


class TestArgvErrorUnrecognizedFlags:
    def test_unrecognized_flag_space_form_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", "--sha", "abc123"])

    def test_unrecognized_flag_equals_form_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", "--repo=/x"])

    def test_help_flag_is_unrecognized_and_raises(self):
        """--help is NOT a recognized flag today -- 106/114 of the live
        enforcement log's silent no-ops were exactly this shape."""
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", "--help"])

    def test_unrecognized_flag_raised_even_when_a_real_positional_appears_earlier(self):
        """The unrecognized-flag scan covers the WHOLE argv, not just up to
        the first positional -- a bad flag anywhere in the call is a real
        argv-shape mistake regardless of where it sits."""
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", "--skip", "/real/dir"])

    def test_error_message_names_the_likely_intended_flags(self):
        with pytest.raises(rr.ArgvError, match=r"--tier"):
            rr._positional_target(["record_review.py", "--sha"])


class TestArgvErrorImplausiblePositional:
    def test_bare_sha_no_slash_raises(self):
        """A 40-hex sha with no path separator -- one of the 5 live
        sha-shaped mistargets the enforcement log recorded."""
        with pytest.raises(rr.ArgvError):
            rr._positional_target(
                ["record_review.py", "a6b349a4d55560b1b47472f515076e78efa1732a"]
            )

    def test_short_sha_prefix_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", "04bbab8eb"])

    def test_pasted_ledger_line_with_spaces_raises(self):
        """The exact live shape found in the enforcement log: an entire
        "<repo> <sha> blockers:0" ledger line pasted into one argv token.
        It DOES contain a "/" in its first path segment, but the embedded
        raw spaces are the real signal this is not a genuine path."""
        candidate = (
            "/Users/x/Desktop/ExampleApp "
            "199ea101b0a065dc1027c6e4ba66a34f0ab0c2c6 blockers:0"
        )
        with pytest.raises(rr.ArgvError):
            rr._positional_target(["record_review.py", candidate])

    def test_real_existing_directory_is_plausible(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        assert rr._positional_target(["record_review.py", str(real_dir)]) == str(real_dir)

    def test_absolute_not_yet_created_path_is_plausible(self, tmp_path):
        """Contains a "/" -- shaped like a real path even though nothing is
        there yet; decide() itself still performs the authoritative
        os.path.isdir() check right after, this only gates the LOUD
        rejection path."""
        not_yet = str(tmp_path / "does-not-exist-yet")
        assert rr._positional_target(["record_review.py", not_yet]) == not_yet

    def test_dot_and_dotdot_are_plausible(self):
        assert rr._positional_target(["record_review.py", "."]) == "."
        assert rr._positional_target(["record_review.py", ".."]) == ".."


class TestPathsVariadicSwallowStopsAtRecognizedFlag:
    """`--paths` must stop swallowing at ANY recognized flag, including the
    NEW ones added by Part B -- not just the pre-existing --clean/--blockers."""

    def test_stops_at_new_flag_tier(self):
        argv = ["record_review.py", "--paths", "a.py", "b.py", "--tier", "high", "/x"]
        assert rr._paths_from_argv(argv) == ["a.py", "b.py"]
        assert rr._positional_target(argv) == "/x"

    def test_stops_at_new_flag_reviewer_and_model(self):
        argv = [
            "record_review.py", "--reviewer", "trust-architect",
            "--paths", "a.py", "--model", "opus", "/x",
        ]
        assert rr._paths_from_argv(argv) == ["a.py"]
        assert rr._positional_target(argv) == "/x"

    def test_stops_at_battery_flag(self):
        argv = ["record_review.py", "--paths", "a.py", "b.py", "--battery", "/x"]
        assert rr._paths_from_argv(argv) == ["a.py", "b.py"]
        assert rr._positional_target(argv) == "/x"


# ===========================================================================
# 2026-08-30 (gate-optimization plan, Item 6) — PART B: new trailing ledger
# fields: tier=/tier_declared=/reviewer=/model=/round=/paths=+paths_n=/
# prev=/vf=, plus the separate battery:<ts> namespace.
# ===========================================================================


class TestParseNewFields:
    def test_reviewer_and_model_are_separate(self):
        fields = rr._parse_new_fields(["x", "--reviewer", "trust-architect", "--model", "opus"])
        assert fields["reviewer"] == "trust-architect"
        assert fields["model"] == "opus"

    def test_model_equals_form(self):
        assert rr._parse_new_fields(["x", "--model=sonnet"])["model"] == "sonnet"

    def test_invalid_model_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._parse_new_fields(["x", "--model", "gpt5"])

    def test_round_space_and_equals_forms(self):
        assert rr._parse_new_fields(["x", "--round", "3"])["round"] == 3
        assert rr._parse_new_fields(["x", "--round=3"])["round"] == 3

    def test_round_zero_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._parse_new_fields(["x", "--round", "0"])

    def test_round_negative_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._parse_new_fields(["x", "--round", "-1"])

    def test_round_non_integer_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._parse_new_fields(["x", "--round", "abc"])

    def test_vf_valid_token_accepted(self):
        assert rr._parse_new_fields(["x", "--vf", "PROVEN"])["vf"] == "PROVEN"

    def test_vf_invalid_token_raises(self):
        with pytest.raises(rr.ArgvError):
            rr._parse_new_fields(["x", "--vf", "MAYBE"])

    @pytest.mark.parametrize("token", sorted(rr._VALID_VF_TOKENS))
    def test_vf_every_valid_token_accepted(self, token):
        assert rr._parse_new_fields(["x", "--vf", token])["vf"] == token

    def test_prev_field(self):
        # --prev requires --round alongside it (2026-08-31, build-wave Lane B).
        # Digest must be exactly 16 hex digits (precommit_review_gate's
        # _DIGEST_LEN) -- round-2 review tightened _PREV_RE's width.
        fields = rr._parse_new_fields(
            ["x", "--prev", "precommit:abc1234567890abc", "--round", "2"]
        )
        assert fields["prev"] == "precommit:abc1234567890abc"

    # -- FINDING 7 (2026-08-30 review): --reviewer/--prev used to silently
    # swallow a following recognized flag as their own value; they now
    # reject loudly, matching --model/--round/--vf's (incidental) behavior.

    def test_reviewer_swallowing_a_following_flag_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer"):
            rr._parse_new_fields(["x", "--reviewer", "--clean"])

    def test_reviewer_equals_form_swallowing_a_flag_name_also_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer"):
            rr._parse_new_fields(["x", "--reviewer=--clean"])

    def test_reviewer_real_value_that_is_not_a_flag_still_accepted(self):
        # A control: a real reviewer name is unaffected by the new check.
        fields = rr._parse_new_fields(["x", "--reviewer", "trust-architect"])
        assert fields["reviewer"] == "trust-architect"

    # -- BLOCKER 3 (2026-08-30 review): the bare --reviewer path had no
    # closed charset of its own (unlike --reviewer-agent-id/
    # --reviewer-tool-use-id's _SAFE_ID_RE, which excludes "#") -- a value
    # containing "#" reached the ledger's reviewer= field verbatim and
    # `parse_reviewer_value` would misparse it as a fabricated compound
    # identity that was never actually claimed.

    def test_reviewer_value_containing_hash_is_sanitized_not_injected(self):
        fields = rr._parse_new_fields(["x", "--reviewer", "a#b#c"])
        assert "#" not in fields["reviewer"]
        assert fields["reviewer"] == "a_b_c"

    def test_reviewer_value_with_hash_never_misparses_as_compound_identity(self):
        # The actual exploit this closes: a raw "#"-laden bare --reviewer
        # value must never be misread back as a fabricated 3-part identity.
        fields = rr._parse_new_fields(["x", "--reviewer", "a#b#c"])
        parsed = rr.parse_reviewer_value(fields["reviewer"])
        assert parsed == {"type": "a_b_c", "agent_id": None, "tool_use_id": None}

    def test_prev_swallowing_a_following_flag_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "--battery"])

    def test_prev_real_value_still_accepted(self):
        # --prev requires --round alongside it (2026-08-31, build-wave Lane B).
        fields = rr._parse_new_fields(
            ["x", "--prev", "precommit:abc1234567890abc", "--round", "1"]
        )
        assert fields["prev"] == "precommit:abc1234567890abc"

    # -- AA-0049 (2026-08-31, build-wave Lane B): --prev shape validation
    # (`^(precommit:[0-9a-f]{16}|sha:[0-9a-f]{7,40})$`) and the
    # --round-required-with---prev
    # rule. Both raise ArgvError -- nothing recorded, matching every other
    # argv-shape refusal in this class.

    def test_prev_malformed_shape_raises(self):
        """A --prev value that isn't '(precommit|sha):<correctly-sized hex>'
        is refused -- this is EXACTLY the live ledger corruption AA-0049
        found ('prev=precommit:29', a 2-hex-digit truncation of a real
        16-digit digest that could never match a real chain link; round-2
        review confirmed the ORIGINAL width-unbounded regex still accepted
        this exact value, since '29' is itself valid hex)."""
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "precommit:29", "--round", "3"])

    def test_prev_live_corruption_second_value_raises(self):
        """The ledger's OTHER live corrupted value (AA-0049)."""
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "precommit:0a", "--round", "3"])

    def test_prev_wrong_prefix_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "commit:abc1234567890abc", "--round", "1"])

    def test_prev_non_hex_digest_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "precommit:ZZZZZZZZZZZZZZZZ", "--round", "1"])

    def test_prev_precommit_digest_too_short_raises(self):
        # 15 hex digits -- one short of the required 16.
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "precommit:abc1234567890ab", "--round", "1"])

    def test_prev_precommit_digest_too_long_raises(self):
        # 17 hex digits -- one over the required 16.
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "precommit:abc1234567890abcd", "--round", "1"])

    def test_prev_sha_prefix_shape_accepted(self):
        fields = rr._parse_new_fields(
            ["x", "--prev", "sha:deadbeef00000000000000000000000000000000", "--round", "2"]
        )
        assert fields["prev"] == "sha:deadbeef00000000000000000000000000000000"

    def test_prev_sha_prefix_short_abbreviated_form_accepted(self):
        # git's minimum abbreviated-sha length (7 hex digits) must be legal.
        fields = rr._parse_new_fields(["x", "--prev", "sha:deadbee", "--round", "2"])
        assert fields["prev"] == "sha:deadbee"

    def test_prev_sha_prefix_too_short_raises(self):
        # 6 hex digits -- one short of git's minimum abbreviation length.
        with pytest.raises(rr.ArgvError, match=r"--prev"):
            rr._parse_new_fields(["x", "--prev", "sha:deadbe", "--round", "1"])

    def test_prev_without_round_raises(self):
        """A --prev with no --round is refused -- the warm-cap walk needs
        round= to reconstruct chain order, and every legitimate
        prev=-carrying ledger entry already carries round= alongside it."""
        with pytest.raises(rr.ArgvError, match=r"--round"):
            rr._parse_new_fields(["x", "--prev", "precommit:abc1234567890abc"])

    def test_prev_with_round_before_it_in_argv_still_satisfied(self):
        # Order-independence: --round parsed before --prev in argv still counts.
        fields = rr._parse_new_fields(
            ["x", "--round", "4", "--prev", "precommit:abc1234567890abc"]
        )
        assert fields["prev"] == "precommit:abc1234567890abc"
        assert fields["round"] == 4

    # -- REGRESSION 3 (round-2 review, 2026-08-31): --warm with no --prev
    # bypassed the consecutive-warm-round cap entirely (main()'s cap-check
    # branch is nested inside "if prev_value:", so a bare --warm never even
    # attempted the walk) while still writing warm=1. --warm now requires
    # BOTH --prev and --round, symmetric with --prev-requires---round above.

    def test_warm_without_prev_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--warm"):
            rr._parse_new_fields(["x", "--warm", "--round", "2"])

    def test_warm_without_round_or_prev_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--warm"):
            rr._parse_new_fields(["x", "--warm"])

    def test_warm_with_prev_and_round_accepted(self):
        fields = rr._parse_new_fields(
            ["x", "--warm", "--prev", "precommit:abc1234567890abc", "--round", "2"]
        )
        assert fields["prev"] == "precommit:abc1234567890abc"
        assert fields["round"] == 2

    def test_tier_declared_raw_captured_but_not_validated_here(self):
        """_parse_new_fields never rejects a --tier value on ITS TOKEN
        VALUE -- ANY disagreement with the computed tier is a signal, so
        even a nonsense (but non-flag-shaped) declared value is captured
        raw and left for main()'s computed-vs-declared comparison, never
        validated against _VALID_TIERS here. It IS rejected when the value
        looks like a swallowed flag -- see the F1 tests below, same
        rationale as --reviewer/--prev above."""
        fields = rr._parse_new_fields(["x", "--tier", "nonsense"])
        assert fields["tier_declared_raw"] == "nonsense"

    # -- F1 (2026-08-30 round-3 review): --tier was left out of the
    # FINDING 7 pass above -- the fourth one-arg flag with no closed value
    # set of its own, and the one whose entire purpose is to be an audit
    # signal, so a swallowed flag here silently corrupts both
    # tier_declared= and triggers a false tier-mismatch log line. Same
    # rejection as --reviewer/--prev.

    def test_tier_swallowing_a_following_flag_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--tier"):
            rr._parse_new_fields(["x", "--tier", "--clean"])

    def test_tier_equals_form_swallowing_a_flag_name_also_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--tier"):
            rr._parse_new_fields(["x", "--tier=--clean"])

    def test_no_new_flags_returns_empty_dict(self):
        assert rr._parse_new_fields(["x", "--clean"]) == {}


# ===========================================================================
# 2026-08-30 (gate-optimization plan, Item 6b) — reviewer= carries the
# dispatch-lease identity (agent_id/tool_use_id) that joins to a real
# ~/.claude/.agent_budget/spend.jsonl row, so an offline audit can later
# tell a real sub-agent review apart from a self-clear. Closes the AUDIT
# gap only -- nothing here blocks anything at commit time.
# ===========================================================================


class TestComposeAndParseReviewerField:
    def test_compose_with_no_identity_returns_bare_type_unchanged(self):
        assert rr.compose_reviewer_field("trust-architect", None, None) == "trust-architect"

    def test_compose_with_only_agent_id_returns_bare_type_unchanged(self):
        # Both-or-neither is enforced by the CALLER (_parse_new_fields); this
        # pure function itself just refuses to build a compound out of a
        # partial identity.
        assert rr.compose_reviewer_field("trust-architect", "abc123", None) == "trust-architect"

    def test_compose_with_both_builds_hash_joined_triple(self):
        val = rr.compose_reviewer_field("code-reviewer", "aa2a7f1545215c433", "toolu_ABC")
        assert val == "code-reviewer#aa2a7f1545215c433#toolu_ABC"

    def test_compose_with_no_type_defaults_to_unknown(self):
        val = rr.compose_reviewer_field(None, "aa2a7f1545215c433", "toolu_ABC")
        assert val == "unknown#aa2a7f1545215c433#toolu_ABC"

    def test_compose_type_containing_hash_is_sanitized(self):
        # "#" in the TYPE component would otherwise desync the 3-way split.
        val = rr.compose_reviewer_field("weird#type", "abc", "toolu_x")
        assert val == "weird_type#abc#toolu_x"

    def test_parse_none_returns_all_none(self):
        assert rr.parse_reviewer_value(None) == {
            "type": None, "agent_id": None, "tool_use_id": None,
        }

    def test_parse_bare_type_is_original_item6_shape(self):
        assert rr.parse_reviewer_value("trust-architect") == {
            "type": "trust-architect", "agent_id": None, "tool_use_id": None,
        }

    def test_parse_well_formed_compound_round_trips(self):
        composed = rr.compose_reviewer_field("code-reviewer", "aa2a7f1545215c433", "toolu_ABC")
        assert rr.parse_reviewer_value(composed) == {
            "type": "code-reviewer",
            "agent_id": "aa2a7f1545215c433",
            "tool_use_id": "toolu_ABC",
        }

    def test_parse_malformed_compound_degrades_to_whole_value_as_type(self):
        # Only two parts -- not a real compound; treat the whole thing as
        # the bare type rather than guessing a partial identity.
        assert rr.parse_reviewer_value("a#b") == {
            "type": "a#b", "agent_id": None, "tool_use_id": None,
        }

    def test_parse_compound_with_empty_part_degrades_to_whole_value(self):
        assert rr.parse_reviewer_value("a##c") == {
            "type": "a##c", "agent_id": None, "tool_use_id": None,
        }


class TestParseNewFieldsReviewerIdentity:
    def test_both_agent_id_and_tool_use_id_composes_into_reviewer_field(self):
        fields = rr._parse_new_fields([
            "x", "--reviewer", "code-reviewer",
            "--reviewer-agent-id", "aa2a7f1545215c433",
            "--reviewer-tool-use-id", "toolu_018GWvbQrzwEVkCaZAf23WNP",
        ])
        assert fields["reviewer"] == (
            "code-reviewer#aa2a7f1545215c433#toolu_018GWvbQrzwEVkCaZAf23WNP"
        )

    def test_identity_with_no_reviewer_type_defaults_to_unknown(self):
        fields = rr._parse_new_fields([
            "x", "--reviewer-agent-id", "aa2a7f1545215c433",
            "--reviewer-tool-use-id", "toolu_ABC",
        ])
        assert fields["reviewer"] == "unknown#aa2a7f1545215c433#toolu_ABC"

    def test_only_agent_id_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer-agent-id"):
            rr._parse_new_fields(["x", "--reviewer-agent-id", "aa2a7f1545215c433"])

    def test_only_tool_use_id_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer-tool-use-id"):
            rr._parse_new_fields(["x", "--reviewer-tool-use-id", "toolu_ABC"])

    def test_agent_id_swallowing_a_following_flag_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer-agent-id"):
            rr._parse_new_fields([
                "x", "--reviewer-agent-id", "--clean",
                "--reviewer-tool-use-id", "toolu_ABC",
            ])

    def test_tool_use_id_swallowing_a_following_flag_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer-tool-use-id"):
            rr._parse_new_fields([
                "x", "--reviewer-agent-id", "aa2a7f1545215c433",
                "--reviewer-tool-use-id", "--battery",
            ])

    def test_agent_id_with_space_is_rejected(self):
        with pytest.raises(rr.ArgvError, match=r"--reviewer-agent-id"):
            rr._parse_new_fields([
                "x", "--reviewer-agent-id", "bad id",
                "--reviewer-tool-use-id", "toolu_ABC",
            ])

    def test_agent_id_starting_with_hyphen_is_rejected(self):
        # Guards the _SAFE_ID_RE "must start with alnum" rule specifically
        # (a bare "--clean"-shaped string is ALL hyphen/letters and would
        # otherwise satisfy a charset-only check).
        with pytest.raises(rr.ArgvError, match=r"--reviewer-agent-id"):
            rr._parse_new_fields([
                "x", "--reviewer-agent-id", "-leading-hyphen",
                "--reviewer-tool-use-id", "toolu_ABC",
            ])

    def test_equals_form_both_supplied(self):
        fields = rr._parse_new_fields([
            "x", "--reviewer-agent-id=aa2a7f1545215c433",
            "--reviewer-tool-use-id=toolu_ABC",
        ])
        assert fields["reviewer"] == "unknown#aa2a7f1545215c433#toolu_ABC"


class TestHeadReviewReviewerIdentity:
    def test_never_recorded_returns_all_none(self, tmp_path):
        path = str(tmp_path / "last_reviewed")
        assert rr.head_review_reviewer_identity(path, "/repo", "deadbeef") == {
            "type": None, "agent_id": None, "tool_use_id": None,
        }

    def test_recorded_with_identity_round_trips(self, tmp_path):
        path = tmp_path / "last_reviewed"
        path.write_text(
            "/repo deadbeef clean ts=2026-08-30T10:00:00Z "
            "reviewer=code-reviewer#aa2a7f1545215c433#toolu_ABC\n"
        )
        identity = rr.head_review_reviewer_identity(str(path), "/repo", "deadbeef")
        assert identity == {
            "type": "code-reviewer",
            "agent_id": "aa2a7f1545215c433",
            "tool_use_id": "toolu_ABC",
        }


@_requires_git
def test_main_reviewer_identity_end_to_end_writes_compound_field(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """The falsifiable core of Item 6b: a real `main()` invocation with a
    reviewer type PLUS the dispatch identity writes a single reviewer=
    field carrying all three, joinable later against spend.jsonl."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "aa2a7f1545215c433",
        "--reviewer-tool-use-id", "toolu_018GWvbQrzwEVkCaZAf23WNP",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert (
        "reviewer=code-reviewer#aa2a7f1545215c433#toolu_018GWvbQrzwEVkCaZAf23WNP" in tokens
    )


@_requires_git
def test_main_reviewer_identity_partial_flags_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """A lone --reviewer-agent-id (no matching --reviewer-tool-use-id) is a
    caller mistake, not a usable join key -- rejected loudly, nothing
    written, mirroring --model's own invalid-value contract."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer-agent-id", "aa2a7f1545215c433",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    out = capsys.readouterr().out
    assert "TOGETHER" in out
    assert "Nothing recorded" in out


@_requires_git
def test_main_reviewer_without_identity_stays_backward_compatible(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A caller that supplies ONLY --reviewer (Item 6's original shape, and
    every ledger line recorded before Item 6b) still writes the bare type
    string -- no identity fields required, nothing new mandatory."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer", "trust-architect",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "reviewer=trust-architect" in tokens


@_requires_git
def test_main_reviewer_hash_injection_is_sanitized_end_to_end(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """BLOCKER 3 falsifiability: a bare --reviewer value containing "#"
    (the compound identity's own join separator) must not survive to the
    ledger, or later be misread back as a fabricated (agent_id,
    tool_use_id) identity that was never actually supplied."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer", "a#b#c",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    reviewer_token = next(t for t in tokens if t.startswith("reviewer="))
    assert "#" not in reviewer_token

    head = rr._git(str(committed_repo), "rev-parse", "HEAD")
    identity = rr.head_review_reviewer_identity(
        str(sandbox.last_reviewed), str(committed_repo), head
    )
    assert identity == {"type": "a_b_c", "agent_id": None, "tool_use_id": None}


class TestItemFromArgv:
    def test_real_value(self):
        assert rr._item_from_argv(["x", "--item", "4400"]) == "4400"

    def test_equals_form(self):
        assert rr._item_from_argv(["x", "--item=4400"]) == "4400"

    def test_absent_is_none(self):
        assert rr._item_from_argv(["x", "--clean"]) is None

    def test_swallowing_a_following_flag_raises(self):
        # FINDING 7: --item used to silently record item="--clean" here.
        with pytest.raises(rr.ArgvError, match=r"--item"):
            rr._item_from_argv(["x", "--item", "--clean"])

    def test_equals_form_swallowing_a_flag_name_also_raises(self):
        with pytest.raises(rr.ArgvError, match=r"--item"):
            rr._item_from_argv(["x", "--item=--clean"])


@_requires_git
def test_main_item_swallowing_a_flag_is_rejected_loudly_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """FINDING 7, main()-level integration: --item's rejection is wired
    into the SAME argv-validation try/except as --reviewer/--model/etc, so
    a caller mistake here is refused loudly with nothing recorded, exactly
    like the pre-existing --model/--round/--vf rejections."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--item", "--clean"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert lines[-1]["decision"] == "argv-error"


class TestBatteryEntry:
    def test_valid_battery_entry_shape(self):
        line = rr._battery_entry("26/27", "1")
        assert line is not None
        assert line.startswith(rr.BATTERY_PREFIX)
        assert "mut=26/27" in line
        assert "stale=1" in line

    def test_invalid_mut_shape_is_none(self):
        assert rr._battery_entry("not-a-fraction", "0") is None
        assert rr._battery_entry(None, "0") is None

    def test_invalid_stale_is_none(self):
        assert rr._battery_entry("26/27", "not-a-number") is None
        assert rr._battery_entry("26/27", "-1") is None
        assert rr._battery_entry("26/27", None) is None


def test_field_tier_unknown_for_legacy_line(tmp_path):
    """A legacy line with no tier= field must read as UNKNOWN, never
    silently defaulted to a real tier value like 'moderate'."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text("/repo/a abc123 clean ts=2026-08-23T12:00:00Z\n")
    fields = rr.head_review_fields(str(ledger), "/repo/a", "abc123")
    assert "tier" not in fields
    assert fields.get("tier", rr.TIER_UNKNOWN) == rr.TIER_UNKNOWN


def test_field_tier_reads_a_real_recorded_tier_value(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/a abc123 clean ts=2026-08-23T12:00:00Z tier=high reviewer=trust-architect\n"
    )
    token = rr._existing_outcome_token(str(ledger), "/repo/a", "abc123")
    assert rr.field_tier(token) == "high"
    fields = rr.head_review_fields(str(ledger), "/repo/a", "abc123")
    assert fields["tier"] == "high"
    assert fields["reviewer"] == "trust-architect"


def test_head_review_fields_never_recorded_is_empty_dict(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text("")
    assert rr.head_review_fields(str(ledger), "/nope", "x") == {}


def test_existing_outcome_token_never_matches_a_battery_line(tmp_path):
    """A battery: line can never satisfy a REAL "<repo_root> <head>" needle
    -- repo_root is always an absolute filesystem path and can never equal
    a literal "battery:<ts>" string, so a lookup for a real repo/head is
    never confused by an unrelated battery: line sitting in the same
    ledger. (Feeding the needle "battery:2026-08-30T00:00:00Z"/"mut=26/27"
    itself back in would trivially "match" its own text -- that is not the
    real-world shape this proves; a real repo_root/head pair never looks
    like that.)"""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "battery:2026-08-30T00:00:00Z mut=26/27 stale=0\n/repo/a sha1 clean\n"
    )
    # No real repo_root+head pair, however chosen, can ever coincide with
    # the battery: line's own text -- confirmed against the ACTUAL entry
    # that does exist for a different repo/head, unaffected by it.
    assert rr._existing_outcome_token(str(ledger), "/repo/a", "sha1") == "clean"
    assert rr._existing_outcome_token(str(ledger), "/repo/other", "shaX") is None


# ---------------------------------------------------------------------------
# main()-level integration: the full argv -> ledger-line round trip for
# every new field.
# ---------------------------------------------------------------------------


@_requires_git
def test_main_tier_is_computed_not_trusted_from_a_disagreeing_flag(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A hooks/-segment path always classifies HIGH via classify(),
    regardless of a caller's disagreeing --tier claim -- the disagreement
    is recorded as an AUDIT signal (tier_declared=), never trusted in place
    of the computed value."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "hooks/foo.py",
        "--tier", "trivial",  # deliberately WRONG -- classify() says high
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert " tier=high" in text
    assert " tier_declared=trivial" in text
    lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    mismatches = [r for r in lines if r["decision"] == "tier-mismatch"]
    assert mismatches, "expected a tier-mismatch decision to be logged"
    assert mismatches[-1]["declared"] == "trivial"
    assert mismatches[-1]["computed"] == "high"


@_requires_git
def test_main_tier_no_mismatch_when_declared_agrees(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "hooks/foo.py", "--tier", "high",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert " tier=high" in text
    assert "tier_declared=" not in text
    lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert not [r for r in lines if r["decision"] == "tier-mismatch"]


@_requires_git
def test_main_tier_computation_exception_never_raises_and_still_records(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """BLOCKER 3 (2026-08-30 review): this module's own documented contract
    is "never raises out to its caller: a crashing hook must not break the
    agent. Every failure degrades to a clean exit 0." A raising classifier
    during tier computation (the reviewer's proven live trigger -- the lazy
    `precommit_review_gate` import + `classify()` call, previously
    unguarded whenever `--paths` was passed) must degrade to `tier=None`,
    never crash `main()` -- and the REST of the call must still proceed to
    record the review, not abort the whole thing over a telemetry failure.
    Calling `rr.main()` directly (not via `pytest.raises`) is itself part
    of the assertion: an uncaught exception here fails this test with a
    traceback, exactly mirroring how it would fail a real caller (e.g. the
    unattended nightly finishing loop)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    def _raise(*_a, **_k):
        raise RuntimeError("boom: classifier exploded")

    monkeypatch.setattr(rr.rrt, "classify", _raise)

    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "hooks/foo.py",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert "tier=" not in text  # degraded to unknown, never half-written
    assert " clean" in text  # the review outcome itself still got recorded


@_requires_git
def test_main_tier_declared_with_no_paths_logs_explicitly(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """FINDING 4 (2026-08-30 review): --tier with no --paths used to be
    silently accepted and discarded -- no tier=, no tier_declared=, no log
    line at all. Now produces a visible log entry (never blocks/errors:
    the call still succeeds and records normally; tier= itself never
    appears at all without --paths, per test_main_no_paths_means_no_tier_computed)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--tier", "high"])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert "tier=" not in text
    lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    entries = [r for r in lines if r["decision"] == "tier-declared-no-paths"]
    assert entries, "expected a tier-declared-no-paths decision to be logged"
    assert entries[-1]["declared"] == "high"


@_requires_git
def test_main_tier_mismatch_not_logged_when_call_aborts_early(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """FINDING 5 (2026-08-30 review): a --tier mismatch computed BEFORE the
    --pre-commit early-abort branches must never be logged for a call that
    ends up aborting with nothing recorded -- an auditor counting mismatches
    must never count a declaration that produced no real ledger entry.
    `f.txt` has no pending change vs HEAD in `committed_repo`, so
    `--pre-commit` aborts via `precommit-empty-diff` before `decide()` is
    ever reached; the deliberately-wrong `--tier trivial` (f.txt classifies
    as the "moderate" default, never "trivial") would have produced a real
    mismatch had the call proceeded."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit",
        "--paths", "f.txt", "--tier", "trivial",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert not [r for r in lines if r["decision"] == "tier-mismatch"]
    assert [r for r in lines if r["decision"] == "precommit-empty-diff"]


@_requires_git
def test_main_tier_mismatch_not_logged_on_status_already(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """FINDING 5, complementary case: a SECOND identical call resolves to
    STATUS_ALREADY (nothing NEW recorded) -- the tier-mismatch log from the
    first call must not be re-emitted on this one, even though the same
    disagreeing --tier is passed again."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    argv = [
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "hooks/foo.py", "--tier", "trivial",  # disagrees w/ computed "moderate"
    ]
    rc1 = rr.main(argv)
    assert rc1 == 0
    lines1 = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert [r for r in lines1 if r["decision"] == "tier-mismatch"]  # first call: real record -> logged

    rc2 = rr.main(argv)
    assert rc2 == 0
    lines2 = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert lines2[-1]["decision"] == "already"
    # No SECOND tier-mismatch entry appended for the STATUS_ALREADY call.
    assert len([r for r in lines2 if r["decision"] == "tier-mismatch"]) == 1


@_requires_git
def test_main_precommit_warns_when_directory_path_has_untracked_files(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """GH #5886 checklist item 3: recording a --pre-commit review whose
    --paths names a DIRECTORY that currently contains untracked files prints
    an advisory NOTE pointing at --rekey -- staging those files later moves
    the digest (AA-0064), and --rekey is how to carry the review forward
    without a second full review. Advisory only: nothing is refused, and the
    review still records normally."""
    newdir = committed_repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "newdir",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "newdir" in out
    assert "untracked" in out
    assert "--rekey" in out
    # Advisory only -- the review still actually recorded.
    assert "recorded review of HEAD" in out
    text = sandbox.last_reviewed.read_text()
    assert "precommit:" in text and "clean" in text


@_requires_git
def test_main_precommit_directory_untracked_warning_fires_from_a_subdirectory(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """NIT 5 (2026-09-23 round-2 review): the directory-has-untracked-files
    NOTE must fire even when the recording command is issued from a
    SUBDIRECTORY of the repo, with `--paths` typed relative to that cwd --
    the isdir check already used `target` (the cwd), but the `ls-files`
    lookup ran from the repo root with the SAME relative path string,
    silently matching nothing and suppressing the note whenever the two
    coordinate frames differ."""
    sub = committed_repo / "sub"
    sub.mkdir()
    newdir = sub / "newdir"
    newdir.mkdir()
    (newdir / "untracked.py").write_text("x = 1\n")
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(sub)})))
    rc = rr.main([
        "record_review.py", str(sub), "--pre-commit", "--clean",
        "--paths", "newdir",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "newdir" in out
    assert "untracked" in out
    assert "--rekey" in out


@_requires_git
def test_main_precommit_no_warning_for_a_plain_file_pathspec(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """Negative control: an ordinary file --paths entry (not a directory)
    must never trigger the directory-untracked-content note."""
    (committed_repo / "f.txt").write_text("changed\n")
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "untracked" not in out
    assert "--rekey" not in out


@_requires_git
def test_main_precommit_no_warning_for_a_directory_with_no_untracked_files(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """A directory --paths entry whose files are ALREADY tracked (only
    content edits pending, nothing untracked underneath) must not trigger
    the note -- there is no untracked-to-staged transition risk."""
    newdir = committed_repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    _run_git(committed_repo, "add", "newdir/a.py")
    _run_git(committed_repo, "commit", "-q", "-m", "add newdir/a.py")
    (newdir / "a.py").write_text("a = 2\n")  # tracked edit only, nothing untracked
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "newdir",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "untracked" not in out
    assert "--rekey" not in out


@_requires_git
def test_main_no_paths_means_no_tier_computed(sandbox, clean_env, committed_repo, monkeypatch):
    """Without --paths there is no pathspec to classify -- tier= must never
    appear at all, not even as a guessed default."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean"])
    assert rc == 0
    assert "tier=" not in sandbox.last_reviewed.read_text()


@_requires_git
def test_main_reviewer_and_model_are_separate_fields(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer", "trust-architect", "--model", "opus",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "reviewer=trust-architect" in tokens
    assert "model=opus" in tokens


@_requires_git
def test_main_invalid_model_is_rejected_loudly_and_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--model", "gpt5"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    out = capsys.readouterr().out
    assert "gpt5" in out
    assert "Nothing recorded" in out


@_requires_git
def test_main_invalid_round_is_rejected_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--round", "0"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_valid_round_is_recorded(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--round", "2"])
    assert rc == 0
    assert "round=2" in sandbox.last_reviewed.read_text()


@_requires_git
def test_main_vf_rejects_invalid_token_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--vf", "BOGUS"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_vf_valid_token_is_recorded(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--vf", "PARTIAL"])
    assert rc == 0
    assert "vf=PARTIAL" in sandbox.last_reviewed.read_text()


@_requires_git
def test_main_prev_field_recorded(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    # --prev requires --round alongside it (2026-08-31, build-wave Lane B).
    # Digest must be exactly 16 hex digits (round-2 review width fix).
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--prev", "precommit:abc1234567890abc", "--round", "2",
    ])
    assert rc == 0
    assert "prev=precommit:abc1234567890abc" in sandbox.last_reviewed.read_text()


# --------------------------------------------------------------------------
# AA-0048/AA-0049 (2026-08-31, build-wave Lane B): --prev self-reference,
# --prev shape at the main() boundary, and the consecutive-warm-round cap.
# --------------------------------------------------------------------------


@_requires_git
def test_main_prev_malformed_shape_rejected_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--prev", "ommit:29", "--round", "3",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_prev_without_round_rejected_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    # A correctly-SHAPED digest (so this refusal is unambiguously the
    # missing---round check, not the shape check).
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--prev", "precommit:abc1234567890abc",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_prev_self_reference_on_precommit_digest_rejected(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """AA-0049's exact live defect: a --pre-commit recording whose --prev
    equals the digest THIS call itself would compute for the same pending
    content -- a chain cannot be its own predecessor. Proven against a
    REAL computed digest (via prg.pending_key), not a guessed string, so
    this fails even if the self-reference check only matched by luck."""
    (committed_repo / "f.txt").write_text("changed\n")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    own_digest = prg.pending_key(root, str(committed_repo), ["f.txt"])
    assert own_digest and own_digest.startswith("precommit:")

    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit",
        "--paths", "f.txt", "--prev", own_digest, "--round", "2",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_prev_self_reference_on_plain_head_rejected(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """The non-precommit form: recording a plain HEAD (no --pre-commit)
    with --prev equal to sha:<that same HEAD> is also a self-reference."""
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--prev", f"sha:{head}", "--round", "2",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_prev_different_digest_not_self_reference_still_recorded(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A genuinely DIFFERENT prior digest is a legitimate chain link, not a
    self-reference -- the check must not false-positive on every --prev."""
    (committed_repo / "f.txt").write_text("changed\n")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    own_digest = prg.pending_key(root, str(committed_repo), ["f.txt"])
    other_digest = "precommit:0000000000000000"
    assert other_digest != own_digest

    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit",
        "--paths", "f.txt", "--prev", other_digest, "--round", "2",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert f"prev={other_digest}" in text


def _record_precommit_round(
    committed_repo,
    content: str,
    *,
    round_n: int,
    prev: str | None,
    warm: bool,
) -> str:
    """Writes `content` to f.txt (giving this round its own real pending
    diff / digest), records a --pre-commit --clean round via rr.main(), and
    returns the digest that round was recorded under. Requires CSA_ENFORCE
    already set and stdin already patched by the caller."""
    (committed_repo / "f.txt").write_text(content)
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    digest = prg.pending_key(root, str(committed_repo), ["f.txt"])
    assert digest and digest.startswith("precommit:")
    argv = [
        "record_review.py", str(committed_repo), "--clean", "--pre-commit",
        "--paths", "f.txt", "--round", str(round_n),
    ]
    if prev:
        argv += ["--prev", prev]
    if warm:
        argv += ["--warm"]
    rc = rr.main(argv)
    assert rc == 0
    return digest


@_requires_git
def test_main_warm_field_recorded_on_ledger_line(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    d1 = _record_precommit_round(
        committed_repo, "round1\n", round_n=1, prev=None, warm=False
    )
    d2 = _record_precommit_round(
        committed_repo, "round2\n", round_n=2, prev=d1, warm=True
    )
    text = sandbox.last_reviewed.read_text()
    lines = [ln for ln in text.strip().splitlines() if d2 in ln]
    assert lines, f"expected a ledger line for {d2}"
    assert "warm=1" in lines[-1]


@_requires_git
def test_main_cold_round_never_carries_warm_field(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    digest = _record_precommit_round(
        committed_repo, "cold-only\n", round_n=1, prev=None, warm=False
    )
    text = sandbox.last_reviewed.read_text()
    lines = [ln for ln in text.strip().splitlines() if digest in ln]
    assert lines
    assert "warm=" not in lines[-1]


@_requires_git
def test_main_third_consecutive_warm_round_refused(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """CLAUDE.md §10's warm-round cap: at most TWO consecutive warm full
    rounds on one prev=-linked chain; the THIRD is refused with the
    cold-dispatch instruction, and refused BEFORE any write (round 3's own
    content never lands in the ledger at all)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    d1 = _record_precommit_round(
        committed_repo, "r1\n", round_n=1, prev=None, warm=False
    )
    d2 = _record_precommit_round(
        committed_repo, "r2\n", round_n=2, prev=d1, warm=True
    )
    d3 = _record_precommit_round(
        committed_repo, "r3\n", round_n=3, prev=d2, warm=True
    )
    # Two consecutive warm rounds (d2, d3) are on record; a third warm round
    # chained off d3 must be refused.
    (committed_repo / "f.txt").write_text("r4\n")
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    d4 = prg.pending_key(root, str(committed_repo), ["f.txt"])
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit",
        "--paths", "f.txt", "--round", "4", "--prev", d3, "--warm",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    assert d4 not in text, "round 4 (3rd consecutive warm) must not be recorded"
    # rounds 1-3 remain on record, untouched by the refusal.
    assert d1 in text
    assert d2 in text
    assert d3 in text


@_requires_git
def test_main_bare_warm_flag_with_no_prev_refused_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """REGRESSION 3 (round-2 review, 2026-08-31): the bare `--clean --warm`
    shape (no --prev, no --round) used to bypass the consecutive-warm-round
    cap entirely -- main()'s cap-check branch only ran INSIDE `if
    prev_value:`, so a --warm with no --prev never attempted the walk at
    all, and record_review still happily wrote a `warm=1` ledger line with
    zero enforcement ever possible on it. --warm now requires --prev and
    --round; this exact shape must be refused, nothing recorded."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--warm"])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_warm_with_round_but_no_prev_still_refused(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """--round alone is not enough -- --warm specifically needs --prev too
    (the walk has nothing to walk FROM without it)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--warm", "--round", "2",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_warm_round_after_a_cold_round_is_not_capped(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """The cap counts CONSECUTIVE warm rounds only -- a cold round resets
    the count, so warm rounds 2 and 3 of a NEW chain (cold, warm, warm) are
    both legal, matching the interleaved-tier bound-(a) precedent (a chain
    break resets the warm count, it does not permanently poison the repo)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    d1 = _record_precommit_round(
        committed_repo, "c1\n", round_n=1, prev=None, warm=False
    )
    d2 = _record_precommit_round(
        committed_repo, "c2\n", round_n=2, prev=d1, warm=True
    )
    d3 = _record_precommit_round(
        committed_repo, "c3\n", round_n=3, prev=d2, warm=True
    )
    text = sandbox.last_reviewed.read_text()
    assert d3 in text


@_requires_git
def test_consecutive_warm_round_count_helper_stops_at_cold_link(
    sandbox, clean_env, committed_repo
):
    """Direct unit coverage of the walking helper itself: a chain of
    warm, warm, cold (walked from the newest) counts exactly 2 consecutive
    warm entries and stops at the cold one."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} precommit:aaaaaaaaaaaaaaaa clean ts=2026-08-31T00:00:00Z round=1\n"
        f"{root} precommit:bbbbbbbbbbbbbbbb clean ts=2026-08-31T00:00:01Z round=2 "
        "prev=precommit:aaaaaaaaaaaaaaaa warm=1\n"
        f"{root} precommit:cccccccccccccccc clean ts=2026-08-31T00:00:02Z round=3 "
        "prev=precommit:bbbbbbbbbbbbbbbb warm=1\n"
    )
    count = rr._consecutive_warm_round_count(
        str(sandbox.last_reviewed), root, "precommit:cccccccccccccccc"
    )
    assert count == 2


@_requires_git
def test_consecutive_warm_round_count_helper_handles_dangling_prev(
    sandbox, clean_env, committed_repo
):
    """A prev= pointing at a key with no ledger entry at all (a dangling/
    foreign link) must stop the walk, never crash or loop forever."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} precommit:1111111111111111 clean ts=2026-08-31T00:00:00Z round=5 "
        "prev=precommit:0000000000000000 warm=1\n"
    )
    count = rr._consecutive_warm_round_count(
        str(sandbox.last_reviewed), root, "precommit:1111111111111111"
    )
    assert count == 1


@_requires_git
def test_consecutive_warm_round_count_helper_walks_sha_chained_entries(
    sandbox, clean_env, committed_repo
):
    """REGRESSION 2 (round-2 review, 2026-08-31): a plain (non---pre-commit)
    recording's decide() writes the BARE sha as the ledger's `head` token
    (``f"{repo_root} {head}"``, no ``sha:`` prefix at all) -- only the
    ``--prev``/``prev=`` SPELLING carries the ``sha:`` prefix. Before the
    fix, `_consecutive_warm_round_count` passed a ``sha:``-prefixed key
    straight into `_existing_outcome_token`, which could never match the
    bare-sha-keyed line, silently returning 0 (no cap enforcement at all)
    for every sha-chained warm round. This ledger is built EXACTLY the way
    a real plain-HEAD recording writes it (bare sha as the second token)
    and must still walk correctly when queried via the ``sha:``-prefixed
    key `--prev`/`_current_digest_key` always uses."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    sha1 = "1111111111111111111111111111111111111111"
    sha2 = "2222222222222222222222222222222222222222"
    sha3 = "3333333333333333333333333333333333333333"
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {sha1} clean ts=2026-08-31T00:00:00Z round=1\n"
        f"{root} {sha2} clean ts=2026-08-31T00:00:01Z round=2 "
        f"prev=sha:{sha1} warm=1\n"
        f"{root} {sha3} clean ts=2026-08-31T00:00:02Z round=3 "
        f"prev=sha:{sha2} warm=1\n"
    )
    count = rr._consecutive_warm_round_count(str(sandbox.last_reviewed), root, f"sha:{sha3}")
    assert count == 2


@_requires_git
def test_consecutive_warm_round_count_helper_sha_chain_stops_at_cold_link(
    sandbox, clean_env, committed_repo
):
    """The sha-chained walk still stops at a cold (non-warm) link, exactly
    like the precommit-chained case."""
    root = _git_out(committed_repo, "rev-parse", "--show-toplevel")
    sha1 = "aaaa111111111111111111111111111111111a"
    sha2 = "bbbb222222222222222222222222222222222b"
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {sha1} clean ts=2026-08-31T00:00:00Z round=1\n"  # cold: no warm=
        f"{root} {sha2} clean ts=2026-08-31T00:00:01Z round=2 prev=sha:{sha1} warm=1\n"
    )
    count = rr._consecutive_warm_round_count(str(sandbox.last_reviewed), root, f"sha:{sha2}")
    assert count == 1


def test_ledger_lookup_key_strips_sha_prefix():
    assert rr._ledger_lookup_key("sha:deadbeef") == "deadbeef"


def test_ledger_lookup_key_leaves_precommit_key_unchanged():
    assert rr._ledger_lookup_key("precommit:abc1234567890abc") == "precommit:abc1234567890abc"


@_requires_git
def test_main_paths_field_joined_with_hash_and_paths_n_always_emitted(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(
        ["record_review.py", str(committed_repo), "--clean", "--paths", "a.py", "b/c.py"]
    )
    assert rc == 0
    text = sandbox.last_reviewed.read_text().strip()
    assert "paths=a.py#b/c.py" in text
    assert "paths_n=2" in text


@_requires_git
def test_main_paths_field_caps_at_12_but_reports_true_total(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    many = [f"f{i}.py" for i in range(15)]
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--paths", *many])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "paths_n=15" in line
    paths_tok = [t for t in line.split() if t.startswith("paths=")][0]
    joined = paths_tok[len("paths="):]
    assert joined.count("#") == 11  # 12 entries -> 11 separators
    assert joined.split("#") == many[:12]


@_requires_git
def test_main_paths_field_sanitizes_embedded_space_never_corrupts_the_line(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "a dir/weird file.py",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text().strip()
    # A single ledger LINE must still be exactly one line -- a raw space in
    # a path would otherwise fracture the space-separated k=v grammar every
    # downstream reader (parse_outcome_token, parse_ledger_fields) relies on.
    assert len(text.splitlines()) == 1
    line = text.splitlines()[0]
    paths_tok = [t for t in line.split() if t.startswith("paths=")][0]
    assert " " not in paths_tok


def test_safe_path_component_neutralizes_embedded_hash():
    # BLOCKER 2 (trust-architect review, 2026-08-30): "#" is deliberately
    # EXCLUDED from `_SAFE_PATH_RE` (unlike the general `_SAFE_FIELD_RE`,
    # which DOES allow "#") precisely because "#" is the paths= join
    # separator -- a path containing a literal "#" must never survive
    # sanitization and fake an extra field boundary.
    assert "#" not in rr._safe_path_component("weird#file.py")
    assert "#" not in rr._safe_path_component("a#b#c.py")


def test_paths_field_embedded_hash_never_desyncs_paths_n_from_split_count():
    # THE regression the reviewer proved live: swapping `_safe_path_component`
    # to reuse the general `_SAFE_FIELD_RE` (which allows "#") instead of the
    # dedicated `_SAFE_PATH_RE` leaves every OTHER test passing while
    # silently desynchronizing paths=/paths_n= -- a path containing a literal
    # "#" would then fake an extra "#"-separator boundary, so a reader
    # splitting paths= on "#" gets MORE components than paths_n= claims.
    # This test is real coverage of that exact failure mode, not just a
    # presence-of-string check: it asserts the INVARIANT a downstream reader
    # actually depends on (split-count == paths_n), for a path containing a
    # literal "#" character specifically.
    joined, total = rr._paths_field(["a#b.py", "c.py", "weird#dir/file#2.py"])
    assert total == 3
    parts = joined.split("#")
    assert len(parts) == total  # exactly paths_n components, never more
    # And each sanitized component individually carries no "#" at all --
    # the invariant above would also hold (vacuously) if `#` were merely
    # ESCAPED rather than replaced, so this pins the actual replacement
    # behavior too.
    assert all("#" not in p for p in parts)


@_requires_git
def test_main_paths_field_sanitizes_embedded_hash_paths_n_matches_split_count(
    sandbox, clean_env, committed_repo, monkeypatch
):
    # Integration-level twin of the pure-function test above, through the
    # real CLI/main() path -- proves the invariant holds end-to-end on the
    # actual ledger line written to disk, not just on `_paths_field` in
    # isolation.
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--paths", "a#b.py", "c.py",
    ])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "paths_n=2" in line
    paths_tok = [t for t in line.split() if t.startswith("paths=")][0]
    joined = paths_tok[len("paths="):]
    assert len(joined.split("#")) == 2  # never 3 -- the embedded "#" must not fake a boundary


@_requires_git
def test_main_battery_writes_the_battery_namespace_line(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--battery",
        "--mut", "26/27", "--stale", "0",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text().strip()
    assert text.startswith(rr.BATTERY_PREFIX)
    assert "mut=26/27 stale=0" in text
    rec = _last_log(sandbox)
    assert rec["decision"] == "battery-recorded"


@_requires_git
def test_main_battery_invalid_records_nothing(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--battery",
        "--mut", "bogus", "--stale", "0",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


@_requires_git
def test_main_battery_log_only_when_not_enforcing(
    sandbox, clean_env, committed_repo, monkeypatch, capsys
):
    """LOG-ONLY: --battery is a write request that was skipped, so it exits 1 and says
    NOT recorded on stderr (same contract as the HEAD / --pre-commit record path); the
    would-record line and the 'battery-would-record' log row are unchanged."""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    argv = [
        "record_review.py", str(committed_repo), "--battery",
        "--mut", "10/10", "--stale", "0",
    ]
    rc = rr.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "battery-would-record"
    assert "(LOG-ONLY) would record mutation-battery result" in captured.out
    assert (
        "NOT recorded (log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"
        in captured.err
    )
    assert "recorded mutation-battery result" not in captured.out

    # Pair: the same call with enforcement on records the line and exits 0.
    clean_env.setenv("CSA_ENFORCE", "1")
    assert rr.main(argv) == 0
    assert sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "battery-recorded"


@_requires_git
def test_precommit_gate_decide_ignores_battery_lines(sandbox, clean_env, tmp_path):
    """precommit_review_gate.decide() must never error on, or misparse, a
    battery:-prefixed ledger line -- proven directly against decide()
    itself, not just record_review's own token parsers."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "a.py").write_text("x = 1\n")
    _run_git(repo, "add", "a.py")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "a.py")
    (repo / "a.py").write_text("x = 2\n")
    root = _git_out(repo, "rev-parse", "--show-toplevel")

    # 1) A ledger that ONLY holds a battery: line -> decide() still
    #    correctly reports "unreviewed" for a real pending change: no
    #    error, and the battery line is never mistaken for coverage.
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text("battery:2026-08-30T00:00:00Z mut=26/27 stale=0\n")
    block, reason, _detail = prg.decide(root, str(repo), ["a.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED

    # 2) A ledger holding BOTH a battery: line AND a real, clean precommit:
    #    entry for this exact content -> the real entry still clears the
    #    gate; the battery line's presence changes nothing.
    key = prg.pending_key(root, str(repo), ["a.py"])
    sandbox.last_reviewed.write_text(
        "battery:2026-08-30T00:00:00Z mut=26/27 stale=0\n"
        f"{root} {key} clean ts=2026-08-30T00:00:01Z\n"
    )
    block2, reason2, _detail2 = prg.decide(root, str(repo), ["a.py"])
    assert block2 is False
    assert reason2 == ""


# ---------------------------------------------------------------------------
# --rekey argv validation (AA-0064, 2026-09-01 waste-elimination P3). The
# mechanism itself (accepts/refuses on real content) is exercised end-to-end
# in test_precommit_review_gate.py alongside precommit_review_gate's own
# reconstruction functions; these cover the argv-shape refusals that never
# even reach that machinery.
# ---------------------------------------------------------------------------


@_requires_git
def test_rekey_rejects_malformed_key_shape(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--rekey", "not-a-real-key",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "rekey-invalid-key"


@_requires_git
def test_rekey_rejects_a_truncated_digest(sandbox, clean_env, committed_repo, monkeypatch):
    # Same truncation shape AA-0049 fixed for --prev; --rekey shares the
    # closed-shape regex and must refuse it identically.
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--rekey", "precommit:29",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "rekey-invalid-key"


@_requires_git
def test_rekey_requires_paths(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main(["record_review.py", str(committed_repo), "--rekey", key])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "rekey-no-paths"


@_requires_git
def test_rekey_conflicts_with_precommit(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--rekey", key, "--pre-commit",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "rekey-and-precommit-conflict"


# ---------------------------------------------------------------------------
# find_clean_precommit_entry_for_paths — the AA-0064 hint lookup itself
# (pure ledger read; precommit_review_gate's wiring of it into the denial
# message is covered in test_precommit_review_gate.py).
# ---------------------------------------------------------------------------


def test_find_clean_precommit_entry_matches_same_paths_set_regardless_of_order(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/x precommit:aaaa1111bbbb2222 clean ts=2026-09-01T00:00:00Z paths=a.py#b.py paths_n=2\n"
    )
    found = rr.find_clean_precommit_entry_for_paths(str(ledger), "/repo/x", ["b.py", "a.py"])
    assert found == "precommit:aaaa1111bbbb2222"


def test_find_clean_precommit_entry_none_when_paths_differ(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/x precommit:aaaa1111bbbb2222 clean ts=2026-09-01T00:00:00Z paths=a.py paths_n=1\n"
    )
    assert rr.find_clean_precommit_entry_for_paths(str(ledger), "/repo/x", ["a.py", "b.py"]) is None


def test_find_clean_precommit_entry_none_when_not_clean(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/x precommit:aaaa1111bbbb2222 blockers:1 ts=2026-09-01T00:00:00Z paths=a.py paths_n=1\n"
    )
    assert rr.find_clean_precommit_entry_for_paths(str(ledger), "/repo/x", ["a.py"]) is None


def test_find_clean_precommit_entry_none_when_repo_differs(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/other precommit:aaaa1111bbbb2222 clean ts=2026-09-01T00:00:00Z paths=a.py paths_n=1\n"
    )
    assert rr.find_clean_precommit_entry_for_paths(str(ledger), "/repo/x", ["a.py"]) is None


def test_find_clean_precommit_entry_most_recent_wins(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/x precommit:aaaa1111bbbb2222 clean ts=2026-09-01T00:00:00Z paths=a.py paths_n=1\n"
        "/repo/x precommit:cccc3333dddd4444 clean ts=2026-09-01T00:00:01Z paths=a.py paths_n=1\n"
    )
    found = rr.find_clean_precommit_entry_for_paths(str(ledger), "/repo/x", ["a.py"])
    assert found == "precommit:cccc3333dddd4444"


# ---------------------------------------------------------------------------
# Item 8 (2026-09-01 fix round): rekey= provenance + carried-forward
# reviewer=/model= identity, so audit_review_attribution.py can tell a
# sanctioned mechanical carry-forward apart from an unattributed clean.
# ---------------------------------------------------------------------------


def test_entry_suffix_emits_rekey_field_only_when_supplied():
    with_rekey = rr._entry_suffix(rekey="precommit:aaaa1111bbbb2222")
    assert "rekey=precommit:aaaa1111bbbb2222" in with_rekey
    without = rr._entry_suffix()
    assert "rekey=" not in without


def test_decide_threads_rekey_field_into_the_ledger_line(sandbox, clean_env, committed_repo):
    d = rr.decide(
        str(committed_repo),
        outcome=rr.OUTCOME_CLEAN,
        head_override="precommit:cccc3333dddd4444",
        paths=["f.txt"],
        rekey="precommit:aaaa1111bbbb2222",
    )
    assert d.status == rr.STATUS_RECORD
    assert "rekey=precommit:aaaa1111bbbb2222" in d.entry


@_requires_git
def test_rekey_cli_carries_forward_reviewer_and_model_and_adds_rekey_field(
    sandbox, clean_env, tmp_path, monkeypatch
):
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    # WS2.4 step 1 (2026-09-20): model= is now DERIVED from spend.jsonl, not
    # trusted from --model -- give this real dispatch identity a real
    # ledger row so the derivation (and therefore --rekey's carry-forward,
    # which is this test's actual point) has something real to join.
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "spend.jsonl").write_text(
        json.dumps({
            "tool_use_id": "toolu_xyz789", "agent_id": "abc123",
            "agent_type": "trust-architect", "model": "claude-opus-5",
        }) + "\n"
    )

    prior_key = prg_mod.pending_key(str(repo), str(repo), ["new_module.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py",
        "--reviewer", "trust-architect",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz789",
    ])
    assert rc == 0

    _run_git(repo, "add", "new_module.py")  # digest moves, but same content
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc2 == 0

    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]  # the rekey entry, recorded second
    assert f"rekey={prior_key}" in new_line
    assert "reviewer=trust-architect#abc123#toolu_xyz789" in new_line
    assert "model=opus" in new_line


@_requires_git
def test_rekey_cli_explicit_reviewer_flag_overrides_carry_forward(
    sandbox, clean_env, tmp_path, monkeypatch
):
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), ["new_module.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py", "--reviewer", "trust-architect",
    ])
    assert rc == 0

    _run_git(repo, "add", "new_module.py")
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key,
        "--paths", "new_module.py", "--reviewer", "code-reviewer",
    ])
    assert rc2 == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert "reviewer=code-reviewer" in new_line
    assert "trust-architect" not in new_line


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4, R7-B1 (cold trust-architect review): --pre-commit and
# --rekey stamp a digest-format version field (`dg=2`) on every NEW entry
# they write, and --rekey REFUSES unless the chain ROOT it is building on
# already carries `dg=2` -- a ledger line recorded before the R6-B1 fix
# existed (`precommit_review_gate._digest_safe_name`'s control-character-
# safe rendering) carries no `dg=` field at all and cannot be trusted as a
# safe rekey source, closing the hole where an old-format digest could not
# distinguish a single oddly-named reviewed entry from fabricated content
# that happens to reconstruct identically under the OLD (pre-fix) rendering.
# ---------------------------------------------------------------------------


@_requires_git
def test_precommit_stamps_dg2_on_new_entry(sandbox, clean_env, tmp_path, monkeypatch):
    """A fresh --pre-commit --clean recording carries dg=2 -- the digest was
    computed via prg.pending_key's current (R6-B1-fixed) rendering."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert "dg=2" in new_line


@_requires_git
def test_rekey_refuses_when_chain_root_has_no_dg_field(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """A pre-FIXED4-shaped ledger line (no dg= field at all -- exactly what
    every entry recorded before the R6-B1 fix existed looks like) is refused
    as a --rekey chain root. This is the direct regression test for R7-B1:
    without the dg=2 requirement, this call would succeed (see
    test_rekey_accepts_when_chain_root_has_dg2 for its accepting twin)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    import precommit_review_gate as prg_mod

    root = str(repo)
    prior_key = prg_mod.pending_key(root, str(repo), ["new_module.py"])

    # Hand-write a PRE-FIXED4-shaped clean entry: outcome + paths= telemetry,
    # but NO dg= field -- exactly what a real entry recorded before this fix
    # existed looks like (paths= predates dg= by weeks; dg= is the newest
    # field this ledger format has ever grown).
    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {prior_key} clean paths=new_module.py paths_n=1\n"
    )

    _run_git(repo, "add", "new_module.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc == 0  # no-op exit code -- record_review never errors, it refuses to record
    text = sandbox.last_reviewed.read_text()
    # Nothing new was appended: still exactly the one hand-written line.
    assert text.strip().splitlines() == [
        f"{root} {prior_key} clean paths=new_module.py paths_n=1"
    ]


@_requires_git
def test_rekey_accepts_when_chain_root_has_dg2(sandbox, clean_env, tmp_path, monkeypatch):
    """The new-format twin of test_rekey_refuses_when_chain_root_has_no_dg_field:
    the IDENTICAL ledger line, but with dg=2 present, accepts the rekey."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    import precommit_review_gate as prg_mod

    root = str(repo)
    prior_key = prg_mod.pending_key(root, str(repo), ["new_module.py"])

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {prior_key} clean paths=new_module.py paths_n=1 dg=2\n"
    )

    _run_git(repo, "add", "new_module.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    lines = text.strip().splitlines()
    assert len(lines) == 2  # the rekey entry was appended
    new_line = lines[-1]
    assert f"rekey={prior_key}" in new_line
    assert "dg=2" in new_line  # the rekey's own new entry is itself a safe future root


@_requires_git
def test_rekey_new_entry_carries_dg2_forward(sandbox, clean_env, tmp_path, monkeypatch):
    """A successful --rekey's own newly-written entry carries dg=2 -- proof
    it is itself a safe future chain root (its content was reconstructed via
    prg.rekey_digest_if_only_untracked_became_staged, which uses the same
    current, R6-B1-fixed rendering --pre-commit uses)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), ["new_module.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py",
    ])
    assert rc == 0

    _run_git(repo, "add", "new_module.py")  # digest moves, but same content
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc2 == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert "dg=2" in new_line


@_requires_git
def test_rekey_chain_two_hops_refuses_when_true_root_has_no_dg_field(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """R7-B1 applies through the chain-root resolution hop too: when a
    --rekey's cited prior entry is ITSELF a rekey entry (one hop), the dg=2
    check applies to the resolved TRUE root, not the cited intermediate
    entry -- a mixed-vintage chain (root recorded before this fix with no
    dg=, intermediate rekeyed after and carrying its own dg=2) still
    refuses, because root resolution walks to the TRUE root's own fields
    (see main()'s --rekey branch: `prior_fields = root_fields`) before the
    dg=2 check ever runs -- the intermediate's own dg=2 is never what gets
    checked for a one-hop chain.

    The intermediate's own digest is a REAL, independently reconstructable
    one (a second untracked file, reviewed once, then staged) -- the
    intermediate/root relationship is a hand-written `rekey=` pointer (as it
    would be after a real chained --rekey), but the digest each key names is
    genuinely real and reproducible, so the eventual --rekey call reaches
    the actual dg=2 chain-root check rather than refusing early for an
    unrelated reason (an unresolvable/fabricated key, or a byte-mismatch)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "root_file.py").write_text("root content\n")

    import precommit_review_gate as prg_mod

    root = str(repo)
    # The TRUE root's own real digest (root_file.py untracked, reviewed).
    true_root_key = prg_mod.pending_key(root, str(repo), ["root_file.py"])

    # The intermediate hop covers a DIFFERENT path (intermediate_file.py),
    # standing in for "whatever the intermediate rekey call was actually
    # about" -- what matters for this test is only that (a) its digest is
    # real/reconstructable and (b) it names true_root_key via rekey=,
    # exactly the shape main()'s own root-resolution walk produces.
    (repo / "intermediate_file.py").write_text("intermediate content\n")
    intermediate_key = prg_mod.pending_key(root, str(repo), ["intermediate_file.py"])

    # NIT 7's own (unaffected-by-this-fix) paths= comparison runs against
    # the RESOLVED ROOT's recorded paths= -- naming intermediate_file.py
    # there too (rather than root_file.py, which is what the root's REAL
    # digest was actually taken over) isolates this test to the dg=2 check
    # alone; NIT 7's own behavior is covered separately by the tests above.
    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {true_root_key} clean paths=intermediate_file.py paths_n=1\n"
        f"{root} {intermediate_key} clean paths=intermediate_file.py paths_n=1"
        f" rekey={true_root_key} dg=2\n"
    )

    # Stage intermediate_file.py -- untracked -> staged, same content, so
    # the reconstruction against intermediate_key's own digest succeeds
    # (this is what proves the refusal below is the dg=2 chain-root check,
    # not an incidental byte mismatch).
    _run_git(repo, "add", "intermediate_file.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--rekey", intermediate_key,
        "--paths", "intermediate_file.py",
    ])
    assert rc == 0  # refuses (no-op), never errors
    text = sandbox.last_reviewed.read_text()
    # Nothing new appended -- still exactly the two hand-written lines.
    assert len(text.strip().splitlines()) == 2


@_requires_git
@pytest.mark.parametrize("stale_dg_value", ["1", "3"])
def test_rekey_refuses_when_chain_root_dg_field_present_but_not_current_version(
    sandbox, clean_env, tmp_path, monkeypatch, stale_dg_value
):
    """N2 (GH #5886 fix-round-8, round-8 cold review): the R7-B1 chain-root
    check must be an EQUALITY check against `_DIGEST_FORMAT_VERSION` ("2"),
    never a mere PRESENCE check for a `dg=` field. A presence-only check
    (e.g. `"dg" not in prior_fields` instead of `prior_fields.get("dg") !=
    _DIGEST_FORMAT_VERSION`) would accept a chain root carrying `dg=1` or
    `dg=3` exactly as readily as a genuine `dg=2` root, defeating the whole
    point of R7-B1: a `dg=` value that is present but NOT the current format
    version is exactly as untrustworthy as no `dg=` field at all (an older
    or a hypothetical future rendering, neither of which this fix can prove
    reconstructs the same way `precommit_review_gate.pending_key` does
    today), and must refuse identically to
    test_rekey_refuses_when_chain_root_has_no_dg_field's own no-field case.
    A presence-only mutant of the real check passes every other test in this
    module (549 at last count) while silently accepting this repro -- this
    test is what turns that mutant RED."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    import precommit_review_gate as prg_mod

    root = str(repo)
    prior_key = prg_mod.pending_key(root, str(repo), ["new_module.py"])

    # A ledger line carrying a `dg=` field that IS present but is NOT the
    # current digest-format version -- the shape a presence-only check would
    # wrongly treat as safe.
    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root} {prior_key} clean paths=new_module.py paths_n=1 dg={stale_dg_value}\n"
    )

    _run_git(repo, "add", "new_module.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc == 0  # no-op exit code -- record_review never errors, it refuses to record
    text = sandbox.last_reviewed.read_text()
    # Nothing new was appended -- still exactly the one hand-written line.
    assert text.strip().splitlines() == [
        f"{root} {prior_key} clean paths=new_module.py paths_n=1 dg={stale_dg_value}"
    ]


# ---------------------------------------------------------------------------
# NIT 7 (2026-09-23 round-2 review, defense in depth): --rekey refuses when
# the prior entry's own `paths=` telemetry field disagrees with the CURRENT
# `--paths` given to --rekey itself, order-independent. When the prior entry
# carries no `paths=` field at all (an older, pre-telemetry ledger line),
# today's behavior is unchanged (not checked here).
# ---------------------------------------------------------------------------


@_requires_git
def test_rekey_refuses_when_current_paths_disagree_with_prior_recorded_paths(
    sandbox, clean_env, tmp_path, monkeypatch
):
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")
    (repo / "other.py").write_text("y = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), ["new_module.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py",
    ])
    assert rc == 0
    before_text = sandbox.last_reviewed.read_text()

    _run_git(repo, "add", "new_module.py")
    # Cite the review of new_module.py's key, but rekey with a DIFFERENT
    # --paths set (other.py, never reviewed at all).
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "other.py",
    ])
    assert rc2 == 0  # never crashes; refusal is a printed message
    assert sandbox.last_reviewed.read_text() == before_text  # nothing written

    # And the gate for other.py must still demand review -- untouched by the
    # refused rekey attempt.
    key_other = prg_mod.pending_key(str(repo), str(repo), ["other.py"])
    assert key_other is not None
    outcome = rr.head_review_outcome(str(sandbox.last_reviewed), str(repo), key_other)
    assert outcome is None


@_requires_git
def test_rekey_paths_mismatch_positive_twin_same_paths_accepts(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Twin: citing the SAME --paths set (order-shuffled) as the original
    review must still succeed -- this check is order-independent, not a
    stricter literal-string match."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "a_new.py").write_text("a = 1\n")
    (repo / "b_new.py").write_text("b = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), ["a_new.py", "b_new.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "a_new.py", "b_new.py",
    ])
    assert rc == 0

    _run_git(repo, "add", "a_new.py", "b_new.py")
    # Same set, different ORDER on the command line.
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key,
        "--paths", "b_new.py", "a_new.py",
    ])
    assert rc2 == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert f"rekey={prior_key}" in new_line


@_requires_git
def test_rekey_paths_mismatch_check_skipped_when_prior_entry_has_no_paths_field(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """A ledger line recorded before the `paths=` telemetry field existed
    carries no `paths=` at all -- NIT 7's check must not fire for it (nothing
    to compare against), preserving today's behavior for old entries. It
    DOES carry `dg=2` here (GH #5886 fix-round-4, R7-B1 requires a current-
    format chain root; see test_rekey_refuses_when_chain_root_has_no_dg_field
    for the pre-R7-B1-shaped case this test used to conflate with the
    no-paths= behavior it actually means to cover)."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")

    import precommit_review_gate as prg_mod

    root = str(repo)
    prior_key = prg_mod.pending_key(root, str(repo), ["new_module.py"])

    # Hand-write a dg=2 clean entry with no paths= field at all (a
    # current-digest-format entry recorded before the paths= telemetry
    # field existed).
    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(f"{root} {prior_key} clean dg=2\n")

    _run_git(repo, "add", "new_module.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    rc = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert f"rekey={prior_key}" in new_line


@_requires_git
def test_rekey_paths_mismatch_accepts_honest_rekey_of_thirteen_paths(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """GH #5886 fix-round-3 BLOCKER B2 (cold review): the ledger's own
    `paths=` field keeps at most 12 entries (`_MAX_PATHS_IN_FIELD`), so the
    ORIGINAL version of NIT 7's check -- exact-set equality between the
    (truncated-to-12) stored `paths=` and the CURRENT full --paths set --
    refused every honest rekey of 13 or more paths outright, since a
    truncated historical record can never equal a complete current one.

    This reproduces exactly that shape: 13 files reviewed together while
    untracked, then all 13 staged with byte-identical content and rekeyed
    with the identical 13-path --paths list. Includes one UNCHANGED,
    already-committed file (`base.txt`) in the reviewed set specifically so
    the underlying byte-identical reconstruction itself can succeed (a
    directory/glob pathspec is NOT used here, and every one of the 13 paths
    is genuinely byte-identical between review and rekey) -- isolation here
    is BY CONSTRUCTION of the setup, not by a separate assertion that
    disables the paths-mismatch check at runtime: if this test passes, the
    only way it could have refused for an unrelated reason is the byte-
    identity/mode checks, and this setup is deliberately shaped so those
    checks succeed regardless of whether the paths-mismatch fix is present.
    The actual falsifiability proof that this fix matters lives in the
    RED/GREEN verification against a scratch copy of `record_review.py`
    with the pre-fix exact-equality comparison restored (see the fix-round-3
    report), not in an in-test assertion.
    """
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")

    many = [f"f{i}.py" for i in range(12)]  # 12 new + base.txt = 13 total paths
    for name in many:
        (repo / name).write_text(f"# {name}\n")
    all_paths = ["base.txt", *many]

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), all_paths)
    assert prior_key and prior_key != prg_mod.UNRESOLVABLE
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", *all_paths,
    ])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "paths_n=13" in line
    paths_tok = [t for t in line.split() if t.startswith("paths=")][0]
    stored = paths_tok[len("paths="):].split("#")
    assert len(stored) == 12  # confirms the field really is truncated at 12

    _run_git(repo, "add", *many)  # stage all 12 new files, byte-identical content

    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", *all_paths,
    ])
    assert rc2 == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert f"rekey={prior_key}" in new_line, (
        "an honest 13-path rekey was wrongly refused by the truncated paths= "
        f"comparison -- ledger tail: {text.strip().splitlines()[-3:]}"
    )


@_requires_git
def test_rekey_paths_mismatch_refuses_extra_path_smuggled_past_truncated_subset_check(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Falsifiability control for B2's fix: a naive SUBSET-only check (drop
    the `len(current_path_set) != prior_paths_n` half) would let a CURRENT
    --paths set that is a strict SUPERSET of the truncated stored 12 pass
    silently, as long as the extra path is a subset match -- i.e. citing the
    original review's key while smuggling in one extra path alongside the
    honest 13.

    The extra path here (`innocuous_extra.py`) is deliberately an ALREADY-
    COMMITTED, UNCHANGED file -- it contributes NOTHING to the reconstructed
    diff whether or not it's named in --paths, so the underlying byte-
    identical reconstruction succeeds either way and CANNOT be what refuses
    this on its own. Only the paths-mismatch check's own count comparison
    (`len(current_path_set) != prior_paths_n`) can catch this specific
    smuggling shape -- proven by patching that half of the check away in a
    scratch copy of this module and confirming THIS exact test then wrongly
    accepts (writes a `rekey=` ledger entry) where the real fix refuses."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    # Committed UNCHANGED alongside base.txt -- stays byte-identical for the
    # rest of the test, so naming it in --paths contributes zero diff.
    (repo / "innocuous_extra.py").write_text("innocuous = 1\n")
    _run_git(repo, "add", "base.txt", "innocuous_extra.py")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt", "innocuous_extra.py")

    many = [f"f{i}.py" for i in range(12)]
    for name in many:
        (repo / name).write_text(f"# {name}\n")
    all_paths = ["base.txt", *many]

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    import precommit_review_gate as prg_mod

    prior_key = prg_mod.pending_key(str(repo), str(repo), all_paths)
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", *all_paths,
    ])
    assert rc == 0
    before_text = sandbox.last_reviewed.read_text()

    _run_git(repo, "add", *many)
    # innocuous_extra.py is NOT re-staged/re-edited -- it stays exactly as
    # committed. Naming it in --paths alongside the honest 13 is a pure
    # paths-set smuggling attempt with zero content-level signal.
    extra_paths = [*all_paths, "innocuous_extra.py"]

    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", *extra_paths,
    ])
    assert rc2 == 0  # never crashes; refusal is a printed message
    assert sandbox.last_reviewed.read_text() == before_text, (
        "an extra, never-reviewed path was wrongly smuggled through a "
        "truncated-paths rekey"
    )


# ---------------------------------------------------------------------------
# Item 18 (2026-09-01 fix round): --rekey + --clean/--blockers is a loud,
# mutually-exclusive refusal, mirroring the --pre-commit conflict check.
# ---------------------------------------------------------------------------


@_requires_git
def test_rekey_conflicts_with_clean_flag(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--rekey", key, "--clean",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "rekey-and-outcome-flag-conflict"


@_requires_git
def test_rekey_conflicts_with_blockers_flag(sandbox, clean_env, committed_repo, monkeypatch):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--rekey", key, "--blockers", "2",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "rekey-and-outcome-flag-conflict"


# ---------------------------------------------------------------------------
# --correct-identity (#5133): corrects ONLY the reviewer= identity on an
# EXISTING ledger entry, appending a correction line rather than mutating the
# original in place. Falsifiability: `test_falsifiability_reproduces_the_bug`
# below reproduces the EXACT pre-fix failure (a corrective re-record of the
# same digest is refused, "already recorded") as its own RED assertion,
# proving the rest of this section's GREEN assertions are testing something
# that was genuinely broken, not a vacuous no-op.
# ---------------------------------------------------------------------------


def _record_precommit_clean(repo, *, agent_id, tool_use_id, reviewer="code-reviewer"):
    """Helper: record a --pre-commit --clean review with a full compound
    identity for whatever content is currently pending in `repo` for
    "f.txt". Returns the digest key. Caller owns stdin/CSA_ENFORCE setup."""
    key = prg.pending_key(str(repo), str(repo), ["f.txt"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", reviewer,
        "--reviewer-agent-id", agent_id,
        "--reviewer-tool-use-id", tool_use_id,
    ])
    assert rc == 0
    return key


@_requires_git
def test_falsifiability_reproduces_the_bug_already_recorded_refuses_correction(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """RED: this is the EXACT pre-fix failure mode from #5133 -- a
    corrective re-record of the SAME digest with a corrected identity is
    refused as 'already recorded' (STATUS_ALREADY), with no way to fix a
    mistyped --reviewer-tool-use-id short of --correct-identity. Proves the
    defect this whole section exists to fix is real, not assumed."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")

    # A corrective re-record of the SAME digest, with the corrected id, is
    # refused -- this is the bug. rc is still 0 (never raises) but nothing
    # new is written.
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # nothing new was recorded
    assert "toolu_WRONG" in lines[0]
    assert "toolu_RIGHT" not in lines[0]
    assert _last_log(sandbox)["decision"] == "already"


@_requires_git
def test_correct_identity_happy_path_appends_not_overwrites(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """GREEN: --correct-identity fixes the exact scenario above. The
    ORIGINAL (wrong) line stays on record -- APPENDED, never rewritten in
    place -- and the new line carries the corrected identity plus a
    corrects_from= audit trail of the old value."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")

    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2  # original PRESERVED, correction APPENDED
    assert "toolu_WRONG" in lines[0]
    assert "toolu_RIGHT" in lines[1]
    assert "corrects_from=code-reviewer#a68b87b7b2aa02cf6#toolu_WRONG" in lines[1]

    # Last-wins: every real consumer of this ledger now resolves the
    # CORRECTED identity.
    identity = rr.head_review_reviewer_identity(str(sandbox.last_reviewed), str(repo), key)
    assert identity["tool_use_id"] == "toolu_RIGHT"

    assert _last_log(sandbox)["decision"] == "corrected-identity"


@_requires_git
def test_correct_identity_log_only_exits_nonzero_and_appends_nothing(
    sandbox, clean_env, tmp_path, monkeypatch, capsys
):
    """LOG-ONLY: --correct-identity is a write request that was skipped, so it prints the
    would-correct line, says NOT corrected on stderr, exits 1, and leaves the ledger
    untouched. Pair: the SAME call with enforcement on appends the correction and exits 0."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")
    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    before = sandbox.last_reviewed.read_text()
    argv = [
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ]

    clean_env.delenv("CSA_ENFORCE", raising=False)
    capsys.readouterr()
    rc = rr.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert "(LOG-ONLY) would correct reviewer identity" in captured.out
    assert "corrected reviewer identity" not in captured.out
    assert (
        "NOT corrected (log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"
        in captured.err
    )
    assert sandbox.last_reviewed.read_text() == before
    assert _last_log(sandbox)["decision"] == "would-correct-identity"

    clean_env.setenv("CSA_ENFORCE", "1")
    assert rr.main(argv) == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2
    assert "toolu_RIGHT" in lines[1]
    assert _last_log(sandbox)["decision"] == "corrected-identity"


@_requires_git
def test_correct_identity_gate_allows_after_correction(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """The precommit_review_gate consumer (gate 3b) still parses a ledger
    containing a correction entry correctly: it allows BOTH before AND
    after the correction (gate 3b never checks identity itself -- a
    wrong-identity `clean` entry is still a real recorded review, so
    'still allowed' alone can never distinguish a working correction from
    a silently-failed one). The falsifying assertion here is the RESOLVED
    IDENTITY the gate's own read helper produces after the correction --
    proving the gate-facing consumer genuinely picks up the corrected
    value via last-wins, not merely that the boolean allow/deny outcome
    happens to be unaffected either way."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    real_root = rr._git(str(repo), "rev-parse", "--show-toplevel")
    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")

    block0, reason0, _ = prg.decide(real_root, str(repo), ["f.txt"])
    assert block0 is False
    identity0 = rr.head_review_reviewer_identity(str(sandbox.last_reviewed), real_root, key)
    assert identity0["tool_use_id"] == "toolu_WRONG"

    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0

    block1, reason1, _ = prg.decide(real_root, str(repo), ["f.txt"])
    assert block1 is False  # still allowed after the correction
    # The falsifying assertion: the gate-facing read now resolves the
    # CORRECTED identity, not the original wrong one -- this fails against
    # a silently-broken --correct-identity (argv rejected, nothing
    # appended) even though block1 alone would not catch it.
    identity1 = rr.head_review_reviewer_identity(str(sandbox.last_reviewed), real_root, key)
    assert identity1["tool_use_id"] == "toolu_RIGHT"


@_requires_git
def test_correct_identity_gate_still_denies_for_a_digest_with_no_entry(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Negative control for the gate-consumer test above: a digest that was
    NEVER recorded at all is still correctly denied -- --correct-identity
    existing elsewhere in the ledger must never accidentally satisfy the
    gate for an unrelated, genuinely-unreviewed digest."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    (repo / "g.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt", "g.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt", "g.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")
    (repo / "g.txt").write_text("also changed\n")
    _run_git(repo, "add", "g.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    real_root = rr._git(str(repo), "rev-parse", "--show-toplevel")
    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0

    # g.txt was never reviewed at all -- still denied.
    block, reason, _ = prg.decide(real_root, str(repo), ["g.txt"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


@_requires_git
def test_correct_identity_refuses_when_no_entry_exists_for_the_key(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "correct-identity-no-prior-entry"


@_requires_git
def test_correct_identity_rejects_malformed_key_shape(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", "not-a-real-key",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc == 0
    assert not sandbox.last_reviewed.exists()
    assert _last_log(sandbox)["decision"] == "correct-identity-invalid-key"


@_requires_git
def test_correct_identity_rejects_a_truncated_digest(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", "precommit:29",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-invalid-key"


@_requires_git
def test_correct_identity_requires_a_new_reviewer_value(
    sandbox, clean_env, tmp_path, monkeypatch
):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main(["record_review.py", str(repo), "--correct-identity", key])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-no-new-reviewer"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


@_requires_git
def test_correct_identity_refuses_outcome_change_via_clean_flag(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Requirement (b): --correct-identity must never change the recorded
    OUTCOME -- --clean/--blockers alongside it is refused loudly, exactly
    like --rekey's own identical mutual-exclusion check."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key, "--clean",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-outcome-flag-conflict"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


@_requires_git
def test_correct_identity_refuses_outcome_change_via_blockers_flag(
    sandbox, clean_env, tmp_path, monkeypatch
):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key, "--blockers", "2",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-outcome-flag-conflict"


@_requires_git
def test_correct_identity_conflicts_with_pre_commit_mode(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--pre-commit", "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-conflicting-mode"


@_requires_git
def test_correct_identity_conflicts_with_rekey_mode(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    key = "precommit:" + "a" * 16
    other_key = "precommit:" + "b" * 16
    rc = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--rekey", other_key, "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-conflicting-mode"


@_requires_git
def test_correct_identity_idempotent_noop_when_identity_unchanged(
    sandbox, clean_env, tmp_path, monkeypatch
):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_SAME")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_SAME",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-no-change"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # nothing appended


@_requires_git
def test_correct_identity_never_touches_outcome_paths_or_other_fields(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Requirement (b), proven at the byte level: every OTHER telemetry
    field (ts=, tier=, paths=, paths_n=) on the corrected line is IDENTICAL
    to the original line -- only reviewer= differs, plus the new
    corrects_from= field."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    original_fields = rr.parse_ledger_fields(lines[0].split(key, 1)[1].strip())
    corrected_fields = rr.parse_ledger_fields(lines[1].split(key, 1)[1].strip())

    for field in ("ts", "tier", "paths", "paths_n"):
        assert original_fields.get(field) == corrected_fields.get(field), field

    assert original_fields["reviewer"] != corrected_fields["reviewer"]
    assert corrected_fields["corrects_from"] == original_fields["reviewer"]

    # the outcome word itself (before any k=v field) is untouched too.
    original_outcome = lines[0].split(key, 1)[1].strip().split()[0]
    corrected_outcome = lines[1].split(key, 1)[1].strip().split()[0]
    assert original_outcome == corrected_outcome == "clean"


def test_rebuild_corrected_token_preserves_every_other_field_byte_for_byte():
    tok = rr._rebuild_corrected_token(
        "clean ts=2026-09-01T00:00:00Z tier=high reviewer=code-reviewer#a#toolu_WRONG "
        "paths=f.txt#g.txt paths_n=2 round=3",
        "code-reviewer#a#toolu_RIGHT",
        "code-reviewer#a#toolu_WRONG",
    )
    fields = rr.parse_ledger_fields(tok)
    assert fields["ts"] == "2026-09-01T00:00:00Z"
    assert fields["tier"] == "high"
    assert fields["paths"] == "f.txt#g.txt"
    assert fields["paths_n"] == "2"
    assert fields["round"] == "3"
    assert fields["reviewer"] == "code-reviewer#a#toolu_RIGHT"
    assert fields["corrects_from"] == "code-reviewer#a#toolu_WRONG"
    assert rr.parse_outcome_token(tok) == (rr.OUTCOME_CLEAN, 0)


def test_rebuild_corrected_token_appends_reviewer_when_none_existed():
    tok = rr._rebuild_corrected_token(
        "clean ts=2026-09-01T00:00:00Z",
        "code-reviewer#a#toolu_NEW",
        "(none)",
    )
    fields = rr.parse_ledger_fields(tok)
    assert fields["reviewer"] == "code-reviewer#a#toolu_NEW"
    assert fields["corrects_from"] == "(none)"
    assert rr.parse_outcome_token(tok) == (rr.OUTCOME_CLEAN, 0)


@_requires_git
def test_correct_identity_refuses_a_bare_legacy_entry_with_no_telemetry(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A bare legacy entry (no outcome suffix, no fields at all -- the
    original two-field ``"<repo> <sha>"`` line) has no reviewer= field
    position under this ledger's grammar (parse_ledger_fields always treats
    the FIRST token as the outcome word) -- correcting it is refused
    loudly rather than silently producing a line whose identity would be
    lost on the next parse."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main(["record_review.py", str(committed_repo)])
    assert rc == 0
    head = _git_out(committed_repo, "rev-parse", "HEAD")

    # --correct-identity's accepted key SPELLING mirrors --prev's
    # ("precommit:<digest>" or "sha:<hex>") -- a legacy plain-HEAD entry's
    # REAL on-disk key is the bare, unprefixed sha (see
    # `_ledger_lookup_key`'s own docs for why); the "sha:" form is only the
    # accepted CLI spelling, translated internally before the ledger lookup.
    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", f"sha:{head}",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "abc123",
        "--reviewer-tool-use-id", "toolu_xyz",
    ])
    assert rc2 == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-no-identity-field"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # nothing appended


@_requires_git
def test_correct_identity_works_on_a_legacy_sha_keyed_entry(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A plain (non --pre-commit) --clean recording stores its key as a
    BARE, unprefixed sha (REGRESSION 2's shape -- see `_ledger_lookup_key`),
    not the `sha:`-prefixed spelling `--correct-identity`/`--prev` accept on
    the CLI. Confirms the internal translation actually finds and corrects
    this real on-disk shape, not just the precommit: shape exercised by the
    rest of this section."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_WRONG",
    ])
    assert rc == 0
    head = _git_out(committed_repo, "rev-parse", "HEAD")
    assert sandbox.last_reviewed.read_text().splitlines()[0].split()[1] == head  # unprefixed

    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", f"sha:{head}",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc2 == 0
    assert _last_log(sandbox)["decision"] == "corrected-identity"

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2
    # the corrected line is written at the SAME bare (unprefixed) key, not
    # the "sha:"-prefixed CLI spelling -- or no real consumer would ever
    # find it.
    assert lines[1].split()[1] == head
    assert "toolu_RIGHT" in lines[1]

    identity = rr.head_review_reviewer_identity(str(sandbox.last_reviewed), str(committed_repo), head)
    assert identity["tool_use_id"] == "toolu_RIGHT"


# ---------------------------------------------------------------------------
# BLOCKER 2 (2026-09-09 fix round, #5133 trust-architect review):
# corrections used to inherit ts= byte-for-byte, so nothing recorded WHEN a
# correction happened -- corrected_at= is the fix.
# ---------------------------------------------------------------------------


def test_rebuild_corrected_token_adds_corrected_at_as_a_sibling_of_ts():
    """RED-baseline-adjacent: corrected_at is a NEW sibling field -- ts= is
    NEVER touched (the byte-fidelity guarantee holds even with
    corrected_at supplied)."""
    tok = rr._rebuild_corrected_token(
        "clean ts=2026-09-01T00:00:00Z tier=high reviewer=code-reviewer#a#toolu_WRONG",
        "code-reviewer#a#toolu_RIGHT",
        "code-reviewer#a#toolu_WRONG",
        "2026-09-09T12:00:00Z",
    )
    fields = rr.parse_ledger_fields(tok)
    assert fields["ts"] == "2026-09-01T00:00:00Z"  # UNCHANGED -- original dispatch time
    assert fields["corrected_at"] == "2026-09-09T12:00:00Z"
    assert fields["reviewer"] == "code-reviewer#a#toolu_RIGHT"
    assert fields["corrects_from"] == "code-reviewer#a#toolu_WRONG"


def test_rebuild_corrected_token_omits_corrected_at_when_not_supplied():
    """corrected_at is OPTIONAL -- every non-`--correct-identity` caller of
    this function (there are none today, but the contract matters) sees no
    behavior change when it's simply not passed."""
    tok = rr._rebuild_corrected_token(
        "clean ts=2026-09-01T00:00:00Z",
        "code-reviewer#a#toolu_NEW",
        "(none)",
    )
    fields = rr.parse_ledger_fields(tok)
    assert "corrected_at" not in fields


@_requires_git
def test_correct_identity_writes_a_corrected_at_distinct_from_original_ts(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """GREEN, at the full main() level: the corrected line carries a fresh
    corrected_at= while its ts= stays byte-identical to the original entry's
    ts= -- proving the write path (not just the pure helper) wires this
    through correctly."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    original_fields = rr.parse_ledger_fields(lines[0].split(key, 1)[1].strip())
    corrected_fields = rr.parse_ledger_fields(lines[1].split(key, 1)[1].strip())

    # ts= is byte-identical (the original review's own dispatch time).
    assert original_fields["ts"] == corrected_fields["ts"]
    # corrected_at= exists ONLY on the corrected line, and is a real,
    # well-formed UTC ISO8601 timestamp distinct from the original ts=.
    assert "corrected_at" not in original_fields
    assert "corrected_at" in corrected_fields
    import datetime as _dt

    parsed = _dt.datetime.strptime(corrected_fields["corrected_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.tzinfo is None  # naive parse of a "Z"-suffixed UTC stamp -- just proves it parses


# ---------------------------------------------------------------------------
# F4 (2026-09-09 fix round, #5133): --warm/--round/--prev/--paths/--model
# are refused LOUDLY alongside --correct-identity -- they used to be
# accepted silently with zero effect.
# ---------------------------------------------------------------------------


@_requires_git
def test_correct_identity_refuses_warm_flag(sandbox, clean_env, tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    prior_key = "precommit:" + "c" * 16
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
        "--warm", "--prev", prior_key, "--round", "2",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-inert-flag"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # nothing appended


@_requires_git
def test_correct_identity_refuses_round_flag_alone(sandbox, clean_env, tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
        "--round", "2",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-inert-flag"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


@_requires_git
def test_correct_identity_refuses_prev_flag(sandbox, clean_env, tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    prior_key = "precommit:" + "c" * 16
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
        "--prev", prior_key, "--round", "1",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-inert-flag"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


@_requires_git
def test_correct_identity_refuses_paths_flag(sandbox, clean_env, tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
        "--paths", "f.txt",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-inert-flag"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


@_requires_git
def test_correct_identity_refuses_model_flag(sandbox, clean_env, tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG")
    rc = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
        "--model", "opus",
    ])
    assert rc == 0
    assert _last_log(sandbox)["decision"] == "correct-identity-inert-flag"
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# F5 (2026-09-09 fix round, #5133): correcting an ALREADY-corrected line
# used to append a DUPLICATE corrects_from= (and would have duplicated
# corrected_at= too) -- last-wins parsing silently dropped the first from
# every structured reader's view. Fixed by REPLACING in place.
# ---------------------------------------------------------------------------


@_requires_git
def test_correct_identity_twice_replaces_corrects_from_in_place_not_duplicates(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """RED-baseline-adjacent (falsifiability via direct field count): a
    SECOND correction of the same key must leave exactly ONE corrects_from=
    token (and ONE corrected_at=) on the final line -- not two. Before the
    fix, `_rebuild_corrected_token` always APPENDED, so a second correction
    produced two `corrects_from=` tokens on the same line; `split()`-based
    counting below would catch that directly."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("base\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "f.txt")
    (repo / "f.txt").write_text("changed\n")
    _run_git(repo, "add", "f.txt")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    key = _record_precommit_clean(repo, agent_id="a68b87b7b2aa02cf6", tool_use_id="toolu_WRONG1")

    rc1 = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_WRONG2",
    ])
    assert rc1 == 0

    rc2 = rr.main([
        "record_review.py", str(repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "a68b87b7b2aa02cf6",
        "--reviewer-tool-use-id", "toolu_RIGHT",
    ])
    assert rc2 == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 3  # original + first correction + second correction

    final_line = lines[2]
    # Exactly ONE corrects_from= token and ONE corrected_at= token on the
    # final line -- a literal count of raw whitespace-split tokens starting
    # with each prefix, independent of parse_ledger_fields's own last-wins
    # behavior (which would mask a duplicate).
    tokens = final_line.split()
    corrects_from_tokens = [t for t in tokens if t.startswith("corrects_from=")]
    corrected_at_tokens = [t for t in tokens if t.startswith("corrected_at=")]
    assert len(corrects_from_tokens) == 1, tokens
    assert len(corrected_at_tokens) == 1, tokens

    # The single corrects_from= names the IMMEDIATELY PRIOR reviewer= value
    # (toolu_WRONG2, the first correction's identity) -- not the original
    # (toolu_WRONG1). The full chain is still reconstructable by walking
    # the ledger's own three successive lines for this key.
    final_fields = rr.parse_ledger_fields(final_line.split(key, 1)[1].strip())
    assert "toolu_WRONG2" in final_fields["corrects_from"]
    assert final_fields["reviewer"].endswith("toolu_RIGHT")

    # Last-wins: the gate-facing read resolves the FINAL (second)
    # correction's identity.
    identity = rr.head_review_reviewer_identity(str(sandbox.last_reviewed), str(repo), key)
    assert identity["tool_use_id"] == "toolu_RIGHT"


# ---------------------------------------------------------------------------
# WS2.4 step 1 (master plan, tracking issue #5828): the REVIEWING MODEL is
# derived from spend.jsonl, never trusted from a self-reported --model, for
# a --pre-commit recording. 14-day warn-only window for a missing/unjoinable
# identity (missing-reviewer-identity logged, record still written).
#
# Falsifiability: `test_falsifiability_pre_fix_module_has_no_derivation` is
# the RED baseline -- it loads HEAD's ACTUAL on-disk record_review.py
# (before this change) from a real scratch copy (never the live file) and
# proves that version has no derive_reviewing_model/normalize_model_tier
# machinery at all, so the joined-model and warn-only-never-refuses
# assertions below are demonstrably exercising something that did not exist
# a moment ago -- not a vacuous, always-passing check.
# ---------------------------------------------------------------------------


def _write_spend_ledger(sandbox, rows):
    """Write `rows` (a list of dicts) as spend.jsonl in the sandboxed
    agent-budget dir. Creates the dir as needed."""
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / "spend.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


class TestNormalizeModelTier:
    def test_opus_family(self):
        assert rr.normalize_model_tier("claude-opus-5[1m]") == "opus"
        assert rr.normalize_model_tier("claude-opus-4-8") == "opus"

    def test_sonnet_family(self):
        assert rr.normalize_model_tier("claude-sonnet-5") == "sonnet"

    def test_haiku_family(self):
        assert rr.normalize_model_tier("claude-haiku-4-5-20251001") == "haiku"

    def test_fable_family(self):
        assert rr.normalize_model_tier("claude-fable-5-1") == "fable"

    def test_bare_tier_word(self):
        assert rr.normalize_model_tier("opus") == "opus"
        assert rr.normalize_model_tier("sonnet") == "sonnet"

    def test_unrecognized_returns_none(self):
        assert rr.normalize_model_tier("gpt-4") is None
        assert rr.normalize_model_tier("garbage") is None

    def test_none_and_non_string_return_none(self):
        assert rr.normalize_model_tier(None) is None
        assert rr.normalize_model_tier(123) is None
        assert rr.normalize_model_tier("") is None


class TestDeriveReviewingModel:
    def test_no_identity_at_all(self, tmp_path):
        result = rr.derive_reviewing_model(str(tmp_path), None, None)
        assert result == rr.ModelDerivation(None, None, "no-identity")

    def test_ledger_missing_file(self, tmp_path):
        result = rr.derive_reviewing_model(str(tmp_path / "nope"), "toolu_A", "a1")
        assert result == rr.ModelDerivation(None, None, "ledger-unreadable")

    def test_joined_row_derives_opus(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        path.write_text(
            json.dumps({
                "tool_use_id": "toolu_A", "agent_id": "a1",
                "agent_type": "code-reviewer", "model": "claude-opus-5[1m]",
            }) + "\n"
        )
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_A", "a1")
        assert result.model == "opus"
        assert result.model_id == "claude-opus-5[1m]"
        assert result.reason == ""

    def test_agent_id_mismatch_on_same_tool_use_id_is_unjoinable(self, tmp_path):
        """A tool_use_id match with a DISAGREEING agent_id is treated as no
        match at all -- the two fields together identify one dispatch."""
        path = tmp_path / "spend.jsonl"
        path.write_text(
            json.dumps({
                "tool_use_id": "toolu_A", "agent_id": "a1",
                "agent_type": "code-reviewer", "model": "claude-opus-5",
            }) + "\n"
        )
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_A", "WRONG_AGENT")
        assert result == rr.ModelDerivation(None, None, "unjoinable")

    def test_no_matching_tool_use_id_is_unjoinable(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        path.write_text(
            json.dumps({
                "tool_use_id": "toolu_OTHER", "agent_id": "a1",
                "agent_type": "code-reviewer", "model": "claude-opus-5",
            }) + "\n"
        )
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_MISSING", "a1")
        assert result == rr.ModelDerivation(None, None, "unjoinable")

    def test_model_requested_fallback_when_model_absent(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        path.write_text(
            json.dumps({
                "tool_use_id": "toolu_A", "agent_id": "a1",
                "agent_type": "code-reviewer", "model_requested": "claude-sonnet-5",
            }) + "\n"
        )
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_A", "a1")
        assert result.model == "sonnet"

    def test_unrecognized_model_string_is_its_own_reason(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        path.write_text(
            json.dumps({
                "tool_use_id": "toolu_A", "agent_id": "a1",
                "agent_type": "code-reviewer", "model": "gpt-4-turbo",
            }) + "\n"
        )
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_A", "a1")
        assert result == rr.ModelDerivation(None, None, "unrecognized-model")

    def test_bounded_scan_finds_a_hit_near_the_end_of_a_huge_ledger(self, tmp_path):
        """The documented bound: a real, recent dispatch's own row is always
        near the END of the file -- a hit within the scan window is found
        without reading the ledger's entire history."""
        path = tmp_path / "spend.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for i in range(5000):
                fh.write(json.dumps({
                    "tool_use_id": f"filler_{i}", "agent_id": "x",
                    "agent_type": "implement", "model": "claude-sonnet-5",
                }) + "\n")
            fh.write(json.dumps({
                "tool_use_id": "toolu_NEAR_END", "agent_id": "a9",
                "agent_type": "trust-architect", "model": "claude-opus-5",
            }) + "\n")
        result = rr.derive_reviewing_model(
            str(tmp_path), "toolu_NEAR_END", "a9", scan_lines=2000
        )
        assert result.model == "opus"

    def test_hit_beyond_the_scan_bound_is_unjoinable(self, tmp_path):
        """Documents the bound's own tradeoff: a real row that exists but
        falls outside the scanned window is reported unjoinable, never a
        false negative silently reported as 'not present' with no reason."""
        path = tmp_path / "spend.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "tool_use_id": "toolu_TOO_EARLY", "agent_id": "a1",
                "agent_type": "code-reviewer", "model": "claude-opus-5",
            }) + "\n")
            for i in range(3000):
                fh.write(json.dumps({
                    "tool_use_id": f"filler_{i}", "agent_id": "x",
                    "agent_type": "implement", "model": "claude-sonnet-5",
                }) + "\n")
        result = rr.derive_reviewing_model(
            str(tmp_path), "toolu_TOO_EARLY", "a1", scan_lines=100
        )
        assert result == rr.ModelDerivation(None, None, "unjoinable")

    def test_never_raises_on_unparseable_lines(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        path.write_text("not json at all\n{}\n[1,2,3]\n")
        result = rr.derive_reviewing_model(str(tmp_path), "toolu_A", "a1")
        assert result == rr.ModelDerivation(None, None, "unjoinable")


@_requires_git
def test_main_precommit_joins_model_from_spend_ledger(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """The falsifiable core of WS2.4 step 1: a real `--pre-commit --clean`
    call whose --reviewer-tool-use-id joins a real spend.jsonl row writes
    model=<derived tier> model_source=ledger to the ledger -- never trusting
    a self-reported --model."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_JOIN1", "agent_id": "agent_join_1",
            "agent_type": "code-reviewer", "model": "claude-opus-5[1m]",
        },
    ])
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_join_1",
        "--reviewer-tool-use-id", "toolu_JOIN1",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "model=opus" in tokens
    assert "model_source=ledger" in tokens
    assert any(t.startswith("model_id=") for t in tokens)
    assert not any(t.startswith("model_declared=") for t in tokens)


@_requires_git
def test_main_precommit_agent_id_mismatch_is_unjoinable_and_warns(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A tool_use_id match with a disagreeing agent_id is treated as
    unjoinable -- the record is still written (warn-only), no model= field
    at all, and missing-reviewer-identity is logged."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_MISMATCH", "agent_id": "real_agent",
            "agent_type": "code-reviewer", "model": "claude-opus-5",
        },
    ])
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "forged_agent",
        "--reviewer-tool-use-id", "toolu_MISMATCH",
    ])
    assert rc == 0
    # WARN ONLY: the record is still written exactly as today.
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "clean" in tokens
    assert not any(t.startswith("model=") for t in tokens)
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    missing = [ln for ln in log_lines if ln["decision"] == "missing-reviewer-identity"]
    assert len(missing) == 1
    assert missing[0]["reason"] == "unjoinable"


@_requires_git
def test_main_precommit_declared_model_disagreeing_with_derived_logs_mismatch(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """--model stays optional and audit-only: when it disagrees with the
    derived value, model-mismatch is logged and the DERIVED value (never
    the declared one) is what gets written as model=."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_MM1", "agent_id": "agent_mm1",
            "agent_type": "code-reviewer", "model": "claude-opus-5",
        },
    ])
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_mm1",
        "--reviewer-tool-use-id", "toolu_MM1",
        "--model", "sonnet",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "model=opus" in tokens  # derived value governs
    assert "model_declared=sonnet" in tokens  # declared value is audit-only
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    mismatches = [ln for ln in log_lines if ln["decision"] == "model-mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0]["declared"] == "sonnet"
    assert mismatches[0]["derived"] == "opus"


@_requires_git
def test_main_precommit_no_identity_writes_record_and_warns(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """No --reviewer-tool-use-id at all: the record is still written
    (warn-only, never refused), with no model= field, and
    missing-reviewer-identity is logged with reason no-identity."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "clean" in tokens
    assert not any(t.startswith("model=") for t in tokens)
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    missing = [ln for ln in log_lines if ln["decision"] == "missing-reviewer-identity"]
    assert len(missing) == 1
    assert missing[0]["reason"] == "no-identity"


@_requires_git
def test_main_precommit_ledger_missing_writes_record_and_warns_ledger_unreadable(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """spend.jsonl absent entirely (never written to the sandbox in this
    test): the record is still written, no model=, and
    missing-reviewer-identity is logged with reason ledger-unreadable --
    never raises, never refuses."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    assert not (sandbox.agent_budget_dir / "spend.jsonl").exists()
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_x",
        "--reviewer-tool-use-id", "toolu_X",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert "clean" in tokens
    assert not any(t.startswith("model=") for t in tokens)
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    missing = [ln for ln in log_lines if ln["decision"] == "missing-reviewer-identity"]
    assert len(missing) == 1
    assert missing[0]["reason"] == "ledger-unreadable"


@_requires_git
def test_main_correct_identity_rederives_model_for_the_new_identity(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Spec item 4: a corrected identity re-derives the model -- the
    corrected line's model= reflects the NEW identity's real dispatch, not
    the original (possibly now-stale) model=."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_OLD", "agent_id": "agent_old",
            "agent_type": "code-reviewer", "model": "claude-sonnet-5",
        },
        {
            "tool_use_id": "toolu_NEW", "agent_id": "agent_new",
            "agent_type": "code-reviewer", "model": "claude-opus-5",
        },
    ])
    rc1 = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_old",
        "--reviewer-tool-use-id", "toolu_OLD",
    ])
    assert rc1 == 0
    first_line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "model=sonnet" in first_line.split()
    key = first_line.split()[1]

    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_new",
        "--reviewer-tool-use-id", "toolu_NEW",
    ])
    assert rc2 == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2
    corrected_tokens = lines[1].split()
    assert "model=opus" in corrected_tokens  # RE-DERIVED, not carried forward
    assert "model_source=ledger" in corrected_tokens


@_requires_git
def test_main_correct_identity_with_no_identity_pair_removes_stale_model(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A correction to a BARE --reviewer type (no agent_id/tool_use_id pair)
    cannot be re-derived -- the now-unverifiable model=/model_source=/
    model_id= fields are removed rather than left stale."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_HAD_MODEL", "agent_id": "agent_had",
            "agent_type": "code-reviewer", "model": "claude-opus-5",
        },
    ])
    rc1 = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_had",
        "--reviewer-tool-use-id", "toolu_HAD_MODEL",
    ])
    assert rc1 == 0
    first_line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "model=opus" in first_line.split()
    key = first_line.split()[1]

    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--reviewer", "trust-architect",
    ])
    assert rc2 == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    corrected_tokens = lines[1].split()
    assert not any(t.startswith("model=") for t in corrected_tokens)
    assert not any(t.startswith("model_source=") for t in corrected_tokens)


@_requires_git
def test_main_rekey_carries_forward_derived_model_and_provenance(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """--rekey carries the ROOT entry's already-derived model=/model_source=
    forward byte-for-byte (it has no --reviewer-tool-use-id of its own to
    join with) -- the rekeyed entry must not look like a fresh, undocumented
    self-reported model=. Mirrors the proven untracked-then-staged shape
    `test_rekey_cli_carries_forward_reviewer_and_model_and_adds_rekey_field`
    already exercises."""
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "new_module.py").write_text("x = 1\n")  # untracked -- reviewed as-is

    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_REKEY_SRC", "agent_id": "agent_rekey",
            "agent_type": "code-reviewer", "model": "claude-opus-5",
        },
    ])
    prior_key = prg.pending_key(str(repo), str(repo), ["new_module.py"])
    rc1 = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean",
        "--paths", "new_module.py",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_rekey",
        "--reviewer-tool-use-id", "toolu_REKEY_SRC",
    ])
    assert rc1 == 0
    lines1 = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines1) == 1
    assert "model=opus" in lines1[0].split()

    _run_git(repo, "add", "new_module.py")  # digest moves, but same content
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
    ])
    assert rc2 == 0
    lines2 = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines2) == 2
    rekeyed_tokens = lines2[1].split()
    assert "model=opus" in rekeyed_tokens
    assert "model_source=ledger" in rekeyed_tokens


@_requires_git
def test_main_precommit_never_raises_when_spend_ledger_is_corrupt(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Never raises on a genuinely corrupt ledger file -- degrades to
    unjoinable/missing-reviewer-identity, exactly like a missing file."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "spend.jsonl").write_text("{{{ not json\n\x00\x01binary garbage")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_x",
        "--reviewer-tool-use-id", "toolu_X",
    ])
    assert rc == 0
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    missing = [ln for ln in log_lines if ln["decision"] == "missing-reviewer-identity"]
    assert len(missing) == 1


# ---------------------------------------------------------------------------
# 2026-09-20 fix round -- regression (finding 2): --correct-identity never
# cleared model_declared=, so it could outlive its own reviewer= identity or
# silently duplicate a re-derived value it no longer disagreed with.
# ---------------------------------------------------------------------------


@_requires_git
def test_main_correct_identity_clears_stale_model_declared_when_bare_reviewer(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Correcting to a BARE --reviewer type (no identity pair) removes a
    PRE-EXISTING model_declared= too, not just model=/model_source=/
    model_id= -- a stale declaration left behind would be the only model
    signal on the corrected line, and it was never true of the corrected
    (identity-less) reviewer= either."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    # No matching spend.jsonl row at all -- the ORIGINAL review derives
    # nothing and falls back to a caller-declared --model, so the entry
    # being corrected genuinely carries model_declared= on record.
    rc1 = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_orig",
        "--reviewer-tool-use-id", "toolu_ORIG",
        "--model", "sonnet",
    ])
    assert rc1 == 0
    first_line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    first_tokens = first_line.split()
    assert "model_declared=sonnet" in first_tokens
    assert not any(t.startswith("model=") for t in first_tokens)
    key = first_tokens[1]

    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--reviewer", "trust-architect",
    ])
    assert rc2 == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2
    corrected_tokens = lines[1].split()
    assert not any(t.startswith("model=") for t in corrected_tokens)
    assert not any(t.startswith("model_source=") for t in corrected_tokens)
    assert not any(t.startswith("model_declared=") for t in corrected_tokens)


@_requires_git
def test_main_correct_identity_clears_model_declared_when_rederived_value_matches(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Correcting to an identity whose DERIVED model happens to equal the
    OLD declaration must never write `model=X model_declared=X` -- the
    "only when it disagreed" invariant is about THIS entry's own derived
    value, and a correction never carries a caller declaration forward at
    all (--model is refused outright alongside --correct-identity)."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    # ORIGINAL entry: caller declared "sonnet" with no derivable identity at
    # all -- model_declared=sonnet is on record, no model=.
    rc1 = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_orig",
        "--reviewer-tool-use-id", "toolu_ORIG",
        "--model", "sonnet",
    ])
    assert rc1 == 0
    first_line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "model_declared=sonnet" in first_line.split()
    key = first_line.split()[1]

    # The CORRECTED identity's real dispatch also happens to be sonnet.
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_CORRECTED", "agent_id": "agent_corrected",
            "agent_type": "code-reviewer", "model": "claude-sonnet-5",
        },
    ])
    rc2 = rr.main([
        "record_review.py", str(committed_repo), "--correct-identity", key,
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_corrected",
        "--reviewer-tool-use-id", "toolu_CORRECTED",
    ])
    assert rc2 == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 2
    corrected_tokens = lines[1].split()
    assert "model=sonnet" in corrected_tokens  # re-derived
    # NEVER model_declared=sonnet alongside it -- a correction carries no
    # caller declaration forward, regardless of what the derived value is.
    assert not any(t.startswith("model_declared=") for t in corrected_tokens)


# ---------------------------------------------------------------------------
# 2026-09-20 fix round -- reviewer-verified-by-hand, now covered by tests.
# ---------------------------------------------------------------------------


@_requires_git
def test_main_precommit_unrecognized_model_string_logs_missing_identity(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """A matched spend.jsonl row whose OWN model string doesn't normalize to
    anything this ledger's vocabulary knows (unrecognized-model) reaches the
    log exactly like every other unjoinable shape -- record still written,
    no model=, reason=unrecognized-model."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")
    _write_spend_ledger(sandbox, [
        {
            "tool_use_id": "toolu_UNREC", "agent_id": "agent_unrec",
            "agent_type": "code-reviewer", "model": "gpt-4-turbo",
        },
    ])
    rc = rr.main([
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
        "--reviewer-agent-id", "agent_unrec",
        "--reviewer-tool-use-id", "toolu_UNREC",
    ])
    assert rc == 0
    tokens = sandbox.last_reviewed.read_text().strip().splitlines()[0].split()
    assert not any(t.startswith("model=") for t in tokens)
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    missing = [ln for ln in log_lines if ln["decision"] == "missing-reviewer-identity"]
    assert len(missing) == 1
    assert missing[0]["reason"] == "unrecognized-model"


@_requires_git
def test_main_precommit_status_already_never_double_logs_missing_identity(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Three IDENTICAL recordings of the same pending content (no identity
    at all, so missing-reviewer-identity would fire on every call that
    actually records something NEW): exactly 1 `recorded`, 2 `already`, and
    -- because only the FIRST call actually records something new -- exactly
    1 `missing-reviewer-identity` line, never 3. This is the SAME
    STATUS_RECORD/STATUS_UPDATE-only gating tier-mismatch already uses,
    applied to missing-reviewer-identity/model-mismatch."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("changed\n")
    _run_git(committed_repo, "add", "f.txt")

    argv = [
        "record_review.py", str(committed_repo), "--pre-commit", "--clean",
        "--paths", "f.txt",
        "--reviewer", "code-reviewer",
    ]
    for _ in range(3):
        rc = rr.main(list(argv))
        assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert len(lines) == 1  # STATUS_UPDATE never fires here -- identical outcome each time

    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    decisions = [ln["decision"] for ln in log_lines if ln.get("hook") == "record_review"]
    assert decisions.count("recorded") == 1
    assert decisions.count("already") == 2
    assert decisions.count("missing-reviewer-identity") == 1


# ---------------------------------------------------------------------------
# WS2.3 (master plan §2.3) -- REVIEW-ROUND CEILING, LOG-ONLY.
#
# derive_review_round() -- the pure ledger-walk that derives a review's
# round number from repo R's OWN history, never trusted from a caller's
# self-declared --round. Mirrors find_clean_precommit_entry_for_paths'
# own test group in style (plain tmp_path ledger files, no git needed for
# the pure-function half); the main()-level wiring (round-mismatch logging,
# the derived value overriding a declared one, and the would-refuse
# tripwire/cap logs) is covered separately below with real git repos.
# ---------------------------------------------------------------------------


def _ledger_line(repo, key, outcome, paths, *, ts="2026-09-21T00:00:00Z"):
    """One `precommit:`-keyed ledger line with a paths= telemetry field --
    the exact shape derive_review_round() reads. `outcome` is the raw
    suffix token ("clean" or "blockers:<n>")."""
    joined = "#".join(paths)
    return f"{repo} precommit:{key} {outcome} ts={ts} paths={joined} paths_n={len(paths)}\n"


def test_derive_review_round_normalizes_path_spellings_identically(tmp_path):
    """B1 regression guard. `file_claims.paths_overlap` is a pure
    string-prefix test, so `--paths` must be NORMALIZED (leading `./`,
    trailing `/`) as well as SANITIZED -- the two are not alternatives, and
    an earlier cut treated them as such.

    Pre-fix, these four spellings of ONE boundary disagreed against the real
    ledger: `hooks/record_review.py` derived round 2 while
    `./hooks/record_review.py` and `hooks/` derived round 1, and
    `stopped_at_clean` came back both True and False for the same directory.
    A silent WRONG round, which would have corrupted by construction the
    7-day observation window that gates enforcement.

    This test exists because the fix shipped WITHOUT one: the full 345-test
    file passed with `fc.normalize_path(...)` removed.

    NOT covered, and deliberately so -- see the module's own note: five
    further spellings (`hooks//x.py`, `hooks/./x.py`, an absolute path,
    `../x/hooks/x.py`, `hooks/../hooks/x.py`) STILL disagree, because
    `normalize_path` does not collapse `//`, resolve `.`/`..`, or
    relativize. They undercount, which is the safe direction under
    LOG-ONLY, and are tracked rather than silently fixed here.
    """
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:1", ["hooks/record_review.py"])
    )
    results = {
        spelling: rr.derive_review_round(str(ledger), "/repo/x", [spelling])
        for spelling in (
            "hooks/record_review.py",
            "./hooks/record_review.py",
            "hooks/",
            "hooks",
        )
    }
    assert all(r == rr.RoundDerivation(2, 1, False) for r in results.values()), results


def test_derive_review_round_normalizes_the_LEDGER_side_too(tmp_path):
    """The normalization must apply to BOTH sides of the comparison.

    Normalizing only the CALLER's paths left the fix half-applied: a ledger
    entry stores whatever spelling its own caller typed (`_paths_field`
    sanitizes but does not normalize), so `paths=./hooks/a.py` was
    unmatchable even by an IDENTICALLY-spelled later call. Measured before
    the fix: all three rows below derived 1 instead of 2.

    Also covers the SANITIZER half, which had zero coverage of its own:
    `my dir/a b.py` must still match a ledger entry written as
    `my_dir/a_b.py`, since `_safe_path_component` maps those characters to
    `_` on the way in.
    """
    cases = [
        ("./hooks/a.py", ["hooks/a.py"]),
        ("./hooks/a.py", ["./hooks/a.py"]),
        ("hooks/", ["hooks/a.py"]),
        ("my_dir/a_b.py", ["my dir/a b.py"]),
    ]
    for entry_spelling, call_paths in cases:
        ledger = tmp_path / f"lr_{abs(hash(entry_spelling + str(call_paths)))}"
        ledger.write_text(
            _ledger_line("/repo/x", "aaaa000000000001", "blockers:1", [entry_spelling])
        )
        result = rr.derive_review_round(str(ledger), "/repo/x", call_paths)
        assert result.derived_round == 2, (entry_spelling, call_paths, result)


def test_derive_review_round_OVERCOUNTS_across_chains_sharing_one_path(tmp_path):
    """Pins the UNSAFE direction, which an earlier docstring denied existed.

    `paths_overlap` is UNION semantics — a call overlaps an entry if ANY
    path matches — so INDEPENDENT chains that merely share one file are
    walked as a single chain. Five unrelated features, each with one
    blockers round, each touching README.md: a brand-new SIXTH feature's
    FIRST review derives round 6 and would log `total-round-cap-would-refuse`.
    Its true round is 1.

    This test asserts the DEFECT, deliberately. It is the honest shape while
    the feature is LOG-ONLY: nothing is refused, so an inflated round only
    pollutes telemetry. When the overcount is fixed before enforcement, THIS
    TEST MUST FAIL and be rewritten to assert 1 — that failure is the signal
    that the fix landed, not a regression. A silent change from 6 to 1 with
    no test movement would mean the fix went in unnoticed and unverified.

    Tracked on #5828.
    """
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "".join(
            _ledger_line(
                "/repo/x", f"aaaa00000000000{i}", "blockers:1", [f"feature{i}.py", "README.md"]
            )
            for i in range(5)
        )
    )
    result = rr.derive_review_round(
        str(ledger), "/repo/x", ["README.md", "brand_new_feature.py"]
    )
    assert result.derived_round == 6, result
    assert result.blockers_found == 5, result


def test_derive_review_round_OVERCOUNTS_from_a_dir_scoped_LEDGER_entry(tmp_path):
    """The overcount is reachable from the RECORDED side too, not only the
    caller's pathspec — the shape an earlier version of the doc missed.

    A directory-scoped pathspec in an EARLIER entry captures every later
    single-file call beneath it. The caller here names ONE brand-new file:
    no shared hot file, no directory in its own pathspec, no multi-path
    commit. None of the caller-side shapes applies, and it still overcounts.

    Live, not latent: the runtime ledger carries 48 distinct
    directory-shaped recorded paths.

    Like its sibling pin, this test asserts the DEFECT deliberately while
    the feature is LOG-ONLY. When the overcount is fixed before enforcement
    it MUST fail and be rewritten to assert 1. Tracked on #5828.
    """
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "".join(
            _ledger_line(
                "/repo/x", f"cccc00000000000{i}", "blockers:1", ["modules/estimate_engine_v3"]
            )
            for i in range(3)
        )
    )
    result = rr.derive_review_round(
        str(ledger), "/repo/x", ["modules/estimate_engine_v3/brand_new_file.py"]
    )
    assert result.derived_round == 4, result
    assert result.blockers_found == 3, result


def test_derive_review_round_fresh_chain_is_round_1(tmp_path):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text("")
    result = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert result.derived_round == 1
    assert result.blockers_found == 0
    assert result.stopped_at_clean is False


def test_derive_review_round_missing_ledger_file_is_round_1(tmp_path):
    ledger = tmp_path / "does_not_exist"
    result = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert result.derived_round == 1


def test_derive_review_round_blockers_then_blockers_then_clean_chain(tmp_path):
    """The task's own required vector: a blockers -> blockers -> clean
    chain on the SAME paths increments the derived round correctly at
    each step, and a call made AFTER the clean entry derives round 1
    again (the chain is closed). derived_round counts --blockers ENTRIES
    (review ROUNDS), never the per-entry finding count n in "blockers:n"
    -- a round that reported 3 findings is still exactly one round, so
    "blockers:3" here counts identically to "blockers:1" would."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:3", ["a.py"], ts="2026-09-21T00:00:00Z")
    )
    # Round 1 was the (unresolved) review that produced this blockers:3
    # entry -- a NEW call on the same paths, walking the ledger as it
    # stands after round 1, must derive round 2 (one blockers ENTRY found,
    # regardless of its own "3" finding count).
    r2 = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert r2.derived_round == 2
    assert r2.blockers_found == 1
    assert r2.stopped_at_clean is False

    # Round 2 also found blockers -- append its own blockers entry and
    # re-derive: round 3 (two blockers entries found).
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(_ledger_line("/repo/x", "bbbb000000000002", "blockers:1", ["a.py"], ts="2026-09-21T00:01:00Z"))
    r3 = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert r3.derived_round == 3
    assert r3.blockers_found == 2
    assert r3.stopped_at_clean is False

    # Round 3 is finally clean -- append it and re-derive: the chain is
    # closed, so a FOURTH call on these same paths derives round 1 again.
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(_ledger_line("/repo/x", "cccc000000000003", "clean", ["a.py"], ts="2026-09-21T00:02:00Z"))
    r4 = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert r4.derived_round == 1
    assert r4.blockers_found == 0
    assert r4.stopped_at_clean is True


def test_derive_review_round_clean_resets_the_chain(tmp_path):
    """A --clean entry covering these paths, followed by an EARLIER-round-
    looking blockers entry that is chronologically AFTER it, must not let
    the pre-clean blocker count leak into the post-clean chain."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:1", ["a.py"], ts="2026-09-21T00:00:00Z")
        + _ledger_line("/repo/x", "bbbb000000000002", "clean", ["a.py"], ts="2026-09-21T00:01:00Z")
    )
    result = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert result.derived_round == 1
    assert result.blockers_found == 0
    assert result.stopped_at_clean is True


def test_derive_review_round_non_overlapping_paths_are_a_different_chain(tmp_path):
    """The task's own required vector: paths that do not overlap the
    ledger's prior blockers entries must NOT be folded into that chain --
    a genuinely disjoint boundary always derives round 1."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:3", ["modules/billing/a.py"])
    )
    result = rr.derive_review_round(str(ledger), "/repo/x", ["modules/voice/b.py"])
    assert result.derived_round == 1
    assert result.blockers_found == 0


def test_derive_review_round_directory_prefix_overlap_counts(tmp_path):
    """paths_overlap is prefix-aware (file_claims's own contract, reused
    verbatim per the task spec) -- a prior blockers entry on a FILE inside
    a directory this call's --paths names must still be found."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:1", ["modules/billing/a.py"])
    )
    result = rr.derive_review_round(str(ledger), "/repo/x", ["modules/billing"])
    assert result.derived_round == 2
    assert result.blockers_found == 1


def test_derive_review_round_scopes_by_repo_root(tmp_path):
    """A blockers entry recorded for a DIFFERENT repo must never be folded
    into this repo's chain, even on identical path strings."""
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/other", "aaaa000000000001", "blockers:5", ["a.py"])
    )
    result = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert result.derived_round == 1


def test_derive_review_round_reuses_file_claims_paths_overlap(tmp_path, monkeypatch):
    """The task's own explicit requirement: overlap MUST reuse
    file_claims.paths_overlap, never a second, independently-written
    comparison. Proven by monkeypatching it and asserting the derivation
    calls through to it rather than silently falling back to some other
    predicate."""
    import file_claims as fc

    calls = []
    real_overlap = fc.paths_overlap

    def _spy(a, b):
        calls.append((frozenset(a), frozenset(b)))
        return real_overlap(a, b)

    monkeypatch.setattr(fc, "paths_overlap", _spy)

    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        _ledger_line("/repo/x", "aaaa000000000001", "blockers:1", ["a.py"])
    )
    rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert len(calls) == 1


def test_derive_review_round_swallows_bad_ledger_and_defaults_to_1(tmp_path, monkeypatch):
    ledger = tmp_path / "last_reviewed"
    ledger.write_text(_ledger_line("/repo/x", "aaaa000000000001", "blockers:1", ["a.py"]))

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(rr, "parse_outcome_token", _boom)
    result = rr.derive_review_round(str(ledger), "/repo/x", ["a.py"])
    assert result == rr.RoundDerivation(1, 0, False)


# ---------------------------------------------------------------------------
# main() wiring: derived round governs, declared!=derived logs
# round-mismatch, and the LOG-ONLY would-refuse tripwire/cap lines at
# round 3 and round 6 -- never a refusal, the commit always still lands.
# ---------------------------------------------------------------------------


@_requires_git
def test_main_precommit_round1_derives_1_with_no_declared_round(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("v1\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert " round=1" in line
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert not any(ln["decision"] == "round-mismatch" for ln in log_lines)
    assert not any("would-refuse" in ln["decision"] for ln in log_lines)


@_requires_git
def test_main_precommit_declared_round_matching_derived_is_not_a_mismatch(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    # A PRIOR blockers entry on the same paths, so the DERIVED round is 2.
    # This shape is the positive control: declaring `--round 2` can only
    # match when the derivation actually ran. A round-1 version of this test
    # was VACUOUS -- it passed identically against reverted source, because
    # pre-change code never emitted `round-mismatch` at all AND already
    # echoed an explicitly-declared `round=1`, so neither assertion could
    # distinguish the two worlds. Caught by a reviewer re-running the
    # falsifiability check instead of trusting the build report, which had
    # claimed all 14 new tests went RED; one had not.
    (committed_repo / "f.txt").write_text("v0\n")
    assert rr.main([
        "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit",
        "--paths", "f.txt",
    ]) == 0
    (committed_repo / "f.txt").write_text("v1\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
        "--round", "2",
    ])
    assert rc == 0
    # The derived value must have been COMPUTED, not merely echoed back.
    line = sandbox.last_reviewed.read_text().strip().splitlines()[-1]
    assert " round=2" in line, line

    # THE DISCRIMINATOR: omit --round entirely. Pre-change code has no
    # derivation at all (no `derive_review_round`, it only echoes a declared
    # --round), so it writes NO round= field here at all. Every assertion
    # above is satisfiable by the old code simply echoing what was declared;
    # this one is not.
    #
    # The expected value is 2, not 3: the `--clean` recorded just above RESET
    # the chain, so only the ONE blockers entry that follows it counts. That
    # reset is itself the behaviour under test, and getting this wrong the
    # first time is what proved the assertion is measuring something real.
    (committed_repo / "f.txt").write_text("v2\n")
    assert rr.main([
        "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit",
        "--paths", "f.txt",
    ]) == 0
    (committed_repo / "f.txt").write_text("v3\n")
    assert rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
    ]) == 0
    derived = sandbox.last_reviewed.read_text().strip().splitlines()[-1]
    assert " round=2" in derived, derived
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    assert not any(ln["decision"] == "round-mismatch" for ln in log_lines)


@_requires_git
def test_main_precommit_declared_round_disagreeing_with_derived_logs_mismatch_but_derived_governs(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """The task's own required vector: declared != derived logs
    round-mismatch, and the DERIVED value (not the declared one) is what
    actually lands on the ledger line -- and the record is NEVER refused
    just because they disagree."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    (committed_repo / "f.txt").write_text("v1\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
        "--round", "99",
    ])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert " round=1" in line  # derived (1), never the declared 99
    assert " round=99" not in line
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    mismatches = [ln for ln in log_lines if ln["decision"] == "round-mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0]["declared"] == 99
    assert mismatches[0]["derived"] == 1


@_requires_git
def test_main_precommit_round_tripwire_at_3_logs_would_refuse_but_still_records(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Round 3 crosses _ROUND_TRIPWIRE: a LOG-ONLY would-refuse line is
    written (round-tripwire-would-refuse), but the record STILL LANDS --
    LOG-ONLY means nothing is ever actually refused in this landing."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    # Round 1: blockers.
    (committed_repo / "f.txt").write_text("v1\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--blockers", "2", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    # Round 2: blockers again (derived round 2 at record time).
    (committed_repo / "f.txt").write_text("v2\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    # Round 3: this call derives round 3 -- crosses _ROUND_TRIPWIRE (3).
    (committed_repo / "f.txt").write_text("v3\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert any(" round=3" in ln and " clean" in ln for ln in lines), (
        "round 3's record must still land -- LOG-ONLY never refuses"
    )
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    tripwires = [ln for ln in log_lines if ln["decision"] == "round-tripwire-would-refuse"]
    assert len(tripwires) == 1
    assert tripwires[0]["derived_round"] == 3
    assert tripwires[0]["blockers_found"] == 2


@_requires_git
def test_main_precommit_round_6_logs_total_cap_would_refuse_but_still_records(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Round 6 crosses _MAX_TOTAL_ROUNDS (5): a DIFFERENT LOG-ONLY
    would-refuse reason (total-round-cap-would-refuse) is logged, and the
    record STILL LANDS -- nothing is ever refused in this LOG-ONLY
    landing, at either threshold."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    for round_n in range(1, 6):  # rounds 1-5, all unresolved blockers
        (committed_repo / "f.txt").write_text(f"v{round_n}\n")
        rc = rr.main([
            "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit",
            "--paths", "f.txt",
        ])
        assert rc == 0

    # Round 6: derives round 6 -- crosses _MAX_TOTAL_ROUNDS (5).
    (committed_repo / "f.txt").write_text("v6\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit",
        "--paths", "f.txt",
    ])
    assert rc == 0

    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert any(" round=6" in ln for ln in lines), "round 6 must still be recorded -- LOG-ONLY never refuses"
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    caps = [ln for ln in log_lines if ln["decision"] == "total-round-cap-would-refuse"]
    assert len(caps) == 1
    assert caps[0]["derived_round"] == 6
    # round 6 must NOT also double-log the (lower) tripwire reason.
    assert not any(ln["decision"] == "round-tripwire-would-refuse" and ln.get("derived_round") == 6
                   for ln in log_lines)


@_requires_git
def test_main_precommit_clean_after_blockers_resets_a_later_chain_to_round_1(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Paired recovery vector: after a clean review closes a boundary's
    chain, a LATER, fresh review of the SAME paths derives round 1 again
    -- a clean outcome is a true reset, not merely a pause."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    (committed_repo / "f.txt").write_text("v1\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    (committed_repo / "f.txt").write_text("v2\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    # A fresh, later edit to the SAME path after the clean review closed
    # the chain -- must derive round 1, not round 3.
    (committed_repo / "f.txt").write_text("v3\n")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "f.txt",
    ])
    assert rc == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    assert " round=1" in lines[-1], lines[-1]


@_requires_git
def test_main_precommit_disjoint_paths_never_share_a_round_chain(
    sandbox, clean_env, committed_repo, monkeypatch
):
    """Two genuinely independent boundaries (disjoint files) in the same
    repo must never inflate each other's derived round."""
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))

    (committed_repo / "f.txt").write_text("v1\n")
    for round_n in range(1, 4):
        (committed_repo / "f.txt").write_text(f"v{round_n}\n")
        rc = rr.main([
            "record_review.py", str(committed_repo), "--blockers", "1", "--pre-commit",
            "--paths", "f.txt",
        ])
        assert rc == 0

    # A DIFFERENT, disjoint path reviewed for the first time -- must derive
    # round 1, not round 4.
    (committed_repo / "g.txt").write_text("g1\n")
    _run_git(committed_repo, "add", "g.txt")
    rc = rr.main([
        "record_review.py", str(committed_repo), "--clean", "--pre-commit", "--paths", "g.txt",
    ])
    assert rc == 0
    lines = sandbox.last_reviewed.read_text().strip().splitlines()
    g_lines = [ln for ln in lines if "paths=g.txt " in ln]
    # Assert the filter MATCHED before asserting over it: a bare any() on an
    # empty list passes silently, so a filter that stopped matching would
    # turn this test green while checking nothing.
    assert len(g_lines) == 1, lines
    assert " round=1" in g_lines[0], g_lines[0]



# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 R6-B2 + M1 decision reversal (cold trust-architect
# review): --pre-commit and --rekey both refuse outright when any of
# GIT_LITERAL_PATHSPECS/GIT_GLOB_PATHSPECS/GIT_NOGLOB_PATHSPECS/
# GIT_ICASE_PATHSPECS is present in the environment -- replacing a
# fix-round-3 attempt that stripped these vars from the GATE's own git calls
# (a regression against HEAD, see precommit_review_gate's own
# REASON_PATHSPEC_ENV_SET comment).
# ---------------------------------------------------------------------------


class TestPathspecEnvVarsRefuseAtRecordReview:
    def teardown_method(self, _method):
        for var in _PATHSPEC_ENV_VARS_FOR_TESTS:
            os.environ.pop(var, None)

    @_requires_git
    @pytest.mark.parametrize("var", list(_PATHSPEC_ENV_VARS_FOR_TESTS))
    def test_precommit_refuses_when_var_is_set(
        self, sandbox, clean_env, committed_repo, monkeypatch, var
    ):
        clean_env.setenv("CSA_ENFORCE", "1")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
        (committed_repo / "f.txt").write_text("changed\n")
        os.environ[var] = "1"
        try:
            rc = rr.main([
                "record_review.py", str(committed_repo), "--pre-commit", "--clean",
                "--paths", "f.txt",
            ])
        finally:
            os.environ.pop(var, None)
        assert rc == 0  # never crashes; refusal is a printed message
        assert not sandbox.last_reviewed.exists() or sandbox.last_reviewed.read_text() == ""

    @_requires_git
    @pytest.mark.parametrize("var", list(_PATHSPEC_ENV_VARS_FOR_TESTS))
    def test_rekey_refuses_when_var_is_set(
        self, sandbox, clean_env, tmp_path, monkeypatch, var
    ):
        if not _have_git():
            pytest.skip("git not available")
        repo = tmp_path / "r"
        repo.mkdir()
        _run_git(repo, "init", "-q", "-b", "main")
        (repo / "base.txt").write_text("base\n")
        _run_git(repo, "add", "base.txt")
        _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
        (repo / "new_module.py").write_text("x = 1\n")

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
        clean_env.setenv("CSA_ENFORCE", "1")

        prior_key = prg.pending_key(str(repo), str(repo), ["new_module.py"])
        rc = rr.main([
            "record_review.py", str(repo), "--pre-commit", "--clean",
            "--paths", "new_module.py",
        ])
        assert rc == 0
        before_text = sandbox.last_reviewed.read_text()

        _run_git(repo, "add", "new_module.py")
        os.environ[var] = "1"
        try:
            rc2 = rr.main([
                "record_review.py", str(repo), "--rekey", prior_key, "--paths", "new_module.py",
            ])
        finally:
            os.environ.pop(var, None)
        assert rc2 == 0
        assert sandbox.last_reviewed.read_text() == before_text, (
            f"--rekey wrongly recorded while {var} was set in the environment"
        )

    @_requires_git
    def test_precommit_unaffected_when_no_var_is_set(
        self, sandbox, clean_env, committed_repo, monkeypatch
    ):
        for var in prg._PATHSPEC_ENV_VARS:
            assert var not in os.environ
        clean_env.setenv("CSA_ENFORCE", "1")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
        (committed_repo / "f.txt").write_text("changed\n")
        rc = rr.main([
            "record_review.py", str(committed_repo), "--pre-commit", "--clean",
            "--paths", "f.txt",
        ])
        assert rc == 0
        text = sandbox.last_reviewed.read_text()
        assert "clean" in text  # recorded normally, completely unaffected


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 (non-blocking, cold review): a --rekey refusal caused
# by LOSSY/AMBIGUOUS reconstruction material gets its own reason
# (`rekey-lossy-material`, distinct from `rekey-content-changed`) and an
# honest message naming that this content can never be safely rekeyed.
# ---------------------------------------------------------------------------


@_requires_git
def test_rekey_lossy_refusal_gets_its_own_reason_and_honest_message(
    sandbox, clean_env, tmp_path, monkeypatch
):
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")

    # A control-character name (the R6-B1 shape) makes _digest_safe_name
    # render it as an unambiguous JSON string -- fine on its own -- but the
    # per-file read cap / invalid-UTF-8 / file-count-cap paths are the
    # simplest LOSSY trigger to reach through the public API: a file over
    # the read cap whose tail changes.
    cap = prg._UNTRACKED_READ_CAP
    big = repo / "big.bin"
    big.write_bytes(b"A" * cap + b"ORIGINAL_TAIL")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    prior_key = prg.pending_key(str(repo), str(repo), ["big.bin"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean", "--paths", "big.bin",
    ])
    assert rc == 0

    big.write_bytes(b"A" * cap + b"TAMPERED_TAIL")  # same length, tail past the cap changes
    _run_git(repo, "add", "big.bin")

    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "big.bin",
    ])
    assert rc2 == 0

    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    decisions = [ln["decision"] for ln in log_lines]
    assert "rekey-lossy-material" in decisions, (
        f"expected a rekey-lossy-material log decision for a read-cap-truncated "
        f"file; got decisions: {decisions}"
    )
    assert "rekey-content-changed" not in decisions, (
        "a lossy refusal must NOT ALSO log the generic rekey-content-changed reason"
    )


@_requires_git
def test_rekey_ordinary_content_mismatch_still_uses_the_generic_reason(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Negative control: an ORDINARY content mismatch (nothing lossy) must
    still log the pre-existing `rekey-content-changed` reason, never the new
    `rekey-lossy-material` one -- the new reason is additive, not a
    replacement."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")
    (repo / "small.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    prior_key = prg.pending_key(str(repo), str(repo), ["small.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean", "--paths", "small.py",
    ])
    assert rc == 0

    (repo / "small.py").write_text("x = 999  # never reviewed\n")  # real content change
    _run_git(repo, "add", "small.py")

    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key, "--paths", "small.py",
    ])
    assert rc2 == 0
    log_lines = [json.loads(ln) for ln in sandbox.log_file.read_text().strip().splitlines()]
    decisions = [ln["decision"] for ln in log_lines]
    assert "rekey-content-changed" in decisions
    assert "rekey-lossy-material" not in decisions


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 (non-blocking, cold review): `paths_n` now counts the
# DISTINCT SANITIZED path set, not the raw input length -- a duplicate (or a
# sanitize-collision) in --paths must not desynchronize paths_n from the set
# a later --rekey comparison actually builds.
# ---------------------------------------------------------------------------


@_requires_git
def test_paths_n_counts_distinct_paths_not_raw_count_with_a_duplicate(
    sandbox, clean_env, committed_repo, monkeypatch
):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(committed_repo)})))
    # 13 distinct entries with ONE literal duplicate -> raw len 14, distinct 13.
    many = [f"f{i}.py" for i in range(12)]
    paths = ["base.txt", *many, "f0.py"]  # f0.py duplicated
    assert len(paths) == 14
    rc = rr.main(["record_review.py", str(committed_repo), "--clean", "--paths", *paths])
    assert rc == 0
    line = sandbox.last_reviewed.read_text().strip().splitlines()[0]
    assert "paths_n=13" in line, line


@_requires_git
def test_rekey_honest_thirteen_distinct_paths_with_a_duplicate_in_original_review_accepts(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """Mutation-gap coverage: without the dedupe fix, a --paths list with a
    literal duplicate desynchronizes paths_n from the deduped set a later
    --rekey builds, falsely refusing an honest rekey. This must ACCEPT."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    _run_git(repo, "add", "base.txt")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt")

    many = [f"f{i}.py" for i in range(12)]
    for name in many:
        (repo / name).write_text(f"# {name}\n")
    # 13 distinct real paths, cited TWICE in --paths (duplicate f0.py).
    review_paths = ["base.txt", *many, "f0.py"]

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    prior_key = prg.pending_key(str(repo), str(repo), ["base.txt", *many])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean", "--paths", *review_paths,
    ])
    assert rc == 0

    _run_git(repo, "add", *many)
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key,
        "--paths", "base.txt", *many,
    ])
    assert rc2 == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert f"rekey={prior_key}" in new_line, (
        "an honest rekey was wrongly refused because the ORIGINAL review's "
        f"--paths carried a duplicate: {text.strip().splitlines()[-3:]}"
    )


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 (non-blocking, cold review): mutation-gap coverage for
# B2's own ≤12-path exact-equality branch (the non-truncated case) -- must
# still refuse an outright mismatch when paths_n does NOT exceed the cap.
# ---------------------------------------------------------------------------


@_requires_git
def test_mutation_gap_exact_equality_still_refuses_under_the_cap(
    sandbox, clean_env, tmp_path, monkeypatch
):
    """If the exact-equality branch (the non-truncated case) were disabled,
    this would wrongly accept a --rekey whose --paths adds one extra,
    ALREADY-COMMITTED-AND-UNCHANGED file on top of the originally-reviewed
    set -- both counts stay under the 12-path cap (so the truncation branch
    never applies) and the extra file contributes ZERO bytes to the
    reconstructed diff (it is untouched since its own commit), so the
    byte-identical check alone cannot distinguish this from an honest
    rekey; only the plain equality check on the paths SET can catch it.
    Mirrors `test_rekey_paths_mismatch_refuses_extra_path_smuggled_past_
    truncated_subset_check`'s own isolation technique, scaled to the
    non-truncated (≤12-path) case that check does not exercise."""
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "r"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    # Committed UNCHANGED alongside base.txt -- contributes zero diff
    # whether or not it's named in --paths.
    (repo / "innocuous_extra.py").write_text("innocuous = 1\n")
    _run_git(repo, "add", "base.txt", "innocuous_extra.py")
    _run_git(repo, "commit", "-q", "-m", "base", "--", "base.txt", "innocuous_extra.py")
    (repo / "reviewed.py").write_text("x = 1\n")

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    clean_env.setenv("CSA_ENFORCE", "1")

    prior_key = prg.pending_key(str(repo), str(repo), ["reviewed.py"])
    rc = rr.main([
        "record_review.py", str(repo), "--pre-commit", "--clean", "--paths", "reviewed.py",
    ])
    assert rc == 0
    before_text = sandbox.last_reviewed.read_text()

    _run_git(repo, "add", "reviewed.py")
    # innocuous_extra.py is NOT re-staged/re-edited -- naming it alongside
    # the honest reviewed.py is a pure paths-set smuggling attempt.
    rc2 = rr.main([
        "record_review.py", str(repo), "--rekey", prior_key,
        "--paths", "reviewed.py", "innocuous_extra.py",
    ])
    assert rc2 == 0
    assert sandbox.last_reviewed.read_text() == before_text, (
        "a --rekey whose --paths smuggles in an extra, unchanged file on top "
        "of the reviewed set must refuse (under-cap exact-equality)"
    )
