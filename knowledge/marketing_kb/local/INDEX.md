# Local Domain — Index

Corpus for the local-presence and local-lead-marketplace lane of a GTM agent
department (GBP, local listing platforms, marketplace-lead platforms, NAP hygiene, and the
economics of comparing them). Grep-reachable on demand — this index is how an agent finds the right
section without reading the whole corpus. Every numeric/behavioral claim in every file below carries
a citation tag — `(official)`, `(third-party)`, `(internal-measured)`, or `(internal
doctrine)` — with a retrieval date, or is marked `UNVERIFIED — seeded, needs derivation` or
`UNVERIFIED (primary source unreachable: <url>)`. See house-style rules at the bottom of this file.

| File | Answers |
|---|---|
| `ANTI-PATTERNS.md` | What must a GTM agent NEVER recommend on a local-presence or local-marketplace platform — duplicate/fake profiles, review solicitation/gating/incentivizing, fabricated review-response claims, cross-brand entanglement, porting dental-vertical numbers as home-services fact, and more. |
| `gbp-optimization.md` | Google Business Profile doctrine — one-profile-per-business, multi-brand/same-owner rules, category selection, Services, Posts, Q&A, content policy, suspension risk and reinstatement, verification. |
| `yelp.md` | Yelp's no-solicitation rule and its enforcement mechanism (Consumer Alerts), the recommendation/filter algorithm, business-account access risk (all-or-nothing user permissions), and Yelp Ads CPC basics. |
| `angi-homeadvisor.md` | Angi/HomeAdvisor team roles (Admin vs. Associate), the official Lead Credit Guidelines (30-day dispute window, store-credit-only, eligible/ineligible categories), and third-party-reported dispute-denial context. |
| `thumbtack.md` | Thumbtack's two lead types (Instant Match/Direct Leads vs. Opportunities) and their different pricing/response mechanics, and the pro-set max-lead-price and weekly-budget levers. |
| `houzz-pro.md` | Houzz Pro's Teams roles (Admin, Field Crew/Design Team, and Finance) and the CRM/marketplace product's own access-and-visibility structure. |
| `nextdoor.md` | The Business Page vs. Ads Manager split — free organic surface vs. paid advertising, and what's structurally different between them. |
| `bbb-apple-bing.md` | BBB accreditation eligibility and the 8 Standards for Trust; Apple Business Connect (Apple Maps) claim/manage basics; Bing Places for Business verification methods and escalation path. |
| `nap-consistency.md` | The Name/Address/Phone canonical-record discipline, why call-tracking numbers are the most common engineered source of NAP drift, and the rebrand/move/merger and audit disciplines that keep every platform in sync. |
| `lead-marketplace-economics.md` | Why "cost per lead" is the wrong cross-platform comparison metric, the fully-loaded cost-per-booked-job formula, and the platform-specific inputs (credits, labor cost, bundled software fees) that make a naive comparison misleading. |
| `dental-practice-local-notes.md` | Where this directory's local-presence doctrine diverges for a dental/medical practice buyer (GBP category/licensure stakes, review-reply content-risk asymmetry, provider-name NAP complexity) — contains **no** HIPAA/PHI doctrine; that lives in `compliance/hipaa-marketing-for-practices.md`. |

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a citation tag with a retrieval date, or is marked
  `UNVERIFIED — seeded, needs derivation` (a number ported from an analogous vertical with no direct
  source check) or `UNVERIFIED (primary source unreachable: <url>)` (a primary source that blocked
  automated retrieval — hhs.gov and ecfr.gov are known blockers; cite the best reachable mirror and
  mark the claim unverified regardless).
- **Claim ids are a single shared `[KB-LOCAL-NNN]` sequence across every file in this directory** —
  never reused across files. Current allocation as of 2026-09-27 (check the live files before
  assuming this table is still current — a later edit may extend a range):

  | File | Range |
  |---|---|
  | `gbp-optimization.md` | 001–016 |
  | `yelp.md` | 001–012 (pre-dates the shared-sequence convention; do not extend this range — treat 001-012 as claimed exclusively by `yelp.md`) |
  | `angi-homeadvisor.md` | 013–021 |
  | `nap-consistency.md` | 017–022 |
  | `thumbtack.md` | 022–029 |
  | `bbb-apple-bing.md` | 023–030 |
  | `houzz-pro.md` | 030–034 |
  | `nextdoor.md` | 035–039 |
  | `lead-marketplace-economics.md` | 040–046 |
  | `dental-practice-local-notes.md` | 047–056 |

  **Known pre-existing overlaps, corrected 2026-09-27 against the live files** (the ranges above
  are allocated ranges, not exclusive-use guarantees, and several genuinely collide): `yelp.md`
  (001–012) and `gbp-optimization.md` (001–016) both start at 001; `gbp-optimization.md` (001–016)
  and `angi-homeadvisor.md` (013–021) overlap at 013–016 — both files independently define
  `[KB-LOCAL-013]` through `[KB-LOCAL-016]`, so a bare reference to any id in that range is
  ambiguous and must be file-qualified (e.g. `gbp-optimization.md [KB-LOCAL-013]` vs.
  `angi-homeadvisor.md [KB-LOCAL-013]`); `angi-homeadvisor.md` (013–021) and `nap-consistency.md`
  (017–022) overlap at 017–021; `nap-consistency.md` (017–022) and
  `thumbtack.md` (022–029) overlap at 022; `thumbtack.md` (022–029) and `bbb-apple-bing.md`
  (023–030) overlap at 023–029; `bbb-apple-bing.md` (023–030) and `houzz-pro.md` (030–034) overlap
  at 030. (An earlier version of this note said "`thumbtack.md` reusing 016" — that was wrong:
  `thumbtack.md`'s own claim ids run 022–029 only, never 016; corrected here rather than
  perpetuated.) These predate this file and are flagged here rather than silently perpetuated — a
  future edit that touches any of the files above should renumber to close the specific overlap it
  touches rather than add to it, but this index does not renumber them unilaterally since doing so
  would break any existing cross-reference to those ids from outside this directory. **The next new
  claim id in this directory is `[KB-LOCAL-057]`** — confirm against the live files before using it,
  since another author may have extended a range since this index was last regenerated.
- Dental/medical-vertical **numbers** never port as fact into a home-services claim, and
  home-services numbers never port as fact into `dental-practice-local-notes.md` — only the
  *mechanism* ports; see that file's own scope-boundary section and `seo/INDEX.md`'s identical rule
  for the dental-analog direction.
- **HIPAA/PHI doctrine lives exclusively in `compliance/hipaa-marketing-for-practices.md`.**
  `dental-practice-local-notes.md` cites it but never restates or paraphrases a compliance rule —
  if a claim in this directory starts to look like a compliance rule instead of a local-presence
  mechanic, it belongs in the compliance file, not here.
- Every platform file ends with a vertical-specific "bend" section, not a single universal one. The
  Contractor bend is **for home-services/contractor (`local_service`) companies**: it translates the
  doctrine for the owner-operator residential-remodeling GC archetype — phone-first, in a truck,
  burned by software/agencies before. The relevant end-customer persona file for a `local_service`
  company is `shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a
  DIFFERENT persona (a B2B software-buyer shape for a company that itself sells *to* contractors) and
  is cited here only as an optional illustration of how an owner-operator behaves, never as the
  persona a `local_service` company's own pack would select. A specific company's own actual buyer —
  including its real revenue band — lives in that company's own persona file, never asserted here.
  `dental-practice-local-notes.md`'s own bend section addresses the dental/medical practice-owner
  archetype instead, per its own note.

## Cross-domain pointers (things a reader here might expect but that belong to a different domain)

- **Local SEO ranking mechanics for GBP/map-pack** (as opposed to the account-operability doctrine
  in `gbp-optimization.md` here) belong to `seo/local-seo-for-contractors.md` — this directory
  covers *how the platforms work and what not to do on them*; the SEO domain covers *how they affect
  ranking*.
- **Review-acquisition campaign operations, response-time-as-ranking-input, and reputation-management
  workflow** beyond the platform-compliance mechanics in `yelp.md`/`gbp-optimization.md` belong to
  `reputation/` (`review-acquisition-compliant.md`, `platform-review-policies.md`,
  `review-velocity-metrics.md`).
- **Paid-channel campaign structure, bid strategy, and budget-as-formula** for any platform in this
  directory that also runs paid ads (Yelp Ads, Nextdoor Ads Manager, Thumbtack's per-lead pricing as
  a paid channel) belongs to `paid_acquisition/` for the campaign-management doctrine; this
  directory documents only the platform mechanics and, in `lead-marketplace-economics.md`, the
  cross-platform cost comparison method — never bid strategy or ad-creative doctrine.
- **HIPAA, PHI, and all patient-privacy/compliance doctrine** belongs exclusively to
  `compliance/hipaa-marketing-for-practices.md` — see the House style note above.
