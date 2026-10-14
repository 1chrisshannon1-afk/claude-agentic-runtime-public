# Type and spacing systems

Governs what a marketing surface's type scale and spacing scale should look like, and how the
brand-architect seat catches a page that has neither — ad-hoc font sizes and paddings chosen
per-element instead of drawn from a declared system. A page with no system is exactly the kind of
"undesigned" verdict visual-hierarchy.md's test #3 flags.

## Why a scale at all

A type/spacing "system" is just a small, finite set of values every element on the page draws
from, instead of every element inventing its own number. The value isn't aesthetic purity — it's
that a finite set of steps makes inconsistency **visible and checkable** (grep the CSS for a
font-size that isn't one of N declared values), where an infinite set of ad-hoc pixel values makes
inconsistency invisible until a human eyeballs the rendered page.

## Type scale doctrine

**Modular scales.** A modular scale multiplies a base size by a fixed ratio per step:
`value = base × ratio^step`, rounded to a clean number
`(third-party, retrieved 2026-09-05 — freeCodeCamp/Medium "8-Point Grid: Typography On The Web,"
consistent with the broader modular-scale convention e.g. type-scale.com)`. Two ratio families:

- **Lower ratios (1.25 "Major Third," 1.333 "Perfect Fourth")** produce gentler jumps between
  steps, suited to dense interfaces with many closely related sizes — this is closer to what a
  product/app UI needs (many small distinctions: body vs. small vs. label).
- **Higher ratios (1.5, or 1.618 "Golden Ratio")** produce dramatic jumps, suited to marketing pages
  and editorial layouts where a small number of loud, clearly differentiated sizes (a huge H1, a
  much smaller body) is the point.

**Never default to an invisible font for display/heading text.** Ported from a third-party web-dev
design-quality doctrine's own Typography section `(internal doctrine, retrieved 2026-09-05)`: never
default to Inter, Roboto, Arial, or system-ui for display or heading text — these carry no character
and are the visual fingerprint of "nobody made a choice here." Body text is the exception: an
invisible font is *fine* for body copy precisely because body copy should not compete for attention
with the heading above it. The pattern to look for and recommend: a distinctive geometric or
characterful sans (or serif) for headings/labels at heavy weights (700–800), paired with a
deliberately quiet, highly legible workhorse font for body paragraphs — check the company's own
pack/dossier for which two fonts it has actually adopted for this split, if any.

**Pass/reject example:**
- REJECT: A landing page variant sets its H1 in `system-ui` because "it loads faster" — the page
  now looks like every default-browser-font template on the internet, which is precisely the tell
  ANTI-PATTERNS.md's table exists to catch.
  Font-loading performance is a real, separate constraint (see the buyer-context bend below) — the
  fix is a well-optimized web-font load (subsetting, `font-display: swap`, preload), never silently
  reverting to a system font for a headline.
- PASS: H1/H2/H3/labels all render in the company's chosen distinctive display font at its declared
  weights; body copy, form labels' helper text, and testimonial quotes render in its chosen quiet
  body font — check the company's own pack/dossier for which two fonts it has actually adopted.

### Method: reading a company's actual type scale (as-is, before any brand-guideline doc exists)

A `b2b_saas` company with both a marketing site and an app dashboard very often has **two
*different* scales in its codebase**, one per surface — this divergence is not, on its own, an
anti-pattern (a marketing page and a dense app UI legitimately want different ratios per the
doctrine above), but it should be found and named on purpose, not left an accident. Pull both from
the company's own pack/dossier or its live CSS/token files directly:

- **A marketing site** commonly uses a small, responsive, editorial-leaning scale — often built with
  `clamp()` so headline size flexes with viewport width rather than jumping at fixed breakpoints —
  with a dramatic, high-ratio jump between its smallest heading step and its largest H1 (a 2.5-3×
  jump is a reasonable editorial target, consistent with "marketing pages want higher ratios" above).
  Check whether the scale was authored by picking a named ratio deliberately, or hand-tuned per
  value with no ratio constant anywhere in the file — the latter isn't wrong, but it's worth naming
  explicitly in a brand-guideline doc so a future editor understands the jump was intentional.
- **An app UI/dashboard** commonly uses a tighter, denser scale with fixed rem values and per-step
  line-height/letter-spacing declared explicitly, clustering adjacent-step ratios near the "Perfect
  Fourth" (1.333) modular-scale family — appropriate for a dense UI with many closely related sizes,
  per the doctrine above.

**Seat implication:** when authoring the eventual brand-guideline doc for any company with both
surfaces, do not silently merge two divergent scales into one. Document both, explicitly, as two
named scales with a stated reason they differ, so a future agent doesn't "fix" the marketing site's
dramatic H1 jump into the app's gentler ratio by mistake (which would flatten the exact editorial
punch the marketing site wants). A completed inventory of one company's own two scales belongs in
that company's own pack/dossier, not in this shared file.

## Spacing scale doctrine

**The 8pt grid.** Snap UI margins, padding, and gaps to multiples of 8px. Most popular screen
resolutions (1920, 1440, 1366, 1280, 1024, 768, 360) are divisible by 8, so elements sized in
multiples of 8 align cleanly across nearly every device; major design systems (IBM Carbon,
Microsoft Fluent, Atlassian, Ant Design, Shopify Polaris, GitHub Primer) adopted this convention
`(third-party, retrieved 2026-09-05 — thehangline.com "8px Grid Spacing System Explained," consistent
across multiple sources including freeCodeCamp's "8-Point Grid" piece)`. The 8pt grid governs
**spacing and sizing** — it is a different axis from the type scale (which follows its own modular
ratio); pairing a baseline/spacing grid with the type scale is what keeps rhythm coherent across
headings, body copy, and interface components
`(third-party, retrieved 2026-09-05, same source set)`.

**Pass/reject example:**
- REJECT: A card component uses `padding: 22px 17px` and a sibling card 3 lines down uses
  `padding: 18px 20px` — neither aligns to 8px (or the company's own 4px-based scale, if it has one
  — see below), and the two don't match each other, so the page reads as fussy/inconsistent even if
  neither number alone looks wrong.
- PASS: Every card in a grid uses the same declared spacing token; a design that needs a
  *smaller* pad for a denser component picks the next step down in the scale rather than an
  arbitrary intermediate value.

### Method: reading a company's actual spacing scale (as-is)

A well-built spacing token file often declares an explicit small-base (commonly 4px) scale (e.g.
`--space-0` through a top step like `--space-16`), where every even step is a clean multiple of 8 —
compatible with the 8pt-grid doctrine while adding half-steps for finer control. Check the token
file's own comments: a common pattern is a scale marked "adopt incrementally," meaning existing
inline padding/margin literals are explicitly out of scope and the app UI has not fully migrated to
it yet. Separately, check whether the marketing site's own CSS references these tokens at all, or
hand-writes its own pixel values that happen to mostly land on 4px/8px-friendly numbers without
being drawn from a shared named scale — this divergence is common and worth naming explicitly.

**Seat implication:** a marketing site's spacing is often *accidentally* mostly-compliant with an
8pt rhythm, not *deliberately* drawing from the app's own spacing scale. A brand-guideline doc
should either (a) formally adopt the app's spacing tokens on the marketing surface too, or (b)
declare the marketing site's spacing values as its own small system and name them — either is fine
per this doctrine, but leaving it unnamed and implicit is the anti-pattern (see ANTI-PATTERNS.md's
"silently diverging token systems" row, which is a color-focused instance of the same underlying
failure this section describes for spacing). A completed reading of one company's own scales
belongs in that company's own pack/dossier, not in this shared file.

## Contractor-buyer bend (for companies whose buyer is a trade owner/GC — see shared/contractor-buyer-psychology.md)

- **Legibility at a glance beats scale elegance.** This buyer is often reading on a cracked phone
  screen in bright sun, one hand on a coffee, standing at a tailgate. A gentler, more "sophisticated"
  type ratio that relies on subtle size differences to signal hierarchy is a liability here — favor
  a marketing site's own dramatic H1-to-H3 jump over an app's gentler dashboard ratio for anything
  this buyer sees in an ad, a text-message link, or a homepage hero.
- **Font-loading weight is a real cost for this buyer, not a nitpick.** A contractor on a job site
  with weak cellular signal pays a real, felt latency cost for un-optimized web-font loading (see
  the REJECT example above) — this is a case where a system's "correctness" (never default to a
  system font) must be paired with a performance discipline (subset the font file, `font-display:
  swap`, preload only the weights actually used) rather than loading every weight of a display font
  nobody asked for. Recommending a web font without also specifying which weights/subsets to
  actually ship is an incomplete spec for this buyer's context.
- **Spacing generosity reads as trustworthy, not slow, to this buyer too** — a cramped, dense layout
  (see ANTI-PATTERNS.md and visual-hierarchy.md) reads as "cheap lead-gen site," which is exactly
  the software category this buyer has often been burned by before. Generous spacing is not a luxury
  aesthetic choice for a SaaS-native audience here; it's part of how this specific buyer
  distinguishes "real software company" from "landing-page mill."

**Apply this bend only when the company pack's `persona_file` is the contractor-buyer shape**
(`shared/contractor-buyer-psychology.md`). A `local_service`/home-services company selling to
homeowners uses `shared/homeowner-buyer-psychology.md` instead — that buyer may weight legibility,
load performance, or spacing differently (see that file's own bend). A dental/medical practice or
any other vertical uses its own `persona_file` from its own pack — never point dental at
`shared/homeowner-buyer-psychology.md`.
