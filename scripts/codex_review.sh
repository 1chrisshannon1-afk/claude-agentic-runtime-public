#!/usr/bin/env bash
# codex_review.sh — hardened wrapper around `codex exec` for the cross-model
# review scaffold. Plan §5 (WS4) §4.3/§4.4/§4.4a/§4.4b/§4.8a is the spec;
# read it in full before changing this script. Fix round 1 (trust-architect,
# reviewer-of-record, blockers=5, all fixed this round) hardened every gate
# below against the specific execution-proven bypasses in that review; see
# docs/subsystems/codex-review.md for the full account.
#
# ============================================================================
# TODAY THIS SCRIPT ALWAYS REFUSES. That is correct and intended: the
# operator has no Codex account yet (2026-09-20), so codex_available.sh
# never passes, so this script never reaches the point of invoking `codex`.
# Nothing has ever been sent to OpenAI by this script. See
# docs/subsystems/codex-review.md.
# ============================================================================
#
# Usage:
#   codex_review.sh <repo_root_abs_path> -- <pathspec...>
#
# Takes ONLY a repo path and a literal pathspec. NO OTHER ARGUMENTS ARE
# ACCEPTED -- there is no "$@" pass-through to codex. Every flag codex_review.sh
# passes to `codex exec` is hard-coded in this file.
#
# ENVIRONMENT VARIABLES THIS SCRIPT HONOURS (and ONLY these -- fix round 1,
# B4, removed every other override; see docs/subsystems/codex-review.md for
# the full rationale table):
#   CODEX_REVIEW_MODEL       -- the -m value. Written into the findings file.
#   CODEX_REVIEW_TIMEOUT_SEC -- integer, 1-600 inclusive. Rejected otherwise.
#   DETECT_SECRETS_BIN       -- override for the egress-scan binary. Must be
#                                executable; still subject to B1's mandatory
#                                positive control (a scanner that cannot
#                                prove it can flag a real secret is refused
#                                regardless of what this variable names).
#   FINDINGS_OUTPUT_DIR      -- where this run's OWN findings JSON is written
#                                (defaults to the real, non-overridable
#                                findings dir below). Canary records, the
#                                schema, AGENTS.md, review-instructions.md,
#                                and the consent marker are NEVER read from
#                                this variable -- always from the runtime
#                                dir this script resolves from its own
#                                on-disk location, so a caller cannot widen
#                                what "available" means by pointing this
#                                variable at a directory it controls.
#   CODEX_REVIEW_TEST_MODE   -- "1" enables the CODEX_BIN override AND makes
#                                the real ~/.codex home resolve from
#                                $CODEX_REVIEW_TEST_HOME instead of the
#                                invoking user's real home -- but ONLY when
#                                this script's own resolved runtime dir is
#                                NOT the real $HOME/.claude (see "Test-mode
#                                discriminator" below). Sets nothing by
#                                itself; combined with CODEX_BIN/
#                                CODEX_REVIEW_TEST_HOME.
#   CODEX_BIN                -- ONLY consulted when CODEX_REVIEW_TEST_MODE=1
#                                AND the discriminator above holds. Otherwise
#                                the real, hard-coded /opt/homebrew/bin/codex
#                                is used unconditionally, with no override.
#   CODEX_REVIEW_TEST_HOME   -- ONLY consulted under the same test-mode gate,
#                                as the directory ~/.codex is resolved
#                                relative to for that run.
#   CODEX_REVIEW_TEST_TRUST_OWNER -- ONLY consulted (by codex_available.sh,
#                                forwarded here) under the same test-mode
#                                gate, and ONLY for the consent marker's
#                                root-ownership check specifically -- every
#                                other consent-marker condition (symlink,
#                                regular-file, mode 0444, JSON validity,
#                                scope) stays fully real even in test mode.
#                                This exists because a test cannot chown a
#                                file to uid 0 without sudo either; the
#                                actual root-owned positive path is
#                                UNVERIFIED by this suite, deliberately, and
#                                is stated as such in the fix-round report.
# Every OTHER variable a prior build of this script read (CODEX_AVAILABLE_SH,
# SCHEMA_FILE, AGENTS_FILE, REVIEW_INSTRUCTIONS_FILE, PYTHON_BIN, PERL_BIN,
# CLAUDE_DIR) is GONE. A caller cannot redirect the availability check, the
# schema, the prompt files, the interpreter, or the runtime-dir resolution.
# This was executed and proven exploitable in fix round 1 (B4): with nothing
# but environment variables, the reviewer drove this script to a "clean"
# exit while handing codex a real-shaped AWS key, a Stripe-shaped key, and a
# denylisted catalog file's contents.
#
# Exit codes (never overlap with "clean" -- see the OUTAGE CONTRACT below):
#    0  schema-valid AND verdict == "clean".
#    1  schema-valid WITH findings (advisory; still gates nothing).
#    2  --sweep-stale completed (a SEPARATE maintenance entry point, never
#       part of the normal <repo> -- <pathspec> invocation shape) -- a
#       distinct code from 0 so a caller can tell "the sweep ran" apart
#       from "the review was clean" without parsing stdout.
#   11  caller error (bad arguments, prohibited/flag-shaped token, repo root
#       missing or not a git repo) -- nothing invoked.
#   12  denylisted path (pathspec, diff rename/copy, or built-export file
#       list) -- refused BEFORE any codex invocation.
#   20  codex not available: binary missing/not executable, or no auth file.
#   21  consent missing or invalid (marker absent, wrong owner, wrong mode,
#       not a regular file, wrong scope, or unparseable).
#   22  no passing canary on record, or the latest passing canary is stale
#       (>30 days), or it was invalidated by codex_available.sh because the
#       codex binary's version no longer matches the one it was measured
#       under. scripts/codex_canary.sh (built 2026-09-23) is what writes a
#       passing record; it cannot itself pass until the operator logs in,
#       so this gate still cannot be satisfied today.
#   13  diff is empty -- nothing pending to review.
#   17  diff exceeds the 20,000-line cap (plan §4.5a item 4).
#   14  egress scan (detect-secrets) found something, errored, or could not
#       prove itself capable of finding anything (scanner-inert) -- hard
#       STOP, fail-closed. Never invokes codex.
#   15  codex invocation failed, timed out, produced no/invalid -o file, the
#       validator itself was unavailable, or the response exceeded the 64KB
#       cap -- OUTAGE (plan §4.5 "Outage").
#   16  internal error (stale export dir from a prior dead run, schema file
#       missing, mktemp failure, etc.) -- OUTAGE.
#  130  SIGINT delivered to the wrapper while codex was running.
#
# OUTAGE CONTRACT: every non-zero, non-{1,11,12} exit prints
# "CODEX ADVISORY OUTAGE: <reason> -- Codex is advisory and gates nothing;
# the boundary proceeds on the existing reviewer-of-record." to stderr. No
# exit path of this script can be mistaken for "review clean" by a caller
# that only checks $? -- 0 is the ONLY clean exit, 1 is findings (still
# advisory), and even on 0 the caller must read the findings file's own
# "verdict" field, never infer cleanliness from the exit code alone.

set -uo pipefail
# NOT `set -e` globally: several steps need to run cleanup (the EXIT trap)
# even after a command fails, and we want precise exit codes per failure
# class rather than bash's generic 1. Each step checks its own status.

_PYTHON_BIN="/usr/bin/python3"
_PERL_BIN="/usr/bin/perl"
_REAL_CODEX_BIN="/opt/homebrew/bin/codex"

# ---------------------------------------------------------------------------
# Runtime dir resolution -- from this script's OWN on-disk location, never
# from a caller-supplied CLAUDE_DIR/HOME. Fix round 1 B4: every
# security-relevant path (schema, AGENTS.md, review-instructions.md, the
# consent marker, canary records) is derived from here, unconditionally.
# ---------------------------------------------------------------------------
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
_RUNTIME_DIR="$(cd "$_SCRIPT_DIR/.." && pwd -P)"

# ---------------------------------------------------------------------------
# Test-mode discriminator (fix round 1 B4). CODEX_BIN and the ~/.codex
# resolution are honoured ONLY when BOTH hold:
#   (a) CODEX_REVIEW_TEST_MODE=1 is set, AND
#   (b) $_RUNTIME_DIR (resolved from THIS SCRIPT'S OWN PATH, not from any
#       caller-supplied variable) is NOT the real invoking user's
#       $HOME/.claude.
# A caller cannot satisfy (b) by setting HOME or any other variable -- the
# real home is resolved via getpwuid(getuid()), which reads the OS user
# database, not the environment. The only way to make (b) true is to
# actually invoke a COPY of this script tree living somewhere else on disk
# (which is exactly what the test suite does -- see hooks/tests/
# test_codex_review.py's _build_test_tree helper). Running the real,
# installed script from ~/.claude/scripts/ can NEVER satisfy (b), so
# CODEX_REVIEW_TEST_MODE=1 is inert against the real installation.
# ---------------------------------------------------------------------------
_REAL_USER_HOME="$("$_PYTHON_BIN" -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)' 2>/dev/null)"
_REAL_USER_CLAUDE_DIR=""
if [ -n "$_REAL_USER_HOME" ]; then
  _REAL_USER_CLAUDE_DIR="$_REAL_USER_HOME/.claude"
fi

_TEST_MODE_ACTIVE=0
if [ "${CODEX_REVIEW_TEST_MODE:-0}" = "1" ] && [ -n "$_REAL_USER_CLAUDE_DIR" ] && [ "$_RUNTIME_DIR" != "$_REAL_USER_CLAUDE_DIR" ]; then
  _TEST_MODE_ACTIVE=1
fi

if [ "$_TEST_MODE_ACTIVE" = "1" ] && [ -n "${CODEX_BIN:-}" ]; then
  CODEX_BIN_RESOLVED="$CODEX_BIN"
else
  CODEX_BIN_RESOLVED="$_REAL_CODEX_BIN"
fi

if [ "$_TEST_MODE_ACTIVE" = "1" ] && [ -n "${CODEX_REVIEW_TEST_HOME:-}" ]; then
  _CODEX_HOME_BASE="$CODEX_REVIEW_TEST_HOME"
else
  _CODEX_HOME_BASE="$_REAL_USER_HOME"
fi
REAL_CODEX_HOME="$_CODEX_HOME_BASE/.codex"

# ---------------------------------------------------------------------------
# Fixed, non-overridable paths -- all derived from $_RUNTIME_DIR.
# ---------------------------------------------------------------------------
CODEX_AVAILABLE_SH="$_SCRIPT_DIR/codex_available.sh"
SCHEMA_FILE="$_RUNTIME_DIR/tools/codex/review_schema.json"
AGENTS_FILE="$_RUNTIME_DIR/tools/codex/AGENTS.md"
REVIEW_INSTRUCTIONS_FILE="$_RUNTIME_DIR/tools/codex/review-instructions.md"
CANARY_DIR="$_RUNTIME_DIR/.review_state/codex"
CONSENT_MARKER="$_RUNTIME_DIR/.review_state/codex/CONSENT.json"
LOG_FILE="$_RUNTIME_DIR/.enforcement/log.jsonl"

# The OUTPUT dir for this run's own findings JSON may be overridden (tests
# need this to avoid writing into the real ~/.claude/.review_state/codex/),
# but this is purely a WRITE-target override -- nothing security-relevant is
# ever READ from it.
FINDINGS_OUTPUT_DIR="${FINDINGS_OUTPUT_DIR:-$CANARY_DIR}"

MODEL="${CODEX_REVIEW_MODEL:-gpt-5-codex}"

# CODEX_REVIEW_TIMEOUT_SEC: integer, 1-600 inclusive (fix round 1 B4).
# Deliberately `${VAR-180}` (no colon) rather than `${VAR:-180}`: the
# colon form treats an EXPLICITLY-SET-BUT-EMPTY value the same as unset,
# silently substituting the default -- so CODEX_REVIEW_TIMEOUT_SEC="" would
# have passed validation as if the caller never set it at all, rather than
# being rejected as the invalid input it is. The no-colon form only
# substitutes when the variable is genuinely UNSET.
_RAW_TIMEOUT="${CODEX_REVIEW_TIMEOUT_SEC-180}"
case "$_RAW_TIMEOUT" in
  ''|*[!0-9]*)
    echo "codex_review: CODEX_REVIEW_TIMEOUT_SEC must be a positive integer, got '$_RAW_TIMEOUT'" >&2
    exit 11
    ;;
esac
if [ "$_RAW_TIMEOUT" -lt 1 ] || [ "$_RAW_TIMEOUT" -gt 600 ]; then
  echo "codex_review: CODEX_REVIEW_TIMEOUT_SEC must be between 1 and 600, got '$_RAW_TIMEOUT'" >&2
  exit 11
fi
REVIEW_TIMEOUT_SEC="$_RAW_TIMEOUT"

DETECT_SECRETS_BIN="${DETECT_SECRETS_BIN:-}"

DIFF_LINE_CAP=20000
FULL_FILE_LINE_CAP=2000
FULL_FILE_COUNT_CAP=20
HUNK_CONTEXT_LINES=200
RESPONSE_BYTE_CAP=65536

# Plan §4.3 "Prohibited, permanently, in any Codex invocation this repo
# makes". Checked against every token the caller supplies before `--`.
# Fix round 1 finding 13: "-s workspace-write" / "-s danger-full-access"
# as SINGLE strings can never match a caller's SEPARATE tokens ("-s",
# "workspace-write") -- any leading-"-" token is already refused first by
# the generic flag-shape check below, so those two entries were dead. Kept
# here ONLY as documentation of what this wrapper's own hard-coded
# invocation must never contain (never checked pairwise against caller
# input, since the generic flag-shape refusal already makes that case
# unreachable); the two entries that DO match a single caller token stay.
_PROHIBITED_SUBSTRINGS=(
  "--dangerously-bypass-approvals-and-sandbox"
  "--dangerously-bypass-hook-trust"
  "--add-dir"
  "sandbox_permissions"
  "shell_environment_policy"
)

_outage() {
  # $1 = exit code, $2 = reason string.
  echo "CODEX ADVISORY OUTAGE: $2 -- Codex is advisory and gates nothing; the boundary proceeds on the existing reviewer-of-record." >&2
  exit "$1"
}

_die_caller_error() {
  echo "codex_review: $1" >&2
  exit "$2"
}

# ---------------------------------------------------------------------------
# --sweep-stale -- a SEPARATE maintenance entry point, not part of the
# normal <repo> -- <pathspec> invocation shape. Removes stale
# codex_export.* directories (which may hold a leaked credential copy from
# a run that died before its cleanup trap ran) that are older than 10
# minutes AND owned by the invoking uid. Never automatic -- only runs when
# explicitly named as the first argument. Prints each path it removes.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--sweep-stale" ]; then
  _EXPORT_ROOT="${TMPDIR:-/tmp}"
  _MY_UID="$(id -u)"
  _now_epoch="$(date +%s)"
  _swept=0
  for d in "$_EXPORT_ROOT"/codex_export.*; do
    [ -d "$d" ] || continue
    _owner_uid="$(stat -f '%u' "$d" 2>/dev/null || stat -c '%u' "$d" 2>/dev/null || echo "")"
    if [ "$_owner_uid" != "$_MY_UID" ]; then
      echo "codex_review --sweep-stale: SKIP (not owned by you): $d" >&2
      continue
    fi
    _mtime_epoch="$(stat -f '%m' "$d" 2>/dev/null || stat -c '%Y' "$d" 2>/dev/null || echo "0")"
    _age_sec=$(( _now_epoch - _mtime_epoch ))
    if [ "$_age_sec" -lt 600 ]; then
      echo "codex_review --sweep-stale: SKIP (younger than 10 minutes, age=${_age_sec}s): $d" >&2
      continue
    fi
    echo "codex_review --sweep-stale: removing $d (age=${_age_sec}s)"
    rm -rf "$d"
    _swept=$((_swept + 1))
  done
  # Fix round 2, non-blocking finding 5: --sweep-stale used to exit 0,
  # the SAME code as a genuinely clean review -- a caller checking only
  # $? could not distinguish "the sweep ran" from "the review was clean".
  # Distinct code (2) and a clear "sweep-stale:" stdout marker now make
  # this unambiguous; documented in this file's own exit-code table,
  # AGENTS.md, and docs/subsystems/codex-review.md.
  echo "codex_review: sweep-stale complete -- removed $_swept stale export director$([ "$_swept" = 1 ] && echo y || echo ies)."
  exit 2
fi

# ---------------------------------------------------------------------------
# Argument parsing -- repo_root then `--` then a literal pathspec. No other
# flags accepted from the caller, ever.
# ---------------------------------------------------------------------------
if [ $# -lt 3 ]; then
  _die_caller_error "usage: codex_review.sh <repo_root_abs_path> -- <pathspec...> | codex_review.sh --sweep-stale" 11
fi

REPO_ROOT="$1"; shift
if [ "$1" != "--" ]; then
  _die_caller_error "second argument must be literal '--' (no pass-through flags accepted): got '$1'" 11
fi
shift

PATHSPEC=("$@")
if [ "${#PATHSPEC[@]}" -eq 0 ]; then
  _die_caller_error "no pathspec supplied after --" 11
fi

for tok in "${PATHSPEC[@]}"; do
  for bad in "${_PROHIBITED_SUBSTRINGS[@]}"; do
    case "$tok" in
      *"$bad"*)
        _die_caller_error "prohibited flag-shaped token in pathspec: '$tok' (matches '$bad')" 11
        ;;
    esac
  done
  case "$tok" in
    -*)
      _die_caller_error "pathspec token looks like a flag, refusing: '$tok' (this wrapper accepts no pass-through arguments)" 11
      ;;
  esac
done

if [ ! -d "$REPO_ROOT" ]; then
  _die_caller_error "repo root does not exist: $REPO_ROOT" 11
fi
if [ ! -d "$REPO_ROOT/.git" ]; then
  _die_caller_error "repo root has no .git: $REPO_ROOT" 11
fi

# ---------------------------------------------------------------------------
# Availability gate. ALWAYS runs the real sibling codex_available.sh
# resolved from THIS SCRIPT'S OWN DIRECTORY -- fix round 1 B4 removed the
# CODEX_AVAILABLE_SH override entirely (it let a caller substitute a
# stub that always passes). Today this ALWAYS refuses (no login yet,
# no consent, no canary) -- correct.
#
# codex_available.sh's own exit codes: 1 = binary missing/not executable,
# 2 = no auth file (not logged in), 3 = consent missing/invalid. Mapped
# here to this script's own outage codes (20 = not available, 21 = consent).
# ---------------------------------------------------------------------------
_AVAIL_OUT="$(mktemp "${TMPDIR:-/tmp}/codex_avail_out.XXXXXX")" || _die_caller_error "mktemp failed" 16
# Fix round 2, non-blocking finding 1: the previous `if ! cmd; then
# _AVAIL_RC=$?` captured the NEGATED condition's own status inside the
# `then` branch -- `! cmd` succeeding (exit 0) is what put us in `then` in
# the first place, so `$?` there is always 0, never cmd's real exit code.
# Every failure silently mapped to the `*)` catch-all (exit 20), and
# exit 21 (consent missing/invalid) was UNREACHABLE regardless of what
# codex_available.sh actually reported. Fixed: run the command directly
# (no `!`), capture `$?` on the very next line, THEN branch on it.
CODEX_REVIEW_TEST_MODE="${CODEX_REVIEW_TEST_MODE:-0}" CODEX_REVIEW_TEST_HOME="${CODEX_REVIEW_TEST_HOME:-}" CODEX_REVIEW_TEST_TRUST_OWNER="${CODEX_REVIEW_TEST_TRUST_OWNER:-0}" bash "$CODEX_AVAILABLE_SH" >"$_AVAIL_OUT" 2>&1
_AVAIL_RC=$?
if [ "$_AVAIL_RC" -ne 0 ]; then
  reason="$(cat "$_AVAIL_OUT" 2>/dev/null || true)"
  rm -f "$_AVAIL_OUT"
  case "$_AVAIL_RC" in
    3) _outage 21 "codex_available.sh: consent missing/invalid: ${reason:-unknown reason}" ;;
    *) _outage 20 "codex_available.sh: not available: ${reason:-unknown reason}" ;;
  esac
fi
rm -f "$_AVAIL_OUT"

# ---------------------------------------------------------------------------
# Canary freshness gate: refuse to run at all unless a passing canary dated
# within 30 days exists at $CANARY_DIR (derived from $_RUNTIME_DIR, never
# from a caller-supplied FINDINGS_OUTPUT_DIR -- fix round 1 B4 split the
# OUTPUT dir override from every READ path, this being one of them).
# scripts/codex_canary.sh (the four-probe canary) was built 2026-09-23 and
# is what writes a passing record here. It cannot itself pass until the
# operator logs in (it propagates codex_available.sh's refusal), so this
# gate still cannot be satisfied today -- a second, independent reason
# nothing can be sent. A record can ALSO be invalidated out from under this
# gate by codex_available.sh when the codex binary's version no longer
# matches the one the canary measured (plan §4.4's version-mismatch
# re-canary), which is why the glob below only ever sees canary_*.json.
# ---------------------------------------------------------------------------
_latest_canary="$("$_PYTHON_BIN" - "$CANARY_DIR" <<'PY'
import glob, json, os, sys, time
d = sys.argv[1]
best = None
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
        best = ts
if best is not None:
    print(best)
PY
)"
if [ -z "$_latest_canary" ]; then
  _outage 22 "no passing canary on record under $CANARY_DIR (run scripts/codex_canary.sh first)"
fi
_now="$(date +%s)"
_age_days=$(( (_now - ${_latest_canary%.*}) / 86400 ))
if [ "$_age_days" -gt 30 ] || [ "$_age_days" -lt 0 ]; then
  _outage 22 "latest passing canary is ${_age_days} days old (>30-day freshness window; re-run scripts/codex_canary.sh)"
fi

# ---------------------------------------------------------------------------
# Egress denylist -- checked against the CALLER'S PATHSPEC before any diff
# is built. A denied path REFUSES THE WHOLE INVOCATION; it never silently
# drops the one file.
#
# Fix round 1 finding 5: case-sensitive match missed .jpeg/.PNG/.JPG/.PEM on
# a case-insensitive filesystem (macOS default). shopt -s nocasematch around
# the match, restored after. Added **/*.jpeg.
# ---------------------------------------------------------------------------
_DENY_GLOBS=(
  "_Config_Project/trade_kb/corpus/*"
  "_Config_Project/trade_kb/corpus_text/*"
  "repo_tooling/trade_kb/*"
  "modules/catalog_api_public/data/*"
  "*.env"
  "*.env.*"
  "*.pem"
  "*.p12"
  "*_credentials*.json"
  "*service-account*.json"
  "modules/_logs/*"
  ".playwright-mcp/*"
  "*.png"
  "*.jpg"
  "*.jpeg"
)

_deny_match() {
  # $1 = path token. Prints the matching glob and returns 0 if denied.
  # Case-INSENSITIVE (fix round 1 finding 5): macOS's default filesystem is
  # case-insensitive, so a.PEM and a.pem are the SAME file on disk; a
  # denylist that only matches lowercase gives a false sense of coverage.
  local p="$1"
  local had_nocasematch=0
  case "$-" in *H*) ;; esac
  if shopt -q nocasematch 2>/dev/null; then had_nocasematch=1; fi
  shopt -s nocasematch
  local matched=""
  for g in "${_DENY_GLOBS[@]}"; do
    case "$p" in
      $g)
        matched="$g"
        break
        ;;
    esac
  done
  if [ "$had_nocasematch" -eq 0 ]; then shopt -u nocasematch; fi
  if [ -n "$matched" ]; then
    echo "$matched"
    return 0
  fi
  return 1
}

_denied_any=0
for tok in "${PATHSPEC[@]}"; do
  if m="$(_deny_match "$tok")"; then
    echo "codex_review: DENYLISTED path in pathspec: '$tok' matches '$m'" >&2
    _denied_any=1
  fi
done
if [ "$_denied_any" -eq 1 ]; then
  echo "codex_review: refusing the WHOLE invocation (denylist), reason=denylist. Codex was NOT invoked." >&2
  echo "codex_review: recovery: re-issue with the denied path(s) removed from the pathspec." >&2
  exit 12
fi

# fixtures/integration_tests content check: deny when the file CONTAINS an
# @-bearing string or an E.164-shaped number, only for paths under
# fixtures/ or integration_tests/.
for tok in "${PATHSPEC[@]}"; do
  case "$tok" in
    */fixtures/*|fixtures/*|*/integration_tests/*|integration_tests/*)
      full="$REPO_ROOT/$tok"
      if [ -f "$full" ]; then
        if "$_PYTHON_BIN" - "$full" <<'PY'
import re, sys
p = sys.argv[1]
try:
    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
except Exception:
    sys.exit(1)
if "@" in text:
    sys.exit(0)
if re.search(r"\+\d{8,15}\b", text):
    sys.exit(0)
sys.exit(1)
PY
        then
          echo "codex_review: DENYLISTED (content check): '$tok' under fixtures/integration_tests contains an @-bearing string or phone-shaped number." >&2
          _denied_any=1
        fi
      fi
      ;;
  esac
done
if [ "$_denied_any" -eq 1 ]; then
  echo "codex_review: refusing the WHOLE invocation (denylist, content check), reason=denylist. Codex was NOT invoked." >&2
  exit 12
fi

# ---------------------------------------------------------------------------
# Rename/copy check (fix round 1 B2, hardened in fix round 2 B7).
#
# `git diff HEAD -- <pathspec>` scopes AWAY the deletion side of a rename
# when the pathspec only names the destination -- `git mv
# modules/catalog_api_public/data/Items.csv docs/readme.md` with pathspec
# `docs/readme.md` makes the denied source path appear NOWHERE in that
# scoped diff. Round 1 fixed this with a SEPARATE, unscoped name-status
# diff (both unstaged and --cached) checked against an EXACT STRING MATCH
# of the caller's raw pathspec tokens.
#
# Round 2 B7: that exact-string match is itself bypassable. `git diff HEAD
# -- <pathspec>` resolves a DIRECTORY token (e.g. `docs`) or a `./`-
# prefixed token (e.g. `./docs/readme.md`) to the files it actually
# contains -- git's own pathspec matching is prefix/normalization-aware,
# but `_pathspec_contains`'s bare `[ "$tok" = "$needle" ]` is not. Proven
# by execution: pathspec `docs` (a directory) and pathspec
# `./docs/readme.md` both bypassed the round-1 check entirely (exit 0,
# denied content reached codex) despite `git diff HEAD -- docs` and `git
# diff HEAD -- ./docs/readme.md` both genuinely including the renamed
# file.
#
# Fixed: never reason from raw tokens. Resolve the actual set of files the
# diff touches via `git diff HEAD --name-only -- "${PATHSPEC[@]}"` (the
# SAME pathspec resolution git itself uses everywhere else in this script,
# so directory/`./`-prefix/pathspec-magic tokens are handled identically
# to how the real diff build handles them a few lines below) -- then check
# each rename/copy record's DESTINATION against THAT resolved set, not the
# raw tokens.
# ---------------------------------------------------------------------------
cd "$REPO_ROOT" || _die_caller_error "cannot cd into repo root: $REPO_ROOT" 11

# The set of files git's own pathspec resolution says the caller's
# pathspec covers -- normalised the same way `git diff --name-only`
# reports paths (repo-relative, no leading ./). Includes both the
# unstaged and staged (--cached) resolution, since a purely-staged rename
# is invisible to the unstaged form.
#
# PINNED BEHAVIOR (fix round 2 B7, tested): a pathspec-magic token such as
# `:(glob)docs/**` is NOT rejected by the earlier flag-shape check (it only
# refuses a token starting with `-`, and `:` is not `-`), and because this
# resolution defers ENTIRELY to git's own `git diff --name-only --
# <pathspec>` rather than reasoning about the token itself, magic pathspecs
# resolve exactly the way git natively resolves them -- verified: a
# `:(glob)docs/**` pathspec against the same denied-rename fixture caught
# it (exit 12), with no special-case code needed, because the resolved
# file set is genuinely what git says the pathspec covers, whatever shape
# the token takes.
_RESOLVED_PATHSPEC_FILES="$(
  {
    git diff HEAD --name-only -- "${PATHSPEC[@]}" 2>/dev/null
    git diff HEAD --cached --name-only -- "${PATHSPEC[@]}" 2>/dev/null
  } | sort -u
)"

_pathspec_contains() {
  # $1 = a path to check against the RESOLVED file set (exact match against
  # git's own normalised output -- never the raw caller tokens).
  local needle="$1"
  local line
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [ "$line" = "$needle" ]; then
      return 0
    fi
  done <<< "$_RESOLVED_PATHSPEC_FILES"
  return 1
}

_check_rename_status() {
  # $1 = extra git-diff args (e.g. --cached)
  local extra="$1"
  local status_out
  status_out="$(git diff HEAD --name-status --find-renames --find-copies $extra 2>/dev/null)"
  local line src dst code
  while IFS=$'\t' read -r code src dst; do
    [ -z "$code" ] && continue
    case "$code" in
      R*|C*)
        [ -z "$dst" ] && continue
        if _pathspec_contains "$dst"; then
          if m="$(_deny_match "$src")"; then
            echo "codex_review: DENYLISTED via rename/copy: source '$src' (matches '$m') -> destination '$dst' is in the RESOLVED pathspec file set" >&2
            _denied_any=1
          fi
        fi
        ;;
    esac
  done <<< "$status_out"
}

_check_rename_status ""
_check_rename_status "--cached"

if [ "$_denied_any" -eq 1 ]; then
  echo "codex_review: refusing the WHOLE invocation (denylist, rename/copy check), reason=denylist. Codex was NOT invoked." >&2
  exit 12
fi

# ---------------------------------------------------------------------------
# Build the diff. New files must be `git add`-ed first by the CALLER (same
# requirement as record_review.py's pending_key -- git diff HEAD omits
# untracked files). This script does not stage anything itself (it never
# mutates the repo under review).
# ---------------------------------------------------------------------------
DIFF_CONTENT="$(git diff HEAD -- "${PATHSPEC[@]}" 2>/dev/null)"
DIFF_LINES=$(printf '%s\n' "$DIFF_CONTENT" | wc -l | tr -d ' ')

if [ -z "$DIFF_CONTENT" ]; then
  _outage 13 "empty diff for the given pathspec -- nothing pending to review"
fi
if [ "$DIFF_LINES" -gt "$DIFF_LINE_CAP" ]; then
  _outage 17 "diff-too-large: $DIFF_LINES lines exceeds the ${DIFF_LINE_CAP}-line cap; Codex not invoked"
fi

# Re-check the denylist against the diff's own file headers (a rename can
# still smuggle a path past the pathspec-only check above in edge cases the
# name-status check does not cover).
DIFF_FILES="$(printf '%s\n' "$DIFF_CONTENT" | grep -E '^\+\+\+ b/|^--- a/' | sed -E 's#^\+\+\+ b/##; s#^--- a/##' | sort -u)"
while IFS= read -r df; do
  [ -z "$df" ] && continue
  if m="$(_deny_match "$df")"; then
    echo "codex_review: DENYLISTED path surfaced via the diff itself (rename?): '$df' matches '$m'" >&2
    _denied_any=1
  fi
done <<< "$DIFF_FILES"
if [ "$_denied_any" -eq 1 ]; then
  echo "codex_review: refusing the WHOLE invocation (denylist, post-diff check), reason=denylist. Codex was NOT invoked." >&2
  exit 12
fi

# ---------------------------------------------------------------------------
# pending_key -- the ledger key this review's findings are stored under.
# Uses precommit_review_gate.pending_key exactly as record_review.py does,
# called from the repo root with the exact literal pathspec tokens. The
# hooks/ directory this imports from is resolved from $_RUNTIME_DIR (this
# script's own on-disk location), never from a caller variable.
# ---------------------------------------------------------------------------
PENDING_KEY="$("$_PYTHON_BIN" - "$_RUNTIME_DIR" "$REPO_ROOT" "${PATHSPEC[@]}" <<'PY'
import os, sys
runtime_dir, repo_root = sys.argv[1], sys.argv[2]
paths = sys.argv[3:]
sys.path.insert(0, os.path.join(runtime_dir, "hooks"))
import precommit_review_gate as g
key = g.pending_key(repo_root, repo_root, paths)
if key:
    print(key)
PY
)"
if [ -z "$PENDING_KEY" ] || [ "$PENDING_KEY" = "__unresolvable__" ]; then
  _outage 16 "could not derive a pending_key for this pathspec (unresolvable or empty) -- see precommit_review_gate.pending_key"
fi

# ---------------------------------------------------------------------------
# Stale-export-dir check (plan §4.8a item 6, unimplemented before this
# round): the wrapper refuses to start a NEW export if a previous one is
# still on disk -- it may hold a credential copy from a run that died
# before its trap ran. --sweep-stale (above, a SEPARATE entry point, never
# parsed as part of the normal <repo> -- <pathspec> invocation) is the only
# sanctioned way to clear one.
# ---------------------------------------------------------------------------
_EXPORT_ROOT="${TMPDIR:-/tmp}"
_stale_count=0
_stale_paths=""
for d in "$_EXPORT_ROOT"/codex_export.*; do
  [ -d "$d" ] || continue
  _stale_count=$((_stale_count + 1))
  _stale_paths="$_stale_paths $d"
  echo "codex_review: STALE export directory found: $d (may hold a credential copy from a prior run that died before cleanup)" >&2
done
if [ "$_stale_count" -gt 0 ]; then
  _outage 16 "$_stale_count stale export director$([ "$_stale_count" = 1 ] && echo y || echo ies) present under $_EXPORT_ROOT ($_stale_paths) -- run 'bash $0 --sweep-stale' to remove ones older than 10 minutes and owned by you, then retry"
fi

# ---------------------------------------------------------------------------
# Build the scratch export: EXPORT_HOME is the mktemp'd dir itself (never
# writable by group/other); EXPORT_DIR is a SUBDIRECTORY of it.
#
# Fix round 1 B3: a prior build set HOME=$EXPORT_DIR and CODEX_HOME=
# $EXPORT_DIR/.codex, with -C $EXPORT_DIR -- so the copied auth file lived
# INSIDE the directory codex's own -C working root pointed at. -s read-only
# restricts WRITES, not reads, and codex runs model-generated shell
# commands, so the auth file was `cat`-able by anything codex was talked
# into running. Now: HOME=$EXPORT_HOME (codex's -C root is the SIBLING
# $EXPORT_DIR/, never $EXPORT_HOME itself), CODEX_HOME=$EXPORT_HOME/.codex
# (also a sibling of $EXPORT_DIR, not inside it). Tested by having the fake
# codex enumerate its -C root recursively and asserting no .codex/auth file
# is reachable under it.
# ---------------------------------------------------------------------------
EXPORT_HOME="$(mktemp -d "$_EXPORT_ROOT/codex_export.XXXXXX")" || _outage 16 "mktemp failed for export dir"
chmod 700 "$EXPORT_HOME"
EXPORT_DIR="$EXPORT_HOME/export"
mkdir -p "$EXPORT_DIR"

CODEX_CHILD_PID=""
_CHILD_REAPED=0

_cleanup() {
  # The export directory (which after the egress scan passes will briefly
  # hold a COPY of the auth file, as a SIBLING of $EXPORT_DIR, never inside
  # it) is removed on EVERY exit path -- success, failure, interrupt.
  #
  # Falsifiability finding (2026-09-20, original build): bash DEFERS trap
  # execution while a foreground PIPELINE is running -- backgrounding the
  # invocation in its own process group and `wait`ing on it (which DOES
  # respond to signals promptly) plus an explicit process-GROUP kill here
  # fixed a real SIGTERM-doesn't-clean-up bug, proven by direct experiment.
  #
  # Fix round 1, non-blocking finding 1 -- STATUS: ATTEMPTED, VERIFIED
  # INSUFFICIENT, NOT SILENTLY CLAIMED FIXED. The originally-proposed fix
  # (clear CODEX_CHILD_PID only after a confirmed reap; give INT the exact
  # same cleanup path as TERM, via the two trap lines below) IS applied.
  # But falsifiability testing during this round (direct experiment,
  # 2026-09-20, multiple independent reproductions -- see the fix-round
  # report) found a DEEPER, UNFIXED problem underneath it: on this machine's
  # bash (GNU bash 3.2.57, macOS's stock /bin/bash -- the only bash present;
  # no newer version is installed, and this script's `#!/usr/bin/env bash`
  # shebang resolves to it), a registered `trap ... INT` on a plain child
  # process (bash script launched via `subprocess.Popen`, no backgrounding,
  # no job control, no `wait` involved at all in the minimal repro) simply
  # DOES NOT FIRE when SIGINT is delivered via `Popen.send_signal()` -- the
  # single most standard way any real process manager/orchestrator sends a
  # signal to a child. `trap -p INT` confirms the handler IS registered;
  # SIGTERM (same shape, replacing `TERM` for `INT` in an otherwise
  # identical test) reliably fires the trap and exits promptly; SIGINT does
  # not, with no combination of `set -m` / `wait` / foreground-vs-backgrounded
  # invocation making a difference. This is a bash-3.2/OS-level signal-
  # disposition characteristic, not something this script's trap ordering
  # can work around. Net effect: TERM-based cleanup (the documented, primary
  # outage-recovery path — see the paragraph above) is proven reliable;
  # INT-based cleanup is NOT proven reliable on this deployment target
  # despite the code being present, and must not be relied upon until a
  # newer bash is confirmed to behave differently. This is why exit 130 is
  # documented in the header as "SIGINT delivered" rather than "SIGINT
  # handled" -- the code path exists and will run correctly on a bash where
  # the trap actually fires, but this repo's own environment cannot
  # currently prove it does.
  if [ -n "$CODEX_CHILD_PID" ] && [ "$_CHILD_REAPED" -eq 0 ]; then
    kill -TERM -- "-$CODEX_CHILD_PID" 2>/dev/null
    sleep 0.2
    kill -9 -- "-$CODEX_CHILD_PID" 2>/dev/null
    _CHILD_REAPED=1
  fi
  if [ -n "${EXPORT_HOME:-}" ] && [ -d "$EXPORT_HOME" ]; then
    rm -rf "$EXPORT_HOME"
  fi
}
trap _cleanup EXIT TERM
trap '_cleanup; exit 130' INT

printf '%s\n' "$DIFF_CONTENT" > "$EXPORT_DIR/diff.patch"

# Distinct tracked files touched by the diff (bounded: 2000 lines/file, 20
# files/invocation).
_file_count=0
while IFS= read -r df; do
  [ -z "$df" ] && continue
  _file_count=$((_file_count + 1))
  dest="$EXPORT_DIR/files/$df"
  mkdir -p "$(dirname "$dest")"
  if [ "$_file_count" -le "$FULL_FILE_COUNT_CAP" ]; then
    line_count="$(git show "HEAD:$df" 2>/dev/null | wc -l | tr -d ' ')"
    if [ -n "$line_count" ] && [ "$line_count" -le "$FULL_FILE_LINE_CAP" ]; then
      git show "HEAD:$df" > "$dest" 2>/dev/null || true
      continue
    fi
  fi
  # Over either cap: windowed context instead of the full file.
  git diff HEAD -U"$HUNK_CONTEXT_LINES" -- "$df" > "$dest.windowed.patch" 2>/dev/null || true
done <<< "$DIFF_FILES"

if [ "$_file_count" -gt "$FULL_FILE_COUNT_CAP" ]; then
  cat > "$EXPORT_DIR/CAPPED_NOTICE.txt" <<EOF
This invocation touches $_file_count files, exceeding the ${FULL_FILE_COUNT_CAP}-file
full-export cap. Files beyond the cap, and any single file over
${FULL_FILE_LINE_CAP} lines, were exported as diff.patch plus a windowed
*.windowed.patch (±${HUNK_CONTEXT_LINES} lines of context per hunk) instead of
their full current text. This is a WINDOWED SLICE, not the whole file.
EOF
fi

# Fix round 1 B2 (second half): re-check the denylist against the BUILT
# EXPORT's actual file list, not only diff headers -- "again to the
# export's file list", per the plan.
while IFS= read -r -d '' exported_file; do
  rel="${exported_file#"$EXPORT_DIR/files/"}"
  [ "$rel" = "$exported_file" ] && continue
  if m="$(_deny_match "$rel")"; then
    echo "codex_review: DENYLISTED path found in the BUILT EXPORT's file list: '$rel' matches '$m'" >&2
    _denied_any=1
  fi
done < <(find "$EXPORT_DIR/files" -type f -print0 2>/dev/null)
if [ "$_denied_any" -eq 1 ]; then
  echo "codex_review: refusing (denylist, built-export check), reason=denylist. Codex was NOT invoked." >&2
  exit 12
fi

# ---------------------------------------------------------------------------
# Egress scan -- purpose-built. Runs `detect-secrets scan` with no
# baseline, no exclude, file-by-file over the assembled export tree.
#
# Fix round 1 B1 -- this scan was VACUOUS before this round: `detect-secrets
# scan` treats its argument as a repository root, and scanning an ABSOLUTE
# path outside the current working directory returns "results": {} (exit 0)
# REGARDLESS of content. Proven by execution: `detect-secrets scan
# /abs/path/leak.py` -> {} ; `cd /abs/path && detect-secrets scan leak.py`
# -> 4 findings, SAME binary, SAME file. Fixed: `cd` into $EXPORT_DIR and
# scan RELATIVE paths. A MANDATORY POSITIVE CONTROL runs first, every
# invocation: a file containing a real-shaped AWS key is written, scanned,
# and if the scanner reports it clean, the whole run REFUSES with
# `scanner-inert` -- so a future detect-secrets behavior change (or a
# broken/no-op DETECT_SECRETS_BIN override) can never silently empty this
# gate again the way it did before this round.
#
# Fix round 1 finding 6: the previous `for f in ... $(find ...)` unquoted
# word-split on whitespace, so a path containing a space was silently never
# scanned. Fixed: `find ... -print0 | while IFS= read -r -d ''`.
#
# Fix round 1 finding 7: the previous heredoc `<<PY` (unquoted delimiter)
# let bash interpolate `$out` (the scanner's own JSON output, MODEL/
# vendor-adjacent data) directly into Python SOURCE TEXT before python ever
# ran -- a latent code-injection path. Fixed: `<<'PY'` (quoted delimiter,
# no interpolation) with the JSON piped over STDIN instead.
# ---------------------------------------------------------------------------
_resolve_detect_secrets() {
  if [ -n "$DETECT_SECRETS_BIN" ] && [ -x "$DETECT_SECRETS_BIN" ]; then
    echo "$DETECT_SECRETS_BIN"
    return 0
  fi
  if command -v detect-secrets >/dev/null 2>&1; then
    command -v detect-secrets
    return 0
  fi
  if [ -x "$REPO_ROOT/.venv/bin/detect-secrets" ]; then
    echo "$REPO_ROOT/.venv/bin/detect-secrets"
    return 0
  fi
  return 1
}

DETECT_SECRETS_RESOLVED="$(_resolve_detect_secrets || true)"
if [ -z "$DETECT_SECRETS_RESOLVED" ]; then
  echo "codex_review: egress scan STOP: detect-secrets binary not found on any known path" >&2
  exit 14
fi

_HELP_SUPPORTS_ALL_PLUGINS=0
if "$DETECT_SECRETS_RESOLVED" scan --help 2>&1 | grep -q -- "--force-use-all-plugins"; then
  _HELP_SUPPORTS_ALL_PLUGINS=1
fi
_ALL_PLUGINS_FLAG=""
if [ "$_HELP_SUPPORTS_ALL_PLUGINS" -eq 1 ]; then
  _ALL_PLUGINS_FLAG="--force-use-all-plugins"
fi

_SCAN_JSON_CHECK_SRC='
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(2)
results = data.get("results", {})
sys.exit(0 if any(results.values()) else 1)
'

_scan_json_has_findings() {
  # Reads scanner JSON on STDIN. The Python SOURCE is a fixed string passed
  # via -c (never touched by scanner output -- finding 7's no-interpolation
  # guarantee is preserved this way too); scanner JSON is piped in as DATA
  # on stdin, never spliced into source text.
  #
  # Deliberately NOT `python3 - <<'PY' ... PY` here: a bare heredoc attached
  # to `python3 -` occupies the interpreter's stdin with the heredoc's OWN
  # content, so a caller's `something | this_function` pipe is silently
  # discarded -- json.load(sys.stdin) then parses the heredoc's literal
  # source text (which is not valid JSON) and always hits the except branch,
  # exit 2, regardless of what was piped in. Proven by direct execution
  # during this fix round: the heredoc form made the B1 mandatory positive
  # control ALWAYS read as scanner-inert, even though the real
  # detect-secrets output it was fed genuinely contained the AWS-key
  # finding (confirmed by capturing and inspecting that exact JSON
  # separately). `-c "<fixed source>"` leaves stdin free for the pipe.
  "$_PYTHON_BIN" -c "$_SCAN_JSON_CHECK_SRC"
}

# --- Mandatory positive control: the scanner MUST be able to find a real
# secret, scanned exactly the way the real scan below will run it (relative
# path, from inside $EXPORT_DIR), before any result from it is trusted.
_CONTROL_DIR="$EXPORT_HOME/.scan_control"
mkdir -p "$_CONTROL_DIR"
_CONTROL_FILE="$_CONTROL_DIR/positive_control.py"
# A real-shaped (non-EXAMPLE, non-placeholder) AWS access key. detect-secrets'
# AWSKeyDetector matches the AKIA-prefixed 20-char pattern independent of
# whether the trailing chars happen to spell anything -- this is not a real
# credential, it is a shape the detector is specifically built to catch.
printf 'aws_secret_access_key = "AK''IAZZ7Q4RVBN3KLMXPD"\n' > "$_CONTROL_FILE"

_control_result="$(cd "$_CONTROL_DIR" && "$DETECT_SECRETS_RESOLVED" scan $_ALL_PLUGINS_FLAG "$(basename "$_CONTROL_FILE")" 2>&1)"
_control_rc=$?
rm -f "$_CONTROL_FILE"
rmdir "$_CONTROL_DIR" 2>/dev/null || true

if [ "$_control_rc" -ne 0 ]; then
  echo "codex_review: egress scan STOP: positive-control scan itself errored: $_control_result" >&2
  exit 14
fi
if ! printf '%s' "$_control_result" | _scan_json_has_findings; then
  echo "codex_review: EGRESS SCAN REFUSED: scanner-inert -- the mandatory positive control (a real-shaped AWS key) was NOT flagged by $DETECT_SECRETS_RESOLVED. A scanner that cannot prove it can find a real secret is never trusted to say a diff is clean." >&2
  exit 14
fi

# --- Real scan, relative paths, from inside $EXPORT_DIR.
_scan_hit=0
_scan_output=""
(
  cd "$EXPORT_DIR" || exit 1
  find . -type f -print0 2>/dev/null
) | while IFS= read -r -d '' rel_f; do
  printf '%s\0' "$rel_f"
done > "$EXPORT_HOME/.scan_filelist"

_any_scan_error=0
while IFS= read -r -d '' rel_f; do
  [ -z "$rel_f" ] && continue
  out="$(cd "$EXPORT_DIR" && "$DETECT_SECRETS_RESOLVED" scan $_ALL_PLUGINS_FLAG "$rel_f" 2>&1)"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    _scan_output="$_scan_output
[scan error on $rel_f]: $out"
    _any_scan_error=1
    continue
  fi
  if printf '%s' "$out" | _scan_json_has_findings; then
    _scan_output="$_scan_output
[secret finding in $rel_f]"
    _scan_hit=1
  fi
done < "$EXPORT_HOME/.scan_filelist"
rm -f "$EXPORT_HOME/.scan_filelist"

if [ "$_scan_hit" -eq 1 ] || [ "$_any_scan_error" -eq 1 ]; then
  echo "codex_review: EGRESS SCAN STOP -- detect-secrets found or errored on the assembled export:$_scan_output" >&2
  echo "codex_review: recorded --codex owed, reason scan-stop. The boundary proceeds on the existing reviewer. Codex was NOT invoked." >&2
  mkdir -p "$FINDINGS_OUTPUT_DIR"
  "$_PYTHON_BIN" - "$FINDINGS_OUTPUT_DIR/$(echo "$PENDING_KEY" | tr ':/' '__').json" "$PENDING_KEY" <<'PY'
import json, sys, time
path, key = sys.argv[1], sys.argv[2]
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"pending_key": key, "codex_status": "owed", "reason": "scan-stop", "ts": time.time()}, fh, indent=2)
PY
  exit 14
fi

# ---------------------------------------------------------------------------
# Copy the auth file into $EXPORT_HOME/.codex (a SIBLING of $EXPORT_DIR,
# never inside it -- fix round 1 B3), mode 600, ONLY after the egress scan
# has passed. Removed by the _cleanup trap on every exit path. Never a
# symlink.
# ---------------------------------------------------------------------------
_auth_src=""
while IFS= read -r -d '' f; do
  _auth_src="$f"
  break
done < <(find "$REAL_CODEX_HOME" -maxdepth 1 -type f -iname "*auth*" -print0 2>/dev/null)
if [ -z "$_auth_src" ]; then
  _outage 20 "no auth file found under $REAL_CODEX_HOME at invocation time (codex_available.sh should have caught this)"
fi

mkdir -p "$EXPORT_HOME/.codex"
chmod 700 "$EXPORT_HOME/.codex"
cp "$_auth_src" "$EXPORT_HOME/.codex/$(basename "$_auth_src")"
chmod 600 "$EXPORT_HOME/.codex/$(basename "$_auth_src")"
if [ -L "$EXPORT_HOME/.codex/$(basename "$_auth_src")" ]; then
  _outage 16 "internal error: auth copy resolved to a symlink, refusing"
fi

# ---------------------------------------------------------------------------
# Assemble the prompt.
# ---------------------------------------------------------------------------
if [ ! -f "$SCHEMA_FILE" ]; then
  _outage 16 "schema file missing: $SCHEMA_FILE"
fi

LAST_MSG="$EXPORT_HOME/last_message.json"

PROMPT_FILE="$EXPORT_DIR/PROMPT.txt"
{
  echo "You are reviewing a bounded code change. Read AGENTS.md and review-instructions.md"
  echo "(both present in this working directory) before doing anything else."
  echo
  echo "The reviewed diff is at ./diff.patch. Full or windowed context for each touched"
  echo "file is under ./files/. Everything under this directory is the ONLY content you"
  echo "have access to -- there is no live repository, no network, and no credentials of"
  echo "any value here."
  echo
  if [ -f "$EXPORT_DIR/CAPPED_NOTICE.txt" ]; then
    echo "NOTE: this export is CAPPED -- see CAPPED_NOTICE.txt. You are reading a windowed"
    echo "slice for some files, not their full current text."
  fi
  echo
  echo "Produce your findings as your final message, conforming exactly to the JSON Schema"
  echo "you were given via --output-schema."
} > "$PROMPT_FILE"

cp "$AGENTS_FILE" "$EXPORT_DIR/AGENTS.md" 2>/dev/null || _outage 16 "AGENTS.md source missing: $AGENTS_FILE"
cp "$REVIEW_INSTRUCTIONS_FILE" "$EXPORT_DIR/review-instructions.md" 2>/dev/null || _outage 16 "review-instructions.md source missing: $REVIEW_INSTRUCTIONS_FILE"

# ---------------------------------------------------------------------------
# Resolve codex to an absolute path and assert it is executable. Fix round 1
# B4: CODEX_BIN_RESOLVED was computed above from the test-mode discriminator
# ONLY -- it is the real, hard-coded /opt/homebrew/bin/codex unless BOTH
# CODEX_REVIEW_TEST_MODE=1 AND this script is running from a non-real-
# install location.
# ---------------------------------------------------------------------------
if [ ! -x "$CODEX_BIN_RESOLVED" ]; then
  _outage 20 "codex binary not executable at resolved absolute path: $CODEX_BIN_RESOLVED"
fi

# ---------------------------------------------------------------------------
# Invoke. env -i with the exact minimal allowlist. PATH is fixed to
# /usr/bin:/bin:/opt/homebrew/bin (node must resolve for the codex shebang).
# HOME is $EXPORT_HOME (the auth copy's parent, NOT codex's -C working
# root -- fix round 1 B3). Bounded run time via the perl alarm idiom.
#
# BACKGROUNDED IN ITS OWN PROCESS GROUP, then `wait`ed on -- not run as a
# blocking foreground pipeline (see _cleanup's comment above for why).
# ---------------------------------------------------------------------------
JSON_EVENTS="$EXPORT_HOME/events.jsonl"

PROMPT_TEXT="$(cat "$PROMPT_FILE")"

set +e
set -m
(
  printf '%s' "$DIFF_CONTENT" | env -i \
    PATH=/usr/bin:/bin:/opt/homebrew/bin \
    HOME="$EXPORT_HOME" \
    TERM=dumb \
    CODEX_HOME="$EXPORT_HOME/.codex" \
    "$_PERL_BIN" -e 'alarm shift; exec @ARGV' "$REVIEW_TIMEOUT_SEC" \
    "$CODEX_BIN_RESOLVED" exec \
      -C "$EXPORT_DIR" \
      -s read-only \
      --ephemeral \
      --ignore-user-config \
      --ignore-rules \
      --skip-git-repo-check \
      -m "$MODEL" \
      --json \
      --output-schema "$SCHEMA_FILE" \
      -o "$LAST_MSG" \
      "$PROMPT_TEXT" \
    > "$JSON_EVENTS" 2>&1
) &
CODEX_CHILD_PID=$!
set +m
wait "$CODEX_CHILD_PID"
CODEX_EXIT=$?
_CHILD_REAPED=1
CODEX_CHILD_PID=""
set -e

if [ "$CODEX_EXIT" -eq 142 ]; then
  _outage 15 "codex timed out after ${REVIEW_TIMEOUT_SEC}s (perl alarm idiom exit 142 -- this is a timeout, not a finding)"
fi
if [ "$CODEX_EXIT" -ne 0 ]; then
  _outage 15 "codex exec exited non-zero ($CODEX_EXIT); see stderr/stdout captured for this run (not persisted -- ephemeral)"
fi

if [ ! -f "$LAST_MSG" ]; then
  _outage 15 "codex produced no -o output-last-message file"
fi

# ---------------------------------------------------------------------------
# 64KB response cap: TRUNCATE, i.e. refuse to parse at all, rather than
# merely flag (fix round 1, non-blocking finding 4). An oversized response
# is an OUTAGE, never partially trusted.
# ---------------------------------------------------------------------------
MSG_BYTES="$(wc -c < "$LAST_MSG" | tr -d ' ')"
if [ "$MSG_BYTES" -gt "$RESPONSE_BYTE_CAP" ]; then
  _outage 15 "response-oversize: last-message file is ${MSG_BYTES} bytes, exceeding the ${RESPONSE_BYTE_CAP}-byte cap -- discarded whole, never parsed"
fi

# ---------------------------------------------------------------------------
# Parse ONLY the -o last-message file, validated against the schema. Never
# the --json event stream. A fake/injected "verdict: clean" inside the
# event stream is NEVER read as a verdict.
#
# Fix round 1 B5: `jsonschema` is now MANDATORY. A prior build fell back to
# a required-keys-only check when `import jsonschema` failed, which
# ACCEPTED a message with "ROGUE_KEY", "severity":"CATASTROPHE",
# "class":"made-up" as verdict=clean (none of those are in the schema's
# enums, but the fallback never checked enums, only key PRESENCE). Fixed:
# no fallback. If the validator cannot be imported, that is an OUTAGE
# (exit 15, reason validator-unavailable) -- never a degraded pass.
# ---------------------------------------------------------------------------
VALIDATION_RESULT="$("$_PYTHON_BIN" - "$LAST_MSG" "$SCHEMA_FILE" <<'PY'
import json, sys
msg_path, schema_path = sys.argv[1], sys.argv[2]
try:
    import jsonschema  # type: ignore
except ImportError as e:
    print(f"OUTAGE:validator-unavailable:{e}")
    sys.exit(0)
try:
    with open(msg_path, "r", encoding="utf-8") as fh:
        msg = json.load(fh)
except Exception as e:
    print(f"INVALID:parse-error:{e}")
    sys.exit(0)
try:
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
except Exception as e:
    print(f"INVALID:schema-load-error:{e}")
    sys.exit(0)
try:
    jsonschema.validate(msg, schema)
except Exception as e:
    print(f"INVALID:schema-error:{e}")
    sys.exit(0)
print("VALID")
PY
)"

if [[ "$VALIDATION_RESULT" == OUTAGE:validator-unavailable:* ]]; then
  _outage 15 "validator-unavailable: $VALIDATION_RESULT"
fi

if [[ "$VALIDATION_RESULT" != VALID* ]]; then
  echo "codex_review: last-message schema validation FAILED: $VALIDATION_RESULT" >&2
  echo "codex_review: recorded --codex down, reason schema-invalid. Message discarded whole." >&2
  mkdir -p "$FINDINGS_OUTPUT_DIR"
  "$_PYTHON_BIN" - "$FINDINGS_OUTPUT_DIR/$(echo "$PENDING_KEY" | tr ':/' '__').json" "$PENDING_KEY" "$VALIDATION_RESULT" <<'PY'
import json, sys, time
path, key, reason = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"pending_key": key, "codex_status": "down", "reason": "schema-invalid", "detail": reason, "ts": time.time()}, fh, indent=2)
PY
  exit 15
fi

# ---------------------------------------------------------------------------
# Parser-side hardening (fix round 1, non-blocking finding 3): DROP any
# finding whose `file` is not inside the pathspec/export (proven
# exploitable: "file":"../../../etc/passwd" was written VERBATIM into the
# findings file by a prior build); STRIP URL-shaped and shell-command-shaped
# substrings from every free-form string field, replacing with
# "[url removed]" / "[command removed]"; bound field lengths (schema already
# does this structurally, re-asserted here defensively). Top-level at-rest
# labels are added so nothing downstream mistakes this file's content for
# anything but untrusted vendor output describing a diff.
# ---------------------------------------------------------------------------
mkdir -p "$FINDINGS_OUTPUT_DIR"
FINDINGS_PATH="$FINDINGS_OUTPUT_DIR/$(echo "$PENDING_KEY" | tr ':/' '__').json"

# Fix round 2 B6: _PATHSPEC_JSON is now passed to the Python block via a
# FILE, referenced by PATH on argv -- never interpolated into Python source
# text. The pre-fix shape expanded it inside a `'''...'''` triple-quoted
# literal in an UNQUOTED `<<PYOUTER` heredoc -- json.dumps() does not
# escape a `'''` sequence inside a string, so a pathspec token containing
# literal `'''` broke out of the string literal and was parsed as
# executable Python source in the ORCHESTRATOR's own process (arbitrary
# code execution, not merely a data bug) -- proven by execution: a
# crafted-name file, passed as the pathspec, drove open().write() to run
# and write a sentinel file. Same bug class as the scan-JSON heredoc fixed
# in round 1 B1 -- this was the ONE remaining site in the script.
#
# The heredoc delimiter is QUOTED (`<<'PYOUTER'`, no interpolation of ANY
# kind happens inside it). Data does NOT arrive via a piped stdin: a
# command with BOTH a pipe into it AND a heredoc attached gives the heredoc
# stdin, silently discarding the pipe -- proven by direct experiment while
# building this fix (`printf X | python3 - <<'H' ... H` fed python neither
# X alone nor the heredoc alone, but a garbled CONCATENATION of the two,
# because the heredoc wins the fd0 slot and the pipe's writer either blocks
# or is simply never read; every test in TestParserHardening went from
# passing to failing with a JSONDecodeError under an earlier draft of this
# fix that used exactly that shape). Fixed: _PATHSPEC_JSON is written to a
# throwaway file inside $EXPORT_HOME (already trap-cleaned on every exit
# path) and its PATH is passed as an ordinary argv argument; the file's
# CONTENT is still never Python source text, only ever read as data via
# `open(path).read()`.
_PATHSPEC_JSON="$("$_PYTHON_BIN" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${PATHSPEC[@]}")"
_PATHSPEC_JSON_FILE="$EXPORT_HOME/.pathspec.json"
printf '%s' "$_PATHSPEC_JSON" > "$_PATHSPEC_JSON_FILE"

"$_PYTHON_BIN" - "$LAST_MSG" "$FINDINGS_PATH" "$PENDING_KEY" "$MODEL" "$_PATHSPEC_JSON_FILE" <<'PYOUTER'
import json, re, sys, time

msg_path, out_path, key, model, pathspec_json_path = (
    sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
)
with open(pathspec_json_path, "r", encoding="utf-8") as fh:
    allowed_paths = set(json.load(fh))

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Pre-existing bug found and fixed while diagnosing the fix round 2 B6
# change (unrelated to B6 itself, but a real defect): \\\$\\( in a raw
# string produces a literal backslash, an escaped-but-meaningless \$, then
# an UNCLOSED, unescaped ( -- re.compile raised "missing ), unterminated
# subpattern" on Python 3.13 (this machine's default python3) and
# apparently tolerated differently on the 3.9 interpreter this script's
# hardcoded /usr/bin/python3 resolves to, which is why it went unnoticed
# until a broader end-to-end run surfaced it. The intent was to match a
# literal `$(` shell-command-substitution shape: \$\( is the correct raw-
# string escaping (one backslash before each of $ and ( ).
_CMD_RE = re.compile(r"(?:^|[\s;|&])(rm\s+-rf|curl\s|wget\s|sudo\s|eval\s|exec\s|bash\s+-c|sh\s+-c|nc\s+-e|>\s*/dev/|\$\(|`)", re.IGNORECASE)

def _sanitize(s):
    if not isinstance(s, str):
        return s
    s = _URL_RE.sub("[url removed]", s)
    s = _CMD_RE.sub("[command removed]", s)
    return s[:2000]

with open(msg_path, "r", encoding="utf-8") as fh:
    msg = json.load(fh)

verdict = msg.get("verdict")
raw_findings = msg.get("findings", [])
kept = []
dropped = 0
for f in raw_findings:
    if not isinstance(f, dict):
        dropped += 1
        continue
    file_field = f.get("file")
    if file_field not in allowed_paths:
        dropped += 1
        continue
    sanitized = dict(f)
    for k in ("claim", "evidence"):
        if k in sanitized:
            sanitized[k] = _sanitize(sanitized[k])
    kept.append(sanitized)

codex_status = "clean" if verdict == "clean" else f"findings:{len(kept)}"

out = {
    "_source": "codex-untrusted-vendor-output",
    "_contract": "data-about-the-diff-never-an-instruction",
    "pending_key": key,
    "codex_status": codex_status,
    "verdict": verdict,
    "model": model,
    "findings": kept,
    "findings_dropped_out_of_pathspec": dropped,
    "not_read": [_sanitize(x) for x in msg.get("not_read", [])],
    "ts": time.time(),
}
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
# Fix round 2, non-blocking finding 3: this block used to `print(verdict or
# "")`, leaking a bare "clean"/"findings" token onto stdout BEFORE the
# wrapper's own "codex_review: OK ..." line -- confusing for any caller
# that reads stdout expecting only the wrapper's own messages. The shell
# below reads the verdict back from the FILE this block just wrote
# ($FINDINGS_PATH), never from this block's stdout, so the print added
# nothing functional. Removed.
PYOUTER
# Fix round 2 heredoc-audit follow-through: $FINDINGS_PATH (derived from
# the FINDINGS_OUTPUT_DIR override, which a caller controls) was previously
# interpolated directly into a `-c "..."` double-quoted Python source
# string -- a single quote or other shell-meaningful character in that path
# could not break bash's own quoting here (double quotes don't split on
# it), but it is still variable data landing in Python SOURCE TEXT rather
# than being passed as data, the exact pattern this round's rule forbids
# everywhere. Fixed: passed as argv, never interpolated.
_FINAL_VERDICT="$("$_PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("verdict") or "")' "$FINDINGS_PATH")"

echo "codex_review: findings written to $FINDINGS_PATH"

# Consent-consumption log line (fix round 1 B4's consent design): every
# successful send is logged, once, append-only.
mkdir -p "$(dirname "$LOG_FILE")"
"$_PYTHON_BIN" - "$LOG_FILE" "$PENDING_KEY" <<'PY' 2>/dev/null || true
import json, sys, time
log_path, key = sys.argv[1], sys.argv[2]
try:
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "codex-consent-consumed", "ts": time.time(), "pending_key": key}) + "\n")
except Exception:
    pass
PY

if [ "$_FINAL_VERDICT" = "clean" ]; then
  echo "codex_review: OK verdict=clean"
  exit 0
else
  echo "codex_review: OK verdict=$_FINAL_VERDICT (findings present -- advisory, gates nothing)"
  exit 1
fi
