export const meta = {
  name: 'issue-wheel-triage',
  description: 'THE ISSUE WHEEL P1: sonnet-only, schema-bound, read-and-report triage of a seed issue list -- Triage verdict, DEFAULT-REFUTE Verify, structural Screen, then plain-JS lane pre-filtering. Writes nothing; ordering is deleted (P4 is deterministic).',
  phases: [
    { title: 'Triage', detail: '6-verdict enum per issue, grounded in gh issue view --comments, 5/agent' },
    { title: 'Verify', detail: 'DEFAULT-REFUTE second pass over close-class verdicts only, 4/agent' },
    { title: 'Screen', detail: 'structural checks on needs_work items, 20/agent; empty return is a FAILURE' },
  ],
}

// =============================================================================
// issue-wheel-triage -- P1 of THE ISSUE WHEEL (plan: issue_wheel_consolidation.md
// section 4). RULE G1 (section 3): this script cannot call the Agent tool and has
// no shell/fs access -- it fans out ONLY via the in-script agent() primitive, and
// every such call is bounded, schema-shaped, READ-AND-REPORT (never a reviewer,
// never a writer, never anything that shells out), pinned to model: 'sonnet'.
//
// RULE G2 (section 3): a mechanical checker
// (~/.claude/hooks/check_workflow_agent_purity.py) proves this file never
// violates G1 -- no shell-out strings, every agent() call pinned to a real
// model, and no agentType among the review/write-capable set
// (code-reviewer / trust-architect / plan-reviewer / implement / test-writer).
//
// Deliberately absent, per section 4 P1 item 5: an "Order"/"Rank" phase. Ordering
// is P4's job and is fully deterministic plain JS outside this script -- no LLM
// ranking agent runs here at all.
//
// args (session-seeded, since a Workflow cannot shell out -- see plan section 4):
//   args.repo, args.project, args.projectOwner   REQUIRED; no baked-in default.
//   args.issues            seed list: [{number, title, labels}, ...]
//   args.priorIndex        ledger cross-wave index (<=300), for grounding/dedupe
//   args.dirtyPaths        P0 snapshot: paths currently dirty in the working tree
//   args.loopHeldPaths     P0 snapshot: paths currently held by the nightly loop
//   args.today             P0's UTC date string (Date.now/new Date unavailable here)
//   args.authorization     standing close-authorization one-liner, passed through
//                          verbatim -- this script never interprets it, only
//                          forwards it into agent prompts as context.
// =============================================================================

// Defense-in-depth (2026-09-09, closing a real reproduced failure -- #5160):
// a calling session sometimes passes `args` as a JSON-ENCODED STRING instead of
// a genuine object (JSON.stringify'd before the tool call, rather than passed as
// the tool call's own args value). Without this fallback, that silently-
// discarded string falls through to the {} default below, which throws
// "args.repo is required" -- a technically truthful but misleading error with
// no hint at the real cause (a stringification bug, not a missing value).
// This widens ACCEPTED INPUT SHAPES only -- it can never weaken the
// required-field contract: a failed parse, or a parse that yields a non-object
// (an array, a number, null), falls through to the identical {} default and the
// identical throws below, exactly as an unparseable/missing args already does.
let ARGS_MAYBE_STRINGIFIED = args
if (typeof ARGS_MAYBE_STRINGIFIED === 'string') {
  try {
    const parsed = JSON.parse(ARGS_MAYBE_STRINGIFIED)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      ARGS_MAYBE_STRINGIFIED = parsed
    }
  } catch (_e) {
    // Not valid JSON -- fall through to the {} default below, same as any
    // other malformed args value.
  }
}

const OPTS = (ARGS_MAYBE_STRINGIFIED && typeof ARGS_MAYBE_STRINGIFIED === 'object' && !Array.isArray(ARGS_MAYBE_STRINGIFIED)) ? ARGS_MAYBE_STRINGIFIED : {}

if (!OPTS.repo || typeof OPTS.repo !== 'string' || !OPTS.repo.trim()) {
  throw new Error("issue-wheel-triage: args.repo is required and must be a non-empty string. No baked-in default.")
}
if (!OPTS.project || typeof OPTS.project !== 'string' || !OPTS.project.trim()) {
  throw new Error("issue-wheel-triage: args.project is required and must be a non-empty string. No baked-in default.")
}
if (!OPTS.projectOwner || typeof OPTS.projectOwner !== 'string' || !OPTS.projectOwner.trim()) {
  throw new Error("issue-wheel-triage: args.projectOwner is required and must be a non-empty string. No baked-in default.")
}

const REPO = OPTS.repo
const PROJECT = OPTS.project
const PROJECT_OWNER = OPTS.projectOwner
const ISSUES = Array.isArray(OPTS.issues) ? OPTS.issues.filter(Boolean) : []
const PRIOR_INDEX = Array.isArray(OPTS.priorIndex) ? OPTS.priorIndex : []
const DIRTY_PATHS = Array.isArray(OPTS.dirtyPaths) ? OPTS.dirtyPaths : []
const LOOP_HELD_PATHS = Array.isArray(OPTS.loopHeldPaths) ? OPTS.loopHeldPaths : []
const TODAY = typeof OPTS.today === 'string' && OPTS.today.trim() ? OPTS.today.trim() : null
const AUTHORIZATION = typeof OPTS.authorization === 'string' ? OPTS.authorization : ''

if (!TODAY) {
  throw new Error(
    "issue-wheel-triage: args.today is required (a UTC date string seeded by the " +
    "calling session) -- Date.now()/new Date() are unavailable inside Workflow scripts."
  )
}

const TRIAGE_BATCH_SIZE = 5
const VERIFY_BATCH_SIZE = 4
const SCREEN_BATCH_SIZE = 20

// GH #4767 (WS14-S1 item 1d): S1-A1's attended run lost 23 of 25 batches
// (24 Triage batches plus 1 Screen batch, not a single 25-batch Triage
// fan-out) to transient server-side 429s ("Server is temporarily limiting
// requests (not your usage limit) - Rate limited") because every batch in a
// phase fires in one synchronized `parallel(...)` burst with no retry (the
// host's own `parallel()` caps real concurrency at `min(16, cores-2)` --
// 16 on this machine -- but a 24-batch Triage fan-out still queues 24
// requests in one synchronized burst against that cap, which is what
// triggered the storm). This bounds the blast radius of a rate-limit storm:
// ONE retry pass per phase, re-running ONLY the batches that failed the
// first pass with a null/malformed return (never a batch whose call THREW
// -- see runBatchesWithRetry's own eligibility rule below), in waves of at
// most this many concurrent agent() calls -- never the full failed set at
// once, which would just reproduce the same synchronized burst.
//
// Finding 3 correction (code review, round 2): this retry is bounded --
// at most one extra attempt per null/malformed batch, at most
// RETRY_WAVE_SIZE in flight at a time -- but that bound is on THIS script's
// own contribution to wall-clock time, not a guarantee that RULE G4's
// 45-minute P1 budget (schedules/prompts/issue_wheel.txt) is never
// approached: a 429 storm hitting both Triage and Verify in the same run can
// still consume a large share of that budget, and RULE G4 applies exactly
// as it did before this change if it does.
const RETRY_WAVE_SIZE = 4

// The 6-verdict enum, carried verbatim from the plan's own citation of
// issue-burndown.js:193-217.
const VERDICTS = ['already_done', 'not_doing', 'duplicate', 'needs_work', 'operator_only', 'unclear']
const CLOSE_CLASS_VERDICTS = ['already_done', 'not_doing', 'duplicate']

const SHA_RE = /^[0-9a-f]{7,40}$/

function chunk(list, size) {
  const out = []
  for (let i = 0; i < list.length; i += size) out.push(list.slice(i, i + size))
  return out
}

// ---- Bounded one-retry-in-waves helper (GH #4767, WS14-S1 item 1d) --------
// `dispatchOne(batch, batchIndex, isRetry)` is supplied by each phase and
// must contain that phase's own single `agent(...)` call site (this helper
// never calls agent() itself, so it adds zero new call sites for
// check_workflow_agent_purity.py / workflow_model_gate.py to find). It is
// called with `isRetry=true` on the retry attempt so the phase can suffix
// its own agent() label with `:retry` (nit 11); every phase's dispatcher
// must forward this into its own `label:` option. It returns a
// `{batch, result, error}`-shaped settlement, matching each phase's existing
// `.then/.catch` shape -- EVERY dispatcher, including Screen's (which
// lacked a `.catch` before this round -- see the fix at dispatchScreenBatch
// below), must attach `.catch((e) => ({ batch, result: null, error: e }))`,
// because this helper (and the host's real `parallel()`) needs a settled
// value, never a rejected promise, to decide retry eligibility.
//
// `isSuccess(result)` (optional, defaults to "result.items is an array") is
// how a phase defines "this batch came back clean" for the purposes of
// counting `recovered` -- Screen's own stricter rule (a valid-but-EMPTY
// items array is ALSO a failure, per its own downstream loop) needs a
// stricter predicate here too (nit 9): otherwise a retry that returns
// `{items: []}` would count as `recovered` even though Screen's own loop
// will still treat that item as screen-failed.
//
// RETRY ELIGIBILITY (design change, code review round 2; predicate corrected
// round 3, Finding 1): only a null/malformed result (no thrown error, and
// either the result itself is null/non-object, or a truthy result whose
// `items` is not an array) is retried -- the exact shape a 429 or a
// malformed/empty agent() return produces. A batch whose call THREW
// (`error` is set) is never retried: a thrown call is typically a host
// stall or a missing-StructuredOutput error, not a transient rate limit, and
// retrying it would multiply a slow failure mode into a compounding one
// instead of fixing a fast transient one -- e.g. a 24-batch Triage fan-out
// retried in 6 waves of 4, each wave gated on the slowest call in it, turns
// one ~18-minute host-stall wave into up to ~108 minutes (6 waves x ~18 min)
// if every wave hits the same stall, rather than fixing the fast 429 case
// this retry actually targets. A thrown batch keeps its original
// error/reason untouched by this helper -- it is not touched by the retry
// loop at all, so its {batch, result: null, error} entry in `results` is
// exactly its first-pass settlement.
//
// Returns `{results, retried, recovered}`:
//   - results: one entry per input batch, in original order -- a batch that
//     was retried has its result REPLACED in place with the retry's own
//     settlement (success or failure), and (nit 10) a batch that fails BOTH
//     attempts carries BOTH the first-pass and the retry's error/failure
//     info via `firstError`/`firstResult` fields added onto the retried
//     settlement, so a phase's own reason-building can cite both.
//   - retried: how many batches were re-run (null/malformed, no thrown error).
//   - recovered: how many of those came back `isSuccess(result)` true.
async function runBatchesWithRetry(batches, dispatchOne, isSuccess) {
  const succeeds = isSuccess || ((result) => !!result && Array.isArray(result.items))
  const results = await parallel(batches.map((batch, i) => () => dispatchOne(batch, i, false)))

  // Retry-eligible: no thrown error AND the result is null/non-object OR its
  // `items` is not an array (the "null/malformed" shape stated throughout
  // the comments/doc above -- a truthy-but-malformed object, e.g.
  // `{itemz: []}` with a typo'd key, is retry-eligible too, not just a bare
  // `null`). A batch whose call THREW is excluded (design change above).
  // Deliberately does NOT flag a Screen-shaped valid-but-EMPTY `items: []`
  // (Array.isArray(result.items) is true there, so it never matches) --
  // that stays Screen's own separate, unretried failure rule.
  const retryEligible = []
  for (let i = 0; i < results.length; i++) {
    const { result, error } = results[i]
    if (!error && (!result || !Array.isArray(result.items))) retryEligible.push(i)
  }

  let recovered = 0
  if (retryEligible.length) {
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
  }

  return { results, retried: retryEligible.length, recovered }
}

// Nit 10: builds a single reason string for a batch that failed the first
// pass -- `baseReason(result, error)` is the phase's own existing
// reason-format function (unchanged per phase: TRIAGE_ERROR:/VERIFY_ERROR:/
// SCREEN_ERROR:-prefixed). When the settlement carries `firstResult`/
// `firstError` (i.e. it WAS retried and failed again), the returned string
// cites BOTH the first-pass reason and the retry's own reason, joined by
// " | retry: ", with " (after retry)" appended -- never just the retry's
// reason alone, which would silently drop the first failure's own
// diagnostic (e.g. a distinct malformed-return shape vs the retry's).
// When the settlement was never retried (no `firstResult`/`firstError` key
// at all -- a thrown call, per the retry-eligibility rule above, or Screen's
// own unretried empty-items shape), returns just the single reason,
// unchanged from before this round.
function buildFailureReason(settlement, baseReason) {
  const wasRetried = Object.prototype.hasOwnProperty.call(settlement, 'firstError')
  if (!wasRetried) return baseReason(settlement.result, settlement.error)
  const firstReason = baseReason(settlement.firstResult, settlement.firstError)
  const retryReason = baseReason(settlement.result, settlement.error)
  return `${firstReason} | retry: ${retryReason} (after retry)`
}

// ---- Shared context injected into every agent prompt -----------------------
const BRIEF = `THE ISSUE WHEEL -- P1 TRIAGE (repo: ${REPO}, project: ${PROJECT}, owner: ${PROJECT_OWNER})

You are a READ-AND-REPORT agent. You never write anything: no commit, no gh
issue close/comment/edit, no file edit. You only READ (gh issue view, source
files) and RETURN a schema-shaped verdict for the orchestrating session to act
on later, outside this script.

Today (UTC, passed in -- do not compute your own date): ${TODAY}
Standing close-authorization context (verbatim, do not interpret -- only cite
it back if directly relevant to your verdict): ${AUTHORIZATION || '(none provided)'}`

// =============================================================================
// Schemas
// =============================================================================

const TRIAGE_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    number: { type: 'integer', description: 'The issue number this verdict is for' },
    verdict: { type: 'string', enum: VERDICTS },
    rationale: { type: 'string', description: 'Why this verdict, grounded in what you actually read (gh issue view --comments, and any cited files)' },
    cited_fix_sha: { type: 'string', description: "REQUIRED when verdict is 'already_done'. Hex commit sha, ^[0-9a-f]{7,40}$ -- never a ref name, never HEAD~N. Never guessed." },
    superseded_by: { type: 'string', description: "REQUIRED when verdict is 'not_doing'. A mechanically-checkable citation: an issue ref or a doc path." },
    duplicate_of: { type: 'string', description: "REQUIRED when verdict is 'duplicate'. The issue number/ref it duplicates." },
    files_touched: { type: 'array', items: { type: 'string' }, description: "For 'needs_work': files you expect the fix to touch, based on what you actually read." },
    size_points: { type: 'integer', description: "For 'needs_work': an estimate size in points, with the reasoning in rationale citing a real path/symbol you read." },
  },
  required: ['number', 'verdict', 'rationale'],
}

const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    items: { type: 'array', items: TRIAGE_ITEM_SCHEMA },
  },
  required: ['items'],
}

const VERIFY_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    number: { type: 'integer' },
    refuted: { type: 'boolean', description: 'TRUE if you could NOT confirm the close-class verdict is correct. Default to true when uncertain.' },
    correction: { type: 'string', description: 'If refuted, what the correct verdict/handling should be. Optional -- a refutation with no correction just leaves the item untouched.' },
    evidence_checked: { type: 'string', description: 'What you actually read/ran to reach this verdict' },
  },
  required: ['number', 'refuted', 'evidence_checked'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    items: { type: 'array', items: VERIFY_ITEM_SCHEMA },
  },
  required: ['items'],
}

const SCREEN_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    number: { type: 'integer' },
    pass: { type: 'boolean' },
    fail_reason: { type: 'string', description: "Required when pass=false. One of: 'no-longer-open', 'no-files-touched', 'no-size-points', 'stale: closed by another lane', or a free-text structural reason." },
  },
  required: ['number', 'pass'],
}

const SCREEN_SCHEMA = {
  type: 'object',
  properties: {
    items: { type: 'array', items: SCREEN_ITEM_SCHEMA },
  },
  required: ['items'],
}

// =============================================================================
// Phase 1 -- Triage. 5 issues/agent. Every batch dispatched in parallel.
// =============================================================================
phase('Triage')
log(`issue-wheel-triage: ${ISSUES.length} seed issue(s), batched ${TRIAGE_BATCH_SIZE}/agent.`)

const triageBatches = chunk(ISSUES, TRIAGE_BATCH_SIZE)

// The single Triage agent() call site (GH #4767 WS14-S1 item 1d: factored so
// both the first pass and the bounded retry share exactly one call site, for
// check_workflow_agent_purity.py / workflow_model_gate.py's `model:`-presence
// scan).
function dispatchTriageBatch(batch, i, isRetry) {
  return agent(`${BRIEF}

YOUR ROLE THIS ROUND: triage a batch of issues. For EACH issue in your batch,
open it for real (gh issue view --comments) and read its full comment thread --
the REAL issue is authoritative, the seed title below is a hint only and may be
stale or wrong. Cross-reference against the prior-wave index provided.

Return exactly one verdict object per issue number in your batch, using this
6-verdict enum: already_done | not_doing | duplicate | needs_work | operator_only | unclear.

Per-verdict rules, strict:
- already_done REQUIRES cited_fix_sha (a real hex commit sha you actually found,
  matching ^[0-9a-f]{7,40}$ -- NEVER a ref name like "HEAD~5", NEVER guessed) AND
  a non-empty rationale. If you cannot find a real hex sha, do NOT use
  already_done -- use unclear instead.
- not_doing REQUIRES superseded_by (an issue ref or doc path you can point to).
- duplicate REQUIRES duplicate_of (the issue/ref it duplicates).
- needs_work should include files_touched (files you actually expect the fix to
  touch, based on what you read) and size_points (with the estimate's reasoning
  in rationale, citing a real path/symbol you opened).
- NEVER cite a file you did not actually open. NEVER guess a sha.

If your batch produces two rows for the same issue number, that is a bug in your
own output -- do not do it; the caller keeps the first, but you should never rely
on that.

SEED ISSUES IN YOUR BATCH (title is a hint only -- verify against the real issue):
${JSON.stringify(batch, null, 2)}

PRIOR-WAVE LEDGER INDEX (cross-reference for dedupe/already-seen context):
${JSON.stringify(PRIOR_INDEX.slice(0, 300), null, 2)}`,
    { label: `triage:${i + 1}${isRetry ? ':retry' : ''}`, phase: 'Triage', model: 'sonnet', schema: TRIAGE_SCHEMA, agentType: 'explore' })
    .then((r) => ({ batch, result: r }))
    .catch((e) => ({ batch, result: null, error: e }))
}

const { results: triageResults, retried: triageRetried, recovered: triageRecovered } =
  await runBatchesWithRetry(triageBatches, dispatchTriageBatch)

if (triageRetried) {
  log(`issue-wheel-triage: Triage retry -> retried ${triageRetried}, recovered ${triageRecovered}.`)
}

// Mirrors Screen's own already-correct contract (see the Screen phase below):
// a missing/malformed agent() return is a FAILURE for every item in that
// batch, never a silent pass-through to an empty array. Plan: H2 "Design --
// the failure-surfacing half" -- Triage and Verify previously swallowed a
// failed batch into `[]` via `.then((r) => (r && Array.isArray(r.items)) ?
// r.items : [])`, silently vanishing those issues from the run entirely with
// no signal in totals. Screen's own site is untouched by this commit. GH
// #4767 WS14-S1 item 1d: a batch reaching this loop as a failure either (a)
// threw on its one and only attempt (never retried, per the design change),
// or (b) was null/malformed on both the first pass AND its retry --
// buildFailureReason() (above runBatchesWithRetry) tells the two apart and
// cites both reasons for case (b) (nit 10).
function triageBaseReason(result, error) {
  return (result === null && error)
    ? `TRIAGE_ERROR: agent call rejected: ${error.message}`
    : 'TRIAGE_ERROR: empty or malformed agent return'
}
const triageBatchFailures = []
const triagedFromBatches = []
for (let i = 0; i < triageResults.length; i++) {
  const settlement = triageResults[i]
  const { result } = settlement
  if (!result || !Array.isArray(result.items)) {
    triageBatchFailures.push({ phase: 'Triage', batch_index: i, reason: buildFailureReason(settlement, triageBaseReason) })
    continue
  }
  triagedFromBatches.push(...result.items)
}

// Dedupe rows by number, first verdict wins.
const seenNumbers = new Set()
const triagedFlat = []
for (const item of triagedFromBatches) {
  if (!item || typeof item.number !== 'number') continue
  if (seenNumbers.has(item.number)) continue
  seenNumbers.add(item.number)
  triagedFlat.push(item)
}

// Schema-change enforcement: an already_done with no valid hex sha routes to
// unclear, never to a close. Same defensive floor for not_doing/duplicate's
// required citation fields, since a schema-conformant model can still return an
// empty string for a "required" field.
//
// code-reviewer blocker: an OFF-ENUM verdict (a value outside VERDICTS --
// the JSON schema's `enum` is model-advisory, not a hard guarantee; a model
// can still return a string that never matches it) previously fell through
// every branch below and was silently dropped from ALL of totals/
// verdicts_close_class/needs_work/operator_only/unclear -- present only in
// totals.triaged_count, absent from every returned array. That contradicts
// this script's own "never silently dropped" invariant (plan section 4/6)
// and this exact same defensive pattern already applied to a MISSING
// required field. Routed to unclear here, same as the other three
// defensive-floor cases, so it always lands in exactly one bucket.
const unclearFallback = []
for (const item of triagedFlat) {
  if (!VERDICTS.includes(item.verdict)) {
    unclearFallback.push(item.number)
    item.rationale = `${item.rationale || ''} [routed to unclear: off-enum verdict ${JSON.stringify(item.verdict)}]`.trim()
    item.verdict = 'unclear'
  } else if (item.verdict === 'already_done' && !(typeof item.cited_fix_sha === 'string' && SHA_RE.test(item.cited_fix_sha)) ) {
    unclearFallback.push(item.number)
    item.verdict = 'unclear'
    item.rationale = `${item.rationale || ''} [routed to unclear: already_done had no valid hex cited_fix_sha]`.trim()
  } else if (item.verdict === 'not_doing' && !(typeof item.superseded_by === 'string' && item.superseded_by.trim())) {
    unclearFallback.push(item.number)
    item.verdict = 'unclear'
    item.rationale = `${item.rationale || ''} [routed to unclear: not_doing had no superseded_by citation]`.trim()
  } else if (item.verdict === 'duplicate' && !(typeof item.duplicate_of === 'string' && item.duplicate_of.trim())) {
    unclearFallback.push(item.number)
    item.verdict = 'unclear'
    item.rationale = `${item.rationale || ''} [routed to unclear: duplicate had no duplicate_of citation]`.trim()
  }
}

log(`issue-wheel-triage: triage produced ${triagedFlat.length} deduped verdict(s)` +
    (unclearFallback.length ? `, ${unclearFallback.length} routed to unclear for a missing required citation.` : '.'))

// =============================================================================
// Phase 2 -- Verify. DEFAULT-REFUTE over close-class verdicts only. 4/agent.
// =============================================================================
phase('Verify')

const closeClassItems = triagedFlat.filter((item) => CLOSE_CLASS_VERDICTS.includes(item.verdict))
const nonCloseClassItems = triagedFlat.filter((item) => !CLOSE_CLASS_VERDICTS.includes(item.verdict))

log(`issue-wheel-triage: verifying ${closeClassItems.length} close-class verdict(s), batched ${VERIFY_BATCH_SIZE}/agent.`)

const verifyBatches = chunk(closeClassItems, VERIFY_BATCH_SIZE)

// The single Verify agent() call site (GH #4767 WS14-S1 item 1d -- see the
// matching Triage comment above for why this is factored out).
function dispatchVerifyBatch(batch, i, isRetry) {
  return agent(`${BRIEF}

YOUR ROLE THIS ROUND: adversarially VERIFY a batch of close-class triage
verdicts (already_done / not_doing / duplicate only). Default to REFUTE --
set refuted=true unless you can positively CONFIRM the verdict is correct by
re-deriving it yourself (open the issue again, check the cited sha/reference
actually exists and actually resolves what it claims).

If your own tooling fails (gh unavailable, a lookup errors out) -- report that
honestly by prefixing evidence_checked with "VERIFIER_ERROR:" and set
refuted=true. A tooling failure must NEVER be reported as a genuine
refutation of the verdict's substance -- it is a distinct failure mode, and the
VERIFIER_ERROR: prefix is how the caller tells the two apart.

If you refute a verdict but do not know the correct handling, leave
'correction' empty -- an unresolved refutation with no correction means the
item is left untouched, not silently reassigned.

BATCH TO VERIFY (each already carries the triage agent's claimed verdict and
citation -- treat as an unverified claim, not as evidence):
${JSON.stringify(batch, null, 2)}`,
    { label: `verify:${i + 1}${isRetry ? ':retry' : ''}`, phase: 'Verify', model: 'sonnet', schema: VERIFY_SCHEMA, agentType: 'explore' })
    .then((r) => ({ batch, result: r }))
    .catch((e) => ({ batch, result: null, error: e }))
}

const { results: verifyResults, retried: verifyRetried, recovered: verifyRecovered } =
  await runBatchesWithRetry(verifyBatches, dispatchVerifyBatch)

if (verifyRetried) {
  log(`issue-wheel-triage: Verify retry -> retried ${verifyRetried}, recovered ${verifyRecovered}.`)
}

// Same failure-surfacing contract as Triage above, mirroring Screen's
// already-correct shape: a missing/malformed agent() return fails every item
// in that batch rather than silently vanishing it. Downstream of this loop,
// an item with no matching verifyByNumber entry already falls into the
// conservative `refuted` bucket below (unchanged) -- so a lost Verify batch
// was already partially safe (over-refutation, never a silent close); this
// addition makes that loss VISIBLE in totals too, not just safe. GH #4767
// WS14-S1 item 1d: a batch reaching this loop as a failure either threw on
// its one and only attempt (never retried, per the design change) or was
// null/malformed on both the first pass and its retry -- see
// buildFailureReason() above runBatchesWithRetry.
function verifyBaseReason(result, error) {
  return (result === null && error)
    ? `VERIFY_ERROR: agent call rejected: ${error.message}`
    : 'VERIFY_ERROR: empty or malformed agent return'
}
const verifyBatchFailures = []
const verifyFlat = []
for (let i = 0; i < verifyResults.length; i++) {
  const settlement = verifyResults[i]
  const { result } = settlement
  if (!result || !Array.isArray(result.items)) {
    verifyBatchFailures.push({ phase: 'Verify', batch_index: i, reason: buildFailureReason(settlement, verifyBaseReason) })
    continue
  }
  for (const item of result.items) {
    if (!item || typeof item.number !== 'number') continue
    verifyFlat.push(item)
  }
}
const verifyByNumber = new Map(verifyFlat.map((v) => [v.number, v]))

const refuted = []
const verifierErrors = []
const verdictsCloseClass = []

for (const item of closeClassItems) {
  const v = verifyByNumber.get(item.number)
  if (!v) {
    // No verdict returned for this item -- treat conservatively as unverified,
    // never as a silent pass-through to a close.
    refuted.push({ number: item.number, item, correction: null, reason: 'no verifier verdict returned' })
    continue
  }
  const isVerifierError = typeof v.evidence_checked === 'string' && v.evidence_checked.startsWith('VERIFIER_ERROR:')
  if (isVerifierError) {
    verifierErrors.push({ number: item.number, item, evidence_checked: v.evidence_checked })
    continue
  }
  if (v.refuted) {
    refuted.push({ number: item.number, item, correction: v.correction || null, evidence_checked: v.evidence_checked })
    continue
  }
  verdictsCloseClass.push(item)
}

log(`issue-wheel-triage: verify -> ${verdictsCloseClass.length} confirmed, ${refuted.length} refuted, ${verifierErrors.length} verifier error(s).`)

// =============================================================================
// Phase 3 -- Screen. Structural only, 20/agent, over needs_work items.
// An empty agent return is a SCREEN FAILURE, never a pass.
// =============================================================================
phase('Screen')

const needsWorkCandidates = nonCloseClassItems.filter((item) => item.verdict === 'needs_work')
log(`issue-wheel-triage: screening ${needsWorkCandidates.length} needs_work item(s), batched ${SCREEN_BATCH_SIZE}/agent.`)

const screenBatches = chunk(needsWorkCandidates, SCREEN_BATCH_SIZE)

// The single Screen agent() call site (GH #4767 WS14-S1 item 1d -- see the
// matching Triage/Verify comment above for why this is factored out).
//
// Follow-up 4 fix (code review round 2, pre-existing bug, not introduced by
// this round): this site previously had NO `.catch`, unlike Triage/Verify.
// A thrown agent() call therefore reached the host's real `parallel()` as a
// REJECTED promise. The real host (CLI 2.1.197) implements `parallel()` on
// `Promise.allSettled`, and maps a rejected slot to a bare `null` with no
// `error` -- so a thrown, uncaught Screen call settles as `null`, not an
// `{result, error}` object, and `const { result } = screenResults[i]`
// downstream, and now `runBatchesWithRetry`'s own `const { result, error }
// = results[i]`, would throw a TypeError destructuring `null`, taking all
// of P1 down with it. Adding the same `.catch` shape Triage/Verify already
// have closes this -- a thrown Screen call now settles as
// `{batch, result: null, error}`, exactly like every other phase.
function dispatchScreenBatch(batch, i, isRetry) {
  return agent(`${BRIEF}

YOUR ROLE THIS ROUND: STRUCTURAL screening only, over a batch of needs_work
triage items. For each issue number in your batch, check:
  1. Is it still open right now (re-check, do not trust the triage pass)?
  2. Do the files_touched it names actually exist at HEAD?
  3. Is size_points present, with a reason in rationale that cites a path or
     symbol you (or the triage agent) actually read?

Return pass=true only if ALL three hold. Otherwise pass=false with a
fail_reason -- use 'stale: closed by another lane' specifically when the issue
closed between triage and now (this is how concurrent-lane staleness across a
batch gets caught).

BATCH TO SCREEN:
${JSON.stringify(batch, null, 2)}`,
    { label: `screen:${i + 1}${isRetry ? ':retry' : ''}`, phase: 'Screen', model: 'sonnet', schema: SCREEN_SCHEMA, agentType: 'explore' })
    .then((r) => ({ batch, result: r }))
    .catch((e) => ({ batch, result: null, error: e }))
}

// GH #4767 WS14-S1 item 1d: same bounded one-retry-in-waves as Triage/Verify.
// runBatchesWithRetry's retry-ELIGIBILITY rule (null/non-object result, no
// thrown error) already never retries a valid-but-EMPTY `items: []` return
// -- that is a truthy, array-typed result, so it is never null/non-object --
// so Screen's own separate, stricter "empty is a fail" rule below correctly
// stays unretried on its OWN, exactly as before (finding 7: an `[]` on the
// first pass is never retried). Screen's own `isSuccess` predicate (passed
// below) additionally makes sure a RETRY that comes back `[]` is not
// wrongly counted as `recovered` (nit 9) -- Screen's downstream loop below
// still treats a length-0 `items` as a failure regardless of whether the
// settlement it is reading was ever retried.
const { results: screenResults, retried: screenRetried, recovered: screenRecovered } = await runBatchesWithRetry(
  screenBatches,
  dispatchScreenBatch,
  (result) => Array.isArray(result && result.items) && result.items.length > 0
)

if (screenRetried) {
  log(`issue-wheel-triage: Screen retry -> retried ${screenRetried}, recovered ${screenRecovered}.`)
}

// GH #4767 WS14-S1 item 1d: Screen's own reason format, used both for a
// null/malformed settlement (Triage/Verify's own shape) and for the
// genuinely-empty-but-valid `items: []` shape that is Screen's OWN stricter
// failure rule (never Triage/Verify's). buildFailureReason() only cites
// BOTH the first-pass and retry reason when the settlement actually carries
// `firstError`/`firstResult` (i.e. it went through a null/malformed retry);
// an `items: []` outcome (first pass or post-retry) was never retry-eligible
// so it never carries those keys, and this returns just the single reason,
// unchanged from before this round.
function screenBaseReason(result, error) {
  if (result === null && error) return `SCREEN_ERROR: agent call rejected: ${error.message}`
  // Covers both shapes: null/malformed (no `items` array at all) and the
  // genuinely-empty-but-valid `items: []` case -- Screen's own downstream
  // loop treats both identically ("empty agent return"), so this reason
  // string is deliberately the same for either.
  return 'SCREEN_ERROR: empty agent return'
}

const needsWorkPass = []
const needsWorkScreenFailed = []

for (const settlement of screenResults) {
  const { batch, result } = settlement
  // Reversed vs. issue-burndown.js's :311 fallback: an empty/missing agent
  // return is a FAILURE for every item in that batch, not a pass-through.
  if (!result || !Array.isArray(result.items) || result.items.length === 0) {
    const fail_reason = buildFailureReason(settlement, screenBaseReason)
    for (const item of batch) {
      needsWorkScreenFailed.push({ number: item.number, item, fail_reason })
    }
    continue
  }
  const byNumber = new Map(result.items.filter((r) => r && typeof r.number === 'number').map((r) => [r.number, r]))
  for (const item of batch) {
    const s = byNumber.get(item.number)
    if (!s) {
      needsWorkScreenFailed.push({ number: item.number, item, fail_reason: 'SCREEN_ERROR: no screen verdict returned for this item' })
      continue
    }
    if (s.pass) {
      needsWorkPass.push(item)
    } else {
      needsWorkScreenFailed.push({ number: item.number, item, fail_reason: s.fail_reason || 'unspecified structural failure' })
    }
  }
}

log(`issue-wheel-triage: screen -> ${needsWorkPass.length} passed, ${needsWorkScreenFailed.length} screen-failed.`)

// =============================================================================
// Phase 4 -- Lane pre-filter. Plain JS, NO-LLM predicates. Tags trust-surface
// rather than excluding it (it routes the reviewer later, per plan section 4).
// =============================================================================

// code-reviewer blocker: TRUST_SURFACE_PATH_RE's four paths (modules/billing,
// modules/licensing, modules/stripe_module, firestore.rules) were a STRICT
// SUBSET of PRICING_PATH_RE's broader (unqualified) billing/stripe_module/
// licensing match and DEPLOY_PATH_RE's firestore.rules match -- every path
// that could ever satisfy isTrustSurface() was therefore ALSO excluded by
// touchesPricing()/isDeployGated() first, so laneReady never carried a
// trust_surface:true item and the "TAGGED, NOT EXCLUDED" reviewer-routing
// this exists to feed (plan section 4 item 4: "trust-architect reviewer-of-
// record OR park") was structurally unreachable. Fixed by carving the four
// trust-surface paths OUT of the broader pricing/deploy exclusions -- they
// still get pre-filtered for other reasons where applicable, but never
// specifically as "pricing"/"deploy-gated" when the REAL reason a later
// reviewer needs to know about is "trust-surface." This is a placeholder
// path list -- plan section 8 names the real source as a per-repo
// `trust_surface_prefixes` in `wheel_repos.json` (not built until a later
// commit); this hardcoded regex is deliberately narrow and will be replaced
// once that config exists, never widened casually in the meantime.
const TRUST_SURFACE_PATH_RE = /(^|\/)(modules\/billing|modules\/licensing|modules\/stripe_module|firestore\.rules)(\/|$)?/i
const PRICING_PATH_RE = /(^|\/)(pricing|billing|stripe_module|licensing)(\/|$)/i
const CATALOG_PATH_RE = /(^|\/)(catalog|catalog_rules)(\/|$)/i
const DEPLOY_PATH_RE = /(cloudbuild|gcp_cicd|deploy|firestore\.rules|storage\.rules)/i

function isPricingExcludedNotTrustSurface(path) {
  return PRICING_PATH_RE.test(path) && !TRUST_SURFACE_PATH_RE.test(path)
}

function isDeployExcludedNotTrustSurface(path) {
  return DEPLOY_PATH_RE.test(path) && !TRUST_SURFACE_PATH_RE.test(path)
}

function isFrontendPath(path) {
  if (typeof path !== 'string') return false
  const parts = path.split('/')
  return parts.includes('frontend') || path.startsWith('shared_frontend/') || path.includes('/shared_frontend/')
}

function hasNoFootprint(item) {
  return !Array.isArray(item.files_touched) || item.files_touched.length === 0
}

function touchesLoopHeld(item) {
  if (!Array.isArray(item.files_touched)) return false
  return item.files_touched.some((f) => LOOP_HELD_PATHS.includes(f))
}

function touchesDirty(item) {
  if (!Array.isArray(item.files_touched)) return false
  return item.files_touched.some((f) => DIRTY_PATHS.includes(f))
}

function isFrontendNoRunner(item) {
  if (!Array.isArray(item.files_touched)) return false
  return item.files_touched.some((f) => isFrontendPath(f))
}

function isDocsOnlyNoTest(item) {
  if (!Array.isArray(item.files_touched) || item.files_touched.length === 0) return false
  const allDocs = item.files_touched.every((f) => typeof f === 'string' && (f.endsWith('.md') || f.endsWith('.html')))
  const hasTest = item.files_touched.some((f) => typeof f === 'string' && (f.includes('/test') || f.includes('_test.') || f.includes('/tests/')))
  return allDocs && !hasTest
}

function touchesPricing(item) {
  return Array.isArray(item.files_touched) && item.files_touched.some((f) => isPricingExcludedNotTrustSurface(f))
}

function touchesCatalogRuling(item) {
  return Array.isArray(item.files_touched) && item.files_touched.some((f) => CATALOG_PATH_RE.test(f))
}

function isDeployGated(item) {
  return Array.isArray(item.files_touched) && item.files_touched.some((f) => isDeployExcludedNotTrustSurface(f))
}

function isZeroDescendantEpic(item) {
  return item.size_points === 0 && typeof item.rationale === 'string' && /epic/i.test(item.rationale)
}

function hasUnresolvedSupersession(item) {
  return typeof item.rationale === 'string' && /supersed/i.test(item.rationale) && !item.superseded_by
}

function isTrustSurface(item) {
  return Array.isArray(item.files_touched) && item.files_touched.some((f) => TRUST_SURFACE_PATH_RE.test(f))
}

// Still within the 'Screen' phase (meta.phases lists exactly Triage/Verify/
// Screen -- the lane pre-filter below is plain JS with no agent calls, so it
// is not a distinct dispatch phase in its own right; it is the deterministic
// tail of Screen, not a re-entry into an earlier phase).
log('issue-wheel-triage: applying plain-JS lane pre-filters to screened needs_work items (no LLM calls).')

const laneReady = []
const lanePrefilterExcluded = []

for (const item of needsWorkPass) {
  const reasons = []
  if (hasNoFootprint(item)) reasons.push('no-footprint')
  if (touchesLoopHeld(item)) reasons.push('loop-held')
  if (touchesDirty(item)) reasons.push('dirty-path')
  if (isFrontendNoRunner(item)) reasons.push('frontend-no-runner')
  if (isDocsOnlyNoTest(item)) reasons.push('docs-only-no-test')
  if (touchesPricing(item)) reasons.push('pricing')
  if (touchesCatalogRuling(item)) reasons.push('catalog-ruling')
  if (isDeployGated(item)) reasons.push('deploy-gated')
  if (isZeroDescendantEpic(item)) reasons.push('zero-descendant-epic')
  if (hasUnresolvedSupersession(item)) reasons.push('unresolved-supersession')

  // trust-surface is TAGGED, never excluded -- it routes the reviewer later.
  const trustSurface = isTrustSurface(item)
  const tagged = { ...item, trust_surface: trustSurface }

  if (reasons.length) {
    lanePrefilterExcluded.push({ number: item.number, item: tagged, exclude_reasons: reasons })
  } else {
    laneReady.push(tagged)
  }
}

log(`issue-wheel-triage: lane pre-filter -> ${laneReady.length} lane-ready, ${lanePrefilterExcluded.length} excluded.`)

// =============================================================================
// Return -- schema-shaped, nothing written.
// No Order/Rank phase: ordering is P4's job outside this script, deterministic.
// =============================================================================

const operatorOnly = triagedFlat.filter((item) => item.verdict === 'operator_only')
const unclear = triagedFlat.filter((item) => item.verdict === 'unclear')

// Combined per-batch failure telemetry across all three fan-out phases (plan:
// H2 "Design -- the failure-surfacing half"). Screen's own batch-failure
// list is derived here from its pre-existing, UNCHANGED {batch, result}
// results -- this reads screenResults, it does not alter Screen's own loop
// or its needsWorkScreenFailed contract in any way. A batch is "failed" the
// same way each phase already defines it: Triage/Verify -- a missing or
// malformed agent() return; Screen -- its own existing empty-or-malformed-
// or-zero-length-items rule.
//
// One {phase, batch_index, reason} entry per failed Screen batch -- mirrors
// the Triage/Verify sites exactly (triageBatchFailures / verifyBatchFailures
// above), so reasons.length always equals failed, per the field's own
// documented contract. A prior version of this block collapsed every failed
// Screen batch into a single reasons-array entry regardless of how many
// batches failed, which desynced reasons.length from failed for >1 failed
// Screen batch.
const screenBatchFailures = screenResults
  .map((settlement, i) => (
    (!settlement.result || !Array.isArray(settlement.result.items) || settlement.result.items.length === 0)
      ? { phase: 'Screen', batch_index: i, reason: buildFailureReason(settlement, screenBaseReason) }
      : null
  ))
  .filter(Boolean)

const triageBatchesTotal = triageBatches.length + verifyBatches.length + screenBatches.length
const triageBatchesFailed = triageBatchFailures.length + verifyBatchFailures.length + screenBatchFailures.length
const triageBatchesReasons = [
  ...triageBatchFailures.map((f) => f.reason),
  ...verifyBatchFailures.map((f) => f.reason),
  ...screenBatchFailures.map((f) => f.reason),
]
// GH #4767 WS14-S1 item 1d: additive-only new fields, combined across all
// three phases exactly like total/ok/failed/reasons above. `failed`/`ok`
// above already reflect the state AFTER each phase's retry (they are
// computed from triageBatchFailures/verifyBatchFailures/screenBatchFailures,
// which are themselves derived from the post-retry triageResults/
// verifyResults/screenResults) -- retried/recovered are reported alongside
// as a NEW pair of keys, never a rename or removal of any existing key
// (RULE G-BATCH-LOSS in schedules/prompts/issue_wheel.txt reads `failed /
// total`, unchanged by this addition).
const triageBatchesRetried = triageRetried + verifyRetried + screenRetried
const triageBatchesRecovered = triageRecovered + verifyRecovered + screenRecovered

const totals = {
  seed_count: ISSUES.length,
  triaged_count: triagedFlat.length,
  close_class_count: closeClassItems.length,
  verified_close_class_count: verdictsCloseClass.length,
  refuted_count: refuted.length,
  verifier_error_count: verifierErrors.length,
  needs_work_count: needsWorkCandidates.length,
  needs_work_screened_pass_count: needsWorkPass.length,
  needs_work_screen_failed_count: needsWorkScreenFailed.length,
  lane_ready_count: laneReady.length,
  lane_prefilter_excluded_count: lanePrefilterExcluded.length,
  operator_only_count: operatorOnly.length,
  unclear_count: unclear.length,
  triage_batches: {
    total: triageBatchesTotal,
    ok: triageBatchesTotal - triageBatchesFailed,
    failed: triageBatchesFailed,
    reasons: triageBatchesReasons,
    retried: triageBatchesRetried,
    recovered: triageBatchesRecovered,
  },
}

log(`issue-wheel-triage: DONE. ${JSON.stringify(totals)}`)

return {
  totals,
  verdicts_close_class: verdictsCloseClass,
  needs_work: laneReady,
  needs_work_screen_failed: needsWorkScreenFailed,
  operator_only: operatorOnly,
  unclear,
  refuted,
  verifier_errors: verifierErrors,
  lane_prefilter_excluded: lanePrefilterExcluded,
}
