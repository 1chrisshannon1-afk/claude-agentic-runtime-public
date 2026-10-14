"""Hermetic tests for hooks/file_claims.py — the path-scoped commit claim ledger.

Covers the pure helpers (normalize_path, paths_overlap, find_contest, claim
parsing), the ledger I/O (read/prune/write/release), the atomic
try_claim_paths/poll_claim_paths pair, and — the point of the whole module — a
concurrency scenario that demonstrates the all-or-nothing claim shape rules out
partial-hold deadlock, leaving only a bounded livelock that the max-wait clamp
terminates. Injectable clocks/sleep mirror test_agent_budget.py's paced_admit
tests so the poll-loop tests run instantly, not in wall-clock time.

Everything runs against the `sandbox` fixture (tmp $HOME) so the operator's
real ~/.claude/.file_claims/ is never touched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import _lib  # noqa: F401  (sys.path shim via conftest)
import file_claims as fc
import pytest


@pytest.fixture(autouse=True)
def _no_ambient_claude_pid(monkeypatch):
    """Module-wide safety net: clear CLAUDE_PID for EVERY test in this file,
    not just the ones using the `sandbox` fixture (conftest.py's `clean_env`
    already clears it there — see that file's own comment). A handful of
    classes here (TestMutexToken, TestCommitMutexClaiming,
    TestSameSessionConcurrentCommitsStillContest, ...) use bare `tmp_path`
    instead of `sandbox`, so they'd otherwise inherit whatever CLAUDE_PID
    happens to be set in the real shell running the suite (always set inside
    an actual Claude Code session) — silently making a test's OWN explicit
    `monkeypatch.setenv("CLAUDE_PID", ...)` ambiguous with ambient state, or
    (for any test not yet aware it needs to set one) picking up a stray real
    pid. Most individual tests here that care already guard themselves
    per-test (see TestOwnerPid, TestWriteClaimRecordsOwnerPid); clearing it
    here too keeps the baseline honest for anything added later.
    """
    monkeypatch.delenv("CLAUDE_PID", raising=False)


def _write_claim_raw(claims_dir: str, agent_id: str, paths: list, claimed_at: float, pid) -> None:
    """Write a claim file directly with an EXPLICIT "pid" field, bypassing
    _write_claim's own _owner_pid() resolution (which always reads the
    live CLAUDE_PID/os.getpid() of the test process — never a dead one) so
    dead-pid tests can pin the pid field to a known value.
    """
    os.makedirs(claims_dir, exist_ok=True)
    path = fc.claim_path(claims_dir, agent_id)
    body = {"agent_id": agent_id, "pid": pid, "claimed_at": claimed_at, "paths": paths}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)


def _dead_pid() -> int:
    """Spawn a trivial subprocess, wait for it to exit, and return its
    (now-guaranteed-dead) pid. Used by every dead-pid test below instead of
    a magic-number pid, which risks colliding with something real.

    NIT (Opus review, 2026-08-30): a theoretical flake window exists between
    `proc.wait()` returning and this pid being asserted "dead" a few lines
    later in the calling test — the OS is free to reuse a just-freed pid for
    an unrelated new process in that gap. Not treated as worth guarding
    against here: pid reuse that fast is vanishingly rare in practice (the
    OS cycles through the pid space before reusing), and every test using
    this helper only ever needs "genuinely not our own live process" for a
    few milliseconds of wall-clock test time, not a durable guarantee.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=5)
    return proc.pid


# ===========================================================================
# Pure helpers.
# ===========================================================================


class TestNormalizePath:
    def test_strips_leading_dot_slash(self):
        assert fc.normalize_path("./a/b.py") == "a/b.py"

    def test_strips_repeated_leading_dot_slash(self):
        assert fc.normalize_path("././a.py") == "a.py"

    def test_strips_trailing_slash(self):
        assert fc.normalize_path("a/b/") == "a/b"

    def test_strips_whitespace(self):
        assert fc.normalize_path("  a.py  ") == "a.py"

    def test_empty_stays_empty(self):
        assert fc.normalize_path("") == ""
        assert fc.normalize_path(None) == ""


class TestPathsOverlap:
    def test_disjoint_sets_no_overlap(self):
        assert fc.paths_overlap({"a.py"}, {"b.py"}) is False

    def test_shared_member_overlaps(self):
        assert fc.paths_overlap({"a.py", "b.py"}, {"b.py", "c.py"}) is True

    def test_empty_sets_no_overlap(self):
        assert fc.paths_overlap(set(), {"a.py"}) is False
        assert fc.paths_overlap(set(), set()) is False


class TestFindContest:
    def test_no_live_claims_no_contest(self):
        assert fc.find_contest({"a.py"}, [], "me") is None

    def test_overlap_with_other_agent_is_contest(self):
        live = [{"agent_id": "other", "paths": ["a.py", "b.py"]}]
        got = fc.find_contest({"a.py"}, live, "me")
        assert got is not None and got["agent_id"] == "other"

    def test_no_overlap_with_other_agent_no_contest(self):
        live = [{"agent_id": "other", "paths": ["b.py"]}]
        assert fc.find_contest({"a.py"}, live, "me") is None

    def test_own_claim_never_self_contests(self):
        live = [{"agent_id": "me", "paths": ["a.py"]}]
        assert fc.find_contest({"a.py"}, live, "me") is None

    def test_returns_first_matching_other_claim(self):
        live = [
            {"agent_id": "x", "paths": ["z.py"]},
            {"agent_id": "y", "paths": ["a.py"]},
        ]
        got = fc.find_contest({"a.py"}, live, "me")
        assert got["agent_id"] == "y"


class TestParseClaimRecord:
    def test_valid_record_parses(self):
        raw = json.dumps({"agent_id": "a1", "pid": 123, "claimed_at": 100.0, "paths": ["x.py", "./y.py"]})
        rec = fc._parse_claim_record(raw)
        assert rec == {"agent_id": "a1", "pid": 123, "claimed_at": 100.0, "paths": ["x.py", "y.py"]}

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not json",
            "[]",
            "null",
            json.dumps({"agent_id": "a1", "paths": ["x"]}),  # missing claimed_at
            json.dumps({"agent_id": "a1", "claimed_at": 1.0}),  # missing paths
            json.dumps({"claimed_at": 1.0, "paths": ["x"]}),  # missing agent_id
            json.dumps({"agent_id": "", "claimed_at": 1.0, "paths": ["x"]}),  # empty agent_id
            json.dumps({"agent_id": "a1", "claimed_at": "not-a-float", "paths": ["x"]}),
            json.dumps({"agent_id": "a1", "claimed_at": 1.0, "paths": "not-a-list"}),
            json.dumps({"agent_id": "a1", "claimed_at": 1.0, "paths": [1, 2]}),
        ],
    )
    def test_malformed_record_returns_none(self, raw):
        assert fc._parse_claim_record(raw) is None


# ===========================================================================
# Ledger I/O — read_live_claims prune-and-self-heal, write, release.
# ===========================================================================


class TestReadLiveClaims:
    def test_missing_dir_returns_empty(self, sandbox):
        assert fc.read_live_claims(str(sandbox.file_claims_dir), 300) == []

    def test_well_formed_claim_is_live(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "agent-a", ["x.py"], claimed_at=1000.0)
        live = fc.read_live_claims(d, ttl=300, now=1010.0)
        assert len(live) == 1 and live[0]["agent_id"] == "agent-a"

    def test_stale_claim_is_pruned(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "agent-a", ["x.py"], claimed_at=1000.0)
        live = fc.read_live_claims(d, ttl=300, now=1301.0)  # age 301 > ttl 300
        assert live == []
        assert not os.path.exists(fc.claim_path(d, "agent-a"))  # self-healed

    def test_malformed_claim_file_is_pruned(self, sandbox):
        d = str(sandbox.file_claims_dir)
        os.makedirs(d, exist_ok=True)
        path = fc.claim_path(d, "garbage")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json at all")
        live = fc.read_live_claims(d, ttl=300, now=1000.0)
        assert live == []
        assert not os.path.exists(path)

    def test_non_claim_files_are_ignored(self, sandbox):
        d = str(sandbox.file_claims_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "admission.lock"), "w", encoding="utf-8") as fh:
            fh.write("")
        assert fc.read_live_claims(d, ttl=300, now=1000.0) == []
        assert os.path.exists(os.path.join(d, "admission.lock"))  # untouched


class TestReadLiveClaimsPerPathTypeTTL:
    """FIX 1: a commit-mutex token self-heals at its OWN, shorter mutex_ttl
    while a real path bundled in the SAME record still honors the full ttl.
    """

    def test_mutex_token_expires_independently_of_bundled_real_path(self, sandbox):
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", ["x.py", mutex], claimed_at=1000.0)

        # age=90: past mutex_ttl(60) but well within ttl(300) -> mutex token
        # drops out of the live record's paths, real path (x.py) survives.
        live = fc.read_live_claims(d, ttl=300, now=1090.0, mutex_ttl=60)
        assert len(live) == 1
        assert live[0]["paths"] == ["x.py"]

    def test_real_path_only_record_unaffected_by_mutex_ttl(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)
        live = fc.read_live_claims(d, ttl=300, now=1090.0, mutex_ttl=60)
        assert live[0]["paths"] == ["x.py"]  # untouched: no mutex token here

    def test_record_with_only_a_mutex_token_disappears_from_live_after_mutex_ttl(self, sandbox):
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", [mutex], claimed_at=1000.0)
        # age=90 > mutex_ttl(60), but < ttl(300) -> filtered paths empty ->
        # record omitted from live (nothing left to contest on) though the
        # file is NOT yet self-healed (see next test).
        live = fc.read_live_claims(d, ttl=300, now=1090.0, mutex_ttl=60)
        assert live == []
        assert os.path.exists(fc.claim_path(d, "a1"))  # not yet removed

    def test_claim_file_is_removed_only_once_every_path_type_expires(self, sandbox):
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", ["x.py", mutex], claimed_at=1000.0)

        # age=301 > max(ttl=300, mutex_ttl=60) -> fully expired -> self-heals.
        live = fc.read_live_claims(d, ttl=300, now=1301.0, mutex_ttl=60)
        assert live == []
        assert not os.path.exists(fc.claim_path(d, "a1"))

    def test_leaked_mutex_only_claim_stops_contesting_a_new_commit_after_mutex_ttl(self, sandbox):
        # The scenario FIX 1 exists for: a leaked commit-mutex claim (crashed
        # holder never released) must stop wedging OTHER commits in that repo
        # within mutex_ttl, not the much longer real-path ttl.
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "leaked-holder", ["a.py", mutex], claimed_at=1000.0)

        # At age=90 (> mutex_ttl 60, < ttl 300): a NEW commit whose only
        # overlap is the mutex token (disjoint real path) now succeeds.
        claimed, contest = fc.try_claim_paths(
            d, ttl=300, agent_id="new-agent", paths=["b.py", mutex], lock_timeout=1.0,
            now=1090.0, mutex_ttl=60,
        )
        assert claimed is True and contest is None

    def test_mutex_default_ttl_used_when_not_passed_explicitly(self, sandbox, monkeypatch):
        monkeypatch.delenv("CSA_COMMIT_MUTEX_TTL_SEC", raising=False)
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", [mutex], claimed_at=1000.0)
        # No mutex_ttl kwarg -> falls back to mutex_ttl_from_env() -> default 60.
        live = fc.read_live_claims(d, ttl=300, now=1090.0)  # age 90 > default 60
        assert live == []


# ===========================================================================
# pid_alive / _owner_pid — #4670 item 1's dead-pid detection primitives.
# ===========================================================================


class TestPidAlive:
    def test_own_pid_is_alive(self):
        assert fc.pid_alive(os.getpid()) is True

    def test_real_exited_subprocess_pid_is_dead(self):
        assert fc.pid_alive(_dead_pid()) is False

    def test_process_lookup_error_is_dead(self, monkeypatch):
        def boom(pid, sig):
            raise ProcessLookupError()

        monkeypatch.setattr(fc.os, "kill", boom)
        assert fc.pid_alive(12345) is False

    def test_permission_error_is_treated_as_alive(self, monkeypatch):
        def boom(pid, sig):
            raise PermissionError()

        monkeypatch.setattr(fc.os, "kill", boom)
        assert fc.pid_alive(12345) is True

    def test_other_exception_fails_open_as_alive(self, monkeypatch):
        def boom(pid, sig):
            raise OSError("weird platform quirk")

        monkeypatch.setattr(fc.os, "kill", boom)
        assert fc.pid_alive(12345) is True

    @pytest.mark.parametrize("bad", [None, "123", 0, -5, 1.5, [], {}])
    def test_non_positive_or_non_int_pid_fails_open_as_alive(self, bad):
        assert fc.pid_alive(bad) is True


class TestOwnerPid:
    """BLOCKER 2 (Opus review, 2026-08-30): _owner_pid() must NEVER fall back
    to os.getpid() — that pid is knowably already dead by the time anyone
    reads it back (the one-shot hook subprocess), and recording it would
    convert an honestly UNKNOWN liveness into a confidently WRONG "dead"
    one, silently collapsing that record's TTL from 300s/60s down to 15s.
    Absent/unparseable CLAUDE_PID must record NO pid at all (None), which
    pid_alive() already treats as "alive" (fail open) — see
    TestPidAlive::test_non_positive_or_non_int_pid_fails_open_as_alive.
    """

    def test_uses_claude_pid_when_set(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PID", "4321")
        assert fc._owner_pid() == 4321

    def test_records_no_pid_when_claude_pid_absent(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PID", raising=False)
        assert fc._owner_pid() is None

    def test_records_no_pid_when_claude_pid_garbage(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PID", "not-a-number")
        assert fc._owner_pid() is None

    def test_records_no_pid_when_claude_pid_non_positive(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PID", "0")
        assert fc._owner_pid() is None
        monkeypatch.setenv("CLAUDE_PID", "-7")
        assert fc._owner_pid() is None

    def test_never_falls_back_to_this_process_own_pid(self, monkeypatch):
        """The exact BLOCKER 2 regression: _owner_pid() must not equal
        os.getpid() when CLAUDE_PID is unset — that would be the reverted,
        knowably-dead fallback."""
        monkeypatch.delenv("CLAUDE_PID", raising=False)
        assert fc._owner_pid() != os.getpid()


class TestWriteClaimRecordsOwnerPid:
    def test_write_claim_records_claude_pid(self, sandbox, monkeypatch):
        monkeypatch.setenv("CLAUDE_PID", "13579")
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)
        with open(fc.claim_path(d, "a1"), encoding="utf-8") as fh:
            body = json.load(fh)
        assert body["pid"] == 13579

    def test_write_claim_records_null_pid_not_getpid_when_claude_pid_absent(self, sandbox, monkeypatch):
        """BLOCKER 2 regression pin at the write-and-reread level: a claim
        written with no CLAUDE_PID in the environment must persist "pid":
        null, never this test process's own os.getpid() — and the resulting
        record must still be treated as LIVE (unaffected by the dead-pid
        clamp), because "no pid" means "liveness unknown", not "dead"."""
        monkeypatch.delenv("CLAUDE_PID", raising=False)
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)
        with open(fc.claim_path(d, "a1"), encoding="utf-8") as fh:
            body = json.load(fh)
        assert body["pid"] is None
        assert body["pid"] != os.getpid()
        # age 20 > dead_pid_ttl(15) would expire a CONFIRMED-dead record --
        # this one must survive, because an unknown pid fails open as alive.
        live = fc.read_live_claims(d, ttl=300, now=1020.0, dead_pid_ttl=15)
        assert len(live) == 1


# ===========================================================================
# Dead-pid self-heal — #4670 item 1: a claim whose owning process is
# confirmed dead self-heals at CSA_DEAD_PID_TTL_SEC (default 15s) instead of
# the record's normal (far longer) ttl/mutex_ttl, for BOTH its real-path and
# commit-mutex entries. A live (or undetermined) owner is unaffected.
# ===========================================================================


class TestDeadPidSelfHeal:
    def test_dead_pid_record_expires_at_dead_pid_ttl_not_full_ttl(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["x.py"], claimed_at=1000.0, pid=_dead_pid())
        # age=20: past dead_pid_ttl(15) but WAY within ttl(300) -> gone.
        live = fc.read_live_claims(d, ttl=300, now=1020.0, dead_pid_ttl=15)
        assert live == []

    def test_dead_pid_record_still_live_within_grace_window(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["x.py"], claimed_at=1000.0, pid=_dead_pid())
        # age=10: within dead_pid_ttl(15) -> a short grace, not instant removal.
        live = fc.read_live_claims(d, ttl=300, now=1010.0, dead_pid_ttl=15)
        assert len(live) == 1 and live[0]["paths"] == ["x.py"]

    def test_dead_pid_mutex_token_also_shortened(self, sandbox, tmp_path):
        d = str(sandbox.file_claims_dir)
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        _write_claim_raw(d, "crashed", ["x.py", mutex], claimed_at=1000.0, pid=_dead_pid())
        # age=20: past dead_pid_ttl(15) -> BOTH the real path and the mutex
        # token gone, even though mutex_ttl(60) alone would still be live.
        live = fc.read_live_claims(d, ttl=300, now=1020.0, mutex_ttl=60, dead_pid_ttl=15)
        assert live == []

    def test_live_pid_record_unaffected_by_dead_pid_ttl(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "alive", ["x.py"], claimed_at=1000.0, pid=os.getpid())
        # age=20 > dead_pid_ttl(15) but the pid is ALIVE -> still live,
        # governed by the normal 300s ttl (unaffected).
        live = fc.read_live_claims(d, ttl=300, now=1020.0, dead_pid_ttl=15)
        assert len(live) == 1

    def test_unknown_pid_field_treated_as_alive_not_dead(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "unknown-owner", ["x.py"], claimed_at=1000.0, pid=None)
        live = fc.read_live_claims(d, ttl=300, now=1020.0, dead_pid_ttl=15)
        assert len(live) == 1  # missing pid fails OPEN, not treated as dead

    def test_dead_pid_never_contests_a_new_commit_past_grace(self, sandbox):
        # The scenario item 1 exists for: a crashed session's leaked claim
        # must stop wedging a NEW commit within the short grace period, not
        # the full 300s TTL.
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["a.py"], claimed_at=1000.0, pid=_dead_pid())
        claimed, contest = fc.try_claim_paths(
            d,
            ttl=300,
            agent_id="new-agent",
            paths=["a.py"],
            lock_timeout=1.0,
            now=1020.0,
            dead_pid_ttl=15,
        )
        assert claimed is True and contest is None

    def test_reset_ledger_removes_dead_pid_record_early(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["a.py"], claimed_at=1000.0, pid=_dead_pid())
        removed = fc.reset_ledger(d, ttl=300, now=1020.0, dead_pid_ttl=15)
        assert removed == 1

    def test_reset_ledger_keeps_a_fresh_dead_pid_record(self, sandbox):
        # Mirrors read_live_claims' own grace window: reset_ledger must not
        # remove a dead-pid record any EARLIER than the grace period allows.
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["a.py"], claimed_at=1000.0, pid=_dead_pid())
        removed = fc.reset_ledger(d, ttl=300, now=1010.0, dead_pid_ttl=15)
        assert removed == 0

    def test_status_payload_reports_pid_alive_false_for_dead_owner(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["a.py"], claimed_at=1000.0, pid=_dead_pid())
        payload = fc.status_payload(d, ttl=300, now=1005.0, dead_pid_ttl=15)
        assert payload["live_claims"][0]["pid_alive"] is False

    def test_status_payload_reports_pid_alive_true_for_live_owner(self, sandbox):
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "alive", ["a.py"], claimed_at=1000.0, pid=os.getpid())
        payload = fc.status_payload(d, ttl=300, now=1005.0)
        assert payload["live_claims"][0]["pid_alive"] is True

    def test_dead_pid_ttl_default_shorter_than_mutex_ttl(self):
        assert fc.DEFAULT_DEAD_PID_TTL == 15
        assert fc.DEFAULT_DEAD_PID_TTL < fc.DEFAULT_MUTEX_TTL < fc.DEFAULT_TTL

    def test_dead_pid_ttl_default_used_when_not_passed_explicitly(self, sandbox, monkeypatch):
        monkeypatch.delenv("CSA_DEAD_PID_TTL_SEC", raising=False)
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["x.py"], claimed_at=1000.0, pid=_dead_pid())
        # No dead_pid_ttl kwarg -> falls back to dead_pid_ttl_from_env() -> 15.
        live = fc.read_live_claims(d, ttl=300, now=1020.0)  # age 20 > default 15
        assert live == []

    def test_none_pid_mutex_token_survives_the_full_mutex_ttl(self, sandbox, tmp_path):
        """Combination test 7 (round-3 review, FINDING 7): a record with NO
        pid at all (None -- e.g. a launchd-spawned `claude -p` session where
        CLAUDE_PID could not be resolved, see _owner_pid()'s docstring) is
        "liveness UNKNOWN", not "confirmed dead" -- it must be governed by
        the FULL mutex_ttl (60s default), never clamped to the short 15s
        dead-pid grace. This is the exact property protecting the nightly
        finishing loop job: its own commit-mutex claim must not self-heal
        out from under it mid-commit just because CLAUDE_PID happened to be
        unresolvable in its environment."""
        d = str(sandbox.file_claims_dir)
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        _write_claim_raw(d, "loop-job", [mutex], claimed_at=1000.0, pid=None)

        # age 59 < mutex_ttl(60) -> still live.
        live = fc.read_live_claims(d, ttl=300, now=1059.0, mutex_ttl=60, dead_pid_ttl=15)
        assert len(live) == 1

        # age 61 > mutex_ttl(60) -> now expired, on the NORMAL 60s schedule
        # (not the 15s dead-pid grace it would hit if pid_alive(None) were
        # ever wrongly treated as "dead").
        live = fc.read_live_claims(d, ttl=300, now=1061.0, mutex_ttl=60, dead_pid_ttl=15)
        assert live == []

    def test_clamp_only_shortens_never_lengthens_real_path_ttl(self, sandbox):
        """Combination test 7 (reviewer round 2): pin the "can only SHORTEN,
        never lengthen" invariant with a dead_pid_ttl LARGER than ttl -- an
        operator misconfiguration, or simply a very small ttl. The dead-pid
        clamp is min(ttl, dead_pid_ttl); it must never let dead_pid_ttl
        WIDEN a record's window past its own, shorter, real ttl."""
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["x.py"], claimed_at=1000.0, pid=_dead_pid())
        # ttl=10 is SHORTER than dead_pid_ttl=15: age=12 must still expire
        # this record -- min(10, 15) == 10, not 15.
        live = fc.read_live_claims(d, ttl=10, now=1012.0, dead_pid_ttl=15)
        assert live == []

    def test_clamp_only_shortens_never_lengthens_mutex_ttl(self, sandbox, tmp_path):
        """Same invariant, mutex-token side: dead_pid_ttl(15) > mutex_ttl(5)
        must still clamp to the SHORTER mutex_ttl, not widen to 15."""
        d = str(sandbox.file_claims_dir)
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        _write_claim_raw(d, "crashed", [mutex], claimed_at=1000.0, pid=_dead_pid())
        live = fc.read_live_claims(d, ttl=300, now=1007.0, mutex_ttl=5, dead_pid_ttl=15)
        assert live == []  # age 7 > min(5, 15) == 5

    def test_default_ratio_dead_owner_claim_self_heals_mid_poll_and_claims_through(self, sandbox):
        """Combination test 8: with the REAL default ratio
        (DEFAULT_DEAD_PID_TTL=15 < DEFAULT_MAX_WAIT=45), a dead owner's
        leaked claim ages past its dead-pid grace DURING a retrying commit's
        poll window, so that commit CLAIMS THROUGH with no deny at all -- it
        never even reaches gate 4's "leaked claim" honesty message (see
        pretooluse_bash._file_claim_block's own docstring: that message is
        only REACHABLE when dead_pid_ttl > max_wait, a non-default/
        misconfigured ratio -- defense in depth, not the everyday path).
        Injectable fake clock (mirrors test_agent_budget.py's paced_admit
        tests) so this runs instantly rather than over 45 real seconds.
        """
        d = str(sandbox.file_claims_dir)
        _write_claim_raw(d, "crashed", ["a.py"], claimed_at=0.0, pid=_dead_pid())

        # A fake wall/mono clock, both advanced in lockstep by sleep_fn, so
        # read_live_claims' wall-clock age and poll_claim_paths' own
        # mono-clock deadline check stay consistent with each other.
        state = {"t": 0.0}

        def wall_now():
            return state["t"]

        def mono_now():
            return state["t"]

        def sleep_fn(seconds):
            state["t"] += seconds

        def jitter_fn(base):
            return base  # deterministic -- no randomness to chase

        result = fc.poll_claim_paths(
            d,
            fc.DEFAULT_TTL,
            "retry-agent",
            ["a.py"],
            lock_timeout=1.0,
            max_wait=fc.DEFAULT_MAX_WAIT,
            poll=fc.DEFAULT_POLL,
            wall_now=wall_now,
            mono_now=mono_now,
            sleep_fn=sleep_fn,
            jitter_fn=jitter_fn,
            mutex_ttl=fc.DEFAULT_MUTEX_TTL,
            dead_pid_ttl=fc.DEFAULT_DEAD_PID_TTL,
        )
        assert result["claimed"] is True
        assert result["contest"] is None
        # Healed at ~dead_pid_ttl (15s), well before the full 45s budget --
        # never had to wait out the whole poll window. BOTH bounds pinned
        # (FINDING 8, round-3 review): the upper bound alone was one-sided
        # and would pass even for an instant-clamp regression (a bug that
        # made the grace period 0s instead of 15s) -- the lower bound proves
        # it genuinely waited out the dead_pid_ttl grace, not a broken clamp
        # that happens to also be faster than 45s.
        assert fc.DEFAULT_DEAD_PID_TTL <= result["waited"] < fc.DEFAULT_MAX_WAIT


class TestWriteClaim:
    def test_write_failure_is_swallowed(self, sandbox, monkeypatch):
        real_open = open

        def boom_open(path, *a, **k):
            if "claim-" in str(path):
                raise OSError("read-only")
            return real_open(path, *a, **k)

        monkeypatch.setattr("builtins.open", boom_open)
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)  # must not raise
        assert fc.read_live_claims(d, 300, now=1000.0) == []


class TestReleaseClaim:
    def test_release_removes_only_that_agents_claim(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "agent-a", ["x.py"], claimed_at=1000.0)
        fc._write_claim(d, "agent-b", ["y.py"], claimed_at=1000.0)
        fc.release_claim(d, "agent-a")
        live = {r["agent_id"] for r in fc.read_live_claims(d, ttl=300, now=1001.0)}
        assert live == {"agent-b"}

    def test_release_of_nonexistent_claim_is_a_noop(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.release_claim(d, "nobody")  # must not raise


# ===========================================================================
# try_claim_paths — the atomic all-or-nothing core.
# ===========================================================================


class TestTryClaimPaths:
    def test_first_claim_succeeds(self, sandbox):
        d = str(sandbox.file_claims_dir)
        claimed, contest = fc.try_claim_paths(d, 300, "a1", ["x.py", "y.py"], lock_timeout=1.0, now=1000.0)
        assert claimed is True and contest is None
        live = fc.read_live_claims(d, 300, now=1001.0)
        assert live[0]["paths"] == ["x.py", "y.py"]

    def test_overlapping_claim_by_other_agent_is_contested_and_claims_nothing(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "a1", ["x.py"], lock_timeout=1.0, now=1000.0)
        claimed, contest = fc.try_claim_paths(d, 300, "a2", ["x.py", "z.py"], lock_timeout=1.0, now=1001.0)
        assert claimed is False and contest["agent_id"] == "a1"
        # a2 must hold NOTHING — not even the non-overlapping z.py (all-or-nothing).
        live = fc.read_live_claims(d, 300, now=1002.0)
        assert {r["agent_id"] for r in live} == {"a1"}

    def test_disjoint_claim_by_other_agent_succeeds(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "a1", ["x.py"], lock_timeout=1.0, now=1000.0)
        claimed, contest = fc.try_claim_paths(d, 300, "a2", ["y.py"], lock_timeout=1.0, now=1001.0)
        assert claimed is True and contest is None

    def test_same_agent_reclaiming_is_not_self_contested(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "a1", ["x.py"], lock_timeout=1.0, now=1000.0)
        claimed, contest = fc.try_claim_paths(d, 300, "a1", ["x.py", "y.py"], lock_timeout=1.0, now=1001.0)
        assert claimed is True and contest is None

    def test_empty_path_set_is_a_noop_success(self, sandbox):
        d = str(sandbox.file_claims_dir)
        claimed, contest = fc.try_claim_paths(d, 300, "a1", [], lock_timeout=1.0, now=1000.0)
        assert claimed is True and contest is None
        assert fc.read_live_claims(d, 300, now=1000.0) == []

    def test_expired_claim_no_longer_contests(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "a1", ["x.py"], lock_timeout=1.0, now=1000.0)
        claimed, contest = fc.try_claim_paths(d, 300, "a2", ["x.py"], lock_timeout=1.0, now=1400.0)
        assert claimed is True and contest is None  # a1's claim aged out

    def test_fails_open_when_lock_unavailable(self, sandbox, monkeypatch):
        d = str(sandbox.file_claims_dir)

        class _NeverLocked:
            def __enter__(self):
                return False

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(fc.ab, "admission_lock", lambda *a, **k: _NeverLocked())
        claimed, contest = fc.try_claim_paths(d, 300, "a1", ["x.py"], lock_timeout=0.01, now=1000.0)
        assert claimed is True and contest is None  # fail OPEN, never wedge


# ===========================================================================
# poll_claim_paths — bounded, jittered retry. Clocks/sleep are injected so
# these run instantly regardless of the configured max_wait/poll interval.
# ===========================================================================


class _FakeClock:
    """A controllable monotonic+wall clock pair for deterministic poll tests."""

    def __init__(self, start=0.0):
        self.t = start
        self.sleeps = []

    def wall(self):
        return self.t

    def mono(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class TestPollClaimPaths:
    def test_claims_immediately_when_clear(self, sandbox):
        d = str(sandbox.file_claims_dir)
        clock = _FakeClock(1000.0)
        result = fc.poll_claim_paths(
            d, 300, "a1", ["x.py"], lock_timeout=1.0, max_wait=10.0, poll=1.0,
            wall_now=clock.wall, mono_now=clock.mono, sleep_fn=clock.sleep, jitter_fn=lambda b: b,
        )
        assert result == {"claimed": True, "contest": None, "waited": 0.0}
        assert clock.sleeps == []  # never had to wait

    def test_gives_up_after_max_wait_when_permanently_contested(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "holder", ["x.py"], lock_timeout=1.0, now=1000.0)
        clock = _FakeClock(1000.0)
        result = fc.poll_claim_paths(
            d, 300, "waiter", ["x.py"], lock_timeout=1.0, max_wait=5.0, poll=1.0,
            wall_now=clock.wall, mono_now=clock.mono, sleep_fn=clock.sleep, jitter_fn=lambda b: b,
        )
        assert result["claimed"] is False
        assert result["contest"]["agent_id"] == "holder"
        assert result["waited"] >= 5.0
        # Never partially claimed x.py while waiting.
        assert {r["agent_id"] for r in fc.read_live_claims(d, 300, now=clock.t)} == {"holder"}

    def test_succeeds_once_holder_releases_mid_poll(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "holder", ["x.py"], lock_timeout=1.0, now=1000.0)
        clock = _FakeClock(1000.0)

        # Release the blocking claim after the first failed attempt, simulating
        # the holder finishing its commit mid-wait.
        real_sleep = clock.sleep
        released = {"done": False}

        def sleep_and_release(seconds):
            real_sleep(seconds)
            if not released["done"]:
                fc.release_claim(d, "holder")
                released["done"] = True

        result = fc.poll_claim_paths(
            d, 300, "waiter", ["x.py"], lock_timeout=1.0, max_wait=10.0, poll=1.0,
            wall_now=clock.wall, mono_now=clock.mono, sleep_fn=sleep_and_release, jitter_fn=lambda b: b,
        )
        assert result["claimed"] is True
        assert {r["agent_id"] for r in fc.read_live_claims(d, 300, now=clock.t)} == {"waiter"}


# ===========================================================================
# REJECTED DESIGN, permanently pinned — same-CLAUDE_PID contest-time widening.
#
# 2026-09-05: a first attempt at fixing the "leak on hook failure" bug (see
# posttooluse_bash.py's module docstring, and file_claims.py's own module
# docstring's "SAME-SESSION RECLAIM" section for the full incident) made
# find_contest() treat a live claim as self-owned whenever its recorded pid
# equalled the CURRENT attempt's own CLAUDE_PID, letting a same-owner retry
# skip/reclaim it. That design was BLOCKED at review with a live repro: this
# runtime's DEFAULT execution mode is up to 30 PARALLEL sub-agents fanned out
# from one orchestrating session, and every one of them shares that ONE
# session's CLAUDE_PID (confirmed empirically: a sub-agent's own Bash
# environment shows CLAUDE_PID equal to the single top-level CLI process).
# pid can distinguish DIFFERENT sessions but NEVER concurrent same-session
# actors -- there is no such thing as "this pid, but a different concurrent
# commit" to tell apart. Any logic that RELEASES or bypasses a claim keyed on
# pid-equality alone therefore lets two truly concurrent same-session
# sub-agent commits in the SAME repo claim through each other's live
# per-repo commit mutex (breaking CLAUDE.md §3's "only one commit in flight
# per repo at a time") and even delete each other's claim files mid-commit
# (breaking §2's path-contest guarantee) -- the actual fix moved to
# RELEASE-TIME instead (wiring the PostToolUseFailure hook event so a call
# only ever releases its OWN tool_use_id's claim, safe by construction; see
# posttooluse_bash.py). This class pins the corrected invariant permanently
# so no future "pid looks like a safe session-identity signal" attempt
# reintroduces the same break without at least failing this test first.
# ===========================================================================


class TestSameSessionConcurrentCommitsStillContest:
    """The reviewer's explicitly-named missing cell: {same CLAUDE_PID} x
    {two CONCURRENT live attempts} must STILL contest. Ambient CLAUDE_PID is
    cleared by the module-wide autouse fixture below, so any pid this class
    sets is deliberate, not incidental.
    """

    def test_two_concurrent_same_pid_commits_same_repo_mutex_still_contest(self, sandbox, monkeypatch, tmp_path):
        """Two PARALLEL sub-agents of the SAME session (same CLAUDE_PID,
        different tool_use_ids) each committing DIFFERENT files in the SAME
        repo. Sub-agent B's disjoint real path must still be blocked by the
        per-repo commit mutex sub-agent A holds -- mirrors the reviewer's
        own repro script exactly (parallel_subagents scenario, part 1).
        """
        d = str(sandbox.file_claims_dir)
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        monkeypatch.setenv("CLAUDE_PID", "70001")  # BOTH sub-agents share this

        claimed_a, _ = fc.try_claim_paths(d, 300, "toolu-A", ["a.py", mutex], lock_timeout=1.0, now=1000.0)
        assert claimed_a is True

        claimed_b, contest_b = fc.try_claim_paths(d, 300, "toolu-B", ["b.py", mutex], lock_timeout=1.0, now=1000.5)
        assert claimed_b is False  # MUST still contest -- same session, but a live CONCURRENT commit
        assert contest_b is not None and contest_b["agent_id"] == "toolu-A"

        # A's claim must survive untouched -- B must not have released it.
        live = fc.read_live_claims(d, ttl=300, now=1001.0)
        assert {r["agent_id"] for r in live} == {"toolu-A"}

    def test_two_concurrent_same_pid_commits_same_file_still_contest(self, sandbox, monkeypatch):
        """Same invariant, overlapping-path variant (reviewer's repro,
        part 2): two same-session sub-agents committing the SAME file
        concurrently -- the second must still be blocked, not silently
        allowed to claim through and clobber the first's in-flight commit.
        """
        d = str(sandbox.file_claims_dir)
        monkeypatch.setenv("CLAUDE_PID", "70002")

        claimed_x, _ = fc.try_claim_paths(d, 300, "toolu-X", ["shared.py"], lock_timeout=1.0, now=1000.0)
        assert claimed_x is True

        claimed_y, contest_y = fc.try_claim_paths(d, 300, "toolu-Y", ["shared.py"], lock_timeout=1.0, now=1000.5)
        assert claimed_y is False
        assert contest_y is not None and contest_y["agent_id"] == "toolu-X"

        live = fc.read_live_claims(d, ttl=300, now=1001.0)
        assert {r["agent_id"] for r in live} == {"toolu-X"}

    def test_find_contest_has_no_pid_parameter(self):
        """Signature pin: find_contest takes exactly (target_paths,
        live_claims, self_agent_id) -- no pid-shaped parameter of any name.
        A future re-introduction of contest-time pid widening would need to
        change this signature, which this test would catch immediately."""
        import inspect

        params = list(inspect.signature(fc.find_contest).parameters)
        assert params == ["target_paths", "live_claims", "self_agent_id"]

    def test_try_claim_paths_has_no_pid_parameter(self):
        import inspect

        params = list(inspect.signature(fc.try_claim_paths).parameters)
        assert "self_owner_pid" not in params
        assert not any("pid" in p.lower() for p in params if p not in ("dead_pid_ttl",))

    def test_no_self_owned_reclaim_helper_exists(self):
        """The release-in-lock helper this rejected design added
        (self_owned_stale_agent_ids) must not exist on the module -- its
        entire premise (pid identifies a single concurrent actor) was the
        root cause of the break."""
        assert not hasattr(fc, "self_owned_stale_agent_ids")
        assert not hasattr(fc, "_same_live_owner")


# ===========================================================================
# Deadlock-proof scenario — the point of the whole module.
#
# Classic circular-wait deadlock needs hold-and-wait: agent A holds X and waits
# on Y while agent B holds Y and waits on X. Prove that shape is unreachable
# here: two agents claiming the SAME two paths in OPPOSITE order never leaves
# either agent holding a partial set.
# ===========================================================================


class TestNoPartialHoldDeadlock:
    def test_opposite_order_claims_never_partially_interleave(self, sandbox):
        d = str(sandbox.file_claims_dir)
        # Agent A wants [X, Y]; Agent B wants [Y, X] (reversed) — the classic
        # setup that deadlocks under incremental (one-resource-at-a-time)
        # locking. Claim it as ONE call each (this module never offers a
        # partial/incremental claim API), interleaved with A going first.
        claimed_a, contest_a = fc.try_claim_paths(d, 300, "A", ["X", "Y"], lock_timeout=1.0, now=1000.0)
        claimed_b, contest_b = fc.try_claim_paths(d, 300, "B", ["Y", "X"], lock_timeout=1.0, now=1000.0)

        assert claimed_a is True
        assert claimed_b is False
        assert contest_b["agent_id"] == "A"
        # B holds NEITHER X nor Y — no partial state for a cycle to form on.
        live = fc.read_live_claims(d, 300, now=1000.0)
        assert {r["agent_id"] for r in live} == {"A"}
        assert set(live[0]["paths"]) == {"X", "Y"}

    def test_many_agents_many_overlapping_claims_exactly_one_wins_per_path_set(self, sandbox):
        d = str(sandbox.file_claims_dir)
        # 5 agents all racing for overlapping windows over a shared path list;
        # every attempt must be all-or-nothing, so the live set can never show
        # two agents both holding the same path.
        attempts = [
            ("a1", ["p1", "p2"]),
            ("a2", ["p2", "p3"]),
            ("a3", ["p3", "p4"]),
            ("a4", ["p1", "p4"]),
            ("a5", ["p5"]),
        ]
        for agent_id, paths in attempts:
            fc.try_claim_paths(d, 300, agent_id, paths, lock_timeout=1.0, now=1000.0)
        live = fc.read_live_claims(d, 300, now=1000.0)
        seen_paths = {}
        for rec in live:
            for p in rec["paths"]:
                assert p not in seen_paths, f"path {p} claimed by both {seen_paths[p]} and {rec['agent_id']}"
                seen_paths[p] = rec["agent_id"]
        # a1 claims first and wins p1,p2; a5's p5 is disjoint from everything a1
        # holds so it always succeeds too (no other agent contests p5).
        assert seen_paths["p1"] == "a1" and seen_paths["p2"] == "a1"
        assert seen_paths["p5"] == "a5"


# ===========================================================================
# status_payload / reset_ledger / CLI main() — light operator-surface coverage.
# ===========================================================================


class TestStatusAndReset:
    def test_status_payload_lists_live_claims(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)
        payload = fc.status_payload(d, ttl=300, now=1010.0)
        assert payload["ttl_sec"] == 300
        assert len(payload["live_claims"]) == 1
        assert payload["live_claims"][0]["agent_id"] == "a1"
        assert payload["live_claims"][0]["age_sec"] == 10.0

    def test_reset_removes_only_stale(self, sandbox):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "fresh", ["x.py"], claimed_at=1000.0)
        fc._write_claim(d, "stale", ["y.py"], claimed_at=100.0)
        removed = fc.reset_ledger(d, ttl=300, now=1000.0)
        assert removed == 1
        remaining = {r["agent_id"] for r in fc.read_live_claims(d, 300, now=1000.0)}
        assert remaining == {"fresh"}

    def test_reset_keeps_a_record_whose_real_path_is_still_within_ttl(self, sandbox):
        # A record whose mutex token has aged past its shorter mutex_ttl but
        # whose bundled real path is still within the longer ttl must NOT be
        # removed by reset_ledger — mirrors read_live_claims' full-removal
        # threshold (max(ttl, mutex_ttl)), not the mutex's own shorter one.
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", ["x.py", mutex], claimed_at=1000.0)
        removed = fc.reset_ledger(d, ttl=300, now=1090.0, mutex_ttl=60)  # age 90
        assert removed == 0
        assert os.path.exists(fc.claim_path(d, "a1"))

    def test_reset_removes_once_every_path_type_expires(self, sandbox):
        d = str(sandbox.file_claims_dir)
        repo = str(sandbox.home / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc._write_claim(d, "a1", ["x.py", mutex], claimed_at=1000.0)
        removed = fc.reset_ledger(d, ttl=300, now=1301.0, mutex_ttl=60)  # age 301
        assert removed == 1
        assert not os.path.exists(fc.claim_path(d, "a1"))

    def test_reset_missing_dir_is_a_noop(self, sandbox):
        assert fc.reset_ledger(str(sandbox.file_claims_dir), ttl=300, now=1000.0) == 0

    def test_reset_ignores_non_claim_files(self, sandbox):
        d = str(sandbox.file_claims_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "admission.lock"), "w", encoding="utf-8") as fh:
            fh.write("")
        assert fc.reset_ledger(d, ttl=300, now=1000.0) == 0
        assert os.path.exists(os.path.join(d, "admission.lock"))

    def test_reset_removes_malformed_claim(self, sandbox):
        d = str(sandbox.file_claims_dir)
        os.makedirs(d, exist_ok=True)
        path = fc.claim_path(d, "garbage")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json")
        assert fc.reset_ledger(d, ttl=300, now=1000.0) == 1
        assert not os.path.exists(path)


# ===========================================================================
# Commit mutex — "only one commit in flight per repo at a time". mutex_token/
# is_mutex_token/mutex_enabled, paths_overlap's new prefix-awareness, and
# status_payload splitting the token out for operator-facing views.
# ===========================================================================


class TestMutexToken:
    def test_token_is_prefixed_and_realpathed(self, tmp_path):
        tok = fc.mutex_token(str(tmp_path))
        assert tok.startswith(fc.MUTEX_PREFIX)
        assert tok == fc.MUTEX_PREFIX + os.path.realpath(str(tmp_path))

    def test_is_mutex_token_true_for_a_token(self, tmp_path):
        assert fc.is_mutex_token(fc.mutex_token(str(tmp_path))) is True

    def test_is_mutex_token_false_for_a_real_path(self):
        assert fc.is_mutex_token("modules/voice/a.py") is False
        assert fc.is_mutex_token("") is False
        assert fc.is_mutex_token(None) is False

    def test_token_survives_normalize_path_intact(self, tmp_path):
        tok = fc.mutex_token(str(tmp_path))
        assert fc.normalize_path(tok) == tok

    def test_two_spellings_of_the_same_repo_collapse_to_one_token(self, tmp_path):
        # A relative vs. absolute path to the same dir must produce the SAME
        # token (realpath'd), so two agents spelling the repo differently
        # still contest each other.
        rel = str(tmp_path)
        assert fc.mutex_token(rel) == fc.mutex_token(os.path.realpath(rel))


class TestMutexEnabled:
    def test_enabled_by_default(self):
        assert fc.mutex_enabled({}) is True

    def test_disabled_via_env(self):
        assert fc.mutex_enabled({"CSA_NO_COMMIT_MUTEX": "1"}) is False

    def test_other_values_leave_it_enabled(self):
        assert fc.mutex_enabled({"CSA_NO_COMMIT_MUTEX": "0"}) is True
        assert fc.mutex_enabled({"CSA_NO_COMMIT_MUTEX": "true"}) is True


class TestPathsOverlapPrefixAware:
    def test_directory_pathspec_overlaps_a_file_inside_it(self):
        assert fc.paths_overlap({"modules"}, {"modules/x.py"}) is True
        assert fc.paths_overlap({"modules/x.py"}, {"modules"}) is True

    def test_sibling_directories_do_not_overlap(self):
        assert fc.paths_overlap({"modules/voice"}, {"modules/billing"}) is False

    def test_equal_paths_still_overlap(self):
        assert fc.paths_overlap({"a.py"}, {"a.py"}) is True

    def test_prefix_string_without_separator_does_not_overlap(self):
        # "modules" must not overlap "modules2/x.py" — the prefix check
        # requires a "/" boundary, not a bare string prefix.
        assert fc.paths_overlap({"modules"}, {"modules2/x.py"}) is False

    def test_two_repo_mutex_tokens_for_different_repos_do_not_overlap(self, tmp_path):
        a = tmp_path / "repo-a"
        b = tmp_path / "repo-b"
        a.mkdir()
        b.mkdir()
        assert fc.paths_overlap({fc.mutex_token(str(a))}, {fc.mutex_token(str(b))}) is False

    def test_same_repo_mutex_token_overlaps_itself(self, tmp_path):
        tok = fc.mutex_token(str(tmp_path))
        assert fc.paths_overlap({tok}, {tok}) is True


class TestCommitMutexClaiming:
    def test_disjoint_real_paths_same_repo_mutex_contest(self, tmp_path):
        d = str(tmp_path / "claims")
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        claimed_a, _ = fc.try_claim_paths(d, 300, "agent-a", ["a.py", mutex], lock_timeout=1.0)
        assert claimed_a is True
        # agent-b's real path is DISJOINT from a.py, but the SAME repo mutex
        # token makes it contested anyway.
        claimed_b, contest = fc.try_claim_paths(d, 300, "agent-b", ["b.py", mutex], lock_timeout=1.0)
        assert claimed_b is False
        assert contest["agent_id"] == "agent-a"

    def test_different_repos_do_not_contest(self, tmp_path):
        d = str(tmp_path / "claims")
        repo_a = str(tmp_path / "repo-a")
        repo_b = str(tmp_path / "repo-b")
        os.makedirs(repo_a, exist_ok=True)
        os.makedirs(repo_b, exist_ok=True)
        claimed_a, _ = fc.try_claim_paths(d, 300, "agent-a", ["x.py", fc.mutex_token(repo_a)], lock_timeout=1.0)
        claimed_b, _ = fc.try_claim_paths(d, 300, "agent-b", ["y.py", fc.mutex_token(repo_b)], lock_timeout=1.0)
        assert claimed_a is True
        assert claimed_b is True  # no shared repo -> no contest

    def test_release_clears_the_mutex_for_the_next_claimant(self, tmp_path):
        d = str(tmp_path / "claims")
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        fc.try_claim_paths(d, 300, "agent-a", ["a.py", mutex], lock_timeout=1.0)
        fc.release_claim(d, "agent-a")
        claimed_b, _ = fc.try_claim_paths(d, 300, "agent-b", ["b.py", mutex], lock_timeout=1.0)
        assert claimed_b is True


class TestSplitMutexPaths:
    """FIX 2: the reusable (real_paths, mutex_repos) splitter, factored out
    of status_payload() so pretooluse_bash.py's own "would-wait" log line can
    reuse it too instead of dumping the raw MUTEX_PREFIX token inline.
    """

    def test_splits_real_paths_and_mutex_tokens(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        real, mutex_repos = fc.split_mutex_paths(["a.py", mutex, "b.py"])
        assert real == ["a.py", "b.py"]
        assert mutex_repos == [os.path.realpath(repo)]

    def test_no_mutex_tokens_yields_empty_second_list(self):
        real, mutex_repos = fc.split_mutex_paths(["a.py", "b.py"])
        assert real == ["a.py", "b.py"]
        assert mutex_repos == []

    def test_only_mutex_tokens_yields_empty_first_list(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        mutex = fc.mutex_token(repo)
        real, mutex_repos = fc.split_mutex_paths([mutex])
        assert real == []
        assert mutex_repos == [os.path.realpath(repo)]

    def test_empty_input_yields_two_empty_lists(self):
        assert fc.split_mutex_paths([]) == ([], [])
        assert fc.split_mutex_paths(None) == ([], [])

    def test_non_string_entries_are_skipped(self):
        real, mutex_repos = fc.split_mutex_paths(["a.py", None, 5, "b.py"])
        assert real == ["a.py", "b.py"]
        assert mutex_repos == []

    def test_multiple_mutex_tokens_for_different_repos(self, tmp_path):
        repo_a = str(tmp_path / "repo-a")
        repo_b = str(tmp_path / "repo-b")
        os.makedirs(repo_a, exist_ok=True)
        os.makedirs(repo_b, exist_ok=True)
        real, mutex_repos = fc.split_mutex_paths([fc.mutex_token(repo_a), "x.py", fc.mutex_token(repo_b)])
        assert real == ["x.py"]
        assert mutex_repos == [os.path.realpath(repo_a), os.path.realpath(repo_b)]


class TestStatusPayloadSplitsMutex:
    def test_mutex_token_split_into_its_own_field(self, tmp_path):
        d = str(tmp_path / "claims")
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        fc._write_claim(d, "a1", ["x.py", fc.mutex_token(repo)], claimed_at=1000.0)
        payload = fc.status_payload(d, ttl=300, now=1010.0)
        entry = payload["live_claims"][0]
        assert entry["paths"] == ["x.py"]
        assert entry["commit_mutex"] == [os.path.realpath(repo)]

    def test_mutex_only_field_reflects_read_live_claims_filtering(self, tmp_path):
        # status_payload must never show an already-expired mutex token as
        # still "live" -- it inherits read_live_claims' per-type filtering.
        d = str(tmp_path / "claims")
        repo = str(tmp_path / "repo")
        os.makedirs(repo, exist_ok=True)
        fc._write_claim(d, "a1", ["x.py", fc.mutex_token(repo)], claimed_at=1000.0)
        payload = fc.status_payload(d, ttl=300, now=1090.0, mutex_ttl=60)  # age 90 > mutex_ttl
        entry = payload["live_claims"][0]
        assert entry["paths"] == ["x.py"]
        assert entry["commit_mutex"] == []  # mutex token aged out, real path didn't

    def test_no_mutex_claim_has_empty_commit_mutex_list(self, tmp_path):
        d = str(tmp_path / "claims")
        fc._write_claim(d, "a1", ["x.py"], claimed_at=1000.0)
        payload = fc.status_payload(d, ttl=300, now=1010.0)
        assert payload["live_claims"][0]["commit_mutex"] == []


class TestEnvConfig:
    def test_defaults(self):
        assert fc.ttl_from_env({}) == fc.DEFAULT_TTL
        assert fc.max_wait_from_env({}) == fc.DEFAULT_MAX_WAIT
        assert fc.poll_from_env({}) == fc.DEFAULT_POLL
        assert fc.mutex_ttl_from_env({}) == fc.DEFAULT_MUTEX_TTL
        assert fc.dead_pid_ttl_from_env({}) == fc.DEFAULT_DEAD_PID_TTL

    def test_overrides(self):
        env = {
            "CSA_FILE_CLAIM_TTL_SEC": "60",
            "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "5",
            "CSA_COMMIT_CLAIM_POLL_SEC": "0.5",
            "CSA_COMMIT_MUTEX_TTL_SEC": "30",
            "CSA_DEAD_PID_TTL_SEC": "7",
        }
        assert fc.ttl_from_env(env) == 60
        assert fc.max_wait_from_env(env) == 5.0
        assert fc.poll_from_env(env) == 0.5
        assert fc.mutex_ttl_from_env(env) == 30
        assert fc.dead_pid_ttl_from_env(env) == 7

    def test_garbage_falls_back_to_default(self):
        env = {"CSA_FILE_CLAIM_TTL_SEC": "not-a-number"}
        assert fc.ttl_from_env(env) == fc.DEFAULT_TTL

    def test_mutex_ttl_garbage_falls_back_to_default(self):
        assert fc.mutex_ttl_from_env({"CSA_COMMIT_MUTEX_TTL_SEC": "nope"}) == fc.DEFAULT_MUTEX_TTL

    def test_dead_pid_ttl_garbage_falls_back_to_default(self):
        assert fc.dead_pid_ttl_from_env({"CSA_DEAD_PID_TTL_SEC": "nope"}) == fc.DEFAULT_DEAD_PID_TTL

    def test_mutex_ttl_default_is_shorter_than_real_path_ttl(self):
        # The whole point of FIX 1: the mutex must self-heal FAR sooner than a
        # real path claim (a leaked mutex must not wedge a repo's commits for
        # anywhere near CSA_FILE_CLAIM_TTL_SEC's full 300s).
        assert fc.DEFAULT_MUTEX_TTL == 60
        assert fc.DEFAULT_MUTEX_TTL < fc.DEFAULT_TTL

    def test_max_wait_default_is_45_under_the_60s_hook_timeout(self):
        # Raised from the original 20s so a commit-mutex wait — now common,
        # since every commit in a repo contests every other — has real room
        # to clear before giving up, while staying comfortably under the
        # PreToolUse hook's own 60s timeout.
        assert fc.DEFAULT_MAX_WAIT == 45.0


class TestCLIMain:
    def _run(self, monkeypatch, capsys, argv):
        rc = fc.main(argv)
        out = capsys.readouterr().out
        return rc, out

    def test_disabled_short_circuits(self, sandbox, monkeypatch, capsys):
        monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
        rc, out = self._run(monkeypatch, capsys, ["status"])
        assert rc == 0 and out == ""

    def test_status_prints_json(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["status"])
        assert rc == 0
        assert json.loads(out)["live_claims"] == []

    def test_claim_check_then_contest(self, sandbox, monkeypatch, capsys):
        rc1, out1 = self._run(monkeypatch, capsys, ["claim-check", "a1", "x.py"])
        assert rc1 == 0 and "OK claimed" in out1
        rc2, out2 = self._run(monkeypatch, capsys, ["claim-check", "a2", "x.py"])
        assert rc2 == 1 and "CONTESTED" in out2

    def test_release_then_status_empty(self, sandbox, monkeypatch, capsys):
        self._run(monkeypatch, capsys, ["claim-check", "a1", "x.py"])
        rc, out = self._run(monkeypatch, capsys, ["release", "a1"])
        assert rc == 0 and "OK released" in out
        _, status_out = self._run(monkeypatch, capsys, ["status"])
        assert json.loads(status_out)["live_claims"] == []

    def test_doctor_smoke(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["doctor"])
        assert rc == 0 and "file_claims doctor" in out

    def test_doctor_reports_mutex_ttl(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["doctor"])
        assert rc == 0
        assert "mutex_ttl_sec  : 60 (CSA_COMMIT_MUTEX_TTL_SEC)" in out

    def test_reset_smoke(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["reset"])
        assert rc == 0 and "OK reset" in out

    def test_claim_check_missing_args_usage_error(self, sandbox, monkeypatch, capsys):
        rc = fc.main(["claim-check", "only-agent-id"])
        err = capsys.readouterr().err
        assert rc == 2 and "usage" in err

    def test_release_missing_args_usage_error(self, sandbox, monkeypatch, capsys):
        rc = fc.main(["release"])
        err = capsys.readouterr().err
        assert rc == 2 and "usage" in err

    def test_argv_defaults_to_sys_argv(self, sandbox, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["file_claims.py", "status"])
        rc, out = self._run(monkeypatch, capsys, None)
        assert rc == 0 and "live_claims" in out

    def test_main_swallows_unexpected_error(self, sandbox, monkeypatch, capsys):
        monkeypatch.setattr(fc, "ttl_from_env", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        rc = fc.main(["status"])
        assert rc == 0

    def test_unknown_subcommand_degrades_open(self, sandbox, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, ["bogus"])
        assert rc == 0  # advisory: never a hard failure

    def test_main_never_raises_on_stdin_free_path(self, sandbox, monkeypatch, capsys):
        # status/doctor/reset never touch stdin; smoke-test the __main__ guard
        # indirectly by calling main() with no argv (defaults to "status").
        rc, out = self._run(monkeypatch, capsys, [])
        assert rc == 0
        assert "live_claims" in out
