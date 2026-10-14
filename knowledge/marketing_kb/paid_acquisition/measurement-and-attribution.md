# Measurement and Attribution — Honest Signal, Not Vanity Metrics

Internal practice mechanism (ported 2026-09), covering the 4-signal conversion-tracking test used
across both the Google Ads and Meta doctrine files and the 48-hour physical-verification rule. The
unifying principle: **never trust a media metric computed against a conversion signal that hasn't
been physically verified as actually firing.**

---

## Conversion-tracking architecture — how tracking should be WIRED, not just whether it fires

The 4-signal test below verifies a conversion signal can be TRUSTED once it exists. This section
covers how it should be ARCHITECTED in the first place — the wiring mistakes that make a signal
untrustworthy in a way the 4-signal test cannot detect, because all four signals can pass cleanly
on a mis-wired conversion.

**Sourcing note:** the double-count mechanism below is a practitioner-observed defect shape
((ported build-incident), dated where cited below) rather than a platform-capability claim — it
describes a wiring mistake a real integration can make, not something the Google Ads platform
itself does. The remaining mechanisms in this section are each tagged individually below, per this
corpus's own citation-style rule: enhanced conversions and offline conversion import cite the
official Google Ads Help pages, retrieved 2026-09-27; Consent Mode v2 defers to
`../measurement/consent-mode.md`'s own citations; GCLID/WBRAID/GBRAID cites the official Google Ads
Help page (answer/10417364, retrieved 2026-09-27); the UTM/auto-tagging interaction defers to
`../measurement/utm-standard.md` §4 `[KB-MEAS-036]`, which is sourced there — see "UTM conventions"
below.

### The double-count trap — one source per conversion action

**The same real conversion must be imported into Google Ads from exactly ONE source.** If a lead
or sale is counted as both a GA4-imported key event AND a native Google Ads conversion tag (or
both a browser-side tag and a server-side/offline import) landing on the same conversion action,
it is counted TWICE — inflating the conversion total, deflating the reported CPA, and corrupting
every downstream bid decision Smart Bidding makes on top of that signal.

- **The diagnostic most guides reach for — two conversion actions with near-identical counts and
  timestamps — will MISS the most common real-world shape of this defect.** The failure is not
  always two actions double-reporting; it is frequently **two different tracking SOURCES (e.g. a
  browser-side tag and a server-side offline import) both resolving to the SAME single conversion
  action**, deduplicated on different identifiers (a browser `transaction_id` vs. a server
  `order_id`) that don't actually match each other — so Google Ads' own dedup on `order_id` never
  catches it, because the two paths never sent matching order IDs in the first place. **Rule: one
  source per conversion action.** Before trusting a conversion count, trace every path that can
  write to that specific action (browser tag, GA4 import, offline/CRM import) and confirm exactly
  one is active, rather than trusting that two actions with different names implies no overlap. This
  is not hypothetical: exactly this shape — a browser-side tag and a server-side/offline import
  landing on the same conversion action with no shared identifier between the two paths — has been
  directly observed ((ported build-incident, 2026-09-19) — a sub-label of `UNVERIFIED`, see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md)'s opening note); the company-specific evidence lives in
  that company's own dossier, never here.

### Regulated-industry hard exception (applies to every mechanism in this file that uploads a conversion or hashed PII)

> **For any company whose pack declares a `regulated` classification (for example `hipaa`),
> enhanced conversions (any part of the unified setting, below), offline conversion import,
> Customer Match, and any hashed-PII upload of any kind are PROHIBITED until the compliance lane
> (`../compliance/hipaa-marketing-for-practices.md`, claim `[KB-COMPLIANCE-049]`) verifies the
> applicable rules and an operator card approves the specific mechanism.** On Google, Customer
> Match is not supported for sensitive-interest advertisers at all
> ([`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md), "Regulated-industry
> gate"), so no card unlocks it there; the compliance-plus-card path applies only to non-Google
> uploads. This exception covers
> Google-side conversion-upload mechanisms and hashed-PII specifically; it does not by itself cover
> Meta's own health-and-wellness advertiser restrictions on optimizing for lower-funnel events or on
> custom audiences — that separate restriction is covered by
> `../compliance/hipaa-marketing-for-practices.md`'s **`[KB-COMPLIANCE-054]`**, which the compliance
> lane holds as UNVERIFIED pending re-fetch of Meta's own (JS-rendered, currently unfetchable)
> Business Help Center pages. For a regulated company, every Meta audience, Pixel or CAPI item
> (including any event carrying even indirectly health-adjacent signal) is prohibited until the
> compliance lane (trust-architect for pixel/CAPI/form; the HIPAA content reviewer for content)
> verifies the specific use from Meta's own policy text; an operator card is additionally required
> only when the item is also one of the upload mechanisms this exception already card-gates (the
> governing plan §20.5.4 items) — the same rule stated in `competitor-targeting-doctrine.md` and
> `meta-ads-doctrine.md`. This exception is file-wide: it also governs the
> cost-per-booked-job feedback loop further below (a value-carrying `Lead`/booked-appointment event
> sent to Meta via CAPI, or an offline conversion import to Google Ads, both carry hashed PII and
> are covered by this same prohibition) — read every "feed real CRM outcomes back" instruction in
> this file as subject to this exception. Changes of this kind go through the regulated-industry
> compliance lane, with **trust-architect as reviewer of record for any tracking, pixel,
> conversion-upload, form, call-recording, chat, or booking-widget change**, and the HIPAA lane's
> content reviewer for content items (the governing plan's §20.5 assignment, restated in
> `../compliance/hipaa-marketing-for-practices.md`; the content-review seat named there,
> `local-presence-architect`, is planned, not yet built — until it exists every content-side HIPAA
> item is treated as prohibited, never routed to a substitute reviewer). This exception overrides the "configure it for every lead-gen conversion action"
> guidance below — read it as "every lead-gen conversion action on a non-regulated company"
> throughout this file. **Mechanism note:** `regulated` is a company-pack field — `list[string]`,
> optional, whose only valid value today is `"hipaa"` — defined in `tools/gtm/company_schema.json`
> and validated by `tools/gtm/company.py` (`VALID_REGULATED`). A pack author reads the field there;
> `../shared/company-pack-authoring.md`'s pack-field list does not yet document it, and that
> omission never means the field or this rule is absent.

### Enhanced conversions (a single unified setting, since April 2026)

**As of April 2026, Google merged the former "Enhanced Conversions for Web" and "Enhanced
Conversions for Leads" into one on/off setting** that improves measurement of conversions already
firing on your site (form submits, purchases) using hashed first-party identifiers (email, phone,
name/address) sent alongside the conversion hit — useful when third-party cookies are blocked,
consent is only partially granted, or the conversion happens in a different browser/device than the
click — **and** sends conversion data for outcomes that happen after a lead-form submission (a
sales-qualified lead, a booked appointment, a closed deal), accepting data from website tags, Data
Manager, and API connections, with no separate implementation choice between the two halves
(official, Google Ads Help "About enhanced conversions for leads," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/15713840). Full mechanism, setup steps, and the
2026-09-27 correction record for this file's own prior two-mechanism framing:
[`../measurement/enhanced-and-offline-conversions.md`](../measurement/enhanced-and-offline-conversions.md).

For a lead-gen account (subject to the regulated-industry exception above), this unified setting is
not optional polish — it is the mechanism that keeps conversion tracking working as the
browser/consent environment gets more restrictive. Configure it for every lead-gen conversion
action on a non-regulated company, not just checkout/purchase events.

### Offline conversion import — closing the loop from "lead" to "won"

**Capture the GCLID (or WBRAID/GBRAID for cross-app clicks) at the moment of form submission**,
store it against the CRM record alongside the lead, and later upload the real outcome (qualified,
booked, won) back to Google Ads once it is known — subject to the regulated-industry exception
above (official, Google Ads Help "About offline conversion imports," retrieved 2026-09-27:
https://support.google.com/google-ads/answer/2998031; full mechanism in
[`../measurement/enhanced-and-offline-conversions.md`](../measurement/enhanced-and-offline-conversions.md)).
This is the only mechanism that teaches Google's bidding algorithm which leads were actually GOOD,
not just which form submits happened — it is what turns this corpus's own cost-per-booked-job north
star (see below) from a reporting-only metric into a real bidding signal Smart Bidding can optimize
toward.

**API surface changed 2026-06-15 — uploads no longer go through the Google Ads API.** The same
official page states: "Starting June 15, 2026, offline conversions import and enhanced conversions
for leads uploads will be migrated to the Data Manager API and blocked in the Google Ads API"
(official, retrieved 2026-09-27, same URL as above). As of 2026-09-27 this migration is in effect:
a build that still targets the Google Ads API for this upload is targeting a blocked path. Route
offline conversion import and enhanced-conversions-for-leads uploads through the **Data Manager
API** (see also [`api-build-mechanics.md`](api-build-mechanics.md), "Conversion uploads are not
built through the Google Ads API"). This file is the corpus's statement of the migration until
`../measurement/enhanced-and-offline-conversions.md` carries it too.

### Consent Mode v2 — a hard-gated tag under-reports; it does not fail loudly

See [`../measurement/consent-mode.md`](../measurement/consent-mode.md) §3 for the full mechanism —
Consent Mode v2 is designed to MODEL conversions under denied consent rather than simply losing
them, and a hand-rolled hard `hasConsent()` gate with no modeled fallback defeats that silently: it
does not error, does not fail the 4-signal test on granted-consent sessions, and simply
under-reports on denied-consent sessions with no visible error state. Before reading any CPA or
conversion-rate number on an account with a consent banner, confirm which implementation pattern is
in place per that file's §4 audit checklist.

### GCLID / WBRAID / GBRAID capture

**GCLID (Google Click Identifier)** is the standard web-click attribution parameter. **WBRAID**
(introduced March 2021) attributes website conversions on iOS under Apple's App Tracking
Transparency restrictions, working alongside Google's conversion modeling. **GBRAID** (launched May
2021) is the equivalent parameter for app-deep-link conversions on iOS 14.5+, added to landing-page
URLs when auto-tagging is enabled (official, Google Ads Help "About GCLID, WBRAID, and GBRAID
identifiers," retrieved 2026-09-27: https://support.google.com/google-ads/answer/10417364). **The
page's own wording is narrower than "no GCLID for iOS 14" in general:** it limits the change to
iOS 14 ad traffic "coming from ads on a handful of Google apps," and states other Google traffic
sources are unaffected, per Apple's ATT policy, as of April 26, 2021 — do not generalize this to
all iOS 14 traffic across every Google surface. Capturing and storing the correct identifier at the
moment of the click/form-submit is the prerequisite for offline conversion import above — without
it, there is nothing to attribute the later "won" outcome back to.

### UTM conventions

Maintain one documented UTM taxonomy (source/medium/campaign/content/term) used consistently
across every channel this corpus covers. **For the UTM/auto-tagging interaction specifically, defer
to [`../measurement/utm-standard.md`](../measurement/utm-standard.md) §4, `[KB-MEAS-036]`, rather
than restating it here** — that claim is already sourced: `gclid` (Google Ads auto-tagging) and
manual UTM parameters serve different purposes and are not mutually exclusive, but stripping or
overriding `gclid` while adding manual UTMs breaks offline-conversion matching even though
UTM-based GA4 attribution keeps working. Use UTMs for cross-channel comparison in the analytics
platform; never let a click-tracking template or redirect drop the auto-tagged `gclid`.

## The 4-signal test: setup is not the same as tested

Installing a tag is SETUP. A conversion is TESTED only when all four of these are true:

1. **A live form submit (or its platform equivalent — a real phone call, a real booking) actually
   triggers the tag.**
2. **The analytics platform's real-time/debug view shows the event landing.**
3. **The ad platform's conversion action reads a real status** (not "no recent conversions," not a
   draft/unpublished state).
4. **The ad platform's own conversion column shows a non-zero, recently-updated value.**

All four, together, are what "tracking is verified" means. Any one missing means tracking is
UNVERIFIED, not "probably fine" — and no budget, bid, or optimization decision should be made
against unverified tracking data. This 4-signal procedure is a standing operating METHOD (ported
from a prior internal ads discipline, origin 2026-09, per this file's own opening line), not a
numeric or platform-behavioral claim, and so carries no `shared/citation-style.md` provenance tag;
the same test applies identically across both Google Ads and Meta in this corpus.

## The 48-hour physical-verification rule

**If NO counted, primary conversion has fired in the last 48 hours, the conversion counter is
untrustworthy — "broken" and "genuinely no demand" are indistinguishable from the number alone.**
Tracking must be physically tested and verified before ANY media metric (CPA, conversion rate,
budget-lost impression share, wasted spend) is trusted or any budget decision is made on top of it.

This is a real, standing rule, not a hypothetical caution: **a phone call that rings the wrong
extension still "fires" a conversion.** The tag firing correctly and the LEAD actually being real
and reachable are two separate questions — the 48-hour fire-check answers the first, not the
second. **The 48-hour window itself is a standing operator procedural rule, not a platform-sourced
figure** — it carries no citation-style.md tag because it is a verification METHOD this corpus
mandates, not a numeric claim about how a platform behaves; treat it as a fixed procedural
requirement of this corpus regardless.

**Verification is API-side/dashboard-side wherever possible** (checking the conversion action's
live status, the tag manager's tag/trigger state, the analytics platform's real-time hits) plus a
genuine physical test: the executor or operator (never this advisory seat, which never submits a
form or places a call on a live site) actually clicks the tracked phone number or submits the form
on the live site, and confirms the event lands in real time in the analytics debug view AND the ad
platform reads "recording conversions." Until that physical test has been done, report tracking as
VERIFIED-firing / UNVERIFIED with the evidence stated plainly — never a bare "tracking is fine."

## Judge conversion health only on COUNTED, PRIMARY actions

A conversion action that is not marked primary, or has `include_in_conversions_metric = false`, is
a secondary/supplementary signal. **A non-counted or deprecated action going silent is NOT a
tracking break** — do not report it as broken, and do not let it lower a tracking-health verdict.
Before judging tracking health at all, enumerate every conversion action with its status, category,
and whether it's counted — and state explicitly which actions were treated as the benchmark for
this judgment.

**The headline "conversions" total can be inflated by micro-conversions.** A page-view-based
engagement signal or a low-value micro-action can be marked as counted alongside real leads,
inflating the conversion column several-fold over the TRUE lead count. Identify the real lead basis
(a call, a form submit, a booking) and judge CPA, conversion rate, and budget decisions against
THAT number — always report the true lead count and the inflated total column as two separate,
explicitly labeled figures, never one blended number.

## Cross-platform reconciliation: what a real discrepancy looks like

When comparing the ad platform's own conversion count against an independent analytics source for
the same window:

| Variance | What it means |
|---|---|
| Under ~15% | Normal — attribution-model and window differences between platforms |
| ~15–30% | Worth investigating, not yet alarming |
| ~30–50% | A real problem — investigate before trusting either number |
| Over ~50% | Very likely a genuine tracking break — do NOT optimize until resolved |

**These variance bands (15% / 30% / 50%) carry no citation-style.md tag — they are an internal
operating heuristic ported from a prior internal ads discipline (origin 2026-09), not a
platform-documented or independently measured figure.** Per this file's own citation-style
discipline, an unsourced numeric threshold should be marked `UNVERIFIED — seeded, needs derivation`
rather than left untagged: **treat these three percentages as UNVERIFIED — seeded, needs
derivation**, useful as a starting heuristic for a first read of the data, not as a
platform-confirmed cutoff. The underlying structure (compare the ad platform's own count against an
independent analytics source; escalate scrutiny as variance grows) is domain-agnostic and portable
regardless of whether the exact percentages hold up under direct measurement.

## Cost-per-booked-job is the north star, never CPL/CTR/impressions alone

**Never report impressions or clicks as success.** Every metric this corpus's channels produce
should ultimately tie back to a real, sourced customer or job:

- **CPL (cost per lead)** is a useful diagnostic but is a VANITY number on its own — a cheap lead
  that never becomes a booked job is worse than a more expensive lead that does.
- **Cost-per-QUALIFIED-lead** is one level better — it accounts for the lead-form qualifier
  filtering out obvious non-fits.
- **Cost-per-booked-job** (fed back from the CRM/scheduling system, not the ad platform's own
  reporting) is the actual north-star metric across every paid channel this corpus covers. Feed
  real CRM outcomes back into the platform's conversion tracking wherever the platform supports it
  (offline conversion import for Google Ads, a value-carrying `Lead`/booked-appointment event for
  Meta) so the platform's own optimization signal improves over time, not just the reporting —
  **subject to the regulated-industry exception above**: both offline conversion import and a
  value-carrying Meta CAPI event carry hashed PII and are prohibited for a regulated company until
  the compliance lane clears the specific mechanism.
- **Marketing-cost-to-revenue** is the guardrail ratio worth tracking alongside cost-per-booked-job
  — it answers "is this channel sustainable at this spend level given the business's actual margin
  structure," which a raw CPL number never answers on its own.

## Attribution windows — know the default and its blind spots

- **Google Ads:** data-driven attribution is the default attribution model for most conversion
  actions ([Google Ads Help: About Data-Driven Attribution](https://support.google.com/google-ads/answer/6394265),
  official, re-fetched 2026-09-27 — that page states the current default plainly but does not give a
  rollout date for when DDA became the default; no rollout date is asserted here for that reason).
- **Meta:** the default attribution window as of January 2026 is **7-day click + 1-day view** —
  Meta removed the 7-day-view and 28-day-click/view options in that update (third-party, DataSlayer
  "Meta Ads Attribution Window Removed January 2026," retrieved 2026-09-05). **For a fast-decision
  service (an emergency repair), a shorter 1-day-click window may be more representative** — a fast
  decision argues for excluding both the 7-day click tail and the 1-day view-through component, not
  for keeping the 7-day click window alone (7-day-click only drops view-through; it does not shorten
  the click window itself). For a typical research-then-call remodeling decision, the platform
  default (7-day click + 1-day view) is reasonable.
- **Never compare Meta and Google "conversions" one-to-one.** The two platforms use materially
  different attribution models and windows — compare each channel to its OWN cost-per-booked-job
  trend over time, never to the other platform's raw conversion count (see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #17).
- **Use incremental/lift measurement periodically, not just last-touch, for a longer sales cycle.**
  Last-touch attribution systematically overstates ad credit for a remodeling decision that may
  span weeks of research across multiple channels and a referral conversation. A periodic (roughly
  quarterly) incrementality check is worth doing once volume supports it; it is not a launch-week
  concern.

## Anomaly detection — the questions to ask before trusting any performance read

Before drawing a conclusion from any performance data, scan for:

- **Sudden cost spikes or drops** — any day at more than 2x or less than 0.5x the trailing 7-day
  average needs an explanation (a budget change? a competitor entering the auction? a tracking
  outage?) before it's treated as signal. **(2x/0.5x thresholds: `UNVERIFIED — seeded, needs
  derivation`** — an internal operating heuristic ported from a prior internal ads discipline, no
  platform or independently-measured source; useful as a first-pass trigger, not a confirmed
  cutoff.)
- **Conversion-rate shifts greater than ~50% week over week** — is this a tracking issue, a
  landing-page change, or a real market shift? **(`UNVERIFIED — seeded, needs derivation`**, same
  basis as above.)
- **Zero-impression campaigns that should be serving** — check approval status, budget, bid, and
  targeting before assuming demand disappeared.
- **High spend with zero conversions over a meaningful window** (a threshold worth setting per
  account, not a universal dollar figure) — tracking broken, or targeting genuinely too broad?

Document what was found, the hypothesized cause (or "unknown — investigate"), the estimated
dollar impact, and the proposed action — never just report the anomaly and move on. **This
reporting discipline itself is a procedural method, not a numeric claim, and carries no
citation-style.md tag for the same reason the 4-signal test above does not.**

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A remodeling GC's "conversion" is a phone call or a form fill requesting an estimate — not a
  purchase.** Read the counted conversion definition (the north star) from the company's pack and
  dossier before building any tracking setup, and card the operator only if it is absent; a
  generic conversion-tracking guide's default assumptions (checkout completion, subscription
  signup) do not map cleanly onto this business model, and a naive setup will often miscount or
  undercount the actual lead-generation events that matter.
- **Cost-per-booked-job requires a real feedback loop from the GC's own scheduling/CRM process**,
  which is almost never automated for a small contractor operation. Be explicit that closing this
  loop — even a simple weekly manual reconciliation of "which leads from which channel actually
  became a signed job" — is where the real measurement value lives, far more than any dashboard
  the ad platform provides on its own.
- **A GC burned by a prior vendor will often have been shown only CTR, impressions, or raw lead
  count as "proof" the campaign worked.** Naming this pattern explicitly and reframing around
  cost-per-booked-job is itself a trust-rebuilding move — it signals this engagement is measuring
  what actually matters to the business, not what's easiest to report.
- **The 48-hour rule and the "wrong number" pattern (see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #8) compound for a GC whose call-forwarding setup changes
  often** — a new hire's cell phone reassigned as the tracked number, a vendor switch on the phone
  system, a temporary answering-service arrangement during a busy season. Treat "verify the actual
  live number" as a standing first-check whenever lead volume looks off, before assuming a media or
  targeting problem.
- **Segment measurement by job type where volume allows.** A GC's kitchen-remodel leads and
  small-repair leads can have wildly different close rates and job values; blending them into one
  cost-per-lead number hides which service line is actually the profitable one to keep funding.
