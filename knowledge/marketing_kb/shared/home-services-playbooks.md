# Home-services playbooks — seasonality, referrals, before/after, galleries

Company-agnostic operational playbooks for a `local_service` (home-services/contractor) company in
this GTM department. Every claim below carries a `[KB-SHARED-NNN]` id and a citation per
[`citation-style.md`](citation-style.md). No company facts, no company name — a specific company's
actual service mix, actual seasonality, and actual referral offer live in that company's own pack
and plan, never here.

## 1. Seasonality

**[KB-SHARED-201]** National construction activity is consistently highest in spring and summer, with
the lowest activity typically in January and February; the U.S. Census Bureau's Survey of
Construction is cited as the underlying data source, and peak period is generally described as May
through September, varying by region (third-party, summarized via Contractor Masters "Seasonal
Demand for Contractor Services," retrieved 2026-09-27:
https://contractormasters.com/seasonal-demand-for-contractor-services/ — a vendor/industry blog
citing Census data; the primary Census Survey of Construction release was not independently pulled
for this entry — treat the *pattern* as directionally reliable and re-derive the exact primary
figures before citing them in a customer-facing claim).

**[KB-SHARED-202]** National Home Remodeling Month is recognized in May by the National Association
of Home Builders (NAHB), which correlates with heavier marketing and booking activity across the
industry (third-party, same Contractor Masters summary as [KB-SHARED-201], retrieved 2026-09-27).

**[KB-SHARED-203]** Interior projects (kitchens, baths, mechanical systems) are commonly recommended
for off-peak winter scheduling, since winter is not weather-constrained for interior work and
contractor availability is higher (and pricing sometimes more competitive) than during the spring/
summer rush that outdoor and addition work is bound to (third-party, aggregated from multiple
contractor-marketing advice pages — Kellow Construction "Best Time of Year to Start a Home Remodel,"
Revive Works PDX "Best Time of Year for a Home Remodel," retrieved 2026-09-27 — vendor advice
content, not an independent study; treat as directional industry-practice guidance, not a measured
statistic).

**[KB-SHARED-204]** Fall is frequently cited as the best overall season for many homeowners to start
a remodel, because contractor demand cools after the summer rush, which can mean more contractor
attention and more competitive pricing than in peak season (third-party, same aggregated sources as
[KB-SHARED-203], retrieved 2026-09-27).

**Playbook implications (mechanism, not a number to port verbatim):**
- **Off-season (roughly Nov–Feb, exterior/addition work; less pronounced for interior work):** lead
  with availability and attention ("we can start your project in weeks, not months right now"),
  since this is genuinely differentiated during the slow season and answers the homeowner's real
  question at this time of year. This is also the highest-leverage window for interior-project ad
  spend and content, per [KB-SHARED-203].
- **Peak season (roughly May–Sep):** lead with proof of capacity and realistic timeline-setting
  ("here's what to expect for scheduling right now") rather than promising fast turnaround the
  company cannot actually deliver during its busiest months — an unrealistic peak-season promise is
  exactly the kind of overpromise `homeowner-buyer-psychology.md` [KB-SHARED-104]/[KB-SHARED-105]
  (the research-and-trust gauntlet and the reputation premium) predicts will damage trust when it's
  not honored — the same burned-before dynamic `contractor-buyer-psychology.md` fact 3 describes for
  the B2B software buyer, applied here to a homeowner burned by an overpromising contractor instead.
  Google/Meta budget pacing should account for this seasonal swing in both traffic and close rate —
  see `paid_acquisition/` for the mechanical budget-pacing doctrine; this file only states the
  seasonal pattern, not the bid math.
- **A specific company's own real seasonality (its own booking calendar, its own regional climate)
  overrides this national pattern** whenever the company's own historical data (real job-start dates
  from its own CRM/lead sink, `(internal-measured)` per `citation-style.md`) contradicts it — a
  roofing-heavy company in a warm climate, for example, may have a materially different seasonal
  curve than the national interior-remodel pattern above. Check company-specific data before
  applying this national default.

## 2. Referral programs

**[KB-SHARED-205]** In one 2026 industry survey of 1,000+ home-service business owners, 59% named
referrals and repeat customers as their top source of new work — ahead of digital ads, social media,
and Local Services Ads (third-party, Jobber "2026 Home Service Trends Report," summarized via
Jobber Academy "10 Customer Referral Program Ideas for Service Businesses," retrieved 2026-09-27:
https://www.getjobber.com/academy/customer-referral-program-ideas/ — vendor-published survey; sample
recruitment method not independently confirmed here).

**[KB-SHARED-206]** The same page cites a Nielsen 2012 statistic that 92% of consumers trust
referrals from people they know above all other forms of advertising (third-party, aggregated via
Jobber Academy, same URL and retrieval date as [KB-SHARED-205] — the Jobber page's own citation is a
13-year-old survey year at time of writing; treat this specific figure as a widely-repeated but dated
industry reference, not a current measurement, and prefer a more recent trust study if one is found
during a future refresh).

**[KB-SHARED-207]** The same source reports that, on its own platform, 70% of referrals made through
its referral tool result in new work being booked (third-party/vendor-platform-internal statistic,
Jobber Academy, same URL and retrieval date as [KB-SHARED-205] — this is the vendor's own platform
data, not an independent industry-wide figure; do not generalize this specific conversion rate to a
company using a different referral mechanism).

**[KB-SHARED-208]** Recommended reward-structure mechanics for a service-business referral program:
reward the *referring* customer with something unrelated to the company's own services (cash, a
gift card to another business, an experience) sized to reflect the value of the project they drove,
and reward the *referred* customer's conversion with something tied to the company's own services
(a discount, a free upgrade) once their referral becomes an approved quote or completed job
(third-party, Referral Rock "Contractor Referral Program: 10 Tactics + Free Tools," retrieved
2026-09-27: https://referralrock.com/blog/contractor-referral-programs/ — a referral-software
vendor's own advice content; treat the structural mechanism as sound generic marketing practice,
and treat any specific dollar amount on that page as `UNVERIFIED — seeded, needs derivation`
per-company, never ported as a set price).

**Playbook mechanism (company-agnostic; a specific reward amount is always a company decision, not
KB doctrine):**
1. **Trigger the ask at the moment of highest satisfaction** — typically project completion/final
   walkthrough, paired with (not instead of) the review-request ask (see §3 below and
   `reputation/review-acquisition-compliant.md`), since both asks share the same trust-is-highest
   moment.
2. **Track referral source explicitly in the lead sink** (`company.json`'s `lead_sink`) so referral
   volume and close rate are measurable against paid-channel performance, per [KB-SHARED-205]'s
   implication that referrals often outperform paid acquisition — a company cannot know this is true
   for itself without the same tagging discipline `paid_acquisition/` already requires for ad
   attribution.
3. **Never condition the referral reward on a positive review, and never combine a referral ask with
   review-gating language** ("refer a friend and leave us 5 stars for a bonus") — this crosses into
   the FTC review-gating prohibition documented in `homeowner-buyer-psychology.md` [KB-SHARED-107]
   and `compliance/review-gating.md`; a referral reward is for a successful referral (a booked job),
   never for review sentiment.
4. **A referral communication to a named past customer is a `crm`/`email`/`sms` action under this
   department's tier table** (see `autonomy-tiers.md`) — it is not exempt from the same consent and
   tier rules as any other outbound message to a named person.

## 3. Before/after photo rules

This section is the operational playbook; the underlying legal/compliance sourcing
([KB-SHARED-106]–[KB-SHARED-108]) lives in `homeowner-buyer-psychology.md` and is not restated here
— read that file's "Before/after photos and testimonials" section first.

**Operational rule set:**
1. **No before/after photo, project photo, or customer testimonial is used in any customer-facing
   surface without a documented release on file for that specific project.** "Documented" means a
   signed release record exists (paper or digital), referencing the specific project/address/date —
   not a verbal "sure, go ahead" with no record. `act.py` (planned; not yet built)'s content-check
   gate (see `company-pack-authoring.md`'s reference to the action gateway) is the mechanical
   backstop; this is the human-process rule that makes that gate satisfiable in the first place.
2. **Get the release at project closeout, while satisfaction is highest** — this is both the
   easiest moment to get a "yes" and the moment closest to when review-acquisition also happens
   (§2 above), so the two asks can be bundled into one closeout conversation without conditioning
   either on the other (see the review-gating caveat above).
3. **Caption honestly.** State the actual scope and actual timeframe; never let an unusually fast or
   unusually dramatic project imply a typical result without a generally-expected-results
   disclosure, per [KB-SHARED-106]. "6-week full gut renovation" is honest; a caption that implies a
   6-week turnaround is what every customer should expect, with no scope qualifier, is not.
4. **Never digitally alter a before/after photo's substantive content** (removing real damage,
   adding fixtures that weren't installed, compositing two different projects to look like one) —
   this is a fabricated-claim violation under `department-anti-patterns.md` item 1's own standard,
   applied to imagery rather than text. Ordinary photo-quality editing (lighting, cropping, color
   correction that doesn't misrepresent the actual work) is not what this rule targets.
5. **AI-generated or AI-edited imagery follows that company's own `ai_content_policy`** (see
   `company-pack-authoring.md` §8 — `disclose_never_strip` vs. `strip_before_publish` vs. `forbid`) —
   a before/after photo is real photography by definition (it documents an actual project), so an
   AI-*generated* "before/after" image is never a substitute for a real one; AI-*assisted* editing of
   a real photo still must pass that company's `ai_content_policy` check before publish, exactly like
   any other asset (see `act.py`'s content checks, `plans/gtm_autonomous_department_plan.md` §6.6 —
   **note: this plan file is local-only, excluded from version control by this runtime's own
   `.gitignore`, so a reader of the GitHub mirror cannot resolve this citation directly; the tracked
   `tools/gtm/README.md` covers the pack tooling `act.py` builds on, though it does not itself
   restate §6.6's content-check specifics**).
6. **A project gallery is a collection of before/after entries, and inherits every rule above per
   entry** — see §4 below for gallery-level rules on top of the per-photo rules here.

## 4. Project galleries

A "project gallery" (a marketing-site page or section showcasing multiple completed projects) is a
higher-leverage but higher-maintenance surface than a single before/after post, because it is
usually a persistent page (not a time-limited social post) and often aggregates multiple projects
that must each independently satisfy §3 above.

**Operational rules:**
1. **Every entry needs its own release, per §3 rule 1** — a gallery is not exempt just because it's
   a lower-visibility page than the homepage; if anything a gallery is *more* likely to be closely
   read by a homeowner deep in the research-and-trust gauntlet (`homeowner-buyer-psychology.md`
   [KB-SHARED-104]), so accuracy matters more here, not less.
2. **Categorize by real, verifiable attributes the homeowner actually searches by** — project type
   (kitchen, bathroom, addition), rough scope/budget band (sourced to the same real cost-book data
   the company's actual estimates use, never an invented "starting at" figure), and general location/
   service area (city or region, not the specific street address, unless the homeowner has
   explicitly consented to that level of identification). This directly serves
   `homeowner-buyer-psychology.md` fact 3 (specificity beats adjectives) and fact 2 (price read as a
   range) at once.
3. **Keep the gallery current — remove or clearly date stale entries.** A gallery whose newest
   project is years old reads as evidence the company has slowed down or stopped, which is a worse
   signal than a smaller, current gallery. This is the same "dead telemetry" instinct
   `observability-architect`'s doctrine applies to logs, applied to a marketing surface instead: a
   stale signal is worse than an honestly smaller one.
4. **A gallery entry that later needs to be removed** (a customer withdraws consent, a dispute
   arises, the project turns out to have quality issues that make it a bad advertisement for the
   company) is removed promptly on request — a homeowner's photo-release consent is not
   irrevocable in perpetuity as a matter of good practice, even where the signed release's exact
   legal terms might permit continued use; treat the relationship, not just the paperwork, as the
   real asset.
5. **Never present a stock/AI/composited image as a real completed project in a gallery** — this is
   the single clearest fabricated-claim violation for a gallery specifically, since a gallery's whole
   premise (per this vertical's positioning) is "this is real work we actually did." See
   `department-anti-patterns.md` item 1 and that company's own AI-content-labeling rule, if it has
   one, for why an AI-sourced image is a categorically different risk from a real photo that's merely
   poorly lit.

## Contractor bend

This file's subject *is* the home-services company's own operating playbook, so there is no further
translation layer to apply for that company's own end customer — but the same standard this file
sets is worth holding this department to as well: real proof over adjectives, honest seasonal
expectations over overpromising, and referral/review mechanics that would survive an FTC audit. A
department that cuts a corner here while telling its `local_service` customers to never cut that
corner is not a credible messenger.
