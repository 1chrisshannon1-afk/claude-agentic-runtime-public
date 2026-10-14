# test-runner

`test-runner` is a narrow, cheap sub-agent whose only job is to execute test suites and report
exactly what happened — pass/fail counts, coverage, and failure details — without fixing anything
itself. It exists to separate *running and observing* tests from *writing or fixing* them, so a
verification pass never quietly turns into an uncontrolled edit. It has two modes: an ordinary run,
and a **flake-detection mode** that answers a different question entirely (see below).

## Model & tools

- **Model:** `haiku` (`agents/test-runner.md` frontmatter, `model:`) — the cheapest model in this
  slice, fitting for a mechanical run-and-report task with no judgment calls beyond "did it pass."
- **Tools:** `Bash, Read, Glob, Grep` (`agents/test-runner.md` frontmatter, `tools:`) — no
  `Edit`/`Write`. It can run commands and read output/files, but it has no mechanical way to change
  a file even if it wanted to. That grant is load-bearing for flake mode: it is *why* the agent
  reports a quarantine candidate rather than quarantining anything itself.

## When it's dispatched

On-demand, whenever an orchestrator needs a suite (or several) actually executed and reported —
after `implement`/`test-writer` land a change, as part of a pre-commit verification pass, or
whenever "run the tests and tell me what broke" is the ask. It's explicitly built to run
**independent suites in parallel** when more than one is requested, e.g. backend and frontend
together (`agents/test-runner.md`, "## What you do") — parallelism INSIDE one dispatch, which is the
cheap kind under `~/.claude/CLAUDE.md` §1 ("Parallel when it pays", rewritten 2026-09-20): one
context prefix is paid once, and the concurrent suites buy wall-clock for free. It is separately dispatched
for **flake detection** when the orchestrator asks for a rerun/soak check or asks whether a failure
is real.

## What it does

Runs the suites the orchestrator names using the project's own test commands — unit, integration,
E2E, coverage — from the correct working directory, adding coverage flags when a coverage number is
requested. It enforces a 10-minute default timeout per suite (or the repo dossier's own stated
bound) and reports a hang as a timeout rather than waiting indefinitely (`agents/test-runner.md`,
"## What you do").

Its most load-bearing rule: **"A suite that collects 0 tests is a FAILURE, not a pass."** A wrong
directory, a bad marker filter, or a swallowed import error can all produce a clean-looking empty
run, so it always reports the collected count and treats `Collected: 0` as a failure needing its
own diagnosis, never as green (`agents/test-runner.md`, "## What you never do"). Its sibling rule
covers the case where SOME tests ran: `Passed + Failed + Errors + Skipped + XFail + XPass` must
equal `Collected`, and any shortfall — a silently deselected test, a run that crashed part-way, an
`error` (its own counter, neither `Failed` nor `Skipped`, always reported as a failure) — is
itself the finding (`agents/test-runner.md`, "## What you never do"). Together they protect
against a false "all green" signal reaching the orchestrator.

Paired with it is a second anti-false-green rule: **it never re-runs a failing test until it goes
green and then reports green.** Re-running is a *measurement* (that is flake mode), never a route
to a pass — "it passed on the retry" is a finding, not a result (`agents/test-runner.md`, "## What
you never do").

It reports in a fixed structure — suite name, exact command + directory, collected count, a
reconciling breakdown of passed/failed/errors/skipped/deselected/xfail/xpass, coverage if
measured, a result of `PASS | FAIL | NOT-RUN: <reason>`, and per-failure test name / assertion /
file:line (`agents/test-runner.md`, "## Reporting") — and surfaces failures the moment a suite
finishes rather than waiting to batch them. The six outcome counters must sum to `Collected`; any
shortfall is itself the finding. **A run with hidden tests is not silently green:** `Skipped`
catches a conditional skip, `XFail` catches an expected failure (its own counter — NOT included in
`Skipped`), `XPass` catches an unexpectedly-passing xfail (JUnit records it as PASSED, the
highest-signal case since it can look like nothing happened), and `Deselected` catches a
marker/`-k` filter (JUnit drops those tests entirely). None of these is itself a failure, but each
is a finding the agent surfaces by name, never a number dropped from the summary — the same
arithmetic-reconciliation discipline that makes `Collected: 0` a failure rather than a pass
(`agents/test-runner.md`, "## What you never do" and "## Reporting").

## Flake-detection mode

A separate mode with its own question, its own procedure, and its own report shape
(`agents/test-runner.md`, "## Flake-detection mode"). The framing matters: **this mode reports
INCONSISTENCY across N reruns of identical code — it does not report pass/fail.** A suite failing
all N times is not flaky, it is broken; a suite passing all N times is "no inconsistency observed
at N=<N>", never "not flaky".

**Preconditions — nothing may vary but the run** (`agents/test-runner.md`, "### Preconditions —
nothing may vary but the run"): the code must be provably identical across all N runs, evidenced by
`git rev-parse HEAD` and `git status --porcelain` before run 1 and after run N (read-only git only);
a tree that changed mid-measurement makes the result **INCONCLUSIVE**, stated as such, with no flake
count reported. Everything else is held constant too — same selection, markers, directory,
environment, parallelism, plugins — because varying any of them measures a *different* thing
(order/parallelism/env sensitivity), a legitimate separate diagnosis but never mixed into one run
set. The 10-minute-per-run bound still applies and N runs cost N times as much; if the selection
does not fit, the agent says so and asks for a narrower selection rather than silently cutting N.
**N defaults to 3, never goes below 3, and is always reported**, with the honesty caveat stated
explicitly: at N=3 a test that fails 1 run in 10 has a ~73% chance that all three runs agree, so it
is most likely *missed* — hence "no inconsistency observed over N runs", plus a recommendation to
raise N when real confidence is needed.

**Tooling** (`agents/test-runner.md`, "### Tooling"): a repo's bespoke flake script is used only if
that repo's dossier names it sanctioned and current — one found by `grep` is not sanctioned. A
rerun-only-the-failures plugin (e.g. `pytest-rerunfailures`' `--reruns`) is forbidden for this mode
even when installed, because re-running until green *hides* the flake instead of measuring it; this
mode re-runs the whole selection every time. The definition names one concrete non-sanctioned
example: in ExampleApp, `repo_tooling/testing/flaky_detector.py` is **SUPERSEDED** (assessed
2026-08-31 by running it) — on a path that collects nothing it prints `Total tests: 0` and exits 0,
it sets `PYTHONPATH` with a `;` separator that collapses on POSIX, it force-sets `DEV_MODE`/
`SKIP_AUTH` so the reruns are not the caller's conditions, it has no subprocess timeout, and its
`--quarantine` flag writes an owner-less, expiry-less name list. "Do not invoke it."

**Procedure** (`agents/test-runner.md`, "### Procedure (plain pytest — core only, no plugin
required)"): run the selection N separate times, each in its own process, capturing a JUnit XML per
run, then tabulate outcomes across runs — every artifact written to a scratch dir, never into the
repo. The definition carries the runnable shell + tabulation snippet, using the repo's own
interpreter from the dossier, `-p no:cacheprovider` (so run *i*'s cache cannot steer run *i+1*) and
no `-x` (which would stop early and make later runs measure a smaller selection). For a JS/TS suite
the same N-separate-invocations shape is run with the repo's own runner and its machine-readable
reporter; with no such reporter, the agent reports UNVERIFIED rather than eyeballing console output.

**Reading the result** (`agents/test-runner.md`, "### Reading the result"): `RUNS=x/N` is read
first — if x < N, a `!! RUN(S) [...] PRODUCED NO JUNIT XML` line names runs that never wrote output
at all, and the measurement is INCOMPLETE → INCONCLUSIVE, never an inconsistency count (a wholly
absent run leaves no `MISSING` marker in the per-test table, so it is invisible there). Then
`COLLECTED_PER_RUN` is
read, before any per-test row — unequal counts, or any test showing `MISSING` in a run, means
a run partially collapsed (import error, fixture failure, collection error), and *that* is the
finding, outranking the per-test table. Zero collected in every run is a FAILURE, exactly as in a
normal run. Any mixed sequence (`passed -> failure -> passed`) is an inconsistency reported as the
sequence, not as a summary verdict. Failing in all N runs is consistently broken — a real failure,
not a flake — and the same `error` outcome repeating in all N runs carries the identical standing:
CONSISTENTLY BROKEN, not flaky, never a clean result, and never proposed for quarantine. `skipped`
flapping in and out counts as an inconsistency too (a conditional skip that is sometimes on is a
coverage hole that hides itself). Each failing run's message is pulled from that specific run's
log — one run's error text is never attached to a different run.

**Report shape** (`agents/test-runner.md`, "### Report shape"): selection, exact per-run command and
directory, N with the identical-code evidence (HEAD sha + tree state), the per-run collected counts
(which must be identical — if not, that IS the finding), the inconsistent tests with their
sequences and errors, the stable counts — passed/failed/errored/skipped, mirroring the tabulator's
own keys, with any key it emits that isn't named still reported by name — and a verdict of
`K INCONSISTENT over N runs` / `no inconsistency observed over N runs` /
`CONSISTENTLY BROKEN (not flaky)` / `INCONCLUSIVE — <reason>`.

**Quarantine — what it reports, never what it does** (`agents/test-runner.md`, "### Quarantine —
what you report, never what you do"): because it edits nothing, it never quarantines anything and
never writes a quarantine list; it reports the finding in the shape a quarantine record requires and
the orchestrator files it. The rules it applies: quarantine, never delete (a flagged test comes off
the merge-*blocking* path but keeps running, so failure data keeps accumulating — deleting converts
a visible flake into a silent coverage hole). **An entry is not a quarantine unless it carries all
three — a ticket, a named owner, and a bounded expiry** (2–4 weeks is the common bar), stated
explicitly per proposed test including a concrete expiry date; missing any of the three makes it an
indefinite quarantine, "a silent coverage hole with paperwork." If the repo has a quarantine
registry, it is audited in the same report (expired or incomplete entries are their own findings);
if the repo has no registry at all, the agent says so plainly, because that means nothing is
tracking the flake budget. A consistently-failing test is never proposed for quarantine — that is a
broken test being hidden.

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` first if present, specifically for "this repo's
test commands, coverage flags, and pass/coverage gate" — and, in flake mode, for the repo's own
interpreter and for whether any bespoke flake script is sanctioned. If it's missing, it says so in
its report and falls back to the repo's `CLAUDE.md` hierarchy/config — "never invent a command or
path" (`agents/test-runner.md`, the "**Repo grounding.**" paragraph). Same mechanism as the rest of
this slice.

## Boundaries — what it will NOT do

- **Never fixes failures** unless the orchestrator explicitly says to (default is collect-and-report
  only) (`agents/test-runner.md`, "## What you never do").
- **Never edits files** — consistent with its tool grant having no `Edit`/`Write`. In flake mode
  this extends to writing no quarantine list and no flake ledger of its own.
- **Never suppresses a failure to get green** — no skip/xfail-to-hide, no `# noqa`, no
  `type: ignore` (`agents/test-runner.md`, "## What you never do").
- **Never retries a failure into a pass** — re-running is a measurement, never a route to green.
- **Never touches git** — no commit, push, or write op; never
  checkout/switch/stash/reset/rebase/restore/clean/worktree (`git restore --staged` alone is
  fine — it only unstages). Flake mode's HEAD/status checks are read-only git
  (`agents/test-runner.md`, "## What you never do").
- **Never silently reports an empty run as a pass** (the 0-tests-collected rule above, which holds
  in flake mode too).
- **Never omits a counter, and never reports counts that don't reconcile** — a normal run always
  reports the full `Passed/Failed/Errors/Skipped/Deselected/XFail/XPass` breakdown, even at
  all-zero, and the six outcome counters (`Passed/Failed/Errors/Skipped/XFail/XPass` —
  `Deselected` sits outside `Collected`, not inside it) must sum to `Collected`; a shortfall, a
  conditional skip, a marker filter, an xfail/xpass, or an `error` (its own counter, neither
  `Failed` nor `Skipped`, always reported as a failure) cannot pass as silently green
  (`agents/test-runner.md`, "## What you never do" and "## Reporting").
- **Never omits a suite it could not run** — reports it as `NOT-RUN: <reason>` rather than
  dropping it or letting it read as a pass; a Bash call denied by a gate is quoted verbatim as the
  finding, never routed around (`agents/test-runner.md`, "## What you never do").

## How it fits with other agents

Pure verification role: runs checks and reports, never fixes. (The former `lint-check` seat was retired 2026-08-31 — lint/format verification is owned by the PostToolUse format hook and pre-commit.)
`test-runner`'s failure reports route back to `implement` (to fix the underlying code) or
`test-writer` (if the test itself is wrong) via the orchestrator — `test-runner` never dispatches
other agents itself, it only reports upward. It typically runs after `implement`/`test-writer` and
before `code-reviewer`/`git-ops`, giving the orchestrator a concrete pass/fail signal to act on
before anything gets committed.

Flake mode gives it a second consumer: `test-architect` names **this** procedure as the sanctioned
flake measurement for its own flake-budget axis and explicitly never runs it itself — the
orchestrator dispatches `test-runner`, and the architect interprets what comes back
(`agents/test-architect.md`, "## Review axes (each finding names its axis)", axis 5). That is also
why the architect will not recommend adopting `flaky_detector.py`: doing so would put it in direct
conflict with this agent's live instruction not to invoke it.

## Example invocation

After `implement` and `test-writer` finish a change touching both a Python backend module and its
TypeScript frontend consumer, the orchestrator dispatches `test-runner` once, asking it to run the
backend `pytest` suite for the changed module and the frontend `vitest` suite in parallel, and to
report collected counts and coverage for both — surfacing immediately if either suite collects zero
tests. Later, when one of those backend tests fails in CI but passes locally, the orchestrator
dispatches `test-runner` again in flake mode over just that selection at N=5 — expecting back a
per-run collected count, the pass/fail sequence per test, and either `INCONSISTENT` with a
three-part quarantine proposal or `CONSISTENTLY BROKEN (not flaky)`.
