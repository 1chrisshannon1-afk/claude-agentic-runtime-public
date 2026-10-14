"""Tests for record_plan_review — the log-only plan-review outcome ledger.

Deliberately thin: this module has no blocking behavior and no gate reads
its ledger, so there is no "does this deny correctly" surface to cover.
What matters is: it records what it's told, degrades safely when told
nothing usable, and never raises.
"""

from __future__ import annotations

import json
import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402
import record_plan_review as rpr  # noqa: E402


def _lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def test_parse_argv_clean():
    target, outcome, blockers, plan = rpr.parse_argv(
        ["/repo", "--clean", "--plan", "/plans/x.md"]
    )
    assert target == "/repo"
    assert outcome == "clean"
    assert blockers is None
    assert plan == "/plans/x.md"


def test_parse_argv_blockers():
    target, outcome, blockers, plan = rpr.parse_argv(["/repo", "--blockers", "3"])
    assert target == "/repo"
    assert outcome == "blockers"
    assert blockers == 3


def test_parse_argv_malformed_blockers_count_leaves_outcome_unset():
    """Round-2 review finding 8: a malformed count must NOT produce a
    truthy-looking 'blockers' outcome with no usable count — that wrote an
    uncountable ledger entry indistinguishable from a real zero. Mirrors
    record_review.py's own _outcome_from_argv exactly: the flag is ignored,
    not half-honored."""
    target, outcome, blockers, plan = rpr.parse_argv(["/repo", "--blockers", "not-a-number"])
    assert outcome is None
    assert blockers is None


def test_parse_argv_blockers_zero_is_clean_not_a_distinct_blockers_state():
    """--blockers 0 means zero unresolved blockers -- that IS clean, per
    record_review.py's own semantics. Recording it as a 'blockers' outcome
    with count 0 was indistinguishable from a malformed/ignored flag."""
    target, outcome, blockers, plan = rpr.parse_argv(["/repo", "--blockers", "0"])
    assert outcome == "clean"
    assert blockers == 0


def test_parse_argv_negative_blockers_is_also_clean():
    target, outcome, blockers, plan = rpr.parse_argv(["/repo", "--blockers", "-3"])
    assert outcome == "clean"
    assert blockers == -3


def test_parse_argv_blockers_equals_form():
    target, outcome, blockers, plan = rpr.parse_argv(["/repo", "--blockers=5"])
    assert outcome == "blockers"
    assert blockers == 5


def test_parse_argv_matches_record_review_semantics_exactly():
    """Direct cross-check against record_review's own outcome parser for the
    same inputs -- the two ledgers must never disagree about what a given
    --blockers value means."""
    import record_review as rr

    for raw in ("0", "-3", "7", "not-a-number"):
        _t, our_outcome, our_blockers, _p = rpr.parse_argv(["/repo", "--blockers", raw])
        their_outcome, their_blockers = rr._outcome_from_argv(["--blockers", raw])
        assert our_outcome == their_outcome, raw
        assert our_blockers == their_blockers, raw


def test_parse_argv_no_outcome_flag():
    target, outcome, blockers, plan = rpr.parse_argv(["/repo"])
    assert target == "/repo"
    assert outcome is None


def test_record_writes_a_line(sandbox):
    ok = rpr.record("/repo/x", "clean", None, "/plans/a.md")
    assert ok is True
    lines = _lines(rpr.plan_reviews_path())
    assert len(lines) == 1
    assert lines[0]["repo"] == "/repo/x"
    assert lines[0]["outcome"] == "clean"
    assert lines[0]["blockers"] == 0
    assert lines[0]["plan"] == "/plans/a.md"
    assert lines[0]["ts"]  # a real timestamp, not empty


def test_record_blockers_carries_the_count(sandbox):
    rpr.record("/repo/x", "blockers", 4, "/plans/b.md")
    lines = _lines(rpr.plan_reviews_path())
    assert lines[0]["blockers"] == 4


def test_multiple_records_append_not_overwrite(sandbox):
    rpr.record("/repo/x", "clean", None, "/plans/a.md")
    rpr.record("/repo/x", "blockers", 2, "/plans/a.md")
    lines = _lines(rpr.plan_reviews_path())
    assert len(lines) == 2


def test_main_no_outcome_records_nothing(sandbox, capsys):
    rc = rpr.main(["/repo"])
    assert rc == 0
    assert not os.path.isfile(rpr.plan_reviews_path())
    out = capsys.readouterr().out
    assert "Nothing recorded" in out


def test_main_clean_writes_and_prints_confirmation(sandbox, capsys):
    rc = rpr.main(["/repo", "--clean", "--plan", "/plans/a.md"])
    assert rc == 0
    lines = _lines(rpr.plan_reviews_path())
    assert len(lines) == 1
    assert lines[0]["outcome"] == "clean"
    out = capsys.readouterr().out
    assert "recorded plan review" in out


def test_main_disabled_by_master_switch_is_a_clean_noop(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    rc = rpr.main(["/repo", "--clean"])
    assert rc == 0
    assert not os.path.isfile(rpr.plan_reviews_path())


def test_record_failure_degrades_to_false_not_raise(sandbox, monkeypatch):
    # Point the review-state dir at a location that cannot be created
    # (a file, not a directory, sits where the dir should go).
    blocked = os.path.join(sandbox.home, "blocked_not_a_dir")
    with open(blocked, "w", encoding="utf-8") as fh:
        fh.write("x")
    monkeypatch.setattr(_lib, "REVIEW_STATE_DIR", os.path.join(blocked, "review_state"))
    ok = rpr.record("/repo", "clean", None, None)
    assert ok is False


def test_never_raises_on_garbage_argv(sandbox):
    # Must not raise, regardless of adversarial input.
    rpr.parse_argv(["--blockers"])  # no value follows
    rpr.parse_argv(["--plan"])  # no value follows
    rpr.parse_argv([])
    assert rpr.main(["--clean"]) == 0  # no positional target at all


def test_main_malformed_blockers_records_nothing(sandbox, capsys):
    """The CLI-level equivalent of test_parse_argv_malformed_blockers_count_
    leaves_outcome_unset -- a bad count must not silently land in the ledger."""
    rc = rpr.main(["/repo", "--blockers", "garbage", "--plan", "/plans/a.md"])
    assert rc == 0
    assert not os.path.isfile(rpr.plan_reviews_path())


def test_main_warns_when_plan_path_missing(sandbox, capsys):
    rc = rpr.main(["/repo", "--clean"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "unattributable" in out
    # Still records -- a missing --plan is a warning, not a refusal.
    lines = _lines(rpr.plan_reviews_path())
    assert len(lines) == 1
    assert lines[0]["plan"] is None


def test_resolve_repo_root_normalizes_a_real_repo(git_repo):
    sub = git_repo / "a" / "b"
    sub.mkdir(parents=True)
    resolved = rpr.resolve_repo_root(str(sub))
    assert resolved == str(git_repo.resolve()) or resolved == str(git_repo)


def test_resolve_repo_root_falls_back_on_non_repo(tmp_path):
    not_a_repo = tmp_path / "plain_dir"
    not_a_repo.mkdir()
    assert rpr.resolve_repo_root(str(not_a_repo)) == str(not_a_repo)


def test_resolve_repo_root_never_raises_on_garbage():
    assert rpr.resolve_repo_root("") == ""
    assert rpr.resolve_repo_root("/plans/a.md") == "/plans/a.md"


def test_main_normalizes_target_before_recording(sandbox, git_repo, capsys):
    sub = git_repo / "nested"
    sub.mkdir()
    rpr.main([str(sub), "--clean", "--plan", "/plans/a.md"])
    lines = _lines(rpr.plan_reviews_path())
    assert len(lines) == 1
    # Recorded against the repo TOPLEVEL, not the subdirectory it was invoked from.
    assert lines[0]["repo"] in (str(git_repo), str(git_repo.resolve()))
    assert lines[0]["repo"] != str(sub)
