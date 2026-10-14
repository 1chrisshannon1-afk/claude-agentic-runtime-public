#!/usr/bin/env python3
"""block_branch_ops — PreToolUse:Bash hook. Blocks agent git state-mutations.

Ported faithfully from ~/.claude/scripts/git_guard.sh (its test harness
~/.claude/scripts/tests/test_git_guard.sh is the behavioral spec). Blocks git
state-mutating subcommands that are reserved for the human operator:

  * checkout / switch / stash / reset / rebase / worktree / restore / clean
    (state verbs — `restore`'s working-tree form is the modern spelling of
    the blocked `checkout --` [index-only `restore --staged`/`-S` stays
    allowed — see below]; `clean` deletes untracked files outright. Added
    2026-08-28 per agentic-systems-architect finding F1: both were
    unblocked and could destroy a peer session's uncommitted work in the
    shared tree. NOTE: this closes ONE path in that class, not the whole
    class — `git rm -f`, `checkout-index -f`, `sparse-checkout set`, and
    `apply -R` remain unblocked and can also destroy tracked working-tree
    content; the confirmed root cause of the actual same-night incident
    this was added for was pre-commit's own whole-tree stash mechanism
    during a DIFFERENT session's commit, not an agent typing one of these
    verbs directly — see CLAUDE.md §2 for the full account.)
  * branch -d / -D / --delete                              (branch deletion)
  * add  -A / --all / -u / --update / . / :/  (incl. combined -Au)  (bulk stage)
  * commit -a / -am / --all                                (bulk commit)

ALLOWS read-only verbs (status/diff/log/show/fetch/push/pull...), branch
LISTING (bare `git branch`, `--list`, `-a`), path-scoped `git add ./x.py`, and
`git commit -m msg`.

CONTRACT (see the spawning task + git_guard.sh):
  * PURE decision function `decision(command) -> (block: bool, reason: str)`.
  * Thin `main()`: read event, decide, emit/log, ALWAYS exit 0. A deny is
    expressed via the canonical PreToolUse JSON object, NEVER via exit code.
  * LOG-ONLY by default: a would-block is only logged (and allowed) unless
    enforcing() is True, at which point the canonical deny is emitted.
  * CSA_DISABLE_HOOKS=1 master-OFF: no-op allow before anything else.
  * Escape hatch: CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env lets a
    would-block through. But ANY command STRING that itself contains the literal
    'CSA_ALLOW_GIT_STATE_OPS' is DENIED (agents must never set it inline).
  * Parse-ambiguity fails CLOSED: a command that mentions a git token but cannot
    be tokenized is treated as a block candidate.
  * Only the Bash tool is gated; every other tool is allowed.

The module never raises out to the caller: a crashing hook must never break the
agent. Every unexpected error degrades to ALLOW.
"""

from __future__ import annotations

import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirroring other hooks)

HOOK_NAME = "block_branch_ops"

# The inline-bypass tripwire: an agent must never smuggle this var into the
# command string. Its literal presence anywhere in the command is a hard block.
ESCAPE_VAR = "CSA_ALLOW_GIT_STATE_OPS"

# Subcommands that mutate working-tree / branch state — always reserved.
STATE_VERBS = frozenset(
    {"checkout", "switch", "stash", "reset", "rebase", "worktree", "restore", "clean"}
)


# ---------------------------------------------------------------------------
# PURE decision core.
#
# decision(command) -> (block, reason)
#
# No env reads, no I/O, no side effects — trivially unit-testable. The env-based
# policy (log-only vs enforce, master-off, escape hatch) lives entirely in
# main(). This mirrors git_guard.sh's tokenized evaluation exactly, delegating
# the segmentation + prefix/global stripping to the shared _lib.git_segments().
# ---------------------------------------------------------------------------


def _has_bad_combined_short(arg: str, letters: str) -> bool:
    """True if `arg` is a combined SHORT flag (-xy, not --long) whose letter set
    intersects `letters`. e.g. -Au for {'A','u'}, -am for {'a'}."""
    if not arg.startswith("-") or arg.startswith("--") or len(arg) <= 1:
        return False
    return bool(set(arg[1:]) & set(letters))


def _add_is_bulk(subargs: list[str]) -> bool:
    """git add: bulk stagers (-A --all -u --update . :/ and combined -Au) block;
    path-scoped adds ('./modules/x.py', 'path/A', '-p') are allowed."""
    for a in subargs:
        if a in ("-A", "--all", "-u", "--update", ".", ":/"):
            return True
        if _has_bad_combined_short(a, "Au"):
            return True
    return False


def _commit_is_all(subargs: list[str]) -> bool:
    """git commit: the -a family (-a -am --all) auto-stages tracked files -> block;
    -m / path-scoped commits are allowed."""
    for a in subargs:
        if a in ("-a", "-am", "--all"):
            return True
        if _has_bad_combined_short(a, "a"):
            return True
    return False


def _branch_is_delete(subargs: list[str]) -> bool:
    """git branch: deletion (-d -D --delete) blocks; listing (bare, --list, -a) ok."""
    return any(a in ("-d", "-D", "--delete") for a in subargs)


def _evaluate_git_argv(git_argv: list[str]) -> tuple[bool, str]:
    """Given a single ['git', <sub>, <args...>] argv, return (block, reason).

    git_argv is already env-stripped and global-option-stripped by
    _lib.git_segments(). The sentinel ['git', '\\x00untokenizable'] surfaces an
    untokenizable-yet-git segment -> fail closed (ambiguous)."""
    if len(git_argv) < 2:
        return (False, "")
    sub = git_argv[1]
    subargs = git_argv[2:]

    if sub == "\x00untokenizable":
        return (True, "untokenizable-segment-with-git")
    if sub == "worktree":
        # Read-only enumeration/cleanup is allowed (2026-08-28, agentic-
        # systems-architect finding F5 — documented known leak, now closed):
        # `list` never mutates anything. `prune` only drops already-missing
        # worktrees' admin metadata, but that can itself orphan a worktree
        # that still holds uncommitted files (e.g. after the repo directory
        # was renamed/moved) — so `repair` (the standard recovery for exactly
        # that state) is allowed alongside it, per round-2 review finding 6,
        # so an agent can't corner itself into a state only the operator can
        # exit. `add`/`remove`/`move` (and a bare `git worktree`, which
        # prints usage but is closest in spirit to a mutating call) stay
        # blocked.
        if subargs[:1] in (["list"], ["prune"], ["repair"]):
            return (False, "")
        return (True, "state-verb:" + sub)
    if sub == "restore":
        # Index-only restore ("unstage a file") is allowed — it rewrites only
        # the index, never the working tree, so it cannot destroy a peer
        # session's uncommitted edits (the hazard this verb's block exists
        # for). This is also gate 3's own printed recovery instruction
        # (check_staged_scope.py: "git restore --staged <unrelated>, then
        # retry") — round-2 review finding 3: blocking `restore` outright,
        # with `reset <path>` already blocked too, left NO way to unstage a
        # file. Any `--worktree`/`-W` flag (which DOES touch the working
        # tree, and makes this the exact modern-spelling-of-`checkout --`
        # case the block exists for) still blocks.
        if any(a in ("--worktree", "-W") for a in subargs):
            return (True, "state-verb:restore")
        if any(a in ("--staged", "-S") for a in subargs):
            return (False, "")
        return (True, "state-verb:restore")
    if sub == "stash":
        # Read-only enumeration is allowed (added after a workflow audit,
        # 2026-09-05): `list`/`show` never touch the working tree, mirroring
        # the worktree/restore carve-outs above. Measured 7-day denial log:
        # 103 of 171 state-verb:stash denials (60%) were `stash list` calls,
        # overwhelmingly agents diagnosing pre-commit's OWN internal stash/
        # restore race (see this file's top-of-file comment) via
        # `git stash list` / checking for an orphaned
        # `~/.cache/pre-commit/patch*` recovery file -- the exact diagnostic
        # workflow this block was itself obstructing. Every mutating form
        # (`push`/`pop`/`apply`/`drop`/`clear`/a bare `git stash`, which
        # defaults to `push`) stays blocked.
        if subargs[:1] in (["list"], ["show"]):
            return (False, "")
        return (True, "state-verb:stash")
    if sub in STATE_VERBS:
        return (True, "state-verb:" + sub)
    if sub == "branch":
        if _branch_is_delete(subargs):
            return (True, "branch-delete")
        return (False, "")
    if sub == "add":
        if _add_is_bulk(subargs):
            return (True, "bulk-add")
        return (False, "")
    if sub == "commit":
        if _commit_is_all(subargs):
            return (True, "commit-all")
        return (False, "")
    # Any other subcommand (status/diff/log/show/fetch/push/pull/...) -> allow.
    return (False, "")


def decision(command: str) -> tuple[bool, str]:
    """Pure policy: should this Bash command be blocked? -> (block, reason).

    Reproduces git_guard.sh's tokenized evaluation:
      1. Empty/whitespace command                         -> allow.
      2. The literal ESCAPE_VAR anywhere in the string     -> BLOCK (tripwire).
      3. Otherwise inspect every git segment; the FIRST segment that carries a
         state-verb / blocked-flag subcommand blocks the whole line (covers
         compound `a && git reset`, pipes, subshells, eval-style chains).
      4. No blocking git segment                           -> allow.

    Does NOT consult env, does NOT decide log-only-vs-enforce, does NOT honor the
    escape hatch — those are main()'s job. Never raises: any error degrades to
    (False, ...) so the guard fails OPEN on its own bugs.
    """
    try:
        if not command or not command.strip():
            return (False, "empty-command")

        # Inline-bypass tripwire: the escape var must never appear in the command
        # string. Checked before any tokenization so even a malformed command
        # that carries it is denied.
        if ESCAPE_VAR in command:
            return (True, "inline-escape-var-forbidden")

        segments = _lib.git_segments(command)
        for git_argv in segments:
            block, reason = _evaluate_git_argv(git_argv)
            if block:
                return (True, reason)
        return (False, "no-git-state-verb")
    except Exception:
        # A bug in the decision core must not crash the hook; fail OPEN.
        return (False, "decision-error")


# ---------------------------------------------------------------------------
# Parse-error fail-closed helper (git_guard.sh parse-error handling).
# ---------------------------------------------------------------------------


def _raw_mentions_git(raw: str) -> bool:
    """Whole-word 'git' detection in a raw payload string (no JSON parse).

    Thin re-export of ``_lib._raw_mentions_git`` (the shared implementation
    moved there 2026-08-30, #4670 item 3b, so this module,
    pretooluse_bash.py's own parse-error path, and _lib.git_segments'
    untokenizable-segment sentinel all share exactly one predicate instead
    of three independently-drifting copies — mirrors git_guard.sh's
    parse-error grep `(^|[^A-Za-z])git([^A-Za-z]|$)`: the bare token 'git'
    surrounded by non-alpha (or string edges)). Used only on this module's
    own fail-closed path when the JSON payload cannot be parsed; kept as a
    top-level name here (rather than inlining `_lib._raw_mentions_git`
    everywhere it's used) because pretooluse_bash.py and this module's own
    tests already call it as `bbo._raw_mentions_git`."""
    return _lib._raw_mentions_git(raw)


# ---------------------------------------------------------------------------
# Thin main() — reads the event, applies env policy, emits/logs, exits 0.
#
# DEAD IN PRODUCTION (documented 2026-08-30, #4670 item 3, after AA-0051
# was issued against THIS module's message string when the live remediation
# text agents actually see lives in pretooluse_bash.py's own
# `_branch_ops_block()` instead): settings.json registers exactly one
# PreToolUse:Bash hook — `bash_gate.sh` -> `pretooluse_bash.py` — which
# imports this module only for its PURE `decision()` (and, separately,
# `_raw_mentions_git`) and never calls `main()`/`_finish()` below. Neither
# function runs on any live agent turn; they exist only for this module's
# own direct-invocation unit tests (`hooks/tests/test_block_branch_ops.py`)
# and as a standalone CLI entry point were this script ever run by hand. NOT
# registered in `check_safety_core_parity.STANDALONE_GUARD_MODULES` — that
# registry is about FILE-level reachability (is this module ever imported by
# something settings.json wires), and this module's file IS reachable (see
# `test_block_branch_ops_is_genuinely_reachable_in_the_real_wired_closure`
# in `hooks/tests/test_check_safety_core_parity.py`); only its own unused
# `main()`/`_finish()` entry point is dead, which that checker has no way to
# express and does not need to. If you are editing a denial MESSAGE an agent
# actually sees, edit `pretooluse_bash.py`'s `_branch_ops_block()`, not this
# file.
# ---------------------------------------------------------------------------


def _finish(block: bool, reason: str, command: str, *, cwd_hint: str | None) -> int:
    """Terminal action for a computed decision. Returns the process exit code
    (ALWAYS 0 — deny is via JSON output, never a nonzero code).

      BLOCK: log the would-block; honor the OWN-env escape hatch (allow + log);
             if enforcing() emit the canonical deny; else stay silent (log-only).
      ALLOW: nothing to emit.
    """
    if not block:
        return 0

    # Escape hatch: only honored from the hook's OWN process env. Any command
    # STRING containing the var was already turned into a BLOCK by decision()
    # (reason 'inline-escape-var-forbidden'), so we must NOT let that specific
    # block be escaped — the tripwire outranks the hatch.
    if reason != "inline-escape-var-forbidden" and os.environ.get(ESCAPE_VAR, "") == "1":
        _lib.log(HOOK_NAME, "escape-allowed", reason=reason, command=command)
        return 0

    enforce = _lib.enforcing(cwd_hint)
    _lib.log(HOOK_NAME, "would-block", reason=reason, command=command, enforce=enforce)

    if enforce:
        _lib.emit_pretooluse_deny(
            "block_branch_ops: blocked git state-mutation ("
            + reason
            + "). This op is reserved for the operator. "
            "See ~/.claude/.enforcement/log.jsonl."
        )
    # Log-only default: allow silently (print nothing).
    return 0


def main() -> int:
    """Entry point. Reads stdin, decides, emits/logs, returns exit code 0."""
    # Master OFF switch — no-op allow before touching anything else.
    if _lib.disabled():
        return 0

    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    ev = _lib._parse_event(raw)

    if not ev:
        # Parse error: fail CLOSED only when the raw string mentions a git token.
        if _raw_mentions_git(raw):
            return _finish(
                True,
                "parse-error-with-git-token",
                raw[:200],
                cwd_hint=None,
            )
        return 0  # no git mention -> nothing to guard.

    # Only gate the Bash tool.
    if _lib.tool_name(ev) != "Bash":
        return 0

    command = _lib.bash_command(ev)
    cwd_hint = _lib.cwd(ev)

    block, reason = decision(command)
    return _finish(block, reason, command, cwd_hint=cwd_hint)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
