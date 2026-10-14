# Pricing Page Doctrine

How a self-serve SaaS pricing page should present its tier ladder, add-ons, and the "pays for
itself" frame, grounded in NN/g's pricing-page research and reconciled against a company's own
canonical pricing decisions. This file does not decide what the prices ARE for any given company —
that is each company's own pricing source-of-truth doc's job exclusively (see the company's own
pack/dossier) — it governs how an already-decided ladder gets presented so a skeptical buyer trusts
it.

## What the evidence says about pricing-page UX

- **Transparent pricing builds trust and speeds decision-making, and is especially load-bearing for
  B2B** — "revealing price on your B2B website is one way to earn people's trust... people view
  companies that hide costs as being evasive and untrustworthy" (official, "State the Price to Give
  B2B Sites a Competitive Advantage," nngroup.com, retrieved 2026-09-05). This directly rules out
  any "contact us" gate on a company's own self-serve tiers (see `ANTI-PATTERNS.md` #4).
- **UNVERIFIED: a pricing headline should speak to business outcomes before mentioning tiers or
  cost, correlating with users staying on the page longer.** This tracks NN/g's general
  outcomes-over-features design guidance, but no specific NN/g pricing-page article naming this
  exact headline claim was found on re-verification (retrieved 2026-09-05) — treat as a reasonable
  practice, not a cited finding, until a specific source is located.
- **UNVERIFIED: most SaaS pricing pages use 3–4 plans**, typically entry/standard/advanced with one
  clearly highlighted best-fit option. No specific NN/g source for this exact figure was found on
  re-verification (retrieved 2026-09-05). Check the company's own pack/dossier for its own real tier
  count and structure — the actual tier count for any given company is a real, cited fact
  independent of whether "3-4 is the norm" holds as a general claim.
- **UNVERIFIED: group related features under scannable structure; use checkmarks, concise labels,
  and tooltips rather than crowding the table.** Widely-repeated pricing-page UX advice, but no
  specific NN/g article was found on re-verification (retrieved 2026-09-05) to cite by name.
- **UNVERIFIED: CTA buttons should be visually prominent but not desperate-looking** — sized to
  stand out, differentiated by tier emphasis, without reading as pushy. NN/g's "'Get Started' Stops
  Users" (nngroup.com) addresses generic CTA copy, not button prominence/sizing specifically, so it
  does not cleanly support this claim; no closer match was found on re-verification (retrieved
  2026-09-05).

## Check the company's own pricing gate before treating any pricing page as ready to publish

A company's pricing source-of-truth doc (see the company's own pack/dossier) may name a blocking
gate on publishing pricing copy as final — e.g. a margin/COGS measurement that must land before
public margin-adjacent claims can be trusted, or a gap between a "ruled end-state" ladder and what
is actually live in the running product. A conversion-architect reviewing pricing-page copy must
check that gate's current status before treating any margin-derived or forward-looking pricing claim
as settled, and must never imply a specific margin number in customer-facing copy regardless
(margin is an internal economics fact, never a customer-facing claim in any case). Reconcile against
the live CODE, not just a doc, whenever a doc's own status banner flags a doc-vs-code gap.

## The pays-for-itself frame — a portable lead-in pattern

A recurring, portable framing pattern for a considered B2B purchase (internal doctrine, retrieved
2026-09-05): **the product pays for itself on the first job it saves or wins — a revenue-moment
tool, never a monthly-software-cost frame.** Where a company's own positioning doc states this as
its standing frame (see the company's own pack/dossier), the instruction is typically explicit:
every pricing section (static site and in-app) should carry this frame as its standing lead-in, not
bury it in a single A/B variant. A pricing-page review should FAIL any version that presents the
tiers as a bare feature/price table with no framing sentence connecting the price to a real job win
or a real time saved.

**UNVERIFIED — seeded:** a claim that a category-standard cost-estimation tool's own buyers
routinely pay well above what a bare feature-price comparison would predict, because the tool sits
on the money moment rather than being a nice-to-have organize tool, was carried in this file as
real-world precedent for the mechanism above. The original figure and its sourcing were tied to one
company's own research and were moved to that company's own pack/dossier; no named vendor source
exists in this corpus. Treat the mechanism itself (grounded in the B2B purchase-psychology
reasoning above) as the doctrine, and re-derive any real-world precedent fresh, with a named
source, before citing one in a review.

## Anti-comparison-trap: don't let this become a features checklist war

NN/g's "group related features under collapsible sections... use checkmarks, concise labels" advice
(official, retrieved 2026-09-05) is a caution against the common SaaS-pricing-page failure mode of a
20-row feature-comparison grid that overwhelms rather than clarifies. For any multi-tier ladder, the
real differentiators worth surfacing prominently are the ones the company's own pricing
source-of-truth doc names as the actual upsell drivers (see the company's own pack/dossier) —
everything else (support tier, file storage) can live in a lower-emphasis row or an expandable
"full details" table.

## Attack lines — verify before use, never assume

Comparative competitive claims (e.g. "our tier includes N seats, theirs includes M at a higher
price," or "our guarantee is stronger than category norms") are powerful conversion copy exactly
because they are specific and falsifiable — but they must be independently verified and dated, not
assumed to still be true. Check the company's own pack/dossier for its own verified, dated
competitive attack lines before using any in pricing-adjacent copy, and never invent or round a
competitive number to make a claim land better.

**Explicitly banned pattern: an unsourced conversion-lift multiplier presented as fact** (e.g. "same
day X closes N times more often"). Adversarially check any such multiplier before it enters copy —
if a specific one has already been checked and rejected for a given company, that rejection is
recorded in the company's own pack/dossier and must never be reintroduced. The honest substitute is
almost always available: ground the claim in the company's own real, sourced funnel data instead of
an unsourced industry multiplier (e.g. "you already paid $X for that lead — quote it before it goes
cold," where $X is a real, measured CAC figure for that specific company).

**For contractor/home-services companies specifically:** the widely repeated "same-day quoting
closes 1.5–2x" multiplier was adversarially checked (internal doctrine, retrieved 2026-09-05) and
found to be unsourced SEO folklore with no locatable primary source. Never use it in copy for a
contractor/home-services company, and treat any close variant of it (a specific multiplier tied to
response speed with no cited source) with the same suspicion until a new primary source postdating
this check is located.

## Reject / pass examples

- **REJECT:** "Estimate 2-3x faster close rates with same-day quoting." — An unsourced multiplier of
  exactly the banned-pattern shape above. REJECTED regardless of how compelling it sounds.
- **PASS:** "You already paid for that lead. Quote it before it goes cold." — Real, honest, grounded
  in the company's own CAC data, no fabricated multiplier.
- **REJECT:** A pricing page with "Contact Sales" as the only button on a tier the company's own
  ladder documents as self-serve. — Gating a self-serve tier behind a sales contact contradicts the
  ladder and NN/g's transparency finding. REJECTED.
- **PASS:** A pricing page where every tier shows its real monthly price, a "Start now" button, and
  a one-line note connecting price to the pays-for-itself frame ("less than the cost of one
  underbid job," for a construction-trades buyer). PASS.

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

Two adjustments beyond the general NN/g doctrine, specific to this buyer:

1. **Lead with the pays-for-itself frame even harder than the doctrine already requires.** A
   tech-fluent SaaS buyer mentally amortizes a monthly software cost against a budget line; a
   working tradesperson's own real behavior often does NOT include that math automatically
   (`shared/contractor-buyer-psychology.md` behavioral fact 4, "price-sensitive on subscription, not
   price-insensitive overall" — a monthly line-item reads as overhead to this buyer even when the
   identical dollar amount framed as a job-payoff would not; see the company's own pack/dossier for
   its own real pricing-objection evidence, where known). The
   pricing page has to do the math for him, visibly, in the price's immediate vicinity: connect the
   monthly number to "the cost of one bathroom fixture" or "less than one underbid job," not just as
   a nice framing line but as the primary persuasive mechanism on the page.
2. **Never assume he'll read a features-comparison table carefully.** The NN/g scannability
   guidance matters more here, not less — this buyer is evaluating on his phone, briefly, expecting
   to be tricked. A dense comparison grid reads as "the fine print where they hide the catch." Keep
   the visible tier cards to the handful of things that actually matter to him (usage quota, seats,
   "everything else you need is included") and put granular detail one click away for anyone who
   wants it, never crammed into the primary view.
