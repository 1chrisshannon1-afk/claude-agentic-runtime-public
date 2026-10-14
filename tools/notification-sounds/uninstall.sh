#!/usr/bin/env bash
# notification-sounds/uninstall.sh — remove the sound hooks this module installed.
#
# Strips any hook whose command references "/System/Library/Sounds/" (the signature of a
# module sound hook) from EVERY hook event, drops now-empty event arrays, and leaves all
# your other hooks and settings untouched. Backs up first. Reload with /hooks afterward.
#   CC_SETTINGS=~/.claude/settings.json   target file (override for testing)
set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo "✗ jq required — brew install jq"; exit 1; }
SETTINGS="${CC_SETTINGS:-$HOME/.claude/settings.json}"
[ -f "$SETTINGS" ] || { echo "nothing to do — $SETTINGS not found"; exit 0; }
cp "$SETTINGS" "$SETTINGS.bak.$(date +%s)"

tmp="$(mktemp)"
jq '
  if (.hooks | type) == "object" then
    .hooks |= (
      to_entries
      | map(.value |= map(select((.hooks[0].command // "") | (contains("cc-notify") or contains("System/Library/Sounds")) | not)))
      | map(select((.value | length) > 0))
      | from_entries
    )
  else . end
' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"

echo "✓ removed module sound hooks from $SETTINGS (other hooks preserved)"
echo "   → open /hooks in Claude Code once, or restart, to unload them."
