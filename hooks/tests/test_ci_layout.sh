#!/usr/bin/env bash
# Safety-rail tests for scripts/ci_layout.sh.
#
# WHY THIS EXISTS: ci_layout.sh runs `git archive HEAD | tar -x` into
# $HOME/.claude of a layout directory and, on --refresh, deletes the old copy
# first. Pointed at the wrong place (a mis-set HOME, a symlink, a directory it
# did not create) that would overwrite or delete a live runtime and every
# other session's uncommitted work. Each case below asserts one refusal that
# stops that, plus the paired success path that proves the refusal is not just
# "the script never works". Intended behaviour is taken from the script's own
# header ("SAFETY RAILS"), not from its current output.
#
# Everything runs in a throwaway world under a directory this test creates,
# with a FAKE home standing in for the real one (HOME is overridden for the
# script, which treats $HOME/.claude as protected) and, where the passwd database
# matters, a python3 shim that answers that one query with a fake home. The real
# home is never named. The test never runs pip or sudo for real (--skip-install, or
# stub interpreters and PATH shims that record their calls) and never runs the
# suite (--run uses a tiny stub repo).
#
# Run: bash hooks/tests/test_ci_layout.sh
# Override the script under test: CI_LAYOUT_SCRIPT=/path/to/ci_layout.sh
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRIPT="${CI_LAYOUT_SCRIPT:-$HERE/../../scripts/ci_layout.sh}"
[ -f "$SCRIPT" ] || { echo "FATAL: $SCRIPT not found"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "FATAL: git not found"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 not found"; exit 1; }

PASS=0
FAIL=0
ok() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
check() { # NAME CMD... : pass when the command succeeds
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then ok "$name"; else bad "$name"; fi
}
eq() { # NAME GOT WANT
  if [ "$2" = "$3" ]; then ok "$1 (got $2)"; else bad "$1 (got '$2', want '$3')"; fi
}
has() { # NAME TEXT PATTERN : pass when TEXT matches the extended regex
  if printf '%s\n' "$2" | grep -Eq -- "$3"; then ok "$1"; else bad "$1 (no match for /$3/ in: $(printf '%s' "$2" | head -c 300))"; fi
}
lacks() { # NAME TEXT PATTERN
  if printf '%s\n' "$2" | grep -Eq -- "$3"; then bad "$1 (unexpected match for /$3/)"; else ok "$1"; fi
}

# --- a throwaway world, outside /tmp (the script refuses /tmp homes) -----------

PARENT="${CI_LAYOUT_TEST_BASE:-${HOME:-/nonexistent}/.cache}"
mkdir -p "$PARENT" || { echo "FATAL: cannot create $PARENT"; exit 1; }
BASE="$(mktemp -d "$PARENT/ci-layout-test.XXXXXX")" || { echo "FATAL: mktemp failed"; exit 1; }
BASE="$(cd "$BASE" && pwd -P)"
case "$BASE" in
  /tmp/* | /private/tmp/*) echo "FATAL: test base $BASE is under /tmp; set CI_LAYOUT_TEST_BASE"; exit 1 ;;
esac
PROBE_TMP="/tmp/ci-layout-test-probe-$$"
PROBE_PRIVATE_TMP="/private/tmp/ci-layout-test-probe-$$"
cleanup() {
  case "$BASE" in
    */ci-layout-test.*) rm -rf "$BASE" ;;
  esac
  rm -rf "$PROBE_TMP" "$PROBE_PRIVATE_TMP"
}
trap cleanup EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
# Run from inside a git hook, GIT_DIR and friends would point every throwaway
# repo call below at the hook's repository. Drop them all.
for _v in $(git rev-parse --local-env-vars 2>/dev/null); do unset "$_v"; done

FAKEHOME="$BASE/fakehome"
CWD="$BASE/cwd"
mkdir -p "$FAKEHOME/.claude/sub" "$CWD"
echo keep >"$FAKEHOME/.claude/sentinel"

# Only the protected tree is snapshotted: on macOS Apple's own python3 writes its
# bytecode cache under $HOME/Library/Caches, which is the interpreter's doing and
# not the script's.
fake_snapshot() { (cd "$FAKEHOME" && find .claude | sort | tr '\n' '|' && cat .claude/sentinel); }
SNAP_BEFORE="$(fake_snapshot)"

# A tiny source repo that carries its own copy of the script (the script archives
# the repo it lives in).
git_in() { # DIR ARGS...
  local d="$1"
  shift
  git -C "$d" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false "$@"
}
make_repo() { # DIR
  local d="$1"
  mkdir -p "$d/scripts" "$d/hooks" "$d/live-testing" "$d/knowledge"
  cp "$SCRIPT" "$d/scripts/ci_layout.sh"
  echo v1 >"$d/hooks/x.py"
  echo gone >"$d/hooks/gone.py"
  echo '{"_example": true}' >"$d/live-testing/allowlist.example.json"
  echo '{"boards": []}' >"$d/knowledge/protected_boards.example.json"
  git init -q "$d" 2>/dev/null
  git_in "$d" add scripts hooks live-testing knowledge
  git_in "$d" commit -q -m init
}
SRC="$BASE/src"
make_repo "$SRC"
CL="$SRC/scripts/ci_layout.sh"

RC=0
OUT=""
cl() { # ARGS... -> RC, OUT. Neutral cwd, fake HOME, no stdin.
  OUT="$(cd "$CWD" && env HOME="$FAKEHOME" bash "$CL" "$@" </dev/null 2>&1)"
  RC=$?
}

echo "usage and syntax"
check "script parses" bash -n "$SCRIPT"
if command -v shellcheck >/dev/null 2>&1; then
  check "script is shellcheck-clean at warning level" shellcheck -S warning "$SCRIPT"
else
  echo "  SKIP  shellcheck not installed"
fi
cl --help
eq "--help exits 0" "$RC" 0
has "--help documents the flags" "$OUT" '--refresh'
has "--help documents --system-deps" "$OUT" '--system-deps'
cl --bogus --home "$BASE/usage/home"
eq "unknown flag is a usage error" "$RC" 2
cl --home
eq "--home without a value is a usage error" "$RC" 2
cl --min-hooks abc --home "$BASE/usage/home"
eq "non-numeric --min-hooks is a usage error" "$RC" 2
check "usage errors create nothing" test ! -e "$BASE/usage"

echo "rail: never the real ~/.claude (resolved paths, any relationship)"
cl --home "$FAKEHOME" --skip-install
eq "home that CONTAINS the real .claude is refused" "$RC" 3
has "  and says why" "$OUT" 'real ~/.claude'
cl --home "$FAKEHOME/.claude" --skip-install
eq "home that IS the real .claude is refused" "$RC" 3
has "  and says why" "$OUT" 'real ~/.claude'
cl --home "$FAKEHOME/.claude/sub/home" --skip-install
eq "home INSIDE the real .claude is refused" "$RC" 3
has "  and says why" "$OUT" 'real ~/.claude'
check "  and nothing was created inside it" test ! -e "$FAKEHOME/.claude/sub/home"
cl --home "$BASE" --skip-install
eq "an ancestor of the real .claude is refused" "$RC" 3
ln -s "$FAKEHOME/.claude" "$BASE/via_link"
cl --home "$BASE/via_link/sub/home" --skip-install
eq "a path that reaches it through a symlinked ancestor is refused" "$RC" 3
has "  and says why" "$OUT" 'real ~/.claude'
ln -s "$FAKEHOME/.claude" "$BASE/sneaky"
cl --home "$BASE/sneaky" --skip-install
eq "a home that is a symlink to it is refused" "$RC" 3
cl --home "$FAKEHOME/home" --skip-install
eq "a layout ROOT that contains the real .claude is refused" "$RC" 3
has "  and names the layout root" "$OUT" 'layout root'
check "  and nothing was created beside it" test ! -e "$FAKEHOME/home"

# The passwd-database home is protected too, independent of $HOME (HOME is what a
# mis-set environment gets wrong). The script reads it with a one-line python3
# query; a shim answers exactly that query with a FAKE passwd home and passes
# everything else to the real python3, so this case also stays in the throwaway
# world: with the protection removed it would extract into the fake, never the real.
REAL_PYTHON3="$(command -v python3)"
FAKEPW="$BASE/fakepw"
mkdir -p "$FAKEPW/.claude/sub" "$BASE/shim/pwbin"
cat >"$BASE/shim/pwbin/python3" <<SHIM
#!/bin/sh
case "\$*" in *pwd.getpwuid*) echo "$FAKEPW"; exit 0 ;; esac
exec "$REAL_PYTHON3" "\$@"
SHIM
chmod +x "$BASE/shim/pwbin/python3"
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" PATH="$BASE/shim/pwbin:$PATH" bash "$CL" --home "$FAKEPW/.claude/sub/home" --skip-install </dev/null 2>&1)"
RC=$?
eq "a home inside the passwd-database home's .claude is refused even when HOME points elsewhere" "$RC" 3
has "  and says why" "$OUT" 'real ~/.claude'
check "  and nothing was created inside it" test ! -e "$FAKEPW/.claude/sub/home"
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" PATH="$BASE/shim/pwbin:$PATH" bash "$CL" --home "$FAKEPW" --skip-install </dev/null 2>&1)"
RC=$?
eq "a home that contains the passwd-database home's .claude is refused" "$RC" 3

# File identity: spellings of the same directory that no string compare relates.
echo "rail: file identity (aliases of the protected directory)"
if [ -d "$FAKEHOME/.CLAUDE" ]; then
  cl --home "$FAKEHOME/.CLAUDE/sub/home" --skip-install
  eq "a case variant of the protected path is refused (case-insensitive filesystem)" "$RC" 3
  has "  by file identity" "$OUT" 'file identity'
  check "  and nothing was created inside it" test ! -e "$FAKEHOME/.claude/sub/home"
  cl --home "$FAKEHOME/.CLAUDE" --skip-install
  eq "the protected directory itself under a case variant is refused" "$RC" 3
  cl --home "$BASE/FAKEHOME" --skip-install
  eq "a case variant of a directory that CONTAINS it is refused" "$RC" 3
  OUT="$(cd "$FAKEHOME/.CLAUDE/sub" && env HOME="$FAKEHOME" bash "$CL" --home "$BASE/okhome2/home" --skip-install </dev/null 2>&1)"
  RC=$?
  eq "a cwd inside it under a case variant is refused" "$RC" 3
else
  echo "  SKIP  case-variant aliases (this filesystem is case-sensitive)"
fi
FIRM="/System/Volumes/Data$FAKEHOME"
if [ -d "$FIRM/.claude" ]; then
  cl --home "$FIRM/.claude/sub/home" --skip-install
  eq "a macOS firmlink spelling of a path inside it is refused" "$RC" 3
  has "  by file identity" "$OUT" 'file identity'
  check "  and nothing was created inside it" test ! -e "$FAKEHOME/.claude/sub/home"
  cl --home "$FIRM" --skip-install
  eq "a firmlink spelling of a directory that CONTAINS it is refused" "$RC" 3
  OUT="$(cd "$FIRM/.claude/sub" && env HOME="$FAKEHOME" bash "$CL" --home "$BASE/okhome3/home" --skip-install </dev/null 2>&1)"
  RC=$?
  eq "a cwd inside it under a firmlink spelling is refused" "$RC" 3
else
  echo "  SKIP  firmlink aliases (no /System/Volumes/Data on this system)"
fi

check "none of the above wrote into the (fake) real home" test "$SNAP_BEFORE" = "$(fake_snapshot)"

echo "rail: not from inside the real ~/.claude"
OUT="$(cd "$FAKEHOME/.claude/sub" && env HOME="$FAKEHOME" bash "$CL" --home "$BASE/okhome/home" --skip-install </dev/null 2>&1)"
RC=$?
eq "a cwd inside the real .claude is refused" "$RC" 3
has "  and says why" "$OUT" 'current directory'
check "  and nothing was created" test ! -e "$BASE/okhome"

echo "rail: HOME outside /tmp"
cl --home "$PROBE_TMP/home" --skip-install
eq "a /tmp home is refused" "$RC" 3
has "  and says why" "$OUT" '/tmp'
cl --home "$PROBE_PRIVATE_TMP/home" --skip-install
eq "a /private/tmp home is refused" "$RC" 3
check "  and neither was created" test ! -e "$PROBE_TMP" -a ! -e "$PROBE_PRIVATE_TMP"
if [ -d /System/Volumes/Data/private/tmp ]; then
  cl --home "/System/Volumes/Data/private/tmp/ci-layout-test-probe-$$/home" --skip-install
  eq "a firmlink spelling of /private/tmp is refused" "$RC" 3
  check "  and was not created" test ! -e "$PROBE_PRIVATE_TMP"
else
  echo "  SKIP  /tmp firmlink alias (no /System/Volumes/Data on this system)"
fi
if [ -d /TMP ]; then
  cl --home "/TMP/ci-layout-test-probe-$$/home" --skip-install
  eq "a case variant of /tmp is refused" "$RC" 3
  check "  and was not created" test ! -e "$PROBE_TMP"
else
  echo "  SKIP  /tmp case alias (this filesystem is case-sensitive)"
fi

echo "rail: a dedicated layout root"
cl --home "$BASE/okroot/notnamedhome" --skip-install
eq "a home not named 'home' is refused" "$RC" 3
check "  and nothing was created" test ! -e "$BASE/okroot"

echo "rail: only a directory this script made"
mkdir -p "$BASE/nomarker/home/.claude"
echo precious >"$BASE/nomarker/home/.claude/precious"
echo keep >"$BASE/nomarker/home/keep.txt"
cl --home "$BASE/nomarker/home" --skip-install
eq "a non-empty home without the marker is refused" "$RC" 3
has "  and names the marker" "$OUT" '\.ci-layout'
cl --home "$BASE/nomarker/home" --skip-install --refresh
eq "  --refresh does not bypass the marker" "$RC" 3
check "  its files survive" test -f "$BASE/nomarker/home/keep.txt" -a -f "$BASE/nomarker/home/.claude/precious"
check "  and no marker was planted in it" test ! -e "$BASE/nomarker/home/.ci-layout"

mkdir -p "$BASE/realdir/home" "$BASE/symroot"
ln -s "$BASE/realdir/home" "$BASE/symroot/home"
cl --home "$BASE/symroot/home" --skip-install
eq "a home that is a symlink is refused" "$RC" 3
has "  and says why" "$OUT" 'symlink'

SRCW="$BASE/srcw/home/.claude"
make_repo "$SRCW"
# A marker and --refresh remove every other obstacle: only the overlap rail is left
# between the script and deleting the checkout it is about to archive.
echo "ci-layout v1" >"$BASE/srcw/home/.ci-layout"
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" bash "$SRCW/scripts/ci_layout.sh" --home "$BASE/srcw/home" --skip-install --refresh </dev/null 2>&1)"
RC=$?
eq "a layout that would overlap the source checkout is refused" "$RC" 3
has "  and says why" "$OUT" 'source checkout'
check "  and the source checkout is intact" test -f "$SRCW/hooks/x.py" -a -d "$SRCW/.git"

mkdir -p "$BASE/nogit/scripts"
cp "$SCRIPT" "$BASE/nogit/scripts/ci_layout.sh"
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" bash "$BASE/nogit/scripts/ci_layout.sh" --home "$BASE/nogit_out/home" --skip-install </dev/null 2>&1)"
RC=$?
eq "a source that is not a git repository fails" "$RC" 1
has "  and says so" "$OUT" 'not a git repository'
check "  without creating a layout" test ! -e "$BASE/nogit_out"

echo "success path: build, seed, reuse, refuse stale, refresh"
POS="$BASE/pos/home"
echo untracked >"$SRC/uncommitted.txt"
cl --home "$POS" --skip-install
eq "a fresh layout builds" "$RC" 0
HEAD1="$(git_in "$SRC" rev-parse HEAD)"
eq "the marker records the commit" "$(sed -n 's/^commit=//p' "$POS/.ci-layout")" "$HEAD1"
eq "HEAD is extracted into <home>/.claude" "$(cat "$POS/.claude/hooks/x.py" 2>/dev/null)" v1
check "projects/ exists" test -d "$POS/.claude/projects"
check "uncommitted files are not in the layout" test ! -e "$POS/.claude/uncommitted.txt"
check "the allowlist is seeded from its example" cmp -s "$POS/.claude/live-testing/allowlist.example.json" "$POS/.claude/live-testing/allowlist.json"
has "  and the seeding is announced" "$OUT" 'seeded live-testing/allowlist\.json'
has "  and the printed environment forces TZ=UTC (as on the CI runners)" "$OUT" 'export TZ=UTC'
check "protected_boards.json is seeded from its example" cmp -s "$POS/.claude/knowledge/protected_boards.example.json" "$POS/.claude/knowledge/protected_boards.json"
check "--skip-install creates no venv" test ! -e "$BASE/pos/venv"
check "the fake real home is still untouched" test "$SNAP_BEFORE" = "$(fake_snapshot)"

echo local >"$POS/.claude/local_marker"
cl --home "$POS" --skip-install
eq "re-running at the same commit succeeds" "$RC" 0
has "  by reusing the layout" "$OUT" 'reusing'
check "  without re-extracting" test -f "$POS/.claude/local_marker"

# commit 2: modify x.py, remove gone.py, track a real allowlist.json, drop the boards example
echo v2 >"$SRC/hooks/x.py"
git_in "$SRC" rm -q hooks/gone.py knowledge/protected_boards.example.json
echo '{"real": true}' >"$SRC/live-testing/allowlist.json"
git_in "$SRC" add hooks/x.py live-testing/allowlist.json
git_in "$SRC" commit -q -m second
HEAD2="$(git_in "$SRC" rev-parse HEAD)"

cl --home "$POS" --skip-install
eq "a layout built from an older commit is refused without --refresh" "$RC" 3
has "  and points at --refresh" "$OUT" '--refresh'
check "  and left untouched" test -f "$POS/.claude/local_marker"

mkdir -p "$BASE/victim"
echo precious >"$BASE/victim/precious"
ln -s "$BASE/victim" "$POS/.claude/extlink"
echo mine >"$POS/keepme"
cl --home "$POS" --skip-install --refresh
eq "--refresh re-extracts" "$RC" 0
eq "  the marker follows HEAD" "$(sed -n 's/^commit=//p' "$POS/.ci-layout")" "$HEAD2"
eq "  new content is present" "$(cat "$POS/.claude/hooks/x.py")" v2
check "  files removed upstream are gone" test ! -e "$POS/.claude/hooks/gone.py"
check "  the old tree was replaced" test ! -e "$POS/.claude/local_marker"
check "  a symlink inside the old tree was not followed" test -f "$BASE/victim/precious"
check "  the symlink itself is gone" test ! -e "$POS/.claude/extlink"
check "  files outside .claude in the layout home survive" test -f "$POS/keepme"
eq "  a tracked allowlist.json is not overwritten by the seed" "$(cat "$POS/.claude/live-testing/allowlist.json")" '{"real": true}'
lacks "  and is not announced as seeded" "$OUT" 'seeded live-testing/allowlist\.json'
check "  no example, no seed (and no noise)" test ! -e "$POS/.claude/knowledge/protected_boards.json"
lacks "  nothing is said about the missing example" "$OUT" 'protected_boards'

echo "rail: a symlinked marker is never followed"
mkdir -p "$BASE/mlink/home"
echo precious >"$BASE/outside_marker"
ln -s "$BASE/outside_marker" "$BASE/mlink/home/.ci-layout"
cl --home "$BASE/mlink/home" --skip-install
eq "a .ci-layout marker that is a symlink is refused" "$RC" 3
has "  and says why" "$OUT" 'symlink'
eq "  and its target was not rewritten" "$(cat "$BASE/outside_marker")" precious

echo "rail: the layout root's siblings are only touched once the root is claimed"
for kind in venv pytest-tmp; do
  mkdir -p "$BASE/root_$kind/$kind"
  echo mine >"$BASE/root_$kind/$kind/keep"
  cl --home "$BASE/root_$kind/home" --skip-install
  eq "an unclaimed root that already has $kind/ is refused" "$RC" 3
  has "  and says why" "$OUT" "$kind.*\.ci-layout-root"
  eq "  its files survive" "$(cat "$BASE/root_$kind/$kind/keep")" mine
  check "  and nothing was created beside it" test ! -e "$BASE/root_$kind/home" -a ! -e "$BASE/root_$kind/.ci-layout-root"
done
mkdir -p "$BASE/root_junit"
echo mine >"$BASE/root_junit/junit-hooks-tests.xml"
cl --home "$BASE/root_junit/home" --skip-install
eq "an unclaimed root with an old junit file is refused" "$RC" 3
eq "  and it survives" "$(cat "$BASE/root_junit/junit-hooks-tests.xml")" mine
mkdir -p "$BASE/root_marker_link"
ln -s "$BASE/outside_marker" "$BASE/root_marker_link/.ci-layout-root"
cl --home "$BASE/root_marker_link/home" --skip-install
eq "a root marker that is a symlink is refused" "$RC" 3
mkdir -p "$BASE/root_other"
echo x >"$BASE/root_other/unrelated.txt"
cl --home "$BASE/root_other/home" --skip-install
eq "a root with only unrelated files is claimed (recovery pair)" "$RC" 0
check "  the root now carries its marker" test -f "$BASE/root_other/.ci-layout-root"
eq "  and the unrelated file is untouched" "$(cat "$BASE/root_other/unrelated.txt")" x
mkdir -p "$BASE/venv_target"
echo mine >"$BASE/venv_target/keep"
ln -s "$BASE/venv_target" "$BASE/root_other/venv"
cl --home "$BASE/root_other/home" --skip-install
eq "a venv that is a symlink is refused even in a claimed root" "$RC" 3
eq "  and its target is untouched" "$(cat "$BASE/venv_target/keep")" mine
rm -f "$BASE/root_other/venv"
ln -s "$BASE/venv_target" "$BASE/root_other/pytest-tmp"
cl --home "$BASE/root_other/home" --skip-install
eq "a pytest-tmp that is a symlink is refused even in a claimed root" "$RC" 3
rm -f "$BASE/root_other/pytest-tmp"

echo "seeding never writes through a symlink"
SYMSRC="$BASE/symsrc"
make_repo "$SYMSRC"
ln -s "$BASE/dangling_target" "$SYMSRC/live-testing/allowlist.json"
git_in "$SYMSRC" add live-testing/allowlist.json
git_in "$SYMSRC" commit -q -m "tracked dangling symlink"
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" bash "$SYMSRC/scripts/ci_layout.sh" --home "$BASE/symseed/home" --skip-install </dev/null 2>&1)"
RC=$?
eq "a layout whose allowlist.json is a tracked dangling symlink still builds" "$RC" 0
check "  the symlink target was not created by the seed" test ! -e "$BASE/dangling_target"
has "  and the skip is announced" "$OUT" 'not seeding live-testing/allowlist\.json'
check "  other seeds still happen" test -f "$BASE/symseed/home/.claude/knowledge/protected_boards.json"

echo "git environment: a hook's GIT_DIR must not redirect the archive"
DECOY="$BASE/decoy"
make_repo "$DECOY"
echo decoy >"$DECOY/hooks/x.py"
git_in "$DECOY" add hooks/x.py
git_in "$DECOY" commit -q -m decoy
OUT="$(cd "$CWD" && env HOME="$FAKEHOME" GIT_DIR="$DECOY/.git" GIT_WORK_TREE="$DECOY" GIT_INDEX_FILE="$DECOY/.git/index" bash "$CL" --home "$BASE/gitenv/home" --skip-install </dev/null 2>&1)"
RC=$?
eq "the layout builds with GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE set" "$RC" 0
eq "  from the script's own repo, not the decoy" "$(cat "$BASE/gitenv/home/.claude/hooks/x.py")" v2
eq "  and the marker records that repo's HEAD" "$(sed -n 's/^commit=//p' "$BASE/gitenv/home/.ci-layout")" "$(git_in "$SRC" rev-parse HEAD)"

echo "the source repository is only read (it may be a live checkout)"
# touch makes a tracked file's stat data stale, which is exactly when a plain
# `git status` rewrites .git/index to refresh it; --no-optional-locks must not.
touch "$SRC/hooks/x.py"
INDEX_BEFORE="$(cksum <"$SRC/.git/index")"
cl --home "$BASE/readonly_src/home" --skip-install
eq "building a layout succeeds" "$RC" 0
eq "  and leaves the source repo's index byte-identical" "$(cksum <"$SRC/.git/index")" "$INDEX_BEFORE"

echo "rail: never follow a symlinked .claude"
SYM="$BASE/sympos/home"
cl --home "$SYM" --skip-install
eq "a second layout builds" "$RC" 0
rm -rf "$SYM/.claude"
mkdir -p "$BASE/victim3"
echo precious >"$BASE/victim3/precious"
ln -s "$BASE/victim3" "$SYM/.claude"
cl --home "$SYM" --skip-install --refresh
eq "a symlinked .claude is refused even with the marker and --refresh" "$RC" 3
has "  and says why" "$OUT" 'symlink'
check "  and its target was not touched" test -f "$BASE/victim3/precious"

echo "packages: ci_layout.sh installs exactly what pyproject.toml declares"
PYPROJECT="$HERE/../../pyproject.toml"
if [ ! -f "$PYPROJECT" ]; then
  bad "pyproject.toml is missing next to the script's checkout ($PYPROJECT)"
else
  OUT="$(python3 - "$SCRIPT" "$PYPROJECT" 2>&1 <<'PY'
import re
import sys

try:
    import tomllib
except ImportError:
    sys.exit(77)

script, pyproject = sys.argv[1:3]
m = re.search(r"^PACKAGES=\((.*?)\)[ \t]*$", open(script).read(), re.M)
if not m:
    print("no PACKAGES=(...) array found in the script")
    sys.exit(1)
installed = sorted(re.findall(r'"([^"]+)"', m.group(1)))
with open(pyproject, "rb") as fh:
    extras = tomllib.load(fh)["project"]["optional-dependencies"]
declared = sorted(extras["test"] + extras["lint"])
if installed != declared:
    print("script installs %s but pyproject declares %s" % (installed, declared))
    sys.exit(1)
if "detect-secrets==1.5.0" not in installed:
    print("detect-secrets is not pinned to 1.5.0, the version scripts/codex_review.sh documents")
    sys.exit(1)
PY
)"
  RC=$?
  if [ "$RC" -eq 77 ]; then
    echo "  SKIP  package parity needs tomllib (Python 3.11+)"
  else
    eq "the installed package list equals pyproject's test+lint extras" "$RC" 0
    if [ "$RC" -ne 0 ]; then echo "        $OUT"; fi
  fi
fi

echo "privilege: nothing is escalated without --system-deps or CI=true"
# Stub interpreters and PATH shims that record their calls. fakepy stands in for the
# venv interpreter (version queries succeed, `-m venv` makes a copy of itself, `-m pip`
# succeeds); fakesys stands in for /usr/bin/python3 (jsonschema is importable once
# something has run `-m pip` or apt-get). Nothing here touches the network or the OS.
SH="$BASE/shim/sys"
mkdir -p "$SH"
cat >"$SH/sudo" <<'SHIM'
#!/bin/sh
echo "sudo $*" >>"$SHIM_LOG"
[ "$1" = "-n" ] && shift
[ "$1" = "true" ] && exit 0
exec "$@"
SHIM
cat >"$SH/apt-get" <<'SHIM'
#!/bin/sh
echo "apt-get $*" >>"$SHIM_LOG"
touch "$SHIM_STATE/jsonschema_installed"
SHIM
cat >"$SH/uname" <<'SHIM'
#!/bin/sh
echo "$FAKE_UNAME"
SHIM
cat >"$SH/fakesys" <<'SHIM'
#!/bin/sh
echo "fakesys $*" >>"$SHIM_LOG"
case "$*" in
  *"import jsonschema"*) [ -f "$SHIM_STATE/jsonschema_installed" ]; exit $? ;;
  *"-m pip"*) touch "$SHIM_STATE/jsonschema_installed"; exit 0 ;;
esac
exit 0
SHIM
cat >"$SH/fakepy" <<'SHIM'
#!/bin/sh
case "$*" in
  *"-m venv"*) mkdir -p "$3/bin"; cp "$0" "$3/bin/python"; chmod +x "$3/bin/python"; exit 0 ;;
  *"-m pip"*) exit 0 ;;
  *"version_info[:2]"*) echo 3.13; exit 0 ;;
esac
exit 0
SHIM
chmod +x "$SH"/*
for kind in iso plain; do
  make_repo "$BASE/sys_$kind"
  # shellcheck disable=SC2016  # the dollar sign is the literal text the script greps for
  if [ "$kind" = iso ]; then
    printf '_PYTHON_BIN="/usr/bin/python3"\n"$_PYTHON_BIN" -I -c pass\n' >"$BASE/sys_$kind/scripts/codex_review.sh"
  else
    printf '_PYTHON_BIN="/usr/bin/python3"\n"$_PYTHON_BIN" -c pass\n' >"$BASE/sys_$kind/scripts/codex_review.sh"
  fi
  git_in "$BASE/sys_$kind" add scripts/codex_review.sh
  git_in "$BASE/sys_$kind" commit -q -m "codex stub"
done
SYS_LAYOUTS=0
SYS_ENV=()
syscl() { # UNAME KIND ARGS... -> RC, OUT, SHIM_LOG, SHIM_STATE (a fresh state per call)
  local un="$1" kind="$2"
  shift 2
  SYS_LAYOUTS=$((SYS_LAYOUTS + 1))
  SHIM_STATE="$BASE/shim/state_$SYS_LAYOUTS"
  SHIM_LOG="$BASE/shim/log_$SYS_LAYOUTS"
  mkdir -p "$SHIM_STATE"
  : >"$SHIM_LOG"
  [ -z "${SYS_PRESEED:-}" ] || touch "$SHIM_STATE/jsonschema_installed"
  OUT="$(cd "$CWD" && env -u CI HOME="$FAKEHOME" PATH="$SH:$PATH" FAKE_UNAME="$un" SHIM_LOG="$SHIM_LOG" \
    SHIM_STATE="$SHIM_STATE" CI_LAYOUT_SYSTEM_PYTHON="$SH/fakesys" ${SYS_ENV[@]+"${SYS_ENV[@]}"} \
    bash "$BASE/sys_$kind/scripts/ci_layout.sh" --home "$BASE/sysl_$SYS_LAYOUTS/home" --python "$SH/fakepy" "$@" </dev/null 2>&1)"
  RC=$?
}
escalated() { grep -Eq '^(sudo|apt-get) ' "$SHIM_LOG"; }
IS_ROOT=0
[ "$(id -u)" = 0 ] && IS_ROOT=1

syscl Linux plain
eq "Linux, default flags: the build succeeds" "$RC" 0
check "  and neither sudo nor apt-get was ever called" test ! -s "$SHIM_LOG" -o -z "$(grep -E '^(sudo|apt-get) ' "$SHIM_LOG")"
has "  the exact command is printed instead" "$OUT" 'ACTION NEEDED: sudo apt-get install -y python3-jsonschema'
has "  with the way to opt in" "$OUT" '--system-deps'
syscl Linux plain --system-deps
eq "Linux, --system-deps: the build succeeds" "$RC" 0
check "  and apt-get ran" grep -q '^apt-get install -y python3-jsonschema' "$SHIM_LOG"
if [ "$IS_ROOT" -eq 0 ]; then check "  through sudo -n" grep -q '^sudo -n apt-get' "$SHIM_LOG"; fi
has "  and jsonschema is reported importable" "$OUT" 'jsonschema is importable'
SYS_ENV=(CI=true)
syscl Linux plain
check "Linux, CI=true: apt-get ran without the flag" grep -q '^apt-get install' "$SHIM_LOG"
SYS_ENV=(CI=false)
syscl Linux plain
check "Linux, CI=false: nothing escalated" test -z "$(grep -E '^(sudo|apt-get) ' "$SHIM_LOG")"
SYS_ENV=()
SYS_PRESEED=1 syscl Linux plain --system-deps
check "Linux, jsonschema already importable: nothing escalated even with --system-deps" test -z "$(grep -E '^(sudo|apt-get) ' "$SHIM_LOG")"
has "  and says so" "$OUT" 'already importable'

syscl Darwin iso
eq "macOS isolated, default flags: the build succeeds" "$RC" 0
check "  and nothing was escalated" test -z "$(grep -E '^(sudo|apt-get) ' "$SHIM_LOG")"
check "  and pip was not run for the system interpreter" test -z "$(grep -E '^fakesys -m pip' "$SHIM_LOG")"
has "  the sudo command is printed instead" "$OUT" 'ACTION NEEDED.*sudo .*-m pip install jsonschema'
syscl Darwin iso --system-deps
eq "macOS isolated, --system-deps: the build succeeds" "$RC" 0
check "  and pip ran for the system interpreter" grep -q '^fakesys -m pip install' "$SHIM_LOG"
if [ "$IS_ROOT" -eq 0 ]; then check "  through sudo -n" grep -q '^sudo -n ' "$SHIM_LOG"; fi
syscl Darwin plain --system-deps
check "macOS non-isolated: the per-user install needs no escalation even with --system-deps" grep -q 'fakesys -m pip install .*--user' "$SHIM_LOG"
check "  and nothing was escalated" test -z "$(grep -E '^(sudo|apt-get) ' "$SHIM_LOG")"

echo "--run accounting (a tiny repo and a stub venv; the real suite is never run here)"
# --run must exit non-zero on a failing test, on a location that ran zero tests, and
# on a count below the threshold, and zero only when everything passed. The venv is
# a bare one that borrows this interpreter's pytest through a .pth file, so no
# network and no pip are involved.
OUTER_SITE="$(python3 -c 'import os, pytest; print(os.path.dirname(os.path.dirname(pytest.__file__)))' 2>/dev/null)" || OUTER_SITE=""
if [ -z "$OUTER_SITE" ] || ! command -v node >/dev/null 2>&1; then
  echo "  SKIP  --run accounting needs pytest importable by python3 and node on PATH"
else
  RS="$BASE/runsrc"
  RH="$BASE/runpos/home"
  mkdir -p "$RS/hooks/tests" "$RS/tools/gtm/tests" "$RS/workflows/tests" "$RS/scripts"
  cp "$SCRIPT" "$RS/scripts/ci_layout.sh"
  printf 'def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n' >"$RS/hooks/tests/test_ok.py"
  printf '#!/bin/sh\nexit 0\n' >"$RS/hooks/tests/ok.sh"
  # shellcheck disable=SC2016  # ${TZ} must reach the written script unexpanded
  printf '#!/bin/sh\n[ "${TZ:-}" = "UTC" ] || { echo "TZ is [${TZ:-}], want UTC" >&2; exit 1; }\n' >"$RS/hooks/tests/tz.sh"
  printf 'def test_g():\n    assert True\n' >"$RS/tools/gtm/tests/test_ok.py"
  printf "import { test } from 'node:test'\ntest('a', () => {})\ntest('b', () => {})\n" >"$RS/workflows/tests/test_issue_wheel_triage.mjs"
  git init -q "$RS" 2>/dev/null
  git_in "$RS" add scripts hooks tools workflows
  git_in "$RS" commit -q -m init
  run_cl() { # ARGS... -> RC, OUT (from the stub repo's own copy of the script)
    OUT="$(cd "$CWD" && env HOME="$FAKEHOME" TZ=America/Denver bash "$RS/scripts/ci_layout.sh" --home "$RH" --skip-install "$@" </dev/null 2>&1)"
    RC=$?
  }
  run_cl --run
  eq "--run with --skip-install and no venv fails clearly" "$RC" 1
  has "  and says how to fix it" "$OUT" 'needs an existing venv'

  python3 -m venv --without-pip "$BASE/runpos/venv" >/dev/null 2>&1 || mkdir -p "$BASE/runpos"
  SITE_DIR="$(find "$BASE/runpos/venv/lib" -maxdepth 2 -type d -name site-packages 2>/dev/null | head -n 1)"
  if [ -z "$SITE_DIR" ]; then
    echo "  SKIP  could not create a stub venv"
  else
    echo "$OUTER_SITE" >"$SITE_DIR/outer.pth"
    run_cl --run --min-hooks 2 --min-gtm 1 --min-node 2
    eq "--run passes when every location passes and meets its minimum" "$RC" 0
    has "  and says so" "$OUT" 'all checks passed'
    has "  the counts are reported" "$OUT" 'hooks/tests +2 executed'
    has "  the run exports TZ=UTC even though the invoker's TZ was America/Denver" "$OUT" 'ok +hooks/tests/tz\.sh'
    run_cl --run --min-hooks 3 --min-gtm 1 --min-node 2
    eq "--run fails when a location ran fewer tests than required" "$RC" 1
    has "  and names the shortfall" "$OUT" 'need at least 3'
    run_cl --run --min-hooks 2 --min-gtm 1 --min-node 3
    eq "--run fails when node ran fewer passing tests than required" "$RC" 1

    printf 'def test_bad():\n    assert False\n' >"$RS/tools/gtm/tests/test_bad.py"
    git_in "$RS" add tools/gtm/tests/test_bad.py
    git_in "$RS" commit -q -m failing
    run_cl --refresh --run --min-hooks 2 --min-gtm 1 --min-node 2
    eq "--run fails when a test fails" "$RC" 1
    has "  and reports the failure" "$OUT" 'FAIL +tools/gtm/tests'
    git_in "$RS" rm -q tools/gtm/tests/test_bad.py
    git_in "$RS" commit -q -m unfail

    printf '#!/bin/sh\nexit 1\n' >"$RS/hooks/tests/bad.sh"
    git_in "$RS" add hooks/tests/bad.sh
    git_in "$RS" commit -q -m badsh
    run_cl --refresh --run --min-hooks 2 --min-gtm 1 --min-node 2
    eq "--run fails when a shell test exits non-zero" "$RC" 1
    has "  and names it" "$OUT" 'FAIL +hooks/tests/bad.sh'
    git_in "$RS" rm -q hooks/tests/bad.sh
    git_in "$RS" commit -q -m unbadsh

    git_in "$RS" rm -q tools/gtm/tests/test_ok.py
    git_in "$RS" commit -q -m empty
    mkdir -p "$RS/tools/gtm/tests"
    run_cl --refresh --run --min-hooks 2 --min-gtm 0 --min-node 2
    eq "--run fails on a location that ran zero tests, even with a zero minimum" "$RC" 1
    has "  and names it" "$OUT" 'FAIL +tools/gtm/tests'
  fi
fi

echo
echo "ci_layout rails: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
