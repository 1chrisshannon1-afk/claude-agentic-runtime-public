"""Tests for validate_agentarch_ledger (#4400, #4436, item 7/8).

Falsifiability: one RED fixture per violation class (proving the check
actually fires without the corresponding fix), one clean fixture proving
zero violations, plus a live-tree run against the real ledger.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_agentarch_ledger as val  # noqa: E402

_HOME = str(Path.home())
# Self-checking precondition (round-8 review, 2026-08-30): several BLOCKER-1
# tests use $HOME (never tmp_path -- see those tests' own comments for why
# tmp_path is unsafe on a CI runner with no TMPDIR set) as an "untrusted cwd"
# outside every always-safe root. That is guaranteed on a normal machine
# layout, but would be silently, vacuously false on any environment where
# HOME itself sits under an always-safe root (e.g. HOME=/tmp in a stripped
# container) -- exactly the class of environment-dependent false green this
# whole file exists to eliminate. Fail loudly at collection time instead of
# passing everything vacuously.
assert not val.agentarch_metric_check._is_always_safe(_HOME), (
    f"test precondition violated: $HOME ({_HOME!r}) resolves under an "
    "always-safe root, so every BLOCKER-1 test using it as an untrusted cwd "
    "would pass vacuously regardless of whether the guard actually works"
)

# Probed, not assumed (round 7 review, 2026-08-28) — see
# test_agentarch_metric_check.py's identical constants for the full
# rationale: these gate ONLY the tests whose assertions depend on a
# filesystem-behavior precondition (case-insensitive APFS / a real
# `/private/tmp` alias), never a security assumption in the guard itself.
_CASE_INSENSITIVE_FS = os.path.exists(f"{_HOME}/.claude/PROJECTS")
_HAS_PRIVATE_TMP_ALIAS = os.path.exists("/private/tmp")


def _row(**overrides: object) -> dict:
    base = {
        "id": "AA-0001",
        "issued_at": "2026-08-25",
        "claim": "some claim",
        "metric": "some metric",
        "metric_command": f"grep -c foo {_HOME}/.claude/hooks/_lib.py",
        "baseline_value": 1,
        "target_direction": "up",
        "status": "open",
        "checked_at": None,
        "checked_value": None,
    }
    base.update(overrides)
    return base


def _write_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _write_registry(tmp_path: Path, repos: dict[str, str]) -> Path:
    p = tmp_path / "repo_registry.json"
    p.write_text(json.dumps({"schema_version": 1, "repos": {k: {"root": v} for k, v in repos.items()}}))
    return p


def _make_registrable_repo(d: Path) -> Path:
    """Marks an existing directory as a real repo checkout (a `.git` entry)
    so `agentarch_metric_check.load_registry` actually accepts it as a
    registry root — Blocker 4 (round 3 review, 2026-08-28) requires a
    registered root to look like a real repo checkout, not an arbitrary
    directory, so any fixture registered BY PATH (never one only ever
    passed as a raw `extra_repo_root`) needs this.
    """
    (d / ".git").mkdir(exist_ok=True)
    return d


# --------------------------------------------------------------------------
# guard_check — RED per class + legal cases
# --------------------------------------------------------------------------


def test_guard_legal_grep_c_under_claude_root():
    ok, reason = val.guard_check(f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_legal_grep_rl_under_claude_root():
    ok, _ = val.guard_check(f"grep -rl heartbeat {_HOME}/.claude/hooks")
    assert ok


def test_guard_illegal_cluster_with_one_bad_constituent_rejected():
    # L7: a cluster is legal iff EVERY constituent letter is individually
    # allowed — one bad letter (here 'z', not in _GREP_FLAGS) fails the
    # whole cluster, not just that letter.
    ok, reason = val.guard_check(f"grep -rz foo {_HOME}/.claude/hooks")
    assert not ok
    assert "unlisted flag" in reason


def test_guard_legal_wc_l():
    ok, _ = val.guard_check(f"wc -l {_HOME}/.claude/hooks/_lib.py")
    assert ok


def test_guard_legal_quoted_multiword_pattern():
    ok, _ = val.guard_check(
        'grep -c "already completed by the session" '
        f"{_HOME}/.claude/schedules/prompts/weekly_report.txt"
    )
    assert ok


@pytest.fixture
def home_repo_checkout():
    """A real repo-checkout-shaped directory under $HOME/.cache.

    The bounds check is a filesystem-IDENTITY test on the deepest EXISTING
    ancestor, so a ``repo_root`` that does not exist on disk grants nothing --
    these tests used to lean on an app checkout that happens to exist under the
    author's home and failed on any other machine. The directory is created
    under $HOME, never pytest's tmp_path: tmp_path sits under /tmp on Linux,
    an always-safe root, which would let the path pass whether or not
    ``repo_root`` was honored (a vacuous pass). The module-level precondition
    above already guarantees $HOME is outside every always-safe root, and
    ``~/.cache`` is neither ``~/.claude`` nor /tmp, so the paired illegal test
    below still discriminates. The user cache directory (not the top of $HOME)
    keeps a crashed run from leaving anything in the home directory itself.
    """
    cache = Path(_HOME) / ".cache"
    cache.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="agentarch-guard-fixture-", dir=str(cache)))
    try:
        _make_registrable_repo(root)
        (root / "CLAUDE.md").write_text("seven\n")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_guard_legal_repo_root_path_when_supplied(home_repo_checkout):
    ok, reason = val.guard_check(
        f"grep -c seven {home_repo_checkout}/CLAUDE.md",
        repo_root=str(home_repo_checkout),
    )
    assert ok, reason


def test_guard_illegal_repo_root_path_without_extra_root(home_repo_checkout):
    # Pair of the test above on the SAME existing path: legal only because
    # repo_root was supplied, outside the allowed roots without it.
    ok, reason = val.guard_check(
        f"grep -c seven {home_repo_checkout}/CLAUDE.md",
        repo_root=None,
    )
    assert not ok
    assert "outside allowed roots" in reason


def test_guard_illegal_unlisted_flag():
    ok, reason = val.guard_check(f"grep --pre-glob foo {_HOME}/.claude/hooks/_lib.py")
    assert not ok
    assert "unlisted flag" in reason


def test_guard_illegal_unrecognized_command():
    ok, reason = val.guard_check("curl https://example.com")
    assert not ok
    assert "unrecognized command form" in reason


def test_guard_illegal_dash_c_shell():
    ok, reason = val.guard_check("python3 -c \"print('hi')\"")
    assert not ok
    assert "'-c'" in reason


def test_guard_illegal_eval():
    ok, reason = val.guard_check("eval echo hi")
    assert not ok
    assert "eval" in reason


def test_guard_illegal_xargs():
    ok, reason = val.guard_check("xargs rm")
    assert not ok
    assert "xargs" in reason


def test_guard_illegal_find_exec():
    ok, reason = val.guard_check("find /tmp -exec rm {} +")
    assert not ok
    assert "find -exec" in reason


def test_guard_illegal_forbidden_substring_semicolon():
    ok, reason = val.guard_check("grep -c foo /tmp/x; rm -rf /")
    assert not ok
    assert "forbidden substring" in reason


def test_guard_illegal_forbidden_substring_backtick():
    ok, reason = val.guard_check("grep -c `whoami` /tmp/x")
    assert not ok
    assert "forbidden substring" in reason


def test_guard_illegal_forbidden_substring_dollar_paren():
    ok, reason = val.guard_check("grep -c $(whoami) /tmp/x")
    assert not ok
    assert "forbidden substring" in reason


def test_guard_illegal_path_traversal():
    ok, reason = val.guard_check(f"cat {_HOME}/.claude/hooks/../../etc/passwd")
    assert not ok
    assert "traversal" in reason


def test_guard_illegal_path_outside_all_roots():
    ok, reason = val.guard_check("cat /etc/passwd")
    assert not ok
    assert "outside allowed roots" in reason


def test_guard_illegal_projects_path_is_never_safe_even_though_under_claude_root():
    """Blocker 5 (round 3 review, 2026-08-28): agentic-systems-architect.md
    documents ~/.claude/projects/ as excluded from the always-safe
    treatment; this must actually be guard-illegal, not merely reported as
    a separate hardcoded-repo-path finding while still being executed."""
    cmd = (
        'grep -rl "[stall] agent" '
        f"{_HOME}/.claude/projects/-Users-x-Desktop-ExampleApp/"
        "884000b8-293a-4be7-9ae6-85b2be304047/workflows"
    )
    ok, reason = val.guard_check(cmd)
    assert not ok
    assert "never-safe" in reason


def test_guard_legal_other_claude_root_paths_are_unaffected_by_projects_exclusion():
    ok, reason = val.guard_check(f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_illegal_never_safe_root_double_slash_spelling_bypass():
    """Blockers 2/5 (round 4 review, 2026-08-28): a `//`-spelled path into
    ~/.claude/projects/ was `abspath`-preserved unnormalized and compared
    unequal to the never-safe root's canonical (single-slash) form, so it
    sailed through as guard-legal even though `find_hardcoded_paths`
    already reported it as a `hardcoded-repo-path` finding — the guard
    that gates real execution and the finding that merely reports one had
    silently diverged. Must be rejected, and never actually executed."""
    cmd = f"grep -rl foo {_HOME}/.claude//projects/-Users-x-Desktop-App/workflows"
    ok, reason = val.guard_check(cmd)
    assert not ok
    assert "never-safe" in reason


def test_guard_illegal_never_safe_root_dot_slash_spelling_bypass():
    """Same class as the `//` bypass above, `/./`-spelled."""
    cmd = f"grep -rl foo {_HOME}/.claude/./projects/-Users-x-Desktop-App/workflows"
    ok, reason = val.guard_check(cmd)
    assert not ok
    assert "never-safe" in reason


def test_guard_illegal_never_safe_root_trailing_slash_spelling():
    """Trailing-slash spelling must be rejected the same way as the
    canonical, `//`, and `/./` spellings (round 4 review ask: confirm this
    stays handled once the others are fixed)."""
    cmd = f"grep -rl foo {_HOME}/.claude/projects/-Users-x-Desktop-App/workflows/"
    ok, reason = val.guard_check(cmd)
    assert not ok
    assert "never-safe" in reason


def test_guard_illegal_never_safe_root_named_bare_with_no_subpath():
    """A bare mention of the never-safe directory itself (no subpath, no
    trailing separator) must not evade the prefix check just because the
    realpath'd candidate lacks the root constant's trailing os.sep."""
    for spelling in (
        f"{_HOME}/.claude/projects",
        f"{_HOME}/.claude//projects",
        f"{_HOME}/.claude/./projects",
    ):
        ok, reason = val.guard_check(f"ls -1 {spelling}")
        assert not ok, f"{spelling!r} was wrongly guard-legal: {reason!r}"
        assert "never-safe" in reason


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="one of its 3 spellings requires a case-insensitive filesystem volume"
)
def test_never_safe_bypass_command_does_not_actually_execute(tmp_path, monkeypatch):
    """Finding #8 (round 6 review, 2026-08-28): the previous version of this
    test only called `guard_check` and asserted not-legal — a duplicate of
    the two preceding tests, despite its name promising to verify the
    COMMAND itself never runs. Rewritten to mirror
    `test_check_ledger_unknown_repo_slug_is_a_distinct_violation_and_never_runs`'s
    pattern: monkeypatch `run_metric_command` to record calls, drive a
    never-safe-spelled row through the full `check_ledger(run_live=True)`
    path, and assert the recorder was never invoked.

    A never-safe-spelled, literal (non-${REPO:<slug>}) path is now also a
    `hardcoded-repo-path` violation, and Finding 5 (round 8 review,
    2026-08-30) makes ANY such violation skip the row entirely BEFORE
    guard-legality is even evaluated — so `metric-command-illegal` no
    longer independently fires for this exact row (guard_check's own
    never-safe-root rejection remains fully covered by the direct
    `guard_check(...)`-calling tests above, unaffected by this ordering).
    The security property this test actually cares about —
    `run_metric_command` is never invoked — is unchanged and still asserted.
    """
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    for spelling in (
        f"{_HOME}/.claude//projects/some-session/workflows",
        f"{_HOME}/.claude/./projects/some-session/workflows",
        f"{_HOME}/.claude/PROJECTS/some-session/workflows",
    ):
        row = _row(
            id="AA-0001",
            metric_command=f"ls -1 {spelling}",
            checked_at="2026-08-25",
            checked_value=0,
        )
        p = _write_ledger(tmp_path, [row])
        v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, today="2026-08-25")
        assert any("hardcoded-repo-path" in x for x in v), (spelling, v)
    assert called == []  # never actually run, for ANY of the bypass spellings


# --------------------------------------------------------------------------
# Blocker 1 (round 6 review, 2026-08-28) — THE ROOT-CAUSE FIX: a
# CASE-VARIANT spelling of ~/.claude/projects/ bypasses a `str.startswith`
# containment predicate entirely on this machine's default
# case-insensitive APFS filesystem (verified: ~/.claude/PROJECTS and
# ~/.claude/projects are the SAME INODE). Falsified end-to-end through the
# REAL check_ledger(run_live=True) execution path — not just guard_check in
# isolation — since that distinction is exactly what mattered in this
# review.
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="requires a case-insensitive filesystem volume"
)
@pytest.mark.parametrize("spelling", ["PROJECTS", "Projects", "pRoJeCtS"])
def test_guard_illegal_case_variant_never_safe_spelling(spelling: str):
    cmd = f"ls -1 {_HOME}/.claude/{spelling}"
    ok, reason = val.guard_check(cmd)
    assert not ok, f"{spelling!r} was wrongly guard-legal: {reason!r}"
    assert "never-safe" in reason


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="requires a case-insensitive filesystem volume"
)
def test_check_ledger_case_variant_never_safe_spelling_is_caught_end_to_end(
    tmp_path, monkeypatch
):
    """THE reviewer's exact repro: a case-variant spelling of the never-safe
    root, run through the FULL `check_ledger(run_live=True)` path — proving
    both that a `checked-value-mismatch` (or any other silent pass) never
    happens, AND that `run_metric_command` is never actually invoked.

    A literal never-safe-spelled path is also a `hardcoded-repo-path`
    violation, and Finding 5 (round 8 review, 2026-08-30) skips the row
    entirely before guard-legality is evaluated, so `metric-command-illegal`
    no longer ALSO fires for this row (see
    `test_never_safe_bypass_command_does_not_actually_execute`'s docstring
    for the same note) — the security property (never executed) is
    unchanged.
    """
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "20\n")
    )
    row = _row(
        id="AA-0001",
        metric_command=f"ls {_HOME}/.claude/PROJECTS",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, today="2026-08-25")
    assert not any("checked-value-mismatch" in x for x in v), v
    assert any("hardcoded-repo-path" in x for x in v), v
    assert called == []


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="requires a case-insensitive filesystem volume"
)
def test_guard_legal_mixed_case_registered_repo_root_via_identity(tmp_path):
    """A registered repo root and a candidate token that names the SAME
    directory via a different case spelling must resolve as legal via
    filesystem IDENTITY, not merely via a lucky string match."""
    real_repo = tmp_path / "RealApp"
    real_repo.mkdir()
    (real_repo / ".git").mkdir()
    (real_repo / "CLAUDE.md").write_text("hi")
    mixed_case_candidate = str(real_repo).replace("RealApp", "REALAPP") + "/CLAUDE.md"
    ok, reason = val.guard_check(f"grep -c hi {mixed_case_candidate}", repo_root=str(real_repo))
    assert ok, reason


# --------------------------------------------------------------------------
# Regression 3 (round 6 review, 2026-08-28) — this module realpaths
# `/tmp` to `/private/tmp`, while agentarch_metric_check.py does not; both
# spellings of the SAME real path must guard-legal identically once the
# comparison is filesystem-identity-based.
# --------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_PRIVATE_TMP_ALIAS, reason="requires /private/tmp (macOS)")
def test_guard_legal_tmp_and_private_tmp_spellings_are_identical():
    real_tmp = tempfile.mkdtemp(dir="/tmp")
    try:
        f = Path(real_tmp) / "haystack.txt"
        f.write_text("x\n")
        via_tmp = str(f)
        via_private_tmp = via_tmp.replace("/tmp/", "/private/tmp/", 1)
        ok1, r1 = val.guard_check(f"cat {via_tmp}")
        ok2, r2 = val.guard_check(f"cat {via_private_tmp}")
        assert ok1, r1
        assert ok2, r2
    finally:
        import shutil

        shutil.rmtree(real_tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Finding #5 (round 6 review, 2026-08-28) — `run_metric_command`'s bare
# `subprocess.run` (no shell) never expanded a `~`-prefixed token, even
# though `_paths_in_bounds` explicitly accepts one as a legal path token per
# the agent definition's own documented design. Chose EXPANSION (not
# rejection) since the agent definition's own canonical churn_report form
# is `python3 ~/.claude/hooks/churn_report.py`.
# --------------------------------------------------------------------------


def test_run_metric_command_expands_tilde_before_subprocess():
    ok, out = val.run_metric_command(["ls", "~/.claude/hooks"])
    assert ok, out
    assert "_lib.py" in out or "validate_agentarch_ledger.py" in out


def test_check_ledger_tilde_path_metric_scores_correctly_end_to_end(tmp_path):
    """Before the fix: `~/.claude/hooks` (never expanded by subprocess.run)
    read as a literal, nonexistent path; `ls` exit-1 on a missing path was
    treated as "grep no-match" success, so the metric silently scored 0
    with no visible error. After the fix, the real directory listing is
    used and the live count matches the real one."""
    real_count = len(
        [n for n in os.listdir(os.path.join(_HOME, ".claude", "hooks")) if not n.startswith(".")]
    )
    row = _row(
        id="AA-0001",
        metric_command="ls -1 ~/.claude/hooks",
        checked_at="2026-08-25",
        checked_value=real_count,
        baseline_value=real_count,
        target_direction="up",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, today="2026-08-25")
    assert not any("checked-value-mismatch" in x for x in v), v


def test_paths_in_bounds_symlink_inside_trusted_root_cannot_escape(tmp_path):
    """Blocker 5 (round 4 review, 2026-08-28): a symlink planted INSIDE an
    already-registered, trusted repo root must not be usable to escape to
    an arbitrary path outside that root — the prefix check must compare
    the REALPATH'd (symlink-resolved) candidate against the root, not the
    literal string, or `<root>/escape -> $HOME` lets any path under $HOME
    read as guard-legal."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    escape_target = tmp_path / "outside"
    escape_target.mkdir()
    secret = escape_target / "id_rsa"
    secret.write_text("secret")
    (repo_root / "escape").symlink_to(escape_target)

    ok, reason = val._paths_in_bounds([f"{repo_root}/escape/id_rsa"], str(repo_root))
    assert not ok
    assert "outside allowed roots" in reason


def test_guard_legal_real_repo_root_path_still_works_after_realpath_fix(tmp_path):
    """Regression guard: switching `_paths_in_bounds` from abspath to
    realpath must not break a perfectly legitimate path inside a
    registered (non-symlinked) repo root."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    real_file = repo_root / "README.md"
    real_file.write_text("hi")
    ok, reason = val.guard_check(f"grep -c hi {real_file}", str(repo_root))
    assert ok, reason


def test_guard_illegal_relative_path_outside_roots_when_joined_to_cwd(tmp_path, monkeypatch):
    # N13: a RELATIVE path token (no leading `/` or `~`) must resolve under
    # an allowed root once joined to the process's own cwd — the same
    # resolution `run_metric_command`'s bare `subprocess.run` actually does —
    # never a free pass just because it lacks a leading slash.
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("cat sub/file.txt")
    assert not ok
    assert "outside allowed roots" in reason


def test_guard_legal_relative_path_resolves_under_claude_root_via_cwd(monkeypatch):
    monkeypatch.chdir(os.path.join(val._HOME, ".claude", "hooks"))
    ok, reason = val.guard_check("cat tests/test_validate_agentarch_ledger.py")
    assert ok, reason


# --------------------------------------------------------------------------
# Finding 1 (round-2 security review, 2026-08-30) — the bare-word (no
# slash, no leading `~`) path exemption used to apply UNCONDITIONALLY
# across all six recognized command forms, even though the ambiguity that
# justifies it (a bare word might be a grep/rg search PATTERN, not a path)
# only exists for grep/rg. Reproduced live, pre-fix: `cat secrets.txt`,
# `wc -l secrets.txt`, `ls -l somedir`, and `jq -r .x data.json` all
# returned guard-legal with ZERO bounds-checking, while the slash-carrying
# spelling of the identical `cat` target, `cat ./secrets.txt`, was already
# correctly bounds-checked and rejected. Every RED case below chdirs to a
# fresh `tmp_path` (never under `~/.claude/` or `/tmp/` — see the existing
# `test_guard_illegal_relative_path_outside_roots_when_joined_to_cwd`'s own
# reliance on this same property) so the bare-word target has nowhere
# legal to resolve to.
# --------------------------------------------------------------------------


def test_guard_illegal_bare_word_cat_target_outside_bounds(tmp_path, monkeypatch):
    """The finding's own exact repro: `cat secrets.txt` must now be
    REJECTED, not silently pass unchecked."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("cat secrets.txt")
    assert not ok, reason
    assert "outside allowed roots" in reason


def test_guard_illegal_bare_word_wc_target_outside_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("wc -l secrets.txt")
    assert not ok, reason
    assert "outside allowed roots" in reason


def test_guard_illegal_bare_word_ls_target_outside_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("ls -l somedir")
    assert not ok, reason
    assert "outside allowed roots" in reason


def test_guard_illegal_bare_word_jq_filter_and_target_outside_bounds(tmp_path, monkeypatch):
    # CORRECTED (Blocker 2, round-3 security review, 2026-08-30): this test
    # used to assert the jq FILTER expression (`.x`) itself was correctly
    # rejected as "outside allowed roots" — that was itself the bug this
    # module's docstring documented factually wrongly: jq DOES have a
    # "pattern"-like argument (its own filter expression), structurally
    # identical in kind to grep/rg's PATTERN, and must be exempt from
    # bounds-checking the same way. Only the FILE operand (`data.json`) is
    # a real filesystem target and must still be bounds-checked and
    # rejected from an untrusted cwd.
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("jq -r .x data.json")
    assert not ok, reason
    assert "outside allowed roots" in reason
    assert "data.json" in reason
    assert ".x" not in reason


def test_guard_legal_jq_filter_alone_never_resolved_as_path(tmp_path, monkeypatch):
    """Paired assertion for the rewrite above: the filter argument itself is
    exempt from bounds-checking regardless of cwd, not merely coincidentally
    in-bounds — proven by a command with NO separate file operand at all
    (jq reading from stdin), which must stay guard-legal even chdir'd to an
    untrusted cwd. If the filter were ever resolved as a path, this would
    fail the same way `jq -r .x data.json`'s `.x` used to before Blocker 2."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("jq -r .x")
    assert ok, reason


def test_guard_illegal_bare_word_git_log_target_outside_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git log secrets.txt")
    assert not ok, reason
    assert "outside allowed roots" in reason


def test_guard_illegal_bare_word_git_show_target_outside_bounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git show secrets.txt")
    assert not ok, reason
    assert "outside allowed roots" in reason


def test_guard_illegal_bare_and_dotslash_spellings_reject_identically(tmp_path, monkeypatch):
    """The exact contrast the finding reproduced: `cat ./secrets.txt` (a
    slash-containing spelling) was ALREADY correctly bounds-checked and
    rejected before this fix; `cat secrets.txt` (the bare-word spelling of
    the IDENTICAL target) is now rejected the same way — closing the gap
    where only the slash-containing spelling was ever actually checked."""
    monkeypatch.chdir(tmp_path)
    ok_bare, reason_bare = val.guard_check("cat secrets.txt")
    ok_dotslash, reason_dotslash = val.guard_check("cat ./secrets.txt")
    assert not ok_bare, reason_bare
    assert not ok_dotslash, reason_dotslash
    assert "outside allowed roots" in reason_bare
    assert "outside allowed roots" in reason_dotslash


def test_guard_legal_bare_word_cat_target_from_trusted_cwd(monkeypatch):
    """The new bounds-check is not a blanket rejection of every bare word —
    from a cwd already under an allowed root, a bare target resolves
    cleanly, exactly as a real metric_command run from this validator's
    own trusted working directory would."""
    monkeypatch.chdir(os.path.join(val._HOME, ".claude", "hooks"))
    ok, reason = val.guard_check("cat _lib.py")
    assert ok, reason


# M4 (round-4 security review, 2026-08-30): recovery-pair coverage for `wc`
# and `ls`, mirroring `cat`'s own RED/GREEN pair immediately above and
# below — `test_guard_illegal_bare_word_wc_target_outside_bounds`/
# `..._ls_target_outside_bounds` already assert the RED half; these are
# their paired GREEN half (CLAUDE.md §6: a redirect/gate assertion needs a
# paired recoverability assertion, never a lone RED with no GREEN).


def test_guard_legal_bare_word_wc_target_from_trusted_cwd(monkeypatch):
    monkeypatch.chdir(os.path.join(val._HOME, ".claude", "hooks"))
    ok, reason = val.guard_check("wc -l _lib.py")
    assert ok, reason


def test_guard_legal_bare_word_ls_target_from_trusted_cwd(monkeypatch):
    monkeypatch.chdir(os.path.join(val._HOME, ".claude", "hooks"))
    ok, reason = val.guard_check("ls -1 tests")
    assert ok, reason


def test_guard_legal_jq_bare_filter_and_absolute_target_from_untrusted_cwd(
    tmp_path, monkeypatch
):
    """CORRECTED (Blocker 2, round-3 security review, 2026-08-30): this test
    used to chdir to a TRUSTED cwd (`~/.claude/hooks`), which made the bare
    filter `.x` coincidentally resolve in-bounds via cwd-join even though
    the pre-fix code gave it no real exemption at all — proving nothing
    about actual intent. Mirrors
    `test_guard_legal_grep_pattern_bare_word_still_exempt_even_with_untrusted_cwd`:
    the filter stays exempt from bounds-checking even chdir'd to an
    UNTRUSTED cwd, proving the filter itself is never resolved as a path.
    The file operand is a real, absolute path and is still properly
    bounds-checked — it passes here only because it names an allowed root,
    independent of cwd."""
    monkeypatch.chdir(tmp_path)  # untrusted: NOT under any allowed root
    ok, reason = val.guard_check(
        f"jq -r .x {val._HOME}/.claude/hooks/tests/test_validate_agentarch_ledger.py"
    )
    assert ok, reason


def test_guard_legal_grep_pattern_bare_word_still_exempt_even_with_untrusted_cwd(
    tmp_path, monkeypatch
):
    """The regression this fix must NOT introduce: grep/rg's actual search
    PATTERN argument (a bare word — no slash) must stay exempt from
    bounds-checking, even chdir'd to an untrusted cwd — proving the
    pattern itself is never resolved as a path at all, not merely
    coincidentally in-bounds. Without the correct index-scoped exemption,
    this quoted, multi-word pattern token (still a single bare shlex token,
    no slash) would be joined against the untrusted cwd and rejected."""
    monkeypatch.chdir(tmp_path)  # untrusted: NOT under any allowed root
    ok, reason = val.guard_check(
        f'grep -c "some search text" {val._HOME}/.claude/hooks/_lib.py'
    )
    assert ok, reason


def test_guard_legal_rg_pattern_bare_word_still_exempt_even_with_untrusted_cwd(
    tmp_path, monkeypatch
):
    # Same property via the `rg` head — `_match_form` collapses both `grep`
    # and `rg` to the same `"grep"` form name; this proves that collapse
    # doesn't lose the pattern-index alignment `_grep_pattern_rest_index`
    # depends on.
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f'rg -c "some search text" {val._HOME}/.claude/hooks/_lib.py')
    assert ok, reason


def test_guard_illegal_grep_sole_bare_argument_is_not_exempted_as_pattern(tmp_path, monkeypatch):
    """The "sole argument" shape `agentarch_metric_check.classify_tokens`
    itself deliberately does not exempt (no separate file operand follows):
    the lone bare word is a real search TARGET, not prose, per that
    function's own docstring — this module's guard must reject it the same
    way, not treat it as an exempt pattern just because it has no slash."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -l secrets.txt")
    assert not ok, reason
    assert "outside allowed roots" in reason


# --------------------------------------------------------------------------
# Blocker 1 (round-3 security review, 2026-08-30) — value-consuming flag
# ARITY: `-e`, `-n`, `--arg`, `--argjson`, `--slurpfile`, `--rawfile` all
# take a following VALUE token the guard used to have no concept of, so it
# bounds-checked that value token as a bare "path-shaped" candidate. Every
# RED case below reproduces a real live regression against an UNTRUSTED
# `tmp_path` cwd; every paired legal case proves the SAME command is
# guard-legal once the flag's value is correctly recognized as a flag
# value, not a path candidate.
# --------------------------------------------------------------------------


def test_guard_legal_aa0059_real_ledger_command_grep_dash_e_dash_e(tmp_path, monkeypatch):
    """The exact regression this blocker fixes: AA-0059's real, committed
    metric_command — `grep -c -e engine-architect -e
    vision-measurement-architect <file>` — must guard-legal from an
    UNTRUSTED cwd. Pre-fix, the SECOND `-e`'s value
    (`vision-measurement-architect`) was wrongly bounds-checked and
    rejected; the first happened to also land on `_grep_pattern_rest_index`'s
    own grep-pattern exemption and passed only by that coincidence."""
    monkeypatch.chdir(tmp_path)
    cmd = (
        "grep -c -e engine-architect -e vision-measurement-architect "
        f"{_HOME}/.claude/knowledge/model_policy.json"
    )
    ok, reason = val.guard_check(cmd)
    assert ok, reason


def test_guard_illegal_grep_dash_e_file_operand_still_bounds_checked(tmp_path, monkeypatch):
    """The security-preserving half of the same fix: a grep command's real
    FILE operand — never an `-e` value — must still be rejected from an
    untrusted cwd, proving the `-e`-value skip is scoped to exactly the
    token following `-e`, not a blanket exemption for the whole command."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -c -e engine-architect secrets.txt")
    assert not ok, reason
    assert "secrets.txt" in reason


def test_guard_legal_git_log_dash_n_numeric_value_from_untrusted_cwd(tmp_path, monkeypatch):
    """`git log -n 12` must not reject `"12"` as a path — the exact
    regression this blocker fixes for git's own value-consuming `-n`."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"git log -n 12 -- {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_illegal_git_log_file_operand_still_bounds_checked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git log -n 12 -- secrets.txt")
    assert not ok, reason
    assert "secrets.txt" in reason


def test_guard_legal_jq_arg_name_value_from_untrusted_cwd(tmp_path, monkeypatch):
    """`jq --arg k v <file>` must not reject `"k"` (the `--arg` NAME) as a
    path — the exact regression this blocker fixes for jq's own
    value-consuming `--arg`."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"jq --arg k v {_HOME}/.claude/knowledge/repo_registry.json")
    assert ok, reason


def test_guard_legal_jq_slurpfile_name_but_file_half_still_bounds_checked(
    tmp_path, monkeypatch
):
    """`--slurpfile`/`--rawfile` take NAME then FILE — two tokens. Only the
    NAME half is a flag value to skip; the FILE half is a real filesystem
    target and must stay fully bounds-checked. Proven both ways: the NAME
    is exempt (this command is otherwise guard-legal from an untrusted cwd
    once the FILE half names an allowed root)..."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"jq --slurpfile mydata {_HOME}/.claude/knowledge/repo_registry.json .x"
    )
    assert ok, reason


def test_guard_illegal_jq_slurpfile_file_half_outside_bounds_still_rejected(
    tmp_path, monkeypatch
):
    """...and (the negative control) when the FILE half names something
    outside all allowed roots, the command is still correctly rejected —
    proving the FILE half was never accidentally swept into the NAME half's
    exemption."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("jq --slurpfile mydata secrets.txt .x")
    assert not ok, reason
    assert "secrets.txt" in reason


def test_guard_illegal_jq_slurpfile_bare_file_half_with_no_filter_still_rejected(
    tmp_path, monkeypatch
):
    """A real interaction bug found WHILE WRITING this fix round's own
    falsifiability tests (not part of the task's original description): a
    naive "first non-flag, non-flag-value token" filter-detection scan
    would land on `--slurpfile`'s own FILE half when no separate filter
    token follows at all — e.g. this exact command — and wrongly exempt it
    as if it were jq's filter, silently reopening the bounds-check bypass
    Blocker 1 exists to close, one token later than `-e`/`-n`/`--arg`.
    `_jq_filter_rest_index` also excludes a two-token flag's FILE half from
    filter CANDIDACY (never from bounds-checking) to close this."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("jq --slurpfile mydata secrets.txt")
    assert not ok, reason
    assert "secrets.txt" in reason


def test_guard_legal_jq_slurpfile_bare_file_half_with_no_filter_from_trusted_root(
    monkeypatch,
):
    """Paired legal case: the identical shape above, but the FILE half
    names a real, allowed root — proving the FILE half is bounds-checked
    normally (accepted when in-bounds), not merely always rejected."""
    monkeypatch.chdir(os.path.join(val._HOME, ".claude"))
    ok, reason = val.guard_check(f"jq --slurpfile mydata {val._HOME}/.claude/hooks/_lib.py")
    assert ok, reason


# --------------------------------------------------------------------------
# ROOT-CAUSE FIX (round-4 security review, 2026-08-30) — a shared per-form
# argument-grammar table (`agentarch_metric_check.FORM_GRAMMARS`) now
# replaces the flag-allowlist + separate ad-hoc pattern/filter-index
# functions this file's own history (Blockers 1-3, round-3 review, above)
# kept patching one grammar fact at a time. B1-B5 below are the five
# blockers that review found in the pre-fix code; M1-M2 are its two
# security-relevant non-blocking findings.
# --------------------------------------------------------------------------


# B1 (CRITICAL) — THE reviewer's own confirmed working exfiltration repro:
# when grep/rg's pattern is supplied via `-e`, real grep/rg semantics
# define NO positional pattern argument at all — every remaining non-flag
# token is a FILE. Pre-fix, the first non-flag token was still wrongly
# exempted as-if-pattern regardless of `-e`'s presence, so `.env` reached
# `run_metric_command`'s real `subprocess.run` completely unchecked.


def test_guard_illegal_grep_dash_e_with_leading_bare_file_operand_B1(tmp_path, monkeypatch):
    """THE core B1 regression test: `grep -c .env -e SECRET` must now be
    REJECTED — `.env` is a real FILE operand (grep reads it), not an
    exempt "pattern", because `-e` already supplies the pattern."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -c .env -e SECRET")
    assert not ok, reason
    assert ".env" in reason


def test_guard_illegal_rg_dash_e_with_leading_bare_file_operand_B1(tmp_path, monkeypatch):
    """Same repro via the `rg` head, proving the fix is not grep-only."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("rg -c .env -e SECRET")
    assert not ok, reason
    assert ".env" in reason


def test_guard_legal_grep_dash_e_with_no_leading_operand_still_works(tmp_path, monkeypatch):
    """Regression guard: AA-0059's own shape (no leading bare operand
    before the value-consuming `-e` occurrences, just the real target file
    at the end) must still guard-legal — B1's fix must not overreach into
    rejecting a command that never had a smuggled file operand at all."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"grep -c -e engine-architect -e vision-measurement-architect "
        f"{_HOME}/.claude/knowledge/model_policy.json"
    )
    assert ok, reason


# B2 — `grep` and `rg` are now SEPARATE forms with correctly modeled,
# DIFFERENT arities: real rg's `-g GLOB`/`-r REPLACEMENT`/`-E ENCODING` are
# value-consuming (verified live against this machine's `rg` 14.1.1);
# real grep has no `-g` at all, and its own `-r`/`-E` are boolean
# (verified live against `/usr/bin/grep`).


def test_guard_legal_rg_dash_g_glob_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f'rg -c -g "*.py" foo {_HOME}/.claude/hooks')
    assert ok, reason


def test_guard_legal_rg_dash_r_replace_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"rg -c -r REPLACED foo {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_legal_rg_dash_E_encoding_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"rg -c -E utf8 foo {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_illegal_grep_dash_g_not_a_real_grep_flag(tmp_path, monkeypatch):
    """Real grep does not recognize `-g` at all (verified live: `grep -g
    foo x` → "invalid option -- g", exit 2) — must be `unlisted flag`,
    never silently accepted the way the old merged grep+rg table did."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"grep -g foo {_HOME}/.claude/hooks/_lib.py")
    assert not ok, reason
    assert "unlisted flag" in reason
    assert "'-g'" in reason


def test_guard_illegal_grep_dash_r_does_not_take_a_value(tmp_path, monkeypatch):
    """grep's own `-r` is BOOLEAN (recursive) — a value token after it is
    an ordinary positional (the search PATTERN here, in the ordinary
    no-`-e` case), never a flag value the way rg's `-r REPLACEMENT` is.
    This command is legal, but for a DIFFERENT reason than rg's `-r` case
    above: `PATTERN` is exempt as grep's own search pattern, and the real
    file operand is bounds-checked normally."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"grep -rc REPLACED {_HOME}/.claude/hooks")
    assert ok, reason


# B3 — jq's `--arg NAME VALUE`/`--argjson NAME VALUE` are now modeled as
# proper TWO-token flags (matching the already-correct `--slurpfile`/
# `--rawfile` NAME+FILE shape), with the VALUE half exempt from
# bounds-checking like a flag value (never like a FILE half).


def test_guard_legal_jq_argjson_name_and_value_from_untrusted_cwd(tmp_path, monkeypatch):
    """`jq --argjson k 5 <file>` must not reject `"k"` (NAME) or `"5"`
    (VALUE) as paths — the exact regression B3 fixes for `--argjson`."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"jq --argjson k 5 {_HOME}/.claude/knowledge/repo_registry.json")
    assert ok, reason


def test_guard_legal_jq_arg_value_does_not_swallow_the_real_filter_B3(tmp_path, monkeypatch):
    """B3's OTHER live regression (bug (a) in the task's own description): a
    single-token `--arg` model marks only the NAME half as a flag value, so
    the VALUE half ('v' here) was wrongly picked up as jq's own FILTER by
    the "first eligible non-flag token" scan, and the REAL filter
    ('.filterexpr') was left un-exempted and wrongly bounds-checked (and
    rejected, since it isn't a real path) — a false rejection of a
    perfectly legal command. Modeling `--arg`/`--argjson` as proper
    two-token flags (NAME then VALUE, both exempt) fixes this by
    construction: the VALUE half is never filter-candidate in the first
    place, so the scan correctly lands on the real filter."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"jq --arg k v .filterexpr {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_legal_jq_rawfile_name_but_file_half_still_bounds_checked(tmp_path, monkeypatch):
    """`--rawfile` NAME/FILE pair (M4 combination coverage — mirrors the
    already-covered `--slurpfile` pair below): the NAME half is exempt,
    the FILE half stays fully bounds-checked and is accepted here because
    it names a real allowed root."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"jq --rawfile mydata {_HOME}/.claude/knowledge/repo_registry.json .x"
    )
    assert ok, reason


def test_guard_illegal_jq_rawfile_file_half_outside_bounds_still_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("jq --rawfile mydata secrets.txt .x")
    assert not ok, reason
    assert "secrets.txt" in reason


# M1 — a token AT or AFTER git's own `--` end-of-options marker is a
# pathspec, NEVER flag-parsed, even one that looks exactly like a legal
# flag: `git log -- -n /etc/passwd` treats BOTH `-n` and `/etc/passwd` as
# literal pathspecs (git's own convention), never the `-n COUNT` flag.


def test_guard_illegal_git_dash_dash_then_dash_n_treated_as_pathspec_M1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git log -- -n /etc/passwd")
    assert not ok, reason


def test_guard_illegal_git_dash_dash_then_dash_n_bare_pathspec_outside_bounds(
    tmp_path, monkeypatch
):
    """Same shape, but the pathspec after `--` is the BARE `-n` token
    itself (no separate value follows it) — proves `-n` is bounds-checked
    as a real pathspec in its own right, not merely skipped as a
    `-`-prefixed token the way it would be before the `--` boundary."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git log -- -n")
    assert not ok, reason
    assert "-n" in reason


def test_guard_legal_git_dash_dash_then_dash_n_pathspec_from_trusted_root(monkeypatch):
    """Paired recovery case: the identical `-- -n <path>` shape, but the
    pathspec resolves under an allowed root — proving `-n` after `--` is
    bounds-checked normally (accepted when in-bounds), not blanket
    rejected merely for looking flag-shaped."""
    monkeypatch.chdir(val._HOME)
    ok, reason = val.guard_check("git log -- .claude/hooks/_lib.py")
    assert ok, reason


def test_guard_legal_git_dash_n_before_dash_dash_is_still_the_real_flag(tmp_path, monkeypatch):
    """Regression guard: `-n` BEFORE a `--` marker is still the real
    `-n COUNT` value-consuming flag, unaffected by M1's fix — only tokens
    AT OR AFTER `--` lose ordinary flag-parsing."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"git log -n 5 -- {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


# M2 — a flag-VALUE token that is itself absolute (`/`-leading) or
# `~`-prefixed is bounds-checked exactly like an ordinary path token, even
# though it sits in "value position" — no legitimate grep/rg PATTERN,
# git `-n` COUNT, or jq NAME/VALUE is ever spelled that way.


def test_guard_illegal_grep_dash_e_value_that_is_an_absolute_tilde_path_M2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"grep -c -e ~/.ssh/id_rsa {_HOME}/.claude/hooks/_lib.py")
    assert not ok, reason
    assert "~/.ssh/id_rsa" in reason


def test_guard_illegal_git_dash_n_value_that_is_a_path_shaped_string_M2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"git log -n {_HOME}/.ssh/id_rsa -- {_HOME}/.claude/hooks/_lib.py")
    assert not ok, reason
    assert "id_rsa" in reason


def test_guard_illegal_jq_arg_name_that_is_an_absolute_path_M2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"jq --arg {_HOME}/.ssh/id_rsa v {_HOME}/.claude/knowledge/repo_registry.json"
    )
    assert not ok, reason
    assert "id_rsa" in reason


def test_guard_illegal_rg_dash_g_value_that_is_an_absolute_path_M2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"rg -c -g {_HOME}/.ssh/id_rsa foo {_HOME}/.claude/hooks/_lib.py")
    assert not ok, reason
    assert "id_rsa" in reason


def test_guard_legal_flag_value_absolute_path_case_when_it_resolves_in_bounds(monkeypatch):
    """M2's fix is a shape-triggered BOUNDS CHECK, not a blanket rejection
    of every absolute/`~` flag value — one that happens to resolve under
    an allowed root is accepted, exactly like any other in-bounds path
    token."""
    monkeypatch.chdir(val._HOME)
    ok, reason = val.guard_check(
        f"git log -n {val._HOME}/.claude/hooks -- {val._HOME}/.claude/hooks/_lib.py"
    )
    assert ok, reason


def test_guard_illegal_flag_value_traversal_token_caught_before_after_M2(tmp_path, monkeypatch):
    """M2 requires the `..`-traversal check to run alongside (never after)
    the flag-value shape gate: a flag value that is BOTH absolute AND
    carries a `..` segment must still be rejected as a traversal, not
    merely as "outside allowed roots"."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"grep -c -e {_HOME}/.claude/hooks/../../etc/passwd secret.txt")
    assert not ok, reason
    assert "traversal" in reason


# --------------------------------------------------------------------------
# ROOT-CAUSE FIX (round-5 security review, 2026-08-30) — a WORKING,
# CONFIRMED arbitrary-file-read exploit in the round-4 design above: two
# composed defects. (a) THE ORDERING BUG — `_paths_in_bounds`' flag-value
# shape gate (M2) ran BEFORE the `..`-traversal check, so a RELATIVE
# traversal token in flag-value position (no leading `/`/`~`) skipped the
# shape gate entirely and was never traversal-checked at all — the gate
# only ever caught an ABSOLUTE/`~`-prefixed flag value. (b)
# THE SCANNING BUG — `agentarch_metric_check.flag_value_indices` (removed
# this round) scanned for value-consuming flag STRING occurrences
# independently, not via real left-to-right consumption, so `-e -e X` let
# the SECOND `-e` (really the FIRST `-e`'s own VALUE) be wrongly
# re-classified as ANOTHER flag needing its own value, exempting `X`.
# Confirmed working, pre-fix: both exploit commands below were guard-legal
# AND actually executed by `run_metric_command`, reading real `/etc/hosts`
# and enumerating real `/etc/ssh` content. Zero prior test coverage existed
# for the entire "phantom flag in value position" combination class — every
# case below is new.
# --------------------------------------------------------------------------


def test_guard_illegal_grep_dash_e_dash_e_traversal_EXPLOIT(tmp_path, monkeypatch):
    """THE reviewer's own first confirmed working exploit repro, verbatim:
    pre-fix, this was guard-legal and `run_metric_command` actually read
    real `/etc/hosts` content."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -c -e -e ../../../etc/hosts")
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_grep_rl_dash_e_dash_e_traversal_EXPLOIT(tmp_path, monkeypatch):
    """THE reviewer's own second confirmed working exploit repro, verbatim
    (the `-rl` cluster variant): pre-fix, this was guard-legal AND
    `run_metric_command` actually recursively enumerated real `/etc/ssh`
    content."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -rl -e -e ../../../etc/ssh")
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_rg_dash_e_dash_e_traversal(tmp_path, monkeypatch):
    """Same doubled-value-consuming-flag shape via the `rg` head, proving
    the consumption fix is not grep-only."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("rg -c -e -e ../../../etc/hosts")
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_rg_dash_g_dash_g_traversal(tmp_path, monkeypatch):
    """Same combination class via rg's OWN value-consuming `-g GLOB` flag —
    a different flag than `-e`, proving the consumption fix is general, not
    hardcoded to one flag letter."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("rg -c -g -g ../../../etc/passwd")
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_git_log_dash_n_dash_n_traversal(tmp_path, monkeypatch):
    """Same combination class via git log's own value-consuming `-n COUNT`
    flag."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("git log -n -n ../../../etc/passwd")
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_jq_arg_dash_arg_traversal(tmp_path, monkeypatch):
    """Same combination class via jq's own two-token `--arg NAME VALUE`
    flag — the doubled `--arg` supplies a relative traversal token as the
    FIRST `--arg`'s own VALUE half, exercising `flag_value_shape_needs_
    bounds_check`'s `..` clause on an arity-2 flag's SECOND consumed token,
    not just an arity-1 flag's single value."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"jq --arg --arg ../../../etc/passwd .filterexpr {_HOME}/.claude/hooks/_lib.py"
    )
    assert not ok, reason
    assert "traversal" in reason


def test_guard_illegal_grep_dash_e_relative_traversal_value_not_doubled(tmp_path, monkeypatch):
    """The relative-`..`-in-flag-value-position case SPECIFICALLY, distinct
    from the already-tested absolute/`~`-prefixed case
    (`test_guard_illegal_flag_value_traversal_token_caught_before_after_M2`
    above) and distinct from the doubled-flag scanning-bug cases above —
    THIS is defect (a) in complete isolation, with only ONE `-e` occurrence
    at all: pre-fix, `flag_value_shape_needs_bounds_check`'s predecessor
    only checked for a leading `/`/`~`, so a RELATIVE traversal token here
    (no leading slash) skipped the shape gate and reached the traversal
    check post-exemption, never actually running it."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -c -e ../../../etc/passwd secret.txt")
    assert not ok, reason
    assert "traversal" in reason


# Paired GREEN recovery half (CLAUDE.md §6: a RED gate assertion needs a
# paired recoverability assertion) — the SAME doubled-value-consuming-flag
# SHAPE as the exploit tests above, but with ordinary, non-traversal values:
# proves the consumption fix does not overreach into rejecting a
# legitimate doubled flag, only the traversal shape.


def test_guard_legal_rg_dash_e_dash_e_no_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"rg -c -e engine-architect -e vision-measurement-architect {_HOME}/.claude/knowledge/model_policy.json"
    )
    assert ok, reason


def test_guard_legal_rg_dash_g_dash_g_no_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f'rg -c -g "*.py" -g "*.md" foo {_HOME}/.claude/hooks')
    assert ok, reason


def test_guard_legal_git_log_dash_n_dash_n_no_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(f"git log -n 5 -n 12 -- {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


def test_guard_legal_jq_arg_dash_arg_no_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        f"jq --arg k1 v1 --arg k2 v2 {_HOME}/.claude/knowledge/repo_registry.json"
    )
    assert ok, reason


# --------------------------------------------------------------------------
# BLOCKER 1 (round-7 security review, 2026-08-30) — companion END-TO-END
# coverage for `agentarch_metric_check.classify_tokens`' own falsifying
# direct unit tests (see that module's test file, same section title, for
# the pure/cwd-independent assertions on `classify_tokens` itself). The
# reviewer's own confirmed mutation (adding `and tokens[i] not in
# grammar.flags` to the value-consumption condition) reopens the doubled-
# value-consuming-flag desync bug for a PLAIN relative bare filename — no
# `..`, no leading `/`/`~` — a shape neither `flag_value_shape_needs_
# bounds_check` nor any other traversal/absolute-path check ever catches,
# so ONLY a correctly-consuming scan classifies it as the real FILE operand
# it is. Every EXISTING doubled-flag test in this file (the `_EXPLOIT`
# class above) uses a `..`-traversal payload instead, which the shape gate
# catches regardless of whether the consuming scan itself works — proving
# only the composed symptom is fixed, never the mechanism: all 258 tests
# in this file and agentarch_metric_check's own test file still passed
# against the exact mutation described above.
#
# CRITICAL: `tmp_path` is deliberately NOT used as the untrusted cwd here,
# unlike most of this file's other tests. `tmp_path` resolves under this
# process's system temp directory (`tempfile.gettempdir()`), which on
# macOS is `$TMPDIR` — a per-user `/private/var/folders/.../T/...` path,
# NOT `/private/tmp` — but on many other platforms (bare Linux with no
# `TMPDIR`/`TEMP`/`TMP` env var set, the common case on a CI runner)
# `tempfile.gettempdir()` falls back to `/tmp` directly, which IS
# `_TMP_ROOT`, one of the two hardcoded always-safe roots
# (`_ALWAYS_SAFE_ROOTS`) `path_resolves_under_root` treats as always
# in-bounds. A relative bare-word FILE target resolved against a
# `tmp_path`-under-`/tmp` cwd would pass the bounds check even under
# CORRECT code (it genuinely IS inside an allowed root) — the RED/GREEN
# transition this test needs to prove would be invisible on any platform
# where that fallback applies, an environment-DEPENDENT false negative,
# not a real pass. `_HOME` is used instead: guaranteed to exist on every
# platform, and — being the home directory itself, never `~/.claude` nor
# `/tmp` — provably outside both always-safe roots regardless of platform
# or `TMPDIR` state.
# --------------------------------------------------------------------------


def test_guard_illegal_grep_dash_e_dash_e_plain_bare_filename_BLOCKER1(monkeypatch):
    """THE reviewer's own first exact demonstrated repro (verbatim, `-c`
    lead flag): must stay REFUSED. Under the described mutation, the second
    `-e` is reclassified as its own `FLAG` (never consumed as the first
    `-e`'s value), so `secret.txt` becomes THAT flag's own value —
    exempt from bounds-checking via `flag_value_shape_needs_bounds_check`'s
    shape gate purely because it doesn't look like a path — and this would
    wrongly return `ok=True`."""
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("grep -c -e -e secret.txt")
    assert not ok, reason
    assert "secret.txt" in reason


def test_guard_illegal_grep_rl_dash_e_dash_e_plain_bare_filename_BLOCKER1(monkeypatch):
    """THE reviewer's own second exact demonstrated repro, verbatim (the
    `-rl` cluster lead-flag variant)."""
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("grep -rl -e -e secretdir")
    assert not ok, reason
    assert "secretdir" in reason


def test_guard_illegal_rg_dash_e_dash_e_plain_bare_filename_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("rg -c -e -e secret.txt")
    assert not ok, reason
    assert "secret.txt" in reason


def test_guard_illegal_rg_dash_g_dash_g_plain_bare_filename_BLOCKER1(monkeypatch):
    """rg's OWN value-consuming `-g GLOB` flag (a different letter than
    `-e`), proving the consumption fix is general, not hardcoded to one
    flag."""
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("rg -c -g -g secretfile.txt")
    assert not ok, reason
    assert "secretfile.txt" in reason


def test_guard_illegal_rg_dash_r_dash_r_plain_bare_filename_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("rg -c -r -r secretfile.txt")
    assert not ok, reason
    assert "secretfile.txt" in reason


def test_guard_illegal_rg_dash_E_dash_E_plain_bare_filename_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("rg -c -E -E secretfile.txt")
    assert not ok, reason
    assert "secretfile.txt" in reason


def test_guard_illegal_git_log_dash_n_dash_n_plain_bare_filename_BLOCKER1(monkeypatch):
    """git log's own value-consuming `-n COUNT` flag — git has no
    positional-role exemption at all, so this isolates the consuming-scan
    mechanism from the grep/rg pattern-role logic entirely."""
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check("git log -n -n secretfile.txt")
    assert not ok, reason
    assert "secretfile.txt" in reason


# Paired GREEN recovery half (CLAUDE.md §6): the SAME doubled-value-
# consuming-flag SHAPE, from the SAME untrusted `_HOME` cwd, with an
# ordinary (non-flag-spelled) value plus a real, allowed-root FILE operand
# — proves the fix does not overreach into rejecting a legitimate doubled
# flag from this cwd, only the "second value happens to textually spell a
# flag" shape.


def test_guard_legal_grep_dash_e_dash_e_ordinary_value_from_home_cwd_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check(
        f"grep -c -e enginearchitect -e visionarchitect {_HOME}/.claude/knowledge/model_policy.json"
    )
    assert ok, reason


def test_guard_legal_rg_dash_g_dash_g_ordinary_value_from_home_cwd_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check(f'rg -c -g "*.py" -g "*.md" foo {_HOME}/.claude/hooks')
    assert ok, reason


def test_guard_legal_git_log_dash_n_dash_n_ordinary_value_from_home_cwd_BLOCKER1(monkeypatch):
    monkeypatch.chdir(_HOME)
    ok, reason = val.guard_check(f"git log -n 5 -n 12 -- {_HOME}/.claude/hooks/_lib.py")
    assert ok, reason


# --------------------------------------------------------------------------
# Blocker 3 (round-3 security review, 2026-08-30) — real combination-
# coverage gap: the reviewer mutated `if form == "grep" and idx ==
# grep_pattern_index:` to `if form == "grep" and grep_pattern_index is not
# None:` (re-opening the bare-word bypass for EVERY token of any grep
# command that has a pattern) and every test in this file still passed —
# a `grep -c PATTERN barefile.md`-shaped command (covering the majority of
# the ledger's 47 real, non-empty live rows — NIT 1, round-5 security
# review, 2026-08-30, correcting a fabricated "60+ of the 67" count that
# never matched the real ledger, which has always had 47 non-empty rows,
# AA-0001 through AA-0047: verify with `grep -c . knowledge/
# agentarch_recommendations.jsonl`) had zero coverage of its own
# non-pattern bare FILE operand actually being bounds-checked.
# --------------------------------------------------------------------------


def test_guard_illegal_grep_bare_file_operand_is_bounds_checked(tmp_path, monkeypatch):
    """Must kill the reviewer's exact described mutation: with the mutation
    applied, `grep_pattern_index is not None` is True for THIS command (it
    has a real pattern), so EVERY bare token — including the bare FILE
    operand `secrets.txt` — would be wrongly exempted and this would return
    `ok=True`. The unmutated code exempts ONLY the token at the pattern's
    own index; the file operand at a different index must still be
    rejected, named in the reason, not the pattern."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check("grep -c somepattern secrets.txt")
    assert not ok, reason
    assert "secrets.txt" in reason
    assert "somepattern" not in reason


def test_guard_legal_churn_report_numeric_flag_value_exempt_even_with_untrusted_cwd(
    tmp_path, monkeypatch
):
    """churn_report's own flag spec (the agent definition's Read-FIRST #4:
    `--days N`, `--json` only) never defines a path-shaped positional
    argument at all — its one legal non-flag token is `--days`'s own
    NUMERIC value, never a filesystem target `run_metric_command` would
    read. Unlike the five forms Finding 1 actually targets (which each
    read an arbitrary caller-named path), there is no path for this form
    to ever smuggle, so it correctly stays exempt regardless of cwd."""
    monkeypatch.chdir(tmp_path)
    ok, reason = val.guard_check(
        "python3 ~/.claude/hooks/churn_report.py --days 30 --json"
    )
    assert ok, reason


def test_guard_legal_churn_report_days_and_json():
    ok, reason = val.guard_check(
        "python3 ~/.claude/hooks/churn_report.py --days 30 --json"
    )
    assert ok, reason


def test_guard_illegal_churn_report_unlisted_flag():
    ok, reason = val.guard_check("python3 ~/.claude/hooks/churn_report.py --unsafe")
    assert not ok
    assert "unlisted flag" in reason


def test_guard_illegal_shlex_parse_failure():
    ok, reason = val.guard_check('grep -c "unclosed quote /tmp/x')
    assert not ok
    assert "unparseable" in reason


def test_guard_illegal_empty_command():
    ok, reason = val.guard_check("")
    assert not ok


def test_guard_legal_git_log_form():
    ok, reason = val.guard_check(
        f"git log -n 5 --oneline -- {_HOME}/.claude/hooks/_lib.py"
    )
    assert ok, reason


def test_guard_illegal_git_forbidden_flag():
    ok, reason = val.guard_check(f"git log --output=/tmp/x -- {_HOME}/.claude/hooks")
    assert not ok
    assert "unlisted flag" in reason


def test_guard_illegal_jq_from_file():
    ok, reason = val.guard_check("jq -f /tmp/prog.jq /tmp/data.json")
    assert not ok
    assert "unlisted flag" in reason


def test_guard_legal_ls_and_cat_no_flags():
    ok1, r1 = val.guard_check(f"ls -la {_HOME}/.claude/hooks")
    assert ok1, r1
    ok2, r2 = val.guard_check(f"cat {_HOME}/.claude/hooks/_lib.py")
    assert ok2, r2


def test_guard_illegal_cat_with_any_flag():
    ok, reason = val.guard_check(f"cat -n {_HOME}/.claude/hooks/_lib.py")
    assert not ok
    assert "unlisted flag" in reason


# the exact AA-0009 stored command: legal grep with an odd-but-valid quoting.
def test_guard_legal_aa0009_actual_command():
    cmd = f'grep -c "git\\" in seg" {_HOME}/.claude/hooks/_lib.py'
    ok, reason = val.guard_check(cmd)
    assert ok, reason


# --------------------------------------------------------------------------
# validate_row — RED per class + clean
# --------------------------------------------------------------------------


def test_validate_row_clean_returns_empty():
    assert val.validate_row(_row(), 1) == []


def test_validate_row_not_a_dict():
    v = val.validate_row("nope", 3)
    assert len(v) == 1 and "not a JSON object" in v[0]


def test_validate_row_missing_field():
    row = _row()
    del row["metric"]
    v = val.validate_row(row, 1)
    assert any(x.startswith("line 1: field-set") and "missing" in x for x in v)


def test_validate_row_extra_field():
    row = _row()
    row["bogus"] = 1
    v = val.validate_row(row, 1)
    assert any(x.startswith("line 1: field-set") and "extra" in x for x in v)


def test_validate_row_field_order_wrong():
    row = _row()
    reordered = {"issued_at": row["issued_at"], "id": row["id"]}
    for k in val.CANONICAL_FIELDS:
        if k not in reordered:
            reordered[k] = row[k]
    v = val.validate_row(reordered, 1)
    assert any(x.startswith("line 1: field-order") for x in v)


def test_validate_row_id_format_bad():
    v = val.validate_row(_row(id="not-an-id"), 1)
    assert any(x.startswith("line 1: id-format") for x in v)


def test_validate_row_id_sequence_mismatch():
    v = val.validate_row(_row(id="AA-0001"), 2)
    assert any(x.startswith("line 2: id-sequence") for x in v)


def test_validate_row_id_sequence_matches_line():
    v = val.validate_row(_row(id="AA-0002"), 2)
    assert not any(x.startswith("id-sequence") or "id-sequence" in x for x in v)


def test_validate_row_bad_issued_at():
    v = val.validate_row(_row(issued_at="08/25/2026"), 1)
    assert any(x.startswith("line 1: date-format") and "issued_at" in x for x in v)


def test_validate_row_bad_checked_at_when_not_null():
    v = val.validate_row(_row(checked_at="not-a-date", checked_value=1), 1)
    assert any(x.startswith("line 1: date-format") and "checked_at" in x for x in v)


def test_validate_row_status_no_change_gets_specific_message():
    v = val.validate_row(_row(status="no-change"), 1)
    hits = [x for x in v if "status-domain" in x]
    assert len(hits) == 1
    assert "REPORT-TABLE-only" in hits[0]


def test_validate_row_status_bogus_generic_message():
    v = val.validate_row(_row(status="bogus"), 1)
    hits = [x for x in v if "status-domain" in x]
    assert len(hits) == 1
    assert "REPORT-TABLE-only" not in hits[0]


def test_validate_row_direction_bad():
    v = val.validate_row(_row(target_direction="sideways"), 1)
    assert any(x.startswith("line 1: direction-domain") for x in v)


def test_validate_row_baseline_value_bool_rejected():
    v = val.validate_row(_row(baseline_value=True), 1)
    assert any(x.startswith("line 1: value-type") and "baseline_value" in x for x in v)


def test_validate_row_checked_value_non_numeric_rejected():
    v = val.validate_row(_row(checked_at="2026-08-25", checked_value="17"), 1)
    assert any(x.startswith("line 1: value-type") and "checked_value" in x for x in v)


def test_validate_row_checked_pairing_value_without_at():
    v = val.validate_row(_row(checked_at=None, checked_value=5), 1)
    assert any(x.startswith("line 1: checked-pairing") for x in v)


def test_validate_row_checked_pairing_at_without_value():
    v = val.validate_row(_row(checked_at="2026-08-25", checked_value=None), 1)
    assert any(x.startswith("line 1: checked-pairing") for x in v)


def test_validate_row_checked_pairing_both_set_is_clean():
    v = val.validate_row(_row(checked_at="2026-08-25", checked_value=0), 1)
    assert not any("checked-pairing" in x for x in v)


def test_validate_row_null_baseline_is_valid_absent_convention():
    v = val.validate_row(_row(baseline_value=None), 1)
    assert not any("value-type" in x and "baseline_value" in x for x in v)


# --------------------------------------------------------------------------
# _interpret_output
# --------------------------------------------------------------------------


def test_interpret_output_grep_c_is_literal_count():
    assert val._interpret_output(["grep", "-c", "x", "/f"], "3\n") == "3"


def test_interpret_output_wc_l_is_leading_field():
    assert val._interpret_output(["wc", "-l", "/f"], "  17 /f\n") == "17"


def test_interpret_output_list_style_counts_nonempty_lines():
    tokens = ["grep", "-rl", "x", "/dir"]
    assert val._interpret_output(tokens, "/a\n/b\n/c\n") == "3"


def test_interpret_output_empty_stdout_is_zero():
    assert val._interpret_output(["grep", "-c", "x", "/f"], "") == "0"
    assert val._interpret_output(["grep", "-rl", "x", "/dir"], "") == "0"


def test_drop_noise_paths_filters_conventional_cache_dirs():
    lines = [
        f"{_HOME}/.claude/hooks/real.py",
        f"{_HOME}/.claude/hooks/__pycache__/real.cpython-313.pyc",
        f"{_HOME}/.claude/hooks/.pytest_cache/v/cache/nodeids",
        f"{_HOME}/.claude/hooks/.ruff_cache/0.1/abc",
        f"{_HOME}/.claude/hooks/tests/other.py",
    ]
    kept = val._drop_noise_paths(lines)
    assert kept == [
        f"{_HOME}/.claude/hooks/real.py",
        f"{_HOME}/.claude/hooks/tests/other.py",
    ]


def test_interpret_output_list_style_excludes_noise_dirs():
    tokens = ["grep", "-rl", "heartbeat", "/dir"]
    stdout = (
        f"{_HOME}/.claude/hooks/real.py\n"
        f"{_HOME}/.claude/hooks/__pycache__/real.cpython-313.pyc\n"
        f"{_HOME}/.claude/hooks/.pytest_cache/v/cache/nodeids\n"
    )
    assert val._interpret_output(tokens, stdout) == "1"


def test_interpret_output_count_mode_is_not_noise_filtered():
    # -c mode's output is already a bare integer, never a path list; the
    # noise filter must never touch it.
    assert val._interpret_output(["grep", "-c", "x", "/f"], "5\n") == "5"


# --------------------------------------------------------------------------
# check_ledger — clean, RED, and live-comparison behavior
# --------------------------------------------------------------------------


def test_check_ledger_clean_fixture_zero_violations(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="AA-0001")])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert v == []


def test_check_ledger_two_row_sequence_clean(tmp_path):
    second = _row(
        id="AA-0002",
        metric_command=f"wc -l {_HOME}/.claude/hooks/_lib.py",
    )
    p = _write_ledger(tmp_path, [_row(id="AA-0001"), second])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert v == []


def test_check_ledger_duplicate_id_flagged(tmp_path):
    p = _write_ledger(tmp_path, [_row(id="AA-0001"), _row(id="AA-0001")])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert any("id-duplicate" in x for x in v)


def test_check_ledger_json_parse_error_flagged(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text('{"id": "AA-0001", not json\n')
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert any("json-parse-error" in x for x in v)


def test_check_ledger_illegal_command_flagged_and_never_run(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(
        val,
        "run_metric_command",
        lambda *a, **k: called.append(1) or (True, "0\n"),
    )
    row = _row(
        id="AA-0001",
        metric_command="curl evil.example.com",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True)
    assert any("metric-command-illegal" in x for x in v)
    assert called == []  # refused, never run


def test_check_ledger_missing_metric_command_flagged(tmp_path):
    row = _row(id="AA-0001")
    del row["metric_command"]
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert any("metric-command-missing" in x for x in v)


def test_check_ledger_run_live_false_skips_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(val, "run_metric_command", lambda *a, **k: (True, "999\n"))
    p = _write_ledger(
        tmp_path,
        [_row(id="AA-0001", checked_at="2026-08-25", checked_value=1)],
    )
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert not any("checked-value-mismatch" in x for x in v)


def _live_score_repo(tmp_path: Path, filename: str, content: str) -> tuple[Path, Path]:
    # Registered and referenced via ${REPO:<slug>} (round 8 review,
    # 2026-08-30), not a literal tmp_path command legalized only via
    # extra_repo_root: after Finding 5's fix, a metric_command hardcoding a
    # bare absolute path outside the always-safe roots is UNCONDITIONALLY
    # skipped (never live-rescored) regardless of whether extra_repo_root
    # also happens to legalize it — a literal tmp_path path is never under
    # ~/.claude/ or /tmp/, so these live-rescore tests would otherwise be
    # vacuously "passing" without actually exercising the rescore logic.
    d = tmp_path / "target"
    d.mkdir(exist_ok=True)
    _make_registrable_repo(d)
    (d / filename).write_text(content)
    registry = _write_registry(tmp_path, {"livescoretarget": str(d)})
    return d, registry


def test_check_ledger_live_growth_in_direction_is_clean(tmp_path):
    # B4: a live-appending `up` metric growing further than its stored
    # checked_value is equal-or-better-in-direction — NOT flagged as needing
    # re-score (the exact real-world case AA-0007's own metric describes: "a
    # re-run moments later may read one more; that is expected, not drift").
    _d, registry = _live_score_repo(tmp_path, "haystack.txt", "needle\nneedle\nneedle\n")
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=1,  # live count has GROWN to 3 — up direction, clean
        baseline_value=1,
        target_direction="up",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-25", registry_path=str(registry)
    )
    assert not any("checked-value-mismatch" in x for x in v), v


def test_check_ledger_live_regression_against_up_direction_flagged(tmp_path):
    # B4: the live value DROPPED below the stored checked_value on an `up`
    # metric — that is a real regression against target_direction — RED.
    _d, registry = _live_score_repo(tmp_path, "haystack.txt", "needle\n")
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=3,  # live count has DROPPED to 1 — against target_direction=up
        baseline_value=1,
        target_direction="up",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-25", registry_path=str(registry)
    )
    hits = [x for x in v if "checked-value-mismatch" in x]
    assert len(hits) == 1, v
    assert "'1'" in hits[0]
    assert "target_direction=up" in hits[0]


def test_check_ledger_live_regression_against_down_direction_flagged(tmp_path):
    # B4: the live value ROSE above the stored checked_value on a `down`
    # metric (lower is better) — regression against target_direction — RED.
    _d, registry = _live_score_repo(tmp_path, "haystack.txt", "needle\nneedle\nneedle\n")
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=1,  # live count has RISEN to 3 — against target_direction=down
        baseline_value=1,
        target_direction="down",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-25", registry_path=str(registry)
    )
    hits = [x for x in v if "checked-value-mismatch" in x]
    assert len(hits) == 1, v
    assert "'3'" in hits[0]
    assert "target_direction=down" in hits[0]


def test_check_ledger_live_fell_below_baseline_flagged_even_if_not_below_checked(tmp_path):
    # B4's second clause: even when the live value is still >= the last
    # checked_value (so the first, direction-vs-checked test alone would miss
    # it), falling back past the original baseline_value is still a real
    # regression on an `up` metric.
    _d, registry = _live_score_repo(tmp_path, "haystack.txt", "needle\n" * 6)
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=5,  # live count is 6, >= checked_value(5) -- fine so far
        baseline_value=10,  # but 6 < baseline_value(10) -- fell back past baseline
        target_direction="up",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-25", registry_path=str(registry)
    )
    hits = [x for x in v if "checked-value-mismatch" in x]
    assert len(hits) == 1, v
    assert "baseline_value" in hits[0]


def test_check_ledger_live_match_is_clean(tmp_path):
    _d, registry = _live_score_repo(tmp_path, "haystack.txt", "needle\nneedle\n")
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=2,
        baseline_value=2,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, registry_path=str(registry))
    assert not any("checked-value-mismatch" in x for x in v), v


def test_check_ledger_live_no_match_grep_exit1_is_not_a_run_failure(tmp_path):
    _d, registry = _live_score_repo(tmp_path, "empty.txt", "nothing here\n")
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:livescoretarget}/empty.txt",
        checked_at="2026-08-25",
        checked_value=0,
        baseline_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, registry_path=str(registry))
    assert not any("metric-command-run-failed" in x for x in v), v
    assert not any("checked-value-mismatch" in x for x in v), v


def test_check_ledger_unreadable_ledger_path(tmp_path):
    v = val.check_ledger(str(tmp_path / "nope.jsonl"), run_live=False)
    assert len(v) == 1 and v[0].startswith("ledger-unreadable")


# --------------------------------------------------------------------------
# multi-root extra_repo_root (AA-0040) — RED without the fix: only ONE root
# could be supplied, so a second app's ledger rows were permanently illegal
# --------------------------------------------------------------------------


def test_guard_legal_path_under_second_of_two_roots(tmp_path):
    # Machine-independent fixture (Regression 4, this fix round): this used
    # to assert against real paths `~/Desktop/ExampleApp` and
    # `~/Desktop/OtherApp`, which only passed because those directories
    # happen to exist on this operator's machine — `path_resolves_under_root`
    # (this diff's own containment test) requires a root to actually EXIST
    # on disk, unlike the old string-comparison code it replaced. Two
    # synthetic, registrable tmp_path repos reproduce the identical shape
    # (a path under the SECOND of two roots) on any machine.
    first_root = tmp_path / "FirstApp"
    first_root.mkdir()
    _make_registrable_repo(first_root)
    second_root = tmp_path / "SecondApp"
    (second_root / ".claude" / "agents").mkdir(parents=True)
    target = second_root / ".claude" / "agents" / "freya.md"
    target.write_text("x")
    _make_registrable_repo(second_root)
    ok, reason = val.guard_check(
        f"grep -c x {target}",
        repo_root=[str(first_root), str(second_root)],
    )
    assert ok, reason


def test_guard_illegal_path_outside_both_roots():
    ok, reason = val.guard_check(
        f"grep -c x {_HOME}/Desktop/Elsewhere/f.md",
        repo_root=[
            f"{_HOME}/Desktop/ExampleApp",
            f"{_HOME}/Desktop/OtherApp",
        ],
    )
    assert not ok
    assert "outside allowed roots" in reason


def test_guard_single_string_root_still_accepted(tmp_path):
    # Backward compatibility: every pre-existing caller passes one str.
    # Machine-independent fixture (Regression 4, this fix round) — see
    # test_guard_legal_path_under_second_of_two_roots's comment above for
    # why a real `~/Desktop/ExampleApp` path is no longer safe to
    # assert against.
    root = tmp_path / "SomeApp"
    root.mkdir()
    _make_registrable_repo(root)
    target = root / "CLAUDE.md"
    target.write_text("seven\n")
    ok, reason = val.guard_check(
        f"grep -c seven {target}",
        repo_root=str(root),
    )
    assert ok, reason


def test_main_passes_every_trailing_argv_as_a_root(tmp_path, monkeypatch):
    seen: dict = {}

    def fake_check(path, extra_repo_root, run_live, today):
        seen["roots"] = list(extra_repo_root)
        return []

    monkeypatch.setattr(val, "check_ledger", fake_check)
    rc = val.main(["prog", str(tmp_path / "l.jsonl"), "/r/one", "/r/two"])
    assert rc == 0
    assert seen["roots"] == ["/r/one", "/r/two"]


def test_main_with_no_roots_falls_back_to_default(tmp_path, monkeypatch):
    seen: dict = {}

    def fake_check(path, extra_repo_root, run_live, today):
        seen["roots"] = extra_repo_root
        return []

    monkeypatch.setattr(val, "check_ledger", fake_check)
    val.main(["prog", str(tmp_path / "l.jsonl")])
    # No baked-in product path (item 3 of the AA-ledger repo-agnosticism fix):
    # the default is None — every registered repo root comes from
    # check_ledger's own registry lookup, never from a hardcoded constant.
    assert seen["roots"] is None


# --------------------------------------------------------------------------
# ${REPO:<slug>} placeholder resolution — RED without the fix: an unresolved
# placeholder token (which contains a literal '/') was treated as a real
# path by guard_check's bounds check (coincidentally passing or failing
# depending on the process's cwd) and then failed at execution with a
# literal "No such file or directory" — every migrated ledger row using the
# placeholder form was permanently unmeasurable.
# --------------------------------------------------------------------------


def test_check_ledger_resolves_known_repo_placeholder_before_run(tmp_path):
    d = tmp_path / "target"
    d.mkdir()
    f = d / "haystack.txt"
    f.write_text("needle\nneedle\n")
    _make_registrable_repo(d)
    registry = _write_registry(tmp_path, {"myrepo": str(d)})
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:myrepo}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=2,
        baseline_value=2,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, registry_path=str(registry))
    assert v == [], v


def test_check_ledger_unknown_repo_slug_is_a_distinct_violation_and_never_runs(tmp_path, monkeypatch):
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    # A REAL registrable repo, not a bare "/tmp" (test-quality fix, round 8
    # review, 2026-08-30): "/tmp" has no `.git` entry, so `load_registry`
    # silently drops it — the registry this test wrote never actually
    # contained "otherrepo" at all, making this test exercise "empty
    # registry" (already covered elsewhere) rather than what its name
    # claims: a registry containing a DIFFERENT repo than the one the row
    # references.
    other = tmp_path / "OtherRepo"
    other.mkdir()
    _make_registrable_repo(other)
    registry = _write_registry(tmp_path, {"otherrepo": str(other)})
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:ghost}/haystack.txt",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, registry_path=str(registry))
    hits = [x for x in v if "metric-command-unknown-repo-slug" in x]
    assert len(hits) == 1, v
    assert "AA-0001" in hits[0]
    assert "ghost" in hits[0]
    assert called == []  # refused, never run


def test_check_ledger_unresolved_placeholder_never_reaches_guard_check(tmp_path, monkeypatch):
    # The exact ordering the fix requires: resolution happens BEFORE the
    # bounds/guard check, so an unresolved placeholder never reaches
    # guard_check at all (never coincidentally passes it via a cwd quirk).
    called: list[int] = []
    monkeypatch.setattr(val, "guard_check", lambda *a, **k: called.append(1) or (True, ""))
    row = _row(id="AA-0001", metric_command="grep -c needle ${REPO:ghost}/haystack.txt")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=None,
        run_live=False,
        registry_path=str(tmp_path / "no_such_registry.json"),
    )
    assert any("metric-command-unknown-repo-slug" in x for x in v), v
    assert called == []


def test_check_ledger_multiple_unknown_slugs_each_get_their_own_violation(tmp_path):
    row = _row(
        id="AA-0001",
        metric_command="grep -c needle ${REPO:ghost1}/f1.txt ${REPO:ghost2}/f2.txt",
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=None,
        run_live=False,
        registry_path=str(tmp_path / "no_such_registry.json"),
    )
    hits = [x for x in v if "metric-command-unknown-repo-slug" in x]
    assert len(hits) == 2, v
    assert any("ghost1" in x for x in hits)
    assert any("ghost2" in x for x in hits)


def test_check_ledger_row_without_placeholder_unaffected_by_missing_registry(tmp_path):
    row = _row(id="AA-0001")  # default metric_command has no placeholder
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=None,
        run_live=False,
        registry_path=str(tmp_path / "no_such_registry.json"),
    )
    assert v == []


def test_check_ledger_registered_repo_root_is_an_allowed_bounds_root_with_no_extra_repo_root(tmp_path):
    # The exact regression this fix closes: a placeholder resolves to a
    # path OUTSIDE ~/.claude/ and /tmp/, and the registry's own entry for
    # that slug must be enough, on its own, to satisfy guard_check's bounds
    # check — no separately-supplied extra_repo_root should be required.
    d = tmp_path / "target"
    d.mkdir()
    f = d / "haystack.txt"
    f.write_text("needle\n")
    _make_registrable_repo(d)
    registry = _write_registry(tmp_path, {"myrepo": str(d)})
    row = _row(id="AA-0001", metric_command="grep -c needle ${REPO:myrepo}/haystack.txt")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False, registry_path=str(registry))
    assert v == [], v


def test_check_ledger_extra_repo_root_and_registry_roots_are_unioned_not_replaced(tmp_path):
    # A caller-supplied extra_repo_root must not silently drop the
    # registry's own roots (which would resurrect the exact regression for
    # every OTHER registered repo's placeholder-based row). The extra root
    # here is a REAL, existing, unrelated directory (not the fictitious
    # nonexistent path this test used before Blocker 2, round 8 review,
    # 2026-08-30 — a nonexistent extra root is now itself rejected and
    # reported, so a legitimate "prove the union" fixture needs a real one).
    d = tmp_path / "target"
    d.mkdir()
    f = d / "haystack.txt"
    f.write_text("needle\n")
    _make_registrable_repo(d)
    registry = _write_registry(tmp_path, {"myrepo": str(d)})
    unrelated_extra = tmp_path / "unrelated_extra"
    unrelated_extra.mkdir()
    # Finding 1 (round-2 security review, 2026-08-30): extra_repo_root now
    # requires a `.git` entry too (matching `load_registry`'s own long-
    # standing requirement), so this "prove the union" fixture needs a real
    # repo checkout, not merely an existing directory, or it would itself
    # get dropped and reported (`extra-repo-root-rejected`), breaking this
    # test's `v == []` assertion for an unrelated reason.
    _make_registrable_repo(unrelated_extra)
    row = _row(id="AA-0001", metric_command="grep -c needle ${REPO:myrepo}/haystack.txt")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=str(unrelated_extra),
        run_live=False,
        registry_path=str(registry),
    )
    assert v == [], v


# --------------------------------------------------------------------------
# Blocker 2 (round 8 review, 2026-08-30) — the CLI/extra_repo_root path was
# the UNVALIDATED producer of the allowed-execution-roots set: `load_registry`
# already runs every registry-sourced root through `_is_overbroad_root`, but
# `main()`'s trailing CLI args reached `check_ledger(extra_repo_root=...)`
# with no equivalent check at all, so `~`, `$HOME`, an ancestor of `$HOME`,
# or `/` all reached `guard_check` as LEGAL bounds-check roots — defeating
# the entire point of validating the registry side.
# --------------------------------------------------------------------------


def _overbroad_extra_roots() -> list[str]:
    return ["~", _HOME, os.path.dirname(_HOME), "/"]


@pytest.mark.parametrize("overbroad_root", _overbroad_extra_roots())
def test_check_ledger_overbroad_extra_repo_root_never_reaches_guard_legal(tmp_path, overbroad_root, monkeypatch):
    # A RELATIVE path token (round 8 review, 2026-08-30 — an absolute one
    # like `cat ~/.ssh/id_rsa` would ALSO trip the independent, unrelated
    # hardcoded-repo-path check and be skipped for THAT reason before ever
    # reaching guard-legality, masking whether Blocker 2's own root
    # validation did anything at all: `find_hardcoded_paths` only scans
    # absolute tokens, so a relative one is the one shape that isolates
    # this specific fix). With cwd chdir'd to $HOME, the relative token
    # `.ssh/id_rsa` is ONLY guard-legal if some root in the allowed set
    # covers all of $HOME — the exact live repro from the review.
    monkeypatch.chdir(_HOME)
    row = _row(
        id="AA-0001",
        metric_command="cat .ssh/id_rsa",
        status="withdrawn",
        checked_at=None,
        checked_value=None,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=overbroad_root, run_live=False)
    assert any("metric-command-illegal" in x for x in v), (overbroad_root, v)
    assert any("extra-repo-root-rejected" in x for x in v), (overbroad_root, v)


def test_check_ledger_overbroad_extra_repo_root_never_actually_executes(tmp_path, monkeypatch):
    monkeypatch.chdir(_HOME)
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    row = _row(
        id="AA-0001",
        metric_command="cat .ssh/id_rsa",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root="~", run_live=True, today="2026-08-25")
    assert any("metric-command-illegal" in x for x in v), v
    assert called == []


def test_check_ledger_non_overbroad_extra_repo_root_still_works(tmp_path):
    # Regression guard: the new validation must not reject a legitimate,
    # non-overbroad extra root (the common case every pre-existing caller
    # relies on) — checked narrowly (no `extra-repo-root-rejected` finding),
    # not via `v == []`, since a literal tmp_path command is independently
    # (and correctly) flagged hardcoded-repo-path regardless of this check.
    # Marked as a real repo checkout (Finding 1, round-2 security review,
    # 2026-08-30 — extra_repo_root now also requires a `.git` entry, so a
    # plain existing directory is no longer enough to prove this case).
    d = tmp_path / "target"
    d.mkdir()
    f = d / "haystack.txt"
    f.write_text("needle\n")
    _make_registrable_repo(d)
    row = _row(id="AA-0001", metric_command=f"grep -c needle {f}")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=str(d), run_live=False)
    assert not any("extra-repo-root-rejected" in x for x in v), v


def test_check_ledger_nonexistent_extra_repo_root_is_dropped_and_reported(tmp_path):
    row = _row(id="AA-0001")  # default metric_command needs no extra root at all
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=str(tmp_path / "does_not_exist_at_all"),
        run_live=False,
    )
    assert any("extra-repo-root-rejected" in x for x in v), v


# --------------------------------------------------------------------------
# Finding 1 (round-2 security review, 2026-08-30) — Blocker 2 above ported
# the overbroad+isdir half of `load_registry`'s acceptance test to the
# CLI-extra-root path, but not the `.git`-presence half: an existing,
# non-overbroad, but non-repo directory (e.g. `~/.ssh`) was still accepted
# as a legal bounds-check root. Reproduced live:
# `extra_repo_root=os.path.expanduser("~/.ssh")` was accepted with zero
# violations and a `cat .ssh/id_rsa`-shaped command actually ran. Both
# producers now share one helper (`agentarch_metric_check.root_is_acceptable`)
# so this cannot drift apart again.
# --------------------------------------------------------------------------


def test_check_ledger_no_git_extra_repo_root_never_reaches_guard_legal(tmp_path, monkeypatch):
    # A RELATIVE command token CONTAINING a slash (mirroring
    # test_check_ledger_overbroad_extra_repo_root_never_reaches_guard_legal's
    # own reasoning) isolates this specific check from the unrelated
    # hardcoded-repo-path scan, which only ever inspects absolute tokens —
    # an absolute path under tmp_path would otherwise be independently (and
    # correctly) flagged hardcoded-repo-path and skipped before guard-check
    # is ever reached, masking whether this fix did anything at all. (A
    # bare word with no slash, e.g. plain `secret.txt`, would isolate this
    # check equally well SINCE Finding 1, round-2 security review,
    # 2026-08-30 — `cat`'s bare-word path exemption was narrowed to only
    # grep/rg's own pattern argument, see `_paths_in_bounds`'s docstring —
    # but this fixture predates that fix and a slash-containing token
    # isolates it regardless of which bare-word rule is in effect, so it is
    # left as-is rather than churned for no behavioral reason.)
    plain_dir = tmp_path / "NotARepo"
    (plain_dir / "sub").mkdir(parents=True)
    (plain_dir / "sub" / "secret.txt").write_text("secret\n")
    monkeypatch.chdir(plain_dir)
    row = _row(
        id="AA-0001",
        metric_command="cat sub/secret.txt",
        status="withdrawn",
        checked_at=None,
        checked_value=None,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=str(plain_dir), run_live=False)
    assert any("metric-command-illegal" in x for x in v), v
    assert any("extra-repo-root-rejected" in x for x in v), v


def test_check_ledger_no_git_extra_repo_root_never_actually_executes(tmp_path, monkeypatch):
    plain_dir = tmp_path / "NotARepo"
    (plain_dir / "sub").mkdir(parents=True)
    (plain_dir / "sub" / "secret.txt").write_text("secret\n")
    monkeypatch.chdir(plain_dir)
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    row = _row(
        id="AA-0001",
        metric_command="cat sub/secret.txt",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=str(plain_dir), run_live=True, today="2026-08-25"
    )
    assert any("metric-command-illegal" in x for x in v), v
    assert called == []  # never actually run


# --------------------------------------------------------------------------
# Blocker 1 (this fix round) — a REGISTRY entry `load_registry` rejects
# (overbroad / nonexistent / no `.git`) used to be structurally
# unreportable: `load_registry` returned a bare dict with no channel to
# name what it dropped, so a rejected registry entry that NO ledger row
# happened to reference produced ZERO violations — contradicting
# `schedules/prompts/daily_sweep.txt`'s and `commands/sweep.md`'s own
# documented claim that such an entry "is dropped and reported as its own
# `extra-repo-root-rejected` violation, never silently accepted." This is
# the falsifiability fixture for that fix: a registry with one good slug
# and one no-`.git` slug must produce exactly one `extra-repo-root-rejected`
# violation naming the bad slug, even though the ledger's own row never
# references it at all.
# --------------------------------------------------------------------------


def test_check_ledger_rejected_registry_entry_is_reported_even_when_unreferenced(tmp_path):
    good = tmp_path / "GoodApp"
    good.mkdir()
    _make_registrable_repo(good)
    bad = tmp_path / "NotARepo"
    bad.mkdir()  # no .git entry — load_registry rejects this one
    registry = _write_registry(tmp_path, {"goodapp": str(good), "badapp": str(bad)})
    # The ledger's sole row references NEITHER slug — proving the violation
    # fires purely from the rejected registry entry, not from some row
    # incidentally naming it (which, before this fix, was the ONLY way a
    # rejection could ever surface, as `unknown-repo-slug`).
    row = _row(id="AA-0001")  # default metric_command has no placeholder at all
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False, registry_path=str(registry))
    hits = [x for x in v if "extra-repo-root-rejected" in x]
    assert len(hits) == 1, v
    assert "badapp" in hits[0]
    assert "goodapp" not in hits[0]
    assert ".git" in hits[0]


# --------------------------------------------------------------------------
# Finding 2 (round-2 security review, 2026-08-30) — a whitespace-containing
# registry root was dropped from `registry` (correct — see
# `agentarch_metric_check.load_registry`'s own docstring for the
# shlex-mis-tokenization hazard this prevents) but NOT added to
# `rejections` either, unlike the other three rejection reasons
# (overbroad/nonexistent/no-`.git`) — so it silently violated this same
# codebase's own unqualified "never silently accepted" promise whenever no
# ledger row happened to reference the exact slug. This is the
# falsifiability fixture proving `load_registry`'s fix reaches all the way
# through `check_ledger` to a real `extra-repo-root-rejected` violation
# line — the identical shape as
# `test_check_ledger_rejected_registry_entry_is_reported_even_when_unreferenced`
# above, for this fourth rejection reason.
# --------------------------------------------------------------------------


def test_check_ledger_whitespace_registry_entry_is_reported_even_when_unreferenced(tmp_path):
    good = tmp_path / "GoodApp"
    good.mkdir()
    _make_registrable_repo(good)
    registry = _write_registry(
        tmp_path,
        {"goodapp": str(good), "spacey": str(tmp_path / "My App")},
    )
    # The ledger's sole row references NEITHER slug — proving the violation
    # fires purely from the rejected registry entry, exactly like the
    # no-`.git` fixture above, not from some row incidentally naming it.
    row = _row(id="AA-0001")  # default metric_command has no placeholder at all
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False, registry_path=str(registry))
    hits = [x for x in v if "extra-repo-root-rejected" in x]
    assert len(hits) == 1, v
    assert "spacey" in hits[0]
    assert "goodapp" not in hits[0]
    assert "whitespace" in hits[0]


# --------------------------------------------------------------------------
# hardcoded-repo-path (Blocker D, 2026-08-28) — RED without the fix: a
# metric_command that hardcodes a bare absolute product-repo path (never
# expressed via ${REPO:<slug>}) passed this validator silently; only
# agentarch_metric_check.py's own, separately-invoked CLI caught it. This
# validator must catch it too, on the RAW command (so a legitimate
# ${REPO:<slug>} placeholder's substituted-in root is never mistaken for a
# hardcoded one), regardless of the row's `status`.
# --------------------------------------------------------------------------


def test_check_ledger_RED_on_planted_hardcoded_repo_path(tmp_path):
    row = _row(
        id="AA-0001",
        metric_command=f"grep -c x {_HOME}/Desktop/OtherApp/CLAUDE.md",
        status="withdrawn",
        checked_at=None,
        checked_value=None,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    hits = [x for x in v if "hardcoded-repo-path" in x]
    assert len(hits) == 1, v
    assert "AA-0001" in hits[0]
    assert f"{_HOME}/Desktop/OtherApp/CLAUDE.md" in hits[0]


def test_check_ledger_hardcoded_repo_path_fires_regardless_of_status():
    """The check is not gated on `status: open` — a withdrawn/moved row's
    metric_command is a permanent record in the file and must not be
    allowed to carry a dangling hardcoded-path landmine either."""
    for status in ("open", "moved", "withdrawn"):
        row = _row(
            id="AA-0001",
            metric_command=f"cat {_HOME}/Desktop/SomeApp/CLAUDE.md",
            status=status,
            checked_at=None,
            checked_value=None,
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ledger.jsonl"
            p.write_text(json.dumps(row) + "\n")
            v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
        assert any("hardcoded-repo-path" in x for x in v), (status, v)


def test_check_ledger_GREEN_placeholder_form_is_never_flagged_as_hardcoded(tmp_path):
    d = tmp_path / "target"
    d.mkdir()
    (d / "haystack.txt").write_text("needle\n")
    _make_registrable_repo(d)
    registry = _write_registry(tmp_path, {"myrepo": str(d)})
    row = _row(id="AA-0001", metric_command="grep -c needle ${REPO:myrepo}/haystack.txt")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False, registry_path=str(registry))
    assert not any("hardcoded-repo-path" in x for x in v), v


def test_check_ledger_session_scoped_projects_path_is_flagged_hardcoded(tmp_path, monkeypatch):
    """Blocker E: a path under ~/.claude/projects/ is not automatically
    safe just because it lives under ~/.claude/ — a metric_command must
    not be able to hide a real product-repo reference inside a session
    transcript directory.

    Blocker 5 (round 3 review, 2026-08-28) originally required this row to
    ALSO be independently guard-illegal, so its command is never actually
    run. Finding 5 (round 8 review, 2026-08-30) makes that guarantee
    STRONGER, not weaker: a hardcoded-repo-path violation now skips the row
    UNCONDITIONALLY, before guard-legality is even evaluated — so
    `metric-command-illegal` no longer independently fires for this row
    (guard_check's own never-safe-root rejection remains directly covered
    by the `guard_check(...)`-calling tests elsewhere in this file). The
    actual security property — never executed — is asserted directly here
    via a mocked `run_metric_command`, which is a stronger proof than the
    previous version's reliance on `metric-command-illegal`'s mere
    presence.
    """
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    row = _row(
        id="AA-0001",
        metric_command=(
            'grep -rl "[stall] agent" '
            f"{_HOME}/.claude/projects/-Users-x-Desktop-ExampleApp/"
            "884000b8-293a-4be7-9ae6-85b2be304047/workflows"
        ),
        status="open",
        checked_at="2026-08-25",
        checked_value=0,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=True, today="2026-08-25")
    assert any("hardcoded-repo-path" in x for x in v), v
    assert called == []


# --------------------------------------------------------------------------
# Finding 4 (round 8 review, 2026-08-30) — a row carrying BOTH an unknown
# ${REPO:<slug>} AND a separate hardcoded path used to only ever report the
# unknown-slug violation (the hardcoded-path scan ran AFTER the unknown-slug
# early `continue`), silently dropping the second finding — while
# `agentarch_metric_check.check_ledger` correctly reports BOTH for the
# identical input, contradicting this module's own docstring claim that it
# reimplements the same guard.
# --------------------------------------------------------------------------


def test_check_ledger_unknown_slug_and_hardcoded_path_both_reported(tmp_path):
    row = _row(
        id="AA-0001",
        metric_command=(
            f"grep -c x ${{REPO:ghostslug}}/CLAUDE.md {_HOME}/Desktop/OtherApp/other.txt"
        ),
        status="withdrawn",
        checked_at=None,
        checked_value=None,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert any("metric-command-unknown-repo-slug" in x and "ghostslug" in x for x in v), v
    assert any(
        "hardcoded-repo-path" in x and f"{_HOME}/Desktop/OtherApp/other.txt" in x for x in v
    ), v


def test_check_ledger_unknown_slug_and_hardcoded_path_matches_agentarch_metric_check(tmp_path):
    # Cross-module parity: the same raw command must produce the same TWO
    # violation classes from both check_ledger implementations.
    import agentarch_metric_check as chk

    command = f"grep -c x ${{REPO:ghostslug}}/CLAUDE.md {_HOME}/Desktop/OtherApp/other.txt"
    row = _row(id="AA-0001", metric_command=command, status="withdrawn", checked_at=None, checked_value=None)
    p = _write_ledger(tmp_path, [row])

    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    other_violations = chk.check_ledger(str(p), str(tmp_path / "no_such_registry.json"))

    assert any("metric-command-unknown-repo-slug" in x for x in v)
    assert any("hardcoded-repo-path" in x for x in v)
    assert any("unknown-repo-slug" in x for x in other_violations)
    assert any("hardcoded-repo-path" in x for x in other_violations)


# --------------------------------------------------------------------------
# Finding 5 (round 8 review, 2026-08-30) — the most serious of this round: a
# metric_command already CLASSIFIED as a hardcoded-repo-path violation was
# still being EXECUTED whenever it happened to ALSO be guard-legal (e.g. a
# literal path that coincides with an already-registered repo's own root),
# directly contradicting this module's own docstring guarantee that
# execution is gated by the SAME bounds check, not merely reported
# separately.
# --------------------------------------------------------------------------


def test_check_ledger_hardcoded_path_row_never_reaches_run_metric_command(tmp_path, monkeypatch):
    called: list[int] = []
    monkeypatch.setattr(
        val, "run_metric_command", lambda *a, **k: called.append(1) or (True, "0\n")
    )
    d = tmp_path / "target"
    d.mkdir()
    f = d / "haystack.txt"
    f.write_text("needle\n")
    _make_registrable_repo(d)
    registry = _write_registry(tmp_path, {"myrepo": str(d)})
    # The literal, hardcoded spelling of the SAME path the registry would
    # also accept as a bounds-check root — guard-legal on its own terms,
    # but flagged hardcoded-repo-path because it is never expressed via
    # ${REPO:<slug>}. Must never actually run.
    row = _row(
        id="AA-0001",
        metric_command=f"grep -c needle {f}",
        checked_at="2026-08-25",
        checked_value=1,
    )
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p),
        extra_repo_root=str(d),
        run_live=True,
        today="2026-08-25",
        registry_path=str(registry),
    )
    assert any("hardcoded-repo-path" in x for x in v), v
    assert called == []  # flagged AND executed must never both be true


# --------------------------------------------------------------------------
# score-or-withdraw (AA-0039) — RED without the fix: an open row with
# checked_at null was skipped forever, so the newest claims were the only
# ones never checked
# --------------------------------------------------------------------------


def _never_scored_row(tmp_path: Path, issued_at: str) -> tuple[Path, dict, Path]:
    # Registered as a real repo checkout and referenced via ${REPO:<slug>}
    # (round 8 review, 2026-08-30) rather than a literal tmp_path command
    # legalized only via extra_repo_root: after Finding 5's fix, ANY
    # metric_command that hardcodes a bare absolute path outside the
    # always-safe roots is now UNCONDITIONALLY skipped (never executed,
    # never live-rescored), regardless of whether extra_repo_root also
    # happens to legalize it — a literal tmp_path path is never under
    # ~/.claude/ or /tmp/, so it would always trip that check. Using the
    # placeholder form is what a real, correctly-migrated ledger row does,
    # and is what actually exercises the live-rescore/never-scored logic
    # these tests are about.
    d = tmp_path / "target"
    d.mkdir(exist_ok=True)
    _make_registrable_repo(d)
    f = d / "haystack.txt"
    f.write_text("needle\nneedle\n")
    registry = _write_registry(tmp_path, {"scoretarget": str(d)})
    row = _row(
        id="AA-0001",
        issued_at=issued_at,
        metric_command="grep -c needle ${REPO:scoretarget}/haystack.txt",
    )
    return d, row, registry


def test_check_ledger_open_row_never_scored_past_grace_is_flagged_with_live_value(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")  # 57 days > 35-day grace
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    hits = [x for x in v if "never-scored" in x]
    assert len(hits) == 1, v
    assert "AA-0001" in hits[0]
    assert "open 57 days" in hits[0]
    assert "live value now 2" in hits[0]  # scorer can record it without re-running


def test_check_ledger_open_row_within_grace_is_not_flagged(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "2026-08-25")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_check_ledger_open_row_exactly_at_grace_is_not_flagged(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-23")  # 35 days == grace, not past it
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_check_ledger_withdrawn_row_never_scored_is_not_flagged(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    row["status"] = "withdrawn"
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_check_ledger_moved_row_with_null_check_is_not_never_scored(tmp_path):
    # The other half of the `status != "open"` predicate: a moved row is
    # already an outcome; its (invalid) null pairing is validate_row's finding.
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    row["status"] = "moved"
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_check_ledger_half_null_pair_is_a_pairing_defect_not_never_scored(tmp_path):
    # checked_at SET, checked_value null: validate_row's checked-pairing
    # violation owns this; the never-scored branch must not claim
    # "checked_at null" about a row whose checked_at is present.
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    row["checked_at"] = "2026-08-01"
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v
    assert any("checked-pairing" in x for x in v), v


def test_check_ledger_reverse_half_null_pair_is_a_pairing_defect_not_never_scored(tmp_path):
    # The MIRROR orientation: checked_at null, checked_value SET. Same rule —
    # one defect, one (pairing) violation; never-scored must not double-report
    # a row that has a recorded value.
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    row["checked_value"] = 2
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v
    assert any("checked-pairing" in x for x in v), v


def test_check_ledger_never_scored_malformed_issued_at_is_skipped_not_crashed(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "not-a-date")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v
    assert any("date-format" in x for x in v), v  # validate_row still reports it


def test_check_ledger_never_scored_reports_unavailable_when_command_fails(tmp_path, monkeypatch):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    p = _write_ledger(tmp_path, [row])
    monkeypatch.setattr(val, "run_metric_command", lambda *a, **k: (False, "exit 2: boom"))
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today="2026-08-27", registry_path=str(registry)
    )
    hits = [x for x in v if "never-scored" in x]
    assert len(hits) == 1, v
    assert "live value now UNAVAILABLE" in hits[0]


def test_check_ledger_never_scored_needs_today_to_age(tmp_path):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    p = _write_ledger(tmp_path, [row])
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=True, today=None, registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_check_ledger_never_scored_not_run_when_run_live_false(tmp_path, monkeypatch):
    d, row, registry = _never_scored_row(tmp_path, "2026-07-01")
    p = _write_ledger(tmp_path, [row])

    def _must_not_run(*_a, **_k):
        raise AssertionError("run_metric_command ran with run_live=False")

    monkeypatch.setattr(val, "run_metric_command", _must_not_run)
    v = val.check_ledger(
        str(p), extra_repo_root=None, run_live=False, today="2026-08-27", registry_path=str(registry)
    )
    assert not any("never-scored" in x for x in v), v


def test_as_roots_edge_cases():
    assert val._as_roots(None) == []
    assert val._as_roots("") == []
    assert val._as_roots([]) == []
    assert val._as_roots("/one") == ["/one"]
    assert val._as_roots(("/one", "/two")) == ["/one", "/two"]
    assert val._as_roots(["/one", "", "/two"]) == ["/one", "/two"]  # empties dropped


def test_check_ledger_blank_lines_skipped(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text(json.dumps(_row(id="AA-0001")) + "\n\n\n")
    v = val.check_ledger(str(p), extra_repo_root=None, run_live=False)
    assert v == []


def test_check_ledger_real_tmp_root_is_allowed():
    # /tmp is an explicitly allowed root regardless of extra_repo_root; use a
    # real /tmp directory (pytest's tmp_path is NOT under literal /tmp on
    # macOS) to exercise that branch specifically.
    real_tmp = tempfile.mkdtemp(dir="/tmp")
    try:
        f = Path(real_tmp) / "haystack.txt"
        f.write_text("x\nx\n")
        ok, reason = val.guard_check(f"grep -c x {f}", repo_root=None)
        assert ok, reason
    finally:
        f.unlink(missing_ok=True)
        Path(real_tmp).rmdir()


# --------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------


def test_main_exit_zero_on_clean_ledger(tmp_path):
    # tmp_path is passed as a trailing extra-root CLI arg purely to exercise
    # that plumbing; marked as a real repo checkout (Finding 1, round-2
    # security review, 2026-08-30 — extra_repo_root now also requires a
    # `.git` entry) so it doesn't itself become an unrelated violation.
    (tmp_path / ".git").mkdir()
    # main() ages every open row against the WALL CLOCK (never-scored grace,
    # NEVER_SCORED_GRACE_DAYS), so a fixture row with a fixed issued_at turns
    # this "clean" ledger into a violation once the calendar passes the grace
    # window (measured 2026-10-12: a 2026-08-25 row was 48 days old, exit 1).
    # Issue the row today so the case stays the clean-ledger case on any date.
    p = _write_ledger(tmp_path, [_row(id="AA-0001", issued_at=date.today().isoformat())])
    rc = val.main([str(val.__file__), str(p), str(tmp_path)])
    assert rc == 0


def test_main_exit_one_on_aged_never_scored_open_row(tmp_path, capsys):
    # Pair of the test above: main() really does pass the wall-clock date down,
    # so an open row older than the grace window with no score fails the run.
    # Without this, dropping `today=` from main() would leave the clean-ledger
    # case green for the wrong reason.
    (tmp_path / ".git").mkdir()
    issued = (date.today() - timedelta(days=val.NEVER_SCORED_GRACE_DAYS + 10)).isoformat()
    p = _write_ledger(tmp_path, [_row(id="AA-0001", issued_at=issued)])
    rc = val.main([str(val.__file__), str(p), str(tmp_path)])
    assert rc == 1
    assert "never-scored" in capsys.readouterr().out


def test_main_exit_one_on_dirty_ledger(tmp_path, capsys):
    # Issued today so the ONLY violation is the structural one under test --
    # with a fixed, now-aged issued_at this exit 1 would also come from the
    # never-scored grace check and pass for the wrong reason.
    row = _row(id="AA-0001", issued_at=date.today().isoformat())
    del row["metric"]
    p = _write_ledger(tmp_path, [row])
    rc = val.main([str(val.__file__), str(p), str(tmp_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "field-set: missing ['metric']" in out
    assert "never-scored" not in out


def test_main_subprocess_reports_and_matches_return_code(tmp_path):
    row = _row(id="AA-0001", status="no-change")
    p = _write_ledger(tmp_path, [row])
    proc = subprocess.run(
        [sys.executable, str(Path(val.__file__)), str(p), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1
    assert "status-domain" in proc.stdout
    assert "violation(s)" in proc.stdout


# --------------------------------------------------------------------------
# live-tree run against the real ledger
# --------------------------------------------------------------------------


# The agentarch ledger is a PER-MACHINE file: a fresh install does not ship it,
# `scripts/init_repo.sh` seeds it from `templates/knowledge/` into
# `<claude dir>/knowledge/` when absent (covered by test_init_repo.py). The
# fixture uses the real ledger when it exists (the runtime: unchanged
# behavior) and otherwise performs the same copy init_repo.sh performs, into a
# sandbox home under pytest's tmp_path -- never into the real home -- so the
# live-tree tests validate the shipped seed instead of dying on a missing file.

_SEED_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "knowledge" / "agentarch_recommendations.jsonl"
)


@pytest.fixture
def live_ledger_path(tmp_path):
    real = Path(val.DEFAULT_LEDGER_PATH)
    if real.is_file():
        return str(real)
    if not _SEED_TEMPLATE.is_file():
        pytest.skip(
            f"no ledger at {real} and no seed template at {_SEED_TEMPLATE} "
            "to stand in for it (init_repo.sh seeds the ledger from that template)"
        )
    seeded = tmp_path / "home" / ".claude" / "knowledge" / "agentarch_recommendations.jsonl"
    seeded.parent.mkdir(parents=True)
    shutil.copyfile(_SEED_TEMPLATE, seeded)
    return str(seeded)


def test_live_tree_ledger_field_schema_is_clean(live_ledger_path):
    # Structural schema (field set/order, id sequence, domains, pairing) must
    # be clean on the real ledger today, independent of any live re-score
    # mismatch a concurrent edit elsewhere might introduce.
    with open(live_ledger_path, encoding="utf-8") as fh:
        lines = fh.readlines()
    structural: list[str] = []
    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        structural.extend(val.validate_row(row, i))
    assert structural == []


def test_live_tree_smoke_run_static_only_does_not_crash(live_ledger_path):
    v = val.check_ledger(live_ledger_path, run_live=False)
    assert isinstance(v, list)
