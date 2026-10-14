#!/usr/bin/env bash
# grant_model_exception.sh — OPERATOR-ONLY. Run this directly in YOUR OWN
# terminal to authorize exactly one off-pin Task dispatch that no self-serve
# mechanism can ever authorize (most notably: any target model of "fable",
# or an escalation whose source pin isn't "sonnet" — see
# hooks/record_model_exception.py's B5 fix for why those are hard-refused).
#
# THIS SCRIPT IS NEVER AGENT-INVOKABLE IN PRACTICE. It is not referenced by
# any agent-facing hook/denial message, is not called by
# record_model_exception.py, and is not something any agent tool grant lets
# an agent run "on its own initiative" as a substitute for a real human
# decision — an agent's own Bash tool call CAN technically shell out to it,
# but doing so is indistinguishable from the operator being asked (via any
# other channel) to run it themselves; the point of this script is that a
# human, not a self-report, decided to grant the exception. Do not wire this
# into any agent workflow, any hook message, or any documentation an agent
# reads as "the way to get an exception."
#
# Writes a single-use, short-TTL grant file that
# hooks/model_pin_gate.py's find_and_consume_operator_grant() consumes
# atomically (same claim mechanism as the self-serve exception-token store —
# see that module's own docstring) the next time the named (agent_type,
# model) pair is dispatched off-pin.
#
# Usage:
#   ~/.claude/scripts/grant_model_exception.sh <agent_type> <model> [ttl_seconds]
#
# Examples:
#   ~/.claude/scripts/grant_model_exception.sh code-reviewer fable
#   ~/.claude/scripts/grant_model_exception.sh trade-tile opus 900
#
# Writes:
#   ~/.claude/.model_exceptions/operator_grant_<agent>_<model>_<ts>.json
#   {"agent_type": ..., "model": ..., "granted_at": ..., "expires_at": ...}

set -euo pipefail

usage() {
  echo "usage: $(basename "$0") <agent_type> <model> [ttl_seconds, default 1800]" >&2
  exit 2
}

AGENT_TYPE="${1:-}"
MODEL="${2:-}"
TTL_SECONDS="${3:-1800}"

[ -n "$AGENT_TYPE" ] || usage
[ -n "$MODEL" ] || usage
case "$TTL_SECONDS" in
  ''|*[!0-9]*) echo "error: ttl_seconds must be a positive integer, got '$TTL_SECONDS'" >&2; exit 2 ;;
esac

DIR="${HOME}/.claude/.model_exceptions"
mkdir -p "$DIR"

NOW_EPOCH=$(date -u +%s)
EXPIRES_EPOCH=$((NOW_EPOCH + TTL_SECONDS))

# BSD date (macOS, this machine) uses `-r <epoch>`; GNU date uses `-d @<epoch>`.
# Try BSD first, fall back to GNU, so this script is portable either way.
fmt_ts() {
  local epoch="$1"
  date -u -r "$epoch" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
    || date -u -d "@${epoch}" +"%Y-%m-%dT%H:%M:%SZ"
}

NOW_TS=$(fmt_ts "$NOW_EPOCH")
EXPIRES_TS=$(fmt_ts "$EXPIRES_EPOCH")
FILE_TS=$(date -u +"%Y%m%dT%H%M%SZ")

OUT_PATH="${DIR}/operator_grant_${AGENT_TYPE}_${MODEL}_${FILE_TS}.json"
TMP_PATH="${OUT_PATH}.tmp.$$"

cat > "$TMP_PATH" <<JSON
{"agent_type": "${AGENT_TYPE}", "model": "${MODEL}", "granted_at": "${NOW_TS}", "expires_at": "${EXPIRES_TS}"}
JSON
mv "$TMP_PATH" "$OUT_PATH"

echo "granted: agent_type=${AGENT_TYPE} model=${MODEL} expires_at=${EXPIRES_TS} (single-use, consumed on the next matching dispatch)"
echo "file: ${OUT_PATH}"
