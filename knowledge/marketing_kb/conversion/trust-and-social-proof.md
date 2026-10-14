# Trust and Social Proof

What counts as real, usable proof for a company today, what counts as fabricated proof (never
recommended — see `ANTI-PATTERNS.md` #3), and where proof has to sit on the page to actually change
a visitor's decision.

## What the evidence says about trust signals and placement

- **19% of shoppers abandon specifically because they don't trust a site with payment
  information** (official, Baymard-grounded research synthesis, retrieved 2026-09-05).
- **Security/trust badges placed directly at the payment/checkout moment lift conversion 15–30% for
  lesser-known brands**; the same badge type in a less prominent position (e.g., a footer, a general
  "about" page) shows a materially weaker effect (third-party synthesis of Baymard-grounded
  research, retrieved 2026-09-05). **Placement is the active ingredient, not the badge's mere
  existence** — badges belong near the payment/card field, not scattered above the fold or on
  unrelated pages.
- **More is not better: past 3–4 distinct badge types, "badge bloat" can actually decrease
  conversion 5–8% by signaling desperation rather than trustworthiness** (third-party synthesis,
  retrieved 2026-09-05). This is a real numeric gate: a page with seven different trust badges
  crammed together is not "extra safe," it's a worse-performing page than one with three well-chosen
  ones.
- **18% of users explicitly look for a security indicator before entering card details**
  (third-party synthesis, retrieved 2026-09-05) — confirming that SOME visible trust signal near
  payment is worth having; the finding above just bounds how many.

**Pass/reject examples, placement-specific:**

- **REJECT:** A row of 6 security/payment badges in the site footer, none near the actual card-entry
  field on the signup form. Badge bloat risk (past the 3–4 threshold) AND wrong placement (footer,
  not at the moment of payment friction) — REJECTED on both counts.
- **PASS:** A specific, real money-back guarantee stated once, directly beside the card field on the
  signup form, plus the actual payment processor's recognizable badge (e.g., Stripe) — 2 trust
  elements, correctly placed. PASS.

## What counts as real proof for an early-stage company, today

Many early-stage companies are pre-convergence: real validation is only a handful of real customers
actually using the product, and that validation does not fully exist yet at customer-testimonial
scale (see the company's own pack/dossier for its own honest-market-risks assessment). A
conversion-architect must not paper over this by inventing scale-proof that isn't there (see
`ANTI-PATTERNS.md` #3). What IS typically real and usable even at this stage:

1. **Verified competitive facts.** A real, hands-on, dated, cited competitive teardown (see the
   company's own pack/dossier for its own competitive-intel citations) establishes real, checkable
   contrasts with a named competitor. Any specific number comparison drawn from such a teardown
   functions as a form of proof-by-specificity that a vague superiority claim never can. Specificity
   itself is a trust signal: a claim precise enough to be falsifiable reads as more credible than a
   vague one, even before the visitor checks it.
2. **The guarantee itself, stated with its real terms.** A real, unconditional guarantee (e.g. an
   N-day money-back guarantee, no conditions — see the company's own pack/dossier for its actual
   terms) is real, verifiable risk-reversal — arguably the single strongest piece of proof a young
   company has, because it requires no customer base to be true.
3. **Transparent, public pricing itself functions as a trust signal** in a category where a named
   competitor gates its higher tiers behind "contact sales" (see the company's own pack/dossier for
   the competitive citation, cross-referenced against NN/g's transparency finding in
   `pricing-page-doctrine.md`). Showing the price is itself a proof point, not just a UX nicety.
4. **Real beta-tester numbers, if and when disclosed** — but only the real count, and only once a
   real count exists to disclose (see the company's own pack/dossier for its own explicit ban on
   inflating this number, `ANTI-PATTERNS.md` #3).
5. **Demo video content**, where a company's own pricing/positioning doc names it as load-bearing —
   most commonly where no free trial exists to let the product persuade a visitor on its own
   (internal doctrine, retrieved 2026-09-05), a full, real, end-to-end demo becomes load-bearing
   proof in the trial's place (see the company's own pack/dossier for whether this applies). A real, full, honest
   walkthrough of a real job is proof-by-demonstration and does not require fabricating anything —
   but it must be an honest demo, never edited to imply a capability that doesn't ship (cross-check
   every claim made on camera against the never-claim list).

## What is explicitly NOT available as proof yet, and must not be faked

- Customer testimonials at meaningful volume/scale, before they genuinely exist (see the company's
  own pack/dossier for its own honest-market-risks assessment).
- A large public review-platform footprint (G2, Capterra star ratings) — do not fabricate or imply
  one exists if it doesn't; if a small real number of reviews exists, use only that real number.
- Case studies with named, attributable customers, unless a real customer has actually agreed to be
  named and quoted.
- Any accuracy claim framed as guaranteed or proven at scale, wherever a company's own never-claim
  list forbids it outright regardless of proof status (see the company's own pack/dossier).

## Reviews and social proof — the honest framing for an early-stage product

Rather than manufacturing the appearance of scale, the honest and still-persuasive move for an
early-stage B2B product is to lean on **specificity and transparency** as the proof mechanism
instead of **volume**: a real, detailed, dated competitive teardown; a real, unconditional
guarantee; real, transparent pricing; an honest demo of a real job. This is not a weaker
substitute for testimonials — for a skeptical buyer specifically, an overly polished page full of
suspiciously perfect five-star quotes can read as LESS credible than an honest, specific,
verifiable claim (see the buyer-segment bend below).

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

1. **This buyer is unusually resistant to generic social proof and unusually responsive to specific,
   checkable claims.** A vague "trusted by contractors nationwide" badge does nothing for someone
   who has been burned by software before — it's exactly the kind of thing every SaaS pitch says.
   What lands instead: a specific, falsifiable fact he could go verify himself if he wanted to (e.g.
   a real, checkable seat-count/price contrast against a named competitor — see the company's own
   pack/dossier for its own real numbers, not a vibe).
2. **Peer proof matters more than platform proof for this buyer, but it has to be REAL.** Trade
   networks are reputation-driven and small-world — a genuine quote from a real tradesperson who
   sounds like him (uses trade language, names a real project type) will do more work than a generic
   "5.0 stars, 200 reviews" widget, precisely because it reads as coming from someone in his world
   rather than a marketing department. The instruction here is not "fabricate a folksy-sounding
   quote" (still forbidden, `ANTI-PATTERNS.md` #3) — it's "when real testimonials do exist, don't
   sand off the trade-specific texture that makes them credible to this specific audience."
3. **The guarantee is the single most important proof point for this exact buyer**, more than for a
   typical SaaS evaluator, because it directly answers his specific fear (getting locked into
   something that doesn't work and can't be undone). Make sure it's never buried — state it plainly,
   near the price and near the card field, in his language ("try it, and if it doesn't work for your
   business, get your money back — no calls, no hassle"), not legal boilerplate phrasing.
