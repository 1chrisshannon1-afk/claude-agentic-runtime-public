# GTM missions — schema reference

This is the runtime-level schema reference for the GTM (go-to-market) marketing/sales
department's mission artifacts, launched via `/gtm "<goal>"` (`~/.claude/skills/gtm/SKILL.md`)
and run by the `marketing-director` agent per the department roster (`~/.claude/CLAUDE.md` §13)
and its own primer (`~/.claude/knowledge/marketing_director_primer.md`). The artifacts themselves
— the mission JSON files and the shared dissent ledger — live in the calling repo's own
`gtm.missions_dir` (`python3 ~/.claude/scripts/repo_manifest.py get gtm.missions_dir`), never in
the runtime. This document is the schema; the ledger's own directory is repo-local and never
exported to the runtime mirror or any other repo.

`marketing-director` is the **sole writer** of every file in `gtm.missions_dir` — specialist
seats never write there directly; they return findings to the director, which records them.

## Mission file: `<mission_id>.json`

Mission id format: `gtm_<YYYY_MM_DD>_<slug>` (e.g. `gtm_2026_09_05_website_conversion_pass`). If a
mission id already exists, the director refuses and asks the launcher for a new slug — ids are
never silently suffixed.

```jsonc
{
  "mission_id": "gtm_2026_09_05_website_conversion_pass",
  "goal_verbatim": "highly converting website for the established audience",
  "clarify_questions": [
    {
      "question": "Which of the 5 /lp/* variants should the mission treat as canonical?",
      "tag": "REPO",              // REPO | RESEARCHABLE | ANSWERED-IN-A-RULED-DOC | OPERATOR
      "asked_of": null,            // seat name if RESEARCHABLE, else null
      "answer": "..."              // filled in once resolved; null while open
    }
  ],
  "operator_answers": [
    {
      "question": "...",           // verbatim question as presented on the decision card
      "answer_verbatim": "...",    // the operator's own words, never paraphrased
      "card_id": "...",            // the operator-input surface's own card id
      "ts": "2026-09-05T18:00:00Z"
      // "applied_as": {...}       // OPTIONAL extra key — how the director mapped a single
                                    // multi-part answer onto the mission's own open items; the
                                    // base schema above has no field for this, so it lives here
                                    // as a permitted addition rather than being dropped
    }
  ],
  "plan": {
    "summary": "...",
    "success_criteria": ["..."],   // mirrored into success_criteria[] below for evaluator use
    "approved_by_operator": true,
    "approved_ts": "2026-09-05T19:00:00Z"
  },
  "success_criteria": ["..."],
  "dispatches": [
    {
      "agent_type": "conversion-architect",   // the seat or landing agent dispatched
      "tool_use_id": "toolu_...",             // the Agent call's tool_use_id, verbatim
      "phase": "produce",                      // optional: clarify | plan | produce | converge | landing
      "round": 1                               // optional
    }
  ],
  "rounds": [
    {
      "round": 1,
      "artifacts_produced": ["artifact_id", "..."],
      "cross_review_summary": "...",
      "fix_wave": ["..."]
    }
  ],
  "artifacts": [
    {
      "artifact_id": "...",
      "seat": "conversion-architect",
      "kind": "SPEC",             // SPEC | DRAFT | FINDING | CHANGED | PUBLISHED | BLOCKER | RULING |
                                  // CORRECTION | CLEARED | screenshot_library | illustration_library |
                                  // renderer | rendered_manifest | tests — widened 2026-09-14 (#5441):
                                  // the non-SPEC/DRAFT kinds are OUTCOME/JOURNAL records (a post actually
                                  // published, a blocker actually hit, a deliverable actually produced),
                                  // each still carrying every mandatory field below; relabelling them SPEC
                                  // would misstate evidence. The product repo's conformance test embeds
                                  // this exact list — change both in the same change, never one alone.
      "file_paths": ["marketing/website/templates/index.html"],
      "current_state": "...",
      "intended_state": "...",
      "success_criterion": "...",
      "evidence": "..."
    }
  ],
  "status": "clarify"             // clarify | planned | producing | converging | presented | halted | in_progress
                                  // (`in_progress` admitted 2026-09-14, #5441, so a normalized record's
                                  // preserved `original_status` stays a schema-valid value and for forward
                                  // compatibility; no live mission carries it at top level today — new
                                  // missions use the phase-named value `producing`)
}
```

Field notes:
- **Additive keys a normalization may carry (permitted, never required — the same standing as
  `applied_as` above):** when a product repo normalizes an evidence record's SHAPE to this schema
  (#5441, 2026-09-14), it preserves the original facts alongside: `original_status` (top-level,
  the status value as first recorded), `status_normalization_note` (top-level, why it was mapped),
  `original_shape` (per artifact, e.g. `"{path, kind, note}"`), and `seat_provenance` (per
  artifact — states that `seat` is the recorder's attribution, not a recorded fact, when the
  original entry carried no seat). A stricter validator must accept these; a normalization must
  never change a factual field.
- `clarify_questions[].tag` follows the four-way taxonomy the director's primer defines: **REPO**
  (the director/seat reads it directly), **RESEARCHABLE** (routed to `market-analyst` for
  market/competitor facts or `research-scout` for tools/OSS/prior-art — see the fence lines in
  both agents' dossiers), **ANSWERED-IN-A-RULED-DOC** (the answer already exists in a repo-local
  ruled doc; read it, never card the operator, the reopen rule binds), or **OPERATOR** (taste,
  spend, identity, judgment — genuinely needs the operator).
  Operator residue lands on the calling repo's own operator-input surface (`repo_manifest.py get
  operator_input`; when that key is `null`, the fallback queue
  `<gtm.missions_dir>/OPERATOR_QUEUE.md` — see the marketing-director primer's operator-surface
  paragraph) as ONE batched, numbered card set — never as separate ad-hoc questions. Operator
  TASKS discovered here (something to DO, not decide) go to whatever tracker doc the repo manifest
  names (`tracker_doc`), never mixed into this schema.
- `artifacts[]` follows the PRODUCE-phase spec contract (director primer §2): exact file paths ·
  CURRENT state · intended state · success criterion · evidence. A spec missing any of these
  fields is refused, not accepted incomplete.
- `dispatches[]` (REQUIRED): one entry per `Agent` call the director makes, carrying at minimum
  `agent_type` + the dispatch's `tool_use_id` verbatim, recorded AS each dispatch is made (never
  reconstructed at mission end). This is what makes a mission's cost verifiable against the
  runtime spend ledger (`~/.claude/.agent_budget/spend.jsonl`) — without a declared dispatch
  identity the correspondence is unbackfillable once missions accumulate.
  **Fallback identity rule:** the `Agent` tool's result surfaces only an `agentId`, so a director
  can only fill `tool_use_id` via the spend-ledger join — and that join can silently fail. When it
  does, the director records the dispatch's `agent_id` verbatim (with `tool_use_id: null` and an
  `identity_note` saying why) rather than guessing a plausible `toolu_...` or leaving a bare
  placeholder; an `agent_id` row is joinable if the ledger is ever backfilled, and an honest gap
  beats an unverifiable fake in a cost-attribution field.
- `status` values map to the mission lifecycle stages; `halted` is set by the dispatching session
  (not the director itself) after an operator or session-issued `TaskStop` on the director's task.

## Dissent ledger: `gtm_reviewed.jsonl`

One shared file for the whole department, written ONLY by `marketing-director` from returned
seat findings (single writer; seats never append; no concurrent writes). One JSON object per
line, one line per `(artifact_id, judge)` pair per round:

```jsonc
{"mission_id": "gtm_2026_09_05_website_conversion_pass", "round": 1, "artifact_id": "spec-004", "judge": "brand-architect", "verdict": "DISSENT", "severity": "major", "cause_key": "stale_pricing_copy", "evidence": "marketing/website/templates/index.html:384-546 cites the pre-09-04 ladder", "ts": "2026-09-05T20:00:00Z"}
```

Field notes:
- `verdict` ∈ `CONCUR` | `DISSENT`.
- `severity` ∈ `blocker` | `major` | `minor` (present on both verdicts; a CONCUR still carries a
  severity field, typically irrelevant but structurally required for uniform parsing).
- `cause_key` — a short, stable string clustering findings by root cause. This is a department-
  local key space — never looked up against any other loop's own cause registry.
- **A DISSENT stays OPEN until a later row for the SAME `(artifact_id, judge)` pair records
  CONCUR.** There is no other way to close a dissent — a later round simply not re-mentioning it is
  NOT closure.
- **Evidence-or-refuse:** a DISSENT row without a resolvable `evidence` field is refused at parse
  time by the evaluator (`~/.claude/tools/gtm/exit_contract.py`) — it is never silently counted as
  a valid dissent. A round where more than 50% of its DISSENT rows lack resolvable evidence is
  marked `DEGRADED-GROUNDING` by the evaluator (computed mechanically, never claimed by an agent)
  and presented as such alongside the round's verdict.

## The evaluator (mechanical convergence — never an agent's own claim)

`~/.claude/tools/gtm/exit_contract.py` reads this ledger for one mission + round window and
prints `GTM convergence: N of 3 assertions met` (or `UNEVALUABLE: <reason>` when the ledger is
missing, empty, or contains a malformed line — never a silent "met" in that case; exit 2 on
UNEVALUABLE, exit 3 on manifest/resolver failure). Assertion ids
are `GTM-CONV-01/02/03` **everywhere** in any GTM artifact — the bare `CONV-0N` form may be
reserved elsewhere (a product repo's own, unrelated estimate loop may own that bare namespace with
different semantics) and must never be used here. Full assertion definitions and test coverage:
`~/.claude/tools/gtm/tests/test_gtm_exit_contract.py`.

The evaluator's `--ledger` CLI flag defaults to `<gtm.missions_dir>/gtm_reviewed.jsonl`, resolved
at runtime from the calling repo's manifest — it never hardcodes a product-repo path. Pass
`--ledger <path>` explicitly to point at a different ledger (e.g. a test fixture).

**The unverified-consensus failure class (GH #4893's provenance):** this evaluator's own
GTM-CONV-03 assertion exists specifically because a DIFFERENT, unrelated evaluator once reported
"3 of 3 met" over a ledger holding 9 real open dissents, because it never actually read verdict
fields — a mechanical convergence check that doesn't check convergence is worse than no check at
all, since it launders an agent's own unverified claim of consensus into something that LOOKS
mechanically verified. `test_4893_shaped_open_dissents_never_report_met` in this module's test
suite is the standing regression guard against that exact class recurring here.

## Rollout posture

Early missions may run the evaluator report-only (its verdict is presented verbatim alongside the
director's own judgment, and only the operator may accept a mission whose evaluator reports N<3);
a mature department makes a `not met` verdict mechanically block PRESENT. Which posture is live
for a given repo is a decision recorded in that repo's own mission history, not in this schema.
