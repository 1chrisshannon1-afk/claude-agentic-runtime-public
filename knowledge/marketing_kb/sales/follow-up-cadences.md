# Follow-Up Cadences

A follow-up cadence is the planned sequence of touches — channel, timing, and message intent — that
carries a lead from first contact to a legitimate "won," "lost," or "archived" outcome. Most
inbound leads that eventually convert do not convert on the first touch; a cadence exists because a
single missed callback or one unanswered voicemail is not evidence a lead is dead.

## 1. How many touches, over what timeframe

**[KB-SALES-017]** A commonly cited benchmark from sales-process research holds that it takes an
average of somewhere in the **6–8 touch** range to generate a viable sales conversation with a new
prospect, and that the majority of sales are not closed until after **5 or more follow-up contacts**
after the initial meeting or inquiry (third-party, widely aggregated across sales-methodology
sources — most commonly traced to Marketing Donut / Invesp-lineage "average touches to close"
roundups; retrieved 2026-09-27 — **UNVERIFIED (primary source unreachable: no single primary study
with a disclosed methodology was independently located for the specific "6–8 touches" / "80% of
sales require 5+ follow-ups" figures; every reachable source is a secondary marketing blog restating
the number without attribution to a citable original dataset)**. Treat the *mechanism* — most
conversions require persistence well beyond a single follow-up, and most reps give up too early — as
robust and consistent across the literature; treat any specific touch-count figure as illustrative,
not a target to hit mechanically regardless of context.

**[KB-SALES-018]** The commonly repeated companion claim — that a large majority of sales reps give
up after one to two follow-up attempts while most sales require more — traces to the same
unattributable secondary-source lineage as [KB-SALES-017]. **UNVERIFIED (primary source
unreachable)** for the exact percentage; cite only as directional evidence that under-persistence,
not over-persistence, is the more common and more costly failure mode in practice.

## 2. Channel mix and spacing — the mechanism, not a fixed script

**[KB-SALES-019]** No single primary, citable study was located during this research pass that
prescribes an exact optimal spacing (e.g., "day 1, day 3, day 7") or exact channel order (call vs.
email vs. SMS) as a universal law. **UNVERIFIED — the specific day-by-day cadence structures
commonly published by CRM/sales-engagement vendors (Salesloft, Outreach, HubSpot blog content) are
third-party vendor-authored guidance reflecting what their own product templates encourage, not
independently validated research; treat any specific cadence template as a reasonable starting
structure to adapt, not a proven-optimal sequence.** The mechanism that *is* well-supported by the
speed-to-lead evidence (`speed-to-lead.md`) and general sales-process literature:
1. **Front-load speed and volume of attempts in the first 24–48 hours**, then decelerate.
   Multiple touch attempts on day one (a call, a text, an email if no answer) reflects the same
   decay-is-front-loaded logic as speed-to-lead — a lead's willingness to engage falls off fastest
   immediately after they inquired, not evenly over weeks.
2. **Vary the channel across the sequence, don't repeat the same one.** A prospect who doesn't
   answer three consecutive phone calls is not necessarily unreachable — they may screen calls but
   read texts, or vice versa. Cycling channel (call → text → email → call) tests reachability more
   efficiently than repeating the channel that already failed.
3. **Extend the interval as the sequence progresses.** Same-day-to-next-day spacing early, widening
   to multi-day and then multi-week spacing later in the sequence, mirrors how urgency and recency
   naturally decay — this is a structural pattern reported consistently across vendor cadence
   templates even where the exact day-counts are unverified.
4. **Define a real "cadence exhausted" endpoint.** A lead is not legitimately "dead" after one
   unanswered call; it also should not be pursued indefinitely with no defined stop. A cadence that
   never ends is functionally the same as harassment risk (see `ANTI-PATTERNS.md`) and provides no
   clean signal for when to move a lead to `reactivation.md`'s longer-horizon nurture track instead.

## 3. Compliance boundaries on channel and timing choices

**[KB-SALES-020]** **UNVERIFIED (primary source unreachable: https://www.fcc.gov/general/telemarketing-and-robocalls
— returns HTTP 403 to automated fetches, confirmed by two independent tools on 2026-09-27; not
confirmed as removed or changed, only as unreachable from here right now).** **TCPA (Telephone
Consumer Protection Act)** governs autodialed/prerecorded calls and text messages to a cell phone.
Under the FCC's framework as commonly summarized by secondary compliance sources, sending a
marketing text or placing an autodialed/prerecorded marketing call to a wireless number generally
requires the recipient's **prior express written consent** obtained before the message is sent —
this is understood to be a materially higher bar than CAN-SPAM's opt-out-only regime for email, but
the exact statutory/regulatory text has not been directly re-verified against the primary source
above and should be re-checked there (or at the underlying rule, 47 CFR § 64.1200) before this
claim is relied on for a specific compliance decision. **A cadence's SMS/call-blast steps must
never be designed as if TCPA consent were implied by a form submission alone** — the specific consent
language, checkbox design, and disclosure requirements for valid prior express written consent are
owned by [`../compliance/tcpa-a2p-10dlc.md`](../compliance/tcpa-a2p-10dlc.md) — consult that file
directly for the exact consent-checkbox language, revocation-handling mechanics, and A2P 10DLC
registration requirements for business SMS before designing a specific cadence step; this file
restates only that every SMS-in-a-cadence recommendation requires documented consent capture and a
working STOP/opt-out path at minimum, and anything beyond that minimum escalates to compliance review
rather than improvising.

**[KB-SALES-021]** **CAN-SPAM** governs the email steps of any cadence. Full doctrine, the five
required elements, and the per-email penalty exposure are owned by
[`../compliance/can-spam.md`](../compliance/can-spam.md) — restated here only to the depth this
domain needs: every email touch in a cadence needs accurate headers, a non-deceptive subject line,
clear commercial identification, a valid physical address, and a working one-step opt-out, and the
opt-out must actually suppress the address from every later step in the same and future cadences,
not just the one email it was clicked from. **Reject pattern specific to cadences:** a lead who
opts out of email step 3 of a 6-step cadence still receiving email step 5 because the suppression
list wasn't checked again before that later send — see `can-spam.md` §4's working checklist, which
applies at every send, not only the first.

**[KB-SALES-022]** **Do Not Call Registry** — a business's own established-business-relationship
exemptions to the National Do Not Call Registry are narrower and more time-limited than commonly
assumed, and calling a number on the Registry outside a valid exemption carries its own FTC/FCC
penalty exposure separate from TCPA's autodialer-specific rules (official, FTC National Do Not Call
Registry for businesses, retrieved 2026-09-27, https://www.ftc.gov/business-guidance/do-not-call).
**UNVERIFIED at the depth needed to state the exact exemption window** (commonly cited as 18 months
from a prior transaction and 3 months from a prior inquiry, but this exact figure was not
independently re-confirmed against the primary FTC text during this pass) — treat any cadence
recommendation involving a cold or aged lead's phone number as needing a live compliance check
against the current Registry rules, not an assumption that an old inquiry still qualifies as an
active relationship.

## 4. What a sales-ops agent actually designs

**[KB-SALES-023]** `(internal doctrine)` A cadence design should specify, for every step: channel, target timing offset
from the trigger event, message intent (not just "follow up" — what question or offer does this
specific touch make), and the compliance gate that applies to that channel (§3 above). A cadence
with no defined endpoint, no compliance gate named per channel, or a message intent of "just
checking in" repeated at every step is under-designed.

**Pass example:** A cadence for an unresponded estimate lead: Day 0 (event: lead submitted) — instant
automated SMS ack with consent already captured at form submission + human call attempt within the
SLA window. Day 1 — second call attempt, different time of day. Day 2 — email (CAN-SPAM compliant,
one-step opt-out) referencing the specific project type they inquired about, not generic. Day 5 —
text (only if SMS consent on file) with a specific, low-friction offer ("Want me to just text you a
ballpark range instead of a call?"). Day 12 — final email in the active sequence, explicitly stating
this is the last active-cadence touch and inviting them to reach back out anytime; lead then moves to
`reactivation.md`'s longer-horizon track, not deleted.

**Reject example:** The same lead gets a phone call every single day for three weeks with no email
or text variation, no defined stop, and no compliance check on whether the number is Registry-listed
or whether repeated same-channel contact after no response for this long starts to look like
harassment rather than diligence.

## Contractor bend

A residential GC's follow-up capacity is bounded by the same one-person-doing-everything reality as
`speed-to-lead.md`'s bend: a 6–8 touch cadence sounds like a call-center operation, but the
mechanism translates fine to a small operation if the *tooling* automates the timing and channel
cycling while the *human* touches (the actual calls) stay realistic in volume — 2–3 real human call
attempts plus automated text/email fill-ins is a legitimate implementation of the same principle,
not a watered-down version of it. The single most common failure this bend exists to prevent: an
owner who mentally treats "I called them once and they didn't pick up" as the whole cadence, when
the evidence above says that's roughly the first 15% of what a full sequence looks like. The
compliance gates in §3 matter *more*, not less, for a small operation with no in-house legal review —
a mislabeled consent checkbox or a DNC-listed number called anyway is a real, personally-borne
liability for an owner-operator, not an abstraction absorbed by a large company's legal department.
