export const meta = {
  name: 'deliver',
  description: 'Understand -> plan -> independent plan review -> parallel execute -> adversarial multi-lens verify -> bounded rework -> HONEST report. The standard way to run a substantial task without hand-driving each step.',
  phases: [
    { title: 'Understand', detail: 'parallel read-only investigation' },
    { title: 'Plan', detail: 'plan + independent Opus plan review' },
    { title: 'Execute', detail: 'implement, split by file' },
    { title: 'Verify', detail: 'adversarial multi-lens verification (Opus)' },
    { title: 'Report', detail: 'honest status, including what is NOT verified' },
  ],
}

// =============================================================================
// deliver -- the reusable delivery loop.
//
// DESIGN NOTES (why it is shaped this way). An earlier, more elaborate draft of
// this workflow was adversarially reviewed by two independent Opus reviewers and
// REJECTED for a set of specific failures. Every one of them is deliberately
// designed out here, and each is called out inline so a future editor does not
// reintroduce it:
//
//   1. It returned done:true while items were unimplemented. Here, `done` is a
//      conjunction of BOTH "every work item actually landed" AND "every verify
//      lens confirmed", and blocked items are surfaced, never dropped.
//   2. It regex-stripped a budget hint out of the operator's task text, which
//      silently corrupted any task containing a "+<number>" ("support phone
//      numbers like +1 555 0100"). Here the task string is passed through
//      VERBATIM, always. Nothing rewrites operator intent.
//   3. Its "max 3 rework rounds" actually computed to 5. Here the bound is a
//      plain literal, and exhausting it reports FAILURE -- it never converts an
//      unverified result into a success.
//   4. It fanned out 5 concurrent Opus/effort-high whole-diff reviewers per
//      round -- exactly the synchronized big-context burst that trips ITPM
//      limits, on an operator already in a credit crunch. Here verification is
//      3 lenses by default (tunable down to 1), and the lens fan-out is the only
//      Opus leg.
//   5. Its planner ran as `general-purpose`, which has Edit/Write -- so the
//      "planning" agent could silently modify files before any review. Here
//      every read-only stage is pinned to a read-only agentType.
//
// COST SHAPE, stated honestly up front: one run costs roughly
//   (UNDERSTAND_ANGLES sonnet) + (1 sonnet plan) + (1 opus plan review)
//   + (N sonnet implementers) + (VERIFY_LENSES opus verifiers) per round,
//   for up to 1 + MAX_REWORK_ROUNDS rounds.
// Opus is used ONLY for plan review and verification -- never for implementation.
// That is the "different model reviews the work" property: the thing that wrote
// the code is never the thing that grades it, and it is a different tier.
//
// USAGE:  Workflow({name: 'deliver', args: 'your task description'})
//   args may also be an object: {task, verifyLenses, maxReworkRounds, understandAngles}
// =============================================================================

// ---- Argument handling -------------------------------------------------------
// Accept a bare string or an options object. NEVER mutate the task text.
const OPTS = (args && typeof args === 'object' && !Array.isArray(args)) ? args : {}
const TASK = typeof args === 'string' ? args : (OPTS.task || '')

if (!TASK || typeof TASK !== 'string' || !TASK.trim()) {
  throw new Error(
    "deliver: no task given. Invoke as Workflow({name:'deliver', args:'<what to do>'}) " +
    "or Workflow({name:'deliver', args:{task:'<what to do>'}})."
  )
}

// Tunables. Conservative defaults: verification is the expensive leg, so it is
// bounded, and the caller can lower it further for a cheap run.
const VERIFY_LENSES = clampInt(OPTS.verifyLenses, 1, 4, 3)
const MAX_REWORK_ROUNDS = clampInt(OPTS.maxReworkRounds, 0, 3, 2)
const UNDERSTAND_ANGLES = clampInt(OPTS.understandAngles, 1, 4, 3)
// Hard ceiling on parallel implementers, independent of how many items the plan
// proposes -- a plan that returns 50 items must not spawn 50 agents.
const MAX_PARALLEL_ITEMS = clampInt(OPTS.maxParallelItems, 1, 8, 6)

function clampInt(v, lo, hi, dflt) {
  const n = typeof v === 'number' ? Math.floor(v) : NaN
  if (!isFinite(n)) return dflt
  if (n < lo) return lo
  if (n > hi) return hi
  return n
}

// ---- Shared context injected into every agent prompt -------------------------
// Sub-agents DO load ~/.claude/CLAUDE.md automatically, so this deliberately does
// NOT restate the contract. It carries only what a fresh sub-agent cannot know:
// the task, and the few obligations that are most often dropped in practice.
const BRIEF = `TASK (verbatim, from the operator -- do not reinterpret or narrow it):
"""
${TASK}
"""

Operating reminders that apply to this task (your CLAUDE.md contract has the full
rules; these are the ones most often dropped):
- Tests assert INTENDED behavior from the spec, never a snapshot of current output.
- Living docs travel with the change, in the SAME change -- not "later".
- Never fake green: no --no-verify, noqa, type: ignore, or bare except: pass.
- Commits are path-scoped (name explicit paths; never 'git add -A'/'.'/'-a').
- Assume other agents are editing this tree right now. Never switch branches,
  never stash, never reset.
- Do NOT push, open a PR, merge, or deploy. Local work only.`

const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    understanding: { type: 'string', description: 'What the task actually requires, in your own words' },
    items: {
      type: 'array',
      description: 'Discrete work items, each owning a DISJOINT set of files so they can run in parallel',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          intent: { type: 'string', description: 'What this item must achieve, and how to tell it worked' },
          files: { type: 'array', items: { type: 'string' }, description: 'Files this item may touch. Must not overlap another item.' },
        },
        required: ['id', 'intent', 'files'],
      },
    },
    risks: { type: 'array', items: { type: 'string' } },
    out_of_scope: { type: 'array', items: { type: 'string' }, description: 'Explicitly what this will NOT do' },
  },
  required: ['understanding', 'items', 'risks', 'out_of_scope'],
}

const PLAN_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean', description: 'False if the plan must change before any code is written' },
    blocking: { type: 'array', items: { type: 'string' }, description: 'Issues that must be fixed before implementing' },
    file_overlap_detected: { type: 'boolean', description: 'True if two items claim the same file (forbidden)' },
    missing_from_plan: { type: 'array', items: { type: 'string' }, description: 'Parts of the operator task the plan silently drops' },
  },
  required: ['approved', 'blocking', 'file_overlap_detected', 'missing_from_plan'],
}

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'blocked'] },
    summary: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'string', description: 'Actual command output / test results proving it works. Not a claim -- output.' },
    blocked_reason: { type: 'string', description: 'Required when status is blocked' },
  },
  required: ['status', 'summary', 'files_changed', 'evidence'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'TRUE if you could NOT confirm the work is complete and correct. Default to true when uncertain.' },
    findings: { type: 'array', items: { type: 'string' }, description: 'Specific defects, each with file:line or command output' },
    evidence_checked: { type: 'string', description: 'What you actually ran/read to reach this verdict' },
  },
  required: ['refuted', 'findings', 'evidence_checked'],
}

// Distinct lenses. Perspective diversity beats N identical checkers -- each of
// these can catch a class the others structurally cannot.
const ALL_LENSES = [
  {
    key: 'works',
    prompt: 'Does the change ACTUALLY do what the task asked? Run the relevant tests/commands yourself and read the real files. Do not accept the implementer\'s self-report as evidence -- re-derive it. If you cannot run something, say so and treat it as unverified.',
  },
  {
    key: 'regressions',
    prompt: 'What did this BREAK? Look for callers of changed functions, changed signatures/behavior other code depends on, tests that no longer cover what they claim, and side effects outside the stated file list. Run the broader test suite if one exists.',
  },
  {
    key: 'intent-and-tests',
    prompt: 'Does the change match the operator\'s STATED intent, including any part quietly dropped or narrowed? And are the tests real: do they assert INTENDED behavior from a spec, or are they lock-in tests that merely snapshot whatever the code now outputs? A lock-in test is a defect, not coverage.',
  },
  {
    key: 'docs-and-issues',
    prompt: 'Did the living docs and issue state travel with this change, per the contract? Check whether docs claim something the code does not actually do -- doc-vs-reality drift is a real defect here, not a nitpick.',
  },
]

// intent-and-tests is the lens that explicitly checks for lock-in tests --
// tests that merely snapshot whatever the code currently outputs instead of
// asserting INTENDED behavior from a spec. That is the operator's explicitly
// stated top concern ("I am concerned that agents are writing tests that
// simply assert whatever the current behavior is without considering what is
// correct and intended"). A plain `ALL_LENSES.slice(0, VERIFY_LENSES)` over a
// fixed-order array meant a caller passing verifyLenses:1 or verifyLenses:2
// would silently drop this exact lens -- no warning, no log line, nothing.
// Fixed here: intent-and-tests is now a MANDATORY baseline lens, unconditionally
// included in EVERY verify pass regardless of VERIFY_LENSES. Whatever budget
// VERIFY_LENSES leaves over (N-1 slots) is filled from the remaining lenses in
// their existing priority order: works, regressions, docs-and-issues.
//
// DELIBERATE CHOICE: when VERIFY_LENSES=1, the one lens that runs is
// intent-and-tests -- NOT works. "Does it even run" is a reasonable baseline
// sanity check, but the operator's stated concern is specifically lock-in
// tests, so that lens outranks "does it work" when only a single lens fits the
// budget. Calling this out explicitly so it is a visible, deliberate priority
// decision, not something silently buried in array order.
const MANDATORY_LENS_KEY = 'intent-and-tests'
const mandatoryLens = ALL_LENSES.find((l) => l.key === MANDATORY_LENS_KEY)
if (!mandatoryLens) {
  throw new Error(
    `deliver: mandatory verify lens '${MANDATORY_LENS_KEY}' was not found in ALL_LENSES ` +
    `(available lens keys: [${ALL_LENSES.map((l) => l.key).join(', ')}]). ` +
    'MANDATORY_LENS_KEY must match a real lens.key in ALL_LENSES -- either restore the ' +
    `'${MANDATORY_LENS_KEY}' lens or update MANDATORY_LENS_KEY to the lens that should be mandatory.`
  )
}
const optionalLenses = ALL_LENSES.filter((l) => l.key !== MANDATORY_LENS_KEY)
const LENSES = [mandatoryLens, ...optionalLenses].slice(0, VERIFY_LENSES)

// =============================================================================
// Phase 1 -- Understand (read-only, parallel, cheap)
// =============================================================================
phase('Understand')
log(`deliver: task received (${TASK.length} chars). ${UNDERSTAND_ANGLES} understand angles, ` +
    `${LENSES.length} verify lenses, up to ${MAX_REWORK_ROUNDS} rework rounds.`)

const ANGLES = [
  'Map the code that this task will have to touch: entry points, key functions, and where the relevant logic actually lives. Cite file:line.',
  'Find the existing tests, harnesses, and CI checks that cover this area, and state exactly how to run them. If a harness already exists for this, say so loudly -- do not let anyone rebuild one.',
  'Find the constraints: relevant rules in CLAUDE.md / engineering standards, existing conventions in the surrounding code, and any prior art or related past changes.',
  'Find what could go wrong: fragile areas, known flaky tests, things that look adjacent and might break.',
].slice(0, UNDERSTAND_ANGLES)

const findings = await parallel(ANGLES.map((angle, i) => () =>
  agent(`${BRIEF}

YOUR ROLE THIS ROUND: read-only investigation. Do NOT change any file.

${angle}

Return a dense, factual briefing with concrete file:line references. If something
the task assumes turns out not to exist, say so plainly -- that is the single most
valuable thing you can report.`,
    { label: `understand:${i + 1}`, phase: 'Understand', model: 'sonnet', agentType: 'explore' })
))

const CONTEXT = findings.filter(Boolean).map((f, i) => `--- investigation ${i + 1} ---\n${f}`).join('\n\n')
if (!CONTEXT.trim()) {
  log('deliver: WARNING -- all investigation agents returned empty. Planning blind.')
}

// =============================================================================
// Phase 2 -- Plan, then INDEPENDENT review before any code is written
// =============================================================================
phase('Plan')

let plan = await agent(`${BRIEF}

Investigation findings from the parallel read-only pass:
${CONTEXT}

Produce an implementation plan. Rules:
- Split the work into items whose file sets DO NOT OVERLAP -- they will be run in
  parallel by separate agents, and two agents editing one file corrupts the tree.
- Every item must state how you would TELL it worked (the observable evidence).
- State explicitly what is OUT of scope, and name anything in the operator's task
  you are deliberately NOT doing and why.
- Do not pad. Fewer, correct items beat many speculative ones.`,
  { label: 'plan', phase: 'Plan', model: 'sonnet', schema: PLAN_SCHEMA, agentType: 'Plan' })

if (!plan) throw new Error('deliver: planning agent returned nothing; aborting rather than guessing.')

// Independent Opus plan review -- the operator's contract requires this BEFORE code.
const planReview = await agent(`${BRIEF}

A plan has been proposed. Review it BEFORE any code is written. Be adversarial:
your job is to find what it gets wrong, not to approve it.

PROPOSED PLAN:
${JSON.stringify(plan, null, 2)}

Investigation context the planner had:
${CONTEXT}

Check specifically:
- Does it actually address the operator's whole task, or does it quietly narrow it?
- Do any two items claim the same file? (That is forbidden -- flag it.)
- Are the "how I'd tell it worked" criteria real and checkable, or hand-waving?
- Does it violate the operating contract (lock-in tests, docs not travelling with
  the change, scope creep, bypassing checks)?
Read the real files to ground your review.`,
  { label: 'plan-review', phase: 'Plan', model: 'opus', schema: PLAN_REVIEW_SCHEMA, agentType: 'plan-reviewer' })

if (planReview && (planReview.file_overlap_detected || !planReview.approved)) {
  log(`deliver: plan review returned blocking issues (${(planReview.blocking || []).length}); revising once.`)
  const revised = await agent(`${BRIEF}

Your previous plan was reviewed and REJECTED. Fix it.

YOUR PREVIOUS PLAN:
${JSON.stringify(plan, null, 2)}

BLOCKING ISSUES: ${JSON.stringify((planReview.blocking) || [])}
PARTS OF THE TASK YOU DROPPED: ${JSON.stringify((planReview.missing_from_plan) || [])}
FILE OVERLAP BETWEEN ITEMS: ${planReview.file_overlap_detected ? 'YES -- items must own disjoint files' : 'no'}

Return a corrected plan addressing every point.`,
    { label: 'plan-revise', phase: 'Plan', model: 'sonnet', schema: PLAN_SCHEMA, agentType: 'Plan' })
  if (revised) plan = revised
}

let items = Array.isArray(plan.items) ? plan.items.filter(Boolean) : []
if (!items.length) throw new Error('deliver: plan produced no work items; aborting.')

// No silent caps -- if we trim, say so.
if (items.length > MAX_PARALLEL_ITEMS) {
  log(`deliver: plan produced ${items.length} items; capping to ${MAX_PARALLEL_ITEMS}. ` +
      `DEFERRED (not done): ${items.slice(MAX_PARALLEL_ITEMS).map((i) => i.id).join(', ')}`)
}
const deferred = items.slice(MAX_PARALLEL_ITEMS).map((i) => i.id)
items = items.slice(0, MAX_PARALLEL_ITEMS)

// =============================================================================
// Phase 3/4 -- Execute, then adversarially verify. Rework loop is bounded and
// its exhaustion is reported as FAILURE, never laundered into success.
// =============================================================================
let round = 0
let implResults = []
let lensVerdicts = []
let verified = false
let priorFindings = []

while (round <= MAX_REWORK_ROUNDS) {
  phase('Execute')
  const isRework = round > 0
  log(isRework
    ? `deliver: rework round ${round}/${MAX_REWORK_ROUNDS} addressing ${priorFindings.length} finding(s).`
    : `deliver: executing ${items.length} item(s) in parallel.`)

  implResults = await parallel(items.map((item) => () =>
    agent(`${BRIEF}

${isRework ? `THIS IS A REWORK ROUND. Verification REJECTED the previous attempt.
Findings you must fix:
${priorFindings.map((f) => `  - ${f}`).join('\n')}

Fix these specifically. Do not start over, and do not expand scope.` : ''}

YOUR WORK ITEM (${item.id}): ${item.intent}
FILES YOU OWN (do not touch files outside this list -- other agents own those):
${(item.files || []).map((f) => `  - ${f}`).join('\n')}

Plan context: ${plan.understanding}

Implement it. Then PROVE it works by running the relevant tests/commands and
returning their ACTUAL output as evidence. If you cannot make it work, return
status 'blocked' with the real reason -- a blocked item reported honestly is far
more useful than a false 'done'. Do not commit; the orchestrator handles that.`,
      { label: `implement:${item.id}`, phase: 'Execute', model: 'sonnet', schema: IMPL_SCHEMA, agentType: 'implement' })
      .then((r) => ({ item, result: r }))
  ))

  const usable = implResults.filter((r) => r && r.result)
  const blocked = usable.filter((r) => r.result.status === 'blocked')
  const landed = usable.filter((r) => r.result.status === 'done')
  const missing = items.length - usable.length

  log(`deliver: execute round ${round} -> ${landed.length} done, ${blocked.length} blocked, ${missing} no-result.`)

  phase('Verify')
  log(`deliver: verify lenses selected for this pass (round ${round}) -> [${LENSES.map((l) => l.key).join(', ')}] ` +
      `(intent-and-tests is a MANDATORY baseline lens and always runs, regardless of verifyLenses=${VERIFY_LENSES}).`)
  const changeSummary = usable.map((r) =>
    `ITEM ${r.item.id} [${r.result.status}]\n  intent: ${r.item.intent}\n  files: ${(r.result.files_changed || []).join(', ')}\n  summary: ${r.result.summary}\n  claimed evidence: ${r.result.evidence}`
  ).join('\n\n')

  lensVerdicts = await parallel(LENSES.map((lens) => () =>
    agent(`${BRIEF}

Work has been performed and claims to be complete. Your job is to REFUTE that claim.

YOUR LENS: ${lens.prompt}

WHAT THE IMPLEMENTERS SAY THEY DID (treat as an UNVERIFIED CLAIM, not as evidence):
${changeSummary}

${blocked.length ? `NOTE: ${blocked.length} item(s) reported BLOCKED and were not completed:
${blocked.map((b) => `  - ${b.item.id}: ${b.result.blocked_reason || 'no reason given'}`).join('\n')}` : ''}

Rules:
- Re-derive everything yourself from the real repo. Run the tests. Read the files.
- Set refuted=true if you cannot CONFIRM correctness and completeness. Uncertainty
  means refuted, not approved. A rubber stamp here is a failure of your job.
- Every finding must cite concrete evidence: file:line, or actual command output.
- Report only real defects. Do not invent problems to seem thorough.`,
      { label: `verify:${lens.key}:r${round}`, phase: 'Verify', model: 'opus', schema: VERIFY_SCHEMA, agentType: 'code-reviewer' })
      .then((v) => ({ lens: lens.key, verdict: v }))
  ))

  const answered = lensVerdicts.filter((v) => v && v.verdict)
  const refuting = answered.filter((v) => v.verdict.refuted)
  const silentLenses = LENSES.length - answered.length

  priorFindings = refuting.flatMap((v) => (v.verdict.findings || []).map((f) => `[${v.lens}] ${f}`))

  // `verified` requires ALL of: every item landed, no deferrals, no lens refuted,
  // and no lens failed to answer. A lens that errored is NOT an implicit pass.
  const allItemsLanded = landed.length === items.length && blocked.length === 0 && missing === 0
  verified = allItemsLanded && refuting.length === 0 && silentLenses === 0 && deferred.length === 0

  log(`deliver: verify round ${round} -> ${refuting.length}/${answered.length} lenses refuted` +
      (silentLenses ? `, ${silentLenses} lens(es) gave no verdict (counted as NOT verified)` : '') +
      `, items landed ${landed.length}/${items.length}.`)

  if (verified) break
  if (round === MAX_REWORK_ROUNDS) {
    log(`deliver: rework bound (${MAX_REWORK_ROUNDS}) exhausted WITHOUT verification. Reporting failure honestly.`)
    break
  }
  if (!priorFindings.length && !allItemsLanded) {
    log('deliver: items did not land but no lens produced actionable findings; reworking on the blocked reasons.')
    priorFindings = blocked.map((b) => `[blocked] ${b.item.id}: ${b.result.blocked_reason || 'no reason given'}`)
  }
  if (!priorFindings.length) {
    log('deliver: nothing actionable to rework on; stopping to avoid a no-progress loop.')
    break
  }
  round += 1
}

// =============================================================================
// Phase 5 -- Honest report. `done` is a conjunction; nothing is laundered.
// =============================================================================
phase('Report')

const usableFinal = implResults.filter((r) => r && r.result)
const blockedFinal = usableFinal.filter((r) => r.result.status === 'blocked')
const answeredFinal = lensVerdicts.filter((v) => v && v.verdict)

const report = {
  done: verified,
  task: TASK,
  rounds_used: round + (verified ? 0 : 0),
  what_landed: usableFinal
    .filter((r) => r.result.status === 'done')
    .map((r) => ({ id: r.item.id, summary: r.result.summary, files: r.result.files_changed })),
  blocked: blockedFinal.map((r) => ({ id: r.item.id, reason: r.result.blocked_reason || 'no reason given' })),
  deferred_never_attempted: deferred,
  verification: {
    lenses_run: LENSES.map((l) => l.key),
    lenses_that_answered: answeredFinal.map((v) => v.lens),
    lenses_that_refuted: answeredFinal.filter((v) => v.verdict.refuted).map((v) => v.lens),
    outstanding_findings: priorFindings,
    independence_caveat:
      'Verifiers are a different model tier (opus) than implementers (sonnet) and run ' +
      'in fresh contexts, but they are still the same model family reading the same ' +
      'post-change tree. Correlated blind spots are possible. This is not proof.',
  },
  out_of_scope_per_plan: plan.out_of_scope || [],
  NOT_done: verified
    ? []
    : [
        ...(blockedFinal.length ? [`${blockedFinal.length} item(s) blocked and never completed`] : []),
        ...(deferred.length ? [`${deferred.length} planned item(s) were never attempted (over the parallel cap)`] : []),
        ...(priorFindings.length ? [`${priorFindings.length} verification finding(s) remain unresolved`] : []),
        ...(answeredFinal.length < LENSES.length ? ['one or more verify lenses returned no verdict'] : []),
      ],
  next_step: verified
    ? 'Work is implemented and survived adversarial verification. Nothing has been pushed, PRd, merged, or deployed -- that still requires the operator.'
    : 'NOT verified. Read NOT_done and verification.outstanding_findings before trusting any of this. Do not treat partial completion as done.',
}

log(report.done
  ? 'deliver: VERIFIED. All items landed and no lens refuted.'
  : `deliver: NOT VERIFIED -- ${report.NOT_done.join('; ')}`)

return report
