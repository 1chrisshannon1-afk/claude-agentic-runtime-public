# Conversion Domain — Index

Grep-reachable corpus for the **conversion-architect** seat: skeptical-stranger review of
landing/pricing/signup surfaces for any company the GTM department runs. Never read wholesale —
grep to the file that answers your question, per the file list below. House style: every
numeric/behavioral claim is tagged `(official)` / `(third-party)` / `(internal-measured)` /
`(internal doctrine)` with a retrieval date, or marked `UNVERIFIED — seeded, needs derivation`. See
each file for its own citations.

| File | Answers |
|---|---|
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a conversion-architect NEVER recommend, on any company's surface, regardless of how well it "should" convert? |
| [`landing-page-skeleton.md`](landing-page-skeleton.md) | What is the canonical section-by-section structure of a converting landing/marketing page, and what does each section's one job look like for a B2B SaaS selling to a skeptical buyer? |
| [`above-the-fold.md`](above-the-fold.md) | What has to be true in the first viewport (headline, subhead, CTA, proof) before a visitor scrolls, and what does the evidence say about how much weight the fold actually carries? |
| [`pricing-page-doctrine.md`](pricing-page-doctrine.md) | How should a self-serve SaaS pricing page present the tier ladder, add-ons, and the "pays for itself" frame so a price-sensitive, skeptical buyer trusts it instead of bouncing? |
| [`forms-and-signup-friction.md`](forms-and-signup-friction.md) | How many fields, what field types, what button copy, and what signup/trial shape (card-required vs. not) should a self-serve SaaS product use, and what does the evidence say each choice costs in conversion? |
| [`trust-and-social-proof.md`](trust-and-social-proof.md) | What counts as real proof (reviews, badges, guarantees, citations) vs. fake social proof, and where does it have to sit on the page to do anything? |
| [`ab-testing-discipline.md`](ab-testing-discipline.md) | How does a test get proposed, sized, run, and called a winner — and how do you read a multi-variant landing-page setup against that discipline? |
| [`paid-destination-doctrine.md`](paid-destination-doctrine.md) | What changes about a landing page's review once it's about to receive AD traffic — Final URL expansion / AI Max, pricing-disclosure ad policy, Quality Score's landing-page-experience component, Meta Instant Forms as a destination choice, and the measurement prerequisite for trusting any conversion finding? |
| [`message-match.md`](message-match.md) | How does ad-to-page message continuity change how a company's message-angle landing-page variants should be used under paid traffic? |
| [`benchmarks.md`](benchmarks.md) | What correctly-attributed conversion-rate reference points exist to judge whether a measured company number warrants investigation? |

## How this domain relates to the others

- **Pricing decisions themselves** (what the tiers/add-ons/numbers actually are) are NOT this
  domain's call — that belongs to each company's own pricing source-of-truth doc (see the
  company's own pack/dossier), cited here as the input this domain must present honestly, never
  re-litigated.
- **Positioning/copy claims** (what a company is allowed to say it does) are NOT this domain's call
  either — that belongs to each company's own positioning doc and its never-claim list (see the
  company's own pack/dossier), cited here as a hard constraint on every page this domain reviews.
- **Paid-acquisition mechanics** (campaign structure, bid strategy, learning-period gates) belong
  to a different seat/domain — this domain only touches the landing surface an ad points at, never
  the campaign that drives traffic to it.
- **Brand voice / verbal identity** belongs to a messaging or brand domain, not here — this domain
  judges structure, friction, and trust mechanics, not tone of voice.
- **Buyer-segment bends** (the "Buyer-segment bend" sections throughout this domain) back one
  persona only — a B2B software buyer at a trade business, sourced to
  `shared/contractor-buyer-psychology.md` — and apply only when the company under review is itself
  selling software to trade-business owners. They do NOT apply to a `local_service` company selling
  directly to homeowners: that persona is the **homeowner**, described in
  `shared/homeowner-buyer-psychology.md`, and several of this domain's contractor-persona bends are
  actively wrong advice for a homeowner audience (e.g. the landing-page-skeleton bend's "never a
  `tel:` link" — a `tel:` CTA is often exactly right for a home-services page). No homeowner bend
  exists in this domain yet; a reviewer working a `local_service` company's consumer-facing surface
  should check the company's own pack for its own persona file and treat this domain's existing
  bends as inapplicable until a homeowner-specific bend is written. A reviewer on an engagement
  outside both personas (e.g. dental) should also check the company's own pack rather than assume
  either bend applies.

## Provenance shorthand used throughout this domain

- **(internal doctrine)** — a general mechanism learned from a specific company engagement and
  ported here because the MECHANISM (the gate, the threshold logic) generalizes across companies.
  The underlying NUMBER attached to any one company's measurement is company-specific and is never
  assumed to hold for a different vertical or business without its own citation.
- **(official)** — Baymard Institute or NN/g's own published research, or another named primary
  source.
- **(third-party)** — a secondary source reporting on official research, or independent industry
  benchmark data (e.g. WordStream/Unbounce aggregators).
- **(internal-measured)** — a number a specific company has actually measured from its own pack
  (see the company's own pack/dossier for the source doc).
- **UNVERIFIED — seeded** and the other `UNVERIFIED` variants — see `shared/citation-style.md` for
  the full set of tag definitions (this domain does not restate them).
