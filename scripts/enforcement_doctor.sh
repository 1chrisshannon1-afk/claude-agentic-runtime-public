#!/usr/bin/env bash
# enforcement_doctor.sh — single "what's enforced right now" report for the
# Claude Code dev runtime. Read-only; never mutates state.
#
# Prints:
#   - RUNTIME_VERSION
#   - each hook wired in ~/.claude/settings.json  (event, matcher, command)
#   - the Python hook modules under ~/.claude/hooks/ (the live enforcement code)
#   - the enforcement deny-set (block_branch_ops / block_unscoped_commit / ...)
#   - a safety-core parity check (settings.json wiring vs. on-disk modules)
#   - whether CSA_ENFORCE / CSA_DISABLE_HOOKS / CSA_ALLOW_GIT_STATE_OPS are set
#   - a summary of ~/.claude/live-testing/allowlist.json
#   - browser pool home / size
#   - recent enforcement log tail (informational)
#
# The bash scripts this reporter once described are RETIRED to
# ~/.claude/scripts/legacy/. The live hooks are the Python modules under
# ~/.claude/hooks/ (run their suite: bash ~/.claude/hooks/run_tests.sh).

set -u

RUNTIME_VERSION="0.2.0"

CLAUDE_HOME="${HOME}/.claude"
SETTINGS="${CLAUDE_HOME}/settings.json"
HOOKS_DIR="${CLAUDE_HOME}/hooks"
ALLOWLIST="${CLAUDE_HOME}/live-testing/allowlist.json"
POOL_HOME="${CSA_BROWSER_POOL_HOME:-${CLAUDE_HOME}/.browser_pool}"
LOG_FILE="${CLAUDE_HOME}/.enforcement/log.jsonl"

echo "==================================================================="
echo " ExampleApp Claude Code Dev Runtime — enforcement_doctor"
echo " RUNTIME_VERSION: ${RUNTIME_VERSION}"
echo "==================================================================="

# ---- env flags -------------------------------------------------------------
echo
echo "[ environment flags ]"
_flag() {
  local name="$1" val="${2:-}"
  if [[ -n "$val" ]]; then echo "  $name = $val"; else echo "  $name = (unset)"; fi
}
_flag CSA_ENFORCE                "${CSA_ENFORCE:-}"
_flag CSA_DISABLE_HOOKS          "${CSA_DISABLE_HOOKS:-}"
_flag CSA_ALLOW_GIT_STATE_OPS    "${CSA_ALLOW_GIT_STATE_OPS:-}"
_flag "CSA_SKIP_REVIEW (inert since 08-20 -- its only consumer, task_completion_gate.py, is retired)" "${CSA_SKIP_REVIEW:-}"
_flag CSA_ANTHROPIC_CEILING      "${CSA_ANTHROPIC_CEILING:-}"
GLOBAL_ENFORCE_FILE="${CLAUDE_HOME}/.enforce"
if [[ -f "$GLOBAL_ENFORCE_FILE" ]]; then
  echo "  ~/.claude/.enforce (global marker) = present"
else
  echo "  ~/.claude/.enforce (global marker) = (absent)"
fi
# Mirrors _lib.py enforcing()'s actual precedence: CSA_DISABLE_HOOKS wins first,
# then CSA_ENFORCE=1, then the global marker file. (Per-project .claude/.csa-enforce
# markers are cwd-dependent and not reflected in this global summary.)
if [[ "${CSA_DISABLE_HOOKS:-}" = "1" ]]; then
  echo "  -> MASTER OFF: CSA_DISABLE_HOOKS=1 disables all hooks regardless of enforce state."
elif [[ "${CSA_ENFORCE:-}" = "1" || -f "$GLOBAL_ENFORCE_FILE" ]]; then
  echo "  -> ENFORCE MODE ACTIVE (global): hooks may emit real deny decisions in every project."
else
  echo "  -> DEFAULT MODE: LOG-ONLY globally (a per-project .claude/.csa-enforce marker may still enforce locally)."
fi

# ---- hooks in settings.json ------------------------------------------------
echo
echo "[ hooks wired in settings.json ]"
if [[ -f "$SETTINGS" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    SETTINGS="$SETTINGS" python3 - <<'PY' 2>/dev/null || echo "  (could not parse settings.json)"
import json, os
p = os.environ["SETTINGS"]
try:
    with open(p) as f:
        d = json.load(f)
except Exception as e:
    print("  (error reading settings.json: %s)" % e); raise SystemExit(0)
hooks = d.get("hooks", {})
if not hooks:
    print("  (no hooks configured — PreToolUse enforcement is INACTIVE)")
else:
    for event, matchers in hooks.items():
        if not isinstance(matchers, list):
            continue
        for m in matchers:
            matcher = m.get("matcher", "*")
            for h in m.get("hooks", []):
                cmd = h.get("command", "")
                print("  %-14s matcher=%-24s -> %s" % (event, matcher, cmd))
PY
  else
    echo "  (python3 unavailable; raw grep)"
    grep -A3 '"hooks"' "$SETTINGS" 2>/dev/null | sed 's/^/  /' || true
  fi
else
  echo "  (no settings.json at $SETTINGS)"
fi

# ---- Python hook modules ---------------------------------------------------
echo
echo "[ Python hook modules — ~/.claude/hooks/*.py (live enforcement code) ]"
if [[ -d "$HOOKS_DIR" ]]; then
  _desc_hook() {
    case "$1" in
      _lib.py)                      echo "shared lib: event parse, enforce resolver, git tokenizer, log/emit" ;;
      block_branch_ops.py)          echo "PreToolUse:Bash gate 1 — block git state verbs (checkout/switch/stash/reset/rebase/restore/clean/branch -d; worktree list/prune/repair and restore --staged are carve-outs)" ;;
      block_head_overwrite.py)      echo "PreToolUse:Bash gate 1b — block 'git show/cat-file <ref>:<path> > <path>' self-overwrite redirects (GH #4387 data-loss fix)" ;;
      block_unscoped_commit.py)     echo "PreToolUse:Bash gate 2 — block bulk/unscoped staging (add -A/-u/./:/ , commit -a)" ;;
      check_staged_scope.py)        echo "PreToolUse:Bash gate 3 — require a non-bulk pathspec on every writing commit; block a (path)set that sweeps out-of-scope files" ;;
      file_claims.py)               echo "PreToolUse:Bash gate 4 — path-scoped commit contest ledger + per-repo commit mutex (one commit in flight per repo)" ;;
      precommit_review_gate.py)     echo "PreToolUse:Bash gate 3b — REVIEW BEFORE THE COMMIT: deny a commit whose exact pending content has no code review on record (clear with record_review.py --pre-commit); lever CSA_NO_PRECOMMIT_REVIEW=1" ;;
      gh_issue_close_gate.py)       echo "PreToolUse:Bash gate 5 — gate GitHub issue-close on resolution evidence" ;;
      churn_tracker.py)             echo "PreToolUse:Bash gate 6 — PURE OBSERVER: logs commits-without-clean-review churn (never blocks)" ;;
      pretooluse_bash.py)           echo "PreToolUse:Bash — the single dispatcher running gates 1-6 + 3b/3c above, first-block-wins" ;;
      posttooluse_bash.py)          echo "PostToolUse:Bash — releases the file_claims claim + records commit authorship (commit_authors.py) after a commit" ;;
      commit_authors.py)            echo "per-(repo,sha) commit-authorship ledger written after each commit (its task_completion_gate consumer is retired)" ;;
      block_prod_mutations.py)      echo "guard: block prod-targeting mutations (gcloud/bq/firestore/secrets)" ;;
      agent_budget.py)              echo "PreToolUse:Task 'gate' + mcp__playwright 'browser_pool' — advisory concurrency ledger" ;;
      redact_browser_phi.py)        echo "PostToolUse:mcp__playwright — scrub JWT/Set-Cookie/session tokens from results" ;;
      task_completion_gate.py)      echo "RETIRED 2026-08-19 (unregistered from settings.json) — review moved BEFORE the commit, see precommit_review_gate.py" ;;
      model_pin_parity.py)          echo "CLI — REPORT-ONLY: runtime agent pins + Opus sanction vs knowledge/model_policy.json; never blocks (#4400)" ;;
      check_safety_core_parity.py)  echo "Stop — assert settings.json wiring matches on-disk hook modules" ;;
      record_review.py)             echo "CLI — stamp the last-reviewed marker; --pre-commit records the review that opens gate 3b" ;;
      record_plan_review.py)        echo "CLI — log-only plan-review outcome ledger (~/.claude/.review_state/plan_reviews.jsonl); not a gate" ;;
      review_risk_tier.py)          echo "CLI — advisory risk-tier classifier (trivial/moderate/high) consulted before choosing full vs. cheap review; not wired into any gate" ;;
      settings_drift_guard.py)      echo "SessionStart: self-heals settings.json model/effortLevel to their committed HEAD value and removes a client-written modelSettings block HEAD does not carry; lever CSA_NO_SETTINGS_DRIFT_GUARD=1" ;;
      pre_commit_ratchet.py)        echo "pre-commit hook — per-commit skip ratchet for the CI-parity gate" ;;
      mint_prod_session.py)         echo "CLI — mint a scoped prod live-testing session" ;;
      sync_agent_rules.py)          echo "CLI — sync AGENT_RULES into the runtime contract" ;;
      no_artifact.py)               echo "RETIRED 2026-09-22 (deleted, unregistered from settings.json) — Anthropic Artifacts are permitted again by operator directive" ;;
      *)                            echo "" ;;
    esac
  }
  for f in "$HOOKS_DIR"/*.py; do
    [[ -e "$f" ]] || continue
    b="$(basename "$f")"
    printf '  %-28s %s\n' "$b" "$(_desc_hook "$b")"
  done
  echo
  echo "  suite: bash ~/.claude/hooks/run_tests.sh   (hooks/tests, tools/gtm/tests, hooks/tests/test_*.sh and the node workflow test; stops at the first failure; per-module coverage when pytest-cov is installed)"
else
  echo "  (no hooks dir at $HOOKS_DIR — Python hook system NOT installed)"
fi

# ---- enforcement deny-set --------------------------------------------------
echo
echo "[ enforcement deny-set (block_branch_ops.py + block_unscoped_commit.py + check_staged_scope.py + file_claims.py + pretooluse_bash.py gate 3c) ]"
cat <<'EOF'
  state verbs (any occurrence): checkout, switch, stash, reset, rebase, worktree
  branch                      : with -d / -D / --delete only (listing allowed)
  add                         : -A, --all, -u, --update, '.', ':/' (path-scoped adds ALLOWED)
  commit                      : -a, -am, --all
  commit pathspec (2026-08-17): MANDATORY on every writing commit segment — a commit with no
                                 `-- <pathspec>` is blocked (missing-pathspec); a whole-tree
                                 pathspec ('.', ':/', the repo root) is ALSO blocked
                                 (bulk-pathspec). Exemptions: real in-progress merge/cherry-pick/
                                 revert/rebase, or --allow-empty. Rollback: CSA_NO_REQUIRE_PATHSPEC=1
  staged scope                : the named pathspec (or, when exempted, the staged index) blocked
                                 if it sweeps out-of-scope / too many files / too many top dirs
  dirty-precommit-config      : gate 3c (#4670 item 3) — a PATHSPEC commit is denied fast when
  (2026-08-30)                  this repo's `.pre-commit-config.yaml` has uncommitted changes
                                 (staged or not); a pathspec commit's temp index would carry a
                                 stale copy and pre-commit would fail on it regardless. EXEMPT when
                                 the commit's own pathspec already names the config. NOT retry-and-
                                 wait like the commit mutex below — recovery is review -> record ->
                                 config-only commit -> retry (see git-ops.md). Rollback:
                                 CSA_NO_DIRTY_CONFIG_GATE=1
  commit mutex (2026-08-17)   : only ONE commit in flight per repo at a time — a second agent's
                                 commit in the SAME repo contests even with disjoint real paths
                                 (file_claims.py's synthetic per-repo token). Rollback: CSA_NO_COMMIT_MUTEX=1
  inline bypass tripwire      : any command STRING containing 'CSA_ALLOW_GIT_STATE_OPS' -> DENY
  escape hatch                : CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN env only (git-state
                                 gates 1/1b/2 only — gates 3/3c/4's blocks have NO escape hatch, each
                                 has its own per-gate rollback lever instead)
  compound/eval segments      : a state-verb in ANY && ; | segment blocks the line; EVERY writing
                                 commit segment of a compound command is checked (gate 3)
  parse ambiguity             : fail CLOSED for git tokens under enforce; log-only otherwise
EOF

# ---- safety-core parity ----------------------------------------------------
echo
echo "[ safety-core parity (settings.json wiring vs. on-disk hook modules) ]"
if [[ -f "$HOOKS_DIR/check_safety_core_parity.py" ]] && command -v python3 >/dev/null 2>&1; then
  # Run the parity checker in enforce mode against a Stop event. It emits a
  # JSON block object on stdout only when there is drift; empty output == OK.
  _parity="$(printf '{"cwd":"%s"}' "$PWD" \
    | CSA_ENFORCE=1 python3 "$HOOKS_DIR/check_safety_core_parity.py" 2>/dev/null)"
  if [[ -z "$_parity" ]]; then
    echo "  OK — every wired hook command resolves to an existing module; no drift."
  else
    echo "  DRIFT DETECTED:"
    echo "    $_parity"
  fi
else
  echo "  (parity checker unavailable)"
fi

# ---- live-testing allowlist summary ---------------------------------------
echo
echo "[ live-testing allowlist ]"
if [[ -f "$ALLOWLIST" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    ALLOWLIST="$ALLOWLIST" python3 - <<'PY' 2>/dev/null || echo "  (could not parse allowlist.json)"
import json, os
p = os.environ["ALLOWLIST"]
try:
    with open(p) as f:
        d = json.load(f)
except Exception as e:
    print("  (error reading allowlist.json: %s)" % e); raise SystemExit(0)
def count(k):
    v = d.get(k)
    return len(v) if isinstance(v, (list, dict)) else ("set" if v else 0)
print("  allowed_origins        : %s entr(y/ies)" % count("allowed_origins"))
print("  allowed_company_tenants: %s entr(y/ies)" % count("allowed_company_tenants"))
print("  test_recipients        : %s entr(y/ies)" % count("test_recipients"))
print("  denied_action_patterns : %s entr(y/ies)" % count("denied_action_patterns"))
PY
  else
    echo "  (python3 unavailable) file present: $ALLOWLIST"
  fi
else
  echo "  (no allowlist.json at $ALLOWLIST — prod live-testing NOT configured)"
fi

# ---- browser pool ----------------------------------------------------------
echo
echo "[ browser pool ]"
echo "  pool_home : $POOL_HOME"
if [[ -d "$POOL_HOME" ]]; then
  _size="$(find "$POOL_HOME" -maxdepth 1 -name 'slot-*' 2>/dev/null | wc -l | tr -d ' ')"
  echo "  pool_size : ${_size:-0} slot marker(s)"
else
  echo "  pool_size : (pool home absent)"
fi

# ---- enforcement log tail --------------------------------------------------
echo
echo "[ recent enforcement decisions ]"
if [[ -f "$LOG_FILE" ]]; then
  _n="$(wc -l < "$LOG_FILE" 2>/dev/null | tr -d ' ')"
  echo "  log: $LOG_FILE (${_n:-0} line(s)) — last up to 5:"
  tail -n 5 "$LOG_FILE" 2>/dev/null | sed 's/^/    /' || true
else
  echo "  (no enforcement log yet at $LOG_FILE)"
fi

echo
echo "RUNTIME_VERSION=${RUNTIME_VERSION}"
exit 0
