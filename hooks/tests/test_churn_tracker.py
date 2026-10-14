"""Hermetic tests for hooks/churn_tracker.py — the informational commit-churn
observer (Part 2 of the review-outcome / churn-tracker task).

Covers the pure helpers (normalize_path, grouping/counting/threshold logic),
the ledger I/O (read/prune/write/reset — mirroring file_claims.py's atomic
write + self-heal-on-read shape), the record_review.py cross-reference
(clean_reviewed_shas), the git plumbing (repo_root_of/_current_head), the
observe_commit/observe_commit_for_event entry points end to end (including the
"3rd touch without a clean review flags, a clean review resets the count"
scenario), status_payload, and the CLI main().

Everything runs against the `sandbox` fixture (tmp $HOME) so the operator's
real ~/.claude/.churn/ and ~/.claude/.review_state/ are never touched. Git is
exercised only through throwaway, offline repos — no network.
"""

from __future__ import annotations

import json
import os
import subprocess

import _lib  # noqa: F401  (sys.path shim via conftest)
import churn_tracker as ct
import pytest


# ===========================================================================
# Helpers — throwaway, offline git repos (mirrors test_record_review.py).
# ===========================================================================


def _run_git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "T"
    env["GIT_AUTHOR_EMAIL"] = "t@example.invalid"
    env["GIT_COMMITTER_NAME"] = "T"
    env["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=15, env=env)


def _git_out(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=15, env=env
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
    if not _have_git():
        pytest.skip("git not available")
    repo = tmp_path / "committed"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    (repo / "f.txt").write_text("hello\n")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "commit", "-q", "-m", "initial")
    return repo


def _write_clean_review(sandbox, repo_root, sha):
    os.makedirs(str(sandbox.review_state_dir), exist_ok=True)
    with open(str(sandbox.last_reviewed), "a", encoding="utf-8") as fh:
        fh.write(f"{repo_root} {sha} clean\n")


# ===========================================================================
# Pure helpers.
# ===========================================================================


class TestNormalizePath:
    def test_strips_leading_dot_slash(self):
        assert ct.normalize_path("./a/b.py") == "a/b.py"

    def test_strips_trailing_slash(self):
        assert ct.normalize_path("a/b/") == "a/b"

    def test_empty_stays_empty(self):
        assert ct.normalize_path("") == ""
        assert ct.normalize_path(None) == ""


class TestCommitFile:
    def test_keyed_by_repo_sha_and_nonce(self, sandbox):
        p1 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n1")
        p2 = ct._commit_file(str(sandbox.churn_dir), "/repo/b", "sha1", "n1")
        p3 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha2", "n1")
        p4 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n2")
        assert len({p1, p2, p3, p4}) == 4  # all four distinct

    def test_same_repo_sha_and_nonce_is_the_same_file(self, sandbox):
        p1 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n1")
        p2 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n1")
        assert p1 == p2

    def test_same_repo_and_sha_different_nonce_is_a_different_file(self, sandbox):
        # CORRECTNESS 21: this is what makes re-observing an UNCHANGED HEAD
        # add a record instead of silently overwriting the earlier one.
        p1 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n1")
        p2 = ct._commit_file(str(sandbox.churn_dir), "/repo/a", "sha1", "n2")
        assert p1 != p2


class TestPathCommitCounts:
    def test_groups_by_path_sorted_oldest_first(self):
        records = [
            {"repo_root": "/r", "sha": "s2", "timestamp": 20.0, "paths": ["a.py"]},
            {"repo_root": "/r", "sha": "s1", "timestamp": 10.0, "paths": ["a.py", "b.py"]},
        ]
        by_path = ct.path_commit_counts(records, "/r")
        assert [e["sha"] for e in by_path["a.py"]] == ["s1", "s2"]
        assert [e["sha"] for e in by_path["b.py"]] == ["s1"]

    def test_other_repos_excluded(self):
        records = [{"repo_root": "/other", "sha": "s1", "timestamp": 10.0, "paths": ["a.py"]}]
        assert ct.path_commit_counts(records, "/r") == {}

    def test_empty_records(self):
        assert ct.path_commit_counts([], "/r") == {}


class TestCleanResetTimestamp:
    def test_no_clean_shas_is_none(self):
        commits = [{"sha": "s1", "timestamp": 10.0}]
        assert ct._clean_reset_timestamp(commits, set(), 0.0) is None

    def test_clean_sha_outside_window_is_none(self):
        commits = [{"sha": "s1", "timestamp": 10.0}]
        assert ct._clean_reset_timestamp(commits, {"s1"}, window_start=20.0) is None

    def test_clean_sha_inside_window(self):
        commits = [{"sha": "s1", "timestamp": 10.0}]
        assert ct._clean_reset_timestamp(commits, {"s1"}, window_start=0.0) == 10.0

    def test_picks_the_latest_of_multiple_clean_shas(self):
        commits = [
            {"sha": "s1", "timestamp": 10.0},
            {"sha": "s2", "timestamp": 20.0},
            {"sha": "s3", "timestamp": 30.0},
        ]
        assert ct._clean_reset_timestamp(commits, {"s1", "s2"}, window_start=0.0) == 20.0


class TestCountSinceCleanReview:
    def test_no_reset_counts_everything_in_window(self):
        commits = [{"sha": "s1", "timestamp": 10.0}, {"sha": "s2", "timestamp": 20.0}]
        assert ct.count_since_clean_review(commits, set(), window_start=0.0) == 2

    def test_out_of_window_commits_excluded(self):
        commits = [{"sha": "s1", "timestamp": 5.0}, {"sha": "s2", "timestamp": 20.0}]
        assert ct.count_since_clean_review(commits, set(), window_start=10.0) == 1

    def test_reset_excludes_the_boundary_commit_and_everything_before(self):
        commits = [
            {"sha": "s1", "timestamp": 10.0},
            {"sha": "s2", "timestamp": 20.0},  # clean review lands here
            {"sha": "s3", "timestamp": 30.0},
        ]
        assert ct.count_since_clean_review(commits, {"s2"}, window_start=0.0) == 1  # only s3


class TestFlaggedPaths:
    def test_below_threshold_not_flagged(self):
        records = [
            {"repo_root": "/r", "sha": f"s{i}", "timestamp": float(i), "paths": ["a.py"]} for i in range(2)
        ]
        assert ct.flagged_paths(records, "/r", set(), threshold=3, window_start=0.0) == {}

    def test_at_threshold_is_flagged(self):
        records = [
            {"repo_root": "/r", "sha": f"s{i}", "timestamp": float(i), "paths": ["a.py"]} for i in range(3)
        ]
        assert ct.flagged_paths(records, "/r", set(), threshold=3, window_start=0.0) == {"a.py": 3}

    def test_only_paths_over_threshold_are_reported(self):
        records = [
            {"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py", "b.py"]},
            {"repo_root": "/r", "sha": "s2", "timestamp": 2.0, "paths": ["a.py"]},
            {"repo_root": "/r", "sha": "s3", "timestamp": 3.0, "paths": ["a.py"]},
        ]
        got = ct.flagged_paths(records, "/r", set(), threshold=3, window_start=0.0)
        assert got == {"a.py": 3}
        assert "b.py" not in got

    def test_clean_review_resets_below_threshold(self):
        records = [
            {"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]},
            {"repo_root": "/r", "sha": "s2", "timestamp": 2.0, "paths": ["a.py"]},
            {"repo_root": "/r", "sha": "s3", "timestamp": 3.0, "paths": ["a.py"]},
        ]
        # s3 itself is the clean-reviewed sha -> resets to 0 remaining.
        assert ct.flagged_paths(records, "/r", {"s3"}, threshold=3, window_start=0.0) == {}


class TestParseCommitRecord:
    def test_valid_record_parses_and_normalizes(self):
        raw = json.dumps(
            {"repo_root": "/r", "sha": "s1", "timestamp": 10.0, "paths": ["./a.py", "b.py/"]}
        )
        rec = ct._parse_commit_record(raw)
        assert rec == {"repo_root": "/r", "sha": "s1", "timestamp": 10.0, "paths": ["a.py", "b.py"]}

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not json",
            "[]",
            "null",
            json.dumps({"sha": "s1", "timestamp": 1.0, "paths": ["x"]}),  # missing repo_root
            json.dumps({"repo_root": "", "sha": "s1", "timestamp": 1.0, "paths": ["x"]}),  # empty repo_root
            json.dumps({"repo_root": "/r", "timestamp": 1.0, "paths": ["x"]}),  # missing sha
            json.dumps({"repo_root": "/r", "sha": "", "timestamp": 1.0, "paths": ["x"]}),  # empty sha
            json.dumps({"repo_root": "/r", "sha": "s1", "paths": ["x"]}),  # missing timestamp
            json.dumps({"repo_root": "/r", "sha": "s1", "timestamp": "bad", "paths": ["x"]}),
            json.dumps({"repo_root": "/r", "sha": "s1", "timestamp": 1.0}),  # missing paths
            json.dumps({"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": "not-a-list"}),
            json.dumps({"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": [1, 2]}),
        ],
    )
    def test_malformed_record_returns_none(self, raw):
        assert ct._parse_commit_record(raw) is None


# ===========================================================================
# Ledger I/O — read_live_commits prune-and-self-heal, write, reset.
# ===========================================================================


class TestReadCommit:
    def test_open_failure_returns_none(self, sandbox, monkeypatch):
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        f = sandbox.churn_dir / f"{ct.COMMIT_PREFIX}x.json"
        f.write_text(json.dumps({"repo_root": "/r", "sha": "s", "timestamp": 1.0, "paths": ["a"]}))

        real_open = open

        def boom_open(path, *a, **k):
            if str(path) == str(f):
                raise OSError("cannot read")
            return real_open(path, *a, **k)

        monkeypatch.setattr("builtins.open", boom_open)
        assert ct._read_commit(str(f)) is None


class TestReadLiveCommits:
    def test_missing_dir_returns_empty(self, sandbox):
        assert ct.read_live_commits(str(sandbox.churn_dir), 300) == []

    def test_live_commit_returned(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=1000.0)
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=1010.0)
        assert len(live) == 1
        assert live[0]["repo_root"] == "/r"
        assert live[0]["sha"] == "s1"
        assert live[0]["paths"] == ["a.py"]

    def test_stale_commit_pruned(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=1000.0)
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=2000.0)
        assert live == []
        assert list(sandbox.churn_dir.iterdir()) == []  # self-healed away

    def test_malformed_file_pruned(self, sandbox):
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        bad = sandbox.churn_dir / f"{ct.COMMIT_PREFIX}bad.json"
        bad.write_text("not json")
        assert ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=1000.0) == []
        assert not bad.exists()

    def test_non_prefixed_files_ignored(self, sandbox):
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        (sandbox.churn_dir / "unrelated.json").write_text("{}")
        assert ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=1000.0) == []
        assert (sandbox.churn_dir / "unrelated.json").exists()  # untouched

    def test_unreadable_dir_fails_open(self, sandbox, monkeypatch):
        monkeypatch.setattr(ct.os, "listdir", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        assert ct.read_live_commits(str(sandbox.churn_dir), 300) == []

    def test_file_removed_between_listdir_and_read_is_skipped(self, sandbox, monkeypatch):
        """Race-condition safety net: a file that vanished between listdir()
        and the exists() check is skipped, not treated as an error."""
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0)
        monkeypatch.setattr(ct.os.path, "exists", lambda *_a, **_k: False)
        assert ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=100.0) == []


class TestRecordCommit:
    def test_writes_a_readable_record(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["./a.py", "b.py"], now=100.0)
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=100.0)
        assert live[0]["paths"] == ["a.py", "b.py"]

    def test_blank_repo_root_is_noop(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "", "s1", ["a.py"], now=100.0)
        assert not sandbox.churn_dir.exists() or list(sandbox.churn_dir.iterdir()) == []

    def test_blank_sha_is_noop(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "", ["a.py"], now=100.0)
        assert not sandbox.churn_dir.exists() or list(sandbox.churn_dir.iterdir()) == []

    def test_empty_paths_is_noop(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", [], now=100.0)
        assert not sandbox.churn_dir.exists() or list(sandbox.churn_dir.iterdir()) == []

    def test_all_blank_paths_after_normalization_is_noop(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["  ", ""], now=100.0)
        assert not sandbox.churn_dir.exists() or list(sandbox.churn_dir.iterdir()) == []

    def test_reobserving_same_commit_adds_a_record_not_overwrites(self, sandbox):
        # CORRECTNESS 21: re-observing an UNCHANGED (repo_root, sha) — e.g. a
        # retried commit attempt with no new HEAD landing — must ADD an
        # observation, never silently collapse into the earlier one. Before
        # the fix this was a same-key overwrite (locked in by the OLD version
        # of this exact test), which under-counted the "same fix attempted
        # repeatedly without a new commit landing" pattern this module exists
        # to catch.
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0)
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py", "b.py"], now=100.0)
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=100.0)
        assert len(live) == 2
        assert {tuple(r["paths"]) for r in live} == {("a.py",), ("a.py", "b.py")}
        assert {r["sha"] for r in live} == {"s1"}

    def test_explicit_nonce_is_deterministic_overwrite(self, sandbox):
        # A caller that DOES pass an explicit, identical nonce gets the
        # original idempotent-overwrite behavior back (documented escape
        # hatch in record_commit's docstring; unused elsewhere today).
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0, nonce="fixed")
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py", "b.py"], now=100.0, nonce="fixed")
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=100.0)
        assert len(live) == 1
        assert live[0]["paths"] == ["a.py", "b.py"]

    def test_now_defaults_to_wall_clock(self, sandbox):
        """No explicit `now` -> record_commit falls back to ab._now_epoch()."""
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"])
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300)
        assert len(live) == 1


class TestWriteCommitFailurePaths:
    def test_swallows_write_failure_and_cleans_tmp(self, sandbox, monkeypatch):
        real_open = open

        def boom_open(path, *a, **k):
            if ".tmp." in str(path):
                raise OSError("disk full")
            return real_open(path, *a, **k)

        monkeypatch.setattr("builtins.open", boom_open)
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0)
        # No stray tmp files, and no partial record either.
        assert ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=100.0) == []


class TestResetLedger:
    def test_missing_dir_returns_zero(self, sandbox):
        assert ct.reset_ledger(str(sandbox.churn_dir), ttl=300, now=1000.0) == 0

    def test_removes_only_stale_or_malformed(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "fresh", ["a.py"], now=990.0)
        ct.record_commit(str(sandbox.churn_dir), "/r", "stale", ["a.py"], now=100.0)
        removed = ct.reset_ledger(str(sandbox.churn_dir), ttl=300, now=1000.0)
        assert removed == 1
        live = ct.read_live_commits(str(sandbox.churn_dir), ttl=300, now=1000.0)
        assert [r["sha"] for r in live] == ["fresh"]

    def test_unreadable_dir_fails_open(self, sandbox, monkeypatch):
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(ct.os, "listdir", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
        assert ct.reset_ledger(str(sandbox.churn_dir), ttl=300) == 0

    def test_file_removed_between_listdir_and_read_is_skipped(self, sandbox, monkeypatch):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0)
        monkeypatch.setattr(ct.os.path, "exists", lambda *_a, **_k: False)
        assert ct.reset_ledger(str(sandbox.churn_dir), ttl=300, now=100.0) == 0

    def test_now_defaults_to_wall_clock(self, sandbox):
        ct.record_commit(str(sandbox.churn_dir), "/r", "s1", ["a.py"], now=100.0)
        removed = ct.reset_ledger(str(sandbox.churn_dir), ttl=0)
        assert removed == 1

    def test_non_prefixed_files_ignored_not_removed(self, sandbox):
        sandbox.churn_dir.mkdir(parents=True, exist_ok=True)
        (sandbox.churn_dir / "unrelated.json").write_text("{}")
        assert ct.reset_ledger(str(sandbox.churn_dir), ttl=300, now=1000.0) == 0
        assert (sandbox.churn_dir / "unrelated.json").exists()


# ===========================================================================
# record_review.py cross-reference — clean_reviewed_shas.
# ===========================================================================


class TestCleanReviewedShas:
    def test_no_clean_review_recorded(self, sandbox):
        records = [{"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]}]
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == set()

    def test_clean_review_recorded_for_a_seen_sha(self, sandbox):
        records = [{"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]}]
        _write_clean_review(sandbox, "/r", "s1")
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == {"s1"}

    def test_blockers_outcome_is_not_clean(self, sandbox):
        records = [{"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]}]
        os.makedirs(str(sandbox.review_state_dir), exist_ok=True)
        with open(str(sandbox.last_reviewed), "a", encoding="utf-8") as fh:
            fh.write("/r s1 blockers:2\n")
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == set()

    def test_only_shas_from_our_own_ledger_are_considered(self, sandbox):
        """A clean review recorded for a sha we've NEVER observed committed is
        NOT surfaced — this module only checks shas it has itself seen."""
        records = [{"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]}]
        _write_clean_review(sandbox, "/r", "unseen-sha")
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == set()

    def test_other_repo_shas_excluded(self, sandbox):
        records = [
            {"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]},
            {"repo_root": "/other", "sha": "s2", "timestamp": 1.0, "paths": ["b.py"]},
        ]
        _write_clean_review(sandbox, "/other", "s2")
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == set()

    def test_lookup_failure_for_one_sha_is_swallowed(self, sandbox, monkeypatch):
        records = [{"repo_root": "/r", "sha": "s1", "timestamp": 1.0, "paths": ["a.py"]}]

        def boom(*_a, **_k):
            raise RuntimeError("ledger read exploded")

        monkeypatch.setattr(ct.rr, "head_review_outcome", boom)
        assert ct.clean_reviewed_shas(records, "/r", str(sandbox.last_reviewed)) == set()


# ===========================================================================
# Git plumbing — repo_root_of / _current_head.
# ===========================================================================


class TestGitPlumbing:
    @_requires_git
    def test_repo_root_of_resolves_toplevel(self, sandbox, committed_repo):
        root = ct.repo_root_of(str(committed_repo))
        assert os.path.samefile(root, str(committed_repo))

    @_requires_git
    def test_repo_root_of_nested_dir_resolves_toplevel(self, sandbox, committed_repo):
        nested = committed_repo / "a" / "b"
        nested.mkdir(parents=True)
        root = ct.repo_root_of(str(nested))
        assert os.path.samefile(root, str(committed_repo))

    def test_repo_root_of_non_repo_is_empty(self, sandbox, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert ct.repo_root_of(str(plain)) == ""

    @_requires_git
    def test_current_head_resolves_sha(self, sandbox, committed_repo):
        expected = _git_out(committed_repo, "rev-parse", "HEAD")
        assert ct._current_head(str(committed_repo)) == expected

    def test_current_head_no_repo_is_empty(self, sandbox, tmp_path):
        assert ct._current_head(str(tmp_path)) == ""

    def test_git_helper_swallows_subprocess_exception(self, sandbox, monkeypatch):
        monkeypatch.setattr(ct.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
        assert ct._git("/x", "rev-parse", "HEAD") == ""

    def test_git_helper_nonzero_returncode_is_empty(self, sandbox, monkeypatch):
        class P:
            returncode = 1
            stdout = ""

        monkeypatch.setattr(ct.subprocess, "run", lambda *a, **k: P())
        assert ct._git("/x", "rev-parse", "HEAD") == ""


# ===========================================================================
# observe_commit / observe_commit_for_event — the entry points gate 5 drives.
# ===========================================================================


class TestObserveCommit:
    def test_blank_repo_root_is_a_noop_report(self, sandbox):
        got = ct.observe_commit(str(sandbox.churn_dir), str(sandbox.last_reviewed), "", "s1", ["a.py"], 7200, 3)
        assert got == {"newly_flagged": {}}

    def test_blank_sha_is_a_noop_report(self, sandbox):
        got = ct.observe_commit(str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "", ["a.py"], 7200, 3)
        assert got == {"newly_flagged": {}}

    def test_empty_paths_is_a_noop_report(self, sandbox):
        got = ct.observe_commit(str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", [], 7200, 3)
        assert got == {"newly_flagged": {}}

    def test_below_threshold_reports_nothing(self, sandbox):
        got = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1000.0
        )
        assert got == {"newly_flagged": {}}

    def test_third_touch_without_clean_review_is_flagged(self, sandbox):
        """The scenario the whole module exists for: the SAME path touched by
        3 commits in the window, no clean review in between -> flagged on the
        3rd observation."""
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1000.0
        )
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s2", ["a.py"], 7200, 3, now=1100.0
        )
        third = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1200.0
        )
        assert third == {"newly_flagged": {"a.py": 3}}

    def test_only_reports_paths_from_THIS_commit_not_every_flagged_path(self, sandbox):
        """A commit touching path X should not report path Y's flagged count
        even if Y is separately flagged in the same repo."""
        for i, ts in enumerate((1000.0, 1100.0, 1200.0)):
            ct.observe_commit(
                str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", f"y{i}", ["y.py"], 7200, 3, now=ts
            )
        got = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "x1", ["x.py"], 7200, 3, now=1300.0
        )
        assert got == {"newly_flagged": {}}  # x.py itself has only 1 touch

    def test_clean_review_then_next_commit_resets_the_count(self, sandbox):
        """3 unclean touches would flag; a clean review recorded at the 3rd
        sha resets so the NEXT commit (which observes that reviewed sha) does
        not re-flag immediately."""
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1000.0
        )
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s2", ["a.py"], 7200, 3, now=1100.0
        )
        third = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1200.0
        )
        assert third == {"newly_flagged": {"a.py": 3}}  # flagged at the 3rd touch

        # A clean review lands at HEAD == s3 (the sha just observed).
        _write_clean_review(sandbox, "/r", "s3")

        # The NEXT commit attempt observes current HEAD == s3 (the reviewed
        # sha) — this is the reset boundary; it does not itself re-flag.
        fourth = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1300.0
        )
        assert fourth == {"newly_flagged": {}}

    def test_internal_error_degrades_to_empty_report(self, sandbox, monkeypatch):
        monkeypatch.setattr(ct, "record_commit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        got = ct.observe_commit(str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3)
        assert got == {"newly_flagged": {}}

    def test_only_flagged_once_at_the_exact_crossing_not_every_subsequent_touch(self, sandbox):
        """CORRECTNESS 9: `newly_flagged` must report a path only at the
        MOMENT it crosses the threshold, matching the docstring's "per path
        that just crossed the threshold" for real — not on every later
        commit that keeps it over threshold too (the pre-fix behavior, which
        made pretooluse_bash's gate 5 re-log "churn-flagged" for the same
        path on every subsequent commit).
        """
        results = []
        for i, sha in enumerate(("s1", "s2", "s3", "s4", "s5")):
            results.append(
                ct.observe_commit(
                    str(sandbox.churn_dir),
                    str(sandbox.last_reviewed),
                    "/r",
                    sha,
                    ["a.py"],
                    7200,
                    3,
                    now=1000.0 + i,
                )
            )
        assert results[0] == {"newly_flagged": {}}
        assert results[1] == {"newly_flagged": {}}
        assert results[2] == {"newly_flagged": {"a.py": 3}}  # the crossing
        assert results[3] == {"newly_flagged": {}}  # still over threshold, NOT re-reported
        assert results[4] == {"newly_flagged": {}}

    def test_same_head_observed_twice_counts_as_two_touches(self, sandbox):
        """CORRECTNESS 21: re-observing an UNCHANGED HEAD (e.g. the same fix
        attempted repeatedly with no new commit landing) counts as TWO
        separate touches toward the threshold, not one silently-collapsed
        touch — exactly the pattern this module exists to catch.
        """
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1000.0
        )
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1010.0
        )
        third = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1020.0
        )
        # 3 OBSERVATIONS, even though every one is at the same sha (retried,
        # never actually landed a new commit) -> the 3rd crosses the threshold.
        assert third == {"newly_flagged": {"a.py": 3}}

    def test_commit_immediately_after_a_clean_review_does_not_over_count(self, sandbox):
        """The commit attempt immediately FOLLOWING a clean review necessarily
        observes current HEAD == the just-reviewed sha (module docstring's
        design note) — possibly more than once, if the real commit is
        retried before it lands. Neither re-observation at the reviewed sha
        should itself count toward a fresh flag; only a genuinely NEW sha
        after it should start counting again, from 1.
        """
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s1", ["a.py"], 7200, 3, now=1000.0
        )
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s2", ["a.py"], 7200, 3, now=1100.0
        )
        ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1200.0
        )
        _write_clean_review(sandbox, "/r", "s3")

        # The commit attempt right after the review retries TWICE before it
        # actually lands -- both retries still observe HEAD == s3.
        r1 = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1300.0
        )
        r2 = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s3", ["a.py"], 7200, 3, now=1310.0
        )
        assert r1 == {"newly_flagged": {}}
        assert r2 == {"newly_flagged": {}}

        # The commit FINALLY lands (a genuinely new sha) -> counts fresh
        # from 1 since the reset, not already primed toward the old count.
        r3 = ct.observe_commit(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", "s4", ["a.py"], 7200, 3, now=1400.0
        )
        assert r3 == {"newly_flagged": {}}


class TestObserveCommitForEvent:
    @_requires_git
    def test_resolves_head_and_observes(self, sandbox, committed_repo):
        got = ct.observe_commit_for_event(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), str(committed_repo), ["a.py"], 7200, 3
        )
        assert got == {"newly_flagged": {}}
        live = ct.read_live_commits(str(sandbox.churn_dir), 7200)
        assert live[0]["repo_root"] == str(committed_repo)

    def test_unresolvable_head_is_a_noop_report_no_ledger_write(self, sandbox, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        got = ct.observe_commit_for_event(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), str(plain), ["a.py"], 7200, 3
        )
        assert got == {"newly_flagged": {}}
        assert ct.read_live_commits(str(sandbox.churn_dir), 7200) == []

    def test_current_head_raising_is_swallowed(self, sandbox, monkeypatch):
        monkeypatch.setattr(ct, "_current_head", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("x")))
        got = ct.observe_commit_for_event(
            str(sandbox.churn_dir), str(sandbox.last_reviewed), "/r", ["a.py"], 7200, 3
        )
        assert got == {"newly_flagged": {}}


# ===========================================================================
# status_payload.
# ===========================================================================


class TestStatusPayload:
    def test_empty_ledger(self, sandbox):
        payload = ct.status_payload(str(sandbox.churn_dir), str(sandbox.last_reviewed), 7200, 3, now=1000.0)
        assert payload == {
            "window_sec": 7200,
            "threshold": 3,
            "tracked_commits": 0,
            "flagged": {},
        }

    def test_multi_repo_flagging(self, sandbox):
        for i, ts in enumerate((1000.0, 1100.0, 1200.0)):
            ct.record_commit(str(sandbox.churn_dir), "/r1", f"a{i}", ["x.py"], now=ts)
        ct.record_commit(str(sandbox.churn_dir), "/r2", "b0", ["y.py"], now=1000.0)  # below threshold

        payload = ct.status_payload(str(sandbox.churn_dir), str(sandbox.last_reviewed), 7200, 3, now=1300.0)
        assert payload["tracked_commits"] == 4
        assert payload["flagged"] == {"/r1": {"x.py": 3}}


# ===========================================================================
# Env config.
# ===========================================================================


class TestEnvConfig:
    def test_defaults(self):
        assert ct.window_from_env({}) == ct.DEFAULT_WINDOW_SEC
        assert ct.threshold_from_env({}) == ct.DEFAULT_THRESHOLD
        assert ct.lock_timeout_from_env({}) == ct.ab.DEFAULT_LOCK_TIMEOUT

    def test_overrides(self):
        env = {"CSA_CHURN_WINDOW_SEC": "60", "CSA_CHURN_THRESHOLD": "5", "CSA_LOCK_TIMEOUT_SEC": "1.5"}
        assert ct.window_from_env(env) == 60
        assert ct.threshold_from_env(env) == 5
        assert ct.lock_timeout_from_env(env) == 1.5

    def test_garbage_falls_back_to_default(self):
        assert ct.window_from_env({"CSA_CHURN_WINDOW_SEC": "nope"}) == ct.DEFAULT_WINDOW_SEC
        assert ct.threshold_from_env({"CSA_CHURN_THRESHOLD": "nope"}) == ct.DEFAULT_THRESHOLD


# ===========================================================================
# CLI main().
# ===========================================================================


class TestCLIMain:
    def _run(self, monkeypatch, capsys, argv):
        rc = ct.main(argv)
        out = capsys.readouterr().out
        return rc, out

    def test_disabled_short_circuits(self, sandbox, monkeypatch, capsys):
        monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
        rc, out = self._run(monkeypatch, capsys, ["status"])
        assert rc == 0 and out == ""

    def test_status_prints_json(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["status"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["flagged"] == {}
        assert payload["tracked_commits"] == 0

    def test_status_reflects_a_flagged_path(self, sandbox, monkeypatch, capsys):
        for i, ts in enumerate((1000.0, 1100.0, 1200.0)):
            ct.record_commit(str(sandbox.churn_dir), "/r", f"s{i}", ["a.py"], now=ts)
        monkeypatch.setattr(ct.ab, "_now_epoch", lambda: 1200)
        rc, out = self._run(monkeypatch, capsys, ["status"])
        payload = json.loads(out)
        assert payload["flagged"] == {"/r": {"a.py": 3}}

    def test_reset_smoke(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["reset"])
        assert rc == 0 and "OK reset" in out

    def test_doctor_smoke(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["doctor"])
        assert rc == 0
        assert "churn_tracker doctor" in out
        assert "INFORMATIONAL ONLY" in out

    def test_argv_defaults_to_sys_argv(self, sandbox, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["churn_tracker.py", "status"])
        rc, out = self._run(monkeypatch, capsys, None)
        assert rc == 0 and "tracked_commits" in out

    def test_unknown_subcommand_degrades_open(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["bogus"])
        assert rc == 0  # advisory: never a hard failure

    def test_no_argv_defaults_to_status(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, [])
        assert rc == 0 and "tracked_commits" in out

    def test_main_swallows_unexpected_error(self, sandbox, monkeypatch, capsys):
        monkeypatch.setattr(ct, "window_from_env", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        rc = ct.main(["status"])
        assert rc == 0
