"""Hermetic tests for hooks/_lib.py.

Covers: the git tokenizer (reproducing git_guard.sh's proven decisions),
enforce-precedence including the CSA_DISABLE_HOOKS master-OFF override,
read_event/_parse_event on garbage, cwd/tool_name/bash_command extraction,
the canonical emitters, and the JSONL log writer.

All tests run against the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir) so the real ~/.claude is never touched.
"""

from __future__ import annotations

import io
import json
import os

import _lib
import pytest

# ===========================================================================
# git_segments — TOKENIZER. Reproduce git_guard.sh's segmentation decisions.
#
# git_guard blocks a command iff at least one git segment carries a state-verb
# subcommand (or a blocked flag). git_segments() is the tokenizer half: it
# yields the git argv per segment. We assert the SEGMENTS the guard would then
# inspect, matching the proven bash vectors.
# ===========================================================================


def _has_git_seg(command):
    """True iff git_segments finds at least one real git argv (not the sentinel)."""
    return any(
        seg and seg[0] == "git" and seg[1:] != ["\x00untokenizable"]
        for seg in _lib.git_segments(command)
    )


def _first_git_argv(command):
    segs = _lib.git_segments(command)
    return segs[0] if segs else None


# --- the REQUIRED task vectors ---------------------------------------------


def test_tok_git_add_A_is_git_segment():
    assert _first_git_argv("git add -A") == ["git", "add", "-A"]


def test_tok_git_add_A_extra_whitespace():
    # 'git   add   -A' collapses to the same argv (shlex handles the spaces).
    assert _first_git_argv("git   add   -A") == ["git", "add", "-A"]


def test_tok_git_dash_C_dir_strips_global():
    # 'git -C /x add -A' -> global -C /x stripped, leaving add -A.
    assert _first_git_argv("git -C /x add -A") == ["git", "add", "-A"]


def test_tok_compound_true_and_git_checkout():
    # 'true && git checkout -b x' -> the git checkout segment is surfaced.
    segs = _lib.git_segments("true && git checkout -b x")
    assert ["git", "checkout", "-b", "x"] in segs


def test_tok_command_substitution_git_reset():
    # 'foo $(git reset --hard)' -> the $( opener is a boundary; git reset is a seg.
    segs = _lib.git_segments("foo $(git reset --hard)")
    assert ["git", "reset", "--hard"] in segs


def test_tok_ls_la_no_git_segment():
    assert _lib.git_segments("ls -la") == []
    assert _has_git_seg("ls -la") is False


def test_tok_git_add_path_digit_is_git_segment_with_path():
    # 'git add ./digit.py' -> git segment WITH the path preserved (path-scoped add).
    assert _first_git_argv("git add ./digit.py") == ["git", "add", "./digit.py"]


# --- broader parity with git_guard.sh vectors ------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git status", ["git", "status"]),
        ("git add ./modules/x.py", ["git", "add", "./modules/x.py"]),
        ("git add path/A", ["git", "add", "path/A"]),
        ("GIT_DIR=x git reset --hard", ["git", "reset", "--hard"]),
        ("git -c user.name=x reset --hard", ["git", "reset", "--hard"]),
        ("git -C /repo checkout main", ["git", "checkout", "main"]),
        ("ENV=1 OTHER=2 git stash", ["git", "stash"]),
        ("/usr/bin/git reset --hard", ["git", "reset", "--hard"]),
        ('git commit -am "x"', ["git", "commit", "-am", "x"]),
        ("git branch -D feat", ["git", "branch", "-D", "feat"]),
        ("git worktree add ../wt", ["git", "worktree", "add", "../wt"]),
    ],
)
def test_tok_argv_parity(command, expected):
    assert _first_git_argv(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "rm -rf build",
        "gitfoo status",  # argv0 basename is gitfoo, not git
        "mygit add -A",  # argv0 basename is mygit, not git
        "echo git is a word",  # 'git' appears but not as argv0
    ],
)
def test_tok_non_git_argv0_no_segment(command):
    # 'echo git is a word' DOES contain a 'git' token but not as argv0, so no seg.
    assert _has_git_seg(command) is False


def test_tok_bare_git_no_subcommand_omitted():
    # bare `git` (no subcommand) has nothing to inspect -> no segment.
    assert _lib.git_segments("git") == []
    assert _lib.git_segments("git -C /x") == []


def test_tok_pipe_boundary_surfaces_git_reset():
    segs = _lib.git_segments("echo hi | git checkout -")
    assert ["git", "checkout", "-"] in segs


def test_tok_semicolon_boundary():
    segs = _lib.git_segments("git status ; git reset --hard")
    assert ["git", "status"] in segs
    assert ["git", "reset", "--hard"] in segs


def test_tok_backtick_boundary():
    segs = _lib.git_segments("echo `git switch main`")
    assert ["git", "switch", "main"] in segs


def test_tok_process_substitution_boundaries():
    segs = _lib.git_segments("diff <(git stash) >(cat)")
    assert ["git", "stash"] in segs


def test_tok_git_global_flags_stripped():
    # --git-dir=X (one token) and --no-pager should be stripped before subcommand.
    assert _first_git_argv("git --no-pager --git-dir=/x reset --hard") == [
        "git",
        "reset",
        "--hard",
    ]
    # --work-tree Y (two-token form)
    assert _first_git_argv("git --work-tree /y checkout main") == [
        "git",
        "checkout",
        "main",
    ]


def test_tok_untokenizable_segment_with_git_is_sentinel():
    # An unbalanced-quote segment mentioning git -> the fail-closed sentinel.
    segs = _lib.git_segments("git commit -m 'unterminated")
    assert ["git", "\x00untokenizable"] in segs
    assert _has_git_seg("git commit -m 'unterminated") is False


def test_tok_untokenizable_segment_without_git_dropped():
    segs = _lib.git_segments("echo 'unterminated")
    assert segs == []


# --- #4670 item 3b: word-boundary fix for the untokenizable-with-git
# sentinel (was a bare `"git" in seg` substring test) --------------------


def test_tok_untokenizable_segment_git_substring_only_not_sentinel():
    # An untokenizable segment whose ONLY "git"-like text is a substring
    # inside a longer word ("legitimate") must NOT trip the fail-closed
    # sentinel. The pre-fix bare substring check (`"git" in seg`) would have
    # wrongly flagged this as an ambiguous git invocation; a real git
    # invocation always has "git" as its own token, bounded by whitespace /
    # quotes / operators on both sides, so this loses no genuine detection.
    segs = _lib.git_segments("echo 'legitimate value")
    assert segs == []


def test_tok_raw_mentions_git_word_boundary_non_prefix_positions():
    # Non-prefix positions must still match -- guards against an accidental
    # "segment startswith git" implementation (item 3b's mandatory probe set,
    # empirically confirmed live during plan review).
    assert _lib._raw_mentions_git("FOO=1 git reset --hard") is True
    assert _lib._raw_mentions_git("/usr/bin/git reset --hard") is True
    assert _lib._raw_mentions_git("echo x | git reset --hard") is True
    assert _lib._raw_mentions_git("(git reset --hard)") is True


@pytest.mark.parametrize(
    "raw,expect",
    [
        (".git", True),
        (".git/config", True),
        ("_git", True),
        ("git2", True),
        (".gitignore", False),
        ("github", False),
        ("legitimate", False),
        ("digit", False),
        # #4670 round-4 blocker fix: ASCII-only word boundary
        # (_is_ascii_alpha, not str.isalpha()). Under the OLD Unicode-aware
        # `c.isalpha()` implementation, 'é'.isalpha() and 'ö'.isalpha() are
        # both True in Python, so these would be wrongly treated as "git"
        # embedded inside a longer word (an accented neighbor counting as
        # alpha) and return False -- letting a git-adjacent accented
        # character slip the boundary check the mandated ASCII regex
        # `(^|[^A-Za-z])git([^A-Za-z]|$)` would have denied. The correct
        # ASCII-only implementation must detect "git" in both regardless.
        ("égit", True),
        ("gitö", True),
    ],
)
def test_lib_raw_mentions_git_isalpha_not_isalnum(raw, expect):
    # isalpha, not isalnum: a digit/underscore/non-alpha neighbor still
    # counts as a word boundary (".git", ".git/config", "_git", "git2" all
    # match -- the character next to "git" is non-alpha); an ALPHA neighbor
    # means "git" is part of a longer word (".gitignore", "github",
    # "legitimate", "digit" do not match). "égit"/"gitö" pin the ASCII-only
    # (not Unicode-aware) requirement specifically -- see cases above.
    assert _lib._raw_mentions_git(raw) is expect


def test_tok_empty_and_whitespace_command():
    assert _lib.git_segments("") == []
    assert _lib.git_segments("   ") == []


def test_tok_multiple_git_segments_all_returned():
    segs = _lib.git_segments("git add file.py && git commit -m x")
    assert ["git", "add", "file.py"] in segs
    assert ["git", "commit", "-m", "x"] in segs


def test_tok_heredoc_commit_message_with_apostrophe_tokenizes_clean():
    # Real bug, root-caused 2026-09-05 (workflow audit into gate-denial
    # friction, top reason: untokenizable-segment-with-git, 214/786
    # denials/7d): the runtime's OWN recommended commit-message idiom
    # (`git commit -F - <<'EOF' ... EOF`) broke once ANY command followed
    # it and the message body contained an apostrophe -- the heredoc
    # body's newline was treated as an ordinary segment boundary, and the
    # SECOND fragment (starting mid-apostrophe) merged with the FOLLOWING
    # command, desyncing quote state and producing the untokenizable
    # sentinel for what should be a perfectly clean trailing command.
    # (Round-2 review finding 3: the first version of this test used a
    # command with no trailing statement, which is a non-falsifiable
    # shape -- pre-fix code already returned the identical result for
    # that shape, since the ambiguous heredoc-body fragment never
    # mentions "git" and gets silently dropped rather than surfaced. This
    # version's trailing `git status` is what actually distinguishes
    # fixed from broken.)
    cmd = "git commit -F - <<'EOF' -- a.py\nfix: contractor's bug\nEOF\ngit status"
    segs = _lib.git_segments(cmd)
    assert ["git", "\x00untokenizable"] not in segs
    assert ["git", "status"] in segs


def test_tok_heredoc_body_never_scanned_for_a_state_verb():
    # A state-verb TEXT inside a QUOTED-delimiter heredoc BODY is inert
    # file content, never an executed command -- it must not be treated
    # as a real git segment.
    cmd = "cat <<'EOF' > /tmp/notes.txt\ngit stash pop\nEOF\ngit status"
    segs = _lib.git_segments(cmd)
    assert ["git", "stash", "pop"] not in segs
    assert ["git", "status"] in segs


def test_tok_unquoted_heredoc_body_substitution_is_live_and_still_caught():
    # BLOCKER, round-3 review (2026-09-05): an UNQUOTED heredoc delimiter
    # (`<<EOF`, no quotes) makes bash perform parameter/command/
    # arithmetic expansion INSIDE the body -- confirmed live in real bash
    # (`cat <<EOF >/dev/null\n$(id -un >&2)\nEOF` prints the real
    # username to stderr). The round-2 fix dropped EVERY heredoc body
    # unconditionally, which silently discarded a real, LIVE command
    # substitution and let a state verb inside `$(...)`/backticks bypass
    # every gate. Only a QUOTED delimiter's body may be dropped as inert;
    # an unquoted one must flow through the same scan that catches a
    # substitution anywhere else.
    cases = [
        ("cat <<EOF > /tmp/x\n$(git checkout main)\nEOF", ["git", "checkout", "main"]),
        ("cat <<EOF > /tmp/x\n`git reset --hard`\nEOF", ["git", "reset", "--hard"]),
        ("cat <<EOF > /tmp/x\n$(git add -A)\nEOF", ["git", "add", "-A"]),
        ("cat <<EOF > /tmp/x\n$(git stash pop)\nEOF", ["git", "stash", "pop"]),
    ]
    for cmd, expected_segment in cases:
        segs = _lib.git_segments(cmd)
        assert expected_segment in segs, f"{cmd!r} did not surface {expected_segment!r}: {segs!r}"


def test_tok_quoted_heredoc_body_substitution_stays_inert():
    # Paired negative for the test above: the IDENTICAL substitution text
    # inside a QUOTED-delimiter body is genuinely inert in real bash (no
    # expansion happens), so it correctly stays un-surfaced.
    cmd = "cat <<'EOF' > /tmp/x\n$(git checkout main)\nEOF"
    segs = _lib.git_segments(cmd)
    assert ["git", "checkout", "main"] not in segs


def test_tok_real_state_verb_immediately_after_a_heredoc_still_caught():
    # REGRESSION GUARD (passes both pre- and post-fix -- not itself
    # falsifying the heredoc fix, but pins behavior the fix must never
    # break): a REAL state-verb command on the line right after a
    # heredoc closes must still be recognized as its own segment.
    cmd = "cat <<'EOF' > /tmp/x.txt\nsome text\nEOF\ngit checkout main"
    segs = _lib.git_segments(cmd)
    assert ["git", "checkout", "main"] in segs


def test_tok_heredoc_opener_line_control_operators_still_split_segments():
    # BLOCKER, round-2 review (2026-09-05): the first version of this fix
    # raw-appended the REST of the heredoc opener's own line without
    # scanning it for control operators, letting a real state verb chained
    # after `&&`/`;`/`|` on that same line slip through unrecognized --
    # confirmed exploitable pre-round-2-fix: `cat <<'EOF' > /tmp/x &&
    # git checkout main` (and `;`/`|` variants, plus gate-2's `git add -A`/
    # `git commit -a`) all failed to surface the trailing git command.
    # Every one of these must now be caught as its own segment.
    cases = [
        ("cat <<'EOF' > /tmp/x && git checkout main\nbody\nEOF", ["git", "checkout", "main"]),
        ("cat <<'EOF' > /tmp/x ; git reset --hard\nbody\nEOF", ["git", "reset", "--hard"]),
        ("cat <<'EOF' > /tmp/x | git stash pop\nbody\nEOF", ["git", "stash", "pop"]),
        ("cat <<'EOF' >/tmp/x && git add -A\nb\nEOF", ["git", "add", "-A"]),
        ("cat <<'EOF' >/tmp/x && git commit -a -m x\nb\nEOF", ["git", "commit", "-a", "-m", "x"]),
    ]
    for cmd, expected_segment in cases:
        segs = _lib.git_segments(cmd)
        assert expected_segment in segs, f"{cmd!r} did not surface {expected_segment!r}: {segs!r}"


def test_tok_heredoc_dash_form_strips_leading_tabs():
    cmd = "git commit -F - <<-'EOF'\n\tsome text\n\tEOF"
    segs = _lib.git_segments(cmd)
    assert segs == [["git", "commit", "-F", "-", "<<-EOF"]]


def test_tok_unterminated_heredoc_never_hangs_or_raises():
    # No closing delimiter anywhere -- must degrade gracefully (consume to
    # end of string), never infinite-loop or raise.
    cmd = "git commit -F - <<'EOF'\nunterminated body with no EOF anywhere"
    segs = _lib.git_segments(cmd)
    assert segs == [["git", "commit", "-F", "-", "<<EOF"]]


def test_tok_arithmetic_shift_operator_never_mistaken_for_a_heredoc_opener():
    # NIT, round-2 review (2026-09-05): an UNQUOTED bare identifier after
    # `<<` also matches a bitshift operator inside `$(( ... ))` --
    # confirmed exploitable pre-fix: `echo $((x << y))\ngit checkout
    # main` treated `y` as a heredoc delimiter, and since no later line
    # is ever exactly `y`, the body-drop loop consumed EVERYTHING
    # including the real trailing `git checkout main`, hiding it
    # entirely. The regex now requires the (unquoted) delimiter to be
    # followed by whitespace/control-operator/end-of-string, never by
    # more expression syntax like a closing paren.
    cmd = "echo $((x << y))\ngit checkout main"
    segs = _lib.git_segments(cmd)
    assert ["git", "checkout", "main"] in segs


def test_tok_here_string_never_mistaken_for_a_heredoc_opener():
    # BLOCKER, round-4 (cold) review (2026-09-05): `<<<word` is a
    # HERE-STRING -- a single-word literal piped in, no body, no
    # terminator line -- a completely different construct from a
    # heredoc. `_HEREDOC_OPEN_RE.match` correctly rejects `<<<word`
    # itself, but without an explicit guard the outer walk falls
    # through, appends one `<`, advances by 1, and lands on the SECOND
    # `<` of the same `<<<` on its next iteration -- where the
    # remaining text (`<<word`) IS a textbook heredoc opener that
    # matches and arms. Since a here-string has no terminator anywhere
    # downstream, the body-drop loop then silently consumes the rest of
    # the command, hiding a real trailing git invocation entirely.
    # Confirmed exploitable end-to-end through the real gate chain
    # before this fix (denied pre-fix, ALLOWED once heredoc-awareness
    # landed without this guard).
    cases = [
        ("cat <<<word\ngit checkout main", ["git", "checkout", "main"]),
        ("grep -q main <<<branchlist\ngit reset --hard", ["git", "reset", "--hard"]),
        ("read v <<<x\ngit add -A", ["git", "add", "-A"]),
        ("cat <<<word\ngit stash pop", ["git", "stash", "pop"]),
        ("cat <<<word\ngit rebase main", ["git", "rebase", "main"]),
        ("cat <<<word\ngit worktree add x", ["git", "worktree", "add", "x"]),
    ]
    for cmd, expected_segment in cases:
        segs = _lib.git_segments(cmd)
        assert expected_segment in segs, f"{cmd!r} did not surface {expected_segment!r}: {segs!r}"


def test_tok_never_raises_on_odd_input():
    # Weird bytes / structures must not raise; just returns a list.
    for c in ["$(", "((((", ")))", "|||", "&& || ;;", "git \x00"]:
        assert isinstance(_lib.git_segments(c), list)


def test_tok_c_global_shortform_and_unknown_flag_stripped():
    # -ck=v short-bundled form (t.startswith('-c')) and an unknown global flag
    # both get skipped so the subcommand is still found.
    assert _lib._strip_git_globals(["git", "-cfoo=bar", "reset", "--hard"]) == [
        "git",
        "reset",
        "--hard",
    ]
    assert _lib._strip_git_globals(["git", "--unknown-global", "checkout", "x"]) == [
        "git",
        "checkout",
        "x",
    ]


def test_tok_git_dash_c_kv_two_token_form():
    # 'git -c k=v reset' (two-token -c form) -> the global pair is stripped.
    assert _lib.git_segments("git -c core.pager=less reset --hard")[0] == [
        "git",
        "reset",
        "--hard",
    ]


def test_tok_empty_segment_skipped():
    # A leading operator produces an empty first segment; it must be dropped, and
    # a segment that is only an env-assignment strips to nothing and is skipped.
    assert _lib.git_segments("&& git status") == [["git", "status"]]
    assert _lib.git_segments("FOO=bar") == []  # env-only -> empty after strip


def test_tok_empty_token_list_segment_skipped(monkeypatch):
    # Defensive guard: if _tokenize yields an empty list for a segment (belt-and-
    # suspenders — shlex.split can't actually do this for a stripped non-empty
    # segment), git_segments must skip it rather than index [0]. We force the
    # empty-list return to exercise the `if not toks: continue` branch.
    real_tokenize = _lib._tokenize

    def sometimes_empty(seg):
        if seg == "git status":
            return []
        return real_tokenize(seg)

    monkeypatch.setattr(_lib, "_tokenize", sometimes_empty)
    # 'git status' segment tokenizes to [] and is skipped; the reset seg survives.
    assert _lib.git_segments("git status ; git reset --hard") == [["git", "reset", "--hard"]]


def test_tok_outer_exception_returns_empty(monkeypatch):
    # Force _split_segments to raise; git_segments swallows it -> [].
    def boom(_s):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(_lib, "_split_segments", boom)
    assert _lib.git_segments("git status") == []


# ===========================================================================
# read_event / _parse_event — garbage tolerance.
# ===========================================================================


def test_parse_event_valid_dict():
    ev = _lib._parse_event('{"tool_name":"Bash","tool_input":{"command":"ls"}}')
    assert ev["tool_name"] == "Bash"


def test_parse_event_garbage_returns_empty():
    for bad in ["not json at all", "", "   ", "{unclosed", "\x00\x01", "12"]:
        assert _lib._parse_event(bad) == {}


def test_parse_event_non_dict_json_returns_empty():
    # Valid JSON but not an object -> {}.
    for bad in ["[1,2,3]", '"a string"', "true", "null", "3.14"]:
        assert _lib._parse_event(bad) == {}


def test_read_event_from_stdin(monkeypatch):
    payload = '{"tool_name":"Bash","tool_input":{"command":"git status"}}'
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    ev = _lib.read_event()
    assert ev["tool_name"] == "Bash"


def test_read_event_garbage_stdin_returns_empty(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("total garbage git reset"))
    assert _lib.read_event() == {}


def test_read_event_stdin_read_raises_returns_empty(monkeypatch):
    class Boom:
        def read(self):
            raise IOError("no stdin")

    monkeypatch.setattr("sys.stdin", Boom())
    assert _lib.read_event() == {}


# ===========================================================================
# field extractors — tool_name / bash_command / cwd.
# ===========================================================================


def test_tool_name_present_and_absent():
    assert _lib.tool_name({"tool_name": "Bash"}) == "Bash"
    assert _lib.tool_name({}) == ""
    assert _lib.tool_name({"tool_name": 123}) == ""  # non-str -> ""


def test_bash_command_present_and_variants():
    assert _lib.bash_command({"tool_input": {"command": "ls -la"}}) == "ls -la"
    assert _lib.bash_command({}) == ""
    assert _lib.bash_command({"tool_input": "not a dict"}) == ""
    assert _lib.bash_command({"tool_input": {"command": 5}}) == ""  # non-str


def test_cwd_precedence_and_fallback(monkeypatch, tmp_path):
    assert _lib.cwd({"cwd": "/a/b"}) == "/a/b"
    assert _lib.cwd({"project_dir": "/c/d"}) == "/c/d"
    # cwd wins over project_dir.
    assert _lib.cwd({"cwd": "/a", "project_dir": "/c"}) == "/a"
    # neither present -> os.getcwd() fallback.
    monkeypatch.chdir(tmp_path)
    assert _lib.cwd({}) == os.getcwd()


def test_extractors_never_raise_on_none_like():
    # Passing odd shapes should degrade, not raise.
    assert _lib.tool_name({"tool_name": None}) == ""
    assert _lib.bash_command({"tool_input": {"command": None}}) == ""


class _RaisingGet:
    """A mapping-like whose .get() raises — to hit the extractors' except guards."""

    def get(self, *a, **k):
        raise RuntimeError("boom")


def test_tool_name_swallows_get_exception():
    assert _lib.tool_name(_RaisingGet()) == ""


def test_bash_command_swallows_get_exception():
    assert _lib.bash_command(_RaisingGet()) == ""


def test_cwd_swallows_get_exception_falls_back(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert _lib.cwd(_RaisingGet()) == os.getcwd()


# ===========================================================================
# disabled() / enforcing() — precedence incl. the DISABLE master-OFF override.
# ===========================================================================


def test_disabled_reads_env(clean_env):
    assert _lib.disabled() is False
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    assert _lib.disabled() is True
    clean_env.setenv("CSA_DISABLE_HOOKS", "0")
    assert _lib.disabled() is False


def test_enforcing_off_by_default(sandbox, clean_env):
    assert _lib.enforcing(str(sandbox.home)) is False


def test_enforcing_env_csa_enforce(sandbox, clean_env):
    clean_env.setenv("CSA_ENFORCE", "1")
    assert _lib.enforcing(str(sandbox.home)) is True


def test_enforcing_global_marker_file(sandbox, clean_env):
    # ~/.claude/.enforce existing turns enforcement ON with no env var.
    sandbox.enforce_file.write_text("")
    assert _lib.enforcing(str(sandbox.home)) is True


def test_enforcing_project_marker(sandbox, clean_env, git_repo, enforce_marker):
    # A repo with .claude/.csa-enforce -> enforcing when cwd is inside it.
    assert _lib.enforcing(str(git_repo)) is False  # marker not yet dropped
    enforce_marker(git_repo)
    assert _lib.enforcing(str(git_repo)) is True


def test_enforcing_project_marker_walks_up(sandbox, clean_env, git_repo, enforce_marker):
    enforce_marker(git_repo)
    nested = git_repo / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert _lib.enforcing(str(nested)) is True


def test_enforcing_repo_without_marker_is_off(sandbox, clean_env, git_repo):
    # A git repo with NO opt-in marker must NOT enforce.
    assert _lib.enforcing(str(git_repo)) is False


def test_disable_overrides_env_enforce(sandbox, clean_env):
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    assert _lib.enforcing(str(sandbox.home)) is False


def test_disable_overrides_global_marker(sandbox, clean_env):
    sandbox.enforce_file.write_text("")
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    assert _lib.enforcing(str(sandbox.home)) is False


def test_disable_overrides_project_marker(sandbox, clean_env, git_repo, enforce_marker):
    enforce_marker(git_repo)
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    assert _lib.enforcing(str(git_repo)) is False


def test_enforcing_default_cwd(sandbox, clean_env, monkeypatch, tmp_path):
    # enforcing() with no arg uses the current dir; a plain tmp dir is not a repo.
    monkeypatch.chdir(tmp_path)
    assert _lib.enforcing() is False


def test_enforcing_swallows_global_marker_stat_error(sandbox, clean_env, monkeypatch):
    # os.path.isfile raising on the global marker must be swallowed, and the walk
    # then falls through to _project_enforced (which is off in the sandbox home).
    def boom(path):
        raise OSError("stat failed")

    monkeypatch.setattr(_lib.os.path, "isfile", boom)
    assert _lib.enforcing(str(sandbox.home)) is False


def test_enforcing_stops_at_first_git(sandbox, clean_env, tmp_path, enforce_marker):
    # Outer repo has the marker; inner repo does NOT. Walking up from inside the
    # inner repo must STOP at the inner .git (no marker) -> OFF, matching the
    # bash `break`.
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").mkdir()
    enforce_marker(outer)
    inner = outer / "inner"
    inner.mkdir()
    (inner / ".git").mkdir()
    assert _lib.enforcing(str(inner)) is False


# ===========================================================================
# Canonical emitters.
# ===========================================================================


def test_emit_pretooluse_deny(capsys):
    _lib.emit_pretooluse_deny("blocked: reason")
    out = capsys.readouterr().out
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert obj["systemMessage"] == "blocked: reason"


def test_emit_pretooluse_deny_reason_reaches_the_denied_agent(capsys):
    # #4415 root cause (2026-08-27): systemMessage is what the OPERATOR sees;
    # permissionDecisionReason is what the denied AGENT sees. Without it every
    # _lib-routed gate surfaced as the generic "Hook PreToolUse:Bash denied
    # this tool", so an unattended loop could not tell gate 3b ("get a
    # review") from gate 4 ("another agent holds these paths, wait"). The two
    # fields must carry the SAME text — the parity no_artifact.py always had.
    _lib.emit_pretooluse_deny("unreviewed-commit: record a review first")
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecisionReason"] == (
        "unreviewed-commit: record a review first"
    )
    assert obj["hookSpecificOutput"]["permissionDecisionReason"] == obj["systemMessage"]


def test_emit_stop_block(capsys):
    _lib.emit_stop_block("needs review")
    out = capsys.readouterr().out
    obj = json.loads(out)
    assert obj == {"decision": "block", "reason": "needs review"}


# ===========================================================================
# log() — appends one JSON line; mkdir -p; never raises.
# ===========================================================================


def test_log_writes_one_jsonl_line(sandbox, clean_env):
    _lib.log("git_guard", "would-block", reason="state-verb:reset", command="git reset")
    assert sandbox.log_file.exists()
    lines = sandbox.log_file.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["hook"] == "git_guard"
    assert rec["decision"] == "would-block"
    assert rec["reason"] == "state-verb:reset"
    assert rec["command"] == "git reset"
    assert rec["enforce"] is False
    assert "ts" in rec


def test_log_appends_multiple_lines(sandbox, clean_env):
    _lib.log("git_guard", "a")
    _lib.log("review_gate", "b")
    lines = sandbox.log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["hook"] == "git_guard"
    assert json.loads(lines[1])["hook"] == "review_gate"


def test_log_enforce_flag_reflects_env(sandbox, clean_env):
    clean_env.setenv("CSA_ENFORCE", "1")
    _lib.log("git_guard", "would-block")
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["enforce"] is True


def test_log_enforce_flag_reflects_global_marker_not_just_env(sandbox, clean_env):
    """08-25: `enforce` used to read raw CSA_ENFORCE only, ignoring the
    global marker (~/.claude/.enforce) that ACTUALLY drives enforcement per
    enforcing()'s own precedence -- every log line lied `enforce: false`
    under global-marker-only enforcement while a real deny was happening
    elsewhere (churn_phase0_measure.md step 4a). CSA_ENFORCE is left unset;
    only the marker file drives this."""
    sandbox.enforce_file.write_text("")
    _lib.log("git_guard", "would-block")
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["enforce"] is True


def test_log_enforce_flag_false_when_nothing_enforces(sandbox, clean_env):
    # Companion negative case: no env, no marker, no project opt-in -> False,
    # unchanged from before this fix (guards against an over-eager fix that
    # always returns True).
    _lib.log("git_guard", "would-block")
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["enforce"] is False


def test_log_caller_enforce_kwarg_overrides_internal_computation(sandbox, clean_env):
    """R6 (08-25): pretooluse_bash's _finish passes its OWN `enforcing(where)`
    as an explicit `enforce=` kwarg so the logged field matches the decision
    it actually made, even when the event's cwd differs from the process cwd
    log()'s own bare enforcing() would fall back to. Proven directly against
    log() here: no env var and no marker enforces anything, yet the caller's
    explicit override still wins (the fields-override loop runs AFTER the
    structural default is set — see log()'s own docstring/comment)."""
    _lib.log("pretooluse_bash", "would-block", enforce=True)
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["enforce"] is True


def test_log_creates_enforcement_dir(sandbox, clean_env):
    assert not sandbox.enforcement_dir.exists()
    _lib.log("h", "d")
    assert sandbox.enforcement_dir.exists()


def test_log_unencodable_field_falls_back(sandbox, clean_env):
    # A non-JSON-serializable field: json.dumps(default=str) coerces it, so the
    # line still writes and stays valid JSON.
    class Weird:
        def __repr__(self):
            return "WEIRD"

    _lib.log("git_guard", "would-block", obj=Weird())
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == "git_guard"
    assert rec["obj"] == "WEIRD"


def test_log_first_dumps_raises_uses_minimal_fallback(sandbox, clean_env, monkeypatch):
    # If the FULL record fails to serialize (even with default=str), log falls
    # back to the minimal {ts,hook,decision} line. Simulate by making the first
    # json.dumps call raise, then delegating to the real dumps for the fallback.
    real_dumps = json.dumps
    state = {"calls": 0}

    def flaky_dumps(obj, *a, **k):
        state["calls"] += 1
        if state["calls"] == 1:
            raise ValueError("cannot serialize record")
        return real_dumps(obj, *a, **k)

    monkeypatch.setattr(_lib.json, "dumps", flaky_dumps)
    _lib.log("git_guard", "would-block", reason="x")
    lines = sandbox.log_file.read_text().strip().splitlines()
    parsed = json.loads(lines[-1])
    assert parsed == {
        "ts": parsed["ts"],
        "hook": "git_guard",
        "decision": "would-block",
    }


def test_log_never_raises_when_dir_unwritable(sandbox, clean_env, monkeypatch):
    # makedirs raising must be swallowed (return, no exception).
    def boom(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(_lib.os, "makedirs", boom)
    # Must not raise.
    _lib.log("git_guard", "would-block")


def test_log_never_raises_when_open_fails(sandbox, clean_env, monkeypatch):
    real_open = open

    def boom_open(path, *a, **k):
        if str(path) == str(sandbox.log_file):
            raise OSError("cannot open")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    _lib.log("git_guard", "would-block")  # must not raise


# ===========================================================================
# Module constants are wired to the sandbox HOME.
# ===========================================================================


def test_path_constants_point_into_sandbox(sandbox):
    assert str(sandbox.claude) in _lib.GLOBAL_ENFORCE_FILE
    assert str(sandbox.claude) in _lib.LOG_FILE
    assert str(sandbox.claude) in _lib.LAST_REVIEWED
    assert str(sandbox.claude) in _lib.AGENT_BUDGET_DIR


# ===========================================================================
# _leading_cd_dir / effective_git_cwd — #5061.
#
# `_split_segments` discards the joining operator ('cd /a && git…',
# 'cd /a; git…', 'cd /a || git…', and the subshell form all yield IDENTICAL
# segment lists — verified by execution, 2026-09-07 plan review), so this
# mechanism is deliberately anchored on the RAW command text instead. Every
# case below was executed against the real implementation before being
# written here (never snapshotted from a first "it looks right" run).
# ===========================================================================


class TestLeadingCdDir:
    def test_leading_cd_and_git_resolves_to_the_cd_target(self):
        assert _lib._leading_cd_dir("cd /abs && git commit -m x", "/cwd") == "/abs"

    def test_multi_cd_last_one_wins(self):
        assert (
            _lib._leading_cd_dir("cd /a && cd /b && git commit -m x", "/cwd")
            == "/b"
        )

    def test_mixed_join_second_cd_bails_to_none_not_stale_base(self):
        """A-1 (dual-review regression): `cd /a && cd /b ; git…` — the shell
        may run git from /b, so returning the stale /a base would be a THIRD
        wrong directory. An unconsumed cd after the &&-chain returns None
        (event-cwd fallback), for every mixed join."""
        for join in (";", "||", "&"):
            cmd = f"cd /a && cd /b {join} git commit -m x -- f.py"
            assert _lib._leading_cd_dir(cmd, "/S") is None, join

    def test_interposed_non_cd_command_stops_the_prefix_at_the_first_cd(self):
        # 'cd /a && echo hi && git…' — only the FIRST `cd <dir> &&` prefix is
        # a match; 'echo hi &&' is not itself a `cd` prefix, so the loop
        # never advances past it and the base stays /a (the intervening
        # command's own effect on cwd is unknowable here and irrelevant —
        # `echo` doesn't change directories in real shell semantics either).
        assert (
            _lib._leading_cd_dir("cd /a && echo hi && git commit -m x", "/cwd")
            == "/a"
        )

    def test_semicolon_join_is_rejected_falls_back_to_none(self):
        # Only `&&` guarantees the cd succeeded before anything after it
        # runs; `;` runs the next command regardless of the cd's exit code.
        assert _lib._leading_cd_dir("cd /a; git commit -m x", "/cwd") is None

    def test_or_join_is_rejected_falls_back_to_none(self):
        assert _lib._leading_cd_dir("cd /a || git commit -m x", "/cwd") is None

    def test_background_join_is_rejected_falls_back_to_none(self):
        assert _lib._leading_cd_dir("cd /a & git commit -m x", "/cwd") is None

    def test_subshell_form_is_rejected_falls_back_to_none(self):
        assert _lib._leading_cd_dir("(cd /a && git commit -m x)", "/cwd") is None

    def test_trailing_cd_after_the_git_invocation_is_not_a_leading_prefix(self):
        # 'git… && cd /a' — the cd comes AFTER the git segment, so it can
        # never have been the directory the git invocation actually ran in.
        assert (
            _lib._leading_cd_dir("git commit -m x && cd /a", "/cwd") is None
        )

    def test_cd_dash_oldpwd_is_rejected(self):
        # `cd -` returns to $OLDPWD, which this process cannot know.
        assert _lib._leading_cd_dir("cd - && git commit -m x", "/cwd") is None

    def test_dollar_var_dir_is_rejected(self):
        assert _lib._leading_cd_dir("cd $HOME && git commit -m x", "/cwd") is None

    def test_backtick_in_dir_is_rejected(self):
        assert (
            _lib._leading_cd_dir("cd `echo /a` && git commit -m x", "/cwd") is None
        )

    def test_tilde_dir_is_expanduser_resolved(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        assert _lib._leading_cd_dir("cd ~/x && git commit -m x", "/cwd") == str(
            home / "x"
        )

    def test_relative_dir_joins_against_cwd(self):
        assert (
            _lib._leading_cd_dir("cd sub && git commit -m x", "/base")
            == "/base/sub"
        )

    def test_quoted_dir_with_spaces_is_unquoted(self):
        assert (
            _lib._leading_cd_dir('cd "/a b" && git commit -m x', "/cwd")
            == "/a b"
        )

    def test_nonexistent_dir_is_still_returned_deliberately(self, tmp_path):
        # DELIBERATE (plan-review residual note 2, #5061): with `&&` the
        # real shell runs NOTHING after a failed `cd` — there is no live
        # command to have targeted the wrong repo. Returning the (bogus)
        # dir here is harmless: the caller's own repo_root resolution then
        # fails on this nonexistent path and degrades to the no-repo path
        # (an allow over a command that executes nothing), never a wrong
        # cross-repo resolution. This is NOT a bug; it is documented and
        # pinned so a future "fix" doesn't quietly special-case a real
        # filesystem check into a function that must never do I/O to decide
        # its own contract.
        bogus = str(tmp_path / "does" / "not" / "exist")
        assert _lib._leading_cd_dir(f"cd {bogus} && git commit -m x", "/cwd") == bogus

    def test_no_cd_prefix_returns_none(self):
        assert _lib._leading_cd_dir("git commit -m x", "/cwd") is None

    def test_empty_command_returns_none(self):
        assert _lib._leading_cd_dir("", "/cwd") is None


class TestEffectiveGitCwd:
    def test_cd_prefix_alone_sets_the_base(self):
        assert (
            _lib.effective_git_cwd("cd /repoB && git commit -m x", "/repoA")
            == "/repoB"
        )

    def test_dash_c_on_the_git_segment_wins_over_the_cd_prefix(self):
        # A `-C` on the git invocation itself always wins for THAT segment —
        # composing in this order (cd prefix, then -C) means an explicit -C
        # is the more specific instruction and must not be overridden by a
        # preceding cd.
        assert (
            _lib.effective_git_cwd(
                "cd /a && git -C /y commit -m x", "/cwd"
            )
            == "/y"
        )

    def test_relative_dash_c_resolves_against_the_cd_prefix_base(self):
        # A relative `-C` path composes against the cd-established base, not
        # the raw event cwd — the cd already moved the frame the rest of the
        # command operates from.
        assert (
            _lib.effective_git_cwd(
                "cd /a && git -C rel commit -m x", "/cwd"
            )
            == "/a/rel"
        )

    def test_no_cd_no_dash_c_falls_back_to_cwd_unchanged(self):
        assert _lib.effective_git_cwd("git commit -m x", "/cwd") == "/cwd"

    def test_unsafe_cd_join_falls_back_to_cwd_not_the_unsafe_dir(self):
        # A `;`-joined cd is rejected by _leading_cd_dir (see
        # TestLeadingCdDir); effective_git_cwd's caller-facing contract is
        # that this degrades to plain `cwd`, bit-for-bit today's pre-#5061
        # behavior, never a silent guess at the unsafe dir.
        assert (
            _lib.effective_git_cwd("cd /a; git commit -m x", "/cwd") == "/cwd"
        )
