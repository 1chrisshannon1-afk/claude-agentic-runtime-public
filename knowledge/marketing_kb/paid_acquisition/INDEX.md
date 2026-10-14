# Paid Acquisition — Index

Domain corpus for the `paid-acquisition-strategist` seat in the GTM department. Grep-reachable
on demand — read the file that answers the question, not the whole corpus. Mechanism originally
ported from a prior internal ads discipline (history only; not a live source; never consulted),
re-derived for the home-services/contractor vertical, extended with Google LSA doctrine.

**Provenance.** The ported mechanism's original source is history only — never open, list, or grep
it to re-derive or extend anything here. Every ported claim is tagged
`(ported incident-derived mechanism, <date>)` or `(ported build-incident, <date>)`, both sub-labels
of `UNVERIFIED — seeded, needs derivation` defined in [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md)'s
opening note. As of 2026-09-28 no file in this folder names a real company, client, or account; health-practice
rules key off the pack's `regulated: ["hipaa"]` flag, never a company name. Company-specific evidence (named case studies, measured figures, build logs) belongs in that
company's own dossier and `marketing_kb_state/`. **Where "that company's dossier" lives:**
always `<home>/.claude/oversight/paid-acquisition-strategist.md`, where `<home>` is the path
`python3 ~/.claude/tools/gtm/company.py resolve <slug>` returns for the company being consulted
(the same call that locates its pack). If the session's current repo is not `<home>`, never read
the current repo's dossier for that consult — it belongs to a different company. **Claim ids:** this folder predates the
`[KB-<DIR>-<NNN>]` claim-id convention used by the newer folders and carries none, so its claims
have not been through `../shared/kb-verification-procedure.md`'s per-claim verifier; each claim
carries its own inline provenance tag instead.

**Governance this corpus applies but does not define:** the money rule, what counts as `$`
approval, and within-ceiling optimizations are stated in
[`../../paid_acquisition_strategist_primer.md`](../../paid_acquisition_strategist_primer.md) §4
(from the governing plan, `~/.claude/plans/gtm_autonomous_department_plan.md` §20.6/§20.8/§20.13).
In short: competitor-brand keywords and other targeting inside an operator-approved budget are
within-ceiling optimizations, agent-executable by the execution lane after the required reviews;
creating a PAUSED campaign (even with a budget field) is T1; enabling, pausing, or removing a
campaign or ad set, starting spend, or changing any budget/cap is `$` and needs the operator's
signed approval. The one targeting exception: pay-per-lead area/category changes (plan §20.6's `$`
row names Thumbtack/Angi; Local Services Ads service areas and job types follow the same rule) are
`$`, not within-ceiling.

**Scope note:** the vertical "bend" sections in this corpus (contractor-specific framing, budget
bands, negative-keyword categories) apply only to a company whose pack declares
`business_model: local_service` **and** whose actual line of business is home-services/contractor
work — `business_model` alone (`local_service | b2b_saas | ecommerce | other`, per
`shared/company-pack-authoring.md`) does not distinguish a contractor from a dental practice, since
both are `local_service`. No pack field records line of business yet, so read it from that
company's dossier; every "Contractor bend" section opens with a pointer back to this note. A
company with a different `business_model`, or a `local_service` company
outside the contractor vertical (e.g. a regulated dental practice), reads the platform-mechanics
doctrine and skips the vertical bend — and a company whose pack declares `regulated` reads that
platform-mechanics doctrine only through the Regulated-industry gates at the top of
[`meta-ads-doctrine.md`](meta-ads-doctrine.md), in
[`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md), and in
[`measurement-and-attribution.md`](measurement-and-attribution.md)'s hard exception.

| File | Answers |
|---|---|
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a paid-acquisition seat NEVER recommend, propose, or auto-apply — round-number budgets, learning-period fragmentation, negativizing demand, broad-match-with-smart-bidding-day-one, and more, each with the incident/mechanism that makes it a hard no. |
| [`grade-a-gates.md`](grade-a-gates.md) | What makes a campaign proposal "Grade A" — the mandatory §0 eight-item self-check (items 1–7 and 8(a) at Plan, 8(b) post-build before any enable proposal), the pre-launch 9-item checklist, and the completeness covenant (every setting/asset/modifier addressed or explicitly N/A). |
| [`budget-as-formula.md`](budget-as-formula.md) | How to size a daily/monthly ad budget — the `Nx tCPA` formula by campaign type, why round numbers are banned, the floor table, and the contractor-specific budget bands. |
| [`bid-strategy-ladder.md`](bid-strategy-ladder.md) | Which bid strategy (Manual CPC → Maximize Clicks → Maximize Conversions → Target CPA → Target ROAS) an account is allowed to run at its current conversion volume, and why skipping a rung burns budget. |
| [`learning-period-gates.md`](learning-period-gates.md) | The minimum age/data-volume an entity (campaign, ad group, ad, keyword, bid strategy) must clear before it may be touched, what counts as a "modification," what resets learning, and the narrow additive exceptions. |
| [`account-audit-rubric.md`](account-audit-rubric.md) | The full account-health audit procedure — structural completeness checks, the 4-signal conversion-tracking verification, the 16-point Search scoring rubric (with N/A normalization and the zero-spend "blocked, not evaluated" rule), a minimal 6-point channel-agnostic sub-rubric for Meta/PMax/LSA accounts, and the ready/caution/remediate score bands. |
| [`bid-adjustment-framework.md`](bid-adjustment-framework.md) | Decision trees and numeric thresholds for the 5 bid-adjustment dimensions (device, location, schedule, age, gender) — minimum data requirements, meaningful-variance thresholds, anti-thrashing cadence, rollback triggers. |
| [`negative-keyword-hygiene.md`](negative-keyword-hygiene.md) | How to build and safely apply negative keywords — the 15-click significance bar, the converter-protection and accepted-payer/owned-segment guards, the EXACT-match-on-brand-terms rule, and the contractor-specific negative categories. |
| [`meta-ads-doctrine.md`](meta-ads-doctrine.md) | Meta (Facebook/Instagram) doctrine for local lead-gen — consolidated Advantage+ structure, audience/retargeting rules, creative-as-the-#1-lever, conversion tracking (Pixel+CAPI+EMQ), the learning-phase 50-event rule, budget scaling, Special Ad Category/TILA compliance for financing offers. |
| [`lsa-for-contractors.md`](lsa-for-contractors.md) | Google Local Services Ads doctrine for contractors — pay-per-lead mechanics, Google Verified badge requirements (the money-back guarantee is discontinued), cost-per-lead bands by trade, the 2026–2027 phased migration into a pay-per-lead Performance Max campaign type (official Google Help, re-fetched 2026-09-28), and how LSA fits alongside standard Search. |
| [`measurement-and-attribution.md`](measurement-and-attribution.md) | How to measure paid channels honestly — the 4-signal conversion-tracking test, the 48-hour physical-verification rule, cost-per-booked-job as the north star (not CPL/CTR/impressions), attribution windows, the CRM-reconciliation discipline, and the hard regulated-industry (e.g. HIPAA) exception blocking enhanced conversions/offline import/Customer Match/hashed-PII upload until a compliance KB verification and an operator card clear it (Customer Match on Google is not available to a sensitive-interest advertiser at all, so no card unlocks it there). |
| [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md) | What you CAN and CANNOT do to target a competitor's audience on Google Ads and Meta — Custom Segments (URL- and search-term-seeded, Display/Video/Demand Gen/Gmail only, never Search), competitor-brand keyword bidding (trademarks in keywords, never ad text; a within-ceiling optimization gated by ANTI-PATTERNS #9's evidence precondition; a paused conquest build is T1, enabling or funding it is `$`), YouTube channel placements by UC id (10-placement save minimum; no content targeting on conversion-optimized video), own-visitor remarketing (audience-source prerequisite, 100-user floor), Demand Gen audience-grouping mechanics and required video-ad fields, Meta interest validity checks and the 2025–2026 detailed-targeting changes, lookalikes (seed-size figures uncited folklore), Advantage+ broad (two third-party sources disagree on hard constraints — disclosed in-file), the Meta Ad Library as the honest Meta competitor-intelligence substitute, the regulated-industry gate (advertiser-curated audiences restricted; Google Custom Segments supported with a sensitive-creative caveat; in-market/affinity supported; every Meta audience, pixel or CAPI item prohibited until the compliance lane verifies it from Meta's own text, with an operator card added only for the plan §20.5.4 upload items), a contractor bend, and Meta system-user/developer-app prerequisites (portfolio guard) — with the standing "never say impossible without the substitute" rule. |
| [`api-build-mechanics.md`](api-build-mechanics.md) | How a campaign structure is actually BUILT and verified via API — what `validate_only` can and cannot prove, batched atomic mutates with temporary resource names, the post-build policy read-back and enable-eligibility table, conversion uploads routed through the Data Manager API (not the Google Ads API), and idempotent re-runs (duplicate-name errors mean the resource already exists, not a retry target). |
| [`asset-authoring-constraints.md`](asset-authoring-constraints.md) | Hard platform constraints on ad assets — structured-snippet value counts (3-10) and character limits (25), RSA exact-duplicate-headline/description rejection, and what a `validate_only` pass does and does not prove about them (it surfaces these as real content errors only once positive-control-proven — a bare "clean" claim proves nothing on its own). |

## How this domain relates to the rest of the GTM corpus

**Strategy files answer WHAT to build; [`api-build-mechanics.md`](api-build-mechanics.md) and
[`asset-authoring-constraints.md`](asset-authoring-constraints.md) answer whether the platform will
actually accept it. A Grade-A proposal that cannot be built is not Grade A** — see
[`grade-a-gates.md`](grade-a-gates.md).

Paid acquisition is demand generation bought directly (Google Ads, LSA, Meta) — distinct from
organic/earned channels and from product-led growth or sales-led motion. Organic work routes to the
runtime GTM seats that own it: SEO to `seo-architect`; GBP, reviews, and referrals to
`marketing-director`'s local/reputation-lane routing. A paid-acquisition-strategist consult that
drifts into landing-page copy, GBP optimization, or review generation is out of lane — flag it, don't
freelance it.
