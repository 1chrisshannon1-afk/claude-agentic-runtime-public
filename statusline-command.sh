#!/bin/sh
# Minimal alternative status line: prints the current git branch only.
# Deliberately NOT `set -eu`: a status line must always finish quietly. `jq` missing or
# a non-repo cwd yields an empty branch and no output, which is the intended result.
input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null)
if [ -n "$branch" ]; then
  printf "branch: %s" "$branch"
fi
