# Measurement Domain — Index

Corpus for the `measurement-architect` seat (GA4 events/key events, GTM container governance,
consent mode, enhanced + offline conversions, call tracking, UTM standard, ads↔CRM reconciliation;
owner of `metrics.json`) for any company the GTM agent department runs. Grep-reachable on demand — this
index is how an agent finds the right section without reading the whole corpus. Every numeric/
behavioral claim in every file below carries a citation tag — `(official)`, `(third-party)`,
`(internal-measured)`, `UNVERIFIED — seeded, needs derivation`, or `UNVERIFIED (primary source
unreachable: <url>)` — with a retrieval date. See house-style rules at the bottom of this file.

**Seat status (2026-09-28):** `measurement-architect` is not yet a registered agent seat as of this
writing. Per `social/INDEX.md`'s own seat-status note,
doctrine here should be read as forward-looking discipline for whoever fills a measurement seat in
the GTM department (most likely an existing generalist seat until a dedicated one is built), not as
a citation to an already-live agent.

| File | Answers |
|---|---|
| `ANTI-PATTERNS.md` | What must this domain NEVER let any seat do or recommend — hard-gating a tag on consent with no modeled fallback, sending raw PII into GA4/hashed-conversion/Customer Match fields, reporting raw volume as qualified leads, silently redefining a registered metric, substituting `0` for missing data, under-sample rate reporting, causal claims from association-only data, ad hoc UTM vocabulary, claiming verification without checking live behavior, unverified state call-recording consent claims, fabricated cross-vertical benchmarks. |
| `ga4-event-design.md` | How to design a GA4 event taxonomy that answers real business decisions — recommended-vs-custom events, naming conventions, hard platform limits, PII rules, key-event discipline, the tracking-plan artifact. |
| `gtm-container-governance.md` | How a GTM container's workspaces, versions, and publish permissions should be governed so a mistaken or malicious tag change can't reach live traffic unreviewed. |
| `consent-mode.md` | How Google Consent Mode v2 actually behaves — the four consent signals, default/update sequencing, and why a hard-gated tag silently under-reports rather than visibly failing. |
| `enhanced-and-offline-conversions.md` | How to close the gap between an ad click and a real-world outcome that happens later or off-platform — Enhanced Conversions (unified web + leads setting, since April 2026) vs. Offline Conversion Import, hashing rules, the GCLID capture requirement. |
| `call-tracking.md` | How phone-call measurement works when the call, not the form, is the primary conversion — dynamic number insertion vs. NAP consistency, what a call-tracking platform can/can't verify, recording-disclosure legal exposure. |
| `utm-standard.md` | The mandatory UTM tagging convention — the five parameters, formatting rules, the self-referral trap, and the link registry. |
| `reconciliation.md` | Why Ads, GA4, and the CRM disagree by design, the 4-signal test for calling a conversion "live," and the reconciliation cadence that catches drift between them. |
| `metric-registry-doctrine.md` | Why a metric's id is frozen once anything depends on it, why a missing value renders `missing` never `0`, and the minimum-sample-size gate before a rate is reportable. |
| `reporting-and-dashboards.md` | The association-vs-causation discipline for any report claim, the minimum evidence bar, and what a recurring report structurally must contain. |

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a citation tag with a retrieval date, or is marked
  `UNVERIFIED — seeded, needs derivation` (a number ported from an analogous vertical or asserted
  from general knowledge with no direct source check) or `UNVERIFIED (primary source unreachable:
  <url>)` (a primary source that blocked automated retrieval, per `shared/citation-style.md`). No
  unsourced numbers.
- Legal/regulatory claims outside this domain's own platform-mechanics scope (state wiretapping law,
  HIPAA, TCPA) are flagged and referred to the `compliance/` domain rather than asserted here as
  settled — see `call-tracking.md` §4 for a worked example of this referral pattern.
- Dental-vertical or any other cross-company **numbers** never port as fact — only the **mechanism**
  (a gate structure, a threshold, a verification procedure) ports; a number is either independently
  re-derived and cited, or marked `UNVERIFIED — seeded from [vertical] analog, needs [this
  company]-specific derivation`.
- A metric's registered id, once anything depends on it, is never silently redefined — see
  `metric-registry-doctrine.md` §2. A missing value is never rendered as `0` — see the same file §3.
- Numeric gates/thresholds/limits (GA4 event limits, minimum sample sizes) include explicit pass/
  reject examples in the file that defines them.
- Every file ends with a "Contractor bend" section translating the doctrine for a small
  owner-operated home-services/trade business archetype — phone-first, in a truck, burned by
  software/agencies before, usually without in-house analytics staff of their own.
  `shared/homeowner-buyer-psychology.md` and `shared/contractor-buyer-psychology.md` are two of
  several persona files a company pack may select — a company pack for a different vertical
  (e.g. a dental practice) selects and reads its own persona file from its own pack instead.

## Cross-domain pointers (things referenced here that belong to a different domain)

- **SEO's technical/schema/local doctrine** — `seo/technical-seo-checklist.md`,
  `seo/schema-strategy.md`, `seo/local-seo-for-contractors.md` — is referenced only where it
  intersects measurement (the NAP-consistency conflict with call-tracking DNI in `call-tracking.md`
  §1; the cloaking-adjacent crawl-parity check referenced from the same file). This corpus does not
  restate SEO doctrine; it cites it.
- **Paid-acquisition mechanics** (bid strategy, campaign structure, budget sizing) belong to the
  `paid_acquisition/` domain — this corpus's `reconciliation.md` and
  `enhanced-and-offline-conversions.md` reference paid-acquisition's own measurement-and-attribution
  doctrine as the origin of the 4-signal test, but do not build out bidding or budget doctrine here.
- **Compliance-owned legal questions** (state consent-law specifics, HIPAA marketing rules, TCPA/
  A2P 10DLC messaging law) are flagged as `UNVERIFIED` and referred to the `compliance/` domain
  rather than settled in this corpus — see `call-tracking.md` §4 and `consent-mode.md` §4 for the
  referral pattern this corpus follows consistently.
- **The dataviz/visual-design rules a dashboard's chart rendering should follow** are adapted briefly
  in `reporting-and-dashboards.md` §3 `(internal doctrine)`; a fuller design-
  system-level treatment of chart construction belongs to whatever design-system doctrine the
  department eventually maintains, not to this measurement corpus.
