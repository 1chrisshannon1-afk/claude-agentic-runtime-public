# Estimate Follow-Up

For a business whose core sales artifact is a quote, estimate, or proposal rather than a live demo
call, the sales cycle's decisive moment is not the pitch — it's what happens between "estimate sent"
and "won or lost." This file covers proposal-open tracking, follow-up timing after a sent estimate,
and the honesty constraints on how urgency is communicated during that window.

## 1. Why the sent-estimate gap is where deals are actually won or lost

**[KB-SALES-033]** Estimate/proposal software vendors (PandaDoc, Proposify, and similar
proposal-tracking tools) commonly report that proposals opened and reviewed within the first **24
hours** of being sent close at meaningfully higher rates than those left unopened or opened much
later, and that follow-up timed to an actual proposal-open event outperforms follow-up sent on a
fixed calendar schedule with no signal of engagement (third-party, aggregated from proposal-software
vendor benchmark content — PandaDoc/Proposify-lineage "proposal statistics" pages — retrieved
2026-09-27 — **UNVERIFIED at the level of a precise conversion-rate multiplier: these are vendor
benchmark blogs built from the vendor's own aggregate customer data with undisclosed methodology and
an inherent incentive to make their own tracking feature look valuable; treat the underlying
mechanism — engagement-triggered follow-up beats blind calendar-scheduled follow-up — as the
well-supported takeaway, not any specific percentage.**)

**[KB-SALES-034] (internal doctrine)** The mechanism this evidence supports, independent of the exact multiplier: a sent
estimate is not a fire-and-forget document. Follow-up timed to a real signal (the prospect opened it,
the prospect opened it a second time three days later, the prospect forwarded it to someone else if
the tool can detect that) is a materially better trigger for a follow-up call than an arbitrary
"call in 3 days" rule applied identically regardless of whether the prospect has even looked at it
yet.

## 2. Proposal-open tracking — what it can and can't tell you

**[KB-SALES-035] (internal doctrine)** Open/view tracking on a sent estimate (via a tracked PDF, a tracked link, or
dedicated proposal software) tells you *that* engagement happened and roughly *when*, not *why* or
*what the prospect concluded*. **Reject pattern:** treating "no opens recorded after 5 days" as proof
the lead has gone cold and moving it to a dead/lost status — an unopened tracking pixel can also mean
the email landed in spam, was opened by IT/spam-filter prefetching (a known false-positive source for
email open tracking generally), or the prospect printed a version someone else sent them without
using the original tracked link. **Pass pattern:** treating a genuine, repeated, multi-day open
pattern (opened day 1, opened again day 4, spent several minutes on it both times) as a strong signal
to call now with a specific, well-timed message — "I saw you had a chance to look this over, what
questions came up?" — while treating a single no-opens data point alone as inconclusive, not
disqualifying.

## 3. Follow-up timing and cadence specific to a sent estimate

**[KB-SALES-036] (internal doctrine)** The general follow-up-cadence mechanism in `follow-up-cadences.md` applies to a
sent-estimate sequence with one estimate-specific addition: the *trigger* for the first follow-up
touch should be the estimate being sent (an event, like the lead-inquiry trigger in
`speed-to-lead.md`), and the cadence should branch on the open-tracking signal where available —
an opened-but-no-response estimate gets a different, more specific follow-up message ("did the scope
match what you had in mind?") than an unopened one (which more plausibly needs a "did this reach
you okay?" check, since a legitimate delivery failure is a real possibility, not just disinterest).
**(Mechanism-level synthesis of [KB-SALES-033]–[KB-SALES-035] and the general cadence doctrine; not
independently sourced beyond those.)**

**[KB-SALES-037] (internal doctrine)** A sent estimate should have an explicit expiration or validity window stated on the
document itself (e.g., "valid for 30 days," reflecting real material/labor cost volatility a
contractor legitimately faces) — this is a pricing/estimating-domain concern for the *number itself*,
but for sales-ops it also functions as a legitimate, honest forcing function for follow-up timing: a
follow-up touch positioned around the actual expiration ("your estimate is valid through the 15th, I
wanted to check in before then") is a real, verifiable urgency signal, distinct from the fabricated
urgency covered in §4 below. **(Mechanism-level; the actual pricing-validity window and its
underlying cost-volatility justification is set by the estimating/pricing function, not sales-ops —
this file only covers using a real window as a follow-up trigger.)**

## 4. Honesty constraints on urgency during follow-up

**[KB-SALES-038]** The FTC's general prohibition on deceptive and unfair trade practices (Section 5 of
the FTC Act) covers fabricated scarcity and urgency claims made to induce a purchase decision — a
false "this price expires tomorrow" or "we only have one crew slot left this month" claim, when
untrue, is a deceptive practice, not a legitimate sales technique (official, FTC Act Section 5
general framework as applied to deceptive marketing claims, retrieved 2026-09-27,
https://www.ftc.gov/legal-library/browse/statutes/federal-trade-commission-act — general
authority; no specific FTC enforcement action against a residential-contractor estimate-urgency
claim was independently located during this pass, so the *application* to this exact fact pattern is
**UNVERIFIED — inferred from the FTC's general deceptive-practices authority, not from a
directly-on-point enforcement precedent; treat the underlying principle — never state urgency or
scarcity that isn't real — as binding regardless, since it follows from the general prohibition on
material deceptive claims**).

**[KB-SALES-039] (internal doctrine)** The correct, non-deceptive equivalent of manufactured urgency is the real
constraint named in §3 — an actual price-validity window tied to real cost volatility, an actual
current scheduling lead time stated honestly ("our next available start date is currently early
November" — true and updated as it changes, not a static "only 2 slots left!" banner that never
changes regardless of actual capacity). **Reject example:** a proposal template with a hardcoded
"Only 3 spots remaining this month!" line that renders identically regardless of the contractor's
actual current booking calendar. **Pass example:** a scheduling-lead-time field that's pulled from
the contractor's actual current calendar and updates as capacity changes, stated as what it is (a
real lead time), never dressed up as manufactured scarcity language.

## Contractor bend

For a small owner-operated residential remodeling business, the "sent estimate" gap described in §1 is frequently the *entire*
sales cycle after the first in-home consultation — there is often no formal demo, no multi-stakeholder
committee, just a homeowner reading a PDF or paper estimate at their kitchen table, possibly compared
side-by-side against one or two competitors' bids. This makes the follow-up call's specific content
matter enormously: a generic "just checking in, did you get a chance to look at that?" call
communicates nothing the homeowner couldn't infer from a form email, while a call that references the
*specific* scope item most likely to need clarification (a material choice, a timeline question, an
allowance line) demonstrates the contractor actually understands their own bid and gives the
homeowner a real reason to engage rather than let the call go to voicemail. Real, honestly-stated
scheduling lead time (§4) is also a genuinely strong, non-manipulative differentiator for this buyer
specifically — a homeowner who has been burned by a contractor who over-promised availability and then
disappeared for weeks (see `../shared/homeowner-buyer-psychology.md`) responds well to a contractor
who states their actual current timeline plainly and holds to it, which is the opposite of fabricated
urgency and should never be blurred with it.
