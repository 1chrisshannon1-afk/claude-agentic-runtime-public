# Landing Page Skeleton — Section-by-Section Structure

The canonical top-to-bottom structure for a marketing/landing page, ported from a vertical-agnostic
landing-page blueprint (internal doctrine, retrieved 2026-09-05) and adapted for a self-serve B2B
SaaS product rather than a local-service business booking calls. Each section has exactly one job.
Do not merge two jobs into one band — this is the single most load-bearing rule in the source
material and it survives the vertical swap unchanged.

## Before building: gather the inputs, never invent them

Per the source blueprint's own opening principle: "A landing page converts on specifics, not
adjectives" (internal doctrine, retrieved 2026-09-05). Before authoring any page, confirm:

1. **The single offer** this page exists to drive — e.g. a signup at a named tier (in whatever
   trial/card shape the company's own pack settles), a booking, a demo video, or a specific
   comparison. One page, one goal.
2. **Proof** — what's actually true today: real customer/beta-tester count if disclosed, the actual
   guarantee terms, the actual competitive facts already verified for this company (see the
   company's own pack/dossier for its own competitive-intel citations). Never invent a number (see
   `ANTI-PATTERNS.md` #3).
3. **Positioning constraints** — re-read the company's own never-claim list (see the company's own
   pack/dossier) before writing a single headline. It governs every word on this page.

If a required input is missing, the honest move is a `needs_manual_step`-style flag to the
requester, not a filled-in guess.

## The section skeleton (top to bottom)

### 1. Hero (above the fold)

One specific headline naming the outcome + audience, one supporting line, **one** primary CTA. See
`above-the-fold.md` for the full doctrine on this section — it is dense enough to warrant its own
file. No second competing CTA here (see `ANTI-PATTERNS.md` #7).

**Adapting the source pattern for a B2B SaaS with no physical location:** the blueprint's
local-service formula is "`<Outcome> in <Town>, <qualifier>`" (internal doctrine, retrieved
2026-09-05) — a company with no town to name should adapt the formula to "`<Outcome> for
<audience>`" using whichever settled positioning pitches the company's own pack/dossier documents
(e.g. a "speed/time saved" pitch for one buyer segment, a "trust/output quality" pitch for
another). Never combine multiple distinct pitches in one headline — segment by which page or
campaign the visitor arrived from.

### 2. Trust bar

A thin, scannable band of concrete, factual proof directly under the hero. The source pattern:
"star rating + review count, 'X years in <Town>', key credentials/affiliations, financing available"
(internal doctrine, retrieved 2026-09-05) — adapt this to whatever is REAL today for the company
under review: guarantee terms, real beta-tester feedback if disclosed, specific competitive facts
the company can defend (see the company's own pack/dossier for its own pricing/competitive source
of truth) — never an invented rating or review count. See `trust-and-social-proof.md` for the full
doctrine on what's usable here today.

### 3. Services / what you get

3–5 offerings as a scannable row, each a short benefit-led label plus one line — never an
equal-weight four-icon grid with generic labels (see `ANTI-PATTERNS.md` #6). This section should
lead with whatever actually differentiates the specific product under review (see the company's own
pack/dossier for its real differentiators) — framed as outcomes, never as a bare feature-name list.

### 4. Proof / testimonials

Real customer quotes with attribution if available; an honest, real aggregate stat if not — never an
invented quote (see `ANTI-PATTERNS.md` #3). An early-stage company's honest current position is
often: this section may legitimately be thinner or reframed around specific, checkable claims (a
real competitive teardown fact, a real guarantee, real pricing transparency) rather than customer
testimonials that don't exist yet. Thin-but-honest beats padded-but-fake every time this gets
reviewed.

### 5. Pricing snapshot / primary CTA repeat

For a SaaS product (unlike the source blueprint's local-service "restate the offer" band), this is
often where the tier ladder itself, or a link to the full pricing page, belongs — paired with the
same primary CTA verb as the hero. See `pricing-page-doctrine.md` for the full doctrine on the
pricing surface itself. This is the conversion moment: per the source material's spatial-composition
guidance, give it "generous padding" and reserve the accent color for here and the hero, used
sparingly elsewhere (internal doctrine, retrieved 2026-09-05).

### 6. FAQ / objection-handling

Not in the original local-service blueprint (which closes on logistics/NAP for a physical
business), but load-bearing for a considered B2B SaaS purchase from a skeptical buyer. Address the
real objections a software-burned buyer will have — e.g. "what happens to my data if I cancel," "is
this another tool I have to babysit," "what if the AI gets it wrong" — answered honestly, and never
with a claim the company's own never-claim list forbids (see the company's own pack/dossier, e.g. an
accuracy guarantee where one is banned).

### 7. Footer / logistics

Contact path, legal links, and the primary action repeated once more. Footer is theme-level in the
source material's own CMS context; for a static site this still means: don't rebuild trust-bar
content here, just make the primary action reachable one more time for a visitor who scrolled all
the way down still undecided.

## Conversion rules that apply to every section (portable mechanism)

- **One primary action, repeated identically.** Hero CTA == mid-page CTA == footer CTA — same verb,
  same destination. A secondary, visually subordinate action (e.g., "watch the demo" as a text link)
  is fine; two co-equal actions are not (internal doctrine, retrieved 2026-09-05; see
  `ANTI-PATTERNS.md` #7).
- **Make the primary action frictionless.** The source rule that "a contact form that emails into
  the void converts worse than a direct booking/phone link" (internal doctrine, retrieved
  2026-09-05) maps directly to a self-serve SaaS product: a direct "start now" signup button beats a
  "request more info" form every time a low-friction path is available (see `ANTI-PATTERNS.md` #9
  and `forms-and-signup-friction.md`).
- **Trust before ask.** Proof appears before the mid-page CTA, not after (internal doctrine,
  retrieved 2026-09-05).
- **Mobile-first reality.** The source material's grounding is local-intent mobile traffic; a
  company's own buyer research may independently confirm the same constraint from a completely
  different angle — see the Buyer-segment bend below for the case of a B2B software buyer sold to
  trade-business owners. Assume mobile is the primary device, not desktop, whenever the target
  buyer's own behavior confirms it.
- **Specificity over adjectives.** Never write what the blueprint calls a page that "could describe
  any medical-office or service-business website built in the last five years" (internal doctrine,
  retrieved 2026-09-05) — sharpen every claim until it's specific to the company under review and
  checkable against its own positioning doc.

## Aesthetic direction discipline

Before authoring any page, state the aesthetic direction in one sentence and hold every choice
against it (internal doctrine, retrieved 2026-09-05). That sentence should reflect the actual target
audience, not a generic SaaS tone — e.g., for a trade-buyer audience, something closer to "confident
and plainspoken: no jargon, real numbers, looks built by people who've been on a job site" than
"clean modern SaaS minimalism," which is indistinguishable from every competitor's page. Typography,
color (three roles: background/text/accent, never a timid four-pastel palette or a purple gradient —
see `brand/ANTI-PATTERNS.md`'s purple-gradient item), and motion all get filtered through that
sentence, per `brand/visual-hierarchy.md`'s full pre-authoring checklist (internal doctrine,
retrieved 2026-09-05).

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

The source blueprint assumes a local-service business (dentist, HVAC company) where the visitor's
next action is booking an appointment or calling — a single, physical-world action. A B2B SaaS
visitor instead has to make a considered software-purchase decision, so the skeleton bends in three
ways:

1. **Add the FAQ/objection-handling section** (not in the source blueprint) — a local-service
   visitor rarely needs persuading that a dentist appointment is safe to book; a software-burned
   contractor needs his specific fears named and answered before he'll hand over a card number.
2. **The mid-page CTA repeat is often a pricing snapshot, not just a restated offer band** — because
   for this buyer, "how much and what do I actually get" IS the offer, not a separate step later.
   Hiding the ladder behind more scrolling costs trust with a buyer who has been quoted opaque
   enterprise pricing before and hated it.
3. **Assume he's reading on his phone, one-handed, between jobs** — not out of the source
   material's local-SEO logic (mobile-intent local search), but because this buyer's profile is
   phone-first, in a truck (`shared/contractor-buyer-psychology.md`, behavioral facts 1–2). The
   practical result is identical either way: CTA thumb-reachable, hero short, no dense paragraph
   walls, phone-legible type sizes — but confirm the CTA is a signup/demo action for the B2B
   software product being sold, never a `tel:` link. This
   bend describes a B2B-software-buyer persona (`shared/contractor-buyer-psychology.md`), not a
   home-services company's own landing page — a `local_service` company selling directly to
   homeowners has a real phone number and a `tel:` CTA is often exactly right there (see
   `shared/homeowner-buyer-psychology.md`); do not apply this bend's "never a `tel:` link" rule to
   that different persona.
