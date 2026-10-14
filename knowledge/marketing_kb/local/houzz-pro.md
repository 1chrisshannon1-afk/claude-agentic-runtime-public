# Houzz Pro — Doctrine

Corpus for the `local/` domain. Company-agnostic: every example below is generic. Citation format
per `shared/citation-style.md`; claim ids continue the `[KB-LOCAL-NNN]` sequence. Retrieval date for
every claim below: 2026-09-27, unless noted otherwise.

---

## 1. Team roles

**[KB-LOCAL-030]** Houzz Pro's Teams feature (a project-management/CRM product, distinct from the
Houzz consumer-facing directory/marketplace) offers **three** default role templates (official,
Houzz Pro Help, "Inviting Your Team Members & Setting Permissions,"
https://pro.houzz.com/pro-help/r/inviting-team-members, retrieved 2026-09-27):

- **Admin** — "Will have access to all features and projects." This is the unrestricted role,
  intended for the business owner or a partner who needs full visibility, comparable in scope to
  Angi's Admin role or a Yelp full-access user.
- **Field Crew/Design Team** — scoped to project-management/execution features: "access to Project
  Management features like Schedule, Takeoffs, Room Planner, etc." This role does not, by default,
  see financial data — it is built for people running the job, not pricing it.
- **Finance** — scoped to money-facing features: "will be able to use Estimates, Purchase Orders,
  Time and Expenses, etc." This is the inverse of Field Crew/Design Team — financial document access
  without necessarily the field-execution tools.

**[KB-LOCAL-031]** Unlike Angi's fixed two-role split (§1 of `angi-homeadvisor.md`), Houzz Pro's
roles are explicitly **starting templates, not fixed tiers**: "Each role comes with preloaded
settings, but you can adjust the permissions to suit you" (official, same source). After inviting a
team member to one of the three roles, an admin can open that member's settings and individually
check or uncheck feature-level permissions — the role name is a convenience default, not a ceiling.

**[KB-LOCAL-032]** Team members (as opposed to subcontractors, see below) receive access to **all
past and future projects by default**, scoped only by whatever role/feature permissions were set —
there is no separate per-project grant step required for a team member (official, Houzz Pro Help,
"Difference Between Team Member and Subcontractor,"
https://pro.houzz.com/pro-help/r/difference-between-team-member-and-subcontractor, retrieved
2026-09-27).

**[KB-LOCAL-033]** **Subcontractors are a structurally different access class from team members:**
a subcontractor's access is granted **project-by-project**, not blanket, unlike a team member's
default all-projects visibility (official, same source as [KB-LOCAL-032]). This is the doctrine-
relevant distinction — a GC bringing on a trade subcontractor for one job should add them as a
Subcontractor, never as a Team Member, or that sub will default into visibility on every other
active and past project in the account.

**[KB-LOCAL-034]** Houzz Pro's own blog post on Teams & permissions (official,
"Collaboration Just Got Easier with Teams,"
https://pro.houzz.com/pro-learn/blog/collaboration-just-got-easier-with-teams, retrieved
2026-09-27) describes only the three broad permission categories already covered above — lead
management, project management, and visual tools (floor plans/mood boards) — plus the
role-template/adjustable-permission mechanism in [KB-LOCAL-031]. **The specific "no sensitive
information will be compromised" quote and the business-partner-vs-project-manager example
(financial data denied, crew scheduling still allowed) are not supported by this or any source
checked in this pass — that framing has been removed rather than restated.** The doctrine-relevant
fact remains [KB-LOCAL-031]: permissions are per-feature and adjustable off the starting
templates, so a role like Field Crew/Design Team can, in principle, be denied financial-feature
access while keeping project-management access — but no source confirms Houzz frames or names that
specific combination the way the removed quote claimed.

---

## Contractor bend

The rule that actually saves a GC money and embarrassment here is [KB-LOCAL-033]: default a
subcontractor to project-scoped access, never to the Team Member role, or that plumber who worked
one bathroom job in March will still be able to see the pricing and photos on every project in the
account in September. For internal staff, the Field Crew/Design Team vs. Finance split maps cleanly
onto "people who run the job" vs. "people who see the money" — an owner does not need to hand-build a
permission set from scratch for a new hire; start from the closest template and adjust only what's
actually different for that person.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend on this platform.*
