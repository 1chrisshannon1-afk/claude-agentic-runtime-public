# Phase-gate model — collect → analyze → plan → approve → execute → verify

Ported mechanism (internal doctrine, retrieved 2026-09-27 — a phase-gate structure this department has carried forward
from prior ads-department work). The structure ports directly; the specific artifacts (CSV exports,
`run_id`s, ad-platform-specific checklists) are that prior work's ads-department shape and are
re-derived below for a GTM department that has no ads-account exports of its own yet.

## The core principle

> "The agent does all the work. The operator only provides intent and approval." (ported mechanism,
> internal doctrine, retrieved 2026-09-27)

A campaign, page, or piece of content is not "done" until every setting, asset, and decision point
is either configured or explicitly marked N/A with evidence. "Left for the operator" or "someone
should check this" is a failure unless a specific, named blocker makes it genuinely
operator-only — see `approval-gate-triad.md` for what counts as a real blocker versus a task an
agent should have just done.

## The six phases and their gates

Each phase has a completion gate. Do not advance until the gate is satisfied, and do not skip a
phase because the task "feels small" — a scaled-down version of each gate still applies to a small
change (see this file's own weekly-vs-full distinction below, a ported split from the same prior
work this file's mechanism comes from).

| Phase | Gate | Completion artifact |
|---|---|---|
| **Collect** | All required source data actually pulled (not assumed from memory) and recorded with what was pulled and when. | A dated data snapshot, keyed to a stable id (a `run_id`-style reference): e.g. "GA4 export pulled 2026-09-05, date range Aug 1–Sep 5." |
| **Analyze** | Findings are numeric and dated, not generic best-practice prose. Every claim is tagged per `citation-style.md`. | A findings doc citing the collect-phase snapshot by its date/id — never a re-statement of an older analysis with a new date slapped on it. |
| **Plan** | Every setting/asset/decision this phase touches is addressed — configured or explicitly N/A with a one-line reason. Self-check run before submission (below). | A proposal file with an approval checkbox at the bottom. |
| **Approve** | The operator checks a box or says "approved" in chat — nothing else counts. A queued platform "recommendation," an auto-apply default, or a backlog item is *not* approval; it's a request to evaluate (see `approval-gate-triad.md`). | The checked box, or the chat transcript line. |
| **Execute** | Every approved item is actually applied — not queued, not "in progress," not "the operator can finish this in the UI." | A completion log with what was applied, exactly as specified. |
| **Verify** | Re-check the live state (site, campaign, account) against the plan after execution. Differences are documented, not silently absorbed. | A verification note confirming match, or naming the discrepancy and its resolution. |

## The plan-phase self-check (mandatory before any proposal is submitted)

Ported directly (internal doctrine, retrieved 2026-09-27): before presenting a proposal, the agent verifies every relevant
item is addressed. For a GTM proposal in this department, the categories translate to:

- **Scope of the change** — what pages/campaigns/copy/assets are touched, named explicitly.
- **Every dimension of the change** — for an ad campaign: budget, bid strategy, targeting,
  schedule, all asset types (see `paid_acquisition/grade-a-gates.md`); for a landing page: every
  section, every CTA, every claim checked against the company's own never-claim list
  (`department-anti-patterns.md` item 2); for a pricing change: every tier, every plan comparison
  surface it must stay consistent with.
- **Evidence** — every material claim or number carries a citation per `citation-style.md`; no
  proposal leans on "generally" or "usually" without a tag.
- **Execution method named for every step** — API, CSV, direct file edit, MCP browser — never "the
  operator does this part."
- **Company/product alignment** — the plan does not contradict the company's own positioning doc's
  audience, pricing principle, or never-claim list; does not introduce a claim the product doesn't
  actually support.
- **Approval checkbox present** — no proposal ships without one.

If any item is missing, fix it before submitting. Do not submit and hope nobody notices — this is
the exact failure mode the self-check exists to prevent (ported doctrine: "do not submit and hope the
user won't notice").

## Weekly/incremental plans vs. full plans (scaled evidence bar)

Not every change needs the full plan-phase treatment. Mirroring a ported split from the same prior
work (internal doctrine, retrieved 2026-09-27):

- **Incremental/optimization-only changes** (a single ad-copy tweak, one landing-page headline
  test, a small budget adjustment): a lighter proposal — user intent quoted, a change table, ≥3
  numeric evidence anchors (≥5 if material), execution mapping, approval checkbox. Still gated,
  just proportionate.
- **Full campaign/page/pricing-structure changes**: the full plan-phase treatment above, with every
  dimension addressed.

Scaling the evidence bar down for a small change is legitimate; skipping the approval gate or the
citation discipline because a change is small is not — those never scale down.

## Common failure modes (ported, re-titled for this department)

| Failure | Fix |
|---|---|
| Plan is a restatement of an older plan with a new date | Pull fresh data for this phase's `analyze` step; cite it, don't recycle the last cycle's numbers. |
| "Operator should check this in the platform UI" | The agent has the same access; do the work. Only document a blocker if it is genuinely technically impossible (2FA, CAPTCHA, credential the agent cannot access). |
| Proposal says "approved" but the box isn't checked | Keep the artifact honest — check the box the moment approval is given, don't narrate approval that hasn't happened on the record. |
| Plan lists a setting but execution skips it | If the plan says a thing will be configured, execution must actually configure it — not just log the intent. |
| No verify-phase re-check after execution | Re-read the live state and confirm it matches the plan; log discrepancies, don't assume success. |

## Contractor bend

The phase-gate model itself is invisible to the end buyer — they never see "Phase: Collect" written
anywhere. What they experience is the *output* of a well-run phase gate: a proposal that doesn't ask
them to configure five dashboard settings themselves, copy that doesn't claim something the product
can't do, and a change that actually shipped instead of half-landing. The discipline this file
describes is precisely what prevents the operator (who stands in for that buyer during planning — a
busy, skeptical, non-technical decision-maker, per `contractor-buyer-psychology.md` /
`homeowner-buyer-psychology.md`) from having to notice a gap and ask for it themselves. If a phase
gate feels like overhead for an internal team, remember its entire purpose is to make sure the buyer
downstream never has to do the agent's job for them.
