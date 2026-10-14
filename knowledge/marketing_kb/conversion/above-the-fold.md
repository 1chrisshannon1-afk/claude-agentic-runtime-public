# Above-the-Fold Doctrine

What has to be true in the first viewport, and how much weight the evidence actually says the fold
carries — not folklore ("nobody scrolls"), but the real, cited numbers.

## What the evidence actually says about the fold

The "nobody scrolls below the fold" claim is often overstated in marketing folklore. The real,
cited research is more specific and slightly less extreme than that:

- **Content 100px above the fold gets 102% more eye-tracking fixations than content 100px below
  it** — a real, sharp attention drop at the fold boundary, not a gradual taper (official, NN/g
  eye-tracking study across 57,453 fixations, cited in "The Fold Manifesto," nngroup.com, original
  study 2015 / synthesis retrieved 2026-09-05).
- **Ads just above the fold get 73% viewability vs. 44% just below** — a separate, converging
  measurement from a Google display-advertising study (official/third-party synthesis, cited in the
  same NN/g piece, retrieved 2026-09-05).
- **NN/g's own synthesis of both studies puts the average above/below-fold attention gap at ~84%**
  (official, nngroup.com "The Fold Manifesto," retrieved 2026-09-05).
- **Users spend roughly 57% of page-viewing time above the fold, and ~74% of viewing time within
  the first two screenfuls (~2160px)** on a typical scroll-tracking study (official, NN/g scrolling-
  and-attention research, retrieved 2026-09-05).

**What this means in practice:** the fold is not a hard wall — people do scroll, and roughly a
quarter of attention lives below the first two screenfuls. But it is a real, measured, steep
attention cliff. Anything that MUST register — the offer, the audience, the primary CTA — belongs
above it. Anything that can wait for a motivated scroller (deep feature detail, FAQ, footer
logistics) can safely live below it.

## The 5-second test doctrine

The 5-second test is NN/g's own standard method for checking whether a hero/above-the-fold design
communicates before conscious, effortful reading kicks in: show the design for exactly 5 seconds,
hide it, then ask what the viewer remembers and understood (official, nngroup.com, retrieved
2026-09-05). "Five seconds isolates the automatic layer of cognition" — whatever survives that
window is the strongest signal actually present in the design (official, same source).

**How to apply it to any company's hero, concretely:** show a reviewer (or a real test subject)
only the hero section for 5 seconds, then ask three questions:

1. **What does this company do?** (Tests the headline + subhead's clarity — not "what industry,"
   but "what does it actually do for me.")
2. **Who is this for?** (Tests whether the audience is legible — the reference buyer for this
   product, per the company's own pack/dossier, should recognize himself, not read something aimed
   at a different buyer entirely.)
3. **What am I supposed to do next?** (Tests the CTA's visibility and specificity — "Start Now"
   with no context fails this; a clear, singular next action passes.)

**Pass/reject examples, worked for a B2B SaaS selling construction-estimating software to
contractors:**

- **REJECT:** A hero reading "AI-Powered Construction Intelligence Platform" with a "Get Started"
  button. A 5-second viewer cannot answer "what does this do" (jargon, no concrete outcome) or "who
  is this for" (could be anyone in construction, including a homeowner or an enterprise IT buyer).
- **PASS:** A hero reading "Real line items from a job description — a work order your subs can run
  on, in minutes" with a "Start your estimate" button. A 5-second viewer can answer all three
  questions: what (estimates that produce real, usable work orders), who (a contractor who deals
  with subs), what next (start an estimate). (The specific speed figure and any photo-derived-input
  capability claim are company-specific — see the company's own pack/dossier for what it can
  actually claim before using either in copy.)

## What must be true above the fold, non-negotiably

Per the landing-page-skeleton doctrine (`landing-page-skeleton.md`), the hero carries:

1. **One specific headline** naming the outcome and the audience — never a generic adjective-only
   claim (internal doctrine, retrieved 2026-09-05).
2. **One supporting subhead** that adds specificity or a differentiator — not a restatement of the
   headline in different words.
3. **Exactly one primary CTA**, visually dominant, no co-equal second button (see
   `ANTI-PATTERNS.md` #7).
4. **No fabricated urgency, no fake proof widget** — see `ANTI-PATTERNS.md` #1–#3. If real proof is
   available and light enough to fit, a single factual trust line (e.g. a real guarantee mention)
   can sit in the hero or immediately below it, but it must never crowd out the headline's job.

## What can safely wait below the fold

- Detailed feature breakdowns, FAQ, testimonials/proof depth, and footer/logistics can all live
  below the fold — the ~74%-of-attention-in-first-two-screenfuls finding (official, NN/g, retrieved
  2026-09-05) means a motivated visitor will reach the second screenful, so this content is not
  wasted, just correctly deprioritized versus the hero's job.
- The mistake to avoid is not "having content below the fold" (normal and fine) — it's putting
  something that MUST register (the offer, the audience fit, the CTA) below the cliff where 84%
  less attention reaches it (official synthesis, NN/g, retrieved 2026-09-05).

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

The 5-second-test framing gets sharper, not softer, for a trade-business buyer. A tech-fluent SaaS
evaluator will often scroll further out of professional habit — reading a pricing page top to
bottom is part of their job. A working tradesperson skimming on his phone between jobs will give a
page closer to the literal 5 seconds than a SaaS buyer would, and if the hero doesn't answer "what
does this do for ME, a guy who runs jobs in the field" in that window, he's gone — back to the group
text where someone recommended a competitor, or back to whatever spreadsheet he already uses. Two
concrete adjustments:

1. **Skip industry jargon entirely in the hero.** "AI-powered construction intelligence platform"
   fails the 5-second test for this buyer even though it might pass for a VC skimming a pitch deck.
   Use plain, checkable language: what does it produce (real line items, a work order), how fast,
   and for whom (a contractor who deals with subs and bids jobs).
2. **The audience-fit question ("who is this for") carries extra weight for this buyer specifically**
   because his prior is "this software wasn't built for someone like me"
   (`shared/contractor-buyer-psychology.md` behavioral fact 3, "burned by software before" — a
   documented pattern of research fatigue and prior tools that overpromised or that his crew refused
   to use; see the company's own pack/dossier for its own specific buyer archetype). If the hero
   visual or copy reads as built for a bigger, more corporate operation,
   he self-selects out in the first two seconds, well before the 5-second window even completes.
