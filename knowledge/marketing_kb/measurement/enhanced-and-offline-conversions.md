# Enhanced Conversions and Offline Conversion Imports

How to close the gap between an online ad click and a real-world outcome that happens later or
off-platform (a phone-booked job, a signed contract, a QuickBooks-recorded payment) — the Google
Ads mechanisms that do this (Enhanced Conversions, a single unified setting since April 2026, and
Offline Conversion Import), what each requires, and the hashing/matching rules that make them safe
to use without leaking PII.

---

## 1. Two different mechanisms, two different problems

**[KB-MEAS-021]** These solve different problems — and, as of an **April 2026** platform change,
the web and leads variants of Enhanced Conversions are no longer separately configured:

| Mechanism | Solves | Timing |
|---|---|---|
| **Enhanced Conversions (web + leads, unified)** | Improves measurement of conversions that already fire on your site (form submits, purchases), *and* sends conversion data for actions that happen after a lead form submission (a sales-qualified lead, a booked appointment, a closed deal) — both under one on/off setting, accepting data from website tags, Data Manager, and API connections. | Near-real-time for on-site conversions; days to weeks after the original click for post-submission lead outcomes, via the Google Ads UI, API, or a Google Sheets/CRM integration. |
| **Offline Conversion Import (OCI)** | Uploads a conversion that happened entirely offline (a phone call booked and closed by a human, an in-store visit, a signed contract) and ties it back to an ad click via a click identifier (GCLID/GBRAID/WBRAID) or a Google Click ID captured at the original visit. | Any time after the click, batch-uploaded via API, Sheets, or a CRM/partner integration. |

**(official, Google Ads Help, "About enhanced conversions for leads," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/15713840 — this page states: "Enhanced conversions
for web and leads are now combined into a single on/off setting. Starting from April 2026, Google
Ads accepts user-provided data from website tags, Data Manager, and API connections, and you will
no longer need to choose between different implementation methods." "About offline conversion
imports," retrieved 2026-09-27: https://support.google.com/google-ads/answer/2998031)**

**Correction (2026-09-27):** this file previously cited
`https://support.google.com/google-ads/answer/13258080` for "About enhanced conversions for
leads" and described Enhanced Conversions for Web and Enhanced Conversions for Leads as two
separate mechanisms with distinct implementations. That URL now returns HTTP 404 (confirmed on
repeated fetch attempts), and the current live page at the URL above states the two were merged
into a single setting starting April 2026 — so the old two-mechanism framing is no longer current
platform behavior, not merely an unreachable citation. Re-verify this page's content before
relying on the exact rollout date or mechanics if this file is read long after 2026-09-27, since
Google may adjust the implementation further.

**A remodeling GC's real funnel almost always depends on the post-submission conversion data (the
former "Enhanced Conversions for Leads" half of the now-unified setting) or OCI, not just the
on-site web conversion** — the value event (a signed contract, a booked job) happens well after
the form submit or call, once a human has actually qualified and closed the lead. Configuring only
the on-site half (because it's the first thing a setup guide covers) is a common gap: the campaign
continues to optimize against form-submits as if they were the real outcome, never learning which
submits actually turned into paid jobs.

## 2. Hashing requirements — never send raw PII

**[KB-MEAS-022]** All three mechanisms require customer data to be hashed with SHA-256 before it
reaches Google's servers. Google's own documentation is explicit about normalization *before*
hashing, because a hash of unnormalized data won't match a hash of normalized data on Google's side
even if the underlying value is the same person. **The following fields are confirmed on the live
page (re-fetched 2026-09-27):**

- Email: lowercase, remove leading/trailing whitespace. Gmail-specific: "remove all periods (.)
  that precede the domain name" for `gmail.com`/`googlemail.com` addresses only — do this
  normalization only for those two domains, not universally.
- Phone: E.164 format (`+` followed by country code and number, digits only — no spaces, dashes, or
  parentheses).

(official, Google Ads Help, "About enhanced conversions," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/9888656)

**Correction (2026-09-27):** this file previously also asserted, under the same citation, three
additional normalization sub-claims that are **not present on the cited page** (confirmed via two
independent fetches targeting them specifically): (a) removing anything after a `+` in the Gmail
local part, (b) name normalization ("lowercase, remove punctuation"), (c) truncating a U.S. postal
code to its first 5 digits. These are removed rather than restated as `UNVERIFIED`, since they were
checked directly against the primary source and found absent, not merely unreachable — asserting
them again with a hedge would still be publishing an unsupported claim. **If a name or postal-code
field is ever sent as part of an enhanced-conversions payload, re-derive its normalization rule from
the live page at the URL above (or Google's current developer reference for the enhanced
conversions API) at implementation time — do not assume the removed sub-claims above are correct
just because they sound plausible.**

**[KB-MEAS-023]** **Never send a raw, unhashed value as if it were hashed** — this is not a
theoretical risk, it is exactly the failure mode
[`ga4-event-design.md`](ga4-event-design.md) §3 warns against for GA4 parameters, applied to a
system where the destination is explicitly designed to accept only hashed input. A tag or script
that hashes client-side (or relies on Google Tag Manager's automatic hashing when using the Google
tag — GTM can be configured to "send unhashed data for Google to normalize and hash automatically,"
applying SHA-256 on Google's side before the data is matched, official, Google Ads Help, "Set up
enhanced conversions for web using Google Tag Manager," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/13262500) must be verified to actually be hashing —
not merely configured with the "enable enhanced conversions" toggle switched on, which some
implementations silently no-op if the underlying data layer variable is missing or malformed rather
than erroring loudly.

**Reject example:** a data layer that pushes `email: "chris@example.com"` into a variable named
`hashed_email` without ever calling a hash function — the field name lies about what it contains.
**Pass example:** the data layer computes `sha256(normalize(email))` before the enhanced-conversions
tag fires, and this is verified by inspecting the actual outbound request payload (via a network
inspector, never by trusting the configuration UI alone) shows a 64-character hex string, not a
plaintext address.

## 3. Consent is a prerequisite, not a parallel track

**[KB-MEAS-024]** Enhanced conversions and offline conversion imports both still require the
underlying consent signals from [`consent-mode.md`](consent-mode.md) to be correctly wired —
sending hashed PII does not exempt a property from consent requirements, because `ad_user_data`
governs whether user data may be sent to Google for advertising purposes at all, independent of
whether that data is hashed. A property with `ad_user_data` denied should not be sending enhanced
conversion data for that user regardless of hashing (official, Google for Developers, "Consent
Mode," retrieved 2026-09-27: https://developers.google.com/tag-platform/security/guides/consent).
Verify consent wiring before enabling either mechanism, not after.

## 4. Offline Conversion Import — the click-identifier requirement

**[KB-MEAS-025]** OCI requires a Google Click Identifier (GCLID for standard clicks, GBRAID/WBRAID
for iOS app-to-web and web conversion measurement under privacy-preserving attribution) captured at
the time of the original ad click and stored alongside the lead record, so the later offline
conversion upload can be matched back to the click that produced it (official, Google Ads Help,
"About offline conversion imports," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/2998031). **The practical implication for a CRM-based
lead flow:** the click identifier must be captured into a hidden form field (or URL parameter passed
through to the CRM) at the moment a lead form is submitted — a lead that arrives with no captured
GCLID/GBRAID/WBRAID cannot be matched to its originating click later, no matter how good the offline
conversion data is. Verify this capture mechanism exists and is actually populating on real
submissions (via the CRM's stored lead records, not just the form's client-side behavior) before
building any offline-conversion reporting on top of it.

**Reject example:** an offline conversion upload with a customer email/phone match key but no
GCLID, uploaded to a Google Ads account that has enhanced conversions configured to key
on the click ID — the match silently fails and the conversion is never attributed. **Pass example:**
the CRM lead record stores `gclid`, `lead_created_at`, and the eventual `deal_closed_at` /
`deal_value`, and the offline conversion upload sends the click identifier alongside the
conversion — verified by confirming in the Google Ads UI's conversion action detail view that
upload counts are non-zero and recently updated (the same signal named in
[`reconciliation.md`](reconciliation.md)'s 4-signal test).

## 5. Upload cadence and the lag this creates in reported ROAS

**[KB-MEAS-026]** Because the real-world qualifying/closing event for a remodeling GC's lead can
take weeks (site visit → estimate → decision → contract signing), any dashboard or report reading
"conversion value" or "ROAS" directly from Google Ads on a *recent* date range is reading an
incomplete number by construction — offline conversions for last week's clicks may not be uploaded
yet. **Correct behavior:** state the upload lag explicitly whenever reporting a recent-period ROAS
figure sourced from offline conversions (e.g. "figures for the last 14 days will rise as offline
conversions are uploaded; treat only 30+ day-old cohorts as settled") — see
[`reporting-and-dashboards.md`](reporting-and-dashboards.md) §2's minimum-sample and settling-window
discipline, which applies with extra force here since the lag is structural, not just a
statistical-noise question.

---

## Contractor bend

- This file's mechanism is the single highest-leverage measurement fix available to a remodeling
  GC's ad account, because their real sales cycle (estimate → contract) almost never completes at
  the moment of the ad click. Without it, Smart Bidding optimizes toward "got a form submit," not
  toward "got a signed $18,000 kitchen job" — those are not the same population, and a GC who has
  ever complained that "the leads are cheap but they're all tire-kickers" is very often describing
  exactly this gap.
- The GC will not have a GCLID-capturing CRM out of the box. This is a build task (a hidden form
  field, a CRM custom field, an export/import bridge) before any offline-conversion doctrine in this
  file can be used — say so plainly rather than assuming the plumbing exists.
- When explaining this to the GC, skip "enhanced conversions" and "GCLID" entirely and lead with the
  business outcome: "right now Google can only see that someone filled out your form — it has no
  idea which of those turned into an actual signed job. Once we wire this up, Google starts
  optimizing toward people who actually become paying customers, not just people who click."
