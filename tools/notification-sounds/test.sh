#!/usr/bin/env bash
# notification-sounds/test.sh — full suite for install.sh / uninstall.sh and the runtime
# behavior of every hook command. No audio: `say` and `afplay` are stubbed to a log so
# invocations/words are counted, not heard. Exit non-zero if any check fails.
#   Usage:  bash test.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL="$HERE/install.sh"; UNINSTALL="$HERE/uninstall.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '       %s\n' "$2"; }
eq()  { [ "$2" = "$3" ] && ok "$1" || bad "$1" "expected [$3] got [$2]"; }

# stub say + afplay → log args (no audio) ---------------------------------------
STUB="$WORK/bin"; mkdir -p "$STUB"
printf '#!/usr/bin/env bash\necho "say $*" >> "$LOG"\n'    > "$STUB/say";    chmod +x "$STUB/say"
printf '#!/usr/bin/env bash\necho "afplay $*" >> "$LOG"\n' > "$STUB/afplay"; chmod +x "$STUB/afplay"
LOG="$WORK/cue.log"
run_hook() { : > "$LOG"; OUT="$(printf '%s' "$2" | PATH="$STUB:$PATH" LOG="$LOG" bash -c "$1" 2>/dev/null)"; RC=$?; sleep 0.4; }
count()   { local n; n=$(grep -c . "$LOG" 2>/dev/null); echo "${n:-0}"; }
cmd_of()  { jq -r "$2" "$1"; }

echo "== Group A: install — merge / preserve / upgrade / idempotency (voice default) =="
S1="$WORK/a1.json"; echo '{}' > "$S1"; CC_SETTINGS="$S1" bash "$INSTALL" >/dev/null
for ev in Notification PermissionRequest PermissionDenied Stop PreCompact; do
  eq "A1 $ev present" "$(jq --arg e "$ev" '.hooks[$e]|length' "$S1")" "1"
done
eq "A1 StopFailure has 3 matcher entries" "$(jq '.hooks.StopFailure|length' "$S1")" "3"
eq "A1 valid JSON"                        "$(jq -e . "$S1" >/dev/null 2>&1 && echo ok)" "ok"
eq "A1 Notification matcher = idle_prompt" "$(jq -r '.hooks.Notification[0].matcher' "$S1")" "idle_prompt"
eq "A1 PreCompact matcher = auto|manual"   "$(jq -r '.hooks.PreCompact[0].matcher' "$S1")" "auto|manual"
eq "A1 StopFailure throttle matcher"       "$(jq -r '[.hooks.StopFailure[]|select(.hooks[0].command|contains("throttled"))][0].matcher' "$S1")" "rate_limit|overloaded"
eq "A1 StopFailure billing matcher"        "$(jq -r '[.hooks.StopFailure[]|select(.hooks[0].command|contains("credits"))][0].matcher' "$S1")" "billing_error"

S2="$WORK/a2.json"
cat > "$S2" <<'EOF'
{ "model": "sonnet",
  "hooks": {
    "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "echo pre" } ] } ],
    "Stop": [ { "hooks": [ { "type": "command", "command": "echo my-own-gate" } ] } ] } }
EOF
CC_SETTINGS="$S2" bash "$INSTALL" >/dev/null
eq "A2 preserves top-level model"       "$(jq -r '.model' "$S2")" "sonnet"
eq "A3 preserves unrelated PreToolUse"  "$(jq -r '.hooks.PreToolUse[0].hooks[0].command' "$S2")" "echo pre"
eq "A3 preserves user's own Stop hook"  "$(jq '[.hooks.Stop[].hooks[0].command|select(.=="echo my-own-gate")]|length' "$S2")" "1"
eq "A3 adds our done cue alongside it"  "$(jq '.hooks.Stop|length' "$S2")" "2"

# upgrade from a legacy tone install (System/Library/Sounds) → replaced, not duplicated
S4="$WORK/a4.json"
cat > "$S4" <<'EOF'
{ "hooks": {
  "Notification": [ { "hooks": [ { "type": "command", "command": "afplay -r 1.8 /System/Library/Sounds/Ping.aiff >/dev/null 2>&1 &" } ] } ],
  "Stop": [ { "hooks": [ { "type": "command", "command": "afplay -r 1.8 /System/Library/Sounds/Glass.aiff >/dev/null 2>&1 &" } ] } ] } }
EOF
CC_SETTINGS="$S4" bash "$INSTALL" >/dev/null
eq "A4 Notification not duplicated"     "$(jq '.hooks.Notification|length' "$S4")" "1"
eq "A4 legacy tone replaced by voice"   "$(jq -r '.hooks.Notification[0].hooks[0].command|contains("say")' "$S4")" "true"
eq "A4 Stop chime replaced, one entry"  "$(jq '.hooks.Stop|length' "$S4")" "1"

CC_SETTINGS="$S1" bash "$INSTALL" >/dev/null; CC_SETTINGS="$S1" bash "$INSTALL" >/dev/null
eq "A5 Notification idempotent"         "$(jq '.hooks.Notification|length' "$S1")" "1"
eq "A5 StopFailure stays 3 (not 9)"     "$(jq '.hooks.StopFailure|length' "$S1")" "3"
eq "A6 backup written"                  "$(ls "$WORK"/a1.json.bak.* >/dev/null 2>&1 && echo ok)" "ok"

echo "== Group B: voice runtime behavior (say stubbed) =="
Q="$(cmd_of "$S1" '.hooks.Notification[0].hooks[0].command')"
A="$(cmd_of "$S1" '.hooks.PermissionRequest[0].hooks[0].command')"
DEN="$(cmd_of "$S1" '.hooks.PermissionDenied[0].hooks[0].command')"
DONE="$(cmd_of "$S1" '.hooks.Stop[-1].hooks[0].command')"
THR="$(cmd_of "$S1" '[.hooks.StopFailure[]|select(.hooks[0].command|contains("throttled"))][0].hooks[0].command')"
CRED="$(cmd_of "$S1" '[.hooks.StopFailure[]|select(.hooks[0].command|contains("credits"))][0].hooks[0].command')"
ERR="$(cmd_of "$S1" '[.hooks.StopFailure[]|select(.hooks[0].command|contains("\"error\""))][0].hooks[0].command')"
CMP="$(cmd_of "$S1" '.hooks.PreCompact[0].hooks[0].command')"

run_hook "$Q" '{}';                          eq "B question says 'question'"  "$(grep -c 'say question' "$LOG")" "1"
run_hook "$A" '{}';                          eq "B approval says 'approval'"  "$(grep -c 'say approval' "$LOG")" "1"
eq "B approval exits 0"      "$RC" "0"
eq "B approval no stdout"    "$OUT" ""      # pure side-effect: never alters approve/deny
run_hook "$DEN" '{}';                        eq "B denied says 'denied'"      "$(grep -c 'say denied' "$LOG")" "1"
run_hook "$THR" '{}';                        eq "B throttle says 'throttled'" "$(grep -c 'say throttled' "$LOG")" "1"
run_hook "$CRED" '{}';                       eq "B credits says 'credits'"    "$(grep -c 'say credits' "$LOG")" "1"
run_hook "$ERR" '{}';                        eq "B error says 'error'"        "$(grep -c 'say error' "$LOG")" "1"
run_hook "$CMP" '{}';                        eq "B compacting says 'compacting'" "$(grep -c 'say compacting' "$LOG")" "1"
run_hook "$DONE" '{"stop_hook_active":true}';  eq "B done silent on re-wake"  "$(count)" "0"
run_hook "$DONE" '{"stop_hook_active":false}'; eq "B done speaks on turn-end" "$(grep -c 'say done' "$LOG")" "1"
run_hook "$DONE" '{}';                         eq "B done fail-open (absent flag)" "$(grep -c 'say done' "$LOG")" "1"
# jq unavailable at runtime → done cue must STILL play
JQB="$WORK/jqb"; mkdir -p "$JQB"; printf '#!/usr/bin/env bash\nexit 127\n' > "$JQB/jq"; chmod +x "$JQB/jq"
: > "$LOG"; printf '%s' '{"stop_hook_active":true}' | PATH="$JQB:$STUB:$PATH" LOG="$LOG" bash -c "$DONE" >/dev/null 2>&1; sleep 0.4
eq "B done fail-open when jq missing"           "$(grep -c 'say done' "$LOG")" "1"

echo "== Group C: knobs + guard =="
S5="$WORK/c1.json"; echo '{}' > "$S5"
CC_SETTINGS="$S5" CC_SAY_DONE=finished CC_SAY_VOICE=Samantha bash "$INSTALL" >/dev/null
eq "C custom word applied"      "$(jq -r '.hooks.Stop[0].hooks[0].command|contains("\"finished\"")' "$S5")" "true"
eq "C custom voice applied"     "$(jq -r '.hooks.Stop[0].hooks[0].command|contains("-v Samantha")' "$S5")" "true"
S6="$WORK/c2.json"; echo '{"keep":1}' > "$S6"
CC_SETTINGS="$S6" CC_CUE=banana bash "$INSTALL" >/dev/null 2>&1
eq "C invalid CC_CUE rejected"  "$([ $? -ne 0 ] && echo ok)" "ok"
eq "C settings untouched"       "$(jq -r '.hooks // "none"' "$S6")" "none"
S7="$WORK/c3.json"; echo '{}' > "$S7"
CC_SETTINGS="$S7" CC_HOOK_PREFIX='[ "${GUARD:-0}" = "1" ] && exit 0; ' bash "$INSTALL" >/dev/null
GG="$(cmd_of "$S7" '.hooks.Stop[0].hooks[0].command')"
: > "$LOG"; printf '%s' '{"stop_hook_active":false}' | PATH="$STUB:$PATH" LOG="$LOG" GUARD=1 bash -c "$GG" >/dev/null 2>&1; sleep 0.4
eq "C guard=1 silences a turn-end" "$(count)" "0"
: > "$LOG"; printf '%s' '{"stop_hook_active":false}' | PATH="$STUB:$PATH" LOG="$LOG" bash -c "$GG" >/dev/null 2>&1; sleep 0.4
eq "C guard unset still speaks"    "$(count)" "1"

echo "== Group D: tone style =="
S8="$WORK/d1.json"; echo '{}' > "$S8"; CC_SETTINGS="$S8" CC_CUE=tone bash "$INSTALL" >/dev/null
TQ="$(cmd_of "$S8" '.hooks.Notification[0].hooks[0].command')"
TDONE="$(cmd_of "$S8" '.hooks.Stop[0].hooks[0].command')"
TDEN="$(cmd_of "$S8" '.hooks.PermissionDenied[0].hooks[0].command')"
run_hook "$TQ" '{}';                          eq "D tone question rings twice" "$(count)" "2"
run_hook "$TDONE" '{"stop_hook_active":false}'; eq "D tone done plays once"     "$(grep -c Glass.aiff "$LOG")" "1"
run_hook "$TDONE" '{"stop_hook_active":true}';  eq "D tone done gated silent"   "$(count)" "0"
run_hook "$TDEN" '{}';                         eq "D tone denied uses Basso"    "$(grep -c Basso.aiff "$LOG")" "1"

echo "== Group E: uninstall =="
S9="$WORK/e1.json"
cat > "$S9" <<'EOF'
{ "model": "opus", "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "echo my-own-gate" } ] } ] } }
EOF
CC_SETTINGS="$S9" bash "$INSTALL" >/dev/null
CC_SETTINGS="$S9" bash "$UNINSTALL" >/dev/null
for ev in Notification PermissionRequest PermissionDenied StopFailure PreCompact; do
  eq "E $ev event removed" "$(jq --arg e "$ev" -r '.hooks[$e] // "gone"' "$S9")" "gone"
done
eq "E our done cue removed from Stop"  "$(jq '[.hooks.Stop[].hooks[0].command|select(contains("cc-notify"))]|length' "$S9")" "0"
eq "E user's own Stop hook preserved"  "$(jq -r '.hooks.Stop[0].hooks[0].command' "$S9")" "echo my-own-gate"
eq "E top-level settings preserved"    "$(jq -r '.model' "$S9")" "opus"

echo
echo "==================== $PASS passed, $FAIL failed ===================="
[ "$FAIL" -eq 0 ]
