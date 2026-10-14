# Outbound Domain — Index

Corpus for the venture department's outbound and relationship-building specialist
(`bizdev-outbound-strategist`) and anyone else drafting B2B cold outreach or founder-led business
development for a solo founder or tiny team. Company-agnostic: no single company's facts and no
company names anywhere in this corpus — a company's own deal folder or manifest supplies the
company-specific facts (target vertical, sending domains, actual partner list) that instantiate the
doctrine below.

Every numeric/behavioral claim carries a stable claim id (`[KB-VOUT-NNN]`, numbered from 001
across all files in this directory together) and a citation tag per
[`../../marketing_kb/shared/citation-style.md`](../../marketing_kb/shared/citation-style.md), with a
retrieval date, or is marked `UNVERIFIED — seeded, needs derivation` or `UNVERIFIED (primary source
unreachable: <url>)`.

| File | Answers |
|---|---|
| [`b2b-cold-email-and-deliverability.md`](b2b-cold-email-and-deliverability.md) | How does a solo founder or tiny team build and run a legally compliant, deliverable B2B cold-email campaign — CAN-SPAM's B2B-specific traps and penalty exposure, list sourcing and no-harvest notices, bought-list vetting, sending-domain and SPF/DKIM/DMARC setup, Google's and Yahoo's bulk-sender requirements (spam-rate thresholds, one-click unsubscribe, RFC 8058), warm-up and per-mailbox volume, bounce/complaint stop rules, sequence design, and the non-US-recipient flag (CASL/UK PECR/EU)? |
| [`founder-led-relationships.md`](founder-led-relationships.md) | How does a first-time founder build the relationships that produce early customers and partners by hand — design-partner programs and letters, referral/channel-partner structures and when they need legal review, trade associations and events, LinkedIn and Facebook by hand with no automation, discovery-call structure, follow-up discipline, CRM-lite tracking, and the hard TCPA lines that apply regardless of how personal or small-scale the outreach is? |
| [`outbound-campaign-playbook.md`](outbound-campaign-playbook.md) | How does a solo founder go from idea to a live compliant B2B campaign in days — test before tooling, the five levers to compete on, segment by one variable and write to its pain, layer a list from public pages and route contacts by the data held, draft with an assistant and edit as a human, reply speed and a reply knowledge base, content plus hand-sent outreach, data-tool pricing models, the sender's own online presence, paid creator posts and their disclosure, channel choice, domain and mailbox provisioning services — and which tactics from the same practitioner source are REJECTED (borrowed profiles, scraping, automated sequencing, domain rotation) or BOUNDED by each company's own rulings (automatic replies and booking, calling the number in a reply's signature)? Single-practitioner source, figures UNVERIFIED. |

## This domain's place in the corpus

This directory is the **venture department's** outbound doctrine — for a solo founder building a
new company from zero, not the GTM marketing department's scaled-outbound doctrine for an
already-operating company. It deliberately **links to, rather than repeats**, the runtime's shared
compliance corpus:

- [`../../marketing_kb/compliance/can-spam.md`](../../marketing_kb/compliance/can-spam.md) — the
  domain of record for CAN-SPAM's five required elements, penalty structure, and opt-out mechanics.
  `b2b-cold-email-and-deliverability.md` cites this file rather than restating its content, adding
  only what's specific to the founder-led B2B use case (deliverability infrastructure, sequence
  design, bulk-sender platform requirements).
- [`../../marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md)
  — the domain of record for TCPA consent, quiet hours, revocation, and A2P 10DLC registration. Both
  files in this directory cite it for the hard line against automated/prerecorded/AI-voice calls and
  cold texts, rather than restating the statutory mechanics.
- [`../../marketing_kb/sales/INDEX.md`](../../marketing_kb/sales/INDEX.md) — the domain of record
  for what happens *after* a lead exists (speed-to-lead, qualification, follow-up cadences, CRM
  hygiene, reactivation, trial-to-paid). This directory's doctrine ends at "a reply was received" or
  "a relationship touch happened" — routing, scoring, and pipeline discipline from that point
  forward is the sales domain's lane. `founder-led-relationships.md` links to
  [`follow-up-cadences.md`](../../marketing_kb/sales/follow-up-cadences.md) and
  [`crm-hygiene.md`](../../marketing_kb/sales/crm-hygiene.md) rather than re-deriving either.

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a `[KB-VOUT-NNN]` claim id and a citation tag (`(official)`,
  `(third-party)`, `(internal-measured)`, `(internal doctrine)`, or `UNVERIFIED — seeded, needs
  derivation` / `UNVERIFIED (primary source unreachable: <url>)`) with a retrieval date, per
  [`../../marketing_kb/shared/citation-style.md`](../../marketing_kb/shared/citation-style.md).
  Claim ids are stable once assigned — never renumber an existing id when adding new claims; append,
  continuing from the highest id currently used across all files in this directory.
- This corpus is company-agnostic by construction: no company name, no personal names, no absolute
  path to any specific company's own folder, no company-specific numbers. Generic examples only ("a
  two-year-old vertical SaaS with one paying customer," "a solo founder building a local-services
  marketplace").
- Every claim is checked against a primary/official source (a regulator, a statute, a platform's own
  legal/help documentation) where one exists, fetched directly before citing — never cited from
  memory of what a page "probably says." Where the primary source itself was unreachable (blocked
  automated fetch, dead link, non-extractable PDF), the claim is marked `UNVERIFIED (primary source
  unreachable: <url>)` and is never silently upgraded to `(official)`.
- Legal and regulatory content in this corpus is information, not legal advice — each file names
  where an attorney (or, for the securities-adjacent edges of relationship-building, e.g. investor
  outreach, securities counsel) needs to make the actual call, and neither file tells the founder to
  sign or promise anything. See each file's own decision rules for exactly where that line sits.
- Every file ends with a "Decision rules" section (plain if/then guidance an agent can apply
  directly) and an "Anti-patterns" section (what to refuse even if asked directly).

## Cross-domain pointers (things adjacent to this domain but owned elsewhere)

- **What happens after a reply or relationship touch turns into an active lead** (qualification,
  routing, follow-up cadence mechanics, CRM discipline, reactivation) is owned by
  [`../../marketing_kb/sales/INDEX.md`](../../marketing_kb/sales/INDEX.md) — this domain starts
  outreach and ends at first genuine engagement; sales-domain doctrine takes it from there.
- **Compliance mechanics for every outbound channel** (CAN-SPAM's exact required elements, TCPA
  consent categories and revocation, A2P 10DLC registration, FTC endorsement/review rules) are
  owned by [`../../marketing_kb/compliance/`](../../marketing_kb/compliance/) — this domain's own
  files apply that doctrine to the founder-led and small-scale-B2B use case, never re-litigate or
  duplicate the underlying regulatory content.
- **Buyer/investor relationship-building for a company that is for sale or raising capital**
  (buyer maps, investor outreach specifically in a fundraising or M&A context, deal terms) is owned
  by the venture department's capital-and-exit doctrine
  (`capital-and-exit-strategist`'s own grounding) — this domain covers general business-development
  and customer/partner relationship building; a fundraising-specific or sale-specific outreach
  motion follows that seat's doctrine instead, with this domain's LinkedIn/event/associations
  mechanics still applying as the *channel* discipline underneath it.
- **Ideal-customer-profile and beachhead-market scoring** (who to target in the first place) is the
  `bizdev-outbound-strategist` agent's own analytical work, informed by
  [`../../marketing_kb/sales/lead-qualification.md`](../../marketing_kb/sales/lead-qualification.md)'s
  qualification frameworks and market-analyst's competitor/market facts — this domain assumes a
  target list exists or is being built, and covers how to reach it, not how to define it.
- **CRM platform selection and technical integration** is an execution/engineering concern, not a
  doctrine concern — this domain (like the sales domain) assumes *some* tracking mechanism exists,
  from a spreadsheet up to a full CRM, and governs the discipline of using it well, never a specific
  vendor's UI.
