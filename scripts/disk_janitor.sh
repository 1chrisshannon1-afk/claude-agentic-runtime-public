#!/usr/bin/env bash
# disk_janitor.sh — the permanent reaper for the 2026-09-19 disk-full incident.
#
# WHY THIS EXISTS
# ----------------
# Disk hit 100% and blocked every session on the machine. Measured root causes,
# all still true after the fix (nothing upstream stops them from recurring):
#   * /private/tmp/claude-501/ grew to 332G across 387 session scratchpad dirs.
#     Two dead sessions alone held 151G EACH — full `cp -R` repo copies, each
#     containing a nested copy of every worktree plus repo_tooling/demo_video/out.
#   * <repo>/.claude/worktrees/ grew to 102G across 234 worktrees (CSA) with ZERO
#     reaping mechanism anywhere on the machine — no cron, no launchd job, no
#     script ever called `git worktree prune` or `remove`. 31 were fully clean
#     and reapable on sight; 203 held uncommitted changes; 1 held an unmerged
#     commit. The 2026-09-16 CLAUDE.md ruling that retired worktrees as the
#     default is PROSE ONLY — it does not stop a tool from opening one, and does
#     not tear one down once opened. 30 new worktrees were created AFTER that
#     ruling: 20 `wf_*` (the Workflow tool opens one per leg and never reads
#     CLAUDE.md) and 10 `agent-*` (dispatches passing isolation:"worktree").
#   * repo_tooling/demo_video/out held 35G of gitignored, zero-tracked-file
#     scratch render output.
#
# This script is the durable backstop for all of it: idempotent, safe, DRY-RUN
# BY DEFAULT (pass --apply to actually delete/reap anything), and it logs every
# action plus bytes reclaimed to ~/.claude/.disk_janitor.log so a repeat run's
# history is auditable.
#
# SAFETY MODEL
# ------------
# Every stage is independently skippable (--skip-<stage>) and every deletion
# path goes through git's own `worktree remove` for worktrees (never `rm -rf`
# on a worktree directory — that leaves the .git/worktrees/<name> administrative
# record behind, corrupting `git worktree list` for the real repo) or a plain
# `rm -rf` scoped to exactly one scratchpad/cache leaf under a path this script
# itself just proved is dead/disposable. Nothing here ever touches a live
# session, a dirty worktree, or content this script cannot positively classify
# as disposable — when in doubt, the default is to SKIP and REPORT, not delete.
#
# What stage (b) sweeps is decided by the repo registry (knowledge/repo_registry.json),
# not by this file: `repo_manifest.py register`, run for any reason, adds that repo's
# `.claude/worktrees/` to the reaper's next --apply run (the per-worktree guards below
# still apply to everything it finds). A registry change is a change to this script's scope.
#
# Usage:
#   disk_janitor.sh                 # dry run, all stages, default thresholds
#   disk_janitor.sh --apply         # actually reclaim
#   disk_janitor.sh --apply --skip-docker --skip-transcripts
#   disk_janitor.sh --session-age-days=3 --worktree-age-days=3 --transcript-age-days=30
#
# See `disk_janitor.sh --help` for the full flag list.

# Deliberately NOT `set -e`: this script is a sweep of independent stages and paths. A
# stage must still run, and a failure must be counted and reported (ERRORS, the summary
# table, the exit status), when an earlier probe fails: `git ... ; rc=$?`, `stat ... ||
# echo 0` and the fail-closed liveness checks all read a nonzero status as DATA. `-u`
# and `pipefail` stay on.
set -uo pipefail

# ---------------------------------------------------------------------------
# Config / defaults
# ---------------------------------------------------------------------------

APPLY=0
SESSION_AGE_DAYS=3
WORKTREE_AGE_DAYS=3
TRANSCRIPT_AGE_DAYS=30
PRECOMMIT_AGE_DAYS=30

SKIP_SESSIONS=0
SKIP_WORKTREES=0
SKIP_DOCKER=0
SKIP_CACHES=0
SKIP_TRANSCRIPTS=0

# $HOME when it is set AND non-empty; otherwise the account database's home (`~` with
# HOME unset). A set-but-empty HOME must not reach `cd ~`/`cd ""`: `cd ""` is a no-op,
# which would make HOME_DIR the current directory and put the log, the registry path and
# the pre-commit cache path under whatever directory the janitor was started in. The
# result is validated right after argument parsing (exit 2 when it is not a real directory).
HOME_DIR="${HOME:-}"
[ -n "$HOME_DIR" ] || HOME_DIR="$(unset HOME; cd ~ 2>/dev/null && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME_DIR/.claude}"
LOG_FILE="$CLAUDE_DIR/.disk_janitor.log"
SCRATCH_ROOT="/private/tmp/claude-501"

# Repos to sweep for worktrees (stage b) are read from the runtime's repo registry,
# `knowledge/repo_registry.json` (`repos.<slug>.root`, stored `~`-relative), and never
# from a path baked into this script: there is NO default product path. A missing,
# unreadable or empty registry means "no product roots", and stage (b) says so and
# sweeps nothing. DISK_JANITOR_REPOS (space-separated paths; a leading `~` is expanded)
# overrides the registry for a machine with a different repo set, and
# DISK_JANITOR_REGISTRY points at a different registry file. Resolved by
# resolve_repos, called from stage_worktrees (so --help and --skip-worktrees never
# read the registry).
REGISTRY_FILE="${DISK_JANITOR_REGISTRY:-$CLAUDE_DIR/knowledge/repo_registry.json}"
REPOS=()
REPOS_SOURCE=""

# Disposable-only ignored-content patterns for worktree stage (b)'s 4th guard.
# Anything ignored that does NOT match one of these is treated as "do not
# reap" and reported, never deleted.
DISPOSABLE_IGNORED_PATTERNS=(
  "__pycache__"
  ".pytest_cache"
  ".ruff_cache"
  ".mypy_cache"
  "node_modules"
  ".venv"
  ".DS_Store"
  "*.tsbuildinfo"
)

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

print_help() {
  cat <<'EOF'
disk_janitor.sh — permanent disk-pressure reaper (see header comment for full rationale)

Usage: disk_janitor.sh [--apply] [options]

  --apply                  Actually reclaim (default: dry run, report only)
  --session-age-days=N     Dead-scratchpad mtime threshold (default: 3)
  --worktree-age-days=N    Clean-worktree mtime threshold (default: 3)
  --transcript-age-days=N  Subagent transcript age threshold (default: 30)
  --precommit-age-days=N   Pre-commit cache-entry age threshold (default: 30)
  --skip-sessions          Skip stage (a): dead-session scratchpads
  --skip-worktrees         Skip stage (b): clean worktrees
  --skip-docker            Skip stage (c): docker image/builder prune
  --skip-caches            Skip stage (d): pre-commit/npm cache trim
  --skip-transcripts       Skip stage (e): old subagent transcripts
  -h, --help                Show this help

Stage (b) repo roots come from knowledge/repo_registry.json (repos.<slug>.root);
a missing or empty registry means no roots and the stage sweeps nothing.
Environment:
  DISK_JANITOR_REPOS       Space-separated repo roots for stage (b); overrides the registry
  DISK_JANITOR_REGISTRY    Registry file to read (default: $CLAUDE_DIR/knowledge/repo_registry.json)
EOF
}

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --session-age-days=*) SESSION_AGE_DAYS="${arg#*=}" ;;
    --worktree-age-days=*) WORKTREE_AGE_DAYS="${arg#*=}" ;;
    --transcript-age-days=*) TRANSCRIPT_AGE_DAYS="${arg#*=}" ;;
    --precommit-age-days=*) PRECOMMIT_AGE_DAYS="${arg#*=}" ;;
    --skip-sessions) SKIP_SESSIONS=1 ;;
    --skip-worktrees) SKIP_WORKTREES=1 ;;
    --skip-docker) SKIP_DOCKER=1 ;;
    --skip-caches) SKIP_CACHES=1 ;;
    --skip-transcripts) SKIP_TRANSCRIPTS=1 ;;
    -h|--help) print_help; exit 0 ;;
    *)
      echo "disk_janitor.sh: unknown argument: $arg" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

# No usable home directory means every path derived from it (CLAUDE_DIR, the log, the
# registry, the pre-commit cache) would be wrong, and an --apply run must not guess.
# Checked after argument parsing so --help still works, and before anything is written.
if [ -z "$HOME_DIR" ] || [ ! -d "$HOME_DIR" ] || [ "$HOME_DIR" = "/" ]; then
  echo "disk_janitor.sh: cannot determine a usable home directory (HOME='${HOME:-}', resolved '$HOME_DIR') -- nothing was done" >&2
  exit 2
fi

MODE_LABEL="DRY-RUN"
if [ "$APPLY" = "1" ]; then
  MODE_LABEL="APPLY"
fi

# ---------------------------------------------------------------------------
# Logging + summary table plumbing
# ---------------------------------------------------------------------------

RUN_STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Table rows accumulated as "stage|candidates|bytes_reclaimable|bytes_reclaimed"
declare -a SUMMARY_ROWS=()

log_line() {
  # jsonl, one line per event, never fails the run on a log-write error
  local stage="$1" event="$2" detail="$3"
  printf '{"ts":"%s","mode":"%s","stage":"%s","event":"%s","detail":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE_LABEL" "$stage" "$event" "$detail" \
    >> "$LOG_FILE" 2>/dev/null || true
}

json_str() {
  # Minimal JSON-string escaper for log details (paths, messages)
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '"%s"' "$s"
}

du_bytes() {
  # Portable-enough byte count for a path; 0 on any failure. Never hangs the
  # whole run — caps at a generous timeout since some of these trees are huge.
  local path="$1"
  if [ ! -e "$path" ]; then
    echo 0
    return 0
  fi
  local out
  out="$(_run_timeout 90 du -sk "$path" 2>/dev/null | awk '{print $1}')"
  if [ -z "$out" ]; then
    echo 0
  else
    echo $((out * 1024))
  fi
}

human_bytes() {
  local bytes="$1"
  awk -v b="$bytes" 'BEGIN {
    split("B KB MB GB TB", units, " ");
    u = 1;
    while (b >= 1024 && u < 5) { b /= 1024; u++ }
    printf "%.1f%s", b, units[u]
  }'
}

add_summary_row() {
  SUMMARY_ROWS+=("$1|$2|$3|$4")
}

print_summary() {
  echo ""
  echo "==================== disk_janitor.sh summary ($MODE_LABEL) ===================="
  printf "%-28s %12s %20s %20s\n" "STAGE" "CANDIDATES" "BYTES_RECLAIMABLE" "BYTES_RECLAIMED"
  local total_reclaimable=0 total_reclaimed=0
  for row in "${SUMMARY_ROWS[@]}"; do
    IFS='|' read -r stage cand reclaimable reclaimed <<< "$row"
    printf "%-28s %12s %20s %20s\n" "$stage" "$cand" "$(human_bytes "$reclaimable")" "$(human_bytes "$reclaimed")"
    total_reclaimable=$((total_reclaimable + reclaimable))
    total_reclaimed=$((total_reclaimed + reclaimed))
  done
  printf "%-28s %12s %20s %20s\n" "TOTAL" "-" "$(human_bytes "$total_reclaimable")" "$(human_bytes "$total_reclaimed")"
  echo "================================================================================="
  if [ "$APPLY" = "0" ]; then
    echo "(dry run — nothing was deleted. Re-run with --apply to actually reclaim.)"
  fi
  echo "Log: $LOG_FILE"
}

ERRORS=0

# ---------------------------------------------------------------------------
# Portable timeout wrapper.
#
# WHY: this machine has neither GNU coreutils' `timeout` nor `gtimeout` on
# PATH (verified 2026-09-19 — `command not found: timeout` under both bash
# and zsh, and no binary at /usr/bin, /usr/local/bin, or /opt/homebrew/bin).
# A silent `command not found` inside a `local out; out="$(timeout ...)"`
# assignment does NOT fail loudly — the assignment just captures empty
# output, which is exactly the bug this comment exists to prevent from
# recurring: it made every du/lsof call silently return nothing, so the
# first version of this script reported 0 bytes reclaimable for everything.
# `_run_timeout` uses only bash/zsh builtins (background job + sleep-then-
# kill watcher), so it never depends on an external `timeout` binary being
# present. `-9` on the follow-up KILL guards a target that ignores TERM.
# ---------------------------------------------------------------------------

_run_timeout() {
  local secs="$1"
  shift
  "$@" &
  local pid=$!
  # The watcher subshell's own stdout/stderr MUST be redirected away from
  # whatever fds it inherits (>/dev/null 2>&1) -- NOT optional. Reproduced
  # 2026-09-19: without this, when `_run_timeout ... | awk ...` is used
  # (every du_bytes call), the watcher -- forked from the SAME pipeline
  # subshell as the real command -- inherits the pipe's write end too. Even
  # after the real command finishes normally and closes its own copy, the
  # STILL-SLEEPING watcher keeps the pipe's write end open until it itself
  # exits (up to secs+2 later), so the reader (awk) blocks waiting for EOF
  # that never comes until the watcher dies. Net effect: every du_bytes call
  # silently stalled for the FULL timeout duration even on instant `du`
  # completions, turning a should-be-fast sessions/worktrees sweep into an
  # apparent hang. Confirmed via isolated repro both ways (hangs without
  # this redirect, completes immediately with it).
  (
    sleep "$secs"
    kill -TERM "$pid" 2>/dev/null
    sleep 2
    kill -KILL "$pid" 2>/dev/null
  ) >/dev/null 2>&1 &
  local watcher=$!
  local rc=0
  wait "$pid" 2>/dev/null
  rc=$?
  kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $rc
}

# ---------------------------------------------------------------------------
# Liveness check — used by stage (a) and reused as a guard by stage (b).
#
# A path is LIVE if EITHER of two independent signals says so (OR, not AND —
# deliberately biased toward false "live", never toward false "dead", since
# treating a live session as dead is the failure mode that must never happen):
#   1. Some process's CWD resolves inside it (lsof -d cwd) — the signal the
#      operator's own brief specified.
#   2. Some process's COMMAND LINE references a path inside it (ps argv grep)
#      — measured live 2026-09-19: dispatched sub-processes (e.g. a Playwright
#      driver script under a session's scratchpad/) commonly do NOT chdir into
#      the scratchpad; they reference it only via argv. Relying on cwd alone
#      would misclassify those as dead.
# ---------------------------------------------------------------------------

# Both process-inventory snapshots are captured ONCE per run (lazily, on
# first use — a run that skips both stage (a) and (b) never pays this cost
# at all) rather than once PER CANDIDATE. This is both a correctness and a
# performance fix: `lsof -d cwd -n` enumerates every open file on the whole
# machine, and re-running it (plus a full `ps -axo command`) for each of
# ~400+ candidate directories in one run is needlessly expensive and, per
# stage_worktrees's own comment on the analogous `git worktree list` bug,
# rapid repeated subprocess forking on this machine has been observed to
# produce flaky results — one static snapshot per run avoids the pattern
# entirely rather than trying to diagnose it further.
_LSOF_CWD_SNAPSHOT=""
_LSOF_CWD_CAPTURED=0
_PS_CMD_SNAPSHOT=""
_PS_CMD_CAPTURED=0

_capture_liveness_snapshots() {
  if [ "$_LSOF_CWD_CAPTURED" = "0" ]; then
    if command -v lsof >/dev/null 2>&1; then
      _LSOF_CWD_SNAPSHOT="$(_run_timeout 30 lsof -d cwd -n 2>/dev/null)"
    fi
    _LSOF_CWD_CAPTURED=1
  fi
  if [ "$_PS_CMD_CAPTURED" = "0" ]; then
    _PS_CMD_SNAPSHOT="$(ps -axo command 2>/dev/null)"
    _PS_CMD_CAPTURED=1
  fi
}

is_path_live() {
  local path="$1"
  _capture_liveness_snapshots
  # Signal 1: any process whose cwd is this path or below it.
  if [ -n "$_LSOF_CWD_SNAPSHOT" ]; then
    if printf '%s\n' "$_LSOF_CWD_SNAPSHOT" | awk -v p="$path" '$9 ~ ("^" p) {found=1} END {exit !found}'; then
      return 0
    fi
  fi
  # Signal 2: any process whose command line mentions this path.
  if printf '%s\n' "$_PS_CMD_SNAPSHOT" | grep -F -q -- "$path"; then
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Portable file mtime (epoch seconds; prints 0 when it cannot be read).
#
# BSD/macOS `stat -f %m` and GNU `stat -c %Y` are mutually unintelligible (on GNU,
# `-f` means "filesystem status" and `-f %m` prints a block of unrelated text), so
# the flavor is probed, trying GNU first: on BSD `-c` is an illegal option and fails
# cleanly. A path that cannot be read yields 0, which every caller already treats as
# "stat failed -> skip", never as "very old".
#
# The probe runs ONCE: main() calls _detect_stat_flavor at the top level before any
# stage, and _file_mtime only reads _STAT_FLAVOR. Detecting lazily inside _file_mtime
# cannot cache anything, because every caller runs it inside `$( )` and a subshell's
# assignment is lost (measured: about 3x the stat forks of the code it replaced). If the
# detector was never run in this shell, _file_mtime still answers correctly by probing
# for that call alone.
# ---------------------------------------------------------------------------

_STAT_FLAVOR=""

# Prints gnu | bsd | none.
_probe_stat_flavor() {
  if stat -c %Y / >/dev/null 2>&1; then
    echo gnu
  elif stat -f %m / >/dev/null 2>&1; then
    echo bsd
  else
    echo none
  fi
}

# Sets _STAT_FLAVOR in the CURRENT shell. Call it from the top level, never inside `$( )`.
_detect_stat_flavor() {
  _STAT_FLAVOR="$(_probe_stat_flavor)"
}

_file_mtime() {
  local path="$1" out flavor="$_STAT_FLAVOR"
  if [ -z "$flavor" ]; then
    flavor="$(_probe_stat_flavor)"
  fi
  case "$flavor" in
    gnu) out="$(stat -c %Y "$path" 2>/dev/null)" ;;
    bsd) out="$(stat -f %m "$path" 2>/dev/null)" ;;
    *) out="" ;;
  esac
  case "$out" in
    '' | *[!0-9]*) echo 0 ;;
    *) echo "$out" ;;
  esac
}

# ---------------------------------------------------------------------------
# Repo roots for stage (b): registry-driven, no default product path.
# ---------------------------------------------------------------------------

# Expand a leading `~` / `~/` against $HOME_DIR. The registry stores roots `~`-relative,
# and bash never expands a tilde that arrives inside a quotation or a variable, so it has
# to be done here explicitly; used verbatim, a `~/x` root would match nothing.
# `~user/` forms are left as given (they are not absolute, so _add_repo drops them).
expand_tilde() {
  case "$1" in
    \~) printf '%s\n' "$HOME_DIR" ;;
    \~/*) printf '%s\n' "$HOME_DIR/${1#\~/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

# Append one root to REPOS: absolute only, no duplicates (two registry slugs may share
# one checkout, and a double sweep would double-count every candidate).
_add_repo() {
  local root="$1" r
  case "$root" in
    /*) ;;
    *) return 0 ;;
  esac
  if [ "${#REPOS[@]}" -gt 0 ]; then
    for r in "${REPOS[@]}"; do
      [ "$r" = "$root" ] && return 0
    done
  fi
  REPOS+=("$root")
}

# Print one absolute root per line from a repo_registry.json. Exit 2 when the file is
# unreadable or is not the expected {"repos": {slug: {"root": ...}}} shape. A root
# stored as `~` or `~/...` expands against the home directory passed as $2.
registry_roots() {
  python3 -I - "$1" "$2" <<'PYEOF'
import json
import os
import sys

path, home = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as fh:
        repos = json.load(fh).get("repos")
except (OSError, ValueError, AttributeError):
    sys.exit(2)
if not isinstance(repos, dict):
    sys.exit(2)
for entry in repos.values():
    root = entry.get("root") if isinstance(entry, dict) else None
    # A newline would split one root into two lines, and a NUL (JSON \\u0000) is silently
    # dropped by the shell's command substitution, truncating the path: reject both.
    if not isinstance(root, str) or not root or "\n" in root or "\x00" in root:
        continue
    if root == "~" or root.startswith("~/"):
        root = home + root[1:]
    if os.path.isabs(root):
        print(os.path.normpath(root))
PYEOF
}

# Fill REPOS (and REPOS_SOURCE) for stage (b). Always returns 0; an unusable source
# leaves REPOS empty after saying why, and the stage then sweeps nothing.
resolve_repos() {
  REPOS=()
  local line out rc noglob=0
  if [ -n "${DISK_JANITOR_REPOS:-}" ]; then
    REPOS_SOURCE="DISK_JANITOR_REPOS"
    # Word-split the space-separated paths with pathname expansion OFF: an entry such as
    # `/work/*` must stay the literal (and then harmlessly skipped) path it was written
    # as, never fan out into every directory under it.
    case "$-" in *f*) noglob=1 ;; esac
    set -f
    # shellcheck disable=SC2086  # deliberate word split: space-separated paths
    for line in $DISK_JANITOR_REPOS; do
      _add_repo "$(expand_tilde "$line")"
    done
    [ "$noglob" = "1" ] || set +f
    return 0
  fi
  REPOS_SOURCE="$REGISTRY_FILE"
  if [ ! -f "$REGISTRY_FILE" ]; then
    echo "[worktrees] no repo registry at $REGISTRY_FILE -- no product roots to sweep (set DISK_JANITOR_REPOS to override)"
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[worktrees] python3 not found, cannot read $REGISTRY_FILE -- no product roots to sweep"
    return 0
  fi
  out="$(registry_roots "$REGISTRY_FILE" "$HOME_DIR")"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "[worktrees] cannot read repo roots from $REGISTRY_FILE (rc=$rc) -- no product roots to sweep"
    return 0
  fi
  while IFS= read -r line; do
    [ -n "$line" ] && _add_repo "$line"
  done <<< "$out"
  return 0
}

# ===========================================================================
# Stage (a): dead-session scratchpads under /private/tmp/claude-501/*/*/
# ===========================================================================

stage_sessions() {
  local stage="sessions"
  if [ "$SKIP_SESSIONS" = "1" ]; then
    echo "[$stage] skipped (--skip-sessions)"
    add_summary_row "$stage" 0 0 0
    return 0
  fi
  echo "[$stage] scanning $SCRATCH_ROOT (age >= ${SESSION_AGE_DAYS}d, no live holder)..."

  if [ ! -d "$SCRATCH_ROOT" ]; then
    echo "[$stage] $SCRATCH_ROOT does not exist — nothing to do"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  local candidates=0 reclaimable=0 reclaimed=0
  local now_epoch
  now_epoch="$(date +%s)"
  local threshold_secs=$((SESSION_AGE_DAYS * 86400))

  # Session dirs are two levels deep: <scratch_root>/<project-slug>/<uuid>/
  local project_dir session_dir mtime_epoch age_secs sz
  for project_dir in "$SCRATCH_ROOT"/*/; do
    [ -d "$project_dir" ] || continue
    for session_dir in "$project_dir"*/; do
      [ -d "$session_dir" ] || continue
      session_dir="${session_dir%/}"

      mtime_epoch="$(_file_mtime "$session_dir")"
      if [ "$mtime_epoch" = "0" ]; then
        log_line "$stage" "stat-failed" "$(json_str "$session_dir")"
        continue
      fi
      age_secs=$((now_epoch - mtime_epoch))
      if [ "$age_secs" -lt "$threshold_secs" ]; then
        continue  # too young, never touch regardless of liveness
      fi

      if is_path_live "$session_dir"; then
        log_line "$stage" "skip-live" "$(json_str "$session_dir")"
        continue
      fi

      sz="$(du_bytes "$session_dir")"
      candidates=$((candidates + 1))
      reclaimable=$((reclaimable + sz))
      echo "  DEAD $(human_bytes "$sz")  $session_dir"
      log_line "$stage" "candidate" "$(json_str "$session_dir")"

      if [ "$APPLY" = "1" ]; then
        if rm -rf -- "$session_dir" 2>/dev/null; then
          reclaimed=$((reclaimed + sz))
          log_line "$stage" "reaped" "$(json_str "$session_dir")"
        else
          echo "  ERROR: failed to remove $session_dir" >&2
          log_line "$stage" "reap-failed" "$(json_str "$session_dir")"
          ERRORS=$((ERRORS + 1))
        fi
      fi
    done
  done

  echo "[$stage] candidates=$candidates reclaimable=$(human_bytes "$reclaimable") reclaimed=$(human_bytes "$reclaimed")"
  add_summary_row "$stage" "$candidates" "$reclaimable" "$reclaimed"
}

# ===========================================================================
# Stage (b): clean worktrees under <repo>/.claude/worktrees/*
# ===========================================================================

# Returns 0 (true) iff every ignored path reported for this worktree matches
# one of the DISPOSABLE_IGNORED_PATTERNS leaf-name globs. Prints the offending
# paths to stderr-ish (stdout, prefixed) when it returns false, for the report.
worktree_ignored_content_is_disposable() {
  local wt="$1"
  local ignored_output ignored_rc raw
  # REVIEW B2 (2026-09-20): capture git's own exit status BEFORE the pipe --
  # a pipeline's status is awk's, so a git failure (rc=128, empty output) was
  # read as "no ignored content" => disposable => reapable. Fail CLOSED: an
  # unreadable worktree is never provably free of valuable ignored content.
  raw="$(git -C "$wt" status --porcelain --ignored 2>/dev/null)"
  ignored_rc=$?
  if [ "$ignored_rc" -ne 0 ]; then
    echo "  (git status --ignored failed rc=$ignored_rc -- treating as NON-disposable)"
    return 1
  fi
  ignored_output="$(printf '%s\n' "$raw" | awk '$1=="!!" {print substr($0,4)}')"
  if [ -z "$ignored_output" ]; then
    return 0  # no ignored content at all -- trivially fine
  fi
  local line leaf matched any_non_disposable=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    # Ignored dirs are reported with a trailing slash by git; strip it, then
    # take the final path component to match against our leaf-name globs.
    line="${line%/}"
    leaf="${line##*/}"
    matched=0
    for pat in "${DISPOSABLE_IGNORED_PATTERNS[@]}"; do
      # shellcheck disable=SC2053
      if [[ "$leaf" == $pat ]]; then
        matched=1
        break
      fi
      # Also match a *path component* equal to the pattern (e.g.
      # ".../__pycache__/foo.pyc" should count as disposable via its parent).
      case "/$line/" in
        */"$pat"/*) matched=1 ;;
      esac
      [ "$matched" = "1" ] && break
    done
    if [ "$matched" = "0" ]; then
      any_non_disposable=1
      echo "    NON-DISPOSABLE ignored content: $line"
    fi
  done <<< "$ignored_output"
  [ "$any_non_disposable" = "0" ]
}

stage_worktrees() {
  local stage="worktrees"
  if [ "$SKIP_WORKTREES" = "1" ]; then
    echo "[$stage] skipped (--skip-worktrees)"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  local candidates=0 reclaimable=0 reclaimed=0
  local now_epoch
  now_epoch="$(date +%s)"
  local threshold_secs=$((WORKTREE_AGE_DAYS * 86400))

  resolve_repos
  if [ "${#REPOS[@]}" -eq 0 ]; then
    echo "[$stage] no repo roots (source: $REPOS_SOURCE) -- nothing to sweep"
    log_line "$stage" "no-repo-roots" "$(json_str "$REPOS_SOURCE")"
    add_summary_row "$stage" 0 0 0
    return 0
  fi
  echo "[$stage] ${#REPOS[@]} repo root(s) from $REPOS_SOURCE"

  local repo
  for repo in "${REPOS[@]}"; do
    if [ ! -d "$repo/.git" ] && [ ! -f "$repo/.git" ]; then
      echo "[$stage] $repo is not a git repo (or missing) — skipping"
      continue
    fi
    local wt_root="$repo/.claude/worktrees"
    if [ ! -d "$wt_root" ]; then
      echo "[$stage] $repo: no $wt_root — nothing to do"
      continue
    fi

    echo "[$stage] scanning $wt_root (age >= ${WORKTREE_AGE_DAYS}d, all 4 guards must hold)..."

    # Comparison base for the "no unmerged commits" guard. This repo's own
    # `.claude/settings.json` sets `worktree.baseRef: "head"` deliberately
    # (CLAUDE.md §2: "the documented 'fresh' default branches from
    # origin/<default>, missing the session's own commits") — every worktree
    # here branches from the MAIN TREE'S OWN CURRENT BRANCH at creation time,
    # not from the remote's default branch. Using origin/HEAD (e.g. `staging`)
    # as the comparison base is WRONG and was measured to produce false
    # "thousands of commits ahead" positives 2026-09-19 (a clean worktree
    # branched from local `8.13.26`, itself ~5000 commits ahead of
    # `origin/staging`, read as unmerged and was skipped outright). The main
    # tree's OWN current branch is the correct, and only correct, base.
    local base_branch
    base_branch="$(git -C "$repo" branch --show-current 2>/dev/null)"
    if [ -z "$base_branch" ]; then
      # Detached HEAD in the main tree itself -- fall back to its own rev,
      # never a remote branch (see rationale above).
      base_branch="$(git -C "$repo" rev-parse HEAD 2>/dev/null)"
    fi

    # Registered-worktree set, computed ONCE per repo (not once per candidate
    # directory). Two independent reasons this matters, both measured
    # 2026-09-19: (1) correctness -- `.claude/worktrees/` on this machine
    # holds real stray, non-worktree content (a plain file, and at least one
    # orphaned directory `git worktree list` no longer knows about at all --
    # `.git/worktrees/` had 232 administrative entries against 235
    # directories on disk), which Guard 0 exists specifically to catch and
    # skip; (2) performance/reliability -- re-invoking
    # `git worktree list --porcelain` inside the per-worktree loop (a full
    # git subprocess fork per candidate, ~230+ times for this repo) was
    # observed to intermittently return a truthy grep failure for EVERY
    # candidate in one run and succeed on a re-run with identical inputs --
    # never diagnosed further since computing the list once removes the
    # rapid-repeated-subprocess pattern entirely, which is the right fix
    # regardless of root cause (a script should not fork 230 subprocesses to
    # answer a question that has one static answer per repo).
    local registered_worktrees
    registered_worktrees="$(git -C "$repo" worktree list --porcelain 2>/dev/null | awk '$1=="worktree" {print $2}')"

    local wt
    for wt in "$wt_root"/*/; do
      [ -d "$wt" ] || continue
      wt="${wt%/}"
      local wt_name
      wt_name="$(basename "$wt")"

      # Guard 0: must actually be a registered git worktree of this repo —
      # never touch a directory `git worktree remove` wouldn't recognize.
      if ! printf '%s\n' "$registered_worktrees" | grep -qxF "$wt"; then
        log_line "$stage" "skip-not-a-worktree" "$(json_str "$wt")"
        continue
      fi

      # Guard 1: porcelain must be empty (no modified/untracked/deleted).
      # REVIEW B2 (2026-09-20): the exit STATUS is load-bearing, not just the
      # output. A corrupted checkout (broken .git gitdir pointer, the exact
      # shape the 2026-09-15 incident produced) exits 128 with EMPTY stdout --
      # indistinguishable from "clean" if status is discarded, so a worktree
      # holding real uncommitted work read as reapable. A git failure here
      # means we CANNOT KNOW whether work is present, which is never a licence
      # to delete: skip and report.
      local porcelain porcelain_rc
      porcelain="$(git -C "$wt" status --porcelain 2>/dev/null)"
      porcelain_rc=$?
      if [ "$porcelain_rc" -ne 0 ]; then
        log_line "$stage" "skip-git-error" "$(json_str "$wt status rc=$porcelain_rc")"
        continue
      fi
      if [ -n "$porcelain" ]; then
        log_line "$stage" "skip-dirty" "$(json_str "$wt")"
        continue
      fi

      # Guard 2: no unmerged commits relative to the main tree's own branch
      # (the worktree's actual creation base — see rationale above).
      # REVIEW B2 (2026-09-20): resolve the worktree branch into a VARIABLE
      # first. Inline substitution of a failing rev-parse yields "$base_branch.."
      # which git resolves as "$base_branch..HEAD" => count 0 => the guard
      # PASSES on a broken checkout instead of falling into skip-rev-list-unknown.
      local ahead wt_branch
      ahead=""
      if [ -n "$base_branch" ]; then
        wt_branch="$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)"
        if [ -n "$wt_branch" ]; then
          ahead="$(git -C "$repo" rev-list --count "$base_branch..$wt_branch" 2>/dev/null)"
        fi
      fi
      if [ -z "$ahead" ]; then
        log_line "$stage" "skip-rev-list-unknown" "$(json_str "$wt")"
        continue
      fi
      if [ "$ahead" != "0" ]; then
        log_line "$stage" "skip-unmerged-commits" "$(json_str "$wt")"
        continue
      fi

      # Guard 3: mtime age threshold.
      local mtime_epoch age_secs
      mtime_epoch="$(_file_mtime "$wt")"
      if [ "$mtime_epoch" = "0" ]; then
        log_line "$stage" "stat-failed" "$(json_str "$wt")"
        continue
      fi
      age_secs=$((now_epoch - mtime_epoch))
      if [ "$age_secs" -lt "$threshold_secs" ]; then
        log_line "$stage" "skip-too-young" "$(json_str "$wt")"
        continue
      fi

      # Guard 4: no live process cwd/argv inside it.
      if is_path_live "$wt"; then
        log_line "$stage" "skip-live" "$(json_str "$wt")"
        continue
      fi

      # Guard 5 (the fourth guard the verifier demanded): ignored content
      # must be disposable-only. A non-disposable ignored artifact (e.g. a
      # harness results dir) blocks reaping and is reported, not deleted.
      echo "  checking ignored content: $wt_name"
      if ! worktree_ignored_content_is_disposable "$wt"; then
        echo "  SKIP (non-disposable ignored content): $wt_name"
        log_line "$stage" "skip-non-disposable-ignored" "$(json_str "$wt")"
        continue
      fi

      local sz
      sz="$(du_bytes "$wt")"
      candidates=$((candidates + 1))
      reclaimable=$((reclaimable + sz))
      echo "  CLEAN $(human_bytes "$sz")  $wt"
      log_line "$stage" "candidate" "$(json_str "$wt")"

      if [ "$APPLY" = "1" ]; then
        if git -C "$repo" worktree remove "$wt" 2>/tmp/disk_janitor_wt_err.$$; then
          reclaimed=$((reclaimed + sz))
          log_line "$stage" "reaped" "$(json_str "$wt")"
        else
          local err_msg
          err_msg="$(cat /tmp/disk_janitor_wt_err.$$ 2>/dev/null)"
          echo "  ERROR: git worktree remove failed for $wt: $err_msg" >&2
          log_line "$stage" "reap-failed" "$(json_str "$wt: $err_msg")"
          ERRORS=$((ERRORS + 1))
        fi
        rm -f /tmp/disk_janitor_wt_err.$$ 2>/dev/null
      fi
    done

    if [ "$APPLY" = "1" ]; then
      git -C "$repo" worktree prune 2>/dev/null || true
      log_line "$stage" "pruned" "$(json_str "$repo")"
    fi
  done

  echo "[$stage] candidates=$candidates reclaimable=$(human_bytes "$reclaimable") reclaimed=$(human_bytes "$reclaimed")"
  add_summary_row "$stage" "$candidates" "$reclaimable" "$reclaimed"
}

# ===========================================================================
# Stage (c): docker image/builder prune (never -a, never volumes)
# ===========================================================================

stage_docker() {
  local stage="docker"
  if [ "$SKIP_DOCKER" = "1" ]; then
    echo "[$stage] skipped (--skip-docker)"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "[$stage] docker CLI not found — skipping"
    add_summary_row "$stage" 0 0 0
    return 0
  fi
  if ! _run_timeout 10 docker info >/dev/null 2>&1; then
    echo "[$stage] docker daemon not responding — skipping cleanly"
    log_line "$stage" "daemon-unresponsive" "\"docker info failed\""
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  # docker system df gives us a reclaimable estimate without mutating anything.
  local before_reclaimable
  before_reclaimable="$(_run_timeout 20 docker system df --format '{{.Reclaimable}}' 2>/dev/null | head -1)"
  echo "[$stage] docker-reported reclaimable (images+build cache, pre-run): ${before_reclaimable:-unknown}"

  local candidates=1  # docker doesn't give us a clean discrete count; report as one stage-level action
  local reclaimable=0 reclaimed=0

  if [ "$APPLY" = "1" ]; then
    local out1 out2
    out1="$(_run_timeout 120 docker image prune -f 2>&1)"
    log_line "$stage" "image-prune" "$(json_str "$out1")"
    out2="$(_run_timeout 120 docker builder prune -f 2>&1)"
    log_line "$stage" "builder-prune" "$(json_str "$out2")"
    echo "$out1"
    echo "$out2"
    # Best-effort bytes-reclaimed parse: docker prints "Total reclaimed space: X"
    local r1 r2
    r1="$(echo "$out1" | grep -oE 'Total reclaimed space: [0-9.]+[A-Za-z]+' | grep -oE '[0-9.]+[A-Za-z]+')"
    r2="$(echo "$out2" | grep -oE 'Total reclaimed space: [0-9.]+[A-Za-z]+' | grep -oE '[0-9.]+[A-Za-z]+')"
    echo "[$stage] reclaimed (docker-reported): image-prune=${r1:-0} builder-prune=${r2:-0}"
  else
    echo "[$stage] (dry run) would run: docker image prune -f && docker builder prune -f"
  fi

  add_summary_row "$stage" "$candidates" "$reclaimable" "$reclaimed"
}

# ===========================================================================
# #5816 (2026-09-19): pre-commit's db.db maps each installed hook repo to a
# cache dir under ~/.cache/pre-commit/repo*. Reaping a dir that db.db STILL
# REFERENCES leaves a dangling row, and every subsequent `git commit` in every
# repo on this machine dies with InvalidManifestError until the row is deleted
# and `pre-commit install-hooks` re-runs. An age threshold alone cannot see
# this: a referenced repo dir that simply has not been touched in 30 days is a
precommit_referenced_dirs() {
  local db="$1/db.db"
  # db.db genuinely absent = pre-commit not installed = nothing to protect.
  # This is the ONLY safe zero-rows case.
  [ -f "$db" ] || return 0
  if ! command -v sqlite3 >/dev/null 2>&1; then
    return 2
  fi
  local out
  if ! out="$(sqlite3 "$db" "SELECT path FROM repos;" 2>/dev/null)"; then
    return 2
  fi
  printf '%s\n' "$out"
  return 0
}

# Stage (d): age-trimmed caches (pre-commit, npm) — never blanket-delete
# ===========================================================================

stage_caches() {
  local stage="caches"
  if [ "$SKIP_CACHES" = "1" ]; then
    echo "[$stage] skipped (--skip-caches)"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  local candidates=0 reclaimable=0 reclaimed=0
  local precommit_cache="$HOME_DIR/.cache/pre-commit"

  if [ -d "$precommit_cache" ]; then
    echo "[$stage] scanning $precommit_cache (age >= ${PRECOMMIT_AGE_DAYS}d entries)..."

    # #5816: collect db.db-referenced dirs ONCE; every candidate is filtered
    # against this set before it is counted, sized, or reaped.
    _referenced_file="$(mktemp)"
    _ref_rc=0
    precommit_referenced_dirs "$precommit_cache" > "$_referenced_file" 2>/dev/null || _ref_rc=$?
    if [ "$_ref_rc" -eq 2 ]; then
      # FAIL CLOSED (B1): we cannot enumerate what db.db still references, so
      # we cannot prove any candidate is safe. Skip the whole pre-commit trim.
      rm -f "$_referenced_file"
      echo "[$stage] pre-commit: CANNOT READ db.db (sqlite3 missing or query failed)"
      echo "[$stage] pre-commit: SKIPPING cache trim entirely — reaping a still-referenced"
      echo "[$stage] pre-commit: repo dir breaks every commit on this machine (#5816)."
      log_line "$stage" "precommit-skipped-unreadable-db" "$(json_str "$precommit_cache")"
      _precommit_skipped=1
    else
      _precommit_skipped=0
      _ref_count="$(wc -l < "$_referenced_file" | tr -d " ")"
      echo "[$stage] pre-commit: $_ref_count repo dir(s) referenced by db.db — protected from reaping"
    fi

    # Prints candidates that are NOT referenced by db.db, NUL-delimited.
    _precommit_candidates() {
      [ "${_precommit_skipped:-0}" = "1" ] && return 0
      while IFS= read -r -d "" _e; do
        if ! grep -Fxq "$_e" "$_referenced_file" 2>/dev/null; then
          printf "%s\\0" "$_e"
        fi
      done < <(find "$precommit_cache" -mindepth 1 -maxdepth 1 -mtime "+${PRECOMMIT_AGE_DAYS}" -print0 2>/dev/null)
    }
    # find's own -mtime handles the age filter; we never glob patch* directly
    # (that pattern is known to exceed ARG_MAX on this machine at scale — see
    # CLAUDE.md's own note on this exact cache dir: 16,989+ entries measured).
    #
    # SIZING is done via ONE BATCHED `du -sk` pass over every candidate path
    # (xargs -0), never a per-entry du_bytes/_run_timeout call. Measured
    # 2026-09-19: this cache holds 14,372 entries older than 30 days on this
    # machine, and calling du_bytes (which forks TWO subprocesses per call
    # via _run_timeout) once per entry in a tight loop exhausted the process
    # table ("fork: Resource temporarily unavailable") before completing.
    # The batched form computes the same total in well under a second.
    local candidate_count
    candidate_count="$(_precommit_candidates | tr -cd '\0' | wc -c | tr -d ' ')"
    candidates="${candidate_count:-0}"

    if [ "$candidates" -gt 0 ]; then
      reclaimable="$(_precommit_candidates \
        | xargs -0 du -sk 2>/dev/null \
        | awk '{sum+=$1} END {printf "%d", sum*1024}')"
      reclaimable="${reclaimable:-0}"
      log_line "$stage" "candidates-batched" "$(json_str "count=$candidates bytes=$reclaimable")"
    fi

    if [ "$APPLY" = "1" ] && [ "$candidates" -gt 0 ]; then
      # Deletion still happens one entry at a time (never a bulk `rm -rf`
      # over an unbounded xargs invocation of rm itself) so a single
      # failure is caught and logged per-path rather than silently
      # swallowed inside a batched command's aggregate exit code.
      while IFS= read -r -d '' entry; do
        if rm -rf -- "$entry" 2>/dev/null; then
          log_line "$stage" "reaped" "$(json_str "$entry")"
        else
          echo "  ERROR: failed to remove $entry" >&2
          log_line "$stage" "reap-failed" "$(json_str "$entry")"
          ERRORS=$((ERRORS + 1))
        fi
      done < <(_precommit_candidates)
      reclaimed="$reclaimable"
    fi
    rm -f "$_referenced_file"
    echo "[$stage] pre-commit cache: candidates=$candidates reclaimable=$(human_bytes "$reclaimable")"
  else
    echo "[$stage] $precommit_cache not present — skipping pre-commit cache trim"
  fi

  if command -v npm >/dev/null 2>&1; then
    if [ "$APPLY" = "1" ]; then
      echo "[$stage] running: npm cache verify"
      local npm_out
      npm_out="$(_run_timeout 120 npm cache verify 2>&1)"
      log_line "$stage" "npm-cache-verify" "$(json_str "$npm_out")"
      echo "$npm_out"
    else
      echo "[$stage] (dry run) would run: npm cache verify"
    fi
  else
    echo "[$stage] npm not found — skipping npm cache verify"
  fi

  add_summary_row "$stage" "$candidates" "$reclaimable" "$reclaimed"
}

# ===========================================================================
# Stage (e): old subagent transcripts under ~/.claude/projects/*/subagents/*.jsonl
# ===========================================================================

stage_transcripts() {
  local stage="transcripts"
  if [ "$SKIP_TRANSCRIPTS" = "1" ]; then
    echo "[$stage] skipped (--skip-transcripts)"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  local projects_root="$CLAUDE_DIR/projects"
  if [ ! -d "$projects_root" ]; then
    echo "[$stage] $projects_root not present — nothing to do"
    add_summary_row "$stage" 0 0 0
    return 0
  fi

  echo "[$stage] scanning $projects_root/*/subagents/*.jsonl (age >= ${TRANSCRIPT_AGE_DAYS}d)..."

  local candidates=0 reclaimable=0 reclaimed=0
  local f sz
  while IFS= read -r -d '' f; do
    sz="$(du_bytes "$f")"
    candidates=$((candidates + 1))
    reclaimable=$((reclaimable + sz))
    log_line "$stage" "candidate" "$(json_str "$f")"
    if [ "$APPLY" = "1" ]; then
      if rm -f -- "$f" 2>/dev/null; then
        reclaimed=$((reclaimed + sz))
        log_line "$stage" "reaped" "$(json_str "$f")"
      else
        echo "  ERROR: failed to remove $f" >&2
        log_line "$stage" "reap-failed" "$(json_str "$f")"
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done < <(find "$projects_root" -path '*/subagents/*.jsonl' -mtime "+${TRANSCRIPT_AGE_DAYS}" -print0 2>/dev/null)

  echo "[$stage] candidates=$candidates reclaimable=$(human_bytes "$reclaimable") reclaimed=$(human_bytes "$reclaimed")"
  add_summary_row "$stage" "$candidates" "$reclaimable" "$reclaimed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
  echo "disk_janitor.sh — mode=$MODE_LABEL run=$RUN_STAMP"
  log_line "run" "start" "$(json_str "mode=$MODE_LABEL")"

  _detect_stat_flavor  # once, at the top level (see "Portable file mtime")

  stage_sessions
  stage_worktrees
  stage_docker
  stage_caches
  stage_transcripts

  print_summary
  log_line "run" "end" "$(json_str "errors=$ERRORS")"

  if [ "$ERRORS" -gt 0 ]; then
    echo "disk_janitor.sh: completed with $ERRORS error(s) — see $LOG_FILE" >&2
    exit 1
  fi
  exit 0
}

main
