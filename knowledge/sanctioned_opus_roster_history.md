# Sanctioned-Opus roster — the per-seat rationale, relocated from CLAUDE.md §10

**What this is.** The WS3 CLAUDE.md refactor (master plan §4) relocates narrative
out of the operating contract without deleting it. This file holds the per-agent
justification prose that had accumulated inside §10's sanctioned-Opus extension
bullet — what each seat does, when it was added, under whose direction, and how
its cost shape compares to its siblings.

**ARCHIVAL — no rule depends on an agent having read this.** The RULE lives in
CLAUDE.md §10 and the roster tables live in §13; both remain there. This file is
context for a human asking "why is this seat on Opus", never an input to any
decision an agent makes.

**Two mechanical constraints the trim had to respect, recorded so a future edit
does not break them** (`hooks/model_pin_parity.py`, violation class
`contract-roster-drift`, currently 0):

1. `_extract_section_10()` requires the literal backticked token `` `<name>` ``
   for every sanctioned-Opus extension agent to appear **somewhere** in §10's
   text. The predicate is deliberately loose — it does not parse the
   enumeration's grammar — which is what makes relocating the prose possible at
   all while keeping the check meaningful.
2. `_extract_section_13()` independently requires a real **table row** per agent
   in §13. That half is untouched by this relocation.

So: §10 keeps every name; §13 keeps every row; the "why" moved here.

---

## The bullet as it stood before the trim (verbatim)

Preserved word-for-word. Section numbering, agent names, dates, issue numbers and
plan paths are all as they were.

```
- **Sanctioned-Opus extension (2026-08-23, #4400/§13; extended 2026-08-25, ExampleApp
  #4436; extended 2026-08-30, operator-delegated, THE STANDARDS LOOP plan
  `~/.claude/plans/standards_loop_roster_plan.md`; extended 2026-09-05, operator-directed, GTM
  department plan `~/.claude/plans/marketing_team_roster_plan.md`; extended 2026-09-10,
  operator-directed, admin-portal visibility audit; extended 2026-09-19, operator-directed, GTM
  bench upgrade — `conversion-architect`, `brand-architect`, `content-strategist`,
  `seo-architect`, `paid-acquisition-strategist`, `pricing-economist`, `video-producer`, and
  `market-analyst` moved from sonnet to opus after the sonnet specialists missed defects the
  Opus director caught on a real mission: a claimed-nonexistent conversion event that actually
  existed, a 4x budget error, and a missing cross-connect guardrail).** The roster adds seven more
  sanctioned Opus AGENTS beyond the two boundaries
  above: `launch-director` (one bounded weekly ranked-judgment report), `test-architect` and
  `trust-architect` (review-boundary agents; trust-architect substitutes FOR code-reviewer on
  trust-surface commits — substitution, never stacking, so the two-boundary rule is preserved),
  `agentic-systems-architect` (a bounded monthly audit of the runtime's own agentic-system
  design — unit size/convergence, consensus/verification economics, grounding quality, gate
  friction, telemetry truth, platform-capability drift, feedback-loop/delivery-flow design,
  on-demand agentic software-factory target-design consults (primer §13/§14, added 2026-08-29),
  and pattern fit against the twenty-pattern catalog — when/where/why/why-not per pattern, each
  with an evidence grade and a baselined cost band (primer §15 + `agentic_patterns_evidence_2026_08_30.md`,
  added 2026-08-30; on the five rows another agent owns — Prioritization/`launch-director`,
  Exploration/`sentinel`, Guardrails/`trust-architect`, HITL and Evaluation/§9's settled review
  ladder — it audits the MECHANISM only, never performs the activity);
  judges, never edits, the identical cost shape as test-architect/trust-architect), and
  `code-quality-architect` (a bounded monthly audit of code structure/coupling/complexity/debt
  trend plus the coding standards themselves — interprets a repo's deterministic debt scan,
  emits rule diffs, NEVER a reviewer at any commit boundary; added 2026-08-30, same cost shape
  as the other monthly-audit architects — test-architect / trust-architect /
  agentic-systems-architect), and `marketing-director` (the first DEPARTMENT ORCHESTRATOR — a
  sanctioned-Opus mission runner, not an oversight watcher: runs operator-launched GTM missions
  through a mechanical-convergence loop, holds the `Agent` tool, dispatch-only via `/gtm`, no
  schedule; added 2026-09-05 — the department-orchestrator CLASS is defined in §13, and every
  future department orchestrator added to `OPUS_AGENTS` must be named in this bullet too, per
  this bullet's own move-together rule), and `admin-portal-architect` (added 2026-09-10,
  operator-directed, admin-portal visibility audit: judges, per admin page/route, whether the
  platform's admin console / back-office WORKS end-to-end in the deployed shape, is DEGRADED,
  DEAD, or a STUB, and ranks what the operator cannot see today that running the business
  requires — findings-only, dispatch-only, never a commit-boundary reviewer, same cost shape as
  code-quality-architect), and `observability-architect` (added 2026-09-15, operator-directed:
  logging/observability architecture audits — structured-logger adoption, correlation-id coverage
  across service and async boundaries, error classification (log-or-reraise, never both/neither),
  severity-string validity against the deployment platform's log-severity enum, alert-to-signal
  traceability (does an alert's filter field actually get emitted, does it pass the page-worthiness
  test), and dead telemetry (signals with no named consumer); interprets code-quality-architect's
  debt-scan metrics (bare except / except-pass / print calls) as an adjacent signal rather than
  recomputing them; findings-only, dispatch-only, never a commit-boundary reviewer — commit-boundary
  logging checks are `code-reviewer`'s lane via the shared doctrine file's own review checklist —
  same cost shape as code-quality-architect/admin-portal-architect), and `devops-architect` (added
  2026-09-16, operator-directed: delivery & infrastructure architecture audits — IaC
  declared-vs-running drift including authority conflicts (two sources appearing to define a value
  where only one takes effect), container/image supply chain, environment topology and parity,
  release/rollback engineering (promote/hotfix path safety, blast radius, rollback-vs-roll-forward
  decided BEFORE the deploy), and runtime service configuration judged for correctness and safety
  never for cost; measures the five DORA delivery metrics (throughput: lead time, deployment
  frequency, failed-deployment recovery time; instability: change fail rate, rework rate — the
  2025 model, NOT the retired four-keys/elite-tier framing) and names the pipeline's actual
  constraint, since optimizing a non-constraint is waste; findings-only, dispatch-only, never a
  commit-boundary reviewer — CI pipeline internals (job timings, caching, `permissions:`, action
  pinning, hook runtimes) stay `git-ops`'s standing lane and this seat may cite a pipeline outcome
  as a metric but never prescribe the fix to a job — same cost shape as
  code-quality-architect/admin-portal-architect/observability-architect). The mechanical mirror of
  this sanction is
  `hooks/sync_agent_rules.OPUS_AGENTS` — that tuple and this bullet must move together — and
  `hooks/model_pin_parity.py` (report-only) checks every runtime agent's pin AND the sanction set
  against `knowledge/model_policy.json`, the machine-readable policy this lives in, and the
  sanctioned-Opus extension set against BOTH `CLAUDE.md`'s own §13 roster table AND this §10
  bullet's backticked enumeration (`contract-roster-drift`, two halves — the §10 half added
  2026-09-05 after `marketing-director` sat in `OPUS_AGENTS` for a day while absent from this
  bullet, and the table-only checker passed).
```

---

## Reading it

Each parenthetical after an agent name is that seat's lane and cost shape. Where
a seat says "same cost shape as X", it means the bounded monthly-audit pattern:
findings-only, dispatch-only, never a commit-boundary reviewer. The one
structural exception named in the prose is `trust-architect`, which SUBSTITUTES
for `code-reviewer` on trust-surface commits rather than stacking on top of it —
that is a rule, and it stays in §10.
