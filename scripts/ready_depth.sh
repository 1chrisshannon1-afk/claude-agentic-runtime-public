#!/usr/bin/env bash
# ready_depth.sh — cheap Ready-column depth SENSOR for a GitHub Project (dev
# runtime, product-agnostic).
#
# WHY THIS EXISTS
# ----------------
# `plan_lane_control_adoption_master_2026_09_20.md` §2 Phase E ("Event-driven
# Ready refill"): the daily oversight job must know whether the operator's
# hand-pick queue (`Ready #1`, per Phase A's board-steward ruling — F12) has
# run low, so it can dispatch a refill pass. This script answers ONLY that
# question — "how many OPEN items currently sit in a named Status column?" —
# and does nothing else. It is a SENSOR, not an actuator:
#
#   * It NEVER writes to the board. Every `gh` call this script makes is a
#     read. There is no --apply flag and there never should be one — a
#     caller that wants to REFILL the column runs a different tool
#     (priority_backfill.py's `reset-ready`/backfill machinery, or whatever
#     Phase E's own refill pass turns out to be) against this script's exit
#     code / printed count, never inside this script.
#   * It prints exactly one machine-parseable line on success
#     (`READY_DEPTH=<n>`, or `READY_DEPTH=>=<n>` above the --limit cap — see
#     WHY STDOUT PRINTS A LOWER BOUND below) and nothing else on stdout, so
#     a caller can do `n="$(ready_depth.sh ... | grep -o '[0-9]*')"` (this
#     extraction is CORRECT even against the capped `>=` form, since the
#     digits are still a valid lower bound) or, more robustly, act on the
#     EXIT CODE alone (see EXIT CODES below) without parsing stdout at all
#     — the exit code is the authoritative signal; stdout is a convenience.
#
# THIS IS A PRODUCT-AGNOSTIC RUNTIME SCRIPT: --owner/--repo/--project/--status
# are always caller-supplied flags, never hardcoded, exactly like
# priority_backfill.py (see that script's own module docstring) — it runs
# against one product's project board today, but nothing in this file may
# assume that, and it carries no default owner, repo or project number.
#
# GRAPHQL BUDGET — WHY THIS DOES NOT DO A FULL BOARD READ
# -----------------------------------------------------------
# priority_backfill.py measured a full `gh project item-list` board read
# (the whole board, ~1,500-1,800 items) at ~1,834 GraphQL points out of the
# account's 5,000-points/hour budget — a budget SHARED by every Claude
# session on this machine (see that script's module docstring and
# docs/subsystems/board-state.md). A sensor invoked once a day by the
# oversight job, forever, must not pay anywhere near that cost per run.
#
# `gh project item-list` accepts a server-side `--query` filter (GitHub's
# Projects filter syntax — see `gh project item-list --help`), e.g.
# `--query 'status:"Ready #1" is:open'`. GraphQL point cost for this command
# is dominated by the number of items the RESPONSE actually returns, not by
# the size of the underlying board (this is priority_backfill.py's own
# documented basis for why a --from-plan per-issue check costs ~2 points
# instead of ~1,834 — cost tracks returned object count). So a query
# server-side-filtered to ONE status column, with --limit capped just above
# the threshold this script is checking, returns at most
# `(threshold + 1)` item nodes regardless of how many thousand items sit on
# the rest of the board — this is the entire cost-avoidance mechanism.
#
# This is NOT the full-board-read path `priority_backfill.py plan` uses, and
# it does not need to be: this script only ever needs to know "is the count
# below N?", never the board's full contents, so capping --limit at
# `threshold + 1` is sufficient to answer that question exactly (if the
# filtered response returns fewer than `threshold + 1` rows, that IS the
# true count; if it returns exactly `threshold + 1`, the true count is
# >= threshold + 1, i.e. "not below threshold" either way, without needing
# the exact number). See `_query_ready_count` below.
#
# WHY STDOUT PRINTS A LOWER BOUND, NOT AN EXACT COUNT, ABOVE THE CAP
# --------------------------------------------------------------------
# When the response returns >= fetch_limit rows, the true column depth could
# be anywhere from fetch_limit to the full board size — this script never
# fetched enough rows to know which. Printing that row count as if it were
# the exact `READY_DEPTH` would be a lower bound silently presented as a
# precise fact to any log/trend reader that doesn't also read this script's
# source. So stdout marks a capped read distinctly: `READY_DEPTH=>=<n>`
# (see `_query_ready_count` and EXIT CODES below) rather than `READY_DEPTH=
# <n>`. A `>=` prefix was chosen over a second `READY_DEPTH_CAPPED=1` line
# because the EXIT CODE, not stdout, is already the authoritative
# below/not-below-threshold signal for an unattended caller (see EXIT CODES)
# — stdout exists for a human/log reader, and a single self-describing line
# is easier for that reader to get right than two lines whose relationship
# must be inferred.
#
# What a stdout-parsing caller actually gets (measured, not assumed — an
# earlier version of this comment claimed such a caller would "fail loudly",
# and that was FALSE):
#   * `grep -o '[0-9]*'`  (the idiom recommended above) yields `11` from
#     `>=11` with NO error. That is a valid LOWER BOUND, which is sufficient
#     for the below-threshold decision and INSUFFICIENT for trending.
#   * `cut -d= -f2` yields `>`; `sed` yields `>=11`. Both are non-numeric,
#     so a `[ "$n" -lt N ]` test errors and the condition is false.
# Neither "fails loudly"; both fail toward NO REFILL, which is the safe
# direction. The exit code remains the only exact channel.
#
# `totalCount` ON THE PROJECT-ITEMS CONNECTION: NOT USED, NOT VERIFIED
# --------------------------------------------------------------------
# If `gh project item-list --format json`'s underlying GraphQL response
# exposes the connection's `totalCount` field (the pre-pagination total
# matching the query filter, independent of `--limit`), that would be a
# strictly better source than counting `--limit`-capped `items` — it would
# dissolve the need for this lower-bound marker entirely. This was checked,
# without any live call against the shared board budget: `gh project
# item-list --help` documents only `--format`/`--limit`/`--owner`/`--query`/
# `--jq`/`--template` and says nothing about the JSON shape; `strings` on
# the installed `gh` binary (2.88.1) turned up a `totalCount`-bearing
# embedded GraphQL query, but it is shaped `projectItems(first:100){...
# status:fieldValueByName...totalCount}` — a hardcoded `first:100` with a
# single-field `status` selector and no `--query`/`--limit` plumbing, which
# does not match `item-list`'s caller-supplied `--limit`/`--query` contract
# and more plausibly belongs to a different command (e.g. one that reports
# which project an issue belongs to). This is INCONCLUSIVE, not a
# confirmation either way. Establishing it properly needs either a live
# call (`gh api graphql` with a hand-written query against the real
# project, or `gh project item-list --format json` compared field-by-field
# against `-q`) or reading the `cli/cli` Go source directly — both out of
# scope for a budget-constrained fix. Until then: this script does NOT rely
# on `totalCount`, and the capped case is handled via the lower-bound
# marker above. Re-investigating `totalCount` is a real, better fix for a
# future change, once the shared GraphQL budget allows a small verifying
# call.
#
# VERIFICATION STATUS OF THE --query SERVER-SIDE FILTER (honest, as of
# 2026-09-21): a `--query 'label:"..."'` filter was independently confirmed
# to genuinely filter server-side (not merely accepted-and-ignored) via a
# positive control (a real label comes back) and a negative control (a
# nonexistent label returns 0). `status:"..."` is a DIFFERENT filter
# dimension on the same syntax and has NOT been independently confirmed the
# same way — the live budget at the time this script was built was too thin
# (measured 398/5000 remaining, shared by concurrent sessions) to safely run
# even a small-`--limit` positive/negative control pair without risking
# starving other work, so this claim is REASONED (the documented filter
# syntax lists `status:` as a first-class qualifier, and GraphQL cost is
# known to track RETURNED node count for this command generally) but NOT
# independently verified with both controls the way `label:` was. Before
# trusting this in a real refill decision: run the two-control check
# (`--query 'status:"Ready #1" is:open'` returns a plausible-but-bounded
# count; `--query 'status:"NoSuchStatusJunkXYZ" is:open'` returns 0) with a
# small `--limit`, and report what it cost.
#
# This script's cost claim overall has NOT been measured against a live
# board (built and tested entirely under a fake-`gh` harness, per the
# standing rule not to run board-touching commands casually against the
# shared live budget while other work is in flight). Treat the cost claim
# above as REASONED, not measured, until a first real run's printed
# "raw items returned" stderr line (see DISCONFIRMABILITY in
# `_query_ready_count` below) confirms it.
#
# `gh api rate_limit` (the REST endpoint) MISREPORTS the GraphQL budget as a
# constant 5000/5000 regardless of actual usage (priority_backfill.py,
# measured live 2026-09-20) — this script NEVER uses it. The only truthful
# query, used here exactly as priority_backfill.py uses it:
#
#     gh api graphql -f query='query{rateLimit{remaining resetAt}}'
#
# `--min-budget N` (default 50 — this script's own reads are cheap; see
# above) refuses BEFORE any other read when the live remaining budget is
# below N. `--min-budget 0` deliberately waives the gate (prints a WAIVED
# line, exactly like priority_backfill.py's own convention), and a
# negative value is rejected at parse time.
#
# DISTINGUISHING "COUNTED 0" FROM "COULD NOT COUNT" (issue #5841)
# ---------------------------------------------------------------
# priority_backfill.py (issue #5841 — a live defect in that sibling script)
# showed that a schema-conforming GraphQL response can carry BOTH `data` and
# a non-null count AND an `errors` array (a partial-success response at HTTP
# 200) — naively reading only the count field manufactures a confident zero
# out of a response that actually failed. For THIS script the failure mode
# would be worse than a wrong number: a caller reading "Ready #1 is empty"
# when the query actually failed would trigger a SPURIOUS refill of ~30
# items into a column that was never actually empty.
#
# This script therefore:
#   * treats a `gh` non-zero exit as a hard failure (exit 2, see EXIT CODES)
#   * treats stdout that fails to `jq` parse as a hard failure (exit 2)
#   * treats a response carrying a top-level `errors` key (even alongside a
#     present `items` array) as a hard failure (exit 2) — a partial-success
#     shape is never trusted for a count
#   * NEVER prints `READY_DEPTH=0` (or any number) unless the read is fully
#     confirmed successful — there is no code path from "read failed" to a
#     printed 0, by construction: the only place COUNT is ever printed is
#     after the exit-code and jq and errors-key checks have all passed.
#
# GUARDING VALUE-TAKING FLAGS (issue #5839)
# -------------------------------------------
# `gh_issue.sh`'s arg-parse loop uses `shift 2` for every value-taking flag
# (e.g. `--triage) TRIAGE="${2:-}"; shift 2 ;;`). When such a flag is the
# LAST argv token, `$#` is 1: `shift 2` on a 1-element argv is a bash ERROR
# — it returns non-zero and shifts NOTHING. `$1` is unchanged, the `case`
# re-matches the same flag, and the loop spins forever (confirmed live,
# 2026-09-21, `gh_issue.sh create --title x --triage` hangs). The `${2:-}`
# default protects the ASSIGNMENT but does nothing for the SHIFT.
#
# Every value-taking flag in this script's parse loop is guarded with an
# explicit `[ $# -ge 2 ]` check BEFORE the shift, so a trailing value-taking
# flag with no value FAILS FAST (exit 2, a clear message) instead of hanging
# — see `_require_value` below, used at every flag site.
#
# EXIT CODES
# -----------
#   0  success — the count was read and IS below --threshold (a caller
#      dispatching "refill when low" should act on this)
#   1  success — the count was read and is NOT below --threshold (no refill
#      needed); ALSO returned by --help
#   2  the count could NOT be determined — a `gh`/`jq` read failure, an
#      unparsable response, a GraphQL `errors` response (even a partial one
#      alongside real data — see issue #5841 above), or an argument error
#      (a malformed flag, a missing required flag, a trailing value-taking
#      flag with no value — see issue #5839 above). NEVER conflated with
#      "counted 0" — no code path prints a count on this exit.
#   3  refused before any read: the live GraphQL budget is below
#      --min-budget (or the budget query itself failed — fail-closed,
#      exactly like priority_backfill.py's own --min-budget contract:
#      an unreadable budget is treated as "cannot proceed", never as
#      "unknown, carry on")
#
# This 0-vs-1 split (rather than "0 always means success, check stdout") is
# DELIBERATE: the module's whole reason for existing is "the daily oversight
# job dispatches the refill when Ready #1 < threshold" — encoding that
# decision directly in the exit code means the calling shell can write
# `if ready_depth.sh ...; then dispatch-refill; fi` with no stdout parsing
# at all, which is the single most failure-resistant way to wire a sensor
# into an unattended job. The printed READY_DEPTH=<n> (or READY_DEPTH=>=<n>
# above the --limit cap — see WHY STDOUT PRINTS A LOWER BOUND above) line is
# kept for a human/log-reading caller. The EXIT CODE is always an exact
# below/not-below-threshold decision (0/1), computed once from the same `$n`
# both channels share, never re-derived independently — but stdout itself is
# NOT always an exact count once the read is capped: a capped stdout line
# and the exit code always AGREE on the below/not-below-threshold verdict,
# they just don't both carry the same numeric precision. A caller that
# wants the exact count, not just the verdict, must use --threshold high
# enough that the real count never reaches the cap, or must not rely on
# stdout at all above whatever cap it expects.
#
# THRESHOLD LOCATION: THE SCRIPT, VIA --threshold (default 10)
# -----------------------------------------------------------------
# The plan text leaves this open ("Decide and DOCUMENT whether that
# threshold lives in the script... or in the caller"). Decision: the
# threshold is a `--threshold` FLAG on this script, defaulting to 10 (the
# plan's own stated number). Rationale:
#   * A sensor whose pass/fail boundary is invisible in its own --help is
#     harder to reason about than one where `ready_depth.sh --help` shows
#     the exact number a caller is depending on.
#   * Keeping the default value's PROVENANCE (Phase E's "< 10") right next
#     to the flag that implements it, in the file that owns the comparison,
#     is what let `_below_threshold` above stay a single computation the
#     exit code and stdout both defer to — pushing the comparison out to
#     every caller (systemd/launchd wrapper, oversight job prompt,
#     `/lane-cleanup`) would mean re-deriving "10" in N places, with N
#     independent chances to drift from the plan's own number.
#   * The caller still fully controls the decision: it can always override
#     via `--threshold N` (exactly as priority_backfill.py exposes
#     `--min-budget` and `--limit` as overridable-but-defaulted flags), so
#     "lives in the script" here means "has a sane, documented default
#     matching the plan text", never "hardcoded, caller can't change it".
#
# USAGE
# ------
#   ready_depth.sh --owner O --project N [--status "Ready #1"]
#                   [--repo OWNER/NAME] [--threshold N] [--min-budget N]
#
#   --owner O          GitHub org/user that owns the project (required).
#   --project N        Project number (required).
#   --status S         Status column to count (default "Ready #1" — Phase
#                       C's board-steward ruling, F12/Phase A.3: this is the
#                       operator's hand-pick queue, distinct from the
#                       agent/wheel queue "Ready #2").
#   --repo OWNER/NAME  Optional. If given, passed through to `gh project
#                       item-list`'s --query as an additional `repo:` filter
#                       term — NOT independently verified against a live
#                       multi-repo board (this script has only ever been run
#                       under a fake-gh harness); omit it to count the
#                       column across the whole project exactly as `gh
#                       project item-list --query` would on its own.
#   --threshold N      Below-this-count triggers exit 0 (default 10 — see
#                       THRESHOLD LOCATION above).
#   --min-budget N     Refuse (exit 3) if live remaining GraphQL budget is
#                       below N before any read (default 50; 0 waives the
#                       gate; negative rejected).
#
# NETWORKING: every read goes through `gh` directly (`gh api graphql` for
# the budget check, `gh project item-list` for the count) — this script
# never calls `gh_issue.sh` or any other wrapper, since it performs no
# writes and needs no write helper.

# Deliberately NOT `set -e` / `pipefail`: this script's contract is its EXIT CODES
# (0 below threshold, 1 not below, 2 count failed, 3 budget refused). Every `gh` /
# `jq` call below captures its own status (`rc=$?`) and maps a failure to one of
# those codes; `-e` would end the run with the shell's own status before the
# mapping, and `pipefail` would change which stage of a pipe a status is read from.
# `-u` stays on.
set -u

# --------------------------------------------------------------------------
# Overridable seams for tests (mirrors priority_backfill.py's PRIORITY_
# BACKFILL_GH_BIN-style env override convention).
# --------------------------------------------------------------------------
GH_BIN="${READY_DEPTH_GH_BIN:-gh}"
JQ_BIN="${READY_DEPTH_JQ_BIN:-jq}"

# Exit codes (see EXIT CODES in the header comment above).
EXIT_BELOW_THRESHOLD=0
EXIT_NOT_BELOW_THRESHOLD=1
EXIT_COUNT_FAILED=2
EXIT_BUDGET_REFUSED=3

_err() { echo "ready_depth: $*" >&2; }
_die_arg() { _err "$*"; exit "$EXIT_COUNT_FAILED"; }
_die_budget() { _err "$*"; exit "$EXIT_BUDGET_REFUSED"; }

_usage() {
  cat <<'USAGE'
usage: ready_depth.sh --owner O --project N [--status "Ready #1"]
                       [--repo OWNER/NAME] [--threshold N] [--min-budget N]

Counts OPEN items in one GitHub Project Status column and exits 0 if the
count is below --threshold (default 10), 1 if not, 2 if the count could not
be determined, 3 if refused for insufficient GraphQL budget. Prints exactly
one line on success: READY_DEPTH=<n> (or READY_DEPTH=>=<n> if the true count
exceeds the internal read cap -- see the script's own header comment).
Never writes to the board.
USAGE
}

# --------------------------------------------------------------------------
# Argument parsing (issue #5839 guard: every value-taking flag checks it has
# a value BEFORE shifting, so a trailing bare flag fails fast instead of
# looping forever on a failed `shift 2`).
# --------------------------------------------------------------------------

OWNER=""
PROJECT=""
STATUS="Ready #1"
REPO=""
THRESHOLD="10"
MIN_BUDGET="50"

# _require_value <flag-name> <remaining-argc> — the #5839 guard used at
# every value-taking flag site below. `gh_issue.sh`'s bug was a bare
# `shift 2` on a 1-element argv (rc=1, shifts nothing, infinite loop this
# case statement would otherwise re-enter). Checking argc BEFORE ever
# touching $2/shift closes that off entirely: a trailing bare flag exits
# immediately (EXIT_COUNT_FAILED) rather than spinning.
_require_value() {
  local flag="$1" argc="$2"
  if [ "$argc" -lt 2 ]; then
    _die_arg "$flag requires a value (it was the last argument)"
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --owner)
      _require_value "--owner" "$#"
      OWNER="$2"; shift 2
      ;;
    --project)
      _require_value "--project" "$#"
      PROJECT="$2"; shift 2
      ;;
    --status)
      _require_value "--status" "$#"
      STATUS="$2"; shift 2
      case "$STATUS" in
        *'"'*) _die_arg "--status must not contain a double-quote character (breaks the --query string's own quoting): got '$STATUS'" ;;
      esac
      ;;
    --repo)
      _require_value "--repo" "$#"
      REPO="$2"; shift 2
      case "$REPO" in
        *'"'*) _die_arg "--repo must not contain a double-quote character (breaks the --query string's own quoting): got '$REPO'" ;;
      esac
      ;;
    --threshold)
      _require_value "--threshold" "$#"
      THRESHOLD="$2"; shift 2
      ;;
    --min-budget)
      _require_value "--min-budget" "$#"
      MIN_BUDGET="$2"; shift 2
      ;;
    --help|-h)
      _usage
      exit "$EXIT_NOT_BELOW_THRESHOLD"
      ;;
    -*)
      _die_arg "unknown flag: $1"
      ;;
    *)
      _die_arg "unexpected positional argument: $1 (this script takes flags only)"
      ;;
  esac
done

[ -n "$OWNER" ] || _die_arg "--owner is required"
[ -n "$PROJECT" ] || _die_arg "--project is required"

case "$PROJECT" in
  ''|*[!0-9]*) _die_arg "--project must be a positive integer (got '$PROJECT')" ;;
esac
case "$THRESHOLD" in
  ''|*[!0-9]*) _die_arg "--threshold must be a non-negative integer (got '$THRESHOLD')" ;;
esac
case "$MIN_BUDGET" in
  ''|*[!0-9]*) _die_arg "--min-budget must be a non-negative integer (got '$MIN_BUDGET')" ;;
esac

command -v "$GH_BIN" >/dev/null 2>&1 || _die_arg "$GH_BIN CLI not found"
command -v "$JQ_BIN" >/dev/null 2>&1 || _die_arg "$JQ_BIN not found"

# --------------------------------------------------------------------------
# Budget awareness — mirrors priority_backfill.py's assert_min_budget:
# `gh api rate_limit` (REST) misreports the GraphQL budget as a constant
# 5000/5000 regardless of real usage; the only truthful query is the one
# below. A failure of the budget query itself is fail-closed (treated as a
# refusal), never "unknown, proceed anyway".
# --------------------------------------------------------------------------

_check_budget() {
  local min_budget="$1"
  if [ "$min_budget" -eq 0 ]; then
    _err "budget gate WAIVED (--min-budget 0) -- no minimum enforced."
    return 0
  fi
  local resp remaining stderr_file stderr_text
  # stdout/stderr captured separately -- same rationale as _query_ready_count
  # below: stray stderr text must never leak into the value we jq-parse.
  stderr_file="$(mktemp "${TMPDIR:-/tmp}/ready_depth_stderr.XXXXXX")"
  resp="$("$GH_BIN" api graphql -f query='query{rateLimit{remaining resetAt}}' 2>"$stderr_file")"
  local rc=$?
  stderr_text="$(cat "$stderr_file" 2>/dev/null)"
  rm -f "$stderr_file" 2>/dev/null
  if [ "$rc" -ne 0 ]; then
    _die_budget "could not verify the GraphQL rate-limit budget (gh api graphql exited $rc: ${stderr_text:-$resp}) -- refusing to proceed (fail-closed); nothing was read"
  fi
  # Mirrors _query_ready_count's own has("errors") guard below: a
  # schema-conforming response can carry BOTH a usable `remaining` value AND
  # a top-level `errors` key (a partial-success response at HTTP 200, issue
  # #5841's exact shape). A budget check that trusted `remaining` anyway
  # could let a partially-failed rateLimit read report a healthy-looking
  # number and wave the real read through. sibling priority_backfill.py has
  # this same gap today; fixed here regardless, per this script's own header
  # argument (DISTINGUISHING "COUNTED 0" FROM "COULD NOT COUNT") that a
  # partial response is never trustworthy -- that argument applies equally
  # to both reads this script makes, not just one of them.
  local has_errors
  has_errors="$(printf '%s' "$resp" | "$JQ_BIN" -r 'has("errors")' 2>/dev/null)"
  if [ "$has_errors" != "false" ]; then
    _die_budget "GraphQL rate-limit budget response carries an 'errors' key (or failed to parse) -- refusing to trust it (fail-closed); nothing was read: $resp"
  fi
  remaining="$(printf '%s' "$resp" | "$JQ_BIN" -r '.data.rateLimit.remaining // empty' 2>/dev/null)"
  case "$remaining" in
    ''|*[!0-9]*)
      _die_budget "could not parse the GraphQL rate-limit budget response -- refusing to proceed (fail-closed); nothing was read: $resp"
      ;;
  esac
  if [ "$remaining" -lt "$min_budget" ]; then
    _die_budget "GraphQL budget too low: remaining=$remaining < --min-budget=$min_budget -- refusing to proceed; nothing was read. This budget is shared across every session on this machine."
  fi
}

_check_budget "$MIN_BUDGET"

# --------------------------------------------------------------------------
# The count itself — ONE server-side-filtered, limit-capped read. See the
# GRAPHQL BUDGET header section for why capping --limit at (threshold + 1)
# is sufficient to answer "is the count below threshold?" without ever
# needing the board's exact size once it's >= threshold.
# --------------------------------------------------------------------------

_query_ready_count() {
  local owner="$1" project="$2" status="$3" repo="$4" threshold="$5"
  local fetch_limit=$((threshold + 1))
  # A threshold of 0 would ask for --limit 1 here, which is fine: --limit 1
  # is enough to distinguish "0 items" (empty response) from "1 or more"
  # (one row), which is exactly what "is count below 0" needs (always false,
  # but the read must still succeed to prove that honestly rather than
  # assume it).

  local query="status:\"$status\" is:open"
  if [ -n "$repo" ]; then
    query="$query repo:\"$repo\""
  fi

  # DISCONFIRMABILITY (added after a live incident, 2026-09-21): a coordinator
  # session mis-read this script's sibling (priority_backfill.py) -- saw a
  # count collapse to 0, assumed a `gh` field had vanished, and spent an hour
  # chasing it before finding the read was fine and their OWN downstream key
  # lookup was wrong. The fix for THIS script is to never make that hour
  # necessary: the exact query string sent to `gh project item-list` and the
  # raw returned item count are ALWAYS printed to stderr (never stdout --
  # this function's own stdout carries only its two-token `<n> <capped>`
  # result line, or nothing on failure; the top-level script assembles the
  # single READY_DEPTH=<n> / READY_DEPTH=>=<n> line from it), unconditionally,
  # not just when something looks wrong -- so a reader can tell "queried
  # fine, genuinely empty" from "the query/field was wrong" without reading
  # this script's source, on every single run.
  _err "querying: status=\"$status\" repo=${repo:-<none>} owner=$owner project=$project --query='$query' --limit=$fetch_limit"

  # stdout and stderr are captured SEPARATELY, never merged (2>&1 would let
  # any stderr noise -- a gh warning banner, a deprecation notice -- corrupt
  # the JSON this script is about to jq-parse from stdout; priority_backfill.py's
  # own _run()/_read_or_raise keeps them apart for the identical reason).
  # stderr goes to a per-call temp file so it can still be folded into an
  # error MESSAGE without ever entering the parsed value.
  local raw rc stderr_file stderr_text
  stderr_file="$(mktemp "${TMPDIR:-/tmp}/ready_depth_stderr.XXXXXX")"
  raw="$("$GH_BIN" project item-list "$project" --owner "$owner" --format json \
      --query "$query" --limit "$fetch_limit" 2>"$stderr_file")"
  rc=$?
  stderr_text="$(cat "$stderr_file" 2>/dev/null)"
  rm -f "$stderr_file" 2>/dev/null
  if [ "$rc" -ne 0 ]; then
    _err "gh project item-list failed (exit $rc): ${stderr_text:-$raw}"
    return 1
  fi

  # issue #5841's exact failure shape: a schema-conforming response can
  # carry BOTH a usable `items` array AND a top-level `errors` key (a
  # partial-success response at HTTP 200, even with a zero `gh` exit code
  # above already checked) -- a response carrying `errors` is NEVER
  # trusted for a count, regardless of what `items` looks like. A response
  # that fails to jq-parse AT ALL (has_errors comes back empty, not the
  # literal string "false") is treated identically -- never distinguished
  # from a genuine errors-key response, since both mean "cannot trust this
  # for a count".
  local has_errors
  has_errors="$(printf '%s' "$raw" | "$JQ_BIN" -r 'has("errors")' 2>/dev/null)"
  if [ "$has_errors" != "false" ]; then
    _err "gh project item-list response carries an 'errors' key (or failed to parse) -- refusing to trust it for a count: $raw"
    return 1
  fi

  local items_type
  items_type="$(printf '%s' "$raw" | "$JQ_BIN" -r '.items | type' 2>/dev/null)"
  if [ "$items_type" != "array" ]; then
    _err "gh project item-list response has no 'items' array -- refusing to trust it for a count: $raw"
    return 1
  fi

  local n
  n="$(printf '%s' "$raw" | "$JQ_BIN" -r '.items | length' 2>/dev/null)"
  case "$n" in
    ''|*[!0-9]*)
      _err "could not read a numeric item count from the response: $raw"
      return 1
      ;;
  esac
  _err "raw items returned: $n (of at most $fetch_limit requested)"

  # Prints TWO space-separated tokens on stdout: the raw numeric row count
  # (always a real number -- this is what the caller uses for the exact
  # below-threshold comparison, which stays correct even when capped: `n >=
  # fetch_limit > threshold` always means "not below threshold" regardless
  # of the true total) and a capped flag (1 if `n` hit or exceeded
  # fetch_limit and is therefore a LOWER BOUND rather than an exact count,
  # 0 otherwise). The caller uses the flag only to choose how to FORMAT
  # stdout's human-facing READY_DEPTH line (see WHY STDOUT PRINTS A LOWER
  # BOUND in the header comment) -- it never affects the exit-code decision.
  if [ "$n" -ge "$fetch_limit" ]; then
    printf '%s %s\n' "$n" "1"
    return 0
  fi

  printf '%s %s\n' "$n" "0"
  return 0
}

QUERY_OUT="$(_query_ready_count "$OWNER" "$PROJECT" "$STATUS" "$REPO" "$THRESHOLD")"
QUERY_RC=$?

if [ "$QUERY_RC" -ne 0 ] || [ -z "$QUERY_OUT" ]; then
  # Never print a count here, under any circumstance -- this is the one
  # invariant issue #5841 exists to enforce (see header comment). A failed
  # read is reported via stderr above and this exit code ONLY.
  exit "$EXIT_COUNT_FAILED"
fi

# _query_ready_count's stdout is exactly two space-separated tokens: the raw
# numeric row count, and a 0/1 capped flag (see that function's own comment
# and WHY STDOUT PRINTS A LOWER BOUND in the header). Read them into two
# separate variables rather than treating $QUERY_OUT as one number.
COUNT="${QUERY_OUT%% *}"
CAPPED="${QUERY_OUT#* }"

case "$COUNT" in
  ''|*[!0-9]*)
    _err "internal error: non-numeric count escaped _query_ready_count: '$QUERY_OUT'"
    exit "$EXIT_COUNT_FAILED"
    ;;
esac
case "$CAPPED" in
  0|1) : ;;
  *)
    _err "internal error: non-boolean capped flag escaped _query_ready_count: '$QUERY_OUT'"
    exit "$EXIT_COUNT_FAILED"
    ;;
esac

if [ "$CAPPED" -eq 1 ]; then
  # A capped read: $COUNT is a LOWER BOUND, not the true column depth (see
  # WHY STDOUT PRINTS A LOWER BOUND in the header comment). Mark it as such
  # on stdout so a log/trend reader never mistakes it for an exact count.
  echo "READY_DEPTH=>=$COUNT"
else
  echo "READY_DEPTH=$COUNT"
fi

# The below-threshold decision always uses the exact raw row count, never
# the formatted string above -- a capped count (COUNT == fetch_limit ==
# threshold + 1) is always > threshold, so this comparison is correct in
# both the capped and uncapped case without any special-casing.
if [ "$COUNT" -lt "$THRESHOLD" ]; then
  exit "$EXIT_BELOW_THRESHOLD"
else
  exit "$EXIT_NOT_BELOW_THRESHOLD"
fi
