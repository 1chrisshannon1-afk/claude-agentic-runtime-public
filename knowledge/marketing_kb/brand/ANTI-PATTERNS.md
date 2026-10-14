# Brand anti-patterns — never recommend these

Every domain KB carries its own ANTI-PATTERNS.md. This is the brand domain's: things the
brand-architect seat must **never** approve, recommend, or wave through on a marketing surface,
regardless of who asks or how much time pressure exists. Mechanism ported from a third-party
web-dev design-quality doctrine reviewed in full 2026-09-05 (see `shared/citation-style.md` for how this
KB labels third-party sourcing) — vertical-specific framing generalized so any company's pack can
apply it.

Each row: the anti-pattern, why it fails, and a concrete pass/reject example so the seat has a
falsifiable test, not a vibe.

## The AI-template tell table (ported wholesale)

Source: a third-party web-dev design-quality doctrine's own "Anti-patterns (never do these)"
section `(internal doctrine, retrieved 2026-09-05)`.

| Anti-pattern | Why it fails | Reject example | Pass example |
|---|---|---|---|
| Generic gradient hero (`#6366f1` → `#8b5cf6`, indigo-to-violet) | Indistinguishable from thousands of templated SaaS landing pages; reads as "nobody chose this on purpose" | A hero section background is a linear-gradient between two evenly-saturated purple/indigo stops with no brand color present | A hero background uses the brand's own palette (see color-and-contrast.md) as a deliberate radial wash, or a real photo, or a solid brand color — never an unbranded purple gradient |
| Stock photo of smiling professionals in a generic office | Signals absence of a real brand; the buyer's product has nothing to do with an open-plan office | A "Why choose us" section shows three people in blazers smiling at a laptop in a glass-walled office | A section shows the buyer's actual work environment (see brand-asset-usage.md's photo-library rules) |
| Full-width colored button rows with no breathing room | Reads as a mid-2000s free WordPress theme; cramped CTAs signal insecurity, not confidence | A row of 4+ full-bleed colored buttons stacked edge-to-edge with under 8px between them | A single, clearly primary CTA per view, generous padding, secondary actions visually subordinate |
| Equal-weight four-column icon grids below the hero | Cookie-cutter "features" layout that says nothing specific about this company | A "Features" section: 4 identical white cards, each with a generic line-icon, a 3-word title, and one sentence, all the same visual weight | A features section groups by outcome, varies card content length/weight by importance, or leads with the strongest differentiator first |
| All-caps body text | Hurts readability at paragraph length; legitimate only for short labels/captions | A testimonial quote or a feature description rendered entirely in uppercase | Uppercase reserved for eyebrows, badges, or single-word labels under ~20 characters |
| Drop shadow on every element | Flattens depth instead of creating it — if everything floats, nothing does | Every card, button, icon, and image on a page carries the same `box-shadow` | Shadow reserved for one focal layer per view (e.g. the featured pricing card, a raised nav) — see visual-hierarchy.md |
| Three or more accent colors at the same visual weight | Looks undesigned; competing accents fight for attention with no clear winner | A page uses purple, teal, and pink CTAs/highlights all at full saturation | One accent color used intentionally; secondary colors present only as muted/soft variants (see color-and-contrast.md's "three roles" rule) |

## Additional brand-specific anti-patterns (not in the ported table, added for this domain)

| Anti-pattern | Why it fails | Reject example | Pass example |
|---|---|---|---|
| Two brand token systems silently diverging | A marketing site copy-pasted the app's token values instead of importing them; the two drift over time with no mechanism to catch it | An illustrative pattern: a marketing site's static CSS hardcodes a hex brand color in its own `:root` instead of referencing the app's shared design-tokens file — check the company's own pack/dossier for whether this company has a confirmed instance and its current status | A single token source of truth, imported or generated into every surface; if a fork is unavoidable (different build pipeline), the fork is declared in writing with a sync-check, not left implicit |
| Recommending a logo variant that fails on its background | Logo becomes illegible or looks like an error the moment a page ships in the "wrong" theme | Recommending the light-background logo variant placed on a dark or brand-colored section background | Recommending the dark-background/reversed logo variant for any dark or brand-colored background — see brand-asset-usage.md |
| AI-generated "customer" headshots paired with testimonial quotes | Deceptive; an FTC endorsement-rules problem the moment a fabricated face is attached to any quote, invented or real | Recommending testimonial headshots be generated and shipped before real, consented customer quotes exist | Neutral initials/avatars or blurred/generic "customer" silhouettes until real, named, consented testimonials exist — a company's own photo brief may already state this; the seat must never override that hold |
| A brand-guideline doc invented from vibes instead of derived from the as-is system | Creates a second, competing "canonical" palette/type spec that contradicts the tokens actually in use, forcing an expensive unwind later | Authoring a brand guide that introduces a new heading font not present in the company's actual live CSS/token files without a migration plan | Any new brand-guideline doc starts from the company's recorded as-is inventory and either ratifies the existing tokens or proposes an explicit, scoped migration |
| Treating the marketing site's aesthetic as separate from the product or service it sells | The buyer judges the underlying offering's competence partly by the marketing page's competence — a template-feeling site undercuts a "we're the real deal" claim before the buyer ever engages further | Approving marketing copy/imagery that looks like a generic template while the actual offering is genuinely specific/differentiated | Marketing visual quality is held to the same "does this look like a real, competent company" bar the underlying offering itself needs to clear for a skeptical buyer |
| Motion for its own sake on a marketing page a phone-first, time-pressured buyer will load on cellular | Heavy animation/parallax slows load and reads as showy rather than trustworthy to this buyer (see the buyer-context bend in every file) | Approving a parallax hero, autoplay video background, or >600ms staggered entrance animation suite for the homepage hero | One orchestrated, sub-600ms entrance per section max `(internal doctrine, retrieved 2026-09-05)`; everything else static |

## Ported review-discipline rule relevant to visual judgment

From a third-party web-dev safety doctrine reviewed in full 2026-09-05 (internal doctrine; see
`shared/citation-style.md`): the source's core mechanism — never ship a visual change without a
**before/after comparison** and an explicit **verification verdict** — is a live-editing/staging
safety protocol (backups, rollback, staging gates), which is out of this seat's lane (that belongs
to whichever seat/agent actually executes web changes for a given company — e.g. its own
`browser-ops`/QA agent plus its own staging-first rule). The **portable review discipline** this
seat DOES inherit:

- **Never judge a visual change from a description alone — see the rendered page (or a
  screenshot/artifact) before verdict.** The source's own cited prior incident describes an agent
  editing production directly with **no staging step, no backup, no screenshots, no audit log** —
  not "empty verification notes causing a silent break." Post-flight verification (taking
  after-screenshots and a visual-parity check) and a completion-lifecycle notes rule are separate
  rules in the source with no stated causal chain from the incident to either specifically. What
  the incident actually motivates is the source's overall staging-first/backup/audit-trail
  discipline — this seat's narrower takeaway (see rendered output, don't judge from a description)
  is a reasonable extension of that broader discipline, not a rule the source states verbatim.
  **Naming-collision caveat, generalized:** a doctrine source's own illustrative prior-incident
  company name can coincidentally match a real tenant/account name inside whatever company this
  seat is currently working for. Before citing any doctrine-source incident by name, confirm which
  real-world entity it actually describes and do not conflate it with a same-named account, tenant,
  or client belonging to the company currently being served — each company's own pack/dossier is
  the place to check for a same-name collision specific to that company.
- **A before/after comparison is mandatory for any change to an existing brand surface** — new
  work being reviewed for the first time doesn't have a "before," but a *change* to a shipped
  logo placement, color, or layout always does. The brand-architect's finding on a diff should name
  what changed and score both states, not just the new one.
- **One logical change per review pass.** Reviewing five unrelated visual changes as one verdict
  hides which one actually caused a regression — a related but new discipline invented for this
  seat, inspired by (not "mirroring") Rule 3's "one logical change per save," which in the source
  governs edit/save granularity during live editing, not how many changes a *reviewer* judges in
  one verdict pass.

## Contractor-buyer bend (for companies whose buyer is a trade owner/GC — see shared/contractor-buyer-psychology.md)

For a company whose buyer is a contractor/trade owner specifically — e.g. a B2B software company
selling to a residential-trade owner or GC — that buyer is not evaluating "does this look like a
2026 SaaS template" the way a tech buyer would; they're pattern-matching against **trade-industry**
software or vendors that have failed them before (a clunky QuickBooks add-on, a CRM built by a
non-trade vendor that looks cheap, a lead-gen site that felt like a bait-and-switch). Two things
follow for companies serving this kind of buyer:

1. **The bar to clear isn't "looks like a modern SaaS company" — it's "looks like it was built by
   people who understand my trade."** A generic-AI-template tell (purple gradient, stock office
   photo) reads to this buyer not as "unoriginal" but as "these people don't actually do this
   trade's work, this is a reskin." The photo-asset rules in brand-asset-usage.md (real jobsite
   imagery, not office stock) matter *more* here than they would for a horizontal SaaS product.
2. **Never approve a "clever" visual metaphor this buyer has to decode.** This buyer is often
   looking at this on a phone, in a truck, between jobs. A visual hierarchy that requires hovering,
   scrolling patiently, or parsing an abstract icon system to understand the value prop is an
   anti-pattern for this buyer even if it would read as "sophisticated" to a SaaS audience — see
   visual-hierarchy.md's F-pattern/above-the-fold rule, which this buyer's context makes load-bearing
   rather than optional.

**Apply this bend only when the company pack's `persona_file` is the contractor-buyer shape**
(`shared/contractor-buyer-psychology.md` — a B2B software company selling to trade owners/GCs). A
`local_service`/home-services company selling to homeowners uses
`shared/homeowner-buyer-psychology.md` instead (that buyer pattern-matches against a different
reference set entirely — see that file's own bend). A dental/medical practice or any other vertical
uses its own `persona_file` from its own pack — never point a dental or medical company at
`shared/homeowner-buyer-psychology.md`, which is the remodeling-homeowner persona, not a patient
persona.
