# GA4 Event Design

How to design a GA4 (Google Analytics 4) event taxonomy that answers real business decisions —
naming conventions, the recommended-vs-custom-event distinction, hard platform limits, and the
"track for decisions, not data" discipline that keeps an event schema from becoming write-only
noise nobody ever queries.

Attribution: sections marked "Adapted (MIT)" below adapt structure from
[coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)'s
`skills/analytics/SKILL.md`, MIT License, Copyright (c) 2025 Corey Haines. The source file states no
numeric thresholds and does not cover enhanced/offline conversions or call tracking — those sections
here are independently sourced from official platform documentation, not adapted from that repo.

---

## 1. Design backwards from the decision, not forward from "what can we track"

**[KB-MEAS-001]** GA4's own event model is built around three categories — **automatically collected
events** (fire with no configuration: `page_view`, `session_start`, `first_visit`, etc.),
**recommended events** (Google-predefined names with prescribed parameters for specific business
verticals: lead-gen, e-commerce, gaming), and **custom events** (anything else you define yourself).
Recommended events exist because they "require additional context to be meaningful" and are "not
sent automatically" — they must be deliberately implemented with the parameters Google expects
before the platform's own reports (funnel exploration, key-event attribution) can use them
(official, Google Analytics Help, "Recommended events," retrieved 2026-09-27:
https://support.google.com/analytics/answer/9267735).

**Adapted (MIT):** the governing question for every new event is *"what decision will this event
let someone make that they can't make today?"* — never *"what could we technically capture here."*
A tracking plan built by enumerating every clickable element on a page produces dozens of events
nobody ever queries; a tracking plan built by first listing the 5-10 real business decisions this
property needs to inform (is the estimate funnel leaking at step 3? which lead source produces
booked jobs, not just form-fills?) and then defining only the events that answer those questions
stays small, cheap to maintain, and actually gets used.

**[KB-MEAS-002]** Before adding any custom event, check whether a **recommended event** already
covers it. Google's four recommended-event categories as of the retrieved documentation: **All
properties** (14 events — `login`, `search`, `share`, `sign_up`, etc.), **Online sales** (14
e-commerce events — `add_to_cart`, `purchase`, `begin_checkout`, etc.), **Lead generation** (6
funnel-stage events), and **Games** (11 events) (official, Google Analytics Help, "Recommended
events," retrieved 2026-09-27: https://support.google.com/analytics/answer/9267735). A remodeling
contractor's estimate-request flow is a lead-generation funnel — check the lead-generation
recommended-event set and its prescribed parameters before inventing a custom `estimate_started` /
`estimate_submitted` pair that duplicates what `generate_lead` (or the specific lead-gen event set)
already models with better out-of-the-box reporting support.

## 2. Naming convention — Object-Action, lowercase, consistent

**[KB-MEAS-003] Adapted (MIT):** name events and parameters in `object_action` snake_case form —
lowercase words separated by underscores, describing the object acted upon then the action taken
(`estimate_submit`, `quote_download`, `phone_click`), never verb-first or mixed-case
(`SubmitEstimate`, `clickPhone`). Consistency matters more than any specific convention choice: a
schema that mixes `snake_case` custom events with `camelCase` ones, or that names the same
conceptual action two different ways in two different places (`form_submit` on one page,
`submit_form` on another), breaks every report and funnel exploration that tries to group by event
name. Document the convention once (a tracking plan, below) and hold every new event to it.

**[KB-MEAS-004]** GA4 enforces hard limits on event structure; a name or parameter over these limits
is silently truncated or the event fails to record as a key event, not rejected loudly:

| Limit | Value | Note |
|---|---|---|
| Event name length | 40 characters | A key-event-marked event over 40 characters loses its key-event status because the appended `_c` suffix no longer fits |
| Event parameters per event | 25 | |
| Event parameter name length | 40 characters | |
| Event parameter value length | 100 characters | `page_title`, `page_referrer`, and `page_location` have documented exceptions |
| User properties per property | 25 | |
| User property name length | 24 characters | |
| User property value length | 36 characters | |

(official, Google Analytics Help, "GA4 event collection limits," retrieved 2026-09-27:
https://support.google.com/analytics/answer/9267744)

**Pass example:** `estimate_submit` (15 chars) with parameters `service_type` (12 chars, value
`bathroom_remodel`, 17 chars), `lead_source` (11 chars, value `organic_search`, 14 chars) — well
inside every limit. **Reject example:** a custom event named
`homeowner_estimate_request_form_submission_completed` (53 characters) — over the 40-character cap;
if marked as a key event it silently stops reporting as one the moment the platform can't append
`_c`.

## 3. No PII in event or parameter values — ever

**[KB-MEAS-005] Adapted (MIT):** never send personally identifiable information (name, email,
phone number, physical address, or any value that on its own or combined with other parameters
identifies a specific person) as a GA4 event parameter or user property value. This is a strict
data-quality and platform-policy requirement, not a style preference — GA4's own terms of service
prohibit sending data that could be used to identify an individual. The correct place for a
first-party identifier used to reconcile a lead across systems is a **hashed** identifier passed
through the platform's purpose-built mechanism (Enhanced Conversions for the Google Ads side — see
[`enhanced-and-offline-conversions.md`](enhanced-and-offline-conversions.md) — never a raw email or
phone number sitting in a `lead_email` custom parameter visible in the GA4 UI to anyone with report
access.

**Reject example:** an event parameter `customer_phone` carrying the raw string
`(555) 123-4567`. **Pass example:** a parameter `lead_id` carrying an internal CRM-generated opaque
ID that means nothing outside your own system, used to join GA4 session data to the CRM record
server-side — the join happens in your own warehouse, not by putting PII into Google's platform.

## 4. Marking key events (conversions) — be deliberate, not exhaustive

**[KB-MEAS-006]** GA4 lets any event be marked as a "key event" (the current term for what was
called a "conversion" in the platform's own reporting before a March 2024 terminology update
(official, Google Analytics Help, "About key events," retrieved 2026-09-27:
https://support.google.com/analytics/answer/9267568) — verify the
current term against the live UI at setup time, since Google has renamed this concept before).
Marking every event as a key event defeats the purpose: key events are meant to isolate the small
set of actions that represent real business value (a submitted estimate request, a phone call
placed, a booked appointment), not every interaction on the site. See
[`metric-registry-doctrine.md`](metric-registry-doctrine.md) for why a bloated key-event list also
corrupts Smart Bidding once those events feed Google Ads as conversion actions — a low-value
micro-conversion marked as a key event competes for the bidding algorithm's optimization attention
against the real conversions that actually matter.

**Reject example:** marking `scroll_75_percent`, `outbound_click`, and `estimate_submit` all as key
events with equal weight — the bidding algorithm has no way to know `estimate_submit` is worth
orders of magnitude more than a scroll depth milestone. **Pass example:** only `estimate_submit`,
`phone_call_click` (with the call-tracking caveats in
[`call-tracking.md`](call-tracking.md)), and `booking_confirmed` marked as key events, each mapped
to a real dollar or pipeline-stage value where the business can estimate one.

## 5. The tracking plan document — the artifact, not just the implementation

**[KB-MEAS-007] Adapted (MIT):** maintain one tracking-plan document (a table, not scattered GTM
comments) listing every event: its name, trigger condition, parameters and their expected values,
which key events it feeds, and which real business decision it exists to inform. This is the
artifact a `gtm-container-governance.md`-scoped reviewer checks against before approving a new
tag/trigger — an event with no corresponding tracking-plan row, or a tracking-plan row with no
stated decision it informs, is itself a review finding (see
[`gtm-container-governance.md`](gtm-container-governance.md)).

## 6. Validation before calling any event "live"

**[KB-MEAS-008]** An event is not verified merely because it was configured — see the 4-signal test
in [`reconciliation.md`](reconciliation.md), ported from this corpus's paid-acquisition doctrine
(`paid_acquisition/measurement-and-attribution.md`), which applies identically to a GA4 custom
event: the trigger must actually fire on a real interaction, GA4's DebugView must show it landing
with the expected parameters, and (for anything feeding Google Ads) the conversion action must read
a real, non-zero, recently-updated status. Test on both desktop and mobile viewport/interaction
paths before calling a new event validated — a click handler bound to a desktop-only hover state is
a common way an event silently never fires for the majority-mobile traffic a home-services site
usually sees.

---

## Contractor bend

- A remodeling GC's website has one real conversion funnel that matters: visitor → estimate
  request → contacted → booked job. Every event in the tracking plan should trace back to a stage
  in that funnel or be cut — a contractor-facing GTM implementation with 40 custom events and three
  that anyone ever looks at is a maintenance cost with no offsetting value.
- Because the GC is very unlikely to have in-house analytics staff, the tracking plan document
  itself (§5) is the single most valuable deliverable of this doctrine for this buyer — it is what
  lets a future person (a new hire, a different agency, the GC themself) understand what's being
  measured and why, without reverse-engineering the GTM container.
- Phone calls are often the *primary* conversion action for this buyer, not a secondary one — see
  [`call-tracking.md`](call-tracking.md) before assuming form submits are the main signal worth
  designing events around.
