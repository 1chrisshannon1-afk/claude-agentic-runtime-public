# Visual hierarchy — what the eye reads first, second, third

Governs how a marketing surface tells a visitor what matters most, in what order, with no words
needed. This is the doctrine the brand-architect seat applies when specifying a page layout or
judging whether a delivered page has a real hierarchy or a flat wall of equal-weight blocks.

## The core discipline: declare the direction before anything else

Ported wholesale from a third-party web-dev design-quality doctrine's own "Pre-authoring checklist"
`(internal doctrine, retrieved 2026-09-05)`. Mechanism: **state the aesthetic direction in one
sentence, then execute it**, before any layout/color/type decision. A page with no declared
direction produces the same forgettable output every time, because every micro-decision defaults to
"whatever the last generic template did."

The template: *"This page is [adjective tone]: [primary visual metaphor or constraint]."*

- Example (illustration of the mechanism only, one vertical): "This page is clinical-minimal:
  generous whitespace, single serif heading, no gradients, data speaks for itself" — a good fit for
  a clinical/medical-practice-facing page.
- Example (a different vertical, contractor/home-services): "This homepage is field-credible:
  photography over illustration, one confident CTA, numbers (time saved, quote accuracy) doing the
  persuading instead of adjectives." **Caveat — this is a spec-writing illustration, not approved
  copy for any real company:** any accuracy-related number used in a real direction sentence or
  downstream headline must be hedged and qualified per that company's own never-claim list (never
  an unqualified accuracy guarantee — see `shared/department-anti-patterns.md` §3 "Never claim
  unverified accuracy" and §2's bullet "Never assert accuracy guarantees before the company has
  actually validated accuracy at the relevant scale," plus the company's own `never_claim_file` per
  `company-pack-authoring.md` §6 for anything specific to its own product). This file hands
  specs to a downstream execution agent who will not necessarily have read that doctrine — do not
  let an accuracy-shaped claim get lifted verbatim into a hero headline as an unqualified claim for
  any company.

**Verify it isn't generic.** If the direction sentence could describe any home-services SaaS site
built in the last five years, it hasn't been sharpened enough — sharpen until it's specific to this
company and this moment. This is the single highest-leverage check the seat can run on a brief: if
a plan/PR arrives with no direction sentence, or a direction sentence that is interchangeable with
any competitor's, that is a REJECT before a single pixel is reviewed.

**Commit to it.** Every color, font, spacing, and motion choice in the deliverable is filtered
through that sentence. A choice that doesn't reinforce it gets cut, not "included because it looks
nice in isolation."

## Reading order: how attention actually flows

`UNVERIFIED — seeded from general UX-research consensus (F-pattern/Z-pattern eye-tracking
findings), needs a home-services-specific eye-tracking citation.` The commonly cited mechanism
(F-pattern for text-heavy/scanning pages, Z-pattern for sparse/landing pages with one clear CTA) is
well established in general web-UX literature but the seat has not sourced a primary eye-tracking
study for this corpus as of 2026-09-05 — treat the *mechanism* (top-left gets first attention on
LTR layouts, a single strong focal point beats scattered ones) as reliable, and the *specific
pattern name* as a convenient label rather than a proven behavior for any one company's audience.

What this means operationally for a hero section:
1. **One primary message, positioned where the eye lands first** (top-left/top-center on desktop,
   full-width top on mobile) — a headline making one specific, concrete claim, not a mission
   statement.
2. **One primary CTA, visually distinct from everything else on the page.** If there are two
   CTAs of equal visual weight above the fold, the hierarchy has already failed — the visitor now
   has to choose, which is friction the page didn't need to introduce.
3. **Supporting proof (numbers, logos, a photo) subordinate to both**, present to reduce doubt
   about the primary claim, never competing with it for the first glance.

## The one-accent-color rule

Ported from a third-party web-dev design-quality doctrine's own Color section: **choose a palette
of three roles — background, text, accent.** One dominant, one supporting, one sharp accent used
sparingly. A palette of four+ evenly weighted colors is "timid" — nothing stands out because
everything is trying to. See color-and-contrast.md for the audit method to check whether a given
company's own token set already encodes this shape (a dominant/supporting brand color plus one
single accent) — and check that company's own pack/dossier for whether its app token set (if it has
one) has since grown many more accent colors for a different, non-marketing purpose (status badges,
chart series) that must never bleed into marketing-surface hierarchy.

**Pass/reject example (generalized):**
- REJECT: A pricing page where the "Basic," "Pro," and "Business" cards each get their own accent
  color (blue border, green border, purple border) to "differentiate" them.
- PASS: One accent color marks the single recommended/featured tier (the brand's own accent color
  as a featured-card border plus a shadow lift); the other tiers are visually quieter, not colored
  differently.

## Shadow, elevation, and "what floats"

Ported from the same third-party doctrine: drop shadow on every element flattens depth instead of
creating it. A hierarchy uses shadow (or any other "raised" signal — border-color shift, background
tint) on **one focal layer per view**, so the reader's eye has exactly one thing that reads as
"closer" to them.

**Pass/reject example (generalized):**
- REJECT: Every card, icon box, and button on a features page carries an identical `box-shadow`;
  nothing reads as more important than anything else.
- PASS: A hover state lifts a card only on interaction (a `translateY` lift plus a shadow applied
  only on `:hover`), and exactly one static element (the featured pricing card, the hero's
  form-card) carries a resting shadow that nothing else on the page has.

## Spatial composition — negative space and asymmetry

Ported from the same third-party doctrine's own Spatial composition section: **generous negative
space signals confidence; cramming content signals insecurity.** Default section padding around
80px vertical is a reasonable target (a responsive `clamp()`-based version of the same default is a
common real-world pattern). Asymmetric layouts (a 60/40 text/image split, an image that bleeds to
an edge) read as more deliberate/memorable than centered 50/50 splits — check whether a company's
own hero section already uses a mildly asymmetric grid (e.g. something like `1.1fr 0.9fr`) rather
than a dead-centered 50/50 split.

**Pass/reject example (generalized):**
- REJECT: A "How it works" section crams 5 steps into a single row with under 12px of gap between
  columns on desktop, forcing horizontal scroll or tiny illegible text on mobile.
- PASS: 3 steps max per row, a generous gap (e.g. 32px), and the row reflows to a single column
  below a reasonable mobile breakpoint (e.g. 800px) rather than shrinking text to fit.

## When a layout is "undesigned" — the seat's verdict test

A page has NO real hierarchy — regardless of how polished any individual element looks — when any
of the following is true. These are the seat's actual verdict criteria, not vibes:

1. **Every section uses the same background, same padding, same card style** with no rhythm change
   from top to bottom — check whether a company's own marketing site already alternates section
   background treatments on purpose (a "canvas"/"canvas2"/"brand" rhythm is a common pattern
   specifically meant to avoid this).
2. **Two or more CTAs above the fold carry identical visual weight** (same size, same saturation,
   same position prominence).
3. **The page's own type scale (see type-and-spacing-systems.md) isn't actually followed** — ad-hoc
   font sizes scattered through the CSS/inline styles that don't map to any declared scale step.
4. **No single element on the page is the visual "loudest" thing** — everything is either equally
   quiet or, worse, equally loud.

## Contractor-buyer bend (for companies whose buyer is a trade owner/GC — see shared/contractor-buyer-psychology.md)

An owner-operator of a trade business (the contractor-buyer archetype in
`shared/contractor-buyer-psychology.md`) opening a company's page on a phone between job-site
walkthroughs will not scroll patiently looking for the point. Hierarchy discipline that would be
"nice to have" for a browsing SaaS evaluator becomes **load-bearing** for this buyer:

- **The single primary CTA and the single concrete claim must both be visible without scrolling on
  a phone screen** — not "near the top," visible in the first viewport. This buyer decides whether
  to keep reading in the first few seconds, from a truck cab or a jobsite, often one-handed.
- **Never make the value prop dependent on hovering, an accordion click, or a scroll-triggered
  reveal to become legible.** A hover-only benefit (a card that only shows its description on
  `:hover`) is invisible on a touchscreen held at arm's length in bright sunlight, which is this
  buyer's actual reading environment more often than a desk.
- **Photography earns hierarchy weight that copy alone doesn't for this buyer** — a real jobsite
  photo in the hero communicates "built for people like me" faster than a paragraph of copy would
  (see ANTI-PATTERNS.md's stock-photo row and brand-asset-usage.md). Give the hero photo real
  visual weight, not a small decorative thumbnail.

**Apply this bend only when the company pack's `persona_file` is the contractor-buyer shape**
(`shared/contractor-buyer-psychology.md`). A `local_service`/home-services company selling to
homeowners uses `shared/homeowner-buyer-psychology.md` instead — that buyer reads hierarchy
differently (see that file's own bend). A dental/medical practice or any other vertical uses its own
`persona_file` from its own pack — never point dental at `shared/homeowner-buyer-psychology.md`.
