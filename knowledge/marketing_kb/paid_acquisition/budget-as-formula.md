# Budget as a Formula, Never a Round Number

## The core rule

**A budget is a formula, not a guess.** State every initial budget as
`{multiplier} x {target CPA} = {result}/day`, with the multiplier and target CPA both cited to
their source. "$80/day" with no derivation is an automatic rejection under the Grade-A §0
self-check (ported incident-derived mechanism, 2026-07 — history only, never a live source). "The account
history has no target CPA yet" is a valid state — say so explicitly and use a cited benchmark as
the assumption, don't invent a number.

Why this is a hard rule and not a style preference: a round-number budget cannot be defended, sized
correctly to a strategy, or audited later against the account's own economics. It's exactly what a
prior marketing vendor probably sold a first-time advertiser ("let's just start at $100/day") — and
it's indistinguishable, after the fact, from a guess that happened to be wrong.

## Budget sizing table by campaign type (ported structure)

The multiplier ranges below are a STRUCTURE ported from a prior internal ads discipline (ported
incident-derived mechanism, 2026-07 — history only). The ratio logic (why PMax needs more headroom
than Search, why Brand is a % of total budget rather than a tCPA multiple) is the load-bearing
part. **Every multiplier and percentage in the table is `UNVERIFIED — seeded, needs derivation`** —
cite it in a proposal as that, never as a platform or benchmark figure. (The Demand Gen row is the
one exception: its multiplier is Google's own published figure, cited in the row.)

**Scope.** The table is written for lead-gen service businesses (`business_model:
local_service` — contractors and practices alike). For a company whose pack declares a different
`business_model` (`b2b_saas`, `ecommerce`, `other`), the ratio logic still holds but the rows that assume
a phone-call/local lead funnel (LSA, Call-only) may not apply — read the funnel shape from that
company's pack and dossier, and cite any row you do use as the seeded structure it is.

| Campaign type | Initial daily budget formula | Notes |
|---|---|---|
| Search | 2-3x target CPA | Start Manual CPC or Maximize Clicks, not Smart Bidding, below the volume floor |
| Performance Max | 10-20x target CPA | Below ~3x tCPA, expect a "Limited by budget" signal — the floor exists because PMax needs headroom across all its inventory types to find volume |
| Local Services Ads (LSA) | Target cost-per-lead × expected weekly lead count = average weekly budget; after the Performance Max migration, that weekly figure ÷ 7 = daily budget | LSA is pay-per-lead and has no keyword bids, but the cap is still derived and shown as math. Setting or changing it (before or after migration) is a `$` item. See [`lsa-for-contractors.md`](lsa-for-contractors.md) |
| Brand | 20-30% of total paid budget | Manual CPC; do not apply smart bidding to brand |
| Remarketing / RLSA | 10-15% of total paid budget | Target CPA 30-50% below the generic-campaign equivalent, once list size supports targeting |
| Call-only | 10-20% less than the equivalent click campaign | Maximize Clicks initially; graduate to Target CPA once call-conversion data exists |
| Demand Gen (incl. YouTube/video inventory) | ≥10x target CPA per day | (official) "Your budget should be at least 10 times your target CPA" — Google Ads Help, "Demand Gen campaign performance guide", `support.google.com/google-ads/answer/16797388`, retrieved 2026-09-27. Demand Gen is this corpus's substitute for Video Action Campaigns (see [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md)), so YouTube video buys are sized with this row. Third-party posts quoting "15x" (e.g. developer-doc summaries) were not confirmed against a Google page — do not cite them. |

(A Shopping row is omitted: it assumes a product catalog, which a service business does not have;
re-add with its own provenance tag if a company's `business_model` needs it.)

## Home-services / contractor CPC and CPL benchmark ranges (third-party, re-derived for this vertical)

The ported multiplier structure above originated in a different (dental) vertical. Its numbers do
not transfer as facts to a remodeling contractor — different search volume, different competitive density, different job
value. The following are freshly re-derived for the home-services/remodeling vertical:

- **General home-services CPC (2026):** roughly $8-$45 per click across trades, with pest control
  and garage doors at the low end and plumbing emergencies, HVAC replacement, and storm-driven
  roofing at the high end. (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as
  "PPC Chief / industry aggregator" with no title or URL, so it cannot be re-opened.)
- **Remodeling/kitchen-and-bath CPC specifically:** roughly $8-$18 per click, higher in
  competitive metros. (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as
  Built-Right Digital — a vendor blog, practitioner opinion at best — with no title or URL.)
- **General home-services CPL (2026):** roughly $91 blended across trades. (Third-party —
  theEdigital 2026 benchmark aggregation, retrieved 2026-09-05 — a vendor blog, practitioner
  opinion, with no URL recorded; `UNVERIFIED — seeded, needs derivation` until re-located.)
- **Remodeling-specific CPL:** roughly $150-$400, with a maturity curve — entry-stage campaigns
  (new account, broad targeting, first ~60 days) run $120-$180/lead; growth-stage (3-6 months of
  optimization) run $90-$140/lead; scaled/mature accounts (12+ months, tight structure, strong
  Quality Score) run $70-$110/lead. (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05
  as an unnamed "industry-aggregator blog synthesis" with no publisher or URL — treat the specific
  dollar bands as directional, not precise; validate against the account's own data as soon as it
  exists, per the "own baseline first" rule below.)
- **Recommended starting monthly budget for a local remodeling contractor new to Google Ads:**
  roughly $1,500-$3,000/month; $3,000-$6,000/month in a competitive major metro.
  (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as "third-party" with no source
  named at all.)

**How to use these responsibly:** they are a sanity check for a brand-new account with zero
history, and a way to catch an obviously miscalibrated target CPA before launch — never a
substitute for the account's own measured numbers once it has them. Judge every account against
its OWN baseline first, then the segment goal, then the vertical benchmark band — in that priority
order. The purpose of any vertical band is the same: catch an unrealistic target before it burns a
month of budget.

## Setting an initial target CPA with zero history

For a genuinely new advertiser with no prior paid-search data, back into a target CPA from the
unit economics, not from a benchmark table alone:

```
expected close rate on booked estimates  x  average job gross profit  =  acceptable cost-per-lead ceiling
```

**No measured cost-per-lead figure from a real contractor account is recorded in this runtime
corpus** — measured figures belong in the measuring company's own dossier, never here. Do not cite a
specific dollar figure until one is confirmed against that company's own account export. The formula still holds
without it: whatever the GC's own measured cost-per-lead turns out to be, weigh it against their
own close rate on estimates sent and their own median job gross margin to get the real acquisition
math — always prefer the operator's own numbers, once they exist, over a third-party benchmark
band.

## Ramp discipline — the 20% rule (Google)

**On Google Ads, never increase a campaign's budget by more than 20% in a single week, and require
at least 7 days between increases.** Doubling a budget must be split into 2-3 steps over 2-3 weeks, never
one jump. See [`learning-period-gates.md`](learning-period-gates.md) for what specifically resets
Smart Bidding's learning when this rule is violated, and the 4-gate ramp-safety check before any
increase is proposed at all. Meta's pacing is different (~20% every 3-4 days) — see
[`meta-ads-doctrine.md`](meta-ads-doctrine.md) §6; never apply one platform's cadence to the other.

**A ramp plan is a schedule of separate `$` proposals; each increase needs its own signed approval
(primer §4).** Writing the ramp down never pre-approves any future step of it.

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A GC thinks in job-cost math, not marketing math.** Frame the budget formula in terms they
  already reason in: "if a lead costs $X and you close 3 in 10, and your average job nets $Y, then
  $Z/day is the number that pencils" lands better than "2x target CPA."
- **A small GC's whole annual marketing spend may be smaller than one month of a larger
  advertiser's budget** (read the company's actual revenue band from its own dossier). The multiplier-based sizing logic still applies, but present the monthly
  total up front, not just the daily figure — a GC budgets by the month or the season (spring/fall
  project-rush cycles), not by the day.
- **Round numbers are exactly what burned this buyer before.** Leading with the formula, shown
  plainly ("here's the math, here's the source"), is a trust-rebuilding move on top of being
  correct.
- **Job value variance is much wider for a remodeling GC than for a SaaS trial.** A kitchen
  remodel and a small bathroom repair can differ by 10x in job value from the same lead source —
  segment budget and target CPA by project type/landing page where volume supports it, rather than
  a single blended target CPA across a GC's whole service mix.
