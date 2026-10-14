# Paid Acquisition — Anti-Patterns

Things a paid-acquisition-strategist seat must NEVER recommend, propose, or auto-apply. Each
entry names the mechanism that makes it wrong and, where one exists, the incident that produced
the rule. Most entries are tagged `(ported incident-derived mechanism, <date>)`: mechanism carried
forward from a prior Google Ads / Meta Ads guardrail set with no locatable primary source, dollar
figures and numeric thresholds re-derived or marked `UNVERIFIED — seeded, needs derivation`.

**Note on this corpus's provenance tags (the single definition — sibling files point here):**
`../shared/citation-style.md` defines six sanctioned tags — `(official)`, `(third-party)`,
`(internal-measured)`, `(internal doctrine)`, `UNVERIFIED — seeded, needs derivation`, and
`UNVERIFIED (primary source unreachable: <url>)` — and defines `(internal-measured)` as data "from
the company's own account data, the operator's own reported experience, or a number produced by
running the company's own tooling." This runtime corpus is shared across every company, so it never
uses `(internal-measured)`. Its "Ported-incident citations" section says to cite an incident-backed
rule as `(internal doctrine, incident: <short label>)` and to tag any borrowed number `UNVERIFIED`;
this corpus's two `ported` labels below predate that wording and are held to the STRICTER status —
they are **sub-labels of `UNVERIFIED — seeded, needs derivation`**, never a seventh tier, because the
incident's own record is not in this corpus to check. Each label below carries exactly the
evidentiary status `UNVERIFIED` carries (no independently checkable primary source in this corpus)
and adds only which kind of gap it is:

- `(ported incident-derived mechanism, <date>)` — a mechanism carried forward from an untraceable
  prior guardrail set.
- `(ported build-incident, <date>)` — a specific dated build attempt whose account-level detail
  lives in the measuring company's own dossier.
- `UNVERIFIED — evidence not yet relocated` — the evidence exists in one company's records but has
  not been written into that company's dossier yet.
- `UNVERIFIED — primary source not located` — no official source could be found at all.
- `UNVERIFIED — needs a direct fetch` (optionally `… of the current official specs`) — an
  official page is known to exist but was not fetched in this pass.
- `UNVERIFIED — primary source unreachable` — shorthand for `citation-style.md`'s own
  `UNVERIFIED (primary source unreachable: <url>)` tag; name the URL where one is known.

Moving these sub-labels into `citation-style.md` itself is open follow-up work; until then this
note governs.

---

## 1. Round-number budgets with no derivation

**Never propose "$80/day" or any budget that isn't expressed as a formula.** A budget must be
stated as `{multiplier}x tCPA = {result}/day` with the multiplier and tCPA both cited. A bare
dollar figure with no derivation is an automatic rejection under the Grade-A §0 self-check.

Why: a round number is a guess dressed as a decision. It cannot be defended, cannot be audited
against the account's own economics, and drifts from whatever the account can actually support.
(Ported incident-derived mechanism, 2026-07; original source not re-fetchable from the runtime —
ported as a structural rule, not a dollar figure.) See [`budget-as-formula.md`](budget-as-formula.md).

## 2. Learning-period fragmentation

**Never modify a campaign, ad group, ad, keyword, or bid strategy before it clears its minimum
age AND minimum data volume**, and never treat Ad Strength (POOR/AVERAGE/GOOD/EXCELLENT) as an
action signal during that window — PENDING means Google hasn't evaluated yet, never a reason to
act.

Why (ported incident-derived mechanism, 2026-07; original source not
re-fetchable from the runtime): an agent paused 1-2 day old RSA ads for "POOR" ad
strength, fragmenting Google's learning period before any real performance data existed. Ad
Strength can read POOR on day 1 and GOOD by day 14 with zero changes made (the specific day-1/
day-14 span: UNVERIFIED — seeded, needs derivation; the load-bearing fact is that the rating can
swing with zero changes made, not the exact number of days). Ad Strength is a
Google-stated feedback tool, not a performance or auction signal — "Ad Strength is a feedback
tool for asset diversity and combination testing. It isn't used to calculate Ad Rank, Quality
Score, or auction wins." ([Google Ads Help: About ad strength](https://support.google.com/google-ads/answer/9921843),
official, retrieved 2026-09-19.) See [`learning-period-gates.md`](learning-period-gates.md) for
the full age/volume table.

## 3. Negativizing demand — the accepted-segment and brand-negative traps

**Never blanket-negativize a brand or payer term without first checking whether it is a
competitor (negativizable) or an owned/accepted segment (never negativizable as a bare term).**
And never apply a brand negative at PHRASE or BROAD match — brand negatives are EXACT match only,
plus explicit variants (misspellings, plurals, word-order), because negative keywords do not
match close variants the way positive keywords do.

**Never negativize the name of a payer, insurer, financing partner, or manufacturer the business
is in-network with or authorized by, without confirming the relationship first.** A search for
"[payer] dentist"/"[financing partner] contractor"/"[manufacturer] authorized dealer" is a
high-intent in-network prospect, not waste — negativizing that payer/partner/manufacturer name as
if it were a competitor suppresses valuable demand instead of cutting waste. For the contractor
vertical specifically: never negativize a financing partner, a supplier co-op brand, or a
manufacturer name the business is an authorized dealer for, without first confirming the
relationship (query it against the company's own accepted-payer/authorized-dealer list before
touching the negative list).

Why (ported incident-derived mechanism, 2026-07, live production failure; original source not
re-fetchable from the runtime): the narrative recommended negativizing an owned/accepted payer
term as wasted spend for a business that was actually in-network with that payer — the specific
account, payer name, and date belong in the measuring company's own paid-acquisition dossier
(`<home>/.claude/oversight/paid-acquisition-strategist.md` and its `marketing_kb_state/`), tagged
`(internal-measured)` there where the company-scoped meaning applies, never named in this shared
runtime file. A PHRASE negative on a competitor's name also blocks "alternatives to X" and "X vs
us" switcher queries — exactly the prospects actively shopping away from that competitor. See
[`negative-keyword-hygiene.md`](negative-keyword-hygiene.md).

## 4. Broad match with Smart Bidding on day one (or on low volume)

**Never pair broad match with a Smart Bidding strategy (Maximize Conversions, Target CPA, Target
ROAS) on an account below the volume floor for that strategy.** Broad match without Smart Bidding
sprays waste on generic terms; broad match on Manual CPC is explicitly dangerous — modern broad
match relies on the algorithm's conversion signal to stay targeted, and Manual CPC gives it none.

Why: this is the single most common way a new account burns its first month of budget. Google's
own push toward broad-match-plus-Smart-Bidding (UNVERIFIED — seeded, needs derivation; a directional
observation about Google's product direction, not sourced to a specific dated official statement)
is real and effective — but only once the
account has cleared the conversion-volume floor for the bidding strategy it's paired with (see
[`bid-strategy-ladder.md`](bid-strategy-ladder.md)). Below that floor, start Exact + Phrase and
build negatives aggressively (ported incident-derived mechanism, 2026-07; original source not
re-fetchable from the runtime).

## 5. Raising budget or bids into a zero-conversion funnel

**A budget or bid raise may never target a campaign, ad group, or keyword with zero counted
conversions in the measurement window** — regardless of how much raw impression share or spend it
is losing. A 0-conversion funnel is always Hold or Reassess, never Act.

Why: a raise into a funnel that has never converted just buys more of whatever isn't working, at
a higher run rate. This holds even when the funnel is heavily rank-limited or budget-limited — fix
the underlying cause (tracking, relevance, bid) and verify a real conversion signal before ever
raising spend into it (ported incident-derived mechanism, 2026-07; original source not
re-fetchable from the runtime).

## 6. Funding the campaign losing the most raw dollars, not the cheapest one

**Never raise budget on whichever budget-capped campaign is losing the most absolute dollars to
its cap without first comparing its cost-per-conversion to the other candidates.** Two campaigns
can both be budget-capped while one converts at $50/lead and the other at $200/lead — only the
efficient one should get the incremental dollar.

Why (ported incident-derived mechanism, 2026-07; original source not re-fetchable from the
runtime): funding by raw lost-dollars alone rewards whichever campaign happens to
have the biggest number attached to its cap, with no regard for whether that spend converts. A
raise is warranted only when budget-lost impression share dominates rank-lost by at least 1.5x
AND the campaign's own CPA is not materially worse (≥2.5x) than the cheapest other candidate or
the account average (both multipliers: UNVERIFIED — seeded, needs derivation; these are heuristic
starting points, not platform-defined or independently benchmarked figures — re-derive per account
before treating either as load-bearing).

## 7. Trusting a conversion count with no live verification

**Never trust a media metric (CPA, conversion rate, budget-lost impression share, wasted spend)
computed against a conversion action that hasn't fired a counted, primary conversion in the last
48 hours.** "Broken" and "genuinely no demand" are indistinguishable from the number alone —
tracking must be physically tested before any budget decision is made on top of it.

Why (ported incident-derived mechanism, 2026-07; original source not re-fetchable from the
runtime): a call action that rings the wrong office still "fires" a conversion — the 48-hour
fire-check (see [`measurement-and-attribution.md`](measurement-and-attribution.md)'s 48-hour
physical-verification rule) is necessary but not sufficient. See that same file for the full
4-signal test.

## 8. "Wrong number" diagnosed from inference, not from reading the actual asset

**Never assert a call-tracking or call-asset "wrong number" without first enumerating every
call asset (account + campaign level) and comparing its actual digits against the canonical
number.** If every number is correct and calls still go astray, the cause is almost always a
targeting/intent mismatch (competitor-name bidding, overly broad match), not a phone problem.

Why (ported incident-derived mechanism, 2026-07; original source not re-fetchable from the
runtime): a review diagnosed a leftover "Smart Campaign with a wrong call number" and told the
operator to remove it, when every call asset actually showed the canonical number and the real
cause was targeting. Read `asset.call_asset.phone_number` (and `country_code`) for every call
asset at account and campaign level via GAQL and compare it against the canonical number
programmatically — the v22 SDK defines `CallAsset.phone_number` as "Required. The advertiser's raw
phone number," directly readable (`google/ads/googleads/v22/common/types/asset_types.py`,
installed SDK, generated protobuf). Escalate to the operator for a UI confirmation only when the
API read itself fails, never as the default path for data the API already returns — see
[`../../marketing_director_primer.md`](../../marketing_director_primer.md)'s OPERATOR-residue
classification (only a genuine taste/spend/identity/judgment call goes to the operator; data the
API already returns is not that).

## 9. Conquest with no evidence, no wrong-company-call measurement, or negatives that block switchers

Competitor-brand keyword bidding on Search is a **standard tactic, never an off-limits one** (full
mechanism: [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md), "Competitor-brand
keyword bidding on Search," which cites this entry as its precondition). Inside an
operator-approved budget it is a **within-ceiling optimization**: agent-executable by the
department's execution lane after the reviews the company's autonomy level requires, with no
separate operator confirmation and no operator-confirmed "conquest goal" needed. This seat itself
only recommends and specifies it — it holds no write access to any ad platform (see
`agents/paid-acquisition-strategist.md`).

**The precondition is evidence, not permission.** The anti-pattern is recommending or sizing
conquest with any of these missing:

- **(a) No evidence on expected CTR or conversion rate for the specific competitor term.** Someone
  searching a competitor's exact name has often already chosen that business — conquest there can
  produce low expected CTR and ad relevance (the actual auction-time quality signals; see
  [`account-audit-rubric.md`](account-audit-rubric.md)'s mental-model section on why Quality Score
  itself is a diagnostic, never an auction input), raising cost per click for an irrelevant match,
  plus wasted spend and "wrong-company" calls — but this is a thing to measure per term, not assume
  universally; some competitor terms convert well and some don't.
- **(b) No plan to measure wrong-company calls** (see #8, "read the actual asset, don't infer") once
  the campaign is live — conquest volume with no wrong-company-call tracking cannot tell efficient
  spend from wasted spend.
- **(c) No exact-match-only negative plan for the business's own brand terms**, so the conquest
  campaign doesn't accidentally cannibalize the business's own brand-defense traffic.

**Money gates money — and only money.** Per the governing plan's money rule (stated in plain
language in [`../../paid_acquisition_strategist_primer.md`](../../paid_acquisition_strategist_primer.md)
§4):
- adding or changing a competitor keyword inside an already-approved budget is **not `$`**;
- building a new conquest campaign **PAUSED**, even with a budget field set, is **T1 construction,
  not `$`** — a paused campaign's budget is committed only at enable;
- **enabling** that campaign (committing its budget), or setting or raising any budget or cap to
  fund it, is **`$`** and goes to the operator as a data-backed proposal for signed sign-off.

**Never default to negativizing a named competitor.** A PHRASE-or-broader negative on a
competitor's name blocks "alternatives to X" and "X vs us" switcher queries — exactly the prospects
actively shopping away from that competitor (see #3). There is no default competitor negative: if
one is warranted, it is EXACT match only and a deliberate, stated choice with its reason recorded.

Why (ported incident-derived mechanism, 2026-07; original source not re-fetchable from the
runtime): the original incident behind this rule was a conquest recommendation made with no
CTR/conversion evidence and no measurement plan, not competitor-brand bidding itself.

## 10. Narrating "applied" before verifying the live account

**Never say a change was "applied," "added," "live," or "done" off a queued or approved step.** An
approval flipping to "approved" is not the same as the mutation executing successfully — the
executor runs afterward and can fail. Read the live state back (the negative list, the campaign
setting, the conversion action) before claiming a change took effect.

Why (ported incident-derived mechanism, 2026-07, live production failure; original
source not re-fetchable from the runtime): a negative-keyword add and a
conversion-action demote were both approved and the assistant reported "applied to the live
account" while the executor actually failed with a schema error — nothing landed.

## 11. Deleting instead of pausing

**Never delete a campaign, ad group, ad, or positive keyword.** Pause only. Deletion destroys
historical performance data and the ability to mine a paused entity later for proven keywords,
winning ad copy, and negative-keyword history.

**Pausing itself is not automatically autonomous.** Pausing a campaign or ad set changes committed
spend and is `$` under the money rule ("stopping spend (pausing, lowering) is `$` too" — see
[`../../paid_acquisition_strategist_primer.md`](../../paid_acquisition_strategist_primer.md) §4):
it goes to the operator as a data-backed proposal and is never approved by a bare chat statement.
Pausing a single ad, ad group, or keyword inside an unchanged budget does not change committed
spend; it is a within-ceiling optimization that follows the company's ordinary autonomy level. "Pause
only, never delete" governs WHICH action is safe to take; it does not by itself say WHO may
authorize taking it.

Why: this is a hard, no-discretion rule across every paid channel this corpus covers (Google Ads,
Meta). The one carve-out is negative-keyword-LIST hygiene — adding, removing, or correcting a
negative entry is list curation, not deleting a serving entity, and carries no performance history
to lose.

## 12. Writing to a PAUSED or REMOVED campaign

**No negative keyword, budget change, bid change, bid-strategy change, or settings change may
ever target a campaign that is not ENABLED.** A paused campaign is read-only historical data — the
one narrow exception is a plain-text suggestion to re-enable it, never a tool-bound action. This
rule governs an already-live account being OPTIMIZED; it does not apply during a brand-new
campaign's initial construction, where campaigns/ad groups/ads are deliberately built PAUSED and
never yet served — see [`api-build-mechanics.md`](api-build-mechanics.md), "Build campaigns/ad
groups/ads PAUSED," for that carve-out and exactly where the boundary between construction and
optimization falls.

Why (ported incident-derived mechanism, 2026-07; original source not re-fetchable from the
runtime): a negative-keyword approval flow wrote targeted campaign IDs resolved outside the normal
snapshot pipeline, and nothing stopped a mutation from being proposed against a non-ENABLED
campaign.

## 13. Recycling LOW-rated ad assets without a rewrite rationale

**Never reuse a headline or description Google's own asset-level reporting has rated LOW without
documenting why.** A LOW rating after sufficient impressions is a real signal; recycling it
because it's already written is lazy, not efficient.

Why: the asset-level performance label already tells you the combination algorithm is deprioritizing
that text against real serving data — carrying it forward unexamined into a new campaign or ad
group just imports the same weak performer into a fresh learning period, where it starts over with
no signal and only degrades again once enough impressions accumulate. (The specific mechanism by
which Google computes and surfaces the LOW/GOOD/BEST label is UNVERIFIED — seeded, needs
derivation; re-derive from Google Ads Help's asset-performance-label documentation before citing a
specific threshold or computation method.)

## 14. Treating a Google-queued "recommendation" as pre-approved

**A Google Ads auto-apply recommendation, an in-product nudge, or a backlog item is a request to
EVALUATE, never an approval.** It must pass the same review and approval gate as any other
proposed change. "Google recommended it" is never authorization on its own. **Auto-apply itself
stays disabled at the platform level, and turning any auto-apply type ON is `$`** — Google Ads lets
an advertiser opt certain recommendation types into applying automatically with no review, and
enabling one removes the human/agent review step from future spend-affecting changes. This is not
an identity/structure notify-then-execute action: it is a `$` item under the governing plan's
money rule (auto-apply is kept OFF; turning it on is `$` — see
`../../paid_acquisition_strategist_primer.md` §4), which means it needs the
operator's explicit sign-off on a data-backed proposal, never a notify-then-execute action an agent
completes on its own after posting a notice. Never turned on by an agent as a convenience, and
never turned on by an agent at all without that sign-off in hand.

## 15. Financing-led ad copy that trips Special Ad Category or skips TILA disclosure

**Never lead ad copy with a specific monthly payment, APR, or "easy/guaranteed approval" language
for a financing offer**, and never omit the required disclosure anywhere a payment or
rate figure appears — Regulation Z's advertising rule requires that an ad stating a specific credit
term (a payment amount, a rate) also disclose the other required terms, including the annual
percentage rate stated as such (12 CFR § 1026.24, official, eCFR, retrieved 2026-09-27 — [text](https://www.ecfr.gov/current/title-12/chapter-X/part-1026/subpart-C/section-1026.24)).
A financing-forward ad can pull Meta's classification into the Financial Products & Services
special ad category, which restricts targeting. **Confirmed by the official source: a minimum age
of 18 is required** — "Ads promoting credit cards, loans or insurance services must be targeted to
people 18 years or older" ([Meta Transparency Center: Financial Products and Services](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/),
official, retrieved 2026-09-27, re-fetched and full-text-checked 2026-09-27 — this page states only
the 18+ floor; it never states an upper age bound, never mandates a full 18-65+ range, never
prohibits narrower age targeting within 18+, and never mentions Lookalike Audiences, Advantage+, or
detailed-targeting expansion anywhere on the page). **Everything beyond the 18+ floor is
UNVERIFIED — seeded, needs derivation:** the claim that age must span the *full* 18-65+ range (no
narrower targeting permitted), and the claim that Lookalike Audiences and Advantage+ detailed-
targeting expansion become unavailable, are carried forward from a prior guardrail set with no
locatable primary source (see [`meta-ads-doctrine.md`](meta-ads-doctrine.md) §8 for a related,
similarly-uncited restriction list — the two lists do not fully agree and neither is sourced to a
fetchable Meta Business Help page as of this retrieval). **Before relying on either the full-range
claim or the Lookalike/Advantage+ claim for a live proposal, re-verify live in Ads Manager at
campaign-creation time** — Meta's own special-ad-category UI shows the actual active restrictions
for the account's current campaign type, which is a stronger source than any of this corpus's own
prior text. Keep financing soft-secondary; lead with the service, not the payment plan (for a
remodeler, see the Contractor bend below).

## 16. Fabricated or AI-generated before/after imagery

**Never use a fabricated, staged, or AI-generated "before/after" transformation image in ad
creative.** A before/after image functions as a testimonial to the product/service's effectiveness
and is subject to the FTC's endorsement and testimonial rules; a fabricated or misleadingly altered
before/after image is deceptive under those rules (16 CFR Part 255, Guides Concerning the Use of
Endorsements and Testimonials in Advertising, official, eCFR, retrieved 2026-09-27 — [text](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255)).
This is a real regulatory exposure, not a style preference, for any business whose ad creative uses
before/after imagery — see the Contractor bend section below for why it lands with particular force
on a remodeling brand specifically.

## 17. Comparing Meta and Google "conversions" one-to-one

**Never present a cross-channel conversion comparison as apples-to-apples** — the two platforms
use different attribution models and windows. Compare each channel to its own cost-per-booked-job
trend, not to the other platform's raw conversion count.

Why: Google Ads and Meta each attribute a conversion under their own model and lookback window, and
neither dedupes against the other (UNVERIFIED — seeded, needs derivation; re-verify against each
platform's current cross-platform attribution documentation rather than assuming this holds
unchanged) — the same real lead can be counted as a Google conversion, a
Meta conversion, or both, depending on click order and window overlap. Ranking "Google converts at
40, Meta at 25" as if the two numbers measured the same thing produces a channel-mix decision built
on an artifact of two different counting methods, not a real performance difference.

## 18. Skipping the account audit before touching bids or budget

**Never run bid, budget, or keyword optimization on an account that hasn't cleared the audit
gate** (structural completeness, conversion-tracking verification, no orphaned campaigns/ad
groups). Optimizing on top of a structurally broken account compounds the defect. See
[`account-audit-rubric.md`](account-audit-rubric.md).

## 19. Trusting a "validated clean" claim with no positive control

**Never report "validated clean" as evidence a campaign build is correct unless the validator's
own ability to report an error has been proven, and the report states which operations were
actually sent.** A Google Ads `validate_only=True` response carries **no `results`** — no created
`resource_name`. Any operation whose parent is created earlier in the same build therefore has
nothing to resolve against and fails as "cannot resolve parent" regardless of whether the
operation itself is valid — batching the whole dependent chain into one atomic
`GoogleAdsService.mutate` with temporary negative-id resource names is the fix for that specific
cascade, and IS the right way to build a multi-step campaign structure (see
[`api-build-mechanics.md`](api-build-mechanics.md), "Batched atomic mutate with temporary resource
names").

**A "validated clean" result is not evidence on its own — it is evidence only once two things are
both true:** (1) a positive control — a deliberately invalid operation run through the identical
validate path — proves the validator/extractor can actually surface an error when one exists, and
(2) the report states operations sent vs. operations skipped client-side before ever reaching the
API. Absent either one, "clean" is indistinguishable from "the validator was incapable of
reporting a failure" or "the risky operations never left the client." A batched, well-formed
`validate_only` pass genuinely DOES return real per-operation content errors — including
structured-snippet value-count/length violations (`collection_size_error: TOO_FEW`,
`string_length_error: TOO_LONG`) and RSA duplicate-asset rejections (`asset_error:
DUPLICATE_ASSET`) — when the operation actually reaches the API and the report-extraction path
is sound; see [`api-build-mechanics.md`](api-build-mechanics.md) and
[`asset-authoring-constraints.md`](asset-authoring-constraints.md) for the specific constraints.

**Root cause of a false "clean" (ported build-incident, 2026-09-19 — deliberately NOT
`(internal-measured)`, since `../shared/citation-style.md` defines that tag as the company's own
account data, and this runtime corpus is shared across every GTM-managed company):** a batched `validate_only` pass reported zero errors, and a
subsequent real (executing) pass against the same in-scope batch then produced content-level
rejections the "clean" validate pass had not surfaced. The validate pass was never actually clean
evidence — two independent defects made it look that way: the tooling's own error-extraction path
could not have surfaced a per-operation content error regardless of what the API returned (a
report-parsing defect, not a platform behavior), and a subset of asset operations had been skipped
client-side before ever being sent to the API, so the API was never asked to validate them at all.
Neither defect is a `validate_only` blind spot — both are the tooling misreporting what happened.
**The specific evidence (which account, request/response captures, defect writeups) belongs in the
measuring company's own paid-acquisition dossier, IF that company has recorded it there** — never
assume it is recorded; a missing record there is a gap in that company's dossier, not something
this runtime file can point to as if it already existed.

**Rule: a "validated clean" claim is not evidence until (a) a positive control shows the validator
CAN report an error, and (b) a sent-vs-skipped operation count accompanies the claim.** Keep local
pre-flight validators as cheap defense-in-depth regardless of API-side validation — they catch
obvious defects before spending a request — but never treat a locally-clean pre-flight check, or an
unproven "validated clean" API response, as a substitute for (a) and (b). State the distinction
plainly in any launch report: "positive-control-proven validate pass, N operations sent / M
skipped, zero content errors" — never a bare "validated clean."

Why: an unproven "clean" report is worse than no report, because it manufactures false confidence
that a build is content-correct when nobody has actually shown the check could catch a defect. See
[`api-build-mechanics.md`](api-build-mechanics.md), "Build campaigns/ad groups/ads PAUSED" and
"Batched atomic mutate with temporary resource names," for the full build-execution mechanics this rule
depends on.

---

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

Within that scope, when the ad-account owner is a small contractor (a GC, remodeler, or similar trade business) who
was burned by a prior agency or marketing vendor before, these anti-patterns land differently than they
would for a marketing team at a larger, more sophisticated advertiser. This is conditional vertical
doctrine, not a fixed persona this corpus assumes for every account — read the ICP specifics
(revenue band, buyer psychology, prior-vendor history) from that company's own persona profile or
dossier, and apply the pattern below only when the account actually fits it:

- **Round-number budgets are exactly what a prior agency probably sold a burned buyer** ("just do
  $100/day"). Leading with a derived formula, shown plainly, is itself a trust-rebuilding move —
  it demonstrates the number isn't a guess.
- **The "wrong number" trap is especially live for a small contractor** whose call-forwarding
  number changed vendors, or whose office manager fields calls on a personal cell that later got
  reassigned to a new hire. Verify the literal digits before ever blaming targeting.
- **Conquest-campaign temptation is high for a contractor, and #9's measure-per-term rule still
  governs it** — a customer who searched a named competitor's business has often already gotten a
  quote from them, so the CTR/conversion evidence #9 requires is frequently unfavorable for this
  vertical. That is a reason to gather the evidence (a small, measured test inside the approved
  budget) before scaling conquest, not a reason to skip measuring and assume the outcome. Where the
  evidence comes back unfavorable, shift keyword focus toward brand defense and the business's own
  high-intent generic terms inside the approved budget (within-ceiling); any change to a
  campaign's budget is a separate `$` proposal (primer §4).
- **"Applied" vs "queued" matters enormously to an owner-operator who checks their phone
  infrequently between jobs.** If a change is reported as live and it silently failed, they have no
  way to notice until a week of flat leads makes them assume the whole channel is dead — and they
  blame the channel or whoever set it up, not the silent failure. Verify before reporting, every time.
- **Financing-copy discipline is not optional for a remodeler** — home-improvement financing
  ("$99/month bathroom remodel") is a frequently-cited contractor-marketing compliance failure
  (UNVERIFIED — seeded, needs derivation; treat "one of the most common" as an unbenchmarked
  characterization pending a sourced frequency figure), and it directly damages the loan officer
  relationship a remodeler depends on for larger jobs. Apply #15 by leading with the remodel
  itself, never the payment plan.
- **The before/after-imagery rule (#16) lands with particular force on a remodeling brand** whose
  entire pitch rests on real craftsmanship — a fabricated or misleadingly altered before/after image
  is a direct hit against the one thing that differentiates a premium remodeler from a
  discount competitor, on top of the regulatory exposure #16 already describes.

For a non-contractor account, or a contractor whose own persona profile states a different buyer
psychology, apply the underlying anti-patterns unchanged and read the persona bend from that
company's own dossier instead of this section.
