# Reactivation

Reactivation (also called win-back) is the discipline of re-engaging a lead or customer who has gone
stalled, lost, or dormant — distinct from the active cadence in `follow-up-cadences.md`, which covers
a lead still inside its initial follow-up window. This file covers segmentation of dormant contacts,
message sequencing for a win-back attempt, and the honesty constraints on what a "win-back" message
can legitimately claim.

## 1. What "dormant" means, and why it needs its own track

**[KB-SALES-040] (internal doctrine)** A lead that exhausts an active follow-up cadence (`follow-up-cadences.md` §4's
"cadence exhausted" endpoint) without a resolution is not evidence the opportunity is permanently
dead — it means the *active, time-pressured* pursuit has ended and the contact should move to a
longer-horizon, lower-frequency track rather than being deleted or ignored. **(Mechanism-level,
consistent with standard sales-process practice and directly downstream of this domain's own
`follow-up-cadences.md` §4 and `crm-hygiene.md` §5 pipeline-stage discipline; not independently
sourced beyond that.)** A customer who was won and then went quiet (stopped responding to
service/upsell outreach, didn't return for a repeat project) is a distinct dormant-segment from a lead
that was never won — the message and channel appropriate to each differs, covered in §2.

**[KB-SALES-041] (internal doctrine)** Segmentation for a reactivation track should separate at minimum: (a) a lead that
went cold before any proposal/estimate was sent (never got far enough to see pricing), (b) a lead that
received an estimate and went quiet (`estimate-follow-up.md`'s track exhausted with no resolution),
and (c) a past customer who hasn't returned for further work. Each has a different plausible reason
for going dormant (never got serious, priced elsewhere, or simply hasn't had a new need arise) and
therefore a different legitimate message — a single generic "just checking in!" blast to all three
segments wastes the segmentation's own value. **(Mechanism-level synthesis; not independently
sourced.)**

## 2. Message sequencing for a win-back attempt

**[KB-SALES-042]** General CRM and lifecycle-marketing practitioner guidance commonly recommends a
short win-back sequence (often 2–4 touches) rather than a single message, using a distinct value
proposition from the original outreach — referencing time elapsed, offering something new (an updated
capability, a seasonal offer, a genuine change in circumstances like new availability) rather than
repeating the original pitch verbatim, and including an easy, low-friction way to say "not interested,
stop contacting me" (third-party, standard lifecycle-marketing/CRM practitioner guidance aggregated
across HubSpot/Salesforce-ecosystem content, retrieved 2026-09-27 — **UNVERIFIED at the level of a
specific optimal touch count or reactivation-rate benchmark; every reachable source is vendor
practitioner content with no disclosed controlled methodology; treat the sequencing mechanism as
reasonable practice, not a proven-optimal formula**).

**[KB-SALES-043] (internal doctrine)** A win-back message should acknowledge the gap honestly rather than pretending no
time has passed — "It's been a while since we last spoke about your [project type]" is honest and
low-pressure; pretending the prior conversation was recent, or omitting that this is a repeat contact
attempt after silence, reads as either forgetful or manipulative depending on how the recipient
perceives it. **(Mechanism-level, tied to the general honesty-in-communication principle this corpus
applies throughout, e.g. `estimate-follow-up.md` §4's urgency-honesty rule.)**

## 3. The compliance and consent boundary that reactivation must respect

**[KB-SALES-044] (internal doctrine)** Reactivation does not reset or bypass any consent or opt-out status the contact
already established — a lead who opted out of email during an earlier active cadence
(`follow-up-cadences.md` §3, `../compliance/can-spam.md`) remains opted out for reactivation
purposes; reactivation on that channel is prohibited for that contact regardless of how much time has
passed, unless the contact affirmatively re-opts-in through some new, verifiable action. The same
applies to SMS/TCPA consent (`follow-up-cadences.md` §3, [KB-SALES-020] —
**UNVERIFIED (primary source unreachable: https://www.fcc.gov/general/telemarketing-and-robocalls,
confirmed 2026-09-27)**) — dormancy is not a consent
event, and a stale-but-never-revoked consent record should still be checked against current
regulatory guidance before a reactivation SMS sends, per the same UNVERIFIED caveat on TCPA specifics
noted in `follow-up-cadences.md`. **Reject pattern:** re-adding an opted-out contact to an active
sending list simply because enough time has passed that the opt-out "feels stale" — an opt-out has no
expiration under CAN-SPAM (verified separately, see `../compliance/can-spam.md`) or TCPA (see the
UNVERIFIED caveat above); it persists until the contact affirmatively reverses it.

**[KB-SALES-045] (internal doctrine)** A win-back message must not misrepresent why the contact is being reached again —
claiming "we noticed you were interested in X" when the actual trigger is a bulk reactivation-segment
export is a mild form of the same deceptive-framing concern addressed more sharply in
`estimate-follow-up.md` §4; keep reactivation messaging honest about its own generic, segment-based
nature rather than fabricating a specific, personal signal that didn't occur.

## 4. Where reactivation overlaps with review acquisition

**[KB-SALES-046] (internal doctrine)** A won-and-gone-quiet past customer (segment (c) in §1) reaching the end of a
project is frequently also the right moment for a review ask — but review acquisition itself
(timing, compliant solicitation language, platform-specific review-gating prohibitions) is owned by
the `reputation/` domain, not this file; a reactivation touch to a past customer that legitimately
also functions as a review-ask touch should follow that domain's own doctrine for the review-request
half of the message, not improvise it here. This file's boundary: reactivation covers re-engaging for
*further business*, and only notes the overlap where a single touch legitimately serves both purposes.

## Contractor bend

For a residential GC, the past-customer segment (§1c) is often the single highest-value reactivation
opportunity and the most commonly neglected one — a homeowner who had a good experience on a bathroom
remodel two years ago is a warm, pre-vetted lead for a kitchen remodel now, dramatically cheaper to
re-engage than a fresh paid lead, but easy to lose track of without deliberate reactivation because a
one-person sales operation is usually fully occupied chasing *new* inbound rather than mining its own
past-customer list. A simple, low-effort seasonal or milestone-triggered touch (an annual "how's the
space holding up, anything else on your list?" message timed to `../shared/home-services-playbooks.md`'s
seasonal patterns) is a realistic, low-overhead implementation of this mechanism for an owner who
can't run a full lifecycle-marketing program — the honesty and consent constraints in §2–3 apply
identically regardless of scale, and matter more for an owner-operator whose personal reputation is
directly on the line for every message sent under the business's name.
