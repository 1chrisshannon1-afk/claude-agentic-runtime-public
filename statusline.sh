#!/bin/bash
# Claude Code status line: model · dir · branch · context% · session cost.
# Hardened to be silent on stderr and robust to missing/odd input (runs sub-second
# across many parallel agents). bash 3.2 compatible (macOS system bash).
#
# Deliberately NOT `set -euo pipefail`: a status line must always print something and
# never fail loudly. Every probe below (jq on odd input, git outside a repo, awk on a
# junk cost) is expected to be able to fail and is already defaulted; `-e`/`-u` would
# turn one bad field into a blank bar plus a stderr burst on every refresh.
# Needs `jq` (optional: without it the bar shows empty fields, never an error).
input=$(cat)

# Single guarded jq pass (silent on error), one value per line so empty fields
# can't collapse (tab-IFS read would merge consecutive empties). Nulls -> "" / 0.
data=$(jq -r '(.model.display_name // ""), (.workspace.current_dir // ""), (.cost.total_cost_usd // 0), (.context_window.used_percentage // 0)' <<<"$input" 2>/dev/null)
{ IFS= read -r MODEL; IFS= read -r DIR; IFS= read -r COST; IFS= read -r PCT; } <<<"$data"

# Force PCT to a guaranteed integer: drop decimals, strip non-digits, default 0.
PCT=${PCT%%.*}
PCT=${PCT//[^0-9]/}
PCT=${PCT:-0}

# Coerce cost to a number (awk +0 turns any junk into 0) — never errors to stderr.
COST_FMT=$(awk -v c="$COST" 'BEGIN { printf "$%.2f", c + 0 }')

CYAN='\033[36m'
PURPLE='\033[35m'
YELLOW='\033[33m'
GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'

if [ "$PCT" -ge 90 ]; then BAR_COLOR="$RED"
elif [ "$PCT" -ge 70 ]; then BAR_COLOR="$YELLOW"
else BAR_COLOR="$GREEN"; fi

# Resolve branch only against a real directory; never run git against the
# status-line process's own cwd when DIR is empty.
BRANCH=""
if [ -n "$DIR" ] && [ -d "$DIR" ]; then
  BRANCH=$(git -C "$DIR" --no-optional-locks branch --show-current 2>/dev/null)
fi

DIR_NAME=${DIR##*/}

# All dynamic values flow through %s args; only operator-controlled color codes
# live in the format string, so a '%' in a branch name can't corrupt output.
if [ -n "$BRANCH" ]; then
  printf "${CYAN}%s${RESET}  ${PURPLE}%s${RESET}  ${GREEN}⎇ %s${RESET}  ${BAR_COLOR}ctx:%s%%${RESET}  ${YELLOW}%s${RESET}\n" \
    "$MODEL" "$DIR_NAME" "$BRANCH" "$PCT" "$COST_FMT"
else
  printf "${CYAN}%s${RESET}  ${PURPLE}%s${RESET}  ${BAR_COLOR}ctx:%s%%${RESET}  ${YELLOW}%s${RESET}\n" \
    "$MODEL" "$DIR_NAME" "$PCT" "$COST_FMT"
fi
