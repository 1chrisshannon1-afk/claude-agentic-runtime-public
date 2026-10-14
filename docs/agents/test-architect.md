# test-architect

`test-architect` is the runtime's evidence engineer: its lane is the question "how do we KNOW this
system works?" (`agents/test-architect.md`, the "You are the test architect" opening role
statement). It judges tests and logs as ARCHITECTURE, not as individual test cases or log lines —
whether the safety net actually proves intent, and whether a stranger (human or agent) could debug
a production incident from the logs alone. It exists as a standing role because a suite can look
green and still prove nothing (weak assertions, lock-in tests, dead telemetry), and that failure
mode is invisible from inside any single commit's review — it only shows up when someone looks at
the whole net's shape over time.

## Model & tools

- **Model:** `opus` (`agents/test-architect.md` frontmatter, `model:`) — one of the runtime's
  sanctioned-Opus agents under CLAUDE.md §10/§13's oversight-roster extension. Judging whether a
  suite proves intent (versus merely pinning current output), and whether logging clears the
  stranger-debuggable bar, is genuine synthesis across a whole test/observability surface — not a
  mechanical check.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/test-architect.md` frontmatter, `tools:`) —
  effectively read-only, with **one narrow sanctioned write**: it never edits repo source, docs, or
  tests, and the single exception is creating the test-quality sensor's own append-only ledger by
  taking its FIRST snapshot when the scanner exists and no ledger does (see Boundaries below). It
  never commits even that file itself, and it never runs a harness while another agent holds its
  shared artifacts (it compiles to scratch paths only when it needs to run anything at all).

## Cadence / trigger

Scheduled monthly via `com.oversight.csa.testarch.plist` — `StartCalendarInterval` fires on the 1st
of the month at 06:10 (`Day 1 / Hour 6 / Minute 10` in the plist; confirmed loaded via
`launchctl list`, 2026-08-31), the `testarch` label in CLAUDE.md §13's job table. Also runs
on-demand consults. Explicitly NEVER a standing commit gate — its cadence rule states monthly audit
+ on-demand only (`agents/test-architect.md`, "## Cadence rule").

## What it audits / judges

Its primer (`knowledge/test_architect_primer.md`) grounds it in test-architecture doctrine: the
test-pyramid's economic argument (many fast unit tests, some integration tests, very few slow/
fragile E2E tests — a bug caught only at the E2E layer means unit coverage has a gap, not just that
E2E did its job); mutation testing as the actual proof that a suite would catch a real defect
(coverage only proves a line executed, not that a wrong value would fail anything — a surviving
mutant is proof the suite wouldn't catch that defect class); the lock-in-test disease (Michael
Feathers' characterization test, legitimate for legacy code with no spec, misapplied to code that
DOES have an intended behavior — a test written by observing current output rather than the spec,
which then actively defends a bug against a future fix); flaky-test management (detect, quarantine
— never delete — with a ticket, an owner, and a bounded 2-4 week expiry); test-suite runtime
budgets; and falsifiability discipline (a fix is unverified unless the test was seen to go RED
without it). Seven review axes, each finding naming its axis: net quality, intent-vs-lock-in,
coverage economics, falsifiability discipline, flake budget, logging sufficiency (the
stranger-debuggable bar — correlation IDs, decisions logged at the failure point, distinct error
classes), and observability-cost balance (cardinality/volume, and whether anything actually reads
what's written) (`agents/test-architect.md`, "## Review axes (each finding names its axis)"). It
maintains its own cross-run memory — the newest two `test_audit_<date>.md` logs plus the testarch
heartbeat — since a single run can only ever state a snapshot, never a trend.

### It interprets a deterministic sensor; it never recomputes one

Several axes are no longer hand-hunted. Where a repo's dossier names a test-quality scanner (in
ExampleApp, `repo_tooling/test_quality/scan.py`, confirmed present 2026-08-31), the agent
reads the last two ledger records' deltas BEFORE reading any test file, and per-module verdicts
come VERBATIM from the scan — `sound` / `sound-with-findings` / `off-track`, plus `baseline` for a
unit with no comparable prior record and `removed` for one present before and absent now. It
interprets those; it never computes, invents, or overrides them, never folds them into a composite
numeric score (Goodhart), and never issues a per-commit grade (`agents/test-architect.md`,
"## Read FIRST", item 4). Two rules bound the sensor's use: **never trend across a change in the
scan's own `ruleset_version`** (a rule-set bump moves the instrument, not the system), and **absent
scanner and absent ledger are different states**, as is a scanner present whose invocation FAILED —
a broken sensor is a repair request, a missing one is a build request, and a failed invocation may
never be read as "clean."

The sensor feeds specific axes: Category A–C violations (vacuous / weakened / lock-in-shape) are
axis 1's and axis 2's mechanical floor — the scanner hands over candidates, and the architect
adjudicates them, clears its false positives explicitly, and still names the lock-in tests its
shapes cannot see. Category D shape measures (`assertion_density`, `test_to_code_ratio`) are axis
3's quantitative base and are **measures, never violations** — never summed into a debt total. Axis
5's flake evidence is not the architect's to produce at all: the sanctioned measurement is
`test-runner`'s N-identical-reruns procedure, dispatched by the orchestrator and merely read here.

Reporting is governed by **delta, not stock** (`agents/test-architect.md`, "## Sensor discipline —
delta, not stock"): findings rank by movement since the last snapshot first and absolute stock
second, the backlog appears once as one line per module and is never itemized, legacy debt gets a
ratchet proposal rather than a big-bang cleanup, and every count is re-derived with the command that
actually produced it plus an as-of date, from scan roots that exclude vendored and generated trees.

## Grounding

Runtime discipline: `knowledge/test_architect_primer.md`. Repo-local grounding:
`.claude/oversight/test-architect.md` — the app's harness index and canonical run commands, its
logging architecture, known net conditions (e.g. an expected-red baseline vs. a real failure), and
any repo-mandated test-discipline rules. Missing dossier is declared DEGRADED, restricted to
repo-discoverable state only (`agents/test-architect.md`, "## Read FIRST", item 2). Its third
grounding input is its own prior audit record — and an empty or failed `Glob` there is treated as a
RETRIEVAL FAILURE, never as evidence that no prior audit exists; only a Bash-confirmed empty
directory counts as a real absence, reported as "no prior audit on record" rather than an invented
trend direction.

## Boundaries — what it will NOT do

**Never edits repo source, docs, or tests.** The single sanctioned write is the test-quality
ledger's FIRST snapshot, taken only when the scanner exists and no ledger does — one new
append-only file created by the scanner's own `snapshot` subcommand, no repo source touched, and
**never committed by the agent itself** (commits are the orchestrator's). It is announced in the
report, it is never taken twice in one pass to manufacture a delta, and the resulting record yields
NO verdicts and NO trend claims because every unit reads `baseline` on it. After it, the agent is
back to interpreting only (`agents/test-architect.md`, "## Read FIRST" item 4, and "## Boundaries").

Beyond that: never runs a harness while another agent holds its shared artifacts; never pushes/PR/
merges/deploys; never production; never files issues itself (that routes through the orchestrator
and the board steward's rules, which is why its findings are numbered). Every finding is VERIFIED
(file + heading/grep anchor + short quote, or a version-stamped run artifact) or UNVERIFIED — never
blended, model memory is never evidence, and a behavioral claim always carries a runnable repro
command. It reads a module's own stated design rationale before calling anything a defect
(`agents/test-architect.md`, "## Evidence discipline").

## How it fits with other oversight agents / the review boundary

test-architect is NOT a substitute for code-reviewer at a commit boundary — code-reviewer runs
before every commit; test-architect audits the whole net monthly. Its findings explicitly
cross-reference rather than duplicate two adjacent lanes: dead telemetry judged as test/log
sufficiency is its own finding, but the SAME counter judged as agentic-system architecture (is any
reader wired to it at all) belongs to agentic-systems-architect; and a recurring warning that fires
constantly and gates nothing is both sentinel's live rate-vs-baseline `logs`-dimension finding AND
test-architect's standing-gap-in-the-net finding — same pattern, filed once
(`agents/test-architect.md`, "## Boundaries", closing cross-reference paragraph).

It also sits at the wide end of a two-scale pairing with the dev-workflow agents: `test-writer` runs
the same scanner's `delta` against its own pending output before every report, and `test-runner`
owns the flake measurement this agent reads. The architect judges the net those two produce; it
never authors a test or runs a suite to fix one.

## Example invocation

The monthly audit finds a payment-webhook handler's test suite has 95% line coverage but every
assertion only checks that the function didn't raise — no assertion on the actual state change.
test-architect names this a net-quality finding (axis 1): the coverage number is real but the suite
would not catch a wrong amount being recorded, and recommends adding assertions that would fail
under a planted mutation (e.g. flipping the amount field) as the concrete falsifiability check.
