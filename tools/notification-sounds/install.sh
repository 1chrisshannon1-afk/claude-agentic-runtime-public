#!/usr/bin/env bash
# notification-sounds/install.sh — audible Claude Code alerts (macOS).
#
# Maps Claude Code hook events to short audio cues so you only look over when needed.
# Default cue style is spoken words (CC_CUE=voice); a chime style is also available (tone).
#
#   Event               Fires when…                                   voice     tone (default sound)
#   Notification/idle   Claude is idle, waiting on your next prompt    "question"  Ping ×2
#   PermissionRequest   an approval prompt appears (even mid-work)     "approval"  Ping ×2
#   PermissionDenied    a tool call is denied/blocked                  "denied"    Basso
#   Stop  (gated)       Claude finishes a turn cleanly (fires ONCE)    "done"      Glass
#   StopFailure/429     turn fails on rate_limit or overloaded         "throttled" Submarine
#   StopFailure/billing turn fails on a billing/quota error            "credits"   Funk
#   StopFailure/other   turn fails on any other API error              "error"     Sosumi
#   PreCompact          context is auto-summarized (or manual /compact)"compacting" Pop
#
# Idempotent: any prior module hook (marked ": cc-notify;" or a legacy tone hook) is replaced,
# so re-running — or switching style/words/knobs — never leaves duplicates.
#
# Knobs (all optional env vars):
#   CC_CUE=voice|tone                 cue style (default voice)
#   CC_SAY_QUESTION / _APPROVAL / _DENIED / _DONE / _ERROR / _THROTTLE / _CREDITS / _COMPACT
#                                     spoken words (voice); defaults are the words above
#   CC_SAY_VOICE=''                   `say -v NAME` (empty = system default; list: say -v '?')
#   CC_SAY_RATE=''                    `say -r WPM` speaking rate
#   CC_SOUND_RATE=1.8                 tone playback rate = pitch (lower = deeper)          (tone)
#   CC_SOUND_QUESTION / _APPROVAL / _DENIED / _DONE / _ERROR / _THROTTLE / _CREDITS / _COMPACT
#                                     per-event sound file in /System/Library/Sounds       (tone)
#   CC_HOOK_PREFIX=''                 shell prefix prepended to every command (e.g. a mute guard)
#   CC_SETTINGS=~/.claude/settings.json   target file (override for testing)
set -euo pipefail

CUE="${CC_CUE:-voice}"
PREFIX="${CC_HOOK_PREFIX:-}"
SETTINGS="${CC_SETTINGS:-$HOME/.claude/settings.json}"
MARK=": cc-notify;"   # marker identifying our hooks (present in every mode)

command -v jq >/dev/null 2>&1 || { echo "✗ jq required — brew install jq"; exit 1; }
# The cues are macOS tools (`say`, `afplay`, /System/Library/Sounds). Elsewhere nothing is
# installed: settings.json is not touched and the hooks it would add could never play.
[ "$(uname -s)" = "Darwin" ] || { echo "✗ macOS-only (uses say / afplay) — nothing installed on $(uname -s)"; exit 1; }

# Build the per-event "play" fragment ($P_*) for the chosen style. All backgrounded with &.
if [ "$CUE" = "voice" ]; then
  command -v say >/dev/null 2>&1 || { echo "✗ say not found — this module is macOS-only"; exit 1; }
  V=""; [ -n "${CC_SAY_VOICE:-}" ] && V="$V -v ${CC_SAY_VOICE}"; [ -n "${CC_SAY_RATE:-}" ] && V="$V -r ${CC_SAY_RATE}"
  say_of() { printf 'say%s "%s" >/dev/null 2>&1 &' "$V" "$1"; }
  P_Q="$(say_of "${CC_SAY_QUESTION:-question}")";  P_A="$(say_of "${CC_SAY_APPROVAL:-approval}")"
  P_DEN="$(say_of "${CC_SAY_DENIED:-denied}")";    P_DONE="$(say_of "${CC_SAY_DONE:-done}")"
  P_ERR="$(say_of "${CC_SAY_ERROR:-error}")";      P_THR="$(say_of "${CC_SAY_THROTTLE:-throttled}")"
  P_CRED="$(say_of "${CC_SAY_CREDITS:-credits}")"; P_CMP="$(say_of "${CC_SAY_COMPACT:-compacting}")"
  DESC="voice: question / approval / denied / done / error / throttled / credits / compacting"
elif [ "$CUE" = "tone" ]; then
  command -v afplay >/dev/null 2>&1 || { echo "✗ afplay not found — this module is macOS-only"; exit 1; }
  RATE="${CC_SOUND_RATE:-1.8}"; SND="/System/Library/Sounds"
  Q_S="${CC_SOUND_QUESTION:-Ping.aiff}"; A_S="${CC_SOUND_APPROVAL:-Ping.aiff}"; DEN_S="${CC_SOUND_DENIED:-Basso.aiff}"
  DONE_S="${CC_SOUND_DONE:-Glass.aiff}"; ERR_S="${CC_SOUND_ERROR:-Sosumi.aiff}"; THR_S="${CC_SOUND_THROTTLE:-Submarine.aiff}"
  CRED_S="${CC_SOUND_CREDITS:-Funk.aiff}"; CMP_S="${CC_SOUND_COMPACT:-Pop.aiff}"
  for f in "$Q_S" "$A_S" "$DEN_S" "$DONE_S" "$ERR_S" "$THR_S" "$CRED_S" "$CMP_S"; do
    [ -f "$SND/$f" ] || { echo "✗ sound not found: $SND/$f (see: ls $SND)"; exit 1; }
  done
  tone_of()  { printf 'afplay -r %s %s/%s >/dev/null 2>&1 &' "$RATE" "$SND" "$1"; }
  ring2_of() { printf '(afplay -r %s %s/%s; afplay -r %s %s/%s) >/dev/null 2>&1 &' "$RATE" "$SND" "$1" "$RATE" "$SND" "$1"; }
  P_Q="$(ring2_of "$Q_S")";  P_A="$(ring2_of "$A_S")"; P_DEN="$(tone_of "$DEN_S")"; P_DONE="$(tone_of "$DONE_S")"
  P_ERR="$(tone_of "$ERR_S")"; P_THR="$(tone_of "$THR_S")"; P_CRED="$(tone_of "$CRED_S")"; P_CMP="$(tone_of "$CMP_S")"
  DESC="tone: $Q_S ×2 / $DONE_S ×1 / distinct sounds for denied·error·throttled·credits·compacting @ rate $RATE"
else
  echo "✗ CC_CUE must be 'voice' or 'tone' (got '$CUE')"; exit 1
fi

# Assemble commands: marker + optional guard + [Stop gate on the 'done' cue] + play.
# The 'done' cue reads the Stop event's stop_hook_active flag so it fires only on a genuine
# turn-end (false/absent) and stays silent on Stop-hook re-wakes (true). If jq is missing at
# runtime the `&&` fails and it falls through to the cue — the finished signal is never lost.
G="jq -e '.stop_hook_active==true' >/dev/null 2>&1 && exit 0; "
C_Q="$MARK ${PREFIX}$P_Q";        C_A="$MARK ${PREFIX}$P_A";    C_DEN="$MARK ${PREFIX}$P_DEN"
C_DONE="$MARK ${PREFIX}${G}$P_DONE"; C_ERR="$MARK ${PREFIX}$P_ERR"; C_THR="$MARK ${PREFIX}$P_THR"
C_CRED="$MARK ${PREFIX}$P_CRED";  C_CMP="$MARK ${PREFIX}$P_CMP"

mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak.$(date +%s)"

tmp="$(mktemp)"
jq --arg q "$C_Q" --arg a "$C_A" --arg den "$C_DEN" --arg fin "$C_DONE" \
   --arg err "$C_ERR" --arg thr "$C_THR" --arg cred "$C_CRED" --arg cmp "$C_CMP" '
  def ours: (.hooks[0].command // "") | (contains("cc-notify") or contains("System/Library/Sounds"));
  def keep(f): (f // []) | map(select(ours | not));
  .hooks //= {}
  | .hooks.Notification      = (keep(.hooks.Notification)      + [{matcher: "idle_prompt", hooks: [{type: "command", command: $q}]}])
  | .hooks.PermissionRequest = (keep(.hooks.PermissionRequest) + [{hooks: [{type: "command", command: $a}]}])
  | .hooks.PermissionDenied  = (keep(.hooks.PermissionDenied)  + [{hooks: [{type: "command", command: $den}]}])
  | .hooks.Stop              = (keep(.hooks.Stop)              + [{hooks: [{type: "command", command: $fin}]}])
  | .hooks.StopFailure       = (keep(.hooks.StopFailure)       + [
      {matcher: "rate_limit|overloaded", hooks: [{type: "command", command: $thr}]},
      {matcher: "billing_error", hooks: [{type: "command", command: $cred}]},
      {matcher: "authentication_failed|oauth_org_not_allowed|invalid_request|model_not_found|server_error|max_output_tokens|unknown", hooks: [{type: "command", command: $err}]}
    ])
  | .hooks.PreCompact        = (keep(.hooks.PreCompact)        + [{matcher: "auto|manual", hooks: [{type: "command", command: $cmp}]}])
' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"

echo "✓ installed in $SETTINGS"
echo "   $DESC${PREFIX:+   (guarded)}"
echo "   → open /hooks in Claude Code once, or restart, to load it."
