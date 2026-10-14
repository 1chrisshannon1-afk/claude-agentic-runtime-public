# plan-reviewer

`plan-reviewer` is the runtime's other mandatory Opus review gate (CLAUDE.md §10) — the one that
fires **before any code is written**. It reads a proposed plan and the operating contract, and
judges whether a worker agent could execute the plan literally, with no further judgment calls of
its own, and produce a correct, complete, hardened result. Unlike `code-reviewer`, nothing
mechanically blocks implementation from starting without this review — the enforcement here is
entirely a CLAUDE.md directive ("Do not start implementing a substantial plan un-reviewed",
CLAUDE.md §10) plus a log-only outcome ledger, not a `PreToolUse` gate.

## Model & tools

- **Model:** `opus` (`agents/plan-reviewer.md:4`), hard-pinned. One of the two boundary reviewers
  named directly in CLAUDE.md §10's "two Opus review points, and only two."
- **Tools:** `Read, Grep, Glob, Bash` (`agents/plan-reviewer.md:5`) — no `Edit`/`Write`. Bash is
  "for read-only verification only; never edit, commit, or run state-changing commands"
  (`agents/plan-reviewer.md:107-108`), used to verify the plan's technical claims against the actual
  codebase rather than trusting the plan's own assertions.

## When it's dispatched

At the **plan boundary — before any code is written** (`agents/plan-reviewer.md:10`), per CLAUDE.md
§10's first review point: "An Opus `plan-reviewer` reviews the plan against the request and this
operating contract, surfacing gaps, risks, and contradictions **before** any code is written. Do not
start implementing a substantial plan un-reviewed" (CLAUDE.md §10, "Do not start implementing a
substantial plan un-reviewed"). "Substantial" is a judgment
call left to the orchestrator — this is not mechanically triggered the way `code-reviewer`'s gate
3b is; there is no hook that inspects an `Edit`/`Write` call and asks whether a plan review is on
file for it.

Inputs it's given: the plan file itself (path supplied by the orchestrator), the original request
the plan is meant to satisfy, and the operating contract at `~/.claude/CLAUDE.md`
(`agents/plan-reviewer.md:27-30`). **A missing or unreadable input is reported, never silently
assumed** — an unreadable plan file, an unsupplied request, or a plan-dependent file that can't be
read gets called out explicitly at the top of the findings, with every check that depended on it
marked as not performed (`agents/plan-reviewer.md:31-41`). Unlike the oversight roster's
specialists, `plan-reviewer` has no dossier/grounding-corpus concept, so this is phrased as a
missing-input rule rather than a borrowed "declare DEGRADED" clause. **When a required input was
missing or unreadable, the review has no verdict** — the orchestrator omits both `--clean` and
`--blockers` when recording it, which `record_plan_review.py` handles as "Nothing recorded" plus a
`no-outcome` log line; `--clean` may never be recorded for a review whose inputs were incomplete,
since zero blockers found because nothing could be read is not a clean plan
(`agents/plan-reviewer.md:37-41`).

## What it does

**The standard is explicitly ABSOLUTE, not partial** — rewritten 2026-08-20 by operator direction
(`agents/plan-reviewer.md:13`, CLAUDE.md §10, "The bar is completeness, not coherence"). A plan
that "reads coherently and covers the
obvious happy path" is not good enough. The bar: "a worker agent given only this plan, with no
further access to the requester, would produce a correct, complete, hardened result"
(`agents/plan-reviewer.md:24-25`). The plan is held to the same seven lenses `code-reviewer` applies
to code — robust, hardened, complete, correct, best-practice, maintainable, scalable — judged
against what the plan will **produce**, not how it reads (`agents/plan-reviewer.md:17-25`,
CLAUDE.md §10, "judged against what the plan will PRODUCE, not how it reads").

**What it checks**, nine dimensions (`agents/plan-reviewer.md:45-103`):
1. **Completeness — no partial plans.** "TODO: figure out X during implementation" or "wire the
   rest up similarly" is a REJECT, filed as `blocker`, not a nit. The test: could two competent
   engineers implement this independently and produce materially different results? If yes, the
   plan is under-specified there. **Explicit carve-out:** a plan that names a real decision point —
   "measure X; if above threshold T, do A (because...); otherwise do B (because...)" — is *complete*
   even though the concrete action isn't known until runtime, because every branch is enumerated
   with a stated criterion and an owner. "Investigate why X is slow, then fix it" is *incomplete* —
   no branches, no criterion. A genuine spike's acceptable shape: name the specific question, the
   concrete artifact that answers it, and what happens for each plausible answer
   (`agents/plan-reviewer.md:51-58`).
2. **Coverage — every affected part of the system.** Trace the actual blast radius by grepping for
   it, not by trusting the plan's own stated scope. A plan is incomplete if it misses a sibling code
   path, a second caller with the same defect, a now-false schema/doc, or a test suite that no
   longer reflects reality — even if every listed step is itself correct.
3. **Root cause vs. band-aid, flagged explicitly — the "hardened" lens above.** A null-check added
   at a call site instead of fixing why a value is null, a retry/timeout bump instead of fixing a
   real failure, a special case instead of fixing a data problem, a new flag/toggle avoiding the
   actually-broken logic: each is a proposed approach that routes around a symptom rather than
   fixing it. "A plan that knowingly ships a band-aid without saying so, and without a tracked
   follow-up for the real fix, is `blocker` severity — not a separate 'band-aid' bucket"
   (`agents/plan-reviewer.md:74-75`). A plan that discloses the tradeoff plainly and files the real
   fix as a tracked follow-up is *not* a blocker on this ground alone.
4. Faithfulness to the request — what's unaddressed.
5. Gaps — missing prerequisites/rollback paths; verification that only tests the happy path (the
   plan's own verification step should include positive recovery tests too, mirroring CLAUDE.md's
   required-pairings rule from §6).
6. Risks — irreversible/outward-facing actions (push/PR/deploy/prod/customer-facing) hidden inside
   "implementation"; missing safety defaults (log-only/degrade-open/kill-switch); new surface area a
   future defect could exploit.
7. Contradictions — internal inconsistencies, and any conflict with the operating contract (branch
   discipline, path-scoped commits, ask-before-outward, tests-assert-intended, docs-travel-with-
   change, issue lifecycle, review cadence, adaptive concurrency).
8. Scope — creep beyond the request **or** under-scope that leaves the goal unmet; both directions
   are failures.
9. Maintainability/scalability of the result — the "maintainable"/"scalable" lenses above, applied
   to what the plan actually produces if implemented exactly as written. A plan that's internally
   consistent but produces brittle, hard-to-extend, or non-scaling code still fails.

**Output:** a numbered findings list, grouped by severity — `blocker / risk / gap / nit`
(`agents/plan-reviewer.md:115`). **Evidence discipline is two-sided:** a finding of the shape "the
plan claims X but the codebase actually does Y" needs a `file:line` (or the exact grep/read command
that reproduces it) for the Y half just as much as the concrete plan location required for the X
half — a codebase claim the reviewer could not confirm is tagged `UNVERIFIED` rather than asserted
as fact, never blended with a confirmed finding (`agents/plan-reviewer.md:117-120`). **Any §1
completeness failure and any undisclosed §3 band-aid are ALWAYS `blocker` severity by definition** —
there is no separate band-aid bucket to file into instead, though a finding can be tagged `blocker
(band-aid)` for visibility (`agents/plan-reviewer.md:121-123`). Every finding must say what SHOULD be
in the plan to close the gap — "this is incomplete" with no description of complete is treated as an
unfinished review (`agents/plan-reviewer.md:111-112`). It states plainly whether the plan is **safe
and complete enough to execute literally, with no worker judgment calls**, or what must change first;
any blocker-severity finding means the plan is not safe to execute
(`agents/plan-reviewer.md:124-126`).

**Round discipline** (`agents/plan-reviewer.md:128-139`) is headed as the contract's own fix-round
cap — CLAUDE.md §10, "Do not re-run a full Opus pass on every fix-and-recheck round" — not as
mirroring `code-reviewer.md`. **Correction (2026-08-31):** the heading used to read "mirrors
`code-reviewer`'s." The cap's authoritative home is CLAUDE.md §10, so the heading now cites it there
rather than a sibling agent file whose line numbers rot. `code-reviewer.md` does carry its own
round-discipline section (its own "## Round discipline" heading), but the two are deliberately *not*
identical — see the two asymmetries below. Round 1 is a full pass against
every check above. When the orchestrator revises the plan and asks for another look, the default is
NOT a full re-run: verify specifically that each
raised finding was actually addressed, the same falsifiability posture as code review's "does this
fix exactly what was reported." Escalate to a full pass again only when: the revision changed the
plan's *overall approach* (not just patched the flagged spots), or two targeted rounds have passed
without a full re-check. **When a round escalates back to a full pass, the reviewer examines the
whole revised plan against every check above even if the continuation prompt names only the
previously-flagged spots — a prompt narrowed to "confirm these are fixed" does not narrow an
escalated round's scope** (`agents/plan-reviewer.md:136-139`). Two asymmetries with `code-reviewer`'s
own round discipline: (1) plan review has no equivalent of a "risk tier `high`" trigger, because
`review_risk_tier.py` classifies file *paths*, which is a code-diff concept a plan file doesn't
carry the same way; and (2) plan review's escalated-round scope-protection sentence above is a
simple one-line rule, not tied to CLAUDE.md §10's formal warm/cold round apparatus (the bounded
warm-continuation protocol, reviewer-of-record substitution checks) that governs `code-reviewer`'s
own version — that machinery is explicitly scoped to the code-review boundary only (see "No
substitution partner" below).

## Grounding

Operates under `~/.claude/CLAUDE.md` in full (`agents/plan-reviewer.md:8`). Verifies the plan's
claims against the actual tree — reads and greps the real files the plan depends on rather than
trusting the plan's own assertions (`agents/plan-reviewer.md:106-108`). No repo-local dossier; its
grounding is the plan text, the original request, and whatever source files the plan references.

## Boundaries — what it will NOT do

- **Never implements, never edits the plan or any file** — no `Edit`/`Write` grant
  (`agents/plan-reviewer.md:11, 126`).
- **Never files, transitions, or closes GitHub issues** — no git/gh write access. Per CLAUDE.md §8,
  any finding that isn't resolved by revising the plan before execution (i.e. knowingly deferred)
  must be filed by the orchestrator as a tracked issue **before implementation starts**, never left
  as a loose note in the plan text (`agents/plan-reviewer.md:155-159`).
- **Never pushes/PRs/merges/deploys** — entirely outside its lane and tool grant.

## How it fits with other agents

- **The two-boundary rule.** `plan-reviewer` and `code-reviewer` are the *only* two standing Opus
  review gates in the runtime (CLAUDE.md §10, "Two Opus review points, and only two"). Nothing
  else — not `test-architect`, not
  `agentic-systems-architect`, not `code-quality-architect` — is a standing gate; those are
  monthly-audit or on-demand agents (CLAUDE.md §13).
- **No substitution partner.** Unlike `code-reviewer`, no other agent substitutes for
  `plan-reviewer` at the plan boundary — the sanctioned-Opus substitution rule (`trust-architect`
  standing in for `code-reviewer` on trust-surface commits) applies only to the *code* review
  boundary, not the plan boundary (CLAUDE.md §10, the sanctioned-Opus extension bullet — cited
  by anchor, not line number: §10 grew 2026-08-30 and line citations into it rot).
- **Feeds `implement`.** A cleared plan is what an `implement` (or specialized builder) agent then
  executes; per the operator's own working preference (`feedback_plans_finish_bounded_review` in
  memory), a plan is FINAL after bounded review — blockers get fixed in the plan text, everything
  else becomes a build directive, not a reason to keep re-reviewing indefinitely.
- **Outcome ledger, log-only.** `python3 ~/.claude/hooks/record_plan_review.py <repo> --clean --plan
  <path>` (or `--blockers <n>`) writes to `~/.claude/.review_state/plan_reviews.jsonl`
  (`agents/plan-reviewer.md:141-153`, CLAUDE.md §10, "Record the plan-review OUTCOME too"). This
  does **not** block anything —
  explicitly unlike gate 3b — it exists purely so "does plan review actually catch things, or is it
  a rubber stamp" is answerable from data rather than assumed. Added 2026-08-20 specifically because
  a 2026-08-20 measurement found plan review had **zero** logged outcomes anywhere, ever, making its
  real catch rate unmeasurable (CLAUDE.md §10, "ZERO logged outcomes anywhere ever"). **A review
  whose required inputs were missing or unreadable records neither flag** — the orchestrator omits
  both `--clean` and `--blockers`, which the script logs as `no-outcome` rather than a fabricated
  clean verdict (`agents/plan-reviewer.md:37-41`).

## Example invocation

*Hypothetical/illustrative — `api/estimate_builder.py` is not a real file in any repo on this
machine (verified: no `api/estimate_builder.py` exists under `~/Desktop/ExampleApp` or
elsewhere in `~/`); the path and line number below are made up to illustrate the shape of a
finding, not a real citation.*

Before implementing a plan to add a new catalog-item pricing path, the orchestrator dispatches
`plan-reviewer` with the plan file and the original request. The reviewer traces the plan's claim
that "no other code path prices catalog items" by grepping the actual codebase, finds a second
pricing call site the plan never mentions, and files it as a `gap`: "the plan misses
`api/estimate_builder.py:212`'s separate pricing call (illustrative — see note above) — either this
plan must cover it too, or the plan must explicitly state why that path is out of scope." It also
finds a step reading "handle
insurance-priced items appropriately" with no criterion for what "appropriately" means, and files
that as a `blocker` under completeness — two engineers could implement it two different ways. The
orchestrator revises the plan to close both, and on the second pass the reviewer runs a targeted
check (does the revision actually name the second call site and state a concrete rule for insurance
items?) rather than a full re-review, confirms both are resolved, records `--clean`, and
implementation begins.
