# CAC / LTV / payback — SMB SaaS unit-economics doctrine

**Answers:** What are the CAC/LTV/payback-period norms for SMB SaaS, how does a company compare
against them today, and how does a seat challenge a growth plan that violates the ratios without
ever touching the price itself?

This file is a **unit-economics lens**, not a pricing lever. Everything here judges whether a
*growth or spend* plan is healthy given the price a company already charges — it never proposes
changing that price. See `ANTI-PATTERNS.md` #4 for why margin/unit-economics math is not this
discipline's product to weaponize into a repricing argument. (This is the pricing-economist seat's
doctrine — see `INDEX.md`: a live runtime agent; whoever handles a pricing question today applies
this file directly.)

## The three core ratios, sourced

**LTV:CAC ratio — 3:1 minimum, origin and misuse.** The 3:1 rule traces to David Skok's (Matrix
Partners) "SaaS Metrics 2.0" framework, published on the *For Entrepreneurs* blog circa 2010
(third-party, retrieved 2026-09-05 via secondary sourcing — Point Nine Land/Medium and
TheSaaSCFO.com both attribute the rule to Skok's original work). Skok derived it from observations
of mature, public SaaS companies (HubSpot, Salesforce, NetSuite-era comparables) at steady state
with stable churn and multi-year customer lifetimes — **the rule was never intended for pre-PMF or
seed-stage companies**, a caveat frequently dropped when the number is repeated. Top-quartile
companies run 4:1 to 6:1; below 3:1 "consistently" is Skok's stated trigger to fix CAC or LTV, not a
single bad quarter.

- (third-party, retrieved 2026-09-05): "if the ratio falls consistently below 3x, it's time to make
  some serious changes to reduce CAC or boost LTV" — most public SaaS comparables (Salesforce,
  Constant Contact-era) run closer to 5:1.

**CAC payback period — 12 months as the classic ceiling, SMB-specific data tighter.** Skok's
original heuristic: payback under 12 months (third-party, retrieved 2026-09-05). More recent
segment-specific data (third-party, retrieved 2026-09-05, aggregated benchmark sources —
GetAleph.com and Optifai's 939-company sample) narrows this for the SMB/self-serve segment
specifically: SMB SaaS (under $15K ACV) recovers CAC in **8-12 months**; prosumer/self-serve tools
can reach **~6.2 months**. Cross-segment payback improved from ~18 months (2024) to ~16 months
(2025) industry-wide, attributed to go-to-market rationalization rather than higher spend
(third-party, retrieved 2026-09-05).

**CAC and LTV dollar ranges for SMB SaaS.** (third-party, retrieved 2026-09-05, aggregated benchmark
sources): SMB CAC typically **$200-$700**; self-serve/PLG-motion SMB products run lower, **$100-$500**.
SMB SaaS LTV benchmarks: **$15K-$40K**. SMB tools reaching 4.0x LTV:CAC are cited as exceeding
baseline. These are cross-vertical SaaS aggregates, not vertical-specific to any one company's
category — see the gap flagged below.

## A company's actual number, sourced from the company's own book

A company's own pricing/economics doc may already have one real number, not a benchmark — e.g. a
real measured blended CAC from live acquisition spend, or (for a B2B company whose buyers themselves
buy leads, such as software sold to home-services contractors) a real measured lead-acquisition
cost the buyer pays in their own business. **A buyer's own lead-acquisition cost is not the same
thing as the GTM company's own SaaS customer-acquisition cost** — do not conflate the two if both
exist in a company's pack. See the company's own pack/dossier for its actual current number.

- **UNVERIFIED — seeded, needs derivation.** A company's actual blended CAC to acquire one paying
  subscriber (across whatever channels are live at launch) frequently has no cited figure until the
  company has actually run its own acquisition spend and counted real signups against it. Until
  then, any CAC used in a unit-economics argument about that company itself must be sourced from
  the cross-vertical SMB SaaS ranges above and labeled as a benchmark stand-in, never presented as
  the company's own measured number.

## Applying the ratios without touching price

A company's own ruled pricing ladder (see the company's own pricing source-of-truth doc) gives a
rough sense of gross contribution per tier once its own per-unit COGS is known (calculated or
measured — see `cogs-currency-method.md`) and its own fixed costs are known. But **LTV requires a
retention/lifetime assumption a pre-launch or recently-launched company typically does not have
yet** (no post-launch churn data exists — see `reopen-discipline.md` evidence class (b)) — so an
LTV:CAC ratio computed before that data exists is necessarily built on an assumed lifetime, not a
measured one.

**What the seat does when a growth plan proposes a CAC target:** check the proposed CAC against the
SMB benchmark ranges above (not against the company's price) and against the tier's monthly
contribution — without a measured lifetime, the honest question is payback period (months to
recover CAC from monthly contribution), not a full LTV:CAC ratio.

- **Pass example (illustrative, all figures constructed, not sourced):** A paid-acquisition plan
  targets $220 CAC for an entry tier priced at $50/mo (~$45 contribution after per-unit COGS at
  worst-case usage). Payback ≈ 220/45 ≈ 4.9 months — comfortably inside even the tightest SMB
  benchmark (6.2-12 months). No pricing action needed; the plan is unit-economically sound at the
  current price.
- **Reject example (illustrative, all figures constructed, not sourced):** A plan proposes $600 CAC
  for the same entry tier. Payback ≈ 600/45 ≈ 13.3 months — outside even the loosest SMB ceiling
  (12 months). The move here is to **question the CAC target or the channel mix that produces it**,
  never to propose raising the entry price to fix the ratio (that would be anti-pattern #1/#2 —
  premium-anchoring/silent repricing dressed as unit economics).
- **Note the honesty gap either way:** an illustrative payback calculation built on a calculated
  (not measured) COGS figure and an assumed, not measured, lifetime should be flagged as such
  whenever the ratio is presented, per this domain's house style (no unsourced numbers, and a
  number built on an unverified input inherits that flag).

## Vertical bends — trade/home-services (B2B) and local-service (B2C)

CAC/LTV framing is investor and growth-team language — many B2B buyers, especially small-business
owners in a hands-on trade, will never see or care about it directly. Two things about a
trade-buyer's world can change how a seat should apply this doctrine even when the internal
monitoring method itself doesn't change:

1. **For home-services contractors specifically, the price they pay per lead is a lived, felt cost
   to them, not an abstraction, so buyer-facing copy that names it lands because it is real to the
   buyer in a way "CAC" never is.** This is exactly why it works as a marketing proof point for a
   B2B company whose buyers themselves buy leads (e.g. software sold to home-services contractors):
   the buyer's own cost-per-lead is a marketing proof point, distinct from the company's own SaaS
   customer-acquisition cost, and the two must never blur together in a deliverable that might reach
   the buyer — the company's own CAC is an internal health metric. See the persona file the company
   pack selects (`persona_file`) — e.g.
   `shared/contractor-buyer-psychology.md` for a B2B-software buyer, or
   `shared/homeowner-buyer-psychology.md` for a B2C service buyer — for how this plays out
   concretely.
2. **A buyer whose own sales cycle is long and trust-gated** (phone-first, burned by software
   before, decides slowly) means a company's own CAC payback for acquiring *that specific buyer* is
   likely to run toward the slower end of the SMB range (8-12 months), not the fast
   self-serve/PLG end (~6.2 months) that a lighter-touch SaaS product might hit. A seat benchmarking
   a company's payback against the aggressive low end of the SMB range risks setting an unrealistic
   bar for a buyer who does not self-serve-sign-up on impulse. Where a company's actual payback is
   measured, prefer the 8-12 month SMB band as the more honest comparison set for a slow-decision,
   trust-gated buyer, and flag the 6.2-month figure as applicable to a different (self-serve,
   low-trust-friction) buyer profile.

For a B2C local-service company (e.g. a residential contractor or a dental practice selling
directly to consumers), CAC/LTV framing is even further from the buyer's own vocabulary, but the
same internal discipline (payback against contribution, never against price) applies unchanged —
only the persona file and channel mix differ.
