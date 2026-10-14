# Brand domain — index

Doctrine for the **brand-architect** seat's discipline: marketing-surface visual identity, "real
company vs. template" verdicts, brand asset governance. This seat is registered on the runtime's
GTM department roster and is dispatched by `marketing-director` during mission phases; this corpus
is the seat's doctrine. This seat **specifies, never draws** — it hands a designer/dev agent a spec
(colors, type, spacing, hierarchy, asset rules) and later judges the output against that spec and
against this corpus's anti-pattern tables. It does not open a design tool and does not commit
CSS/HTML itself.

Grep this corpus on demand — do not load it wholesale into context. One line per file below: name
+ the question it answers.

| File | Answers |
|---|---|
| [ANTI-PATTERNS.md](ANTI-PATTERNS.md) | What must a brand-architect **never** recommend, approve, or let ship? AI-template tells, stock-photo smells, palette/type sins, motion sins — each with why it fails and a pass/reject example. |
| [visual-hierarchy.md](visual-hierarchy.md) | How does a page tell the eye what matters first, second, third? Aesthetic-direction discipline, F/Z-pattern scanning, one-accent-color rule, card/section hover language, when a layout is "undesigned." |
| [type-and-spacing-systems.md](type-and-spacing-systems.md) | What type scale and spacing scale should a marketing surface use, and how do you catch a page that has neither (ad-hoc font sizes, inconsistent padding)? Modular scale ratios, the 8pt grid, and the method for reading a company's actual scale values. |
| [color-and-contrast.md](color-and-contrast.md) | What are the exact WCAG contrast thresholds, how many roles should a palette carry, and how do you audit a company's own token set against both rules? |
| [brand-asset-usage.md](brand-asset-usage.md) | Which logo file/variant goes on which background, what's the minimum clear space and size, and what photo-asset rules keep a company's imagery from reading as generic stock? |

## Seat operating notes (read once, not per-task)

- **This seat judges the marketing surface** (the marketing site, generated ad creative, social
  assets, sales decks) — not the in-app product UI, for a `b2b_saas` company that has one. The
  app's own design system is grounding context only, read from the company's own pack/dossier
  (see `company-pack-authoring.md` in this KB's `shared/` — a company's own as-is-state doc lives
  in its own home, never in this runtime), because a marketing site's CSS can silently fork from
  the app's tokens, and the two must be reconciled or deliberately declared separate — the seat
  does not own in-app UI review.
- **If no brand-guideline doc exists yet for a given company, authoring that doc's spec is this
  seat's first real assignment** for that company. This corpus is the doctrine the seat applies
  when writing it and when reviewing anything against it afterward.
- **Every numeric or behavioral claim in this corpus is tagged** `(official)` / `(third-party)` /
  `(internal-measured)` / `(internal doctrine)` with a retrieval date, or marked `UNVERIFIED —
  seeded, needs derivation`. See `shared/citation-style.md` for what each tag means and when a
  company's own pack, or a seat's own work product, should use `(internal-measured)` for a fact it
  derived directly from that company's live assets. Never state an untagged number as fact in a
  work product downstream of this corpus.
- **The buyer-context bend is not optional.** Every file ends with a section on how the doctrine
  changes for the company's actual buyer persona: `shared/contractor-buyer-psychology.md` when the
  company sells software to trade owners/GCs (`b2b_saas`, describing a B2B software buyer);
  `shared/homeowner-buyer-psychology.md` for a `local_service`/home-services company selling to
  homeowners (a residential end-customer buyer); or the company's own `persona_file` for any other
  vertical — never apply the homeowner-buyer lens to a dental/medical or other non-home-services
  company. Phone-first, time-pressured, skeptical-of-software buyers read a marketing surface very
  differently from a desk-bound, tech-literate SaaS evaluator. Apply the lens that matches the
  company actually being worked on before recommending anything to a marketing surface that buyer
  will see.
