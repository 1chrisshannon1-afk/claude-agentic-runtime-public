# Competitor-audit method

Ported mechanism (internal doctrine, retrieved 2026-09-27 — a competitive-intelligence procedure this department has
carried forward from prior work). The discovery methods, tiering structure, and scoring rubric port
directly — they are channel-agnostic competitive-intelligence method, not tied to any one vertical or
company. This file is the *method* only; a specific company's own competitor set, tiering, and
current scoring read are that company's own facts and live in that company's own dossier/positioning
doc, never here.

**Check whether the company already has a live, sourced competitive sweep before running a new one**
— most companies this department serves will have a positioning/competitive-landscape doc
(`market-analyst`'s own output, or the company's own product-positioning doc) recording its most
recent sweep. This file is the *method* for running the next one; that company doc is the most recent
*result*. Do not re-run a full sweep from scratch when a company's existing sweep is still current —
refresh only the parts that have plausibly moved (a competitor's pricing page, a new feature launch)
rather than re-deriving the whole landscape.

## Purpose

Competitive intelligence informs keyword strategy, ad copy, pricing presentation, content gaps, and
positioning. This audit produces a ranked competitor profile and an actionable gap analysis — never
just a list of "here's who else exists."

## Section 1 — competitor identification

Cast a wide net, then narrow. Discovery methods, generalized across a B2B SaaS competitor set and a
local-service-business competitor set (the exact mix depends on the company's `business_model`):

| Method | How | What it reveals |
|---|---|---|
| **Direct search** | Search core buyer-intent terms for this company's category and record who ranks organic, paid, and in any AI-overview panel. | Direct search competitors and how the category is currently being answered by search engines. |
| **Ad-platform auction insights** | Once the company runs paid search: impression share, overlap rate, outranking share against named competitors. | Paid-search competitors and relative position — see `paid_acquisition/account-audit-rubric.md`. |
| **Vendor/review comparison sites** | For a B2B SaaS company: G2, Capterra, Software Advice for the company's category. For a `local_service` company: Google/Yelp/Angi/Houzz listings for the same service area. | Who else is positioned in this category, and how reviewers frame the comparison. |
| **Trade-press and industry forums** | Category-relevant forums and communities — for a contractor/home-services software company, this concretely means trade-specific communities (e.g. r/Construction, r/Contractor, JLC forums) and trade-association newsletters, generalized for other verticals as the analogous forum/community set. | What real buyers actually say about tools/vendors they've tried — richer signal than review-site copy. |
| **Operator/customer input** | Ask real prospects and customers: "what do you use now / what did you look at instead?" | Real-world competitors data sources might miss — this is often the single highest-value source for a pre-launch or early-stage product, especially for a buyer whose actual behavior (word of mouth, in-person conversation) undercounts in digital discovery methods (see that persona's own behavioral facts in `contractor-buyer-psychology.md` or `homeowner-buyer-psychology.md`). |
| **Vendor's own marketing/help docs** | The vendor's own site, help center, pricing page. | Ground truth about what a competitor actually claims and ships — help/support docs are more reliable than marketing copy for verifying an actual feature set or mechanism. |

**Competitor tiers** (generalized, definitions company-agnostic):

| Tier | Definition | How many to track |
|---|---|---|
| **Tier 1 — Primary** | Direct competition for the same buyer, same job, same or adjacent price point. | 3–5 |
| **Tier 2 — Secondary** | Overlaps on part of the job (e.g. a single-function point tool covering one piece of the workflow, such as a pure takeoff tool or a pure CRM/invoicing tool for a contractor-software company) or a different-but-adjacent segment (e.g. commercial or new-construction software, adjacent to a residential-remodeling-focused product). | 3–5 |
| **Tier 3 — Aspirational** | Market leader worth benchmarking even if not a direct competitor for the same buyer today (an architecturally-related but not directly-competing product, useful as proof a broader approach works). | 1–3 |

A specific company's own current tiering (which named vendors sit in which tier, and why) is that
company's own fact — record it in that company's own positioning/competitive-landscape doc, sourced
and dated, never invented here or assumed to carry over from a different company's competitor set.

**For contractor/home-services software companies specifically** (internal doctrine, retrieved 2026-09-27 — vertical
application of the generalized method above): buyer-intent direct search typically means terms like
"contractor estimating software," "AI construction estimate," or a specific-job variant such as
"bathroom remodel estimate software"; the relevant vendor/review comparison sites are G2, Capterra,
and Software Advice under categories like "construction estimating software" or "contractor CRM";
and a vendor's own marketing/help docs are the right ground-truth check for verifying an actual
claimed feature set (support/help docs over marketing copy) before crediting or discounting a
competitor's mechanism claim.

## Section 2 — the seven analysis dimensions

Generalized across a SaaS competitor set and a local-service competitor set (a `local_service`
company's ads/SEO/website/reputation/social dimensions may need re-mapping if evaluating other local
businesses rather than software products — that re-mapping is the company's own analysis, not
restated here):

1. **Product/mechanism** — what does the competitor actually *do* under the hood (a rules/logic
   engine vs. LLM inference vs. manual human work vs. a hardware-based approach)? For a company whose
   own positioning rests on a mechanism differentiator, this is often the single most important
   dimension — verify from the vendor's own documentation, never from marketing copy or a demo video
   alone (a demo can look identical whether the underlying output is derived or guessed — a live
   demo reaction is a warning to verify further, not proof the underlying claim holds).
2. **Pricing and packaging** — entry price, what's included at entry, usage caps/credit meters, and
   how the pricing frame is presented (a monthly-cost frame vs. a pays-for-itself/revenue-moment
   frame — see the relevant persona file's price-framing fact and
   [`pricing/price-position-watch.md`](../pricing/price-position-watch.md)).
3. **Positioning and messaging** — headline value prop, target segment language, and whether they
   claim capabilities they don't actually ship (this is where a competitor's own never-claim
   violations become an opportunity, not just a fact to note).
4. **Accuracy/trust signal** — how does the competitor substantiate its output is trustworthy? A
   named citation to an authoritative source, a case study, nothing? Assess whether each competitor
   has a real trust anchor or is asking for blind trust, and whether this company's own trust anchor
   (if it has one — a published industry reference, a verifiable methodology) is a genuine
   differentiator worth leading with.
5. **Search/content footprint** — organic keyword coverage, content depth on buyer-intent topics,
   whether they own category-defining search terms.
6. **Reviews and reputation** — rating and volume on the relevant review platform, and specifically
   what reviewers *complain about* (feature gaps, support quality, pricing surprises) — complaints
   are gap-analysis gold.
7. **Recent movement** — funding, feature launches, pricing changes in the last 6 months. Treat any
   single-source press figure as directional only, never as a precise measurement, per
   `citation-style.md`.

## Section 3 — competitive matrix and gap analysis

Build a comparison table (dimension × competitor), then produce:

1. **Where we lead** — advantages to protect and lead with in messaging.
2. **Where we lag** — gaps to close, prioritized by buyer impact (not by what's easiest to fix).
3. **Where competitors are vulnerable** — weaknesses to position against honestly (never
   fabricated — see `department-anti-patterns.md`).
4. **Quick wins** — low-effort messaging/positioning fixes.
5. **Strategic moves** — larger initiatives that shift competitive position over time.

## Scoring

Rubric structure ported directly; criteria are stated generically and re-derived per vertical/company
when applied:

| Rating | Criteria |
|---|---|
| GREEN | Clear, verified differentiation from Tier 1 on the dimension the company's own positioning leads with, no unaddressed pricing gap, no unanswered trust-signal gap. |
| YELLOW | Differentiated on the lead dimension but trailing on 1–2 other dimensions (pricing position, content footprint) — gaps identified and addressable. |
| RED | No clear differentiation communicated, or trailing on 3+ dimensions with no plan to close them. |

**A company's own honest current read (which rating, and why) is that company's own fact** —
sourced and dated in its own positioning doc, never assumed or rounded up here. A rating that depends
on real-world validation still pending (e.g. a mechanism differentiation that is real in principle but
not yet proven at scale) should stay at the lower rating until that validation actually exists — never
round up in copy or an internal report before it does.

## Contractor bend

The competitor audit itself is invisible to the buyer, but its findings directly shape what this
buyer is told and how. Two bend-specific cautions, generalized across both persona files this
department maintains: **first**, for a time-poor, non-desktop-comparison-shopping buyer (see
`contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`), never build competitive copy
around a feature comparison table full of checkmarks and X's — this buyer doesn't shop like a SaaS
evaluator running a spreadsheet comparison; they ask a peer or try one thing and judge it fast. Lead
competitive positioning with the one concrete difference that matters to their actual decision, not a
twelve-row feature grid. **Second**, never let a competitive gap-analysis finding turn into
disparagement in copy — `department-anti-patterns.md` covers this, but it bears repeating here: this
kind of buyer is skeptical of vendors who badmouth competitors as much as they're skeptical of
vendors who overclaim their own product.
