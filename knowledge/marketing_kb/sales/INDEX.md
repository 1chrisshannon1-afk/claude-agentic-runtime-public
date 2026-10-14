# Sales Domain — Index

Corpus for the sales-operations side of the GTM department: what happens to a lead or trial
signup *after* marketing generates it, and before/after it becomes a customer. Company-agnostic:
no single company's facts and no company names anywhere in this corpus.
Written for whichever GTM agent seat is handling lead response, CRM discipline, or trial
conversion for a given company pack; each company's own pack/manifest supplies the
company-specific facts (CRM platform, sales-cycle length, trial length, actual response-time SLA)
that instantiate the doctrine below. Grep-reachable — read the file that answers your question,
not the whole corpus. Every numeric/behavioral claim carries a stable claim id
(`[KB-SALES-NNN]`) and a citation tag per
[`../shared/citation-style.md`](../shared/citation-style.md), with a retrieval date, or is marked
`UNVERIFIED (primary source unreachable: <url>)`.

| File | Answers |
|---|---|
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a sales-ops agent NEVER recommend or automate, regardless of how well it "should" convert or how much faster it would be? |
| [`speed-to-lead.md`](speed-to-lead.md) | How fast does a new inbound lead actually need a response, what does the evidence say happens to conversion odds per minute of delay, and how does an agent design a response-time SLA and escalation path around that? |
| [`lead-qualification.md`](lead-qualification.md) | What frameworks (BANT and its successors, MEDDIC/MEDDPICC) actually qualify a lead, when does each apply, and how does a qualification score change routing/prioritization? |
| [`follow-up-cadences.md`](follow-up-cadences.md) | How many touches, over what channel mix and what timing, does a multi-touch follow-up cadence need before a lead is legitimately called dead — and what compliance constraints (TCPA, CAN-SPAM) bound the channel and timing choices? |
| [`crm-hygiene.md`](crm-hygiene.md) | What does CRM data decay actually cost, what's the mechanical discipline (required fields, dedup, decay-triggered re-verification, pipeline-stage definitions) that keeps a CRM usable instead of becoming a graveyard? |
| [`estimate-follow-up.md`](estimate-follow-up.md) | For a business whose core sales artifact is a quote/estimate/proposal rather than a demo, what does the follow-up sequence from "estimate sent" to "won or lost" look like, and what does the evidence say about proposal-open tracking and follow-up timing? |
| [`reactivation.md`](reactivation.md) | How does a sales-ops agent win back a stalled, lost, or dormant lead/customer — segmentation, message sequencing, and the honesty constraints on a "win-back" claim? |
| [`b2b-trial-to-paid.md`](b2b-trial-to-paid.md) | What separates a trial that converts from one that doesn't (opt-in vs. opt-out, activation milestones, PQL scoring), and what do the actual benchmark studies say a healthy trial-to-paid rate looks like? |
| [`outreach-levers-and-drafting.md`](outreach-levers-and-drafting.md) | (Business-to-business, partner and prospect outreach; not a template for patient messages.) What should an outreach or promotional message lead with (offer, unique mechanism, free value hook, segmentation, social proof) and what must be true before each is claimed? How do you segment by one variable, draft with an assistant (four variants, stitch, human edit, swipe file) and launch small? Single vendor-affiliated practitioner source, figures UNVERIFIED. |
| [`reply-handling.md`](reply-handling.md) | What happens between a reply (or an after-hours inquiry) arriving and the person being booked? Who owns replies and by when, how replies from every channel reach one queue, what goes in the reply knowledge base, what an assistant may draft versus what a person must approve, how opt-outs and phone calls are handled? Single-practitioner source, figures UNVERIFIED. |

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a `[KB-SALES-NNN]` claim id and a citation tag
  (`(official)`, `(third-party)`, `(internal-measured)`, or `UNVERIFIED — seeded, needs
  derivation` / `UNVERIFIED (primary source unreachable: <url>)`) with a retrieval date, per
  [`../shared/citation-style.md`](../shared/citation-style.md). Claim ids are stable once assigned
  — never renumber an existing id when adding new claims; append.
- This corpus is company-agnostic by construction: no company name, no company-specific CRM
  screenshot, no company-specific numbers. Generic examples only ("a residential remodeling GC," "a
  B2B SaaS company," "a lead named Jane Doe at Acme Co."). A company pack's own KB or manifest
  supplies the facts that turn this doctrine into a specific SLA, cadence, or script for that
  company.
- Every claim is checked against a primary/official source (the platform's own help center or
  developer docs, a regulator, a statute, or a court opinion) where one exists. Where the primary
  source itself was unreachable (blocked automated fetch, paywall, dead link), the claim cites the
  best reachable mirror or secondary report AND is marked `UNVERIFIED (primary source unreachable:
  <url>)` — it is never presented as settled.
- A number that is directionally true but drawn from vendor-published aggregate data (a CRM
  vendor's own blog citing its own customer base, an SEO-optimized "benchmark" roundup with no
  disclosed methodology) is tagged `(third-party)` with its methodology and sample size named where
  known, and flagged as directional rather than authoritative — see `speed-to-lead.md` for a worked
  example of separating an academically-anchored figure from a vendor-blog restatement of it.
- Numeric gates/frameworks (response-time SLAs, cadence touch counts, qualification-score
  thresholds) include explicit pass/reject examples in the file that defines them.
- Every file ends with a "Contractor bend" section translating the doctrine for a small
  owner-operated home-services/trade business archetype — phone-first, in a truck, burned by
  software/agencies before, whose "sales team" may be one owner-operator answering their own phone
  between job sites. This is the same archetype used throughout the SEO and conversion domains, restated here because
  sales-ops doctrine (who calls back when, on what cadence) is where that archetype's real
  constraints bite hardest. `shared/contractor-buyer-psychology.md` is one of several persona files
  a company pack may select — a company pack for a different vertical (e.g. a dental practice)
  selects and reads its own persona file from its own pack instead.
- Material adapted from the MIT-licensed `coreyhaines31/marketingskills` repository carries an
  attribution + MIT notice line in the adapting file's header. This corpus adapts *structure and
  checklists* from that source where noted, never verbatim prose without the notice.

**Claim-id gap notice (2026-09-28):** `[KB-SALES-007]`–`[KB-SALES-009]` are not assigned to any
claim in this corpus as of this writing. This is not believed to be a scrub deletion — those ids are
not present at first commit, and pre-commit history is unrecoverable from git (this corpus was never
tracked before this pass, so `git log`/`git diff HEAD` show nothing to check the gap against) — but
is noted here so a future auditor does not mistake the gap for lost content without further evidence
either way. New claims append after the highest currently-used id; a gap is never backfilled with an
unrelated new claim.

## Cross-domain pointers (things adjacent to this domain but owned elsewhere)

- **Lead generation itself** (how a lead arrives — paid search, SEO, local listings, referral) is
  owned by the `seo/`, `paid_acquisition/`, and `local/` domains. This domain starts at the moment
  a lead exists in a CRM or inbox and ends when it is won, lost, or legitimately archived.
- **Review acquisition and reputation management** (asking a won customer for a review, responding
  to reviews) is owned by the `reputation/` domain — referenced here only where a reactivation or
  follow-up touch legitimately doubles as a review ask (`reactivation.md` notes the boundary).
- **Compliance mechanics for outbound channels** (CAN-SPAM's exact required elements, TCPA consent
  categories, A2P 10DLC registration) are restated here only to the depth a sales-ops cadence needs
  to stay legal — the fuller regulatory doctrine belongs to the `compliance/` domain
  (`compliance/can-spam.md`, `compliance/tcpa-a2p-10dlc.md`), the domain of record; this corpus's
  compliance citations should be reconciled against it rather than duplicated forward without
  re-checking.
- **CRM platform selection and technical integration** (which CRM, API wiring, webhook design) is
  an execution/engineering concern, not a doctrine concern — this corpus assumes *some* CRM exists
  and governs the discipline of using it well, never a specific vendor's UI.
- **Pricing and packaging** (trial length, whether a trial requires a card, tier structure) is
  owned by the `pricing/` domain — `b2b-trial-to-paid.md` cites pricing-domain findings on
  card-required vs. card-not-required trial mechanics as an input, never re-litigates the pricing
  decision itself.
