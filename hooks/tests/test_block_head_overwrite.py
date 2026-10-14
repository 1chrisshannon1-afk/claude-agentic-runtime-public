"""Hermetic tests for hooks/block_head_overwrite.py.

GH #4387 is the spec: an agent ran `git show HEAD:<path> > <path>` to
"restore formatting sanity" and permanently destroyed uncommitted,
never-staged feature work with no git-recoverable trace. This suite covers
the pure decision function's full branch matrix (the exact exploit shape,
adjacent-but-legitimate patterns that must NOT block, and edge cases) plus
the thin main() driver (log-only vs enforce, dryrun, kill-switch, escape
hatch, inline tripwire).

Everything runs against the `sandbox` fixture ($HOME + _lib path constants
pointed into a tmp dir) so the operator's real ~/.claude is never touched.
No network, no subprocess except one throwaway invocation of the module
through a sandboxed HOME to cover the __main__ entry point.
"""

from __future__ import annotations

import io
import json

import _lib  # noqa: F401  (imported for parity / sys.path shim via conftest)

# The module lives one dir up from tests/; conftest already put it on sys.path.
import block_head_overwrite as guard
import pytest

# ===========================================================================
# Helpers.
# ===========================================================================


def _ev(command, tool_name="Bash", **extra):
    """Build a Bash PreToolUse event dict."""
    ev = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    ev.update(extra)
    return ev


def _reason(command, tool_name="Bash"):
    return guard.decide(_ev(command, tool_name=tool_name)).reason


def _blocks(command, tool_name="Bash"):
    return guard.decide(_ev(command, tool_name=tool_name)).block


def _run_main(monkeypatch, payload, capsys):
    """Drive main() end-to-end with `payload` (dict|str) on stdin; return (rc, out)."""
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = guard.main()
    out = capsys.readouterr().out
    return rc, out


# ===========================================================================
# The exact GH #4387 exploit shape, and its `cat-file` sibling.
# ===========================================================================

_EXPLOIT_VECTORS = [
    (
        "the exact GH #4387 shape (relative path both sides)",
        "git show HEAD:agency/src/components/dental_analytics/PayerAnalysisPanel.jsx "
        "> agency/src/components/dental_analytics/PayerAnalysisPanel.jsx",
    ),
    (
        "absolute destination path, repo-relative ref:path",
        "git show HEAD:agency/src/components/dental_analytics/PayerAnalysisPanel.jsx "
        "> /Users/x/Desktop/OtherApp/agency/src/components/dental_analytics/"
        "PayerAnalysisPanel.jsx",
    ),
    ("append form (>>) is equally destructive", "git show HEAD:foo.py >> foo.py"),
    ("a non-HEAD ref (branch name)", "git show main:foo.py > foo.py"),
    ("a non-HEAD ref (remote branch)", "git show origin/main:foo.py > foo.py"),
    ("a relative-form ref (HEAD~2)", "git show HEAD~2:foo.py > foo.py"),
    ("a full SHA ref", "git show abc123def456:foo.py > foo.py"),
    ("./-prefixed destination", "git show HEAD:foo.py > ./foo.py"),
    ("./-prefixed source path", "git show HEAD:./foo.py > foo.py"),
    ("cat-file -p equivalent", "git cat-file -p HEAD:foo.py > foo.py"),
    ("cat-file -p equivalent, append form", "git cat-file -p HEAD:foo.py >> foo.py"),
    ("compound command via &&", "cd /tmp && git show HEAD:foo.py > foo.py"),
    (
        "git -C <dir> global option stripped first",
        "git -C /some/repo show HEAD:foo.py > foo.py",
    ),
    # Glued (unspaced) redirect variants -- code-reviewer BLOCKER: shlex.split
    # (which _lib.git_segments() uses) does NOT split a redirect operator
    # glued to adjacent text the way a real shell does. A real shell treats
    # `>foo.py`, `foo.py>`, `foo.py>bar.py`, and `1>foo.py` identically to
    # the spaced `> foo.py` form -- every one of these is an equally live
    # exploit shape an agent could plausibly reach for after being denied
    # on the spaced form.
    ("glued redirect, no space before dest", "git show HEAD:foo.py >foo.py"),
    ("glued redirect, no space after source", "git show HEAD:foo.py> foo.py"),
    ("glued redirect, no space either side", "git show HEAD:foo.py>foo.py"),
    ("glued append, no space before dest", "git show HEAD:foo.py >>foo.py"),
    ("glued append, no space either side", "git show HEAD:foo.py>>foo.py"),
    ("fd-qualified redirect with space", "git show HEAD:foo.py 1> foo.py"),
    ("fd-qualified redirect, glued", "git show HEAD:foo.py 1>foo.py"),
    ("cat-file, glued redirect", "git cat-file -p HEAD:foo.py>foo.py"),
    # ROUND 3 (code-reviewer, 2026-09-05): 5 MORE confirmed-destructive
    # variants, verified in a real bash AND zsh shell against a scratch git
    # repo with genuine uncommitted content -- every one destroyed it. These
    # exploit the fact that `|` and `&` are ALSO redirect-operator
    # characters in specific adjacent positions, which `_lib.git_segments()`
    # (built for git-state-verb parsing, where those characters genuinely
    # ARE command separators) tears apart before round 1/2's tokenizer-based
    # detection ever saw them. This is why round 3 stopped using that
    # tokenizer for this hook's detection entirely -- see the module's own
    # ROUND 3 docstring note.
    ("noclobber override (>|), spaced", "git show HEAD:foo.py >| foo.py"),
    ("noclobber override (>|), glued", "git show HEAD:foo.py >|foo.py"),
    ("fd-qualified noclobber override, spaced", "git show HEAD:foo.py 1>| foo.py"),
    ("fd-duplication then real redirect", "git show HEAD:foo.py 2>&1 > foo.py"),
    (
        "two operators in one token, second is the real hit",
        "git show HEAD:foo.py >/tmp/x>foo.py",
    ),
    # Self-review adversarial pass (2026-09-05): quoted destinations/specs
    # are a real, common shell spelling and were confirmed missed before
    # `_normalize_path`/the ref:path extraction stripped a matched
    # surrounding quote pair.
    ("double-quoted destination", 'git show HEAD:foo.py > "foo.py"'),
    ("single-quoted destination", "git show HEAD:foo.py > 'foo.py'"),
    ("double-quoted ref:path spec", 'git show "HEAD:foo.py" > foo.py'),
    ("single-quoted ref:path spec", "git show 'HEAD:foo.py' > foo.py"),
    ("both quoted", 'git show "HEAD:foo.py" > "foo.py"'),
    # ROUND 4 (code-reviewer cold review, 2026-09-05): 6 MORE
    # live-shell-confirmed-destructive shapes (bash AND zsh), found by
    # adversarial fuzzing against a scratch git repo with genuine
    # uncommitted content.
    ("bash '>&' both-streams redirect", "git show HEAD:foo.py >& foo.py"),
    ("subshell wrapping", "(git show HEAD:foo.py > foo.py)"),
    ("brace-group wrapping", "{ git show HEAD:foo.py > foo.py; }"),
    (
        "glued --long-opt=value global option",
        "git --git-dir=.git show HEAD:foo.py > foo.py",
    ),
    (
        "cat-file bare format word (no -p flag)",
        "git cat-file blob HEAD:foo.py > foo.py",
    ),
    (
        "backslash line-continuation before the redirect",
        "git show HEAD:foo.py \\\n> foo.py",
    ),
    # ROUND 5 (code-reviewer cold review, 2026-09-05), Blocker 1: shell
    # keyword/command-prefix invocation boundaries. The round-4 fix widened
    # `_GIT_SHOW_INVOKE_RE`'s leading-boundary alternation to admit `(){}$(`,
    # but that is itself an enumeration that does not generalize -- ANY
    # word-plus-space immediately before `git` (a shell keyword body, or a
    # command-prefix wrapper) was still invisible to the old alternation.
    # All 15 confirmed live in bash. Fixed via a word-boundary negative
    # lookbehind (`(?<![\w./-])`) replacing the enumerated alternation.
    ("if/then keyword-body prefix", "if true; then git show HEAD:foo.py > foo.py; fi"),
    (
        "for/do keyword-body prefix",
        "for i in 1; do git show HEAD:foo.py > foo.py; done",
    ),
    (
        "while/do keyword-body prefix",
        "while true; do git show HEAD:foo.py > foo.py; done",
    ),
    (
        "until/do keyword-body prefix",
        "until false; do git show HEAD:foo.py > foo.py; done",
    ),
    ("nohup command-prefix wrapper", "nohup git show HEAD:foo.py > foo.py"),
    ("time command-prefix wrapper", "time git show HEAD:foo.py > foo.py"),
    (
        "exec command-prefix (not exec-scoped redirect)",
        "exec git show HEAD:foo.py > foo.py",
    ),
    ("command builtin prefix", "command git show HEAD:foo.py > foo.py"),
    ("stdbuf command-prefix wrapper", "stdbuf -o0 git show HEAD:foo.py > foo.py"),
    ("! negation prefix", "! git show HEAD:foo.py > foo.py"),
    # ROUND 5, Blocker 2: embedded/partial shell quoting. A prior version of
    # `_normalize_path`/the ref:path extraction stripped only a single,
    # FULLY-MATCHED pair of surrounding quotes. A real shell removes
    # quoting/escaping PER-CHARACTER, so quoting embedded ANYWHERE in the
    # word is an equally real, equally destructive spelling. All 5 confirmed
    # live in bash.
    ("double-quote glued mid-word in destination", 'git show HEAD:foo.py > "foo".py'),
    (
        "single-quote glued mid-word in the ref:path spec",
        "git show HEAD:fo'o'.py > foo.py",
    ),
    ("bare backslash-escaped char in destination", "git show HEAD:foo.py > foo\\.py"),
    (
        "single-quoted prefix glued to the rest of the destination",
        "git show HEAD:foo.py > 'foo'.py",
    ),
    (
        "single-quoted prefix glued to the rest of the ref:path spec",
        "git show HEAD:'foo'.py > foo.py",
    ),
    # ROUND 6 (code-reviewer cold review, 2026-09-05), Blocker 1: a
    # backtick-wrapped whole invocation (command substitution) leaked
    # through because the round-5 invoke-boundary lookbehind admits a
    # backtick as an opener, but `_redirect_destinations`'s stop-set was
    # never re-widened to match -- the destination was captured WITH the
    # trailing backtick glued on. Both confirmed live-destructive in bash.
    (
        "backtick-wrapped whole invocation (command substitution)",
        "`git show HEAD:foo.py > foo.py`",
    ),
    (
        "backtick-wrapped invocation in an assignment",
        "x=`git show HEAD:foo.py > foo.py`",
    ),
    # ROUND 6, Blocker 2: `$"..."` (bash locale-translation quoting) shares
    # the same closing `"` and escape set as plain double-quoting, but
    # `_shell_unquote`'s `$` branch only recognized a following `'`
    # (ANSI-C), so `$"foo.py"` fell through to the bare-character path and
    # never unquoted. Confirmed live-destructive in bash.
    (
        "dollar-double-quoted destination (locale string)",
        'git show HEAD:foo.py > $"foo.py"',
    ),
    (
        "dollar-double-quoted ref:path spec (locale string)",
        'git show HEAD:$"foo.py" > foo.py',
    ),
]


@pytest.mark.parametrize(
    "desc,command", _EXPLOIT_VECTORS, ids=[v[0] for v in _EXPLOIT_VECTORS]
)
def test_blocks_self_overwrite_shapes(desc, command):
    assert _blocks(command) is True, f"expected BLOCK for: {desc}"


# ===========================================================================
# Legitimate / adjacent patterns that must NOT block.
# ===========================================================================

_ALLOWED_VECTORS = [
    (
        "redirect to a DIFFERENT path (backup/scratch extraction)",
        "git show HEAD:foo.py > foo.py.bak",
    ),
    (
        "redirect to a DIFFERENT path (renamed extraction)",
        "git show HEAD:foo.py > /tmp/old_foo.py",
    ),
    ("no redirect at all -- just inspecting", "git show HEAD:foo.py"),
    ("bare git show with no ref:path (e.g. showing the last commit)", "git show HEAD"),
    ("git diff -- <path> (the recommended alternative)", "git diff -- foo.py"),
    ("git log with no redirect", "git log --oneline -5"),
    ("git status", "git status"),
    ("a completely unrelated redirect", "echo hello > foo.py"),
    ("cat piping a DIFFERENT file's content", "cat other.py > foo.py"),
    (
        "git show of a DIFFERENT file than the destination",
        "git show HEAD:bar.py > foo.py",
    ),
    (
        "only a partial path-segment match (must not false-positive)",
        "git show HEAD:Foo.jsx > components/Foo.jsx",
    ),
    ("empty command", ""),
    ("git show with options but no redirect", "git show --stat HEAD:foo.py"),
    ("glued redirect to a DIFFERENT path", "git show HEAD:foo.py >bar.py"),
    ("glued redirect, both sides different, no space", "git show HEAD:foo.py>bar.py"),
    ("quoted destination, DIFFERENT path", 'git show HEAD:foo.py > "bar.py"'),
    ("quoted ref:path spec, DIFFERENT destination", 'git show "HEAD:foo.py" > bar.py'),
    # ROUND 4 counterparts: the new shapes above, redirected to a DIFFERENT
    # path, must still ALLOW.
    ("'>&' both-streams, DIFFERENT path", "git show HEAD:foo.py >& bar.py"),
    ("subshell wrapping, DIFFERENT path", "(git show HEAD:foo.py > bar.py)"),
    ("brace-group wrapping, DIFFERENT path", "{ git show HEAD:foo.py > bar.py; }"),
    (
        "cat-file bare format word, DIFFERENT path",
        "git cat-file blob HEAD:foo.py > bar.py",
    ),
    # ROUND 4 out-of-scope shapes (documented CONTRACT boundary, see module
    # docstring): dynamic expansion, eval, exec-scoped redirects, and
    # pipe-to-writer tools are undecidable from static command text alone.
    # These are destructive in a live shell but this hook correctly does
    # not (and structurally cannot) catch them -- listed here so a future
    # round doesn't relitigate them as oversights.
    (
        "dynamic destination via command substitution (out of scope)",
        "git show HEAD:foo.py > $(echo foo.py)",
    ),
    ("dynamic destination via variable (out of scope)", "git show HEAD:foo.py > $F"),
    ("pipe to tee (out of scope)", "git show HEAD:foo.py | tee foo.py"),
    ("exec-scoped redirect (out of scope)", "exec > foo.py; git show HEAD:foo.py"),
    # ROUND 5 counterparts: false-positive checks for the word-boundary fix
    # (a lookalike command name must NOT match) plus DIFFERENT-path
    # counterparts for every new keyword/prefix and embedded-quoting shape.
    ("false-positive check: mygit is not git", "mygit show HEAD:foo.py > foo.py"),
    (
        "false-positive check: ./git relative-path invocation",
        "./git show HEAD:foo.py > foo.py",
    ),
    ("false-positive check: my-git is not git", "my-git show HEAD:foo.py > foo.py"),
    (
        "if/then keyword-body prefix, DIFFERENT path",
        "if true; then git show HEAD:foo.py > bar.py; fi",
    ),
    (
        "for/do keyword-body prefix, DIFFERENT path",
        "for i in 1; do git show HEAD:foo.py > bar.py; done",
    ),
    (
        "nohup command-prefix wrapper, DIFFERENT path",
        "nohup git show HEAD:foo.py > bar.py",
    ),
    (
        "time command-prefix wrapper, DIFFERENT path",
        "time git show HEAD:foo.py > bar.py",
    ),
    ("command builtin prefix, DIFFERENT path", "command git show HEAD:foo.py > bar.py"),
    (
        "stdbuf command-prefix wrapper, DIFFERENT path",
        "stdbuf -o0 git show HEAD:foo.py > bar.py",
    ),
    ("! negation prefix, DIFFERENT path", "! git show HEAD:foo.py > bar.py"),
    (
        "double-quote glued mid-word, DIFFERENT path",
        'git show HEAD:foo.py > "bar".py',
    ),
    (
        "single-quote glued mid-word in ref:path spec, DIFFERENT path",
        "git show HEAD:fo'o'.py > bar.py",
    ),
    (
        "bare backslash-escaped char, DIFFERENT path",
        "git show HEAD:foo.py > bar\\.py",
    ),
    (
        "single-quoted prefix glued to destination, DIFFERENT path",
        "git show HEAD:foo.py > 'bar'.py",
    ),
    (
        "single-quoted prefix glued to ref:path spec, DIFFERENT path",
        "git show HEAD:'foo'.py > bar.py",
    ),
    (
        "backtick-wrapped invocation, DIFFERENT path",
        "`git show HEAD:foo.py > bar.py`",
    ),
    (
        "backtick-wrapped invocation in an assignment, DIFFERENT path",
        "x=`git show HEAD:foo.py > bar.py`",
    ),
    (
        "dollar-double-quoted destination, DIFFERENT path",
        'git show HEAD:foo.py > $"bar.py"',
    ),
    (
        "dollar-double-quoted ref:path spec, DIFFERENT destination",
        'git show HEAD:$"foo.py" > bar.py',
    ),
]


@pytest.mark.parametrize(
    "desc,command", _ALLOWED_VECTORS, ids=[v[0] for v in _ALLOWED_VECTORS]
)
def test_allows_legitimate_patterns(desc, command):
    assert _blocks(command) is False, f"expected ALLOW for: {desc}"


def test_reason_tag_matches_subcommand():
    assert _reason("git show HEAD:foo.py > foo.py") == "show-redirect-self-overwrite"
    assert (
        _reason("git cat-file -p HEAD:foo.py > foo.py")
        == "cat-file-redirect-self-overwrite"
    )


# ===========================================================================
# _redirect_destinations — the raw-text redirect-operator scanner (ROUND 3).
# ===========================================================================


class TestRedirectDestinations:
    def test_spaced_redirect(self):
        assert guard._redirect_destinations(" > foo.py") == ["foo.py"]

    def test_glued_before_dest(self):
        assert guard._redirect_destinations(" >foo.py") == ["foo.py"]

    def test_glued_after_source_no_dest_before_op(self):
        """The operator only ever produces a destination from what comes
        AFTER it -- text before the operator is not this function's concern
        (the caller already consumed that as the ref:path spec)."""
        assert guard._redirect_destinations(">foo.py") == ["foo.py"]

    def test_append_form(self):
        assert guard._redirect_destinations(" >> foo.py") == ["foo.py"]

    def test_fd_qualified(self):
        assert guard._redirect_destinations(" 1> foo.py") == ["foo.py"]
        assert guard._redirect_destinations(" 1>foo.py") == ["foo.py"]

    def test_noclobber_override(self):
        assert guard._redirect_destinations(" >| foo.py") == ["foo.py"]
        assert guard._redirect_destinations(" >|foo.py") == ["foo.py"]

    def test_fd_qualified_noclobber(self):
        assert guard._redirect_destinations(" 1>| foo.py") == ["foo.py"]

    def test_fd_duplication_has_no_destination(self):
        """`2>&1` duplicates fd 2 onto fd 1 -- there is no FILE destination
        here at all, and this must never be misread as one."""
        assert guard._redirect_destinations(" 2>&1") == []

    def test_fd_duplication_then_real_redirect(self):
        """The exact round-3 bypass: a duplication with no destination,
        immediately followed by a real redirect -- only the real one
        contributes a destination."""
        assert guard._redirect_destinations(" 2>&1 > foo.py") == ["foo.py"]

    def test_two_operators_both_contribute(self):
        """Multiple redirects in one region each produce their own
        destination -- a caller must check ALL of them, not just the last,
        since shell evaluates every redirect as a real write."""
        assert guard._redirect_destinations(" >/tmp/x>foo.py") == ["/tmp/x", "foo.py"]

    def test_no_operator_no_destinations(self):
        assert guard._redirect_destinations(" foo.py bar.py") == []

    def test_empty_string(self):
        assert guard._redirect_destinations("") == []

    def test_dangling_operator_no_destination(self):
        assert guard._redirect_destinations(" >") == []
        assert guard._redirect_destinations(" > ") == []

    def test_destination_bounded_by_separator(self):
        """A destination never crosses a real separator or another
        operator/pipe/background character."""
        assert guard._redirect_destinations(" > foo.py; echo done") == ["foo.py"]
        assert guard._redirect_destinations(" > foo.py && echo done") == ["foo.py"]


# ===========================================================================
# _same_target — the path-comparison helper directly.
# ===========================================================================


class TestSameTarget:
    def test_exact_match(self):
        assert guard._same_target("foo.py", "foo.py") is True

    def test_dot_slash_prefix_normalized(self):
        assert guard._same_target("./foo.py", "foo.py") is True
        assert guard._same_target("foo.py", "./foo.py") is True

    def test_quoted_destination_matches_unquoted_ref(self):
        """A real, common shell spelling -- `> "foo.py"` is exactly as
        destructive as `> foo.py`."""
        assert guard._same_target("foo.py", '"foo.py"') is True
        assert guard._same_target("foo.py", "'foo.py'") is True

    def test_quoted_ref_matches_unquoted_destination(self):
        assert guard._same_target('"foo.py"', "foo.py") is True

    def test_quoted_different_path_does_not_match(self):
        assert guard._same_target("foo.py", '"bar.py"') is False

    def test_mismatched_quote_chars_not_stripped(self):
        """A genuinely malformed/mismatched quote pair (not real shell
        syntax) is left as-is rather than guessed at -- it simply won't
        match, which is the safe (ALLOW) direction for this narrow gate."""
        assert guard._same_target("foo.py", "'foo.py\"") is False

    def test_absolute_dest_suffix_match(self):
        assert (
            guard._same_target(
                "agency/src/foo.jsx", "/Users/x/Desktop/OtherApp/agency/src/foo.jsx"
            )
            is True
        )

    def test_absolute_dest_no_suffix_match(self):
        assert (
            guard._same_target(
                "agency/src/foo.jsx", "/Users/x/Desktop/OtherApp/other/foo.jsx"
            )
            is False
        )

    def test_partial_segment_is_not_a_match(self):
        """A bare string-suffix match would wrongly match 'Foo.jsx' against
        '.../components/Foo.jsx' -- this must require a full, segment-aligned
        path match, not a filename-only coincidence."""
        assert guard._same_target("Foo.jsx", "/repo/components/Foo.jsx") is False

    def test_different_relative_paths(self):
        assert guard._same_target("foo.py", "bar.py") is False

    def test_empty_inputs_never_match(self):
        assert guard._same_target("", "foo.py") is False
        assert guard._same_target("foo.py", "") is False
        assert guard._same_target("", "") is False


# ===========================================================================
# Escape hatch / inline tripwire (shared CSA_ALLOW_GIT_STATE_OPS var).
# ===========================================================================


def test_inline_tripwire_always_blocks_even_with_env_escape(monkeypatch):
    monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
    command = "git show HEAD:foo.py > foo.py  # CSA_ALLOW_GIT_STATE_OPS"
    d = guard.decide(_ev(command))
    assert d.block is True
    assert d.reason == "inline-escape-var-forbidden"


def test_env_escape_hatch_allows_via_main(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
    rc, _ = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py"), capsys)
    assert rc == 0
    log_lines = (
        sandbox.log_file.read_text().splitlines() if sandbox.log_file.exists() else []
    )
    assert any(
        '"escape-allowed"' in ln and "block_head_overwrite" in ln for ln in log_lines
    )


# ===========================================================================
# main() driver: log-only vs enforce, dryrun, kill-switch.
# ===========================================================================


def test_main_log_only_allows_and_logs(sandbox, monkeypatch, capsys):
    """Default (no CSA_ENFORCE): would-block is logged but the tool call is
    allowed (rc 0, no deny JSON printed)."""
    rc, out = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py"), capsys)
    assert rc == 0
    assert out == ""
    log_lines = sandbox.log_file.read_text().splitlines()
    assert any(
        '"would-block"' in ln and "block_head_overwrite" in ln for ln in log_lines
    )


def test_main_enforce_emits_deny(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py"), capsys)
    assert rc == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "block_head_overwrite"
        in payload["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_main_enforce_allows_legitimate_pattern(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py.bak"), capsys)
    assert rc == 0
    assert out == ""


def test_kill_switch_short_circuits_before_anything(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py"), capsys)
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_dryrun_mode_prints_block(monkeypatch, capsys):
    monkeypatch.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(monkeypatch, _ev("git show HEAD:foo.py > foo.py"), capsys)
    assert rc == 0
    assert out.strip() == "BLOCK"


def test_dryrun_mode_prints_allow(monkeypatch, capsys):
    monkeypatch.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(monkeypatch, _ev("git status"), capsys)
    assert rc == 0
    assert out.strip() == "ALLOW"


def test_non_bash_tool_never_blocks(monkeypatch, capsys):
    monkeypatch.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(
        monkeypatch, _ev("git show HEAD:foo.py > foo.py", tool_name="Read"), capsys
    )
    assert rc == 0
    assert out.strip() == "ALLOW"


def test_malformed_json_degrades_to_allow(monkeypatch, capsys):
    rc, out = _run_main(monkeypatch, "{not valid json", capsys)
    assert rc == 0
    assert out == ""


# ===========================================================================
# decide() never raises on garbage input.
# ===========================================================================


@pytest.mark.parametrize(
    "ev",
    [
        {},
        {"tool_name": "Bash"},
        {"tool_name": "Bash", "tool_input": {}},
        {"tool_name": "Bash", "tool_input": {"command": None}},
        {"tool_name": "Bash", "tool_input": {"command": 12345}},
        {"tool_name": None},
        None,
    ],
    ids=[
        "empty",
        "no-input",
        "empty-input",
        "none-command",
        "int-command",
        "none-tool-name",
        "none-event",
    ],
)
def test_decide_never_raises_on_garbage(ev):
    d = guard.decide(ev if ev is not None else {})
    assert d.block is False


def test_find_redirect_overwrite_never_raises_on_garbage():
    for bad_command in (
        "",
        "git",
        "git show",
        "git show no-colon-here > x",
        None,
        12345,
        [],
    ):
        assert guard._find_redirect_overwrite(bad_command) is None


def test_redirect_destinations_never_raises_on_garbage():
    for bad_text in (None, 12345, []):
        assert guard._redirect_destinations(bad_text) == []
