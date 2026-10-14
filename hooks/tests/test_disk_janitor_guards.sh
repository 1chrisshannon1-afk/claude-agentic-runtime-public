#!/usr/bin/env bash
# Guard tests for scripts/disk_janitor.sh.
#
# WHY THIS EXISTS: the 2026-09-20 Opus review found 842 lines of deletion logic
# with zero tests, while the 186-line warn-only hook beside it had 19. Both
# blockers it found (B1, B2) lived in the untested file, and both were the same
# defect class: a guard that FAILS OPEN — reading "I could not determine this"
# as "this is safe to delete."
#
# Every test here asserts INTENDED behavior from that safety contract, not
# current output: an unknowable state must SKIP, never reap. Each one was
# confirmed to FAIL against the pre-fix source before the fix landed.
#
# Run: bash ~/.claude/hooks/tests/test_disk_janitor_guards.sh
set -u

SRC="${DISK_JANITOR_SRC:-$HOME/.claude/scripts/disk_janitor.sh}"
[ -f "$SRC" ] || { echo "FATAL: $SRC not found"; exit 1; }

# Pull the two pure-ish guard functions out of the real script so these tests
# track the shipped source rather than a copy that can drift.
# The guard reads the DISPOSABLE_IGNORED_PATTERNS array from the script's
# global scope, so source that declaration too rather than redefining the list
# here -- a hand-copied list would silently drift from the shipped policy and
# these tests would stop testing the real thing.
eval "$(awk '/^DISPOSABLE_IGNORED_PATTERNS=\(/,/^\)/' "$SRC")"
eval "$(awk '/^precommit_referenced_dirs\(\) \{/,/^\}/' "$SRC")"
eval "$(awk '/^worktree_ignored_content_is_disposable\(\) \{/,/^\}/' "$SRC")"

if [ "${#DISPOSABLE_IGNORED_PATTERNS[@]}" -eq 0 ]; then
  echo "FATAL: DISPOSABLE_IGNORED_PATTERNS not sourced from $SRC"; exit 1
fi

PASS=0; FAIL=0
ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
# shellcheck disable=SC2015  # ok() cannot fail, so A && B || C is safe here
eq()   { [ "$2" = "$3" ] && ok "$1 (got $2)" || bad "$1 (got $2, want $3)"; }

WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
cd "$WORK" || exit 1

echo "B1 — the pre-commit db.db reference filter"
echo "  contract: 0 = authoritative answer, 2 = cannot determine (caller MUST skip)"

# Reaping a repo dir db.db still references leaves a dangling row and breaks
# EVERY commit on the machine with InvalidManifestError (#5816). If we
# cannot read db.db we cannot prove any candidate is unreferenced.
mkdir -p c_nosqlite && : > c_nosqlite/db.db
rc=0
# shellcheck disable=SC2123  # deliberate: hides sqlite3, scoped to this subshell only
( PATH=/nonexistent; precommit_referenced_dirs "$WORK/c_nosqlite" ) >/dev/null 2>&1 || rc=$?
eq "sqlite3 missing => cannot determine" "$rc" "2"

mkdir -p c_corrupt && echo "this is not a sqlite database" > c_corrupt/db.db
rc=0; precommit_referenced_dirs "$WORK/c_corrupt" >/dev/null 2>&1 || rc=$?
eq "db.db unreadable => cannot determine" "$rc" "2"

# The ONLY safe zero-rows case: pre-commit simply is not installed.
mkdir -p c_absent
rc=0; precommit_referenced_dirs "$WORK/c_absent" >/dev/null 2>&1 || rc=$?
eq "db.db absent => authoritative none" "$rc" "0"

if command -v sqlite3 >/dev/null 2>&1; then
  mkdir -p c_good
  sqlite3 c_good/db.db \
    "CREATE TABLE repos(repo TEXT, ref TEXT, path TEXT);
     INSERT INTO repos VALUES('r1','1','$WORK/c_good/repoAAA');
     INSERT INTO repos VALUES('r2','2','$WORK/c_good/repoBBB');" 2>/dev/null
  rc=0; precommit_referenced_dirs "$WORK/c_good" >/dev/null 2>&1 || rc=$?
  eq "readable db.db => authoritative" "$rc" "0"
  n=$(precommit_referenced_dirs "$WORK/c_good" 2>/dev/null | grep -c 'repo[AB]')
  eq "both referenced dirs enumerated" "$n" "2"
else
  echo "  SKIP  sqlite3 unavailable — happy-path enumeration not exercised"
fi

echo "B2 — worktree ignored-content guard"
echo "  contract: a worktree whose state cannot be read is NEVER disposable"

# The 2026-09-15 incident produced exactly this shape: checkouts agents could
# not cleanly remove, with phantom-deletion diffs. git exits 128 with EMPTY
# stdout, which the pre-fix code read as "no ignored content" => disposable.
mkdir -p wt_broken && echo "gitdir: /nonexistent/xyz" > wt_broken/.git
echo "real uncommitted work" > wt_broken/important.txt
if worktree_ignored_content_is_disposable "$WORK/wt_broken" >/dev/null 2>&1; then
  bad "corrupted worktree must NOT be disposable"
else
  ok "corrupted worktree => non-disposable (fails closed)"
fi

# A path that is not a git repository at all is equally unknowable.
mkdir -p not_a_repo && echo x > not_a_repo/file.txt
if worktree_ignored_content_is_disposable "$WORK/not_a_repo" >/dev/null 2>&1; then
  bad "non-repo path must NOT be disposable"
else
  ok "non-repo path => non-disposable (fails closed)"
fi

# Positive control: a healthy repo whose only ignored content IS disposable
# must still pass, or the guard would be uselessly conservative and reap nothing.
if command -v git >/dev/null 2>&1; then
  mkdir -p wt_clean && cd wt_clean || exit 1
  git init -q . 2>/dev/null
  echo "__pycache__/" > .gitignore
  mkdir -p __pycache__ && echo cached > __pycache__/x.pyc
  git add -- .gitignore 2>/dev/null
  git -c user.email=t@t -c user.name=t commit -qm init -- .gitignore 2>/dev/null
  cd "$WORK" || exit 1
  if worktree_ignored_content_is_disposable "$WORK/wt_clean" >/dev/null 2>&1; then
    ok "healthy repo, only __pycache__ ignored => disposable"
  else
    bad "healthy repo with disposable-only ignored content should pass"
  fi

  # And the real protective case: ignored content that is NOT a build cache.
  mkdir -p wt_logs && cd wt_logs || exit 1
  git init -q . 2>/dev/null
  echo "logs/" > .gitignore
  mkdir -p logs && echo "expensive harness output" > logs/run.log
  git add -- .gitignore 2>/dev/null
  git -c user.email=t@t -c user.name=t commit -qm init -- .gitignore 2>/dev/null
  cd "$WORK" || exit 1
  if worktree_ignored_content_is_disposable "$WORK/wt_logs" >/dev/null 2>&1; then
    bad "ignored real logs must NOT be disposable"
  else
    ok "ignored non-cache content => non-disposable"
  fi
else
  echo "  SKIP  git unavailable — positive controls not exercised"
fi

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
