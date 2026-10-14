# TCPA & A2P 10DLC — consent, quiet hours, and SMS/call compliance

Company-agnostic doctrine. Governs every text message and outbound/autodialed call a GTM seat
drafts, schedules, or triggers — review-request texts, appointment reminders, lead follow-up SMS,
promotional blasts, and any call placed by an autodialer or using a prerecorded/artificial voice.
See [`can-spam.md`](can-spam.md) for the parallel (and legally distinct) regime governing email, and
[`privacy-and-consent.md`](privacy-and-consent.md) for the separate question of what consent is
needed to *collect and store* the phone number itself.

**Standing rule for this file:** every claim carries a stable id `[KB-COMPLIANCE-NNN]` per
`shared/citation-style.md`. This file's ids start at **024** to avoid colliding with the numbers
already in use elsewhere in this directory — see this file's own §6 note on the pre-existing
`KB-COMPLIANCE-001`–`017` numbering collision between `ftc-endorsements-and-fake-reviews.md` and
`hipaa-marketing-for-practices.md`, which has since been fixed by renumbering the HIPAA file's
claims to `043`–`059` (see `INDEX.md`'s "Known corpus defect" section for the full before/after).

---

## 1. TCPA — the federal floor for calls and texts

**[KB-COMPLIANCE-024]** The Telephone Consumer Protection Act (TCPA, 47 U.S.C. § 227) and its
implementing FCC regulations (47 CFR § 64.1200) require **prior express written consent** before
sending an autodialed or prerecorded/artificial-voice marketing text or call to a residential or
wireless number. "Written consent" under the FCC's rules must be a clear, unambiguous
authorization that (a) is in writing (including an electronic signature/checkbox with a clear
disclosure), (b) identifies the specific phone number being authorized, and (c) clearly and
conspicuously discloses that the consumer is agreeing to receive autodialed/prerecorded marketing
messages and is not required to consent as a condition of purchasing any good or service. **The
regulatory text itself (47 CFR § 64.1200) is confirmed** against the Cornell Legal Information
Institute mirror, https://www.law.cornell.edu/cfr/text/47/64.1200, retrieved 2026-09-27 — this is
the actual basis for this claim's content. **Correction (2026-09-27): the FCC Consumer Guide URL
this claim also cited (`https://www.fcc.gov/consumers/guides/stop-unwanted-robocalls-and-texts`)
returned HTTP 403 to a direct fetch at verification time and was not independently confirmed to
state this content** — it was previously labeled `(official)` with no unreachable flag,
inconsistent with this file's own handling of the ecfr.gov 403 case. **UNVERIFIED (primary source
unreachable: https://www.fcc.gov/consumers/guides/stop-unwanted-robocalls-and-texts)** as to the
FCC's own consumer-guide restatement specifically; the regulatory holding above rests on the
confirmed Cornell LII mirror of 47 CFR § 64.1200, not on the unreachable FCC guide page.

**[KB-COMPLIANCE-025] (internal doctrine, retrieved 2026-09-27) Doctrine recommendation, not an
independent regulatory holding —** treat
consent for **texts** and consent for **calls** as legally separate: do not assume consent to call
a number by itself authorizes texting it, or vice versa. A lead form or opt-in checkbox should say
which channel(s) it authorizes; a checkbox that only says "contact me about my estimate" is
ambiguous as to channel and this corpus's doctrine is to treat it as *not* authorizing
autodialed/prerecorded calls or texts until the wording is fixed to name the channel explicitly.
**Correction (2026-09-27): the cited FCC source (claim 024's 47 CFR § 64.1200 text, verified
directly against the Cornell LII mirror) does not itself state a channel-separateness rule** — its
consent-disclosure requirement is worded generally ("telemarketing calls using an automatic
telephone dialing system or an artificial or prerecorded voice") and does not explicitly
distinguish text-channel consent from call-channel consent as two separate authorizations. The
channel-separateness practice recommended here is this corpus's own conservative inference, not a
holding the regulation states — label it as a doctrine recommendation when stating it to a client,
not as a cited legal requirement, per [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) item 9.

**[KB-COMPLIANCE-026]** TCPA statutory damages are **$500 per violation**, trebled to **$1,500 per
violation** for a willful or knowing violation — and, as with CAN-SPAM (see
[`can-spam.md`](can-spam.md) [KB-COMPLIANCE-023]), "per violation" means **per message/call**, not
per campaign, which is what makes TCPA exposure scale directly and dangerously with list size.
TCPA claims are also frequently brought as class actions, which is the mechanism that turns a
single bad autodialed blast into a seven- or eight-figure exposure event. (official, 47 U.S.C. §
227(b)(3), text via Cornell LII mirror, retrieved 2026-09-27,
https://www.law.cornell.edu/uscode/text/47/227 — `uscode.house.gov`'s own hosted text was not
independently re-checked at retrieval time; treat as UNVERIFIED against the primary government
host specifically, though the Cornell mirror text is standard practice for citing this statute.)

**[KB-COMPLIANCE-027] Correction (2026-09-27), two issues fixed:** (1) the previously-cited URL
(`https://www.fcc.gov/document/fcc-affirms-consumers-can-revoke-consent-any-reasonable-way`)
returned HTTP 403 to a direct fetch at verification time and was never actually confirmed readable
— it was labeled `(official)` and "reachable at retrieval time" with no unreachable flag, which was
not correct; (2) the ruling was misdated and mischaracterized as a single "2023 ruling." The
"any reasonable means" revocation standard actually **originates from the FCC's 2015 Omnibus
Declaratory Ruling and Order** (30 FCC Rcd 7961, 2015), which first held that a consumer who gave
prior express consent may revoke it through any reasonable means. The FCC then, in a **February 15,
2024** Report and Order (FCC 24-24, docket CG 02-278), **codified** that pre-existing 2015 standard
into a formal rule and added specifics: callers/texters cannot designate an exclusive revocation
channel or exact keyword; for texts, a fixed list of standardized keywords ("stop," "quit," "end,"
"revoke," "opt out," "cancel," "unsubscribe") must be honored; a verbal revocation on a call, an
email, or a reply in any words that clearly convey a stop request must also be honored if that is
the reasonable method the consumer actually used; and revocation must be honored **within a
reasonable time, not to exceed 10 business days** — the same outer bound as CAN-SPAM's opt-out
window. A limited one-time confirmatory text in response to a revocation request is separately
permitted (effective April 4, 2024); the remaining 2024 rule changes were, as of the secondary
source below, stayed pending OMB review. (official: the 2015 origin and 2024 codification/dates
are corroborated by Manatt's TCPA Connect newsletter, a law-firm secondary source, retrieved
2026-09-27, https://www.manatt.com/insights/newsletters/tcpa-connect/fcc-adopts-revocation-rules —
the FCC's own primary order text, https://docs.fcc.gov/public/attachments/FCC-24-24A1.pdf, was
fetched but returned binary/non-extractable PDF content at retrieval time and could not be quoted
directly; **UNVERIFIED (primary source unreachable in readable form: FCC-24-24A1.pdf did not
extract as text; the consumer-guide URL previously cited also returned 403)** as to the primary
FCC order's exact wording — the substantive dates and "any reasonable means" holding above rest on
the corroborating secondary source, not on a directly-read primary FCC text.)

---

## 2. Quiet hours / permissible calling and texting windows

**[KB-COMPLIANCE-028]** The TCPA itself does not set a single federal quiet-hours clock by
statute; the FCC's telemarketing rules (47 CFR § 64.1200(c), enforced jointly with the FTC's
Telemarketing Sales Rule, 16 CFR Part 310) restrict **telemarketing calls** to the hours of
**8:00 a.m. to 9:00 p.m. local time at the called party's location**. This is the floor doctrine
treats as applying to any outbound marketing call or text absent a more specific, sourced state
rule (§2.1 below). (official, 47 CFR § 64.1200(c)(1) via Cornell LII mirror, retrieved 2026-09-27,
https://www.law.cornell.edu/cfr/text/47/64.1200 — the FTC's own Telemarketing Sales Rule
restatement of the same window is at https://www.ftc.gov/business-guidance/resources/complying-telemarketing-sales-rule, retrieved 2026-09-27, which corroborates the same 8am–9pm local-time
window from the enforcement side.)

**[KB-COMPLIANCE-029]** "Local time at the called party's location" means the recipient's time
zone, not the sender's — a nationally operating GTM seat sending a coordinated SMS blast must
either segment the send list by recipient time zone or use the most restrictive zone represented
in the list (the earliest 9:00 p.m. among all recipients) as the send cutoff, and the latest
8:00 a.m. as the send floor, unless the sending platform can genuinely time-zone-segment sends
per recipient. (official, same source as claim 028 — the "called party's location" language is
in the regulatory text itself.)

### 2.1 State-level quiet-hours and calling-window variations

**[KB-COMPLIANCE-030] UNVERIFIED (primary source unreachable per-state; no single federal
registry of state telemarketing-hour statutes was reached at retrieval time) —** several states
impose calling/texting windows narrower than the federal 8am–9pm floor, and a subset restrict
Sunday calling entirely; Florida's Telephone Solicitation Act and Oklahoma's telemarketing statute
are commonly cited examples of narrower state windows in third-party compliance-vendor summaries,
but this corpus was unable to independently retrieve and verify the current exact statutory hours
for any individual state's calling-window statute from that state's own official code site at
retrieval time (2026-09-27). **Doctrine until re-verified:** treat any multi-state or
nationwide SMS/call campaign as though the strictest known state floor could apply, and require a
state-by-state statutory check (each state's own official code/legislature site, not a
third-party vendor blog) before greenlighting a campaign that runs in a state not previously
verified in this file. This entire subsection is UNVERIFIED and must not be presented to an
operator or a client as a settled quiet-hours ruling for any specific state — it exists only to
flag that the federal floor is not automatically the tightest applicable rule.

**[KB-COMPLIANCE-031]** Regardless of the state-specific gap in claim 030, the **safe default
practice** this corpus recommends — narrower than the federal floor, and therefore compliant
with every state variant this corpus is aware of without needing per-state verification for every
campaign — is to restrict marketing calls/texts to **9:00 a.m.–8:00 p.m. recipient-local time,
Monday–Saturday, with no Sunday sends** unless a specific campaign has been individually
state-verified to permit Sunday contact in every state it targets. This is a doctrine
recommendation (a conservative operating default), not itself an independent regulatory citation —
label it as such when stating it to a client, distinct from the cited federal floor in claim 028.

---

## 3. A2P 10DLC — the carrier-network compliance layer (distinct from TCPA)

**[KB-COMPLIANCE-032] Correction (2026-09-27): the previously-cited primary source
(`https://www.campaignregistry.com/a2p-10dlc/`) is dead — verified via direct fetch, returns
HTTP 404 "Page not found."** Re-sourced below to a reachable page. Application-to-Person (A2P)
10DLC is **not a law** — it is a carrier (AT&T/T-Mobile/Verizon) registration and
throughput-governance system for text messages sent from a standard 10-digit long code number
using an application/platform (as opposed to a person manually texting from their own phone), with
The Campaign Registry ("TCR") serving as the registry/reputation authority for it. It sits on top
of, and does not replace, TCPA legal-consent requirements — a message can be fully TCR-registered
and A2P-compliant while still violating TCPA if the underlying consent was never obtained, and
conversely an unregistered or under-registered sender faces carrier consequences (claim 033)
independent of TCPA compliance. (official, Twilio's own A2P 10DLC compliance documentation,
retrieved 2026-09-27, https://www.twilio.com/docs/messaging/compliance/a2p-10dlc — "A2P
(Application-to-Person) 10DLC (10-digit long code) is the standard that United States telecom
carriers have put in place to ensure that SMS traffic to US end users through long code phone
numbers is verified and consensual"; a major registered CSP/reseller of the TCR system describing
how it works, in the same "operator/participant of the system describing the system" sense this
corpus treats as `(official)` for vendor/platform documentation. The Campaign Registry's own site
still exists at `https://www.campaignregistry.com/` and its PDF materials, e.g.
`https://www.campaignregistry.com/wp-content/uploads/TCR-Intro-2026-v4_comp.pdf`, corroborate TCR's
"Reputation Authority" role, but that PDF's text was not machine-extractable at retrieval time —
Twilio's page is the source actually relied on for this claim's specific wording.)

**[KB-COMPLIANCE-033]** Registration is two-layered: a **Brand** (the business entity sending
messages, verified against EIN/business registration data) registers once, then one or more
**Campaigns** (a specific use case — e.g. "customer care," "marketing," "mixed") register under
that brand, each providing information about how end users opt in, opt out, and receive help, plus
a description of the purpose of the messages sent. **Correction (2026-09-27):** the previously-cited
source for this claim is dead (see claim 032); re-verified directly against Twilio's own A2P 10DLC
documentation (https://www.twilio.com/docs/messaging/compliance/a2p-10dlc, retrieved 2026-09-27),
which confirms the Brand/Campaign structure and the opt-in/opt-out/help-info declaration, but does
**not** use or confirm the specific terms "sample message copy," "carrier-level filtering," or
"outright blocking" — the reachable source states only that registering "results in lower message
filtering and higher messaging throughput" and that unregistered senders "receive additional
carrier fees for sending unregistered traffic." Doctrine until a stronger primary source is found:
treat under-registration as carrying real throughput/cost consequences (confirmed) and possible
filtering (implied by the "lower filtering" framing of registration), but do not state to a client
that under-registration causes "outright blocking" or that Campaigns must declare literal "sample
message copy" — neither is confirmed by the currently reachable source. (official, Twilio's A2P
10DLC documentation, retrieved 2026-09-27, as above.)

**[KB-COMPLIANCE-034]** Carrier throughput limits scale with **Brand trust score** — a low-trust or
unverified Brand is capped at a lower daily message volume than a fully-vetted one, meaning a
large, well-consented send list can still fail to deliver on time if the underlying Brand
registration is thin. This is an operational (deliverability) consequence, not a legal-penalty one,
but it is exactly the kind of "boring infrastructure" failure that makes a technically-compliant
campaign fail in practice — flag Brand/Campaign registration status as a pre-send checklist item
independent of the TCPA consent check. **Correction (2026-09-27):** the previously-cited source is
dead (see claim 032); re-verified directly against Twilio's A2P 10DLC documentation
(https://www.twilio.com/docs/messaging/compliance/a2p-10dlc, retrieved 2026-09-27), which does
confirm Trust-Score-scaled throughput in these terms — "From 2,000 and up to unlimited SMS
segments and MMS per day to T-Mobile, depending on your Trust Score" — and confirms different
Brand registration types (e.g. Sole Proprietor, Low-Volume Standard, Standard) carry distinct
daily volume caps. It does **not** use the term "Campaign vetting tier" — that framing is this
corpus's own generalization and is removed here rather than attributed to the source. Specific
numeric throughput tiers change periodically by carrier policy and are not restated here as a
fixed table; re-verify against the live Twilio/TCR documentation before quoting a specific number
in a client-facing proposal. (official, Twilio's A2P 10DLC documentation, retrieved 2026-09-27, as
above.)

**[KB-COMPLIANCE-035]** A2P 10DLC Campaign registration requires describing how end users opt in,
opt out, and receive help (e.g., "web form with checkbox," "keyword opt-in via text," "verbal
consent captured in CRM"). This declaration must match reality — declaring an opt-in method the
business doesn't actually use, to obtain a more favorable classification, is itself a
Campaign-registration integrity risk independent of any TCPA exposure, and this corpus treats
mismatched opt-in declarations as a hard anti-pattern (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md)).
**Correction (2026-09-27):** the previously-cited source is dead (see claim 032); re-verified
directly against Twilio's A2P 10DLC documentation
(https://www.twilio.com/docs/messaging/compliance/a2p-10dlc, retrieved 2026-09-27), which confirms
that Campaign registration requires "information about how end users can opt-in, opt-out, and
receive help" and a description of message purpose — it does not use the term "vetting tier" in
connection with this declaration (see claim 034's correction), so that framing is removed. (official,
Twilio's A2P 10DLC documentation, retrieved 2026-09-27, as above.)

---

## 4. Working checklist before any SMS/voice campaign sends

1. Does every recipient have **written consent specific to the SMS/call channel being used** (not
   just "contact me" ambiguity — see claim 025)?
2. Is the send window restricted to the doctrine default in claim 031 (9am–8pm recipient-local,
   Mon–Sat, no Sunday) unless every targeted state has been individually verified to permit a wider
   window?
3. Does the send list exclude every number that has revoked consent by **any** reasonable means
   (not just an exact "STOP" keyword match — see claim 027), and is the revocation honored within
   10 business days?
4. Is the sending Brand/Campaign actually registered with TCR for the content type being sent
   (marketing vs. customer-care), and does the registered opt-in method match what was actually
   used to collect consent (claim 035)?
5. For a nationwide or multi-state list: has this specific state combination been checked against
   claim 030's UNVERIFIED gap, or is the send restricted to the conservative default in claim 031?

---

## 5. Contractor bend

A small owner-operated home-services/trade business's SMS use is almost always one of three things: appointment/estimate reminders,
review-request texts after job completion, or a lead-follow-up sequence from a CRM. The single
most common real-world failure mode for this buyer isn't a malicious blast — it's a **CRM or
scheduling tool that auto-texts on a trigger (job status change, invoice sent) without the office
ever having captured explicit SMS consent from that specific customer**, because the tool made
texting the path of least resistance and nobody checked the box was ever presented. Before this
seat recommends or configures any auto-texting workflow: (a) confirm the intake form or
contract the customer actually signed contains SMS-specific consent language naming the number,
not just an email field; (b) confirm the CRM/scheduling tool used is itself TCR-registered under
this business's own Brand (a shared or improperly-registered sending number used across multiple
of one owner's businesses — see the company's own pack/dossier for any standing
cross-connection/entity-isolation rule that owner has adopted — is both a TCPA
attribution risk and an A2P registration-integrity risk, since claim 033's Brand/Campaign
declarations are meant to describe one real business, not several sharing infrastructure); (c)
default every send to the conservative claim-031 window rather than assuming a single national
default is safe. Lead with "this protects you from a lawsuit that can cost more than your whole
year's marketing budget, and it's a one-time setup" — this buyer will act on stakes framed in
dollars and one-time effort, not on the statutory mechanics.

---

## 6. Known corpus defect this file does not fix — FIXED, see INDEX.md

This file's claim ids intentionally start at 024, not 013, because
`ftc-endorsements-and-fake-reviews.md` already uses `[KB-COMPLIANCE-001]` through `[KB-COMPLIANCE-012]`
and `review-gating.md` uses `013`–`018`. `hipaa-marketing-for-practices.md` previously,
independently, and collidingly numbered its own claims `[KB-COMPLIANCE-001]` through
`[KB-COMPLIANCE-017]` in the same id space — this has since been fixed by renumbering that file's
claims to `043`–`059`; see [`INDEX.md`](INDEX.md)'s "Known corpus defect" section for the full
before/after. This file's own `024`–`035` range never collided and is unchanged.
