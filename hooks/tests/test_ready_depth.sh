#!/usr/bin/env bash
# Falsifiable tests for scripts/ready_depth.sh (Lane Control master plan,
# WS1 Phase E — "Event-driven Ready refill").
#
# WHY THIS EXISTS: ready_depth.sh is a SENSOR the daily oversight job trusts
# unattended to decide whether to dispatch a board refill. Every test here
# asserts INTENDED behavior from the module's own header contract (see that
# file's EXIT CODES / GRAPHQL BUDGET / issue #5841 / issue #5839 sections),
# never a snapshot of what the code happens to do. Each one was confirmed to
# FAIL against the pre-fix/stub source before landing (see the accompanying
# session report's falsification log) — this file exists specifically
# because a spurious "Ready #1 is empty" reading (the #5841 failure shape)
# would trigger an unwanted refill of ~30 items, and a hung trailing-flag
# parse (the #5839 failure shape) would eat a whole unattended job's wall
# clock and file nothing.
#
# Every gh call is FAKED — this suite never touches the live board or the
# shared GraphQL budget, per the standing rule (and this task's explicit
# instruction) never to run this against the real board while other
# sessions share the same budget.
#
# Run: bash ~/.claude/hooks/tests/test_ready_depth.sh
set -u

SRC="${READY_DEPTH_SRC:-$HOME/.claude/scripts/ready_depth.sh}"
[ -f "$SRC" ] || { echo "FATAL: $SRC not found"; exit 1; }

PASS=0; FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

WORK="$(mktemp -d)"
FAKEBIN="$WORK/fakebin"
mkdir -p "$FAKEBIN"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# A timeout wrapper that works on this machine: `timeout`/`gtimeout` do not
# exist here (see CLAUDE.md's own note on this) -- use perl's alarm, the
# repo's documented idiom (`run_oversight_job.sh`'s own quota pre-flight).
_with_timeout() {
  local secs="$1"; shift
  perl -e 'alarm shift; exec @ARGV' "$secs" "$@"
}

# --------------------------------------------------------------------------
# Fake `gh` fixtures. Each writer produces a self-contained fake `gh` script
# on $FAKEBIN/gh; tests select PATH="$FAKEBIN:$PATH" before invoking the
# real ready_depth.sh so the SUT is exercised end to end, never reimplemented.
# --------------------------------------------------------------------------

# _fake_gh_healthy <item_count> [budget_remaining] — a well-behaved gh: the
# rateLimit query reports a healthy budget, and `project item-list` returns
# exactly <item_count> synthetic items with no errors key. This is the
# baseline POSITIVE CONTROL fixture -- if a test using this can't get a
# clean success, nothing else in the suite is trustworthy either.
_fake_gh_healthy() {
  local count="$1" budget="${2:-3000}"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":$budget,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS}"
  exit 0
fi
echo "unhandled fake gh invocation: \$*" >&2
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_healthy_argv_logging <item_count> <argv_log_path> — Opus review's
# prescribed fix for the c/d/e/f/g/h/i cluster (dropping is:open, dropping
# --query entirely, weakening --limit, inflating fetch_limit, etc.): a
# well-behaved gh that ALSO appends its full argv (one arg per line, a
# blank-line record separator between invocations) to <argv_log_path> before
# answering, for both the rateLimit call and the item-list call. This is
# what lets a test assert the ACTUAL --query string and --limit value the
# script sent, rather than only the correctness of the printed count --
# every one of these mutations (drop is:open, drop --query, hardcode
# --limit 30, inflate fetch_limit to threshold+100) leaves the COUNT
# assertions green (the fake still answers with exactly <item_count> items
# regardless of what it was asked for) and is invisible without this.
_fake_gh_healthy_argv_logging() {
  local count="$1" argv_log="$2"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
{
  for a in "\$@"; do printf '%s\n' "\$a"; done
  printf '\n'
} >> "$argv_log"
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS}"
  exit 0
fi
echo "unhandled fake gh invocation: \$*" >&2
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_healthy_noisy_stderr <item_count> — identical to the above but
# the item-list call ALSO writes unrelated text to stderr (a deprecation
# banner, a warning) on the way to a valid, well-formed stdout JSON payload.
# This is the regression fixture for the stdout/stderr-conflation bug found
# and fixed while building this script: a naive `2>&1` capture would corrupt
# the JSON this fixture's stdout carries and wrongly report a read failure.
_fake_gh_healthy_noisy_stderr() {
  local count="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  echo "warning: some unrelated gh deprecation notice" >&2
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS}"
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_item_list_process_failure — `gh project item-list` exits non-zero
# with a plain error on stderr (a genuine transport/auth failure), while
# api graphql (the budget check, which runs first) is healthy.
_fake_gh_item_list_process_failure() {
  cat > "$FAKEBIN/gh" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "api" ] && [ "$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "item-list" ]; then
  echo "gh: transient network failure" >&2
  exit 1
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_item_list_rc_nonzero_with_valid_json — Opus review BLOCKER 1's
# exact reproduction: `gh project item-list` writes a SCHEMA-VALID JSON
# response (a real, parseable `items` array) to stdout AND an error line to
# stderr, but exits 1. This is a real shape `gh` can produce -- a partial
# response already flushed to stdout before a later pagination page fails.
# Without the `if [ "$rc" -ne 0 ]` guard at _query_ready_count's `gh`
# invocation, this fixture's valid stdout sails straight through the
# `has("errors")` and `.items | length` checks below it (there is no
# `errors` key and `items` really is an array) and reports a false count --
# exactly the #5841 failure shape the guard exists to prevent, just reached
# via the exit code rather than the response body. The pre-existing
# `_fake_gh_item_list_process_failure` fixture above does NOT exercise this
# guard: it writes nothing to stdout, so an empty string fails the jq parse
# and a DIFFERENT, later check catches it -- masking this guard as tested
# when it was not (confirmed by removing the guard: the suite stayed fully
# green until this fixture/test pair were added).
# _fake_gh_items_non_array — the ERRORS-FREE non-array shape. `gh` exits 0
# and returns a well-formed document whose `items` is NOT an array: null,
# an object, a number, a string. This is the #5841 family reached by a
# THIRD route, and only the `items_type != "array"` guard catches it:
#   - `has("errors")` never fires   -- there IS no errors key
#   - the numeric-`n` check never fires -- `length` always yields a number
# because `jq`'s `length` on a non-array is not an error (verified
# directly: null->0, {"a":1}->1, 5->5, "abcdefg"->7). So `{"items":null}`
# silently becomes a confident ZERO, which is the single worst output this
# sensor can produce: a spurious refill of ~30 items on a column whose
# depth was never actually read. Removing the guard left the suite fully
# green until this fixture and its tests were added.
_fake_gh_items_non_array() {
  local payload="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  echo '{"items": $payload}'
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

_fake_gh_item_list_rc_nonzero_with_valid_json() {
  local count="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS}"
  echo "gh: pagination failed partway through" >&2
  exit 1
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_partial_errors — the EXACT issue #5841 shape: a schema-conforming
# response with `gh` exiting 0, a real (non-null) `items` array present, AND
# a top-level `errors` key alongside it (a partial-success GraphQL response
# at HTTP 200). This must NEVER be read as "count = <items length>".
_fake_gh_partial_errors() {
  local count="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":3000,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS, \\"errors\\": [{\\"message\\": \\"some field errored\\"}]}"
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_low_budget — the rateLimit query reports a real but low
# remaining budget; item-list ITSELF would succeed if reached, but must
# never be called once the budget gate refuses.
_fake_gh_low_budget() {
  local remaining="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":$remaining,"resetAt":"2099-01-01T00:00:00Z"}}}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  echo "MARKER: item-list was called despite low budget" > "$WORK/item_list_called"
  echo '{"items": []}'
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_budget_partial_errors — the issue #5841 shape applied to the
# BUDGET query specifically: `gh api graphql` for rateLimit exits 0 with a
# real, usable `remaining` value AND a top-level `errors` key alongside it.
# item-list would succeed if reached (marks a file so a test can prove it
# was never called), but the budget response must never be trusted for a
# go/no-go decision once it carries an errors key, regardless of how
# healthy `remaining` looks.
_fake_gh_budget_partial_errors() {
  local remaining="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo '{"data":{"rateLimit":{"remaining":$remaining,"resetAt":"2099-01-01T00:00:00Z"}},"errors":[{"message":"some field errored"}]}'
  exit 0
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  echo "MARKER: item-list was called despite a partial-errors budget response" > "$WORK/item_list_called_after_budget_errors"
  echo '{"items": []}'
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

# _fake_gh_budget_query_should_not_be_called — proves the BUDGET query
# specifically (`gh api graphql` for rateLimit) is never invoked, while
# still answering `project item-list` normally -- --min-budget 0 waives
# only the budget CHECK, not the actual count read, so a fixture that
# failed on EVERY gh call (including item-list) would make a correct
# waiver indistinguishable from a broken one that also skips the real
# work. If `api graphql` is ever called despite the waiver, it writes a
# marker file and fails loudly; `project item-list` always succeeds.
_fake_gh_budget_query_should_not_be_called() {
  local count="$1"
  cat > "$FAKEBIN/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "api" ] && [ "\$2" = "graphql" ]; then
  echo "MARKER: budget query was called despite --min-budget 0: \$*" > "$WORK/budget_query_called_unexpectedly"
  exit 1
fi
if [ "\$1" = "project" ] && [ "\$2" = "item-list" ]; then
  ITEMS="\$(python3 -c "import json; print(json.dumps([{'id': i} for i in range($count)]))")"
  echo "{\\"items\\": \$ITEMS}"
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/gh"
}

_run_sut() {
  PATH="$FAKEBIN:$PATH" READY_DEPTH_GH_BIN=gh _with_timeout 10 bash "$SRC" "$@"
}

# ==========================================================================
# 1. A successful count, including a correct count of 0 (positive control)
# ==========================================================================
echo "1. successful counts"

_fake_gh_healthy 3
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=3" ]; then
  ok "count=3, threshold=10 -> exit 0, prints READY_DEPTH=3"
else
  bad "count=3, threshold=10 -> exit 0, prints READY_DEPTH=3 (got rc=$rc out='$out')"
fi

# The "correct count of 0" case is its own required assertion (task spec):
# a genuinely empty column must print READY_DEPTH=0 and exit 0 (below
# threshold), NOT be conflated with any failure path.
_fake_gh_healthy 0
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=0" ]; then
  ok "genuine count=0 -> exit 0 (below threshold), prints READY_DEPTH=0"
else
  bad "genuine count=0 -> exit 0, prints READY_DEPTH=0 (got rc=$rc out='$out')"
fi

# ==========================================================================
# 1b. The ACTUAL argv sent to `gh project item-list` is asserted, not just
#     the printed count (Opus review's untested-guard cluster c/e/f/g: a
#     correct count from a well-behaved fake proves nothing about whether
#     is:open was dropped, --query was dropped entirely, --limit was
#     weakened to a fixed 30, or fetch_limit was inflated -- the fake
#     answers with the same <count> regardless of what argv it received,
#     so only inspecting the LOGGED argv can catch any of these).
# ==========================================================================
echo "1b. the exact --query / --limit / --owner argv sent to gh is correct"

ARGV_LOG="$WORK/argv.log"

# (c)/(e): --query must be PRESENT and must include is:open -- dropping
# is:open counts closed items too (inflates depth, suppresses a needed
# refill); dropping --query entirely returns the whole unfiltered board.
rm -f "$ARGV_LOG"
_fake_gh_healthy_argv_logging 3 "$ARGV_LOG"
_run_sut --owner O --project 1 --status "Ready #1" --threshold 10 >/dev/null 2>&1
item_list_call="$(awk '/^item-list$/{found=1} found{print} /^$/{if(found)exit}' "$ARGV_LOG")"
if printf '%s' "$item_list_call" | grep -qx -- '--query' && \
   printf '%s' "$item_list_call" | grep -q 'is:open' && \
   printf '%s' "$item_list_call" | grep -q 'status:"Ready #1"'; then
  ok "(c)/(e): gh project item-list is called with --query containing status:\"Ready #1\" AND is:open"
else
  bad "(c)/(e): --query with status + is:open not found in logged argv: $(printf '%s' "$item_list_call" | tr '\n' '|')"
fi

# (f): --limit must carry the SCRIPT-COMPUTED fetch_limit (threshold+1),
# never a hardcoded constant -- this is the entire cost-avoidance mechanism
# the header claims exists; a hardcoded --limit 30 would silently defeat it
# while every count-based test still passes.
rm -f "$ARGV_LOG"
_fake_gh_healthy_argv_logging 3 "$ARGV_LOG"
_run_sut --owner O --project 1 --threshold 7 >/dev/null 2>&1
item_list_call="$(awk '/^item-list$/{found=1} found{print} /^$/{if(found)exit}' "$ARGV_LOG")"
limit_value="$(printf '%s\n' "$item_list_call" | awk '/^--limit$/{getline; print; exit}')"
if [ "$limit_value" = "8" ]; then
  ok "(f)/(g): --threshold 7 sends --limit 8 (fetch_limit = threshold + 1, not a hardcoded constant)"
else
  bad "(f)/(g): --threshold 7 should send --limit 8, got --limit '$limit_value' (argv: $(printf '%s' "$item_list_call" | tr '\n' '|'))"
fi

# Recovery/positive-control pairing for (f)/(g): a DIFFERENT threshold sends
# a DIFFERENT --limit, proving the value tracks the flag rather than being
# coincidentally correct for one input.
rm -f "$ARGV_LOG"
_fake_gh_healthy_argv_logging 3 "$ARGV_LOG"
_run_sut --owner O --project 1 --threshold 2 >/dev/null 2>&1
item_list_call="$(awk '/^item-list$/{found=1} found{print} /^$/{if(found)exit}' "$ARGV_LOG")"
limit_value="$(printf '%s\n' "$item_list_call" | awk '/^--limit$/{getline; print; exit}')"
if [ "$limit_value" = "3" ]; then
  ok "(f)/(g) recovery: --threshold 2 sends --limit 3 (a different threshold -> a different, correct limit)"
else
  bad "(f)/(g) recovery: --threshold 2 should send --limit 3, got --limit '$limit_value'"
fi

# --owner and the project positional are also asserted end to end, since
# nothing above checks them directly.
rm -f "$ARGV_LOG"
_fake_gh_healthy_argv_logging 3 "$ARGV_LOG"
_run_sut --owner someorg --project 42 --threshold 10 >/dev/null 2>&1
item_list_call="$(awk '/^item-list$/{found=1} found{print} /^$/{if(found)exit}' "$ARGV_LOG")"
if printf '%s' "$item_list_call" | grep -qx '42' && \
   printf '%s' "$item_list_call" | grep -qx -- '--owner' && \
   printf '%s' "$item_list_call" | grep -qx 'someorg'; then
  ok "gh project item-list is called with the caller's --owner and project number"
else
  bad "gh project item-list argv missing owner/project: $(printf '%s' "$item_list_call" | tr '\n' '|')"
fi

# ==========================================================================
# 1c. Argument-validation errors are reported as ARGUMENT errors, never
#     misrepresented as a count failure that happens to share an exit code.
# ==========================================================================
echo "1c. argument validation"

# (k): a non-numeric --threshold must be a CLEAN argument error, not an
# `unbound variable` crash. Before the fix, `--threshold abc` reached
# `[ "$n" -lt "$THRESHOLD" ]` (or similar unset arithmetic) and bash's `set
# -u` killed the script with "abc: unbound variable" -- same exit code (2)
# as every other argument error, but for the WRONG reason, and any stderr
# message a caller might log would be misleading about what happened.
_fake_gh_healthy 3
out="$(_run_sut --owner O --project 1 --threshold abc 2>"$WORK/stderr_k")"
rc=$?
stderr_k="$(cat "$WORK/stderr_k" 2>/dev/null)"
if [ "$rc" -eq 2 ] && [ -z "$out" ] && ! printf '%s' "$stderr_k" | grep -qi 'unbound variable'; then
  ok "(k): --threshold abc -> clean exit 2 argument error, not an unbound-variable crash"
else
  bad "(k): --threshold abc -> clean exit 2, no unbound-variable text (got rc=$rc out='$out' stderr='$stderr_k')"
fi

# `--project is required` is KEPT rather than deleted as redundant: an
# empty $PROJECT would also be caught by the integer check below it, so
# behavior is identical either way, but the dedicated message names the
# actual problem ("required") instead of "must be a positive integer
# (got '')". This test pins the MESSAGE, which is the only thing the
# check contributes -- without it the check reads as live code that
# nothing depends on.
out="$(_run_sut --owner O --threshold 10 2>"$WORK/stderr_p")"
rc=$?
stderr_p="$(cat "$WORK/stderr_p" 2>/dev/null)"
if [ "$rc" -eq 2 ] && printf '%s' "$stderr_p" | grep -q 'project is required'; then
  ok "--project omitted -> exit 2 naming it as REQUIRED, not as a bad integer"
else
  bad "--project omitted -> expected exit 2 and 'project is required' (got rc=$rc stderr='$stderr_p')"
fi

# --min-budget validation. This is the one argument guard whose failure
# mode SILENTLY DISABLES A SAFETY GATE rather than producing a wrong
# number: without the check, `--min-budget abc` skips the budget gate
# entirely and the run proceeds (measured: rc=0, READY_DEPTH=3). The
# header also claims a negative value is rejected at parse time -- true
# (the *[!0-9]* pattern catches the '-'), but it was unpinned until now.
for _bad in abc -5; do
  out="$(_run_sut --owner O --project 1 --min-budget "$_bad" 2>/dev/null)"
  rc=$?
  if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
    ok "--min-budget $_bad -> exit 2 argument error, budget gate never skipped"
  else
    bad "--min-budget $_bad -> expected exit 2 and no count (got rc=$rc out='$out')"
  fi
done

# PAIRED RECOVERY: a VALID --min-budget must still be honoured, so the
# validation cannot decay into "reject everything".
_fake_gh_healthy 3
out="$(_run_sut --owner O --project 1 --threshold 10 --min-budget 100 2>/dev/null)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=3" ]; then
  ok "--min-budget 100 (valid, met) -> the read proceeds normally"
else
  bad "--min-budget 100 -> expected exit 0 and READY_DEPTH=3 (got rc=$rc out='$out')"
fi

# (j): --project must be validated as an integer (mirrors the existing
# --threshold/--min-budget integer checks) -- a non-numeric project number
# must fail as an argument error before any gh call is made.
out="$(_run_sut --owner O --project abc --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "(j): --project abc -> exit 2 argument error (non-integer project number rejected)"
else
  bad "(j): --project abc -> exit 2 argument error (got rc=$rc out='$out')"
fi

# (l): an unknown flag must be rejected, never silently ignored -- a typo'd
# flag silently doing nothing is indistinguishable from a successful run
# using defaults, which is dangerous for an unattended caller.
out="$(_run_sut --owner O --project 1 --threshold 10 --bogus-flag 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ]; then
  ok "(l): an unknown flag (--bogus-flag) is rejected, not silently ignored"
else
  bad "(l): an unknown flag should be rejected with exit 2 (got rc=$rc)"
fi

# (m): a stray positional argument must be rejected, never silently ignored
# (this script takes flags only -- see its own --help text).
out="$(_run_sut --owner O --project 1 --threshold 10 stray_positional 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ]; then
  ok "(m): a stray positional argument is rejected, not silently ignored"
else
  bad "(m): a stray positional argument should be rejected with exit 2 (got rc=$rc)"
fi

# (n): --owner is required -- omitting it must fail with a clear argument
# error before any gh call, never proceed with an empty owner.
out="$(_run_sut --project 1 --threshold 10 2>"$WORK/stderr_n")"
rc=$?
stderr_n="$(cat "$WORK/stderr_n" 2>/dev/null)"
if [ "$rc" -eq 2 ] && printf '%s' "$stderr_n" | grep -qi 'owner.*required'; then
  ok "(n): omitting --owner -> exit 2 with an '--owner is required' message"
else
  bad "(n): omitting --owner -> exit 2, '--owner is required' message (got rc=$rc stderr='$stderr_n')"
fi

# Recovery partner for the whole 1c block: a fully valid, complete argv
# (mirrors every flag exercised above) still succeeds normally.
_fake_gh_healthy 4
out="$(_run_sut --owner O --project 1 --status "Ready #1" --threshold 10 --min-budget 50)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=4" ]; then
  ok "recovery: a fully valid argv (every flag from section 1c) still succeeds normally"
else
  bad "recovery: a fully valid argv should succeed (got rc=$rc out='$out')"
fi

# ==========================================================================
# 2. A FAILED query exits non-zero and DISTINCTLY, and NEVER prints 0 as if
#    it were a count (issue #5841's exact failure class).
# ==========================================================================
echo "2. failed queries never manufacture a count (issue #5841)"

_fake_gh_item_list_process_failure
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "gh process failure -> exit 2 (EXIT_COUNT_FAILED), stdout carries no READY_DEPTH line"
else
  bad "gh process failure -> exit 2, no stdout count (got rc=$rc out='$out')"
fi
if printf '%s' "$out" | grep -q 'READY_DEPTH=0'; then
  bad "gh process failure must never print READY_DEPTH=0"
else
  ok "gh process failure never prints READY_DEPTH=0"
fi

# Opus review BLOCKER 1: `gh` exits non-zero (rc=1) but ALREADY wrote a
# schema-valid, non-empty `items` array to stdout before failing (a real
# partial-pagination-failure shape). Must still refuse -- the rc check must
# fire BEFORE the has("errors")/items-array/length checks ever look at that
# stdout, regardless of how well-formed it is. count=5 chosen so a bug that
# reports the count anyway is visibly wrong (READY_DEPTH=5), not
# coincidentally masked by a count of 0.
_fake_gh_item_list_rc_nonzero_with_valid_json 5
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "gh exits nonzero despite valid stdout JSON -> exit 2, never trusts the partial stdout"
else
  bad "gh exits nonzero despite valid stdout JSON -> exit 2, no printed count (got rc=$rc out='$out')"
fi

# ERRORS-FREE non-array `items` -- the guard `items_type != "array"` is the
# ONLY thing standing between these and a confident wrong count. null is
# the dangerous one (length -> 0 -> READY_DEPTH=0 -> spurious refill); 5 is
# included so a regression is visibly wrong rather than coincidentally
# looking like an empty column.
for _payload in 'null' '{"a":1}' '5' '"abcdefg"'; do
  _fake_gh_items_non_array "$_payload"
  out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
  rc=$?
  if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
    ok "items=$_payload (no errors key) -> exit 2, never a count"
  else
    bad "items=$_payload (no errors key) -> expected exit 2 and no count (got rc=$rc out='$out')"
  fi
done

# PAIRED RECOVERY: a genuine empty ARRAY is a real, trustworthy zero and
# must still be reported. The guard must reject non-arrays, not all zeros.
_fake_gh_items_non_array '[]'
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=0" ]; then
  ok "items=[] -> a REAL zero is still reported (exit 0, READY_DEPTH=0)"
else
  bad "items=[] -> expected exit 0 and READY_DEPTH=0 (got rc=$rc out='$out')"
fi

# The exact #5841 shape: items present AND errors present. Must refuse, not
# report items|length as the count.
_fake_gh_partial_errors 0
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "partial data+errors response (items=0) -> exit 2, no printed count"
else
  bad "partial data+errors response (items=0) -> exit 2, no printed count (got rc=$rc out='$out')"
fi

_fake_gh_partial_errors 5
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "partial data+errors response (items=5) -> exit 2, never reports 5 as the count"
else
  bad "partial data+errors response (items=5) -> exit 2 (got rc=$rc out='$out')"
fi

# Distinctness, fixed as a REAL assertion (was tautological before this fix
# -- it reused $rc from the assertion immediately above, which had already
# asserted rc==2, so "$rc != 0/1/3" was true by construction and could never
# fail regardless of what the script actually does). Four INDEPENDENT SUT
# runs, one per exit-code meaning, each producing its own fresh variable;
# the four codes are then compared pairwise so a real collision (e.g. a
# future change that made the budget-refusal path exit 2 instead of 3)
# would actually be caught.
_fake_gh_healthy 3
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
rc_below=$?
_fake_gh_healthy 99
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
rc_not_below=$?
_fake_gh_item_list_process_failure
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
rc_count_failed=$?
_fake_gh_low_budget 1
_run_sut --owner O --project 1 --min-budget 50 >/dev/null 2>&1
rc_budget_refused=$?
if [ "$rc_below" -eq 0 ] && [ "$rc_not_below" -eq 1 ] && \
   [ "$rc_count_failed" -eq 2 ] && [ "$rc_budget_refused" -eq 3 ] && \
   [ "$rc_below" != "$rc_not_below" ] && [ "$rc_below" != "$rc_count_failed" ] && \
   [ "$rc_below" != "$rc_budget_refused" ] && [ "$rc_not_below" != "$rc_count_failed" ] && \
   [ "$rc_not_below" != "$rc_budget_refused" ] && [ "$rc_count_failed" != "$rc_budget_refused" ]; then
  ok "all four exit codes (0/1/2/3), from four independent runs, are pairwise distinct"
else
  bad "exit codes are not all pairwise distinct (below=$rc_below not_below=$rc_not_below count_failed=$rc_count_failed budget_refused=$rc_budget_refused)"
fi

# Regression fixture: noisy stderr on an otherwise-successful call must
# never be misread as a failure (the stdout/stderr-conflation bug found and
# fixed while building this script).
_fake_gh_healthy_noisy_stderr 4
out="$(_run_sut --owner O --project 1 --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=4" ]; then
  ok "stderr noise alongside valid stdout JSON does not corrupt the count"
else
  bad "stderr noise alongside valid stdout JSON does not corrupt the count (got rc=$rc out='$out')"
fi

# ==========================================================================
# 3. Threshold comparison at the boundary: 9, 10, 11 (threshold=10)
# ==========================================================================
echo "3. threshold boundary (threshold=10)"

_fake_gh_healthy 9
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=9" ]; then
  ok "count=9 < threshold=10 -> exit 0 (below), READY_DEPTH=9"
else
  bad "count=9 < threshold=10 -> exit 0 (got rc=$rc out='$out')"
fi

_fake_gh_healthy 10
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=10" ]; then
  ok "count=10 == threshold=10 -> exit 1 (NOT below), READY_DEPTH=10"
else
  bad "count=10 == threshold=10 -> exit 1 (got rc=$rc out='$out')"
fi

# count=11 == fetch_limit (threshold=10 -> fetch_limit=threshold+1=11): this
# is the CAPPED case, not an exact count -- see section 3b below for why
# stdout must read READY_DEPTH=>=11, not READY_DEPTH=11.
_fake_gh_healthy 11
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=>=11" ]; then
  ok "count=11 == fetch_limit -> exit 1 (NOT below), READY_DEPTH=>=11 (capped, not exact)"
else
  bad "count=11 == fetch_limit -> exit 1, READY_DEPTH=>=11 (got rc=$rc out='$out')"
fi

# ==========================================================================
# 3b. Capped-read marker (Opus review B2): count == fetch_limit is a LOWER
#     BOUND and must print distinctly (READY_DEPTH=>=<n>) from count <
#     fetch_limit, which is an EXACT count (READY_DEPTH=<n>). Before this
#     fix both branches of the capping `if` printed byte-identically --
#     collapsing the whole `if [ "$n" -ge "$fetch_limit" ]` block into one
#     unconditional `printf '%s\n' "$n"; return 0` left the suite fully
#     green (falsified below), the exact defect the review reported.
# ==========================================================================
echo "3b. capped-read marker distinguishes count==fetch_limit from count<fetch_limit"

# threshold=0 -> fetch_limit=1. count=0 is the exact, uncapped case (0 < 1).
_fake_gh_healthy 0
out="$(_run_sut --owner O --project 1 --threshold 0)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=0" ]; then
  ok "threshold=0, count=0 < fetch_limit=1 -> exact READY_DEPTH=0 (not capped)"
else
  bad "threshold=0, count=0 < fetch_limit=1 -> exact READY_DEPTH=0 (got rc=$rc out='$out')"
fi

# threshold=0 -> fetch_limit=1. count=1 == fetch_limit=1: capped.
_fake_gh_healthy 1
out="$(_run_sut --owner O --project 1 --threshold 0)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=>=1" ]; then
  ok "threshold=0, count=1 == fetch_limit=1 -> capped READY_DEPTH=>=1"
else
  bad "threshold=0, count=1 == fetch_limit=1 -> capped READY_DEPTH=>=1 (got rc=$rc out='$out')"
fi

# threshold=5 -> fetch_limit=6. count=5 is exact (5 < 6, one below the cap),
# but 5 is NOT below threshold=5 (5 < 5 is false), so exit is 1 -- this case
# exists to prove capped-vs-exact formatting is independent of the
# below-threshold exit-code decision (a different axis entirely).
_fake_gh_healthy 5
out="$(_run_sut --owner O --project 1 --threshold 5)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=5" ]; then
  ok "threshold=5, count=5 < fetch_limit=6 -> exact READY_DEPTH=5, exit 1 (not below threshold)"
else
  bad "threshold=5, count=5 < fetch_limit=6 -> exact READY_DEPTH=5, exit 1 (got rc=$rc out='$out')"
fi

# threshold=5 -> fetch_limit=6. count=6 == fetch_limit: capped, and the
# exit code must still be correct (not below threshold) even though the
# printed number is a lower bound, not an exact count.
_fake_gh_healthy 6
out="$(_run_sut --owner O --project 1 --threshold 5)"
rc=$?
if [ "$rc" -eq 1 ] && [ "$out" = "READY_DEPTH=>=6" ]; then
  ok "threshold=5, count=6 == fetch_limit=6 -> capped READY_DEPTH=>=6, exit 1 still correct"
else
  bad "threshold=5, count=6 == fetch_limit=6 -> capped READY_DEPTH=>=6, exit 1 (got rc=$rc out='$out')"
fi

# ==========================================================================
# 4. A trailing value-taking flag exits cleanly rather than hanging
#    (issue #5839's exact failure class). Every value-taking flag is
#    checked, each with a real wall-clock timeout so a regression to the
#    bare-`shift 2` bug actually FAILS this test rather than hanging it.
# ==========================================================================
echo "4. trailing value-taking flags never hang (issue #5839)"

_fake_gh_healthy 1
for flag in --owner --project --status --repo --threshold --min-budget; do
  start_ts=$(date +%s)
  out="$(PATH="$FAKEBIN:$PATH" READY_DEPTH_GH_BIN=gh _with_timeout 5 bash "$SRC" --owner O --project 1 "$flag" 2>/dev/null)"
  rc=$?
  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  # perl's alarm sends SIGALRM, which without a handler kills the child with
  # exit 142 (128+14) or similar signal-shaped exit -- a hang reaches this,
  # our guard should never let it. Assert BOTH the non-hang exit code AND a
  # tight elapsed-time bound, so a slow-but-technically-bounded failure
  # can't quietly pass either.
  if [ "$rc" -eq 2 ] && [ "$elapsed" -lt 5 ]; then
    ok "trailing $flag with no value -> exit 2 within ${elapsed}s (no hang)"
  else
    bad "trailing $flag with no value -> exit 2 within <5s (got rc=$rc elapsed=${elapsed}s)"
  fi
done

# ==========================================================================
# 5. Recovery partners — every refusal above gets a paired success path.
# ==========================================================================
echo "5. recovery partners for every refusal tested above"

# Recovery for: trailing value-taking flag refusal -> the SAME flag WITH a
# value parses and succeeds normally.
_fake_gh_healthy 2
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=2" ]; then
  ok "recovery: --threshold WITH a value parses and succeeds (paired with the trailing-flag refusal above)"
else
  bad "recovery: --threshold WITH a value should succeed (got rc=$rc out='$out')"
fi

out="$(_run_sut --owner O --project 1 --status "Ready #1" --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=2" ]; then
  ok "recovery: --status WITH a value parses and succeeds"
else
  bad "recovery: --status WITH a value should succeed (got rc=$rc out='$out')"
fi

# Recovery for: gh process failure -> a subsequent healthy call succeeds
# (proves the failure path doesn't leave any process-global state broken).
_fake_gh_item_list_process_failure
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
_fake_gh_healthy 6
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=6" ]; then
  ok "recovery: a healthy call after a prior failed call succeeds cleanly"
else
  bad "recovery: a healthy call after a prior failure should succeed (got rc=$rc out='$out')"
fi

# Recovery for: gh nonzero-rc-with-valid-JSON (Opus review BLOCKER 1) -> a
# subsequent genuinely healthy call succeeds (proves the rc check doesn't
# leave any process-global state broken, mirroring the process-failure
# recovery pair above).
_fake_gh_item_list_rc_nonzero_with_valid_json 5
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
_fake_gh_healthy 8
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=8" ]; then
  ok "recovery: a healthy call after a prior nonzero-rc-with-valid-JSON call succeeds cleanly"
else
  bad "recovery: a healthy call after a prior nonzero-rc-with-valid-JSON call should succeed (got rc=$rc out='$out')"
fi

# Recovery for: partial errors response -> a subsequent clean response
# succeeds (proves the errors-key check doesn't wrongly latch/cache).
# count=5 < threshold=10, so the correct recovery outcome is exit 0 (below
# threshold) -- an EARLIER version of this assertion wrongly expected exit
# 1 here, which is itself exactly the kind of un-falsified assertion this
# suite exists to avoid; caught by actually running it (see falsification
# log in the accompanying session report).
_fake_gh_partial_errors 5
_run_sut --owner O --project 1 --threshold 10 >/dev/null 2>&1
_fake_gh_healthy 5
out="$(_run_sut --owner O --project 1 --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=5" ]; then
  ok "recovery: a clean response after a prior partial-errors response succeeds"
else
  bad "recovery: a clean response after a prior partial-errors response should succeed (got rc=$rc out='$out')"
fi

# ==========================================================================
# 6. Budget refusal (exit 3) is DISTINCT from a count failure (exit 2), and
#    it refuses BEFORE ever calling item-list -- paired with the waiver
#    recovery path (--min-budget 0).
# ==========================================================================
echo "6. budget gate: refusal, distinctness, and the waiver recovery path"

rm -f "$WORK/item_list_called"
_fake_gh_low_budget 5
out="$(_run_sut --owner O --project 1 --min-budget 50 2>/dev/null)"
rc=$?
if [ "$rc" -eq 3 ] && [ -z "$out" ]; then
  ok "remaining=5 < --min-budget=50 -> exit 3, no printed count"
else
  bad "remaining=5 < --min-budget=50 -> exit 3, no printed count (got rc=$rc out='$out')"
fi
if [ -f "$WORK/item_list_called" ]; then
  bad "item-list must NEVER be called once the budget gate refuses"
else
  ok "item-list is never called once the budget gate refuses"
fi
# (The old "budget-refusal exit code (3) is distinct from count-failure
# exit code (2)" assertion that lived here was TAUTOLOGICAL -- it reused
# $rc from the assertion immediately above, which had already asserted
# rc==3, so "$rc != 2" was true by construction. Replaced by section 2's
# consolidated four-independent-runs pairwise-distinctness assertion,
# which actually exercises all four codes fresh and can fail.)

# Recovery: --min-budget 0 deliberately waives the BUDGET CHECK specifically
# (`gh api graphql` for rateLimit is never invoked) while the real count
# read (`gh project item-list`) still proceeds normally -- these are two
# different gh subcommands, so "gh is never called at all" would be the
# WRONG assertion (item-list legitimately runs); the fixture below answers
# item-list normally and only marks/fails on the budget query specifically.
rm -f "$WORK/budget_query_called_unexpectedly"
_fake_gh_budget_query_should_not_be_called 7
out="$(_run_sut --owner O --project 1 --min-budget 0)"
rc=$?
if [ -f "$WORK/budget_query_called_unexpectedly" ]; then
  bad "--min-budget 0 must waive the gate without ever invoking the budget query ($(cat "$WORK/budget_query_called_unexpectedly"))"
else
  ok "--min-budget 0 waives the gate without ever invoking the budget query"
fi

# The SAME run above already proves the waiver reaches the read path end to
# end (not just that the budget query was skipped) -- item-list answered
# normally and the script must still report the real count from it.
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=7" ]; then
  ok "recovery: --min-budget 0 waives the gate and the read still succeeds"
else
  bad "recovery: --min-budget 0 waives the gate and the read still succeeds (got rc=$rc out='$out')"
fi

# _check_budget's own has("errors") guard (added alongside
# _query_ready_count's identical, pre-existing guard): a rateLimit response
# carrying BOTH a usable `remaining` AND a top-level `errors` key (issue
# #5841's shape, applied to the budget read this time) must refuse, and
# must never let item-list run.
rm -f "$WORK/item_list_called_after_budget_errors"
_fake_gh_budget_partial_errors 3000
out="$(_run_sut --owner O --project 1 --min-budget 50 2>/dev/null)"
rc=$?
if [ "$rc" -eq 3 ] && [ -z "$out" ]; then
  ok "budget response with a healthy remaining=3000 AND an errors key -> exit 3, refused"
else
  bad "budget response with remaining=3000 AND an errors key -> exit 3 (got rc=$rc out='$out')"
fi
if [ -f "$WORK/item_list_called_after_budget_errors" ]; then
  bad "item-list must NEVER be called after a partial-errors budget response"
else
  ok "item-list is never called after a partial-errors budget response"
fi

# Recovery: a subsequent healthy, errors-free budget response succeeds
# normally (proves the errors-key check doesn't latch/cache across calls).
_fake_gh_healthy 4
out="$(_run_sut --owner O --project 1 --min-budget 50)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=4" ]; then
  ok "recovery: a clean budget response after a prior partial-errors budget response succeeds"
else
  bad "recovery: a clean budget response after a prior partial-errors budget response should succeed (got rc=$rc out='$out')"
fi

# ==========================================================================
# 7. Value quoting: --status / --repo must reject an embedded double-quote
#    (breaks the --query string's own quoting -- see the script's own
#    header/parse-loop comment). Not a shell-injection issue (every value
#    is passed as a separate argv element), but a query-correctness one.
# ==========================================================================
echo "7. --status / --repo reject an embedded double-quote"

_fake_gh_healthy 1
out="$(_run_sut --owner O --project 1 --status 'a" OR "b' --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "--status containing a double-quote is rejected at parse time"
else
  bad "--status containing a double-quote should be rejected (got rc=$rc out='$out')"
fi

out="$(_run_sut --owner O --project 1 --repo 'a/b" OR "x' --threshold 10 2>/dev/null)"
rc=$?
if [ "$rc" -eq 2 ] && [ -z "$out" ]; then
  ok "--repo containing a double-quote is rejected at parse time"
else
  bad "--repo containing a double-quote should be rejected (got rc=$rc out='$out')"
fi

# Recovery: a --status / --repo value with no double-quote parses and
# succeeds normally (paired with both refusals above).
out="$(_run_sut --owner O --project 1 --status "Ready #1" --repo "someorg/somerepo" --threshold 10)"
rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "READY_DEPTH=1" ]; then
  ok "recovery: --status / --repo without a double-quote parse and succeed normally"
else
  bad "recovery: --status / --repo without a double-quote should succeed (got rc=$rc out='$out')"
fi

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
