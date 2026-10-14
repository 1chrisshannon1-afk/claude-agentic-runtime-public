# Paid Acquisition — Audience Targeting Reference (Google Ads + Meta)

Portable platform mechanics for audience targeting that
[`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md) does not already cover:
Custom Segment seed options and limits, Observation vs. Targeting on Search, placement buys,
own-data list mechanics, consent effects on list growth, Meta interest-lookup endpoints, Meta's
own-data audience sources, Special Ad Category classification risk, sequenced retargeting, and a
cross-platform decision table. Read [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md)
first for anything about competitors; this file adds the surrounding mechanics.

**Provenance (2026-09-28).** The platform mechanics here were moved from a retired runtime file
(`~/.claude/knowledge/gtm_targeting_doctrine.md`, authored and adversarially re-verified
2026-09-19, deleted 2026-09-28 because its scope line and "we/us" statements belonged to one
company). Its company-specific content now lives in that company's own paid-acquisition dossier;
nothing company-specific is kept here. Citations keep their original retrieval dates. Where this
file and `competitor-targeting-doctrine.md` touch the same fact, `competitor-targeting-doctrine.md`
wins: several facts in the retired file were corrected there on 2026-09-27 (the Meta
detailed-targeting exclusion date, the lookalike seed-size figures, the Advantage+ hard-constraint
list, the YouTube placement-minimum and "Drive conversions" sources), and those corrected versions
are not repeated here.

**No app-specific facts here.** Account ids, budgets, seed lists, personas and measured figures
live in the company's dossier at `<home>/.claude/oversight/paid-acquisition-strategist.md`
(`<home>` from `python3 ~/.claude/tools/gtm/company.py resolve <slug>`; never the session's
current repo when that is a different company).

**Regulated companies.** A company whose pack declares `regulated: ["hipaa"]` reads every
mechanism below through the Regulated-industry gate in
[`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md) and the hard exception in
[`measurement-and-attribution.md`](measurement-and-attribution.md). Customer Match, own-data
segments, audience expansion/Optimized Targeting and lookalike segments are not available on Google
for that category; every Meta audience, pixel or CAPI item waits for compliance-lane verification.

**Money.** Nothing here changes the money rule. Audience and targeting choices inside an
operator-approved budget are within-ceiling optimizations; enabling a campaign, starting spend or
changing any budget/cap is `$` ([`../../paid_acquisition_strategist_primer.md`](../../paid_acquisition_strategist_primer.md) §4).

## 1. Routing a targeting question

- **Targeting questions are RESEARCHABLE, not operator cards** (`~/.claude/knowledge/marketing_director_primer.md`
  §2, CLARIFY routing). Genuine operator items in this area are narrow: spend authorization,
  account/identity decisions, and legal questions about trademark use in comparative claims.
- **Never answer a targeting question from memory.** Both platforms changed materially in
  2025–2026 (Google's similar audiences are gone; Meta removed a large set of detailed-targeting
  interests with a silent non-delivery failure mode). Read this file and
  `competitor-targeting-doctrine.md`; if the answer is not in either, fetch the platform's own
  current documentation and cite it with a retrieval date.
- **Every platform-capability claim carries a URL and an as-of date.** Anything unsourced is marked
  as a judgment call.

## 2. Google Custom Segments — seed options and limits

Custom Segment mechanics, member types, the `SEARCH` vs. `AUTO` type distinction, Observation vs.
Targeting attachment, and PMax audience-signal use are in `competitor-targeting-doctrine.md`
("Custom Segments"). This section adds the UI seed names and the published limits.

**The four seed options, by their UI names** (official,
[About custom segments](https://support.google.com/google-ads/answer/9805516?hl=en), retrieved
2026-09-19, not re-fetched):

| UI option | What you enter | What Google does |
|---|---|---|
| "People with any of these interests or purchase intentions" (default) | Keywords/phrases | Broad interest and purchase-intent modeling |
| "People who searched for any of these terms on Google" | Search terms | Reaches people who performed those searches on Google properties, including Search and YouTube |
| "People who browse websites similar to" | URLs | Reaches people who browse sites similar to those URLs |
| "People who use apps similar to" | App names | Reaches people using similar apps |

Google states for both the URL and the app options that the seed is modeling, not placement:
"This doesn't mean your ads will show on those URLs," and "This doesn't mean that your ads will
show on those apps" (same page, retrieved 2026-09-19, not re-fetched). Showing an ad on a specific
site, app or channel is placement targeting (§4), a separate mechanism.

**URL granularity.** Google does not publish whether a deep path (for example a `/pricing` page)
is honored more narrowly than the bare domain. Practitioner consensus is that modeling works at
roughly the domain level (third-party,
[jyll.ca, Inside Google Ads ep. 63](https://jyll.ca/insidegoogleads/63), and
[Google Ads Community thread 330385179](https://support.google.com/google-ads/thread/330385179/what-exactly-to-enter-as-url-in-people-who-browse-websites-similar-to?hl=en),
both retrieved 2026-09-19, not re-fetched). **Seed the bare domain. Any claim that deep-path
seeding targets visitors of that specific page is UNVERIFIED and never goes in a spec as fact.**

**Published limits** (official, About custom segments, retrieved 2026-09-19, not re-fetched):
custom segments are not shareable across accounts; manager (MCC) accounts cannot use them; they are
reviewed against Google's advertising policies; and the Audience-insights panel settings do not
persist after the segment builder closes. Google publishes no maximum member count or per-URL
character limit — **treat any specific number as UNVERIFIED.**

**API notes** (official,
[Custom Audiences](https://developers.google.com/google-ads/api/docs/remarketing/audience-segments/custom-audiences)
and [Targeting settings](https://developers.google.com/google-ads/api/docs/targeting/targeting-settings),
both retrieved 2026-09-19, not re-fetched):
- Report on attached segments with `ad_group_audience_view` / `campaign_audience_view`.
- On update, the entire `TargetingSetting` object must be rebuilt and passed back — a partial
  update silently drops the restrictions it omits.

**PMax signal timing.** A custom segment used as a Performance Max audience signal is applied at
the asset-group level, and Google's models need up to about two weeks to absorb a new signal —
do not judge a signal before then (official,
[About audience signals for Performance Max](https://support.google.com/google-ads/answer/14530785?hl=en),
retrieved 2026-09-19, not re-fetched).

## 3. Observation first on Search

On Search and Shopping the default audience setting is **Observation**, which does not restrict
reach and only enables bid adjustments and reporting (official,
[About "Targeting" and "Observation" settings](https://support.google.com/google-ads/answer/7365594?hl=en),
retrieved 2026-09-19, not re-fetched). Search supports affinity, detailed demographics, in-market
and your-data segments, but not custom segments (official,
[About audience segments](https://support.google.com/google-ads/answer/2497941?hl=en), retrieved
2026-09-19, not re-fetched).

**Rule: never switch a Search audience to Targeting until Observation data shows it converts
better.** Search already carries keyword intent; a hard audience restriction on top cuts volume
without a proven efficiency gain.

**Off-the-shelf segments.** In-market segments (people actively researching or comparing a
category) sit nearer the conversion than affinity segments (long-term interests; better for
Display/YouTube reach than for Search efficiency) (official, About audience segments, and
[About affinity segments](https://support.google.com/google-ads/answer/13151406?hl=en), both
retrieved 2026-09-19, not re-fetched). Detailed demographics include employment/industry-adjacent
attributes; check availability per campaign type at build time. A segment's label is not evidence
it matches the company's buyer — run off-the-shelf segments in Observation and let data promote
them. Which categories fit a given buyer is a company fact, read from that company's dossier.

## 4. Placement targeting on YouTube and Display

Placement targeting puts an ad on specific channels, videos, sites or apps. UI: campaign →
Content → Placements → Enter, then paste channel/video URLs (third-party,
[Search Engine Land placements guide](https://searchengineland.com/google-ads-placements-guide-websites-apps-youtube-462050),
retrieved 2026-09-19, not re-fetched). The API mechanics (channel id `UC…`, never a handle), the
10-channel save minimum, the squatter-channel check, and the rule that conversion-optimized video
carries no content targeting are in `competitor-targeting-doctrine.md` ("YouTube channel
placements").

- Placements can include a competitor's channel or independent channels on the buyer's subject.
  Independent education/how-to channels in the buyer's field often carry more volume than a
  competitor's own channel; judge by the channel's real audience, not its name.
- Expect **high CPMs** from a small inventory pool.
- A placement buy optimizes for views, not conversions (conversion-optimized video offers no
  placement targeting). A spec that pairs "conversion video" with "run on these channels" is
  internally contradictory.

## 5. Own-data lists on Google

The remarketing floor (100 active users in 30 days; the pre-2024-02-01 customer-list exception)
and the Audience-source prerequisite are in `competitor-targeting-doctrine.md` ("Own-visitor
remarketing").

- **Membership duration:** default 30 days, maximum 540 days; a return visit refreshes the user's
  timestamp; changing the duration applies retroactively to existing members (official,
  [How your data segments work](https://support.google.com/google-ads/answer/2472738?hl=en),
  retrieved 2026-09-19, not re-fetched).
- **The floor is a rolling window**, so a list that accrues too slowly never fills. Traffic must
  reach about 100 active users per 30 days before remarketing works at all; the tag is a
  prerequisite for the traffic campaign, not a later add-on.
- **Build the lists before the first dollar of spend** — a list only accrues members once the tag
  and Audience source are live. A typical starting set: all visitors; pricing-page visitors;
  signup/lead-form started but not completed; content readers; converted users (for exclusion).
- **An old customer list that under-delivers** may still be on the legacy 1,000-matched-user
  requirement (uploaded before 2024-02-01): re-upload it rather than debug it.
- **Customer Match** (hashed emails/phones for targeting, exclusion and seeding): users added or
  updated more than 540 days ago are removed automatically, enforced from 2025-04-07 — re-upload
  on a cadence or lists decay silently (third-party,
  [Overt Digital Marketing](https://overtdigitalmarketing.com.au/google-tightens-customer-match-data-rules-in-major-privacy-update/),
  retrieved 2026-09-19, not re-fetched). Using Customer Match in Targeting mode has historically
  required account standing (policy and payment history; reported thresholds such as 90+ days in
  Google Ads and significant lifetime spend); lower-standing accounts can still use Observation.
  **The specific thresholds are UNVERIFIED** — check eligibility in-product before a spec depends
  on it. A company with no meaningful customer list treats Customer Match as a later-phase
  instrument. Regulated companies: not available on Google at all (see the gate).
- **Similar audiences** are retired on Google (see `competitor-targeting-doctrine.md`); the
  replacements are Optimized Targeting (Display/Demand Gen) and audience expansion (Video).

## 6. Consent mode and list growth

Consent Mode v2's four signals and its modeling behavior are in
[`../measurement/consent-mode.md`](../measurement/consent-mode.md). One effect matters directly for
audiences: a user can grant `ad_storage` while denying `ad_personalization` — the conversion is
still measured, but **that user is not added to a remarketing list** (official,
[Updates to consent mode for EEA traffic](https://support.google.com/google-ads/answer/13695607?hl=en),
retrieved 2026-09-19, not re-fetched). Lists grow more slowly wherever personalization consent is
often denied, and Consent Mode v2 via a Google-certified CMP is mandatory for EEA traffic (same
page). How much this matters depends on the company's geography, which its dossier records.

A CMP vendor reports that from 2026-06-15 Google Signals no longer governs advertising data in GA4
properties linked to Google Ads, with `ad_storage` governing the GA4→Ads flow instead (third-party,
[UniConsent](https://www.uniconsent.com/blog/google-ads-consent-mode-change-2026), retrieved
2026-09-19, not re-fetched). **UNVERIFIED** — the only source is a vendor; confirm against Google's
own documentation before relying on it.

## 7. Meta — finding and checking interests

The deprecation timeline, the silent non-delivery failure mode, and the `adinterestvalid` /
`adinterestsuggestion` checks are in `competitor-targeting-doctrine.md` ("Interest targeting").
This section adds the full endpoint table and the pre-launch procedure.

All endpoints are `GET https://graph.facebook.com/v<API_VERSION>/search` (official,
[Targeting Search](https://developers.facebook.com/docs/marketing-api/audiences/reference/targeting-search),
retrieved 2026-09-19, not re-fetched):

| Purpose | Params | Returns |
|---|---|---|
| Search interests | `type=adinterest&q=<term>` | `id`, `name`, `path`, `locale` |
| Validate interests (the dead-interest check) | `type=adinterestvalid` + `interest_list=[...]` or `interest_fbid_list=[...]` | `name`, `valid`, `id`, `audience_size` |
| Suggest related interests | `type=adinterestsuggestion&interest_list=[...]` | `id`, `name`, `audience_size`, `path`, `description` |
| Browse categories | `type=adTargetingCategory&class=interests\|behaviors\|demographics\|life_events\|industries\|income\|family_statuses\|user_device\|user_os` | `id`, `name`, `audience_size_lower_bound`, `audience_size_upper_bound`, `path`, `description`, `type` |
| Employer / job title / school / major | `type=adworkemployer` \| `adworkposition` \| `adeducationschool` \| `adeducationmajor`, with `q=<term>` | `id`, `name`, `coverage`, `subtext` |

**Pre-launch check, every Meta spec that names an interest:**
1. In Ads Manager → Ad set → Audience → Detailed targeting, type each intended interest into the
   search box. If it does not appear, it does not exist — never paste an id from an old plan, a
   blog post or a prior mission artifact.
2. Validate programmatically with `type=adinterestvalid`. This is the mechanically checkable
   success criterion for any spec that names an interest.
3. Any ad set showing zero delivery is checked for a dead interest **first**, before budget, bid or
   creative is touched.

Affected ad sets were flagged in Ads Manager with an orange triangle notice icon from 2025-12-15
(third-party, [Web Blend](https://webblend.au/blog/meta-ads-targeting-changes/), retrieved
2026-09-19, not re-fetched). Meta's own notice page for the change is JS-rendered and has never
returned readable text to this corpus's fetch tooling; confirm the current state visually in Ads
Manager before a first Meta launch.

**Detailed targeting is a hint, not a fence.** Meta treats the options you add as audience
suggestions and shows ads to other people when it predicts better performance (third-party,
Conversios and Linear Design, cited in `competitor-targeting-doctrine.md`'s Advantage+ section).
Never write a spec that depends on detailed targeting as a hard filter.

**Job title, employer and industry targeting** (`adworkposition`, `adworkemployer`, the
`industries` class) depends on self-reported profile fields. These are sparse and stale for
owner-operators and trades, who rarely keep an accurate employer/title field. Treat it as a weak
signal for such buyers, never the primary lever.

## 8. Meta — own-data audiences and exclusions

**Custom Audience sources** (official,
[About custom audiences](https://www.facebook.com/business/help/744354708981227), retrieved
2026-09-19, not re-fetched): website visitors via the Pixel; server events via the Conversions API;
customer lists (hashed email and phone with country code, lowercased and trimmed); app activity;
catalog engagement; and engagement audiences — video viewers, lead-form openers, ad interactors,
and the company's own Page/Instagram followers and engagers.

**Only assets you own.** An engagement audience cannot be built from a competitor's Page,
Instagram account or videos (third-party,
[LSEO](https://lseo.com/paid-media/paid-social-media-marketing/leverage-custom-audiences-for-powerful-meta-ads-results/),
retrieved 2026-09-19, not re-fetched). Vendors selling competitor-fan audiences operate against
Meta's terms — never recommend, procure, or evaluate them as an option.

**Exclusions.** With detailed-targeting exclusions removed (date and source in
`competitor-targeting-doctrine.md`), exclusion runs through Custom Audience exclusion. Exclude
existing customers, current trial/beta users and recent converters from acquisition campaigns,
unless the campaign's explicit job is retention or win-back.

**Lookalikes** need a quality seed from the company's own converters; seed-size figures are
uncited folklore (see `competitor-targeting-doctrine.md`). A company without a meaningful converter
list treats lookalikes as a later-phase instrument and starts with broad + Advantage+.

## 9. Meta — Special Ad Category classification risk

Category definitions and the TILA/financing rules are in
[`meta-ads-doctrine.md`](meta-ads-doctrine.md) §8. Two further practitioner-reported mechanics,
held as third-party reports (not re-fetched since 2026-09-19):

- **Special Ad Categories strip targeting.** Reported restrictions: no ZIP targeting, no age/gender
  filtering, no lookalikes; Custom Audiences from CRM and pixel generally remain (third-party,
  [Jon Loomer](https://www.jonloomer.com/special-ad-categories-meta-ads/), retrieved 2026-09-19).
  `meta-ads-doctrine.md` §8 holds these restrictions as UNVERIFIED against Meta's own pages;
  re-check in Ads Manager at campaign creation.
- **Automatic multimodal classification.** Several independent practitioner sources describe Meta
  scanning each ad before its first impression — text, image, video, audio and the **landing page**
  together — and applying category restrictions even when the advertiser selected no category.
  Classifiers reportedly look for real-estate imagery (floor plans, building exteriors, "For Sale"
  signs), employment imagery (office/hiring framing) and credit visuals (card mockups, loan
  calculators). Working around a classification is reportedly logged as an "Evasion" violation
  that damages account health (third-party,
  [1ClickReport](https://www.1clickreport.com/blog/meta-ad-policy-changes-2026-compliance-guide),
  [Denote](https://denote.net/blog/meta-ads-policy-update-2026),
  [AuditSocials](https://www.auditsocials.com/blog/meta-sensitive-category-ad-targeting-audience-compliance-2026-personal-attributes),
  all retrieved 2026-09-19).

**What to do:** never select a Special Ad Category voluntarily when the offer is not in one; audit
creative **and the landing page** for housing-, hiring- or credit-adjacent imagery and wording
before launch (a financing or careers section on the destination page counts); if restrictions
appear unexpectedly, treat it as a creative classification problem and change the creative openly,
never iterate to dodge the classifier. For a home-services or home-adjacent company, exterior house
photography is a genuine, non-obvious trigger — prefer product screenshots and people-at-work
imagery where the company's own asset rules allow.

## 10. Sequenced retargeting of your own visitors

Sequence by depth of intent, not by time alone:

1. **Saw the homepage, bounced** → what the offer is, one line, one proof point.
2. **Read a feature/content page** → the specific problem the offer solves.
3. **Hit pricing, did not convert** → objection handling: price framing, risk-reversal framing,
   the actual current offer.
4. **Started signup/lead form, did not finish** → highest value, smallest audience, most direct
   creative.
5. **Converted** → exclude from all acquisition; separate activation/retention messaging only.

**Frequency.** Retargeting pools are small, so frequency climbs fast. Cap frequency where the
platform allows; set membership windows short (7/14/30 days) rather than the 540-day maximum so the
pool refreshes; refresh creative on a fixed cadence, because a small pool fatigues faster than a
prospecting pool.

**Exclusions are part of every spec.** Every acquisition campaign excludes converters; every
retargeting tier excludes the deeper tiers, so each person sits in exactly one message stream.

Regulated companies: own-visitor remarketing is not available on Google, and every Meta own-data
audience waits for compliance-lane verification (see the gate).

## 11. Decision table — "you want to reach X → use Y"

| You want to reach… | On Google | On Meta |
|---|---|---|
| People actively searching for the category | Search on generic and category keywords, exact/phrase, its own campaign | No search intent on Meta — broad + Advantage+ and strong creative |
| People comparing the company to a named competitor | Search on competitor-brand keywords (keywords only, never ad text); off Search, a `SEARCH`-type Custom Segment on competitor brand terms (see `competitor-targeting-doctrine.md`) | A surviving brand interest verified live, as a suggestion; comparison-led creative informed by an Ad Library teardown, never naming the rival in ad text |
| People who searched for a competitor, reached on Display/YouTube/Demand Gen | Custom Segment, "People who searched for any of these terms on Google" | No equivalent |
| People who behave like a competitor's audience | URL-seeded Custom Segment on Display/Demand Gen/Video; as a PMax signal | No seeded equivalent — broad + Advantage+ |
| People consuming content in the buyer's field | Placement targeting on relevant channels (§4); affinity/in-market in Observation (§3) | Broad + Advantage+; creative in the buyer's own language |
| The company's own past visitors | Your-data remarketing (§5) | Website Custom Audience via Pixel + CAPI (§8) |
| The company's own engagers | Video viewers via YouTube-linked lists | Engagement Custom Audiences (§8) |
| People like the company's best customers | Customer Match + Optimized Targeting (§5) | Lookalike off a quality converter seed (§8) — a later-phase instrument without a real seed |
| Everyone in the served geography, letting the platform sort | PMax with audience signals; Demand Gen | Advantage+ with broad targeting |
| Nobody who is already a customer | Customer Match list as exclusion | Custom Audience exclusion (§8) |

Regulated companies read every row through the gate: the own-data and lookalike rows are not
available on Google, and every Meta row waits for compliance-lane verification.

**Impossible requests and their substitutes** (target a competitor's actual visitors, Page fans,
app users or customer list; buy a competitor-audience list; exclude an interest on Meta; restrict
Meta delivery to one interest): see `competitor-targeting-doctrine.md`'s CANNOT sections and its
standing rule — never answer "impossible" without naming the substitute. Obtaining a competitor's
email or customer list is never an option: it is a data-provenance and legal problem, not a
targeting choice. Build the company's own list instead.

## 12. Re-verification log

| Area | Last verified | Re-verify when |
|---|---|---|
| Custom Segment seed options, published limits, PMax signal timing | 2026-09-19 | Quarterly, or on any PMax/Demand Gen announcement |
| Search Observation default; audience types supported on Search | 2026-09-19 | Quarterly |
| Remarketing membership duration (30-day default, 540-day max) | 2026-09-19 | Quarterly |
| Customer Match 540-day expiry; Targeting-mode eligibility thresholds (UNVERIFIED) | 2026-09-19 | Before any spec depends on Customer Match |
| Consent `ad_personalization` effect on list growth; GA4 Signals change (UNVERIFIED) | 2026-09-19 | Before any EEA launch; the Signals claim before relying on it |
| Meta Targeting Search endpoint table | 2026-09-19 | On each Marketing API version bump |
| Meta interest existence, per named interest | Never — check live every time | Every build |
| Special Ad Category restrictions and multimodal classification | 2026-09-19 (third-party only) | Before the first Meta launch; quarterly thereafter |

## Sources

Dated per entry. "Retrieved 2026-09-19, not re-fetched" means the citation carries forward from
the 2026-09-19 adversarial pass of the retired file, unchecked since. Vendor and practitioner blogs
are practitioner opinion, never platform documentation.

- support.google.com/google-ads/answer/9805516 (official, retrieved 2026-09-19, not re-fetched) —
  backs: the four seed options, the "doesn't mean your ads will show on those URLs/apps" semantic,
  and the published limits
- jyll.ca/insidegoogleads/63 and the Google Ads Community thread 330385179 (third-party, retrieved
  2026-09-19, not re-fetched) — back: domain-level URL modeling (practitioner consensus)
- developers.google.com/google-ads/api/docs/remarketing/audience-segments/custom-audiences and
  developers.google.com/google-ads/api/docs/targeting/targeting-settings (official, retrieved
  2026-09-19, not re-fetched) — back: audience-view reporting; full `TargetingSetting` rebuild on
  update
- support.google.com/google-ads/answer/14530785 (official, retrieved 2026-09-19, not re-fetched) —
  backs: PMax audience signals at asset-group level, up to ~2 weeks to absorb
- support.google.com/google-ads/answer/7365594 (official, retrieved 2026-09-19, not re-fetched) —
  backs: Observation as the Search/Shopping default
- support.google.com/google-ads/answer/2497941 and /13151406 (official, retrieved 2026-09-19, not
  re-fetched) — back: audience types supported on Search; in-market vs. affinity
- searchengineland.com/google-ads-placements-guide-websites-apps-youtube-462050 (third-party,
  retrieved 2026-09-19, not re-fetched) — backs: the placement UI path
- support.google.com/google-ads/answer/2472738 (official, retrieved 2026-09-19, not re-fetched) —
  backs: membership duration default/maximum and retroactive duration changes
- overtdigitalmarketing.com.au/google-tightens-customer-match-data-rules-in-major-privacy-update
  (third-party, retrieved 2026-09-19, not re-fetched) — backs: Customer Match 540-day expiry
- support.google.com/google-ads/answer/13695607 (official, retrieved 2026-09-19, not re-fetched) —
  backs: `ad_personalization` denial keeps users off remarketing lists; EEA CMP requirement
- uniconsent.com/blog/google-ads-consent-mode-change-2026 (third-party vendor, retrieved 2026-09-19,
  not re-fetched) — backs: the 2026-06-15 GA4 Signals change, UNVERIFIED
- developers.facebook.com/docs/marketing-api/audiences/reference/targeting-search (official,
  retrieved 2026-09-19, not re-fetched) — backs: the endpoint table
- webblend.au/blog/meta-ads-targeting-changes (third-party, retrieved 2026-09-19, not re-fetched) —
  backs: the orange-triangle flag from 2025-12-15
- facebook.com/business/help/744354708981227 (official, retrieved 2026-09-19, not re-fetched) —
  backs: Custom Audience sources
- lseo.com/paid-media/paid-social-media-marketing/leverage-custom-audiences-for-powerful-meta-ads-results
  (third-party, retrieved 2026-09-19, not re-fetched) — backs: own-assets-only engagement audiences
- jonloomer.com/special-ad-categories-meta-ads (third-party, retrieved 2026-09-19, not re-fetched) —
  backs: reported Special Ad Category targeting restrictions
- 1clickreport.com/blog/meta-ad-policy-changes-2026-compliance-guide,
  denote.net/blog/meta-ads-policy-update-2026, and
  auditsocials.com/blog/meta-sensitive-category-ad-targeting-audience-compliance-2026-personal-attributes
  (third-party, retrieved 2026-09-19, not re-fetched) — back: multimodal classification, landing
  page in scope, the "Evasion" violation
