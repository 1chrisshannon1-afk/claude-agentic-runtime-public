"""Hermetic tests for hooks/commit_authors.py — the per-(repo,sha) commit
authorship ledger.

Covers: the record()/author_of() round trip, first-write-wins idempotency,
repo-scoped lookups (no cross-repo collision on a reused sha), the pure
parse-ledger helper's tolerance of blank/garbage/malformed lines, pruning
(bounds growth, keeps recent entries, never loses a just-appended line, keeps
only the newest N when still over the cap after the age cutoff), and the
fail-OPEN behavior when the shared admission_lock is unavailable (record()
still appends; only the prune step is skipped).

All tests write to a throwaway tmp_path ledger file — never the real
~/.claude/.review_state/commit_authors.
"""

from __future__ import annotations

import json
import os

import agent_budget as ab
import commit_authors as ca

# ===========================================================================
# Pure parsing — no filesystem.
# ===========================================================================


class TestParseLine:
    def test_well_formed_line_parses(self):
        line = json.dumps({"ts": 100.0, "repo": "/r", "sha": "abc", "session": "s1"})
        assert ca._parse_line(line) == {"ts": 100.0, "repo": "/r", "sha": "abc", "session": "s1"}

    def test_blank_line_is_none(self):
        assert ca._parse_line("") is None
        assert ca._parse_line("   \n") is None

    def test_invalid_json_is_none(self):
        assert ca._parse_line("not json at all") is None
        assert ca._parse_line("{unclosed") is None

    def test_non_dict_json_is_none(self):
        assert ca._parse_line("[1,2,3]") is None
        assert ca._parse_line('"a string"') is None
        assert ca._parse_line("42") is None

    def test_missing_field_is_none(self):
        assert ca._parse_line(json.dumps({"ts": 1, "repo": "/r", "sha": "s"})) is None  # no session
        assert ca._parse_line(json.dumps({"ts": 1, "sha": "s", "session": "x"})) is None  # no repo

    def test_blank_or_wrong_typed_field_is_none(self):
        assert ca._parse_line(json.dumps({"ts": 1, "repo": "", "sha": "s", "session": "x"})) is None
        assert ca._parse_line(json.dumps({"ts": 1, "repo": 5, "sha": "s", "session": "x"})) is None
        assert ca._parse_line(json.dumps({"ts": "nope", "repo": "/r", "sha": "s", "session": "x"})) is None

    def test_ts_accepts_numeric_string(self):
        rec = ca._parse_line(json.dumps({"ts": "100.5", "repo": "/r", "sha": "s", "session": "x"}))
        assert rec == {"ts": 100.5, "repo": "/r", "sha": "s", "session": "x"}


class TestParseLedger:
    def test_skips_unparseable_lines_keeps_well_formed(self):
        text = "\n".join(
            [
                "not json",
                json.dumps({"ts": 1, "repo": "/r", "sha": "a", "session": "s1"}),
                "",
                "{broken",
                json.dumps({"ts": 2, "repo": "/r", "sha": "b", "session": "s2"}),
            ]
        )
        recs = ca.parse_ledger(text)
        assert [r["sha"] for r in recs] == ["a", "b"]

    def test_empty_text_is_empty_list(self):
        assert ca.parse_ledger("") == []

    def test_never_raises_on_odd_input(self):
        assert ca.parse_ledger("\x00\x01garbage\nmore\n") == []


# ===========================================================================
# record() / author_of() — the round trip.
# ===========================================================================


class TestRecordAndLookup:
    def test_roundtrip(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True
        assert ca.author_of(ledger, "/repo", "sha1") == "session-a"

    def test_first_write_wins_second_call_does_not_override(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True
        # A second, different session records for the SAME (repo, sha):
        # no-op — the first author stays on record.
        assert ca.record(ledger, "/repo", "sha1", "session-b", now=1001.0) is False
        assert ca.author_of(ledger, "/repo", "sha1") == "session-a"
        # Exactly one line was written.
        with open(ledger, encoding="utf-8") as fh:
            assert len(fh.readlines()) == 1

    def test_different_repos_same_sha_dont_collide(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        assert ca.record(ledger, "/repo-a", "deadbeef", "session-a", now=1000.0) is True
        assert ca.record(ledger, "/repo-b", "deadbeef", "session-b", now=1000.0) is True
        assert ca.author_of(ledger, "/repo-a", "deadbeef") == "session-a"
        assert ca.author_of(ledger, "/repo-b", "deadbeef") == "session-b"

    def test_different_sha_same_repo_both_recorded(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0)
        ca.record(ledger, "/repo", "sha2", "session-b", now=1001.0)
        assert ca.author_of(ledger, "/repo", "sha1") == "session-a"
        assert ca.author_of(ledger, "/repo", "sha2") == "session-b"

    def test_author_of_missing_file_is_none(self, tmp_path):
        assert ca.author_of(str(tmp_path / "nope"), "/repo", "sha1") is None

    def test_author_of_garbage_file_is_none(self, tmp_path):
        ledger = tmp_path / "commit_authors"
        ledger.write_text("not json\n{also broken\n")
        assert ca.author_of(str(ledger), "/repo", "sha1") is None

    def test_author_of_unparseable_lines_skipped_well_formed_still_found(self, tmp_path):
        ledger = tmp_path / "commit_authors"
        ledger.write_text(
            "garbage line\n"
            + json.dumps({"ts": 1, "repo": "/repo", "sha": "sha1", "session": "s1"})
            + "\n"
        )
        assert ca.author_of(str(ledger), "/repo", "sha1") == "s1"

    def test_author_of_missing_args_is_none(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0)
        assert ca.author_of("", "/repo", "sha1") is None
        assert ca.author_of(ledger, "", "sha1") is None
        assert ca.author_of(ledger, "/repo", "") is None

    def test_record_missing_args_is_false(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        assert ca.record(ledger, "", "sha1", "s1") is False
        assert ca.record(ledger, "/repo", "", "s1") is False
        assert ca.record(ledger, "/repo", "sha1", "") is False
        assert ca.record("", "/repo", "sha1", "s1") is False
        assert not os.path.exists(ledger)

    def test_record_creates_parent_dir(self, tmp_path):
        ledger = str(tmp_path / "nested" / "dir" / "commit_authors")
        assert ca.record(ledger, "/repo", "sha1", "s1", now=1000.0) is True
        assert os.path.isfile(ledger)

    def test_record_default_now_uses_wall_clock(self, tmp_path):
        import time

        ledger = str(tmp_path / "commit_authors")
        before = time.time()
        ca.record(ledger, "/repo", "sha1", "s1")
        after = time.time()
        with open(ledger, encoding="utf-8") as fh:
            rec = json.loads(fh.readline())
        assert before - 1 <= rec["ts"] <= after + 1


# ===========================================================================
# Pruning — bounds growth without losing recent/just-appended data.
# ===========================================================================


class TestPrune:
    def _seed(self, ledger_path, n, now, spacing=1.0, session="seed"):
        """Write `n` well-formed lines directly, timestamped `now - i*spacing`
        counting DOWN from the newest (line 0) to the oldest (line n-1)."""
        lines = []
        for i in range(n):
            ts = now - i * spacing
            lines.append(json.dumps({"ts": ts, "repo": "/repo", "sha": f"sha{i}", "session": session}))
        with open(ledger_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_no_prune_under_threshold(self, tmp_path):
        ledger = str(tmp_path / "commit_authors")
        now = 1_000_000.0
        self._seed(ledger, 10, now)
        with open(ledger, encoding="utf-8") as fh:
            before = fh.readlines()
        ca._prune(ledger, now)
        with open(ledger, encoding="utf-8") as fh:
            after = fh.readlines()
        assert before == after  # untouched — below PRUNE_THRESHOLD

    def test_prune_drops_entries_older_than_14_days(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ca, "PRUNE_THRESHOLD", 5)
        ledger = str(tmp_path / "commit_authors")
        now = 1_000_000.0
        old_ts = now - (ca.PRUNE_KEEP_DAYS * 86400 + 100)  # just past the cutoff
        lines = [
            json.dumps({"ts": now, "repo": "/repo", "sha": "fresh", "session": "s"}),
            json.dumps({"ts": old_ts, "repo": "/repo", "sha": "stale", "session": "s"}),
        ]
        # Pad past the (patched) threshold with more fresh lines.
        for i in range(6):
            lines.append(json.dumps({"ts": now - i, "repo": "/repo", "sha": f"pad{i}", "session": "s"}))
        with open(ledger, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

        ca._prune(ledger, now)

        assert ca.author_of(ledger, "/repo", "fresh") == "s"
        assert ca.author_of(ledger, "/repo", "stale") is None  # pruned away

    def test_prune_never_loses_a_just_appended_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ca, "PRUNE_THRESHOLD", 5)
        ledger = str(tmp_path / "commit_authors")
        now = 1_000_000.0
        self._seed(ledger, 6, now)  # already over the (patched) threshold

        assert ca.record(ledger, "/repo", "brand-new-sha", "fresh-session", now=now + 1) is True
        assert ca.author_of(ledger, "/repo", "brand-new-sha") == "fresh-session"

    def test_prune_keeps_only_newest_when_still_over_cap_after_age_cutoff(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ca, "PRUNE_THRESHOLD", 5)
        monkeypatch.setattr(ca, "PRUNE_KEEP_MAX", 3)
        ledger = str(tmp_path / "commit_authors")
        now = 1_000_000.0
        # All 6 entries are WITHIN the 14-day cutoff (spaced 1s apart), so the
        # age filter keeps all of them; the newest-N cap must still trim to 3.
        self._seed(ledger, 6, now, spacing=1.0)

        ca._prune(ledger, now)

        with open(ledger, encoding="utf-8") as fh:
            kept = ca.parse_ledger(fh.read())
        assert len(kept) == 3
        # The newest three (sha0, sha1, sha2 per _seed's "newest first" numbering).
        assert {r["sha"] for r in kept} == {"sha0", "sha1", "sha2"}

    def test_prune_no_op_on_unreadable_file(self, tmp_path):
        # Missing file: _prune must not raise, and must not create one.
        ledger = str(tmp_path / "missing")
        ca._prune(ledger, 1000.0)
        assert not os.path.exists(ledger)


# ===========================================================================
# Fail-OPEN on lock contention — record() still appends; only pruning skips.
# ===========================================================================


def test_record_fails_open_when_lock_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    ledger_dir = tmp_path / "ledgerdir"
    ledger = str(ledger_dir / "commit_authors")
    with ab.admission_lock(str(ledger_dir), timeout_s=0.5) as held:
        assert held is True
        # The lock is contended from inside record()'s perspective: it still
        # appends (fails OPEN) rather than skipping the record entirely.
        assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True
    assert ca.author_of(ledger, "/repo", "sha1") == "session-a"


def test_record_skips_prune_when_lock_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "PRUNE_THRESHOLD", 2)
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    ledger_dir = tmp_path / "ledgerdir"
    ledger_dir.mkdir()
    ledger = str(ledger_dir / "commit_authors")
    now = 1_000_000.0
    with open(ledger, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now, "repo": "/repo", "sha": "old1", "session": "s"}) + "\n")
        fh.write(json.dumps({"ts": now, "repo": "/repo", "sha": "old2", "session": "s"}) + "\n")
        fh.write(json.dumps({"ts": now, "repo": "/repo", "sha": "old3", "session": "s"}) + "\n")

    with ab.admission_lock(str(ledger_dir), timeout_s=0.5) as held:
        assert held is True
        assert ca.record(ledger, "/repo", "new-sha", "session-a", now=now + 1) is True

    # The append landed even though the lock was contended, but pruning (which
    # only ever runs from inside the lock) did NOT run: all 4 lines survive.
    with open(ledger, encoding="utf-8") as fh:
        assert len(fh.readlines()) == 4
    assert ca.author_of(ledger, "/repo", "new-sha") == "session-a"


def test_record_prunes_when_lock_is_available(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "PRUNE_THRESHOLD", 2)
    ledger = str(tmp_path / "commit_authors")
    now = 1_000_000.0
    with open(ledger, "w", encoding="utf-8") as fh:
        old_ts = now - (ca.PRUNE_KEEP_DAYS * 86400 + 100)
        fh.write(json.dumps({"ts": old_ts, "repo": "/repo", "sha": "stale", "session": "s"}) + "\n")
        fh.write(json.dumps({"ts": now, "repo": "/repo", "sha": "fresh", "session": "s"}) + "\n")

    assert ca.record(ledger, "/repo", "new-sha", "session-a", now=now + 1) is True

    assert ca.author_of(ledger, "/repo", "stale") is None  # pruned
    assert ca.author_of(ledger, "/repo", "fresh") == "s"
    assert ca.author_of(ledger, "/repo", "new-sha") == "session-a"


# ===========================================================================
# FIX 3: an unlocked append that races a concurrent LOCKED holder's
# _prune()/os.replace() can land on the old, now-unlinked inode and be lost.
# record() verifies its own write landed and retries ONCE if it did not.
# ===========================================================================


def test_record_retries_once_when_unlocked_append_is_lost_to_a_concurrent_prune(tmp_path, monkeypatch):
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    ledger_dir = tmp_path / "ledgerdir"
    ledger_dir.mkdir()
    ledger = str(ledger_dir / "commit_authors")
    decoy = str(ledger_dir / "decoy")  # stands in for the old, unlinked inode

    calls = {"n": 0}
    real_append = ca._append_line

    def flaky_append(path, line):
        calls["n"] += 1
        if calls["n"] == 1:
            # Simulate: the append raced a concurrent LOCKED holder's
            # _prune() -> os.replace() and landed on the OLD inode, never
            # reaching `ledger` at all.
            return real_append(decoy, line)
        return real_append(path, line)

    monkeypatch.setattr(ca, "_append_line", flaky_append)

    with ab.admission_lock(str(ledger_dir), timeout_s=0.5) as held:
        assert held is True  # forces record() onto its unlocked fail-open path
        assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True

    assert calls["n"] == 2  # first append lost, retried exactly once
    assert ca.author_of(ledger, "/repo", "sha1") == "session-a"  # the retry landed


def test_record_verification_is_a_noop_when_the_append_actually_landed(tmp_path, monkeypatch):
    # The common case: no concurrent prune actually happened. Verification
    # must not trigger a spurious second append.
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    ledger_dir = tmp_path / "ledgerdir"
    ledger_dir.mkdir()
    ledger = str(ledger_dir / "commit_authors")

    calls = {"n": 0}
    real_append = ca._append_line

    def counting_append(path, line):
        calls["n"] += 1
        return real_append(path, line)

    monkeypatch.setattr(ca, "_append_line", counting_append)

    with ab.admission_lock(str(ledger_dir), timeout_s=0.5) as held:
        assert held is True
        assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True

    assert calls["n"] == 1  # verification passed first try -- no retry
    assert ca.author_of(ledger, "/repo", "sha1") == "session-a"
    with open(ledger, encoding="utf-8") as fh:
        assert len(fh.readlines()) == 1  # exactly one line, not duplicated


def test_record_never_retries_more_than_once_even_if_still_lost(tmp_path, monkeypatch):
    # Bounded retry: even if the append keeps getting "lost", record() tries
    # at most twice total (one original attempt + one retry), never loops.
    monkeypatch.setenv("CSA_LOCK_TIMEOUT_SEC", "0.05")
    ledger_dir = tmp_path / "ledgerdir"
    ledger_dir.mkdir()
    ledger = str(ledger_dir / "commit_authors")
    decoy = str(ledger_dir / "decoy")

    calls = {"n": 0}
    real_append = ca._append_line

    def always_lost(path, line):
        calls["n"] += 1
        return real_append(decoy, line)  # every attempt "loses" the write

    monkeypatch.setattr(ca, "_append_line", always_lost)

    with ab.admission_lock(str(ledger_dir), timeout_s=0.5) as held:
        assert held is True
        ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0)

    assert calls["n"] == 2  # exactly one retry attempted, never more
    assert ca.author_of(ledger, "/repo", "sha1") is None  # genuinely lost both times


def test_record_retry_still_skipped_when_lock_is_held(tmp_path, monkeypatch):
    # The verify-and-retry logic is specific to the UNLOCKED fail-open path;
    # a normal locked record() must behave exactly as before (one append,
    # then prune -- no verification re-read at all).
    ledger = str(tmp_path / "commit_authors")
    calls = {"n": 0}
    real_append = ca._append_line

    def counting_append(path, line):
        calls["n"] += 1
        return real_append(path, line)

    monkeypatch.setattr(ca, "_append_line", counting_append)
    assert ca.record(ledger, "/repo", "sha1", "session-a", now=1000.0) is True
    assert calls["n"] == 1
    assert ca.author_of(ledger, "/repo", "sha1") == "session-a"


# ===========================================================================
# lock_timeout_from_env — thin wrapper parity with the sibling modules.
# ===========================================================================


def test_lock_timeout_from_env_default_and_override():
    assert ca.lock_timeout_from_env({}) == ab.DEFAULT_LOCK_TIMEOUT
    assert ca.lock_timeout_from_env({"CSA_LOCK_TIMEOUT_SEC": "5"}) == 5.0
