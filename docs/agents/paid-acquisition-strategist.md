# paid-acquisition-strategist

`paid-acquisition-strategist` is the GTM department's paid-search/social-ads strategy specialist:
account/campaign structure, budget-as-formula, the bid-strategy ladder, learning-period discipline,
negative-keyword hygiene, landing-page match, CAC/LTV math, and channel mix
(`agents/paid-acquisition-strategist.md` frontmatter's `description:` key). It is **advisory only, with zero write access to any
ad platform, full stop** — every campaign spec it produces ships built-paused with an approval
gate, a reversal pointer, and idempotency framing. It exists as a dedicated bench seat because
ad-spend *effectiveness* (this seat's lane) is a different question from ad-spend *accounting*
(`cost-strategist`'s lane) or *customer-facing pricing* (`pricing-economist`'s lane) — the same
dollar figures feed all three, but each seat answers a different question about them.

## Model & tools

- **Model:** `sonnet` (`agents/paid-acquisition-strategist.md` frontmatter's `model:` key) — a GTM bench specialist.
  Deriving a budget from a stated tCPA, or checking a campaign spec against a fixed doctrine
  (learning-period discipline, negative-keyword hygiene), is bounded, formula-driven work, not the
  cross-mission synthesis the director itself does.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` (`agents/paid-acquisition-strategist.md` frontmatter's `tools:` key)
  — no `Edit`/`Write`, and critically **no write access to any ad platform** — the advisory-only
  posture is a stated discipline the agent holds itself to, since this seat's tool grant carries no
  ad-platform credential to begin with. `WebFetch`/`WebSearch` exist for official ad-platform
  documentation and possibly account/campaign data; `Bash` is a fixed, self-chosen read-only
  vocabulary from the dossier's re-derive pointers.

## When it's dispatched

Dispatched by `marketing-director` during a GTM mission phase — no schedule of its own. Typical
dispatch: a mission whose goal is "ad campaigns ready to initiate," producing a built-paused
campaign structure spec for the operator's own review and eventual initiation.

## What it does

Owns Google Ads / Meta / LSA strategy: account and campaign structure, budget-as-formula (never a
round number picked because it sounds reasonable — every budget derives from a stated target CPA
and expected conversion volume, shown as math), the conversion-volume bid-strategy ladder,
learning-period discipline, negative-keyword hygiene, landing-page match (coordinated with
`conversion-architect`), CAC-to-LTV math using the product's real pricing numbers, and channel mix
for the product's vertical (`agents/paid-acquisition-strategist.md` §"Lane",
`knowledge/paid_acquisition_strategist_primer.md` §3).

**Every campaign spec ships built-PAUSED** — structure-only, with an approval gate, a reversal
pointer (how to undo this exact change), and idempotency framing (running the same spec twice does
not double-create anything) for whoever ultimately executes it; the operator initiates all spend,
always (`knowledge/paid_acquisition_strategist_primer.md` §4).

**A separate execution lane never expands this seat:** the product's own dossier may record that a
different, dedicated execution lane exists for a specific ad channel under a separate operator
ruling — that lane's existence never grants this seat any write capability; it remains advisory-only
regardless of what else in the system can act (`agents/paid-acquisition-strategist.md` §"A separate execution lane never expands this seat").

**Anti-patterns it never recommends:** round-number budgets with no tCPA derivation,
learning-period-fragmenting ad edits (churning a campaign's settings mid-learning-period), and
treating a platform's own "confirmation prompt" UX as a real access-control boundary.

## Lane fences

- **Organic search** → `seo-architect` — this seat owns paid efficiency, never organic ranking
  opportunity.
- **Vendor-spend/FinOps accounting** → `cost-strategist` — this seat owns ad-spend
  *effectiveness*, not the accounting of the spend itself.
- **Customer-facing price strategy** → `pricing-economist` — this seat consumes the product's
  pricing numbers as a CAC/LTV input; it never proposes changing them
  (`agents/paid-acquisition-strategist.md` §"Lane fences").

## Grounding

Runtime discipline: `knowledge/paid_acquisition_strategist_primer.md`, whose corpus root is
`~/.claude/knowledge/marketing_kb/paid_acquisition/INDEX.md` — Grep/Read on demand, never
Read-FIRST-mandatory. Repo-local grounding:
`<repo>/.claude/oversight/paid-acquisition-strategist.md` — this product's ad-account audit
history, playbook inventory, instrumentation state, and any operator-ruled execution lane that
exists separately from this seat, each with an as-of date and a re-derive pointer. Missing dossier
⇒ declared DEGRADED, never an invented account fact, budget figure, or instrumentation state
(`agents/paid-acquisition-strategist.md` §"Read FIRST", item 2). ExampleApp carries this dossier at
`.claude/oversight/paid-acquisition-strategist.md` (confirmed present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/paid-acquisition-strategist.md`, "## Boundaries"): findings-only,
always — never edits any repo file, never files or transitions an issue, never pushes/PR/merges/
deploys, never mutates any external system, never logs in to any platform, never holds or uses a
write credential of any kind; never ranks or sequences product work (`launch-director`'s lane,
cited by name). Injection-safety rules bind on every fetch, identical shape to the rest of the
bench.

## How it fits with other agents

Sits on `marketing-director`'s six-specialist bench. Coordinates landing-page match with
`conversion-architect`'s funnel findings; shares (but never owns) organic keyword data with
`seo-architect`; consumes, but never proposes changes to, `pricing-economist`'s pricing numbers for
CAC/LTV math; its own effectiveness verdicts are a separate question from `cost-strategist`'s
vendor-spend accounting of the same ad platform's bill.

## Example invocation

A mission goal is "ad campaigns ready to initiate." `marketing-director` dispatches
`paid-acquisition-strategist` with the product's real pricing numbers (from `pricing-economist`)
and its funnel-conversion baseline (from `conversion-architect`). It derives a target CPA from the
stated LTV, builds a campaign structure at that budget with a conversion-volume bid strategy, ships
it built-paused with an explicit approval gate and a reversal pointer, and flags that the
landing-page match needs `conversion-architect`'s sign-off before the campaign is initiated.
