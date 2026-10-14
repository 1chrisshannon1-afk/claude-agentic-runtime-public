#!/usr/bin/env python3
"""block_unscoped_commit — PreToolUse:Bash hook.

Blocks BULK / unscoped git staging + committing while ALLOWING path-scoped work:

  BLOCKED   git add -A / --all / -u / --update / . / :/     (bulk stagers)
            git add -Au / -uA / ...                          (combined short flags
                                                              containing A or u)
            git commit -a / -am / --all                      (auto-stage-all commit)
            git commit -<flags-containing-a>                 (e.g. -am, -av a bundle)

  ALLOWED   git add ./modules/x.py   git add path/A   git add modules/x.py y.py
            git add -p                                        (patch mode)
            git commit -m "msg"       git add f.py && git commit -m "msg"
            every non-add/non-commit git subcommand, every non-git command.

Ported from ~/.claude/scripts/git_guard.sh — this module owns only the `add` and
`commit` slice of that guard (whole-token flag matching, NOT substring). The
git_guard test vectors for add/commit are the spec and are reproduced verbatim
in the test suite.

STRUCTURE (per the hook-system contract):
  * `decide(event)` is a PURE function: (event dict) -> Decision. No I/O, no env
    reads beyond what the shared `_lib` helpers already encapsulate for tokenizing.
    Its inputs (tool_name, command) come straight off the event dict.
  * `main()` is a thin shell: read the event, compute the decision, then LOG
    always on a would-block, and EMIT a real deny ONLY when enforcing(). It always
    exits 0 — a deny is expressed via the JSON deny object, never via exit code.

SWITCHES (resolved in main(), matching git_guard.sh):
  * CSA_DISABLE_HOOKS=1  master OFF — no-op allow (handled first).
  * enforcing()          LOG-ONLY unless ON (env CSA_ENFORCE=1, the global
                         ~/.claude/.enforce marker, or a per-project opt-in).
  * CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN env  lets a hit through, BUT any
                         command STRING containing that var name is DENIED (agents
                         must never smuggle it inline).
  * CSA_GUARD_DRYRUN=print  prints the decision word (ALLOW/BLOCK) and exits 0,
                         regardless of enforce/log-only — the test-harness hook.
"""

from __future__ import annotations

import os
import sys

# Make `import _lib` work no matter the pytest rootdir / cwd the hook fires in.
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

HOOK_NAME = "block_unscoped_commit"

# The escape var an agent must never smuggle into a command string.
_ESCAPE_VAR = "CSA_ALLOW_GIT_STATE_OPS"

# Bulk `git add` stagers, matched as WHOLE tokens (never substring). A path like
# `path/A` or `./digit.py` is NOT in this set, so it is ALLOWED.
_ADD_BULK_TOKENS = frozenset({"-A", "--all", "-u", "--update", ".", ":/"})

# `git commit` auto-stage-all forms, matched as whole tokens.
_COMMIT_ALL_TOKENS = frozenset({"-a", "-am", "--all"})


class Decision:
    """A pure decision result. `block` is the verdict; `reason` is the audit tag."""

    __slots__ = ("block", "reason")

    def __init__(self, block: bool, reason: str):
        self.block = block
        self.reason = reason

    # Equality + repr make assertions in the test suite terse and readable.
    def __eq__(self, other):
        return (
            isinstance(other, Decision)
            and self.block == other.block
            and self.reason == other.reason
        )

    def __repr__(self):  # pragma: no cover - debug aid only
        verb = "BLOCK" if self.block else "ALLOW"
        return f"Decision({verb}, {self.reason!r})"


def _short_flags(token: str):
    """Return the letter set of a bundled short-flag token, or None if not one.

    A bundled short flag is a single-dash token of length > 1 that is NOT a
    long (`--`) option: e.g. `-Au` -> {'A','u'}, `-am` -> {'a','m'}. `--all`
    and `-A` (which are matched exactly elsewhere) still pass through here, but
    the caller only consults this for the *combined* case.
    """
    if token.startswith("-") and not token.startswith("--") and len(token) > 1:
        return set(token[1:])
    return None


def _add_is_bulk(args) -> bool:
    """True iff a `git add` arg list contains a bulk stager (whole-token match).

    Blocks `-A --all -u --update . :/` as exact tokens, plus any combined short
    flag whose letters include `A` or `u` (e.g. `-Au`, `-uA`). Path arguments
    (`./x.py`, `path/A`, `modules/x.py`) never match — they are allowed.
    """
    for a in args:
        if a in _ADD_BULK_TOKENS:
            return True
        letters = _short_flags(a)
        if letters is not None and (letters & {"A", "u"}):
            return True
    return False


def _commit_is_all(args) -> bool:
    """True iff a `git commit` arg list auto-stages everything (`-a` family)."""
    for a in args:
        if a in _COMMIT_ALL_TOKENS:
            return True
        letters = _short_flags(a)
        if letters is not None and "a" in letters:
            return True
    return False


def decide(event: dict) -> Decision:
    """PURE decision: does this event's Bash command bulk-add or -a-commit?

    Precedence (ported from git_guard.sh, add/commit slice):
      1. Non-Bash tool                       -> ALLOW (not-bash-tool).
      2. Empty / whitespace-only command     -> ALLOW (empty-command).
      3. Command string carries the escape var literally -> BLOCK
         (inline-escape-var-forbidden) — agents must never smuggle it inline.
      4. Any git segment is untokenizable but mentions git -> BLOCK
         (untokenizable-segment-with-git) — fail closed on ambiguity.
      5. Any `git add` segment is bulk        -> BLOCK (bulk-add).
      6. Any `git commit` segment is -a-family -> BLOCK (commit-all).
      7. otherwise                            -> ALLOW (no-bulk-add-or-commit-all).

    Never raises: any unexpected error degrades to a conservative allow so a
    crashing guard cannot break the agent (the enforce-side fail-closed for
    parse ambiguity is handled explicitly in step 4 via the sentinel).
    """
    try:
        if _lib.tool_name(event) != "Bash":
            return Decision(False, "not-bash-tool")

        command = _lib.bash_command(event)
        if not command or not command.strip():
            return Decision(False, "empty-command")

        # Inline-bypass tripwire: the raw command must never mention the escape var.
        if _ESCAPE_VAR in command:
            return Decision(True, "inline-escape-var-forbidden")

        for git_argv in _lib.git_segments(command):
            # git_segments yields ["git", <sub>, <args...>] per git segment, or the
            # sentinel ["git", "\x00untokenizable"] for an ambiguous segment.
            if len(git_argv) >= 2 and git_argv[1] == "\x00untokenizable":
                return Decision(True, "untokenizable-segment-with-git")
            if len(git_argv) < 2:
                continue
            sub = git_argv[1]
            args = git_argv[2:]
            if sub == "add":
                if _add_is_bulk(args):
                    return Decision(True, "bulk-add")
            elif sub == "commit":
                if _commit_is_all(args):
                    return Decision(True, "commit-all")
            # every other subcommand is out of this module's scope -> allow.

        return Decision(False, "no-bulk-add-or-commit-all")
    except Exception:
        # Degrade open: a guard that crashes must not break the tool call.
        return Decision(False, "guard-error")


def _dryrun_mode() -> bool:
    """CSA_GUARD_DRYRUN=print — the test-harness hook that prints ALLOW/BLOCK."""
    return os.environ.get("CSA_GUARD_DRYRUN", "") == "print"


def _escape_hatch_active() -> bool:
    """CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env.

    Only meaningful once decide() has NOT already blocked on the inline tripwire:
    a command string containing the var name is denied before we get here.
    """
    return os.environ.get(_ESCAPE_VAR, "") == "1"


def main() -> int:
    """Thin driver: read event -> decide -> log/emit -> exit 0.

    A deny is expressed purely through the emitted JSON object; the exit code is
    ALWAYS 0 so Claude Code consumes the decision object rather than treating a
    non-zero exit as a hook crash.
    """
    # Master OFF switch: a global no-op. In dryrun still report ALLOW so the test
    # harness can observe the neutralization.
    if _lib.disabled():
        if _dryrun_mode():
            print("ALLOW")
        return 0

    event = _lib.read_event()
    decision = decide(event)
    command = _lib.bash_command(event)

    # The escape hatch converts a hit into an allow, EXCEPT when the hit is the
    # inline-tripwire itself (a command string that smuggled the var name). That
    # case must stay blocked no matter what the process env says.
    if (
        decision.block
        and decision.reason != "inline-escape-var-forbidden"
        and _escape_hatch_active()
    ):
        _lib.log(HOOK_NAME, "escape-allowed", reason=decision.reason, command=command)
        decision = Decision(False, "escape-hatch:" + decision.reason)

    if decision.block:
        # LOG the would-block on every hit, enforcing or not — the audit trail is
        # the whole point of log-only mode.
        enforce = _lib.enforcing(_lib.cwd(event))
        _lib.log(HOOK_NAME, "would-block", reason=decision.reason, command=command, enforce=enforce)
        if _dryrun_mode():
            print("BLOCK")
            return 0
        if enforce:
            _lib.emit_pretooluse_deny(
                f"{HOOK_NAME}: blocked bulk/unscoped git staging "
                f"({decision.reason}). Stage explicit paths (git add path/to/file) and "
                'commit with: git commit -m "..." -- <path> [<path>...]; -A/--all/-u/. '
                "and commit -a are reserved for the operator. "
                "See ~/.claude/.enforcement/log.jsonl."
            )
            return 0
        # log-only default: allow silently.
        return 0

    # ALLOW.
    if _dryrun_mode():
        print("ALLOW")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
