# Call Tracking

How phone-call measurement actually works for a business where the phone call, not the web form, is
often the primary conversion action — dynamic number insertion (DNI) mechanics, what a call-tracking
platform can and cannot tell you, and the consent/recording-disclosure obligations that are jurisdiction-
specific and easy to get structurally wrong.

---

## 1. Why call tracking exists as its own discipline

**[KB-MEAS-027]** A phone number printed once on a website, a GBP listing, and a printed flyer gives
no way to know which channel produced any given call. **Dynamic Number Insertion (DNI)** solves this
by serving a different tracking phone number to different visitor segments (by traffic source,
campaign, or even individual session) via JavaScript that swaps the displayed number based on how the
visitor arrived — the call-tracking platform then knows which source/campaign/keyword produced each
call because each one rang a distinctly-attributed number.

**[KB-MEAS-028]** This creates a structural conflict with local SEO: Google's own local-ranking
guidance is unambiguous that a business's Name, Address, Phone (NAP) must be **consistent** across
the website, Google Business Profile, and every citation/directory — DNI, by design, shows a
*different* number to different visitors than the one listed on GBP and directories. **Correct
mitigation, in order of preference:**
1. **Exclude the primary/static NAP number from DNI** — display the true business number in
   schema markup (`telephone` in `LocalBusiness` schema), the footer, and the GBP listing exactly as
   registered, and reserve DNI swapping for a *secondary* number shown only in ad-traffic-specific
   contexts (a specific landing page tied to a specific campaign) that never appears in citations.
2. Use a **static tracking number per major channel** (one number for organic, one for paid ads via
   Google Ads' own call reporting — see §2 — with GBP-sourced calls left on the true static NAP
   number, since GBP has no native call-tracking mechanism of its own, see §2) rather than a fully
   dynamic per-session number — coarser attribution, but the GBP-listed number stays genuinely static
   and citation-consistent.
3. If session-level DNI must be used site-wide, ensure the number search engines actually crawl and
   index (in schema, in any static/server-rendered HTML) is the true static number, and confirm this
   with the parity check from [`ANTI-PATTERNS.md`](../seo/ANTI-PATTERNS.md) §4's cloaking-adjacent
   guidance — the crawled version must match what a human visitor from organic search sees, never a
   DNI-swapped number shown only to paid-traffic sessions.

(Mechanism sourced from this corpus's own local-SEO NAP-consistency doctrine,
[`local-seo-for-contractors.md`](../seo/local-seo-for-contractors.md). Google's own Business Profile
guidelines require that a listed phone number "connect to your individual business location," must
be "under the direct control of the business," and should be "a local phone number instead of a
central call center helpline number whenever possible" (official, Google Business Profile Help,
"Guidelines for representing your business on Google," retrieved 2026-09-27:
https://support.google.com/business/answer/3038177) — this constrains what a GBP-listed number may
be, but the page does not name dynamic number insertion or call-tracking numbers specifically, nor
does it state a cross-platform (website/GBP/directory) consistency rule in those terms.
**UNVERIFIED — seeded, needs derivation: the DNI-vs-NAP conflict itself is a well-documented tension
in local-SEO practice, but no single official Google source was found naming DNI by name or a
directory/citation-consistency requirement verbatim; treat the conflict as real and the mitigation
below as the safe-default engineering answer, not as a quoted official policy.**)

## 2. Google's own native call tracking — the lowest-risk option, and where it no longer applies

**[KB-MEAS-029]** Google Ads' **call reporting** (used by call assets/call extensions, location
assets, and call-only ads) assigns a **Google forwarding number** to the ad — calls to it are
routed to the real business number while Google logs call duration, start time, and caller number
for attribution/bidding purposes (official, Google Ads Help, "About call reporting," retrieved
2026-09-27: https://support.google.com/google-ads/answer/2454052 — "When call reporting is turned
on, a Google forwarding number is assigned to your ad, enabling you to track details like call
duration, call start time, caller phone number"). Because this forwarding number is attached to the
**ad**, not the GBP listing's own displayed number, it does not create the NAP-consistency conflict
in §1.

**Google Business Profile's own call-forwarding/call-tracking feature was discontinued on July 31,
2024, and does not exist as a current mechanism** — as of that date, calls placed via a Business
Profile's Call button go directly to "the merchant's supplied phone number in Google Business
Profile," with no Google-provided tracking number in between (official, Google Business Profile
Help, "Changes to Google Business Profile chat and call history," retrieved 2026-09-27:
https://support.google.com/business/answer/14919056). **Do not configure for, or tell a client to
expect, GBP-native call attribution — it is not available.** For GBP-sourced call attribution today,
the only options are: (a) accept that GBP calls are unattributed by source (they call the true,
static NAP number, satisfying §1's consistency requirement by construction), or (b) use a
call-tracking platform's DNI number specifically on the GBP listing, which reintroduces the
NAP-consistency conflict §1 exists to avoid and should only be done with the mitigations in §1
applied.

Prefer Google Ads' native call reporting for ad-sourced calls before reaching for a third-party
DNI script on ad traffic; reserve third-party DNI for the website organic/direct
traffic-source-attribution use case, subject to §1's NAP-consistency mitigations.

## 3. What a call-tracking platform can verify — and what it can't

**[KB-MEAS-030]** `(internal doctrine)` A call-tracking platform's dashboard tells you a call happened, its duration, and
(via DNI) which source/campaign/keyword it's attributed to. **It does not, on its own, tell you
whether the call was a real lead, a wrong number, a spam/robocall, or a genuinely qualified
prospect who booked a job** — that requires either call recording review (with the consent
disclosure obligations in §4) or a human tagging outcome in the CRM. **A call-tracking number count
is not a lead count and must never be reported as one** without a stated qualification step —
mirroring [`ga4-event-design.md`](ga4-event-design.md)'s key-event discipline: a raw call count
inflates apparent lead volume the same way an unfiltered form-submit count does, and a GC who is
being told "you got 40 calls this month" when 15 were wrong numbers or spam will correctly conclude
the reporting is untrustworthy the first time they cross-check it against their own memory of real
jobs booked.

**Reject example:** reporting "call volume" as the funnel's primary conversion metric with no
qualified/unqualified split. **Pass example:** reporting qualified calls (a human or a recording
review confirmed genuine service inquiry) separately from total call volume, feeding only the
qualified count into [`metric-registry-doctrine.md`](metric-registry-doctrine.md)'s registered
lead metric.

## 4. Call recording and disclosure — a jurisdiction-specific legal requirement, not a platform setting

**[KB-MEAS-031]** Whether a call may be recorded, and whether the caller must be told it's being
recorded, is governed by **state (and in some cases federal) wiretapping/eavesdropping law in the
United States**, not by the call-tracking platform's own settings — enabling "call recording" in a
vendor's dashboard does not itself make recording legal in every state. The United States is split
between **one-party-consent** states (only one party to the call — e.g., the business — needs to
consent, so no disclosure to the caller is legally required) and **two-party/all-party-consent**
states (every party must consent, which in practice means a spoken disclosure — "this call may be
recorded for quality purposes" — must play before recording begins).

**UNVERIFIED (primary source unreachable: https://www.justia.com/50-state-surveys/recording-phone-calls-and-conversations/
— returned HTTP 403 on retrieval attempt 2026-09-27; this claim requires a live, state-by-state
legal citation against a primary regulatory or statutory source, which this attempt could not reach).**
A secondary legal-guide source (not a primary statute, and this corpus's own compliance-referral
convention below still applies) states its count as **eleven** two-party/all-party-consent states but
**names only ten verbatim** — California, Connecticut, Florida, Illinois, Maryland, Massachusetts,
Montana, New Hampshire, Pennsylvania, and Washington — a count/list mismatch present in the source
page itself (the eleventh state is never identified on the page); the source also separately notes
Illinois's two-party rule was struck down in 2014 and that Hawaii and Massachusetts have non-standard
variants (third-party, Digital Media Law Project, "Recording Phone Calls and Conversations," retrieved
2026-09-27: https://www.dmlp.org/legal-guide/recording-phone-calls-and-conversations — a legal-guide
summary, not a primary statute; the one-party/two-party consent framework itself is a widely-documented
feature of U.S. wiretapping law, but this specific state list — and even its stated count — must be
re-confirmed against a current primary legal source, e.g. the relevant state statute, before being
stated as fact to any specific company, and remains referred to the `compliance/` domain rather than
settled here per this file's own referral convention below).
**Correct behavior until verified:** default to playing an unambiguous recording
disclosure on every tracked line, regardless of the business's home state — this mirrors the
same "when uncertain which of two stricter regimes applies, the stricter one is the safe default"
posture already applied to multi-brand/same-owner risk in
[`local/gbp-optimization.md`](../local/gbp-optimization.md) §2 and its "Contractor bend" section,
ported generically here — and avoids the legal exposure entirely rather than requiring a
state-by-state determination before every deployment. Most call-tracking platforms (the vendor, not
this doctrine) offer a built-in recording-disclosure message specifically for this reason — enable
it by default and treat disabling it as requiring an explicit, cited legal basis for that specific
state, never a default.

**[KB-MEAS-032]** A remodeling GC operating in a single state, or a multi-location business
operating across state lines, has different exposure: a single-state business can (once verified)
rely on that state's specific rule; a multi-state business handling calls that could originate from
any state should treat every call as potentially subject to the stricter regime, since the caller's
location — not the business's — is often the relevant jurisdiction for consent-law purposes
(UNVERIFIED — seeded, needs derivation: this jurisdictional-nexus claim needs its own legal
verification before being stated as settled to a specific company; flag to the `compliance/` domain
per this corpus's own referral convention in [`consent-mode.md`](consent-mode.md) §4 rather than
asserting it here as legal advice).

## 5. Verifying a call-tracking implementation

1. The number displayed to organic/GBP-sourced visitors and listed in schema/citations is the true
   static NAP number (§1) — confirmed by comparing the rendered page's visible number and its
   `LocalBusiness` schema `telephone` field against the GBP listing.
2. DNI (where used) is scoped to paid/campaign-specific contexts only, never applied to the number
   shown to a citation-crawling bot or a GBP-referred visitor.
3. A recording disclosure plays on every tracked line by default (§4), unless a specific,
   currently-verified legal basis says otherwise for that jurisdiction.
4. The platform's call outcome (qualified/unqualified, or a CRM-recorded disposition) — not raw call
   count — is what feeds the registered lead metric (§3, [`metric-registry-doctrine.md`](metric-registry-doctrine.md)).
5. Call-sourced conversions that feed Google Ads (via a call-conversion import or Google's own call
   conversion tracking) pass the same 4-signal validation as any other conversion action
   ([`reconciliation.md`](reconciliation.md)).

---

## Contractor bend

- For a small owner-operated remodeling business, the phone is very often the *primary* lead channel, not a
  secondary one — many homeowners calling about a bathroom remodel or storm-damage repair want to
  talk to a person immediately, not fill out a form. Treating call tracking as an afterthought to
  web-form tracking (the more common default in a lot of generic marketing-agency setups) means the
  dominant conversion channel for this specific buyer type is the one most likely to be under-measured.
- The disclosure-message legal risk in §4 is exactly the kind of thing this buyer has no ability to
  evaluate themselves and no in-house legal counsel to ask — the safe-default posture (always
  disclose) exists specifically because this buyer would otherwise have no way to know they were
  exposed.
- When reporting call metrics to the GC, always show qualified calls, not raw call count — a GC
  reviewing "40 calls" against their own memory of "maybe 10 of those sounded like real jobs" is
  exactly the credibility-destroying mismatch described in §3.


## Field notes: phone menus and AI answering (added 2026-09-28)

- **[KB-MEAS-056] A press-a-key menu is the cheapest spam wall;** robocalls can't press keys. Route
  subcontractors with a hidden key, and send current clients to a queue so they don't hear an
  extension's greeting twice (internal doctrine, retrieved 2026-09-28).
- **[KB-MEAS-057] An AI answering agent behind a menu must never transfer to the main number;** it
  loops back into the menu. Transfer to a direct extension or direct-dial number (internal doctrine, retrieved 2026-09-28).
- **[KB-MEAS-058] Read a hosted phone system's real routing from its admin API, not the settings UI.**
  On one cloud phone system, the older answering-rule list returned empty and the call rules lived
  in a newer state-rules endpoint (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-MEAS-059] Recorded prompts:** use one synthetic voice across menu and agent where possible
  (a different voice at the hand-off sounds broken). Normalize loudness (about -16 LUFS in one observed setup, UNVERIFIED — seeded, needs derivation), and verify
  every clip with speech-to-text before upload (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
