#!/usr/bin/env bash
# ci_layout.sh -- build (and optionally run) the exact layout this repo's tests
# and CI expect.
#
# WHY A LAYOUT AT ALL
# -------------------
# The runtime is a DEPLOYED shape: hooks resolve their files as $HOME/.claude/...
# (hooks/_lib.py sets CLAUDE_DIR = $HOME/.claude, settings.json wires every hook by
# that path, bash_gate.sh execs $HOME/.claude/hooks/pretooluse_bash.py). Running
# the suite from a checkout anywhere else fails hundreds of tests with
# "~/.claude/scripts/<x>.sh: No such file" and says nothing about the code. This
# script builds the shape the tests were written against, the same way every time:
#
#   <layout root>/                a dedicated directory, the parent of --home
#     .ci-layout-root             marker: the siblings below are ours to touch
#     home/                       $HOME for the run, OUTSIDE /tmp and /private/tmp
#       .ci-layout                marker: this directory is ours to rewrite
#       .claude/                  `git archive HEAD` of this repo, via tar -x
#         projects/               created (exists on every real install)
#         live-testing/allowlist.json             seeded from the .example.json
#         knowledge/protected_boards.json         seeded from the .example.json
#     venv/                       pytest, pytest-cov, ruff, jsonschema, detect-secrets
#     pytest-tmp/                 pytest --basetemp: a SIBLING of home, not under it
#
# The run environment is part of the layout: HOME is the layout home, stdin is
# /dev/null, and TZ=UTC (the GitHub ubuntu legs run in UTC; a developer's macOS
# machine would otherwise run the suite in its local zone and disagree with CI).
#
# Why each part matters is recorded where it is done below. In short: HOME must
# not be under /tmp (agentarch_metric_check.py treats /tmp as an always-safe root,
# which silently changes what it flags); --basetemp must not be under HOME
# (repo_manifest.py stores registry roots HOME-relative, so a tmp_path under HOME
# breaks test_register_preserves_root_sharing_alias) and must not be under /tmp
# either (same always-safe-root reason); jsonschema must be importable by
# /usr/bin/python3 because scripts/codex_review.sh hardcodes that interpreter.
#
# USAGE
#   bash scripts/ci_layout.sh [--home DIR] [--python PATH] [--refresh] [--run]
#                             [--skip-install] [--system-deps] [--min-hooks N]
#                             [--min-gtm N] [--min-node N]
#
#   --home DIR       layout home; must end in /home (default ~/.cache/ci-layout/home)
#   --python PATH    interpreter for the venv (default python3; must be >= 3.9)
#   --refresh        re-extract HEAD over an existing layout (needs the marker)
#   --run            after building, run acceptance #1 inside the layout and exit
#                    non-zero on any failure or on a location that ran zero tests
#   --skip-install   install nothing: no venv creation or pip, no interpreter
#                    installs (a debug and test aid). With --run the venv must
#                    already exist.
#   --system-deps    allow ONE privileged step: installing jsonschema for
#                    /usr/bin/python3 (sudo pip on macOS when codex_review.sh runs
#                    it isolated, apt-get on Linux). Without this flag, or CI=true,
#                    nothing is ever escalated: the exact command is printed
#                    ("ACTION NEEDED") and the build continues.
#   --min-hooks N    --run: required executed tests in hooks/tests   (default 7900)
#   --min-gtm N      --run: required executed tests in tools/gtm/tests (default 350)
#   --min-node N     --run: required passing node tests               (default 13)
#
# Only what is COMMITTED reaches the layout (git archive HEAD); uncommitted edits
# are reported, not copied.
#
# SAFETY RAILS (each is exercised by hooks/tests/test_ci_layout.sh)
# ------------------------------------------------------------------
# A wrong --home or HOME here would extract HEAD over a live runtime and destroy
# every other session's uncommitted work, so this script refuses (exit 3) when:
#   * the layout home, or the layout root above it, is, contains, or lies inside
#     the real ~/.claude (checked against BOTH the passwd-database home and the
#     invoking $HOME). Two layers: the paths are compared after resolving
#     symlinks, AND by file identity (device and inode, os.path.samefile) between
#     every EXISTING ancestor of the candidate and the protected directory, in both
#     directions. The identity layer is what catches spellings no string compare
#     sees: a case variant (~/.CLAUDE) on a case-insensitive filesystem, or a macOS
#     firmlink (/System/Volumes/Data/Users/...). A protected directory that does
#     not exist yet cannot be compared by identity and is compared by path only;
#   * the layout's .claude would overlap the source checkout being archived (same
#     two layers);
#   * the layout home resolves into /tmp or /private/tmp (same two layers);
#   * the current directory is inside the real ~/.claude (same two layers);
#   * the layout home, an existing layout .claude, or a .ci-layout marker is a
#     symlink, or so is <root>/venv or <root>/pytest-tmp;
#   * the layout home exists, is not empty, and has no .ci-layout marker;
#   * the layout root has a venv/, a pytest-tmp/, or an earlier run's junit/log
#     files but no .ci-layout-root marker: pip would install into that venv and
#     pytest wipes its --basetemp on every run, so neither is touched unless this
#     script claimed the root first;
#   * a layout exists for a different commit and --refresh was not given.
# What this script deletes: <home>/.claude on --refresh (only after the home marker
# is proven present, never following a symlink); the junit/log files it writes in
# the root (only after the root marker is proven present). pytest itself wipes
# <root>/pytest-tmp on every run, which is why the root marker gates it too.
# It never deletes a venv.
#
# PRIVILEGE: nothing runs under sudo, or as root-only apt-get, unless --system-deps
# or CI=true was given. A cached sudo ticket is not consent.
#
# EXIT CODES  0 ok | 1 failure | 2 usage | 3 a safety rail refused
#
# bash 3.2 compatible (macOS /bin/bash): no mapfile, no associative arrays.

set -euo pipefail

PROG="ci_layout"
EXIT_USAGE=2
EXIT_REFUSED=3
MARKER_NAME=".ci-layout"
ROOT_MARKER_NAME=".ci-layout-root"
MARKER_VERSION="ci-layout v1"

die() { echo "$PROG: ERROR: $*" >&2; exit 1; }
usage_error() { echo "$PROG: $*" >&2; echo "Try: bash $0 --help" >&2; exit "$EXIT_USAGE"; }
refuse() { echo "$PROG: REFUSING: $*" >&2; exit "$EXIT_REFUSED"; }
info() { echo "$PROG: $*"; }

usage() {
  sed -n '/^# USAGE$/,/^# Only what is COMMITTED/p' "$0" | sed -e 's/^# \{0,1\}//' -e '$d'
}

# --- arguments -------------------------------------------------------------

LAYOUT_HOME_ARG=""
PY_ARG="python3"
DO_REFRESH=0
DO_RUN=0
SKIP_INSTALL=0
SYSTEM_DEPS=0
[ "${CI:-}" = "true" ] && SYSTEM_DEPS=1
MIN_HOOKS=7900
MIN_GTM=350
MIN_NODE=13

need_value() { [ "$2" -ge 2 ] || usage_error "$1 needs a value"; }
need_int() {
  case "$2" in
    '' | *[!0-9]*) usage_error "$1 needs a non-negative integer, got '$2'" ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --home) need_value "$1" "$#"; LAYOUT_HOME_ARG="$2"; shift 2 ;;
    --python) need_value "$1" "$#"; PY_ARG="$2"; shift 2 ;;
    --min-hooks) need_value "$1" "$#"; need_int "$1" "$2"; MIN_HOOKS="$2"; shift 2 ;;
    --min-gtm) need_value "$1" "$#"; need_int "$1" "$2"; MIN_GTM="$2"; shift 2 ;;
    --min-node) need_value "$1" "$#"; need_int "$1" "$2"; MIN_NODE="$2"; shift 2 ;;
    --refresh) DO_REFRESH=1; shift ;;
    --run) DO_RUN=1; shift ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    --system-deps) SYSTEM_DEPS=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) usage_error "unknown argument: $1" ;;
  esac
done

# --- path helpers (python3 normalises; macOS has no `realpath -m`) -----------

command -v python3 >/dev/null 2>&1 || die "python3 is required on PATH (path normalisation)"
git --version >/dev/null 2>&1 || die "git is required on PATH"

# Run from inside a git hook, GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE point at the
# repository being committed to and would redirect every `git -C <source>` call
# below at the wrong repo. Drop all of git's repo-local variables.
for _v in $(git rev-parse --local-env-vars 2>/dev/null); do unset "$_v"; done

realpath_of() { python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"; }
abspath_of() { python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$1"; }

# path_within CHILD PARENT: 0 when CHILD is PARENT or lies beneath it.
# Both arguments must be absolute and already symlink-resolved.
path_within() {
  local child="$1" parent="$2"
  [ "$parent" = "/" ] && return 0
  case "$child/" in
    "$parent"/*) return 0 ;;
  esac
  return 1
}
overlaps() { path_within "$1" "$2" || path_within "$2" "$1"; }

# identity_overlap MODE CANDIDATE PROTECTED -> prints "inside", "contains" or nothing.
# Compares by file identity (os.path.samefile: device + inode), not by spelling, so a
# case variant on a case-insensitive filesystem or a firmlink alias cannot slip past
# the string compare. "inside": CANDIDATE or one of its existing ancestors IS
# PROTECTED. "contains" (MODE=either only): PROTECTED or one of its existing
# ancestors IS CANDIDATE. Only existing paths can be compared.
identity_overlap() {
  python3 -I -c '
import os
import sys

mode, cand, prot = sys.argv[1:4]


def chain(p):
    p = os.path.abspath(p)
    out = []
    while True:
        out.append(p)
        parent = os.path.dirname(p)
        if parent == p:
            return out
        p = parent


def exists(p):
    try:
        os.stat(p)
        return True
    except OSError:
        return False


def same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


if exists(prot) and any(same(a, prot) for a in chain(cand) if exists(a)):
    print("inside")
elif mode == "either" and exists(cand) and any(same(cand, b) for b in chain(prot) if exists(b)):
    print("contains")
' "$1" "$2" "$3"
}

# --- the real ~/.claude, and the source checkout ------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_REPO="$(cd "$SCRIPT_DIR/.." && pwd -P)"

# The passwd database, NOT $HOME: $HOME is exactly what a mis-set environment gets
# wrong. Both are protected, so neither a stale nor an overridden HOME is a way in.
PW_HOME="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')" ||
  die "cannot determine the real home directory"
[ -n "$PW_HOME" ] || die "cannot determine the real home directory"

PROTECTED=()
add_protected() {
  local p q
  p="$(realpath_of "$1")"
  for q in ${PROTECTED[@]+"${PROTECTED[@]}"}; do
    [ "$q" = "$p" ] && return 0
  done
  PROTECTED+=("$p")
}
add_protected "$PW_HOME/.claude"
add_protected "${HOME:-$PW_HOME}/.claude"

check_not_real_claude() { # LABEL RESOLVED_PATH [SPELLED_PATH]
  local label="$1" resolved="$2" spelled="${3:-$2}" p how
  for p in ${PROTECTED[@]+"${PROTECTED[@]}"}; do
    if overlaps "$resolved" "$p"; then
      refuse "$label '$resolved' is, contains, or lies inside the real ~/.claude ('$p'); extracting here could overwrite the live runtime"
    fi
    how="$(identity_overlap either "$resolved" "$p")"
    [ -n "$how" ] || how="$(identity_overlap either "$spelled" "$p")"
    if [ -n "$how" ]; then
      refuse "$label '$spelled' $how the real ~/.claude ('$p') by file identity (same directory under another spelling, such as a case variant or a firmlink); extracting here could overwrite the live runtime"
    fi
  done
}

# Rail: never run from inside the real ~/.claude.
CWD_REAL="$(pwd -P)"
for _p in ${PROTECTED[@]+"${PROTECTED[@]}"}; do
  if path_within "$CWD_REAL" "$_p" || [ -n "$(identity_overlap inside "$CWD_REAL" "$_p")" ]; then
    refuse "current directory '$CWD_REAL' is inside the real ~/.claude ('$_p'); cd somewhere else first (for example: cd \"\$HOME\")"
  fi
done

# --- resolve and check the target -------------------------------------------

if [ -z "$LAYOUT_HOME_ARG" ]; then
  LAYOUT_HOME_ARG="${HOME:-$PW_HOME}/.cache/ci-layout/home"
fi
HOME_ABS="$(abspath_of "$LAYOUT_HOME_ARG")"
LAYOUT_HOME="$(realpath_of "$LAYOUT_HOME_ARG")"
LAYOUT_ROOT="$(dirname "$LAYOUT_HOME")"
TARGET="$LAYOUT_HOME/.claude"
MARKER="$LAYOUT_HOME/$MARKER_NAME"
ROOT_MARKER="$LAYOUT_ROOT/$ROOT_MARKER_NAME"
VENV="$LAYOUT_ROOT/venv"
BASETEMP="$LAYOUT_ROOT/pytest-tmp"

# Rail: the real ~/.claude (by resolved path, so a symlink into it does not help).
check_not_real_claude "layout home" "$LAYOUT_HOME" "$HOME_ABS"
check_not_real_claude "layout root" "$LAYOUT_ROOT" "$(dirname "$HOME_ABS")"
check_not_real_claude "layout .claude" "$TARGET" "$HOME_ABS/.claude"

# Rail: never archive over the checkout the archive comes from.
if overlaps "$TARGET" "$SOURCE_REPO" || [ -n "$(identity_overlap either "$TARGET" "$SOURCE_REPO")" ] ||
  [ -n "$(identity_overlap either "$HOME_ABS/.claude" "$SOURCE_REPO")" ]; then
  refuse "layout .claude '$TARGET' overlaps the source checkout '$SOURCE_REPO'"
fi

# Rail: HOME outside /tmp (see header).
for _t in /tmp /private/tmp; do
  if path_within "$LAYOUT_HOME" "$_t" || path_within "$HOME_ABS" "$_t" ||
    [ -n "$(identity_overlap inside "$LAYOUT_HOME" "$_t")" ] ||
    [ -n "$(identity_overlap inside "$HOME_ABS" "$_t")" ]; then
    refuse "layout home '$LAYOUT_HOME' is under $_t; agentarch_metric_check.py treats /tmp as an always-safe root, which would change what it flags"
  fi
done

# Rail: a dedicated, sibling-bearing layout root.
if [ "$(basename "$LAYOUT_HOME")" != "home" ] || [ "$LAYOUT_ROOT" = "/" ]; then
  refuse "--home must be a directory named 'home' inside a dedicated directory (got '$LAYOUT_HOME'); venv/ and pytest-tmp/ are created beside it"
fi

# Rail: no symlinks at the points we write through or delete.
if [ -L "$HOME_ABS" ]; then
  refuse "layout home '$HOME_ABS' is a symlink"
fi
if [ -L "$TARGET" ]; then
  refuse "layout .claude '$TARGET' is a symlink; it is never followed or deleted"
fi
if [ -L "$MARKER" ]; then
  refuse "marker '$MARKER' is a symlink; it is never followed"
fi

# Rail: only ever rewrite a directory this script made.
if [ -e "$LAYOUT_HOME" ]; then
  [ -d "$LAYOUT_HOME" ] || refuse "layout home '$LAYOUT_HOME' exists and is not a directory"
  if [ ! -f "$MARKER" ]; then
    if [ -n "$(ls -A "$LAYOUT_HOME")" ]; then
      refuse "layout home '$LAYOUT_HOME' is not empty and has no $MARKER_NAME marker; it was not created by $PROG and will not be touched"
    fi
  fi
fi

# Rail: the siblings of home (venv/, pytest-tmp/, junit and log files) are only
# touched under a root this script claimed. pip installs into the venv and pytest
# wipes its --basetemp on every run, so a pre-existing one is somebody else's data
# until proven otherwise.
if [ -L "$ROOT_MARKER" ]; then
  refuse "root marker '$ROOT_MARKER' is a symlink; it is never followed"
fi
for _n in venv pytest-tmp; do
  if [ -L "$LAYOUT_ROOT/$_n" ]; then
    refuse "'$LAYOUT_ROOT/$_n' is a symlink; the layout never installs or wipes through one"
  fi
done
if [ ! -f "$ROOT_MARKER" ]; then
  # Unmatched globs stay literal and fail the -e test, so no nullglob is needed.
  for _n in "$LAYOUT_ROOT/venv" "$LAYOUT_ROOT/pytest-tmp" "$LAYOUT_ROOT"/junit-*.xml \
    "$LAYOUT_ROOT"/sh-*.log "$LAYOUT_ROOT/node-test.log"; do
    if [ -e "$_n" ]; then
      refuse "layout root '$LAYOUT_ROOT' already contains '$(basename "$_n")' but has no $ROOT_MARKER_NAME marker; it was not created by $PROG and will not be touched (use a different --home, or create the marker yourself if this directory is a layout from an older run)"
    fi
  done
fi

# --- the source ---------------------------------------------------------------

git -C "$SOURCE_REPO" rev-parse --git-dir >/dev/null 2>&1 ||
  die "'$SOURCE_REPO' is not a git repository; the layout is built from 'git archive HEAD'"
HEAD_SHA="$(git -C "$SOURCE_REPO" rev-parse HEAD)" || die "cannot resolve HEAD in '$SOURCE_REPO'"

marker_value() { sed -n "s/^$1=//p" "$MARKER" | head -n 1; }

# --- build the tree -----------------------------------------------------------

NEED_EXTRACT=1
if [ -d "$TARGET" ]; then
  [ -f "$MARKER" ] || refuse "layout .claude exists without a $MARKER_NAME marker in '$LAYOUT_HOME'"
  if [ "$DO_REFRESH" -eq 1 ]; then
    # The marker is proven present above. rm does not follow symlinks inside the
    # tree, and the top level was just checked not to be one. No trailing slash:
    # BSD rm would follow a symlink given with one.
    info "refreshing: removing the old $TARGET"
    rm -rf -- "$TARGET"
  elif [ "$(marker_value commit)" = "$HEAD_SHA" ]; then
    info "reusing the existing layout at $LAYOUT_HOME (same commit ${HEAD_SHA}); pass --refresh to re-extract"
    NEED_EXTRACT=0
  else
    refuse "the layout at '$LAYOUT_HOME' was built from commit '$(marker_value commit)', HEAD is '$HEAD_SHA'; pass --refresh to re-extract"
  fi
fi

# write_marker DEST LINE...: temp file in the same directory, then rename, so a marker
# is never a half-written file and a pre-planted file at the temp name is never used.
write_marker() {
  local dest="$1" tmp
  shift
  tmp="$(mktemp "$dest.XXXXXX")"
  printf '%s\n' "$@" >"$tmp"
  mv -f "$tmp" "$dest"
}

mkdir -p "$LAYOUT_HOME"
[ -f "$ROOT_MARKER" ] || write_marker "$ROOT_MARKER" "ci-layout-root v1"
if [ "$NEED_EXTRACT" -eq 1 ]; then
  # --no-optional-locks: the source is often a live checkout; a status refresh must
  # not take its index lock.
  DIRTY="$(git --no-optional-locks -C "$SOURCE_REPO" status --porcelain --untracked-files=no | wc -l | tr -d ' ')"
  if [ "$DIRTY" -gt 0 ]; then
    info "WARNING: $DIRTY tracked file(s) in $SOURCE_REPO have uncommitted changes; the layout holds HEAD only"
  fi
  # Marker first, commit recorded only after a complete extraction: an interrupted
  # run leaves a directory this script will still recognise as its own (and will
  # refuse to reuse without --refresh), never one it must refuse to touch.
  write_marker "$MARKER" "$MARKER_VERSION"
  mkdir -p "$TARGET"
  git -C "$SOURCE_REPO" archive --format=tar HEAD | tar -x -C "$TARGET"
  write_marker "$MARKER" "$MARKER_VERSION" "commit=$HEAD_SHA" "source=$SOURCE_REPO"
  info "extracted HEAD ${HEAD_SHA} into $TARGET"
fi

# projects/ exists on every real install, and agentarch_metric_check.py needs the
# never-safe root to exist for its path resolution to classify anything under it.
mkdir -p "$TARGET/projects"

# Per-machine files the tests read, seeded from their shipped examples only when
# the example is present and the real file is not. Never a fallback at runtime.
seed_example() { # EXAMPLE_REL TARGET_REL
  [ -f "$TARGET/$1" ] || return 0
  if [ -L "$TARGET/$2" ]; then
    # `[ ! -e ]` is true for a dangling symlink and cp would write through it.
    info "NOTE: not seeding $2: it is a symlink"
  elif [ ! -e "$TARGET/$2" ]; then
    cp "$TARGET/$1" "$TARGET/$2"
    info "seeded $2 from $1"
  fi
}
seed_example live-testing/allowlist.example.json live-testing/allowlist.json
seed_example knowledge/protected_boards.example.json knowledge/protected_boards.json

# --- python environment -------------------------------------------------------

PYTEST_OPTS="--basetemp=$(printf '%q' "$BASETEMP") -p no:cacheprovider"

# EXACTLY the [project.optional-dependencies] test + lint extras of pyproject.toml
# (hooks/tests/test_ci_layout.sh fails if the two differ). detect-secrets is pinned to
# the version scripts/codex_review.sh documents and was measured against.
PACKAGES=("pytest>=8" "pytest-cov" "ruff==0.15.18" "jsonschema" "detect-secrets==1.5.0")

interp_version() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])'; }

setup_venv() {
  local pyver have
  command -v "$PY_ARG" >/dev/null 2>&1 || die "python interpreter '$PY_ARG' not found"
  "$PY_ARG" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' ||
    die "'$PY_ARG' is older than Python 3.9"
  pyver="$(interp_version "$PY_ARG")"
  if [ -e "$VENV" ]; then
    have="$(interp_version "$VENV/bin/python")" ||
      die "the venv at '$VENV' is unusable; this script never deletes a venv, so use a different --home or remove it yourself if it is yours"
    [ "$have" = "$pyver" ] ||
      die "the venv at '$VENV' is Python $have but --python is $pyver; use a different --home per Python version"
  else
    "$PY_ARG" -m venv "$VENV"
  fi
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check "${PACKAGES[@]}"
  info "venv ready: $VENV (Python $pyver)"
}

# scripts/codex_review.sh hardcodes /usr/bin/python3 and PYTHON_BIN is deliberately
# inert (a hardening decision; do not reintroduce it), so jsonschema has to be
# importable BY THAT INTERPRETER. How depends on the OS, and on whether the script
# runs it isolated (-I), which ignores the per-user site directory.
codex_runs_isolated() {
  grep -Eq '(_PYTHON_BIN"|/usr/bin/python3)[[:space:]]+-I([[:space:]]|$)' \
    "$TARGET/scripts/codex_review.sh" 2>/dev/null
}

# The interpreter jsonschema must be importable by. Overridable only so the tests can
# point it at a stub; the default is the hardcoded path in scripts/codex_review.sh.
SYSTEM_PYTHON="${CI_LAYOUT_SYSTEM_PYTHON:-/usr/bin/python3}"

system_jsonschema_importable() { # ISOLATED(0|1)
  if [ "$1" -eq 1 ]; then
    HOME="$LAYOUT_HOME" "$SYSTEM_PYTHON" -I -c 'import jsonschema' 2>/dev/null
  else
    HOME="$LAYOUT_HOME" "$SYSTEM_PYTHON" -c 'import jsonschema' 2>/dev/null
  fi
}

# Escalation needs explicit consent (--system-deps, or CI=true) AND a way to do it. A
# cached sudo ticket is not consent, so sudo is not even probed without the flag.
escalation_available() {
  [ "$SYSTEM_DEPS" -eq 1 ] || return 1
  [ "$(id -u)" = "0" ] || sudo -n true 2>/dev/null
}
run_escalated() {
  if [ "$(id -u)" = "0" ]; then "$@"; else sudo -n "$@"; fi
}
HINT_SYSTEM_DEPS="re-run with --system-deps (or CI=true) to let this script do it"

install_system_jsonschema() {
  local sysbin="$SYSTEM_PYTHON" os isolated=0
  if [ ! -x "$sysbin" ]; then
    info "note: $sysbin does not exist; skipping its jsonschema install (scripts/codex_review.sh hardcodes it)"
    return 0
  fi
  codex_runs_isolated && isolated=1
  if system_jsonschema_importable "$isolated"; then
    info "jsonschema is already importable by $sysbin"
    return 0
  fi
  os="$(uname -s)"
  case "$os" in
    Darwin)
      if [ "$isolated" -eq 1 ]; then
        # -I drops the user site: it must go into the system site-packages.
        if escalation_available; then
          run_escalated "$sysbin" -m pip install --quiet --disable-pip-version-check --no-warn-script-location jsonschema
        else
          info "ACTION NEEDED (codex_review.sh runs $sysbin -I, which ignores the per-user site): sudo $sysbin -m pip install jsonschema   [$HINT_SYSTEM_DEPS]"
        fi
      else
        HOME="$LAYOUT_HOME" "$sysbin" -m pip install --quiet --disable-pip-version-check --no-warn-script-location --user jsonschema
      fi
      ;;
    Linux)
      if escalation_available; then
        run_escalated apt-get install -y python3-jsonschema >/dev/null
      else
        info "ACTION NEEDED: sudo apt-get install -y python3-jsonschema   [$HINT_SYSTEM_DEPS]"
      fi
      ;;
    *) info "note: unsupported OS '$os'; install jsonschema for $sysbin yourself" ;;
  esac
  if system_jsonschema_importable "$isolated"; then
    info "jsonschema is importable by $sysbin"
  else
    info "WARNING: jsonschema is NOT importable by $sysbin; tests of scripts/codex_review.sh will fail with 'validator-unavailable'"
  fi
}

if [ "$SKIP_INSTALL" -eq 0 ]; then
  setup_venv
  install_system_jsonschema
else
  info "--skip-install: venv and interpreter installs skipped"
  if [ "$DO_RUN" -eq 1 ] && [ ! -x "$VENV/bin/python" ]; then
    die "--run with --skip-install needs an existing venv at '$VENV'; build the layout once without --skip-install"
  fi
fi

# --- guidance -------------------------------------------------------------------

q() { printf '%q' "$1"; }

print_commands() {
  cat <<EOF

Layout ready.
  home        $LAYOUT_HOME
  checkout    $TARGET   (commit $HEAD_SHA)
  venv        $VENV
  basetemp    $BASETEMP   (a sibling of home; pytest wipes it on every run)

Enter it exactly like this (every acceptance command below runs from here):

  cd $(q "$TARGET")
  export HOME=$(q "$LAYOUT_HOME")
  export TZ=UTC
  export PATH=$(q "$VENV/bin"):"\$PATH"
  export PYTEST_ADDOPTS=$(q "$PYTEST_OPTS")
  # stdin must be /dev/null; do not create .enforce or any state directory

Acceptance #1 - tests (each must run more than zero tests):
  python -m pytest hooks/tests -q -m "not live_machine"          # 0 failed, 0 errors, >= $MIN_HOOKS executed
  python -m pytest tools/gtm/tests -q                            # 0 failed, >= $MIN_GTM executed
  python -m pytest live-testing/tests -q                         # 0 failed (skip if the directory is not exported)
  for f in hooks/tests/*.sh; do bash "\$f" || echo "FAIL \$f"; done
  node --test --test-reporter=tap workflows/tests/test_issue_wheel_triage.mjs   # # fail 0, # pass >= $MIN_NODE
Acceptance #2 - static checks:
  ruff check .
  ruff format --check
  find . -name '*.sh' -not -path './scripts/legacy/*' -not -path './scripts/codex_review.sh' -exec shellcheck -S warning {} +
  python scripts/check_guard_wiring.py
Acceptance #3/#4 - demo and installer: not shipped yet (bash demo/run_demo.sh --ci and
  bash hooks/tests/test_install_hooks.sh arrive with them; see CHANGELOG "Known gaps").
Acceptance #5 - every argparse CLI answers --help (also part of the hooks/tests run):
  python -m pytest hooks/tests/test_cli_help.py -q

Or run acceptance #1 for you:  bash $(q "$0") --home $(q "$LAYOUT_HOME") --run
EOF
}

# --- --run: acceptance #1 ---------------------------------------------------------

# Run a command inside the layout with the invoker's CSA_*/CLAUDE_*/PYTEST_*/venv
# variables scrubbed, HOME pointed at the layout, TZ forced to UTC (as on the CI
# runners), stdin from /dev/null.
in_layout() {
  (
    cd "$TARGET"
    local v
    for v in $(git rev-parse --local-env-vars 2>/dev/null); do unset "$v"; done
    for v in $(compgen -e); do
      case "$v" in
        CSA_* | CLAUDE_* | PYTEST_* | PYTHONPATH | PYTHONHOME | VIRTUAL_ENV | CONDA_*) unset "$v" ;;
      esac
    done
    export HOME="$LAYOUT_HOME"
    export TZ=UTC
    export PATH="$VENV/bin:$PATH"
    export PYTEST_ADDOPTS="$PYTEST_OPTS"
    exec "$@" </dev/null
  )
}

RUN_FAILURES=0
RUN_REPORT=()
record() { # STATUS LABEL DETAIL
  RUN_REPORT+=("$(printf '%-5s %-28s %s' "$1" "$2" "$3")")
  if [ "$1" != "ok" ]; then RUN_FAILURES=$((RUN_FAILURES + 1)); fi
}

junit_counts() { # XML -> "tests failures errors skipped"
  "$VENV/bin/python" - "$1" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
t = f = e = s = 0
for suite in suites:
    t += int(suite.get("tests", 0))
    f += int(suite.get("failures", 0))
    e += int(suite.get("errors", 0))
    s += int(suite.get("skipped", 0))
print(t, f, e, s)
PY
}

run_pytest() { # LABEL PATH MIN [extra pytest args...]
  local label="$1" path="$2" min="$3" xml rc=0 counts t f e s executed
  shift 3
  xml="$LAYOUT_ROOT/junit-$(echo "$label" | tr '/' '-').xml"
  rm -f "$xml"
  info "running pytest $path"
  in_layout "$VENV/bin/python" -m pytest "$path" -q -o junit_family=xunit2 \
    "--junitxml=$xml" ${1+"$@"} || rc=$?
  if [ ! -f "$xml" ]; then
    record FAIL "$label" "pytest exited $rc and wrote no result file"
    return 0
  fi
  counts="$(junit_counts "$xml")"
  read -r t f e s <<<"$counts"
  executed=$((t - s))
  if [ "$rc" -ne 0 ] || [ "$f" -ne 0 ] || [ "$e" -ne 0 ]; then
    record FAIL "$label" "exit $rc: $f failed, $e errors, $executed executed, $s skipped"
  elif [ "$executed" -lt 1 ] || [ "$executed" -lt "$min" ]; then
    record FAIL "$label" "only $executed executed, need at least $min ($s skipped)"
  else
    record ok "$label" "$executed executed, $s skipped"
  fi
}

run_acceptance_1() {
  local f name n=0 log rc
  run_pytest hooks/tests hooks/tests "$MIN_HOOKS" -m "not live_machine"
  run_pytest tools/gtm/tests tools/gtm/tests "$MIN_GTM"
  if [ -d "$TARGET/live-testing/tests" ]; then
    run_pytest live-testing/tests live-testing/tests 1
  else
    record ok live-testing/tests "not exported; nothing to run"
  fi

  for f in "$TARGET"/hooks/tests/*.sh; do
    [ -e "$f" ] || continue
    n=$((n + 1))
    name="$(basename "$f")"
    log="$LAYOUT_ROOT/sh-$name.log"
    rc=0
    info "running hooks/tests/$name"
    in_layout bash "$f" >"$log" 2>&1 || rc=$?
    if [ "$rc" -ne 0 ]; then
      tail -n 20 "$log" >&2
      record FAIL "hooks/tests/$name" "exit $rc (log: $log)"
    else
      record ok "hooks/tests/$name" "exit 0"
    fi
  done
  if [ "$n" -eq 0 ]; then record FAIL "hooks/tests/*.sh" "no shell tests found"; fi

  log="$LAYOUT_ROOT/node-test.log"
  rc=0
  info "running node --test workflows/tests/test_issue_wheel_triage.mjs"
  if command -v node >/dev/null 2>&1; then
    in_layout node --test --test-reporter=tap workflows/tests/test_issue_wheel_triage.mjs >"$log" 2>&1 || rc=$?
    local npass nfail
    npass="$(sed -n 's/^# pass \([0-9][0-9]*\).*/\1/p' "$log" | tail -n 1)"
    nfail="$(sed -n 's/^# fail \([0-9][0-9]*\).*/\1/p' "$log" | tail -n 1)"
    npass="${npass:-0}"; nfail="${nfail:-1}"
    if [ "$rc" -ne 0 ] || [ "$nfail" -ne 0 ] || [ "$npass" -lt "$MIN_NODE" ]; then
      record FAIL workflows/tests "exit $rc: $npass pass, $nfail fail (need 0 fail, >= $MIN_NODE pass; log: $log)"
    else
      record ok workflows/tests "$npass pass, 0 fail"
    fi
  else
    record FAIL workflows/tests "node is not on PATH"
  fi
}

print_commands

if [ "$DO_RUN" -eq 1 ]; then
  echo
  info "--run: acceptance #1 inside the layout"
  run_acceptance_1
  echo
  echo "$PROG: acceptance #1 summary"
  for _line in ${RUN_REPORT[@]+"${RUN_REPORT[@]}"}; do echo "  $_line"; done
  if [ "$RUN_FAILURES" -gt 0 ]; then
    echo "$PROG: $RUN_FAILURES check(s) FAILED" >&2
    exit 1
  fi
  echo "$PROG: all checks passed"
fi
