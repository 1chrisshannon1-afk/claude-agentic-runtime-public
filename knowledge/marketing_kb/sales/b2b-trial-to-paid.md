# B2B Trial-to-Paid

What separates a free or trial signup that converts to a paying customer from one that churns
silently is a distinct discipline from lead-generation or lead-qualification: opt-in vs. opt-out
trial design, activation-milestone definition, and product-qualified-lead (PQL) scoring. This file
covers the evidence on what actually predicts trial conversion, not the pricing/packaging decision of
what a trial should cost or how long it should run (owned by the `pricing/` domain — see the boundary
note in `INDEX.md`).

## 1. Card-required (opt-out) vs. card-not-required (opt-in) trials

**[KB-SALES-047]** Two structurally different trial models exist and convert very differently by
definition, not just by degree: an **opt-out trial** requires payment information upfront and
auto-converts to a paid subscription unless the user actively cancels before the trial ends; an
**opt-in trial** requires no payment information upfront and requires the user to actively choose to
become a paying customer at the end. SaaS benchmark research (most frequently cited: Totango/other
PLG-benchmark analyses) commonly reports that opt-out trials convert to paying at meaningfully higher
raw rates than opt-in trials, because the "conversion" event for an opt-out trial is largely a
non-cancellation default rather than an active purchase decision (third-party, aggregated PLG/SaaS
benchmark commentary — Totango and other product-led-growth benchmark report lineage — retrieved
2026-09-27 — **UNVERIFIED at the level of a specific percentage-point gap between the two models: the
underlying benchmark reports were not independently re-pulled with disclosed methodology during this
pass; treat the direction (opt-out numerically converts higher) as well-supported and structurally
obvious given how each model defines its own conversion event, and treat any specific percentage
figure as illustrative only**).

**[KB-SALES-048] (internal doctrine)** The higher raw opt-out conversion rate is **not** equivalent to a better business
outcome — a user who "converts" only because they forgot to cancel a card-required trial is a
materially higher churn and refund-request risk than a user who actively chose to pay with no card on
file, and opt-out trials that convert primarily via inattention carry real customer-trust and
chargeback-dispute risk (mechanism-level inference from the structural difference in [KB-SALES-047];
consistent with widely-discussed PLG practitioner commentary on "trial-then-forgot-to-cancel" churn
and support-ticket/chargeback load, but **not tied to a single specific disclosed study** — treat as
a well-reasoned mechanism, not an independently measured statistic). **The choice between the two
models is a pricing/packaging decision** (owned by `pricing/`, referenced here only as an input this
domain's PQL scoring and follow-up cadence must account for) — a card-required trial's "trial ending"
follow-up message serves a different purpose (preventing an unwanted silent charge, which is itself an
honesty obligation, not just a sales opportunity) than a card-not-required trial's "trial ending"
message (which is a genuine conversion ask with no risk of surprising the user with a charge).

## 2. Activation milestones — what predicts real conversion, not just signup

**[KB-SALES-049]** Product-led-growth practitioner literature (commonly associated with the "Aha
moment" / activation-milestone framework popularized across PLG case studies, e.g. the widely-cited
account of a specific engagement threshold correlating with retention in early-stage growth
literature) consistently argues that raw trial signup is a weak predictor of conversion, while a
specific, product-defined **activation milestone** — a concrete action or threshold that correlates
with the user having experienced real value, not just logged in — is a much stronger predictor
(third-party, aggregated PLG practitioner/case-study literature, retrieved 2026-09-27 —
**UNVERIFIED at the level of any universal activation-milestone definition or specific correlation
statistic: activation milestones are, by the framework's own logic, product-specific and must be
independently derived from that specific product's own usage data — no generic milestone or
percentage ports as fact across products**).

**[KB-SALES-050] (internal doctrine)** The mechanism a sales-ops agent should design around, independent of any specific
product's exact milestone: identify the smallest concrete action inside the trial that plausibly
correlates with the user having experienced the product's core value (not merely "logged in" or
"clicked around"), instrument it as a trackable event, and treat *reaching* that milestone — not
merely *time elapsed in trial* — as the trigger for both automated nurture content and a human sales
touch where a human sales motion exists. A trial-days-remaining countdown email sent identically to a
user who hit the activation milestone on day one and a user who never logged in past signup treats two
very differently-positioned users the same way, which wastes the more promising user's attention with
generic content and fails to give the never-activated user the specific nudge (often product education
or onboarding help, not a sales pitch) they actually need.

## 3. Product-qualified leads (PQLs) — scoring usage, not just firmographics

**[KB-SALES-051]** A PQL model scores a trial or freemium user's likelihood to convert and/or expand
based on actual in-product usage behavior (features used, activation milestones reached, usage
frequency/recency, team/seat growth within the trial) rather than — or in addition to — the
traditional firmographic/demographic scoring a marketing-qualified-lead (MQL) model uses. This is a
widely adopted practice across PLG-motion B2B SaaS companies (third-party, consistently described
across PLG practitioner and RevOps literature, retrieved 2026-09-27 — mechanism well-supported and
widely practiced; **no single universal PQL scoring formula is citable as authoritative, since the
specific signals and weights are inherently product-specific** — treat any generic PQL scoring
template as a structure to adapt with product-specific data, not a formula to port verbatim).

**[KB-SALES-052] (internal doctrine)** The same qualification-score discipline from `lead-qualification.md` §3 applies to
a PQL score specifically: a PQL score that isn't wired to actually change what happens next (routing
a high-scoring trial user to a proactive human touch, triggering a specific in-app nudge for a
stalled-but-not-activated user) is bookkeeping, not qualification. **Reject example:** a PQL score
field populated on every trial account, visible on a dashboard, but with no automation or human
process that actually acts differently based on the score. **Pass example:** a trial user who reaches
the activation milestone and adds a second team member within the first week is automatically flagged
for a proactive "how's it going, want a quick walkthrough of X" outreach, while a user who never
activates by day 5 of a 14-day trial receives targeted onboarding content instead of a sales pitch.

## 4. What healthy trial-to-paid benchmarks actually say

**[KB-SALES-053]** Commonly cited SaaS trial-to-paid conversion benchmarks vary enormously by
model — opt-in free trials are frequently reported in a **rough single-digit-to-low-teens percent**
range, opt-out (card-required) trials frequently reported meaningfully higher (sometimes cited in the
**~50%+** range for well-optimized products, given the structural non-cancellation-default dynamic in
[KB-SALES-047]) — but every such figure comes from aggregated vendor/analyst benchmark reports without
a single disclosed, independently-verified cross-industry methodology (third-party, aggregated across
multiple SaaS-benchmark sources — OpenView, ProfitWell/Paddle-lineage, and similar PLG benchmark
report content — retrieved 2026-09-27 — **UNVERIFIED at the level of any precise percentage: treat
the wide range and the structural opt-in-vs-opt-out gap as the reliable takeaway; never present a
specific percentage from this literature to an operator as a target their own product should hit,
since it depends heavily on product category, price point, and trial design choices this corpus does
not control**).

## Contractor bend

This file's subject — B2B SaaS trial-to-paid mechanics — describes the sales motion for software
being sold *to* a business (relevant to a GTM department selling a SaaS product to contractors, for
example), not the mechanism by which a residential GC sells *their own* remodeling services to a
homeowner, which is a fundamentally different, project-based, quote-driven sale covered by
`estimate-follow-up.md` instead. Where this file's doctrine does apply directly: if the company's
own product is being trialed by a prospective contractor customer, the activation-
milestone and PQL discipline above governs that trial's own follow-up design — e.g., a contractor
trial account that reaches a strong, product-specific activation milestone (for an estimating tool,
completing a first real estimate; the equivalent milestone varies by product) should trigger
meaningfully different follow-up than one that signed
up and never returned, exactly per §2–3 above. A buyer archetype already burned by software before
(see `../shared/contractor-buyer-psychology.md`) responds particularly badly to a trial experience
that feels like it's tracking and scoring them without any transparency — activation-milestone-based
outreach should read as genuinely helpful ("noticed you haven't tried X yet, want a hand?"), never as
a thinly disguised sales-pressure escalation triggered by a score the contractor can't see.
