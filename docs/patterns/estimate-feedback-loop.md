# The estimate feedback loop (theory only)

The author's remodeling-estimate product runs a team of domain agents that review the estimating
engine's output and feed fixes back into it. **The agents, their prompts, the trade knowledge base,
the engine and the loop's code are not part of this repository** — they are product IP and stay
private. This page explains the idea, so you can build your own version for any domain where an
engine produces confident numbers that only an expert can check.

## The problem it solves

A deterministic estimating engine never crashes on a bad estimate. It prints a clean, plausible
total that is wrong because a catalog row has the wrong unit, a rule fires for the wrong job, or a
needed line is missing. Unit tests catch code bugs; they do not catch "a tile setter would laugh at
this." The errors are domain errors, they are silent, and there are too many job combinations for a
person to review by hand.

## The team

| Role | What it does | What it never does |
|---|---|---|
| **General contractor (GC)** — orchestrator, strongest model | The only agent the operator talks to. Decides which trades see which estimate, checks their answers, merges them into root causes, and reports. | Edit code or data. |
| **Trade specialists** — one per trade (for example tile, plumbing, electrical), cheaper model | Answer only questions in their own trade. Every claim cites a source document or is marked UNVERIFIED. | Answer outside their lane, guess, or fix anything. |
| **Engine architect** — strongest model | Diagnoses how the engine produced a verified defect and specifies the fix. | Edit code, or decide what is correct for a trade. |
| **Knowledge verifier** | Checks that a cited source actually says what the specialist claimed. | Add opinions of its own. |
| **Measurement specialist** | Judges the design of how photos and measurements become quantities. | Edit code. |

The split mirrors a real job site: the GC knows what done-right looks like and how trades interact;
each trade knows its own depth. Keeping each specialist inside one lane is what makes its answers
checkable.

## One round of the loop

1. **Generate** a fixed, versioned set of job scenarios through the real engine.
2. **Group** scenarios whose outputs are identical and review each group once. This cuts review cost
   without hiding a change, because the grouping key includes every field that can move a price.
3. **Route.** For cheap exploratory passes, send each estimate only to the trades its inputs
   involve. A round that counts toward finishing sends every scenario to every required trade,
   because a broken routing map hides exactly the omissions it causes.
4. **Review.** Each trade returns a structured verdict. A finding with no citation is discarded, not
   softened.
5. **Consolidate.** The GC merges findings into root causes and matches each against a registry of
   known causes, so the same defect is never filed twice under new names.
6. **Fix.** The engine architect diagnoses and specifies the fix, a human approves it, and a
   separate implementer agent writes it, test first. No reviewer edits.
7. **Record.** An append-only ledger records which scenarios each judge found clean, so the next
   round knows what regressed.

## When the loop is done

"Nothing new found" is never accepted from the agents that did the finding. Convergence is
computed offline from the recorded ledgers by a separate evaluator:

- a round counts only if every required judge reviewed every scenario in the set and every judge
  agrees on every scenario, with no open dissent;
- every round answers a fixed list of operator questions ("lenses"), so a reviewer cannot skip the
  uncomfortable ones;
- prices are cross-checked across scenarios for outliers;
- one such clean round stops the loop. Its results go to a person for manual review, and the person
  decides what happens next. The loop never widens its own scenario set.

Adding a new trade never re-grades old rounds: each round is judged against the roster that ran it.

## What made it work

- **Cite or discard.** Agents invent plausible trade "facts." Requiring a source, and a separate
  verifier for the source, removed most of that.
- **The operator's rulings outrank the agents.** When a finding conflicts with a recorded ruling,
  it is flagged as a conflict for the operator, never "fixed" by the agent.
- **Reviewers return findings; they never edit.** A separate implementer makes every change. The same rule as this runtime's code reviewers
  (see `docs/subsystems/review-ladder.md`).
- **Cheap specialists, strong judgment where it counts.** Most of the reading is done on the
  cheaper model; the strongest model is reserved for orchestration and engine judgment.
- **Measure from ledgers, not from summaries.** The same lesson as the runtime's review gate: a
  self-report is a claim, a ledger row is evidence.

## How it relates to this runtime

The loop runs on this runtime's machinery: the review gate, the model pins, the spend ledger and
the issue tracker rules all apply to it. Its agents live in the product repository, not in
`agents/`, which is why they are absent here. To build your own, copy the shape (orchestrator,
lane-locked specialists, verifier, fixer, ledger, offline exit check), not the domain.
