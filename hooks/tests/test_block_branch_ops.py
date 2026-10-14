"""Hermetic tests for hooks/block_branch_ops.py.

The behavioral spec is the proven bash guard's own harness
~/.claude/scripts/tests/test_git_guard.sh — EVERY vector there is reproduced
here as a pytest case (see TestPortedGitGuardVectors), then expanded with
main()/enforcement/log-only/escape-hatch/parse-error coverage.

Two layers of testing:
  * decision(command) — the PURE policy core. Trivially asserted, no I/O.
  * main() — the thin driver. Driven by feeding a JSON payload on stdin
    (monkeypatched) and capturing stdout + the JSONL decision log, all inside
    the hermetic `sandbox` fixture so the real ~/.claude is never touched.

Every test runs under the sandbox ($HOME + _lib path constants -> tmp dir) or at
minimum clean_env, so no real enforcement state, network, or git is involved.
"""

from __future__ import annotations

import io
import json

import _lib  # noqa: F401  (ensures the hooks dir is on sys.path via conftest)
import block_branch_ops as bbo
import pytest

# ===========================================================================
# Helpers.
# ===========================================================================


def _blocked(command: str) -> bool:
    """Convenience: does the pure decision block this command?"""
    return bbo.decision(command)[0]


def _reason(command: str) -> str:
    return bbo.decision(command)[1]


def _run_main(monkeypatch, payload, *, env=None):
    """Feed a JSON payload (dict or raw str) to main() via stdin and capture.

    Returns (exit_code, stdout_str). Any env dict is applied with monkeypatch.
    """
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = bbo.main()
    return rc, buf.getvalue()


def _is_deny(stdout: str) -> bool:
    """True iff stdout is the canonical PreToolUse deny object."""
    if not stdout.strip():
        return False
    try:
        obj = json.loads(stdout)
    except Exception:
        return False
    hso = obj.get("hookSpecificOutput", {})
    return hso.get("hookEventName") == "PreToolUse" and hso.get("permissionDecision") == "deny"


def _read_log(sandbox):
    """Return the parsed JSONL decision-log records (empty list if none)."""
    if not sandbox.log_file.exists():
        return []
    return [json.loads(line) for line in sandbox.log_file.read_text().strip().splitlines() if line]


# ===========================================================================
# PORTED VECTORS — one pytest case per assert_decision in test_git_guard.sh.
#
# Each (command, expected_block) pair is copied verbatim from the bash harness.
# This is the spec; if the module diverges from the proven guard, one of these
# fails. Parametrization keeps them 1:1 and greppable against the source.
# ===========================================================================


class TestPortedGitGuardVectors:
    # (command, should_block) — mirrors test_git_guard.sh assert_decision lines.
    VECTORS = [
        # ---- REQUIRED VECTORS from the task ----
        ("git   add   -A", True),  # extra whitespace
        ("git add --all", True),
        ("git -C /x add -A", True),
        ("GIT_DIR=x git reset --hard", True),
        ("true && git checkout -b x", True),  # compound
        ("git add ./modules/x.py", False),  # path-scoped
        ("git add path/A", False),  # path containing A
        ("git status", False),
        ("CSA_ALLOW_GIT_STATE_OPS=1 git reset --hard", True),  # inline bypass
        # ---- state verbs ----
        ("git checkout main", True),
        ("git switch -c feat", True),
        ("git stash", True),
        ("git stash pop", True),
        ("git rebase -i HEAD~2", True),
        ("git worktree add ../wt", True),
        ("git reset --soft HEAD~1", True),
        # ---- branch: delete blocked, listing allowed ----
        ("git branch -d feat", True),
        ("git branch -D feat", True),
        ("git branch", False),
        ("git branch --list", False),
        ("git branch -a", False),
        # ---- add: bulk blocked, path-scoped allowed ----
        ("git add .", True),
        ("git add -u", True),
        ("git add --update", True),
        ("git add :/", True),
        ("git add -Au", True),  # combined short
        ("git add modules/x.py y.py", False),
        ("git add -p", False),  # patch mode
        ("git add ./path/Apple.py", False),  # A in name
        # ---- commit: -a family blocked, path/-m allowed ----
        ('git commit -a -m "x"', True),
        ('git commit -am "x"', True),
        ("git commit --all", True),
        ('git commit -m "a message"', False),
        # ---- compound / pipe / eval-style ----
        ("echo hi | git checkout -", True),
        ("git status ; git reset --hard", True),
        ("false || git switch main", True),
        ("git status && git diff", False),
        ('git add file.py && git commit -m "x"', False),
        # ---- read-only verbs always allowed ----
        ("git diff", False),
        ("git log --oneline", False),
        ("git show HEAD", False),
        ("git fetch origin", False),
        ("git push origin HEAD", False),  # not a state verb
        # ---- global-arg stripping keeps state-verb detection ----
        ("git -c user.name=x reset --hard", True),
        ("git -C /repo checkout main", True),
        ("ENV=1 OTHER=2 git stash", True),
        ("/usr/bin/git reset --hard", True),  # abs path
        # ---- inline-bypass tripwire regardless of position ----
        ("echo CSA_ALLOW_GIT_STATE_OPS=1 && git add file.py", True),
        # ---- non-git commands always allowed ----
        ("ls -la", False),
        ("rm -rf build", False),
        ("gitfoo status", False),  # not git argv0
        ("mygit add -A", False),  # not git argv0
    ]

    @pytest.mark.parametrize("command,should_block", VECTORS)
    def test_decision_matches_bash_vector(self, command, should_block, clean_env):
        # The pure decision must agree with the proven bash guard's DRYRUN result.
        assert _blocked(command) is should_block, (
            f"{command!r}: expected block={should_block}, got {bbo.decision(command)}"
        )


# ===========================================================================
# Reason strings — assert the specific REASON the guard records, not just the
# boolean, so a regression that blocks for the wrong cause is caught.
# ===========================================================================


class TestDecisionReasons:
    @pytest.mark.parametrize(
        "command,reason",
        [
            ("git checkout main", "state-verb:checkout"),
            ("git switch main", "state-verb:switch"),
            ("git stash", "state-verb:stash"),
            # 2026-09-05: every MUTATING stash form stays blocked -- only
            # list/show (read-only) are carved out, per test_allow_reason_
            # is_not_a_block above.
            ("git stash push", "state-verb:stash"),
            ("git stash pop", "state-verb:stash"),
            ("git stash apply", "state-verb:stash"),
            ("git stash drop", "state-verb:stash"),
            ("git stash clear", "state-verb:stash"),
            ("git reset --hard", "state-verb:reset"),
            ("git rebase main", "state-verb:rebase"),
            ("git worktree add x", "state-verb:worktree"),
            ("git worktree remove x", "state-verb:worktree"),
            ("git worktree move x y", "state-verb:worktree"),
            ("git worktree", "state-verb:worktree"),
            ("git worktree lock x", "state-verb:worktree"),
            ("git worktree unlock x", "state-verb:worktree"),
            # bypass check: a compound command's SECOND segment being a
            # mutating worktree verb still blocks the whole line, same as
            # any other state verb (decision()'s per-segment scan).
            ("git worktree list && git worktree add x", "state-verb:worktree"),
            ("git branch -D feat", "branch-delete"),
            ("git add -A", "bulk-add"),
            ('git commit -a -m "x"', "commit-all"),
            ("CSA_ALLOW_GIT_STATE_OPS=1 git status", "inline-escape-var-forbidden"),
            # 2026-08-28 additions (agentic-systems-architect findings F1/F5):
            ("git restore modules/x.py", "state-verb:restore"),
            ("git restore --staged --worktree .", "state-verb:restore"),
            ("git clean -fdx", "state-verb:clean"),
            ("git clean -fd modules/", "state-verb:clean"),
        ],
    )
    def test_block_reason(self, command, reason, clean_env):
        block, got = bbo.decision(command)
        assert block is True
        assert got == reason

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git branch",
            "git add ./x.py",
            'git commit -m "x"',
            "ls",
            # 2026-08-28 addition (agentic-systems-architect finding F5):
            # read-only worktree enumeration/cleanup never mutates which
            # worktree an agent is IN, so it's allowed even though `worktree
            # add`/`remove`/etc. stay blocked as state verbs. `repair` is the
            # standard recovery for a `prune`-orphaned worktree (round-2
            # review finding 6) so it's allowed alongside them.
            "git worktree list",
            "git worktree prune",
            "git worktree repair",
            # trailing-flag forms and the prefix form all still resolve to
            # the same allowed subcommand (round-2 review finding 11).
            "git worktree list --porcelain",
            "git worktree prune -n",
            "git worktree prune --expire=now",
            "git -C /repo worktree list",
            # round-2 review finding 3: index-only restore ("unstage a
            # file") is gate 3's own printed recovery instruction and must
            # stay usable — it rewrites only the index, never the working
            # tree, so it can't destroy a peer session's uncommitted edits.
            "git restore --staged modules/x.py",
            "git restore -S modules/x.py",
            # 2026-09-05 addition (workflow audit into gate-denial friction):
            # `stash list`/`show` never touch the working tree -- mirroring
            # the worktree/restore carve-outs above. Measured: 60% of a
            # week's state-verb:stash denials were `stash list`, mostly
            # agents diagnosing pre-commit's own internal stash/restore race
            # (this file's top-of-file comment), a workflow this block was
            # itself obstructing.
            "git stash list",
            "git stash show",
            "git -C /repo stash list",
        ],
    )
    def test_allow_reason_is_not_a_block(self, command, clean_env):
        block, reason = bbo.decision(command)
        assert block is False
        assert reason in ("no-git-state-verb", "empty-command")

    def test_empty_command_allowed(self, clean_env):
        assert bbo.decision("") == (False, "empty-command")
        assert bbo.decision("   ") == (False, "empty-command")
        assert bbo.decision("\t\n ") == (False, "empty-command")


# ===========================================================================
# #4670 item 3b — word-boundary fix for the untokenizable-with-git
# sentinel. The fix touches ONLY _lib.git_segments' sentinel path (an
# untokenizable segment's own ambiguity check); every ALREADY-tokenizable
# vector below must decide byte-for-byte identically before and after it —
# this is the mandatory regression set the plan names explicitly.
# ===========================================================================


class TestItem3bWordBoundaryRegressionSet:
    @pytest.mark.parametrize(
        "command,should_block,reason",
        [
            ("git worktree add ../wt", True, "state-verb:worktree"),
            ("git -C /repo checkout main", True, "state-verb:checkout"),
            ("foo $(git stash)", True, "state-verb:stash"),
            ("git restore --worktree modules/x.py", True, "state-verb:restore"),
            ("git restore --staged modules/x.py", False, "no-git-state-verb"),
            ("git add -Au", True, "bulk-add"),
            ("git commit -a -m x", True, "commit-all"),
        ],
    )
    def test_regression_set_unchanged(self, command, should_block, reason, clean_env):
        block, got_reason = bbo.decision(command)
        assert block is should_block
        assert got_reason == reason

    def test_rm_rf_dot_git_stays_out_of_scope(self, clean_env):
        # argv0 != "git" -> this gate never covers it, before or after the
        # word-boundary fix. Not a claim that it's safe -- only that this
        # gate's scope is unchanged.
        assert bbo.decision("rm -rf .git") == (False, "no-git-state-verb")

    def test_escape_var_tripwire_stays_raw_substring_not_word_boundary(self, clean_env):
        # The CSA_ALLOW_GIT_STATE_OPS inline-bypass tripwire (decision()'s
        # OWN check, independent of _lib.git_segments) must NOT be
        # "harmonized" onto the word-boundary predicate -- it stays a raw
        # substring test on the whole command string. A real bypass would
        # exist if smuggling the var as part of a longer token silently
        # stopped tripping the block.
        assert bbo.decision("X=CSA_ALLOW_GIT_STATE_OPSFOO git status") == (
            True,
            "inline-escape-var-forbidden",
        )

    # --- known-open bypasses under the word-boundary net, unchanged by this
    # fix (neither newly created nor newly closed) -----------------------
    #
    # These four are documented pre-existing gaps in gate 1's scope, not
    # part of this fix's remit -- closing any of them in a FUTURE gate-1
    # hardening pass is an IMPROVEMENT, not a regression. If one of these
    # tests goes RED because a future change closes the bypass it asserts,
    # UPDATE the assertion to match the improved (blocking) behavior; never
    # revert the hardening just to make the test pass again.

    def test_env_indirection_bypass_stays_open(self, clean_env):
        assert bbo.decision("G=git; $G reset --hard") == (False, "no-git-state-verb")

    def test_alias_bypass_stays_open(self, clean_env):
        assert bbo.decision("alias g=git && g reset --hard") == (
            False,
            "no-git-state-verb",
        )

    def test_eval_bypass_stays_open(self, clean_env):
        # argv0 becomes "eval", not "git" -> out of scope, same as before.
        assert bbo.decision('eval "git reset --hard"') == (False, "no-git-state-verb")

    def test_python_subprocess_bypass_stays_open(self, clean_env):
        assert bbo.decision(
            "python3 -c \"import subprocess; subprocess.run(['git','reset','--hard'])\""
        ) == (False, "no-git-state-verb")

    def test_quote_fragmentation_is_actually_already_caught_not_a_bypass(self, clean_env):
        # CORRECTION: the plan text lists `g"i"t reset --hard` as a 5th
        # known-open "quote-fragmentation" bypass alongside the four above.
        # Empirically this is FALSE and was never a bypass under either the
        # old or new sentinel logic: shlex.split (used for every TOKENIZABLE
        # segment, unrelated to the untokenizable sentinel this item fixes)
        # correctly reassembles the split quotes into the single token
        # "git" before decision() ever inspects argv0, so this command is
        # (and always was) blocked as state-verb:reset. Asserting the TRUE,
        # verified-live behavior here rather than the plan's unverified
        # claim (see the falsifiability discipline this task was run
        # under) -- flagged explicitly in the implementer's report.
        assert bbo.decision('g"i"t reset --hard') == (True, "state-verb:reset")


# ===========================================================================
# Expanded decision-core edge cases beyond the bash vectors.
# ===========================================================================


class TestDecisionExpanded:
    def test_combined_short_reset_via_switch_all_state_verbs(self, clean_env):
        # Every state verb, each under a global-arg prefix, still blocks.
        # Iterates the real bbo.STATE_VERBS set (not a hardcoded tuple, per
        # round-2 review finding 12) so a future addition gets this coverage
        # automatically instead of silently escaping it. `git <verb> x` with
        # no other flags falls through every carve-out (worktree's list/
        # prune/repair, restore's --staged) for every verb currently in the
        # set, so a bare positional arg is a valid probe for all of them.
        for verb in sorted(bbo.STATE_VERBS):
            assert _blocked(f"git -c k=v {verb} x") is True
            assert _reason(f"git {verb} x") == f"state-verb:{verb}"

    def test_add_combined_short_uA_order_independent(self, clean_env):
        assert _blocked("git add -uA") is True
        assert _blocked("git add -Ap") is True  # A bundled with p
        assert _reason("git add -uA") == "bulk-add"

    def test_add_short_p_only_is_allowed(self, clean_env):
        # -p alone (no A/u) is interactive patch staging -> allowed.
        assert _blocked("git add -p") is False

    def test_commit_combined_short_with_a_blocks(self, clean_env):
        assert _blocked('git commit -av -m "x"') is True  # a bundled with v
        assert _blocked('git commit -vam "x"') is True

    def test_commit_short_without_a_allowed(self, clean_env):
        # -v (verbose) / -m without -a is a safe scoped commit.
        assert _blocked('git commit -v -m "x"') is False

    def test_branch_move_and_copy_not_blocked(self, clean_env):
        # Only delete flags block; -m (move) / -c (copy) branch ops are allowed by
        # the proven guard (it only special-cases -d/-D/--delete).
        assert _blocked("git branch -m old new") is False
        assert _blocked("git branch --list 'feat/*'") is False

    def test_subshell_hides_state_verb_still_blocks(self, clean_env):
        # A state verb inside $( ) / <( ) / a bare subshell is its own segment.
        assert _blocked("echo $(git reset --hard)") is True
        assert _blocked("diff <(git checkout x)") is True
        assert _blocked("(git stash)") is True

    def test_backtick_substitution_blocks(self, clean_env):
        assert _blocked("x=`git reset --hard`") is True

    def test_untokenizable_segment_with_git_fails_closed(self, clean_env):
        # An unbalanced quote makes the segment untokenizable; because it mentions
        # git, _lib surfaces the sentinel and the guard blocks (fail closed).
        block, reason = bbo.decision("git reset 'unterminated")
        assert block is True
        assert reason == "untokenizable-segment-with-git"

    def test_untokenizable_segment_without_git_allowed(self, clean_env):
        # Unbalanced quote but NO git token -> nothing to guard.
        assert _blocked("echo 'unterminated") is False

    def test_abs_and_env_prefixed_git(self, clean_env):
        assert _blocked("/usr/local/bin/git reset --hard") is True
        assert _blocked("FOO=1 BAR=2 /usr/bin/git checkout x") is True

    def test_git_with_no_subcommand_allowed(self, clean_env):
        # bare `git` (help banner) has no subcommand to inspect.
        assert _blocked("git") is False
        assert _blocked("git -C /repo") is False  # only a global, no sub

    def test_non_git_lookalikes_allowed(self, clean_env):
        for cmd in ("digit 3", "legitimate --all", "./gitk", "git-foo reset"):
            assert _blocked(cmd) is False

    def test_decision_swallows_internal_error(self, monkeypatch, clean_env):
        # If git_segments blows up, decision fails OPEN (block=False).
        def boom(_c):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(bbo._lib, "git_segments", boom)
        assert bbo.decision("git reset --hard") == (False, "decision-error")

    def test_decision_none_command(self, clean_env):
        assert bbo.decision(None) == (False, "empty-command")


# ===========================================================================
# main() — LOG-ONLY default. A would-block is logged and ALLOWED (no deny),
# and main always returns 0.
# ===========================================================================


class TestMainLogOnly:
    def test_state_verb_log_only_allows_silently(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(monkeypatch, make_payload(command="git reset --hard"))
        assert rc == 0
        assert out == ""  # log-only: emits nothing
        recs = _read_log(sandbox)
        assert len(recs) == 1
        assert recs[0]["decision"] == "would-block"
        assert recs[0]["reason"] == "state-verb:reset"
        assert recs[0]["hook"] == bbo.HOOK_NAME
        assert recs[0]["command"] == "git reset --hard"

    def test_bulk_add_log_only(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(monkeypatch, make_payload(command="git add -A"))
        assert rc == 0 and out == ""
        assert _read_log(sandbox)[0]["reason"] == "bulk-add"

    def test_safe_command_allows_and_does_not_log(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(monkeypatch, make_payload(command="git status"))
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []  # allow -> nothing written

    def test_non_bash_tool_allowed_no_log(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(monkeypatch, make_payload(tool_name="Read", command="git reset --hard"))
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_empty_command_allowed(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(monkeypatch, make_payload(command="   "))
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []


# ===========================================================================
# main() — ENFORCING. A would-block emits the canonical PreToolUse deny.
# ===========================================================================


class TestMainEnforcing:
    def test_enforce_env_emits_deny_for_state_verb(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git reset --hard"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert _is_deny(out)
        obj = json.loads(out)
        assert "state-verb:reset" in obj["systemMessage"]
        # still logged.
        assert _read_log(sandbox)[0]["decision"] == "would-block"

    def test_enforce_env_emits_deny_for_bulk_add(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git add -A"),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)

    def test_enforce_does_not_deny_read_only_verb(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git status"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert out == ""  # allow -> no deny even when enforcing

    def test_global_enforce_marker_emits_deny(self, sandbox, monkeypatch, make_payload):
        # ~/.claude/.enforce marker turns enforcement ON with no env var.
        sandbox.enforce_file.write_text("")
        rc, out = _run_main(monkeypatch, make_payload(command="git reset --hard"))
        assert _is_deny(out)

    def test_project_marker_via_cwd_emits_deny(
        self, sandbox, monkeypatch, make_payload, git_repo, enforce_marker
    ):
        enforce_marker(git_repo)
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git checkout main", cwd=str(git_repo)),
        )
        assert _is_deny(out)

    def test_project_repo_without_marker_stays_log_only(
        self, sandbox, monkeypatch, make_payload, git_repo
    ):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git checkout main", cwd=str(git_repo)),
        )
        assert out == ""  # repo present but not opted-in -> log-only


# ===========================================================================
# main() — MASTER OFF switch. CSA_DISABLE_HOOKS=1 neutralizes everything.
# ===========================================================================


class TestMainDisabled:
    def test_disable_neutralizes_state_verb_even_under_enforce(
        self, sandbox, monkeypatch, make_payload
    ):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git reset --hard"),
            env={"CSA_ENFORCE": "1", "CSA_DISABLE_HOOKS": "1"},
        )
        assert rc == 0
        assert out == ""
        assert _read_log(sandbox) == []  # disabled: no evaluation, no log

    def test_disable_overrides_global_marker(self, sandbox, monkeypatch, make_payload):
        sandbox.enforce_file.write_text("")
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git reset --hard"),
            env={"CSA_DISABLE_HOOKS": "1"},
        )
        assert out == ""

    def test_disable_with_inline_bypass_still_noop(self, sandbox, monkeypatch, make_payload):
        # master-off wins even over the tripwire.
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="CSA_ALLOW_GIT_STATE_OPS=1 git reset"),
            env={"CSA_DISABLE_HOOKS": "1"},
        )
        assert out == "" and _read_log(sandbox) == []


# ===========================================================================
# main() — ESCAPE HATCH via the hook's OWN env (never inline).
# ===========================================================================


class TestMainEscapeHatch:
    def test_own_env_escape_allows_state_verb(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1", "CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert out == ""  # escaped -> no deny even under enforce
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "escape-allowed"
        assert rec["reason"] == "state-verb:reset"

    def test_own_env_escape_does_not_bypass_inline_tripwire(
        self, sandbox, monkeypatch, make_payload
    ):
        # The command STRING contains the var -> tripwire block, which the OWN-env
        # hatch must NOT be able to escape. Under enforce, this still denies.
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="CSA_ALLOW_GIT_STATE_OPS=1 git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1", "CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "inline-escape-var-forbidden" in obj["systemMessage"]

    def test_escape_var_set_to_non_1_does_not_escape(self, sandbox, monkeypatch, make_payload):
        # Only the exact value "1" enables the hatch.
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "0", "CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)


# ===========================================================================
# main() — inline tripwire (no escape env at all).
# ===========================================================================


class TestMainInlineTripwire:
    def test_inline_var_blocks_even_with_safe_git(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="echo CSA_ALLOW_GIT_STATE_OPS=1 && git add file.py"),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)

    def test_inline_var_blocks_even_with_no_git(self, sandbox, monkeypatch, make_payload):
        # The var alone is forbidden even without any git command.
        block, reason = bbo.decision("export CSA_ALLOW_GIT_STATE_OPS=1")
        assert (block, reason) == (True, "inline-escape-var-forbidden")

    def test_inline_var_log_only_default(self, sandbox, monkeypatch, make_payload):
        rc, out = _run_main(
            monkeypatch,
            make_payload(command="CSA_ALLOW_GIT_STATE_OPS=1 git reset"),
        )
        assert out == ""  # log-only default
        assert _read_log(sandbox)[0]["reason"] == "inline-escape-var-forbidden"


# ===========================================================================
# main() — PARSE ERROR handling: fail CLOSED with a git token, else allow.
# ===========================================================================


class TestMainParseError:
    def test_malformed_json_with_git_fails_closed_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            "not json at all git reset --hard",
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        assert _read_log(sandbox)[0]["reason"] == "parse-error-with-git-token"

    def test_malformed_json_with_git_log_only_default(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "not json at all git reset --hard")
        assert out == ""  # log-only
        assert _read_log(sandbox)[0]["reason"] == "parse-error-with-git-token"

    def test_malformed_json_no_git_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "total garbage not json here")
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_empty_stdin_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "")
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_non_dict_json_with_git_token_fails_closed(self, sandbox, monkeypatch):
        # Valid JSON but a list, not an object -> _parse_event returns {}; the raw
        # string mentions git -> fail closed.
        rc, out = _run_main(
            monkeypatch,
            '["git", "reset", "--hard"]',
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)

    def test_stdin_read_raises_treated_as_no_git(self, sandbox, monkeypatch):
        class Boom:
            def read(self):
                raise IOError("no stdin")

        monkeypatch.setattr("sys.stdin", Boom())
        buf = io.StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        rc = bbo.main()
        assert rc == 0 and buf.getvalue() == ""

    @pytest.mark.parametrize(
        "raw,expect",
        [
            ("git reset", True),
            # 'git-foo' -> 'git' bounded by a non-alpha ('-') -> whole-word match,
            # exactly as the bash grep (^|[^A-Za-z])git([^A-Za-z]|$) fires. This is
            # the fail-closed side: on a parse error we err toward blocking.
            ("run git-foo", True),
            ("digit here", False),  # 'git' inside 'digit' -> not a whole word
            ("legit reset", False),  # 'git' inside 'legit'
            ("the git tool", True),
            ("git", True),
            ("agitprop", False),
            ("", False),
            # #4670 round-4 blocker fix: ASCII-only word boundary,
            # exercised through the real bbo._raw_mentions_git delegation
            # (not monkeypatched) -- mirrors _lib's own regression cases so
            # a future re-implementation inside block_branch_ops.py that
            # accidentally reverts to Unicode-aware isalpha() is caught
            # here too, not only in _lib's test module.
            ("égit", True),
            ("gitö", True),
        ],
    )
    def test_raw_mentions_git_word_boundary(self, raw, expect):
        assert bbo._raw_mentions_git(raw) is expect

    def test_raw_mentions_git_is_a_re_export_not_a_reimplementation(self, monkeypatch):
        # #4670 item 3b: block_branch_ops._raw_mentions_git must call
        # THROUGH to _lib._raw_mentions_git (the single shared
        # implementation), never carry its own duplicate copy of the
        # word-boundary logic. Proven by monkeypatching _lib's version to a
        # detectable sentinel and confirming bbo's own top-level name
        # reflects it.
        calls = []

        def fake(raw):
            calls.append(raw)
            return "SENTINEL"

        monkeypatch.setattr(bbo._lib, "_raw_mentions_git", fake)
        assert bbo._raw_mentions_git("anything") == "SENTINEL"
        assert calls == ["anything"]


# ===========================================================================
# main() — _finish direct coverage of the escape/enforce branch matrix.
# ===========================================================================


class TestFinishBranches:
    def test_finish_allow_is_noop(self, sandbox, clean_env):
        assert bbo._finish(False, "no-git-state-verb", "ls", cwd_hint=None) == 0
        assert _read_log(sandbox) == []

    def test_finish_block_log_only(self, sandbox, clean_env):
        rc = bbo._finish(True, "state-verb:reset", "git reset", cwd_hint=None)
        assert rc == 0
        assert _read_log(sandbox)[0]["decision"] == "would-block"

    def test_finish_block_enforce_emits(self, sandbox, clean_env, capsys, monkeypatch):
        monkeypatch.setenv("CSA_ENFORCE", "1")
        bbo._finish(True, "state-verb:reset", "git reset", cwd_hint=None)
        assert _is_deny(capsys.readouterr().out)

    def test_finish_escape_hatch_logs_escape_allowed(self, sandbox, clean_env, monkeypatch):
        monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc = bbo._finish(True, "state-verb:reset", "git reset", cwd_hint=None)
        assert rc == 0
        assert _read_log(sandbox)[0]["decision"] == "escape-allowed"

    def test_finish_tripwire_not_escapable(self, sandbox, clean_env, capsys, monkeypatch):
        monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
        monkeypatch.setenv("CSA_ENFORCE", "1")
        bbo._finish(True, "inline-escape-var-forbidden", "x", cwd_hint=None)
        # tripwire outranks the hatch -> a deny is emitted (would-block logged).
        assert _is_deny(capsys.readouterr().out)


# ===========================================================================
# Small unit tests for the flag helpers (pin the combined-short logic).
# ===========================================================================


class TestFlagHelpers:
    @pytest.mark.parametrize(
        "arg,letters,expect",
        [
            ("-Au", "Au", True),
            ("-uA", "Au", True),
            ("-Ap", "Au", True),  # A present, p ignored
            ("-p", "Au", False),
            ("--all", "Au", False),  # long flag, not combined-short
            ("-", "Au", False),  # lone dash
            ("file", "Au", False),  # not a flag
            ("-am", "a", True),
            ("-vm", "a", False),
        ],
    )
    def test_has_bad_combined_short(self, arg, letters, expect):
        assert bbo._has_bad_combined_short(arg, letters) is expect

    def test_add_is_bulk_matrix(self):
        assert bbo._add_is_bulk(["-A"]) is True
        assert bbo._add_is_bulk([".", "x"]) is True
        assert bbo._add_is_bulk(["./a.py"]) is False
        assert bbo._add_is_bulk([]) is False

    def test_commit_is_all_matrix(self):
        assert bbo._commit_is_all(["-a"]) is True
        assert bbo._commit_is_all(["--all"]) is True
        assert bbo._commit_is_all(["-m", "x"]) is False

    def test_branch_is_delete_matrix(self):
        assert bbo._branch_is_delete(["-d", "x"]) is True
        assert bbo._branch_is_delete(["--delete", "x"]) is True
        assert bbo._branch_is_delete(["--list"]) is False

    def test_evaluate_short_argv_no_subcommand(self):
        assert bbo._evaluate_git_argv(["git"]) == (False, "")

    def test_evaluate_sentinel_fails_closed(self):
        assert bbo._evaluate_git_argv(["git", "\x00untokenizable"]) == (
            True,
            "untokenizable-segment-with-git",
        )


# ===========================================================================
# Import-time sys.path shim — exercise the branch that inserts the hooks dir
# when it is NOT already importable (conftest normally pre-adds it, so a plain
# import never runs that line).
# ===========================================================================


def test_import_inserts_hooks_dir_when_missing(monkeypatch):
    # Exec the module SOURCE in a fresh namespace with the hooks dir removed from
    # sys.path, so the `if _HOOKS_DIR not in sys.path: sys.path.insert(...)` guard
    # runs. We restore sys.path afterward (via monkeypatch) and assert the module
    # both re-inserted its own dir and imported _lib successfully.
    import os as _os
    import sys as _sys

    hooks_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    src = _os.path.join(hooks_dir, "block_branch_ops.py")
    with open(src, encoding="utf-8") as fh:
        code = fh.read()

    monkeypatch.setattr(_sys, "path", [p for p in _sys.path if p != hooks_dir])
    ns = {"__file__": src, "__name__": "block_branch_ops_reimport"}
    exec(compile(code, src, "exec"), ns)  # noqa: S102 - deliberate re-exec of our own module

    assert hooks_dir in _sys.path  # the guard inserted it back
    assert ns["HOOK_NAME"] == "block_branch_ops"
    assert ns["decision"]("git reset --hard")[0] is True
