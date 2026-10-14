# Paid-Destination Doctrine

Added 2026-09-19. What changes when a surface this seat reviews is about to receive AD TRAFFIC
rather than only organic/referral traffic. House style: every numeric/behavioral claim is tagged
`(official)` / `(third-party)` / `(internal-measured)` / `(internal doctrine)` with a retrieval
date — see `INDEX.md`.

## 1. The destination is not a fixed address (Google Ads AI Max / Final URL expansion)

In Google Ads AI Max for Search, **Final URL expansion** lets Google route a click to any page on
the domain it judges more relevant to the query — overriding the campaign-specified final URL.
Final URL expansion is turned **on by default** when AI Max settings are opted into. **Text
customization must be enabled to use it** — turning Text customization off also turns off Final
URL expansion. Google also documents **URL exclusions** (exclude specific URLs from ever receiving
expanded traffic) and **URL inclusions** (constrain expansion to a named set of URLs).
(official, Google Ads Help 16230205, "About Final URL expansion in Search," retrieved 2026-09-19)

**Duty:**
1. Before certifying any landing-page finding as applying to "the page traffic lands on," verify
   whether AI Max / Final URL expansion is active on the account. The page reviewed is not
   necessarily the page a real click reaches.
2. Prescribe URL exclusions for every public page that must never receive ad traffic — blog posts,
   comparison pages, `/features`, terms/privacy — and URL inclusions to constrain expansion to the
   intended offer page. This is destination governance and is in this seat's lane; campaign
   structure and bidding decisions remain paid-acquisition-strategist's call.
3. Read the account's landing-page report (not this seat's own crawl) to see which URLs actually
   received traffic before concluding a finding was reached by real visitors.

Whether expansion measurably *hurts* a single-offer lead-gen page is practitioner opinion from
third-party SEO-vendor content, not an official or measured finding (third-party, adnabu.com /
adalign.io, retrieved 2026-09-19) — state it as directional if raised at all; the verify-and-govern
duty above stands on the official doc alone and does not need that claim to be true.

## 2. Pricing disclosure is a hard gate on every paid destination

Google enforces a **Dishonest Pricing Practices** section of the Misrepresentation policy
(enforcement began 2025-10-28, ramping over roughly four weeks). It prohibits "failure to clearly
and conspicuously disclose the payment model or full expense that a user will bear before and
after purchase," requires disclosure of recurring costs and billing interval for
subscriptions/memberships, bans making cost information hard to find "by using similar or
identical text and background colors, very small fonts, or other page elements that block this
information visually," and bans promoting a free trial without stating the trial period and the
automatic charge that follows. A warning is issued at least 7 days before any account suspension.
(official, Google Ads Policy Help 15938375 + 6020955, retrieved 2026-09-19; the 2025-10-28
enforcement date is third-party-corroborated — kliken.com, seroundtable.com, retrieved
2026-09-19 — the official policy page itself states no date, so always cite the date to the
third-party source, never to Google)

**Duty — a hard pass/reject gate on every paid destination:** verify the recurring amount, billing
interval, the fact the card is charged immediately (not after a trial, where that's the model),
and any money-back terms are all present in body-copy contrast and size, above or at the
card-entry step — never only in a footer, a terms link, or a modal. Reject any destination where
the recurring charge is discoverable only after a click.

This supports, never reopens, a locked pricing model — the gate is about disclosure *placement*,
never about the price or the model itself. It converges with this corpus's existing buyer-anxiety
placement rule (`forms-and-signup-friction.md`) but is independently mandatory: a page can pass
the anxiety test and still risk ad disapproval.

## 3. Landing page experience is a Quality Score component — findings on a paid destination have a
media-cost consequence

Landing page experience is one of three Quality Score components alongside expected clickthrough
rate and ad relevance (official, Google Ads Help 6167130, retrieved 2026-09-19). **Google
publishes no component weights** — confirmed directly against the official page, which states only
that the components help decide whether to update ad text, keywords, or landing page content. Any
percentage split (e.g. a commonly-cited ~39/39/22 estimate) is third-party reverse-engineering
(Adalysis, across large account samples, retrieved 2026-09-19) and must be cited as such, never as
Google's own figure. Practitioner analyses report materially higher CPCs on below-average landing
page ratings (third-party, groas.com, directional only, retrieved 2026-09-19).

This seat's paid-acquisition-doctrine peer already carries the account-side Quality Score
thresholds and gates — see `paid_acquisition/account-audit-rubric.md` (QS 1-3/4-6/7+ bands),
`paid_acquisition/learning-period-gates.md` ("Quality Score is not real-time"),
`paid_acquisition/grade-a-gates.md`, and `paid_acquisition/ANTI-PATTERNS.md`. This section does not
restate that doctrine — it exists so this seat applies the consequence, not so it re-derives the
mechanism.

**Duty:** when a finding is on a paid destination, state the media-cost consequence alongside the
conversion consequence — a friction finding there is not only a lost signup, it raises the price of
every future click. This changes prioritization: on a paid destination, a fix that raises landing
page experience compounds against spend and outranks an equal-sized conversion fix on an
organic-only page. Never estimate a specific Quality Score number (unknowable from outside the
account) — name the component being harmed, name the direction, hand account-side measurement to
paid-acquisition-strategist.

## 4. Meta: the destination is a choice, not a default

On Meta, the destination is a choice between a hosted landing page and an in-platform **Instant
Form** that prefills from the user's profile. Meta reports advertisers running both saw an average
60% lower cost per lead and 125% increase in lead volume versus website-form campaigns alone
(official, Meta for Business, retrieved 2026-09-19).

Choosing the destination type is paid-acquisition-strategist's call — full doctrine lives in
`paid_acquisition/meta-ads-doctrine.md` §7 (qualifier-question and sub-5-minute-response
prerequisites already specified there; do not re-derive it here).

**Duty:** when the stated goal is activation/feedback volume rather than revenue conversion,
surface the Instant Form option explicitly rather than silently defaulting to page-only review,
then review whichever destination is actually chosen. Under a card-required signup model, an
Instant Form can only ever capture a lead, never a paid activation — say that plainly and never
present it as a like-for-like substitute for the signup page.

## 5. Speed is a Core Web Vitals question with a paid-destination consequence

Thresholds, p75 methodology, measurement tooling, and the contractor (mobile-first, job-site)
bend live in `seo/web-vitals-thresholds.md` — read them there, never restate the numbers here.
`paid_acquisition/grade-a-gates.md` carries the same thresholds as an account-side gate.

**Duty:**
1. On a paid destination, speed is both a conversion variable and an input to the landing page
   experience Quality Score component (§3) — a slow ad destination is charged for twice.
2. Measure the device mix the destination's real traffic actually uses, and never certify landing
   page speed on desktop alone when the paid traffic driving it is mobile-majority. For companies
   selling to trade-business owners specifically, whose buyers are on phones on job sites over
   weak connections, the **mobile** p75 figure is the only one that matters — a desktop-only speed
   check on that funnel is not evidence.
3. Measure before prescribing; never assert a page is slow without a measurement and its retrieval
   date.

A widely-circulated claim that Google tightened LCP to 2.0s in a March 2026 core update does
**not** hold — verified directly against the official source on 2026-09-19: web.dev/articles/vitals
still specifies LCP 2.5s / INP 200ms / CLS 0.1 (INP replaced FID as a stable vital in 2024). The
2.0s figure traces to third-party content (digitalapplied.com) — do not let it re-enter this
corpus.

## 6. Measurement must exist before a finding is trusted — the launch-night prerequisite

Before certifying any surface as an ad destination, verify the measurement chain exists — without
it, none of this seat's own findings can ever be falsified.

1. **Conversion tags actually fire** on the real signup-success event. A tag container with unset
   measurement IDs is a container, not measurement.
2. **Click-ID persistence:** GCLID/WBRAID/GBRAID (Google) and `fbclid` (Meta) must survive the
   landing→signup navigation. A page that drops query parameters on an internal redirect silently
   destroys attribution — this is a page-side defect squarely in this seat's own lane, the one item
   of the four this seat can both detect and prescribe a fix for.
3. **Server-side pairing:** browser pixel and Conversions API deduplicated on a shared `event_id`.
   Doctrine already exists at `paid_acquisition/meta-ads-doctrine.md` — cross-reference it, don't
   restate it.
4. **Consent:** for EEA/UK traffic, Consent Mode v2 requires four parameters — `ad_storage`,
   `analytics_storage`, `ad_user_data`, `ad_personalization`. A banner setting only the first two
   is a v1 implementation that fails v2 silently (third-party, consent-platform vendor content,
   retrieved 2026-09-19 — re-verify against Google's own Consent Mode documentation before treating
   as official).

**Duty:** if conversion tracking is not verified live, say so as `bounded: false` at the top of the
response and label every downstream conversion claim a hypothesis. On a launch night this is the
first check, not the last.
