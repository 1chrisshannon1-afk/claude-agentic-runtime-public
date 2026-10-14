#!/usr/bin/env bash
# Tests for scripts/disk_janitor.sh's registry-driven repo roots and portable mtime helper.
#
# WHY THIS EXISTS: stage (b) of the janitor (an --apply script that runs unattended) swept a
# default repo list with two product paths baked into the runtime script. The roots now come
# from knowledge/repo_registry.json (repos.<slug>.root, stored ~-relative, so the script must
# expand the ~ itself) with NO default product path; a missing or empty registry means "no
# product roots" and the stage says so. The two `stat -f %m` calls were BSD-only and are now
# one helper that probes BSD/GNU flavor once. A set-but-empty $HOME used to make the script's
# home directory the current directory; it now resolves to the account home or refuses.
#
# Every test asserts the intended behavior (roots expand, nothing is invented, an unreadable
# source sweeps nothing and says why), not a snapshot of current output. Each was seen to
# fail against a scratch mutant of the script (see the mutation list in the change record).
#
# Method: pure functions are pulled out of the real script by name (same technique as
# test_disk_janitor_guards.sh) so the tests track the shipped source; one end-to-end dry-run
# of the real script runs the worktrees stage only, against a scratch HOME and registry. It
# never passes --apply and never reads the operator's real registry.
#
# Env: DISK_JANITOR_SRC=<path> points the tests at a candidate or mutant copy of the script.
# Run: bash hooks/tests/test_disk_janitor_roots.sh      Exit: 0 all pass, 1 otherwise.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${DISK_JANITOR_SRC:-$HERE/../../scripts/disk_janitor.sh}"
[ -f "$SRC" ] || { echo "FATAL: $SRC not found" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 required" >&2; exit 1; }

PASS=0
FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
# eq <label> <got> <want>
eq() {
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/janitor_roots.XXXXXX")" || exit 1
trap 'rm -rf "$WORK"' EXIT
# A TMPDIR with a trailing slash yields "//" in the path; the script normalizes roots, so
# compare against the same normalized, symlink-resolved form.
WORK="$(cd "$WORK" && pwd -P)" || exit 1
mkdir -p "$WORK/home"
HOME_DIR="$WORK/home"

# Pull the functions under test out of the shipped script.
for fn in expand_tilde _add_repo registry_roots resolve_repos _file_mtime; do
  body="$(awk -v fn="$fn" '$0 == fn "() {" {p=1} p {print} p && /^\}/ {exit}' "$SRC")"
  if [ -z "$body" ]; then
    echo "FATAL: function $fn not found in $SRC" >&2
    exit 1
  fi
  eval "$body"
done
# The flavor detector is checked for explicitly below (so a script without it fails ONE
# named assertion instead of aborting the file); load it when present.
HAVE_DETECTOR=0
for fn in _probe_stat_flavor _detect_stat_flavor; do
  body="$(awk -v fn="$fn" '$0 == fn "() {" {p=1} p {print} p && /^\}/ {exit}' "$SRC")"
  if [ -n "$body" ]; then eval "$body"; fi
done
if declare -F _detect_stat_flavor >/dev/null; then HAVE_DETECTOR=1; else _detect_stat_flavor() { :; }; fi

REPOS=()
REPOS_SOURCE=""
_STAT_FLAVOR=""
REGISTRY_FILE="$WORK/registry.json"
unset DISK_JANITOR_REPOS

# set_registry <json>
set_registry() { printf '%s' "$1" > "$REGISTRY_FILE"; }
# joined: REPOS as one '|'-joined string (empty -> "")
joined() {
  local out="" r
  if [ "${#REPOS[@]}" -gt 0 ]; then
    for r in "${REPOS[@]}"; do out="${out:+$out|}$r"; done
  fi
  printf '%s' "$out"
}

echo "registry roots -- ~ expands, nothing is invented"
set_registry '{"schema_version":1,"repos":{"alpha":{"root":"~/work/alpha"},"beta":{"root":"~/work/beta"}}}'
resolve_repos >/dev/null
eq "~-relative registry roots expand to the home dir" "$(joined)" "$HOME_DIR/work/alpha|$HOME_DIR/work/beta"
case "$(joined)" in
  *"~"*) bad "no root keeps a literal ~" ;;
  *) ok "no root keeps a literal ~" ;;
esac
eq "REPOS_SOURCE names the registry file" "$REPOS_SOURCE" "$REGISTRY_FILE"

set_registry '{"repos":{"a":{"root":"/abs/one"},"b":{"root":"relative/two"},"c":{},"d":"notadict","e":{"root":""},"f":{"root":123},"g":{"root":"~/x/"}}}'
resolve_repos >/dev/null
eq "absolute kept; relative, rootless, non-dict, empty, non-string dropped; trailing slash normalized" \
  "$(joined)" "/abs/one|$HOME_DIR/x"

set_registry '{"repos":{"one":{"root":"~/shared"},"two":{"root":"~/shared"}}}'
resolve_repos >/dev/null
eq "two slugs sharing one checkout sweep it once" "$(joined)" "$HOME_DIR/shared"

# A JSON \u0000 in a root: the shell's command substitution silently drops NUL, which would
# truncate "~/nul\0bad" into a DIFFERENT path ("~/nulbad"). Reject the entry instead.
set_registry '{"repos":{"a":{"root":"~/nul\u0000bad"},"b":{"root":"~/good"},"c":{"root":"~/new\nline"}}}'
resolve_repos >/dev/null
eq "a root holding NUL (or a newline) is rejected, never truncated into another path" "$(joined)" "$HOME_DIR/good"

echo "registry roots -- an unusable source sweeps nothing and says why"
rm -f "$REGISTRY_FILE"
out="$(resolve_repos)"
resolve_repos >/dev/null
eq "missing registry => no roots" "$(joined)" ""
case "$out" in
  *"no repo registry"*"no product roots"*) ok "missing registry says so" ;;
  *) bad "missing registry must say there is no registry / no product roots (got: $out)" ;;
esac

set_registry '{"repos":{}}'
resolve_repos >/dev/null
rc=$?
eq "empty registry => no roots" "$(joined)" ""
eq "empty registry is not an error (rc 0)" "$rc" "0"

set_registry '{"repos": {"a": {"root": "~/x"'
out="$(resolve_repos)"
resolve_repos >/dev/null
eq "malformed JSON => no roots (fails closed)" "$(joined)" ""
case "$out" in
  *"cannot read repo roots"*) ok "malformed JSON says it could not be read" ;;
  *) bad "malformed JSON must be reported (got: $out)" ;;
esac

set_registry '["not","an","object"]'
resolve_repos >/dev/null
eq "wrong top-level shape => no roots" "$(joined)" ""
set_registry '{"repos":["a","b"]}'
resolve_repos >/dev/null
eq "repos not an object => no roots" "$(joined)" ""

echo "registry roots -- explicit override"
set_registry '{"repos":{"x":{"root":"/from/registry"}}}'
tilde='~'  # held in a variable: the point is a LITERAL ~ reaching the script
DISK_JANITOR_REPOS="$tilde/ov1 /abs/ov2 rel/ov3 $tilde/ov1" resolve_repos >/dev/null
eq "DISK_JANITOR_REPOS wins, expands ~, drops relative, dedups" "$(joined)" "$HOME_DIR/ov1|/abs/ov2"
eq "override reports its source" "$REPOS_SOURCE" "DISK_JANITOR_REPOS"
DISK_JANITOR_REPOS="" resolve_repos >/dev/null
eq "an empty override falls back to the registry" "$(joined)" "/from/registry"
# Pathname expansion must stay OFF while the override is word-split: an absolute glob entry
# is kept as the literal path it was written as, never fanned out over real directories.
mkdir -p "$WORK/globdir/a" "$WORK/globdir/b"
DISK_JANITOR_REPOS="$WORK/globdir/* /abs/x" resolve_repos >/dev/null
eq "a glob entry in DISK_JANITOR_REPOS is not expanded" "$(joined)" "$WORK/globdir/*|/abs/x"
case "$-" in
  *f*) bad "noglob must be restored after resolve_repos" ;;
  *) ok "noglob is restored after resolve_repos" ;;
esac

echo "source hygiene -- no default product path"
# Active (non-comment) lines must hold no absolute home path and no Desktop path; the original
# defect was exactly a hardcoded list of them.
hits="$(grep -Ev '^[[:space:]]*#' "$SRC" | grep -nE '/Users/|/home/[a-z]|Desktop/' || true)"
eq "no hardcoded /Users, /home or Desktop path in active lines" "$hits" ""
hits="$(grep -Ev '^[[:space:]]*#' "$SRC" | grep -nE '^[[:space:]]*"~/' || true)"
eq "no ~/ path literal in active lines (a quoted or variable ~ never expands)" "$hits" ""
hits="$(grep -n '^DEFAULT_REPOS' "$SRC" || true)"
eq "no DEFAULT_REPOS list" "$hits" ""

echo "_file_mtime -- BSD and GNU stat"
touch "$WORK/f.txt"
python3 -I -c 'import os,sys; os.utime(sys.argv[1], (1600000000, 1600000000))' "$WORK/f.txt"
_STAT_FLAVOR=""
_detect_stat_flavor
eq "the janitor defines a top-level flavor detector (_detect_stat_flavor)" "$HAVE_DETECTOR" "1"
eq "reads a known mtime with the host stat" "$(_file_mtime "$WORK/f.txt")" "1600000000"
eq "a missing path yields 0 (callers treat 0 as stat-failed)" "$(_file_mtime "$WORK/nope")" "0"
mkdir "$WORK/d"
python3 -I -c 'import os,sys; os.utime(sys.argv[1], (1700000000, 1700000000))' "$WORK/d"
eq "reads a directory mtime" "$(_file_mtime "$WORK/d")" "1700000000"

# Fake `stat` shims prove each flavor path on any host: the shim answers only its own flavor's
# syntax (the other option exits 1, as a real stat of the other family does).
mkdir -p "$WORK/gnu" "$WORK/bsd" "$WORK/none" "$WORK/count"
for flavor in gnu bsd; do
  if [ "$flavor" = "gnu" ]; then
    accept='-c'
    other='-f'
  else
    accept='-f'
    other='-c'
  fi
  cat > "$WORK/$flavor/stat" <<SHIM
#!/bin/sh
# usage: stat $accept FORMAT PATH   (the $other form is rejected, like the other stat family)
[ "\$1" = "$accept" ] || { echo "stat: illegal option -- \$1" >&2; exit 1; }
exec python3 -I -c 'import os,sys; print(int(os.stat(sys.argv[1]).st_mtime))' "\$3"
SHIM
  chmod +x "$WORK/$flavor/stat"
done
printf '#!/bin/sh\nexit 1\n' > "$WORK/none/stat"
chmod +x "$WORK/none/stat"

_STAT_FLAVOR=""
PATH="$WORK/gnu:$PATH" _detect_stat_flavor
got="$(PATH="$WORK/gnu:$PATH" _file_mtime "$WORK/f.txt")"
eq "GNU-only stat (-c %Y) is read correctly" "$got" "1600000000"
_STAT_FLAVOR=""
PATH="$WORK/bsd:$PATH" _detect_stat_flavor
got="$(PATH="$WORK/bsd:$PATH" _file_mtime "$WORK/f.txt")"
eq "BSD-only stat (-f %m) is read correctly" "$got" "1600000000"
_STAT_FLAVOR=""
PATH="$WORK/none:$PATH" _detect_stat_flavor
got="$(PATH="$WORK/none:$PATH" _file_mtime "$WORK/f.txt")"
eq "no usable stat => 0, never garbage" "$got" "0"
_STAT_FLAVOR=""
got="$(PATH="$WORK/gnu:$PATH" _file_mtime "$WORK/f.txt")"
eq "without a prior detect, _file_mtime still answers correctly (probes for that call)" "$got" "1600000000"

# The flavor is probed ONCE. Every real caller runs _file_mtime inside $( ), where a cached
# assignment is lost, so the probe has to happen at the top level beforehand: after it, N
# reads must cost exactly N stat forks.
REAL_STAT="$(command -v stat)"
printf '#!/bin/sh\necho x >> "%s"\nexec "%s" "$@"\n' "$WORK/stat_calls" "$REAL_STAT" > "$WORK/count/stat"
chmod +x "$WORK/count/stat"
: > "$WORK/stat_calls"
_STAT_FLAVOR=""
PATH="$WORK/count:$PATH" _detect_stat_flavor
before="$(wc -l < "$WORK/stat_calls" | tr -d ' ')"
for _i in 1 2 3 4 5; do
  : "$(PATH="$WORK/count:$PATH" _file_mtime "$WORK/f.txt")"
done
after="$(wc -l < "$WORK/stat_calls" | tr -d ' ')"
eq "5 mtime reads cost exactly 5 stat forks once the flavor is detected" "$((after - before))" "5"
_STAT_FLAVOR=""

echo "home directory -- a set-but-empty \$HOME must never become the current directory"
# The two resolution lines, pulled out of the script and run in a scratch cwd with HOME empty.
mkdir -p "$WORK/cwd"
home_lines="$(grep -E '^HOME_DIR=|^\[ -n "\$HOME_DIR" \] \|\|' "$SRC")"
acct_home="$(python3 -I -c 'import os,pwd; print(pwd.getpwuid(os.getuid()).pw_dir)' 2>/dev/null)"
if [ -d "$acct_home" ] && [ "$acct_home" != "$WORK/cwd" ]; then
  got="$(cd "$WORK/cwd" && env HOME= "$BASH" -c "$home_lines"'; printf %s "$HOME_DIR"')"
  if [ "$got" = "$WORK/cwd" ]; then
    bad "an empty HOME made the home directory the current directory"
  else
    ok "an empty HOME does not become the current directory"
  fi
  eq "an empty HOME resolves to the account database's home" "$got" "$acct_home"
else
  echo "  SKIP  no account-database home on this host: empty-HOME fallback not exercised"
fi
got="$(cd "$WORK/cwd" && env HOME="$WORK/cwd" "$BASH" -c "$home_lines"'; printf %s "$HOME_DIR"')"
eq "a real HOME is used as given" "$got" "$WORK/cwd"

# Full runs, every stage skipped: an unusable home must stop the script (exit 2) before it
# writes anything; a good one runs and writes only under CLAUDE_DIR.
SKIPS="--skip-sessions --skip-worktrees --skip-docker --skip-caches --skip-transcripts"
guard_run() {  # guard_run <HOME value> -> sets GRC, GERR; runs in an empty scratch cwd
  rm -rf "$WORK/cwd3"
  mkdir -p "$WORK/cwd3"
  # SKIPS is deliberately word-split into the stage flags.
  # shellcheck disable=SC2086
  GERR="$(cd "$WORK/cwd3" && env -i PATH="$PATH" HOME="$1" "$BASH" "$SRC" $SKIPS 2>&1 >/dev/null)"
  GRC=$?
}
guard_run /
eq "HOME=/ => exit 2" "$GRC" "2"
has_msg() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (got: $2)" ;; esac; }
has_msg "HOME=/ => says why" "$GERR" "usable home directory"
eq "HOME=/ => nothing written in the cwd" "$(ls -A "$WORK/cwd3" | wc -l | tr -d ' ')" "0"
guard_run "$WORK/does-not-exist"
eq "HOME=<nonexistent dir> => exit 2" "$GRC" "2"
eq "HOME=<nonexistent dir> => nothing written in the cwd" "$(ls -A "$WORK/cwd3" | wc -l | tr -d ' ')" "0"
mkdir -p "$WORK/goodhome"
rm -rf "$WORK/cwd3"
mkdir -p "$WORK/cwd3"
# SKIPS is deliberately word-split into the stage flags.
# shellcheck disable=SC2086
(cd "$WORK/cwd3" && env -i PATH="$PATH" HOME="$WORK/goodhome" CLAUDE_DIR="$WORK/goodhome/.claude" "$BASH" "$SRC" $SKIPS >/dev/null 2>&1)
eq "a good HOME runs (exit 0)" "$?" "0"
eq "a good HOME writes nothing in the cwd" "$(ls -A "$WORK/cwd3" | wc -l | tr -d ' ')" "0"
[ -f "$WORK/goodhome/.claude/.disk_janitor.log" ] && ok "a good HOME logs under CLAUDE_DIR" || bad "expected the log under CLAUDE_DIR"

echo "end to end -- the real script, worktrees stage only, dry run, scratch HOME"
E2E_HOME="$WORK/e2e"
mkdir -p "$E2E_HOME/.claude/knowledge" "$E2E_HOME/proj"
git init -q "$E2E_HOME/proj" 2>/dev/null
printf '%s' '{"schema_version":1,"repos":{"demo":{"root":"~/proj"}}}' > "$E2E_HOME/.claude/knowledge/repo_registry.json"
run_janitor() {
  # env -i keeps the operator's environment (DISK_JANITOR_*, CLAUDE_DIR) out of the run.
  env -i HOME="$E2E_HOME" PATH="$PATH" CLAUDE_DIR="$E2E_HOME/.claude" \
    bash "$SRC" --skip-sessions --skip-docker --skip-caches --skip-transcripts 2>&1
}
out="$(run_janitor)"
rc=$?
eq "dry run exits 0" "$rc" "0"
case "$out" in
  *"1 repo root(s) from $E2E_HOME/.claude/knowledge/repo_registry.json"*) ok "the registry's root is used" ;;
  *) bad "expected one repo root from the scratch registry (got: $out)" ;;
esac
case "$out" in
  *"$E2E_HOME/proj: no $E2E_HOME/proj/.claude/worktrees"*) ok "the ~ root expanded to the real scratch dir and was visited" ;;
  *) bad "the expanded root was not visited (got: $out)" ;;
esac
case "$out" in
  *"(dry run"*) ok "reported as a dry run" ;;
  *) bad "must report dry run" ;;
esac

printf '%s' '{"repos":{}}' > "$E2E_HOME/.claude/knowledge/repo_registry.json"
out="$(run_janitor)"
case "$out" in
  *"no repo roots"*"nothing to sweep"*) ok "an empty registry: the stage says there are no roots" ;;
  *) bad "empty registry must say 'no repo roots ... nothing to sweep' (got: $out)" ;;
esac
rm -f "$E2E_HOME/.claude/knowledge/repo_registry.json"
out="$(run_janitor)"
case "$out" in
  *"no repo registry"*"no repo roots"*) ok "a missing registry: the stage says so and sweeps nothing" ;;
  *) bad "missing registry must say so (got: $out)" ;;
esac
case "$out" in
  *"scanning"*) bad "a missing registry must not scan any root (got: $out)" ;;
  *) ok "a missing registry scans nothing" ;;
esac

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
