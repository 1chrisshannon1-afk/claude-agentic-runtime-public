# Schema Strategy — Structured Data for a SaaS + Local-Service Business

A company that sells SaaS into a local/service-area vertical (e.g. software for contractors) is
unusual in needing **two** schema identities on the same domain family: a `SoftwareApplication`
identity (it's a SaaS product) and, for any future local/service-area presence, a `LocalBusiness`-
family identity. Most schema guidance online assumes one or the other, not both. This file covers
what to deploy, what NOT to deploy (see the May 2026 FAQPage deprecation below — this is the
single most important fact in this file), and how to validate.

---

## 1. The May 2026 FAQPage deprecation — read this before recommending FAQ schema

**Google removed the FAQ rich result from Search entirely, effective May 7, 2026, and removed its
own documentation for the feature in the June 2026 changelog** (official, Google Search Central
changelog, retrieved 2026-09-05: https://developers.google.com/search/updates). Prior to removal,
eligibility was already narrowed to "well-known, authoritative government and health websites"
(official, same source, per the September 2023 update note) — meaning FAQPage schema had already
stopped working as a general-purpose CTR lever for a general-audience SaaS business well before
the full removal.

**What this means in practice:**
- Marking up FAQ content in `FAQPage` JSON-LD today produces **no visible rich-result change** in
  Google Search for any site. It is not harmful to leave existing markup in place (no penalty for
  having it), but it must **never be recommended as an SEO win** going forward — that recommendation
  is stale as of any doctrine written before mid-2026. See `ANTI-PATTERNS.md` §7.
- Doctrine written before mid-2026 commonly still lists `FAQ` schema as a recommended type to
  enable rich results (star ratings, prices, FAQ accordions) (internal doctrine, retrieved
  2026-09-05). **That specific claim is now incorrect for FAQ specifically** and should not be
  ported forward as current doctrine — treat any such reference found in an older source as stale,
  and flag it as a stale-source finding rather than silently correcting it upstream in a source
  this corpus doesn't own.
- **What still works and is worth doing:** writing genuinely useful, well-structured on-page FAQ
  *content* (not the schema, the actual reader-facing text) remains valuable for: (a) Google's AI
  Overviews and other generative-answer surfaces, which draw from page content regardless of
  schema presence, (b) the "helpful content" / people-first quality signal (see
  `keyword-research-doctrine.md`), and (c) genuinely answering the buyer's actual pre-purchase
  questions, which is the entire point of an FAQ section — the schema markup was always a
  distribution mechanism for the content, never the value itself. Keep writing FAQ content; stop
  citing `FAQPage` schema as why.

## 2. `SoftwareApplication` — a SaaS company's core product identity

**Key properties** (official, Schema.org, retrieved 2026-09-05: https://schema.org/SoftwareApplication):

| Property | Use for a SaaS product |
|---|---|
| `applicationCategory` | e.g. `"BusinessApplication"` — text or URL |
| `operatingSystem` | `"Web"` for a browser-based SaaS |
| `offers` | An `Offer`/`Demand` object per pricing tier (see the company's own pricing pack for current tier structure — never hardcode a price here that could drift) |
| `aggregateRating` | Only if genuine, visible-on-page review data exists to back it — see the authenticity note below |
| `featureList` | Real product capabilities specific to the product |
| `softwareVersion` | Optional; skip if the product isn't version-numbered publicly |

**Authenticity constraint (critical — ties directly to `ANTI-PATTERNS.md` §3):** "The schema
itself does not mandate that review or rating data be genuine... any verification of authenticity
would depend on implementation practices by individual publishers" (official, Schema.org semantics
description, retrieved 2026-09-05) — meaning **Schema.org's spec will not stop you from lying, but
Google's spam policy will penalize you for it.** Never populate `aggregateRating` with a number
that doesn't match what's actually rendered and verifiable on the page (a real review widget, a
real testimonials count). If the company has no review platform live yet, omit `aggregateRating`
entirely rather than estimate or aspire to a number.

**Where it goes:** The marketing homepage (`/`) and a features page are the natural placements —
see the company's own as-is state doc/pack for how its build pipeline would need to inject this
(this is commonly a gap, not a landmine — check that doc's own gap list for the specific company).

## 3. `Organization` — brand identity, knowledge panel eligibility

Minimal viable properties: `name`, `url`, `logo` (per Google's logo guidelines — a URL to a
reasonably sized, square-ish image), `sameAs` (links to verified social/professional profiles —
LinkedIn, etc.), and `contactPoint` if there's a real support channel. This is what feeds a
Knowledge Panel and disambiguates the brand entity from any other similarly-named company. Low
effort, low risk, worth doing once, rarely needs revisiting.

## 4. `LocalBusiness` (and its more specific subtypes) — for local/service-area presence

**Required properties for eligibility** (official, Google Search Central "Local Business" doc,
retrieved 2026-09-05: https://developers.google.com/search/docs/appearance/structured-data/local-business):
`address` (as a `PostalAddress` object) and `name`. Everything else — `telephone`, `geo`,
`openingHoursSpecification`, `priceRange`, `url` — is recommended, not required, but each adds
signal.

**A company that is itself a local service business deploys the relevant `LocalBusiness` subtype
directly on its own domain** — e.g. `HomeAndConstructionBusiness` for a contracting/remodeling
company, `Dentist` for a dental or other medical-practice storefront (official, Schema.org,
retrieved 2026-09-27: https://schema.org/HomeAndConstructionBusiness,
https://schema.org/Dentist) — using the required/recommended properties above. **For a SaaS
company selling to contractors, this section is normally
written for that company's *contractor customers*, not for the SaaS company itself** — a SaaS
company without a physical service area has no reason to deploy `LocalBusiness` schema on its own
marketing domain. It's documented here because the `seo-architect` seat's customer-facing guidance
(help docs, onboarding content, any "how to set up your GBP" content a company ships to its own
contractor customers) needs to be correct, and because a future customer-facing content play
("local SEO tools for contractors," a customer-facing SEO feature) would need this doctrine. If a
given SaaS company itself ever adds office locations with public-facing addresses, revisit for that
company specifically.

**Quality guideline:** Google's own documentation for this type does not spell out "must match your
Google Business Profile" as an explicit written rule (verified directly against the doc,
retrieved 2026-09-05 — do not over-claim a rule that isn't stated), but the practical consequence
of *not* matching is real: NAP (Name/Address/Phone) inconsistency across your own schema, your GBP,
and any citation directory is a well-established local-ranking drag (see
`local-seo-for-contractors.md`) even though it isn't framed as a structured-data *penalty* per se.
Treat "match your GBP exactly" as a strong best practice, not a documented hard requirement.

## 5. `Service` schema — for a contractor customer's individual service pages

Recommended per the source doctrine (internal doctrine, retrieved 2026-09-05) for pages like
"Kitchen Remodeling," "Roofing," etc. — pairs naturally with `LocalBusiness` via the `provider`
property. Relevant to a company's customer-facing guidance, not to that company's own marketing
site (for a SaaS company selling into this vertical).

## 6. `Review` / `AggregateRating` on any page

Same authenticity constraint as §2. Google's July 2026 Review Snippets update specifically added
guidance on "fake and undisclosed incentivized reviews" (official, retrieved 2026-09-05) — this is
a live enforcement area, not a dormant rule. Never mark up review data that isn't visibly present
and verifiably real on the same page.

## 7. What NOT to deploy right now

- **`FAQPage`** as an SEO lever — see §1. (Keep the content; drop the "this helps SEO" framing.)
- **`HowTo`** — not requested in this corpus's scope and Google has been steadily narrowing
  `HowTo` rich-result eligibility over recent years; verify current status before recommending if
  it comes up (not independently re-derived here — flag as **UNVERIFIED, needs derivation** if a
  future task needs it).
- Any schema type whose data doesn't match visible on-page content, per §2/§6's authenticity
  constraint and `ANTI-PATTERNS.md` §3.

## 8. Validation cadence

Validate via Search Console's Structured Data / Rich Results reports. Fix errors immediately; fix
warnings within 7 days (internal doctrine, retrieved 2026-09-05 — mechanism ported as-is,
vertical-agnostic). Google's own Rich Results Test tool
(https://search.google.com/test/rich-results) is the pre-deploy check before anything ships.

---

## Contractor bend

For a SaaS company's own marketing site, schema work is invisible to the GC buyer (see
`shared/contractor-buyer-psychology.md`) and should stay that way — it's plumbing, not a feature
to sell them. Where this *does* surface to that buyer is in the company's product itself, if/when
it ships anything that touches the contractor's own web presence (a "local SEO checklist" feature,
GBP guidance in onboarding, etc.). For that surface: this buyer will not know what "schema markup"
means and doesn't need to — translate `LocalBusiness` schema
guidance into "make sure your business name, address, and phone number are typed identically
everywhere online" and `Review`/`AggregateRating` guidance into "never let anyone talk you into
buying fake reviews or a review-schema shortcut — Google is actively cracking down on exactly that
in 2026, and it can cost you your whole listing." This buyer has almost certainly been offered a
"guaranteed 5-star reviews" service by some vendor at some point; naming that pattern explicitly as
the thing to avoid lands better than an abstract policy citation.
