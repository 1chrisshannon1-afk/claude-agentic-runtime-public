# Conversion Anti-Patterns — Never Recommend These

A conversion-architect reviewing any company's landing page, pricing page, or signup flow must
NEVER recommend the items below, regardless of the fact that a competitor uses them, that they
"technically lift conversion in some study," or that fixing something else is harder. Each entry
states the pattern, why it's out, and its source class.

## 1. Fake urgency / manufactured scarcity

**Never recommend:** countdown timers on evergreen offers, "X people are viewing this plan right
now" widgets with no real live count behind them, "price goes up at midnight" banners with no real
pricing-change event scheduled, "only 3 spots left" claims for an unlimited-capacity SaaS signup.

**Why:** Every company's own never-claim list (see the company's own pack/dossier) should be
unambiguous about fabrication — forbidding fabricated testimonials, statistics, capability claims,
or pricing sources not already true of the shipped product is a hard constraint on all copy. Fake
urgency is the pricing-page/CTA-band version of the same fabrication a never-claim list already
forbids for testimonials and stats — there is no carve-out for urgency mechanics. It is also a
buyer-specific failure mode for a buyer who has been burned by software before (see each file's
buyer-segment bend): a countdown timer on a B2B tool reads as exactly the kind of manipulative SaaS
trick that confirms his priors against buying software at all.

**Reject example:** "Add a banner: 'Founding member pricing ends in 48 hours!' that resets every
time someone visits." — This is fabricated urgency; there is no real pricing deadline. REJECTED.

**Pass example:** "The 30-day money-back guarantee has a real, enforced 30-day window from the
charge date." — Real, verifiable, time-bound. PASS.

## 2. Countdown timers

**Never recommend:** any JS countdown widget on a marketing or pricing page, real deadline or not,
unless the deadline is (a) genuinely operationally true, (b) identical for every visitor (not
reset per-session), and (c) tied to a real, cited business event (e.g., an actual price increase
already scheduled and announced). Per-visitor-reset countdown timers are always fake and always
out, full stop — no exception clause applies to that specific mechanic.

**Why:** Per-session-reset timers are the canonical "AI-template SaaS" tell — see the
purple-gradient/generic-template anti-pattern below (#6); this is the same signal in a different
widget. They also directly collide with the honest-market-risks discipline any positioning doc
should carry, which warns against a demo said to be persuasive on a first look but that doesn't
hold up on real, sustained trust (internal doctrine, retrieved 2026-09-05) — a fake countdown is
itself the same demo-well/trust-never trick.

## 3. Fake or unverifiable social proof

**Never recommend:** invented review counts, invented "trusted by N customers" numbers, stock
logos of companies that aren't real customers, a 5-star badge with no linked, checkable review
source, an "as seen in" bar naming outlets that never covered the product, synthetic
"John D., Denver CO" testimonials with no real attributable person behind them.

**Why:** Directly named in the landing-page blueprint's own anti-pattern table — "Invented stats
('trusted by 10,000 customers')... Fabrication; legal + trust risk. Use only confirmed numbers"
(internal doctrine, ported from a prior CRO engagement, retrieved 2026-09-05). This mechanism also
has a primary regulatory source in the US: the FTC's Consumer Reviews and Testimonials rule (16
CFR Part 465, 2024) bans fabricated or non-representative reviews/testimonials outright, and the
FTC's Endorsement Guides (16 CFR Part 255) separately govern disclosure requirements for real
endorsements — UNVERIFIED — seeded, needs derivation (asserted from general knowledge of these
rules; the FTC's own pages were not fetched this pass — re-verify directly before citing either as
`(official)` in a review, and correct the CFR part/title above if a live read finds them wrong).
Any company's own never-claim list should reinforce both with the identical prohibition on
fabricated testimonials. See `trust-and-social-proof.md` for what counts as real proof a company
can actually use today — an early-stage company's honest position is usually: no meaningful public
review corpus yet, so early-stage proof mechanics are different, not faked-up versions of scale
proof.

**Reject example:** "Put 'Trusted by 500+ customers' in the hero — round up from our beta cohort so
it sounds credible." — Fabricated number. REJECTED, regardless of how close the real number is.

**Pass example:** "Name the real number of beta testers if disclosed, or omit the claim entirely
until there is a real number worth stating." — PASS.

## 4. Hidden or "contact us for pricing" pricing on a self-serve product

**Never recommend:** gating a self-serve tier ladder behind a form, sales call, or
chat-to-reveal-price pattern for a product actually sold self-serve at a published SaaS price
point, not an enterprise deal requiring a sales-assisted quote.

**Why:** NN/g's own pricing-page research is explicit that transparent pricing builds trust and
speeds decision-making (official, NN/g-sourced synthesis via third-party aggregation, retrieved
2026-09-05 — see `pricing-page-doctrine.md` for the full citation chain). It also directly
contradicts any pitch built on the contrast "we are NOT that kind of opaque, gated product" against
a named competitor whose higher tiers are sales-assisted with no public price (see the company's
own pack/dossier for the competitive citation) — hiding price would hand away a real, verified
competitive advantage where that contrast is true.

**Buyer-segment bend (B2B software sold to trade-business owners; persona:
`shared/contractor-buyer-psychology.md`):** for a phone-first tradesperson buyer in a truck, this is
even more binding — he has zero patience for "book a call to find out the price." He wants the
number, now, on his phone screen. Gating price here is not just against best practice; it is against
this buyer's entire mode of operating.

## 5. Mandatory demo/sales-call gate before any self-serve trial or signup

**Never recommend:** forcing a "book a demo" step before a self-serve tier can be tried or bought.

**Why:** Same principle as #4 — a self-serve SaaS product priced and shaped with a real published
ladder is not an enterprise sale. A mandatory-demo gate adds friction with no offsetting trust
benefit for a buyer who is price-sensitive and time-poor. Where a company's own settled model (see
the company's own pack/dossier) already describes a self-serve risk-reversal signup (e.g., card
required at signup, charged day one, money-back guarantee) rather than a sales-qualified one, a
mandatory demo gate directly contradicts that settled model. (This does not forbid an OPTIONAL
"talk to us first" link for a genuinely large/enterprise-tier prospect — it forbids making that the
only path in.)

## 6. Purple-gradient, generic-AI-template hero aesthetic

**Never recommend:** a `#6366f1`→`#8b5cf6`-style purple/violet gradient hero, a generic Inter/
Roboto/system-ui display heading with no character, a stock photo of smiling strangers in a
generic office, an equal-weight four-icon "features" grid that says nothing specific to this
product, drop shadows on every element, or three-plus accent colors at equal weight.

**Why:** Verbatim anti-pattern table (internal doctrine, retrieved 2026-09-05): "Generic gradient
hero... Indistinguishable from 10,000 SaaS landing pages," "Stock photo of smiling professionals in
a generic office... Signals absence of a real brand," "Equal-weight four-column icon grids below
the hero... Cookie-cutter 'features' layout; says nothing specific." This is exactly the
"AI-generated template" signal already documented in `brand/ANTI-PATTERNS.md`'s purple-gradient
item (same internal-doctrine source, retrieved 2026-09-05) — see that file rather than treating
this as a second, independently-sourced claim. A skeptical, software-burned buyer is the single
worst audience to show a page that visually announces itself as templated, low-effort, or
interchangeable with every other SaaS pitch he's already ignored.

**Buyer-segment bend (B2B software sold to trade-business owners; persona:
`shared/contractor-buyer-psychology.md`):** this buyer's mental model of software is "another guy
selling me something that doesn't work in the field." A generic AI-template look actively confirms
that prior before a single word of copy is read. The visual direction has to look like it was built
by people who understand a real trade business — not by a template generator.

## 7. Two co-equal competing CTAs in the hero

**Never recommend:** two buttons of equal visual weight in the hero pushing different actions (e.g.
"Start Free Trial" and "Book a Demo" both styled as primary buttons, same size, same prominence).

**Why:** Named directly in the landing-page blueprint's anti-pattern table: "Two co-equal CTAs in
the hero... Splits intent; conversion drops. One primary action" (internal doctrine, retrieved
2026-09-05). One primary action, repeated identically down the page, is the blueprint's first
conversion rule. A secondary, visually subordinate action (e.g., "See how it works" as a text link
under a solid primary button) is fine; two equal buttons are not.

## 8. Long "about us" or company-story wall before any CTA

**Never recommend:** a lengthy founder-story, mission-statement, or "who we are" section placed
above or between the hero and the first CTA repeat.

**Why:** Named directly in the blueprint's anti-pattern table: "A long 'About us' wall before any
CTA... Buries the action. Lead with the offer; bio comes later or on another page" (internal
doctrine, retrieved 2026-09-05). Company story is legitimate content — it just belongs on an About
page, not gating the primary conversion path.

## 9. Contact-form-only path with no phone/direct alternative for a high-intent visitor

**Never recommend:** routing every conversion path through a "contact us and someone will reach
out" form with no faster alternative (a booking link, a direct trial-start button, a visible phone
number) when a lower-friction path exists.

**Why:** Named directly in the blueprint's anti-pattern table: "Contact-form-only with no phone/
booking... Adds friction for a high-intent local visitor. Always offer call/book" (internal
doctrine, retrieved 2026-09-05). For a self-serve SaaS product specifically this maps to: never
make "request a demo" the ONLY way to start — the self-serve signup/trial path must always be the
default, visible, low-friction option (see `forms-and-signup-friction.md`).

**Buyer-segment note:** the mechanism generalizes even for a company that isn't a local-service
business with a phone number to answer — the point is the same: don't force a high-intent visitor
into the slowest, least certain path when a direct one exists.

## 10. Deceptive cancel-flow friction ("email to cancel," hidden cancel button, retention dark patterns)

**Never recommend:** requiring an email or phone call to cancel, burying the cancel action behind
multiple confirm-dialog dark patterns, or any pattern that fails ROSCA's simple-cancellation
requirement (see `content/ad-copy-doctrine.md` §8, item 4 (ROSCA)).

**Why:** A money-back guarantee is worth little if canceling to claim it is itself hard (internal
doctrine, retrieved 2026-09-05) — any company's own risk-reversal model, where one exists (see the
company's own pack/dossier), should state friction-free cancellation as an explicit condition of the
offer, never an email-to-cancel or buried-button pattern. This is both a legal exposure and a direct
contradiction of the trust story a
company is trying to build with a skeptical, once-burned buyer — a hard cancel flow is the single
fastest way to confirm his fear that this is "another software trap." On the legal half: ROSCA
(the Restore Online Shoppers' Confidence Act) remains in force and independently enforced regardless
of the FTC's own since-vacated "click to cancel" rule — see `content/ad-copy-doctrine.md` §8, item 4
(ROSCA) for the citation chain; never imply the vacated FTC rule itself is what's in force.

## 11. Silently applying assumed defaults without accept-or-change disclosure, anywhere pricing/scope numbers reach the visitor

**Never recommend:** any marketing or in-app surface that presents an AI-filled or ruled-default
number as if it were the user's own exact input, with no visible "we assumed X — accept or change"
affordance.

**Why:** Any input a product's own engine fills with a ruled default must be presented to the user
as accept-or-change, never silently applied and never described in copy as if the user's exact
inputs drove every number without review (internal doctrine, retrieved 2026-09-05 — see the
company's own pack/dossier for the specific ruling, where one exists). This binds conversion
surfaces too, not just the product itself — e.g., never build a pricing calculator or ROI widget
that silently assumes inputs and presents a headline number as if the visitor supplied every
variable.

## 12. Any claim from the never-claim list, restated as a "growth hack"

**Never recommend**, even reframed as a conversion tactic, any claim a company's own never-claim
list forbids (see the company's own pack/dossier for the specific list — e.g. capability claims
that overstate what actually ships, accuracy guarantees like "always accurate, guaranteed correct,"
or export/deliverable claims for something that doesn't ship). A conversion-architect does not get
a carve-out to inflate a claim "for the landing page only" — a never-claim list applies to every
governed copy surface, landing pages included.

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

None of the above softens for a phone-first tradesperson buyer — if anything every one of them is
MORE damaging to a mid-size trade-business archetype than to a typical SaaS buyer, because he
arrives with a stronger prior of distrust ("burned by software before") and less patience for
figuring out if a claim is real. A sharp trade buyer notices a fake countdown timer or a stock
photo faster than a tech-fluent SaaS buyer does — construction is a small-world, reputation-driven
industry, and someone who feels tricked by marketing tells his crew, his supplier rep, and the guy
at the lumber yard. The cost of one of these anti-patterns firing on this audience is not "lower
conversion," it's "burned bridge in a network that talks to itself."
