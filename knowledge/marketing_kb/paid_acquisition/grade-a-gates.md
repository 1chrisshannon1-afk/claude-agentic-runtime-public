# Grade-A Gates — What Makes a Campaign Proposal Launch-Ready

Ported incident-derived mechanism, 2026-07 (original source not re-fetchable from the runtime) —
the standard exists because "left for UI" and "operator should check" proposals shipped incomplete
campaigns for real accounts. The core principle carries unchanged: **a campaign is not "done" until
every setting, every asset type, every modifier, every targeting dimension is either configured or
explicitly marked N/A with evidence.** "The operator can add that later" is a failure unless a
genuine technical blocker is documented.

---

## The phase-gate model

Work moves through six phases, each with a completion gate. Do not advance until the gate is
satisfied, and do not skip a phase or move backward:

| Phase | Gate | Artifact |
|---|---|---|
| Collect | Full data pull completed or documented failure | Export/rollup data present |
| Analyze | Evidence is numeric and run-scoped, not generic best practice | Research notes updated this session |
| Plan | §0 items 1–7 and 8(a) pass, and the proposal states its 8(b) post-build read-back plan (8(b) itself cannot be checked until after Execute) | Proposal doc marking each line `$` / T1 / within-ceiling |
| Approve | See "Approval is not one thing," below — a `$` item and a within-ceiling item clear different gates | Signed approval (for `$` items) or review record (for the rest) |
| Execute | Every plan item actually applied | Change log with before/after + reversal note |
| Verify | Post-change QA export confirms entities match the plan, AND §0 item 8(b) passes: every created ad's post-build policy `approval_status`/`review_status` is read back — ad policy review is asynchronous, so a clean build or a clean `validate_only` pass never proves an ad is actually approved to serve. 8(b) gates the later, separate enable (`$`) proposal, not the original Plan gate | Discrepancies documented and resolved; approval status recorded per ad |

### Approval is not one thing

**A specialist agent recommends; it never executes money, and a chat statement is never approval
for money.** The money rule — which items are `$`, T1, or within-ceiling, and what a valid `$`
approval is — is stated once, in
[`../../paid_acquisition_strategist_primer.md`](../../paid_acquisition_strategist_primer.md) §4
(from the governing plan, `~/.claude/plans/gtm_autonomous_department_plan.md` §20.6, §20.8,
§20.13). This section only applies it to the Approve gate:

- **`$` items** clear only with the operator's signed approval or the `owner_executed` fallback
  (primer §4). The proposal records which one, per line item.
- **T1 items** (a campaign, ad group or ad built PAUSED, even with a budget field set — see
  [`api-build-mechanics.md`](api-build-mechanics.md), "Build campaigns/ad groups/ads PAUSED")
  and **within-ceiling items** clear with the review record the company's autonomy level
  requires; this advisory seat never executes them itself.

A proposal that mixes kinds of item states each line item's class (`$` / T1 / within-ceiling) and
never treats one approval as clearing more than one class.

## Grade-A §0 self-check — 8 mandatory items (proposal-level)

Items 1–7 and 8(a) must pass before a proposal is presented, and the proposal must state how 8(b)
will be checked after the build. 8(b) itself is checked at Verify and must pass before any enable
(`$`) proposal is presented. Fix a failing item before submitting — never submit and hope it goes
unnoticed.

```
1. BUDGET_FORMULA — expressed as "Nx tCPA" with N and tCPA stated
   REJECT: any $/day amount with no derivation (e.g. "$80/day" alone)
   PASS:   "2x $75 = $150/day (Search, Max Clicks phase)"

2. PRE_LAUNCH_CHECKLIST — all 9 readiness items checked (see below)
   REJECT: any unacknowledged unknown item

3. BID_STRATEGY_LADDER — strategy matches the conversion-volume rung
   REJECT: any strategy that skips a rung of bid-strategy-ladder.md's table — the ladder is the
   only source of the numeric cutoffs; do not restate them here (see bid-strategy-ladder.md for
   the full ladder, including the ECPC-deprecated note)

4. RAMP_PLAN — states initial budget, the platform's own increase cadence (Google: <=20%/week,
   >=7 days apart, per budget-as-formula.md; Meta: ~20% every 3-4 days, per meta-ads-doctrine.md
   §6), and the 4-gate ramp check (see [`learning-period-gates.md`](learning-period-gates.md) for
   that check's definition). A ramp plan is a schedule of separate `$` proposals; each increase
   needs its own signed approval (primer §4) — the plan never pre-approves a future step.
   REJECT: "increase budget as needed" with no cadence stated; a ramp presented as approved in
   advance

5. CAMPAIGN_TYPE_RULE — cites the specific rule for this campaign type
   REJECT: Brand campaign on smart bidding; PMax launched with no feed/profile validation

6. MONITORING_CADENCE — a dated plan with window-specific allowed/prohibited actions
   REJECT: "monitor weekly" with no specific window rules

7. SOURCES_CITED — every numeric claim carries a citation
   REJECT: an uncited CPA benchmark, conversion threshold, or budget multiplier

8. BUILDABLE — checked in two parts, at two different phases; a plan cannot pass the Plan gate on
   part (a) alone and skip part (b) later — both are mandatory before the campaign is live.
   (a) Plan-time buildability, checked at the Plan gate: the proposed structure and asset set can
   actually be built via the API as specified.
   REJECT: an asset set that violates asset-authoring-constraints.md's limits — only for the asset
   classes that file actually covers (structured-snippet value count/length, RSA duplicate-
   headline/description, and the other per-asset-type limits recorded there); a build plan that
   does not follow api-build-mechanics.md's batched temporary-resource-name ordering for a
   multi-step chain; any "validated clean" claim made with no positive control proving the
   validator can report an error, and no count of operations sent vs. skipped
   (b) The enable-proposal gate, checked at the Verify phase, after Execute has actually built the
   campaign: every ad in scope has been read back per api-build-mechanics.md's enable-eligibility
   rule (below) and confirmed eligible for enable — policy review is asynchronous, so a clean build
   or a clean validate pass never substitutes for this read.
   REJECT: a proposal to enable a campaign/ad group/ad whose `ad_group_ad.policy_summary.
   approval_status`/`review_status` has not been read back post-build, or has been read back but
   does not clear [`api-build-mechanics.md`](api-build-mechanics.md)'s enable-eligibility table
   (the single definition of which `approval_status`/`review_status` combinations allow an enable
   proposal — never restated or re-derived here)
   (see [`api-build-mechanics.md`](api-build-mechanics.md) and
   [`asset-authoring-constraints.md`](asset-authoring-constraints.md))
```

## Pre-launch readiness checklist — 9 items, all mandatory

A single unchecked item halts the proposal.

- [ ] Conversion tracking linked (GA4/Ads or equivalent), auto-tagging on, click-ID passing
- [ ] Conversion action imported once, not double-imported from two sources
- [ ] Enhanced/first-party conversion matching configured for lead-gen campaigns — **or N/A for a
      company whose pack declares `regulated`**, per
      [`measurement-and-attribution.md`](measurement-and-attribution.md)'s "Regulated-industry hard
      exception" (state the exception in the proposal). The same N/A path applies to any offline
      conversion import or other hashed-PII upload this proposal would otherwise include.
- [ ] Consent framework implemented where legally required; recommended globally
- [ ] Landing page meets Core Web Vitals targets (LCP ≤ 2.5s mobile — "good" is 2.5 seconds or
      less, per web.dev's own wording, not a strict `<`; INP and CLS within Google's
      current thresholds — re-verify at [web.dev/vitals](https://web.dev/vitals/), official,
      retrieved 2026-09-05)
- [ ] Conversion action marked Primary (supporting actions marked Secondary)
- [ ] Attribution model set deliberately, not left on a stale legacy default
- [ ] Conversion value populated (needed for value-based bidding) or explicitly acknowledged empty
- [ ] Tag firing verified end-to-end in a preview/debug tool before launch — this is SETUP, not
      TESTING, until the 4-signal test passes (see measurement-and-attribution.md)

## The completeness covenant (full campaign plans)

For any add/launch/major-rebuild plan, address EVERY item below — content, or an explicit N/A
with a one-line reason. A plan that only touches keywords or ad copy while ignoring the rest is
not Grade-A.

**Campaign settings:** budget (as a formula), bid strategy (with target value if applicable),
network settings, language targeting, ad schedule (with rationale or "24/7, no dayparting
justified because..."), location targets with presence-vs-interest setting stated explicitly (see
"Geo targeting: the setting that silently wastes budget," below).

### Geo targeting: the setting that silently wastes budget

Every location target has an underlying "location options" setting with two values, and Google
defaults every new campaign to the broader one:

- **Presence or Interest (the default)** — "Reach people in, regularly in, or who've shown
  interest in your targeted locations." This serves ads to people who merely searched about or
  showed interest in the targeted location while being physically somewhere else entirely.
- **Presence** — "Reach people in or regularly in your targeted locations." This serves ads only
  to people who are actually in, or regularly in, the targeted area.

("Reach people in, regularly in, or who've shown interest in your targeted locations" /
"Reach people in or regularly in your targeted locations" —
[Google Ads Help: About location options for your campaign](https://support.google.com/google-ads/answer/1722038),
official, retrieved 2026-09-19. "Most campaigns will notice a decrease in impressions when
switching away from the default" — same source.)

**Doctrine: for a fixed-service-area offer** (a local contractor, or any business that only serves
customers physically located in a defined geography), **the interest half of the default buys
clicks from people merely researching the topic while physically outside the service area — pure
waste on that kind of offer. Set Presence for every campaign unless the company's own geo ruling
names a specific reason to keep Presence-or-Interest**, and state which setting is in effect
explicitly in every plan — never leave it implied by "the default." A company selling nationally or
without a fixed service area may have a real reason to keep Presence-or-Interest; that reasoning
belongs in that company's own paid-acquisition dossier as a named ruling, not assumed here either
way.

**Failure mode to watch:** duplicating an existing campaign is the common way this setting
silently reverts to Presence-or-Interest even when the original campaign was correctly set to
Presence — re-verify the location-options setting after any campaign copy/duplicate, not just at
first build.

**Exclusion asymmetry:** location EXCLUSIONS operate on Presence only, regardless of the
inclusion setting above — an exclusion never excludes on "interest," only on physical
presence/regular presence ([same source](https://support.google.com/google-ads/answer/1722038),
retrieved 2026-09-19).

**Bid adjustments — all 5 dimensions, current → proposed or "no change — [evidence]":** device,
location, ad schedule, age, gender. See [`bid-adjustment-framework.md`](bid-adjustment-framework.md)
for the decision trees and thresholds.

**Asset types — every one, content or explicit N/A + reason:** sitelinks, callouts, structured
snippets, call asset, business name, business logo, images, price asset (if applicable), promotion
asset (if applicable), lead form (if applicable).

**Structure:** keywords with match types per ad group; negatives with match types
(campaign-level and/or account-level shared list); RSAs with every headline/description filled,
final URL, and path segments if used.

**Company-profile alignment:** services in the plan match what the business actually offers (no
overreach beyond scope); messaging rules respected (approved words, words to never use, any
compliance restriction); landing pages match a documented mapping — not everything pointed at the
homepage; target areas match the documented service area; budget aligns with stated goals;
negative-keyword seeds from onboarding are included.

**Evidence and execution:** impression-share analysis cited (budget-limited vs rank-limited);
conversion tracking verified; every claim carries a numeric anchor; execution method specified for
every item (bulk editor / API / manual UI step — never a bare "operator does this"); any anomaly
or data-quality issue documented.

## Common failure modes to check against before submitting

| Failure | Fix |
|---|---|
| Plan restates an old strategy doc with no fresh evidence | Pull current numbers for this specific proposal |
| No bid-adjustment table | All 5 dimensions required; propose % changes where data shows variance |
| "No change" on all modifiers with no evidence | Not allowed when the data shows a real gap; state parity or low volume explicitly |
| No extension/asset coverage check | Cite every relevant asset type, not just sitelinks/callouts |
| Ignored ad schedule / dayparting | Must review time-of-day/day-of-week performance even if the conclusion is "no change" |
| RSA copy recycled blindly | Check asset-level performance labels before reusing; LOW-rated assets need a rewrite |
| "Operator should do this in the UI" | Acceptable only when the step names one of: (a) a genuine technical blocker (2FA, CAPTCHA) — document the exact blocker; (b) a `$` action the operator makes themselves, recorded as `owner_executed` as the primer §4 defines it (card id + a verify-read of the new absolute value); (c) a NEVER-class step under the governing plan's autonomy rules — for example a step that would require creating or joining a Meta Business Portfolio for any company, which is never created or joined by an agent and is never presumed to be a routine operator to-do either: it is surfaced as an operator card, and the plan halts there rather than listing it as a step the operator will just handle. A bare "operator does this" with none of these three named is still rejected. |
| Plan lists a setting but execution skips it | If the plan says "-15% mobile," the execution must actually apply it |
| No QA export after execution | Re-verify the live account matches the plan before declaring done |
| No post-build policy-approval readback | Enabling while any ad's `approval_status`/`review_status` is unread, or fails api-build-mechanics.md's enable-eligibility table (still under review, disapproved, an unlisted combination, or an `APPROVED_LIMITED`/`AREA_OF_INTEREST_ONLY` limitation the operator has not accepted), is not Grade-A — see §0 item 8(b) |
| Language targeting not mentioned | Must be stated explicitly, even when it's the obvious default |

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

Within that scope, when the account owner is a small contractor or similar owner-operator business, apply this
conditional vertical doctrine — read the specific persona (revenue band, buyer psychology, prior
vendor history) from that company's own dossier rather than assuming it here:

- **The completeness covenant matters even more for a small contractor than for a larger,
  marketing-sophisticated account** — a typical owner-operator has ONE campaign, ONE budget, and no
  in-house marketing staff to notice a half-configured setup. There is no second pair of eyes
  catching a missing conversion action or an un-set geo radius; the covenant IS the second pair of
  eyes.
- **The 9-item pre-launch checklist should be presented in plain language, not jargon.** "Is your
  phone-call tracking actually connected to Google yet?" lands better than "Enhanced conversions
  configured." The underlying gate is identical; the delivery isn't.
- **A buyer burned by a prior vendor will ask "did it actually go live?"** — treat the Verify phase
  as the deliverable that rebuilds trust, not an internal QA step. Show them the live campaign
  screenshot or the read-back confirmation, not just a "done" message.
- **Budget-formula transparency (Nx tCPA, shown plainly) is a trust move**, not just a rigor move,
  for a buyer who has been sold round numbers before ("just do $150/day, trust me").
