# Reputation Domain — Index

Grep-reachable index for reputation-management doctrine (review acquisition, platform policy,
response drafting, escalation) in a GTM agent department. This corpus is not
meant to be read wholesale — find the file that answers your question, read that file only. Every
numeric/behavioral claim in `review-acquisition-compliant.md`, `platform-review-policies.md`,
`review-velocity-metrics.md`, and `ANTI-PATTERNS.md` carries a stable id `[KB-REP-NNN]`
and a citation — `(official)`, `(third-party)`, `(internal-measured)`, or `(internal
doctrine)` — with a retrieval date, or is marked `UNVERIFIED — seeded, needs derivation` or
`UNVERIFIED (primary source unreachable: <url>)`. See house-style rules at the bottom of this file.
This file (INDEX.md) itself defines no claim ids of its own.

**Relocation note (2026-09-27):** `never-do.md`, `escalation-triggers.md`, and
`response-templates-by-severity.md` moved here from `content/reputation/` and de-specialized
(company names/paths removed) 2026-09-27 — see `content/INDEX.md` for the redirect note left in
their old location. Everything else in this directory (`review-acquisition-compliant.md`,
`platform-review-policies.md`, `review-velocity-metrics.md`, this file, `ANTI-PATTERNS.md`) is new
as of this same change. **These three relocated files still use their legacy inline `Citation
(...)` format and define no `[KB-REP-NNN]` ids of their own (correction, 2026-09-27 follow-up
review, finding 4) — the `[KB-REP-NNN]` claim-id requirement below applies only to the five files
newly authored in this domain, not to the three relocated ones. A future pass that assigns the
three relocated files stable ids should continue the sequence from `[KB-REP-042]` (the highest id
already in use in this directory: `platform-review-policies.md` 001-013,
`review-acquisition-compliant.md` 014-023, `review-velocity-metrics.md` 024-033,
`ANTI-PATTERNS.md` 034-041 — no collisions to avoid below 042).**

**Seat status:** `content-strategist` is a registered seat (see `content/INDEX.md`'s own
seat-status note) — but a dedicated reputation-specific seat does not yet exist, so read
"reputation-focused seat" references in this corpus as forward-looking discipline for whoever
fills that role next, not as a citation to an already-live agent.

| File | Answers |
|---|---|
| [`review-acquisition-compliant.md`](review-acquisition-compliant.md) | How does a business ask customers for reviews without gating — what does the FTC's 2024 rule (16 CFR Part 465) actually require section by section, and what does a fully compliant ask-flow look like end to end? |
| [`platform-review-policies.md`](platform-review-policies.md) | What does each major platform (Google, Yelp, Facebook, Angi, Houzz, BBB) actually permit and forbid around soliciting, responding to, and disputing reviews — and which of these are confirmed vs. still unverified? |
| [`review-velocity-metrics.md`](review-velocity-metrics.md) | How many reviews, how recent, what star rating, and how fast a response — with real numbers — before a review profile measurably changes a prospect's decision? |
| [`response-templates-by-severity.md`](response-templates-by-severity.md) | How does a review response change by star rating (5/4/3/2/1)? What's the required structure for a negative-review response? |
| [`escalation-triggers.md`](escalation-triggers.md) | When does a review response require the operator's hand instead of an agent draft? What review content stops an agent cold? |
| [`never-do.md`](never-do.md) | What review/reputation tactics are illegal (FTC) or bannable (platform policy) — gating, incentivized sentiment, fake reviews, threats, astroturfing? |
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a reputation-focused seat NEVER recommend, across acquisition, response drafting, and escalation? |

## Reading order for a new task

- **Setting up or auditing a review-acquisition program:** start with `review-acquisition-compliant.md`,
  then check the specific platforms involved against `platform-review-policies.md`, then benchmark
  the current profile against `review-velocity-metrics.md`.
- **Drafting a response to an existing review:** start with `escalation-triggers.md` to confirm the
  review doesn't need the operator's hand first, then `response-templates-by-severity.md` for
  structure, checking every draft against `never-do.md` and `ANTI-PATTERNS.md` before proposing it.

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a citation tag with a retrieval date, a stable
  `[KB-REP-NNN]` claim id, and either a real source or an explicit UNVERIFIED marker — no unsourced
  numbers, and no claim presented as settled when its primary source could not be reached. See
  `shared/citation-style.md` for the full tag taxonomy.
- When a primary source blocks automated retrieval (this happened repeatedly in this domain — FTC's
  own ftc.gov rule page, the Federal Register notice, and ecfr.gov's direct rule page all returned
  403/redirect-loop responses on 2026-09-27), the best reachable mirror is cited instead (Cornell
  Law's eCFR mirror, `law.cornell.edu`, worked for the FTC rule text) and the fact that the primary
  was unreachable is stated alongside the mirror citation — never silently substituted without
  saying so.
- When NO source — primary or mirror — could be reached (this happened for Facebook, Angi, Houzz,
  and BBB in this domain), the claim is marked `UNVERIFIED (primary source unreachable: <url>)`
  with the exact URL(s) attempted, never presented as settled fact and never silently dropped from
  the corpus — a platform this corpus can't yet confirm rules for is still a platform a GC uses, so
  the gap itself is useful information for whoever reads this file next.
- Dental-vertical or other analogous-vertical **numbers** never port as fact — only the **mechanism**
  ports (see `never-do.md`'s and `escalation-triggers.md`'s own "mechanism, not the numbers"
  sections for worked examples already in this corpus).
- **HIPAA/PHI doctrine lives exclusively in `compliance/hipaa-marketing-for-practices.md`.** This
  directory's own files (`escalation-triggers.md`, `response-templates-by-severity.md`,
  `never-do.md`, `ANTI-PATTERNS.md`) point to it as a mandatory pre-filter for any HIPAA-covered
  practice account but never restate or paraphrase its rules — matching `local/INDEX.md`'s
  identical house-style line for that directory.
- Every file ends with a vertical-specific bend section. The Contractor bend is **for
  home-services/contractor (`local_service`) companies**: it translates the doctrine for the
  owner-operator residential-remodeling GC archetype — phone-first, in a truck, burned by
  software/agencies before, usually with no dedicated marketing staff handling reputation. The
  relevant end-customer persona file for a `local_service` company is
  `shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a DIFFERENT
  persona (a B2B software-buyer shape for a company that itself sells *to* contractors) and is
  cited here only as an optional illustration of how an owner-operator behaves. A specific
  company's own actual buyer — including its real revenue band — lives in that company's own
  persona file, never asserted here.

## Cross-domain pointers (things that touch this domain but belong elsewhere)

- **The full legal text of the FTC rule and adjacent compliance doctrine** (CAN-SPAM, TCPA,
  endorsement-disclosure specifics beyond what `review-acquisition-compliant.md` needs to explain
  its own rules) belongs in the `compliance/` domain, per the department build plan. That domain now
  exists: see [`compliance/ftc-endorsements-and-fake-reviews.md`](../compliance/ftc-endorsements-and-fake-reviews.md)
  for the full Part 465 rule (section-by-section breakdown, penalty exposure) and
  [`compliance/review-gating.md`](../compliance/review-gating.md) for the gating-specific deep-dive.
  `review-acquisition-compliant.md` cites both directly rather than duplicating their rule text.
- **Reviews as a local-SEO ranking input** (as opposed to a consumer-trust/conversion input, which
  is this domain's concern) belongs to the `seo/` domain — see `seo/INDEX.md`'s own cross-domain
  pointer back to this directory, and `seo/local-seo-for-contractors.md` for the ranking-factor
  angle. This corpus's `review-velocity-metrics.md` [KB-REP-031] explicitly declines to make an
  unsourced ranking-factor claim and defers it to that file instead.
- **Review-request delivery mechanics as an email/SMS sequence** (subject lines, send timing,
  CAN-SPAM/TCPA compliance of the SEND itself, as opposed to the compliance of the ASK's content)
  belongs to `content/email-sequence-doctrine.md` and the `compliance/` domain's
  [`compliance/can-spam.md`](../compliance/can-spam.md) and
  [`compliance/tcpa-a2p-10dlc.md`](../compliance/tcpa-a2p-10dlc.md), not here — this domain covers
  what the ask may say and how a resulting review may be handled, not the mechanics of the send
  itself.
- **CRM workflow for logging and tracking reviews/complaints as a sales-ops process** (as opposed to
  the review-response doctrine itself) belongs to
  [`sales/crm-hygiene.md`](../sales/crm-hygiene.md).
