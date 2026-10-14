# Paid Acquisition — Competitor Targeting

## Competitor-targeting doctrine (2026-09-19)

Portable doctrine: what a paid-acquisition seat CAN and CANNOT do to target a competitor's
audience on Google Ads and Meta, the exact mechanism for each CAN, and the standing rule for
every CANNOT. Operator directive this doctrine exists to satisfy, verbatim: **"our agent needs to
know to do this on its own. and how to do it."** — this file is the "how," not just the "what is
allowed." No app-specific account IDs, budgets, or seed lists live here — those belong in the
company's own dossier at `<home>/.claude/oversight/paid-acquisition-strategist.md` (`<home>`
from `company.py resolve <slug>`; never the session's current repo when that is a different
company).

Surrounding audience mechanics (Custom Segment seed options and limits, Observation on Search,
placement buys, own-data list mechanics, consent effects, the Meta interest-lookup endpoints, Meta
own-data audiences, Special Ad Category classification risk, sequenced retargeting, and a
reach-X-use-Y decision table) are in [`audience-targeting-reference.md`](audience-targeting-reference.md).

### The standing rule

**Never tell the operator "impossible" without naming the real substitute and specifying it as a
built-paused spec for the execution lane.** Every
CANNOT below has a CAN-shaped substitute listed next to it. A paid-acquisition seat that stops at
"platforms don't allow that" without proposing the substitute has not finished the finding.

### Regulated-industry gate — read before applying ANY substitute below

**For a company whose pack declares a regulated classification** (`regulated: ["hipaa"]` — the
field and its only valid value are defined in `tools/gtm/company_schema.json` and validated by
`tools/gtm/company.py`), the substitutes below split into three groups. A company whose pack
declares `regulated: ["hipaa"]` (e.g. a health or dental practice) additionally follows
[`../compliance/hipaa-marketing-for-practices.md`](../compliance/hipaa-marketing-for-practices.md)
in full, and its HIPAA lane reviews every tracking or audience change. The pack flag is the
trigger, never a guess from the business type: a health/dental company whose pack omits the flag
is a pack defect to report, with audience/data substitutes treated as blocked until it is fixed.

1. **Restricted — advertiser-curated audiences:** Customer Match, the advertiser's own data
   segments (own-visitor remarketing lists, website/engagement custom audiences), audience
   expansion / Optimized Targeting, and lookalike/similar segments, plus any customer-list or
   hashed-PII upload. The restriction has two parts:
   - **On Google these are not available at all.** Platform policy rules them out for this
     category, so no compliance review or operator card can unlock them. Do not specify them for
     a regulated company's Google account.
   - **Everywhere else, any hashed-PII or customer/patient-list upload to any platform (including
     a list-seeded Meta custom audience or lookalike) is a governing plan §20.5.4 upload item —
     prohibited until the compliance lane verifies the specific use AND an operator card approves
     it. Every other Meta audience follows the Meta-side rule below (compliance-lane verification
     only, no card).**

   Google's own "Health in personalized advertising" page lists these as **not
   supported** for a sensitive-interest-category advertiser: "Advertiser-curated audiences: These
   audiences can't be used if promoting in sensitive interest categories, because they may
   inadvertently contain sensitive user signals," with Customer match, Your data segments, Audience
   expansion, and Lookalike segments each marked not supported (official, Google Advertising
   Policies Help, `support.google.com/adspolicy/answer/16701855`, re-fetched 2026-09-27; also
   `../compliance/hipaa-marketing-for-practices.md` `[KB-COMPLIANCE-052]`/`[KB-COMPLIANCE-053]`).
   Upload mechanics: see `measurement-and-attribution.md`'s "Regulated-industry hard exception" and
   `../compliance/hipaa-marketing-for-practices.md` `[KB-COMPLIANCE-049]`.
2. **Supported by Google's policy, with a caveat — Google Custom Segments.** The same page lists
   Custom segments as a separate, **supported** category, not as an advertiser-curated audience,
   with this condition: "Custom Segment audiences using sensitive creative assets or pointing to
   sensitive landing pages will only serve with Display campaigns to non-sensitive audiences or
   contextually" (official, same URL, re-fetched 2026-09-27). So Custom Segments are **not
   prohibited** for a health/HIPAA company. The caveat means: if the ad creative or landing page is
   itself health-sensitive (which a dental or medical practice's usually is), expect delivery to be
   narrowed to Display, to non-sensitive audiences, or to contextual placements — size and forecast
   for that, and never promise the reach a non-regulated advertiser would get. Seed choice is still
   reviewed: never seed a segment with terms or URLs that describe a health condition.
3. **Supported by Google's policy — Google-curated audiences.** The same page marks predefined
   Google audiences, in-market segments, and affinity as supported ("These audiences can be used
   even if promoting in sensitive interest categories"; demographics "with exceptions"). Apply them
   in Observation first, as for any company.

**Meta side — UNVERIFIED, prohibited until verified.** Meta's own Sensitive Health Information /
restricted-data policy is held UNVERIFIED in `../compliance/hipaa-marketing-for-practices.md`
`[KB-COMPLIANCE-054]` (Meta's Business Help Center
pages are JS-rendered and returned no readable text to this corpus's fetch tooling). For a
regulated company, Meta interest targeting, Advantage+ broad, website/engagement custom audiences,
lookalikes, and any Pixel/CAPI event carrying health-adjacent signal are prohibited until the
compliance lane (trust-architect for pixel/CAPI/form; the HIPAA content reviewer for content)
verifies the specific use from Meta's own policy text — one rule for every Meta audience, pixel or
CAPI item. An operator card is additionally required only when the item is also a governing plan
§20.5.4 upload item (Customer Match, enhanced conversions for leads, offline conversion uploads, any
patient/customer-list upload). The Meta Ad Library teardown (intelligence, not
targeting) is unaffected.

**Competitor-brand keyword bidding on Search stays outside this gate** — it is a keyword mechanism
with no audience or uploaded-data component, so no advertiser-curated-audience or health-signal
question applies. Ad text and landing pages still follow the company's claims policy and, for a
company whose pack declares `regulated: ["hipaa"]`, the HIPAA compliance file.

### GOOGLE — what you CAN do

#### Custom Segments (interest-model, not a visitor list)
- UI: Audience manager → Segments → **+** → Custom segments.
- API: `CustomAudienceService`. On create: `type` is `AUTO` or `SEARCH` — `INTEREST` and
  `PURCHASE_INTENT` are rejected on a newly created segment and kept only for existing ones
  (`CustomAudience.type_` docstring, `google/ads/googleads/v22/resources/types/custom_audience.py`
  in the installed google-ads 31.3.0 SDK, read 2026-09-27). `AUTO` lets Google pick the best
  interpretation (interest or search) at serving time; `SEARCH` "matches users by what they
  searched on Google Search" (`CustomAudienceTypeEnum`, `enums/types/custom_audience_type.py`,
  same SDK); `custom_audience.status` is OUTPUT-ONLY, never set on create; `name` is the unique key — a duplicate name returns
  `CustomAudienceError.NAME_ALREADY_USED`, which means the segment already exists, not an error to
  retry past.
- Member types: `CustomAudienceMemberType` = `KEYWORD` | `URL` | `PLACE_CATEGORY` | `APP`.
- **`URL` members mean "people who browse websites SIMILAR TO" the seed URLs — an interest model,
  NOT a visitor list.** Never describe this to a stakeholder as "people who visited
  `competitor.com`." It is an affinity signal Google infers from browsing patterns, not a record
  of who visited a specific site.
- **`KEYWORD` members are a second, separate competitor instrument — do not treat the `URL` seed as
  the only one.** A Custom Segment can instead be seeded with search terms, including competitor
  brand names and their natural modifiers (`<brand>`, `<brand> pricing`, `<brand> reviews`,
  `<brand> alternative`). **Only a segment created with `type: SEARCH` means "people who searched
  for any of these terms on Google"**; under `type: AUTO` Google chooses between an interest and a
  search interpretation, so never describe an `AUTO` segment to the operator as search-intent
  targeting. Build competitor search-term segments as `SEARCH` when that is the intent. A `SEARCH`
  segment is an *observed behavior* signal (they actually searched that term), closer to real in-market intent than the
  `URL` seed's *modeled interest* signal, and it is what makes competitor-brand search intent
  reachable on Display, Demand Gen, Video/YouTube, and as a PMax audience signal — surfaces where
  competitor-brand keyword bidding (below, Search-only) does not exist. **Seed both member types in
  separate segments so their performance is separable** — do not conflate them or describe either
  one as "the" competitor instrument (third-party practitioner opinion:
  [Store Growers](https://www.storegrowers.com/google-ads-custom-audience-segments/), re-fetched
  2026-09-27 — "You want to target the customer base of your competitors... custom segments are one
  of the best ways to tap into these users"; and
  [Search Engine Land](https://searchengineland.com/google-ads-custom-segments-464521), retrieved
  2026-09-19, not re-fetched).
- Custom Segments serve on **Display, Video/YouTube, Demand Gen, and Gmail only — never on Search,
  in any mode.** A campaign expecting a custom segment to narrow Search traffic is misconfigured;
  the Search substitute is competitor-brand keyword bidding (below) plus your own remarketing
  lists in Observation.
- **Performance Max is a separate case: a custom segment is never applied directly to a PMax
  campaign.** It can instead be attached as an **audience signal** at the asset-group level — a
  hint to PMax's automation that speeds learning, never a targeting constraint that narrows or
  restricts delivery (official,
  [About custom segments](https://support.google.com/google-ads/answer/9805516?hl=en), retrieved
  2026-09-19). **The seat must never describe a PMax audience signal as "targeting"** — a spec that
  says "we'll restrict PMax to competitor-seeded audiences" is factually wrong about how PMax works.
- Attach at ad-group level: `AdGroupCriterion.custom_audience.custom_audience = <resource_name>`.
  Observation vs. targeting (narrowing) is set via
  `Campaign.targeting_setting.target_restrictions[{targeting_dimension: AUDIENCE, bid_only:
  true|false}]` — `bid_only: true` = Observation (report + bid-adjust, does not narrow reach),
  `bid_only: false` = targeting (narrows reach to the segment). Default to Observation first on any
  segment without a proven volume floor.
- Sources: support.google.com/google-ads/answer/9805516 and /2497941 (official, retrieved
  2026-09-19).

#### Competitor-brand keyword bidding on Search
> **Precondition — [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #9 (evidence, not permission).**
> Competitor-brand keyword bidding is a standard tactic. Inside an operator-approved budget it is a
> within-ceiling optimization: agent-executable by the department's execution lane after the
> reviews the company's autonomy level requires, with no separate operator confirmation (this
> advisory seat recommends and specifies it; it never executes). #9's precondition is evidence:
> (a) expected CTR/conversion evidence per competitor term (measured per term, never assumed),
> (b) a plan to measure wrong-company calls once live, and (c) an exact-match-only negative plan
> for the business's own brand terms. **Money gates money:** a keyword add inside an approved
> budget is not `$`; building a new conquest campaign PAUSED (even with a budget field set) is T1,
> not `$`; enabling it (committing its budget), or setting or raising any budget or cap to fund
> it, is `$` and goes to the operator as a data-backed proposal. There is no default competitor
> negative: a PHRASE-or-broader negative blocks "alternatives to X" and "X vs us" switcher
> queries, so if one is warranted it is EXACT match only and a deliberate, stated choice.
- Trademarked competitor names ARE allowed as **keywords** you bid on.
- A trademark complaint from the competitor blocks the mark in **ad text**. **UNVERIFIED:** that
  this specifically produces a "silent headline disapproval with no separate alert to chase down"
  is not shown in the cited source below — the source states the ad-text restriction on complaint,
  not the disapproval-notification mechanics; confirm the silent/no-alert characterization against
  a fetchable source before relying on it.
- **Rule: a competitor trademark never appears in headline, description, path, sitelink, callout,
  or structured snippet text — keyword only.**
- Source: support.google.com/adspolicy/answer/6118 (official, retrieved 2026-09-19).
- Enforcement is complaint-driven: the trademark owner must submit a valid complaint identifying
  the ads, and a July 2023 change moved Google away from blanket same-industry restriction toward
  requiring holders to identify each infringing ad or party (third-party,
  [BluePear](https://bluepear.net/blog/google-ads-trademark-policy) and
  [AdPolice](https://www.adpolice.com/en/google-ads-trademark-policies-qa/), both retrieved
  2026-09-19, not re-fetched). **This is platform policy, not legal advice:** trademark law
  (US confusion analysis; non-US regimes are materially stricter) is outside every GTM seat's lane,
  and a genuine legal question about comparative use is an operator item, unlike the mechanics
  here.
- **Structure and expected economics.** Put competitor-brand terms in their own dedicated
  campaign with its own budget, so they cannot drain a generic or brand campaign and their metrics
  never contaminate a working campaign's bid strategy (building it paused is T1; enabling or
  funding it is `$`, per the precondition above). Exact or phrase match only — broad match on a
  competitor's brand name spends fast on loosely related queries. Expect low Quality Score
  (practitioner reports put it around 3–5, uncited), CPCs above own-brand and often above generic
  terms, and mid-funnel comparison-shopping intent with lower conversion rates — measure per term
  under #9 before scaling.

#### YouTube channel placements
- `YouTubeChannelInfo.channel_id` takes a `UC…` channel id — **never a handle, never a URL.** A
  handle (`@brandname`) must first be resolved to its `UC…` id before it can be used as a
  placement criterion.
- **Squatter-channel risk:** a handle search can surface an unofficial fan/parody/squatter channel
  using the brand's name. Verify the channel is the real, currently-active brand account (sub
  count, upload cadence, official links) before resolving a handle to an id and using it.
- **Build-blocking minimum: a campaign using YouTube channel/video placement targeting needs at
  least 10 channels or videos in the placement list, or it cannot be saved** — "You need to select
  a minimum of 10 channels or videos to save the campaign" (third-party practitioner source,
  [ClickedOn](https://clickedon.co/insights/google-ads-video-targeting-options), re-fetched
  2026-09-27; no official Google page stating the number has been located — UNVERIFIED against a
  primary source). Plan the placement list at ≥10 from the start; a wrong count announces itself
  immediately as a save failure.
- **Conversion-optimized video carries no content targeting.** Google removed content targeting
  (keywords, topics, placements) from Video campaigns that drive conversions: "From early 2023, all
  existing content targeting settings will be automatically removed from video campaigns that drive
  conversions," and "you'll no longer be able to add content targeting to new and existing
  conversion campaigns" (official, Google Ads Help "Optimize your Video campaign for more
  conversions," `support.google.com/google-ads/answer/9424882`, retrieved 2026-09-27). Those
  campaigns can no longer be created at all (see "Campaign types that no longer exist," below). A
  spec pairing "conversion-optimized video" with "run on competitor channels" is internally
  contradictory — use a views-oriented video campaign for placement-driven buys. Demand Gen
  channel controls (below) select surfaces (In-Stream, Shorts, Gmail…), not specific YouTube
  channels. Whether Demand Gen supports specific-channel placement targeting is UNVERIFIED in this
  corpus — confirm against current Google documentation before specifying it.

#### Similar Audiences are retired — know the replacements
- Google **sunset similar audiences (similar segments)**: it stopped generating new ones on
  **2023-05-01** and removed existing ones from every campaign and ad group on **2023-08-01**.
- Replacements: **Optimized Targeting** (Display, Demand Gen — Video Action Campaigns are
  retired; see "Campaign types that no longer exist," below) — **on by default**, and can be
  turned **off per ad group**; it uses the selected audience as a starting signal and expands
  delivery beyond it, leaning on Smart Bidding — and **Audience Expansion** (Video), the same
  mechanism carried forward on the surfaces VACs were upgraded into.
- **Rule for the seat:** when a campaign must reach ONLY the custom segment / remarketing list
  (e.g. a tight competitor-adjacent test where bleed into a broader audience would waste budget or
  confound the read), **turn Optimized Targeting OFF** in that ad group. When expansion is wanted,
  leave it **ON** and treat the segment as a seed rather than a hard boundary.
- **Never propose "a similar audience off our converters" on Google** — that feature has not
  existed since 2023 and asserting it is a hard factual error.
- Sources: [Search Ads 360 Help — similar audiences sunset](https://support.google.com/sa360/answer/13388565?hl=en)
  (official, retrieved 2026-09-19) and
  [Search Engine Journal](https://www.searchenginejournal.com/google-announces-sunset-of-similar-audiences/470017/)
  (third-party, retrieved 2026-09-19).

#### Own-visitor remarketing
- Prerequisite most teams forget: the AW tag must be firing on every page **and** an **Audience
  source must be enabled** — UI: Audience manager → Audience sources → Google tag → Set up tag.
  Nothing populates a remarketing list without this step even when the base tag itself is
  correctly installed and pinging.
- Floor to serve: **100 active visitors/users in the trailing 30 days — the same floor for
  Display, Search (RLSA), and YouTube alike.** The split in the source is by LIST TYPE and UPLOAD
  DATE, not by network: a customer-list upload refreshed on or after 2024-02-01 needs 100 matched
  users; one uploaded before that date is grandfathered at the old 1,000-matched-user requirement
  until it's refreshed. (Source: support.google.com/google-ads/answer/7476585, re-verified
  2026-09-27 against the live page text — "must have a minimum of 100 active visitors or users
  within the last 30 days," with the 1,000 figure appearing only in "any list uploaded before
  February 1, 2024 must still meet the previous requirement of minimum of 1,000 matched users." See
  "Corrections" at the end of this file for the 2026-09-19→2026-09-27 correction history on this
  claim.)
- Rule-based lists (v22 protobuf shape — `RuleBasedUserListInfo` carries only
  `prepopulation_status` and `flexible_rule_user_list`; legacy expression/date-rule fields are
  gone; `lookback_window_days` sits on each `FlexibleRuleOperandInfo` operand. Field names verified
  2026-09-27 against the installed google-ads 31.3.0 SDK:
  `google/ads/googleads/v22/common/types/user_lists.py` (`RuleBasedUserListInfo`,
  `FlexibleRuleUserListInfo`, `FlexibleRuleOperandInfo`, `UserListRuleInfo`,
  `UserListRuleItemInfo`), `resources/types/user_list.py` (`membership_status`), and the enums
  `OR`, `OR_OF_ANDS`, `CONTAINS`, `OPEN`, `REQUESTED` in `enums/types/`): build via `FlexibleRuleUserListInfo{inclusive_rule_operator: OR, inclusive_operands:
  [{rule: {rule_type: OR_OF_ANDS, rule_item_groups: [{rule_items: [{name: 'url__',
  string_rule_item: {operator: CONTAINS, value: <substring>}}]}]}, lookback_window_days: N}]}`,
  `membership_status: OPEN`, `prepopulation_status: REQUESTED`. **(Value semantics — the
  `url__` rule-item name, how the rule matches, and whether the API accepts this exact
  combination — are UNVERIFIED as of 2026-09-27; confirm them with a positive-control-proven
  `validate_only` pass, with a stated sent-vs-skipped operation count, before the first real call — see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19, "Trusting a 'validated clean' claim with no positive
  control." A batched `validate_only` pass genuinely DOES surface real per-operation content/value
  errors once the operation reaches the API and the caller's own error-extraction path is sound — an
  unproven "clean" result is not itself evidence the field names/values are correct; see
  [`api-build-mechanics.md`](api-build-mechanics.md) for the mechanics.)**

#### In-market / affinity audiences
- Query available categories: `SELECT user_interest.resource_name, user_interest.name,
  user_interest.taxonomy_type FROM user_interest`, then filter names for categories matching the
  company's pack-declared vertical (e.g. Business Services / Business Technology & Software for a
  B2B SaaS vertical; Home & Garden / Home Improvement for a home-services/contractor vertical).
- Apply in **Observation** first — never narrow reach to an in-market/affinity category without a
  proven volume floor from Observation data.

#### Demand Gen with video-responsive ads
- `demand_gen_video_responsive_ad` accepts an existing public YouTube video id as a creative
  asset — no separate video upload/hosting is required if a usable public video already exists.
- **Required fields are broader than they look, and a missing-field error does not name them.** A
  `demand_gen_video_responsive_ad` create omitting any required field returns a bare
  `field_error: REQUIRED` plus repeated `collection_size_error: TOO_FEW` with **no field path**
  named in the error ((ported build-incident, 2026-09-19), Google Ads API v22: one `REQUIRED` plus
  three `TOO_FEW` on a live execute-pass create attempt — **UNVERIFIED — evidence not yet
  relocated** to the measuring company's own dossier; not restated as build-log detail here). **Because the
  error carries no field path, which specific fields the three `TOO_FEW` errors correspond to is NOT
  in evidence — do not attribute them to particular fields.** Supply all of:
  `videos` (YouTube video asset), `headlines`, `long_headlines`, `descriptions`, `logo_images`,
  `business_name`, `call_to_actions`, `final_urls` — supply all of these on every create rather
  than guessing which subset caused a given `TOO_FEW`/`REQUIRED` error. Build a Demand Gen
  video ad from a complete asset checklist, never incrementally from a Search-ad mental model.
  (Per-field minimum counts UNVERIFIED against the v22 RPC reference as of 2026-09-19 — confirm
  before relying on a specific number.)
- **Demand Gen ad groups run under audience grouping, and the switch is IMMUTABLE.**
  `AdGroup.audience_setting.use_audience_grouped` can be set ONLY at ad-group create — never on
  update (confirmed against the installed v22 client library protobuf, `AudienceSetting`:
  "Immutable. If true, this ad group uses an Audience resource for audience targeting. If false,
  this ad group may use audience segment criteria instead." — v22 generated resource types,
  cross-checked against [Remarketing: audience targeting](https://developers.google.com/google-ads/api/docs/remarketing/audiences),
  retrieved 2026-09-19). Whether it defaults to `true` for a new Demand Gen ad group is
  UNVERIFIED — always set it explicitly on create. Two consequences, both seen as live refusals
  ((ported build-incident, 2026-09-19), v22 API — **UNVERIFIED — evidence not yet relocated** to the
  measuring company's own dossier):
  1. **Per-segment `AdGroupCriterion` audience attachment is rejected** once grouping is set —
     `criterion_error: CANNOT_ADD_AUDIENCE_SEGMENT_CRITERION_WHEN_AUDIENCE_GROUPED_IS_SET`. Build
     ONE `Audience` resource carrying all segment dimensions (custom segments, user lists) plus
     any exclusions, and attach that single resource to every Demand Gen ad group — never attach
     segments one-by-one via `AdGroupCriterion` the way the in-market/affinity or Custom Segment
     sections above describe for other campaign types.
  2. **Campaign-level criterion exclusions are rejected on Demand Gen** —
     `criterion_error: CANNOT_EXCLUDE_CRITERION`. Express the exclusion as an `exclusion_dimension`
     inside the Audience resource instead of a campaign-level `CampaignCriterion` exclusion.
  Always set `use_audience_grouped = true` explicitly on create even when it appears to match the
  current server default — leaving it undeclared risks a future default change stranding the ad
  group in the wrong mode with no repair path, since the field cannot be updated afterward.

### Campaign types that no longer exist (verify before specifying)

**Video Action Campaigns (VAC) cannot be created — the API rejects them, and so does the UI.**
[Google Ads Help: Video action campaigns are becoming Demand Gen campaigns](https://support.google.com/google-ads/answer/15110871)
(official, re-fetched 2026-09-27) states four dated key-date milestones plus a fifth in-body fact
about the September 2025 batch, all directly confirmed on this re-fetch:
- **April 2025** — Google removed the option to create new Video Action Campaigns from Google Ads.
- **July 2025** — Google began automatically upgrading existing Video Action Campaigns to Demand
  Gen (the stated start of the auto-upgrade rollout).
- **September 2025** (stated in the page body, not as a separate key date) — "As of September 2025,"
  any account with Video action campaign spend within 2025 had all its VACs upgraded to Demand Gen
  in that batch — i.e. AFTER the July 2025 start, as the ordinary reading of the dates requires; an
  account with **no** 2025 VAC spend instead had its VACs **removed** (not upgraded) as part of the
  same September batch, with historical data retained. A campaign that could not upgrade because of
  an error had its **original VAC deleted**.
- **December 2025** — Google Ads blocks the ability to extend campaign end dates past January 31,
  2026 — a separate, unrelated restriction, not itself an upgrade event.
- **April 2026** — the final remaining campaigns are auto-upgraded to Demand Gen.

Do not attribute the auto-upgrade itself to December 2025 — that date is the end-date-extension
block, a different fact from the same page. Do not describe the September 2025 batch as landing
"earlier than" or "by" the July 2025 start — September comes after July, and the page states the
batch as a September 2025 event following the July 2025 rollout start, not preceding or coinciding
with it. The API reference states plainly:
"You cannot create new Video campaigns or update existing ones using the Google Ads API"
([Google Ads API: Video campaigns overview](https://developers.google.com/google-ads/api/docs/video/overview),
official, retrieved 2026-09-19), which also names Demand Gen as "fully supported in the Google Ads
API for both creation and management." A live create attempt (executed 2026-09-19, on a live
Google Ads account, v22 API) returned a composite `context_error: OPERATION_NOT_PERMITTED_FOR_CONTEXT`
/ `mutate_error: MUTATE_NOT_ALLOWED` refusal, plus `field_error: REQUIRED` and
`date_error: LATER_THAN_MAXIMUM_DATE` on the same attempt — a mix of context/mutate refusal and
payload-level defects, not a single clean refusal with "no payload fix available"; the
platform-level conclusion (VAC creation is blocked) rests on the official docs above, not on this
one live attempt's error set alone. (The live attempt is a (ported build-incident, 2026-09-19);
**UNVERIFIED — evidence not yet relocated** to the measuring company's own dossier.)

**Substitute:** a Demand Gen campaign, fully supported for creation and management via API,
serving the same YouTube/Discover/Gmail surfaces. Restrict a Demand Gen ad group to the wanted
surfaces with `ad_group.demand_gen_ad_group_settings.channel_controls` (an **ad-group-level**
field, not campaign-level). **`channel_controls` selects surfaces, not specific YouTube channels:**
specific-channel placement on Demand Gen stays UNVERIFIED (see "YouTube channel placements,"
above), so for a genuine channel-placement buy use a views-oriented Video campaign instead. The
real surface list is seven channels (YouTube In-Stream, In-Feed, Shorts, Discover, Gmail, Display, Maps) under two
higher-level strategies, `ALL_CHANNELS` (default) or `ALL_OWNED_AND_OPERATED_CHANNELS`
([Google Ads API: Demand Gen channel controls](https://developers.google.com/google-ads/api/docs/demand-gen/channel-controls),
retrieved 2026-09-19) — so a YouTube-only placement intent should select the YouTube channels
specifically rather than accepting the all-channels default. What does NOT survive the VAC → Demand
Gen upgrade path, re-confirmed against the 2026-09-27 re-fetch of the same page: lead form ads
(beta) — Performance Max suggested instead; seasonal-event targeting; the new-customer-acquisition
bidding goal — lookalike segments/exclusions recommended instead; shared budgets — campaigns pace
independently despite retaining the setting; frequency caps — the platform "automatically accounts
for over-exposure" instead; bid modifiers; combined audiences; and affiliate location assets (beta),
with no stated alternative for that last one.

**A seat that specifies a Video Action campaign in 2026 is specifying something that cannot be
built.** Verify current campaign-type availability before proposing it — this class of error (a
campaign type that used to exist and no longer does) is exactly what "never say impossible without
naming the real substitute" (the standing rule, above) is for, applied in reverse: never propose
the retired thing without already knowing and stating its replacement.

### GOOGLE — what you CANNOT do

- **You cannot target another company's actual site visitors.** URL-based Custom Segments are a
  "similar-to" interest model (above), never a literal visitor list — no Google mechanism exists
  to retarget people who visited a specific competitor's domain.
- **Substitute (subject to [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #9's evidence precondition and,
  for a regulated company, the Regulated-industry gate above):** competitor-brand keyword bidding
  (captures active competitor-brand searchers, which is a stronger buying-intent signal than
  passive browsing similarity anyway) + URL- and search-term-seeded Custom Segments for the closest
  available approximation + your own-visitor remarketing lists in Observation stacked on top for
  incremental signal.

### META — what you CAN do

#### Interest targeting (brand-dependent — verify live, never assume)
> **Freshness gate (added 2026-09-19).** Every specific claim in this subsection — which interests
> exist, which are deprecated, and what the exclusion rules are — is a point-in-time reading of a
> surface Meta changes repeatedly and often without announcement. Treat each as UNVERIFIED once it
> is more than ~30 days past its retrieval date, and re-confirm against the live
> `adinterestvalid` endpoint (or Ads Manager) BEFORE building an ad set on it. Two removals inside
> one year are recorded below; assume a third has happened and check, rather than assuming the list
> below is still complete.
- Not every brand exists as a Meta ad-interest; confirm before building around one:
  `GET /search?type=adinterestvalid&interest_list=[...]` (Marketing API v26.0, current as of
  2026-09-19 — Meta revs this version number periodically; confirm the current version before
  building against it) returns which
  interests in the list are valid plus each one's audience size, and
  `GET /search?type=adinterestsuggestion` surfaces adjacent/suggested interests once you have at
  least one valid seed.
- **Deprecated interests silently stop delivery as of 2026-01-15** — an ad set built on a
  deprecated interest does not error, it simply stops serving: "If you had ad sets created before
  June 23, 2025 still running with deprecated targeting, those ad sets simply stopped serving
  impressions on January 15, 2026" (third-party practitioner source,
  [Pixel Movers](https://pixelmovers.co/blog/meta-detailed-targeting-removed-what-works-2026),
  re-fetched 2026-09-27; [Web Blend](https://webblend.au/blog/meta-ads-targeting-changes/),
  retrieved 2026-09-19, not re-fetched). Pixel Movers also dates deprecated interests becoming
  unavailable in NEW ad sets to 2025-12-15. [Social Media Today](https://www.socialmediatoday.com/news/meta-removes-more-detailed-ad-targeting-options-facebook-instagram/757856/)
  (third-party, published 2025-08-17, re-fetched 2026-09-27) independently states the
  consolidations "will take effect from January 15th 2026." Re-validate interest ids
  periodically, not just at build time. **Brandwatch describes a different, earlier phase and is
  cited separately, not as corroboration of "no error":** its text is a pre-deadline warning that an
  ad set left unfixed "will fail to go live" before 2026-01-15
  ([Brandwatch help center](https://social-media-management-help.brandwatch.com/en/articles/13215856-meta-changes-to-detailed-targeting-interests-in-advertise),
  third-party, retrieved 2026-09-19, not re-fetched).
- **Detailed-targeting exclusions were removed from the platform entirely on 2025-03-31** — "cannot
  exclude based on interest anymore" (third-party, Pixel Movers, re-fetched 2026-09-27). Use
  custom-audience exclusions instead of a detailed-targeting negative.
- **On 2025-06-23, Meta began consolidating detailed-targeting interest categories** — a separate
  event from the exclusions removal: "EDM fans" merged into broader music interests, "SUVs" into
  broader auto interests (third-party, Pixel Movers, re-fetched 2026-09-27 — the only source this
  corpus has for the June date and the example). Meta's own notice URL
  `facebook.com/business/help/458835214668072`, cited by an earlier pass for the 2026-01-15
  deprecation, has never been fetchable by this corpus's tooling and is not relied on for any date.
- Source: developers.facebook.com/docs/marketing-api/audiences/reference/targeting-search/
  (official, retrieved 2026-09-19).

#### Advantage+ audience, broad
- Broad targeting qualified by creative rather than by targeting narrowness. **Two co-cited sources
  disagree on the exact hard-constraint list, and this file relies on the narrower one — the
  disagreement is stated here rather than left implicit.** Conversios states: "Only location and
  minimum age are hard constraints. Everything else including interests, custom audiences, and
  lookalikes is a soft guide" (third-party, re-fetched directly 2026-09-27,
  [Conversios](https://www.conversios.io/blog/meta-advantage-audience-vs-detailed-targeting-2026-guide/)).
  **Linear Design, cited in the same paragraph for supplementary framing, states the opposite for
  exclusions and Special Ad Category:** it lists location, languages, minimum age, exclusions, AND
  Special Ad Category restrictions together as the enforced hard controls, with only
  age-above-minimum/gender/interests/custom-audiences/lookalikes as overridable suggestions
  (third-party, [Linear Design](https://lineardesign.com/blog/metas-advantage-audience/), retrieved
  2026-09-19, not re-fetched). **Neither source is Meta's own documentation, so this is not resolved by
  simply picking one — until an official Meta source is fetched, treat exclusions and Special Ad
  Category as a live disagreement between two third-party sources, not as settled either way.**
  Special Ad Category compliance in particular should not be assumed "soft" given the
  legal/regulatory stakes; treating it as confirmed-hard on Linear Design's citation alone is the
  safer default for that specific control until Meta's own documentation is fetched, even though
  this file otherwise defers to Conversios' narrower list for location/age. Location and minimum age
  are hard under both sources and are not in dispute. Everything both sources agree is soft (age
  above the minimum, gender, detailed targeting, custom audiences, lookalikes) is a suggestion
  Meta's own automation can expand past when it predicts better performance — let the creative do
  the audience qualification for those inputs; do not over-narrow them. See "Corrections" at the end
  of this file for a prior uncited figure dropped from this section.

#### Page-engagement custom audiences
- Build a custom audience from people who engaged with **your own** Page (video views, post
  engagement, Page visits, message starts, etc.) — this is fully sanctioned; it is engagement with
  YOUR asset, not a competitor's.

#### Lookalikes from your own converters
- Seed from your own converter event (custom audience of purchasers/signups/leads). A commonly
  repeated "≥100 people from a single country" floor and a "1,000-5,000 for a quality seed" figure
  circulate in practitioner writing, but **no source that actually states either number has been
  located.** The figure was previously cited to
  [AdNabu](https://blog.adnabu.com/facebook/meta-advantage-plus-audience/) — direct re-fetch of that
  page (2026-09-27) found it contains **no numeric audience-size or seed-size figures of any kind**
  (only unrelated cost-reduction percentages); the citation was wrong. Meta's own Lookalike
  Audiences help page is JS-rendered and returned no readable body text to this session's fetch
  tooling (same standing tooling limitation noted elsewhere in this file for other Meta help pages).
  **Treat both figures as uncited practitioner folklore with no located source — not even a
  third-party citation, UNVERIFIED against any source at all** — until a fetchable page (official or
  third-party) that actually states a number is found. Any claim that a lookalike becomes
  "meaningful" at some other specific count (e.g. ~500 seed users) is the same class of unsourced
  folklore. Seed quality dominates seed size regardless — a small list of real converters beats a
  large list of low-intent signups.

#### Website custom audiences from your own pixel
- Requires **your own** pixel firing on **your own** site — no cross-site or cross-advertiser
  visitor data is ever available.
- A commonly repeated minimum for a usable audience is **100 people**; no Meta-primary source for
  this specific figure has been located as of 2026-09-27 (Meta's own Custom Audiences help pages are
  JS-rendered and not retrievable by this corpus's fetch tooling — a standing tooling limitation, not
  a transient failure). **UNVERIFIED against a platform-primary source** — treat as a widely repeated
  practitioner figure, not a confirmed platform floor, until a fetchable primary source is found.
- **Cross-reference — reconciled with [`meta-ads-doctrine.md`](meta-ads-doctrine.md):** that
  file reports Ads Manager labeling a fresh website-visitors audience "Below 1,000" and not
  delivering it — a (ported incident-derived mechanism, 2026-06) observation, **UNVERIFIED —
  evidence not yet relocated** to the measuring company's own dossier. No fetchable Meta primary
  source for a hard 1,000-visitor delivery floor has been found. **Reconciled statement: treat an
  audience under ~1,000 as expect-no-delivery until independently verified;** below either figure,
  expect a thin, hard-to-serve audience, and prospecting may need to seed traffic through another
  channel before retargeting reaches useful scale.

#### The Meta Ad Library — the competitor instrument Meta actually gives you
**The honest answer to "what CAN we do about competitors on Meta" is not audience construction — it
is intelligence.** Meta offers no competitor *targeting* mechanism at all (confirmed above and
below), but it offers first-class competitor *intelligence*, free and without an account:
[facebook.com/ads/library](https://www.facebook.com/ads/library) (coverage and limits per
third-party practitioner sources [Shopify](https://www.shopify.com/blog/ad-library-facebook) and
[AdLibrary guide](https://adlibrary.com/guides/how-to-use-meta-ad-library-competitor-research), both
retrieved 2026-09-19, not re-fetched).
- Shows every ad currently running across Facebook, Instagram, Messenger, and Audience Network for
  any advertiser, searchable by brand name, with creative, start date, platforms, and active status.
- Good for: offers, hooks, price framing, objection handling, and which creative a competitor has
  run long enough to imply it is working.
- **Hard limits:** non-political ads disappear once inactive (no historical archive for a paused
  campaign); no filter by engagement or spend; and it reveals **nothing about targeting** — audience
  composition is never exposed by any Meta endpoint or report, by design.
- **Doctrine: when asked "how do we go after [competitor] on Meta," the correct deliverable is an
  Ad Library creative/offer teardown plus broad+Advantage+ delivery informed by it — not an audience
  construction.** Answering "we can't do competitor targeting on Meta" and stopping there is an
  incomplete finding under this file's own standing rule (never answer "impossible" without naming
  the real substitute) — the Ad Library is that substitute for Meta specifically.

#### Learning phase discipline
- An ad set needs roughly **50 optimization events in a rolling 7-day window** to exit the learning
  phase and deliver efficiently; below that it stays in (or returns to) learning, where delivery is
  less efficient (third-party practitioner sources
  [AdLibrary](https://adlibrary.com/posts/meta-ads-learning-phase-50-events-guide) and
  [Cometly](https://www.cometly.com/post/facebook-ads-learning-phase-stuck), both retrieved
  2026-09-19 — no Meta-primary source for the exact "50" figure has been located; treat as
  **UNVERIFIED against a platform-primary source**). Structure the campaign (consolidate ad sets,
  pick the single highest-volume real event as the optimization event) around hitting that floor
  rather than fragmenting budget across ad sets that individually cannot reach it.

### META — what you CANNOT do

- **You cannot target another company's actual site visitors or Page visitors/followers on Meta,
  under any mechanism.** Meta has **no URL-seeded audience mechanism at all** (no Meta equivalent
  of Google's Custom Segments) — Website Custom Audiences require your own pixel on your own site,
  full stop.
- **Substitute:** interest targeting on the competitor's brand where it plausibly exists as a
  valid ad-interest (verify live via the typeahead/validity endpoints above — never assume a brand
  is a valid interest), stacked with Advantage+ broad + creative-led qualification, plus your own
  lookalikes/retargeting once you have enough seed volume from your own site/Page, **plus a Meta Ad
  Library creative/offer teardown of the competitor's live ads** (above) to inform that creative —
  the honest, complete Meta substitute is intelligence-informed broad delivery, not an audience.

### CANNOT, stated once for both platforms

**No advertiser on either platform can retarget another company's actual site visitors or Page
followers.** This is a platform-level privacy boundary, not a missing feature or a tier-gated
capability — there is no paid tier, API access level, or workaround that unlocks it on Google or
Meta. Google's URL-based Custom Segments are the closest available approximation and are an
interest/similarity model, not a visitor record; Meta has no URL-seeded mechanism whatsoever. Any
proposal that assumes otherwise is a misunderstanding of the platform, not a targeting decision —
correct it and route to the substitutes listed above (for an unregulated company: competitor-brand
keyword bidding + URL- and search-term-seeded Custom Segments + in-market/affinity on Google;
interest targeting + Advantage+ broad + your-own-asset retargeting + a Meta Ad Library teardown on
Meta), subject to [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #9's evidence precondition, rather than
reporting the goal as unreachable. **For a regulated company, the Regulated-industry gate above
replaces that list:** on Google, competitor-brand keywords + Custom Segments (with the
sensitive-creative caveat) + in-market/affinity; own-visitor remarketing and every other
advertiser-curated audience is unavailable; every Meta audience item (interest targeting,
Advantage+ broad, own-asset retargeting, lookalikes) waits for compliance-lane verification. The
Meta Ad Library teardown is intelligence, not targeting, and stays available.

### META: API access prerequisites

> **Guard, before any of this applies:** use this only if the company already owns a Business
> Portfolio holding solely its own assets — **never create or join one**; if Meta's flow requires
> one, that step is an operator card (a NEVER row in the governing plan's autonomy matrix). Which
> setup steps are identity-class notify-then-execute actions, and which are restricted to a
> dedicated token-capture seat, is authorization policy outside this corpus: the governing plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md` §20.10, machine-local background) plans a
> dedicated `gtm-credential-setup` seat for token capture — **planned, not yet built**; until it
> exists, no agent captures a token. This file states only the platform mechanism.

**Meta system-user tokens need a business-owned developer app** ((ported build-incident,
2026-09-19) — this one item's evidence has been relocated to the measuring company's own
paid-acquisition dossier, never restated by path here, unlike the other ported build-incidents in
this file, which still carry "evidence not yet relocated"; not independently confirmed against Meta's own developer documentation). A Business Portfolio system
user cannot generate an `ads_management` token while the
portfolio's only app is Meta's built-in Conversions API Application — "Generate token" stays
disabled. The prerequisite is a real developer app (type Business, owned by that one business
only, with the Marketing API product) assigned to the system user. Meta's system-user name policy
rejects many plain names; reuse an existing system user rather than iterating (3-strike rule).

**UNVERIFIED, no primary-source citation obtained as of 2026-09-19 — confirm against Meta's own
developer documentation before relying on either claim:** that the generated token has a fixed
60-day expiry (Meta also documents non-expiring system-user tokens under some configurations, so
"the token is 60-day" should not be asserted as universal without checking the specific token
type generated); and that a non-discrimination policy certification gates asset assignment.
Record the app id next to the token secret so the probe/build script can call `GET /debug_token`
with the right app.

### Contractor bend

Applies only to a company whose pack declares `business_model: local_service` and whose line of
business is home-services/contractor work (see `INDEX.md`'s scope note; no pack field records line
of business yet, so read it from that company's dossier). Read the persona from that
company's own dossier; this is conditional vertical doctrine, not an assumed persona.

- **Competitors are usually small local businesses, not national brands.** Most will not exist as a
  valid Meta ad-interest — expect `adinterestvalid` to return nothing for them, and fall straight to
  the Meta substitute set (broad + creative-led qualification + your own-asset audiences + an Ad
  Library teardown). A local competitor may also run no Meta ads at all, in which case the teardown
  is short and says so.
- **Competitor-brand keywords on a local contractor's name carry a high wrong-company-call risk.**
  Someone searching a named local contractor usually wants that business's phone number. #9's (b)
  wrong-company-call measurement is not optional here; start with a small, measured test inside the
  approved budget and read call recordings or call outcomes before scaling.
- **A local competitor's URL is a thin Custom Segment seed.** Small sites carry little browsing
  signal for Google to model. Prefer search-term seeds (the competitor's name plus the trade and
  service-area modifiers, e.g. `<name> reviews`, `<trade> <city>`) over URL seeds, and seed several
  competitors together so the segment reaches a usable size.
- **Local Services Ads offer no competitor targeting at all** — LSA has no keyword or audience
  targeting, and its placement weighs the bid, the business's responsiveness and its profile
  quality (rating, review count, response time, verification) (see
  [`lsa-for-contractors.md`](lsa-for-contractors.md), official Local Services Help `answer/7527305`
  cited there). Competitor
  strategy on LSA means winning those factors, not targeting.
- **Ad Library teardowns are high-value for this vertical** — local competitors' offers (free
  estimates, financing, seasonal promotions) are visible there and inform creative directly.
  Financing offers still follow [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #15.

### Sources

**Dated per entry. "Re-fetched 2026-09-27" means this file's own fetch on that date; "retrieved
2026-09-19, not re-fetched" means the citation carries forward from the 2026-09-19 pass unchecked
since. Vendor and practitioner blogs are practitioner opinion, never platform documentation.**

- support.google.com/adspolicy/answer/16701855 (official, re-fetched 2026-09-27) — backs: the
  Regulated-industry gate's three groups — advertiser-curated audiences (Customer Match, your data
  segments, audience expansion, lookalike segments) not supported; Custom segments supported with
  the sensitive-creative/landing-page serving caveat; predefined Google audiences, in-market and
  affinity supported
- support.google.com/google-ads/answer/9805516 (official, retrieved 2026-09-19) — backs: Custom
  Segments overview, seed types, Observation-vs-targeting distinction, and PMax audience-signal use
- support.google.com/google-ads/answer/2497941 (official, retrieved 2026-09-19) — backs: the
  Display/Video/Demand-Gen/Gmail-not-Search surface table
- storegrowers.com/google-ads-custom-audience-segments (third-party practitioner opinion,
  re-fetched 2026-09-27) and searchengineland.com/google-ads-custom-segments-464521 (third-party,
  retrieved 2026-09-19, not re-fetched) — back: the competitor-seeded Custom Segment pattern
- support.google.com/google-ads/answer/7476585 (official, re-verified 2026-09-27) — backs:
  own-visitor remarketing's 100-user/30-day floor on Display, Search (RLSA), and YouTube, and the
  1,000-user floor for a customer list uploaded before 2024-02-01. **Demand Gen is not named on
  this page for this floor** — do not add it without a source that states it
- support.google.com/adspolicy/answer/6118 (official, retrieved 2026-09-19) — backs: competitor
  trademark policy — keyword allowed, ad text restricted on complaint
- clickedon.co/insights/google-ads-video-targeting-options (third-party practitioner source,
  re-fetched 2026-09-27) — backs: the 10-channels-or-videos minimum to save a placement-targeted
  video campaign (no official source located)
- support.google.com/google-ads/answer/9424882 (official, retrieved 2026-09-27) — backs: content
  targeting (keywords, topics, placements) removed from Video campaigns that drive conversions
- support.google.com/google-ads/answer/15110871 (official, re-fetched 2026-09-27) — backs: the Video
  Action Campaign creation-stop/auto-upgrade-to-Demand-Gen timeline and what does not survive the
  upgrade
- developers.google.com/google-ads/api/docs/video/overview (official, retrieved 2026-09-19) — backs:
  "cannot create new Video campaigns or update existing ones using the Google Ads API"
- developers.google.com/google-ads/api/docs/demand-gen/channel-controls (official, retrieved
  2026-09-19) — backs: Demand Gen ad-group-level `channel_controls` and the 7-channel/2-strategy list
- developers.google.com/google-ads/api/docs/remarketing/audiences (official, retrieved 2026-09-19)
  — backs: Demand Gen `use_audience_grouped` immutability, cross-checked against the installed v22
  client library
- support.google.com/sa360/answer/13388565 (official, retrieved 2026-09-19) and
  searchenginejournal.com/google-announces-sunset-of-similar-audiences/470017 (third-party, retrieved
  2026-09-19) — back: the similar-audiences sunset dates
- developers.facebook.com/docs/marketing-api/audiences/reference/targeting-search/ (official,
  retrieved 2026-09-19) — backs: `adinterestvalid`/`adinterestsuggestion` endpoints
- pixelmovers.co/blog/meta-detailed-targeting-removed-what-works-2026 (third-party practitioner
  source, re-fetched 2026-09-27) — backs: exclusions removed 2025-03-31; interest consolidation from
  2025-06-23 with the "EDM fans" example; deprecated interests unavailable in new ad sets
  2025-12-15; existing ad sets on deprecated interests stopped serving 2026-01-15
- webblend.au/blog/meta-ads-targeting-changes (third-party, retrieved 2026-09-19, not re-fetched) —
  backs: the 2026-01-15 silent-non-delivery characterization, alongside Pixel Movers
- socialmediatoday.com/news/meta-removes-more-detailed-ad-targeting-options-facebook-instagram/757856
  (third-party, published 2025-08-17, re-fetched 2026-09-27) — backs: consolidations taking effect
  2026-01-15. It does not state the June 2025 date or the "EDM fans" example
- Brandwatch help center (third-party, retrieved 2026-09-19, not re-fetched) — backs: the
  pre-deadline "will fail to go live" warning, a different phase from the post-deadline silent stop
- facebook.com/business/help/458835214668072 — never fetchable by this corpus's tooling; not relied
  on for any date or claim
- conversios.io/blog/meta-advantage-audience-vs-detailed-targeting-2026-guide (third-party,
  re-fetched 2026-09-27) — backs: location and minimum age as hard constraints, everything else on
  its own list soft (silent on exclusions and Special Ad Category)
- lineardesign.com/blog/metas-advantage-audience (third-party, retrieved 2026-09-19, not re-fetched)
  — backs: a different hard-constraint list that also includes languages, exclusions and Special Ad
  Category — cited as a disclosed disagreement
- adlibrary.com/posts/meta-ads-learning-phase-50-events-guide and
  cometly.com/post/facebook-ads-learning-phase-stuck (third-party, retrieved 2026-09-19, not
  re-fetched) — back: the ~50-events/7-day learning-phase figure, UNVERIFIED against a Meta source
- shopify.com/blog/ad-library-facebook and
  adlibrary.com/guides/how-to-use-meta-ad-library-competitor-research (third-party, retrieved
  2026-09-19, not re-fetched) — back: the Meta Ad Library's coverage and limits
- blog.adnabu.com/facebook/meta-advantage-plus-audience — **not a source for any claim here**; see
  Corrections

### Corrections

- **2026-09-27, Regulated-industry gate:** an intermediate edit declared Google Custom Segments
  prohibited for a health/HIPAA company as "advertiser-curated audiences." Google's own policy page
  (`support.google.com/adspolicy/answer/16701855`, re-fetched 2026-09-27) lists Custom segments as a
  separate, supported category with a sensitive-creative/landing-page serving caveat, and marks
  in-market and affinity supported. The gate now follows that page.
- **2026-09-27, YouTube placement sources:** the "Drive conversions has no placement targeting"
  claim was cited to ClickedOn, which does not state it; it now cites Google's own help page
  (answer/9424882). The 10-placement minimum was cited to Adzoola, which does not state it; it now
  cites ClickedOn, which does.
- **2026-09-27, Meta detailed-targeting dates:** earlier text attributed the 2025-06-23 date and the
  "EDM fans" example to Social Media Today and the 2026-01-15 date to a Meta help URL. On re-fetch,
  Social Media Today (published 2025-08-17) states only the 2026-01-15 effective date; the June date,
  the example, and the 2025-03-31 exclusions removal come from Pixel Movers; the Meta URL was never
  fetchable and is no longer relied on.
- **2026-09-27, own-visitor remarketing floor:** an intermediate edit misread answer/7476585 as
  splitting the 100-vs-1,000-user floor by network. The split is by customer-list upload date
  (before vs. on/after 2024-02-01). Demand Gen was dropped from the network list because that page
  does not name it.
- **2026-09-27, Advantage+ audience "hard constraints":** a prior version stated
  location/language/minimum-age/exclusions/Special-Ad-Category as confirmed hard constraints and
  cited an uncited "2-4 audience suggestions" figure. Conversios confirms only location and minimum
  age; Linear Design lists more. The section now discloses the disagreement and treats Special Ad
  Category as hard by default.
- **2026-09-27, lookalike seed-size figures:** the ≥100-seed and 1,000-5,000 figures were cited to
  an AdNabu post that contains no such numbers. Both are now uncited folklore.
- **2026-09-27, validate_only characterization:** corrected to match
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19 ("Trusting a 'validated clean' claim with no positive
  control") and `api-build-mechanics.md`: a batched `validate_only` pass does surface real
  per-operation content errors once the operation reaches the API and the error-extraction path is
  positive-control-proven.
- **2026-09-27, competitor-conquest gate:** earlier text in this file and in ANTI-PATTERNS #9
  disagreed on whether an operator-confirmed conquest goal was required and on the default
  competitor negative, and called a new paused conquest campaign `$`. All now follow the governing
  plan: evidence precondition only; no default negative; a paused build is T1; enabling or funding
  it is `$`.
- **2026-09-27, secondary-file citations:** claims previously cited "per" a mixed
  company-scoped targeting file now cite their sources directly, with fetch dates stated.
- **2026-09-28, that targeting file retired:** its remaining platform mechanics moved into
  [`audience-targeting-reference.md`](audience-targeting-reference.md) and the trademark-enforcement
  and campaign-structure bullets above; its company-scoped content moved to that company's own
  paid-acquisition dossier; the file was deleted.
