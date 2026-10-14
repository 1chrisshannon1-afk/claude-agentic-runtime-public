# Compliance Anti-Patterns — Things a Seat Must NEVER Recommend

Every item below is something any GTM agent touching reviews, email, SMS/calls, endorsements, or
personal/health data must refuse to propose, even when a founder/operator asks for it directly, even
when a competitor is visibly doing it, and even when it would plausibly work short-term. Cite this
file, and the specific source file's claim id, when refusing.

---

## 1. Review gating (routing only happy customers to the public review ask)

**What it is:** Asking only customers who indicated satisfaction (via a private survey, an NPS
score, or human judgment) to leave a public review, while unhappy customers are routed to a private
form instead — a two-step funnel where the public review link is conditional on a sentiment signal.

**Why it's banned:** This is a distinct, codified violation under 16 CFR § 465.7, not just "smart
funnel design" — see [`review-gating.md`](review-gating.md) [KB-COMPLIANCE-013] through
[KB-COMPLIANCE-018] for the full mechanism and the compliant alternative.

**Reject example:** "If you had a great experience, click here to leave a Google review! If not,
click here to tell us how we can improve" presented as the only two options. **Pass example:** every
customer at the same touchpoint gets the same public-review ask; a private feedback channel is
offered *in addition*, never as a replacement for the low-score branch.

## 2. Fake, incentivized, or insider reviews without disclosure

**What it is:** Writing, purchasing, or soliciting a review from someone who didn't actually use the
product/service; paying or otherwise incentivizing a review conditioned on it being positive; having
an owner, employee, or family member post a review of the business without disclosing the
connection.

**Why it's banned:** Directly prohibited under 16 CFR Part 465 §§ 465.2, 465.4, and 465.5 — see
[`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) §1 for the
section-by-section breakdown and the $53,088-per-violation penalty ceiling.

**Reject example:** offering a discount contingent on a 5-star review, or having the owner's spouse
post a glowing review under a name that doesn't disclose the relationship. **Pass example:**
incentivizing the *act* of leaving a review (any rating) with a small, disclosed thank-you that
doesn't condition on sentiment, and requiring any employee/owner/family review to carry a clear
"I work here" / "I'm the owner" disclosure.

## 3. Commercial email missing any of the five CAN-SPAM elements

**What it is:** Sending a promotional email with a deceptive subject line, a spoofed or unclear
sender identity, no physical postal address, or no working one-click opt-out.

**Why it's banned:** Each missing element is independently a federal violation, and — critically —
exposure is **per recipient**, not per campaign; see [`can-spam.md`](can-spam.md)
[KB-COMPLIANCE-021] through [KB-COMPLIANCE-023].

**Reject example:** a re-engagement blast to an old, unscrubbed list that includes addresses that
already opted out months ago. **Pass example:** every send checked against a live, enforced
suppression list immediately before sending, regardless of how the list was assembled or merged.

## 4. Autodialed/prerecorded texts or calls without channel-specific written consent

**What it is:** Treating a general "contact me" opt-in as sufficient authorization to send
autodialed marketing texts or prerecorded/artificial-voice calls, or continuing to text/call a
number after any reasonable-means revocation because it didn't use the exact expected "STOP"
keyword.

**Why it's banned:** TCPA requires prior express **written** consent specific to the channel used,
and revocation must be honored through any reasonable means the consumer chooses — see
[`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md) [KB-COMPLIANCE-024] through [KB-COMPLIANCE-027]. Statutory
damages of $500–$1,500 per message, frequently pursued as class actions, make this one of the
highest-dollar-exposure items in this entire corpus.

**Reject example:** continuing an SMS drip sequence to a number that replied "please stop texting
me" in plain language, because the automation only watched for the literal word "STOP." **Pass
example:** any reasonably-worded opt-out request, in any channel, immediately suppresses future
autodialed contact to that number within 10 business days.

## 5. Sending or calling outside the permitted window

**What it is:** Scheduling an SMS or call campaign using the sender's own time zone as the
reference clock instead of each recipient's local time, or ignoring a stricter state-specific
quiet-hours statute.

**Why it's banned:** The federal floor restricts telemarketing calls/texts to 8am–9pm **at the
called party's location**, and several states impose narrower windows this corpus has not
exhaustively verified — see [`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md) [KB-COMPLIANCE-028] through
[KB-COMPLIANCE-031].

**Reject example:** a single nationwide 7am Eastern send that lands at 4am Pacific for West Coast
recipients. **Pass example:** the doctrine default (9am–8pm recipient-local, Mon–Sat, no Sunday)
unless every targeted state has been individually verified to allow more.

## 6. Declaring an A2P 10DLC opt-in method that doesn't match reality

**What it is:** Registering a carrier Campaign with an opt-in method (e.g. "web form with
checkbox") that isn't actually how consent is being collected, to obtain a more favorable vetting
tier or content classification.

**Why it's banned:** This is a Campaign-registration integrity violation independent of TCPA
exposure — see [`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md) [KB-COMPLIANCE-035]. It also compounds risk:
a mismatched declaration means the actual (unverified) consent flow was never scrutinized against
the claim being made about it.

**Reject example:** declaring "double opt-in web form" to Twilio/TCR while the actual flow is a
single unchecked pre-ticked box. **Pass example:** the declared opt-in method is exactly what a
compliance reviewer would see if they walked the real user flow themselves.

## 7. Geofencing or targeting based on health-adjacent location/behavior signals

**What it is:** Drawing an ad-targeting geofence around a healthcare, rehab, mental-health, or
reproductive/sexual-health facility to target people as patients or visitors, or building a
retargeting audience from browsing behavior that reveals an attempt to seek health care.

**Why it's banned:** Washington's My Health My Data Act explicitly prohibits exactly this mechanism
and applies regardless of HIPAA-covered-entity status; other states may have comparable statutes
this corpus has not exhaustively verified — see
[`privacy-and-consent.md`](privacy-and-consent.md) [KB-COMPLIANCE-038] through [KB-COMPLIANCE-040].
This is one of the few items in this entire corpus where "ask forgiveness" is never an acceptable
posture, because MHMDA creates a **private right of action** — an individual consumer, not just a
regulator, can sue (claim 041).

**Reject example:** an accessibility-remodeling campaign geofencing a rehab clinic's parking lot to
retarget people leaving physical therapy. **Pass example:** targeting based on stated homeowner
intent (a lead form, a search query for "walk-in tub installation") with no location or behavioral
signal tied to a healthcare facility.

## 8. Reusing a PHI-adjacent detail in a public review reply

**What it is:** A practice's public reply to an online review that confirms someone was a patient,
or references their treatment, insurance, or visit details, even defensively ("we only charged you
what your insurance allowed for your procedure on [date]").

**Why it's banned:** Confirmed OCR enforcement pattern for HIPAA-covered entities — see
[`hipaa-marketing-for-practices.md`](hipaa-marketing-for-practices.md) for the sourced settlement
examples and the required reply doctrine. Even where the reviewer disclosed their own status first,
the covered entity confirming or adding detail is the violation.

**Reject example:** "You were only in our office for a routine cleaning, not the procedure you're
describing." **Pass example:** "We take all patient feedback seriously and would welcome the chance
to discuss your experience directly — please contact our office at [number]," which neither confirms
nor denies any relationship.

## 9. Treating a ported benchmark number, or an unverified state-law claim, as settled fact

**What it is:** Stating a specific compliance threshold, dollar penalty, or state-law rule with
confidence when the underlying claim in this corpus is marked `UNVERIFIED`, or restating a number
from a different vertical/jurisdiction as if independently confirmed here.

**Why it's banned:** This corpus's entire citation discipline exists to make the difference between
a verified claim and a guess visible at a glance — see `shared/citation-style.md`. Compliance
doctrine specifically is the domain where an unverified claim is most likely to be relied on
directly in a client-facing legal-adjacent statement, so the cost of silently upgrading
"UNVERIFIED" to "confirmed" is highest here.

**Reject example:** telling an operator "Nevada also bans this geofencing tactic" when
[`privacy-and-consent.md`](privacy-and-consent.md) [KB-COMPLIANCE-040] explicitly marks that
UNVERIFIED. **Pass example:** "Washington explicitly bans this; other states may — we have not
independently verified which, so treat the Washington rule as the safe floor everywhere until a
specific state is checked."

---

## Contractor bend

None of the above changes for a home-services company specifically — the small owner-operated
trade-business archetype this section addresses — if anything the
stakes are higher, because this buyer has no in-house legal or compliance staff to catch a bad
recommendation before it becomes a class-action-scale TCPA exposure or a review-platform ban. When
explaining why something is off-limits to this buyer, skip the statutory-citation framing and lead
with the dollar and business-continuity consequence in plain terms: "this can cost you more than a
year of marketing spend, and it's a one-time setup to do it right" lands; "16 CFR § 465.7 prohibits
selective solicitation" does not. Never assume this buyer will push back on a shortcut being
offered — review gating, a geofenced rehab-clinic campaign, and a "just text everyone who filled out
a form once" send are all things a well-meaning owner might ask for because they sound like normal
marketing, not because they intend to break a rule they've never heard of. The obligation to refuse,
and to explain the real (not hypothetical) consequence, is entirely on the agent.
