# Meta Ads Doctrine (Facebook + Instagram) for Local Lead-Gen

Ported mechanism from a prior internal Meta-ads guardrail set and its home-services vertical
playbook (ported incident-derived mechanism, 2026-06 — history only, never a live source; its
`last_reviewed` date was 2026-06). Figures in this file without an `(official)`/`(third-party)`
tag carry that ported status and are `UNVERIFIED — seeded, needs derivation`. The contractor
framing here is generic to a planned-project residential GC; read a specific company's revenue band
and buyer persona from that company's own dossier, never from this file.

### Regulated-industry gate — read before applying §1, §2, §4, §5, §7 or §9

**For a company whose pack declares a `regulated` classification** (`regulated: ["hipaa"]`), the
Meta mechanics in this file that touch audiences or conversion data do **not** apply as written.
Meta's own sensitive-health / restricted-data rules are held UNVERIFIED by the compliance lane, so
Meta interest targeting, Advantage+ broad / Advantage+ Audience, website/engagement custom
audiences, customer-list uploads, lookalikes, and any Pixel or CAPI event carrying even indirectly
health-adjacent signal (including hashed advanced matching) are **prohibited for a regulated
company until the compliance lane (trust-architect for pixel/CAPI/form; the HIPAA content reviewer
for content) verifies the specific use from Meta's own policy text** — one rule for every Meta
audience, pixel or CAPI item. An operator card is additionally required only for the governing plan
§20.5.4 upload items (Customer Match, enhanced conversions for leads, offline conversion uploads, any
patient/customer-list upload — so a customer-list custom audience or a list-seeded lookalike needs
the card as well).
Governing text: [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md)'s
"Regulated-industry gate" (Meta side) and
[`measurement-and-attribution.md`](measurement-and-attribution.md)'s "Regulated-industry hard
exception". A company whose pack declares `regulated: ["hipaa"]` (e.g. a health or dental
practice) additionally follows
[`../compliance/hipaa-marketing-for-practices.md`](../compliance/hipaa-marketing-for-practices.md)
in full. **trust-architect is reviewer of record for any pixel, CAPI, conversion-upload, or
lead-form change on a regulated company** (governing plan §20.5). Everything below marked
"(non-regulated companies only)" is scoped by this gate; the structural, creative, learning-phase
and budget-pacing guidance applies to every company.

---

## 1. Campaign structure — consolidate hard, let the AI optimize

The single biggest structural mistake on Meta is budget fragmentation. The 2025–2026 doctrine
shift is decisively toward fewer, larger, AI-driven campaigns:

- Run **1 to 2 primary campaigns per objective**, not 5 to 10 (third-party synthesis, AdStellar
  2026 campaign-structure guide, retrieved 2026-09-05 — practitioner opinion; the earlier
  "official mechanism, Meta Advantage+ Sales campaign guidance" attribution named no fetchable Meta
  page, so the Meta-official half of this claim is `UNVERIFIED — primary source not located`).
- Within a campaign, **3 to 5 ad sets**, each isolating one real variable (audience or placement),
  and **3 to 5 ads per ad set** (third-party, OptiFOX 2026 best-practices, retrieved 2026-09-05).
- Default to **Advantage+ campaigns** with full AI automation as the primary structure
  (non-regulated companies only — see the gate above); reserve manual campaigns for a Special Ad
  Category case where targeting control is legally required.
- Use **Campaign Budget Optimization (Advantage campaign budget)** at the campaign level so Meta
  reallocates spend to the best ad sets automatically — do not hand-set per-ad-set budgets.
- Separate **prospecting** and **retargeting** into distinct campaigns or clearly separated ad
  sets so each can be read and budgeted independently.
- Before scaling structure, confirm the account can realistically produce roughly **50 optimization
  events per ad set per week** at the chosen budget — if not, consolidate further rather than
  adding structure (see the learning-phase section below).

## 2. Audiences — trust broad + Advantage+ Audience over hand-picked interests

The 2025–2026 shift: lookalikes and detailed interest-stacking are diminished; broad targeting fed
by Advantage+ Audience now outperforms hand-tuned interest lists in most cases.

- **(Non-regulated companies only — see the Regulated-industry gate above.)** Start every new
  prospecting campaign with **Advantage+ Audience** and broad targeting. Feed 1–2 audience
  suggestions as a hint; let Meta expand from there.
- Treat detailed (interest/behavior) targeting as **optional supplementary signal**, not the
  primary lever. Narrow interest stacks raise cost and accelerate creative fatigue.
- If a lookalike is used at all, use a **1% lookalike** off a strong seed (real customers or
  qualified leads) — do not layer it with custom audiences.
- **Minimum retargeting audience ~1,000 matched users; aim for 5,000+** for stable delivery. Do not
  launch a retargeting ad set against an audience below ~1,000 — Meta's own delivery minimum will
  report the audience as **"Below 1,000"** and it cannot deliver until site traffic grows — seed
  traffic with cold prospecting / Google first; do not launch a starved retargeting ad set (ported
  incident-derived mechanism, 2026-06, observed on a real home-remodeling account — **UNVERIFIED —
  evidence not yet relocated** to that company's own dossier; no fetchable Meta primary source for
  a hard 1,000 floor has been found, see
  [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md), "Website custom audiences
  from your own pixel").
- **Suppress past customers and existing leads** from cold-prospecting campaigns; exclude anyone
  already in retargeting from prospecting, to prevent internal auction competition and fatigue.
- Build a CRM customer-list custom audience (hashed email + phone) for both suppression and as a
  lookalike seed. Phone must carry a country code; email must be lowercased/trimmed before hashing.
  **Never for a company whose pack declares `regulated`** — customer-list uploads, lookalikes and
  health-adjacent Pixel/CAPI events are prohibited there until the compliance lane verifies the
  specific use from Meta's own policy text, and the customer-list upload (a plan §20.5.4 item) also
  needs an operator card (the gate above; see
  [`measurement-and-attribution.md`](measurement-and-attribution.md)'s "Regulated-industry hard
  exception" and `../compliance/hipaa-marketing-for-practices.md` `[KB-COMPLIANCE-054]`).

## 3. Creative — the #1 performance lever, ahead of audience and budget

With Advantage+ handling targeting, creative is where an account actually competes.

- **Creative changes routinely swing cost-per-result 20–50%**, versus 5–10% from audience/structure
  tweaks alone (third-party, Dark Room creative-fatigue framework 2026, retrieved 2026-09-05).
  Invest there first.
- **Authentic, phone-shot, UGC-style content materially outperforms studio production** for local
  services. A contractor filming themselves on a job site talking through real work outperforms a
  polished ad at nearly every budget level.
- **Default format: Reels, 9:16 vertical, with captions** (85%+ of Meta video is watched without
  sound — an uncaptioned video loses most of its potential audience).
- **Win the first 3 seconds.** Open with a clear, specific hook; on-screen text readable without
  sound from frame 1.
- **Creative fatigue signals — act on the FIRST one, not the third:** frequency above ~3–4 on cold
  audiences, CPM-per-reach rising, or CTR down 20%+ over two weeks. Replace or supplement creative;
  don't wait for CPA to visibly collapse.
- For local services specifically, the proven creative types are **real before/after**, **customer
  video testimonials**, crew/craftsmanship footage, and a clear offer (free estimate/consult).
  **Never fabricate or AI-generate before/after imagery** — this is an FTC exposure, not a style
  choice (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #16).

## 4. Conversion tracking — Pixel + CAPI is the 2026 baseline, not an upgrade

**(Non-regulated companies only.** For a company whose pack declares `regulated`, every item in
this section and the case study below — Pixel `Lead` events, CAPI, hashed advanced matching, the
EMQ target — is prohibited until the compliance lane verifies the specific event from Meta's own
policy text, with trust-architect as reviewer of record; an event that uploads CRM/offline
conversions or customer-list PII is a plan §20.5.4 item and also needs an operator card. See the
Regulated-industry gate at the top of this file.)

- **Install both the Pixel AND the Conversions API (CAPI) on every non-regulated company's site.** Pixel alone misses a
  meaningful share of conversions to iOS/ATT, ad-blockers, and cookie limits.
- **The base pixel firing only `PageView` is the silent campaign-killer.** Confirm a real `Lead`
  event fires on actual conversion — both browser-side and server-side — before spending anything
  beyond a nominal test budget. This is the single most common real-world failure mode documented
  end-to-end on a real home-remodeling account (see the case study below).
- **Deduplicate with a shared `event_id`** across the browser pixel event and the server-side CAPI
  event for the same conversion, or the dual setup double-counts.
- **Target Event Match Quality (EMQ) of 8+ out of 10.** Send hashed email first, then phone, then
  `external_id`, then name/city/state/zip, then `fbp`/`fbc` cookies, then IP + user-agent — as many
  as available; a single identifier is weak.
- **Aggregated Event Measurement changed June 2025:** the old 8-event limit and manual
  event-prioritization were removed. Send all eligible conversion events and let Meta aggregate.
- **Verify the domain** in Business Settings (Brand Safety → Domains) — protects tracking
  configuration and is required for reliable measurement.
- Prefer wiring all of this in **GTM, never the site's CMS directly** — additive, reversible, no
  destructive edit to a paying customer's live site (see the setup pattern below).

### Case study — a real home-remodeling account, verified end-to-end

(Non-regulated companies only — the client-side hashing listener in step 3 and the CAPI relay in
step 2 are exactly the data flow the Regulated-industry gate prohibits for a regulated company.)
This exact conversion-tracking fix was built and verified on a real residential-remodeling account
(ported incident-derived mechanism, 2026-06 — **UNVERIFIED — evidence not yet relocated** to that
company's own dossier, and never restated here). The pattern is directly transferable and worth carrying whole:

**Diagnosis:** most sites have only the base pixel hardcoded (`fbq('init', ...)` +
`fbq('track', 'PageView')`) and nothing else — check the live GTM container itself (not just the
page) for any `fbq`/Meta tag; zero hits means Google gets the lead conversion and Meta gets only a
pageview.

**The fix (all in GTM + a server relay, never touching the site's CMS):**
1. A browser pixel `Lead` tag (GTM Custom HTML) fired on the same trigger the site's existing
   Google conversion uses (usually the thank-you-page view).
2. A server-side CAPI relay (a small function holding the Meta token, POSTing to
   `graph.facebook.com/v20.0/{pixel_id}/events`, origin-gated to the company's domain) — recovers
   the 10–30% the browser pixel loses to ad-blockers and iOS.
3. Email/phone advanced matching captured via a GTM "All Pages" listener that hashes form inputs
   client-side into short-TTL cookies, read and forwarded by the relay tag — no per-form or CMS
   edit required.
4. A single shared `event_id` per pageview, used by both the browser pixel and the server beacon,
   for dedup.

**Verify before trusting:** load the thank-you page and confirm `facebook.com/tr/?...&ev=Lead`
returns 200, the relay returns `events_received: 1`, and EMQ climbs in Events Manager over the
first few days. (Ported incident-derived mechanism, 2026-06 — the "10–30%" recovery figure is
`UNVERIFIED — seeded, needs derivation`. The Graph API version in step 2 is the version used then;
use the current Marketing API version.)

## 5. The learning phase — the biggest way local budgets get wasted

- A new ad set enters the learning phase and typically exits once it accumulates **roughly 50
  optimization events within 7 days** (third-party, Pigeon Digital "50-conversion rule" 2026,
  retrieved 2026-09-05). Below that, it still runs, but with much higher variance.
- **Do not edit targeting, budget, creative, or bid strategy during the learning phase.** Each
  significant edit resets learning, and a reset ad set re-enters the same elevated-CPA learning
  window described above — commonly cited at roughly **20–50% higher CPA** than post-learning
  performance (third-party, cross-referenced across Cometly's "Facebook Ads Learning Phase
  Optimization Tips" and Modern Marketing Institute's Meta learning-phase guidance, both 2026,
  retrieved 2026-09-05). No third-party source found ties a specific percentage or a 48–72-hour
  duration to the reset itself as distinct from the general learning-phase premium — treat the
  window as "however long it takes to reaccumulate the ~50-event threshold above," not a fixed
  clock.
- **Wait 3–7 days before judging** a new ad set; early variance is expected, not a signal to act.
- **Consolidate to learn faster** — fewer ad sets each clearing 50/week beats many ad sets none of
  which do. This is the practical reason behind the consolidation rule in section 1.
- If an ad set genuinely cannot hit ~50 events/week at the available budget, optimize for an
  earlier, higher-volume event (e.g. form-submit instead of booked-appointment) so the algorithm
  gets signal at all, while still feeding the deeper event via CAPI for quality (non-regulated
  companies only; for a regulated company no CAPI event is sent until the Regulated-industry gate
  above is cleared).

## 6. Budget and scaling — the 20% rule, and the real minimum-budget math

- **Vertical scaling on Meta: raise budget by no more than ~20% every 3 to 4 days.** Larger jumps
  force the auction to re-explore and reset learning. This is the Meta pacing rule; Google's
  slower cadence (≤20% per week, ≥7 days between increases) is in
  [`budget-as-formula.md`](budget-as-formula.md) — never apply one platform's cadence to the
  other. **A ramp is a schedule of separate `$` proposals; each increase needs its own signed
  approval (primer §4)** — a pacing rule never pre-approves a future increase.
- **Only scale when fundamentals are healthy:** CPA comfortably below target, frequency below ~2 on
  prospecting, the ad set spends its full daily budget, delivery is stable.
- **Horizontal scaling** (new audiences, new creative, new placements) is the growth lever once
  vertical headroom is gone — carries its own fresh-creative requirement to avoid fatigue at higher
  spend.
- **The real minimum-budget math, done honestly:** a target CPL of $60 requires roughly
  $3,000/week (~$429/day) PER AD SET to realistically clear the 50-events/week learning-exit
  threshold (third-party arithmetic, derived from the 50-event rule and observed CPL ranges,
  retrieved 2026-09-05). At early-stage contractor budgets — often $1,000–$3,000/MONTH total, not
  per week per ad set — most accounts will run in "Learning Limited" indefinitely, and that is an
  expected, not a failure, state. Consolidate to 1 ad set, optimize for the highest-volume honest
  signal available, and judge trends over 4–8 weeks, never week to week.

## 7. Lead generation — optimize for qualified leads, not raw form fills

- **Instant (Lead) Forms usually win for local lead-gen** — pre-filled fields, lower friction,
  materially lower cost-per-lead than sending cold traffic to a landing page. **(Non-regulated
  companies only:** a Lead form on a regulated company collects health-adjacent PII inside Meta and
  is prohibited until the compliance lane verifies the specific use from Meta's own policy text,
  with trust-architect as reviewer of record for any form change — see the Regulated-industry gate
  above.)
- **Add a qualifier question** to filter tire-kickers: service type, timeline, or budget band. This
  is the single biggest quality lever on cold Meta traffic for a contractor.
- **Speed-to-lead is decisive:** leads contacted within ~5 minutes convert **over 8x** higher than
  leads contacted between 5 minutes and 24 hours later (third-party, InsideSales "Lead Response
  Study" 2021 — 55M+ sales activities across 5.7M inbound leads at 400+ companies; still the
  standard-cited benchmark for this figure, retrieved 2026-09-05). Do not run Meta lead-gen unless a
  sub-5-minute auto-response is wired — this is a hard prerequisite, not a nice-to-have.
- **Measure cost-per-QUALIFIED-lead and cost-per-booked-job, not raw CPL.** CPL on cold Meta
  traffic is a vanity number; the real signal comes from CRM outcomes (see
  [`measurement-and-attribution.md`](measurement-and-attribution.md)).

## 8. Compliance — Special Ad Categories and TILA

- **Home services is not, on its face, one of Meta's Special Ad Categories** — Meta's Marketing
  API lists the categories as `HOUSING`, `EMPLOYMENT`, `FINANCIAL_PRODUCTS_SERVICES`, and
  `ISSUES_ELECTIONS_POLITICS` (official, Meta for Developers "Special Ad Categories",
  `developers.facebook.com/docs/marketing-api/audiences/special-ad-category/`, retrieved
  2026-09-27). That page does **not** define the `HOUSING` category's scope, and Meta's Business
  Help "How to Choose a Special Ad Category" page (`facebook.com/business/help/298000447747885`)
  returned no readable body text on 2026-09-27 — so whether a given home-improvement or
  home-repair ad falls under `HOUSING` is `UNVERIFIED — primary source unreachable`. Confirm the
  category in Ads Manager at campaign creation rather than assuming full targeting.
- **Consumer financing offers can pull an ad toward the Financial Products/Credit category.** The
  only restriction confirmed from Meta's own page is the 18+ minimum age; the further restrictions
  commonly listed (detailed targeting stripped, lookalikes disallowed, wide geo radius, no
  age/gender filtering) are `UNVERIFIED — seeded, needs derivation` — see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #15, and re-verify in Ads Manager at campaign creation. Keep financing **soft-secondary** in ad copy — lead with the
  remodel, not the payment plan — so the ad classifies on the actual service, not the loan.
- **TILA / Reg Z (1026.24):** any ad or landing page stating a specific monthly payment, APR, down
  payment, or term triggers a required financing disclosure. Reuse the business's approved
  disclosure language; never invent financing terms.
- **No "easy/guaranteed approval" language**, and never target by inferred credit or financial
  status.
- **No invented statistics** in ad copy ("X% of our customers finance...") unless documented and
  sourced.
- **Ad copy also follows the company pack's `claims_policy` and that company's dossier.**

## 9. Home-services vertical starting points (ported)

**Scope:** contractor-vertical companies only, per [`INDEX.md`](INDEX.md)'s scope note — a company
outside the home-services/contractor vertical skips this section.

Ported from the prior discipline's home-services vertical playbook (ported incident-derived
mechanism, 2026-06; every figure below is `UNVERIFIED — seeded, needs derivation`):

- **Geo:** 10–15 mile radius from the business; widen for emergency/immediate-need services,
  narrow for planned high-ticket work.
- **Audience (non-regulated companies only — see the gate above):** homeowners broadly, with
  Advantage+ Audience; for high-ticket remodeling work, lean
  on the home-improvement interest signal as a HINT, not a hard filter.
- **Creative:** real before/after, customer video testimonials, crew/craftsmanship, warranties and
  guarantees. A Reels tour of a finished job plus a quick testimonial plus a clear CTA performs
  well.
- **Lead-form qualifier:** service type and scope/budget band, to filter unqualified leads early.
- **Budget:** ~$10–$15/day per ad set minimum to have any real chance of exiting learning; premium
  high-ticket work can support more.
- **Follow-up:** most inquiries need a callback within 24 hours; wire the sub-5-minute
  auto-response. Measure cost-per-booked-job, not CPL.
- **Ramp expectation:** stable lead flow in ~30–60 days, first appointments in ~7–14 days. Do not
  judge week-2 CPL; judge cost-per-booked-job over 6–8 weeks.

(Ported 2026-06 — already more than ~90 days old as of 2026-09-27; re-verify against current Meta
guidance before relying on any figure, per this corpus's citation-style staleness rule.)

## 10. Home-services CPL benchmark bands (third-party, re-derived for the remodeling sub-vertical)

**Scope:** contractor-vertical companies only, per [`INDEX.md`](INDEX.md)'s scope note — a company
outside the home-services/contractor vertical skips this section.

The ported vertical playbook carries no dollar benchmarks (it was mechanism-only). The following are
freshly retrieved for a remodeling-specific budget
sanity check:

- **Blended home-services Meta CPL (2026):** roughly $30–$34, trending upward year over year
  (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as "industry benchmark
  aggregation" with no publisher, title, or URL, so the source cannot be re-opened).
- **Trade-specific spread:** plumbing, painting, and landscaping typically run $45–$80/lead; roofing
  and full remodels push to $80–$120/lead; high-ticket HVAC/roofing can exceed $115/lead
  (`UNVERIFIED — seeded, needs derivation`: same unnamed "industry benchmark aggregation",
  2026-09-05).
- **Creative-format lift:** video ads produce meaningfully lower CPL than static images for
  contractors (cited range 30–60% lower); owner-on-camera video and carousel formats also show
  material CPL reduction versus generic static creative (`UNVERIFIED — seeded, needs derivation`:
  recorded 2026-09-05 as "third-party" with no named source — treat as directional; validate
  against the account's own creative tests before trusting the specific percentages).

**How to use these:** the same discipline as every other benchmark in this corpus — a sanity check
for a brand-new account, never a substitute for the account's own measured CPL once it exists.
Judge against the account's own baseline first, then the segment goal, then this benchmark band.

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A small GC's Meta budget will almost always sit below the honest minimum-budget math in
  section 6.** Say this plainly rather than pretending the account will exit "Learning Limited" on
  schedule — set expectations for a longer, noisier ramp and judge trends over 6–8 weeks, exactly
  as the home-services vertical guidance already states.
- **The conversion-tracking pattern (section 4) is the single highest-value thing to
  check on almost any new contractor Meta account** — a contractor's marketing site was very likely
  built by a web developer who installed the base Pixel and stopped there, with zero awareness that
  `Lead` never fires. Diagnosing this in the first session, before recommending any creative or
  audience change, is usually the actual unlock.
- **Financing-copy discipline (section 8) is not optional for a remodeler.** Home-improvement
  financing offers ("$99/month bathroom remodel") are reported as one of the most common
  contractor-marketing compliance failures (`UNVERIFIED — seeded, needs derivation`: no frequency
  source located, same tag as ANTI-PATTERNS) and directly risk the lender relationship a GC depends on for larger jobs —
  treat this as a hard gate on any ad copy review, not a nice-to-have compliance note.
- **A GC will ask "why not just run it on Facebook too, it's cheaper than Google."** Frame Meta
  honestly as a DIFFERENT kind of demand: Google Search captures people already looking for a
  contractor RIGHT NOW; Meta interrupts people who weren't actively searching, with a creative and
  offer good enough to make them raise their hand. Both matter, but they answer different questions
  and should never be judged against each other on raw CPL alone.
