#!/usr/bin/env bash
# test_bash_gate_patterns.sh -- table test for hooks/bash_gate.sh's matched-command set.
#
# WHY THIS EXISTS: bash_gate.sh is the pure-bash fast path in front of the PreToolUse:Bash
# guard chain (pretooluse_bash.py). It reads the hook payload once and spawns the python
# dispatcher ONLY when the payload could be a git op, a gcloud identity change, the inline
# bypass tripwire, a `gh issue close`, an issue-create, or a protected-board add. Everything
# else must be allowed WITHOUT a python spawn. Two failure modes matter, and they are
# opposite: a pattern that stops matching silently waives a guard for that command shape
# (the dangerous direction); a pattern that over-matches only costs a python spawn.
#
# The linter once flagged SC2221/SC2222 on that case statement (a later alternative fully
# shadowed by an earlier one). Removing a shadowed alternative must keep the matched set
# IDENTICAL; this table is how that is proven, and it stays as the guard against a later
# edit narrowing the set by accident. The expectations are the gate's decisions as they
# stand today (route to the dispatcher vs fast-allow), checked row by row against the case
# statement's own arms, not a snapshot of whatever a rewrite happens to output.
#
# Method: run the REAL gate with a stub `python3` first on PATH and an isolated $HOME. The
# stub records that it was invoked (and with which script); the gate's decision is "dispatch"
# if the stub ran, "allow" otherwise. The real dispatcher is never run here.
#
# Env: BASH_GATE_SRC=<path> points the table at a candidate or mutant copy of the gate
# (default: ../bash_gate.sh next to this file's tests dir).
#
# Run: bash hooks/tests/test_bash_gate_patterns.sh      Exit: 0 all pass, 1 otherwise.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="${BASH_GATE_SRC:-$HERE/../bash_gate.sh}"
[ -f "$GATE" ] || { echo "FATAL: gate not found: $GATE" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/bash_gate_patterns.XXXXXX")" || { echo "FATAL: mktemp" >&2; exit 1; }
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin" "$WORK/home/.claude/hooks"

# Stub interpreter: drains stdin (the gate pipes the payload in), records its argv.
cat > "$WORK/bin/python3" <<STUB
#!/bin/sh
cat > /dev/null
printf '%s\n' "\$*" >> "$WORK/dispatched"
exit 0
STUB
chmod +x "$WORK/bin/python3"

PASS=0
FAIL=0
DECISION=""
GATE_RC=0

# decide <command> [VAR=value ...]  -> sets DECISION (dispatch|allow) and GATE_RC.
decide() {
  local cmd="$1"
  shift
  local esc payload
  esc="${cmd//\\/\\\\}"
  esc="${esc//\"/\\\"}"
  # Neutral scaffolding: none of these fields contains git/gcloud/gh/project, so a bare
  # `ls` row proves the envelope itself never triggers a dispatch.
  payload="{\"session_id\":\"s1\",\"cwd\":\"/work/proj\",\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"$esc\"}}"
  rm -f "$WORK/dispatched"
  printf '%s' "$payload" \
    | env -u CSA_DISABLE_HOOKS env "$@" HOME="$WORK/home" PATH="$WORK/bin:$PATH" bash "$GATE" >/dev/null 2>&1
  GATE_RC=$?
  if [ -e "$WORK/dispatched" ]; then DECISION="dispatch"; else DECISION="allow"; fi
}

# row <expected> <command> <why> [VAR=value ...]
row() {
  local want="$1" cmd="$2" why="$3"
  shift 3
  decide "$cmd" "$@"
  if [ "$DECISION" = "$want" ] && [ "$GATE_RC" -eq 0 ]; then
    PASS=$((PASS + 1))
    printf '  PASS  %-8s %s  [%s]\n' "$want" "$cmd" "$why"
  else
    FAIL=$((FAIL + 1))
    printf '  FAIL  want=%s got=%s rc=%s  %s  [%s]\n' "$want" "$DECISION" "$GATE_RC" "$cmd" "$why"
  fi
}

echo "controls -- commands no guard acts on must fast-allow (no python spawn)"
row allow 'ls -la' 'plain listing'
row allow 'echo hello' 'plain echo'
row allow 'npm test' 'unrelated tool'
row allow 'python3 -m pytest hooks/tests -q' 'unrelated python'
row allow 'echo high though' '"gh" only as a substring of ordinary words'
row allow 'gh pr view 5' 'gh read with no guarded token'
row allow 'gh issue list' 'gh issue read, no close/create'
row allow 'gh issue view 5' 'gh issue read, no close/create'
row allow 'gh api repos/o/r/pulls' 'gh api with no project/addProjectV2'
row allow 'echo project plan' '"project" in prose without gh'
row allow 'python3 -m pytest -p no:cacheprovider create' '-p and create but no gh token'
row allow 'gh close issue' 'gh issue close tokens out of order'
row allow 'bash scripts/gh_issue.sh resolve 5' 'gh_issue.sh without create or close'
row allow 'bash scripts/gh_issue.sh transition 5 --column Done' 'gh_issue.sh transition'

echo "git -- every git invocation routes to the dispatcher (state verbs, staging, commits)"
row dispatch 'git checkout main' 'state verb: checkout'
row dispatch 'git switch -c topic' 'state verb: switch'
row dispatch 'git stash' 'state verb: stash'
row dispatch 'git stash pop' 'state verb: stash pop'
row dispatch 'git reset --hard HEAD' 'state verb: reset'
row dispatch 'git rebase -i HEAD~3' 'state verb: rebase'
row dispatch 'git restore --staged a.py' 'restore, index-only form (dispatcher allows it)'
row dispatch 'git restore a.py' 'restore, working-tree form (dispatcher denies it)'
row dispatch 'git add -A' 'bulk staging: add -A'
row dispatch 'git add .' 'bulk staging: add .'
row dispatch 'git commit -a -m x' 'commit -a'
row dispatch 'git commit -m x -- a.py' 'commit with pathspec'
row dispatch 'git commit -m x' 'commit without pathspec'
row dispatch 'git worktree list' 'worktree list (allowed form)'
row dispatch 'git worktree add ../x' 'worktree add (blocked form)'
row dispatch 'git -C /repo status' 'git -C prefix'
row dispatch 'cat .gitignore' 'substring posture: "git" inside a filename'
row dispatch 'echo digital' 'substring posture: "git" inside an ordinary word'

echo "gcloud / inline tripwire"
row dispatch 'gcloud config set account a@b.example' 'gcloud identity mutation'
row dispatch 'gcloud auth login' 'gcloud auth'
row dispatch 'CSA_ALLOW_GIT_STATE_OPS=1 true' 'inline bypass tripwire (uppercase GIT: only the tripwire arm matches)'

echo "gh issue close / create (gates 5 and the create observer)"
row dispatch 'gh issue close 12 --comment x' 'gh issue close'
row dispatch 'gh --repo o/r issue close 12' 'gh issue close, flags between tokens'
row dispatch 'bash scripts/gh_issue.sh close 12' 'helper close: gh_issue.sh close (gh..issue..close)'
row dispatch 'gh issue create --title t' 'gh issue create'
row dispatch 'gh_issue.sh create --title t' 'helper create, bare name'
row dispatch '/opt/x/bin/gh_issue.sh create --related 5' 'helper create, any path prefix'
row dispatch './gh_issue.sh    create --title t' 'helper create, extra spaces'
row dispatch 'bash ~/.claude/scripts/gh_issue.sh --force-new create' 'helper create, flag before verb'

echo "protected-board add shapes (gate 5b)"
row dispatch 'gh project item-add 1 --owner o --url u' 'gh project'
row dispatch "gh api graphql -f query='mutation{addProjectV2ItemById(input:{})}'" 'addProjectV2 mutation'
row dispatch 'somecmd addProjectV2DraftIssue' 'addProjectV2 alone (no gh needed)'
row dispatch 'gh issue edit 5 --add-project Board' '--add-project flag'
row dispatch 'gh pr create --project=Board --title x' '--project= flag'
row dispatch 'somecmd --project Board' '--project flag, no gh at all'
row dispatch 'gh pr create -p Board --title x' 'short -p on gh create (only the *gh*create*-p* arm)'
row dispatch 'gh pr edit 3 -p Board' 'short -p on gh edit (only the *gh*edit*-p* arm)'

echo "kill switch"
row allow 'git stash' 'CSA_DISABLE_HOOKS=1 is a global no-op' CSA_DISABLE_HOOKS=1
row allow 'gh issue close 12' 'CSA_DISABLE_HOOKS=1 beats every arm' CSA_DISABLE_HOOKS=1
row dispatch 'git stash' 'CSA_DISABLE_HOOKS=0 does not disable' CSA_DISABLE_HOOKS=0

echo "dispatcher contract"
decide 'git stash'
if grep -q 'pretooluse_bash.py' "$WORK/dispatched" 2>/dev/null; then
  PASS=$((PASS + 1)); echo "  PASS  a dispatch runs \$HOME/.claude/hooks/pretooluse_bash.py"
else
  FAIL=$((FAIL + 1)); echo "  FAIL  a dispatch must run pretooluse_bash.py (got: $(cat "$WORK/dispatched" 2>/dev/null))"
fi
if grep -q "^$WORK/home/.claude/hooks/pretooluse_bash.py\$" "$WORK/dispatched" 2>/dev/null; then
  PASS=$((PASS + 1)); echo "  PASS  the dispatcher path is resolved from \$HOME (check_safety_core_parity reads this literal)"
else
  FAIL=$((FAIL + 1)); echo "  FAIL  the dispatcher path must be \$HOME/.claude/hooks/pretooluse_bash.py (got: $(cat "$WORK/dispatched" 2>/dev/null))"
fi
if grep -Fq 'python3 "$HOME/.claude/hooks/pretooluse_bash.py"' "$GATE"; then
  PASS=$((PASS + 1)); echo "  PASS  source keeps the literal python3 \"\$HOME/.claude/hooks/pretooluse_bash.py\" invocation"
else
  FAIL=$((FAIL + 1)); echo "  FAIL  source lost the literal dispatcher invocation check_safety_core_parity.py scans for"
fi

echo "shim hygiene -- the three live gate shims must stay out of strict mode"
# Per the hook contract only exit code 2 blocks a tool call; any other nonzero exit is a
# NON-blocking hook error. So strict mode inside a shim does not deny anything: it makes the
# guard the shim fronts silently NOT run for that call, and adds an error to every call. The
# shims exist to reach their final `exit 0` / dispatch, so none of them takes `set -e`, `-u`
# or `pipefail`. POST_BASH_GATE_SRC / AGENT_ROUTER_PATH_SRC point at candidate copies, like
# BASH_GATE_SRC does for the gate under test.
SHIM_NAMES=(bash_gate.sh post_bash_gate.sh agent_router_path.sh)
SHIM_PATHS=("$GATE" "${POST_BASH_GATE_SRC:-$HERE/../post_bash_gate.sh}" "${AGENT_ROUTER_PATH_SRC:-$HERE/../agent_router_path.sh}")
for i in 0 1 2; do
  name="${SHIM_NAMES[$i]}"
  shim="${SHIM_PATHS[$i]}"
  if [ ! -f "$shim" ]; then
    FAIL=$((FAIL + 1)); echo "  FAIL  $name: not found at $shim"
    continue
  fi
  if grep -Ev '^[[:space:]]*#' "$shim" | grep -Eq '^[[:space:]]*set[[:space:]]+-[A-Za-z]*[eu]|set[[:space:]]+-o[[:space:]]+(errexit|nounset|pipefail)'; then
    FAIL=$((FAIL + 1)); echo "  FAIL  $name must not enable set -e / -u / pipefail"
  else
    PASS=$((PASS + 1)); echo "  PASS  $name: no set -e / -u / pipefail outside comments"
  fi
  if bash -n "$shim" 2>/dev/null; then
    PASS=$((PASS + 1)); echo "  PASS  $name: bash -n"
  else
    FAIL=$((FAIL + 1)); echo "  FAIL  $name: bash -n reports a syntax error"
  fi
  if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck -S warning "$shim" >/dev/null 2>&1; then
      PASS=$((PASS + 1)); echo "  PASS  $name: shellcheck -S warning clean"
    else
      FAIL=$((FAIL + 1)); echo "  FAIL  $name: shellcheck -S warning reports findings"
    fi
  else
    echo "  SKIP  $name: shellcheck not installed"
  fi
done

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
