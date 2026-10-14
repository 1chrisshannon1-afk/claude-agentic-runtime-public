#!/usr/bin/env bash
# run_tests.sh -- the full hermetic test run for this checkout.
#
# Runs, in order, from the repository root, and stops at the first failure:
#   1. python  hooks/tests                 (per-module coverage table when pytest-cov is installed)
#   2. python  tools/gtm/tests
#   3. shell   every hooks/tests/test_*.sh (each is run with bash; exit status is the verdict)
#   4. node    workflows/tests/test_issue_wheel_triage.mjs
#
# A location that runs zero tests is a FAILURE, not a pass: each pytest location
# must report at least one passed test, and the node file must pass at least
# NODE_MIN_PASS tests (a vacuous green is how a hollowed suite hides).
#
# Hermetic by default: the suite's conftest.py sandboxes $HOME per test, so this
# does not touch the operator's live enforcement/review/budget state. The one
# deliberate exception is the `live_machine` smoke tests, which read this
# machine's real telemetry and are therefore deselected unless asked for. Every
# location runs with stdin from /dev/null. Like the suite itself this must run
# from the deployed shape (the checkout IS $HOME/.claude); to test any other
# checkout, stage it with scripts/ci_layout.sh, which also sets the environment
# below for you.
#
# Usage:  bash hooks/run_tests.sh          (from any directory)
# Exit:   0 only when every location passed with a non-zero test count.
#
# Environment (all optional):
#   PYTHON                   interpreter to use (default: python3)
#   RUN_TESTS_LIVE_MACHINE   set to 1 to include the slow `live_machine` smoke tests, which
#                            read this machine's real telemetry (default: deselected)
#   RUN_TESTS_SKIP_NODE      set to 1 to skip the node location when node is not installed
#   PYTEST_ADDOPTS           standard pytest variable, applied to both pytest locations. Use it
#                            to move pytest's temp dirs: by default they live under the system
#                            temp dir (/tmp on Linux), which agentarch_metric_check.py treats as
#                            an always-safe root and so changes what its tests assert. Give it a
#                            dedicated directory outside /tmp and outside $HOME, e.g.
#                              PYTEST_ADDOPTS="--basetemp=/var/tmp/csa-pytest-tmp" bash hooks/run_tests.sh
#                            pytest CLEARS that directory on every run, so never point it at one
#                            that holds anything else.
#
# Needs: bash, python3 with pytest, and node (unless RUN_TESTS_SKIP_NODE=1).
# pytest-cov is optional: coverage is measured and reported only when
# `import pytest_cov` succeeds. GNU `timeout` is not needed.

set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$HOOKS_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
# Floor for the node location: the file holds well over this many tests, so a
# load failure or a wall of skips cannot satisfy a bare "tests > 0".
NODE_MIN_PASS=13

cd "$ROOT_DIR" || {
  echo "run_tests.sh: cannot cd into repository root '$ROOT_DIR'" >&2
  exit 2
}

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/run_tests.XXXXXX")"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

fail() {
  echo >&2
  echo "run_tests.sh: FAIL: $*" >&2
  exit 1
}

# last_count LOG PATTERN -> the number in front of the last "<n> PATTERN" in LOG, or 0.
last_count() {
  local found
  found="$(grep -Eo "[0-9]+ $2" "$1" | tail -n 1 | grep -Eo '^[0-9]+' || true)"
  echo "${found:-0}"
}

# run_pytest LABEL ARGS... -- stream pytest, then require exit 0 AND passed > 0.
# Sets PYTEST_PASSED to the passed-test count for the caller.
PYTEST_PASSED=0
run_pytest() {
  local label="$1" log rc
  shift
  log="$WORK_DIR/pytest.$$.log"
  echo
  echo "=== $label ==="
  set +e
  "$PYTHON" -m pytest "$@" </dev/null 2>&1 | tee "$log"
  rc="${PIPESTATUS[0]}"
  set -e
  [ "$rc" -eq 0 ] || fail "$label: pytest exited $rc"
  PYTEST_PASSED="$(last_count "$log" passed)"
  [ "$PYTEST_PASSED" -gt 0 ] || fail "$label: pytest exited 0 but ran 0 passing tests (collected nothing, or every test skipped)"
  rm -f "$log"
  SUMMARY+=("$label: $PYTEST_PASSED passed")
  TOTAL_PASSED=$((TOTAL_PASSED + PYTEST_PASSED))
}

SUMMARY=()
TOTAL_PASSED=0

# ---- 1. hooks/tests -------------------------------------------------------
MARK_ARGS=(-m "not live_machine")
if [ "${RUN_TESTS_LIVE_MACHINE:-0}" = "1" ]; then
  MARK_ARGS=()
fi

COV_JSON=""
COV_ARGS=()
if "$PYTHON" -c "import pytest_cov" >/dev/null 2>&1; then
  COV_JSON="$WORK_DIR/coverage.json"
  # Measure every hooks/*.py source module; the table below filters the report
  # down to those, leaving out the tests/ package and conftest scaffolding.
  COV_ARGS=(--cov=hooks --cov-report=term-missing "--cov-report=json:$COV_JSON")
  export COVERAGE_FILE="$WORK_DIR/.coverage"
else
  echo "run_tests.sh: pytest-cov not installed -- running hooks/tests WITHOUT coverage" >&2
fi

run_pytest "hooks/tests" hooks/tests -q \
  ${MARK_ARGS[@]+"${MARK_ARGS[@]}"} ${COV_ARGS[@]+"${COV_ARGS[@]}"}

if [ -n "$COV_JSON" ] && [ -f "$COV_JSON" ]; then
  echo
  echo "==================================================================="
  echo " Per-module line coverage -- hooks/*.py source modules"
  echo "==================================================================="
  COV_JSON="$COV_JSON" "$PYTHON" - <<'PY'
import json
import os

cov_path = os.environ["COV_JSON"]
try:
    with open(cov_path, encoding="utf-8") as fh:
        data = json.load(fh)
except Exception as exc:  # the report is advisory; the test verdict is already in
    print(f"  (could not read coverage report: {exc})")
    raise SystemExit(0)

rows = []
for name, info in sorted(data.get("files", {}).items()):
    norm = name.replace("\\", "/")
    base = os.path.basename(norm)
    # Source modules only: skip the test package and the conftest scaffolding.
    if "tests/" in norm or base == "conftest.py" or not base.endswith(".py"):
        continue
    summ = info.get("summary", {})
    rows.append(
        (base, summ.get("num_statements", 0), summ.get("missing_lines", 0), summ.get("percent_covered", 0.0))
    )

width = max([len(r[0]) for r in rows] + [len("Module")])
print(f"  {'Module':<{width}}  {'Stmts':>6}  {'Miss':>5}  {'Cover':>7}")
print("  " + "-" * (width + 24))
for base, stmts, miss, pct in rows:
    print(f"  {base:<{width}}  {stmts:>6}  {miss:>5}  {pct:>6.1f}%")
print("  " + "-" * (width + 24))

totals = data.get("totals", {})
print(
    f"  {'TOTAL (incl. tests)':<{width}}  {totals.get('num_statements', 0):>6}  "
    f"{totals.get('missing_lines', 0):>5}  {totals.get('percent_covered', 0.0):>6.1f}%"
)
s_stmts = sum(r[1] for r in rows)
s_miss = sum(r[2] for r in rows)
s_pct = (100.0 * (s_stmts - s_miss) / s_stmts) if s_stmts else 100.0
print(f"  {'TOTAL (source only)':<{width}}  {s_stmts:>6}  {s_miss:>5}  {s_pct:>6.1f}%")
PY
fi

# ---- 2. tools/gtm/tests ---------------------------------------------------
run_pytest "tools/gtm/tests" tools/gtm/tests -q

# ---- 3. hooks/tests/*.sh --------------------------------------------------
SH_TESTS=()
for candidate in "$HOOKS_DIR"/tests/test_*.sh; do
  if [ -f "$candidate" ]; then
    SH_TESTS+=("$candidate")
  fi
done
[ "${#SH_TESTS[@]}" -gt 0 ] || fail "hooks/tests/test_*.sh: found no shell tests to run"
for sh_test in "${SH_TESTS[@]}"; do
  rel="${sh_test#"$ROOT_DIR"/}"
  echo
  echo "=== $rel ==="
  bash "$sh_test" </dev/null || fail "$rel exited non-zero"
done
SUMMARY+=("hooks/tests/test_*.sh: ${#SH_TESTS[@]} scripts ok")

# ---- 4. workflows/tests (node) --------------------------------------------
NODE_TEST="workflows/tests/test_issue_wheel_triage.mjs"
echo
echo "=== $NODE_TEST ==="
if ! command -v node >/dev/null 2>&1; then
  if [ "${RUN_TESTS_SKIP_NODE:-0}" = "1" ]; then
    echo "run_tests.sh: node not installed -- skipping $NODE_TEST (RUN_TESTS_SKIP_NODE=1)" >&2
    SUMMARY+=("$NODE_TEST: SKIPPED (node not installed)")
  else
    fail "node is not installed, so $NODE_TEST cannot run (set RUN_TESTS_SKIP_NODE=1 to skip it)"
  fi
else
  NODE_LOG="$WORK_DIR/node.log"
  set +e
  node --test --test-reporter=tap "$NODE_TEST" </dev/null 2>&1 | tee "$NODE_LOG"
  node_rc="${PIPESTATUS[0]}"
  set -e
  [ "$node_rc" -eq 0 ] || fail "$NODE_TEST: node --test exited $node_rc"
  node_pass="$(grep -E '^# pass [0-9]+' "$NODE_LOG" | tail -n 1 | grep -Eo '[0-9]+$' || true)"
  node_fail="$(grep -E '^# fail [0-9]+' "$NODE_LOG" | tail -n 1 | grep -Eo '[0-9]+$' || true)"
  [ -n "$node_pass" ] && [ -n "$node_fail" ] || fail "$NODE_TEST: could not read '# pass' / '# fail' from the node TAP summary"
  [ "$node_fail" -eq 0 ] || fail "$NODE_TEST: $node_fail failing test(s)"
  [ "$node_pass" -ge "$NODE_MIN_PASS" ] || fail "$NODE_TEST: only $node_pass passing test(s), expected at least $NODE_MIN_PASS"
  SUMMARY+=("$NODE_TEST: $node_pass passed")
  TOTAL_PASSED=$((TOTAL_PASSED + node_pass))
fi

echo
echo "==================================================================="
echo " run_tests.sh: ALL LOCATIONS PASSED"
for line in "${SUMMARY[@]}"; do
  echo "   $line"
done
echo "   TOTAL TESTS (python + node passed): $TOTAL_PASSED"
echo "==================================================================="
