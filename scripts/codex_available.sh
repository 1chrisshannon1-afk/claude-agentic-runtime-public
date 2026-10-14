#!/usr/bin/env bash
# codex_available.sh — readiness gate for the Codex cross-model review
# scaffold. Exit 0 ONLY when all three preconditions hold. Never invokes
# codex, never reads any credential's contents, never prints one.
#
# Plan: plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md
# §5 (WS4). Consulted by scripts/codex_review.sh before it does anything else.
# Hardened in fix round 1 (trust-architect, reviewer-of-record) after
# execution proved a full bypass was possible via nothing but environment
# variables (B4) — see docs/subsystems/codex-review.md for the full account.
#
# Preconditions, checked in this order (first failure wins -- distinct exit
# code + one-line stderr reason each):
#   1. The absolute binary /opt/homebrew/bin/codex exists and is executable.
#   2. An auth file exists under the invoking user's REAL ~/.codex/ --
#      EXISTENCE ONLY. This script never opens, reads, or prints it.
#   3. The consent marker exists AND is valid: a REGULAR file (never a
#      symlink), owned by uid 0 (root), mode EXACTLY 0444, containing valid
#      JSON with "scope" == "ws4-v1-advisory". Any other shape -- a
#      user-owned file, a symlink, wrong mode, wrong/missing scope, a
#      directory, unparseable JSON -- is treated as NOT consented. An agent
#      running as the operator can DELETE this marker (fails safe -- consent
#      is revoked) but cannot CREATE one that passes, because it cannot
#      chown a file to root without sudo, which this scaffold's own
#      standing rule forbids any agent from ever invoking. The marker is
#      written ONLY by scripts/grant_codex_consent.sh, run manually by the
#      human operator with sudo in their own terminal.
#
# Today (no codex login, no consent given): this ALWAYS exits non-zero. That
# is the correct, intended state -- see docs/subsystems/codex-review.md.
#
# Usage: codex_available.sh   (no arguments)
#
# The ONLY environment variables this script honours, and only together
# (fix round 1 B4 -- removed CODEX_BIN/CODEX_HOME/CLAUDE_DIR overrides
# entirely from the general case; see codex_review.sh's own header for the
# full rationale table, which this script mirrors exactly):
#   CODEX_REVIEW_TEST_MODE=1  + a runtime dir (resolved from THIS SCRIPT'S
#   OWN ON-DISK LOCATION, never from a caller variable) that is NOT the
#   real invoking user's $HOME/.claude, together unlock:
#     CODEX_REVIEW_TEST_HOME  -- where ~/.codex is resolved from, for that
#                                 run only.
#     CODEX_REVIEW_TEST_TRUST_OWNER=1 -- treats the consent marker's
#                                 root-ownership requirement as satisfied
#                                 (uid check only -- symlink, regular-file,
#                                 mode-0444, JSON-validity, and scope checks
#                                 stay fully real). A test cannot chown a
#                                 file to uid 0 without sudo either, so this
#                                 is the one narrow seam that exists to
#                                 exercise the positive consent path at all;
#                                 the genuine root-owned path is UNVERIFIED
#                                 by any test in this repo.
# Running the real, installed script from ~/.claude/scripts/ can NEVER
# satisfy the test-mode discriminator, so CODEX_REVIEW_TEST_MODE=1 (and the
# two variables above it unlocks) is inert against the real installation --
# it cannot be used to make this script lie about the real machine's state.

set -uo pipefail

_PYTHON_BIN="/usr/bin/python3"
_PERL_BIN="/usr/bin/perl"
_REAL_CODEX_BIN="/opt/homebrew/bin/codex"

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
_RUNTIME_DIR="$(cd "$_SCRIPT_DIR/.." && pwd -P)"

_REAL_USER_HOME="$("$_PYTHON_BIN" -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)' 2>/dev/null)"
_REAL_USER_CLAUDE_DIR=""
if [ -n "$_REAL_USER_HOME" ]; then
  _REAL_USER_CLAUDE_DIR="$_REAL_USER_HOME/.claude"
fi

_TEST_MODE_ACTIVE=0
if [ "${CODEX_REVIEW_TEST_MODE:-0}" = "1" ] && [ -n "$_REAL_USER_CLAUDE_DIR" ] && [ "$_RUNTIME_DIR" != "$_REAL_USER_CLAUDE_DIR" ]; then
  _TEST_MODE_ACTIVE=1
fi

if [ "$_TEST_MODE_ACTIVE" = "1" ] && [ -n "${CODEX_REVIEW_TEST_HOME:-}" ]; then
  _CODEX_HOME_BASE="$CODEX_REVIEW_TEST_HOME"
else
  _CODEX_HOME_BASE="$_REAL_USER_HOME"
fi
CODEX_HOME_RESOLVED="$_CODEX_HOME_BASE/.codex"
CONSENT_MARKER="$_RUNTIME_DIR/.review_state/codex/CONSENT.json"
# Derived from $_RUNTIME_DIR (this script's own on-disk location), never
# from a caller variable -- same non-overridable read-path rule as every
# other security-relevant path here. Used only by the version-mismatch
# re-canary check at the end of this script.
CANARY_DIR="$_RUNTIME_DIR/.review_state/codex"

# --- 1. binary exists and is executable -----------------------------------
if [ ! -x "$_REAL_CODEX_BIN" ]; then
  echo "codex_available: NOT READY: codex binary not found or not executable at $_REAL_CODEX_BIN" >&2
  exit 1
fi

# --- 2. auth file exists (existence only -- never opened) ------------------
# Fix round 1, non-blocking finding 9: `find -type f` EXCLUDES a symlink by
# accident, so a symlinked auth file silently fell through to "not logged
# in" rather than being deliberately refused for what it actually is. Check
# for a symlink FIRST, with its own reason, before the regular-file check.
auth_symlink_found=0
if [ -d "$CODEX_HOME_RESOLVED" ]; then
  while IFS= read -r -d '' _f; do
    auth_symlink_found=1
    break
  done < <(find "$CODEX_HOME_RESOLVED" -maxdepth 1 -type l -iname "*auth*" -print0 2>/dev/null)
fi
if [ "$auth_symlink_found" -eq 1 ]; then
  echo "codex_available: NOT READY: auth file under $CODEX_HOME_RESOLVED is a SYMLINK, refusing deliberately (never trusted, regardless of what it points to)" >&2
  exit 2
fi

auth_found=0
if [ -d "$CODEX_HOME_RESOLVED" ]; then
  while IFS= read -r -d '' _f; do
    auth_found=1
    break
  done < <(find "$CODEX_HOME_RESOLVED" -maxdepth 1 -type f -iname "*auth*" -print0 2>/dev/null)
fi
if [ "$auth_found" -eq 0 ]; then
  echo "codex_available: NOT READY: no auth file found under $CODEX_HOME_RESOLVED (not logged in — run 'codex login')" >&2
  exit 2
fi

# --- 3. consent marker exists AND is valid ----------------------------------
if [ -L "$CONSENT_MARKER" ]; then
  echo "codex_available: NOT READY: consent marker is a symlink, refusing (never trusted, per design)" >&2
  exit 3
fi
if [ ! -f "$CONSENT_MARKER" ]; then
  echo "codex_available: NOT READY: no consent marker at $CONSENT_MARKER (operator has not approved sending code to OpenAI -- run scripts/grant_codex_consent.sh as the operator, with sudo)" >&2
  exit 3
fi

# TEST_MODE seam for the uid==0 check ONLY (never for symlink/regular-file/
# mode/JSON-validity/scope, which stay fully real in every case). This is
# structurally the one condition a test cannot exercise honestly without
# real root: a test cannot chown a file to uid 0 without sudo either. Gated
# by the SAME inert-against-real-install discriminator as everything else
# in this script (CODEX_REVIEW_TEST_MODE=1 AND a non-real runtime dir) --
# see the header comment. Against the real install, $_TEST_TRUST_OWNER is
# always 0, so this branch can never fire there.
_TEST_TRUST_OWNER=0
if [ "$_TEST_MODE_ACTIVE" = "1" ] && [ "${CODEX_REVIEW_TEST_TRUST_OWNER:-0}" = "1" ]; then
  _TEST_TRUST_OWNER=1
fi

_CONSENT_CHECK="$("$_PYTHON_BIN" - "$CONSENT_MARKER" "$_TEST_TRUST_OWNER" <<'PY'
import json, os, stat, sys

path = sys.argv[1]
trust_owner = sys.argv[2] == "1"

try:
    st = os.lstat(path)
except Exception as e:
    print(f"stat-failed:{e}")
    sys.exit(0)

if stat.S_ISLNK(st.st_mode):
    print("is-symlink")
    sys.exit(0)
if not stat.S_ISREG(st.st_mode):
    print("not-regular-file")
    sys.exit(0)
if st.st_uid != 0 and not trust_owner:
    print(f"wrong-owner:uid={st.st_uid}")
    sys.exit(0)
mode = stat.S_IMODE(st.st_mode)
if mode != 0o444:
    print(f"wrong-mode:{oct(mode)}")
    sys.exit(0)

try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception as e:
    print(f"unparseable-json:{e}")
    sys.exit(0)

if not isinstance(data, dict):
    print("not-a-json-object")
    sys.exit(0)
if data.get("scope") != "ws4-v1-advisory":
    print(f"wrong-scope:{data.get('scope')!r}")
    sys.exit(0)

print("VALID")
PY
)"

if [ "$_CONSENT_CHECK" != "VALID" ]; then
  echo "codex_available: NOT READY: consent marker invalid: $_CONSENT_CHECK" >&2
  exit 3
fi

# --- 4. codex version: record it, and force a re-canary on a mismatch ------
# Plan §4.4: "Probes 1, 2 and 4 re-run after any `codex` version change;
# scripts/codex_available.sh records the version and forces a re-canary on a
# mismatch." Before 2026-09-23 no codex version was captured ANYWHERE on
# disk, so that sentence had no mechanism behind it at all and an upgrade
# that silently widened the sandbox was caught only by the 30-day freshness
# window, never immediately.
#
# The mechanism: compare the binary's CURRENT version against the version
# the latest PASSING canary recorded under. On a mismatch, INVALIDATE that
# canary by renaming it aside (never deleting it -- the record is evidence
# of what was measured, and of when). codex_review.sh's gate then finds no
# passing canary and refuses with exit 22, which is precisely "forces a
# re-canary".
#
# Invalidation is a RENAME, so it is non-destructive and idempotent: the
# gate globs canary_*.json, and a file renamed to
# canary_<date>.superseded-<ver>.json.invalid no longer matches that glob.
#
# This step never BLOCKS readiness by itself: a version we cannot read, or
# a canary dir we cannot write, leaves the earlier three preconditions as
# the only verdict. A version mismatch is surfaced on stderr and acted on by
# invalidating the stale record -- the refusal is then codex_review.sh's,
# via the gate that already exists, rather than a second refusal path here.
_CURRENT_VERSION=""
_ver_raw="$(env -i PATH=/usr/bin:/bin:/opt/homebrew/bin TERM=dumb \
  "$_PERL_BIN" -e 'alarm shift; exec @ARGV' 15 "$_REAL_CODEX_BIN" --version 2>/dev/null)"
if [ -n "$_ver_raw" ]; then
  _CURRENT_VERSION="$(printf '%s' "$_ver_raw" | head -n 1 | tr -d '\000' | cut -c1-200)"
fi

if [ -n "$_CURRENT_VERSION" ]; then
  _VERSION_CHECK="$("$_PYTHON_BIN" - "$CANARY_DIR" "$_CURRENT_VERSION" <<'PY'
import glob, json, os, sys

d, current = sys.argv[1], sys.argv[2]

# Find the newest PASSING canary -- the same selection codex_review.sh's own
# gate makes, so this acts on exactly the record that gate would honour.
best = None
best_path = None
for p in sorted(glob.glob(os.path.join(d, "canary_*.json"))):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        continue
    if not data.get("passed"):
        continue
    ts = data.get("ts")
    if not isinstance(ts, (int, float)):
        continue
    if best is None or ts > best:
        best, best_path = ts, p

if best_path is None:
    print("no-passing-canary")
    sys.exit(0)

try:
    with open(best_path, "r", encoding="utf-8") as fh:
        recorded = json.load(fh).get("codex_version")
except Exception:
    print("no-passing-canary")
    sys.exit(0)

if not isinstance(recorded, str) or not recorded or recorded == "unknown":
    # A canary that recorded no usable version cannot be compared. Leave it
    # alone: the 30-day freshness window is its only bound, which is the
    # pre-existing (weaker) behaviour, not a regression introduced here.
    print("version-unknown-in-record")
    sys.exit(0)

if recorded == current:
    print("version-match")
    sys.exit(0)

# MISMATCH. Rename the stale passing canary out of the gate's glob. Never
# delete: the record is evidence of what was measured under which version.
safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in recorded)[:60]
dest = best_path[:-len(".json")] + ".superseded-" + safe + ".json.invalid"
try:
    os.replace(best_path, dest)
except Exception as e:
    print(f"mismatch-invalidate-failed:{e}")
    sys.exit(0)

print(f"version-mismatch:{recorded}->{current}")
PY
)"

  case "$_VERSION_CHECK" in
    version-mismatch:*)
      echo "codex_available: codex version changed (${_VERSION_CHECK#version-mismatch:}) -- the previous passing canary was measured under a DIFFERENT codex build and has been invalidated (renamed aside, not deleted). Re-run scripts/codex_canary.sh before any review; codex_review.sh will refuse with exit 22 until you do." >&2
      ;;
    mismatch-invalidate-failed:*)
      echo "codex_available: WARNING: codex version changed but the stale canary could NOT be invalidated (${_VERSION_CHECK#mismatch-invalidate-failed:}) -- re-run scripts/codex_canary.sh manually; do not rely on the existing record." >&2
      ;;
    version-unknown-in-record)
      echo "codex_available: NOTE: the latest passing canary recorded no usable codex version, so a version-mismatch re-canary cannot be forced for it; only the 30-day freshness window bounds it." >&2
      ;;
  esac
fi

echo "codex_available: READY"
exit 0
