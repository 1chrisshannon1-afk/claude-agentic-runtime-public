# Measurement Anti-Patterns — Things a Seat Must NEVER Do

Every item below is something the `measurement-architect` seat (or any GTM agent touching
measurement) must refuse to do or recommend, even when a founder/operator asks for it directly, even
when a competitor or a prior agency visibly does it, and even when it would make a report look better
short-term. Cite this file when refusing.

---

## 1. Hard-gating a tag on a boolean consent check with no modeled fallback

**What it is:** Implementing `if (hasConsent('analytics_storage')) { fireTag() }` instead of the
standard `gtag`/GTM built-in consent integration.

**Why it's banned:** Consent Mode's entire design premise is that denied consent should trigger
modeled estimation, not silent data loss. A hard gate defeats this and produces a silently
under-reported number with no error state anywhere to flag it — see `consent-mode.md` §3 for the
full mechanism. **Reject example:** any tag-firing logic that checks a consent boolean and simply
returns early on `denied` with no Consent Mode integration underneath it. **Pass example:** the
standard `gtag('consent', ...)` lifecycle, verified per `consent-mode.md` §4's audit checklist.

## 2. Sending raw PII into a GA4 parameter, a hashed-conversion field, or a Customer Match list

**What it is:** A `lead_email`/`customer_phone` custom parameter carrying a raw address or number;
an enhanced-conversions field populated with unhashed data behind a misleadingly-named variable.

**Why it's banned:** GA4's own terms of service prohibit sending personally identifiable data as an
event parameter; enhanced conversions and offline conversion imports are explicitly designed to
accept only SHA-256-hashed, normalized values. See `ga4-event-design.md` §3 and
`enhanced-and-offline-conversions.md` §2. **Reject example:** a parameter named `hashed_email` that
was never actually passed through a hash function. **Pass example:** an opaque internal CRM id used
to join session data to a lead record server-side, with real hashing verified against the actual
outbound network payload, not the configuration UI's toggle state.

## 3. Reporting raw call/click/session volume as if it were a qualified lead count

**What it is:** Presenting total call-tracking volume, total form-submit count, or total session
count as "leads" with no qualification or deduplication step.

**Why it's banned:** A call-tracking number, a GA4 event count, or a raw session count each measure
a different, narrower thing than "a real prospective customer" — wrong numbers, spam, and duplicate
touches across channels all inflate these counts. See `call-tracking.md` §3 and `reconciliation.md`
§3.4. **Reject example:** "You got 40 leads from Google this month" reported from raw call-tracking
volume with no qualified/unqualified split. **Pass example:** qualified leads (CRM-confirmed genuine
inquiries) reported separately from raw volume, with the gap explained.

## 4. Redefining a registered metric's formula in place

**What it is:** Changing what `cost_per_lead` (or any registered metric id) computes — a different
filter, a different attribution window, a different date-range convention — without creating a new
id, so historical and post-change values sit under the same label with different meanings.

**Why it's banned:** This makes every trend chart spanning the change silently misleading — see
`metric-registry-doctrine.md` §2. **Reject example:** redefining `cost_per_lead` from "spend / all
submits" to "spend / qualified leads" in place. **Pass example:** a new `cost_per_qualified_lead` id,
registered separately, with the old id's historical meaning preserved.

## 5. Substituting `0` for missing or unavailable data

**What it is:** Rendering a metric as `0` when the real state is "the API call failed," "the
tracking wasn't live yet," or "no data has arrived."

**Why it's banned:** `0` is a real, meaningful value (nothing happened) that becomes indistinguishable
from "we don't know" once rendered — and averages/sums/trend lines computed over a silently-zeroed
gap are systematically wrong while looking precise. See `metric-registry-doctrine.md` §3. **Reject
example:** "Meta ROAS: 0.0x" for a week the Meta API integration was actually broken. **Pass
example:** the same cell renders "no data — API error" and is excluded from any rollup calculation.

## 6. Reporting a rate metric from a sample too small to mean anything

**What it is:** Presenting a computed percentage (a close rate, a CTR, a CPA) from a handful of
underlying events as if it carried the same confidence as a large-sample figure, with no sample size
stated.

**Why it's banned:** A "50% close rate" from 2 leads and from 200 leads are not the same claim, and
presenting them identically erases the reader's ability to judge confidence. See
`metric-registry-doctrine.md` §4 and `reporting-and-dashboards.md` §2. **Reject example:** "Campaign
B has a 50% close rate" with n=2 and no sample-size disclosure. **Pass example:** "insufficient data
to compare reliably (n=2)" until the registered minimum sample size is cleared.

## 7. Stating a causal claim from an association-only comparison

**What it is:** "The new landing page increased conversions by 20%" from an uncontrolled before/
after comparison with no ruled-out confounders (seasonality, a simultaneous campaign change,
competitor activity).

**Why it's banned:** An association is not evidence of causation without a design that can actually
isolate cause (a real A/B test, or a rigorously ruled-out confounder set) — see
`reporting-and-dashboards.md` §1. **Reject example:** any causal verb ("increased," "caused," "drove")
applied to an uncontrolled before/after comparison. **Pass example:** "conversion rate rose 20% in
the two weeks after launch" stated as an observation, with a controlled test proposed if a causal
answer is actually needed for the decision at hand.

## 8. Applying UTM parameters to an internal, same-domain link

**What it is:** Tagging a link from one page to another page on the same property with
`utm_source`/`utm_medium`/etc.

**Why it's banned:** GA4 can start a new, misattributed session on arrival at a UTM-tagged internal
link, fragmenting one real visit into two sessions attributed to a source that didn't actually bring
the visitor to the site. See `utm-standard.md` §3. **Reject example:** a "related services" module
linking to another page on the same domain with `?utm_source=blog&utm_medium=internal` appended.
**Pass example:** the same link carries no UTM parameters; internal navigation is analyzed with
GA4's own in-page/internal-traffic reporting instead.

## 9. Using an inconsistent, ad hoc UTM vocabulary per campaign

**What it is:** Letting `utm_source`/`utm_medium` values vary in case or spelling across campaigns
for the same actual channel (`Facebook` vs. `facebook` vs. `FB`).

**Why it's banned:** GA4 groups by exact string match — inconsistent casing/spelling fragments one
channel's data into multiple unreconcilable rows, corrupting every downstream channel-performance
comparison. See `utm-standard.md` §2. **Reject example:** two Meta campaigns tagged with different
source/medium casing. **Pass example:** a fixed, documented, all-lowercase vocabulary applied
without exception, tracked in a link registry.

## 10. Claiming a verification was performed when only configuration was checked

**What it is:** Reporting a conversion action, tag, or event as "live" or "verified" because it was
configured in a platform UI, without running the 4-signal test.

**Why it's banned:** Configuration is not firing; firing is not landing correctly; landing is not
being read by the downstream platform; and desktop success is not mobile success. Skipping any of
the four signals in `reconciliation.md` §2 produces a false-clean report — the same structural
danger this corpus's SEO domain names for a falsely-claimed Manual Actions check
(`seo/ANTI-PATTERNS.md` #9). **Reject example:** "GA4 tracking is live" stated from the GTM
configuration UI alone. **Pass example:** all four signals confirmed, including a real mobile-path
test, before calling anything live.

## 11. Asserting a state-specific call-recording consent rule without live legal verification

**What it is:** Telling a company "your state doesn't require call-recording disclosure" (or the
reverse) from general knowledge of one-party/two-party consent categories, without re-verifying the
specific state's current rule against a primary legal source.

**Why it's banned:** This is a legal determination with real regulatory exposure, not a platform-
mechanics fact this domain can settle on its own — see `call-tracking.md` §4's explicit
`UNVERIFIED` marking and its safe-default (always disclose) posture. **Reject example:** disabling a
recording disclosure for a company because "that state is one-party consent," sourced from memory.
**Pass example:** the default disclosure stays on; a state-specific exception is adopted only after
the `compliance/` domain verifies the current rule from a primary source and records the citation.

## 12. Fabricating a home-services benchmark number from an unrelated vertical's data

**What it is:** Quoting a benchmark CPL/CPA/close-rate figure sourced from a different vertical
(e.g. dental-practice patient acquisition) as if it applies to a residential remodeling GC.

**Why it's banned:** These numbers are vertical-specific by construction; porting them as fact
mis-prices every downstream recommendation this corpus feeds — see the house-style rule in
`INDEX.md` and the identical rule in `seo/ANTI-PATTERNS.md` #10. Only the *mechanism* (a gate
structure, a verification procedure, a threshold's logical shape) ports; the number never does
without independent, cited, home-services-specific derivation.

---

## Contractor bend

None of the above changes for the small owner-operated home-services/trade business buyer — if anything the stakes are higher, because
this buyer has no in-house analyst to catch a bad number before it drives a real budget decision.
When explaining why something here is off-limits, skip the platform-mechanics framing and lead with
the business consequence in plain terms: "if we report a number that isn't real, you make a decision
based on something that didn't happen — that's worse than not having the number at all." Never
assume this buyer will independently catch an inflated or fabricated figure; the obligation not to
produce one is entirely on this department.
