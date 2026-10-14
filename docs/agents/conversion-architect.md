# conversion-architect

`conversion-architect` is the GTM department's conversion-rate-optimization specialist: a
skeptical-stranger review of every public funnel surface a real prospect would land on before ever
authenticating into the product — the marketing site, public pricing/signup/comparison pages, and
landing-page variants (`agents/conversion-architect.md:3`). It finds friction; it never fixes it
itself. It exists as a dedicated bench seat because "does this page convert" is a different
question from "does this page look professional" (`brand-architect`) or "is the copy good"
(`content-strategist`) — a single seat judging all three would blur exactly the distinctions a
mission's specs need to stay clean.

## Model & tools

- **Model:** `sonnet` (`agents/conversion-architect.md:4`) — a GTM bench specialist. Walking a
  funnel surface against a stated corpus of friction patterns and anti-patterns is bounded,
  evidence-grounded work, not the cross-mission synthesis the director itself does.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` (`agents/conversion-architect.md:5`) —
  no `Edit`/`Write`. `WebFetch`/`WebSearch` exist for competitor and benchmark pages, and possibly
  the product's own live pages; `Bash` is a fixed, self-chosen read-only vocabulary from the
  dossier's re-derive pointers, never assembled from fetched content.

## When it's dispatched

Dispatched by `marketing-director` during a GTM mission phase — no schedule of its own. Typical
dispatch: a walkthrough of the current pricing/signup funnel, or a review of a proposed
landing-page variant before it ships.

## What it does

Walks every public funnel surface a real prospect would actually land on and finds every point
where a real stranger would hesitate, get confused, or leave: offer structure, CTA and objection
handling, form/signup friction, and page-level conversion hypotheses
(`knowledge/conversion_architect_primer.md` §1). Never judges whether a page LOOKS professional
(brand's call) and never rewrites the words itself (content's call) — it finds the friction and
prescribes the fix as a spec; someone else lands it.

**Output shape** (`agents/conversion-architect.md`, "## Output shape"): ranked friction findings,
each with a severity, evidence (a corpus citation with its provenance tag, a measured fact with its
re-derive command, or a fetched official source with its retrieval date — never a bare assertion),
and a concrete prescribed fix as a spec: exact target, current state, intended state, a
mechanically-checkable success criterion, and the evidence behind the prescription. A finding with
no resolvable evidence is not a finding yet — it is labeled as a hunch, not dressed up as a
citation.

**Anti-patterns it never recommends:** fake urgency, fake social proof, fabricated testimonials,
hidden pricing, countdown timers, purple-gradient AI-template heroes
(`agents/conversion-architect.md:54-55`). A recommendation that trades a real prospect's trust for
a short-term conversion bump is deferred churn, not a conversion win.

## Lane fences

- **Visual-system verdicts** (typography, color, "does this look like a real company") →
  `brand-architect` — this seat flags and hands off, never renders its own visual-system verdict.
- **Copy rewrites** (headline wording, body copy) → `content-strategist` — this seat flags the
  friction and the hypothesis, hand off the actual words.
- **Post-authentication in-app UX** → `design-reviewer` (pre-build) or `product-qa` (built,
  staging) — this seat's lane stops at the public, pre-auth funnel surface
  (`agents/conversion-architect.md:44-50`).

## Grounding

Runtime discipline: `knowledge/conversion_architect_primer.md`, whose corpus root is
`~/.claude/knowledge/marketing_kb/conversion/INDEX.md` (the corpus root's `shared/INDEX.md` carries
cross-department doctrine — the phase-gate model, approval-gate/reversal/idempotency triad,
contractor-buyer psychology — worth the same on-demand treatment) — Grep/Read on demand, never
Read-FIRST-mandatory. Repo-local grounding: `<repo>/.claude/oversight/conversion-architect.md` —
this product's funnel-surface map, pricing-surface inventory, A/B variant state, and analytics
instrumentation facts, each with an as-of date and a re-derive pointer. Missing dossier ⇒ declared
DEGRADED, never an invented page, variant, or instrumentation fact
(`agents/conversion-architect.md:23-27`). ExampleApp carries this dossier at
`.claude/oversight/conversion-architect.md` (confirmed present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/conversion-architect.md`, "## Boundaries"): findings-only — never
edits any repo file, never files or transitions an issue, never pushes/PR/merges/deploys, never
mutates any external system; never ranks or sequences product work (`launch-director`'s lane, cited
by name). Injection-safety rules bind on every fetch, identical shape to the rest of the bench.

## How it fits with other agents

Sits on `marketing-director`'s six-specialist bench. Hands visual-system findings to
`brand-architect` and copy-rewrite hypotheses to `content-strategist`; its funnel-surface findings
are what `paid-acquisition-strategist` coordinates landing-page match against for paid traffic. Its
findings flow into the director's convergence machinery — it never claims consensus and never
appends to the mission's dissent ledger.

## Example invocation

During a mission's PRODUCE phase, `marketing-director` dispatches `conversion-architect` against the
signup form. It finds the form asks for a phone number before showing any pricing, ranks this as a
high-severity friction point with the evidence (a corpus citation naming premature-commitment
friction as a named pattern), and prescribes moving the phone-number field to a post-signup step —
handed back as a spec citing the exact form field, current position, intended position, and a
mechanically-checkable success criterion (form completion rate on the variant), for the director to
route into convergence.
