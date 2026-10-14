# Review-Acquisition-Compliant — How to Ask for Reviews Without Gating

How a business asks customers for reviews in a way that is legal (FTC) and platform-safe, with no
review gating anywhere in the flow. This file is the **acquisition** side (how to ask); `never-do.md`
is the **prohibited-tactics** side (what never to do once you're asking); `escalation-triggers.md`
and `response-templates-by-severity.md` cover what happens after a review already exists.

**Where the rule text itself lives:** this file gives pointers and the operational doctrine derived
from the rule; the full legal text of the FTC rule and adjacent compliance-domain doctrine
(CAN-SPAM, TCPA, endorsement-disclosure specifics) lives in
[`compliance/ftc-endorsements-and-fake-reviews.md`](../compliance/ftc-endorsements-and-fake-reviews.md)
(full Part 465 breakdown and penalty exposure) and
[`compliance/review-gating.md`](../compliance/review-gating.md) (the gating deep-dive) — this file
does not duplicate their rule text, only the operational doctrine derived from it.

Every claim below carries a stable id `[KB-REP-NNN]` (continuing this directory's numbering from
`platform-review-policies.md`) and a citation. Retrieval date for FTC sources: **2026-09-27**.

## 1. The rule that governs every acquisition tactic

**[KB-REP-014]** The FTC's Trade Regulation Rule on the Use of Consumer Reviews and Testimonials,
codified at **16 CFR Part 465**, took effect **October 21, 2024**, and applies to any business
whose reviews reach U.S. consumers regardless of the business's size, vertical, or the platform the
review appears on. (official, Cornell Law School Legal Information Institute, eCFR mirror,
retrieved 2026-09-27: https://www.law.cornell.edu/cfr/text/16/part-465 — used as the reachable
mirror because ftc.gov's own rule page and the Federal Register's original notice both blocked
automated retrieval on this date; ecfr.gov also blocked retrieval directly.)

**[KB-REP-015]** The rule is organized into named prohibited-practice sections, each independently
enforceable: **§465.2** (fake or false consumer reviews, consumer testimonials, or celebrity
testimonials), **§465.4** (buying positive or negative consumer reviews), **§465.5** (undisclosed
insider consumer reviews/testimonials), **§465.6** (company-controlled review websites or entities
presented as independent), **§465.7** (review suppression), and **§465.8** (misuse of fake
indicators of social media influence). (official, same source as [KB-REP-014], retrieved
2026-09-27)

**[KB-REP-016]** Penalty exposure is per-violation and inflation-adjusted annually — see
[`compliance/ftc-endorsements-and-fake-reviews.md`](../compliance/ftc-endorsements-and-fake-reviews.md)
[KB-COMPLIANCE-004] for the current ceiling and its sourcing; this file does not restate the number,
per this corpus's rule against duplicating a cited figure across files.

## 2. §465.4 — no incentive tied to writing a review, full stop

**[KB-REP-017]** Quoting the rule's own operative language as retrieved: *"It is an unfair or
deceptive act or practice and a violation of this part for a business to provide compensation or
other incentives in exchange for... the writing or creation of consumer reviews."* (official, same
source as [KB-REP-014], §465.4, retrieved 2026-09-27) This bans compensation or incentives whether
explicitly conditioned on a rating or not — a card that says "leave any review, good or bad, and
get $10 off" is still banned, because the incentive is conditioned on the act of reviewing itself,
not merely on the review's sentiment. This is a stricter reading than an incentive-for-5-stars
scheme; do not assume an unconditional "leave any review" incentive is safe merely because it
doesn't specify a rating.

- **REJECT:** "Leave us a review — any review — and we'll enter you in a monthly $100 gift card
  drawing."
- **REJECT:** "Get a free filter replacement when you post feedback about your HVAC install."
- **ACCEPT:** Asking for a review with nothing offered in exchange, applied identically to every
  customer regardless of predicted sentiment.

## 3. §465.7 — review suppression / gating, precisely defined

**[KB-REP-018]** Quoting the rule's own operative language as retrieved: the rule prohibits
materially misrepresenting *"that the consumer reviews of one or more of the products or services
it sells displayed in a portion of its website or platform dedicated in whole or in part to
receiving and displaying consumer reviews represent most or all the reviews submitted to the
website or platform when reviews are being suppressed (i.e., not displayable) based upon their
ratings or their negative sentiment."* (official, same source as [KB-REP-014], §465.7, retrieved
2026-09-27) In plain terms: a business cannot represent its displayed reviews as broadly
representative while quietly filtering out negative ones by rating or sentiment. This is what
review-gating flows (survey first, route unhappy respondents to a private form, route happy ones
to the public review link) actually violate — not because asking a customer how they feel is
itself illegal, but because the RESULT misrepresents what the public review surface represents.

**[KB-REP-019]** The rule carries an explicit, narrow safe harbor: suppression IS permitted for
content that is a trade secret, defamatory, contains personal information, is discriminatory,
contains a clearly false statement, is a suspected fake review, or is unrelated to the products or
services actually offered — provided the removal criteria are applied uniformly, not selectively
by sentiment or rating. (official, same source as [KB-REP-014], §465.7, retrieved 2026-09-27) A
business may still moderate genuinely abusive, off-topic, or fake content; it may not moderate
genuine negative sentiment.

- **REJECT:** A post-service survey ("How was your experience?") that routes anyone who answers
  positively to a public Google review link and routes anyone who answers negatively to a private
  "tell us more" form instead — this is precisely [KB-REP-018]'s prohibited shape.
- **REJECT:** Deleting a genuinely negative but non-abusive, on-topic review from a
  company-hosted testimonials page while keeping every positive one, then describing that page as
  "what our customers say" — misrepresents the page as representative when it isn't.
- **ACCEPT:** Removing a review that names a third party's private phone number, or one that is
  provably about a different company entirely (a mismatched-business review) — this fits
  [KB-REP-019]'s uniform, criteria-based safe harbor.
- **ACCEPT:** A single request flow sent to every customer alike, with the same link, regardless
  of any predicted or expressed sentiment — see `never-do.md` #2's ACCEPT pattern for the same
  structure stated from the response-drafting side.

## 4. §465.5 — insider reviews need disclosure

**[KB-REP-020]** The rule prohibits undisclosed insider consumer reviews and testimonials —
reviews written by employees, owners, or their close relatives about their own business, presented
as if from an independent customer, without disclosing the relationship. (official, same source as
[KB-REP-014], §465.5, retrieved 2026-09-27 — section title and scope confirmed; exact operative
text not independently quoted in this file's retrieval pass, so treat any more specific wording
attributed to §465.5 beyond "requires disclosure of a material connection" as UNVERIFIED until a
direct quote is retrieved.)

- **REJECT:** An owner or crew member posting a 5-star review of their own company from a personal
  account with no disclosure of the employment relationship.
- **ACCEPT:** An owner's family member who was ALSO a genuine paying customer discloses the
  relationship explicitly in the review text before describing their real experience.

## 5. What a compliant acquisition flow looks like, end to end

**[KB-REP-021]** (internal synthesis of [KB-REP-014] through [KB-REP-020] plus the platform rules
in `platform-review-policies.md` — not a separate citation.) A review-acquisition flow that
survives every rule in this file and every platform's own policy shares these properties:

1. **Same ask, every customer, same moment** — typically at project completion / final walkthrough
   / invoice-paid, regardless of how the job visibly went.
2. **No incentive of any kind** tied to the act of reviewing (§465.4) — not a discount, not a
   sweepstakes entry, not a referral credit bundled into the same message.
3. **No pre-screening question** that determines which customers receive the ask or which
   platform link they receive (§465.7) — one flow, one link (or the same set of links), for
   everyone.
4. **No fabricated or employee-authored reviews presented as independent** (§465.2, §465.5).
5. **Moderation limited to the uniform, content-based safe harbor** in [KB-REP-019] — never
   sentiment-based.
6. **Disclosure of any material connection** — an employee, owner, or relative who genuinely
   reviews the business discloses the relationship in the review itself.

**[KB-REP-022]** This flow is deliberately the SAME shape as `never-do.md` #1 and #2's ACCEPT
patterns and `escalation-triggers.md`/`response-templates-by-severity.md`'s "ask everybody the
same way, every time, no strings" framing — this file describes the acquisition-side mechanics
that produce that shape; the other files describe the response-drafting discipline once reviews
exist. They are one coherent doctrine viewed from two ends of the same process, not two competing
rule sets.

## 6. Platform-specific caveat

**[KB-REP-023]** The FTC rule is a legal floor that applies regardless of platform; it does NOT
override a stricter individual platform policy. Yelp, per `platform-review-policies.md`
[KB-REP-006], instructs businesses not to solicit reviews at all — stricter than the FTC floor,
which only bans incentivized/gated solicitation, not solicitation itself. A compliant flow must
satisfy the FTC rule AND whichever individual platform's own rule is stricter for that platform.

## Contractor bend

The FTC rule reads like a document written for e-commerce platforms with thousands of reviews and
automated moderation pipelines — the owner-operator residential-remodeling GC archetype (whose
relevant end-customer persona is `shared/homeowner-buyer-psychology.md`;
`shared/contractor-buyer-psychology.md` is a different, B2B software-buyer persona) has neither. In practice this means the *mechanism*
that gets a solo owner-operator or a small office team in trouble is almost never a sophisticated
review-suppression algorithm; it's a well-meaning, low-tech shortcut: the office manager glances at
how a job seemed to go and only sends the review-request text to the customers who seemed happy.
That is [KB-REP-018]'s prohibited shape, done by hand instead of by software, and it is just as
much a violation. The single sentence that keeps this buyer compliant without needing to memorize
six CFR sections: **send the same request, to every customer, the same way, every time — no
exceptions for the job that went sideways.**
