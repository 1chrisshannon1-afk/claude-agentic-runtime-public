# API Build Mechanics — How a Campaign Structure Is Actually Built and Verified

Every other file in this corpus is strategy doctrine — WHAT to build (budget, bidding, targeting,
measurement). This file is the execution layer — WHETHER the platform will actually accept what
you specify, and how to build and verify it via the Google Ads API without the cascade failures
and false-confidence traps that cost a real live build attempt (ported build-incident, 2026-09-19).
Strategy files answer WHAT to build; this file and
[`asset-authoring-constraints.md`](asset-authoring-constraints.md) answer whether the platform will
actually accept it. **A Grade-A proposal that cannot be built is not Grade A** — see
[`grade-a-gates.md`](grade-a-gates.md), which now also carries the buildability gate this file
feeds.

Sourcing for this file: a live execute-pass build attempt against a real Google Ads account,
tagged `(ported build-incident, 2026-09-19)` below — a sub-label of `UNVERIFIED — seeded, needs
derivation`, defined once in [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md)'s opening note. This file
states only the platform-mechanism lesson that attempt produced, cross-checked directly against
the installed v22 Google Ads client library and official Google documentation as cited inline. The
company-specific build evidence (which account, which log files, exact op counts) belongs in the
measuring company's own paid-acquisition dossier (`<home>/.claude/oversight/paid-acquisition-strategist.md`
and its `marketing_kb_state/`), never in this runtime file, and is never assumed to already be
written down there.

---

## Build campaigns/ad groups/ads PAUSED

**Every campaign, ad group, and ad created by the execution lane that builds this seat's spec is
created with status `PAUSED`.** This seat itself is advisory-only with zero write access to any ad
platform (see `agents/paid-acquisition-strategist.md`); "build" in this file means whatever separate
execution lane turns a spec into API calls. Enabling a campaign commits money, pausing one changes
committed spend, and both are `$` actions: each needs a data-backed proposal plus explicit operator sign-off, never something
performed automatically as part of the build. **Creating a paused campaign with a budget stays a
non-`$`, construction-only step — a paused campaign's budget is committed only at enable, never at
creation** — so the initial build itself is never a `$` action requiring the operator's money
sign-off; only the later enable step is. This does not mean the initial build needs no review at
all: creating a campaign/ad group/ad is tiered T1 (reversible, not yet public — a draft, a paused
item) under the governing plan's autonomy tiers, so it is reviewed per the company's current
autonomy level like any other T1 change, never assumed to be a free action outside that review.

**One precision note:** "everything PAUSED" is imprecise if taken to mean every resource type.
CAMPAIGNS, AD GROUPS, and ADS are created PAUSED. CRITERIA (keywords, audiences, placements)
are correctly created ENABLED underneath a paused parent — an enabled criterion under a paused
campaign or ad group does not serve, because the parent's paused status gates delivery; creating
criteria disabled as well serves no purpose and complicates the eventual enable step. Say
"campaigns/ad groups/ads PAUSED; criteria ENABLED under them," not a blanket "everything paused."

**This does not conflict with [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #12** ("Writing to a PAUSED
or REMOVED campaign") even though that rule forbids writing to a paused campaign — the two govern
different phases. ANTI-PATTERNS #12 governs OPTIMIZING an existing, previously-live account: a
paused campaign there is read-only historical data, and no negative/budget/bid/settings change may
target it. This section governs INITIAL CONSTRUCTION, where nothing has ever served and the
campaign is paused specifically *because* it is mid-build, not because it was intentionally
retired. Once a campaign built by this process has been enabled and later paused again for any
reason, ANTI-PATTERNS #12 governs it from that point forward — the construction carve-out applies
only during the original build, never again after the campaign has actually served.

## Batched atomic mutate with temporary resource names

**Why a naive step-by-step build fails:** `validate_only=True` responses carry no `results` — "If
true, the request is validated but not executed. Only errors are returned, not results" (v22 SDK
proto docstring, `google/ads/googleads/v22/services/types/google_ads_service.py`, cross-checked
against [Google Ads API: API structure](https://developers.google.com/google-ads/api/docs/concepts/api-structure),
retrieved 2026-09-27). If you validate a budget create, then try to validate a campaign create that
references the (unreturned) budget's resource name, the campaign step has nothing to resolve its
parent against and fails as "cannot resolve parent" — even though every individual operation is
itself perfectly valid. **(ported build-incident, 2026-09-19):** the 6 dependent steps after the budget
(campaign → campaign criterion → ad group → ad-group criterion → RSA ad → asset) all failed behind
the unreturned budget in a step-by-step `validate_only` pass, purely from the missing-`results`
mechanic, with zero actual content defects among them.

**The fix:** build the whole dependent chain as **one atomic `MutateGoogleAdsRequest`**, ordered
**budgets → campaigns → campaign criteria → ad groups → ad-group criteria → assets → asset
links/ads** — asset resources (structured snippets, sitelinks, callouts, images) must be created
before any `CampaignAsset`/`AdGroupAsset` link that references them; RSA headline/description text
is inline on the ad create itself, not a separate asset. Each create carries an explicit temporary
**negative-id resource name** (e.g. `customers/{customer_id}/campaignBudgets/-1`) and every later
operation in the SAME request references that identical string as its parent. This is Google's own
documented temporary-resource-name mechanism
([Google Ads API: Temporary resource names](https://developers.google.com/google-ads/api/docs/mutating/best-practices),
retrieved 2026-09-27) — negative IDs are scoped to a single request, unique per request, and never
persist across requests. This is the only way the chain resolves correctly under `validate_only`,
and it is also simply the right way to build a multi-step campaign structure, whether validating or
executing for real. A single `GoogleAdsService.Mutate` request enforces a limit of 10,000 mutate
operations (up to 20,000 when every operation in the request is an `AdGroupCriterionOperation`) —
exceeding it returns `RequestError.TOO_MANY_MUTATE_OPERATIONS`
([Google Ads API: Mutating best practices](https://developers.google.com/google-ads/api/docs/mutating/best-practices),
official, retrieved 2026-09-27). Split into several atomic requests only at a dependency-closed
boundary (a point where nothing later in the chain references a temporary resource name from an
earlier request), once that cap is reached.

**A batched `validate_only` pass proves a request is well-FORMED (field names, types, shape) — and,
when the operation actually reaches the API and the caller's own error-extraction path is sound, it
ALSO surfaces real per-operation content errors** (missing parameters, incorrect field values,
length/word/punctuation policy violations). Where it stops proving anything is **ad policy
review**, which is asynchronous and separate from both `validate_only` and the synchronous
execute-pass result — see "Policy review is asynchronous," below. So "well-formed, not well-valued"
never described `validate_only`'s relationship to *content* validity (which it does cover, per
Google's own documentation quoted next) — it describes its relationship to *policy approval*, which
no synchronous call, validate or execute, can ever confirm. Google's own documentation says plainly
that a
validated request "would then be fully validated as if it were going to be executed, but the final
execution is skipped," and that validate_only can reveal "missing parameters and incorrect field
values," including automatic rejection for violations of "specific words, punctuation,
capitalization, or length"
([Google Ads API: API structure](https://developers.google.com/google-ads/api/docs/concepts/api-structure),
official, retrieved 2026-09-27) — this is the source for the "as if it were going to be executed"
and field-length claims; the v22 SDK's own `validate_only` docstring is narrower and says only "If
true, the request is validated but not executed. Only errors are returned, not results"
(`google/ads/googleads/v22/services/types/google_ads_service.py`, installed SDK, generated
protobuf) — it does not itself describe field-length or content-error coverage. A ported
build-incident (2026-09-19 build's own tooling) reported a batched validate as "clean" while a same-scope real
(executing) pass then produced structured-snippet and duplicate-asset content rejections — but that
"clean" result came from a local extractor that could never have reported an error regardless of
what the API actually said (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #19 for the root-cause
analysis) and from asset operations that were skipped client-side before validation, never sent to
the API at all. **The lesson is not "validate_only has a blind spot for content" — it is "a
validator's 'clean' result is not evidence until a positive control (a deliberately invalid
operation) proves it can report an error, and a report of operations sent vs. skipped must
accompany any 'validated clean' claim."** Keep local pre-flight validators as cheap defense-in-depth
regardless — never as a substitute for a real, positive-control-proven validate pass.

## Policy review is asynchronous — a clean build is not an approved ad

**Passing `validate_only`, and even a successful execute-pass build, proves the request was
well-formed and (per the caveats above) content-valid — neither proves the ad is approved to
serve.** Google Ads runs ad policy review as a separate, asynchronous process after the ad is
created; a newly-created ad sits under review and can be approved, disapproved, or approved with
limited serving (e.g. restricted by country) at any point after the build call returns
successfully. A "validated clean, built PAUSED" report is not a claim that the ads will serve once
enabled — it is silent on policy status entirely.

**After any build, read back each created ad's policy state before ever proposing to enable it:**
`ad_group_ad.policy_summary.approval_status` and `ad_group_ad.policy_summary.review_status` (v22
SDK, `google/ads/googleads/v22/resources/types/ad_group_ad.py`, `AdGroupAdPolicySummary` —
`review_status` is "Output only. Where in the review process this ad is"; `approval_status` is
"Output only. The overall approval status of this ad, calculated based on the status of its
individual policy topic entries."). Include both fields, per ad, in the build report.

**The enable-eligibility rule (the single definition — every other file in this corpus, including
[`grade-a-gates.md`](grade-a-gates.md)'s §0 item 8 and its failure-mode table, points here rather
than restating it):**

The v22 `PolicyApprovalStatusEnum.PolicyApprovalStatus` values are `APPROVED`, `APPROVED_LIMITED`,
`DISAPPROVED`, `AREA_OF_INTEREST_ONLY`, `UNKNOWN`, `UNSPECIFIED` (v22 SDK,
`google/ads/googleads/v22/enums/types/policy_approval_status.py`, installed SDK, generated
protobuf) — **there is no `ELIGIBLE` value in this enum.** The v22
`PolicyReviewStatusEnum.PolicyReviewStatus` values are `REVIEWED`, `REVIEW_IN_PROGRESS`,
`ELIGIBLE_MAY_SERVE`, `UNDER_APPEAL`, `UNKNOWN`, `UNSPECIFIED` (same file's sibling module,
`policy_review_status.py`) — `REVIEWED` means "Primary review complete. Other reviews may be
continuing" (v22 proto docstring, quoted verbatim) — **even `REVIEWED` is not an absolute guarantee
no further review is happening, though it is the strongest signal the API exposes.**
`ELIGIBLE_MAY_SERVE` means "The resource is eligible and may be serving but could still undergo
further review" (v22 proto docstring, quoted verbatim) — **this is still under review, not
`REVIEWED`, and is treated as blocking below.**

| `approval_status` | `review_status` | Enable proposal allowed? |
|---|---|---|
| `APPROVED` | `REVIEWED` | **Yes** — the strongest signal the API exposes, though `REVIEWED`'s own docstring allows other reviews to continue; state the read-back status verbatim in the enable proposal rather than claiming an absolute guarantee. |
| `APPROVED` | `ELIGIBLE_MAY_SERVE` or `REVIEW_IN_PROGRESS` | No — still under review for at least one policy topic; the read-back is stale evidence of nothing until `review_status` reaches `REVIEWED`. |
| `APPROVED_LIMITED` | `REVIEWED` | **Conditional** — the ad will serve, but with a stated limitation (e.g. geo-restricted). The enable proposal states the exact limitation from the ad's policy topic entries explicitly, for the operator to accept or reject; never enable silently on `APPROVED_LIMITED` as if it were unrestricted `APPROVED`. |
| `AREA_OF_INTEREST_ONLY` | any | **No, unless the operator explicitly accepts the stated limitation** — whatever the location-options setting. The v22 docstring reads: "Will not serve in targeted countries, but may serve for users who are searching for information about the targeted countries," and the enum's own severity order ranks it MORE severe than `APPROVED_LIMITED` ("The order of severity is DISAPPROVED, AREA_OF_INTEREST_ONLY, APPROVED_LIMITED and APPROVED") — so the ad does not serve inside the targeted area under any location option (v22 SDK, `policy_approval_status.py`, installed SDK, generated protobuf, read 2026-09-27). Under a Presence-only setting (see [`grade-a-gates.md`](grade-a-gates.md), "Geo targeting: the setting that silently wastes budget") it cannot serve to the intended audience at all. Flag it as a policy/geo mismatch requiring a decision, never propose the enable as if it will deliver. |
| `DISAPPROVED` | any | No. Fix the disapproved policy topic and rebuild the ad text; never propose enabling a disapproved ad. |
| `UNKNOWN` / `UNSPECIFIED` | any | No — the read itself was inconclusive; re-read before proposing anything. |
| **Any combination not listed above** (e.g. `APPROVED` with `UNDER_APPEAL`/`UNKNOWN`/`UNSPECIFIED`; `APPROVED_LIMITED` with any `review_status` other than `REVIEWED`) | — | **No** — default-deny; re-read, and wait for `REVIEWED`. |

**Never propose the enable (`$`) step for a campaign/ad group while any ad in scope is anything
other than a "Yes" row, or a "Conditional"/`AREA_OF_INTEREST_ONLY` row whose limitation is stated
in the proposal and explicitly accepted by the operator** — the enable proposal states each ad's
read-back `approval_status` and `review_status` explicitly, plus the specific limitation for every
conditional row, not just "build succeeded."

## Conversion uploads are not built through the Google Ads API

Offline conversion import and enhanced-conversions-for-leads uploads moved to the **Data Manager
API** and are blocked in the Google Ads API from 2026-06-15 (official, Google Ads Help "About
offline conversion imports," `support.google.com/google-ads/answer/2998031`, retrieved
2026-09-27). This file's batched-mutate mechanics cover campaign-structure builds only; never
specify a conversion upload as a `GoogleAdsService` mutate. Mechanism and the regulated-company
prohibition: [`measurement-and-attribution.md`](measurement-and-attribution.md), "Offline
conversion import."

## Idempotency and resume

**A partially-completed build must be resumable without re-issuing already-created resources.**
Before re-running a build against an account that may already hold some of the intended structure:

1. **Pre-flight READ existing resources by their natural key, not just "by name"** — most resource
   types in a typical build chain have no name field at all, so "read by intended names" only
   covers a minority of what a build actually creates. Use the identity key for each resource type
   (see the table below), excluding any row already in `REMOVED` status — a removed resource is not
   "already done."
2. **Skip what already exists AND matches spec** rather than blindly re-issuing every create
   operation — see step 3, a natural-key match alone is not enough to skip safely.
3. **Never blindly retry past a duplicate error, and never treat a natural-key match alone as proof
   the step is done.** Re-issuing a create for a resource type WITH a real duplicate error returns
   one of the real v22 errors — `MutateError.RESOURCE_ALREADY_EXISTS`,
   `CampaignError.DUPLICATE_CAMPAIGN_NAME`, `AdGroupError.DUPLICATE_ADGROUP_NAME`,
   `CampaignBudgetError.DUPLICATE_NAME`, or `CustomAudienceError.NAME_ALREADY_USED` (see
   [`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md)'s Custom Segments section
   for that last one) — never `DUPLICATE_CRITERION`, which does not exist in the v22 error enums.
   Most keyword/audience criteria, RSAs, and text assets have **no name field and no duplicate-name
   error class at all** — for those, the pre-flight read-back (step 1) is the ONLY detection
   mechanism; there is no error to catch on re-issue. **A duplicate-name error, or a natural-key
   match on read-back, means a matching resource exists — it does not mean that resource matches
   your spec.** Read the existing resource back, exclude `REMOVED` rows, and diff its spec-bearing
   fields (status, budget amount, geo target-type setting, bidding strategy, network settings,
   headline/description set, criterion bid) against the intended spec. Fields match → continue the
   chain from the existing resource's name. Fields mismatch → stop and raise it as a
   finding/proposal; never adopt the existing resource's differing settings silently.

**Natural key per resource type** (use this instead of "name" once a resource type has no name
field):

| Resource type | Natural key | Duplicate-error class exists? |
|---|---|---|
| Campaign budget | name | Yes — `CampaignBudgetError.DUPLICATE_NAME` |
| Campaign | name | Yes — `CampaignError.DUPLICATE_CAMPAIGN_NAME` |
| Ad group | name (scoped to parent campaign) | Yes — `AdGroupError.DUPLICATE_ADGROUP_NAME` |
| Keyword criterion | (parent ad group, keyword text, match type) | No — detect only by read-back |
| Other criteria (audience, location, device, etc.) | (parent, criterion type, criterion value/id) | No — detect only by read-back |
| RSA ad | (parent ad group, the full headline set + description set, sorted) | No — detect only by read-back |
| Text/structured-snippet/sitelink/callout/etc. asset | (asset type, content — e.g. the exact snippet values, or link text + URL) | Partial — three named error classes exist (v22 `AssetErrorEnum.AssetError`, installed SDK): `DUPLICATE_ASSET` ("Assets are duplicated across operations" — within the same request); `DUPLICATE_ASSET_NAME` ("The asset name is duplicated, either across operations or with an existing asset" — this one DOES catch a cross-request duplicate, but only for a **named** asset type, e.g. structured snippets have no name field and cannot trigger it); `DUPLICATE_ASSETS_WITH_DIFFERENT_FIELD_VALUE` (identical `Asset.asset_data` across operations submitted with a different field value — within the same request). None of the three is a general cross-request dedupe guarantee for an unnamed content asset (structured snippet, sitelink, callout) resubmitted with identical content in a later request — whether the API deduplicates that case at all is UNVERIFIED; treat read-back (step 1 above) as the only detection mechanism for it, not an error class. |
| Custom audience | name | Yes — `CustomAudienceError.NAME_ALREADY_USED` |

Keep the `REMOVED`-exclusion rule and the spec-diff rule above for every row in this table, not just
the named-resource rows.

## Sources (retrieved 2026-09-27 unless noted)

- developers.google.com/google-ads/api/docs/concepts/api-structure (official, retrieved 2026-09-27)
  — backs: `validate_only` behavior, including that a validated request is checked "as if it were
  going to be executed, but the final execution is skipped" and that missing parameters, incorrect
  field values, and length/word/punctuation/capitalization policy violations are among the errors it
  surfaces (cited inline, "Batched atomic mutate")
- developers.google.com/google-ads/api/docs/mutating/best-practices (official, retrieved
  2026-09-27) — backs: temporary negative-id resource-name mechanism, per-request scoping and
  uniqueness, and the 10,000/20,000 per-request mutate-operation cap and
  `RequestError.TOO_MANY_MUTATE_OPERATIONS` (cited inline, "Batched atomic mutate")
- v22 Google Ads client library, `google/ads/googleads/v22/services/types/google_ads_service.py`
  (installed SDK, generated protobuf) — backs: the narrower `validate_only` docstring quote ("If
  true, the request is validated but not executed. Only errors are returned, not results"), cited
  inline as distinct from the api-structure page's broader claim
- v22 Google Ads client library, `google/ads/googleads/v22/resources/types/ad_group_ad.py`
  (installed SDK, generated protobuf, `AdGroupAdPolicySummary`) — backs: the
  `approval_status`/`review_status` fields and their "Output only" docstrings, quoted verbatim
  (cited inline, "Policy review is asynchronous")
- v22 Google Ads client library, `google/ads/googleads/v22/enums/types/policy_approval_status.py`
  and `policy_review_status.py` (installed SDK, generated protobuf) — backs: the full enumerated
  value lists for `PolicyApprovalStatus` (`APPROVED`, `APPROVED_LIMITED`, `DISAPPROVED`,
  `AREA_OF_INTEREST_ONLY`, `UNKNOWN`, `UNSPECIFIED` — confirming no `ELIGIBLE` value exists) and
  `PolicyReviewStatus` (`REVIEWED`, `REVIEW_IN_PROGRESS`, `ELIGIBLE_MAY_SERVE`, `UNDER_APPEAL`,
  `UNKNOWN`, `UNSPECIFIED`) and the `REVIEWED`/`ELIGIBLE_MAY_SERVE` docstrings, quoted verbatim
  (verified by direct enum introspection against the installed package; cited inline, "Policy
  review is asynchronous," the enable-eligibility table), plus the `AREA_OF_INTEREST_ONLY`
  docstring and the enum's severity-order docstring (re-read 2026-09-27)
- v22 Google Ads client library, `google/ads/googleads/v22/errors/types/{mutate_error,
  campaign_error, ad_group_error, campaign_budget_error, custom_audience_error, asset_error}.py`
  (installed SDK) — backs: the real duplicate/already-exists enum names in "Idempotency and resume"
  (verified by grepping the installed package; `DUPLICATE_CRITERION` does not exist anywhere in the
  v22 error enums), and the three `AssetError` duplicate-class docstrings quoted verbatim in the
  asset-resource row of the natural-key table
- support.google.com/google-ads/answer/2998031 (official, Google Ads Help "About offline
  conversion imports," retrieved 2026-09-27) — backs: offline conversion import and
  enhanced-conversions-for-leads uploads moving to the Data Manager API and being blocked in the
  Google Ads API from 2026-06-15 (cited inline, "Conversion uploads are not built through the
  Google Ads API")
- Company-specific build evidence (which account, exact log rows, op counts, the extractor and
  request-id defects) belongs in the measuring company's own paid-acquisition dossier
  (`<home>/.claude/oversight/paid-acquisition-strategist.md` and its `marketing_kb_state/`) — this
  runtime file never names a company or cites a product-repo path for it.

**Note:** the `CallAsset.phone_number` proto citation that previously appeared here backs a claim
made in [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #8, not a claim made in this file — it is cited
inline there instead (that entry's own paragraph), per this corpus's one-citation-per-claim
discipline; it is not restated here.
