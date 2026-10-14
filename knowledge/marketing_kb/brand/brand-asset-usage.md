# Brand asset usage — logos and the photo library

Governs which logo file goes where, minimum size/clear space, and the rules that keep a company's
photo library from reading as generic stock. This file is the practical "which exact asset, on
which background" reference — a company's own pack/dossier has the full inventory context (its
actual logo file paths, hex values, and CSS line citations); this file states the mechanism and
the pass/reject test, not any one company's own numbers.

## Logo file naming — read this before recommending a variant

`(internal doctrine, mechanism generalized from direct pixel sampling of a real logo asset set,
retrieved 2026-09-05)`.
**A "for dark background" suffix or variant name should describe the background the file is FOR,
not the ink color of the mark** — this is easy to get backwards and doing so is exactly the kind of
mistake ANTI-PATTERNS.md's "logo fails on its background" row exists to catch. A typical logo asset
set carries this shape (adapt the exact filenames to the company's own naming convention, found in
its pack/dossier):

| File role | Typical mark treatment | Use on |
|---|---|---|
| Full wordmark, light-background variant | Dark-ink wordmark, transparent background | **Light backgrounds** — white, a pale canvas tone, any light brand-tint surface |
| Full wordmark, dark-background variant | White/near-white wordmark, transparent background | **Dark or saturated backgrounds** — a dark footer, a brand-color section, any photo-overlay dark scrim |
| Icon-only mark, light-background variant | Same dark-ink treatment as the full wordmark, square, icon-only (no wordmark) | Light backgrounds, small square placements (favicon-adjacent, app icon, social avatar) |
| Icon-only mark, dark-background variant | Same light treatment as the dark-background wordmark, square | Dark/saturated square placements |

Content bounding boxes (useful for cropping/padding math) vary per company's actual exported
asset — the pattern to check for is whether the wordmark fills its canvas edge-to-edge (little to
no built-in padding, meaning **external clear space is mandatory**) or has generous built-in
padding already (an icon-only mark much more often needs the former; a full wordmark often has the
latter). Sample the company's own PNG/SVG directly rather than assuming.

**Pass/reject example (generalized):**
- REJECT: Placing the light-background wordmark variant on a dark or brand-saturated section
  background, or in a dark-background footer — the dark-on-dark mark becomes illegible or
  invisible. This is a live risk whenever the site's own CSS lets markup reference either logo
  variant interchangeably in a nav or header component — confirm the markup always picks the
  light-background variant on a light sticky nav, never the dark-background variant.
- PASS: The dark-background variant used inside a brand-color section or the footer; the
  light-background variant used on a light sticky nav.

## Minimum size and clear space

`(third-party — general brand-identity convention, retrieved 2026-09-05; no company-specific figure
should be assumed ratified unless that company's own brand-guideline doc actually states one)`. Two
conventions are common across brand guides surveyed (Johns Hopkins Medicine, University at Buffalo,
Loma Linda University Health brand sites, among others):

- **Clear space as a proportion of mark height ("X"):** margin on all sides ≥ some fraction of the
  logo's own height — cited examples range from a uniform 20% of symbol height to an asymmetric
  0.4X (top/sides) / 0.5X (bottom). Either convention is acceptable; **pick one and hold it fixed**
  once ratified — the specific fraction matters less than never placing text or another logo inside
  the declared margin.
- **Minimum reproduction size:** commonly cited horizontal-format floor ≈1.5in / vertical-format
  floor ≈1.25in for print; for web, the equivalent test is **legibility of the wordmark's smallest
  letterform at the rendered size**, not a fixed pixel number — check the company's own live nav
  logo size against this test (its pack/dossier or a direct CSS read gives the actual pixel value);
  do not recommend shrinking it further without testing actual on-screen legibility at that size.

**A company-specific clear-space or minimum-size rule may not exist yet for a given company** —
`UNVERIFIED — seeded from general convention` until that company has ratified its own
brand-guideline doc. Until then, the safe default the seat should apply for any company: **never
let another element (text, an icon, a photo edge) sit closer to the logo than roughly 20% of the
logo's own rendered height**, and never scale the full wordmark below a height at which the
individual letterforms of the company's actual name become visually merged or illegible (test at
the actual target size, don't estimate).

**Pass/reject example (generalized):**
- REJECT: A social-share composite that places the logo directly abutting headline text with no
  gap, or shrinks the full wordmark to fit a crowded corner at a size where the company name reads
  as a gray smear.
- PASS: A logo composited with its own dedicated space, headline text separated from it, not
  touching — check the company's own image-asset brief for its stated approach to this exact
  composite, if one exists.

## Photo library rules — the "real company vs. template" test for imagery

Grounded in the house rules of a real, unusually rigorous marketing photo brief this doctrine was
derived from `(internal doctrine, retrieved 2026-09-05)`, worth preserving as a portable mechanism,
plus the stock-photo anti-pattern (ANTI-PATTERNS.md) and the external conversion data below.

**The mechanism a good photo brief gets right (keep this discipline for every future photo asset,
generated or licensed, for any company):**
1. **Specific to the actual buyer and the actual work**, never generic "construction" or "business
   people" — a strong brief for a trade-vertical company targets that trade's own specific work and
   the exact real-world moments its buyer would recognize. For a company selling to contractors (a
   B2B software company): photographing a bathroom with a phone, reviewing an estimate at a
   tailgate. For a `local_service`/home-services company selling to homeowners, the counterpart shot
   list is the homeowner's own moments: a real finished-room "after" shot, a crew working on site.
   Neither reads as stock-photo boardroom scenes.
2. **Brand color appears in wardrobe/props, not as a filter** — a work shirt in the brand's own
   color, a matching accent — this is how a photo library stays "on brand" without looking like a
   color-graded stock pack.
3. **Mood is candid-documentary, not glossy stock** — "slightly imperfect, authentic, grit where
   appropriate" is a strong brief's own language; this is the opposite instinct from a polished
   stock-photo smile, and is the right instinct to keep.
4. **Never let a generator render legible on-screen UI/app text** — phone/tablet screens face away
   or are out of focus in every prompt; app UI gets composited in separately. This avoids the
   dead giveaway of garbled fake-UI text that screams "AI-generated."

**The ethics/legal guardrail (ANTI-PATTERNS.md duplicates this as a top-line anti-pattern — it is
that important):** never pair an AI-generated or stock "customer" face with a testimonial quote,
invented or real. A well-built photo brief holds testimonial-headshot generation on hold until
real, consented customer quotes exist. **This corpus ratifies that hold as standing doctrine for
every company** — the brand-architect seat must reject any request to generate or source
customer-testimonial faces ahead of real testimonials for any company, not just note it as one
brief's opinion.

**Stock vs. authentic — the external evidence for why this matters:**
- Landing pages using authentic human images convert roughly 45% better than generic stock photo
  equivalents, per HubSpot-cited research; a separate Marketing Experiments study found real photos
  produced ~35% higher conversion than stock `(third-party, retrieved 2026-09-05 — figures as
  reported by aggregator sources citing HubSpot/MarketingExperiments; the seat has not verified the
  original primary studies directly, treat the exact percentages as indicative rather than
  precision-audited)`.
- Sites using authentic team photography scored roughly 65% higher on visitor trust than stock-photo
  equivalents in surveyed research `(third-party, retrieved 2026-09-05, same caveat — indicative,
  not independently re-verified against a primary source)`.
- Design/aesthetic quality is the single most commonly cited driver of web credibility judgments:
  Stanford's Web Credibility Project (2002) found "design look" was the most prominent factor
  mentioned by participants explaining credibility judgments — cited in 46.1% of comments, ahead of
  information structure (28.5%) `(third-party, retrieved 2026-09-05 —
  credibility.stanford.edu/research.html and secondary summaries of the 2002 Stanford-Makovsky
  study)`. This is old (2002) but the underlying mechanism — visual polish is read as a proxy for
  competence/trustworthiness before any content is evaluated — has no reason to have reversed, and
  is consistent with the newer authentic-photo findings above.

**Pass/reject example (generalized):**
- REJECT: Sourcing a stock photo of generic smiling people in business-casual attire in an office
  for a "Why our customers choose us" section (this is ANTI-PATTERNS.md's stock-photo row, restated
  here with the photo-library-specific evidence for why).
- PASS: A company's own real shot list (contractor with phone on a jobsite, reviewing an estimate
  at a tailgate, a real finished-project "after" shot, or that vertical's own equivalent) — a
  well-specified brief's shots meet this bar by design; check the company's own pack/dossier for
  its actual brief if one exists.

## Contractor-buyer bend (for companies whose buyer is a trade owner/GC — see shared/contractor-buyer-psychology.md)

- **This buyer's trust calculus runs almost entirely on "does this look like people who understand
  MY trade," not "does this look professional" in the abstract.** A technically polished stock photo
  of an unrelated white-collar scene can score *worse* with this buyer than a rougher but genuinely
  on-trade photo — polish is not the same axis as relevance for this audience. Weight
  trade-specificity above generic production value when the two trade off.
- **Logo legibility at small size matters more here than for a desktop-first SaaS buyer** — this
  buyer is disproportionately viewing marketing surfaces (texted links, ads, a bookmark on a phone
  home screen) at small, square-icon sizes. Prioritize icon-variant legibility testing at genuinely
  small real-world sizes (32px, 48px favicon/PWA-icon scale) over wordmark refinement at large hero
  sizes.
- **Never license a rushed/decorative stock photo pack "to save time" for a launch.** This buyer
  has often been burned by software vendors before (see the seat's own operating notes in
  INDEX.md/every file's framing) — a marketing surface that visibly cuts the authenticity corner
  reads as exactly the kind of vendor they've learned to distrust. The time saved is not worth the
  trust cost for this specific buyer, even where it might be an acceptable tradeoff for a
  lower-trust-sensitivity audience.

**Apply this bend only when the company pack's `persona_file` is the contractor-buyer shape**
(`shared/contractor-buyer-psychology.md`). A `local_service`/home-services company selling to
homeowners uses `shared/homeowner-buyer-psychology.md` instead — that buyer runs a different trust
calculus (see that file's own bend). A dental/medical practice or any other vertical uses its own
`persona_file` from its own pack — never point dental at `shared/homeowner-buyer-psychology.md`.
