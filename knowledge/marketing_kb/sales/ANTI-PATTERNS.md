# Sales-Ops Anti-Patterns — Things a Seat Must NEVER Recommend or Automate

Every item below is something a sales-ops GTM seat must refuse to propose or automate, even when it
would plausibly increase short-term contact rates or conversion, even when a competitor visibly does
it, and even when an operator asks for it directly. Cite this file when refusing.

---

## 1. Autodialing or texting a cell number with no documented prior express written consent

**What it is:** Adding a phone number to an autodialed call queue or an SMS blast/cadence step
without a recorded, verifiable prior express written consent event for that specific number.

**Why it's banned:** TCPA requires prior express written consent before an autodialed or prerecorded
marketing call or text reaches a wireless number, and violations carry statutory per-message/per-call
penalty exposure — **UNVERIFIED (primary source unreachable: https://www.fcc.gov/general/telemarketing-and-robocalls,
returns HTTP 403 to automated fetches; confirmed 2026-09-27) — see `follow-up-cadences.md` §3,
[KB-SALES-020] for the full caveat and the cross-check via 47 CFR § 64.1200.** Unlike CAN-SPAM's
opt-out email regime, this is understood to be an **opt-in** requirement — the
absence of a complaint or opt-out is not evidence consent existed. A single ungoverned SMS blast can
generate per-recipient liability that scales with list size, exactly like the CAN-SPAM exposure
described in `../compliance/can-spam.md` §3.

**Reject example:** Importing a list of phone numbers scraped from public listings or an old
spreadsheet with no consent field, then adding them to an automated SMS cadence "because they're
technically leads." **Pass example:** A form that captures explicit SMS opt-in language at the moment
of submission, stored with a timestamp and the source page, checked before every SMS-cadence step —
see `follow-up-cadences.md` §3.

## 2. Calling a number on the Do Not Call Registry outside a verified, time-limited exemption

**What it is:** Treating any past inquiry or transaction as a permanent license to call a Registry-
listed number, without checking whether the specific exemption window still applies.

**Why it's banned:** The established-business-relationship exemptions to the National Do Not Call
Registry are time-limited, not permanent (official, FTC National Do Not Call Registry for businesses,
retrieved 2026-09-27, https://www.ftc.gov/business-guidance/do-not-call — see
`follow-up-cadences.md` §3, [KB-SALES-022], which flags the exact window as needing live
verification). Calling outside a valid exemption is a real, per-call penalty exposure.

**Reject example:** Resuming outbound calls to a two-year-old inquiry list because "they inquired with
us before, so they're a customer relationship." **Pass example:** Checking the actual, current
exemption window against live regulatory guidance before treating an aged inquiry as call-eligible,
and defaulting to not calling when the window is unverified.

## 3. Ignoring an opt-out because "enough time has passed" or the record is on a different list

**What it is:** Re-adding a contact to an active send list after they opted out, on the theory that a
merged list, a new campaign, or elapsed time resets their consent status.

**Why it's banned:** CAN-SPAM opt-outs and TCPA consent revocations do not expire and are not scoped
to a single campaign or list — see `reactivation.md` §3, [KB-SALES-044], and
`../compliance/can-spam.md` §2's opt-out processing rules. A merged or re-imported list is one of the
most common real-world ways this gets violated unintentionally, which is exactly why it's named
explicitly rather than assumed obvious.

**Reject example:** A win-back campaign pulls from "all past leads" without cross-checking the current
suppression list, resending to someone who unsubscribed eight months ago. **Pass example:** Every
send, cadence, and reactivation list is checked against the live, current suppression list
immediately before sending — never at signup time only.

## 4. Fabricated urgency or scarcity in an estimate or proposal follow-up

**What it is:** Stating a deadline, limited slot count, or expiring discount that does not reflect the
contractor's actual current capacity, pricing validity, or scheduling constraints.

**Why it's banned:** This is a deceptive practice under the FTC Act's general prohibition on unfair or
deceptive acts (official, general FTC Act Section 5 authority, retrieved 2026-09-27,
https://www.ftc.gov/legal-library/browse/statutes/federal-trade-commission-act — see
`estimate-follow-up.md` §4, [KB-SALES-038]–[KB-SALES-039], which flags the specific-precedent
application as unverified but the underlying principle as binding regardless). It is also a
trust-destroying pattern for a buyer archetype already primed to distrust sales pressure (see
`../shared/homeowner-buyer-psychology.md` and `../shared/contractor-buyer-psychology.md`).

**Reject example:** A proposal template with a static "Only 2 crew slots left this month!" line that
renders identically regardless of the contractor's real booking calendar. **Pass example:** A
scheduling-lead-time statement pulled from the contractor's actual current calendar, stated honestly
and updated as it changes.

## 5. Gating a lead's first response behind full qualification

**What it is:** Delaying the first human contact with a new inbound lead until a full BANT or
MEDDPICC qualification pass is complete, rather than responding fast and qualifying progressively.

**Why it's banned:** This directly contradicts the best-evidenced finding in this entire domain — the
decay in contact/qualification odds is steep and front-loaded within the first minutes to hours (see
`speed-to-lead.md` §1–§2). A framework's overhead becoming the bottleneck to first contact is named
explicitly as a reject pattern in `lead-qualification.md` §3.

**Reject example:** A rep spends 20 minutes fully MEDDPICC-scoring a $400 transactional lead in the
CRM before making the first callback attempt. **Pass example:** A 2-question automated triage happens
before or during the very first contact attempt; deeper qualification happens once a human is already
engaged, per `lead-qualification.md` §3's pass example.

## 6. Treating a single unopened tracking pixel or one unanswered call as proof a lead is dead

**What it is:** Marking a lead lost or moving it out of active pursuit based on one inconclusive
non-engagement signal, rather than a defined, exhausted cadence.

**Why it's banned:** Open-tracking and call-answer signals have well-known false-negative causes
(spam filtering, prefetch scanning, a call simply missed while driving) — treating one such signal as
conclusive is named explicitly as a reject pattern in `estimate-follow-up.md` §2, and contradicts the
evidence in `follow-up-cadences.md` §1 that most conversions require persistence well past a single
touch.

**Reject example:** A lead is auto-marked "Lost — Unresponsive" after one unanswered call with no
further attempts. **Pass example:** A lead moves to lost/dormant status only after a defined,
multi-touch, multi-channel cadence is genuinely exhausted, per `follow-up-cadences.md` §2's
"cadence exhausted" endpoint discipline.

## 7. Reporting a qualification score, PQL score, or CRM field as meaningful when nothing acts on it

**What it is:** Displaying or citing a qualification/PQL score, pipeline stage, or "hot lead" flag as
if it drives real prioritization, when no actual routing, escalation, or automation is wired to it.

**Why it's banned:** Named explicitly as bookkeeping-not-qualification in `lead-qualification.md` §3
and `b2b-trial-to-paid.md` §3 — a score that doesn't change what happens next gives false confidence
that leads are being prioritized correctly when they aren't, which is worse than having no score at
all because it hides the gap instead of surfacing it.

**Reject example:** A PQL score column populated and visible on a dashboard, admired in a weekly
review, with no automation or human process that treats a high scorer differently from a low scorer.
**Pass example:** A defined action (proactive outreach, priority routing, an in-app nudge) is
triggered mechanically by the score crossing a threshold, and that trigger is checkable in the
activity log.

## 8. Fabricating or porting benchmark numbers as if independently verified for this business

**What it is:** Stating a specific conversion rate, touch-count benchmark, or response-time statistic
from this corpus's cited third-party sources as if it were this specific company's own measured
performance, or porting a number from an unrelated vertical (e.g., a dental-practice or enterprise
SaaS benchmark) as a home-services-specific fact.

**Why it's banned:** Every third-party figure in this corpus is explicitly flagged with its
verification status per `../shared/citation-style.md` precisely so it is never mistaken for a
company's own measured result — see the worked example distinguishing `(internal-measured)` from a
calculated or cited figure in that file. Presenting a vendor-blog benchmark to an operator as if it
were this company's actual number misleads a real business decision (staffing, ad spend, tooling
choice).

**Reject example:** Telling an operator "your trial-to-paid rate should be 50%+ like the SaaS
benchmarks" when no comparable opt-out trial model or company-specific measurement exists.
**Pass example:** Citing the benchmark range with its full UNVERIFIED/third-party caveat intact, and
recommending the company measure its *own* actual rate before treating any external figure as a
target.

## 9. Automating a win-back or reactivation message that misrepresents why the contact is being reached

**What it is:** Sending a reactivation message that implies a specific, personal trigger ("we noticed
you were still interested in X") when the actual trigger is a bulk dormancy-segment export.

**Why it's banned:** Named explicitly in `reactivation.md` §3, [KB-SALES-045] — this is a milder form
of the same deceptive-framing concern that governs fabricated urgency (§4 above), and this corpus's
house style treats honesty about a message's own generic nature as non-negotiable throughout.

**Reject example:** An automated win-back email claiming "I was just thinking about your project" sent
identically to an entire dormant-lead segment on a schedule. **Pass example:** An honest acknowledgment
of the time gap and the real reason for reaching out, per `reactivation.md` §2's pass pattern.

---

## Contractor bend

None of the above changes for the small owner-operated home-services/trade business buyer — if anything the personal liability is
higher, because a TCPA or Do Not Call violation lands on the individual owner-operator's business
identity directly, with no in-house legal or compliance department to catch it first, and because
this buyer's own reputation among a small local customer base is disproportionately damaged by being
caught using a manipulative sales tactic (a fabricated deadline, a call after opting out) that a
larger company might absorb as a minor incident. When refusing one of these patterns to this buyer,
lead with the concrete personal consequence — "this can create real legal exposure tied directly to
you and your license, not just the business" — rather than an abstract compliance-framework
explanation; this buyer responds to plain, consequence-first reasoning, not policy citations.
