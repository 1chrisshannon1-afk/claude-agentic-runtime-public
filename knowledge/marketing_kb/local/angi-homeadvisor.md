# Angi / HomeAdvisor — Doctrine

Corpus for the `local/` domain. Company-agnostic: every example below is generic. Citation format
per `shared/citation-style.md`; claim ids continue the `[KB-LOCAL-NNN]` sequence started in
`yelp.md`. Retrieval date for every claim below: 2026-09-27, unless noted otherwise.

**Same-company note:** Angi and HomeAdvisor are the same parent company's two consumer-facing
brands, sharing one pro-facing back end (the pro login at `pro.homeadvisor.com` serves both).
Doctrine in this file applies to both brand surfaces unless stated otherwise.

---

## 1. Roles: Admin and Associate

**[KB-LOCAL-013]** Angi Pro's team-management feature offers exactly **two** roles — there is no
third tier (official, Angi Help Center, "How to Manage My Team,"
https://intercom.help/angi/en/articles/10722223-how-to-manage-my-team, retrieved 2026-09-27):

- **Admin** — "the highest level of access to your Angi account." An admin can manage service
  locations, lead volume, opportunities, monthly budget, statements, and payments, and can manage
  team members (add/remove other users, change their roles). Notably, an admin **cannot edit their
  own login credentials** through this same interface (official, same source) — a documented
  quirk worth knowing before assuming any in-account setting can fix a locked-out admin's own
  login.
- **Associate** — can receive lead notifications, follow up with homeowners, and request reviews,
  but explicitly **cannot make any change that would impact monthly spend.** Associates cannot
  manage lead volume, opportunities, monthly budget, statements, payments, or team members
  (official, same source). Angi's own guidance frames this as the right role "for employees taking
  calls or working in the field" — i.e., staff who need to work leads but should never be able to
  move the budget dial.

**[KB-LOCAL-014]** Both roles share a common floor of access: viewing all leads, viewing reviews,
requesting reviews, managing notifications, using the messaging feature, and using app integrations
(official, same source as [KB-LOCAL-013]). The Admin/Associate split is purely about
spend-and-account-structure control, not about lead visibility.

**Practical implication:** a GC bringing on a field estimator or a call-answering office employee
should default to Associate — it gives them everything needed to work a lead (call back, message,
request a review after a job) with zero exposure to accidentally changing the monthly ad budget or
service-area targeting. Admin should be reserved for the owner or whoever is actually accountable
for the marketing spend decision.

---

## 2. Lead credit / dispute policy

**[KB-LOCAL-015]** The official Lead Credit Guidelines (official, HomeAdvisor/Angi Pro,
"Lead Credit Guidelines," https://pro.homeadvisor.com/terms/lead-credit-guidelines/, retrieved
2026-09-27) set a **30-day window**: "Credits must be requested by you within 30 days of the date
that the charge was incurred." A dispute filed after that window is explicitly listed among the
situations the policy does **not** cover — it is not merely discouraged, it is out of scope by the
policy's own terms.

**[KB-LOCAL-016]** Credits are issued as **store credit only, never a cash refund** — "Credits will
be issued as store credits, which will be applied toward future charges to your account" — and they
**expire six months after issuance if unused** (official, same source). A pro who disputes and wins
does not get money back; they get spend they must use against future leads within six months or
lose it.

**[KB-LOCAL-017]** Full-credit-eligible situations, per the official policy (same source):
- Duplicate leads from the same consumer.
- A lead outside the pro's stated service area (wrong zip code).
- A lead for a job type not on the pro's profile.
- A lead identified as a competitor testing the system.
- Contact information that is entirely wrong or disconnected.

**[KB-LOCAL-018]** Partial-credit-eligible: a lead submitted under the wrong job type *may* receive
partial credit if that job type does actually exist somewhere on the pro's profile — i.e., a
near-miss classification error, not a total mismatch (official, same source).

**[KB-LOCAL-019]** Explicitly **not** eligible for credit — the policy states these are "accounted
for in our lead pricing and therefore not eligible for lead credits": the consumer not calling back,
the consumer finding someone else, the consumer changing their mind, the consumer window-shopping
with no real intent, simply not winning the job, or a dispute request submitted more than 30 days
after the lead was received (official, same source). This is the single most important line in the
policy for setting realistic pro expectations: **the platform prices in the possibility that a paid
lead does not convert** — a bad hit rate alone, with no data-quality defect, is not a valid dispute
reason.

**[KB-LOCAL-020]** **UNVERIFIED (primary source unreachable: no specific reachable page could be
identified for this claim)** — a prior version of this entry cited "30-50% denial rates" and "~5
credits per territory" as third-party reporting, but named no specific source URL, and the
reachable official primary source for this domain — the Lead Credit Guidelines page cited in
[KB-LOCAL-015] (https://pro.homeadvisor.com/terms/lead-credit-guidelines/, re-checked 2026-09-27) —
was directly re-verified during this pass and confirmed to **contain neither figure**: no stated
denial-rate percentage and no stated per-territory credit cap. Both specific numbers have been
removed rather than re-hedged, since no primary or attributable third-party source supports them.
What the official policy *does* confirm is narrower and already covered in [KB-LOCAL-017]–[KB-LOCAL-019]:
credit eligibility is scoped to specific data-quality defects, and a low conversion/hit rate alone
is explicitly not a valid dispute reason. Do not cite a specific denial-rate percentage or
per-territory credit cap for Angi/HomeAdvisor without a fresh, named, checkable source.

**[KB-LOCAL-021]** **UNVERIFIED (primary source unreachable: no specific reachable page could be
identified for this claim)** — a prior version of this entry cited a "48-hour" practical
dispute-filing window, attributed only to unnamed "aggregated contractor-guide sources." The
official Lead Credit Guidelines page (https://pro.homeadvisor.com/terms/lead-credit-guidelines/,
re-checked 2026-09-27, same source as [KB-LOCAL-015]) states only a **30-day** outer bound for
requesting credits and contains no 48-hour figure anywhere. The specific "48 hours" claim has been
removed rather than re-hedged, since no primary or attributable third-party source supports it. The
only confirmed filing-window fact for this platform is the official 30-day window in [KB-LOCAL-015];
do not cite a 48-hour (or any other sub-30-day) deadline without a fresh, named, checkable source.

---

## Contractor bend — for home-services/contractor (`local_service`) companies

For the owner-operator residential-remodeling GC archetype (whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona, used elsewhere only as an owner-operator behavior illustration), the
single most expensive mistake on this platform is not reading the
credit-ineligibility list before spending on leads: a consumer who ghosts, shops around, or simply
picks someone else is a normal, priced-in outcome here, not a refund case — arguing that point wastes
time and store credit expires unused anyway if the dispute drags past six months. The Admin/Associate
split matters more than it looks: an owner who wants an estimator answering Angi leads from the
truck should hand them Associate, not Admin — it is the difference between "can follow up with a
homeowner" and "can accidentally change next month's ad budget while trying to find the lead list."
The only confirmed dispute-window number is the official **30-day** outer bound in [KB-LOCAL-015] —
a previously-recorded "48-hour" filing window and a "30-50% denial rate" figure were both removed
from this file (see [KB-LOCAL-020], [KB-LOCAL-021]) because no reachable source, official or
third-party, actually supported them. Never invent or repeat either figure in front of a
contractor; if a specific denial rate or a faster filing deadline matters to the conversation,
verify it live against the pro's own account or the current official policy page first.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend on this platform.*
