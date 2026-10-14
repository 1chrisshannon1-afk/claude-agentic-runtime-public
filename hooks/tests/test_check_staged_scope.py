"""Hermetic tests for hooks/check_staged_scope.py.

check_staged_scope is a PreToolUse:Bash guard that inspects the ACTUAL git index
before a `git commit` and blocks commits that would sweep files outside the
change's declared scope. git_guard.sh (the ported source) blocks the bulk
STAGERS by reading the command string; those vectors are reproduced here against
this module's command-inspection helpers (is_git_commit / commit_message /
pathspec / scope), then the pure decide() and the index-reading main() are
exercised to >=90% line coverage.

All tests run against the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir) so the real ~/.claude is never touched; the only git ever run is
in throwaway repos created by the `git_repo` fixture (offline, no network).
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import check_staged_scope as css
import pytest

# ===========================================================================
# is_git_commit — reuses _lib.git_segments; reproduce git_guard's tokenizer
# handling of compound/pipe/subshell forms, but keyed on the `commit` verb.
# ===========================================================================


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git commit -m 'x'", True),
        ('git commit -m "a message"', True),
        ("git commit -am 'x'", True),  # -am still a commit (git_guard blocks -a)
        ("git commit --message=x", True),
        ("git -C /repo commit -m x", True),  # global -C stripped
        ("GIT_DIR=x git commit -m x", True),  # leading env stripped
        ("git status && git commit -m x", True),  # compound: commit segment
        ("echo hi | git commit -m x", True),  # pipe boundary
        ("git commit --dry-run", False),  # dry-run writes nothing
        ("git commit -m x --dry-run", False),
        ("git status", False),
        ("git add file.py", False),
        ("git push origin HEAD", False),
        ("ls -la", False),
        ("gitfoo commit -m x", False),  # argv0 basename not git
        ("echo git commit is words", False),  # 'commit' not a git subcommand here
        ("", False),
    ],
)
def test_is_git_commit(command, expected):
    assert css.is_git_commit(command) is expected


def test_is_git_commit_bare_git_no_subcommand():
    assert css.is_git_commit("git") is False
    assert css.is_git_commit("git -C /x") is False


def test_untokenizable_real_commit_stays_conservatively_unguarded_by_this_gate():
    # #4670 item 3b mandatory blast-radius test: an untokenizable segment
    # that IS a genuine (word-boundary) git invocation must keep yielding an
    # EMPTY writing_commit_segments()/is_git_commit()==False here, exactly as
    # before the word-boundary fix -- pretooluse_bash.py's own docs (the
    # "untokenizable sentinel -> writing_commit_segments == []" chain) rely
    # on this gate NOT silently starting to guard an unparseable commit; the
    # command is caught upstream by gate 1 (block_branch_ops) instead, which
    # is what keeps this conservative fall-through safe. The word-boundary
    # change must not turn the sentinel segment into something this gate's
    # own `seg[1] == "commit"` check would ever match.
    command = "git commit -m 'unterminated"
    assert css.writing_commit_segments(command) == []
    assert css.is_git_commit(command) is False


def test_untokenizable_git_substring_only_segment_also_stays_unguarded():
    # The companion case: an untokenizable segment whose ONLY "git"-like text
    # is a substring inside a longer word ("legitimate") is now dropped
    # entirely by _lib.git_segments (no sentinel at all, post-fix) rather
    # than becoming a false-positive sentinel -- either way this gate's own
    # consumers must see no commit segment.
    command = "echo 'legitimate value"
    assert css.writing_commit_segments(command) == []
    assert css.is_git_commit(command) is False


# ===========================================================================
# commit_message — extract the -m / --message value.
# ===========================================================================


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git commit -m 'hello world'", "hello world"),
        ('git commit -m "feat(voice): x"', "feat(voice): x"),
        ("git commit --message 'the msg'", "the msg"),
        ("git commit --message=inline", "inline"),
        ("git commit -m", ""),  # -m with no value
        ("git commit --amend --no-edit", ""),  # no message flag
        ("git commit", ""),
        ("git status", ""),  # not a commit
    ],
)
def test_commit_message(command, expected):
    assert css.commit_message(command) == expected


# ===========================================================================
# commit_pathspec — explicit `git commit -- <paths>`.
# ===========================================================================


def test_commit_pathspec_extracts_paths_after_dashdash():
    assert css.commit_pathspec("git commit -m x -- a.py b.py") == ["a.py", "b.py"]


def test_commit_pathspec_none_when_no_dashdash():
    assert css.commit_pathspec("git commit -m x") == []


def test_commit_pathspec_empty_after_dashdash():
    assert css.commit_pathspec("git commit -m x --") == []


def test_commit_pathspec_not_a_commit():
    assert css.commit_pathspec("git status") == []


# ===========================================================================
# scope_from_message — conventional-commit scope token.
# ===========================================================================


@pytest.mark.parametrize(
    "message,expected",
    [
        ("feat(voice): route to opus", "voice"),
        ("fix(estimate-status): stamp", "estimate-status"),
        ("refactor(api/routes): tidy", "api/routes"),  # slashed scope kept whole
        ("feat!(voice): breaking", None),  # '!' before paren is not conventional
        ("feat(voice)!: breaking", "voice"),  # '!' after paren is allowed
        ("fix: no scope here", None),
        ("chore: bump", None),
        ("just a free-form subject", None),
        ("feat(): empty scope", None),
        ("", None),
        ("docs(readme): update", "readme"),
    ],
)
def test_scope_from_message(message, expected):
    assert css.scope_from_message(message) == expected


# ===========================================================================
# path helpers — top_dir, _normalize, _scope_matches.
# ===========================================================================


@pytest.mark.parametrize(
    "path,expected",
    [
        ("modules/voice/x.py", "modules"),
        ("./modules/voice/x.py", "modules"),  # leading ./ stripped
        ("README.md", ""),  # root file -> no top dir
        ("a/b/c", "a"),
        ("  spaced/path  ", "spaced"),
    ],
)
def test_top_dir(path, expected):
    assert css.top_dir(path) == expected


def test_normalize_strips_repeated_dot_slash():
    assert css._normalize("././modules/x.py") == "modules/x.py"
    assert css._normalize("  ./a.py ") == "a.py"


@pytest.mark.parametrize(
    "path,scope,expected",
    [
        ("modules/voice/x.py", "voice", True),  # segment match
        ("modules/estimate/x.py", "voice", False),
        ("voice/x.py", "voice", True),  # top-dir match
        ("modules/api/routes/x.py", "api/routes", True),  # slashed aligned run
        ("modules/api/other/x.py", "api/routes", False),  # not aligned
        ("modules/voice/x.py", "modules", True),  # scope is a real top segment
        ("README.md", "voice", False),  # root file never in a dir scope
    ],
)
def test_scope_matches(path, scope, expected):
    assert css._scope_matches(path, scope) is expected


# ===========================================================================
# decide() — the PURE decision function. Exhaustive over every branch.
# ===========================================================================


def test_decide_empty_index_allows():
    d = css.decide([])
    assert d.action == "ALLOW"
    assert d.reason == "empty-index"


def test_decide_all_whitespace_paths_treated_empty():
    d = css.decide(["   ", "", "\t"])
    assert d.action == "ALLOW"
    assert d.reason == "empty-index"


def test_decide_has_no_pathspec_concept_it_only_ever_judges_a_path_set():
    # decide() itself has no "pathspec" kwarg / blanket-allow branch any more —
    # a pathspec set is judged by the SAME rules as a staged index (see
    # _decide_with_pathspec). Passing a stray kwarg is a TypeError, not a
    # silent allow — regression guard for the removed "explicit-pathspec"
    # blanket-allow branch.
    import pytest as _pytest

    with _pytest.raises(TypeError):
        css.decide(["a.py"], scope="voice", pathspec=["a.py"])


def test_decide_in_scope_allows():
    d = css.decide(
        ["modules/voice/a.py", "modules/voice/b.py"],
        scope="voice",
    )
    assert d.action == "ALLOW"
    assert d.reason == "in-scope"
    assert d.detail["count"] == 2


def test_decide_out_of_scope_blocks():
    d = css.decide(
        ["modules/voice/a.py", "modules/billing/b.py"],
        scope="voice",
    )
    assert d.action == "BLOCK"
    assert d.reason == "out-of-scope"
    assert d.detail["out_of_scope"] == ["modules/billing/b.py"]
    assert d.detail["scope"] == "voice"


def test_decide_out_of_scope_sorts_offenders():
    d = css.decide(
        ["modules/voice/a.py", "z/z.py", "a/a.py"],
        scope="voice",
    )
    assert d.action == "BLOCK"
    assert d.detail["out_of_scope"] == ["a/a.py", "z/z.py"]


def test_decide_no_scope_skips_scope_check_but_still_sweeps():
    # Unscoped commit: scope check skipped; a small focused set is ALLOWED.
    d = css.decide(["modules/voice/a.py", "modules/voice/b.py"], scope=None)
    assert d.action == "ALLOW"
    assert d.reason == "in-scope"


def test_decide_too_many_files_blocks():
    paths = [f"modules/voice/f{i}.py" for i in range(31)]  # > default 30
    d = css.decide(paths, scope="voice")
    assert d.action == "BLOCK"
    assert d.reason == "too-many-files"
    assert d.detail["count"] == 31
    assert d.detail["max_files"] == css.DEFAULT_MAX_FILES


def test_decide_exactly_max_files_allows():
    paths = [f"modules/voice/f{i}.py" for i in range(css.DEFAULT_MAX_FILES)]
    d = css.decide(paths, scope="voice")
    assert d.action == "ALLOW"  # boundary: == max is fine, only > blocks


def test_decide_custom_max_files():
    d = css.decide(
        ["modules/voice/a.py", "modules/voice/b.py", "modules/voice/c.py"],
        scope="voice",
        max_files=2,
    )
    assert d.action == "BLOCK"
    assert d.reason == "too-many-files"


def test_decide_too_many_top_dirs_blocks():
    # 5 distinct top-level dirs > default 4, no scope so scope-check is skipped.
    paths = [f"dir{i}/f.py" for i in range(5)]
    d = css.decide(paths, scope=None)
    assert d.action == "BLOCK"
    assert d.reason == "too-many-top-dirs"
    assert d.detail["max_top_dirs"] == css.DEFAULT_MAX_TOP_DIRS
    assert len(d.detail["top_dirs"]) == 5


def test_decide_root_files_count_as_root_bucket():
    # Loose root files plus a few dirs: root bucket + 4 dirs = 5 buckets > 4.
    paths = ["README.md", "LICENSE", "a/x.py", "b/x.py", "c/x.py", "d/x.py"]
    d = css.decide(paths, scope=None)
    assert d.action == "BLOCK"
    assert d.reason == "too-many-top-dirs"
    assert "<root>" in d.detail["top_dirs"]


def test_decide_exactly_max_top_dirs_allows():
    paths = [f"dir{i}/f.py" for i in range(css.DEFAULT_MAX_TOP_DIRS)]
    d = css.decide(paths, scope=None)
    assert d.action == "ALLOW"


def test_decide_custom_max_top_dirs():
    paths = ["a/x.py", "b/x.py", "c/x.py"]
    d = css.decide(paths, scope=None, max_top_dirs=2)
    assert d.action == "BLOCK"
    assert d.reason == "too-many-top-dirs"


def test_decide_scope_check_precedes_sweep():
    # Out-of-scope beats too-many-files when both would fire (order matters).
    paths = ["modules/billing/b.py"] + [f"modules/voice/f{i}.py" for i in range(40)]
    d = css.decide(paths, scope="voice")
    assert d.reason == "out-of-scope"  # not too-many-files


def test_decide_leading_dotslash_normalized_in_scope():
    d = css.decide(["./modules/voice/a.py"], scope="voice")
    assert d.action == "ALLOW"


def test_decision_equality_and_repr():
    a = css.Decision("ALLOW", "x", {"k": 1})
    b = css.Decision("ALLOW", "x", {"k": 1})
    c = css.Decision("BLOCK", "x", {"k": 1})
    assert a == b
    assert a != c
    assert a != "not-a-decision"
    assert "ALLOW" in repr(a)


# ===========================================================================
# read_staged_paths — the impure index reader, against THROWAWAY repos only.
# ===========================================================================


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_AUTHOR_NAME", "t")
    env.setdefault("GIT_AUTHOR_EMAIL", "t@t")
    env.setdefault("GIT_COMMITTER_NAME", "t")
    env.setdefault("GIT_COMMITTER_EMAIL", "t@t")
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        timeout=15,
        env=env,
    )


def _has_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10)
        return True
    except Exception:  # pragma: no cover - git present in CI/dev
        return False


requires_git = pytest.mark.skipif(not _has_git(), reason="git not available")


@requires_git
def test_read_staged_paths_empty_index(git_repo):
    assert css.read_staged_paths(str(git_repo)) == []


@requires_git
def test_read_staged_paths_reports_staged_files(git_repo):
    (git_repo / "a.py").write_text("x\n")
    sub = git_repo / "modules" / "voice"
    sub.mkdir(parents=True)
    (sub / "b.py").write_text("y\n")
    _git(git_repo, "add", "a.py", "modules/voice/b.py")
    staged = set(css.read_staged_paths(str(git_repo)))
    assert staged == {"a.py", "modules/voice/b.py"}


@requires_git
def test_read_staged_paths_handles_spaces_in_names(git_repo):
    (git_repo / "with space.py").write_text("x\n")
    _git(git_repo, "add", "with space.py")
    assert css.read_staged_paths(str(git_repo)) == ["with space.py"]


@requires_git
def test_read_staged_paths_only_staged_not_working_tree(git_repo):
    (git_repo / "staged.py").write_text("x\n")
    (git_repo / "unstaged.py").write_text("y\n")
    _git(git_repo, "add", "staged.py")
    assert css.read_staged_paths(str(git_repo)) == ["staged.py"]


def test_read_staged_paths_non_repo_returns_empty(tmp_path):
    # A dir that is not a git repo -> git errors -> [] (degrade open).
    d = tmp_path / "not_a_repo"
    d.mkdir()
    assert css.read_staged_paths(str(d)) == []


def test_read_staged_paths_git_raises_returns_empty(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "run", boom)
    assert css.read_staged_paths(str(tmp_path)) == []


def test_read_staged_paths_nonzero_returncode_returns_empty(monkeypatch, tmp_path):
    class Fake:
        returncode = 128
        stdout = b"garbage"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    assert css.read_staged_paths(str(tmp_path)) == []


def test_read_staged_paths_empty_cwd_passes_none(monkeypatch):
    seen = {}

    class Fake:
        returncode = 0
        stdout = b""

    def fake_run(cmd, **kwargs):
        seen["cwd"] = kwargs.get("cwd")
        return Fake()

    monkeypatch.setattr(subprocess, "run", fake_run)
    css.read_staged_paths("")
    assert seen["cwd"] is None  # empty string coerced to None


# ===========================================================================
# main() — the THIN driver. Feed a payload on stdin, assert emit/log/exit.
#
# Uses CSA_STAGED_SCOPE_DRYRUN=print for decision assertions, and the enforce
# path (capsys) for the canonical-deny emission. All hermetic via `sandbox`.
# ===========================================================================


def _feed(monkeypatch, tool_name="Bash", command="git commit -m x", cwd=None, **extra):
    ev = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    if cwd is not None:
        ev["cwd"] = cwd
    ev.update(extra)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(ev)))


def _stage(monkeypatch, paths):
    """Stub read_staged_paths so main() sees a fixed index (keeps main hermetic)."""
    monkeypatch.setattr(css, "read_staged_paths", lambda cwd: list(paths))


def test_main_disabled_is_noop_allow(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit -m 'feat(voice): x'")
    _stage(monkeypatch, ["modules/billing/b.py"])  # would-block, but disabled
    rc = css.main()
    assert rc == 0
    # dryrun prints ALLOW even though the index is out of scope, because disabled.
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_disabled_writes_no_log(sandbox, clean_env, monkeypatch):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): x'")
    _stage(monkeypatch, ["modules/billing/b.py"])
    css.main()
    assert not sandbox.log_file.exists()


def test_main_non_bash_tool_allows(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, tool_name="Read", command="git commit -m x")
    _stage(monkeypatch, ["modules/billing/b.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_non_commit_command_allows(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git status")
    _stage(monkeypatch, [f"d{i}/x.py" for i in range(10)])  # would sweep if checked
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


# The next several tests exercise the underlying scope/sweep decide() logic
# against the STAGED INDEX in isolation from the mandatory-pathspec feature —
# none of these commands carry a `-- <pathspec>`, so each sets
# CSA_NO_REQUIRE_PATHSPEC=1 (the documented operator rollback lever) to reach
# the pre-existing staged-index path deliberately, rather than tripping the
# (correct, but off-topic for these tests) missing-pathspec block first.
# Mandatory-pathspec itself has its own dedicated section further down.


def test_main_dryrun_block_out_of_scope(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/billing/b.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "BLOCK"


def test_main_dryrun_allow_in_scope(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/voice/b.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_dryrun_block_sweep_no_scope(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'wip'")  # free-form, no scope
    _stage(monkeypatch, [f"dir{i}/f.py" for i in range(6)])
    css.main()
    assert capsys.readouterr().out.strip() == "BLOCK"


def test_main_env_scope_override(sandbox, clean_env, monkeypatch, capsys):
    # CSA_COMMIT_SCOPE overrides the (absent) message scope.
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    clean_env.setenv("CSA_COMMIT_SCOPE", "voice")
    _feed(monkeypatch, command="git commit -m 'wip no conventional prefix'")
    _stage(monkeypatch, ["modules/billing/b.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "BLOCK"


def test_main_explicit_pathspec_allows(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit -m 'feat(voice): x' -- modules/voice/a.py")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/billing/b.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_logonly_default_blocks_silently_but_logs(sandbox, clean_env, monkeypatch, capsys):
    # No enforce, no dryrun: a BLOCK logs would-block and emits NOTHING (allow).
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/billing/b.py"])
    rc = css.main()
    assert rc == 0
    assert capsys.readouterr().out == ""  # silent in log-only mode
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == "check_staged_scope"
    assert rec["decision"] == "would-block"
    assert rec["reason"] == "out-of-scope"
    assert rec["out_of_scope"] == ["modules/billing/b.py"]
    assert rec["enforce"] is False


def test_main_enforce_emits_canonical_deny(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/billing/b.py"])
    rc = css.main()
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "check_staged_scope" in obj["systemMessage"]
    # and it also logged
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-block"
    assert rec["reason"] == "out-of-scope"
    assert rec["enforce"] is True


def test_main_enforce_does_not_deny_in_scope(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py", "modules/voice/b.py"])
    rc = css.main()
    assert rc == 0
    assert "permissionDecision" not in capsys.readouterr().out
    assert not sandbox.log_file.exists()  # no would-block logged for an ALLOW


def test_main_allow_writes_no_log(sandbox, clean_env, monkeypatch):
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py"])
    css.main()
    assert not sandbox.log_file.exists()


def test_main_degrades_open_on_unexpected_error(sandbox, clean_env, monkeypatch, capsys):
    # If read_event blows up, main must NOT propagate — it allows (exit 0).
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit -m x")

    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(css._lib, "read_event", boom)
    rc = css.main()
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ALLOW"  # dryrun still reports ALLOW


def test_main_missing_pathspec_default_blocks(sandbox, clean_env, monkeypatch, capsys):
    """The core of this feature: a pathspec-less commit is BLOCKED by
    default, no operator override needed."""
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "BLOCK"


def test_main_missing_pathspec_deny_message_is_reason_aware(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed(monkeypatch, command="git commit -m 'feat(voice): route'")
    _stage(monkeypatch, ["modules/voice/a.py"])
    css.main()
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "missing-pathspec" in obj["systemMessage"]
    assert 'git commit -m "..." -- <path>' in obj["systemMessage"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["reason"] == "missing-pathspec"


def test_main_reads_real_stdin_no_git(sandbox, clean_env, monkeypatch, capsys):
    # Full path with the REAL read_staged_paths against a non-repo cwd -> []
    # -> empty-index -> ALLOW (exercises the un-stubbed reader through main()).
    # No pathspec on the command, so the pathspec-mandatory feature is
    # deliberately relaxed here too — this test is about the staged-path
    # reader, not about mandatory-pathspec.
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    clean_env.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    d = sandbox.home / "not_a_repo"
    d.mkdir()
    _feed(monkeypatch, command="git commit -m 'feat(voice): x'", cwd=str(d))
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


# ===========================================================================
# writing_commit_segments — per-segment view of a (possibly compound) command.
# ===========================================================================


def test_writing_commit_segments_single_commit_with_pathspec():
    segs = css.writing_commit_segments("git commit -m 'feat(voice): x' -- a.py b.py")
    assert len(segs) == 1
    assert segs[0]["pathspec"] == ["a.py", "b.py"]
    assert segs[0]["message"] == "feat(voice): x"
    assert segs[0]["amend"] is False
    assert segs[0]["allow_empty"] is False


def test_writing_commit_segments_amend_and_allow_empty_flags():
    segs = css.writing_commit_segments("git commit --amend --allow-empty -m x")
    assert segs[0]["amend"] is True
    assert segs[0]["allow_empty"] is True


def test_writing_commit_segments_dry_run_excluded():
    assert css.writing_commit_segments("git commit --dry-run -m x") == []


def test_writing_commit_segments_no_verify_short_flag_is_not_dry_run():
    # -n is git commit's --no-verify short flag, NOT dry-run: the segment
    # still writes and must still be guarded.
    segs = css.writing_commit_segments("git commit -n -m x -- a.py")
    assert len(segs) == 1
    assert segs[0]["pathspec"] == ["a.py"]


def test_writing_commit_segments_multiple_writing_segments_all_returned():
    segs = css.writing_commit_segments("git commit -m a -- x.py && git commit -m b -- y.py")
    assert len(segs) == 2
    assert segs[0]["pathspec"] == ["x.py"]
    assert segs[1]["pathspec"] == ["y.py"]


def test_writing_commit_segments_leading_dry_run_does_not_suppress_later_real_segment():
    segs = css.writing_commit_segments("git commit --dry-run && git commit -m x -- a.py")
    assert len(segs) == 1
    assert segs[0]["pathspec"] == ["a.py"]


def test_is_git_commit_true_for_any_writing_segment_in_compound():
    assert css.is_git_commit("git commit --dry-run && git commit -m x -- a.py") is True
    assert css.is_git_commit("git commit --dry-run") is False


# ===========================================================================
# is_bulk_pathspec — reject "commit everything" spelled as a pathspec.
# ===========================================================================


@pytest.mark.parametrize("token", [".", "./", "..", ":/", ":/.", "*"])
def test_is_bulk_pathspec_literal_tokens(token):
    assert css.is_bulk_pathspec([token]) is True


def test_is_bulk_pathspec_real_path_not_bulk():
    assert css.is_bulk_pathspec(["modules/voice/a.py"]) is False


def test_is_bulk_pathspec_mixed_set_any_bulk_entry_trips_it():
    assert css.is_bulk_pathspec(["modules/voice/a.py", "."]) is True


def test_is_bulk_pathspec_absolute_repo_root_is_bulk(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert css.is_bulk_pathspec([str(repo)], repo_root=str(repo)) is True


def test_is_bulk_pathspec_absolute_non_root_path_not_bulk(tmp_path):
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    assert css.is_bulk_pathspec([str(repo / "sub" / "a.py")], repo_root=str(repo)) is False


def test_is_bulk_pathspec_no_repo_root_skips_absolute_check_not_a_false_positive():
    # Without a repo_root to compare against, an absolute path is never
    # flagged bulk on that ground alone (only the literal-token check runs).
    assert css.is_bulk_pathspec(["/some/absolute/path.py"]) is False


# ===========================================================================
# merge_in_progress — the mid-merge/cherry-pick/revert/rebase exemption.
# ===========================================================================


def test_merge_in_progress_true_when_any_git_path_exists(monkeypatch):
    monkeypatch.setattr(
        css, "_git_path_exists", lambda cwd, p: p == "MERGE_HEAD"
    )
    assert css.merge_in_progress("/x") is True


def test_merge_in_progress_false_when_none_exist(monkeypatch):
    monkeypatch.setattr(css, "_git_path_exists", lambda cwd, p: False)
    assert css.merge_in_progress("/x") is False


@requires_git
def test_merge_in_progress_real_repo_clean_checkout_is_false(git_repo):
    assert css.merge_in_progress(str(git_repo)) is False


# ===========================================================================
# _decide_missing_pathspec — the exemption ladder for a pathspec-less segment.
# ===========================================================================


def test_decide_missing_pathspec_no_exemption_blocks():
    d = css._decide_missing_pathspec(
        {"allow_empty": False}, ["modules/voice/a.py"], scope=None, mid_merge=False, require_pathspec=True
    )
    assert d.action == "BLOCK"
    assert d.reason == "missing-pathspec"


def test_decide_missing_pathspec_mid_merge_exempts_and_falls_through():
    d = css._decide_missing_pathspec(
        {"allow_empty": False}, ["modules/voice/a.py"], scope="voice", mid_merge=True, require_pathspec=True
    )
    assert d.action == "ALLOW"
    assert d.detail["pathspec_exempt"] == "merge-in-progress"


def test_decide_missing_pathspec_allow_empty_exempts():
    d = css._decide_missing_pathspec(
        {"allow_empty": True}, [], scope=None, mid_merge=False, require_pathspec=True
    )
    assert d.action == "ALLOW"
    assert d.detail["pathspec_exempt"] == "allow-empty"


def test_decide_missing_pathspec_env_override_exempts():
    d = css._decide_missing_pathspec(
        {"allow_empty": False},
        ["modules/voice/a.py"],
        scope="voice",
        mid_merge=False,
        require_pathspec=False,
    )
    assert d.action == "ALLOW"
    assert d.detail["pathspec_exempt"] == "no-require-pathspec-env"


def test_decide_missing_pathspec_exemption_still_enforces_scope_sweep():
    # An exemption lifts ONLY the missing-pathspec block, never the
    # underlying scope/sweep check on the (now-exempted) staged index.
    d = css._decide_missing_pathspec(
        {"allow_empty": True},
        ["modules/voice/a.py", "modules/billing/b.py"],
        scope="voice",
        mid_merge=False,
        require_pathspec=True,
    )
    assert d.action == "BLOCK"
    assert d.reason == "out-of-scope"


# ===========================================================================
# _decide_with_pathspec — a real pathspec is judged, not blanket-allowed.
# ===========================================================================


def test_decide_with_pathspec_bulk_blocks():
    d = css._decide_with_pathspec([".", "a.py"], scope=None, repo_root=None)
    assert d.action == "BLOCK"
    assert d.reason == "bulk-pathspec"


def test_decide_with_pathspec_in_scope_allows():
    d = css._decide_with_pathspec(["modules/voice/a.py"], scope="voice", repo_root=None)
    assert d.action == "ALLOW"


def test_decide_with_pathspec_cross_directory_allowed_no_scope_check():
    # A named pathspec has ALREADY done its own scoping — the conventional-
    # commit message scope is a topic label, not a literal directory
    # requirement, so a pathspec spanning multiple directories (e.g. code +
    # docs, paired in the same commit per CLAUDE.md §5) is NOT blocked just
    # because "voice" isn't a literal path segment of every entry.
    d = css._decide_with_pathspec(
        ["modules/voice/a.py", "wildly/unrelated/y.py"], scope="voice", repo_root=None
    )
    assert d.action == "ALLOW"


def test_decide_with_pathspec_scope_param_is_ignored():
    # The `scope` kwarg is accepted for signature symmetry but must have NO
    # effect on the decision for an explicit pathspec — regression guard for
    # the bug this fix closes (scope check must never run on a named pathspec).
    with_scope = css._decide_with_pathspec(["modules/voice/a.py", "docs/x.md"], scope="voice", repo_root=None)
    without_scope = css._decide_with_pathspec(["modules/voice/a.py", "docs/x.md"], scope=None, repo_root=None)
    assert with_scope.action == without_scope.action == "ALLOW"


def test_decide_with_pathspec_real_review_regression_case():
    # The exact failing case from the Opus code-review replay: a conventional-
    # commit scope word ("ai_agent") that is a topic label, not a literal
    # directory prefix, paired with a docs file in a completely different top-
    # level directory in the SAME commit — must be ALLOWED.
    d = css._decide_with_pathspec(
        ["modules/ai_agent/core/agent.py", "_Config_Project/docs/TESTING_AND_HARNESSES.md"],
        scope="ai_agent",
        repo_root=None,
    )
    assert d.action == "ALLOW"


def test_decide_with_pathspec_too_many_files_blocks():
    pathspec = [f"modules/voice/f{i}.py" for i in range(31)]
    d = css._decide_with_pathspec(pathspec, scope="voice", repo_root=None)
    assert d.action == "BLOCK"
    assert d.reason == "too-many-files"


def test_decide_with_pathspec_too_many_top_dirs_still_blocks():
    # Sweep protection (breadth across unrelated top-level dirs) still fully
    # applies to a named pathspec — only the scope check was removed.
    pathspec = [f"dir{i}/f.py" for i in range(css.DEFAULT_MAX_TOP_DIRS + 1)]
    d = css._decide_with_pathspec(pathspec, scope=None, repo_root=None)
    assert d.action == "BLOCK"
    assert d.reason == "too-many-top-dirs"


def test_decide_with_pathspec_empty_pathspec_allows():
    d = css._decide_with_pathspec([], scope="voice", repo_root=None)
    assert d.action == "ALLOW"
    assert d.reason == "empty-index"


# ===========================================================================
# decision_for_event — the full per-segment, first-violation-wins pipeline.
# ===========================================================================


def _ev(command, cwd="/x"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_decision_for_event_no_writing_segment_allows():
    d = css.decision_for_event(_ev("git status"), [])
    assert d.action == "ALLOW"
    assert d.reason == "no-writing-commit-segment"


def test_decision_for_event_good_pathspec_allows():
    d = css.decision_for_event(_ev("git commit -m 'feat(voice): x' -- modules/voice/a.py"), [])
    assert d.action == "ALLOW"


def test_decision_for_event_cross_directory_pathspec_allowed_real_review_case():
    # End-to-end regression for the exact Opus-review-found blocker: pairing
    # code + docs in ONE commit (CLAUDE.md §5-mandated) whose conventional-
    # commit scope word ("ai_agent") is not a literal path segment of the
    # docs file must NOT block.
    d = css.decision_for_event(
        _ev(
            "git commit -m 'fix(ai_agent): x' "
            "-- modules/ai_agent/core/agent.py _Config_Project/docs/TESTING_AND_HARNESSES.md"
        ),
        [],
    )
    assert d.action == "ALLOW"


def test_decision_for_event_bulk_pathspec_blocks():
    d = css.decision_for_event(_ev("git commit -m x -- ."), [])
    assert d.action == "BLOCK"
    assert d.reason == "bulk-pathspec"


def test_decision_for_event_no_pathspec_blocks_by_default():
    d = css.decision_for_event(_ev("git commit -m x"), ["a.py"])
    assert d.action == "BLOCK"
    assert d.reason == "missing-pathspec"


def test_decision_for_event_no_require_pathspec_env_falls_through(monkeypatch):
    monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
    d = css.decision_for_event(_ev("git commit -m 'feat(voice): x'"), ["modules/voice/a.py"])
    assert d.action == "ALLOW"


def test_decision_for_event_compound_blocks_on_second_segment():
    d = css.decision_for_event(
        _ev("git commit -m a -- modules/voice/x.py && git commit -m b"), ["modules/voice/x.py"]
    )
    assert d.action == "BLOCK"
    assert d.reason == "missing-pathspec"


def test_decision_for_event_dry_run_does_not_suppress_later_segment():
    d = css.decision_for_event(_ev("git commit --dry-run && git commit -m x"), ["a.py"])
    assert d.action == "BLOCK"
    assert d.reason == "missing-pathspec"


def test_decision_for_event_merge_in_progress_exempts_pathspec_less_commit(monkeypatch):
    monkeypatch.setattr(css, "merge_in_progress", lambda cwd: True)
    d = css.decision_for_event(_ev("git commit -m 'merge recovery'"), ["a.py"])
    assert d.action == "ALLOW"
    assert d.detail.get("pathspec_exempt") == "merge-in-progress"


def test_decision_for_event_repo_root_reused_when_passed_in(monkeypatch):
    """When the caller already resolved repo_root, decision_for_event must
    reuse it (never re-shell to git) for the absolute-path bulk-pathspec check."""
    calls = []
    monkeypatch.setattr(css, "_repo_root", lambda cwd: calls.append(cwd) or "/should/not/be/used")
    d = css.decision_for_event(
        _ev("git commit -m x -- /already/resolved"), [], repo_root="/already/resolved"
    )
    assert calls == []  # _repo_root never invoked — the passed-in value was reused
    assert d.action == "BLOCK"
    assert d.reason == "bulk-pathspec"


# ===========================================================================
# deny_message — reason-aware operator-facing text.
# ===========================================================================


def test_deny_message_missing_pathspec():
    msg = css.deny_message(css.Decision("BLOCK", "missing-pathspec"))
    assert "missing-pathspec" in msg
    assert 'git commit -m "..." -- <path>' in msg


def test_deny_message_bulk_pathspec():
    msg = css.deny_message(css.Decision("BLOCK", "bulk-pathspec"))
    assert "bulk-pathspec" in msg
    assert "git commit -- ." in msg


def test_deny_message_generic_scope_sweep_reason():
    msg = css.deny_message(css.Decision("BLOCK", "out-of-scope"))
    assert "out-of-scope" in msg
    assert "sweep files outside" in msg


# ===========================================================================
# main() — merge-in-progress / allow-empty / bulk-pathspec end-to-end.
# ===========================================================================


def test_main_merge_in_progress_allows_pathspec_less_commit(sandbox, clean_env, monkeypatch, capsys):
    """Recovery pairing: a real git repo mid-merge can still commit without a
    pathspec (git itself would refuse a partial commit here)."""
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    monkeypatch.setattr(css, "merge_in_progress", lambda cwd: True)
    _feed(monkeypatch, command="git commit -m 'Merge branch x'")
    _stage(monkeypatch, ["modules/voice/a.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_allow_empty_allows_pathspec_less_commit(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit --allow-empty -m 'checkpoint'")
    _stage(monkeypatch, [])
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"


def test_main_bulk_pathspec_blocks(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed(monkeypatch, command="git commit -m 'x' -- .")
    _stage(monkeypatch, ["a.py"])
    css.main()
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "bulk-pathspec" in obj["systemMessage"]


def test_main_compound_second_segment_missing_pathspec_blocks(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(monkeypatch, command="git commit -m a -- modules/voice/x.py && git commit -m b")
    _stage(monkeypatch, ["modules/voice/x.py"])
    css.main()
    assert capsys.readouterr().out.strip() == "BLOCK"


def test_main_cross_directory_pathspec_allowed_real_review_case(sandbox, clean_env, monkeypatch, capsys):
    # Full main() pipeline, real review-replay case: a `fix(ai_agent): ...`
    # commit naming both a code file AND a docs file (different top-level
    # dirs) via an explicit pathspec must be ALLOWED, not blocked as
    # "out-of-scope".
    clean_env.setenv("CSA_STAGED_SCOPE_DRYRUN", "print")
    _feed(
        monkeypatch,
        command=(
            "git commit -m 'fix(ai_agent): x' "
            "-- modules/ai_agent/core/agent.py _Config_Project/docs/TESTING_AND_HARNESSES.md"
        ),
    )
    css.main()
    assert capsys.readouterr().out.strip() == "ALLOW"
