"""Hermetic tests for hooks/issue_wheel_queue.py — THE ISSUE WHEEL's Queue
Keeper (Component A). Renamed from test_sdw_queue.py (issue_wheel_consolidation.md
§5, commit 2) alongside issue_wheel_queue.py itself.

Everything here is pure-function or filesystem-only against tmp_path; no real
`gh`/`git` subprocess call is ever made (load_gh_open_issues / load_dirty_paths
are exercised only through their injectable seams in run(), or their pure
helper functions are tested directly against fabricated subprocess output).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402
import issue_wheel_queue as sq  # noqa: E402


# ===========================================================================
# Pure helpers.
# ===========================================================================


class TestPathInExclusiveSet:
    def test_estimate_engine_v3_subtree_matches(self):
        assert sq._path_in_exclusive_set("modules/estimate_engine_v3/estimate_generator/generator.py")

    def test_catalog_source_v3_top_level_file_matches(self):
        assert sq._path_in_exclusive_set("modules/catalog_api_public/data/catalog_source_v3/Items.csv")

    def test_trade_kb_subtree_matches(self):
        assert sq._path_in_exclusive_set("_Config_Project/trade_kb/checklists/bath.md")

    def test_catalog_rulings_doc_matches_exactly(self):
        assert sq._path_in_exclusive_set("_Config_Project/docs/domain/catalog_rules_and_rulings.md")

    def test_unrelated_module_does_not_match(self):
        assert not sq._path_in_exclusive_set("modules/billing/api/webhook_checkout_handler.py")

    def test_estimate_product_layer_is_a_different_module_and_does_not_match(self):
        # This is the exact confusion that caused the 9/10 park incident: the
        # loop's OWN paths under modules/estimate_engine_v3/ are exclusive,
        # but a sibling module name must never accidentally match.
        assert not sq._path_in_exclusive_set(
            "modules/estimate_product_layer/frontend/vite.config.ts"
        )


class TestExcludedLabels:
    def test_dept_prefix_excluded(self):
        assert sq._has_excluded_label(["dept:marketing"]) == "dept:marketing"

    def test_operator_only_excluded(self):
        assert sq._has_excluded_label(["operator-only"]) == "operator-only"

    def test_needs_ruling_label_excluded(self):
        assert sq._has_excluded_label(["needs-ruling"]) == "needs-ruling"

    def test_case_insensitive(self):
        assert sq._has_excluded_label(["Dept:Marketing"]) == "Dept:Marketing"

    def test_ordinary_labels_pass(self):
        assert sq._has_excluded_label(["bug", "area:billing", "difficulty:2"]) is None

    def test_empty_or_none_passes(self):
        assert sq._has_excluded_label([]) is None
        assert sq._has_excluded_label(None) is None


class TestCommentBlocks:
    def test_needs_ruling_phrase_blocks(self):
        assert sq._comment_blocks("This needs a ruling before anyone touches it.")

    def test_needs_ruling_no_article_blocks(self):
        assert sq._comment_blocks("needs ruling from operator")

    def test_do_not_fix_blocks(self):
        assert sq._comment_blocks("Do not fix — waiting on vendor.")

    def test_blocked_on_operator_blocks(self):
        assert sq._comment_blocks("blocked on operator decision")

    def test_ordinary_comment_passes(self):
        assert not sq._comment_blocks("Fixed in a9f0834f8, closing.")

    def test_none_passes(self):
        assert not sq._comment_blocks(None)


class TestExpandAndCheckPaths:
    def test_literal_existing_path_survives(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["a.py"])
        assert surviving == ["a.py"]
        assert dropped == []
        assert escaped == []
        assert whole_repo == []

    def test_literal_missing_path_is_dropped(self, tmp_path):
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["does_not_exist.py"])
        assert surviving == []
        assert dropped == ["does_not_exist.py"]
        assert escaped == []
        assert whole_repo == []

    def test_glob_with_matches_expands_to_concrete_paths(self, tmp_path):
        (tmp_path / "mod").mkdir()
        (tmp_path / "mod" / "a.py").write_text("x")
        (tmp_path / "mod" / "b.py").write_text("x")
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["mod/*.py"])
        assert sorted(surviving) == ["mod/a.py", "mod/b.py"]
        assert dropped == []
        assert escaped == []
        assert whole_repo == []

    def test_glob_with_no_matches_is_dropped(self, tmp_path):
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["nomatch/**/*.py"])
        assert surviving == []
        assert dropped == ["nomatch/**/*.py"]
        assert escaped == []
        assert whole_repo == []

    def test_directory_path_survives_as_a_directory(self, tmp_path):
        (tmp_path / "mod").mkdir()
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["mod/"])
        # os.path.exists on a directory is True regardless of trailing slash;
        # the resolved repo-relative form drops the trailing slash.
        assert surviving == ["mod"]
        assert dropped == []
        assert escaped == []
        assert whole_repo == []

    def test_mixed_survivors_and_drops(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(tmp_path), ["a.py", "missing.py"])
        assert surviving == ["a.py"]
        assert dropped == ["missing.py"]
        assert escaped == []
        assert whole_repo == []

    # --- BLOCKER 1/2 RED-PROOF: absolute paths and ../ traversal must never
    # resolve to something outside the repo, regardless of what exists there.

    def test_absolute_path_into_another_real_directory_is_escaped_not_survived(self, tmp_path):
        """Pre-fix, os.path.join(repo, p) silently DISCARDS repo when p is
        absolute (stdlib os.path.join behavior) -- an absolute path pointing
        at a real file anywhere on disk would then survive as if it were a
        genuine repo-relative path. Must be rejected into `escaped`, never
        `surviving`, regardless of whether the absolute target exists."""
        outside = tmp_path.parent / f"outside_{tmp_path.name}"
        outside.mkdir(exist_ok=True)
        (outside / "generator.py").write_text("x")
        repo = tmp_path / "repo"
        repo.mkdir()
        abs_path = str(outside / "generator.py")
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), [abs_path])
        assert surviving == []
        assert escaped == [abs_path]
        assert whole_repo == []

    def test_dotdot_traversal_escaping_repo_is_escaped_not_survived(self, tmp_path):
        """A ../../../ style traversal that resolves outside the repo root
        must be rejected into `escaped`, even when the resolved target
        genuinely exists on disk (e.g. /etc/hosts)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        traversal = "../../../../../../../../etc/hosts"
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), [traversal])
        assert surviving == []
        assert escaped == [traversal]
        assert whole_repo == []

    def test_traversal_that_stays_inside_repo_survives_normally(self, tmp_path):
        """A `..` segment that resolves back to somewhere still INSIDE the
        repo (e.g. mod/../a.py -> a.py) is not an escape -- containment, not
        the literal presence of `..`, is what's being enforced."""
        repo = tmp_path / "repo"
        (repo / "mod").mkdir(parents=True)
        (repo / "a.py").write_text("x")
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), ["mod/../a.py"])
        assert surviving == ["a.py"]
        assert escaped == []
        assert whole_repo == []

    def test_absolute_glob_pattern_is_escaped(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        pattern = "/etc/*.conf"
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), [pattern])
        assert surviving == []
        assert escaped == [pattern]
        assert whole_repo == []

    # --- MAJOR RED-PROOF (round 3): "." (and the repo's own absolute path)
    # must resolve to the repo root and be rejected as `whole_repo`, never
    # `surviving` -- pre-fix, resolve_repo_relative_path(repo, ".") returned
    # "" (a valid containment result, since "" IS the repo), which then
    # passed _path_in_exclusive_set("") (no glob prefix matches an empty
    # string) and the dirty-path guard (no dirty entry matches an empty
    # string either) as if it were an ordinary narrow single-file claim.

    def test_dot_resolves_to_repo_root_and_is_rejected_as_whole_repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), ["."])
        assert surviving == []
        assert escaped == []
        assert whole_repo == ["."]

    def test_repos_own_absolute_path_is_rejected_as_whole_repo(self, tmp_path):
        """The repo's own absolute path (as a declared candidate) resolves
        to the same "" repo-root shape as "." -- must be rejected the same
        way, never treated as merely `escaped` (it IS contained -- it just
        IS the whole repo) nor as `surviving` (os.path.exists on the repo
        root itself would trivially be True, which is exactly the bug)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        surviving, dropped, escaped, whole_repo = sq.expand_and_check_paths(str(repo), [str(repo)])
        assert surviving == []
        assert escaped == []
        assert whole_repo == [str(repo)]


class TestComputeEffectiveRank:
    """FIX-Q4: aging is now bounded, PER-WEEK (not per-day), and floored at
    1 -- see compute_effective_rank's own docstring for the exact formula
    (age_weeks = age_days // 7; bounded_age = min(age_weeks, eff_rank - 1)).
    """

    def test_zero_age_no_shift(self):
        now = 1_000_000.0
        eff = sq.compute_effective_rank(5, sq._iso_now(now), now, fallback_rank=99)
        assert eff == 5

    def test_one_day_old_is_less_than_one_week_no_shift_yet(self):
        # FIX-Q4: aging is now per-WEEK, not per-day -- a single day old no
        # longer shifts effective_rank at all (pre-fix this shifted by 1).
        now = 1_000_000.0
        one_day_ago = now - 86400
        eff = sq.compute_effective_rank(5, sq._iso_now(one_day_ago), now, fallback_rank=99)
        assert eff == 5

    def test_exactly_one_week_old_shifts_by_one(self):
        now = 1_000_000.0
        one_week_ago = now - (86400 * 7)
        eff = sq.compute_effective_rank(5, sq._iso_now(one_week_ago), now, fallback_rank=99)
        assert eff == 4

    def test_ten_weeks_old_shifts_by_ten(self):
        now = 1_000_000.0
        ten_weeks_ago = now - (86400 * 7 * 10)
        eff = sq.compute_effective_rank(20, sq._iso_now(ten_weeks_ago), now, fallback_rank=99)
        assert eff == 10

    def test_partial_week_floors_down_not_up(self):
        # 1.9 weeks old must floor to 1 week, not round to 2 — the module
        # docstring is explicit this is floor(), not round().
        now = 1_000_000.0
        partial = now - (86400 * 7 * 1.9)
        eff = sq.compute_effective_rank(10, sq._iso_now(partial), now, fallback_rank=99)
        assert eff == 9

    def test_aging_is_bounded_and_never_drops_below_one(self):
        """FIX-Q4 RED-PROOF: pre-fix, unbounded per-day aging could drive
        effective_rank negative for an old enough low-priority item. Now
        bounded at (rank - 1), so effective_rank floors at exactly 1
        regardless of how old the item is."""
        now = 1_000_000.0
        # rank 3, 100 weeks old -- age_weeks(100) would blow way past
        # rank-1=2 under an unbounded subtraction; must floor at 1.
        hundred_weeks_ago = now - (86400 * 7 * 100)
        eff = sq.compute_effective_rank(3, sq._iso_now(hundred_weeks_ago), now, fallback_rank=99)
        assert eff == 1

    def test_aging_bound_uses_exactly_rank_minus_one(self):
        """The bound is rank - 1, not some other floor -- rank 5, enough
        age to exceed 4 weeks, must floor at effective_rank 1 (5 - 4),
        never lower."""
        now = 1_000_000.0
        fifty_weeks_ago = now - (86400 * 7 * 50)
        eff = sq.compute_effective_rank(5, sq._iso_now(fifty_weeks_ago), now, fallback_rank=99)
        assert eff == 1

    def test_missing_rank_uses_fallback(self):
        now = 1_000_000.0
        eff = sq.compute_effective_rank(None, sq._iso_now(now), now, fallback_rank=42)
        assert eff == 42

    def test_missing_first_ready_at_treated_as_zero_age(self):
        now = 1_000_000.0
        eff = sq.compute_effective_rank(7, None, now, fallback_rank=99)
        assert eff == 7

    def test_unparseable_first_ready_at_treated_as_zero_age(self):
        now = 1_000_000.0
        eff = sq.compute_effective_rank(7, "not-a-date", now, fallback_rank=99)
        assert eff == 7


class TestApplyValidPredicate:
    def _base_item(self, **overrides):
        item = {
            "issue": 100,
            "open": True,
            "title": "sample",
            "labels": [],
            "last_comment": None,
            "paths": ["a.py"],
            "size_points": 2,
        }
        item.update(overrides)
        return item

    def test_closed_issue_is_invalid(self, tmp_path):
        """Unit-level check of the PURE predicate only: apply_valid_predicate
        must reject an item whose `open` key is explicitly False (this is
        the shape run()'s real resolve_open_state() produces once it has
        confirmed an issue closed — see TestRunEndToEnd's
        test_ledger_only_item_confirmed_closed_via_gh_view_is_dropped for the
        REAL production path this predicate is actually driven from, through
        merge_sources -> resolve_open_state -> confirm_issue_state, never a
        raw open=False literal in production)."""
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(open=False), repo=str(tmp_path), dirty_paths=set()
        )
        assert not ok
        assert reason == "closed"

    def test_missing_open_key_defaults_to_state_unconfirmed_not_open(self, tmp_path):
        """A genuinely missing `open` key (the predicate's own fail-closed
        default) must never be treated as open -- this is the safety net for
        any caller that bypasses run()'s resolve_open_state() confirmation
        step entirely."""
        (tmp_path / "a.py").write_text("x")
        item = self._base_item()
        del item["open"]
        ok, reason, _ = sq.apply_valid_predicate(item, repo=str(tmp_path), dirty_paths=set())
        assert not ok
        assert reason == "state-unconfirmed"

    def test_open_state_reason_preferred_over_generic_closed(self, tmp_path):
        """MINOR 3 RED-PROOF (unit level): when the item carries an explicit
        `open_state_reason` (resolve_open_state()'s own more specific marker
        for "gh-unreachable" / "unconfirmable"), that reason must be
        reported instead of the generic "closed" -- this is what run()'s
        dropped log actually surfaces through this predicate's return
        value."""
        (tmp_path / "a.py").write_text("x")
        item = self._base_item(open=False)
        item["open_state_reason"] = "unconfirmable"
        ok, reason, _ = sq.apply_valid_predicate(item, repo=str(tmp_path), dirty_paths=set())
        assert not ok
        assert reason == "unconfirmable"

    def test_excluded_label_is_invalid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(labels=["operator-only"]), repo=str(tmp_path), dirty_paths=set()
        )
        assert not ok
        assert reason.startswith("excluded-label")

    def test_blocking_comment_is_invalid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(last_comment="needs a ruling"), repo=str(tmp_path), dirty_paths=set()
        )
        assert not ok
        assert reason == "blocked-by-comment"

    def test_nonexistent_path_item_is_excluded(self, tmp_path):
        """RED-PROOF target 1: an item whose ONLY declared path does not
        exist on disk must never be emitted as ready — this is precisely the
        9/10-parked-items failure mode the whole module exists to prevent.
        """
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["modules/estimate_product_layer/estimate_generator/generator.py"]),
            repo=str(tmp_path),
            dirty_paths=set(),
        )
        assert not ok
        assert reason == "no-existing-paths"

    def test_partial_path_survival_narrows_paths_and_stays_valid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, resolved = sq.apply_valid_predicate(
            self._base_item(paths=["a.py", "missing.py"]), repo=str(tmp_path), dirty_paths=set()
        )
        assert ok
        assert reason is None
        assert resolved["paths"] == ["a.py"]
        assert resolved["dropped_paths"] == ["missing.py"]

    def test_dirty_path_item_is_excluded(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["a.py"]), repo=str(tmp_path), dirty_paths={"a.py"}
        )
        assert not ok
        assert reason == "dirty-path:a.py"

    def test_dirty_directory_prefix_excludes_nested_path(self, tmp_path):
        (tmp_path / "mod").mkdir()
        (tmp_path / "mod" / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["mod/a.py"]), repo=str(tmp_path), dirty_paths={"mod"}
        )
        assert not ok
        assert reason == "dirty-path:mod/a.py"

    def test_unknown_size_points_is_invalid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(size_points=None), repo=str(tmp_path), dirty_paths=set()
        )
        assert not ok
        assert reason == "size-unknown"

    def test_size_points_over_five_is_invalid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(size_points=6), repo=str(tmp_path), dirty_paths=set()
        )
        assert not ok
        assert reason == "too-large:6"

    def test_size_points_exactly_five_is_valid(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(size_points=5), repo=str(tmp_path), dirty_paths=set()
        )
        assert ok
        assert reason is None

    def test_estimate_loop_exclusive_path_item_is_excluded(self, tmp_path):
        """RED-PROOF target 2: an item whose path falls under the
        estimate-loop's exclusive set must never be emitted, even when every
        other leg of the predicate passes — the SDW must never contend with
        that loop's own files.
        """
        d = tmp_path / "modules" / "estimate_engine_v3" / "estimate_generator"
        d.mkdir(parents=True)
        (d / "generator.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["modules/estimate_engine_v3/estimate_generator/generator.py"]),
            repo=str(tmp_path),
            dirty_paths=set(),
        )
        assert not ok
        assert reason.startswith("estimate-loop-exclusive")

    def test_fully_valid_item_passes(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        ok, reason, resolved = sq.apply_valid_predicate(
            self._base_item(), repo=str(tmp_path), dirty_paths=set()
        )
        assert ok
        assert reason is None
        assert resolved["paths"] == ["a.py"]

    def test_absolute_path_into_a_sibling_real_directory_is_rejected_not_valid(self, tmp_path):
        """BLOCKER 1/2 RED-PROOF (end-to-end): pre-fix, an ABSOLUTE path
        pointing at a real file OUTSIDE the repo bypassed BOTH the
        exclusive-set fence and the dirty-path guard, because
        os.path.join(repo, p) silently discards `repo` for an absolute `p`,
        and the (then-string-only) exclusive-set/dirty-path checks compared
        the resulting absolute string against repo-relative glob prefixes --
        which never match, so the item came back VALID even though the path
        was never actually inside the repo at all. Must now be rejected
        outright, regardless of what the absolute path resolves to."""
        real_repo = tmp_path / "real_repo"
        real_repo.mkdir()
        outside = tmp_path / "outside" / "modules" / "estimate_engine_v3" / "estimate_generator"
        outside.mkdir(parents=True)
        abs_target = outside / "generator.py"
        abs_target.write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=[str(abs_target)]),
            repo=str(real_repo),
            dirty_paths=set(),
        )
        assert not ok
        assert reason == f"path-escapes-repo:{abs_target}"

    def test_dotdot_traversal_to_etc_hosts_is_rejected_not_valid(self, tmp_path):
        """BLOCKER 2 RED-PROOF (end-to-end): a `../../../../../../etc/hosts`
        style traversal must never be validated just because the resolved
        target happens to exist on disk."""
        repo = tmp_path / "repo"
        repo.mkdir()
        traversal = "../../../../../../../../etc/hosts"
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=[traversal]),
            repo=str(repo),
            dirty_paths=set(),
        )
        assert not ok
        assert reason == f"path-escapes-repo:{traversal}"

    # --- MAJOR RED-PROOF (round 3, end-to-end): a whole-repo claim ("." or
    # the repo's own absolute path) must never be validated, even when the
    # repo has completely clean git status and no other check would catch
    # it -- this is the exact executed repro from the round-2 review: a
    # dirty engine file ELSEWHERE in the repo never even factors in, because
    # the whole-repo claim is invalid on its own terms regardless of what
    # else is dirty.

    def test_dot_path_claim_is_rejected_even_with_engine_file_dirty_elsewhere(self, tmp_path):
        """Pre-fix: resolve_repo_relative_path(repo, ".") returned "" (the
        repo root, a valid containment result), which then passed
        _path_in_exclusive_set("") (empty string matches no glob prefix) and
        the dirty guard (empty string matches no dirty entry) even with an
        unrelated engine file genuinely dirty -- a whole-repo claim rode
        through emitted as a reserved_slot item, authorizing the entire
        tree. Must now be rejected outright as `whole-repo-path`."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "estimate_engine_v3" / "estimate_generator"
        d.mkdir(parents=True)
        (d / "generator.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["."]),
            repo=str(repo),
            dirty_paths={"modules/estimate_engine_v3/estimate_generator/generator.py"},
        )
        assert not ok
        assert reason == "whole-repo-path:."

    def test_repos_own_absolute_path_claim_is_rejected_not_valid(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=[str(repo)]),
            repo=str(repo),
            dirty_paths=set(),
        )
        assert not ok
        assert reason == f"whole-repo-path:{repo}"

    def test_whole_repo_claim_rejected_even_alongside_a_surviving_narrow_path(self, tmp_path):
        """A whole-repo entry must invalidate the WHOLE item even when other
        declared paths on it are genuinely narrow and would otherwise
        survive -- letting it ride along with a legitimate path would still
        authorize the entire tree via the one whole-repo entry."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "a.py").write_text("x")
        ok, reason, _ = sq.apply_valid_predicate(
            self._base_item(paths=["a.py", "."]),
            repo=str(repo),
            dirty_paths=set(),
        )
        assert not ok
        assert reason == "whole-repo-path:."


class TestMergeSources:
    def test_dedupes_by_issue_and_unions_fields(self):
        """BLOCKER fix (round 3): the ledger's `size_points` was sized
        against the LEDGER's own paths (x.py) -- once the ranked queue
        overwrites `paths` with its own, DIFFERENT set (y.py), the ledger's
        size_points describes a path set that no longer applies to this
        item and must not survive unchanged (see the BLOCKER RED-PROOF tests
        below for the full real-world repro this generalizes)."""
        gh = [{"issue": 1, "open": True, "title": "gh title", "labels": ["bug"], "last_comment": None}]
        ledger = [{"issue": 1, "paths": ["x.py"], "size_points": 2}]
        ranked = [{"issue": 1, "rank": 3, "title": "ranked title", "paths": ["y.py"]}]
        merged = sq.merge_sources(gh, ledger, ranked)
        assert len(merged) == 1
        item = merged[0]
        assert item["issue"] == 1
        assert item["labels"] == ["bug"]
        # size_points is dropped back to unknown -- it was sized against
        # ledger's paths (x.py), which paths no longer reflects.
        assert "size_points" not in item
        # ranked queue wins for title/paths (most curated source)
        assert item["title"] == "ranked title"
        assert item["paths"] == ["y.py"]

    def test_ledger_only_item_has_no_rank(self):
        merged = sq.merge_sources([], [{"issue": 2, "paths": ["z.py"], "size_points": 1}], [])
        assert len(merged) == 1
        assert "rank" not in merged[0]

    def test_gh_only_item_carries_no_paths(self):
        merged = sq.merge_sources(
            [{"issue": 3, "open": True, "title": "t", "labels": [], "last_comment": None}], [], []
        )
        assert merged[0].get("paths") is None

    # --- BLOCKER RED-PROOF (round 3): the exact real-world repro the
    # reviewer executed -- ledger sizes an issue against a SMALL path
    # (size_points:1, paths:['small/file.py']), the ranked queue carries
    # the SAME issue number with an entirely different, EXPANDED path set
    # (a glob-style subtree). Pre-fix, merge_sources kept the ledger's
    # size_points (setdefault, never touched by the ranked loop) while the
    # ranked loop unconditionally overwrote `paths` -- the surviving pair
    # was (ledger's size, ranked's paths), so the merged item claimed
    # size 1 while its own `paths` field actually named the huge subtree.
    # Downstream, apply_valid_predicate's size-points leg would then pass
    # VALID:True on size 1 while the item's paths authorized every file the
    # huge/subsystem/** glob expands to.

    def test_ledger_size_never_survives_a_ranked_path_swap_for_the_same_issue(self, tmp_path):
        ledger = [{"issue": 9999, "paths": ["small/file.py"], "size_points": 1}]
        ranked = [{"issue": 9999, "rank": 1, "paths": ["huge/subsystem/**"]}]
        merged = sq.merge_sources([], ledger, ranked)
        assert len(merged) == 1
        item = merged[0]
        assert item["paths"] == ["huge/subsystem/**"]
        # The stale size_points (sized against small/file.py, never
        # huge/subsystem/**) must NOT survive the path swap.
        assert "size_points" not in item

    def test_ledger_size_never_survives_a_ranked_path_swap_end_to_end(self, tmp_path):
        """Full end-to-end repro through apply_valid_predicate: pre-fix this
        would return VALID:True on size 1 while `paths` names a huge
        expanded subtree the reviewer never actually sized. Post-fix, the
        stale size_points is dropped, so the item now correctly fails
        size-unknown (fail-closed, per the module's own stated safety
        posture) rather than being silently authorized at the wrong size."""
        repo = tmp_path / "repo"
        d = repo / "huge" / "subsystem"
        d.mkdir(parents=True)
        (d / "a.py").write_text("x")
        (d / "b.py").write_text("x")
        ledger = [{"issue": 9999, "paths": ["small/file.py"], "size_points": 1}]
        ranked = [{"issue": 9999, "rank": 1, "paths": ["huge/subsystem/**"]}]
        merged = sq.merge_sources([], ledger, ranked)
        item = dict(merged[0], open=True)
        ok, reason, _ = sq.apply_valid_predicate(item, repo=str(repo), dirty_paths=set())
        assert not ok
        assert reason == "size-unknown"

    def test_control_same_paths_in_both_sources_keeps_ledger_size(self, tmp_path):
        """Control: when the ranked queue's `paths` for the same issue are
        the SAME paths the ledger already sized (no actual path swap), the
        ledger's size_points remains legitimately applicable and must be
        kept -- this fix must not blanket-drop size_points whenever the
        ranked queue merely re-asserts the identical path set."""
        ledger = [{"issue": 42, "paths": ["small/file.py"], "size_points": 3}]
        ranked = [{"issue": 42, "rank": 1, "paths": ["small/file.py"]}]
        merged = sq.merge_sources([], ledger, ranked)
        assert len(merged) == 1
        item = merged[0]
        assert item["paths"] == ["small/file.py"]
        assert item["size_points"] == 3


class TestMergeSourcesTierLookupPass:
    """FIX-Q4 Part B: merge_sources' final tier-lookup pass over the
    already-merged dict."""

    def test_every_merged_entry_gets_a_tier_from_the_map(self):
        ledger = [{"issue": 1, "paths": ["a.py"], "size_points": 1}]
        merged = sq.merge_sources([], ledger, [], (), {1: 0})
        assert merged[0]["tier"] == 0

    def test_issue_absent_from_tier_map_defaults_to_tier_2(self):
        ledger = [{"issue": 1, "paths": ["a.py"], "size_points": 1}]
        merged = sq.merge_sources([], ledger, [], (), {999: 0})
        assert merged[0]["tier"] == 2

    def test_none_tracker_tiers_defaults_every_entry_to_tier_2(self):
        """Matches the caller's own `tracker_tiers or {}` guard pattern --
        merge_sources itself also guards `tracker_tiers or {}` internally."""
        ledger = [{"issue": 1, "paths": ["a.py"], "size_points": 1}]
        merged = sq.merge_sources([], ledger, [], (), None)
        assert merged[0]["tier"] == 2

    def test_omitting_tracker_tiers_entirely_still_defaults_to_tier_2(self):
        """The 3-positional-arg call sites (this module's whole pre-FIX-Q4
        test suite) must keep working unchanged -- tier defaults to 2."""
        ledger = [{"issue": 1, "paths": ["a.py"], "size_points": 1}]
        merged = sq.merge_sources([], ledger, [])
        assert merged[0]["tier"] == 2


class TestMergeSourcesFreshTriageUnion:
    """FIX-Q7: merge_sources' new 4th parameter, fresh_triage_items. Reuses
    the plan's own described test cases (a)-(c), plus G1 (verbatim P1
    schema through the CLI end-to-end) and G2 (additive, never destructive).
    """

    def test_fresh_only_item_reaches_merged_output_with_size_points(self):
        """(a): a fresh_triage_items entry with no ledger/gh counterpart
        must merge in with its own size_points/paths -- reaching ready.json
        (once confirm_issue_state_fn resolves it open) is covered by the
        end-to-end test in TestRunEndToEnd below; this is the merge-level
        proof."""
        fresh = [{"number": 8001, "size_points": 2, "files_touched": ["a.py"], "reason": "fresh finding"}]
        merged = sq.merge_sources([], [], [], fresh)
        assert len(merged) == 1
        item = merged[0]
        assert item["issue"] == 8001
        assert item["size_points"] == 2
        assert item["paths"] == ["a.py"]
        assert item["title"] == "fresh finding"
        # Never open=True from this loop alone -- confirm_issue_state_fn is
        # the only path that sets it.
        assert "open" not in item

    def test_fresh_item_sharing_issue_with_stale_ledger_row_emits_fresh_values(self):
        """(b): fresh triage OVERWRITES a stale ledger row's size_points/
        paths for the same issue number."""
        ledger = [{"issue": 8002, "paths": ["stale/path.py"], "size_points": 5, "title": "stale reason"}]
        fresh = [{"number": 8002, "size_points": 1, "files_touched": ["fresh/path.py"], "reason": "fresh reason"}]
        merged = sq.merge_sources([], ledger, [], fresh)
        assert len(merged) == 1
        item = merged[0]
        assert item["size_points"] == 1
        assert item["paths"] == ["fresh/path.py"]
        assert item["title"] == "fresh reason"

    def test_fresh_item_also_in_ranked_queue_with_different_paths_still_loses_size_points(self):
        """(c): a fresh item whose issue ALSO appears in the ranked queue
        with genuinely DIFFERENT paths still has size_points dropped by the
        UNCHANGED round-3 branch -- this is the KEPT behavior (reversing
        the plan's own note that an earlier round wrongly assumed an
        exemption was needed here; none is)."""
        fresh = [{"number": 8003, "size_points": 1, "files_touched": ["fresh/path.py"], "reason": "fresh"}]
        ranked = [{"issue": 8003, "rank": 1, "paths": ["ranked/different/path.py"]}]
        merged = sq.merge_sources([], [], ranked, fresh)
        assert len(merged) == 1
        item = merged[0]
        assert item["paths"] == ["ranked/different/path.py"]
        assert "size_points" not in item

    def test_partial_fresh_record_never_destroys_a_good_ledger_value(self):
        """A fresh record with no files_touched/size_points at all must
        never overwrite a good prior ledger value with a missing one."""
        ledger = [{"issue": 8004, "paths": ["good/path.py"], "size_points": 3, "title": "good title"}]
        fresh = [{"number": 8004, "reason": "just an updated title, no sizing info"}]
        merged = sq.merge_sources([], ledger, [], fresh)
        assert len(merged) == 1
        item = merged[0]
        assert item["paths"] == ["good/path.py"]
        assert item["size_points"] == 3
        assert item["title"] == "just an updated title, no sizing info"

    def test_fresh_item_with_non_int_number_is_skipped(self):
        fresh = [{"number": "not-an-int", "size_points": 1, "files_touched": ["a.py"]}]
        merged = sq.merge_sources([], [], [], fresh)
        assert merged == []

    def test_fresh_triage_items_default_omitted_keeps_existing_call_sites_working(self):
        """fresh_triage_items=() is keyword-defaulted -- the 3-positional
        call convention this module's whole pre-FIX-Q7 suite uses must keep
        working unchanged."""
        merged = sq.merge_sources([], [{"issue": 1, "paths": ["a.py"], "size_points": 1}], [])
        assert len(merged) == 1

    def test_g2_fresh_union_is_additive_never_destructive_to_eligible_count(self, tmp_path):
        """G2: construct a fresh item that would overwrite a good ledger
        size_points with a MISSING one (a partial fresh record) and assert
        the eligible-item count does NOT decrease relative to running the
        same inputs without the fresh union -- proving the guarded
        overwrite behavior is additive, never destructive."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "good.py").write_text("x")
        ledger = [{"issue": 8005, "paths": ["good.py"], "size_points": 2}]

        without_fresh = sq.merge_sources([], ledger, [])
        with_partial_fresh = sq.merge_sources([], ledger, [], [{"number": 8005, "reason": "partial, no size"}])

        def _eligible_count(candidates):
            count = 0
            for item in candidates:
                item = dict(item, open=True)
                ok, _reason, _resolved = sq.apply_valid_predicate(item, repo=str(repo), dirty_paths=set())
                if ok:
                    count += 1
            return count

        assert _eligible_count(with_partial_fresh) >= _eligible_count(without_fresh)


class TestRankAndReserveTierSortKey:
    """FIX-Q4 Part C: sort is lexicographic on (tier, effective_rank,
    issue) -- a tier-2 item can never outrank a tier-0/1 item at any age."""

    def test_tier_0_always_sorts_before_tier_2_regardless_of_rank(self):
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 1, "tier": 2, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": 999, "tier": 0, "first_ready_at": sq._iso_now(now)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [2, 1]

    def test_no_amount_of_aging_lets_tier_2_cross_into_tier_0(self):
        """Even a VERY old tier-2 item (aged to its floor) must never
        outrank a fresh tier-0 item."""
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 5, "tier": 0, "first_ready_at": sq._iso_now(now)},
            {
                "issue": 2,
                "rank": 3,
                "tier": 2,
                "first_ready_at": sq._iso_now(now - 86400 * 7 * 500),
            },
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [1, 2]

    def test_within_same_tier_effective_rank_still_decides_order(self):
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 5, "tier": 1, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": 2, "tier": 1, "first_ready_at": sq._iso_now(now)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [2, 1]

    def test_missing_tier_field_defaults_to_2(self):
        """An item with no `tier` key at all (e.g. a synthetic/legacy test
        item built without going through merge_sources) defaults to tier 2,
        matching merge_sources' own default."""
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 1, "tier": 0, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": 1, "first_ready_at": sq._iso_now(now)},  # no tier key
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [1, 2]


class TestRankAndReserve:
    def test_reserved_slot_is_the_oldest_item(self):
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 1, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": 5, "first_ready_at": sq._iso_now(now - 86400 * 30)},
            {"issue": 3, "rank": 3, "first_ready_at": sq._iso_now(now - 86400 * 5)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        reserved = [it for it in ranked if it["reserved_slot"]]
        assert len(reserved) == 1
        assert reserved[0]["issue"] == 2

    def test_exactly_one_reserved_slot_regardless_of_count(self):
        now = 1_000_000.0
        items = [{"issue": i, "rank": i, "first_ready_at": sq._iso_now(now - i)} for i in range(1, 11)]
        ranked = sq.rank_and_reserve(items, now)
        reserved = [it for it in ranked if it["reserved_slot"]]
        assert len(reserved) == 1

    def test_empty_input_yields_empty_output(self):
        assert sq.rank_and_reserve([], 1_000_000.0) == []

    def test_single_item_is_always_reserved(self):
        now = 1_000_000.0
        ranked = sq.rank_and_reserve([{"issue": 1, "rank": 1, "first_ready_at": sq._iso_now(now)}], now)
        assert ranked[0]["reserved_slot"] is True

    def test_sort_order_uses_effective_rank_aging_can_reorder(self):
        # FIX-Q4: aging is now per-WEEK -- 5 days is still 0 full weeks, so
        # this needs a genuinely multi-week gap to reorder (pre-fix, per-day
        # aging reordered off a 5-day gap alone).
        now = 1_000_000.0
        # issue 1: rank 3, fresh (effective_rank 3)
        # issue 2: rank 5, 3 weeks old (effective_rank 5-3=2) -> sorts FIRST
        items = [
            {"issue": 1, "rank": 3, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": 5, "first_ready_at": sq._iso_now(now - 86400 * 7 * 3)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [2, 1]

    def test_tie_break_by_issue_number_ascending(self):
        now = 1_000_000.0
        items = [
            {"issue": 20, "rank": 1, "first_ready_at": sq._iso_now(now)},
            {"issue": 10, "rank": 1, "first_ready_at": sq._iso_now(now)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        assert [it["issue"] for it in ranked] == [10, 20]

    def test_no_rank_falls_back_to_unranked_floor_constant(self):
        """FIX-Q3 RED-PROOF: an unranked item's effective_rank must be the
        fixed UNRANKED_FLOOR constant (1000), not a computed "one past the
        worst ranked item" -- the old computed fallback degenerated to rank
        1 for EVERY item whenever no item in the batch had a real rank at
        all, which this test's OWN pre-fix sibling ('falls back past worst
        ranked item', fallback == worst + 1 == 6 here) could not catch,
        since it always included at least one genuinely ranked item."""
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": 5, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": None, "first_ready_at": sq._iso_now(now)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        # issue 2 has no rank -> fallback = UNRANKED_FLOOR (1000) -> sorts AFTER issue 1
        assert [it["issue"] for it in ranked] == [1, 2]
        assert ranked[1]["effective_rank"] == sq.UNRANKED_FLOOR

    def test_unranked_item_gets_floor_even_when_no_item_in_batch_has_a_real_rank(self):
        """FIX-Q3 RED-PROOF, the exact regression the constant floor fixes:
        pre-fix, `worst_rank = max(..., default=0)` defaulted to 0 when NO
        item had a real rank, so fallback_rank = 1 -- every item in an
        all-unranked batch got effective_rank 1, indistinguishable from a
        genuinely top-ranked item. Post-fix, every item still gets
        UNRANKED_FLOOR (1000), not 1."""
        now = 1_000_000.0
        items = [
            {"issue": 1, "rank": None, "first_ready_at": sq._iso_now(now)},
            {"issue": 2, "rank": None, "first_ready_at": sq._iso_now(now)},
        ]
        ranked = sq.rank_and_reserve(items, now)
        for it in ranked:
            assert it["effective_rank"] == sq.UNRANKED_FLOOR
            assert it["effective_rank"] != 1


class TestCarryForwardFirstReadyAt:
    def test_new_item_gets_now(self):
        candidates = [{"issue": 1}]
        sq._carry_forward_first_ready_at(candidates, {}, "2026-09-01T00:00:00Z")
        assert candidates[0]["first_ready_at"] == "2026-09-01T00:00:00Z"

    def test_previously_seen_item_keeps_its_original_timestamp(self):
        candidates = [{"issue": 1}]
        previous = {"items": [{"issue": 1, "first_ready_at": "2026-08-01T00:00:00Z"}]}
        sq._carry_forward_first_ready_at(candidates, previous, "2026-09-01T00:00:00Z")
        assert candidates[0]["first_ready_at"] == "2026-08-01T00:00:00Z"


# ===========================================================================
# End-to-end run() against a fabricated repo — no real gh/git subprocess.
# ===========================================================================


class TestRunEndToEnd:
    def _write_ledger(self, path, entries):
        payload = {
            "waves": [
                {"wave": 1, "needs_work": entries},
            ]
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_full_pipeline_excludes_nonexistent_path_item(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 500,
                    "size_points": 2,
                    "files_touched": ["does/not/exist.py"],
                    "reason": "phantom item",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert payload["items"] == []
        assert {"issue": 500, "reason": "no-existing-paths"} in payload["dropped"]
        assert payload["degraded"] is False
        # Confirm it was actually WRITTEN, not just returned.
        with open(ready_path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        assert on_disk == payload

    def test_full_pipeline_excludes_loop_path_item(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "estimate_engine_v3" / "estimate_generator"
        d.mkdir(parents=True)
        (d / "generator.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 501,
                    "size_points": 2,
                    "files_touched": ["modules/estimate_engine_v3/estimate_generator/generator.py"],
                    "reason": "engine item",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert payload["items"] == []
        assert any(d["issue"] == 501 and d["reason"].startswith("estimate-loop-exclusive") for d in payload["dropped"])

    def test_full_pipeline_emits_valid_item_with_reserved_slot(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 502,
                    "size_points": 3,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "real fix",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert len(payload["items"]) == 1
        assert payload["items"][0]["issue"] == 502
        assert payload["items"][0]["reserved_slot"] is True
        assert payload["degraded"] is False

    def test_second_run_preserves_first_ready_at_for_aging(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 503,
                    "size_points": 3,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "real fix",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        first = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        first_ready_at = first["items"][0]["first_ready_at"]

        second = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0 + 86400 * 3,
            now_iso="2026-09-04T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert second["items"][0]["first_ready_at"] == first_ready_at

    def test_dirty_path_from_git_status_excludes_item(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 504,
                    "size_points": 3,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "real fix but someone has it open",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths={"modules/billing/api/webhook.py"},
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert payload["items"] == []
        assert any(d["issue"] == 504 and d["reason"].startswith("dirty-path") for d in payload["dropped"])

    # --- BLOCKER 3 RED-PROOF: the REAL production path (a ledger-only item
    # absent from gh's open-list, individually confirmed CLOSED via
    # confirm_issue_state) -- replaces the old synthetic open=False unit test
    # for THIS end-to-end scenario, per the review's explicit instruction.

    def test_ledger_only_item_confirmed_closed_via_gh_view_is_dropped(self, tmp_path):
        """The exact '#9 was already CLOSED' class of bug: issue 9 is a
        ledger-only candidate, absent from gh's own open-issue list (source
        1 never mentions it at all -- gh_items=[]). Pre-fix, merge_sources()
        defaulted such an item to open=True unconditionally, so it would
        have been emitted as ready. Post-fix, run() must individually
        confirm its real state via confirm_issue_state() (here injected to
        report CLOSED, simulating a real `gh issue view 9` call) and drop it
        as closed -- never silently pass it through as open."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 9,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "already closed upstream",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        seen_confirm_calls = []

        def fake_confirm(repo_arg, issue_num):
            seen_confirm_calls.append(issue_num)
            return "CLOSED", [], None

        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=fake_confirm,
        )
        assert seen_confirm_calls == [9]
        assert payload["items"] == []
        assert {"issue": 9, "reason": "closed"} in payload["dropped"]
        assert payload["degraded"] is False

    def test_ranked_queue_only_item_confirmed_open_is_emitted(self, tmp_path):
        """The mirror case: a ranked-queue-only item confirmed genuinely
        OPEN via confirm_issue_state() must still be emitted -- confirming
        state is a real check, not a de-facto rejection of every
        non-gh-listed item."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "csa_state_2026-09-01.html").write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":77,"title":"t","paths":["modules/billing/api/webhook.py"]}]'
            "</script>"
        )
        ledger_path = tmp_path / "ledger.json"
        # Ledger co-contributes size_points for the same issue# -- a ranked-
        # queue-only item with no size at all fails size-unknown regardless
        # of open state, which isn't what this test is checking. The
        # ledger's files_touched must match the ranked queue's own `paths`
        # (both genuinely agree on the same file) -- the BLOCKER fix (round
        # 3) correctly drops a ledger size_points that was sized against a
        # DIFFERENT path set than what the ranked queue ends up overwriting
        # `paths` with; that is not what this test exercises.
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 77,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "sized by ledger",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(plans_dir),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert len(payload["items"]) == 1, payload["dropped"]
        assert payload["items"][0]["issue"] == 77

    def test_gh_present_item_never_triggers_a_confirm_call(self, tmp_path):
        """An item gh's OWN open-list already confirmed open must never
        trigger a redundant confirm_issue_state_fn call -- merge_sources()
        already set open=True from genuine gh presence."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [{"number": 88, "size_points": 1, "files_touched": ["modules/billing/api/webhook.py"], "reason": "r"}],
        )
        ready_path = tmp_path / "ready.json"
        calls = []

        def fake_confirm(repo_arg, issue_num):
            calls.append(issue_num)
            return "OPEN", [], None

        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[{"issue": 88, "open": True, "title": "t", "labels": [], "last_comment": None}],
            dirty_paths=set(),
            confirm_issue_state_fn=fake_confirm,
        )
        assert calls == []
        assert len(payload["items"]) == 1

    # --- BLOCKER 4 RED-PROOF: gh unreachable must degrade closed, with an
    # explicit degraded marker, never a silent vacuous pass.

    def test_gh_unreachable_degrades_closed_with_explicit_marker(self, tmp_path):
        """Pre-fix: gh failure returned [] from load_gh_open_issues, which
        was indistinguishable from 'confirmed zero open issues' -- a closed,
        dept-labeled, ruling-blocked item would then pass every gate
        vacuously (labels/last_comment both None/absent) and be emitted as
        ready with an EMPTY dropped[] list. Post-fix: gh unreachable must
        fail every non-gh-confirmed item CLOSED and set a top-level
        degraded:true marker with a reason, so no consumer can mistake this
        run for a clean one.

        MINOR 3 fix (round 3): the per-item dropped reason is now the more
        specific "gh-unreachable" (from resolve_open_state()'s own
        open_state_reason marker), not the generic "closed" -- this item was
        never actually CONFIRMED closed, gh itself could not be reached at
        all, and those are genuinely distinct failure modes a caller/auditor
        must be able to tell apart."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 4901,
                    "size_points": 1,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "closed, dept-labeled, ruling-blocked upstream",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        confirm_calls = []

        def fake_confirm(repo_arg, issue_num):
            # Must NEVER even be called once gh itself is unreachable -- see
            # resolve_open_state()'s own docstring for why burning N more
            # subprocess calls against an already-unreachable gh is pointless.
            confirm_calls.append(issue_num)
            return "OPEN", [], None

        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=([], False),  # (items, reachable) -- simulated gh outage
            dirty_paths=set(),
            confirm_issue_state_fn=fake_confirm,
        )
        assert confirm_calls == []
        assert payload["items"] == []
        assert payload["degraded"] is True
        assert payload["degraded_reason"] == "gh-unreachable"
        assert {"issue": 4901, "reason": "gh-unreachable"} in payload["dropped"]
        # Confirm the marker is actually WRITTEN, not just returned.
        with open(ready_path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        assert on_disk["degraded"] is True

    def test_per_issue_confirm_failure_is_unconfirmable_distinct_from_closed_and_gh_unreachable(
        self, tmp_path
    ):
        """MINOR 3 RED-PROOF: a THIRD distinct failure mode -- gh's own
        open-list call succeeded (gh_reachable=True, so the run is never
        run-wide degraded), but the per-issue `gh issue view` confirm call
        for THIS specific issue itself could not resolve a state (simulates
        a nonzero exit / garbage response for just that one issue). Must be
        reported as "unconfirmable", never collapsed into the generic
        "closed" the way a genuinely CLOSED item is, and never conflated
        with the run-wide "gh-unreachable" reason either -- all three are
        real, distinct signals a caller/auditor must be able to tell apart."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 5001,
                    "size_points": 1,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "confirm call itself fails for this one issue",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"

        def fake_confirm(repo_arg, issue_num):
            # Simulates confirm_issue_state()'s own None/None/None return on
            # an unparseable/garbage per-issue response.
            return None, None, None

        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],  # gh itself IS reachable -- an empty, confirmed list
            dirty_paths=set(),
            confirm_issue_state_fn=fake_confirm,
        )
        assert payload["degraded"] is False
        assert {"issue": 5001, "reason": "unconfirmable"} in payload["dropped"]

    def test_gh_reachable_normal_run_is_never_marked_degraded(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(str(ledger_path), [])
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
        )
        assert payload["degraded"] is False
        assert "degraded_reason" not in payload

    def test_git_status_unreachable_degrades_closed_and_refuses_every_item(self, tmp_path):
        """MINOR 9 RED-PROOF (end-to-end): git status being unreachable must
        degrade the run and refuse EVERY item, even a genuinely valid,
        confirmed-open one -- never silently trust an empty dirty-set that
        might just mean 'couldn't check'."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [{"number": 9001, "size_points": 1, "files_touched": ["modules/billing/api/webhook.py"], "reason": "r"}],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=(set(), False),  # (dirty_paths, reachable) -- git status unreachable
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert payload["items"] == []
        assert payload["degraded"] is True
        assert payload["degraded_reason"] == "git-status-unreachable"
        assert {"issue": 9001, "reason": "dirty-state-unconfirmed"} in payload["dropped"]

    def test_both_gh_and_git_unreachable_reports_both_reasons(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(str(ledger_path), [])
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=([], False),
            dirty_paths=(set(), False),
        )
        assert payload["degraded"] is True
        assert payload["degraded_reason"] == "gh-unreachable+git-status-unreachable"

    # --- FIX-Q7 end-to-end: run()'s own fresh_triage_items thread-through.

    def test_fresh_only_item_reaches_ready_json_once_confirmed_open(self, tmp_path):
        """(a), run()-level: a fresh_triage_items entry with no ledger/gh
        counterpart, once confirm_issue_state_fn resolves it open, reaches
        ready.json with a non-null size_points."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(str(ledger_path), [])
        ready_path = tmp_path / "ready.json"
        fresh = [
            {
                "number": 8101,
                "size_points": 2,
                "files_touched": ["modules/billing/api/webhook.py"],
                "reason": "fresh triage finding",
            }
        ]
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            fresh_triage_items=fresh,
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert len(payload["items"]) == 1
        assert payload["items"][0]["issue"] == 8101
        assert payload["items"][0]["size_points"] == 2

    def test_fresh_triage_items_none_is_a_no_op_matching_pre_fix_behavior(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [{"number": 8102, "size_points": 1, "files_touched": ["modules/billing/api/webhook.py"], "reason": "r"}],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            fresh_triage_items=None,
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert len(payload["items"]) == 1
        assert payload["items"][0]["issue"] == 8102

    # --- FIX-Q4 end-to-end: run()'s own tracker_rel thread-through.

    def test_tracker_rel_none_defaults_every_item_to_tier_2(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [{"number": 8103, "size_points": 1, "files_touched": ["modules/billing/api/webhook.py"], "reason": "r"}],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            tracker_rel=None,
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert payload["items"][0]["tier"] == 2

    def test_tracker_rel_supplied_assigns_real_tier(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        tracker_html = (
            "<html><body><script>const QA_ROWS = "
            '[{"i":"#8104","s":"failed"}];'
            "</script></body></html>"
        )
        (repo / "tracker.html").write_text(tracker_html)
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [{"number": 8104, "size_points": 1, "files_touched": ["modules/billing/api/webhook.py"], "reason": "r"}],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            tracker_rel="tracker.html",
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert payload["items"][0]["tier"] == 0


class TestRankedSourceVisibility:
    """H6 / commit c8 falsifiable test: the ranked-queue path's own
    correctness (repair) AND visibility (the `ranked_source` payload field)
    together. Plan text (H6's "Falsifiable test" subsection):

    RED: with the ranked directory ABSENT (today's real condition --
    `~/.claude/plans/wheel/<slug>/` does not exist yet) and triaged items
    present, assert `degraded` is `false` and nothing names the empty-
    ranking condition. Reproduces today exactly.
    GREEN: snapshot present in the new per-slug path -> real ranks,
    `ranked_count` matches; with the directory still empty/absent ->
    `ranked_source` reports `ranked_count == 0` and a null `matched_file`
    (the field that lets a caller -- issue_wheel.txt's RULE G-RANKED-EMPTY
    -- set `degraded_reason: "ranked-queue-empty"` itself; run() only emits
    the visibility field, it does not itself flip `degraded`, per the
    plan's step 4 and run()'s own docstring).

    Pre-fix, `run()`'s emitted payload carried no `ranked_source` key at
    all (confirmed by diffing this module against HEAD) -- these RED
    assertions (`"ranked_source" not in payload`) are literally true
    against the pre-fix code, not a synthetic stand-in for it.
    """

    def _write_ledger(self, path, entries):
        payload = {"waves": [{"wave": 1, "needs_work": entries}]}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def _repo_with_touchable_file(self, tmp_path, rel_path):
        repo = tmp_path / "repo"
        full = repo / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("x")
        return repo

    def test_red_absent_ranked_dir_with_triaged_items_is_not_degraded_and_silent(self, tmp_path):
        """RED case, verbatim from the plan: ranked directory absent (the
        real ~/.claude/plans/wheel/<slug>/ condition before H6), triaged
        items present. Against the PRE-FIX module this payload carried no
        `ranked_source` key at all and `degraded` never reflected an empty
        ranked queue -- both remain true post-fix too (this is the
        non-regression half): `degraded` must still read `false` here,
        since an empty ranked source alone is never this module's own
        degraded condition (that's RULE G-RANKED-EMPTY's job, evaluated by
        the session outside this function, per the plan's step 4)."""
        repo = self._repo_with_touchable_file(tmp_path, "modules/billing/api/webhook.py")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 700,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "triaged item, no ranked snapshot exists yet",
                }
            ],
        )
        absent_dir = tmp_path / "plans" / "wheel" / "csa"
        assert not absent_dir.exists()  # the genuinely-missing-directory condition, not an empty one
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(absent_dir),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        # Triaged item genuinely made it into the ranked queue's candidate set.
        assert len(payload["items"]) == 1
        assert payload["degraded"] is False
        assert "degraded_reason" not in payload

    def test_green_ranked_source_reports_absent_dir_as_zero_count_null_file(self, tmp_path):
        """GREEN half: the SAME absent-directory scenario as the RED test
        above must now be visible via `ranked_source`, even though
        `degraded` itself is correctly still false (run() emits the signal,
        it does not gate on it -- that is issue_wheel.txt's job)."""
        repo = self._repo_with_touchable_file(tmp_path, "modules/billing/api/webhook.py")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 701,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "triaged item, ranked dir absent",
                }
            ],
        )
        absent_dir = tmp_path / "plans" / "wheel" / "csa"
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(absent_dir),
            ready_path=str(ready_path),
            ranked_glob=sq.DEFAULT_RANKED_GLOB,
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert payload["ranked_source"] == {
            "dir": str(absent_dir),
            "glob": sq.DEFAULT_RANKED_GLOB,
            "matched_file": None,
            "ranked_count": 0,
        }
        # Confirm the field was actually WRITTEN to disk, not just returned.
        with open(ready_path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        assert on_disk["ranked_source"] == payload["ranked_source"]

    def test_green_ranked_source_reports_real_snapshot_matched_file_and_count(self, tmp_path):
        """GREEN half: a real per-slug snapshot present -> `ranked_source`
        names the exact file `load_ranked_queue` itself read and the real
        contributed count -- proving `matched_file`/`ranked_count` are not
        hardcoded placeholders but reflect the actual lookup
        (`_newest_ranked_state_html`), matching `load_ranked_queue`'s own
        internal result rather than a second, possibly-divergent scan."""
        repo = self._repo_with_touchable_file(tmp_path, "modules/billing/api/webhook.py")
        ledger_path = tmp_path / "ledger.json"
        self._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 702,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "triaged item, real ranked snapshot exists",
                }
            ],
        )
        ranked_dir = tmp_path / "plans" / "wheel" / "csa"
        ranked_dir.mkdir(parents=True)
        snapshot = ranked_dir / "csa_state_2026-09-01.html"
        snapshot.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":702,"title":"real","paths":["modules/billing/api/webhook.py"]}]'
            "</script>"
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(ranked_dir),
            ready_path=str(ready_path),
            ranked_glob=sq.DEFAULT_RANKED_GLOB,
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo_arg, num: ("OPEN", [], None),
        )
        assert payload["ranked_source"]["matched_file"] == str(snapshot)
        assert payload["ranked_source"]["ranked_count"] == 1
        assert payload["ranked_source"]["dir"] == str(ranked_dir)
        assert payload["ranked_source"]["glob"] == sq.DEFAULT_RANKED_GLOB
        assert payload["degraded"] is False

    def test_glob_red_undated_backup_file_would_be_picked_by_old_undated_glob(self):
        """Glob RED/GREEN, verbatim from the plan: `csa_state_backup.html`
        alongside a dated file -> RED (today's pre-fix plist glob,
        `csa_state_*.html`) picks `backup` (sorts after the dated name
        lexicographically), GREEN (the aligned dated glob now shipped in
        both wheel plists) picks the dated file instead. This proves the
        actual OLD plist value (still readable from git history / the diff)
        was genuinely vulnerable, not a strawman pattern nobody shipped."""
        old_undated_glob = "csa_state_*.html"
        names = ["csa_state_2026-09-01.html", "csa_state_backup.html"]
        names.sort()  # matches _newest_ranked_state_html's own lexicographic pick of candidates[-1]
        matched_under_old = [n for n in names if fnmatch.fnmatch(n, old_undated_glob)]
        assert matched_under_old[-1] == "csa_state_backup.html", (
            "RED: the pre-fix undated glob must wrongly prefer the non-dated backup file "
            "as 'newest' -- reproduces the real bug this commit closes"
        )

    def test_glob_green_aligned_dated_glob_rejects_backup_file_and_picks_dated_snapshot(self, tmp_path):
        """GREEN counterpart, exercised through the real `load_ranked_queue`
        entry point (not just fnmatch in isolation) with the exact aligned
        glob now shipped in `com.oversight.wheel.csa.plist`
        (`WHEEL_RANKED_GLOB`), confirming the fix actually closes the RED
        case above end-to-end."""
        aligned_glob = "csa_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"
        assert aligned_glob == sq.DEFAULT_RANKED_GLOB  # the plist now matches the module default exactly
        dated = tmp_path / "csa_state_2026-09-01.html"
        dated.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":9,"title":"real","paths":["a.py"]}]</script>'
        )
        backup = tmp_path / "csa_state_backup.html"
        backup.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":999,"title":"WRONG","paths":["z.py"]}]</script>'
        )
        result = sq.load_ranked_queue(str(tmp_path), aligned_glob)
        assert len(result) == 1
        assert result[0]["issue"] == 9

    def test_agency_plist_glob_is_agency_shaped_not_csa_shaped(self):
        """H6 step 3 / review risk R1: each plist's `WHEEL_RANKED_GLOB` must
        be aligned to its OWN slug's dated filename shape -- Agency's plist
        must NOT be pointed at CSA's `csa_state_*` pattern (rev 3's own
        text bug this commit's design corrects). Read directly from the
        real on-disk agency plist so a future accidental copy-paste of
        CSA's glob into Agency's plist is caught.

        Path resolution uses `_lib.CLAUDE_DIR` (the module's own canonical
        runtime-root constant) rather than `dirname(dirname(__file__))` --
        nit 6: the latter is fragile to a test-file relocation (it silently
        recomputes a DIFFERENT wrong path instead of failing loudly), and
        skips (rather than hard-fails) when the plist is genuinely absent,
        so a real layout change reads as skipped, not a false test failure
        unrelated to this test's own subject."""
        import pytest

        agency_plist_path = os.path.join(_lib.CLAUDE_DIR, "schedules", "com.oversight.wheel.agency.plist")
        if not os.path.isfile(agency_plist_path):
            pytest.skip(f"com.oversight.wheel.agency.plist not found at {agency_plist_path}")
        with open(agency_plist_path, encoding="utf-8") as fh:
            content = fh.read()
        m = re.search(r"<key>WHEEL_RANKED_GLOB</key>\s*<string>([^<]+)</string>", content)
        assert m, "WHEEL_RANKED_GLOB not found in com.oversight.wheel.agency.plist"
        agency_glob = m.group(1)
        assert agency_glob == "agency_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"
        assert not agency_glob.startswith("csa_state_"), (
            "RED: rev 3's bug pointed Agency's plist at CSA's own dated glob shape, "
            "which would never match any agency_state_*.html snapshot"
        )

    def test_csa_plist_glob_matches_module_default_exactly(self):
        """H6 step 3: CSA's plist glob must match `DEFAULT_RANKED_GLOB`
        byte-for-byte (not merely 'a dated pattern') -- read directly from
        the real on-disk CSA plist.

        Path resolution uses `_lib.CLAUDE_DIR` (see the Agency test above
        for the full nit-6 rationale) with a `pytest.skip` when the plist is
        genuinely absent, rather than `dirname(dirname(__file__))`."""
        import pytest

        csa_plist_path = os.path.join(_lib.CLAUDE_DIR, "schedules", "com.oversight.wheel.csa.plist")
        if not os.path.isfile(csa_plist_path):
            pytest.skip(f"com.oversight.wheel.csa.plist not found at {csa_plist_path}")
        with open(csa_plist_path, encoding="utf-8") as fh:
            content = fh.read()
        m = re.search(r"<key>WHEEL_RANKED_GLOB</key>\s*<string>([^<]+)</string>", content)
        assert m, "WHEEL_RANKED_GLOB not found in com.oversight.wheel.csa.plist"
        assert m.group(1) == sq.DEFAULT_RANKED_GLOB


class TestCliFreshTriageEndToEnd:
    """FIX-Q7 gap G1: feed a VERBATIM P1 needs_work[] record (P1's own raw
    field-shape, unmodified) through the documented --fresh-triage CLI flag
    into run(), asserting a non-null size_points reaches ready.json. Hand-
    built fixtures at the merge_sources/run() level would all pass even
    against a wrong field-shape blocker; only a CLI-level, verbatim-schema
    test catches that class."""

    def test_verbatim_p1_needs_work_record_through_cli_flag_reaches_ready_json(self, tmp_path):
        """CLI-boundary proof only: `--fresh-triage <path>` genuinely reads
        the file and threads its (verbatim, untranslated) content into
        `run()`'s `merge_sources()` call, reaching the emitted payload as
        SOME record for issue 8105 (in `items` or `dropped` -- this
        subprocess has no real `gh`/git to confirm the issue open, so it
        cannot honestly go further than merge/dropped-reason visibility).

        code-reviewer finding: an EARLIER version of this docstring claimed
        this test proves `size_points` survives the full thread-through, but
        the assertion below only ever checked membership -- and this
        subprocess environment cannot actually reach that assertion
        honestly (no real `gh`, so the item is dropped `unconfirmable`
        before ever reaching `apply_valid_predicate`'s `size_points` check).
        The GENUINE `size_points`-survival proof, at the level where it CAN
        be asserted (via `confirm_issue_state_fn` injection, which this
        subprocess-based CLI test structurally cannot do), lives in
        `TestMergeSourcesFreshTriageUnion.test_fresh_only_item_reaches_
        ready_json_once_confirmed_open` above -- that test is `run()`-level,
        not CLI-level, specifically so it CAN inject a fake confirmation.
        """
        import subprocess

        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")

        # P1's OWN raw needs_work[] record shape, verbatim -- number /
        # files_touched / size_points / reason / lane_hint, never
        # pre-translated to this module's internal issue/paths/title shape.
        fresh_triage_path = tmp_path / "fresh_triage.json"
        fresh_triage_path.write_text(
            json.dumps(
                [
                    {
                        "number": 8105,
                        "files_touched": ["modules/billing/api/webhook.py"],
                        "size_points": 1,
                        "reason": "verbatim P1 needs_work record",
                        "lane_hint": "billing",
                    }
                ]
            )
        )

        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--tracker-rel",
                "nonexistent_tracker.html",
                "--fresh-triage",
                str(fresh_triage_path),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        seen = {d.get("issue"): d for d in payload.get("dropped", [])}
        seen.update({it.get("issue"): it for it in payload.get("items", [])})
        assert 8105 in seen

    def _run_cli_with_fresh_triage(self, tmp_path, fresh_triage_arg, out_path=None):
        """Shared CLI-invocation helper for the two fail-loud tests below --
        never writes an --out path unless the caller wants to check it
        stays absent."""
        import subprocess

        repo = tmp_path / "repo"
        (repo / "modules").mkdir(parents=True)
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        args = [
            sys.executable,
            os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
            "run",
            "--repo",
            str(repo),
            "--slug",
            "testslug",
            "--tracker-rel",
            "nonexistent_tracker.html",
            "--fresh-triage",
            fresh_triage_arg,
        ]
        if out_path is not None:
            args += ["--out", str(out_path)]
        else:
            env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        return subprocess.run(args, capture_output=True, text=True, env=env, timeout=15)

    def test_fresh_triage_missing_file_fails_loud_exit_2_no_output_written(self, tmp_path):
        """code-reviewer round-2 blocker: the --fresh-triage fail-open fix
        (a missing/corrupt file must exit 2, never exit 0 with a STALE
        ready.json left in place) shipped with NO test proving it -- a
        scratch-copy revert of just the try/except guard left this suite
        fully GREEN, meaning the fix's absence was undetectable. The
        returncode assertion below is the LOAD-BEARING one for THAT specific
        regression (confirmed: reverting the guard makes returncode go
        0->2, RED). The stale-output assertion is defense-in-depth for a
        DIFFERENT regression class (code-reviewer round 3, cold pass) -- a
        guard that fires AFTER run() rather than before would still exit
        non-zero but could leave a partially-written --out; this assertion
        would catch that shape even though it adds no power against the
        specific revert this test was written to catch."""
        out_path = tmp_path / "out.json"
        # Pre-seed a stale file at --out; see the docstring above for what
        # this assertion does and does not add detection power against.
        stale_marker = json.dumps({"stale": True})
        out_path.write_text(stale_marker)

        proc = self._run_cli_with_fresh_triage(
            tmp_path, str(tmp_path / "nonexistent_fresh_triage.json"), out_path=out_path
        )

        assert proc.returncode == 2, proc.stderr
        assert "--fresh-triage" in proc.stderr
        # The pre-existing stale file must survive UNCHANGED -- a rewritten
        # (even if empty) --out would still be evidence of a partial run.
        assert out_path.read_text() == stale_marker

    def test_fresh_triage_malformed_json_fails_loud_exit_2_no_output_written(self, tmp_path):
        """Sibling of the missing-file case: malformed JSON must fail the
        same way, not merely propagate an unhandled traceback or silently
        treat the file as empty."""
        out_path = tmp_path / "out.json"
        stale_marker = json.dumps({"stale": True})
        out_path.write_text(stale_marker)

        bad_json_path = tmp_path / "malformed_fresh_triage.json"
        bad_json_path.write_text("{not valid json")

        proc = self._run_cli_with_fresh_triage(tmp_path, str(bad_json_path), out_path=out_path)

        assert proc.returncode == 2, proc.stderr
        assert "--fresh-triage" in proc.stderr
        assert out_path.read_text() == stale_marker


# ===========================================================================
# Loaders — parsing logic against fabricated input (no real subprocess/gh).
# ===========================================================================


class TestLoadLedgerNeedsWork:
    def test_picks_the_highest_numbered_wave_with_needs_work(self, tmp_path):
        path = tmp_path / "ledger.json"
        payload = {
            "waves": [
                {"wave": 1, "needs_work": [{"number": 1, "size_points": 1, "files_touched": [], "reason": "old"}]},
                {"wave": 2},  # no needs_work key at all -- must be skipped, not crash
                {"wave": 3, "needs_work": [{"number": 2, "size_points": 1, "files_touched": [], "reason": "new"}]},
            ]
        }
        path.write_text(json.dumps(payload))
        result = sq.load_ledger_needs_work(str(path))
        assert len(result) == 1
        assert result[0]["issue"] == 2

    def test_missing_file_returns_empty(self, tmp_path):
        assert sq.load_ledger_needs_work(str(tmp_path / "nope.json")) == []

    def test_malformed_json_returns_empty(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        assert sq.load_ledger_needs_work(str(path)) == []

    def test_entries_never_carry_a_dead_open_field(self, tmp_path):
        """NIT 5 RED-PROOF: a ledger entry must not emit a hardcoded
        "open": True field -- nothing downstream (merge_sources' own ledger
        loop) ever reads it, and a real open/closed determination is made
        exclusively via confirm_issue_state(), never this hardcoded value."""
        path = tmp_path / "ledger.json"
        payload = {
            "waves": [
                {"wave": 1, "needs_work": [{"number": 1, "size_points": 1, "files_touched": [], "reason": "r"}]},
            ]
        }
        path.write_text(json.dumps(payload))
        result = sq.load_ledger_needs_work(str(path))
        assert len(result) == 1
        assert "open" not in result[0]


class TestFixQ1LedgerRelDefault:
    """FIX-Q1: the CSA-shaped join in main()'s `run` sub-command becomes
    os.path.join(repo, ledger_rel) from --ledger-rel, default byte-identical
    to CSA's historical hardcoded path."""

    def test_default_ledger_rel_matches_historical_csa_hardcoded_path(self):
        assert sq.DEFAULT_LEDGER_REL == os.path.join(
            "_Config_Project", "docs", "domain", "issue_burndown_ledger.json"
        )

    def test_default_ledger_rel_joined_with_repo_reproduces_old_hardcode(self, tmp_path):
        repo = str(tmp_path)
        old_hardcoded = os.path.join(repo, "_Config_Project", "docs", "domain", "issue_burndown_ledger.json")
        new_composed = os.path.join(repo, sq.DEFAULT_LEDGER_REL)
        assert old_hardcoded == new_composed


class TestLoadRankedQueue:
    def test_picks_newest_dated_html_and_parses_script_tag(self, tmp_path):
        older = tmp_path / "csa_state_2026-08-01.html"
        newer = tmp_path / "csa_state_2026-09-01.html"
        older.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":1,"title":"old","paths":["a.py"]}]</script>'
        )
        newer.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":2,"title":"new","paths":["b.py"]}]</script>'
        )
        result = sq.load_ranked_queue(str(tmp_path))
        assert len(result) == 1
        assert result[0]["issue"] == 2

    def test_missing_dir_returns_empty(self, tmp_path):
        assert sq.load_ranked_queue(str(tmp_path / "nope")) == []

    def test_missing_script_tag_returns_empty(self, tmp_path):
        path = tmp_path / "csa_state_2026-09-01.html"
        path.write_text("<html><body>no queue here</body></html>")
        assert sq.load_ranked_queue(str(tmp_path)) == []

    # --- FIX-Q2 RED-PROOF: --ranked-glob replaces the old literal
    # ^csa_state_\d{4}-\d{2}-\d{2}\.html$ regex with an fnmatch-based glob
    # pattern, and load_ranked_queue reads from a repo-scoped subdirectory.

    def test_ranked_glob_default_is_byte_identical_to_old_csa_pattern(self, tmp_path):
        """Omitting glob_pattern must select exactly the files the old
        hardcoded regex `^csa_state_\\d{4}-\\d{2}-\\d{2}\\.html$` would have
        selected -- code-reviewer blocker: the original test used only a
        negative fixture that fails BOTH the old regex and a too-loose
        `csa_state_*.html` default identically, so it had zero power to
        detect the actual divergence (a bare `*` wildcard also matches a
        non-date name). This version adds a REAL divergent fixture: a
        non-date `csa_state_*.html` name that sorts AFTER the real dated
        snapshot lexicographically, proving the default is genuinely
        date-anchored, not merely prefix-anchored."""
        dated = tmp_path / "csa_state_2026-09-01.html"
        dated.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":9,"title":"t","paths":["a.py"]}]</script>'
        )
        # Not matching the old CSA regex shape at all -- must NOT be picked.
        (tmp_path / "not_a_csa_state_file.html").write_text("garbage")
        # Sorts AFTER "csa_state_2026-09-01.html" lexicographically (a "d"
        # > any digit), so a too-loose glob would silently pick THIS one as
        # "newest" instead of the real dated snapshot.
        (tmp_path / "csa_state_draft.html").write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":999,"title":"WRONG","paths":["z.py"]}]</script>'
        )
        result = sq.load_ranked_queue(str(tmp_path))
        assert len(result) == 1
        assert result[0]["issue"] == 9

    def test_ranked_glob_default_rejects_non_date_csa_state_filenames(self):
        """Direct unit-level proof, independent of load_ranked_queue's file
        I/O, that the default glob is genuinely date-anchored (not a bare
        `*`) -- each of these is a REAL divergence code-reviewer round 1
        demonstrated between fnmatch(*, ...) and the old regex."""
        for bad_name in (
            "csa_state_draft.html",
            "csa_state_backup.html",
            "csa_state_2026-09-07-old.html",
            "csa_state_2026-9-7.html",
        ):
            assert not fnmatch.fnmatch(bad_name, sq.DEFAULT_RANKED_GLOB), bad_name
        assert fnmatch.fnmatch("csa_state_2026-09-07.html", sq.DEFAULT_RANKED_GLOB)

    def test_custom_ranked_glob_selects_a_non_csa_naming_convention(self, tmp_path):
        """A repo-scoped glob (e.g. Agency's own naming) must be usable
        instead of CSA's hardcoded pattern -- the fnmatch conversion must
        not silently only work for the CSA shape."""
        csa_shaped = tmp_path / "csa_state_2026-09-01.html"
        csa_shaped.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":1,"title":"csa","paths":["a.py"]}]</script>'
        )
        agency_shaped = tmp_path / "agency_state_2026-09-01.html"
        agency_shaped.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":2,"title":"agency","paths":["b.py"]}]</script>'
        )
        result = sq.load_ranked_queue(str(tmp_path), "agency_state_*.html")
        assert len(result) == 1
        assert result[0]["issue"] == 2

    def test_ranked_glob_picks_newest_among_matching_files_only(self, tmp_path):
        older = tmp_path / "custom_state_2026-08-01.html"
        newer = tmp_path / "custom_state_2026-09-01.html"
        non_matching_newest = tmp_path / "zzz_unrelated.html"
        older.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":1,"title":"old","paths":["a.py"]}]</script>'
        )
        newer.write_text(
            '<script type="application/json" id="oversight-ranked-queue">'
            '[{"rank":1,"issue":2,"title":"new","paths":["b.py"]}]</script>'
        )
        non_matching_newest.write_text("should never be selected")
        result = sq.load_ranked_queue(str(tmp_path), "custom_state_*.html")
        assert len(result) == 1
        assert result[0]["issue"] == 2

    def test_repo_scoped_subdirectory_that_does_not_exist_yet_returns_empty_never_raises(self, tmp_path):
        """FIX-Q2: a `~/.claude/plans/wheel/<slug>/` subdirectory need not
        exist yet -- a missing directory must behave like today's 'no
        ranked queue found', never raise."""
        missing = tmp_path / "plans" / "wheel" / "brand-new-slug"
        assert not missing.exists()
        assert sq.load_ranked_queue(str(missing)) == []


class TestExtractQaRowsText:
    def test_extracts_balanced_array_ignoring_nested_bracket_shaped_strings(self):
        html = (
            'prefix <script>x</script> const QA_ROWS = ['
            '{"c":"a","i":"#1","s":"deployed","note":"contains a ]; substring"},'
            '{"c":"b","i":"#2","s":"local"}'
            ']; more html after'
        )
        result = sq._extract_qa_rows_text(html)
        assert result is not None
        assert result.startswith("[") and result.endswith("]")
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_missing_literal_returns_none(self):
        assert sq._extract_qa_rows_text("<html>no rows here</html>") is None

    def test_unterminated_array_returns_none(self):
        assert sq._extract_qa_rows_text('const QA_ROWS = [{"c":"a"') is None


class TestStripHtmlCommentsOutsideStrings:
    def test_strips_comment_between_elements(self):
        text = '[{"a":1}, <!-- a real html comment --> {"a":2}]'
        stripped = sq._strip_html_comments_outside_strings(text)
        assert "<!--" not in stripped
        parsed = json.loads(stripped)
        assert len(parsed) == 2

    def test_never_strips_comment_shaped_substring_inside_a_string(self):
        text = '[{"note": "looks like <!-- a comment --> but is real data"}]'
        stripped = sq._strip_html_comments_outside_strings(text)
        parsed = json.loads(stripped)
        assert parsed[0]["note"] == "looks like <!-- a comment --> but is real data"

    def test_unterminated_comment_stops_cleanly(self):
        text = '[{"a":1}, <!-- never closes'
        # Must not raise -- the malformed trailer is simply dropped.
        stripped = sq._strip_html_comments_outside_strings(text)
        assert stripped.startswith('[{"a":1}, ')


class TestLoadTrackerTiers:
    """FIX-Q4 Part A: the load_tracker_tiers() loader.

    The two tests that read the REAL ExampleApp tracker
    (`launch_readiness.html`) were REMOVED 2026-09-20: that file was deleted
    on 2026-09-16 by operator directive (launch readiness moved to GitHub
    issues) and the wheel's `--tracker-rel` input was retired with it, so
    there is no live file to re-derive against. They had been failing ever
    since. The loader's semantics stay proven by the synthetic-fixture tests
    below; the Agency real-file test remains and skips when that repo is
    absent. The retirement's own contract -- a missing tracker degrades to
    `{}` rather than raising -- is pinned here instead."""

    AGENCY_TRACKER = "/Users/x/Desktop/OtherApp/plans/launch-plan.html"

    def test_missing_tracker_file_degrades_to_empty_not_raise(self, tmp_path):
        assert sq.load_tracker_tiers(str(tmp_path), "no_such_tracker.html") == {}

    def test_parses_real_agency_tracker_without_raising(self):
        if not os.path.exists(self.AGENCY_TRACKER):
            import pytest

            pytest.skip("OtherApp repo not present on this machine")
        repo, rel = os.path.split(self.AGENCY_TRACKER)
        tiers = sq.load_tracker_tiers(repo, rel)
        assert isinstance(tiers, dict)
        assert len(tiers) > 0

    # --- Synthetic-fixture unit tests for the tiering/collision rules
    # themselves (the two real-file tests above prove the loader survives
    # real-world data; these prove the exact tiering semantics).

    def _write_tracker(self, tmp_path, rows):
        html = "<html><body><script>const QA_ROWS = " + json.dumps(rows) + ";</script></body></html>"
        path = tmp_path / "tracker.html"
        path.write_text(html)
        return path

    def test_failed_blocked_notstarted_are_tier_0(self, tmp_path):
        rows = [
            {"i": "#1", "s": "failed"},
            {"i": "#2", "s": "blocked"},
            {"i": "#3", "s": "notstarted"},
        ]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {1: 0, 2: 0, 3: 0}

    def test_local_is_tier_1(self, tmp_path):
        rows = [{"i": "#5", "s": "local"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {5: 1}

    def test_deployed_is_tier_2_not_tier_1(self, tmp_path):
        """FIX-Q5 RED-PROOF: deployed is deliberately tier 2."""
        rows = [{"i": "#6", "s": "deployed"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {6: 2}

    def test_unknown_status_defaults_to_tier_2(self, tmp_path):
        rows = [{"i": "#7", "s": "onstaging"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {7: 2}

    def test_multiple_issue_refs_in_one_row_all_extracted(self, tmp_path):
        rows = [{"i": "#100, #101 #102", "s": "failed"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {100: 0, 101: 0, 102: 0}

    def test_collision_takes_the_lower_more_urgent_tier(self, tmp_path):
        rows = [
            {"i": "#1", "s": "deployed"},   # tier 2
            {"i": "#1", "s": "failed"},     # tier 0 -- must win
        ]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {1: 0}

    def test_row_with_no_i_field_contributes_nothing(self, tmp_path):
        rows = [{"s": "failed"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {}

    def test_row_with_no_hash_number_in_i_field_contributes_nothing(self, tmp_path):
        rows = [{"i": "no-id", "s": "failed"}]
        self._write_tracker(tmp_path, rows)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {}

    def test_missing_file_fails_soft_to_empty_dict(self, tmp_path):
        tiers = sq.load_tracker_tiers(str(tmp_path), "does_not_exist.html")
        assert tiers == {}

    def test_missing_qa_rows_literal_fails_soft_to_empty_dict(self, tmp_path):
        path = tmp_path / "tracker.html"
        path.write_text("<html><body>no QA_ROWS here</body></html>")
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {}

    def test_malformed_json_fails_soft_to_empty_dict(self, tmp_path):
        path = tmp_path / "tracker.html"
        path.write_text("<html><script>const QA_ROWS = [{not json];</script></html>")
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {}

    def test_html_comment_between_array_elements_is_stripped_and_parses(self, tmp_path):
        """Mirrors the real Agency-file defect this loader must survive."""
        html = (
            "<html><body><script>const QA_ROWS = ["
            '{"i":"#1","s":"failed"},'
            "<!-- an html comment between elements -->"
            '{"i":"#2","s":"local"}'
            "];</script></body></html>"
        )
        path = tmp_path / "tracker.html"
        path.write_text(html)
        tiers = sq.load_tracker_tiers(str(tmp_path), "tracker.html")
        assert tiers == {1: 0, 2: 1}


class TestLoadDirtyPaths:
    def test_parses_porcelain_z_output(self, monkeypatch, tmp_path):
        def fake_run(cmd, cwd=None, timeout=30.0):
            return "M  a.py\x00?? b.py\x00", True

        monkeypatch.setattr(sq, "_run", fake_run)
        dirty, reachable = sq.load_dirty_paths(str(tmp_path))
        assert dirty == {"a.py", "b.py"}
        assert reachable is True

    def test_git_unavailable_returns_empty_set_and_unreachable(self, monkeypatch, tmp_path):
        """MINOR 9 RED-PROOF: git status could not be run at all -- must
        report reachable=False (never silently "nothing is dirty"), so the
        caller (run()) can fail the whole run closed rather than trust an
        empty dirty-set that might just mean 'couldn't check'."""
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, False))
        dirty, reachable = sq.load_dirty_paths(str(tmp_path))
        assert dirty == set()
        assert reachable is False

    def test_git_nonzero_exit_also_reports_unreachable(self, monkeypatch, tmp_path):
        """A launched-but-failed git status (not a repo, corrupt index) is
        equally untrustworthy -- also reachable=False, not just a launch
        failure."""
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, True))
        dirty, reachable = sq.load_dirty_paths(str(tmp_path))
        assert dirty == set()
        assert reachable is False

    def test_rename_record_captures_both_old_and_new_path(self, monkeypatch, tmp_path):
        def fake_run(cmd, cwd=None, timeout=30.0):
            return "R  old.py\x00new.py\x00", True

        monkeypatch.setattr(sq, "_run", fake_run)
        dirty, reachable = sq.load_dirty_paths(str(tmp_path))
        assert dirty == {"old.py", "new.py"}
        assert reachable is True


class TestLoadGhOpenIssues:
    def test_parses_gh_json_output(self, monkeypatch, tmp_path):
        gh_output = json.dumps(
            [
                {
                    "number": 42,
                    "title": "a real issue",
                    "labels": [{"name": "bug"}],
                    "comments": [{"body": "first"}, {"body": "last one"}],
                }
            ]
        )
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (gh_output, True))
        result, reachable = sq.load_gh_open_issues(str(tmp_path))
        assert reachable is True
        assert len(result) == 1
        assert result[0]["issue"] == 42
        assert result[0]["labels"] == ["bug"]
        assert result[0]["last_comment"] == "last one"

    def test_gh_failure_returns_empty_but_still_reachable(self, monkeypatch, tmp_path):
        """A nonzero exit / empty stdout means gh ran and genuinely reported
        nothing (or errored in a way the process itself could report) --
        distinct from BLOCKER 4's unreachable case below."""
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, True))
        result, reachable = sq.load_gh_open_issues(str(tmp_path))
        assert result == []
        assert reachable is True

    def test_gh_unreachable_returns_empty_and_unreachable(self, monkeypatch, tmp_path):
        """BLOCKER 4 RED-PROOF (unit level): gh could not even be launched
        (binary missing, timeout, permission error) -- reachable must be
        False, distinct from a confirmed-empty response."""
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, False))
        result, reachable = sq.load_gh_open_issues(str(tmp_path))
        assert result == []
        assert reachable is False

    def test_no_comments_yields_none_last_comment(self, monkeypatch, tmp_path):
        gh_output = json.dumps([{"number": 1, "title": "t", "labels": [], "comments": []}])
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (gh_output, True))
        result, _reachable = sq.load_gh_open_issues(str(tmp_path))
        assert result[0]["last_comment"] is None


class TestConfirmIssueState:
    def test_confirmed_open(self, monkeypatch, tmp_path):
        out = json.dumps({"state": "OPEN", "labels": [{"name": "bug"}], "comments": [{"body": "last"}]})
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (out, True))
        assert sq.confirm_issue_state(str(tmp_path), 42) == ("OPEN", ["bug"], "last")

    def test_confirmed_closed(self, monkeypatch, tmp_path):
        out = json.dumps({"state": "CLOSED", "labels": [], "comments": []})
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (out, True))
        assert sq.confirm_issue_state(str(tmp_path), 9) == ("CLOSED", [], None)

    def test_unreachable_is_unconfirmable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, False))
        assert sq.confirm_issue_state(str(tmp_path), 9) == (None, None, None)

    def test_nonzero_exit_is_unconfirmable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (None, True))
        assert sq.confirm_issue_state(str(tmp_path), 9) == (None, None, None)

    def test_garbage_output_is_unconfirmable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: ("nonsense\n", True))
        assert sq.confirm_issue_state(str(tmp_path), 9) == (None, None, None)

    def test_missing_state_field_is_unconfirmable(self, monkeypatch, tmp_path):
        out = json.dumps({"labels": [], "comments": []})
        monkeypatch.setattr(sq, "_run", lambda cmd, cwd=None, timeout=30.0: (out, True))
        assert sq.confirm_issue_state(str(tmp_path), 9) == (None, None, None)

    def test_fetches_state_labels_and_comments_in_one_call(self, monkeypatch, tmp_path):
        """MINOR 2 RED-PROOF (unit level): the real gh call must request
        state, labels, AND comments together -- pre-fix it requested only
        `--json state`, so labels/comments were never available to populate
        onto a ledger/ranked-only confirmed item."""
        seen_cmds = []

        def fake_run(cmd, cwd=None, timeout=30.0):
            seen_cmds.append(cmd)
            return json.dumps({"state": "OPEN", "labels": [], "comments": []}), True

        monkeypatch.setattr(sq, "_run", fake_run)
        sq.confirm_issue_state(str(tmp_path), 9)
        assert len(seen_cmds) == 1
        cmd = seen_cmds[0]
        assert "--json" in cmd
        json_arg = cmd[cmd.index("--json") + 1]
        assert "state" in json_arg and "labels" in json_arg and "comments" in json_arg


# ===========================================================================
# CLI smoke test (subprocess, mirrors file_claims.py's own CLI test style).
# ===========================================================================


class TestCli:
    def test_status_with_no_ready_file_prints_empty_dict(self, tmp_path, monkeypatch):
        import subprocess

        env = dict(os.environ)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [sys.executable, os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"), "status"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0
        assert json.loads(proc.stdout) == {}

    def test_run_without_repo_flag_or_env_refuses_with_clear_message(self, tmp_path):
        """NIT 13 RED-PROOF (carried forward from sdw_queue.py): no baked-in
        DEFAULT_REPO -- `run` with neither --repo nor CSA_SDW_REPO set must
        refuse outright with a clear message, never silently fall back to
        any hardcoded product-repo path. `--slug`/`--tracker-rel` are now
        argparse-required flags (FIX-Q2/Q4) and must be supplied so the run
        reaches the repo check at all, rather than failing on argparse's own
        generic missing-required-argument error first."""
        import subprocess

        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--slug",
                "testslug",
                "--tracker-rel",
                "tracker.html",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 2
        assert "no repo specified" in proc.stderr

    def test_run_with_repo_flag_succeeds_without_env_var(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--tracker-rel",
                "tracker.html",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["repo"] == str(repo)

    def test_run_ledger_rel_flag_defaults_to_byte_identical_csa_path(self, tmp_path):
        """FIX-Q1 RED-PROOF: omitting --ledger-rel must resolve to the exact
        same historical CSA-shaped ledger path as before this commit."""
        assert sq.DEFAULT_LEDGER_REL == os.path.join(
            "_Config_Project", "docs", "domain", "issue_burndown_ledger.json"
        )

    def test_run_accepts_all_six_new_flags_and_threads_ledger_rel(self, tmp_path):
        """Structural CLI smoke test: every one of the six new flags is
        accepted (no argparse rejection), and a non-default --ledger-rel
        genuinely changes which ledger file is read (proving main() threads
        the flag through to run(), not just accepting-and-ignoring it)."""
        import subprocess

        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        custom_ledger_dir = repo / "custom"
        custom_ledger_dir.mkdir()
        (custom_ledger_dir / "ledger.json").write_text(
            json.dumps(
                {
                    "waves": [
                        {
                            "wave": 1,
                            "needs_work": [
                                {
                                    "number": 7001,
                                    "size_points": 1,
                                    "files_touched": ["modules/billing/api/webhook.py"],
                                    "reason": "via custom ledger-rel",
                                }
                            ],
                        }
                    ]
                }
            )
        )
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--ledger-rel",
                "custom/ledger.json",
                "--tracker-rel",
                "nonexistent_tracker.html",
                "--ranked-glob",
                "custom_state_*.html",
                "--out",
                str(tmp_path / "custom_out.json"),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        # This is a smoke-level presence check (--repo isn't gh/git-mocked
        # here, so the item may or may not survive apply_valid_predicate's
        # dirty-path/gh-confirmation legs) -- what it actually proves is
        # that --ledger-rel was READ from the custom path at all (the
        # default path doesn't exist under `repo`, so item 7001 could only
        # appear here via the custom path being genuinely threaded through).
        assert os.path.exists(tmp_path / "custom_out.json")
        seen_issue_nums = {d.get("issue") for d in payload.get("dropped", [])} | {
            it.get("issue") for it in payload.get("items", [])
        }
        assert 7001 in seen_issue_nums

    def test_run_tracker_rel_is_optional_and_logs_tracker_disabled(self, tmp_path):
        """THE ISSUE WHEEL plan, Phase C item 4: --tracker-rel was
        `required=True`; the tracker HTML it pointed at (launch_readiness.html
        / launch-plan.html) was deleted 2026-09-16, and load_tracker_tiers()
        was already failing soft to {} on every real run. Omitting the flag
        entirely must run successfully (never an argparse "the following
        arguments are required" error) and must log tracker-disabled to
        stderr exactly once."""
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["repo"] == str(repo)
        assert proc.stderr.count("tracker-disabled") == 1
        assert "--tracker-rel" in proc.stderr

    def test_run_tracker_rel_still_accepted_when_supplied(self, tmp_path):
        """Paired recovery/regression test for the flag above: supplying
        --tracker-rel must behave exactly as before (no tracker-disabled log
        line, run still succeeds) -- optionality must not have broken the
        supplied-value path."""
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--tracker-rel",
                "tracker.html",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["repo"] == str(repo)
        assert "tracker-disabled" not in proc.stderr


# ===========================================================================
# Issue-exclusion mechanism
# (plan_wheel_exclusion_and_quiescence_2026_09_13.md, Finding 1 + the
# Rollout/verification expanded test list, items (a)-(d)). Three additive
# changes under test:
#   1. "wheel:hold" added to EXCLUDED_LABELS_EXACT (pure data, exercised
#      through the EXISTING _has_excluded_label / apply_valid_predicate /
#      run() code paths -- no new code required for this one).
#   2. A new `exclude_issues: set[int] | None = None` parameter on run(),
#      dropping any candidate whose `issue` is in that set with
#      dropped_log reason f"env-excluded:{item['issue']}".
#   3. A new `--exclude-issues` CLI flag on the `run` sub-command
#      (comma-separated issue numbers), parsed into a set of ints (or None
#      when unset/empty) and threaded through to run().
# ===========================================================================


class TestWheelHoldLabelExclusion:
    """(a): "wheel:hold" is dropped via the EXISTING _has_excluded_label
    gate, mirroring the existing operator-only/needs-ruling coverage above
    (TestExcludedLabels, TestApplyValidPredicate.test_excluded_label_is_invalid)
    with the new label value. This label is pure data on
    EXCLUDED_LABELS_EXACT -- it must be provable through the SAME code
    paths already used for "operator-only", with none of the new
    exclude_issues/CLI plumbing involved at all.
    """

    def test_wheel_hold_is_in_the_excluded_labels_tuple(self):
        # Direct data-shape assertion: the new label is genuinely registered,
        # not merely handled by some other code path that happens to also
        # reject it.
        assert "wheel:hold" in sq.EXCLUDED_LABELS_EXACT

    def test_has_excluded_label_flags_wheel_hold(self):
        assert sq._has_excluded_label(["wheel:hold"]) == "wheel:hold"

    def test_has_excluded_label_flags_wheel_hold_case_insensitively(self):
        assert sq._has_excluded_label(["Wheel:Hold"]) == "Wheel:Hold"

    def test_wheel_hold_alongside_ordinary_labels_still_flags(self):
        assert sq._has_excluded_label(["bug", "wheel:hold", "area:billing"]) == "wheel:hold"

    def test_apply_valid_predicate_rejects_wheel_hold_labeled_item(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        item = {
            "issue": 100,
            "open": True,
            "title": "sample",
            "labels": ["wheel:hold"],
            "last_comment": None,
            "paths": ["a.py"],
            "size_points": 2,
        }
        ok, reason, _ = sq.apply_valid_predicate(item, repo=str(tmp_path), dirty_paths=set())
        assert not ok
        assert reason == "excluded-label:wheel:hold"

    def test_full_pipeline_drops_wheel_hold_labeled_gh_item(self, tmp_path):
        """End-to-end through run(): a gh-sourced item carrying wheel:hold
        must never reach `items`, and must be reported in `dropped` with the
        excluded-label reason -- exercised entirely through EXISTING code
        (merge_sources -> apply_valid_predicate), no exclude_issues
        involved."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 600,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "held by a peer session",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        gh_items = [
            {
                "issue": 600,
                "open": True,
                "title": "held item",
                "labels": ["wheel:hold"],
                "last_comment": None,
            }
        ]
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=gh_items,
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        assert payload["items"] == []
        assert {"issue": 600, "reason": "excluded-label:wheel:hold"} in payload["dropped"]


class TestRunExcludeIssuesParameter:
    """(b): run(..., exclude_issues={...}) drops exactly the named issues,
    with dropped_log reason f"env-excluded:{issue}", while other candidates
    are unaffected and proceed through ranking normally.
    """

    def _make_repo_with_two_valid_issues(self, tmp_path, ledger_path, ready_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "a.py").write_text("x")
        (d / "b.py").write_text("x")
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 123,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/a.py"],
                    "reason": "should be excluded this run",
                },
                {
                    "number": 456,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/b.py"],
                    "reason": "should proceed normally",
                },
            ],
        )
        return repo

    def test_excluded_issue_is_dropped_with_env_excluded_reason(self, tmp_path):
        ledger_path = tmp_path / "ledger.json"
        ready_path = tmp_path / "ready.json"
        repo = self._make_repo_with_two_valid_issues(tmp_path, ledger_path, ready_path)
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={123},
        )
        assert {"issue": 123, "reason": "env-excluded:123"} in payload["dropped"]

    def test_non_excluded_issue_is_not_dropped_and_reaches_items(self, tmp_path):
        ledger_path = tmp_path / "ledger.json"
        ready_path = tmp_path / "ready.json"
        repo = self._make_repo_with_two_valid_issues(tmp_path, ledger_path, ready_path)
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={123},
        )
        item_issue_nums = {it["issue"] for it in payload["items"]}
        assert 456 in item_issue_nums
        assert 123 not in item_issue_nums
        dropped_issue_nums = {d["issue"] for d in payload["dropped"]}
        assert 456 not in dropped_issue_nums

    def test_excluded_issue_never_appears_in_items_even_though_otherwise_valid(self, tmp_path):
        """The excluded item here is otherwise fully VALID (real path,
        legal size, open, no other exclusion) -- exclude_issues must be
        sufficient on its own to keep it out of `items`, proving this is a
        genuine filter and not merely coincidental with some other drop
        reason."""
        ledger_path = tmp_path / "ledger.json"
        ready_path = tmp_path / "ready.json"
        repo = self._make_repo_with_two_valid_issues(tmp_path, ledger_path, ready_path)
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues=set(),
        )
        # Control: with an EMPTY exclusion set, issue 123 DOES reach items --
        # proving that its absence in the test above is caused specifically
        # by exclude_issues={123}, not by some unrelated validity failure.
        item_issue_nums = {it["issue"] for it in payload["items"]}
        assert 123 in item_issue_nums

    def test_exclude_issues_none_is_a_no_op(self, tmp_path):
        """The default (exclude_issues=None) must behave identically to
        never having the parameter at all -- no item is dropped for an
        env-excluded reason."""
        ledger_path = tmp_path / "ledger.json"
        ready_path = tmp_path / "ready.json"
        repo = self._make_repo_with_two_valid_issues(tmp_path, ledger_path, ready_path)
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues=None,
        )
        assert not any(str(d.get("reason", "")).startswith("env-excluded") for d in payload["dropped"])
        item_issue_nums = {it["issue"] for it in payload["items"]}
        assert {123, 456}.issubset(item_issue_nums)

    def test_excluding_an_issue_not_present_in_the_candidate_set_is_a_no_op(self, tmp_path):
        """Excluding an issue number that doesn't exist in this run's
        candidate set must never raise or otherwise perturb the run -- it
        simply has nothing to match against."""
        ledger_path = tmp_path / "ledger.json"
        ready_path = tmp_path / "ready.json"
        repo = self._make_repo_with_two_valid_issues(tmp_path, ledger_path, ready_path)
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={999999},
        )
        item_issue_nums = {it["issue"] for it in payload["items"]}
        assert {123, 456}.issubset(item_issue_nums)


class TestExcludeIssuesCliParsing:
    """(c): the --exclude-issues CLI argument.

    Contract under test (plan_wheel_exclusion_and_quiescence_2026_09_13.md,
    Finding 1(b) + Implementation plan item 1): a valid comma-separated list
    of non-negative integers parses into that exact set of ints; an
    unset/empty value produces NO exclusions (None, per run()'s own
    `exclude_issues: set[int] | None = None` signature -- never an empty
    set, which is a materially different value: an empty set is a
    deliberate "exclude nothing, but the machinery ran," whereas None is
    "exclusion wasn't requested at all" -- run()'s own filtering loop must
    treat both as a no-op either way, but the CLI's OWN parse result is
    specified as None for "not requested," matching the parameter's
    documented default); and a malformed token (a non-digit entry) is a
    hard, loud failure -- never a silently-empty or silently-partial set.
    """

    def _run_cli(self, tmp_path, extra_args, env_overrides=None):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--tracker-rel",
                "nonexistent_tracker.html",
            ]
            + extra_args,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )

    def test_valid_comma_separated_list_round_trips_into_the_run(self, tmp_path):
        """A valid --exclude-issues value must genuinely reach run()'s own
        exclude_issues filter -- proven end-to-end via the CLI subprocess by
        constructing a real, otherwise-valid candidate at the named issue
        number and confirming it is dropped with the env-excluded reason."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = repo / "_Config_Project" / "docs" / "domain" / "issue_burndown_ledger.json"
        os.makedirs(ledger_path.parent, exist_ok=True)
        with open(ledger_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "waves": [
                        {
                            "wave": 1,
                            "needs_work": [
                                {
                                    "number": 123,
                                    "size_points": 2,
                                    "files_touched": ["modules/billing/api/webhook.py"],
                                    "reason": "should be excluded via CLI",
                                }
                            ],
                        }
                    ]
                },
                fh,
            )
        import subprocess

        # A real `git status` call is what load_dirty_paths() actually
        # invokes (this test drives the real CLI end-to-end, not an
        # injected seam) -- a non-repo tmp_path fails that call entirely
        # (reachable=False), which correctly fails the WHOLE run closed
        # (dirty-state-unconfirmed for every candidate) per this module's
        # own documented safety posture. That is a real, separate behavior
        # from what THIS test is proving (exclude_issues filtering) --
        # init a real, clean repo so git status succeeds and the run can
        # actually reach the exclude_issues filter.
        subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=15)

        env = dict(os.environ)
        env.pop("CSA_SDW_REPO", None)
        env["CSA_SDW_READY_PATH"] = str(tmp_path / "ready.json")
        env["HOME"] = str(tmp_path / "home")
        os.makedirs(env["HOME"], exist_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(_HOOKS_DIR, "issue_wheel_queue.py"),
                "run",
                "--repo",
                str(repo),
                "--slug",
                "testslug",
                "--tracker-rel",
                "nonexistent_tracker.html",
                "--exclude-issues",
                "123,456",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert {"issue": 123, "reason": "env-excluded:123"} in payload["dropped"]

    def test_unset_exclude_issues_flag_produces_no_exclusions(self, tmp_path):
        proc = self._run_cli(tmp_path, [])
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert not any(str(d.get("reason", "")).startswith("env-excluded") for d in payload.get("dropped", []))

    def test_empty_string_exclude_issues_produces_no_exclusions(self, tmp_path):
        proc = self._run_cli(tmp_path, ["--exclude-issues", ""])
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert not any(str(d.get("reason", "")).startswith("env-excluded") for d in payload.get("dropped", []))

    def test_malformed_token_raises_a_clear_error_not_a_silent_empty_set(self, tmp_path):
        """This is the test that catches an implementer who added
        silent-degradation instead of a hard failure: a value like
        "abc,123" (one malformed token mixed with one well-formed one) must
        cause the run to fail loudly -- nonzero exit and a clear message on
        stderr -- never silently drop the bad token and proceed with a
        partial/empty exclusion set, and never exit 0 with a normal-looking
        payload as if nothing was wrong."""
        proc = self._run_cli(tmp_path, ["--exclude-issues", "abc,123"])
        assert proc.returncode != 0
        assert proc.stdout.strip() == "" or "error" in proc.stdout.lower()
        assert proc.stderr.strip() != ""

    def test_malformed_value_never_silently_proceeds_with_a_ready_json_write(self, tmp_path):
        """Companion to the assertion above, from the ready.json-write side:
        a malformed --exclude-issues must never reach the point of writing
        an emitted ready.json at all -- the failure must happen before the
        pipeline runs, exactly like the existing --fresh-triage bad-path
        failure mode (main()'s own code-reviewer-blocker-1 precedent)."""
        ready_path = tmp_path / "ready.json"
        proc = self._run_cli(tmp_path, ["--exclude-issues", "abc,123"])
        assert proc.returncode != 0
        assert not ready_path.exists()

    def test_purely_whitespace_token_is_also_malformed(self, tmp_path):
        """A stray extra comma / whitespace-only token (e.g. "123,,456" or
        "123, ,456") must be treated as malformed input, not silently
        skipped -- a lenient parser that drops empty/blank tokens without
        erroring would defeat the "clear error, never silent partial set"
        requirement for what is, in effect, a malformed list."""
        proc = self._run_cli(tmp_path, ["--exclude-issues", "123,,456"])
        assert proc.returncode != 0
        assert proc.stderr.strip() != ""

    def test_negative_number_token_is_malformed(self, tmp_path):
        """Issue numbers are non-negative by construction (plan's own
        wording: "a bare non-negative integer") -- a negative number must
        be rejected the same way any other non-digit token is, not silently
        accepted as a valid (if nonsensical) exclusion.

        trust-architect M3: the space-separated form
        ["--exclude-issues", "-5,123"] passes for the WRONG reason -- argparse
        itself rejects "-5,123" as option-like before this module's own parse
        guard ever runs, so this shape does not actually exercise the code
        under test. The "=" form (["--exclude-issues=-5,123"]) bypasses
        argparse's option-like heuristic entirely and reaches this module's
        own parser, which is what must be proven to reject it."""
        proc = self._run_cli(tmp_path, ["--exclude-issues=-5,123"])
        assert proc.returncode != 0
        assert proc.stderr.strip() != ""


class TestExcludedItemsRemainVisibleInDroppedArray:
    """(d): an excluded item -- via EITHER the label path or the
    exclude_issues path -- must still appear in payload["dropped"] with its
    exclusion reason, never simply vanish from the payload. This is the
    mechanical proof behind Finding 1's "never a silent skip" /
    trust-surface-visibility claim (an excluded trust-surface item is still
    reported, just not lane-opened).
    """

    def test_label_excluded_item_appears_in_dropped_with_reason(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 700,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "held via label",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        gh_items = [
            {
                "issue": 700,
                "open": True,
                "title": "held item",
                "labels": ["wheel:hold"],
                "last_comment": None,
            }
        ]
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=gh_items,
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
        )
        dropped_by_issue = {d["issue"]: d["reason"] for d in payload["dropped"]}
        assert dropped_by_issue.get(700) == "excluded-label:wheel:hold"
        # Never silently vanished: the issue number must be traceable
        # SOMEWHERE in the payload (dropped here; never neither array).
        all_issue_nums = {it["issue"] for it in payload["items"]} | set(dropped_by_issue)
        assert 700 in all_issue_nums

    def test_exclude_issues_excluded_item_appears_in_dropped_with_reason(self, tmp_path):
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 701,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "held via exclude_issues",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={701},
        )
        dropped_by_issue = {d["issue"]: d["reason"] for d in payload["dropped"]}
        assert dropped_by_issue.get(701) == "env-excluded:701"
        all_issue_nums = {it["issue"] for it in payload["items"]} | set(dropped_by_issue)
        assert 701 in all_issue_nums

    def test_excluded_item_never_appears_in_items_array(self, tmp_path):
        """The other half of "visible but not lane-opened": an excluded
        item is reported in `dropped`, but must NEVER also appear in
        `items` (which is what would actually open a lane for it)."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 702,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "held via exclude_issues",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        payload = sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={702},
        )
        item_issue_nums = {it["issue"] for it in payload["items"]}
        assert 702 not in item_issue_nums

    def test_dropped_entry_is_also_written_to_disk_not_just_returned(self, tmp_path):
        """The dropped array's exclusion-reason entry must survive the
        atomic write to ready.json, not merely exist in the in-memory
        return value -- a caller reading ready.json from disk (as
        issue_wheel.txt's own P4 step does) must see the same visibility
        guarantee."""
        repo = tmp_path / "repo"
        d = repo / "modules" / "billing" / "api"
        d.mkdir(parents=True)
        (d / "webhook.py").write_text("x")
        ledger_path = tmp_path / "ledger.json"
        TestRunEndToEnd()._write_ledger(
            str(ledger_path),
            [
                {
                    "number": 703,
                    "size_points": 2,
                    "files_touched": ["modules/billing/api/webhook.py"],
                    "reason": "held via exclude_issues",
                }
            ],
        )
        ready_path = tmp_path / "ready.json"
        sq.run(
            repo=str(repo),
            ledger_path=str(ledger_path),
            plans_dir=str(tmp_path / "no_plans_dir"),
            ready_path=str(ready_path),
            now_ts=1_000_000.0,
            now_iso="2026-09-01T00:00:00Z",
            gh_items=[],
            dirty_paths=set(),
            confirm_issue_state_fn=lambda repo, num: ("OPEN", [], None),
            exclude_issues={703},
        )
        with open(ready_path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        dropped_by_issue = {d["issue"]: d["reason"] for d in on_disk["dropped"]}
        assert dropped_by_issue.get(703) == "env-excluded:703"
