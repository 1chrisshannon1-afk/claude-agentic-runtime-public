// =============================================================================
// test_issue_wheel_triage.mjs -- Node test harness for issue-wheel-triage.js
// (THE ISSUE WHEEL P1). Plan: luminous-napping-marble.md, H2 "Test-harness
// mechanism, decided" (commit #2 of the commit sequence).
//
// WHY A SHIM, NOT A STANDARD IMPORT (closes round-3 blocker B1 / round-4
// blocker B4-1 -- see the plan section this file implements):
// issue-wheel-triage.js is a Workflow *script body*, not an ES module. It
// opens with `export const meta = {...}` and ends with a top-level
// `return {...}` (confirmed at the end of the production file) -- a bare
// `import()` or `--experimental-vm-modules` load of this file throws
// `SyntaxError: Illegal return statement`, because a top-level `return` is
// not legal in any standard module or script body. There is no ESM/CJS
// loader seam for this file's shape.
//
// REJECTED ALTERNATIVE: extracting the fan-out logic into an importable
// sibling (e.g. workflows/lib/triage_phases.mjs) shared by production and
// test. Rejected because check_workflow_agent_purity.py's own
// _FILENAME_GLOB_PATTERN ("issue-wheel-*.js") only scans files matching that
// glob -- a lib/ sibling would sit permanently OUTSIDE the purity checker's
// coverage, silently exempting exactly the code this hardening plan exists
// to bring under review discipline. This file does not do that: it reads
// and executes the REAL, unmodified production source text, verbatim, with
// zero new files for the purity checker to miss.
//
// CHOSEN MECHANISM: read the production file's source text, strip its
// leading `export const meta = {...}` block (meta is asserted on
// separately, never executed inside the shim -- `export` is illegal inside
// a Function/AsyncFunction body), and wrap the remainder -- including its
// trailing `return {...}` -- in `new AsyncFunction(...)`. The production
// script contains top-level `await` (nit 12, GH #4767 WS14-S1 item 1d: this
// used to read "three sites: Triage/Verify/Screen each `await
// parallel(...)`" -- since the bounded-retry helper `runBatchesWithRetry`
// was factored out, there are TWO textual `await parallel(...)` call sites
// -- the first pass and the retry-wave loop, both inside that one shared
// helper -- called once per phase (three times at runtime: Triage, Verify,
// Screen) rather than three separate top-level call sites), which a plain
// `new Function(...)` cannot hold (`SyntaxError: await is only valid in
// async functions...`), so the constructor MUST be AsyncFunction, derived
// via `Object.getPrototypeOf(async function(){}).constructor` -- there is
// no global `AsyncFunction` binding.
//
// INJECTABLE IDENTIFIER LIST: every free identifier the Workflow host
// supplies that the script actually references. Grepping the production
// file finds four, not just `agent`: `agent`, `args`, `log`, `parallel`,
// `phase`. All four are host-injected free variables that get closed over
// by the raw script body once it is turned into an AsyncFunction; there is
// no other way for the body's bare `agent(...)`, `args`/`OPTS`, `log(...)`,
// `parallel(...)`, and `phase(...)` references to resolve. If a future edit
// to the production script introduces another host-supplied free
// identifier, `new AsyncFunction(...)` itself does NOT fail at construction
// time (the body is not scanned for free variables until it runs) -- the
// failure surfaces the first time that new identifier is referenced during
// execution, as a loud `ReferenceError` naming the missing identifier. That
// is the intended drift signal, not a silent pass: a shim run that produces
// a clean result proves nothing was missing; a ReferenceError is exactly
// the "shim needs updating" alarm this file is designed to raise.
// =============================================================================

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { execFileSync } from 'node:child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PRODUCTION_FILE = path.join(__dirname, '..', 'issue-wheel-triage.js')

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

// The exact free-identifier list the Workflow host supplies to this script,
// in the order they are bound as AsyncFunction parameters. Keep this in
// sync with the production file's actual references -- see the
// ReferenceError drift-signal note above for what happens when it drifts.
const INJECTABLE_IDENTIFIERS = ['agent', 'args', 'log', 'parallel', 'phase']

// Matches the production file's leading `export const meta = { ... }`
// block. Deliberately anchored at the very start of the source (`^`, no
// `m` flag on this half) since that is the file's only legal `export` and
// it must be the first thing in the file for this strip to be correct.
// Non-greedy up to the FIRST top-level `}\n` following `export const meta`
// would be fragile against nested braces inside meta's own value (its
// `phases` array of objects), so instead this locates the matching closing
// brace by brace-depth counting rather than a regex alone -- see
// stripLeadingMetaExport() below.
const META_EXPORT_PREFIX_RE = /^export\s+const\s+meta\s*=\s*\{/

/**
 * Reads issue-wheel-triage.js's source text and splits it into:
 *   - metaSource: the raw text of the `export const meta = {...}` object
 *     literal (for separate regex/JSON-style assertions on its shape --
 *     never executed inside the AsyncFunction shim, since `export` is
 *     illegal inside a Function/AsyncFunction body)
 *   - body: everything after that block, which is the text handed to
 *     `new AsyncFunction(...)` as its function body
 *
 * Brace-depth counting (not a single regex) is used to find the end of the
 * meta object literal, because meta's own value contains nested object
 * literals (the `phases` array) whose braces would break a naive
 * non-greedy "first closing brace" regex.
 *
 * Throws loudly if the production file's shape has changed in a way this
 * stripper doesn't understand -- confirmed at each throw site.
 */
function stripLeadingMetaExport(source) {
  const prefixMatch = source.match(META_EXPORT_PREFIX_RE)
  if (!prefixMatch) {
    throw new Error(
      'test_issue_wheel_triage.mjs: production file shape changed -- ' +
      'expected it to open with "export const meta = {" and it does not. ' +
      'The meta-stripping logic in this test file needs updating.'
    )
  }
  // Walk forward from the opening brace of the meta object literal,
  // tracking depth, to find the brace that closes it. This intentionally
  // does not attempt to skip braces inside string/template literals within
  // meta -- the production meta block is a plain object literal of string
  // properties and a nested array of plain objects (confirmed by reading
  // the file), so a full JS tokenizer is not warranted here.
  const openBraceIndex = prefixMatch[0].length - 1 // index of the "{" itself
  let depth = 0
  let endIndex = -1
  for (let i = openBraceIndex; i < source.length; i++) {
    const ch = source[i]
    if (ch === '{') depth++
    else if (ch === '}') {
      depth--
      if (depth === 0) {
        endIndex = i
        break
      }
    }
  }
  if (endIndex === -1) {
    throw new Error(
      'test_issue_wheel_triage.mjs: could not find the closing brace of the ' +
      'leading "export const meta = {...}" block by brace-depth counting -- ' +
      'the production file shape changed. The meta-stripping logic in this ' +
      'test file needs updating.'
    )
  }

  const metaObjectSource = source.slice(openBraceIndex, endIndex + 1)
  // Consume through the statement's trailing `}` and an optional semicolon
  // plus the rest of that line, so `body` starts cleanly on the next line.
  let afterMeta = endIndex + 1
  if (source[afterMeta] === ';') afterMeta++
  const nextNewline = source.indexOf('\n', afterMeta)
  const body = nextNewline === -1 ? '' : source.slice(nextNewline + 1)

  return { metaObjectSource, body }
}

/**
 * Parses the `export const meta = {...}` object literal's source text into
 * a real JS value WITHOUT executing it inside the shim (export is illegal
 * inside a Function/AsyncFunction body). Uses `new Function('return (' +
 * src + ')')` -- deliberately the PLAIN (non-async) Function constructor,
 * scoped to evaluating a single object-literal expression with no
 * await/export/return-statement content of its own, which is a
 * meaningfully narrower operation than executing the full script body.
 */
function parseMetaObject(metaObjectSource) {
  // eslint-disable-next-line no-new-func
  const evaluator = new Function(`return (${metaObjectSource})`)
  return evaluator()
}

/**
 * Loads issue-wheel-triage.js's source, strips its leading meta export,
 * and returns:
 *   - meta: the parsed meta object (name, description, phases)
 *   - run(injected): an async function that constructs a fresh
 *     AsyncFunction from the stripped body on every call (so each test
 *     case gets an independent closure over its own stub agent/parallel/
 *     phase/log and its own args -- no shared state leaks between test
 *     cases) and invokes it with the given injected values, awaited,
 *     returning whatever the production script's own top-level `return
 *     {...}` produces.
 *
 * injected is an object with keys drawn from INJECTABLE_IDENTIFIERS
 * (agent, args, log, parallel, phase); any identifier a caller omits is
 * bound to a permissive no-op default EXCEPT `args`, which has no safe
 * default (the production file throws immediately without a valid
 * args.repo/project/projectOwner/today) and must always be supplied by the
 * caller.
 *
 * sourceTextOverride: TEST-ONLY escape hatch (optional). When provided, this
 * exact string is used as the production source text instead of reading
 * PRODUCTION_FILE from disk -- lets a test drive this real function
 * end-to-end against a deliberately mutated/drifted source (e.g. a second
 * top-level export) without writing a temp file. Omitted entirely in normal
 * use, where the real production file is always read from disk.
 */
export function loadIssueWheelTriageShim(sourceTextOverride) {
  const source = typeof sourceTextOverride === 'string' ? sourceTextOverride : readFileSync(PRODUCTION_FILE, 'utf8')
  const { metaObjectSource, body } = stripLeadingMetaExport(source)

  // Closes round-4 risk B4-R2's drift-detection concern for the
  // meta-stripping step specifically: if the strip left another `export`
  // statement in the body (e.g. the production file grew a second export),
  // that is illegal inside an AsyncFunction body and would otherwise fail
  // with an opaque SyntaxError far from its real cause. Fail loudly here
  // instead, naming the actual problem.
  if (/^\s*export\s/m.test(body)) {
    throw new Error(
      'test_issue_wheel_triage.mjs: production file shape changed -- the ' +
      'stripped body still contains a top-level "export" statement after ' +
      'removing the leading meta block. The meta-stripping logic in this ' +
      'test file needs updating (there may be a second export now).'
    )
  }

  const meta = parseMetaObject(metaObjectSource)

  const shimFn = new AsyncFunction(...INJECTABLE_IDENTIFIERS, body)

  async function run(injected) {
    if (!injected || typeof injected.args === 'undefined') {
      throw new Error(
        'test_issue_wheel_triage.mjs: run(injected) requires an explicit ' +
        'injected.args -- there is no safe default (the production script ' +
        'throws immediately without args.repo/project/projectOwner/today).'
      )
    }
    const boundAgent = injected.agent || defaultStubAgent
    const boundLog = injected.log || (() => {})
    const boundParallel = injected.parallel || defaultParallel
    const boundPhase = injected.phase || (() => {})
    return shimFn(boundAgent, injected.args, boundLog, boundParallel, boundPhase)
  }

  return { meta, run, source, body }
}

// Permissive defaults for identifiers a test case doesn't care about
// stubbing itself -- never used for `args`, which always requires an
// explicit caller-supplied value (see run() above).
async function defaultStubAgent() {
  return { items: [] }
}

// The production script's own fan-out shape is `parallel(list.map((x) => ()
// => agent(...)))` -- an array of zero-arg thunks. The real Workflow host's
// `parallel()` implementation is not available to this test file (it is a
// host primitive, not something this repo's Workflow scripts define), so
// the default here runs the thunks concurrently via Promise.all, which is a
// faithful enough semantic stand-in for "fan out and await all of them" for
// exercising the production script's own downstream aggregation logic. Any
// test case that needs to control ordering, partial failure, or timing
// should pass its own `parallel` stub instead of relying on this default.
async function defaultParallel(thunks) {
  return Promise.all(thunks.map((thunk) => thunk()))
}

// -----------------------------------------------------------------------
// Minimal args fixture builder (closes round-4 risk B4-R1): the production
// script hard-fails without args.today (Date.now()/new Date() are
// unavailable inside Workflow scripts), and also requires
// args.repo/args.project/args.projectOwner. This is the harness's shared
// minimum-viable fixture, seeded here rather than left to be discovered as
// a failure during a later commit's test-writing.
// -----------------------------------------------------------------------
export function minimalArgs(overrides = {}) {
  return {
    repo: 'ExampleApp',
    project: 'test-project',
    projectOwner: 'test-owner',
    today: '2026-09-09',
    issues: [],
    ...overrides,
  }
}

export { INJECTABLE_IDENTIFIERS, PRODUCTION_FILE, stripLeadingMetaExport, parseMetaObject }

// =============================================================================
// Harness smoke tests. These prove the AsyncFunction shim mechanism itself
// works against the REAL, unmodified issue-wheel-triage.js -- that it loads,
// strips meta correctly, executes the real fan-out/dedupe/schema-enforcement/
// lane-prefilter logic unchanged, and returns the script's own real return
// value. This file intentionally stops at proving the HARNESS works; the
// RED/GREEN behavioral proof for commit #3's own fix (Triage/Verify
// batch-failure surfacing) lands directly below these smoke tests, in this
// same commit -- see the "Falsifiable RED/GREEN pairs for commit #3" section
// further down this file. (RULE G-BATCH-LOSS, the ≥50% combined-loss degrade
// rule that consumes this commit's totals.triage_batches field, is a
// separate, later commit (#4) and is not tested here.)
//
// Run: node --test ~/.claude/workflows/tests/test_issue_wheel_triage.mjs
// =============================================================================

import { test } from 'node:test'
import assert from 'node:assert/strict'

test('loadIssueWheelTriageShim() parses meta without executing it', () => {
  const { meta } = loadIssueWheelTriageShim()
  assert.equal(meta.name, 'issue-wheel-triage')
  assert.equal(typeof meta.description, 'string')
  assert.ok(Array.isArray(meta.phases))
  assert.deepEqual(
    meta.phases.map((p) => p.title),
    ['Triage', 'Verify', 'Screen']
  )
})

test('loadIssueWheelTriageShim() strips the leading export cleanly (no export left in body)', () => {
  const { body } = loadIssueWheelTriageShim()
  assert.ok(!/^\s*export\s/m.test(body), 'stripped body must contain no top-level export statement')
})

test('the shim throws the production file\'s own required-args errors for missing args.repo', async () => {
  const { run } = loadIssueWheelTriageShim()
  await assert.rejects(
    () => run({ args: minimalArgs({ repo: '' }) }),
    /args\.repo is required/
  )
})

test('the shim throws the production file\'s own required-args errors for missing args.today', async () => {
  const { run } = loadIssueWheelTriageShim()
  await assert.rejects(
    () => run({ args: { repo: 'r', project: 'p', projectOwner: 'o', issues: [] } }),
    /args\.today is required/
  )
})

test('the real script executes end-to-end through the shim with zero seed issues', async () => {
  const { run } = loadIssueWheelTriageShim()
  const result = await run({ args: minimalArgs({ issues: [] }) })
  assert.equal(result.totals.seed_count, 0)
  assert.equal(result.totals.triaged_count, 0)
  assert.deepEqual(result.needs_work, [])
  assert.deepEqual(result.verdicts_close_class, [])
})

test('the real script fans out one agent() call per Triage batch and dedupes by number', async () => {
  const { run } = loadIssueWheelTriageShim()
  const seenLabels = []
  // Issue #1 gets an 'unclear' verdict (non-close-class) so this fixture
  // exercises Triage's own fan-out/dedupe logic without also invoking
  // Verify's separate fan-out -- Verify's own contract is covered by other
  // test cases in this file.
  const stubAgent = async (_prompt, opts) => {
    seenLabels.push(opts.label)
    // Two seed issues, one Triage batch (batch size 5) -- return a verdict
    // for both, plus a duplicate row for #1 to prove first-wins dedupe.
    return {
      items: [
        { number: 1, verdict: 'unclear', rationale: 'r1' },
        { number: 1, verdict: 'operator_only', rationale: 'duplicate-row-should-be-ignored' },
        { number: 2, verdict: 'unclear', rationale: 'r2' },
      ],
    }
  }
  const result = await run({
    args: minimalArgs({
      issues: [
        { number: 1, title: 'one', labels: [] },
        { number: 2, title: 'two', labels: [] },
      ],
    }),
    agent: stubAgent,
  })
  assert.deepEqual(seenLabels, ['triage:1'])
  assert.equal(result.totals.triaged_count, 2)
  // First verdict for #1 wins (unclear), the duplicate operator_only row is
  // discarded -- proving the real dedupe logic ran unmodified.
  const one = result.unclear.find((i) => i.number === 1)
  assert.ok(one, 'issue #1 must land in unclear (first verdict wins the dedupe)')
  assert.equal(one.verdict, 'unclear')
  assert.equal(result.operator_only.find((i) => i.number === 1), undefined)
})

test('an off-enum Triage verdict is routed to unclear, never silently dropped (existing defensive floor)', async () => {
  const { run } = loadIssueWheelTriageShim()
  const stubAgent = async () => ({
    items: [{ number: 7, verdict: 'totally_not_a_real_verdict', rationale: 'bogus' }],
  })
  const result = await run({
    args: minimalArgs({ issues: [{ number: 7, title: 'seven', labels: [] }] }),
    agent: stubAgent,
  })
  assert.equal(result.unclear.length, 1)
  assert.equal(result.unclear[0].number, 7)
  assert.match(result.unclear[0].rationale, /routed to unclear: off-enum verdict/)
})

test("Screen's existing {batch, result} contract: an empty agent return fails every item in that batch (not a pass-through)", async () => {
  const { run } = loadIssueWheelTriageShim()
  // Drive one needs_work item through Triage so it reaches Screen, then
  // stub Screen's own agent() call (label starts with "screen:") to return
  // an empty items array -- Screen's pre-existing, already-correct
  // contract treats that as a failure for every item in the batch.
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [
          {
            number: 42,
            verdict: 'needs_work',
            rationale: 'cites shared/ai/model_registry.py',
            files_touched: ['shared/ai/model_registry.py'],
            size_points: 3,
          },
        ],
      }
    }
    if (opts.label.startsWith('screen:')) {
      return { items: [] }
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }
  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })
  assert.equal(result.needs_work_screen_failed.length, 1)
  assert.equal(result.needs_work_screen_failed[0].number, 42)
  assert.equal(result.needs_work_screen_failed[0].fail_reason, 'SCREEN_ERROR: empty agent return')
  assert.deepEqual(result.needs_work, [])
})

// =============================================================================
// Falsifiable RED/GREEN pairs for the harness MECHANISM itself (this commit
// has zero production-code changes -- see the file-header note above -- so
// the thing under test here is not H2's bug, it is the shim's own claimed
// guarantees: correct brace-depth extraction of `meta`, loud failure on a
// shape-changed production file, and a loud ReferenceError -- never a silent
// pass -- when the script references a host identifier the shim didn't bind.
// Each RED case reproduces a REAL prior failure mode (the rejected naive-
// regex approach, or a mutated/drifted source file) rather than a synthetic
// fixture that only exercises the already-working path.
// =============================================================================

test('RED: a naive non-greedy regex (the approach this file deliberately did NOT take) mis-locates the end of meta on the real production file, proving brace-depth counting was necessary, not cosmetic', () => {
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  // This is the exact naive alternative the header comment (lines 74-78) and
  // stripLeadingMetaExport()'s own docstring warn against: a non-greedy
  // match up to the FIRST top-level-looking `}` following `export const
  // meta = {`. The real meta block's `phases` array contains multiple
  // nested `{ title: ..., detail: ... }` objects, so this naive pattern
  // closes on the first nested object's own closing brace, not the true end
  // of the meta literal.
  const naiveMatch = source.match(/^export\s+const\s+meta\s*=\s*(\{[\s\S]*?\})/)
  assert.ok(naiveMatch, 'naive regex should still find *a* match on the real file')
  // Prove the naive match is WRONG: it must NOT parse as a complete, valid
  // meta object (it truncates mid-literal-ideally a SyntaxError, or at best
  // parses into a fragment lacking `phases`).
  let naiveParsedOk = false
  let naiveHasAllThreePhases = false
  try {
    // eslint-disable-next-line no-new-func
    const naiveValue = new Function(`return (${naiveMatch[1]})`)()
    naiveParsedOk = true
    naiveHasAllThreePhases = Array.isArray(naiveValue.phases) && naiveValue.phases.length === 3
  } catch (_e) {
    naiveParsedOk = false
  }
  assert.ok(
    !naiveParsedOk || !naiveHasAllThreePhases,
    'the naive non-greedy regex must NOT successfully reconstruct a complete 3-phase meta object -- ' +
    'if it does, the nested-brace hazard this harness is designed around no longer reproduces and this ' +
    'RED case needs re-deriving against the real file'
  )

  // GREEN: the real brace-depth-counting stripper gets the true, complete
  // object, all three phases intact -- the same real production file, same
  // real meta block, correct extraction.
  const { metaObjectSource } = stripLeadingMetaExport(source)
  const meta = parseMetaObject(metaObjectSource)
  assert.equal(meta.phases.length, 3)
  assert.deepEqual(meta.phases.map((p) => p.title), ['Triage', 'Verify', 'Screen'])
})

test('RED/GREEN: stripLeadingMetaExport() throws loudly (never silently mis-parses) when the source does not open with "export const meta = {"', () => {
  // RED: today, feeding a shape the stripper doesn't understand must not
  // silently produce a wrong-but-plausible split -- it must throw, naming
  // the real problem, per the plan's own drift-detection requirement.
  const mutatedSource = '"use strict";\n' + readFileSync(PRODUCTION_FILE, 'utf8')
  assert.throws(
    () => stripLeadingMetaExport(mutatedSource),
    /production file shape changed/,
    'a source not opening with the expected meta export must fail loudly, not silently mis-split'
  )

  // GREEN: the real, unmutated production file still strips cleanly.
  const realSource = readFileSync(PRODUCTION_FILE, 'utf8')
  assert.doesNotThrow(() => stripLeadingMetaExport(realSource))
})

test('RED/GREEN: loadIssueWheelTriageShim() throws loudly when the stripped body still contains a top-level export (second-export drift)', () => {
  // RED: simulate a future production-file edit that adds a second
  // top-level export after the meta block, and drive it through the REAL
  // public entry point (via the test-only sourceTextOverride escape hatch)
  // -- not a copy of the guard's condition. Today (this commit's own code),
  // that must be caught explicitly by the leftover-export guard rather than
  // surfacing later as an opaque SyntaxError from the AsyncFunction
  // constructor.
  const realSource = readFileSync(PRODUCTION_FILE, 'utf8')
  const driftedSource = realSource + '\nexport const somethingElse = 1\n'
  assert.throws(
    () => loadIssueWheelTriageShim(driftedSource),
    /stripped body still contains a top-level "export" statement/,
    'a source whose body has a leftover export must fail loudly via the explicit guard, not an opaque downstream SyntaxError'
  )

  // Sanity check that the RED case above is a genuine reproduction and not
  // vacuous: confirm that WITHOUT the explicit guard, this same drifted body
  // really would have hit the AsyncFunction constructor and thrown only an
  // opaque SyntaxError -- proving the guard is load-bearing, not redundant
  // with what the constructor would have reported anyway.
  const { body: driftedBody } = stripLeadingMetaExport(driftedSource)
  assert.throws(
    () => new AsyncFunction(...INJECTABLE_IDENTIFIERS, driftedBody),
    SyntaxError,
    'sanity: without the explicit guard, the AsyncFunction constructor itself only reports an opaque SyntaxError for this shape'
  )

  // GREEN: loading the REAL, undrifted production file through the actual
  // public entry point (default disk read, no override) never trips this
  // guard.
  assert.doesNotThrow(() => loadIssueWheelTriageShim())
})

test('RED/GREEN: a script body referencing a host identifier the shim did not bind fails loudly with ReferenceError naming it (the drift signal for INJECTABLE_IDENTIFIERS)', async () => {
  // RED: reproduces the exact drift scenario the plan's header comment
  // describes -- a future production-script edit starts referencing a new
  // host-supplied free identifier (e.g. `secrets`) that INJECTABLE_IDENTIFIERS
  // does not yet know about. Drive this through the REAL public entry point
  // (loadIssueWheelTriageShim + sourceTextOverride, then run()) against the
  // real production file's meta block with a drifted trailing body appended
  // -- proving the actual shim construction/invocation path throws
  // ReferenceError naming the missing identifier, not a hand-built stand-in.
  const realSource = readFileSync(PRODUCTION_FILE, 'utf8')
  const { metaObjectSource } = stripLeadingMetaExport(realSource)
  const driftedSource = `export const meta = ${metaObjectSource}\nreturn { sawSecrets: secrets }\n`
  const { run: driftedRun } = loadIssueWheelTriageShim(driftedSource)
  await assert.rejects(
    () => driftedRun({ args: minimalArgs() }),
    (err) => err instanceof ReferenceError && /secrets/.test(err.message),
    'referencing an unbound host identifier must fail with a ReferenceError naming it, never resolve silently'
  )

  // GREEN: the REAL production file, with the REAL current
  // INJECTABLE_IDENTIFIERS list (agent, args, log, parallel, phase), has no
  // such drift today -- it runs end-to-end with zero ReferenceError.
  const { run } = loadIssueWheelTriageShim()
  await assert.doesNotReject(() => run({ args: minimalArgs({ issues: [] }) }))
})

// =============================================================================
// Falsifiable RED/GREEN pairs for commit #3 of the commit sequence: "Surface
// Triage/Verify batch failures matching Screen's existing contract" (plan H2
// "Design -- the failure-surfacing half"). Each RED case runs the REAL,
// unmodified PRIOR commit's source (git commit 64f9ebc, the parent of this
// commit's own working-tree changes -- fetched live via `git show`, never a
// hand-typed synthetic fixture) through the SAME shim/assertions used against
// the current on-disk (post-fix) source, proving the fix actually changed
// observable behavior rather than merely adding dead code.
//
// Batch sizes are load-bearing for these fixtures: TRIAGE_BATCH_SIZE=5,
// VERIFY_BATCH_SIZE=4 (issue-wheel-triage.js, confirmed by direct read). The
// plan's own RED scenario is "3 of 4 batches 429". 4 Triage batches therefore
// needs 16-20 seed issues (5/batch, last batch may be partial); 4 Verify
// batches needs 13-16 close-class items (4/batch) surviving Triage.
// =============================================================================

/**
 * Returns the exact source text of issue-wheel-triage.js as committed at
 * PRE_FIX_REV -- the real parent commit, i.e. the file's shape BEFORE this
 * commit's own working-tree fix (the `.then((r) => (r && Array.isArray(r.items))
 * ? r.items : [])` swallow-to-empty-array shape, with no `totals.triage_batches`
 * key anywhere in its `totals` object -- both confirmed by direct `git show`
 * during test authoring). Using the real git history (rather than a hand-typed
 * "what it used to look like" string) means this RED fixture cannot silently
 * drift from what the bug actually was.
 */
// HISTORY-COUPLED FIXTURES (read this before touching the RED cases below).
// The RED cases run the file as it was at two earlier commits, fetched with
// `git show <rev>:...`. Those commits exist only in the runtime's own git
// history. A checkout without them -- a public clone, or a `git archive`
// extraction with no .git directory at all -- cannot supply them, and before
// this guard the very first `git show` threw at module load, which failed the
// WHOLE file (0 tests ran) instead of just those comparisons. Now an absent
// revision skips ONLY the cases that need it, with the reason printed here and
// attached to each skipped case; every other test, including each GREEN twin
// that runs the committed on-disk file, still runs.
//
// "Absent" means exactly two things, told apart by git's own message: there is
// no repository at all ("not a git repository"), or the repository does not have
// the object ("invalid object name"). Any other failure -- git missing, a
// corrupt repository, the revision present but the file gone from it -- is not
// "history is unavailable", it is a broken fixture or environment, and it throws
// with git's stderr rather than quietly skipping coverage.
export function classifyGitShowFailure(stderr) {
  const text = String(stderr || '')
  if (/not a git repository/i.test(text)) return 'absent'
  if (/invalid object name/i.test(text)) return 'absent'
  return 'error'
}

function readHistoricalSource(rev) {
  try {
    return execFileSync('git', ['show', `${rev}:workflows/issue-wheel-triage.js`], {
      cwd: path.join(__dirname, '..', '..'),
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
  } catch (err) {
    const stderr = err && err.stderr ? String(err.stderr) : ''
    if (classifyGitShowFailure(stderr) === 'absent') return null
    throw new Error(
      `test_issue_wheel_triage.mjs: reading ${rev}:workflows/issue-wheel-triage.js from git failed for a reason ` +
      `other than the history being absent, so the RED cases cannot be trusted either way.\n` +
      `  error: ${err && err.message ? String(err.message).split('\n')[0] : err}\n  git stderr: ${stderr.trim() || '(none)'}`
    )
  }
}

// Returns false when the revision is available (run the case), else the skip
// reason, and prints it once.
function historySkipReason(rev, source) {
  if (source !== null) return false
  const reason = `history object ${rev} is not available in this checkout (it exists only in the runtime's own git history)`
  console.warn(`test_issue_wheel_triage.mjs: SKIPPING the cases that compare against ${rev}: ${reason}`)
  return reason
}

// Fails loudly rather than letting an absent revision fall through to the
// on-disk source (loadIssueWheelTriageShim treats a non-string as "no override"),
// which would turn a RED case into a second GREEN one.
function requireHistorical(rev, source) {
  if (source === null) {
    throw new Error(`test_issue_wheel_triage.mjs: history object ${rev} is unavailable but a case that needs it was run`)
  }
  return source
}

const PRE_FIX_REV = '64f9ebc'
const PRE_FIX_SOURCE = readHistoricalSource(PRE_FIX_REV)
const PRE_FIX_SKIP = historySkipReason(PRE_FIX_REV, PRE_FIX_SOURCE)
function readPreFixSource() {
  return requireHistorical(PRE_FIX_REV, PRE_FIX_SOURCE)
}

// Sanity-checked once at module load, not inside a test body: confirms the
// fixture commit really is the swallow-to-[] shape this suite's RED cases
// depend on, and really has no triage_batches key -- so a future rebase/
// history rewrite that changes what 64f9ebc contains fails LOUDLY here with a
// clear message, rather than these RED tests silently passing for the wrong
// reason (a shim construction error, an unrelated throw) if the fixture ever
// stops matching the bug it claims to reproduce. Runs only when the revision
// is present; an absent revision is reported above, not checked.
if (PRE_FIX_SOURCE !== null) {
  const preFixSource = PRE_FIX_SOURCE
  if (!/\.then\(\(r\) => \(r && Array\.isArray\(r\.items\)\) \? r\.items : \[\]\)/.test(preFixSource)) {
    throw new Error(
      `test_issue_wheel_triage.mjs: PRE_FIX_REV (${PRE_FIX_REV}) no longer contains the expected ` +
      'swallow-to-empty-array shape this RED fixture is built around -- the commit fixture needs updating.'
    )
  }
  if (/triage_batches/.test(preFixSource)) {
    throw new Error(
      `test_issue_wheel_triage.mjs: PRE_FIX_REV (${PRE_FIX_REV}) unexpectedly already contains ` +
      '"triage_batches" -- it should predate this commit\'s fix entirely. The commit fixture needs updating.'
    )
  }
}

// GH #4767 WS14-S1 item 1d, Finding 8 (code review round 2): the RETRY
// mechanism's own RED fixture must pin the commit that predates the RETRY
// work specifically, not PRE_FIX_REV above -- 64f9ebc predates the
// batch-loss-SURFACING fix entirely (no `triage_batches` key at all), which
// is a DIFFERENT, earlier bug than the one 1d fixes. a3d9e0a is the real
// parent of 1d's own working-tree changes: it HAS `triage_batches` (the
// batch-loss-surfacing fix already landed) but has no `runBatchesWithRetry`/
// `RETRY_WAVE_SIZE` at all -- confirmed by direct `git show` during test
// authoring, and by the sanity check below.
const RETRY_PRE_FIX_REV = 'a3d9e0a'
const RETRY_PRE_FIX_SOURCE = readHistoricalSource(RETRY_PRE_FIX_REV)
const RETRY_PRE_FIX_SKIP = historySkipReason(RETRY_PRE_FIX_REV, RETRY_PRE_FIX_SOURCE)
function readRetryPreFixSource() {
  return requireHistorical(RETRY_PRE_FIX_REV, RETRY_PRE_FIX_SOURCE)
}
if (RETRY_PRE_FIX_SOURCE !== null) {
  const retryPreFixSource = RETRY_PRE_FIX_SOURCE
  if (!/triage_batches/.test(retryPreFixSource)) {
    throw new Error(
      `test_issue_wheel_triage.mjs: RETRY_PRE_FIX_REV (${RETRY_PRE_FIX_REV}) unexpectedly has no ` +
      '"triage_batches" key -- it should postdate the batch-loss-surfacing fix. The commit fixture needs updating.'
    )
  }
  if (/runBatchesWithRetry|RETRY_WAVE_SIZE/.test(retryPreFixSource)) {
    throw new Error(
      `test_issue_wheel_triage.mjs: RETRY_PRE_FIX_REV (${RETRY_PRE_FIX_REV}) unexpectedly already ` +
      'contains the retry mechanism -- it should predate 1d\'s own fix entirely. The commit fixture needs updating.'
    )
  }
}

// Builds a stub agent() that returns a valid-shaped items array for every
// batch EXCEPT the batches at the given zero-based indices for the given
// label prefix, which return `null` (the exact "malformed/empty return"
// shape a rate-limited/429'd agent() call produces per the plan's own RED
// scenario). Batch index is derived from the numeric suffix of `opts.label`
// (e.g. "triage:3" -> index 2), matching this production script's own
// `label: \`${prefix}:${i + 1}\`` convention at every fan-out site.
function makeFailingBatchAgent({ labelPrefix, failIndices, itemForBatch }) {
  return async (_prompt, opts) => {
    if (!opts.label.startsWith(`${labelPrefix}:`)) {
      // Any other phase's call (e.g. Screen, once Triage/Verify feed it) gets
      // a permissive empty-but-valid response so it never becomes a spurious
      // additional failure this test isn't asserting about.
      return { items: [] }
    }
    // GH #4767 WS14-S1 item 1d: a retried call's label carries a ":retry"
    // suffix (e.g. "triage:1:retry") -- strip it before parsing the numeric
    // batch index, otherwise Number("1:retry") is NaN and this fixture would
    // wrongly "recover" every retried batch regardless of failIndices.
    const numericLabel = opts.label.endsWith(':retry') ? opts.label.slice(0, -':retry'.length) : opts.label
    const batchIndex = Number(numericLabel.slice(labelPrefix.length + 1)) - 1
    if (failIndices.includes(batchIndex)) {
      return null // the exact "malformed/empty return" shape a 429 produces
    }
    return { items: itemForBatch(batchIndex) }
  }
}

// 18 seed issues -> chunk(., 5) = 4 Triage batches of sizes [5,5,5,3]. Every
// issue gets a distinct number so dedupe never interferes with counting.
function make18SeedIssues() {
  return Array.from({ length: 18 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
}

test('RED (pre-fix, commit 64f9ebc): 3 of 4 Triage batches returning a malformed agent() response silently vanishes those issues, with totals reporting no failure', { skip: PRE_FIX_SKIP }, async () => {
  const preFixSource = readPreFixSource()
  const { run } = loadIssueWheelTriageShim(preFixSource)

  const stubAgent = makeFailingBatchAgent({
    labelPrefix: 'triage',
    failIndices: [0, 1, 2], // 3 of 4 batches fail; only batch index 3 (issues 16-18) succeeds
    itemForBatch: (batchIndex) => {
      const start = batchIndex * 5
      const size = batchIndex === 3 ? 3 : 5
      return Array.from({ length: size }, (_, k) => ({
        number: start + k + 1,
        verdict: 'unclear',
        rationale: `seen batch ${batchIndex}`,
      }))
    },
  })

  const result = await run({ args: minimalArgs({ issues: make18SeedIssues() }), agent: stubAgent })

  // Reproduces the bug exactly: only the 4th (surviving) batch's 3 items make
  // it through triagedFlat -- the other 15 are silently gone, and there is no
  // triage_batches key at all to say so (confirmed by the module-load sanity
  // check above that this fixture predates the field's existence).
  assert.equal(result.unclear.length, 3, 'pre-fix: only the one surviving batch\'s items should appear')
  assert.deepEqual(
    result.unclear.map((i) => i.number).sort((a, b) => a - b),
    [16, 17, 18]
  )
  assert.equal(result.totals.triaged_count, 3)
  assert.equal(
    result.totals.triage_batches,
    undefined,
    'pre-fix: totals must have no triage_batches key at all -- the loss is invisible, not merely zero'
  )
  // Exit clean: the script returns normally, no thrown error, nothing in the
  // return shape hints at the 15 lost issues.
  assert.ok(result.totals, 'the script must still return normally (a silent, non-crashing loss is the bug)')
})

test('GREEN (post-fix, on-disk source): the same 3-of-4-Triage-batches failure is now visible in totals.triage_batches', async () => {
  const { run } = loadIssueWheelTriageShim() // real on-disk source, i.e. this commit's own fix

  const stubAgent = makeFailingBatchAgent({
    labelPrefix: 'triage',
    failIndices: [0, 1, 2],
    itemForBatch: (batchIndex) => {
      const start = batchIndex * 5
      const size = batchIndex === 3 ? 3 : 5
      return Array.from({ length: size }, (_, k) => ({
        number: start + k + 1,
        verdict: 'unclear',
        rationale: `seen batch ${batchIndex}`,
      }))
    },
  })

  const result = await run({ args: minimalArgs({ issues: make18SeedIssues() }), agent: stubAgent })

  // Same lossy outcome for the surviving data (the fix does not change what
  // data comes through, only whether the loss is visible) --
  assert.equal(result.unclear.length, 3)
  // -- but now the loss is reported honestly:
  assert.ok(result.totals.triage_batches, 'post-fix: totals.triage_batches must exist')
  assert.equal(result.totals.triage_batches.total, 4, '4 Triage batches from 18 issues at batch size 5')
  assert.equal(result.totals.triage_batches.failed, 3)
  assert.equal(result.totals.triage_batches.ok, 1)
  // GH #4767 WS14-S1 item 1d: these 3 batches return null on BOTH the first
  // pass and the retry (makeFailingBatchAgent fails them unconditionally),
  // so they were retried (retried==3, recovered==0) and each carries the
  // dual first+retry reason (nit 10), joined by " | retry: " with the
  // trailing "(after retry)" marker.
  assert.equal(result.totals.triage_batches.retried, 3)
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(
    result.totals.triage_batches.reasons.filter((r) =>
      r === 'TRIAGE_ERROR: empty or malformed agent return | retry: TRIAGE_ERROR: empty or malformed agent return (after retry)'
    ).length,
    3
  )
})

// 16 close-class-eligible seed issues -> Triage returns all as 'already_done'
// with a valid cited_fix_sha (so none get defensively routed to unclear),
// giving Verify chunk(., 4) = 4 batches of 4.
function make16AlreadyDoneItems() {
  return Array.from({ length: 16 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
}

test('RED (pre-fix, commit 64f9ebc): 3 of 4 Verify batches returning a malformed agent() response is already partially safe (over-refutation) but invisible in totals', { skip: PRE_FIX_SKIP }, async () => {
  const preFixSource = readPreFixSource()
  const { run } = loadIssueWheelTriageShim(preFixSource)

  const seedIssues = make16AlreadyDoneItems()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      // One Triage batch (5/agent, 16 issues -> 4 batches); return a valid
      // already_done verdict (close-class) for every issue in this call's batch.
      return {
        items: opts && Array.isArray(seedIssues)
          ? seedIssues
              .filter((_, idx) => Math.floor(idx / 5) === Number(opts.label.slice(7)) - 1)
              .map((s) => ({ number: s.number, verdict: 'already_done', cited_fix_sha: 'abc1234', rationale: 'r' }))
          : [],
      }
    }
    if (opts.label.startsWith('verify:')) {
      const batchIndex = Number(opts.label.slice(7)) - 1
      if (batchIndex <= 2) return null // 3 of 4 Verify batches fail
      // Batch 3 (the one surviving batch) genuinely CONFIRMS its 4 items
      // (refuted=false), so this fixture cleanly separates "lost to a failed
      // batch" (12 items, the thing under test) from "verified normally" (4
      // items) -- rather than leaving batch 3 ALSO unconfirmed, which would
      // conflate the two and make the 12-vs-16 count ambiguous.
      const batchStart = batchIndex * 4
      const batchItems = seedIssues.slice(batchStart, batchStart + 4)
      return {
        items: batchItems.map((s) => ({ number: s.number, refuted: false, evidence_checked: 're-derived and confirmed' })),
      }
    }
    return { items: [] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.close_class_count, 16, 'all 16 should be close-class (already_done)')
  // Pre-fix: no triage_batches key exists to report the Verify loss either.
  assert.equal(result.totals.triage_batches, undefined)
  // The already-partially-safe behavior: items whose batch failed get no
  // verifyByNumber entry, and fall into `refuted` with 'no verifier verdict
  // returned' -- never a silent close. This is unchanged by the fix (the plan
  // explicitly says don't touch this downstream fallback), asserted here to
  // establish the pre-fix baseline this exact number is compared against below.
  const refutedForFailedBatches = result.refuted.filter((r) => r.reason === 'no verifier verdict returned')
  assert.equal(refutedForFailedBatches.length, 12, '3 failed batches x 4 items/batch = 12 conservatively refuted')
  // The 4th (surviving) batch's items were genuinely confirmed, not lost:
  assert.equal(result.totals.verified_close_class_count, 4)
})

test('GREEN (post-fix, on-disk source): the same 3-of-4-Verify-batches failure is now visible in totals.triage_batches, with the conservative refuted-fallback unchanged', async () => {
  const { run } = loadIssueWheelTriageShim()

  // GH #4767 WS14-S1 item 1d: strips a possible ":retry" label suffix before
  // parsing the numeric batch index -- otherwise Number("1:retry") is NaN
  // and every retried batch would wrongly "succeed" regardless of intent.
  const stripRetrySuffix = (label) => (label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label)

  const seedIssues = make16AlreadyDoneItems()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: seedIssues
          .filter((_, idx) => Math.floor(idx / 5) === Number(stripRetrySuffix(opts.label).slice(7)) - 1)
          .map((s) => ({ number: s.number, verdict: 'already_done', cited_fix_sha: 'abc1234', rationale: 'r' })),
      }
    }
    if (opts.label.startsWith('verify:')) {
      const batchIndex = Number(stripRetrySuffix(opts.label).slice(7)) - 1
      if (batchIndex <= 2) return null // fails BOTH the first pass and the retry, unconditionally
      const batchStart = batchIndex * 4
      const batchItems = seedIssues.slice(batchStart, batchStart + 4)
      return {
        items: batchItems.map((s) => ({ number: s.number, refuted: false, evidence_checked: 're-derived and confirmed' })),
      }
    }
    return { items: [] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.close_class_count, 16)
  // Unchanged conservative behavior (proves the fix did not touch the
  // downstream fallback, per the plan's explicit instruction):
  const refutedForFailedBatches = result.refuted.filter((r) => r.reason === 'no verifier verdict returned')
  assert.equal(refutedForFailedBatches.length, 12)
  assert.equal(result.totals.verified_close_class_count, 4)
  // Now visible in totals:
  assert.ok(result.totals.triage_batches)
  assert.equal(result.totals.triage_batches.failed, 3)
  assert.equal(result.totals.triage_batches.retried, 3, 'all 3 failing Verify batches were retried')
  assert.equal(result.totals.triage_batches.recovered, 0, 'null on both attempts -- none recovered')
  assert.equal(
    result.totals.triage_batches.reasons.filter((r) =>
      r === 'VERIFY_ERROR: empty or malformed agent return | retry: VERIFY_ERROR: empty or malformed agent return (after retry)'
    ).length,
    3
  )
})

test('Screen regression guard: needsWorkScreenFailed behavior and per-item attribution are byte-identical pre-fix vs. post-fix (Screen site untouched)', { skip: PRE_FIX_SKIP }, async () => {
  const preFixSource = readPreFixSource()
  const { run: preFixRun } = loadIssueWheelTriageShim(preFixSource)
  const { run: postFixRun } = loadIssueWheelTriageShim()

  // One needs_work item reaching Screen; Screen's own agent() call returns an
  // empty items array -- Screen's pre-existing, already-correct contract
  // treats that as SCREEN_ERROR for every item in the batch. Identical
  // fixture run through both source versions.
  const buildStubAgent = () => async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [
          {
            number: 99,
            verdict: 'needs_work',
            rationale: 'cites shared/ai/model_registry.py',
            files_touched: ['shared/ai/model_registry.py'],
            size_points: 2,
          },
        ],
      }
    }
    if (opts.label.startsWith('screen:')) {
      return { items: [] }
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }

  const args = minimalArgs({ issues: [{ number: 99, title: 'ninety-nine', labels: [] }] })
  const preFixResult = await preFixRun({ args, agent: buildStubAgent() })
  const postFixResult = await postFixRun({ args, agent: buildStubAgent() })

  assert.deepEqual(
    preFixResult.needs_work_screen_failed,
    postFixResult.needs_work_screen_failed,
    'Screen\'s own needs_work_screen_failed output must be byte-identical pre- and post-fix -- proves the Screen site was not touched'
  )
  assert.equal(postFixResult.needs_work_screen_failed.length, 1)
  assert.equal(postFixResult.needs_work_screen_failed[0].number, 99)
  assert.equal(postFixResult.needs_work_screen_failed[0].fail_reason, 'SCREEN_ERROR: empty agent return')
  assert.deepEqual(preFixResult.needs_work, [])
  assert.deepEqual(postFixResult.needs_work, [])

  // The fix's own aggregation (post-fix only, pre-fix has no totals.triage_batches
  // key at all) must fold Screen's pre-existing failure into the combined
  // count too, without altering how Screen computed needs_work_screen_failed:
  assert.equal(preFixResult.totals.triage_batches, undefined)
  assert.ok(postFixResult.totals.triage_batches)
  assert.equal(postFixResult.totals.triage_batches.failed, 1, 'the one failed Screen batch must count toward the combined total')
  assert.ok(
    postFixResult.totals.triage_batches.reasons.includes('SCREEN_ERROR: empty agent return'),
    'Screen\'s failure reason must appear in the combined reasons list'
  )
})

test('Blocker 1 regression: reasons.length equals failed for MULTIPLE failed Screen batches, one {phase, batch_index, reason} entry per batch (not collapsed to one)', async () => {
  const { run } = loadIssueWheelTriageShim()

  // SCREEN_BATCH_SIZE is 20 (confirmed by direct read of the production
  // file); 21 needs_work items reaching Screen therefore chunk into 2 Screen
  // batches ([20, 1]). Both Screen batches return an empty items array --
  // Screen's own pre-existing contract treats each as a failure. A prior
  // version of the aggregation collapsed every failed Screen batch into a
  // SINGLE reasons-array entry regardless of how many batches failed, which
  // desynced reasons.length (1) from failed (2) -- this fixture reproduces
  // exactly that desync and proves the fix keeps them equal.
  const seedIssues = Array.from({ length: 21 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      // TRIAGE_BATCH_SIZE is 5 -> 21 issues chunk into 5 Triage batches;
      // return a needs_work verdict (with the required files_touched/
      // size_points) for every issue in this call's own batch.
      const batchIndex = Number(opts.label.slice(7)) - 1
      const start = batchIndex * 5
      const size = Math.min(5, 21 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1,
          verdict: 'needs_work',
          rationale: 'cites shared/ai/model_registry.py',
          files_touched: ['shared/ai/model_registry.py'],
          size_points: 1,
        })),
      }
    }
    if (opts.label.startsWith('screen:')) {
      return { items: [] } // both Screen batches fail
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.needs_work_count, 21, 'all 21 items must have reached Screen as needs_work')
  assert.equal(result.needs_work_screen_failed.length, 21, 'every item across both failed Screen batches must be screen-failed')

  // The actual Blocker 1 assertion: exactly 2 failed Screen batches, and
  // reasons.length must equal that count -- not 1, which is what the
  // collapsed-to-a-single-entry bug produced regardless of failed batch count.
  // totals.triage_batches.total combines ALL three phases: 5 Triage batches
  // (21 issues / TRIAGE_BATCH_SIZE=5) + 0 Verify batches (needs_work is not
  // close-class, so Verify never runs) + 2 Screen batches (21 items /
  // SCREEN_BATCH_SIZE=20) = 7.
  assert.ok(result.totals.triage_batches, 'totals.triage_batches must exist')
  assert.equal(result.totals.triage_batches.total, 7, '5 Triage + 0 Verify + 2 Screen batches combined')
  assert.equal(result.totals.triage_batches.failed, 2, 'both Screen batches failed; all 5 Triage batches succeeded')
  assert.equal(result.totals.triage_batches.ok, 5)
  const screenReasons = result.totals.triage_batches.reasons.filter((r) => r === 'SCREEN_ERROR: empty agent return')
  assert.equal(
    screenReasons.length,
    result.totals.triage_batches.failed,
    'reasons.length must equal failed -- one SCREEN_ERROR reason per failed Screen batch, never collapsed to a single entry'
  )
  assert.equal(screenReasons.length, 2)
})

test('Nit 3 regression: a REJECTED (thrown) Triage agent() call is captured as a failed batch, not an uncaught rejection that crashes the run', async () => {
  const { run } = loadIssueWheelTriageShim()

  // 6 seed issues -> chunk(., 5) = 2 Triage batches ([5, 1]). Batch 1 throws
  // (simulating a rejected agent() promise, distinct from the null/malformed
  // "429" shape the other Blocker-3 fixtures use); batch 2 succeeds normally.
  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const stubAgent = async (_prompt, opts) => {
    if (opts.label === 'triage:1') {
      throw new Error('simulated rejected agent() call')
    }
    if (opts.label.startsWith('triage:')) {
      return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
    }
    return { items: [] }
  }

  // Must not reject/throw -- the .catch() site is what proves this.
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.total, 2)
  assert.equal(result.totals.triage_batches.failed, 1, 'the rejected batch must be captured as a failure, not silently lost or thrown')
  assert.equal(result.totals.triage_batches.ok, 1)
  // GH #4767 WS14-S1 item 1d, design change (code review round 2): a THROWN
  // call is never retried (only a null/malformed-with-no-thrown-error result
  // is retry-eligible) -- so retried/recovered stay 0 and the reason carries
  // NO "(after retry)" suffix, since there was no retry.
  assert.equal(result.totals.triage_batches.retried, 0, 'a thrown call is not retry-eligible')
  assert.equal(result.totals.triage_batches.recovered, 0)
  // A genuine rejection carries its own diagnostic message, not the generic
  // empty-or-malformed string -- distinguishing a 429/thrown error from a
  // merely null/malformed return is the point of this fixture.
  assert.equal(
    result.totals.triage_batches.reasons.filter((r) => r === 'TRIAGE_ERROR: agent call rejected: simulated rejected agent() call').length,
    1
  )
  // The surviving batch's item still comes through normally.
  assert.equal(result.unclear.length, 1)
  assert.equal(result.unclear[0].number, 6)
})

test('Nit 3 regression: a REJECTED (thrown) Verify agent() call is captured as a failed batch, not an uncaught rejection that crashes the run', async () => {
  const { run } = loadIssueWheelTriageShim()

  // 8 already_done seed issues -> Triage returns all 8 as close-class;
  // chunk(., 4) = 2 Verify batches. Batch 1 throws; batch 2 confirms normally.
  const seedIssues = Array.from({ length: 8 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      const batchIndex = Number(opts.label.slice(7)) - 1
      const start = batchIndex * 5
      const size = Math.min(5, 8 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1,
          verdict: 'already_done',
          cited_fix_sha: 'abc1234',
          rationale: 'r',
        })),
      }
    }
    if (opts.label === 'verify:1') {
      throw new Error('simulated rejected agent() call')
    }
    if (opts.label.startsWith('verify:')) {
      const batchIndex = Number(opts.label.slice(7)) - 1
      const start = batchIndex * 4
      const size = Math.min(4, 8 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1,
          refuted: false,
          evidence_checked: 're-derived and confirmed',
        })),
      }
    }
    return { items: [] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.close_class_count, 8)
  assert.equal(result.totals.triage_batches.failed, 1, 'the rejected Verify batch must be captured as a failure, not thrown')
  // GH #4767 WS14-S1 item 1d, design change: a thrown call is never retried.
  assert.equal(result.totals.triage_batches.retried, 0, 'a thrown call is not retry-eligible')
  assert.equal(result.totals.triage_batches.recovered, 0)
  // A genuine rejection carries its own diagnostic message, not the generic
  // empty-or-malformed string.
  assert.equal(
    result.totals.triage_batches.reasons.filter((r) => r === 'VERIFY_ERROR: agent call rejected: simulated rejected agent() call').length,
    1
  )
  // The failed batch's 4 items fall into the existing conservative refuted
  // fallback (unchanged downstream behavior), the surviving batch's 4 items
  // are genuinely confirmed.
  const refutedForFailedBatch = result.refuted.filter((r) => r.reason === 'no verifier verdict returned')
  assert.equal(refutedForFailedBatch.length, 4)
  assert.equal(result.totals.verified_close_class_count, 4)
})

test('sanity: totals.triage_batches.ok + failed always equals total, across all three phases combined (post-fix, happy path)', async () => {
  const { run } = loadIssueWheelTriageShim()
  const result = await run({ args: minimalArgs({ issues: [] }) })
  assert.ok(result.totals.triage_batches)
  assert.equal(result.totals.triage_batches.total, 0)
  assert.equal(result.totals.triage_batches.ok, 0)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.deepEqual(result.totals.triage_batches.reasons, [])
})

// =============================================================================
// GH #4767 (WS14-S1 item 1d): bounded one-retry-in-waves-of-4 for Triage,
// Verify and Screen. Each RED case below runs the pinned pre-fix revision
// (RETRY_PRE_FIX_REV, no retry mechanism at all -- `runBatchesWithRetry`
// does not exist in that source) to prove the fixture genuinely exercises
// new behavior, then the on-disk (post-fix) source for the matching GREEN.
// =============================================================================


test('RED (pre-fix, commit a3d9e0a): a batch failing once and succeeding on a would-be retry has NO retry mechanism, so it stays failed and lost', { skip: RETRY_PRE_FIX_SKIP }, async () => {
  const retryPreFixSource = readRetryPreFixSource()
  const { run } = loadIssueWheelTriageShim(retryPreFixSource)

  // 6 seed issues -> chunk(., 5) = 2 Triage batches. Batch 1 (issues 1-5)
  // fails every call (a3d9e0a has no retry loop to call it a second time);
  // batch 2 succeeds normally.
  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const stubAgent = async (_prompt, opts) => {
    if (opts.label === 'triage:1') return null
    if (opts.label.startsWith('triage:')) {
      return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
    }
    return { items: [] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  // a3d9e0a already HAS totals.triage_batches (the batch-loss-surfacing fix
  // from the prior round is already in), but with no retry: issues 1-5 are
  // permanently lost, `failed` is 1, and there is no `retried`/`recovered`
  // key at all -- that pair is what 1d's own fix adds.
  assert.equal(result.unclear.length, 1)
  assert.equal(result.unclear[0].number, 6)
  assert.ok(result.totals.triage_batches, 'a3d9e0a already has the triage_batches key from the prior fix')
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.equal(result.totals.triage_batches.retried, undefined, 'a3d9e0a has no retried key -- no retry mechanism exists yet')
  assert.equal(result.totals.triage_batches.recovered, undefined)
})

test('GREEN (a): a Triage batch that fails on the first pass and succeeds on retry is recovered -- ok == total, failed == 0, retried == recovered == N; issue numbers 1-12 each appear exactly once', async () => {
  const { run } = loadIssueWheelTriageShim()

  // 12 seed issues -> chunk(., 5) = 3 Triage batches ([5,5,2]), indices
  // [0,1,2]. Per code review Blocker 1 follow-up: fail batches NOT at the
  // front (indices 1 and 2 of 0..2) -- this is what actually exercises a
  // `results[w]`-vs-`results[idx]` off-by-slip in the retry-wave write-back
  // (a bug that fails batch 0 exclusively would never notice a swapped
  // index, since 0 is both the array position and the batch index in that
  // case). Track per-label call counts to distinguish "first attempt" from
  // "retry attempt" without any host timing API.
  const seedIssues = Array.from({ length: 12 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  // GH #4767 WS14-S1 item 1d: strips a possible ":retry" label suffix before
  // parsing the numeric batch index.
  const parseBatchIndex = (label) => {
    const numeric = label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label
    return Number(numeric.slice('triage:'.length)) - 1
  }
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    callCounts.set(label, (callCounts.get(label) || 0) + 1)
    const isRetryCall = label.endsWith(':retry')
    const batchIndex = parseBatchIndex(label)
    const start = batchIndex * 5
    const size = Math.min(5, 12 - start)
    const items = () => Array.from({ length: size }, (_, k) => ({
      number: start + k + 1,
      verdict: 'unclear',
      rationale: `batch ${batchIndex} ${isRetryCall ? 'retry' : 'first'}`,
    }))
    if ((batchIndex === 1 || batchIndex === 2) && !isRetryCall) {
      return null // fail the first attempt only -- NOT the front batch (index 0)
    }
    return { items: items() }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.unclear.length, 12, 'all 12 issues must be recovered across the retry')
  // Every issue number 1-12 must appear EXACTLY once -- a `results[w]` vs
  // `results[idx]` write-back slip would either duplicate one batch's items
  // (overwriting the wrong slot) or lose another's (never getting its
  // recovered items written to the right slot).
  const sortedNumbers = result.unclear.map((i) => i.number).sort((a, b) => a - b)
  assert.deepEqual(sortedNumbers, Array.from({ length: 12 }, (_, i) => i + 1))
  const numberCounts = new Map()
  for (const n of sortedNumbers) numberCounts.set(n, (numberCounts.get(n) || 0) + 1)
  for (const [n, count] of numberCounts) assert.equal(count, 1, `issue ${n} must appear exactly once, got ${count}`)

  assert.equal(result.totals.triage_batches.total, 3)
  assert.equal(result.totals.triage_batches.ok, 3, 'ok == total once every batch is recovered')
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(result.totals.triage_batches.retried, 2, 'exactly the 2 batches that failed the first pass were retried')
  assert.equal(result.totals.triage_batches.recovered, 2, 'both retried batches succeeded on retry')
  // Each recovered batch's agent() was called exactly twice (first pass +
  // one retry, distinguished by the ":retry" label suffix -- nit 11), never
  // a third time.
  assert.equal(callCounts.get('triage:2'), 1, 'batch index 1 (label triage:2) fails first pass once')
  assert.equal(callCounts.get('triage:2:retry'), 1, 'batch index 1 is retried exactly once, under the :retry label')
  assert.equal(callCounts.get('triage:3'), 1, 'batch index 2 (label triage:3) fails first pass once')
  assert.equal(callCounts.get('triage:3:retry'), 1, 'batch index 2 is retried exactly once, under the :retry label')
  assert.equal(callCounts.get('triage:1'), 1, 'a batch that never failed is called exactly once, no retry')
  assert.equal(callCounts.get('triage:1:retry'), undefined, 'a batch that never failed has no :retry call at all')
})

test('(b) a batch that fails BOTH the first pass and the retry stays failed, with a dual first+retry reason and "(after retry)" appended', async () => {
  const { run } = loadIssueWheelTriageShim()

  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    const n = (callCounts.get(label) || 0) + 1
    callCounts.set(label, n)
    if (label === 'triage:1' || label === 'triage:1:retry') return null // fails every attempt, including the retry
    return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.total, 2)
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 0)
  // Nit 10: both the first-pass reason and the retry's own reason are kept,
  // joined by " | retry: ", with "(after retry)" appended once at the end.
  assert.deepEqual(
    result.totals.triage_batches.reasons,
    ['TRIAGE_ERROR: empty or malformed agent return | retry: TRIAGE_ERROR: empty or malformed agent return (after retry)']
  )
  // Called exactly twice: first pass ("triage:1") + one retry
  // ("triage:1:retry"), never a third time -- the retry is bounded to ONE
  // attempt, never a loop.
  assert.equal(callCounts.get('triage:1'), 1)
  assert.equal(callCounts.get('triage:1:retry'), 1)
  assert.equal(result.unclear.length, 1)
  assert.equal(result.unclear[0].number, 6)
})

// =============================================================================
// Blocker 1 (code review round 2): the ORIGINAL test (c) tracked in-flight
// count across BOTH the first pass and every retry wave combined, which a
// mutant that launches every retry wave at once
// (`Promise.all(waves.map(w => parallel(...)))`, i.e. no wave-bounding at
// all) still PASSED -- the unbounded first pass alone already drives
// maxInFlight well past 4, so the assertion never actually distinguished a
// wave-bounded retry from an unbounded one. Replaced with the reviewer's own
// fixture: track in-flight ONLY during calls made AFTER the very first
// parallel() invocation (the first pass), which is exactly the retry pass.
// =============================================================================

test('(c) retry waves never exceed RETRY_WAVE_SIZE (4) concurrent agent() calls -- RED on concurrent-waves and single-wave mutants, GREEN on the real file', async () => {
  const { run } = loadIssueWheelTriageShim()

  // 60 seed issues -> chunk(., 5) = 12 Triage batches, ALL of which fail on
  // their first attempt and succeed on retry -- so the retry pass must
  // re-run all 12 failed batches across multiple waves.
  const seedIssues = Array.from({ length: 60 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))

  let callIndex = 0
  let inFlight = 0
  let maxRetryInFlight = 0
  const trackingParallel = async (thunks) => {
    const isFirstPass = callIndex++ === 0
    return Promise.all(thunks.map(async (t) => {
      inFlight++
      if (!isFirstPass) maxRetryInFlight = Math.max(maxRetryInFlight, inFlight)
      try { return await t() } finally { inFlight-- }
    }))
  }

  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    const n = (callCounts.get(label) || 0) + 1
    callCounts.set(label, n)
    const numeric = label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label
    const batchIndex = Number(numeric.slice('triage:'.length)) - 1
    const start = batchIndex * 5
    const size = Math.min(5, 60 - start)
    if (!label.endsWith(':retry')) return null // every batch fails its first attempt
    return {
      items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, verdict: 'unclear', rationale: 'r' })),
    }
  }

  const result = await run({
    args: minimalArgs({ issues: seedIssues }),
    agent: stubAgent,
    parallel: trackingParallel,
  })

  assert.equal(result.totals.triage_batches.total, 12)
  assert.equal(result.totals.triage_batches.retried, 12, 'all 12 batches failed the first pass and were retried')
  assert.equal(result.totals.triage_batches.recovered, 12)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.ok(maxRetryInFlight <= 4, `retry-pass in-flight count must never exceed 4, got ${maxRetryInFlight}`)
  assert.ok(maxRetryInFlight >= 1, 'sanity: at least one retry call must have actually run')
})

test('(c) MUTANT sanity -- concurrent-waves mutant (launches every retry wave at once) must go RED', async () => {
  // Reproduces the exact mutant the code review measured passing the
  // original test (c): instead of a sequential `for (const wave of waves)`
  // loop (one `parallel()` call per wave, awaited before the next), this
  // mutant fires ALL waves' parallel() calls at once via
  // `Promise.all(waves.map((wave) => parallel(...)))` -- so every retry
  // batch is in flight simultaneously, never bounded to 4.
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  const original = `  if (retryEligible.length) {
    const waves = chunk(retryEligible, RETRY_WAVE_SIZE)
    for (const wave of waves) {
      const retryOutcomes = await parallel(wave.map((idx) => () => dispatchOne(batches[idx], idx, true)))
      for (let w = 0; w < wave.length; w++) {
        const idx = wave[w]
        const firstPass = results[idx]
        const retryOutcome = retryOutcomes[w]
        // Nit 10: a batch failing both attempts keeps BOTH settlements --
        // the retry's own {batch, result, error} plus the first pass's,
        // under firstResult/firstError, so a phase can build a reason
        // string citing both without this helper knowing each phase's own
        // reason-string format.
        results[idx] = { ...retryOutcome, firstResult: firstPass.result, firstError: firstPass.error }
        if (succeeds(retryOutcome.result)) recovered++
      }
    }
  }`
  const mutated = `  if (retryEligible.length) {
    const waves = chunk(retryEligible, RETRY_WAVE_SIZE)
    const allWaveOutcomes = await Promise.all(waves.map((wave) =>
      parallel(wave.map((idx) => () => dispatchOne(batches[idx], idx, true)))
    ))
    for (let wIdx = 0; wIdx < waves.length; wIdx++) {
      const wave = waves[wIdx]
      const retryOutcomes = allWaveOutcomes[wIdx]
      for (let w = 0; w < wave.length; w++) {
        const idx = wave[w]
        const firstPass = results[idx]
        const retryOutcome = retryOutcomes[w]
        results[idx] = { ...retryOutcome, firstResult: firstPass.result, firstError: firstPass.error }
        if (succeeds(retryOutcome.result)) recovered++
      }
    }
  }`
  assert.ok(source.includes(original), 'the real runBatchesWithRetry retry-wave loop text has drifted -- update this mutant fixture')
  const mutatedSource = source.replace(original, mutated)
  assert.notEqual(mutatedSource, source, 'mutation must actually change the source')
  const { run } = loadIssueWheelTriageShim(mutatedSource)

  const seedIssues = Array.from({ length: 60 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  let callIndex = 0
  let inFlight = 0
  let maxRetryInFlight = 0
  const trackingParallel = async (thunks) => {
    const isFirstPass = callIndex++ === 0
    return Promise.all(thunks.map(async (t) => {
      inFlight++
      if (!isFirstPass) maxRetryInFlight = Math.max(maxRetryInFlight, inFlight)
      try { return await t() } finally { inFlight-- }
    }))
  }
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    const numeric = label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label
    const batchIndex = Number(numeric.slice('triage:'.length)) - 1
    const start = batchIndex * 5
    const size = Math.min(5, 60 - start)
    if (!label.endsWith(':retry')) return null
    return {
      items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, verdict: 'unclear', rationale: 'r' })),
    }
  }

  await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent, parallel: trackingParallel })

  // RED: the concurrent-waves mutant lets all 12 retry batches run at once.
  assert.equal(maxRetryInFlight, 12, 'concurrent-waves mutant must show all 12 retry batches in flight at once')
  assert.ok(maxRetryInFlight > 4, 'sanity: the mutant must actually violate the wave-size-4 bound')
})

test('(c) MUTANT sanity -- single-wave mutant (RETRY_WAVE_SIZE effectively unbounded) must go RED', async () => {
  // A second mutant shape: RETRY_WAVE_SIZE itself widened to cover every
  // failed batch in one wave (chunk(retryEligible, retryEligible.length) in
  // effect) -- structurally different from the concurrent-waves mutant
  // above (this one keeps the sequential-loop SHAPE but removes the bound),
  // yet must be caught by the same assertion.
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  const original = 'const RETRY_WAVE_SIZE = 4'
  assert.ok(source.includes(original), 'RETRY_WAVE_SIZE declaration text has drifted -- update this mutant fixture')
  const mutatedSource = source.replace(original, 'const RETRY_WAVE_SIZE = 9999')
  assert.notEqual(mutatedSource, source)
  const { run } = loadIssueWheelTriageShim(mutatedSource)

  const seedIssues = Array.from({ length: 60 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  let callIndex = 0
  let inFlight = 0
  let maxRetryInFlight = 0
  const trackingParallel = async (thunks) => {
    const isFirstPass = callIndex++ === 0
    return Promise.all(thunks.map(async (t) => {
      inFlight++
      if (!isFirstPass) maxRetryInFlight = Math.max(maxRetryInFlight, inFlight)
      try { return await t() } finally { inFlight-- }
    }))
  }
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    const numeric = label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label
    const batchIndex = Number(numeric.slice('triage:'.length)) - 1
    const start = batchIndex * 5
    const size = Math.min(5, 60 - start)
    if (!label.endsWith(':retry')) return null
    return {
      items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, verdict: 'unclear', rationale: 'r' })),
    }
  }

  await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent, parallel: trackingParallel })

  // RED: with RETRY_WAVE_SIZE=9999, chunk() produces a single wave holding
  // all 12 failed batches -- one parallel() call, 12 in flight.
  assert.equal(maxRetryInFlight, 12, 'single-wave mutant must show all 12 retry batches in one unbounded wave')
  assert.ok(maxRetryInFlight > 4, 'sanity: the mutant must actually violate the wave-size-4 bound')
})

test('(c2) each retry-wave parallel() call receives at most RETRY_WAVE_SIZE thunks', async () => {
  const { run } = loadIssueWheelTriageShim()

  const seedIssues = Array.from({ length: 60 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const parallelCallSizes = []
  const trackingParallel = async (thunks) => {
    parallelCallSizes.push(thunks.length)
    return Promise.all(thunks.map((thunk) => thunk()))
  }
  const stubAgent = async (_prompt, opts) => {
    const label = opts.label
    const numeric = label.endsWith(':retry') ? label.slice(0, -':retry'.length) : label
    const batchIndex = Number(numeric.slice('triage:'.length)) - 1
    const start = batchIndex * 5
    const size = Math.min(5, 60 - start)
    if (!label.endsWith(':retry')) return null
    return {
      items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, verdict: 'unclear', rationale: 'r' })),
    }
  }

  await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent, parallel: trackingParallel })

  // First call is the unbounded first pass (12 thunks); every SUBSEQUENT
  // NON-EMPTY parallel() call is a Triage retry wave and must carry at most
  // RETRY_WAVE_SIZE (4). All 12 seed issues verdict as 'unclear'
  // (non-close-class), so Verify's own batches list is empty and Screen has
  // no needs_work candidates -- both phases still call parallel([]) once
  // each for their (empty) first pass, which resolves to a 0-length call;
  // those are filtered out here since they are not Triage retry waves.
  assert.equal(parallelCallSizes[0], 12, 'first pass dispatches all 12 Triage batches at once, unchanged')
  const nonEmptyCallSizes = parallelCallSizes.filter((size) => size > 0)
  const retryWaveSizes = nonEmptyCallSizes.slice(1)
  assert.ok(retryWaveSizes.length >= 1, 'at least one retry wave must have run')
  for (const size of retryWaveSizes) {
    assert.ok(size <= 4, `every retry wave must carry at most 4 concurrent calls, got ${size}`)
  }
  // 12 failed batches / wave size 4 = exactly 3 retry waves of [4,4,4].
  assert.deepEqual(retryWaveSizes, [4, 4, 4])
})

test('(d) no retry when nothing fails -- agent call count equals batch count and retried == 0', async () => {
  const { run } = loadIssueWheelTriageShim()

  const seedIssues = Array.from({ length: 12 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  let agentCallCount = 0
  const stubAgent = async (_prompt, opts) => {
    agentCallCount++
    const batchIndex = Number(opts.label.slice('triage:'.length)) - 1
    const start = batchIndex * 5
    const size = Math.min(5, 12 - start)
    return {
      items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, verdict: 'unclear', rationale: 'r' })),
    }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.total, 3, '3 Triage batches from 12 issues at batch size 5')
  assert.equal(agentCallCount, 3, 'exactly one agent() call per batch, no retry calls')
  assert.equal(result.totals.triage_batches.retried, 0)
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(result.totals.triage_batches.ok, 3)
})

// =============================================================================
// Design change (code review round 2): only a null/malformed result with NO
// thrown error is retried -- a THROWN call (host stall, missing
// StructuredOutput) is never retried, closing the compounding-stall worst
// case (5 batches x up to ~180s each could otherwise become up to ~108
// minutes for Triage alone with a naive "retry everything" rule).
// =============================================================================

test('a THROWN Triage call is not retried and keeps its own error reason, un-suffixed', async () => {
  const { run } = loadIssueWheelTriageShim()
  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    callCounts.set(opts.label, (callCounts.get(opts.label) || 0) + 1)
    if (opts.label === 'triage:1') throw new Error('host stall')
    return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
  }
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.retried, 0, 'a thrown call is never retry-eligible')
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.deepEqual(result.totals.triage_batches.reasons, ['TRIAGE_ERROR: agent call rejected: host stall'])
  assert.equal(callCounts.get('triage:1'), 1, 'called exactly once -- never retried')
  assert.equal(callCounts.get('triage:1:retry'), undefined)
})

test('a THROWN Verify call is not retried and keeps its own error reason, un-suffixed', async () => {
  const { run } = loadIssueWheelTriageShim()
  const seedIssues = Array.from({ length: 8 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      const batchIndex = Number(opts.label.slice('triage:'.length)) - 1
      const start = batchIndex * 5
      const size = Math.min(5, 8 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1, verdict: 'already_done', cited_fix_sha: 'abc1234', rationale: 'r',
        })),
      }
    }
    if (opts.label.startsWith('verify:')) {
      callCounts.set(opts.label, (callCounts.get(opts.label) || 0) + 1)
      if (opts.label === 'verify:1') throw new Error('host stall')
      const batchIndex = Number(opts.label.slice('verify:'.length)) - 1
      const start = batchIndex * 4
      const size = Math.min(4, 8 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({ number: start + k + 1, refuted: false, evidence_checked: 're-derived and confirmed' })),
      }
    }
    return { items: [] }
  }
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.retried, 0)
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.deepEqual(result.totals.triage_batches.reasons, ['VERIFY_ERROR: agent call rejected: host stall'])
  assert.equal(callCounts.get('verify:1'), 1, 'called exactly once -- never retried')
  assert.equal(callCounts.get('verify:1:retry'), undefined)
})

test('a null-then-success Triage call is recovered (design-change eligibility: null with no thrown error IS retried)', async () => {
  const { run } = loadIssueWheelTriageShim()
  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    callCounts.set(opts.label, (callCounts.get(opts.label) || 0) + 1)
    if (opts.label === 'triage:1') return null
    if (opts.label === 'triage:1:retry') return { items: [{ number: 1, verdict: 'unclear', rationale: 'recovered' }] }
    return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
  }
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 1)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(callCounts.get('triage:1'), 1)
  assert.equal(callCounts.get('triage:1:retry'), 1)
  // Batch 1's recovered issue (#1) plus batch 2's own issue (#6, returned by
  // the fallback branch) -- both must be present, proving recovery merges
  // cleanly with an unrelated batch that never failed at all.
  assert.equal(result.unclear.length, 2)
  assert.deepEqual(result.unclear.map((i) => i.number).sort((a, b) => a - b), [1, 6])
})

test('Finding 1: a truthy-but-malformed first pass ({itemz: []}, no real items array) IS retry-eligible and can recover', async () => {
  // The retry predicate is `!error && (!result || !Array.isArray(result.items))`
  // -- deliberately not `!result` alone. A truthy object whose `items` key is
  // missing or misspelled (e.g. a schema-violating `{itemz: []}` return) must
  // be just as retry-eligible as a bare `null`, since it is the same
  // "malformed" shape the comments and doc describe throughout.
  const { run } = loadIssueWheelTriageShim()
  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    callCounts.set(opts.label, (callCounts.get(opts.label) || 0) + 1)
    if (opts.label === 'triage:1') return { itemz: [] } // truthy, but no real `items` array -- malformed, not null
    if (opts.label === 'triage:1:retry') return { items: [{ number: 1, verdict: 'unclear', rationale: 'recovered' }] }
    return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
  }
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.triage_batches.retried, 1, 'a truthy-but-malformed ({itemz: []}) result must be retry-eligible')
  assert.equal(result.totals.triage_batches.recovered, 1)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(callCounts.get('triage:1'), 1)
  assert.equal(callCounts.get('triage:1:retry'), 1)
  assert.equal(result.unclear.length, 2)
  assert.deepEqual(result.unclear.map((i) => i.number).sort((a, b) => a - b), [1, 6])
})

test('Finding 1 MUTANT sanity -- narrowing the predicate back to bare `!result` must go RED on the {itemz: []} case', async () => {
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  const original = 'if (!error && (!result || !Array.isArray(result.items))) retryEligible.push(i)'
  assert.ok(source.includes(original), 'retryEligible predicate text has drifted -- update this mutant fixture')
  const mutated = 'if (!result && !error) retryEligible.push(i)' // the OLD, narrower predicate this round replaced
  const mutatedSource = source.replace(original, mutated)
  assert.notEqual(mutatedSource, source)
  const { run } = loadIssueWheelTriageShim(mutatedSource)

  const seedIssues = Array.from({ length: 6 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const callCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    callCounts.set(opts.label, (callCounts.get(opts.label) || 0) + 1)
    if (opts.label === 'triage:1') return { itemz: [] }
    if (opts.label === 'triage:1:retry') return { items: [{ number: 1, verdict: 'unclear', rationale: 'recovered' }] }
    return { items: [{ number: 6, verdict: 'unclear', rationale: 'r6' }] }
  }
  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  // RED: with the narrower `!result` predicate, a truthy-but-malformed
  // `{itemz: []}` result is never retried at all -- it silently sails
  // through as if `Array.isArray(result.items)` were true, even though it
  // is false, because runBatchesWithRetry's own failure detection loop
  // (separate from retryEligible) still runs `!result || !Array.isArray(...)`
  // and correctly flags it as failed -- but with no retry attempt.
  assert.equal(callCounts.get('triage:1:retry'), undefined, 'the narrowed mutant never retries a truthy-but-malformed result')
  assert.equal(result.totals.triage_batches.retried, 0)
  assert.equal(result.totals.triage_batches.failed, 1)
})

test('(e-verify) a Verify batch that fails on the first pass and succeeds on retry is recovered', async () => {
  const { run } = loadIssueWheelTriageShim()

  // 8 already_done seed issues -> Triage returns all 8 as close-class;
  // chunk(., 4) = 2 Verify batches. Batch 1 (verify:1) fails its first
  // attempt only and succeeds on retry; batch 2 confirms immediately.
  const seedIssues = Array.from({ length: 8 }, (_, i) => ({ number: i + 1, title: `issue ${i + 1}`, labels: [] }))
  const verifyCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      const batchIndex = Number(opts.label.slice('triage:'.length)) - 1
      const start = batchIndex * 5
      const size = Math.min(5, 8 - start)
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1,
          verdict: 'already_done',
          cited_fix_sha: 'abc1234',
          rationale: 'r',
        })),
      }
    }
    if (opts.label.startsWith('verify:')) {
      verifyCallCounts.set(opts.label, (verifyCallCounts.get(opts.label) || 0) + 1)
      const numeric = opts.label.endsWith(':retry') ? opts.label.slice(0, -':retry'.length) : opts.label
      const batchIndex = Number(numeric.slice('verify:'.length)) - 1
      const start = batchIndex * 4
      const size = Math.min(4, 8 - start)
      if (opts.label === 'verify:1') return null // fail first attempt only
      return {
        items: Array.from({ length: size }, (_, k) => ({
          number: start + k + 1,
          refuted: false,
          evidence_checked: 're-derived and confirmed',
        })),
      }
    }
    return { items: [] }
  }

  const result = await run({ args: minimalArgs({ issues: seedIssues }), agent: stubAgent })

  assert.equal(result.totals.close_class_count, 8)
  assert.equal(result.totals.verified_close_class_count, 8, 'all 8 confirmed once the retried batch recovers')
  assert.equal(result.refuted.length, 0, 'no items fell into the conservative refuted fallback once recovered')
  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 1)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(verifyCallCounts.get('verify:1'), 1, 'first pass called once')
  assert.equal(verifyCallCounts.get('verify:1:retry'), 1, 'retry called exactly once, under the :retry label')
})

test('(e-screen) a Screen batch that fails on the first pass and succeeds on retry is recovered', async () => {
  const { run } = loadIssueWheelTriageShim()

  // One needs_work item reaching Screen. Screen's own agent() call (label
  // "screen:1") returns null on the first attempt (the retry-eligible
  // malformed shape) and a genuine pass=true on the retry.
  const screenCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [
          {
            number: 42,
            verdict: 'needs_work',
            rationale: 'cites shared/ai/model_registry.py',
            files_touched: ['shared/ai/model_registry.py'],
            size_points: 3,
          },
        ],
      }
    }
    if (opts.label.startsWith('screen:')) {
      screenCallCounts.set(opts.label, (screenCallCounts.get(opts.label) || 0) + 1)
      if (opts.label === 'screen:1') return null // fail first attempt only
      return { items: [{ number: 42, pass: true }] }
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }

  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })

  assert.deepEqual(result.needs_work_screen_failed, [], 'the recovered item must not be screen-failed')
  assert.equal(result.needs_work.length, 1)
  assert.equal(result.needs_work[0].number, 42)
  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 1)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.equal(screenCallCounts.get('screen:1'), 1, 'first pass called once')
  assert.equal(screenCallCounts.get('screen:1:retry'), 1, 'retry called exactly once, under the :retry label')
})

// =============================================================================
// Coverage (Finding 7, code review round 2)
// =============================================================================

test('Screen null-then-null: fails BOTH attempts, reason carries "(after retry)"', async () => {
  const { run } = loadIssueWheelTriageShim()
  const screenCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      screenCallCounts.set(opts.label, (screenCallCounts.get(opts.label) || 0) + 1)
      return null // fails BOTH the first pass and the retry
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }
  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })

  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.deepEqual(
    result.totals.triage_batches.reasons,
    ['SCREEN_ERROR: empty agent return | retry: SCREEN_ERROR: empty agent return (after retry)']
  )
  assert.equal(result.needs_work_screen_failed.length, 1)
  assert.equal(result.needs_work_screen_failed[0].number, 42)
  assert.equal(
    result.needs_work_screen_failed[0].fail_reason,
    'SCREEN_ERROR: empty agent return | retry: SCREEN_ERROR: empty agent return (after retry)'
  )
  assert.equal(screenCallCounts.get('screen:1'), 1)
  assert.equal(screenCallCounts.get('screen:1:retry'), 1)
})

test('Screen null-then-[]: retry returns a valid-but-empty items array -- still a failure, and NOT counted as recovered (nit 9)', async () => {
  const { run } = loadIssueWheelTriageShim()
  const screenCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      screenCallCounts.set(opts.label, (screenCallCounts.get(opts.label) || 0) + 1)
      if (opts.label === 'screen:1') return null // null on first pass -- retry-eligible
      return { items: [] } // retry returns a VALID but EMPTY array -- not a success for Screen
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }
  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })

  // Nit 9: `runBatchesWithRetry` sees a truthy, array-typed `items` on the
  // retry, so its own generic "did the call settle cleanly" check would
  // normally call this recovered -- but Screen's own passed-in isSuccess
  // predicate (Array.isArray(items) && items.length > 0) must override that
  // and correctly report NOT recovered, since Screen's own downstream loop
  // still treats a length-0 items array as a failure.
  assert.equal(result.totals.triage_batches.retried, 1)
  assert.equal(result.totals.triage_batches.recovered, 0, 'an empty-array retry result must NOT count as recovered for Screen')
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.equal(result.needs_work_screen_failed.length, 1)
  assert.equal(result.needs_work_screen_failed[0].number, 42)
  assert.equal(screenCallCounts.get('screen:1'), 1)
  assert.equal(screenCallCounts.get('screen:1:retry'), 1)
})

test('Screen returning [] on the FIRST pass is never retried -- a mutant that retries empties goes RED', async () => {
  const { run } = loadIssueWheelTriageShim()
  const screenCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      screenCallCounts.set(opts.label, (screenCallCounts.get(opts.label) || 0) + 1)
      return { items: [] } // valid-but-empty on the FIRST pass -- never retry-eligible
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }
  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })

  assert.equal(result.totals.triage_batches.retried, 0, 'a valid-but-empty first-pass result is never retry-eligible')
  assert.equal(result.totals.triage_batches.recovered, 0)
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.equal(screenCallCounts.get('screen:1'), 1)
  assert.equal(screenCallCounts.get('screen:1:retry'), undefined, 'no retry call at all -- proves this specific shape is never retried')
})

test('MUTANT sanity -- a mutant that retries Screen empties (widens eligibility to include length-0 items) must go RED against this suite', async () => {
  // Code review round 3, Finding 1: the real predicate text is
  // `!error && (!result || !Array.isArray(result.items))`, not
  // `!result && !error` -- this fixture's copied text must match the real
  // source exactly, or the `source.includes(original)` guard below fails
  // loudly instead of silently mutating nothing. A mutant that widens this
  // predicate to ALSO include a valid-but-empty items array would call
  // agent() a second time for screen:1 in the previous test's scenario --
  // this directly falsifies that specific defect.
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  const original = 'if (!error && (!result || !Array.isArray(result.items))) retryEligible.push(i)'
  assert.ok(source.includes(original), 'retryEligible predicate text has drifted -- update this mutant fixture')
  const mutated = 'if (!error && (!result || !Array.isArray(result.items) || result.items.length === 0)) retryEligible.push(i)'
  const mutatedSource = source.replace(original, mutated)
  assert.notEqual(mutatedSource, source)
  const { run } = loadIssueWheelTriageShim(mutatedSource)

  const screenCallCounts = new Map()
  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      screenCallCounts.set(opts.label, (screenCallCounts.get(opts.label) || 0) + 1)
      return { items: [] }
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }
  await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
  })

  // RED: the mutant DOES retry an empty-items-on-first-pass Screen batch.
  assert.equal(screenCallCounts.get('screen:1:retry'), 1, 'the mutant must actually retry the empty-items batch (sanity that the mutation works)')
})

// =============================================================================
// Follow-up 4 (code review round 2): dispatchScreenBatch had no `.catch`,
// unlike Triage/Verify -- a thrown Screen agent() call reached the host's
// real `parallel()` as a rejected promise rather than a settled
// `{batch, result: null, error}` value. RED on HEAD (pre-this-round source,
// i.e. the mutant below reproduces removing the .catch this round added).
//
// Code review round 3, Finding 2: the real host (CLI 2.1.197) implements
// `parallel()` on `Promise.allSettled`, and maps a REJECTED slot to a bare
// `null` -- it does NOT propagate the rejection outward the way
// `Promise.all` does. The stub below matches that exactly, so the
// no-`.catch` mutant now fails with a TypeError destructuring `null`
// (`const { result, error } = results[i]`), not a rejection carrying the
// thrown error's own message -- this is the actual failure shape the real
// host produces, not the Promise.all-shaped approximation this suite used
// before.
// =============================================================================

// A host-like `parallel` stub matching CLI 2.1.197's real implementation:
// `Promise.allSettled`, with a rejected slot mapped to a bare `null` (never
// a rethrown rejection, never an {error} wrapper) -- exactly what a
// production dispatchOne with NO `.catch` produces when its own agent()
// call throws.
async function hostLikeParallel(thunks) {
  const settled = await Promise.allSettled(thunks.map((thunk) => thunk()))
  return settled.map((s) => (s.status === 'fulfilled' ? s.value : null))
}

test('Follow-up 4: a thrown Screen agent() call does not crash P1 -- settles as {result: null, error}, batch counted as failed with the error reason', async () => {
  const { run } = loadIssueWheelTriageShim()

  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      throw new Error('simulated host stall')
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }

  // Must not reject/throw -- proves dispatchScreenBatch's .catch settles the
  // thrown call (into {batch, result: null, error}) before it ever reaches
  // the host's real allSettled-based parallel(), so the host never sees a
  // rejected slot to map to a bare null in the first place.
  const result = await run({
    args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
    agent: stubAgent,
    parallel: hostLikeParallel,
  })

  assert.equal(result.totals.triage_batches.retried, 0, 'a thrown call is never retry-eligible')
  assert.equal(result.totals.triage_batches.failed, 1)
  assert.deepEqual(result.totals.triage_batches.reasons, ['SCREEN_ERROR: agent call rejected: simulated host stall'])
  assert.equal(result.needs_work_screen_failed.length, 1)
  assert.equal(result.needs_work_screen_failed[0].number, 42)
  assert.equal(result.needs_work_screen_failed[0].fail_reason, 'SCREEN_ERROR: agent call rejected: simulated host stall')
})

test('Follow-up 4 MUTANT sanity -- removing dispatchScreenBatch\'s .catch crashes P1 with a TypeError on a thrown Screen call under the real allSettled-shaped host (RED on the pre-fix shape, GREEN on the real file)', async () => {
  const source = readFileSync(PRODUCTION_FILE, 'utf8')
  // The exact .catch line this round added to dispatchScreenBatch.
  const original = `    { label: \`screen:\${i + 1}\${isRetry ? ':retry' : ''}\`, phase: 'Screen', model: 'sonnet', schema: SCREEN_SCHEMA, agentType: 'explore' })
    .then((r) => ({ batch, result: r }))
    .catch((e) => ({ batch, result: null, error: e }))
}`
  assert.ok(source.includes(original), 'dispatchScreenBatch\'s .then/.catch text has drifted -- update this mutant fixture')
  const mutated = original.replace("\n    .catch((e) => ({ batch, result: null, error: e }))\n}", '\n}')
  assert.notEqual(mutated, original, 'mutation must actually remove the .catch line')
  const mutatedSource = source.replace(original, mutated)
  assert.notEqual(mutatedSource, source)
  const { run } = loadIssueWheelTriageShim(mutatedSource)

  const stubAgent = async (_prompt, opts) => {
    if (opts.label.startsWith('triage:')) {
      return {
        items: [{ number: 42, verdict: 'needs_work', rationale: 'cites shared/ai/model_registry.py', files_touched: ['shared/ai/model_registry.py'], size_points: 3 }],
      }
    }
    if (opts.label.startsWith('screen:')) {
      throw new Error('simulated host stall')
    }
    throw new Error(`unexpected agent() call: ${opts.label}`)
  }

  // RED: without the .catch, the host's real allSettled-based parallel()
  // maps the rejected Screen slot to a bare `null` (never propagating
  // "simulated host stall" outward at all) -- so
  // `runBatchesWithRetry`'s own `const { result, error } = results[i]`
  // throws a TypeError destructuring `null`, which is the actual crash
  // shape this bug produces under the real host, not a rejection carrying
  // the original error message.
  await assert.rejects(
    () => run({
      args: minimalArgs({ issues: [{ number: 42, title: 'forty-two', labels: [] }] }),
      agent: stubAgent,
      parallel: hostLikeParallel,
    }),
    (err) => err instanceof TypeError && /destructure/.test(err.message),
    'without dispatchScreenBatch\'s .catch, a thrown Screen call must crash the whole run with a TypeError destructuring null (this is the pre-fix bug under the real allSettled-shaped host)'
  )
})

test('sanity: totals.triage_batches.ok + failed always equals total, across all three phases combined (post-fix, happy path)', async () => {
  const { run } = loadIssueWheelTriageShim()
  const result = await run({ args: minimalArgs({ issues: [] }) })
  assert.ok(result.totals.triage_batches)
  assert.equal(result.totals.triage_batches.total, 0)
  assert.equal(result.totals.triage_batches.ok, 0)
  assert.equal(result.totals.triage_batches.failed, 0)
  assert.deepEqual(result.totals.triage_batches.reasons, [])
  assert.equal(result.totals.triage_batches.retried, 0)
  assert.equal(result.totals.triage_batches.recovered, 0)
})

// -----------------------------------------------------------------------------
// The history guard's classifier: only "no repository" and "no such object" mean
// the historical RED cases may be skipped. Everything else must be loud.
// -----------------------------------------------------------------------------

test('classifyGitShowFailure: no repository at all means the history is absent', () => {
  assert.equal(
    classifyGitShowFailure('fatal: not a git repository (or any of the parent directories): .git\n'),
    'absent'
  )
})

test('classifyGitShowFailure: a repository without the object means the history is absent', () => {
  assert.equal(classifyGitShowFailure("fatal: invalid object name '64f9ebc'.\n"), 'absent')
})

test('classifyGitShowFailure: every other failure is an error, never a quiet skip', () => {
  for (const stderr of [
    "fatal: path 'workflows/issue-wheel-triage.js' does not exist in '64f9ebc'\n",
    'fatal: bad object HEAD\n',
    'error: object file .git/objects/ab/cdef is empty\n',
    'fatal: unable to read tree 0123456789abcdef\n',
    '',
    undefined,
  ]) {
    assert.equal(classifyGitShowFailure(stderr), 'error', `stderr ${JSON.stringify(stderr)}`)
  }
})
