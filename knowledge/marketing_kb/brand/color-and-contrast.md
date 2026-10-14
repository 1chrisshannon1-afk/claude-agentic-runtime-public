# Color and contrast

Governs palette structure (how many colors, what roles) and the exact accessibility thresholds a
color choice must clear. This is the one file in this domain where "looks fine to me" is not an
acceptable verdict — contrast is a number, and the number either clears the bar or it doesn't.

## WCAG contrast thresholds — official, exact

`(official — W3C WCAG 2.1, retrieved 2026-09-05)`. Ratios are computed from relative luminance per
the WCAG formula and must **not be rounded** — 4.499:1 does not meet a 4.5:1 threshold
(w3.org/WAI/WCAG21/Understanding/contrast-minimum.html; non-text: /non-text-contrast.html; AAA:
/contrast-enhanced.html, all retrieved 2026-09-05).

| Success Criterion | Level | Applies to | Threshold |
|---|---|---|---|
| 1.4.3 Contrast (Minimum) | AA | Normal text | **4.5:1** |
| 1.4.3 Contrast (Minimum) | AA | Large text | **3:1** |
| 1.4.6 Contrast (Enhanced) | AAA | Normal text | **7:1** |
| 1.4.6 Contrast (Enhanced) | AAA | Large text | **4.5:1** |
| 1.4.11 Non-text Contrast | AA | UI component boundaries/states (buttons, inputs, focus indicators) needed to identify the component | **3:1** against adjacent color(s) |
| 1.4.11 Non-text Contrast | AA | Graphical objects required to understand content | **3:1** |

**"Large text" definition (official):** at least 18pt regular, or 14pt bold (≈24px regular / ≈18.7px
bold), or the CJK-equivalent size.

**1.4.11 exemptions (official):** inactive/disabled controls; graphics where a particular
presentation is essential to the information (logos, flags, photos); purely decorative graphics;
a graphic whose information is redundant with adjacent text. **Logos are explicitly exempt** — a
brand mark does not need to clear 3:1 against its background to pass WCAG, though brand-asset-usage.md's
legibility rules still apply for other (non-compliance) reasons.

**Which level a given company should target:** `UNVERIFIED per-company — needs an explicit
operator/engineering ruling for each company; check that company's own pack/dossier for whether one
exists.` Absent a company-specific ruling naming a target WCAG level for its marketing site, AA is
the near-universal legal/commercial baseline (ADA-related web litigation and most vendor
accessibility statements cite AA, not AAA) — the seat should treat **AA as the default floor to
enforce** and flag AAA
gaps as a to-do, not a blocker, absent an explicit ruling raising the bar.

## The three-role palette rule

Ported from a third-party web-dev design-quality doctrine's own Color section `(internal doctrine,
retrieved 2026-09-05)`: **choose a palette of three roles — background, text, accent.** One
dominant, one supporting, one sharp accent used sparingly. A palette of four+ evenly-weighted colors
is timid; a dominant background plus a single vivid accent outperforms it. Never use
purple-gradient-on-white as a default — see ANTI-PATTERNS.md.

## Method: audit a company's actual marketing-site color pairs against AA

This is the audit method the brand-architect seat runs against any company's own live palette — not
an illustration to skip. Pull every declared background/text/accent hex pair actually in use from
the company's own CSS/token source (its pack/dossier names the file), compute the WCAG
relative-luminance contrast ratio for each real pairing directly (do not estimate or round — 4.499:1
does not meet 4.5:1), and score each against the AA thresholds above. A completed audit for a real
company belongs in that company's own pack/dossier, not in this shared file — check there for
whether a given company already has one on record.

**What this kind of audit reliably finds, generalized from real audits run this way:** a palette
that passes comfortably on body-copy pairs (dark ink on white typically clears AA by a wide margin,
often ≥10:1 `(internal doctrine, retrieved 2026-09-27)`) can still have
exactly one high-visibility failure hiding in a saturated accent color used for a primary CTA
button — because a vivid, mid-saturation accent (the kind picked precisely because it "pops") is
often the pairing closest to the 4.5:1 floor, while quieter body-text pairings clear it by a wide
margin. **Always check the primary CTA/button color pairing specifically, at its actual rendered
font size**, not just the body-copy pairs — a marginal-looking accent color is exactly where a real
defect tends to live.

### The size trap: a bold button can still fail AA at 16-17px

A common, easy-to-miss failure mode: a button's text renders **bold** and a reviewer eyeballing it
assumes "large text" (the looser 3:1 threshold) applies. **The official large-text bold threshold is
14pt bold ≈ 18.67px, not 14px bold** — a 16-17px bold button label is still roughly 1.7-2.7px short of
qualifying as large text (18.67 − 17 ≈ 1.7; 18.67 − 16 ≈ 2.7), so the stricter 4.5:1 (AA normal)
threshold applies, not 3:1. Compute the actual rendered px size (accounting for any relative unit
like `rem`/`vw`/`clamp()`) before deciding which threshold governs — never assume bold weight alone
earns the looser bar.

**Pass/reject example (the exact test to apply to any future button/badge color choice, for any
company):**
- REJECT: Any pairing under 4.5:1 used for real body-weight interactive text under ~18.7px bold /
  24px regular — e.g. a vivid accent-color background with white or the accent's own hue as text,
  computed below 4.5:1 at the button's actual rendered size.
- PASS: Either (a) darken the accent background to a deeper shade of the same hue until it clears
  4.5:1 while staying visually "the accent," or (b) keep the lighter accent but switch to the
  palette's darkest ink color as the text color instead of white — this often clears AA normal-text
  by a comfortable margin since dark-on-mid-saturation frequently outperforms white-on-mid-saturation
  — or (c) bump the button's font size/weight past the large-text floor and accept the looser 3:1
  bar. Options (a)/(b) are strictly safer since they don't depend on a designer remembering a size
  floor on every future reuse of this button style.

**If an audit finds a genuine, currently-shipping failure** on a real company's live marketing
surface, that is not a hypothetical finding — file it through that company's own tracked-issue
process immediately (see this KB's `shared/` phase-gate/approval doctrine for how findings become
actioned work), don't silently note it in a doctrine file.

## Contractor-buyer bend (for companies whose buyer is a trade owner/GC — see shared/contractor-buyer-psychology.md)

- **This buyer is more likely, not less, to be reading in bad lighting conditions** — direct
  sunlight on a phone screen, a dusty tablet, older eyes after years in the trade. WCAG AA is a
  *legal-risk floor*, but for this specific buyer treat any marginal pass (anything within roughly
  0.3 of the 4.5:1 floor `(internal doctrine, retrieved 2026-09-27)`) as fragile, not "fine" — a
  future palette tweak that nudges either color
  half a shade could silently drop it below the floor with zero visual warning to whoever made the
  change. Recommend AAA (7:1) for anything this buyer must read outdoors under real time pressure —
  a phone number, a CTA, a price — even though AA is the stated floor.
- **A failing CTA-button contrast is not a nitpick for this buyer — it is the button they have to
  find and tap to become a lead.** A marginal-contrast primary action costs more real conversions
  from a squinting-in-sunlight audience than it would from an office-desk SaaS buyer. Treat any such
  finding as this file's highest-priority fix for a company serving this buyer, precisely because of
  who's tapping it.
- **Never recommend a "sophisticated" muted/low-contrast palette trend for this audience** — a
  design fashion that favors soft, desaturated grays-on-grays (common in SaaS aesthetic trends)
  actively fights this buyer's real reading conditions. Prefer a company's existing high-contrast
  body-copy choices (anything comfortably into AAA territory) over any proposal to soften them for
  aesthetic reasons.

**Apply this bend only when the company pack's `persona_file` is the contractor-buyer shape**
(`shared/contractor-buyer-psychology.md`). A `local_service`/home-services company selling to
homeowners uses `shared/homeowner-buyer-psychology.md` instead — that buyer may not share this
reading-environment profile (see that file's own bend). A dental/medical practice or any other
vertical uses its own `persona_file` from its own pack — never assume outdoor/bright-sunlight
legibility is the binding constraint for a company whose buyer isn't a contractor/trade owner.
