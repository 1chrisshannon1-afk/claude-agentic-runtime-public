#!/usr/bin/env python3
"""Mutation battery for precommit_review_gate — the evidence behind its catch rate.

The gate exists to stop agents self-certifying green. That would be hollow if
its OWN suite were never shown capable of failing, so this plants a specific
defect in each load-bearing decision and confirms the suite goes red for it.

Per `feedback_never_claim_guard_coverage_untested`: the number this prints is
the only catch rate that may appear in a doc or a commit message. Several of
these anchors exist because an Opus review found the suite green against
defects it should have caught (two vacuous tests, a cwd-normalization wedge,
a macOS symlink fail-open) — the denominator is not chosen to flatter.

Copies the whole hooks tree out of ~/.claude into a temp dir and mutates the
COPY, so the operator's live hook system is never modified.

Usage:  python3 ~/.claude/hooks/tests/precommit_review_mutation_battery.py
Exit 0 = every mutation caught; 1 = a gap or a stale anchor; 2 = control RED
(battery invalid, its numbers mean nothing).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path.home() / ".claude/hooks"
SUITE = "tests/test_precommit_review_gate.py"

# (id, file, old, new)
MUTATIONS = [
    (
        "H1_gate_not_wired_into_dispatcher",
        "pretooluse_bash.py",
        '        b, detail = _precommit_review_block(\n            ev, command, effective_where, staged, real_repo_root\n        )\n        if b is not None:\n            return b, detail\n',
        "",
    ),
    (
        "H2_decide_never_blocks",
        "precommit_review_gate.py",
        "        if outcome is None:\n            return (",
        "        if False:\n            return (",
    ),
    (
        "H3_blocks_even_when_reviewed",
        "precommit_review_gate.py",
        "        outcome = rr.head_review_outcome(ledger, repo_root, key)",
        "        outcome = None",
    ),
    (
        "H4_digest_ignores_the_commits_paths",
        "precommit_review_gate.py",
        '    diff = _git(repo_root, "diff", "HEAD", "--", *ordered)',
        '    diff = _git(repo_root, "diff", "HEAD")',
    ),
    (
        # Repointed 2026-08-30 (#4670 landed gate 3c between 3b and 4,
        # staling the original 3b<->4 swap below — see H28/H29 for 3c's own
        # two properties, deny-before-claim and pathspec-commits-only).
        # Asserts 3b (precommit_review_block) still runs before its new
        # immediate neighbor, 3c (dirty_precommit_config_block).
        "H5_gate_runs_after_the_file_claim_mutex",
        "pretooluse_bash.py",
        '        b, detail = _precommit_review_block(\n            ev, command, effective_where, staged, real_repo_root\n        )\n        if b is not None:\n            return b, detail\n        b = _dirty_precommit_config_block(command, effective_where, real_repo_root)\n        if b is not None:\n            return b, {}\n',
        '        b = _dirty_precommit_config_block(command, effective_where, real_repo_root)\n        if b is not None:\n            return b, {}\n        b, detail = _precommit_review_block(\n            ev, command, effective_where, staged, real_repo_root\n        )\n        if b is not None:\n            return b, detail\n',
    ),
    (
        # NEW 2026-08-30 (#4670/gate-optimization plan Item 0 follow-up).
        # Property (a): gate 3c must deny BEFORE gate 4 takes a file claim —
        # the whole point of ordering 3c ahead of 4 is that a config-denied
        # commit never parks the commit mutex. The plan's own spec (§2 Item 0
        # step 2) named one anchor "H28_gate3c_runs_after_gate3b" covering
        # both of gate 3c's properties; a mutation battery can only plant one
        # defect per entry, so this was split into two (this one + H29 below)
        # — deliberately, but the split kept the plan's original name, which
        # names H5's property (3c after 3b), not this one's (3c before 4).
        # Renamed to match what this mutation actually proves.
        "H28_gate3c_runs_before_the_file_claim_mutex",
        "pretooluse_bash.py",
        '        b = _dirty_precommit_config_block(command, effective_where, real_repo_root)\n        if b is not None:\n            return b, {}\n        b, detail = _file_claim_block(ev, command, effective_where, targets, real_repo_root)\n        if b is not None:\n            return b, detail\n',
        '        b, detail = _file_claim_block(ev, command, effective_where, targets, real_repo_root)\n        if b is not None:\n            return b, detail\n        b = _dirty_precommit_config_block(command, effective_where, real_repo_root)\n        if b is not None:\n            return b, {}\n',
    ),
    (
        # NEW 2026-08-30. Property (b): gate 3c must fire ONLY on pathspec
        # commits — a non-pathspec Bash command must never be gated here.
        # Neutralizes _dirty_precommit_config_block's own pathspec guard.
        "H29_gate3c_pathspec_only_scope",
        "pretooluse_bash.py",
        "    if not _declared_pathspec(command)[1]:\n        return None\n    if _pathspec_includes_precommit_config(command, where, repo_root):",
        "    if _pathspec_includes_precommit_config(command, where, repo_root):",
    ),
    (
        "H6_paths_flag_swallows_the_target_dir",
        "record_review.py",
        '        if a == "--paths":',
        '        if a == "--paths-DISABLED":',
    ),
    (
        "H7_recorded_blockers_ignored",
        "precommit_review_gate.py",
        "        if status == rr.OUTCOME_BLOCKERS:",
        "        if False:",
    ),
    (
        "H8_precommit_namespace_collides_with_shas",
        "precommit_review_gate.py",
        'PRECOMMIT_PREFIX = "precommit:"',
        'PRECOMMIT_PREFIX = ""',
    ),
    (
        "H10_untracked_new_files_dropped_from_digest",
        "precommit_review_gate.py",
        "    return diff + _untracked_material(repo_root, ordered)",
        "    return diff",
    ),
    (
        "H11_symlinked_repo_path_breaks_normalization",
        "precommit_review_gate.py",
        "            rel = os.path.relpath(os.path.join(os.path.realpath(head), tail), root)",
        "            rel = os.path.relpath(os.path.abspath(base), os.path.abspath(repo_root))",
    ),
    (
        "H12_cwd_relative_pathspec_not_normalized",
        "precommit_review_gate.py",
        "    ordered = normalize_paths(repo_root, cwd, paths)",
        "    ordered = sorted(set(paths))",
    ),
    (
        "H13_operator_rollback_lever_ignored",
        "precommit_review_gate.py",
        "        if disabled_by_operator():\n            return (False, \"\", {})",
        "        if False:\n            return (False, \"\", {})",
    ),
    (
        "H14_unresolvable_pathspec_waved_through",
        "precommit_review_gate.py",
        "    if unresolvable(repo_root, cwd, list(paths)):\n        return UNRESOLVABLE",
        "    if False:\n        return UNRESOLVABLE",
    ),
    (
        "H15_include_flag_does_not_widen_targets",
        "pretooluse_bash.py",
        "            if _segment_includes_index(seg):\n                any_missing = True",
        "            if False:\n                any_missing = True",
    ),
    (
        "H16_unreadable_ledger_denies_instead_of_failing_open",
        "precommit_review_gate.py",
        "        if not _ledger_readable(ledger):",
        "        if False:",
    ),
    (
        # Must stay SYNTACTICALLY VALID. An earlier version of this mutant left a
        # dangling `if` with no body, so pytest errored at collection and it scored
        # CAUGHT without any test asserting anything -- a mutation that measures
        # nothing inflates the very number this file exists to keep honest.
        "H9_empty_diff_still_demands_a_review",
        "precommit_review_gate.py",
        "    if diff_text.strip():\n        return PRECOMMIT_PREFIX + digest_of(diff_text)\n    return None",
        "    return PRECOMMIT_PREFIX + digest_of(diff_text)",
    ),
    # H17-H21: added with the round-2 review's fixes, for the same reason as
    # M14-M17 above -- every one of these decisions was found broken by a
    # review while this battery reported a perfect score.
    (
        "H17_unresolvable_checked_after_the_digest",
        "precommit_review_gate.py",
        "    if unresolvable(repo_root, cwd, list(paths)):\n        return UNRESOLVABLE\n    diff_text = pending_diff(repo_root, cwd, paths)",
        "    diff_text = pending_diff(repo_root, cwd, paths)",
    ),
    (
        "H18_remedy_paths_not_shell_quoted",
        "precommit_review_gate.py",
        "    joined = \" \".join(shlex.quote(p) for p in sorted(set(paths)))",
        "    joined = \" \".join(sorted(set(paths)))",
    ),
    (
        "H19_bundled_include_flag_missed",
        "pretooluse_bash.py",
        "        letters = buc._short_flags(tok)\n        if letters and \"i\" in letters:\n            return True",
        "        if tok == \"-i\":\n            return True",
    ),
    (
        "H20_review_targets_conflate_coordinate_systems",
        "pretooluse_bash.py",
        "    review_targets = _review_target_paths(ev, command, where, staged, repo_root)\n    block, reason, detail = prg.decide(\n        repo_root, repo_root or where, review_targets, command=command\n    )",
        "    review_targets = _commit_target_paths(ev, command, where, staged)\n    block, reason, detail = prg.decide(\n        repo_root, where, review_targets, command=command\n    )",
    ),
    (
        "H21_untracked_listing_without_nul_separation",
        "precommit_review_gate.py",
        '    listing = _git(cwd, "-c", "core.quotePath=false", "ls-files", "--others",\n                   "--exclude-standard", "-z", "--", *ordered)',
        '    listing = _git(cwd, "ls-files", "--others", "--exclude-standard", "--", *ordered)',
    ),
    # H22-H24: added 2026-08-20 with the round-3 review's fixes (B1 LEAK, B2
    # LEAK, B3 WEDGE) -- same reason as H17-H21 above. H25 added the same day
    # with the round-4 review's fixes to those same 3 fixes (round 3's B3 fix
    # reopened a narrower leak of its own, and its B1 fix was itself an
    # unbounded false-positive trap) -- same reason again.
    (
        "H22_unquoted_command_substitution_not_refused",
        "precommit_review_gate.py",
        '        if command and command_has_unquoted_command_substitution(command):\n            return (\n                True,\n                REASON_UNRESOLVABLE,\n                {"paths": sorted(set(paths or []))[:20]},\n            )\n',
        "",
    ),
    (
        "H23_real_file_with_a_shell_metachar_still_refused",
        "precommit_review_gate.py",
        "        if all(m in _EXCUSABLE_VIA_REAL_CONTENT for m in hits) and _token_resolves_to_real_content(\n            repo_root, cwd, t\n        ):\n            continue",
        "        if _token_resolves_to_real_content(repo_root, cwd, t):\n            continue",
    ),
    (
        "H24_include_abbreviation_not_recognized",
        "pretooluse_bash.py",
        '    return tok.startswith(_INCLUDE_ABBREV_FLOOR) and "--include".startswith(tok)',
        '    return tok == "--include"',
    ),
    (
        # Round-4 finding: the scan armed at the first `--` and never
        # disarmed, so a perfectly ordinary chained command with nothing
        # dangerous in its OWN pathspec was denied forever -- recording a
        # review can never clear an UNRESOLVABLE verdict. This mutant removes
        # the disarm-on-control-operator branches, reverting to that
        # unbounded (and self-inflicted-false-positive) behavior.
        "H25_command_substitution_scan_never_disarms",
        "precommit_review_gate.py",
        '        if c in (";", "|", "\\n"):',
        "        if False:",
    ),
    (
        # Round-4 finding: `$`/backtick/`{` were excused by the SAME
        # real-content check as `(`/`~`, but those three can expand an
        # unquoted token to a DIFFERENT string before git ever sees it -- "a
        # file literally named '$FILES' exists" is not evidence of what an
        # unquoted `$FILES` would actually expand to. This mutant widens the
        # excusable set back to all of _SHELL_META, reopening that leak.
        "H26_expanding_metachars_wrongly_excusable",
        "precommit_review_gate.py",
        '_EXCUSABLE_VIA_REAL_CONTENT = ("(", "~")',
        "_EXCUSABLE_VIA_REAL_CONTENT = _SHELL_META",
    ),
    (
        # Round-5 finding: a REDIRECTION `&` (`2>&1`, `>&2`, `&>file`) was
        # treated as a control operator and disarmed the scan mid-pathspec,
        # reopening the leak for that shape only -- `-- a.py 2>&1 $(cmd)`
        # digested "a.py" + the literal "2>" fragment (which matches
        # nothing) while the real shell would land $(cmd)'s expansion
        # unreviewed. This mutant removes the redirection exception, making
        # every bare `&` disarm unconditionally again.
        "H27_redirection_ampersand_wrongly_disarms",
        "precommit_review_gate.py",
        '            prev = command[i - 1] if i > 0 else ""\n            nxt = command[i + 1] if i + 1 < n else ""\n            if prev not in (">", "<") and nxt != ">":\n                armed = False',
        "            armed = False",
    ),
]


def build(workdir: Path, name: str) -> Path:
    root = workdir / name
    shutil.copytree(HOOKS, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return root


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", SUITE, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=1200,
        # The copy lives in a temp dir, not at ~/.claude, so the foreign-root session guard
        # in the copied hooks/tests/conftest.py would abort every run with exit 2: the
        # control would read RED, and no mutant run could be told from a real catch.
        env={**os.environ, "CSA_TESTS_ALLOW_FOREIGN_ROOT": "1"},
    )


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="hook_mutations_"))
    try:
        ctl = run(build(workdir, "H0_control"))
        print(f"[control] {'GREEN' if ctl.returncode == 0 else 'RED -- battery invalid'}")
        if ctl.returncode != 0:
            print(ctl.stdout[-3000:])
            return 2

        caught = 0
        stale: list[str] = []
        for name, fname, old, new in MUTATIONS:
            root = build(workdir, name)
            target = root / fname
            text = target.read_text()
            if old not in text:
                # A moved anchor is a FAILURE, not a skip: passing silently
                # over it would quietly shrink the measured catch rate.
                stale.append(name)
                print(f"[{name}] STALE ANCHOR in {fname}")
                continue
            target.write_text(text.replace(old, new, 1))
            proc = run(root)
            hit = proc.returncode != 0
            caught += hit
            tail = [ln for ln in proc.stdout.splitlines() if "passed" in ln or "failed" in ln]
            print(f"[{name}] {'CAUGHT' if hit else 'SURVIVED  <-- GAP'}  {tail[-1] if tail else ''}")

        print(f"\ncatch rate: {caught}/{len(MUTATIONS)}")
        if stale:
            print(f"stale anchors (fix these first): {', '.join(stale)}")
        return 0 if caught == len(MUTATIONS) and not stale else 1
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
