"""Tests for replay_review_rounds — the review-round ledger replay tool.

Spec source: the module's own docstring, `record_review.derive_review_round`
(the production walk this tool must faithfully mirror), and ExampleApp
#5828. Each test states the defect it catches.

THE CENTRAL TEST IS `test_derive_matches_production_on_generated_ledgers`.
This tool's entire value rests on one claim — that its replayed walk behaves
like production. If that drifts, every number it prints is wrong, including
the numbers used to reject a plan. A differential test makes that a
MAINTAINED property rather than a one-time verification.

Why this module exists at all: `--self-test` covers the predicate shape table
only. Both blockers found in review (a repo root containing a space; a
malformed `paths_n=` aborting the run) lived in ledger PARSING, which
`--self-test` never touches. A green self-test was not evidence about them.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "scripts"))

import record_review as rr  # noqa: E402

_SCRIPTS = os.path.join(os.path.expanduser("~/.claude"), "scripts")
sys.path.insert(0, _SCRIPTS)
import replay_review_rounds as rrr  # noqa: E402


def _ledger(tmp_path, lines) -> str:
    # mkdir: callers pass sub-paths (tmp_path / "x") to get a second,
    # independent ledger within one test; pytest creates only tmp_path itself.
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "last_reviewed"
    p.write_text("".join(line if line.endswith("\n") else line + "\n" for line in lines))
    return str(p)


def _line(repo, key, outcome, paths, paths_n=None):
    n = paths_n if paths_n is not None else len(paths)
    return f"{repo} precommit:{key} {outcome} paths={'#'.join(paths)} paths_n={n}"


# --------------------------------------------------------------------------
# B1 — a repo root containing a space
# --------------------------------------------------------------------------

def test_a_repo_root_containing_a_space_is_not_dropped(tmp_path):
    """THE LIVE CASE. `/Users/x/Desktop/other project` is a
    real repo root in the live ledger. Splitting on the FIRST space parses it as
    '/Users/x/Desktop/agentic' and the remainder fails the
    `precommit:` check, so the repo silently gets NO ROW AT ALL — a per-repo
    table that omits a repo production walks. Production anchors on the known
    repo root instead (record_review.py:1344)."""
    repo = "/Users/me/Desktop/other project"
    led = _ledger(tmp_path, [
        _line(repo, "aaa", "blockers:2", ["a.py"]),
        _line(repo, "bbb", "clean", ["a.py"]),
    ])
    entries = rrr.load_entries(led)
    assert [e["repo"] for e in entries] == [repo, repo], entries


def test_a_repo_root_without_a_space_still_parses(tmp_path):
    """PAIRED RECOVERY: the ordinary case must keep working — the fix must
    not trade one parse bug for another."""
    repo = "/Users/me/Desktop/Plain"
    led = _ledger(tmp_path, [_line(repo, "aaa", "clean", ["a.py"])])
    assert [e["repo"] for e in rrr.load_entries(led)] == [repo]


def test_a_repo_root_containing_a_spaced_prefix_matches_production(tmp_path):
    """Finding 8. A root containing " precommit:" WITH its leading space:
    partitioning on the FIRST occurrence cuts the root in half and drops the
    row, while production (which knows `repo_root` up front and matches a
    prefix) parses it. rpartition reproduces production."""
    repo = "/Users/me/weird precommit:dir"
    led = _ledger(tmp_path, [_line(repo, "aaa", "clean", ["a.py"])])
    assert [e["repo"] for e in rrr.load_entries(led)] == [repo]


def test_a_repo_root_containing_the_prefix_as_a_substring(tmp_path):
    """The anchor is ' precommit:' WITH its leading space, so a repo whose
    own name contains the bare token is not mis-split. Named UNVERIFIED by
    the reviewer; pinned here rather than left open."""
    repo = "/Users/me/precommit:stuff"
    led = _ledger(tmp_path, [_line(repo, "aaa", "clean", ["a.py"])])
    assert [e["repo"] for e in rrr.load_entries(led)] == [repo]


# --------------------------------------------------------------------------
# B2 — a malformed paths_n must not abort a full-ledger run
# --------------------------------------------------------------------------

def test_a_malformed_paths_n_does_not_abort_the_run(tmp_path):
    """The ledger is append-only and multi-writer, and this tool's contract
    is 'safe to run at any time'. A bare int() raised ValueError and killed
    a 6-second full-ledger run at whatever line it reached."""
    led = _ledger(tmp_path, [
        "/r precommit:aaa clean paths=a.py paths_n=abc",
        _line("/r", "bbb", "clean", ["b.py"]),
    ])
    entries = rrr.load_entries(led)
    assert len(entries) == 2, entries


def test_a_malformed_paths_n_falls_back_to_the_stored_count(tmp_path):
    """Falling back is right; falling back SILENTLY is not — it would hide
    corruption behind a plausible number. The count is what the fallback
    yields, and the module reports the occurrence on stderr."""
    led = _ledger(tmp_path, ["/r precommit:aaa clean paths=a.py#b.py paths_n=abc"])
    assert rrr.load_entries(led)[0]["n_paths"] == 2


def test_a_wellformed_paths_n_is_preferred_over_the_stored_count(tmp_path):
    """PAIRED RECOVERY, and the defect I shipped: `paths=` is capped at 12,
    so recomputing the count from it reports 0% truncation on a ledger that
    is 17% truncated. `paths_n=` carries the TRUE width."""
    led = _ledger(tmp_path, [_line("/r", "aaa", "clean", ["a.py"], paths_n=40)])
    assert rrr.load_entries(led)[0]["n_paths"] == 40


# --------------------------------------------------------------------------
# Population selection
# --------------------------------------------------------------------------

@pytest.mark.parametrize("line,why", [
    ("/r deadbeef clean paths=a.py paths_n=1", "not precommit-keyed"),
    ("/r precommit:aaa clean", "no paths= field"),
    ("/r precommit:aaa unknown-outcome paths=a.py paths_n=1", "not clean/blockers"),
    ("", "blank"),
    ("garbage", "malformed"),
])
def test_unreplayable_lines_are_skipped_not_crashed_on(tmp_path, line, why):
    """Each mirrors a production `continue` guard. A line production skips
    must not enter the population, or every per-repo figure is biased."""
    assert rrr.load_entries(_ledger(tmp_path, [line])) == [], why


def test_a_missing_ledger_returns_empty_rather_than_raising(tmp_path):
    assert rrr.load_entries(str(tmp_path / "nope")) == []


# --------------------------------------------------------------------------
# THE CENTRAL TEST — faithfulness to production
# --------------------------------------------------------------------------

def test_derive_matches_production_on_generated_ledgers(tmp_path):
    """This tool's whole value is that its walk behaves like production's.

    Generates randomized ledgers and asserts `derive(overlap, ...)` equals
    `record_review.derive_review_round` on every one. Without this, drift in
    either walk is invisible and every published figure silently rots.
    """
    rng = random.Random(20260921)
    pool = ["a.py", "b.py", "c.py", "README.md", "dir", "dir/x.py"]
    repo = "/r"

    for trial in range(200):
        lines, entries = [], []
        for i in range(rng.randint(0, 6)):
            paths = rng.sample(pool, rng.randint(1, 3))
            outcome = rng.choice(["clean", "blockers:1", "blockers:3"])
            lines.append(_line(repo, f"k{i}", outcome, paths))
            entries.append((paths, outcome))
        led = _ledger(tmp_path / f"t{trial}", lines) if lines else _ledger(tmp_path / f"t{trial}", [])

        call = rng.sample(pool, rng.randint(1, 3))
        prior = rrr.load_entries(led)
        mine = rrr.derive(rrr.overlap, repo, frozenset(
            rrr.fc.normalize_path(p) for p in call), prior)

        # Real signature: (last_reviewed_path, repo_root, raw_paths).
        # `.derived_round` by name -- RoundDerivation._fields is
        # ('derived_round','blockers_found','stopped_at_clean'); an earlier
        # `hasattr(got,"round")` fallback was dead code from a guessed
        # signature and always took the positional branch.
        theirs = rr.derive_review_round(led, repo, call).derived_round

        assert mine == theirs, (
            f"trial {trial}: replay={mine} production={theirs}\n"
            f"  ledger={entries}\n  call={call}"
        )


def test_clean_resets_and_blockers_increment(tmp_path):
    """The chain rule itself, stated explicitly rather than only implied by
    the differential test — so a reader can see the intended semantics."""
    led = _ledger(tmp_path, [
        _line("/r", "a", "blockers:1", ["f.py"]),
        _line("/r", "b", "blockers:1", ["f.py"]),
    ])
    prior = rrr.load_entries(led)
    assert rrr.derive(rrr.overlap, "/r", frozenset(["f.py"]), prior) == 3

    led2 = _ledger(tmp_path / "x", [
        _line("/r", "a", "blockers:1", ["f.py"]),
        _line("/r", "b", "clean", ["f.py"]),
    ])
    assert rrr.derive(rrr.overlap, "/r", frozenset(["f.py"]),
                      rrr.load_entries(led2)) == 1


def test_entries_from_another_repo_never_join_the_chain(tmp_path):
    """Repo scoping. Without it every repo's chains merge into one."""
    led = _ledger(tmp_path, [
        _line("/other", "a", "blockers:1", ["f.py"]),
        _line("/other", "b", "blockers:1", ["f.py"]),
    ])
    assert rrr.derive(rrr.overlap, "/r", frozenset(["f.py"]),
                      rrr.load_entries(led)) == 1


# --------------------------------------------------------------------------
# The predicate itself
# --------------------------------------------------------------------------

@pytest.mark.parametrize("call,entry,want", [
    ({"a.py"}, {"a.py"}, True),
    ({"a.py"}, {"a.py", "b.py"}, True),
    ({"a.py", "b.py"}, {"a.py"}, True),
    ({"m/x.py"}, {"m"}, True),
    ({"f1.py", "README.md"}, {"f2.py", "README.md"}, False),
    ({"a.py"}, {"b.py"}, False),
    ({"foo.py.bak"}, {"foo.py"}, False),
])
def test_same_boundary_shape_table(call, entry, want):
    assert rrr.same_boundary(frozenset(call), frozenset(entry)) is want


@pytest.mark.parametrize("call,entry", [
    (set(), set()),
    ({"a.py"}, set()),
    (set(), {"a.py"}),
])
def test_empty_sets_never_match_under_either_predicate(call, entry):
    """`all([])` is vacuously True, which would make a path-less entry match
    EVERY call — a chain-merger strictly worse than the defect being fixed.
    Both predicates must agree here, or the two columns are not comparable."""
    c, e = frozenset(call), frozenset(entry)
    assert rrr.same_boundary(c, e) is False
    assert rrr.overlap(c, e) is False


def test_the_candidate_matches_a_strict_subset_of_the_shipped_rule():
    """The property the tool's own guidance rests on: `same_boundary` implies
    `paths_overlap`. It is why a round can only RISE when a CLEAN entry stops
    closing the chain. If this ever fails, that guidance is false."""
    rng = random.Random(7)
    pool = ["a", "b", "c", "d/e", "d", "README.md"]
    for _ in range(2000):
        c = frozenset(rng.sample(pool, rng.randint(1, 3)))
        e = frozenset(rng.sample(pool, rng.randint(1, 3)))
        if rrr.same_boundary(c, e):
            assert rrr.overlap(c, e), (c, e)


def test_self_test_passes():
    assert rrr.self_test() == 0


# --------------------------------------------------------------------------
# ROUND-2 SURFACE — the reset/increment split, truncation fallbacks, and the
# monotone assertion.
#
# These exist because round 2 shipped four new features with ZERO tests, and
# two of them were defective in ways the 27 round-1 tests could not see: a
# cosmetic display flag inverted the monotone verdict, and an identity check
# on a function object made the headline depend on how a callable was built.
# The suite's own docstring already named this shape ("a green self-test was
# not evidence about them"); round 2 reproduced it one layer up.
# --------------------------------------------------------------------------

def test_the_reset_predicate_is_not_identified_by_object_identity(tmp_path):
    """THE B4 DEFECT. `reset_pred is overlap` made the result depend on HOW
    the callable was constructed: a lambda wrapping `overlap` computes the
    identical thing but is a different object, which flipped the live
    headline from 88 changed / 0 up to 184 changed / 101 up — i.e. from
    'provably monotone' to 'manufactures 101 false-high rounds'."""
    import functools

    led = _ledger(tmp_path, [
        _line("/r", "a", "blockers:1", ["f1.py", "README.md"]),
        _line("/r", "b", "clean", ["f2.py", "README.md"]),
        _line("/r", "c", "blockers:1", ["f1.py", "README.md"]),
    ])
    entries = rrr.load_entries(led)

    def totals(reset_pred):
        per = rrr.replay(entries, rrr.same_boundary, reset_pred=reset_pred,
                         trunc_fallback="half-sample", reset_uses_candidate=False)
        return (sum(r["changed"] for r in per.values()),
                sum(r["up"] for r in per.values()))

    bare = totals(rrr.overlap)
    assert totals(lambda c, e: rrr.overlap(c, e)) == bare
    assert totals(functools.partial(rrr.overlap)) == bare


def test_a_clean_entry_closes_the_chain_on_overlap_not_containment(tmp_path):
    """The ADOPTED semantics (plan rev 3). A partially-overlapping clean
    still closes — unchanged from today — which is what makes the change
    monotone. Requiring containment to close is what put entries into the
    >=8 refusal band."""
    led = _ledger(tmp_path, [
        _line("/r", "a", "blockers:1", ["f1.py", "README.md"]),
        _line("/r", "b", "clean", ["f2.py", "README.md"]),
    ])
    prior = rrr.load_entries(led)
    call = frozenset(["f1.py", "README.md"])
    per = rrr.replay(prior + [{"line": 9, "repo": "/r", "key": "z",
                               "status": rr.OUTCOME_BLOCKERS, "paths": call,
                               "fields": {}, "n_paths": 2}],
                     rrr.same_boundary, reset_pred=rrr.overlap,
                     trunc_fallback="none", reset_uses_candidate=False)
    assert sum(r["up"] for r in per.values()) == 0


def test_a_disjoint_clean_does_not_close_the_chain(tmp_path):
    """PAIRED RECOVERY for the case above: 'overlap closes' must not decay
    into 'anything closes'."""
    assert rrr.overlap(frozenset(["a.py"]), frozenset(["b.py"])) is False


def test_is_truncated_is_keyed_on_the_stored_count_not_a_literal_12(tmp_path):
    """`_MAX_PATHS_IN_FIELD` is a writer-side constant. A hardcoded 12 here
    silently stops matching if it ever changes — and computing the count
    from the already-truncated field reported 0% truncation on a ledger
    that is 17% truncated."""
    led = _ledger(tmp_path, [
        _line("/r", "a", "clean", ["x.py"], paths_n=40),   # stored 1, true 40
        _line("/r", "b", "clean", ["y.py"], paths_n=1),    # stored 1, true 1
    ])
    a, b = rrr.load_entries(led)
    assert rrr.is_truncated(a) is True
    assert rrr.is_truncated(b) is False


@pytest.mark.parametrize("sample,call,want", [
    (["a", "b"], ["a", "b"], True),          # 2/2
    (["a", "b"], ["a"], True),               # 1/2 == exactly half
    (["a", "b", "c"], ["a"], False),         # 1/3 under half
    (["a", "b", "c", "d"], ["a", "b"], True),  # 2/4 exactly half
    ([], ["a"], False),                      # empty sample never matches
    (["a"], [], False),                      # empty call never matches
])
def test_half_sample_fallback_at_the_boundary(sample, call, want):
    """Variant E's cut. Exactly-half must MATCH (>= 50%), just-under must
    not — a boundary that silently flips inverts the fallback's meaning."""
    assert rrr.half_sample_under_call(
        frozenset(call), frozenset(sample)) is want


def test_the_union_fallback_keeps_the_shape5_overcount_alive(tmp_path):
    """Why variant E was adopted over D: a plain `overlap` fallback re-merges
    two boundaries that share one file whenever the entry is truncated — the
    exact defect this whole change exists to fix, kept alive for the 17% of
    entries that are truncated."""
    sample = frozenset(["README.md"] + [f"f{i}.py" for i in range(11)])
    call = frozenset(["other.py", "README.md"])
    assert rrr.overlap(call, sample) is True             # D merges
    assert rrr.half_sample_under_call(call, sample) is False  # E separates


def test_min_entries_cannot_change_the_monotone_verdict_or_exit_code(tmp_path, capsys):
    """THE B3 DEFECT. `--min-entries` is a DISPLAY filter. Feeding it into
    the monotone assertion meant a cosmetic flag could turn a failing
    assertion green: measured on the live ledger, --min-entries 1800 printed
    'up == 0 in every repo' and exited 0 for a rule that manufactures 112
    false-high rounds."""
    led = _ledger(tmp_path, [
        _line("/big", "a", "blockers:1", ["f1.py", "README.md"]),
        _line("/big", "b", "clean", ["f2.py", "README.md"]),
        _line("/big", "c", "blockers:1", ["f1.py", "README.md"]),
        _line("/big", "d", "blockers:1", ["f1.py", "README.md"]),
    ])
    base = ["--ledger", led, "--reset-predicate", "same", "--trunc-fallback", "none"]
    shown = rrr.main(base + ["--min-entries", "1"])
    shown_out = capsys.readouterr().out
    hidden = rrr.main(base + ["--min-entries", "9999"])
    hidden_out = capsys.readouterr().out
    assert shown == hidden, "a display filter changed the exit code"

    # The PRINTED figures must be filter-invariant too, not just the return
    # value. Asserting only the exit code is what let the DOWN count stay
    # on the filtered counter inside the very sentence the UP count was
    # fixed in: at --min-entries 400 one screen showed UP=112 (true) beside
    # DOWN=89 (true 100), and at 1800 DOWN read 0. DOWN is the "intended
    # correction" figure, so under-reporting it understates the benefit
    # while UP correctly reports the risk -- a biased comparison.
    def _fig(out, label):
        m = re.search(label + r" \((\d+)\)|" + label + r" all (\d+)", out)
        assert m, f"{label!r} not found in output -- the wording changed and "
        # a None==None comparison below would have passed vacuously
        return m.group(1) or m.group(2)

    assert _fig(shown_out, "DOWN moves") == _fig(hidden_out, "DOWN moves")
    assert _fig(shown_out, "Inspect") == _fig(hidden_out, "Inspect")

    # The VERDICT LINE is a THIRD read of the same fact, independent of the
    # exit code and of the figures above. Asserting only the return value
    # let a single-line mutation print "MONOTONE: up == 0 in every repo"
    # directly above "Inspect all 112" while exiting 1 -- with all 44 tests
    # green. The two reads were only consistent because one edit happened
    # to fix both, not because anything constrained them.
    assert ("NOT MONOTONE" in shown_out) == ("NOT MONOTONE" in hidden_out)
    for rc, out in ((shown, shown_out), (hidden, hidden_out)):
        assert (rc == 0) == ("NOT MONOTONE" not in out), (
            f"verdict line and exit code disagree: rc={rc}")


def test_the_json_path_carries_the_same_verdict_and_exit_code(tmp_path, capsys):
    """R2: `--json` returned 0 unconditionally, so the assertion protected
    only the human-readable path — while JSON is the one a caller gates on.
    The payload must also name the FULL variant; an artifact that cannot be
    tied to its config is the attribution failure that started #5828."""
    led = _ledger(tmp_path, [
        _line("/r", "a", "blockers:1", ["f1.py", "README.md"]),
        _line("/r", "b", "clean", ["f2.py", "README.md"]),
        _line("/r", "c", "blockers:1", ["f1.py", "README.md"]),
    ])
    base = ["--ledger", led, "--reset-predicate", "same", "--trunc-fallback", "none"]
    text_rc = rrr.main(base)
    capsys.readouterr()
    json_rc = rrr.main(base + ["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert json_rc == text_rc
    assert payload["monotone"] is (payload["up_moves"] == 0)
    for field in ("predicate", "reset_predicate", "trunc_fallback"):
        assert field in payload, field


def test_an_empty_ledger_exits_2_distinctly_from_a_monotone_result(tmp_path, capsys):
    """Exit-code contract: 0 monotone / 1 non-monotone / 2 nothing to
    replay. 'could not replay' must never read as 'replayed, all clear'."""
    assert rrr.main(["--ledger", str(_ledger(tmp_path, []))]) == 2
    capsys.readouterr()
    led = _ledger(tmp_path / "ok", [_line("/r", "a", "clean", ["f.py"])])
    assert rrr.main(["--ledger", led]) == 0


def test_replay_requires_the_reset_intent_to_be_stated(tmp_path):
    """F7. There is deliberately NO default for `reset_uses_candidate`.

    An inferred default (`reset_pred is not overlap`) reproduces the B4
    defect verbatim for the next caller — and was itself untested, so
    mutating it to a constant left all 41 tests green. A mandatory
    keyword-only argument cannot silently infer wrong.
    """
    led = _ledger(tmp_path, [_line("/r", "a", "clean", ["f.py"])])
    entries = rrr.load_entries(led)
    with pytest.raises(TypeError):
        rrr.replay(entries, rrr.same_boundary, reset_pred=rrr.overlap)


def test_elide_keeps_two_similar_repo_paths_distinguishable():
    """N1. Left-truncation rendered `…/69-reap-sweep-5260-v2` and
    `…/69-reap-sweep-5260` near-identically — backwards, since the
    distinguishing part of a repo path is usually its tail. A function
    whose whole purpose is that two paths not collide must be tested on
    two paths that nearly do."""
    a = "/Users/someone/Desktop/Proj/.claude/worktrees/69-reap-sweep-5260-v2"
    b = "/Users/someone/Desktop/Proj/.claude/worktrees/69-reap-sweep-5260"
    ea, eb = rrr._elide(a), rrr._elide(b)
    assert ea != eb, (ea, eb)
    assert len(ea) <= 52 and len(eb) <= 52
    assert ea.endswith("-v2")


def test_elide_leaves_a_short_path_untouched():
    """PAIRED RECOVERY: elision must not fire when it is not needed."""
    assert rrr._elide("/short/path") == "/short/path"


def test_replay_scopes_the_chain_walk_to_one_repo(tmp_path):
    """BLOCKER 2. `replay()`'s inner `derive_new` is a SECOND walk that
    `derive()` does not share, and its repo guard had no test.

    Removing that one line leaves all 44 tests green while inverting the
    adopted rule's entire justification on the live ledger: up=0/changed=88/
    MONOTONE/exit 0 becomes up=3/changed=96/NOT MONOTONE/exit 1. The whole
    case for the rule is `up == 0`.
    """
    led = _ledger(tmp_path, [
        _line("/other", "a", "blockers:1", ["f.py"]),
        _line("/other", "b", "blockers:1", ["f.py"]),
        _line("/r", "c", "blockers:1", ["f.py"]),
    ])
    per = rrr.replay(rrr.load_entries(led), rrr.same_boundary,
                     reset_pred=rrr.overlap, trunc_fallback="none",
                     reset_uses_candidate=False)
    assert per["/r"]["peak_new"] == 1, "another repo's chain leaked in"
    assert per["/r"]["peak_old"] == 1


def test_replay_actually_wires_in_the_truncation_fallback(tmp_path):
    """Finding 3. `half_sample_under_call` was tested in isolation but
    nothing asserted `replay()` CALLS it: forcing `inc_match` to ignore the
    fallback left 44 green while the live `changed` total moved 88 -> 106."""
    # The call must NOT be contained in the entry (or `same_boundary`
    # already matches and the fallback is never consulted -- my first
    # fixture made exactly that mistake and could not discriminate), but
    # must share >=50% of the truncated sample so the fallback DOES match.
    wide = [f"p{i}.py" for i in range(12)]
    call = wide[:7] + ["zz.py"]
    led = _ledger(tmp_path, [
        _line("/r", "a", "blockers:1", wide, paths_n=40),
        _line("/r", "b", "blockers:1", call, paths_n=len(call)),
    ])
    entries0 = rrr.load_entries(led)
    assert not rrr.same_boundary(entries0[1]["paths"], entries0[0]["paths"])
    assert rrr.half_sample_under_call(entries0[1]["paths"], entries0[0]["paths"])
    entries = rrr.load_entries(led)

    def changed(fb):
        per = rrr.replay(entries, rrr.same_boundary, reset_pred=rrr.overlap,
                         trunc_fallback=fb, reset_uses_candidate=False)
        return sum(r["changed"] for r in per.values())

    assert changed("none") != changed("half-sample"), (
        "the fallback is not reaching replay()'s increment test")


def test_prev_linked_relation_labels_are_directional(tmp_path):
    """Finding 4. Swapping the subset/superset labels left 44 green while
    the live census moved `call-superset-of-prev` 49 -> mislabeled and
    PARTIAL 37 -> 47. The doc's "of 37 partial pairs, 26 truncated" claim
    rests entirely on these labels being the right way round."""
    led = _ledger(tmp_path, [
        _line("/r", "aaa", "clean", ["a.py"]),
        "/r precommit:bbb clean paths=a.py#b.py paths_n=2 prev=precommit:aaa",
    ])
    rel, _partial = rrr.prev_linked_relations(rrr.load_entries(led))
    # the CALL (a.py, b.py) is a SUPERSET of its prev (a.py)
    assert rel["call-superset-of-prev"] == 1, dict(rel)
    assert rel["call-subset-of-prev"] == 0, dict(rel)
