# test-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file. Every count carries its re-derive command + an as-of date. VERIFIED = read, grepped,
or run live this pass; anything else is carried forward, not re-measured. A missing or stale
section here means the agent declares itself DEGRADED and audits only repo-discoverable state,
saying explicitly what it could not ground.

## (a) The harness index

*What goes here: this app's master test/harness index doc (if one exists) — its size, top
sections, and the canonical command(s) to run the full suite plus any tier variants. The auditor
needs a single, current entry point before it can judge anything about test-net health.*
Re-derive: `` `grep -n "^## \|^# " <your-harness-index-doc>` ``.

- __HARNESS_INDEX_DOC__ — *path + byte count + top section headings.*
- __TEST_RUNNER_CMD__ — *the one canonical "run everything" command, plus named tier variants
  (behavior/adversarial/determinism-style suites, if this repo has them).*
- __BUNDLE_COMPILE_PREREQUISITE__ — *if any suite needs a build/compile step before it can pass
  (e.g. a data bundle that must be freshly compiled or every test reds on an unrelated cause),
  name the exact recompile command and the gitignored artifact path it writes.*
- __SHARED_ARTIFACT_CONTENTION_RULE__ — *if that compiled artifact is a SHARED path other
  concurrent harness runs may depend on, the rule for compiling to a scratch path instead of
  overwriting it when another agent could be mid-run — cite this repo's own file-contention
  discipline, never invent one.*
- __CI_GATING_ENTRY_POINT__ — *the pre-push / local-CI recipe this repo runs before any push, and
  which flag makes it match the real CI job (a "parity" mode, if this repo has one).*

## Scan + ledger (the sensor this agent interprets — never recomputes)

*What goes here: if this repo runs a deterministic test-quality scanner (lock-in-test detection,
vacuous-assertion detection, etc.), the scanner's path, its subcommands, its scan roots/
exclusions, its full check list (violations vs. measures — never sum a measure into a debt
total), its ledger path and append semantics, and who is allowed to write to that ledger and
when. The agent INTERPRETS this sensor's output; it never recomputes a verdict by hand.* Re-derive:
`` `python3 <your-scanner-path> --help` ``.

- __TEST_QUALITY_SCANNER_PATH__ — *the scanner module/script path, if one exists.*
- __SCAN_ROOTS__ — *the exact list of top-level dirs/units the scanner covers, and what it
  deliberately excludes (vendored deps, node_modules-equivalents, worktree checkouts, etc.).*
- __VIOLATION_CHECKS__ — *the full named list of violation checks the scanner sums into a debt
  total.*
- __MEASURE_CHECKS__ — *the checks that are informational only and never summed into a total
  (e.g. assertion density, test:code ratio, test-pyramid lane counts).*
- __TEST_QUALITY_LEDGER_PATH__ — *the append-only ledger file, and the write-ownership rule: who
  (which scheduled job / which agent) is sanctioned to append a new record, and when the agent's
  own role is read-only interpretation instead.*
- __RULESET_VERSION_RULE__ — *never trend across a ruleset-version bump — state the current
  version and the date of the last bump, if any.*
- __LEDGER_WRITE_OWNERSHIP_SPLIT__ — *if the FIRST ledger record and every SUBSEQUENT one have
  different sanctioned writers (e.g. the agent takes a one-time baseline when none exists; a
  scheduled audit's orchestrating session owns every append after that), state the split exactly
  — a rule keyed only on "no ledger exists yet" silently deadlocks once one does.*
- __DIRTY_TREE_TREND_POLICY__ — *whether a record taken against an uncommitted/dirty tree is
  trend-eligible (flagged, not suppressed) or excluded outright — state which, and why.*

## Known-and-accepted debt (report WITH rationale, never as fresh findings)

*What goes here: the current STOCK baseline (total violations, by-check breakdown, worst units) —
written down so a first audit does not re-discover the same numbers as new findings. Trajectory
(delta between two ledger records under the same ruleset version), never stock, is what counts as
a real finding after the baseline exists.*

- __TEST_DEBT_BASELINE__ — *total violations, by-check breakdown, as-of date, re-derive command.*
- __TEST_DEBT_ACCEPTED_PATTERN__ — *any single check that dominates the backlog for a structural,
  accepted reason (e.g. an idiom the scanner cannot distinguish from a real defect) — state the
  reason, not just the count.*
- __WORST_UNITS_RANKING__ — *the worst-unit ranking at baseline; note that the ORDER is the
  durable fact, the totals move with the tree.*
- __CATEGORY_D_MEASURES_SHAPE__ — *the informational-only measures (assertion density, test:code
  ratio, pyramid lane counts) at baseline, written to low precision deliberately — the exact
  values move under nothing but ordinary concurrent edits, so quoting them to more than an order
  of magnitude is false precision and how this section goes stale.*
- __STRUCTURALLY_UNMEASURED_LANE__ — *any test lane (e.g. a true E2E lane) this scanner cannot see
  at all because it lives in a different language/tool outside the scanner's scope — name it so a
  zero count is never misread as "no tests exist" for that lane.*

## (b) Golden net — condemned-baseline semantics, mutation battery, falsifiability

*What goes here: if this app has a "golden net" (a baseline-signature regression net) or a
mutation-testing harness that plants known bugs to measure catch rate, describe its trust
semantics (what makes a baseline "condemned" vs. "active"), the mutation battery's size, and the
falsifiability-gate tool (if one exists) that proves a fix is real by reverting it and confirming
red.* Re-derive: `` `grep -n "<baseline-trust-marker>" <your-harness-index-doc>` ``.

- __GOLDEN_NET_BASELINE_TRUST__ — *how a baseline's trust state is tracked and what happens when
  it's untrusted.*
- __MUTATION_BATTERY_SIZE__ — *planted-bug count + how to run it.*
- __FALSIFIABILITY_GATE_TOOL__ — *the tool (if any) that reverts a fix and confirms the paired
  test goes red without it — its verdict vocabulary and exit codes.*
- __FALSIFIABILITY_GATE_WIRING__ — *whether the falsifiability tool above is actually wired into
  any consumer (pre-commit hook, CI job, local-CI script) or exists but is invoked by nobody — a
  wired invocation nobody reads the exit code of is not an enforced gate; say which state this is
  in, don't assume wired-means-enforced.*

## D1 mutation-survival baseline (if this app runs a chat/tool-agent dispatch harness)

*What goes here: if this app dispatches tools via an in-app agent (e.g. a chat copilot) and runs
a mutation-survival check (gutting a tool's own execution function and confirming the harness
still catches it), the current survived/killed count, the re-derive script shape, and the
specific class of tool that still survives (and why) — this is a live, re-measured number, never
a frozen one; state its as-of date every time it's quoted.*

- __D1_MUTATION_SURVIVAL_COUNT__ — *survived/killed counts, as-of date, re-derive script path or
  inline shape.*
- __D1_KNOWN_SURVIVOR_CLASS__ — *the class of tool dispatch that still survives the mutation
  (e.g. a receipt-minting tool with no dedicated recorder-call assertion) — a real, scoped,
  narrower gap, not a general harness failure.*

## Coverage gate

*What goes here: the coverage-floor config value, the REAL CI invocation that enforces it (which
job, which step — and whether a DIFFERENT job in the same CI config runs coverage with the floor
deliberately zeroed for an unrelated reason, which is not the gate), and whether the gate is
enforced-when-run or has ever actually completed end-to-end in CI.*

- __COVERAGE_FLOOR_VALUE__ — *the configured floor + its file/line.*
- __COVERAGE_GATE_REAL_INVOCATION__ — *the CI job/step that actually enforces it, and its
  `if:`/trigger condition (may legitimately skip on an ordinary narrow PR).*
- __COVERAGE_GATE_ENFORCEMENT_TIER__ — *enforced-when-run vs. report-only — state which, sourced
  from this repo's own CI-config classification, never assumed from the floor's existence alone.*

## Known net conditions

*What goes here: which suites are EXPECTED to be red right now (an intentionally-skipped or
known-failing suite, a suite gated behind an unmet local precondition, a suite that only passes
after a build/compile step this file already names above), why each one is expected-red, and the
concrete signal that distinguishes an expected-red suite from a real, newly-introduced failure —
so a single run never mistakes one for the other.*

- __EXPECTED_RED_BASELINE__ — *the exact suite/test-id list currently expected-red, the reason for
  each (missing local precondition, a tracked issue, a deliberate skip), and the check (a marker
  string, a skip reason, an issue-number citation in the failure output) that tells this baseline
  apart from a genuinely new red.*

## (c) LOGGING REALITY

*What goes here: this app's actual logging architecture — which logger wrapper(s) exist, whether
plain stdlib loggers coexist with a structured one, where logs land (stdout/file/cloud sink), and
the read-back recipe for querying them live.*

- __STRUCTURED_LOGGER_MODULE__ — *the structured-logging wrapper module, if one exists.*
- __PLAIN_LOGGER_COEXISTENCE__ — *any modules that bypass the wrapper and call the stdlib logger
  directly — named honestly, since this is a real split the auditor must check before judging a
  module's logging.*
- __LOG_READBACK_RECIPE__ — *the actual command to read recent logs live (log-sink query, etc.).*

## KNOWN STANDING DEFECTS — first audit seeds from these (TRACKED, not new)

*What goes here: currently-open, already-filed issues relevant to test-net/observability health —
each with its issue number, one-line description, and VERIFIED-with-date citation, so a first
audit treats them as tracked history rather than rediscovering them.*

- __STANDING_DEFECT_1__ — *issue # + description + verify command.*
- __ORPHAN_TOOL_CHECK__ — *any test-support module found to be an orphan (no live caller anywhere
  outside its own file/archived docs) — its line count, the grep that proves zero live callers,
  and the decision this leaves open (adopt it, rewrite it, or delete it — never leave both an old
  and new version alive at once).*

## (d) Lane boundary vs. any engine-specific test architect

*What goes here: if this repo has a separate specialist agent that owns test/harness architecture
for one specific subsystem (e.g. a domain engine's own correctness net), state the boundary
explicitly — this agent owns the APP-WIDE test/observability architecture (frontend suites,
integration tests, CI gating, the pre-push recipe); the subsystem specialist owns its own domain's
correctness net.*

- __LANE_BOUNDARY_NOTE__ — *the specific subsystem carved out, and which agent owns it.*
- __LANE_BOUNDARY_EVIDENCE__ — *the concrete paths that prove this agent's own scope (e.g. the
  frontend/E2E harness heading, the integration-tests directory, the CI-gating section) — cite
  what actually exists, not an assumed division of labor.*

## Subsystem inventory

*What goes here: for this app's highest-value subsystems (the ones with the largest
un-enumerated decision spaces), a table of: module path(s), the decision-vocabulary source of
truth, the instrument (if any) that measures coverage of that vocabulary, the reader/consumer of
that instrument's output, and the current vocabulary size. This does not need to cover every
module — state which subsystems it covers and flag any absent module as a tracked gap, not a
silent omission.*

| subsystem | module path(s) | decision-vocabulary source of truth | instrument (path or NONE) | reader (ledger/CI/NONE) | vocab size (as-of, re-derived) |
|---|---|---|---|---|---|
| __SUBSYSTEM_ROW__ | | | | | |

- __SHARED_ROUTE_COVERAGE_INSTRUMENT__ — *if a single shared helper (e.g. a route-presence
  assertion) is deployed identically across many modules, name it once here rather than in every
  row — and state exactly what it does NOT measure (status codes, auth outcomes, payload shape,
  permission combinations) so its presence is never mistaken for closing a bigger gap.*
- __SUBSYSTEM_SWEEP_FOLLOWUP__ — *if this table covers only the highest-value subsystems and not
  every module in the repo, say so explicitly and name the follow-up to sweep the rest — any
  module absent from this table is a tracked gap, never a silent one.*

## How to re-derive

*What goes here: the full command block backing every count in this file, grouped by the fact
they support, so the next audit can re-run them wholesale.*

__RE_DERIVE_COMMAND_BLOCK__
