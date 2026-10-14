# UTM Standard

A single, mandatory UTM tagging convention for every link this department creates or hands to a
company to publish — because an inconsistent UTM scheme is functionally the same as having no
attribution at all: GA4 and every downstream report groups by the literal string value, so
`Facebook` / `facebook` / `FB` / `fb_ads` become four different, unreconcilable "sources."

---

## 1. The core parameters this department uses, and what each answers

**[KB-MEAS-033]** Google's own campaign URL builder documentation does not use "required"/"optional"
terminology and does not define a fixed count of five parameters — it lists several parameters
(including `utm_id`, `utm_source_platform`, `utm_creative_format`, and `utm_marketing_tactic`,
the last two of which it notes "isn't currently reported in Google Analytics properties") and states
plainly: **"When you add parameters to a URL, you should always use `utm_source`, `utm_medium`, and
`utm_campaign`,"** and separately, for manual setup, "we strongly recommend that you set all relevant
UTM parameters, especially `utm_source`, `utm_medium`, `utm_campaign`, `utm_id`, and
`utm_source_platform`." This department narrows that broader set to the five parameters below —
a deliberate scope decision for this corpus's own tagging convention, not a claim about how Google's
page itself categorizes them:

| Parameter | This department's usage | Answers | Example |
|---|---|---|---|
| `utm_source` | Always set (Google: "always use") | Where the traffic originated (the referrer/platform) | `google`, `facebook`, `newsletter` |
| `utm_medium` | Always set (Google: "always use") | The marketing medium/channel type | `cpc`, `organic`, `email`, `social` |
| `utm_campaign` | Always set (Google: "always use") | The specific campaign, promotion, or initiative | `spring_kitchen_promo`, `always_on_leadgen` |
| `utm_term` | Situational | The paid keyword (search ads) | `bathroom+remodel+springfield` |
| `utm_content` | Situational | Differentiates similar content/links within the same ad/campaign (A/B variant, ad position, link location) | `variant_a`, `header_cta`, `footer_cta` |

(official, Google Analytics Help, "Custom campaigns," retrieved 2026-09-27:
https://support.google.com/analytics/answer/10917952 — verified via direct fetch 2026-09-27 that
the page uses no required/optional framing and lists additional parameters this table omits by this
department's own choice, not because the source excludes them.)

## 2. Formatting rules — case, separators, and why they're non-negotiable

**[KB-MEAS-034]** GA4 treats UTM parameter values as **case-sensitive, exact-match strings** for
grouping in acquisition reports — `Google`, `google`, and `GOOGLE` are three distinct source values
to the platform, producing three separate (and individually too-small-to-be-useful) rows in any
report grouped by source (official, Google Analytics Help, "Custom campaigns," retrieved 2026-09-27:
https://support.google.com/analytics/answer/10917952 — "Parameter values are case sensitive, e.g.
`utm_source=google` is different from `utm_source=Google`," with the same page's best-practices
section naming `Meta`/`meta` as an example of values treated as distinct). **This department's
standing convention, to be applied without exception:**

- **All lowercase, always** — no exceptions for brand names, campaign names, or anything else.
- **Underscores, never spaces or hyphens, as the word separator** within a parameter value
  (`spring_kitchen_promo`, not `spring-kitchen-promo` or `spring kitchen promo`) — a space in a URL
  gets URL-encoded to `%20` or `+` depending on the encoder, which then displays inconsistently
  across tools reading the same raw URL; picking one separator and enforcing it eliminates this
  entirely.
- **A closed, documented vocabulary for `utm_source` and `utm_medium`** — never a value invented
  ad hoc per campaign. The medium vocabulary in particular should be a short, fixed list (`cpc`,
  `organic`, `email`, `social`, `referral`, `display`, `affiliate`) matching the categories GA4's own
  default channel grouping expects, so traffic tagged with a non-standard medium value doesn't fall
  into an "Unassigned" or misclassified channel grouping bucket.

**Reject example:** one campaign tagged `utm_source=Facebook&utm_medium=Social-Media` and another
tagged `utm_source=facebook&utm_medium=paid_social` for the same platform and channel type — GA4
reports these as different sources/mediums entirely, splitting what should be one channel's data
into fragments too small to draw any conclusion from. **Pass example:** every Meta paid campaign
uses exactly `utm_source=facebook&utm_medium=paid_social` (or `utm_source=instagram` for
Instagram-specific placements, per a documented source-per-platform rule), with only `utm_campaign`
and `utm_content` varying between campaigns.

## 3. What NOT to tag — the self-referral trap

**[KB-MEAS-035]** **Never** apply UTM parameters to a link pointing to a page on the *same domain*
as the one the link lives on (an internal link from a blog post to a service page). **Correction
(2026-09-27): GA4 itself does not restart a session on encountering new campaign parameters** —
that was Universal Analytics' (GA4's deprecated predecessor) behavior, and GA4 explicitly reversed
it: "Sessions aren't restarted at midnight or when new campaign parameters are encountered," versus
UA's "If a user picks up new campaign parameters while on the website, a new session will be
started" (official, Google Analytics Help, "Comparing metrics: Google Analytics vs. Universal
Analytics," retrieved 2026-09-27: https://support.google.com/analytics/answer/11986666). GA4's own
session documentation confirms only that "the `session_start` event carries the information that
determines the attribution of the session, such as the gclid, UTM parameters, and referrer" (official,
Google Analytics Help, "GA4 Sessions," retrieved 2026-09-27:
https://support.google.com/analytics/answer/9191807) — it does not state whether a mid-session click
to an internally-UTM-tagged link overwrites that already-recorded attribution.
**UNVERIFIED — seeded, needs derivation: no official Google documentation was found (reachable
sources were checked) stating whether a UTM-tagged internal link updates or overwrites an active
session's already-recorded attribution; this specific mechanism is not confirmed and should not be
asserted as fact until a source is found.** **Doctrine/judgment, not a factual claim — the standing
reason to avoid self-referral tagging regardless:** even without a confirmed
overwrite mechanism, UTM-tagging an internal link miscategorizes that click's own event-level
campaign data and risks polluting attribution reports if the platform's attribution model ever
re-evaluates mid-session touches — there is no upside to tagging an internal link and a plausible
downside, so the practice is avoided on that basis alone (this is this department's own risk
judgment, not a sourced Google statement), not on the specific (unverified) mechanism
above. **Correct behavior:**
UTM parameters belong only on links that cross from an *external* system (an email, a paid ad, a
social post, a partner referral) into the property being measured — never on internal navigation.

**Reject example:** a "related services" module on a blog post links to the kitchen-remodel service
page with `?utm_source=blog&utm_medium=internal` appended. **Pass example:** the same internal link
carries no UTM parameters at all; internal-navigation analysis uses GA4's own internal traffic /
in-page navigation reporting, not UTM tagging.

## 4. Where UTMs interact with — and can break — offline/enhanced conversion matching

**[KB-MEAS-036]** A UTM-tagged link and a Google Ads auto-tagged link (which carries a `gclid`
parameter automatically, independent of any manual UTM tagging) are not mutually exclusive but serve
different purposes (official, Google Ads Help, "About auto-tagging," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/3095550 — "After someone clicks your ad, auto-tagging
adds a...parameter called GCLID...to the URLs people click through"; the same page notes that in
GA4, "auto-tagging is prioritized over manual tagging due to the absence of an override option" —
the source confirms auto-tagging adds `gclid` and that it takes priority over manual tagging in GA4,
but does not explicitly state whether the appending step itself occurs independent of whether manual
UTMs are also present on the URL, so treat that specific independence claim as the safe operational
reading of "prioritized... due to the absence of an override option" rather than a verbatim quote):
`gclid` is what makes [`enhanced-and-offline-conversions.md`](enhanced-and-offline-conversions.md)'s
click-to-conversion matching possible; UTM parameters are what makes a *non-Google-Ads* channel
(email, organic social, a partner referral) attributable in GA4's acquisition reports. **Never strip
or override the `gclid` parameter when constructing a landing-page URL for a Google Ads campaign** —
a click-tracking template or redirect that drops the auto-tagged `gclid` while adding manual UTMs
breaks the offline-conversion match path even though the UTM-based GA4 attribution still works,
producing a confusing state where GA4 shows the traffic correctly but Google Ads shows zero
conversions for it.

## 5. The link registry — every tagged link recorded, not improvised per campaign

**[KB-MEAS-037]** `(internal doctrine)` Maintain one running registry (a row per distinct tagged URL: the full URL, its
five UTM values, what asset/placement it lives on, and the date created) mirroring the tracking-plan
discipline in [`ga4-event-design.md`](ga4-event-design.md) §5 — the artifact, not just the
implementation. This is what lets a future reviewer (or the operator) verify a reported number
traces to a real, correctly-tagged link rather than trusting that tagging happened correctly by
convention alone, and what prevents two different pieces of content from accidentally reusing the
same `utm_campaign` + `utm_content` combination and having their traffic silently merged in reports.

---

## Contractor bend

- A remodeling GC's marketing mix is typically a handful of channels (Google Ads, GBP, Meta, maybe a
  local lead-marketplace platform, occasional email/SMS to past customers) — small enough that a
  clean UTM registry (§5) is genuinely maintainable by hand, with no excuse for the fragmented-source
  mess described in §2 that a busy team might otherwise tolerate at higher volume.
- Because this buyer relies entirely on this department's reporting to know which channel is working
  (they have no analyst of their own to catch a tagging inconsistency), a broken or inconsistent UTM
  scheme doesn't just produce ugly reports — it can directly cause a wrong keep/kill decision on
  spend, because a channel that's actually working looks worse than it is simply because its traffic
  got split across three differently-cased source values.
