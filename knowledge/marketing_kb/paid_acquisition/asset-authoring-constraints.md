# Asset Authoring Constraints — Hard Platform Limits on Ad Assets

Hard, platform-enforced constraints on ad-asset content — value/character/count limits for every
asset type the Grade-A completeness covenant requires (structured snippets, RSAs, sitelinks,
callouts, call assets, price assets, promotion assets; business-name/logo, images, and lead-form
fields are marked UNVERIFIED below where no primary source was reachable), RSA duplicate-asset
rejection, and which of
these a `validate_only` pass surfaces only when the operation actually reaches the API and the
validator's own error-extraction path is proven by a positive control (see
[`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19). These are authoring-time constraints, not strategy (a
future `rsa-and-asset-strategy.md`, if authored, would cover how to build a strong asset set — no
such file exists in this corpus as of 2026-09-27); see [`api-build-mechanics.md`](api-build-mechanics.md)
for the full mechanics of why an unproven "validated clean" claim is not sufficient proof these
constraints are satisfied.

**Coverage note:** `grade-a-gates.md`'s §0 item 8 (BUILDABLE) rejects a proposal that violates this
file's limits. This file covers the asset classes listed above; for any asset type marked
UNVERIFIED below, BUILDABLE cannot mechanically check it — a positive-control-proven `validate_only`
pass is the fallback proof for those until a primary source fills the gap.

Sourcing: a live execute-pass build attempt against a real Google Ads account produced the
rejection classes cited below, tagged `(ported build-incident, 2026-09-19)` — a sub-label of
`UNVERIFIED — seeded, needs derivation`, defined once in [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md)'s
opening note. Numeric limits are cross-checked against the installed v22 Google Ads client library
protobuf and official Google documentation as cited inline. Company-specific build evidence
(which account, exact log rows) belongs in the measuring company's own paid-acquisition dossier
(`<home>/.claude/oversight/paid-acquisition-strategist.md` and its `marketing_kb_state/`), never
in this runtime file, and is never assumed to already be recorded there.

---

## Structured snippets

**Minimum 3 values, maximum 10, each at most 25 characters**, under a header drawn from Google's
fixed, documented header list (e.g. "Types," "Services," "Amenities"). The 3-value minimum (and the
**at least 4 values per header recommended** for fuller display) is confirmed by Google's own help
documentation: "Enter at least 3 values"
([Google Ads Help: About structured snippet extensions](https://support.google.com/google-ads/answer/6280012),
official, retrieved 2026-09-19). **The 10-value maximum and the 25-character-per-value limit are
not stated on that help page** — they come from the installed v22 client library protobuf instead:
`google.ads.googleads.v22.common.types.asset_types.StructuredSnippetAsset` states values "should be
between 3 and 10, inclusive" and each value "between 1 and 25 characters, inclusive." Cite the help
page for the 3-value minimum; cite the v22 proto for the 10-value maximum and the 25-character
limit.

- **Below 3 values, the asset is rejected outright** — `collection_size_error: TOO_FEW`.
- **Over 25 characters per value** — `string_length_error: TOO_LONG`.
- **(ported build-incident, 2026-09-19):** a live build produced multiple rejections against structured-
  snippet headers, a mix of `TOO_FEW` and `TOO_LONG`. The general lesson: validate the parsed
  value list's own count and per-value length locally, immediately after whatever step splits raw
  input into individual snippet values and before any API call — a parser that joins what should
  have been several short values into one long one (e.g. splitting on the wrong delimiter) produces
  exactly this `TOO_FEW`/`TOO_LONG` mix, and a batched `validate_only` pass will not reliably catch
  it either: see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19 for why a "clean" validate result is not
  evidence on its own (the affected operations can be skipped client-side before validation, and a
  build's own validator/extractor can independently be unable to report a content error regardless
  of what the API returns). The specific 2026-09-19 defect (which delimiter, which log rows) belongs
  in the measuring company's own paid-acquisition dossier, not here.

## Responsive Search Ads (RSAs)

**Exact-duplicate headline or description text within one RSA is rejected** —
`asset_error: DUPLICATE_ASSET: Assets are duplicated across operations`.
**(ported build-incident, 2026-09-19):** a live build's RSA create was refused on exactly this error,
for an ad group whose RSA carried the same headline text at two different headline slots. **The
build log records the error type and the ad group name only — it does not record which two
headline slots collided; never cite specific slot numbers for this class of incident unless a log
actually records them.**

**Abort on a duplicate, never dedupe silently.** A duplicate headline/description is an authoring
defect — it means two slots were meant to carry different messages and don't. Silently dropping
the repeat changes the ad's effective headline count without anyone deciding to accept a thinner
asset pool. Validate headline/description uniqueness, per-field character limits, and
trademark-free text (per [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md)'s
keyword-only competitor-trademark rule) locally before any API call, as cheap defense-in-depth — a
real, positive-control-proven `validate_only` pass DOES surface these content errors when the
operation actually reaches the API; see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19 for what a
"clean" validate result is and is not evidence of.

**Ad copy also follows the company pack's `claims_policy` and that company's dossier.** This file
covers only platform limits; what the text may claim is set by that company's pack and dossier.

**Count and character limits:** 3-15 headlines (minimum 3 required, maximum 15), each up to 30
characters; 2-4 descriptions (minimum 2 required, maximum 4), each up to 90 characters; two
optional path fields, up to 15 characters each, `path2` settable only when `path1` is also set
([Google Ads Help: About responsive search ads](https://support.google.com/google-ads/answer/7684791),
official, retrieved 2026-09-27). A double-width-language character (Korean, Japanese, Chinese)
counts as 2 characters against every one of these limits (same source). The v22 proto
(`ResponsiveSearchAdInfo`) carries no count/length limits of its own — headlines/descriptions are
unbounded `repeated` fields at the schema level, so these limits are enforced by the API at
mutate/validate time, not visible in the message definition; cite the help page above, not the
proto, for RSA counts and character limits.

## Sitelinks

**Link text: 1-25 characters, required.** Two optional description lines, `description1` and
`description2`, each 1-35 characters — if either is set, both must be set (v22 proto,
`SitelinkAsset`: link text "should be between 1 and 25, inclusive"; `description1` "if set, the
length should be between 1 and 35, inclusive, and `description2` must also be set"; `description2`
carries the mirror-image wording, "and `description1` must also be set"). **At least 2 sitelinks
must be created for any to be eligible
to show** ([Google Ads Help: About sitelink assets](https://support.google.com/google-ads/answer/2375416),
official, retrieved 2026-09-27, confirms the 25-character link-text limit and the 2-sitelink
display minimum; it does not itself state the description-line character limit — that figure is
from the v22 proto above).

## Callouts

**Callout text: 1-25 characters, required** (v22 proto, `CalloutAsset`, and confirmed by
[Google Ads Help: About callout assets](https://support.google.com/google-ads/answer/6079510),
official, retrieved 2026-09-27, which states the same 25-character limit). No documented minimum
count to create, but fewer than 2 callouts typically will not show at all in practice — treat 2 as
the practical floor pending a primary-source minimum-count citation (`UNVERIFIED — seeded, needs
derivation`).

## Call assets

**`country_code` and `phone_number` are both required fields** — `phone_number` is "the
advertiser's raw phone number" (v22 proto, `CallAsset`), directly readable and comparable
programmatically (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #8 for why this matters for
"wrong number" diagnosis). No character-count limit is stated in the proto for `phone_number`
itself; validate it against a real phone-number format, not a length check.

## Price assets

**3-8 price offerings per price asset** — the v22 `PriceAsset` proto states the collection size
"should be between 3 and 8, inclusive"; this is a size constraint on the collection, not a
`Required` field marking, and no primary source states it as a hard minimum-to-create the way the
sitelink 2-minimum-to-show is stated. **Each individual offering's `header`, `description`,
`price`, and `final_url` are separately marked `Required`** on the `PriceOffering` message itself
(v22 proto, `PriceOffering`); `header` and `description` are each "The length of this string should
be between 1 and 25, inclusive."

## Promotion assets

**`promotion_target` is Required** — "a freeform description of what the promotion is targeting"
(v22 proto, `PromotionAsset`) — with no character-count limit stated in the proto. **Exactly one of
`percent_off` or `money_amount_off` is required** (a proto `oneof`: "Either this or [the other] is
required," stated symmetrically on both fields) — a promotion asset with neither, or with both set,
is malformed. `promotion_code` and `orders_over_amount` are each optional and mutually exclusive
with each other (a second `oneof`, `promotion_trigger`) but not with the discount fields.
`terms_and_conditions_text` and `terms_and_conditions_uri` are both optional, with no
character-count limit stated in the proto for the text field. `redemption_start_date` /
`redemption_end_date` / `start_date` / `end_date` are optional `yyyy-MM-dd` strings; `occasion`, if
set, constrains the redemption window to fall inside that occasion's own date range (v22 proto,
`PromotionExtensionOccasionEnum`).

**No official Google Ads Help page was reachable as of this retrieval that states a character
limit for `promotion_target`, `terms_and_conditions_text`, or a minimum-count-to-show requirement
analogous to sitelinks' 2-minimum** (checked: support.google.com/google-ads/answer/7367521 and
support.google.com/adspolicy/answer/7374309, retrieved 2026-09-27 — both describe the creation
flow and content-policy restrictions, such as the promo-code field never containing a phone number
or product description, but neither states a text-length limit or a minimum asset count). **Tag
any character-count or minimum-count claim for promotion assets UNVERIFIED — needs a direct fetch
of the current official specs** if one is added to a proposal; only the proto's `Required`-field
markings and the two `oneof` constraints above are sourced.

## Not yet sourced from a primary reference — UNVERIFIED

The completeness covenant in `grade-a-gates.md` also requires business name, business logo,
images, and lead-form assets to be addressed — five asset classes in total once promotion assets
(above, sourced for its required-field/oneof mechanics but UNVERIFIED for character/count limits)
are included in the count. The v22 proto declares required fields for lead-form
assets (`business_name`, `call_to_action_type`, `call_to_action_description`, `headline`,
`description`, `privacy_policy_url` — all required; background image must be exactly 1200x628px)
but states no character-count limits for any of the text fields. Business-name and logo/image size
and format specs were not found in the proto or in a reachable official help page as of
2026-09-27. **Tag these UNVERIFIED — needs a direct fetch of the current official specs** rather
than assume a figure; until sourced, `grade-a-gates.md`'s BUILDABLE gate cannot mechanically check
these asset classes (business name, business logo, images, lead-form fields — and promotion
assets' own character/count limits) and must fall back to a positive-control-proven `validate_only`
pass as the only available proof for them.

## Sources (retrieved 2026-09-19; RSA/sitelink/callout figures retrieved 2026-09-27)

- support.google.com/google-ads/answer/6280012 (official) — backs: structured snippet minimum-3-
  values requirement and the 4+-values-per-header recommendation (cited inline, "Structured
  snippets"). Does NOT back the max-10 or 25-character figures — see the v22 proto citation below
  for those.
- support.google.com/google-ads/answer/7684791 (official, retrieved 2026-09-27) — backs: RSA
  headline count (3-15) and character limit (30), description count (2-4) and character limit
  (90), path-field character limit (15), and the double-width-character-counts-as-2 rule (cited
  inline, "Responsive Search Ads (RSAs)")
- support.google.com/google-ads/answer/2375416 (official, retrieved 2026-09-27) — backs: sitelink
  link-text 25-character limit and the 2-sitelink display minimum (cited inline, "Sitelinks")
- support.google.com/google-ads/answer/6079510 (official, retrieved 2026-09-27) — backs: callout
  25-character limit (cited inline, "Callouts")
- v22 Google Ads client library,
  `google/ads/googleads/v22/common/types/asset_types.py` (installed SDK, generated protobuf,
  `StructuredSnippetAsset`) — backs: max-10-values and 25-character-per-value limits, quoted
  verbatim ("The size of this collection should be between 3 and 10, inclusive. The length of each
  value should be between 1 and 25 characters, inclusive.") (cited inline, "Structured snippets")
- v22 Google Ads client library, same file, `ResponsiveSearchAdInfo` — confirms the proto carries
  no count/length constraint of its own for RSA headlines/descriptions (cited inline, "Responsive
  Search Ads (RSAs)")
- v22 Google Ads client library, same file, `SitelinkAsset` — backs: sitelink description-line
  1-35-character limit and the both-must-be-set rule (cited inline, "Sitelinks")
- v22 Google Ads client library, same file, `CalloutAsset` — backs: callout 1-25-character limit
  (cited inline, "Callouts")
- v22 Google Ads client library, same file, `CallAsset` — backs: `country_code`/`phone_number`
  required-field status (cited inline, "Call assets")
- v22 Google Ads client library, same file, `PriceAsset`/`PriceOffering` — backs: 3-8 price
  offerings per asset, 1-25-character header/description limits (cited inline, "Price assets")
- v22 Google Ads client library, same file, `PromotionAsset` — backs: `promotion_target`'s
  Required status, the `percent_off`/`money_amount_off` and `promotion_code`/`orders_over_amount`
  `oneof` constraints, and the absence of any stated character limit for `promotion_target` or
  `terms_and_conditions_text` (cited inline, "Promotion assets")
- support.google.com/google-ads/answer/7367521 and support.google.com/adspolicy/answer/7374309
  (official, retrieved 2026-09-27) — checked for promotion-asset character/count limits; neither
  states one, which is why those limits are tagged UNVERIFIED rather than omitted or asserted
  (cited inline, "Promotion assets")
- v22 Google Ads client library, same file, `LeadFormAsset` — backs: the required-field list with
  no stated character limits (cited inline, "Not yet sourced from a primary reference")
- Company-specific build evidence (which account, exact log rows and step names, the affected ad
  group's name) belongs in the measuring company's own paid-acquisition dossier
  (`<home>/.claude/oversight/paid-acquisition-strategist.md` and its `marketing_kb_state/`) — this
  runtime file never names a company or cites a product-repo path for it.


## Field notes: Google Ads business name and IDs (added 2026-09-28)

- **The business-name asset must match the landing-page domain/site or the verified advertiser
  name.** The asset form says so. When the verified advertiser is the owner's personal name and the
  domain uses a different word than the brand, the brand name keeps getting rejected. Put the exact
  brand name on every page of the site first, then submit (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28; approval outcome UNVERIFIED — seeded,
  needs derivation).
- **The `ocid` in Google Ads URLs is not the customer ID.** Read the 10-digit customer ID from the
  account menu before recording it anywhere (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **Change history's default date range can exclude today.** Confirm a fresh edit in the asset
  library itself (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
