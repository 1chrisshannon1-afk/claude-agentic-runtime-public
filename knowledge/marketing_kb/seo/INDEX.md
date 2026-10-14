# SEO Domain — Index

Corpus for the `seo-architect` seat (technical + content SEO, schema, Core Web Vitals, local SEO for
service-area businesses) in the GTM agent department. This corpus is company-agnostic — it serves
any company the department runs a mission for; a company's own facts, numbers, and rulings live in
that company's own pack/dossier, never here. Grep-reachable on demand — this index is how an agent
finds the right section without reading the whole corpus. Every numeric/behavioral claim in every
file below carries a citation tag — `(official)`, `(third-party)`, `(internal-measured)`, or
`(internal doctrine)` — with a retrieval date, or is marked `UNVERIFIED — seeded, needs derivation`.
See house-style rules at the bottom of this file.

| File | Answers |
|---|---|
| `ANTI-PATTERNS.md` | What must this seat NEVER recommend — doorway pages, keyword stuffing, schema spam, cloaking, scaled/AI content abuse, link schemes, deprecated-schema recommendations, false P0-clean claims, porting a different vertical's benchmark numbers as fact. |
| `technical-seo-checklist.md` | What's the mechanical crawl/index/canonicalization/robots/sitemap correctness bar, and what's the weekly/monthly/quarterly operational cadence, and what are the P0 (Manual Action / Security Issue) risk surfaces and their tooling gap? |
| `schema-strategy.md` | Which Schema.org types should a SaaS company selling into a local/service-area vertical (and its contractor customers) actually deploy in 2026 — including the critical May 2026 FAQPage rich-result deprecation that changes prior doctrine? |
| `web-vitals-thresholds.md` | What are the exact LCP/INP/CLS thresholds, how are they measured (p75, mobile/desktop split), and how does the 2026 PSI-drops-CrUX-field-data change affect how an agent should pull this data? |
| `local-seo-for-contractors.md` | How does GBP/local-SEO doctrine (service-area setup, category selection, reviews, response time, NAP consistency, multi-location audits) apply to a service-area business (home services/contracting) specifically? |
| `keyword-research-doctrine.md` | How to do keyword research pre-launch (Keyword Planner-first, no GSC history yet), the intent-segmentation framework, "almost there" keywords, and the mandatory organic/paid alignment gate before any paid-spend recommendation? |

## House style, restated for anyone editing this corpus

- **"The source doctrine"** (used throughout this corpus) means a prior engagement's own GSC/
  local-ads playbooks and related skill files, originally written for a different vertical
  (storefront/appointment-based, not home services) and ported into this corpus where the
  underlying mechanism generalizes. It is cited as `(internal doctrine)`, never by naming the
  company or file it came from — the *vertical* itself may be named where doing so is useful
  doctrine (e.g. "patient" → "customer/homeowner" substitution guidance), but the specific company
  or source file never is.
- Every numeric/behavioral claim carries a citation tag with a retrieval date, or is marked
  `UNVERIFIED — seeded, needs derivation`. No unsourced numbers.
- A mechanism carried over from another vertical's doctrine is labeled `(internal doctrine)` — it
  is borrowed evidence from a different vertical, not independently re-verified for home services,
  even where the mechanism ports cleanly. See `shared/citation-style.md` for the full tag
  taxonomy.
- Numeric gates/rubrics/ladders (CWV thresholds, sitemap limits, review-count minimums) include
  explicit pass/reject examples in the file that defines them.
- A different vertical's **numbers** (CPC/CPA/CPL benchmarks, payer logic) never port as fact —
  only the **mechanism** (the gate structure, the threshold logic) ports; a number either gets
  independently re-derived and cited for home services, or is marked `UNVERIFIED — seeded from
  [vertical] analog, needs home-services derivation`.
- Every file ends with a "Contractor bend" section translating the doctrine for the home-services/
  contracting buyer archetype — phone-first, in a truck, burned by software/agencies before. See
  `shared/contractor-buyer-psychology.md` for the full persona (one of several persona files a
  company pack may select, alongside `shared/homeowner-buyer-psychology.md`).

## Cross-domain pointers (things found in the source doctrine that belong to a different domain)

- **Paid search (Google Ads) mechanics** — bid strategy, Quality Score internals beyond its CWV/
  cannibalization intersection with SEO, campaign structure — belongs to `paid_acquisition/` (see
  `paid_acquisition/INDEX.md`), not here. Referenced only where SEO and paid interact (the
  organic-alignment gate in `keyword-research-doctrine.md`).
- **GA4 / analytics measurement** (event tagging, conversion tracking, reporting recipes) belongs to
  `measurement/` (see `measurement/INDEX.md`). Referenced only where it appears as the post-click
  half of a GSC pre-click signal (`keyword-research-doctrine.md` briefly notes a GA4 blended-report
  pattern from the source doctrine's own paid/organic playbook but does not build it out — that
  belongs in `measurement/`).
- **Review-platform/reputation management as its own discipline** (drafting responses, escalation
  policy, review-request campaigns as a CRM workflow) is touched in `local-seo-for-contractors.md`
  only insofar as it's an SEO ranking input; the fuller reputation-management operational doctrine
  belongs in `reputation/` (see `reputation/INDEX.md`, which points back here for the ranking-factor
  half of the same material).
- **Local paid-lead platforms as a paid-channel strategy** (Google LSA budget/bid-mode setup, Yelp
  Ads contract terms, Thumbtack Promote budget allocation, Nextdoor Ads creative) belongs to
  `local/` (see `local/INDEX.md`); this corpus ports only the *organic-adjacent* mechanism (reviews
  and response time as ranking/lead-quality levers, which apply to organic map-pack ranking too)
  into `local-seo-for-contractors.md`, and explicitly does not build out local-ads campaign
  management doctrine.
- **Content calendar / content-marketing operations** (the 4-week calendar cadence, educational/
  social-proof/seasonal post mix) belongs to `content/` (see `content/INDEX.md`); this corpus
  touches content only at the keyword-to-content-brief boundary
  (`keyword-research-doctrine.md`'s intent segmentation and Helpful Content self-assessment) and
  does not build out a publishing calendar or content-ops doctrine.
