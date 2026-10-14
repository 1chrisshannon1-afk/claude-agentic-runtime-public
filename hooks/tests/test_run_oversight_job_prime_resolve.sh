#!/usr/bin/env bash
# Tests for schedules/run_oversight_job.sh's two host-lookup helpers:
#   _resolve_prime_sh   -- finds the browser-pool priming script through the repo registry
#   _resolve_claude_bin -- finds the claude CLI without baking in a macOS-only path
#
# WHY THIS EXISTS: the wrapper used to run `$HOME/Desktop/<product>/scripts/
# prime_browser_pool.sh` from a path baked into the script, and fell back to
# /opt/homebrew/bin/claude on every OS. The priming script is now found through
# knowledge/repo_registry.json (`repos.<slug>.root`, stored ~-relative), optionally pinned
# by OVERSIGHT_PRIME_REPO, and an unresolvable lookup must SKIP the pre-flight and say why
# on stderr -- never guess a path, never silently skip. The job that depends on it is
# loaded under launchd with no way to see a failure except its .err.log and the typed
# prime_status heartbeat key.
#
# Method: the two helper functions are pulled out of the real wrapper by name (so these
# tests track the shipped source), then one end-to-end block runs a COPY of the real
# wrapper in a scratch $HOME with a stub `claude` and stub priming scripts. The real
# priming script (a live staging login) and the real claude CLI are never invoked.
#
# Env: OVERSIGHT_WRAPPER_SRC=<path> points the tests at a candidate or mutant wrapper.
# Run: bash hooks/tests/test_run_oversight_job_prime_resolve.sh      Exit: 0 all pass, 1 otherwise.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${OVERSIGHT_WRAPPER_SRC:-$HERE/../../schedules/run_oversight_job.sh}"
[ -f "$SRC" ] || { echo "FATAL: $SRC not found" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 required" >&2; exit 1; }

PASS=0
FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
eq() {
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}
has() {  # has <label> <haystack> <needle>
  case "$2" in
    *"$3"*) ok "$1" ;;
    *) bad "$1 (missing '$3' in: $2)" ;;
  esac
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/prime_resolve.XXXXXX")" || exit 1
trap 'rm -rf "$WORK"' EXIT
WORK="$(cd "$WORK" && pwd -P)" || exit 1
H="$WORK/home"
mkdir -p "$H/.claude/knowledge" "$H/.claude/schedules" "$WORK/bin" "$WORK/nobin"

for fn in _resolve_prime_sh _resolve_claude_bin; do
  body="$(awk -v fn="$fn" '$0 == fn "() {" {p=1} p {print} p && /^\}/ {exit}' "$SRC")"
  if [ -z "$body" ]; then
    echo "FATAL: function $fn not found in $SRC" >&2
    exit 1
  fi
  eval "$body"
done

REG="$H/.claude/knowledge/repo_registry.json"

# mkrepo <name> [x]: ~/<name>/scripts/prime_browser_pool.sh; second arg "x" makes it executable.
mkrepo() {
  mkdir -p "$H/$1/scripts"
  printf '#!/bin/bash\nexit 0\n' > "$H/$1/scripts/prime_browser_pool.sh"
  if [ "${2:-}" = "x" ]; then chmod +x "$H/$1/scripts/prime_browser_pool.sh"; else chmod -x "$H/$1/scripts/prime_browser_pool.sh"; fi
}

# nlines <text>: how many "prime pre-flight not run" lines the text holds.
nlines() {
  printf '%s\n' "$1" | grep -c 'prime pre-flight not run'
}

# resolve <env assignments...>: runs _resolve_prime_sh in a clean env; sets OUT, ERR, RC.
resolve() {
  local errf="$WORK/resolve.err"
  # "$BASH" by absolute path: a case below hands the function a PATH that has no bash on it.
  OUT="$(env -i HOME="$H" PATH="$PATH" "$@" "$BASH" -c "$(declare -f _resolve_prime_sh); _resolve_prime_sh" 2>"$errf")"
  RC=$?
  ERR="$(cat "$errf")"
}

echo "_resolve_prime_sh -- opt-in and discovery"
printf '%s' '{"repos":{"a":{"root":"~/repoA"},"b":{"root":"~/repoB"}}}' > "$REG"
mkrepo repoA x
mkrepo repoB x
rm -rf "$H/repoB/scripts"
resolve
eq "OVERSIGHT_PRIME_APP unset => resolves nothing" "$OUT" ""
eq "OVERSIGHT_PRIME_APP unset => silent (no stderr)" "$ERR" ""
eq "OVERSIGHT_PRIME_APP unset => rc 0 (job not opted in)" "$RC" "0"

resolve OVERSIGHT_PRIME_APP=app
eq "the one registered repo holding the script is found; ~ expands against HOME" "$OUT" "$H/repoA/scripts/prime_browser_pool.sh"
eq "success is silent" "$ERR" ""
eq "success rc 0" "$RC" "0"

echo "_resolve_prime_sh -- explicit slug"
mkrepo repoB x
resolve OVERSIGHT_PRIME_APP=app OVERSIGHT_PRIME_REPO=b
eq "OVERSIGHT_PRIME_REPO pins the repo even when two hold the script" "$OUT" "$H/repoB/scripts/prime_browser_pool.sh"
resolve OVERSIGHT_PRIME_APP=app OVERSIGHT_PRIME_REPO=a
eq "OVERSIGHT_PRIME_REPO can pin the other one" "$OUT" "$H/repoA/scripts/prime_browser_pool.sh"

echo "_resolve_prime_sh -- every unresolvable case skips and says why"
resolve OVERSIGHT_PRIME_APP=app
eq "two candidates, no slug => resolves nothing (never guesses)" "$OUT" ""
[ "$RC" -ne 0 ] && ok "two candidates => nonzero rc" || bad "two candidates must exit nonzero"
has "ambiguity names the knob" "$ERR" "OVERSIGHT_PRIME_REPO"
eq "ambiguity prints exactly one reason line" "$(nlines "$ERR")" "1"
has "ambiguity says more than one" "$ERR" "more than one registered repo"
has "stderr carries the WRAPPER prefix the daily sweep keys on" "$ERR" "WRAPPER: prime pre-flight not run - "

resolve OVERSIGHT_PRIME_APP=app OVERSIGHT_PRIME_REPO=nosuch
eq "unknown slug => resolves nothing" "$OUT" ""
has "unknown slug is named in the error" "$ERR" "OVERSIGHT_PRIME_REPO=nosuch"
eq "unknown slug prints exactly one reason line" "$(nlines "$ERR")" "1"

printf '%s' '{"repos":{"a":{"root":"~/repoA"},"c":{"root":"~/repoC"}}}' > "$REG"
rm -rf "$H/repoA/scripts" "$H/repoB"
mkdir -p "$H/repoC"
resolve OVERSIGHT_PRIME_APP=app
eq "no repo holds the script => resolves nothing" "$OUT" ""
has "says no registered repo has it" "$ERR" "no registered repo has an executable scripts/prime_browser_pool.sh"
eq "no match prints exactly one reason line" "$(nlines "$ERR")" "1"
resolve OVERSIGHT_PRIME_APP=app OVERSIGHT_PRIME_REPO=c
has "explicit slug without the script is reported against that repo" "$ERR" "no repo c has an executable"

mkrepo repoA ""
resolve OVERSIGHT_PRIME_APP=app
eq "a non-executable script is not resolved" "$OUT" ""
rm -rf "$H/repoA/scripts"
mkdir -p "$H/repoA/scripts/prime_browser_pool.sh"
resolve OVERSIGHT_PRIME_APP=app
eq "a directory named like the script is not resolved" "$OUT" ""
rm -rf "$H/repoA/scripts"

rm -f "$REG"
resolve OVERSIGHT_PRIME_APP=app
eq "missing registry => resolves nothing" "$OUT" ""
has "missing registry is reported" "$ERR" "cannot read the repo registry"
eq "missing registry prints exactly one reason line" "$(nlines "$ERR")" "1"
printf '%s' '{"repos": {"a": {"root": "~/repoA"' > "$REG"
resolve OVERSIGHT_PRIME_APP=app
eq "malformed registry => resolves nothing" "$OUT" ""
has "malformed registry is reported" "$ERR" "cannot read the repo registry"
printf '%s' '{"repos": []}' > "$REG"
resolve OVERSIGHT_PRIME_APP=app
has "wrong registry shape is reported" "$ERR" "has no 'repos' object"

echo "_resolve_prime_sh -- the failures only the shell can see"
# python3 missing: the interpreter is not on PATH at all.
mkdir -p "$WORK/nopy"
printf '%s' '{"repos":{"a":{"root":"~/repoA"}}}' > "$REG"
mkrepo repoA x
resolve OVERSIGHT_PRIME_APP=app PATH="$WORK/nopy"
eq "python3 missing => resolves nothing" "$OUT" ""
[ "$RC" -ne 0 ] && ok "python3 missing => nonzero rc" || bad "python3 missing must exit nonzero"
has "python3 missing is reported" "$ERR" "WRAPPER: prime pre-flight not run - python3 not found"
eq "python3 missing prints exactly one reason line" "$(nlines "$ERR")" "1"

# The lookup dying without saying why (an uncaught exception exits 1 with a traceback).
mkdir -p "$WORK/crashpy"
printf '#!/bin/sh\ncat > /dev/null\necho "Traceback (most recent call last):" >&2\nexit 1\n' > "$WORK/crashpy/python3"
chmod +x "$WORK/crashpy/python3"
resolve OVERSIGHT_PRIME_APP=app PATH="$WORK/crashpy:$PATH"
eq "a crashing lookup => resolves nothing" "$OUT" ""
[ "$RC" -ne 0 ] && ok "a crashing lookup => nonzero rc" || bad "a crash must exit nonzero"
has "a crash is reported by the shell around it" "$ERR" "WRAPPER: prime pre-flight not run - the registry lookup crashed (python3 exit 1)"
eq "a crash adds exactly one WRAPPER line (the traceback is not one)" "$(nlines "$ERR")" "1"

# A NUL in a root (JSON \u0000) used to raise inside os.path.isfile -> a crash; it is now
# just an unusable root, and the good repo still resolves.
printf '%s' '{"repos":{"n":{"root":"~/x\u0000y"},"a":{"root":"~/repoA"}}}' > "$REG"
resolve OVERSIGHT_PRIME_APP=app
eq "a root holding NUL is skipped, the good repo still resolves" "$OUT" "$H/repoA/scripts/prime_browser_pool.sh"
eq "a root holding NUL does not crash the lookup (silent)" "$ERR" ""
resolve OVERSIGHT_PRIME_APP=app OVERSIGHT_PRIME_REPO=n
has "pinning the NUL-root slug is reported as an unusable repo, not a crash" "$ERR" "OVERSIGHT_PRIME_REPO=n is not a repo with a root"

echo "_resolve_claude_bin -- PATH first, no macOS-only path elsewhere"
# claude_bin <PATH value>: runs _resolve_claude_bin under a clean env with that PATH. The shell
# is invoked by absolute path ($BASH) because the restricted PATHs below do not contain bash.
claude_bin() {
  env -i HOME="$H" PATH="$1" "$BASH" -c "$(declare -f _resolve_claude_bin); _resolve_claude_bin"
}
printf '#!/bin/sh\nexit 0\n' > "$WORK/bin/claude"
chmod +x "$WORK/bin/claude"
for os in Darwin Linux; do
  printf '#!/bin/sh\necho %s\n' "$os" > "$WORK/nobin/uname"
  chmod +x "$WORK/nobin/uname"
  eq "claude on PATH wins on $os" "$(claude_bin "$WORK/bin:$WORK/nobin")" "$WORK/bin/claude"
done

printf '#!/bin/sh\necho Darwin\n' > "$WORK/nobin/uname"
eq "macOS, claude not on PATH => the Homebrew path (found or the historical default)" \
  "$(claude_bin "$WORK/nobin")" "/opt/homebrew/bin/claude"

printf '#!/bin/sh\necho Linux\n' > "$WORK/nobin/uname"
mkdir -p "$H/.local/bin"
printf '#!/bin/sh\nexit 0\n' > "$H/.local/bin/claude"
chmod +x "$H/.local/bin/claude"
eq "Linux, claude not on PATH => the native installer's ~/.local/bin" \
  "$(claude_bin "$WORK/nobin")" "$H/.local/bin/claude"
rm -f "$H/.local/bin/claude"
got="$(claude_bin "$WORK/nobin")"
if [ -z "$got" ]; then
  bad "Linux with nothing installed must still print a command name (got nothing)"
elif [ "$got" = "/opt/homebrew/bin/claude" ]; then
  bad "Linux must never fall back to the macOS-only Homebrew path (got $got)"
else
  ok "Linux with nothing installed never falls back to the macOS-only Homebrew path (got '$got')"
fi

echo "source hygiene"
hits="$(grep -Ev '^[[:space:]]*#' "$SRC" | grep -nE 'Desktop/|/Users/' || true)"
eq "no product or home path in the wrapper's active lines" "$hits" ""
n="$(grep -c '^PRIME_SH=' "$SRC")"
eq "PRIME_SH stays one column-0 assignment (the sandbox tests rewrite it by name)" "$n" "1"
n="$(grep -c '^CLAUDE_BIN=' "$SRC")"
eq "CLAUDE_BIN stays one column-0 assignment (the sandbox tests rewrite it by name)" "$n" "1"

echo "end to end -- the real wrapper (a copy, scratch HOME, stub claude, stub priming scripts)"
WRAP="$H/.claude/schedules/run_oversight_job.sh"
cp "$SRC" "$WRAP"
cat > "$WORK/bin/claude" <<'STUB'
#!/bin/bash
python3 -I - "${STUB_HEARTBEAT}" <<'PY'
import datetime
import json
import sys

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump({"job": "t", "started_at": now, "finished_at": now, "exit": 0,
               "cadence": "weekly", "summary": "stub END"}, fh)
PY
STUB
chmod +x "$WORK/bin/claude"
echo "test prompt - never sent to a model" > "$WORK/prompt.txt"
MARK="$WORK/prime_marker"

# stub_repo <name>: a registered-repo layout whose priming script records its slug argument.
stub_repo() {
  mkdir -p "$H/$1/scripts"
  printf '#!/bin/bash\nprintf "%%s\\n" "$1" >> "%s"\nexit 0\n' "$MARK" > "$H/$1/scripts/prime_browser_pool.sh"
  chmod +x "$H/$1/scripts/prime_browser_pool.sh"
}
# run_wrapper <label> <env assignments...>: sets WRC, WERR, WHB (heartbeat file).
run_wrapper() {
  local label="$1"
  shift
  WHB="$H/.claude/schedules/heartbeats/$label.json"
  rm -f "$MARK" "$WHB"
  env -i HOME="$H" PATH="$WORK/bin:$PATH" STUB_HEARTBEAT="$WHB" "$@" \
    bash "${WRAP_USE:-$WRAP}" "$label" "$WORK/prompt.txt" weekly 60 >"$WORK/w.out" 2>"$WORK/w.err" < /dev/null
  WRC=$?
  WERR="$(cat "$WORK/w.err")"
}
hb() {
  python3 -I -c 'import json,sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2], "<ABSENT>"))
except Exception as e:
    print("<UNREADABLE:%s>" % e)' "$WHB" "$1"
}

rm -rf "$H/repoA" "$H/repoB" "$H/repoC"
stub_repo repoA
printf '%s' '{"repos":{"a":{"root":"~/repoA"},"b":{"root":"~/repoB"}}}' > "$REG"
run_wrapper e1 OVERSIGHT_PRIME_APP=exampleapp
eq "E1 wrapper exits 0" "$WRC" "0"
eq "E1 the registry-resolved script ran once with the app slug" "$(cat "$MARK" 2>/dev/null)" "exampleapp"
eq "E1 prime_status=ok" "$(hb prime_status)" "ok"
eq "E1 the session still ran" "$(hb summary)" "stub END"

stub_repo repoB
run_wrapper e2 OVERSIGHT_PRIME_APP=exampleapp
eq "E2 ambiguous => wrapper still exits 0 (non-fatal by design)" "$WRC" "0"
eq "E2 ambiguous => the priming script did not run" "$(cat "$MARK" 2>/dev/null)" ""
eq "E2 ambiguous => prime_status=skipped" "$(hb prime_status)" "skipped"
has "E2 ambiguous => .err.log says why" "$WERR" "more than one registered repo"
eq "E2 ambiguous => exactly one WRAPPER reason line in .err.log" "$(nlines "$WERR")" "1"
eq "E2 the session still ran" "$(hb summary)" "stub END"

run_wrapper e3 OVERSIGHT_PRIME_APP=exampleapp OVERSIGHT_PRIME_REPO=b
eq "E3 explicit slug resolves the ambiguity: the script ran" "$(cat "$MARK" 2>/dev/null)" "exampleapp"
eq "E3 prime_status=ok" "$(hb prime_status)" "ok"

rm -f "$REG"
run_wrapper e4 OVERSIGHT_PRIME_APP=exampleapp
eq "E4 no registry => wrapper exits 0" "$WRC" "0"
eq "E4 no registry => skipped" "$(hb prime_status)" "skipped"
has "E4 no registry => .err.log says why" "$WERR" "cannot read the repo registry"
eq "E4 no registry => exactly one WRAPPER reason line in .err.log" "$(nlines "$WERR")" "1"

# E6: python3 finds the script but the wrapper's own shell rejects it (-x). A copy of the
# wrapper whose PRIME_SH line points at a non-executable file stands in for that disagreement.
printf '%s' '{"repos":{"a":{"root":"~/repoA"}}}' > "$REG"
printf '#!/bin/bash\nexit 0\n' > "$WORK/notexec.sh"
chmod -x "$WORK/notexec.sh"
WRAP_NX="$H/.claude/schedules/run_oversight_job_notexec.sh"
sed -e "s|^PRIME_SH=.*\$|PRIME_SH=\"$WORK/notexec.sh\"|" "$WRAP" > "$WRAP_NX"
n_changed="$(diff "$WRAP" "$WRAP_NX" | grep -c '^[<>]')"
eq "E6 the stand-in wrapper differs from the real one in exactly the PRIME_SH line" "$n_changed" "2"
WRAP_USE="$WRAP_NX" run_wrapper e6 OVERSIGHT_PRIME_APP=exampleapp
eq "E6 wrapper exits 0" "$WRC" "0"
eq "E6 prime_status=skipped" "$(hb prime_status)" "skipped"
has "E6 .err.log says the path is not executable" "$WERR" "WRAPPER: prime pre-flight not run - $WORK/notexec.sh is not executable by the wrapper's shell"
eq "E6 exactly one WRAPPER reason line in .err.log" "$(nlines "$WERR")" "1"
eq "E6 the session still ran" "$(hb summary)" "stub END"

printf '%s' '{"repos":{"a":{"root":"~/repoA"}}}' > "$REG"
run_wrapper e5
eq "E5 not opted in => the priming script did not run" "$(cat "$MARK" 2>/dev/null)" ""
eq "E5 not opted in => prime_status=skipped" "$(hb prime_status)" "skipped"
case "$WERR" in
  *"prime pre-flight"*) bad "E5 a job that did not opt in must print no prime diagnostic (got: $WERR)" ;;
  *) ok "E5 a job that did not opt in prints no prime diagnostic" ;;
esac

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
