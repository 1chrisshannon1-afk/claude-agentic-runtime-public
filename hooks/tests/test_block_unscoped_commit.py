"""Hermetic tests for hooks/block_unscoped_commit.py.

The git_guard.sh add/commit vectors are the spec: every `git add` / `git commit`
case from ~/.claude/scripts/tests/test_git_guard.sh is reproduced here (see the
`_GIT_GUARD_ADD_COMMIT_VECTORS` table), then expanded to cover the pure decision
function's full branch matrix and the thin main() driver (log-only vs enforce,
dryrun, kill-switch, escape hatch, inline tripwire, parse-error fail-closed).

Everything runs against the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir) so the operator's real ~/.claude is never touched. No network; the
only subprocess is one throwaway invocation of the module through a sandboxed HOME
to cover the __main__ entry point.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys

import _lib  # noqa: F401  (imported for parity / sys.path shim via conftest)

# The module lives one dir up from tests/; conftest already put it on sys.path.
import block_unscoped_commit as guard
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
# PORTED SPEC — the git_guard.sh add/commit vectors, verbatim.
#
# (expected_block, description, command). ALLOW == not block, BLOCK == block.
# These are the exact `git add` / `git commit` lines from test_git_guard.sh,
# which the task names as the spec to reproduce.
# ===========================================================================

_GIT_GUARD_ADD_COMMIT_VECTORS = [
    # ---- add: bulk blocked, path-scoped allowed --------------------------
    (True, "git add -A", "git add -A"),
    (True, "git add -A extra whitespace", "git   add   -A"),
    (True, "git add --all", "git add --all"),
    (True, "git -C /x add -A (global stripped)", "git -C /x add -A"),
    (True, "git add .", "git add ."),
    (True, "git add -u", "git add -u"),
    (True, "git add --update", "git add --update"),
    (True, "git add :/", "git add :/"),
    (True, "git add -Au (combined short)", "git add -Au"),
    (False, "git add ./modules/x.py (path-scoped)", "git add ./modules/x.py"),
    (False, "git add path/A (path containing A)", "git add path/A"),
    (False, "git add modules/x.py y.py", "git add modules/x.py y.py"),
    (False, "git add -p (patch mode)", "git add -p"),
    (False, "git add ./path/Apple.py (A in name)", "git add ./path/Apple.py"),
    # ---- commit: -a family blocked, path/-m allowed ----------------------
    (True, "git commit -a -m x", 'git commit -a -m "x"'),
    (True, "git commit -am x", 'git commit -am "x"'),
    (True, "git commit --all", "git commit --all"),
    (False, "git commit -m msg (safe)", 'git commit -m "a message"'),
    # ---- compound involving add/commit -----------------------------------
    (False, "git add file.py && git commit -m x", 'git add file.py && git commit -m "x"'),
]


@pytest.mark.parametrize(
    "expected_block,desc,command",
    _GIT_GUARD_ADD_COMMIT_VECTORS,
    ids=[v[1] for v in _GIT_GUARD_ADD_COMMIT_VECTORS],
)
def test_git_guard_add_commit_vectors(expected_block, desc, command):
    assert _blocks(command) is expected_block, desc


# ===========================================================================
# EXPANSION — bulk-add reason tag + more staging flag shapes.
# ===========================================================================


@pytest.mark.parametrize(
    "command",
    [
        "git add -A",
        "git add --all",
        "git add -u",
        "git add --update",
        "git add .",
        "git add :/",
        "git add -Au",
        "git add -uA",
        "git add -uv",  # combined short with u + something
        "git add -Av",  # combined short with A + something
        "git add src/a.py -A",  # bulk flag AFTER a path still blocks
    ],
)
def test_bulk_add_blocks_with_reason(command):
    d = guard.decide(_ev(command))
    assert d.block is True
    assert d.reason == "bulk-add"


@pytest.mark.parametrize(
    "command",
    [
        "git add ./modules/x.py",
        "git add path/A",
        "git add path/Update.py",  # 'update' in a filename, not --update
        "git add ./all_files.py",  # 'all' in a filename, not --all
        "git add modules/x.py y.py",
        "git add -p",  # patch mode is fine
        "git add --patch",
        "git add -n file.py",  # dry-run add
        "git add -i",  # interactive add — no A/u letters
        "git add",  # bare add (no args) — not bulk
    ],
)
def test_scoped_add_allows(command):
    d = guard.decide(_ev(command))
    assert d.block is False
    assert d.reason == "no-bulk-add-or-commit-all"


# ===========================================================================
# EXPANSION — commit -a family + safe commits.
# ===========================================================================


@pytest.mark.parametrize(
    "command",
    [
        'git commit -a -m "x"',
        'git commit -am "x"',
        'git commit -ma "x"',  # letters reversed, still contains 'a'
        "git commit --all",
        "git commit -av",  # -a bundled with verbose
    ],
)
def test_commit_all_blocks_with_reason(command):
    d = guard.decide(_ev(command))
    assert d.block is True
    assert d.reason == "commit-all"


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "a message"',  # 'a message' text must NOT trigger -a
        "git commit --amend --no-edit",  # amend is not auto-stage-all
        "git commit -v",
        'git commit --message "msg with -a inside"',
        "git commit",  # bare commit
    ],
)
def test_safe_commit_allows(command):
    d = guard.decide(_ev(command))
    assert d.block is False
    assert d.reason == "no-bulk-add-or-commit-all"


# ===========================================================================
# EXPANSION — whole-token matching (NOT substring) is the crux.
# ===========================================================================


def test_whole_token_not_substring_add():
    # A filename that merely CONTAINS the letters of a bulk flag is a path token,
    # not a flag — it must ALLOW (naive substring matching would wrongly fire).
    # `path/-Anot` is a single token starting with 'p' (never a dash), so it is a
    # path argument, and `-A` embedded in it is not a whole-token flag match.
    assert _blocks("git add path/-Anot") is False
    # `--update` embedded in a path is likewise not the --update flag.
    assert _blocks("git add src/--update-helper.py") is False


def test_dot_only_as_whole_token_blocks():
    assert _blocks("git add .") is True
    # '.hidden' or './x' is a DIFFERENT token — allowed.
    assert _blocks("git add .hidden") is False
    assert _blocks("git add ./x") is False


def test_double_dash_all_is_whole_token():
    assert _blocks("git add --all") is True
    # a long flag that merely starts with --all... would need to be exact; guard
    # only blocks the exact token, so a hypothetical '--allow' is not blocked.
    assert _blocks("git add --allow-empty-message") is False


# ===========================================================================
# EXPANSION — compound / global-arg stripping still catches add/commit.
# ===========================================================================


def test_compound_semicolon_bulk_add_blocks():
    assert _blocks("git status ; git add -A") is True
    assert _reason("git status ; git add -A") == "bulk-add"


def test_compound_pipe_commit_all_blocks():
    assert _blocks("echo hi | git commit -am wip") is True
    assert _reason("echo hi | git commit -am wip") == "commit-all"


def test_compound_command_substitution_bulk_add():
    assert _blocks("foo $(git add --all)") is True


def test_compound_scoped_add_then_commit_allows():
    assert _blocks('git add file.py && git commit -m "x"') is False


def test_global_c_stripped_still_detects_commit_all():
    assert _blocks('git -c user.name=x commit -am "wip"') is True


def test_abs_path_git_bulk_add_blocks():
    assert _blocks("/usr/bin/git add -A") is True


def test_env_prefix_then_git_bulk_add_blocks():
    assert _blocks("ENV=1 OTHER=2 git add -A") is True


# ===========================================================================
# EXPANSION — out-of-scope git subcommands + non-git are ALLOWED.
#
# This module owns ONLY add/commit; state-verbs, branch -d, push, etc. are the
# concern of OTHER hook modules and must pass through here as allow.
# ===========================================================================


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git diff",
        "git log --oneline",
        "git show HEAD",
        "git fetch origin",
        "git push origin HEAD",
        "git checkout main",  # a state-verb — NOT this module's job
        "git reset --hard",  # ditto
        "git branch -D feat",  # ditto
        "git stash",  # ditto
        "ls -la",
        "rm -rf build",
        "gitfoo add -A",  # argv0 is not 'git'
        "mygit commit -am x",  # argv0 is not 'git'
    ],
)
def test_out_of_scope_and_non_git_allow(command):
    assert _blocks(command) is False


def test_bare_git_no_subcommand_allows():
    assert _blocks("git") is False
    assert _blocks("git -C /x") is False  # global only, no subcommand


# ===========================================================================
# decide() — the other pure-function branches.
# ===========================================================================


def test_non_bash_tool_allows():
    d = guard.decide(_ev("git add -A", tool_name="Read"))
    assert d.block is False
    assert d.reason == "not-bash-tool"


def test_missing_tool_name_allows():
    assert guard.decide({"tool_input": {"command": "git add -A"}}).reason == ("not-bash-tool")


def test_empty_command_allows():
    assert guard.decide(_ev("")).reason == "empty-command"
    assert guard.decide(_ev("   ")).reason == "empty-command"
    assert guard.decide(_ev(None)).reason == "empty-command"  # no tool_input


def test_inline_escape_var_blocks_even_with_safe_command():
    # Any command STRING that mentions the escape var is denied outright, even a
    # perfectly safe scoped add — an agent must never smuggle it inline.
    d = guard.decide(_ev("echo CSA_ALLOW_GIT_STATE_OPS=1 && git add file.py"))
    assert d.block is True
    assert d.reason == "inline-escape-var-forbidden"


def test_inline_escape_var_takes_precedence_over_bulk_add():
    d = guard.decide(_ev("CSA_ALLOW_GIT_STATE_OPS=1 git add -A"))
    assert d.reason == "inline-escape-var-forbidden"


def test_untokenizable_segment_with_git_fails_closed():
    # An unbalanced-quote segment that mentions git surfaces the sentinel -> BLOCK.
    d = guard.decide(_ev("git add 'unterminated"))
    assert d.block is True
    assert d.reason == "untokenizable-segment-with-git"


def test_untokenizable_segment_without_git_allows():
    # Unbalanced quotes but NO git mention -> nothing to guard.
    d = guard.decide(_ev("echo 'unterminated"))
    assert d.block is False


def test_untokenizable_segment_git_substring_only_allows():
    # #4670 item 3b: an untokenizable segment whose only "git"-like text
    # is a substring inside a longer word ("legitimate") must not trip the
    # sentinel here either -- this gate reuses _lib.git_segments (the same
    # shared tokenizer gate 1 and gate 3 also call), so the word-boundary
    # fix must propagate to this independent call site too.
    d = guard.decide(_ev("echo 'legitimate value"))
    assert d.block is False


def test_sentinel_only_real_git_untokenizable_segment_blocks_via_sentinel():
    # #4670 item 3b mandatory blast-radius test (fix-round correction): a
    # command carrying ONLY an untokenizable segment with a real
    # (word-boundary) git invocation -- no bulk-add/-A anywhere -- must still
    # reach and trip the sentinel after the word-boundary fix. This is the
    # non-vacuous half of the original "still blocks" test: the segment below
    # ("git add \" from a backslash-continued line, `a'b.py` on the next
    # line carrying the unbalanced quote) is untokenizable and mentions git
    # as a whole word, with NOTHING else in the command that could block it
    # first -- so a regression in the sentinel path (e.g. the word-boundary
    # predicate wrongly returning False here) is directly observable via the
    # reason, not masked by a second, unrelated trigger.
    d = guard.decide(_ev("git add \\\n  a'b.py"))
    assert d.block is True
    assert d.reason == "untokenizable-segment-with-git"


def test_compound_bulk_add_plus_untokenizable_real_git_segment_still_blocks():
    # Companion precedence-pinning test: when BOTH a bulk `git add -A` AND a
    # separate untokenizable real-git segment are present in the same
    # command, gate 2's per-segment loop hits the bulk-add segment FIRST
    # (segments are walked in command order and the loop returns on its first
    # match) -- so `bulk-add` wins, not the sentinel. This was proven
    # vacuous as originally written (it only asserted `d.block is True`,
    # which is trivially satisfied by bulk-add alone and says nothing about
    # whether the sentinel path was ever exercised -- confirmed empirically
    # by stubbing `_lib._raw_mentions_git` to always-False and observing this
    # assertion still passed). Asserting the specific reason here pins the
    # actual precedence and makes the test meaningful again; the sentinel's
    # OWN non-vacuous coverage lives in the test directly above (and in
    # `test_untokenizable_segment_with_git_fails_closed`).
    d = guard.decide(_ev("git add -A && git add \\\n  a'b.py"))
    assert d.block is True
    assert d.reason == "bulk-add"


def test_decide_swallows_internal_error(monkeypatch):
    # If git_segments blows up, decide degrades to a conservative allow.
    def boom(_cmd):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(guard._lib, "git_segments", boom)
    d = guard.decide(_ev("git add file.py"))
    assert d.block is False
    assert d.reason == "guard-error"


def test_git_argv_len_one_segment_skipped(monkeypatch):
    # Defensive: a git_segments entry with only ["git"] (len < 2, not sentinel)
    # must be skipped, not indexed. Force such an entry.
    monkeypatch.setattr(guard._lib, "git_segments", lambda _c: [["git"]])
    d = guard.decide(_ev("git"))
    assert d.block is False
    assert d.reason == "no-bulk-add-or-commit-all"


# ===========================================================================
# Helper units — _short_flags / _add_is_bulk / _commit_is_all.
# ===========================================================================


def test_decision_equality_and_inequality():
    # Decision.__eq__ underpins the terse assertions above; exercise it directly.
    assert guard.Decision(True, "bulk-add") == guard.Decision(True, "bulk-add")
    assert guard.Decision(True, "bulk-add") != guard.Decision(False, "bulk-add")
    assert guard.Decision(True, "bulk-add") != guard.Decision(True, "commit-all")
    # Comparison against a non-Decision is False, not an error.
    assert (guard.Decision(True, "x") == "not-a-decision") is False
    assert guard.Decision(True, "x") != object()


def test_syspath_shim_reinserts_when_absent():
    """Import the module fresh with _HOOKS_DIR absent from sys.path.

    conftest puts the hooks dir on sys.path before the module is first imported,
    so the module's import-time `sys.path.insert(0, _HOOKS_DIR)` guard is normally
    a no-op (its true branch never runs under pytest). We load the module source
    under a fresh module object with the dir removed from sys.path, forcing the
    self-bootstrap branch, then restore sys.path and sys.modules exactly.
    """
    hooks_dir = guard._HOOKS_DIR
    module_path = os.path.join(hooks_dir, "block_unscoped_commit.py")
    occurrences = sys.path.count(hooks_dir)
    saved_module = sys.modules.get("block_unscoped_commit")

    while hooks_dir in sys.path:
        sys.path.remove(hooks_dir)
    try:
        assert hooks_dir not in sys.path
        spec = importlib.util.spec_from_file_location(
            "block_unscoped_commit_freshimport", module_path
        )
        fresh = importlib.util.module_from_spec(spec)
        # Executing the module body runs the import-time shim; since hooks_dir is
        # absent, its `if _HOOKS_DIR not in sys.path` true branch fires.
        spec.loader.exec_module(fresh)
        assert hooks_dir in sys.path  # the shim re-inserted it
        # The fresh copy is fully functional (proves it self-bootstrapped _lib).
        assert fresh.decide(_ev("git add -A")).reason == "bulk-add"
    finally:
        # Restore sys.path multiplicity and the canonical module object.
        while hooks_dir in sys.path:
            sys.path.remove(hooks_dir)
        for _ in range(max(occurrences, 1)):
            sys.path.insert(0, hooks_dir)
        if saved_module is not None:
            sys.modules["block_unscoped_commit"] = saved_module


def test_short_flags_parsing():
    assert guard._short_flags("-Au") == {"A", "u"}
    assert guard._short_flags("-am") == {"a", "m"}
    assert guard._short_flags("--all") is None  # long option, not a bundle
    assert guard._short_flags("-") is None  # bare dash, len 1
    assert guard._short_flags("file.py") is None  # not a flag


def test_add_is_bulk_unit():
    assert guard._add_is_bulk(["-A"]) is True
    assert guard._add_is_bulk(["--update"]) is True
    assert guard._add_is_bulk(["-uA"]) is True
    assert guard._add_is_bulk(["./x.py", "y.py"]) is False
    assert guard._add_is_bulk(["-p"]) is False
    assert guard._add_is_bulk([]) is False


def test_commit_is_all_unit():
    assert guard._commit_is_all(["-am", "msg"]) is True
    assert guard._commit_is_all(["--all"]) is True
    assert guard._commit_is_all(["-m", "msg"]) is False
    assert guard._commit_is_all([]) is False


# ===========================================================================
# main() — thin driver. LOG-ONLY default, enforce emits deny, dryrun prints.
# ===========================================================================


def test_main_logonly_bulk_add_allows_but_logs(sandbox, clean_env, monkeypatch, capsys):
    # Default (not enforcing): a bulk add is a would-block that LOGS but emits
    # nothing and exits 0 (log-only allow).
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out == ""  # nothing emitted in log-only mode
    lines = sandbox.log_file.read_text().strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["hook"] == guard.HOOK_NAME
    assert rec["decision"] == "would-block"
    assert rec["reason"] == "bulk-add"
    assert rec["command"] == "git add -A"


def test_main_logonly_safe_add_no_log_no_output(sandbox, clean_env, monkeypatch, capsys):
    rc, out = _run_main(monkeypatch, _ev("git add ./x.py"), capsys)
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()  # allow path logs nothing


def test_main_enforce_emits_deny_for_bulk_add(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "bulk-add" in obj["systemMessage"]
    # It still logs the would-block.
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-block"
    assert rec["enforce"] is True


def test_main_enforce_emits_deny_for_commit_all(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev('git commit -am "wip"'), capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "commit-all" in obj["systemMessage"]


def test_main_enforce_does_not_deny_safe_commit(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev('git commit -m "msg"'), capsys)
    assert rc == 0
    assert out == ""  # no deny object for a safe commit


def test_main_enforce_via_global_marker(sandbox, clean_env, monkeypatch, capsys):
    # No CSA_ENFORCE env — enforcement comes from the ~/.claude/.enforce marker.
    sandbox.enforce_file.write_text("")
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ===========================================================================
# main() — dryrun harness mode.
# ===========================================================================


def test_main_dryrun_prints_block(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out.strip() == "BLOCK"


def test_main_dryrun_prints_allow(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(monkeypatch, _ev("git add ./x.py"), capsys)
    assert rc == 0
    assert out.strip() == "ALLOW"


def test_main_dryrun_block_takes_priority_over_enforce_emit(
    sandbox, clean_env, monkeypatch, capsys
):
    # In dryrun the decision WORD is printed even when enforcing; the deny object
    # is NOT emitted (dryrun short-circuits before the enforce branch).
    clean_env.setenv("CSA_GUARD_DRYRUN", "print")
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out.strip() == "BLOCK"
    assert "permissionDecision" not in out


# ===========================================================================
# main() — master kill switch.
# ===========================================================================


def test_main_disable_hooks_noop_allow(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    clean_env.setenv("CSA_ENFORCE", "1")  # even with enforce ON, disable wins
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()  # no-op: not even a log line


def test_main_disable_hooks_dryrun_still_reports_allow(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    clean_env.setenv("CSA_GUARD_DRYRUN", "print")
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out.strip() == "ALLOW"


# ===========================================================================
# main() — escape hatch (OWN env) vs inline tripwire.
# ===========================================================================


def test_main_escape_hatch_own_env_allows_bulk_add(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
    clean_env.setenv("CSA_ENFORCE", "1")  # would deny, but escape hatch overrides
    rc, out = _run_main(monkeypatch, _ev("git add -A"), capsys)
    assert rc == 0
    assert out == ""  # allowed through, no deny
    # An escape-allowed audit line is written.
    decisions = [
        json.loads(x)["decision"] for x in sandbox.log_file.read_text().strip().splitlines()
    ]
    assert "escape-allowed" in decisions


def test_main_escape_hatch_does_not_rescue_inline_tripwire(sandbox, clean_env, monkeypatch, capsys):
    # The escape var in the OWN env must NOT rescue a command that smuggled the
    # var name inline — that specific block stands.
    clean_env.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
    clean_env.setenv("CSA_ENFORCE", "1")
    cmd = "echo CSA_ALLOW_GIT_STATE_OPS=1 && git add file.py"
    rc, out = _run_main(monkeypatch, _ev(cmd), capsys)
    assert rc == 0
    obj = json.loads(out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "inline-escape-var-forbidden" in obj["systemMessage"]


def test_main_escape_hatch_logonly_still_allows(sandbox, clean_env, monkeypatch, capsys):
    # Escape hatch in log-only mode: allowed, and the escape-allowed line logged.
    clean_env.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
    rc, out = _run_main(monkeypatch, _ev("git commit -am wip"), capsys)
    assert rc == 0
    assert out == ""
    decisions = [
        json.loads(x)["decision"] for x in sandbox.log_file.read_text().strip().splitlines()
    ]
    assert "escape-allowed" in decisions


# ===========================================================================
# main() — non-Bash / empty / parse-error paths.
# ===========================================================================


def test_main_non_bash_tool_allows(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(
        monkeypatch, {"tool_name": "Read", "tool_input": {"command": "git add -A"}}, capsys
    )
    assert rc == 0
    assert out == ""


def test_main_empty_stdin_allows(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, "", capsys)
    assert rc == 0
    assert out == ""


def test_main_garbage_stdin_allows(sandbox, clean_env, monkeypatch, capsys):
    # Non-JSON stdin -> read_event returns {} -> not-bash-tool -> allow. Even in
    # enforce mode this must not emit a deny (this module scopes to add/commit and
    # has nothing to fail-closed on when the tool_name isn't even Bash).
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, "total garbage not json", capsys)
    assert rc == 0
    assert out == ""


def test_main_enforce_dryrun_off_logonly_bulk_add_silent(sandbox, clean_env, monkeypatch, capsys):
    # Sanity: not enforcing, not dryrun -> a would-block is silent (log only).
    rc, out = _run_main(monkeypatch, _ev("git commit --all"), capsys)
    assert rc == 0
    assert out == ""
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["reason"] == "commit-all"


# ===========================================================================
# Entry point — cover the __main__ guard via a real (sandboxed) subprocess.
# ===========================================================================


def test_module_runs_as_script_dryrun_block(tmp_path):
    """Invoke the module as `python block_unscoped_commit.py` with a sandbox HOME.

    Exercises the `if __name__ == "__main__": sys.exit(main())` entry point end to
    end. HOME points into tmp_path so no real ~/.claude is touched; no network.
    """
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    module_path = os.path.join(guard._HOOKS_DIR, "block_unscoped_commit.py")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git add -A"}})
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["CSA_GUARD_DRYRUN"] = "print"
    env.pop("CSA_ENFORCE", None)
    env.pop("CSA_DISABLE_HOOKS", None)
    env.pop("CSA_ALLOW_GIT_STATE_OPS", None)
    proc = subprocess.run(
        [sys.executable, module_path],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "BLOCK"


def test_module_runs_as_script_dryrun_allow(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    module_path = os.path.join(guard._HOOKS_DIR, "block_unscoped_commit.py")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git add ./safe.py"}})
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["CSA_GUARD_DRYRUN"] = "print"
    env.pop("CSA_ENFORCE", None)
    env.pop("CSA_DISABLE_HOOKS", None)
    proc = subprocess.run(
        [sys.executable, module_path],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "ALLOW"
