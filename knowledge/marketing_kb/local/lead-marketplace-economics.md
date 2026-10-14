# Lead-Marketplace Economics — Cost Per Booked Job

Corpus for the `local/` domain. Company-agnostic: every example below is generic, not a real
company's account or numbers. Citation format per `shared/citation-style.md`; claim ids continue the
`[KB-LOCAL-NNN]` sequence started in `yelp.md` (highest in use before this file: `KB-LOCAL-039` in
`nextdoor.md` — this file starts at 040). Retrieval date for every claim below: 2026-09-27, unless
noted otherwise.

This file does not restate any platform's own mechanics (lead pricing model, dispute policy, role
structure) — those live in that platform's own file in this directory. This file owns exactly one
question: **given all of them charge differently, how does a GTM agent compare them on the metric
that actually matters to the buyer** — cost per *booked job*, not cost per lead, cost per click, or
cost per contact.

---

## 1. Why "cost per lead" is the wrong comparison metric

**[KB-LOCAL-040]** Every platform in this directory charges on a different unit: Yelp Ads bills
per-click (`local/yelp.md` §4); Thumbtack bills per-lead with two structurally different lead types
at different price points (`local/thumbtack.md` §1); Angi/HomeAdvisor bills per-lead with a
lead-credit dispute system that prices in some fraction of non-converting leads as non-refundable
(`local/angi-homeadvisor.md` §2); Houzz Pro's marketplace-adjacent lead product and Nextdoor's Ads
Manager have their own separate cost structures again. **Mechanism, not a numbered claim:** because
the billing unit differs across every platform, "cost per lead" and "cost per click" are not
comparable across this list — e.g. a hypothetical $12 Yelp click and a hypothetical $45 Thumbtack
Instant Match lead are not the same kind of number, and ranking platforms by raw per-unit cost
produces a meaningless ranking.

**[KB-LOCAL-041]** (internal doctrine) The only unit that is genuinely comparable across every
platform in this directory is **fully-loaded cost per booked job**: total dollars spent on that
platform in a period, divided by the number of jobs actually booked (signed contract or deposit
taken) that are attributable to that platform in the same period. This is a standard paid-channel
unit-economics method, not a platform-specific one — it is the same logic a marketer applies to
compare Google Ads against Meta Ads against a print-mail campaign, restated here for lead
marketplaces specifically (mechanism derived from `pricing/cac-ltv-payback.md`'s fully-loaded CAC
method; the platform-specific inputs below are what makes it computable per marketplace).

**Reject example:** telling an operator "Angi is cheaper than Thumbtack" because Angi's average
lead price is lower, without accounting for close rate, dispute-credit recovery, or the labor cost
of following up on leads that were never eligible for the platform's own credit policy
(`local/angi-homeadvisor.md` [KB-LOCAL-019]).

**Pass example:** computing cost per booked job separately for each platform over the same
trailing period, using the formula in §2, before recommending a budget shift between platforms.

## 2. The formula and its required inputs

**[KB-LOCAL-042]** (internal doctrine, derived from `pricing/cac-ltv-payback.md`'s fully-loaded CAC
method) Cost per booked job, fully loaded:

```
cost_per_booked_job = (gross_spend - net_credits_recovered + attributable_labor_cost)
                       / jobs_booked
```

Where, for a given platform and period:
- **gross_spend** — total dollars actually charged by the platform (ad spend, per-lead charges,
  subscription/software fee if the platform bundles one, e.g. Houzz Pro's CRM tier).
- **net_credits_recovered** — dollars actually returned as usable credit under that platform's own
  dispute policy (e.g. Angi/HomeAdvisor's [KB-LOCAL-016]–[KB-LOCAL-018]), counted only once
  redeemed against a future charge, not merely "requested" or "approved" — an approved-but-unused
  credit that later expires (Angi's six-month expiry, [KB-LOCAL-016]) contributes zero, not its
  face value, once it lapses.
- **attributable_labor_cost** — the real cost of staff time spent following up on that platform's
  leads (calls, texts, quotes written) in the period, apportioned by lead volume from that
  platform. This term is the one most often left out of a naive comparison, and it is exactly the
  term that penalizes a marketplace with a high volume of low-intent or unqualified contacts (see
  `local/angi-homeadvisor.md` [KB-LOCAL-019] on non-refundable low-intent leads) — a platform that
  looks cheap per lead can be expensive per booked job once the labor to work every dead-end lead
  is counted.
- **jobs_booked** — a signed contract or a deposit actually taken, attributed to the platform via
  the lead's own origin field (never inferred from memory of "where most of our leads come from" —
  this mirrors the general local-doctrine live-read discipline already established in
  `local/nap-consistency.md` [KB-LOCAL-022] and `seo/local-seo-for-contractors.md` §6: read the
  actual CRM/lead-source record, don't estimate it).

**No general-purpose numeric benchmark for this formula's output is recorded in this file** — a
specific cost-per-booked-job figure is inherently a real business's `(internal-measured)` record
(per `shared/citation-style.md`), never a number this doctrine file can assert as typical across
an unspecified home-services business. Any specific figure quoted to an operator must cite that
operator's own CRM/billing data with a retrieval date, not this file.

## 3. Platform-specific inputs the formula must account for

**[KB-LOCAL-043]** Each platform's own mechanics change what belongs in `gross_spend` and
`net_credits_recovered` — this is *why* the comparison must be done platform-by-platform rather than
by a shared assumption:

- **Yelp Ads** — no lead-credit/dispute system comparable to Angi's exists in this corpus's Yelp
  doctrine; `gross_spend` is simply the CPC total for the period, and the auction-driven CPC plus
  confirmed-uneven daily pacing (`local/yelp.md` [KB-LOCAL-011], [KB-LOCAL-012]) means a monthly
  Yelp figure can swing period-to-period for reasons unrelated to lead quality.
- **Thumbtack** — the two lead types (`local/thumbtack.md` §1) must be tracked separately before
  being summed, because Instant Match (Direct Leads) and Opportunities have structurally different
  price points and response mechanics; a blended average across both types obscures which one is
  actually producing booked jobs at what marginal cost.
- **Angi/HomeAdvisor** — `net_credits_recovered` is a real, nonzero term here specifically because
  the platform has a formal, cited dispute-credit mechanism (`local/angi-homeadvisor.md`
  [KB-LOCAL-015]–[KB-LOCAL-018]); a comparison that uses only `gross_spend` and ignores recovered
  credits overstates Angi's true cost, while one that treats *requested* (not redeemed) credit as
  recovered understates it — use redeemed credit only, per §2.
- **Houzz Pro** — Houzz Pro bundles a project-management/CRM product with its lead/marketplace
  surface (`local/houzz-pro.md` §1 intro); if the subscription fee is paid regardless of lead
  volume for its CRM value alone, apportioning 100% of the subscription cost into a lead-economics
  comparison overstates that platform's true cost-per-booked-job relative to a pure pay-per-lead
  platform — the fee should be split between "software cost" and "lead-generation cost" based on
  how the business actually uses the product, stated explicitly whenever this comparison is run,
  never silently assumed.
- **Nextdoor** — the free Business Page and the paid Ads Manager (`local/nextdoor.md` §1) are
  separate surfaces with separate cost profiles; a job attributable to organic Business Page
  activity has a `gross_spend` of $0 for that channel (making its cost-per-booked-job calculation
  degenerate/undefined in a useful way — flag it as "organic, not comparable to a paid channel," not
  as "infinitely efficient") and must not be blended into the paid Ads Manager figure.

## 4. Comparing across platforms — the decision frame, not a ranking

**[KB-LOCAL-044]** **This file does not, and cannot responsibly, rank the platforms in this
directory by cost-per-booked-job in general** — the real number depends on the specific business's
close rate, trade mix, service area, and labor cost, all of which vary enough between businesses
that a cross-business ranking would be exactly the kind of unsourced, seeded-from-nowhere number
`shared/citation-style.md` exists to prevent. **What this file provides is the method** (§2–§3); the
actual ranking must be computed per business from that business's own CRM/billing records before any
budget-reallocation recommendation is made.

**Reject example:** "Move budget from Angi to Thumbtack because Thumbtack is generally more
cost-effective for contractors" — asserted with no business-specific computation behind it.

**Pass example:** "Over the last 90 days, this account's own CRM data (`internal-measured`, dated)
shows cost-per-booked-job of $X on Angi and $Y on Thumbtack, computed per §2; recommend shifting
$Z of monthly budget from the higher figure to the lower one, watching close rate over the next
period to confirm the shift held" — a specific, sourced, reversible recommendation.

**[KB-LOCAL-045]** A platform showing an attractively low `gross_spend`-only cost per lead but a
high volume of leads explicitly excluded from that platform's own credit-eligibility list (see
`local/angi-homeadvisor.md` [KB-LOCAL-019] for Angi's named exclusions — no-show, window-shopper,
lost-to-competitor) is a candidate for a *labor-cost* problem, not necessarily a platform-quality
problem: the fix may be a faster speed-to-lead process or better lead-qualification screening on
intake, rather than abandoning the platform. Diagnose which term in the §2 formula is actually
driving a bad number before recommending a channel cut.

## 5. Re-verification cadence

**[KB-LOCAL-046]** Every platform's fee structure, credit policy, and lead-type mix is subject to
change without the kind of public changelog Google/Meta ad policies get (contrast with
`seo/schema-strategy.md`'s treatment of a dated, announced Google policy change) — re-pull each
platform's own current help-center pricing/dispute pages before anchoring a new cost-per-booked-job
comparison on a citation older than 90 days, per `shared/citation-style.md`'s general
re-verification guidance. Do not carry forward a prior period's platform-mechanics assumptions into
a new comparison without checking they still hold.

---

## Contractor bend — for home-services/contractor (`local_service`) companies

The owner-operator residential-remodeling GC archetype (whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona) does not think in "cost per lead" — they think "did that
platform pay for itself this month." Translate this file's whole method into one sentence for that
buyer: **"count what you spent, subtract what you got back in credits, add what your time following
up was worth, and divide by how many of those turned into a signed job — that's the only number that
tells you whether a platform is working."** Two things to watch for specifically with this buyer:
(1) they will often already sense which platform "feels" more productive from memory of recent jobs,
and that instinct is frequently wrong once labor cost and dispute credits are actually counted — run
the real numbers before confirming or correcting the hunch; (2) never let this buyer cut a platform
based on a single bad month — pull the same 90-day-minimum window this file's re-verification
cadence implies, since marketplace lead volume and lead quality both swing period-to-period for
reasons (seasonality, local competitor activity, the platform's own algorithm changes) that have
nothing to do with the business itself.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend across these platforms. Every claim id
in this file is unique within the `local/` domain; do not reuse `[KB-LOCAL-NNN]` numbers already
used by a sibling file in this directory (040-046 claimed by this file as of 2026-09-27; check every
sibling file's own range before adding a new claim to any file in this directory).*
