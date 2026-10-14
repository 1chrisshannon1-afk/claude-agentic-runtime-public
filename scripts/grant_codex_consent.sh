#!/usr/bin/env bash
# grant_codex_consent.sh — OPERATOR-ONLY. Run this directly in YOUR OWN
# terminal, WITH sudo, to authorize the Codex cross-model review scaffold
# (WS4) to send code diffs to OpenAI. No self-serve mechanism, and no agent
# running as the operator, can ever create the file this script writes --
# it must be owned by root, and this script refuses outright unless it is
# actually running as root.
#
# THIS SCRIPT IS NEVER AGENT-INVOKABLE IN PRACTICE. It is not referenced by
# any agent-facing hook/denial message, is not called by
# codex_available.sh or codex_review.sh, and is not something any agent
# tool grant lets an agent run "on its own initiative" as a substitute for
# a real human decision — an agent's own Bash tool call CAN technically
# shell out to `sudo bash grant_codex_consent.sh`, but sudo will prompt for
# the operator's own password/Touch ID interactively, which no agent can
# supply; the point of this script is that a human, not a self-report,
# decided to grant consent. Do not wire this into any agent workflow, any
# hook message, or any documentation an agent reads as "the way to get
# consent." An agent must never attempt to invoke this script with sudo —
# the runtime's own standing rule is that no agent ever tries to sudo, full
# stop, and this script's own refusal-when-not-root is not a substitute for
# that rule, only a backstop for it.
#
# What it writes: <runtime dir>/.review_state/codex/CONSENT.json, owned by
# root (uid 0), mode 0444 (read-only to everyone, writable by no one
# without root), a REGULAR file (never a symlink), containing:
#   {"consented_at": <epoch>, "operator": "<SUDO_USER>",
#    "scope": "ws4-v1-advisory", "host": "<hostname>"}
#
# codex_available.sh treats ANY other shape at that path -- user-owned,
# wrong mode, a symlink, wrong/missing scope, unparseable JSON -- as NOT
# consented. Deleting the file (which an ordinary agent CAN do, running as
# the operator's own user) revokes consent -- that direction fails safe.
# Creating a file that PASSES the check requires this script, requires
# root, and requires the human to have actually typed their own sudo
# password (or otherwise authenticated to sudo) themselves.
#
# Usage:
#   sudo bash ~/.claude/scripts/grant_codex_consent.sh
#   sudo bash ~/.claude/scripts/grant_codex_consent.sh --revoke
#   sudo bash ~/.claude/scripts/grant_codex_consent.sh --dry-run
#
# Refuses unless: `id -u` == 0 (i.e. actually running as root, which only
# happens via sudo/su) AND $SUDO_USER is set (so the marker can record
# WHICH human account granted consent, not just "root" — running as a bare
# root shell with no SUDO_USER set is refused too, since it cannot name an
# operator).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
CONSENT_DIR="$RUNTIME_DIR/.review_state/codex"
CONSENT_FILE="$CONSENT_DIR/CONSENT.json"

DRY_RUN=0
REVOKE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --revoke) REVOKE=1; shift ;;
    -h|--help)
      sed -n '2,40p' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *)
      echo "grant_codex_consent: unknown argument: $1" >&2
      exit 2 ;;
  esac
done

# --- Refuse unless genuinely root via sudo ---------------------------------
CURRENT_UID="$(id -u)"
if [ "$CURRENT_UID" != "0" ]; then
  echo "grant_codex_consent: REFUSED: must be run as root (via sudo), got uid=$CURRENT_UID." >&2
  echo "  Usage: sudo bash $0" >&2
  exit 1
fi

if [ -z "${SUDO_USER:-}" ]; then
  echo "grant_codex_consent: REFUSED: \$SUDO_USER is not set -- this must be run via 'sudo', not as a bare root shell, so the consent record can name which human account granted it." >&2
  exit 1
fi

if [ "$REVOKE" -eq 1 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would revoke: $CONSENT_FILE (if it exists)"
    exit 0
  fi
  if [ -e "$CONSENT_FILE" ] || [ -L "$CONSENT_FILE" ]; then
    rm -f "$CONSENT_FILE"
    echo "revoked: $CONSENT_FILE removed"
  else
    echo "nothing to revoke: $CONSENT_FILE did not exist"
  fi
  exit 0
fi

NOW_EPOCH="$(date -u +%s)"
HOST="$(hostname)"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "would write (owner root, mode 0444, regular file):"
  echo "  $CONSENT_FILE"
  echo "  {\"consented_at\": $NOW_EPOCH, \"operator\": \"$SUDO_USER\", \"scope\": \"ws4-v1-advisory\", \"host\": \"$HOST\"}"
  exit 0
fi

mkdir -p "$CONSENT_DIR"
# Directory itself need not be root-owned (the operator's own user created
# .review_state/ already); only the marker FILE's ownership matters to
# codex_available.sh's check.

TMP_PATH="${CONSENT_FILE}.tmp.$$"
# Never write through a symlink: if a prior path segment or the target
# itself is a symlink, refuse rather than follow it.
if [ -L "$CONSENT_FILE" ]; then
  echo "grant_codex_consent: REFUSED: $CONSENT_FILE already exists as a symlink -- remove it by hand first, this script will never write through one." >&2
  exit 1
fi

cat > "$TMP_PATH" <<JSON
{"consented_at": ${NOW_EPOCH}, "operator": "${SUDO_USER}", "scope": "ws4-v1-advisory", "host": "${HOST}"}
JSON

chown root:wheel "$TMP_PATH" 2>/dev/null || chown root "$TMP_PATH"
chmod 0444 "$TMP_PATH"
mv -f "$TMP_PATH" "$CONSENT_FILE"

echo "granted: consent recorded at $CONSENT_FILE (owner root, mode 0444)"
echo "operator: $SUDO_USER"
echo "scope: ws4-v1-advisory"
echo "revoke any time with: sudo bash $0 --revoke"
