# CRM Hygiene

CRM hygiene is the mechanical discipline that keeps a CRM a usable decision-making tool instead of a
graveyard of stale, duplicated, unroutable records. This file covers required-field discipline,
deduplication, decay-triggered re-verification, and pipeline-stage definitions — the plumbing that
every other file in this domain assumes works.

## 1. What data decay actually costs

**[KB-SALES-024]** B2B contact and company data is widely reported to decay at a meaningful ongoing
rate — commonly cited figures in the CRM/data-quality vendor literature put natural B2B database
decay somewhere in the **22–30% per year** range, driven by job changes, company moves, phone/email
changes, and business closures (third-party, aggregated from CRM data-quality vendor research —
ZoomInfo, Validity/BriteVerify-lineage decay-rate studies — retrieved 2026-09-27 —
**UNVERIFIED at the precise percentage: every reachable source is a vendor whose product sells data
enrichment/cleansing, an inherent incentive to state decay as high; treat the range as directionally
correct evidence that decay is real and ongoing, not a number to cite to an operator as a precise,
independently-audited statistic**).

**[KB-SALES-025]** The downstream cost of unmanaged decay is qualitative and well-documented as a
mechanism even where the dollar-cost figures are vendor-sourced and directional: reps waste time
calling disconnected numbers or emailing bounced addresses, pipeline reports overstate real
opportunity because stale records were never purged or re-scored, marketing sends to bad addresses
degrade email deliverability/sender reputation for the *whole* domain (not just the bad send), and
duplicate records split a single prospect's history across two records, hiding the true touch count
and qualification status. **(third-party, widely stated across CRM vendor and analyst commentary,
retrieved 2026-09-27 — mechanism well-supported, dollar-cost figures vendor-sourced and directional
only.)**

## 2. Required fields — the minimum a record needs to be actionable

**[KB-SALES-026] (internal doctrine)** No single universal "required field list" is authoritative across all CRMs or
businesses — required fields are legitimately business-specific (a services business needs a service
address; a SaaS company needs a company-size field for tier routing). The **mechanism** that is
well-supported regardless of the specific field list: a required field should exist only if something
downstream (routing, a report, a qualification score) actually breaks or silently misleads when it's
missing — a field required "for completeness" with no downstream consumer is bookkeeping overhead
that reps will route around (skip, enter garbage data to satisfy a mandatory-field validator) rather
than genuinely populate. **Reject example:** marking 12 fields "required" on lead intake, including
several no report or automation ever reads, resulting in reps typing "N/A" or a placeholder value
into fields the form won't let them skip — this is worse than an empty field, because it looks
populated in a report while being equally uninformative.

## 3. Deduplication

**[KB-SALES-027]** Duplicate records are a well-documented, mechanism-level CRM failure: they split a
prospect's real history across two or more records, causing double-counted pipeline in reports,
conflicting qualification scores, and — most damaging for the speed-to-lead discipline in this
domain — two different reps independently calling the same prospect within minutes of each other
because neither record showed the other's activity (third-party, consistently reported across
CRM-vendor and Salesforce-ecosystem data-quality guidance, retrieved 2026-09-27 — mechanism robust;
no independently-verified universal duplicate-rate statistic is cited here because reported rates
vary enormously by CRM age, import history, and integration count, making any single "X% of records
are duplicates" figure non-generalizable).

**[KB-SALES-028] (internal doctrine)** The mechanical discipline: dedupe on a **fuzzy match**, not just exact-string
match — email is the most reliable single dedup key where present (case-insensitive, trimmed), but
phone-number normalization (strip formatting, compare last-10-digits for US numbers) and
name+company fuzzy matching catch the far larger set of duplicates that exact-match misses (a lead
who typed their name differently on two form fills, a company name with or without "LLC"). **Merge,
don't delete** — a proper dedup merge preserves the union of activity history from both records
rather than picking one and discarding the other's touches, which would silently erase real qualification
signal (a call logged on the "losing" record in a naive delete-and-keep-one dedup).

**Pass example:** An automated dedup rule runs nightly, flags fuzzy matches (same normalized phone,
name similarity above a threshold) for human review before merging rather than auto-merging silently,
and the merge preserves both records' full activity timelines.

**Reject example:** No dedup process exists; the same prospect has four separate records from four
different lead-source imports over two years, each with a different qualification status, and no one
notices until two reps call the same person the same week.

## 4. Decay-triggered re-verification

**[KB-SALES-029]** Rather than a blanket periodic "clean the whole database" sweep (expensive, and
treats a record updated yesterday the same as one untouched for three years), the better-supported
mechanism is **decay-triggered re-verification**: flag a record for re-verification when a specific
signal suggests staleness — an email bounce, a phone number that reaches a disconnected-number
message, no activity of any kind for a defined inactivity window, or an external signal (a job-change
notification from an enrichment tool, where one is in use). This targets cleanup effort at records
that are actually likely stale, rather than spending equal effort on records that don't need it.
**(third-party, standard data-quality-management pattern described across CRM vendor and RevOps
practitioner content, retrieved 2026-09-27 — mechanism-level, not tied to a single disclosed study.)**

**[KB-SALES-030]** A hard bounce (permanent delivery failure — mailbox doesn't exist, domain doesn't
resolve) should immediately suppress future email sends to that address pending re-verification —
continuing to send to a hard-bounced address is what damages sender-domain deliverability reputation
for every other email sent from that domain, not just the bounced one (official mechanism, consistent
with ESP-published sender-reputation guidance and CAN-SPAM's own suppression-list discipline, see
`../compliance/can-spam.md`; retrieved 2026-09-27). A soft bounce (temporary — mailbox full, server
timeout) should not trigger the same immediate suppression, but repeated soft bounces on the same
address over time should escalate to the same treatment as a hard bounce.

## 5. Pipeline-stage definitions

**[KB-SALES-031] (internal doctrine)** A pipeline stage is only useful if it has an unambiguous entry/exit criterion that
two different reps would apply the same way — a stage defined by a feeling ("seems interested") rather
than an observable event (a qualification call completed with a specific outcome, a proposal sent, a
signed contract received) produces a pipeline report that looks precise but reflects each rep's
personal judgment rather than a comparable state. **(Mechanism-level, consistent with standard sales
methodology practice; no single external citation applies because stage definitions are inherently
business-specific — the discipline itself, not a specific stage list, is what this claim asserts.)**

**Reject example:** A pipeline with stages "New," "Working," "Hot," "Cold" — "Hot" and "Cold" are
subjective labels a rep assigns from gut feel, not an observable event, so two reps' "Hot" leads are
not comparable and a forecast built on stage counts is unreliable. **Pass example:** "New →
Contacted (first outreach attempt logged) → Qualified (BANT/qualification questions answered and
scored) → Proposal Sent (specific document/quote sent, timestamped) → Won/Lost (closed with a
recorded reason)" — every transition is tied to a specific, checkable event.

**[KB-SALES-032] (internal doctrine)** A qualification score or pipeline stage that is set once and never revisited
becomes stale in exactly the same way contact data does — see `lead-qualification.md` §3's point
that a qualification framework is only useful if it changes what happens next; the CRM-hygiene
corollary is that the *field itself* needs the same decay-triggered re-verification discipline as
contact data (a lead marked "Qualified" three months ago with no subsequent activity should trigger
review, not sit in the qualified bucket indefinitely inflating pipeline value).

## Contractor bend

A one-person or small-office GC's "CRM" is very often a spreadsheet, a paper job board, or a basic
CRM used inconsistently between the owner and one office admin — the mechanism above still applies
at that scale, just implemented lighter-weight: a "required field" list of maybe three fields (name,
phone, project type) that are genuinely always filled because they're genuinely always needed for the
very next action (the callback); a manual weekly glance for obvious duplicates rather than an
automated nightly job; and pipeline stages simple enough that the owner and the office admin apply
them the same way without a training document. The failure mode to name explicitly for this buyer:
a CRM that looks organized (lots of fields, custom stages) but that nobody actually keeps current
is worse than a simple spreadsheet that's actually trustworthy, because a stale "sophisticated" CRM
gives false confidence in numbers (pipeline value, lead counts) the owner then makes real staffing
and ad-spend decisions against.
