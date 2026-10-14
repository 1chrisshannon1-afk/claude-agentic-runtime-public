"""Hermetic tests for hooks/task_completion_gate.py -- RETIRED 2026-08-20 (see
that module's own docstring). Kept passing so the dormant module stays in a
known-good state for any future revival; not exercised by any live hook.

Ported from ~/.claude/scripts/review-gate.sh: every documented vector of the
bash script is reproduced as a pytest case (see the "PORTED BASH VECTORS"
section), then expanded to cover the pure decision function's whole branch space
and the thin main() wiring to >=90% line coverage.

All tests run against the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir) so the operator's real ~/.claude / review state is never touched.
Git is exercised ONLY through the throwaway `git_repo` fixture or via injected
fake lookups — no network, no real repos.
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import _lib
import commit_authors as ca
import pytest
import task_completion_gate as tcg

# ===========================================================================
# Helpers.
# ===========================================================================

_UNSET = object()  # sentinel: "_call caller didn't pass author_fn at all"


def _mk(**kw) -> dict:
    """Build a minimal Stop event payload."""
    ev: dict = {}
    if "cwd" in kw:
        ev["cwd"] = kw["cwd"]
    if "session_id" in kw:
        ev["session_id"] = kw["session_id"]
    return ev


def _call(
    sandbox,
    ev,
    *,
    disabled=False,
    skip_review=False,
    enforcing=False,
    repo_root_fn=None,
    head_sha_fn=None,
    outcome_fn=None,
    author_fn=_UNSET,
    commit_authors_path=None,
):
    """Invoke decide() with sandbox paths + the given flags/injected git fns.

    author_fn defaults to "this event's own session authored the HEAD" — the
    pre-authorship-scoping behavior every existing vector in this file was
    written against — so tests that don't care about WHO authored a HEAD keep
    exercising exactly what they exercised before. Pass an explicit author_fn
    (e.g. a different/None-returning lookup) to test the FOREIGN /
    UNKNOWN_AUTHOR paths; pass commit_authors_path to exercise the REAL
    commit_authors.author_of against a ledger you populated yourself.
    """
    kwargs = dict(
        state_dir=str(sandbox.review_state_dir),
        last_reviewed_path=str(sandbox.last_reviewed),
        commit_authors_path=commit_authors_path or str(sandbox.commit_authors),
        enforce_marker_rel=_lib.PROJECT_ENFORCE_MARKER,
        disabled=disabled,
        skip_review=skip_review,
        enforcing=enforcing,
    )
    if repo_root_fn is not None:
        kwargs["repo_root_fn"] = repo_root_fn
    if head_sha_fn is not None:
        kwargs["head_sha_fn"] = head_sha_fn
    if outcome_fn is not None:
        kwargs["outcome_fn"] = outcome_fn
    if author_fn is _UNSET:
        session = tcg._session_id(ev)
        kwargs["author_fn"] = lambda *_a, **_k: session
    elif author_fn is not None:
        kwargs["author_fn"] = author_fn
    return tcg.decide(ev, **kwargs)


def _fake_git(repo_root, head):
    """Return (repo_root_fn, head_sha_fn) that ignore their input and return these."""
    return (lambda _cwd: repo_root), (lambda _root: head)


def _opt_in(repo_path):
    """Drop the .claude/.csa-enforce opt-in marker in `repo_path`; return its Path."""
    d = os.path.join(str(repo_path), ".claude")
    os.makedirs(d, exist_ok=True)
    marker = os.path.join(d, ".csa-enforce")
    with open(marker, "w", encoding="utf-8"):
        pass
    return marker


def _write_reviewed(sandbox, repo_root, head):
    """Append a "<repo_root> <sha>" line to the last_reviewed ledger."""
    os.makedirs(str(sandbox.review_state_dir), exist_ok=True)
    with open(str(sandbox.last_reviewed), "a", encoding="utf-8") as fh:
        fh.write(f"{repo_root} {head}\n")


def _write_author(sandbox, repo_root, head, session):
    """Record (repo_root, head) as authored by `session` in the sandboxed
    commit_authors ledger, via the REAL commit_authors.record() (not a hand-
    rolled line) so these tests exercise the actual on-disk format."""
    ca.record(str(sandbox.commit_authors), repo_root, head, session)


def _write_reviewed_with_outcome(sandbox, repo_root, head, token):
    """Append a "<repo_root> <sha> <token>" outcome-bearing line (e.g. "clean"
    or "blockers:2") to the last_reviewed ledger."""
    os.makedirs(str(sandbox.review_state_dir), exist_ok=True)
    with open(str(sandbox.last_reviewed), "a", encoding="utf-8") as fh:
        fh.write(f"{repo_root} {head} {token}\n")


# ===========================================================================
# PORTED BASH VECTORS — each maps 1:1 to a review-gate.sh no-op / branch.
# ===========================================================================


def test_vector_disabled_master_switch_noop(sandbox, tmp_path):
    """CSA_DISABLE_HOOKS=1 -> immediate no-op (bash: return 0 at the top)."""
    repo = tmp_path / "r"
    repo.mkdir()
    _opt_in(repo)
    root = str(repo)
    d = _call(sandbox, _mk(cwd=root), disabled=True)
    assert d.outcome == tcg.NOOP
    assert d.block is False


def test_vector_cwd_not_a_directory_noop(sandbox, tmp_path):
    """cwd points nowhere -> no-op (bash: [[ -d "$cwd" ]] || return 0)."""
    d = _call(sandbox, _mk(cwd=str(tmp_path / "does-not-exist")))
    assert d.outcome == tcg.NOOP
    assert d.reason == "no-cwd"


def test_vector_not_a_git_repo_noop(sandbox, tmp_path):
    """cwd exists but is not a git repo -> no-op (bash: repo_root empty)."""
    plain = tmp_path / "plain"
    plain.mkdir()
    rr, hs = (lambda _c: None), (lambda _r: "x")
    d = _call(sandbox, _mk(cwd=str(plain)), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.NOOP
    assert d.reason == "not-a-git-repo"


def test_vector_repo_without_opt_in_marker_noop(sandbox, tmp_path):
    """A git repo lacking .claude/.csa-enforce -> no-op (bash opt-in gate)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    rr, hs = _fake_git(str(repo), "a" * 40)
    d = _call(sandbox, _mk(cwd=str(repo)), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.NOOP
    assert d.reason == "not-opted-in"


def test_vector_no_head_sha_noop(sandbox, tmp_path):
    """Opted-in repo but HEAD unresolvable (empty repo) -> no-op."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    rr, hs = _fake_git(str(repo), None)
    d = _call(sandbox, _mk(cwd=str(repo)), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.NOOP
    assert d.reason == "no-head"


def test_vector_head_already_reviewed_ok(sandbox, tmp_path):
    """HEAD present in last_reviewed -> ok / head-already-reviewed (bash reviewed=1)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "b" * 40
    _write_reviewed(sandbox, root, head)
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.OK
    assert d.reason == "head-already-reviewed"
    assert d.block is False


# ===========================================================================
# OUTCOME-AWARE — REVIEWED_WITH_BLOCKERS: a reviewed HEAD whose review found
# unresolved blockers gets a DISTINCT, more actionable signal than a bare OK —
# but NEVER a block, matching every other gate's LOG-ONLY-by-default philosophy.
# ===========================================================================


def test_reviewed_head_with_blockers_outcome_is_distinguishable(sandbox, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "1" * 40
    _write_reviewed_with_outcome(sandbox, root, head, "blockers:2")
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.REVIEWED_WITH_BLOCKERS
    assert "2 unresolved blocker(s)" in d.reason
    assert head[:12] in d.reason
    assert root in d.reason
    assert "fix them, not just re-run record_review" in d.reason


def test_reviewed_head_with_blockers_never_blocks_even_when_enforcing(sandbox, tmp_path):
    """The critical non-negotiable: this is a stepping stone, NEVER a new
    hard-block, regardless of enforcing()."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "2" * 40
    _write_reviewed_with_outcome(sandbox, root, head, "blockers:9")
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), enforcing=True, repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.REVIEWED_WITH_BLOCKERS
    assert d.block is False


def test_reviewed_head_with_clean_outcome_is_plain_ok(sandbox, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "3" * 40
    _write_reviewed_with_outcome(sandbox, root, head, "clean")
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.OK
    assert d.reason == "head-already-reviewed"


def test_reviewed_head_with_unknown_outcome_stays_plain_ok(sandbox, tmp_path):
    """A legacy/unspecified-outcome line (no third field) behaves EXACTLY as
    before this feature: plain OK, never the new distinguishable state."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "4" * 40
    _write_reviewed(sandbox, root, head)  # bare two-field legacy line
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.OK


def test_reviewed_head_outcome_fn_raising_degrades_to_plain_ok(sandbox, tmp_path):
    """A crashing outcome_fn must not break the gate — degrade to plain OK."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "5" * 40
    _write_reviewed(sandbox, root, head)
    rr, hs = _fake_git(root, head)

    def boom_outcome(*_a, **_k):
        raise RuntimeError("ledger read exploded")

    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs, outcome_fn=boom_outcome)
    assert d.outcome == tcg.OK


def test_reviewed_head_outcome_fn_returning_none_is_plain_ok(sandbox, tmp_path):
    """outcome_fn returning None (defensive: head_reviewed() said True but the
    outcome lookup somehow found nothing) degrades to plain OK, not a crash."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "6" * 40
    _write_reviewed(sandbox, root, head)
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs, outcome_fn=lambda *_a, **_k: None
    )
    assert d.outcome == tcg.OK


def test_vector_new_unreviewed_head_would_warn_log_only(sandbox, tmp_path):
    """New unreviewed HEAD, NOT enforcing -> would-warn, LOG-ONLY, never blocks."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "c" * 40
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox, _mk(cwd=root, session_id="s1"), enforcing=False, repo_root_fn=rr, head_sha_fn=hs
    )
    assert d.outcome == tcg.WOULD_WARN
    assert d.reason == "head-not-reviewed"
    assert d.block is False
    # A per-(repo,session,head) sentinel was written to prevent a re-fire loop.
    assert os.path.isfile(tcg.fired_sentinel(str(sandbox.review_state_dir), root, "s1", head))


def test_vector_refire_guard_silences_second_call(sandbox, tmp_path):
    """Second Stop for the same HEAD+session stays quiet (bash sentinel guard)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "d" * 40
    rr, hs = _fake_git(root, head)
    first = _call(sandbox, _mk(cwd=root, session_id="s1"), repo_root_fn=rr, head_sha_fn=hs)
    assert first.outcome == tcg.WOULD_WARN
    second = _call(sandbox, _mk(cwd=root, session_id="s1"), repo_root_fn=rr, head_sha_fn=hs)
    assert second.outcome == tcg.SILENCED
    assert second.block is False


def test_vector_skip_review_one_shot_consumes_sentinel(sandbox, tmp_path):
    """CSA_SKIP_REVIEW=1 burns a sentinel and ends the turn once (bash skip path)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "e" * 40
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox, _mk(cwd=root, session_id="s1"), skip_review=True, repo_root_fn=rr, head_sha_fn=hs
    )
    assert d.outcome == tcg.SKIP_CONSUMED
    assert d.reason == "csa-skip-review-one-shot"
    assert os.path.isfile(tcg.skip_sentinel(str(sandbox.review_state_dir), root, "s1"))


def test_vector_skip_review_second_turn_falls_through(sandbox, tmp_path):
    """After the one-shot is consumed, a second CSA_SKIP_REVIEW turn evaluates
    normally (bash: 'already consumed once -> fall through')."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "f" * 40
    rr, hs = _fake_git(root, head)
    first = _call(
        sandbox, _mk(cwd=root, session_id="s1"), skip_review=True, repo_root_fn=rr, head_sha_fn=hs
    )
    assert first.outcome == tcg.SKIP_CONSUMED
    second = _call(
        sandbox, _mk(cwd=root, session_id="s1"), skip_review=True, repo_root_fn=rr, head_sha_fn=hs
    )
    # Fell through to normal evaluation: new unreviewed HEAD -> would-warn.
    assert second.outcome == tcg.WOULD_WARN


def test_vector_enforcing_new_head_emits_block(sandbox, tmp_path):
    """New unreviewed HEAD AND enforcing() -> BLOCK with the surfaced message."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "0123456789abcdef" + "0" * 24  # 40 chars
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox, _mk(cwd=root, session_id="s1"), enforcing=True, repo_root_fn=rr, head_sha_fn=hs
    )
    assert d.outcome == tcg.BLOCK
    assert d.block is True
    assert "no Opus review on record" in d.reason
    assert head[:12] in d.reason  # short sha surfaced
    assert root in d.reason
    assert "CSA_SKIP_REVIEW=1" in d.reason


# ===========================================================================
# EXPANDED — pure decide() branch coverage beyond the raw bash vectors.
# ===========================================================================


def test_disabled_beats_enforcing(sandbox, tmp_path):
    """Master OFF wins even when enforcing=True would otherwise block."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    rr, hs = _fake_git(str(repo), "a" * 40)
    d = _call(
        sandbox, _mk(cwd=str(repo)), disabled=True, enforcing=True, repo_root_fn=rr, head_sha_fn=hs
    )
    assert d.outcome == tcg.NOOP


def test_empty_cwd_string_is_noop(sandbox):
    """A payload whose cwd is an empty string falls back to getcwd; if that dir
    is not a repo we still no-op — assert via an injected non-repo lookup."""
    rr, hs = (lambda _c: None), (lambda _r: "x")
    d = _call(sandbox, {"cwd": ""}, repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.NOOP
    assert d.reason == "not-a-git-repo"


def test_session_defaults_to_nosession(sandbox, tmp_path):
    """A payload without a session id keys sentinels under 'nosession'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "9" * 40
    rr, hs = _fake_git(root, head)
    d = _call(sandbox, _mk(cwd=root), repo_root_fn=rr, head_sha_fn=hs)
    assert d.outcome == tcg.WOULD_WARN
    assert os.path.isfile(
        tcg.fired_sentinel(str(sandbox.review_state_dir), root, "nosession", head)
    )


def test_different_head_after_review_warns_again(sandbox, tmp_path):
    """A reviewed HEAD is ok; advancing to a NEW HEAD (commit boundary) warns."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root = str(repo)
    old, new = "1" * 40, "2" * 40
    _write_reviewed(sandbox, root, old)

    rr = lambda _c: root  # noqa: E731
    d_old = _call(
        sandbox, _mk(cwd=root, session_id="s"), repo_root_fn=rr, head_sha_fn=lambda _r: old
    )
    assert d_old.outcome == tcg.OK
    d_new = _call(
        sandbox, _mk(cwd=root, session_id="s"), repo_root_fn=rr, head_sha_fn=lambda _r: new
    )
    assert d_new.outcome == tcg.WOULD_WARN


def test_refire_guard_is_per_session(sandbox, tmp_path):
    """The same HEAD in a DIFFERENT session warns again (sentinel is per-session)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "3" * 40
    rr, hs = _fake_git(root, head)
    a = _call(sandbox, _mk(cwd=root, session_id="sA"), repo_root_fn=rr, head_sha_fn=hs)
    b = _call(sandbox, _mk(cwd=root, session_id="sB"), repo_root_fn=rr, head_sha_fn=hs)
    assert a.outcome == tcg.WOULD_WARN
    assert b.outcome == tcg.WOULD_WARN


def test_skip_then_still_warns_on_new_head_next_session(sandbox, tmp_path):
    """skip sentinel is per-(repo,session): a new session re-arms the one-shot."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "4" * 40
    rr, hs = _fake_git(root, head)
    s1 = _call(
        sandbox, _mk(cwd=root, session_id="s1"), skip_review=True, repo_root_fn=rr, head_sha_fn=hs
    )
    s2 = _call(
        sandbox, _mk(cwd=root, session_id="s2"), skip_review=True, repo_root_fn=rr, head_sha_fn=hs
    )
    assert s1.outcome == tcg.SKIP_CONSUMED
    assert s2.outcome == tcg.SKIP_CONSUMED


def test_internal_error_degrades_open(sandbox):
    """A lookup fn that raises -> decide() degrades OPEN to a benign no-op."""

    def boom(_c):
        raise RuntimeError("git blew up")

    d = _call(sandbox, _mk(cwd=str(sandbox.home)), repo_root_fn=boom)
    assert d.outcome == tcg.NOOP
    assert d.reason == "internal-error"


def test_head_reviewed_substring_match_semantics(sandbox, tmp_path):
    """head_reviewed uses grep -F substring semantics on the "<root> <sha>" needle."""
    root, head = "/x/repo", "abc123"
    path = str(sandbox.last_reviewed)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"noise {root} {head} trailing\n")
    assert tcg.head_reviewed(path, root, head) is True
    assert tcg.head_reviewed(path, root, "zzz") is False


def test_head_reviewed_missing_file_is_false(sandbox):
    assert tcg.head_reviewed(str(sandbox.last_reviewed), "/x", "y") is False


def test_repo_key_sanitizes_slashes_and_spaces():
    assert tcg._repo_key("/a b/c") == "_a_b_c"


def test_session_id_non_string_defaults(sandbox):
    """A non-string session_id in the payload falls back to 'nosession'."""
    assert tcg._session_id({"session_id": 123}) == "nosession"
    assert tcg._session_id({"sessionId": "alt"}) == "alt"
    assert tcg._session_id({}) == "nosession"


def test_session_id_degrades_on_raising_get(sandbox):
    """_session_id swallows a .get() that raises and returns the default."""

    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("no get")

    assert tcg._session_id(Boom()) == "nosession"


def test_touch_swallows_unwritable_path(sandbox):
    """_touch degrades silently when the target dir cannot be created."""
    # A path under an existing *file* can't be made into a dir -> swallowed.
    f = sandbox.home / "afile"
    f.write_text("x")
    tcg._touch(str(f / "nested" / "sentinel"))  # must not raise
    assert not (f / "nested").exists()


# ===========================================================================
# AUTHORSHIP SCOPING — the whole point of this ledger: only the session that
# actually committed a HEAD ever sees WOULD_WARN/BLOCK/REVIEWED_WITH_BLOCKERS;
# a different or unknown session sees a quiet, non-blocking outcome instead
# (mechanizes "never review a HEAD I didn't produce" — feedback_no_review_
# others_work). These tests use the REAL commit_authors.author_of (via
# commit_authors_path) rather than _call's own-session default, so they
# exercise the actual ledger read, not just an injected stub.
# ===========================================================================


def test_foreign_session_unreviewed_head_never_warns_or_blocks(sandbox, tmp_path):
    """A HEAD committed by a DIFFERENT session -> FOREIGN, never WOULD_WARN/BLOCK,
    even when enforcing() is True."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "a1" * 20
    _write_author(sandbox, root, head, "session-A")
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox,
        _mk(cwd=root, session_id="session-B"),
        enforcing=True,
        repo_root_fn=rr,
        head_sha_fn=hs,
        author_fn=None,  # use the REAL commit_authors.author_of
    )
    assert d.outcome == tcg.FOREIGN
    assert d.block is False
    assert "different session" in d.reason


def test_unknown_author_unreviewed_head_never_warns_or_blocks(sandbox, tmp_path):
    """A HEAD with NO recorded author (operator terminal commit, pre-ledger
    HEAD, missed write) -> UNKNOWN_AUTHOR, never WOULD_WARN/BLOCK, even
    enforcing()."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "b2" * 20
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox,
        _mk(cwd=root, session_id="session-B"),
        enforcing=True,
        repo_root_fn=rr,
        head_sha_fn=hs,
        author_fn=None,  # ledger has no record for this HEAD
    )
    assert d.outcome == tcg.UNKNOWN_AUTHOR
    assert d.block is False
    assert "no recorded commit author" in d.reason


def test_own_session_unreviewed_head_still_warns_via_real_ledger(sandbox, tmp_path):
    """Sanity: the SAME session that committed a HEAD (per the real ledger)
    still gets WOULD_WARN, unchanged."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "c3" * 20
    _write_author(sandbox, root, head, "session-A")
    rr, hs = _fake_git(root, head)
    d = _call(
        sandbox,
        _mk(cwd=root, session_id="session-A"),
        repo_root_fn=rr,
        head_sha_fn=hs,
        author_fn=None,
    )
    assert d.outcome == tcg.WOULD_WARN


def test_foreign_and_unknown_share_the_refire_sentinel(sandbox, tmp_path):
    """FOREIGN and UNKNOWN_AUTHOR are deduped by the SAME per-(repo,session,head)
    sentinel as WOULD_WARN — a second Stop turn is SILENCED regardless of
    which of the three outcomes fired first."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "d4" * 20
    _write_author(sandbox, root, head, "session-A")
    rr, hs = _fake_git(root, head)
    first = _call(
        sandbox, _mk(cwd=root, session_id="session-B"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    second = _call(
        sandbox, _mk(cwd=root, session_id="session-B"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    assert first.outcome == tcg.FOREIGN
    assert second.outcome == tcg.SILENCED


def test_reviewed_with_blockers_scoped_to_author_session_only(sandbox, tmp_path):
    """REVIEWED_WITH_BLOCKERS is authorship-scoped too: the committing session
    sees it; a different session sees a plain OK for the exact same HEAD."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "e5" * 20
    _write_reviewed_with_outcome(sandbox, root, head, "blockers:3")
    _write_author(sandbox, root, head, "session-A")
    rr, hs = _fake_git(root, head)

    d_author = _call(
        sandbox, _mk(cwd=root, session_id="session-A"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    assert d_author.outcome == tcg.REVIEWED_WITH_BLOCKERS

    d_other = _call(
        sandbox, _mk(cwd=root, session_id="session-B"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    assert d_other.outcome == tcg.OK


def test_recovery_after_review_recorded_author_session_returns_ok(sandbox, tmp_path):
    """Recovery pairing (ENGINEERING_STANDARDS §6): once the author session's
    HEAD is recorded reviewed (clean), that SAME session's Stop turn returns
    OK — the original WOULD_WARN/BLOCK is recoverable, not a dead end."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "f6" * 20
    _write_author(sandbox, root, head, "session-A")
    rr, hs = _fake_git(root, head)

    before = _call(
        sandbox, _mk(cwd=root, session_id="session-A"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    assert before.outcome == tcg.WOULD_WARN

    _write_reviewed_with_outcome(sandbox, root, head, "clean")
    after = _call(
        sandbox, _mk(cwd=root, session_id="session-A"), repo_root_fn=rr, head_sha_fn=hs, author_fn=None
    )
    assert after.outcome == tcg.OK


def test_subagent_shaped_payload_attributes_to_parent_session(sandbox, tmp_path):
    """A sub-agent's Stop payload carries the SAME session_id as its parent
    session (plus extra fields Claude Code may add) — commit_authors.record()
    (writer side) and this gate (reader side) must agree on that identity, so
    a sub-agent's own commit is still recognized as authored by "this session"."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "07" * 20
    parent_session = "parent-session-123"
    _write_author(sandbox, root, head, parent_session)
    rr, hs = _fake_git(root, head)
    subagent_payload = _mk(cwd=root, session_id=parent_session)
    subagent_payload["agent_id"] = "subagent-xyz"  # extra field a sub-agent payload carries
    subagent_payload["transcript_path"] = "/some/path.jsonl"
    d = _call(sandbox, subagent_payload, repo_root_fn=rr, head_sha_fn=hs, author_fn=None)
    assert d.outcome == tcg.WOULD_WARN  # recognized as the SAME (parent) session


def test_main_end_to_end_foreign_head_emits_no_stop_block(sandbox, monkeypatch, tmp_path):
    """Full main() wiring: a HEAD authored by a DIFFERENT session never emits
    a Stop-block JSON object, even under enforcing() — assert the actual
    emitted stdout, not just the Decision."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "18" * 20
    _write_author(sandbox, root, head, "session-OTHER")
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))
    sandbox.enforce_file.write_text("")  # enforcing ON

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "session-ME"})
    assert rc == 0
    assert out == ""  # NEVER a Stop block for a foreign HEAD
    logged = _read_log(sandbox)
    assert logged[-1]["decision"] == tcg.FOREIGN


# ===========================================================================
# Decision value object.
# ===========================================================================


def test_decision_block_property():
    assert tcg.Decision(tcg.BLOCK, "r").block is True
    assert tcg.Decision(tcg.WOULD_WARN, "r").block is False


# ===========================================================================
# Real-git integration (throwaway repo only) — proves the default git lookups.
# ===========================================================================


def _git_available():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_real_git_lookups_resolve_root_and_head(sandbox, tmp_path):
    """repo_root_of + head_sha_of work against a real throwaway commit."""
    repo = tmp_path / "realrepo"
    repo.mkdir()
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@example.com"
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=15, env=env
        )

    root = tcg.repo_root_of(str(repo))
    assert root is not None
    assert os.path.samefile(root, str(repo))
    head = tcg.head_sha_of(root)
    assert head is not None and len(head) == 40


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_real_git_lookups_return_none_outside_repo(sandbox, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert tcg.repo_root_of(str(plain)) is None


def test_git_helper_handles_missing_binary(sandbox, monkeypatch):
    """_git returns None when the git subprocess raises (e.g. binary missing)."""

    def boom(*a, **k):
        raise FileNotFoundError("no git")

    monkeypatch.setattr(tcg.subprocess, "run", boom)
    assert tcg._git("/x", "rev-parse", "HEAD") is None
    assert tcg.repo_root_of("/x") is None
    assert tcg.head_sha_of("/x") is None


def test_git_helper_nonzero_returncode_is_none(sandbox, monkeypatch):
    class P:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(tcg.subprocess, "run", lambda *a, **k: P())
    assert tcg._git("/x", "rev-parse", "HEAD") is None


# ===========================================================================
# main() wiring — read event -> decide -> emit/log -> exit 0.
# ===========================================================================


def _run_main(monkeypatch, payload: dict):
    """Drive main() with `payload` on stdin; capture stdout. Returns (rc, stdout)."""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = tcg.main()
    return rc, buf.getvalue()


def test_main_noop_writes_nothing(sandbox, monkeypatch, tmp_path):
    """A non-repo cwd -> main() exits 0, no stdout, no log line."""
    plain = tmp_path / "plain"
    plain.mkdir()
    rc, out = _run_main(monkeypatch, {"cwd": str(plain), "session_id": "s"})
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_main_would_warn_logs_only_no_block(sandbox, monkeypatch, tmp_path):
    """Opted-in new HEAD, authored by THIS session, not enforcing -> main()
    logs would-warn, emits no block."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "a" * 40
    _write_author(sandbox, root, head, "s")
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    # decide() defaults its git fns to the module globals -> patch takes effect.
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""  # log-only: nothing on stdout
    logged = _read_log(sandbox)
    assert logged and logged[-1]["decision"] == tcg.WOULD_WARN
    assert logged[-1]["hook"] == "review_gate"


def test_main_enforcing_emits_stop_block(sandbox, monkeypatch, tmp_path):
    """Opted-in new HEAD authored by THIS session, enforcing via global marker
    -> main() emits a Stop block."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "b" * 40
    _write_author(sandbox, root, head, "s")
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))
    # Turn enforcing ON via the sandboxed global marker file.
    sandbox.enforce_file.write_text("")

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    obj = json.loads(out)
    assert obj["decision"] == "block"
    assert "no Opus review on record" in obj["reason"]
    logged = _read_log(sandbox)
    assert logged[-1]["decision"] == tcg.BLOCK


def test_main_silenced_second_call_no_output(sandbox, monkeypatch, tmp_path):
    """Second main() for the same HEAD+session is silent (no stdout, no new log)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "c" * 40
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))

    _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    n_after_first = len(_read_log(sandbox))
    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""
    assert len(_read_log(sandbox)) == n_after_first  # SILENCED writes no log


def test_main_skip_review_env(sandbox, monkeypatch, tmp_path):
    """CSA_SKIP_REVIEW=1 in the env drives main() down the skip-consumed path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "d" * 40
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))
    monkeypatch.setenv("CSA_SKIP_REVIEW", "1")

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""
    assert _read_log(sandbox)[-1]["decision"] == tcg.SKIP_CONSUMED


def test_main_disabled_master_switch(sandbox, monkeypatch, tmp_path):
    """CSA_DISABLE_HOOKS=1 -> main() no-ops even with an opted-in enforcing repo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    sandbox.enforce_file.write_text("")
    root, head = str(repo), "e" * 40
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_main_degrades_open_on_exception(sandbox, monkeypatch):
    """If decide() raises inside main(), main() still exits 0 and emits nothing."""

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tcg, "decide", boom)
    rc, out = _run_main(monkeypatch, {"cwd": "/x"})
    assert rc == 0
    assert out == ""


def test_main_head_already_reviewed_logs_ok(sandbox, monkeypatch, tmp_path):
    """A reviewed HEAD -> main() logs 'ok', no stdout."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "f" * 40
    _write_reviewed(sandbox, root, head)
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""
    assert _read_log(sandbox)[-1]["decision"] == tcg.OK


def test_main_reviewed_with_blockers_logs_distinct_outcome_never_blocks(sandbox, monkeypatch, tmp_path):
    """End-to-end through the REAL default outcome_fn (record_review.head_
    review_outcome, unpatched): a HEAD reviewed with unresolved blockers on
    record logs REVIEWED_WITH_BLOCKERS and STILL emits no Stop block, even
    when enforcing() is ON via the global marker."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _opt_in(repo)
    root, head = str(repo), "9" * 40
    _write_reviewed_with_outcome(sandbox, root, head, "blockers:2")
    _write_author(sandbox, root, head, "s")
    monkeypatch.setattr(tcg, "repo_root_of", lambda _c: root)
    monkeypatch.setattr(tcg, "head_sha_of", lambda _r: head)
    monkeypatch.setattr(tcg, "decide", _decide_using_module_git(tcg.decide))
    sandbox.enforce_file.write_text("")  # enforcing ON

    rc, out = _run_main(monkeypatch, {"cwd": root, "session_id": "s"})
    assert rc == 0
    assert out == ""  # NEVER a Stop block, regardless of enforcing()
    rec = _read_log(sandbox)[-1]
    assert rec["decision"] == tcg.REVIEWED_WITH_BLOCKERS
    assert "2 unresolved blocker(s)" in rec["reason"]


# --- main() helpers --------------------------------------------------------


def _decide_using_module_git(orig_decide):
    """Wrap decide() so it uses tcg.repo_root_of / head_sha_of AS CURRENTLY
    PATCHED on the module (monkeypatch replaces the globals after decide captured
    its defaults, so re-inject the live module attributes)."""

    def _wrapped(ev, **kw):
        kw["repo_root_fn"] = tcg.repo_root_of
        kw["head_sha_fn"] = tcg.head_sha_of
        return orig_decide(ev, **kw)

    return _wrapped


def _read_log(sandbox):
    """Parse the JSONL enforcement log into a list of dicts (empty if absent)."""
    p = sandbox.log_file
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
