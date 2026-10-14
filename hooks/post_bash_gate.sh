#!/usr/bin/env bash
# post_bash_gate.sh — pure-bash fast-path for the PostToolUse:Bash hook.
#
# Mirrors bash_gate.sh's trick exactly, on the OUT side: the vast majority of
# Bash tool calls are not git commits and have nothing to release. This gate
# reads the hook payload from stdin ONCE and, unless it could possibly be a git
# commit, exits 0 WITHOUT touching python — a non-git command costs ~0.
#
# Only when the payload contains 'git' do we pay for the single python3 spawn
# that runs posttooluse_bash.py (today: release this call's file_claims claim,
# if any — see file_claims.py / pretooluse_bash.py gate 4).
#
# This hook never blocks: posttooluse_bash.py always exits 0. This wrapper only
# ever exits 0 too (a nonzero exit would be read as a hook crash, not a signal).
#
# Deliberately NOT `set -euo pipefail`: this shim runs after every Bash tool call
# machine-wide and must always reach its own `exit 0` / dispatch. `-e` would turn an
# unreadable stdin or a failing interpreter spawn into a hook crash on every call;
# `-u` and `pipefail` add failure paths with nothing to gain on a control flow this
# short. (bash_gate.sh, its PreToolUse sibling, is pinned the same way and tested by
# hooks/tests/test_bash_gate_patterns.sh.)

[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0

payload="$(cat)"

case "$payload" in
  *git*)
    printf '%s' "$payload" | python3 "$HOME/.claude/hooks/posttooluse_bash.py"
    ;;
  *)
    exit 0
    ;;
esac
