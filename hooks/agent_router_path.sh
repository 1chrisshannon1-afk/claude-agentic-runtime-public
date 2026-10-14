#!/usr/bin/env bash
# Fast path for hooks/agent_router.py --path (PostToolUse Write|Edit|MultiEdit):
# only paths that could match a path rule start Python; everything else exits in
# a few milliseconds with no output. Fails open.
#
# Deliberately NOT `set -euo pipefail`: this shim runs after every Write/Edit
# machine-wide and must fail OPEN, always reaching its own final `exit 0`. `-e` would
# make an unreadable stdin or a failing router spawn exit nonzero (a hook error on
# every edit); `-u` and `pipefail` add failure paths with nothing to gain on a
# control flow this short.
payload="$(cat)" || exit 0
shopt -s nocasematch
case "$payload" in
  *'/.claude/agents/'*|*'/plans/'*|*'_kb/'*) printf '%s' "$payload" | python3 "$HOME/.claude/hooks/agent_router.py" --path ;;
esac
exit 0
