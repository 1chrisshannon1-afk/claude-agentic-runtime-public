# Google Business Profile (GBP) Optimization

Domain doctrine for a `local-presence-architect`-class seat's Google Business Profile work:
categories, services, posts, Q&A, photos, verification, suspension risk, and the multi-brand /
same-owner rules that a company operating more than one brand or location must get right before
touching GBP at all. Company-agnostic — no company facts, no company names. Every claim below
carries a `[KB-LOCAL-NNN]` id and a citation per `shared/citation-style.md`.

---

## 1. One profile per business — the foundational rule

**[KB-LOCAL-001]** A business may have only one Business Profile per business. Google states
plainly: "There should only be one profile per business, as this can cause problems with how your
information displays on Google Maps and Search." (official, Google Business Profile Help,
"Guidelines for representing your business on Google," retrieved 2026-09-27:
https://support.google.com/business/answer/3038177)

**[KB-LOCAL-002]** A profile is flagged as a duplicate when any of these hold: a verified profile
already exists for the same business; multiple profiles share the same address; or multiple
profiles exist for the same business offering different services. A profile marked duplicate does
not show in Google Search or Maps results. (official, Google Business Profile Help, "Resolve
duplicate profiles & ownership issues," retrieved 2026-09-27:
https://support.google.com/business/answer/12756178)

**Reject example:** creating a second GBP listing for the same location because the first one's
login credentials were lost, rather than recovering access to the original.

**Pass example:** requesting ownership/manager access to the existing verified profile (the
current owner has a response window before an appeal path opens), or reporting a genuine duplicate
for merge via Google Maps rather than operating two live listings for one business.

## 2. Multi-brand / same-owner rules — read before touching a second brand's listing

**[KB-LOCAL-003]** Two or more brands operating out of one address may NOT be combined into a
single profile. Google's own guidance: "pick one brand's name for the Business Profile. If the
brands operate independently, you may use a separate profile for each brand at this location."
(official, Google Business Profile Help, "Guidelines for representing your business on Google,"
retrieved 2026-09-27: https://support.google.com/business/answer/3038177)

**[KB-LOCAL-004]** Distinct, eligible businesses sharing one address may each hold a separate
profile only when each one independently qualifies for a Business Profile AND there is a "clearly
visible difference in signage" distinguishing them on-site — this exception explicitly covers
multiple brands, rebranded locations, departments within a larger institution, and individual
practitioners at a shared location. When both businesses serve customers at the shared location,
Google may require evidence of the permanent signage for both. (official, Google Business Profile
Help, "Resolve duplicate profiles & ownership issues" + "Guidelines for representing your business
on Google," retrieved 2026-09-27: https://support.google.com/business/answer/12756178,
https://support.google.com/business/answer/3038177)

**[KB-LOCAL-005]** A business offering multiple services under one brand and one address should
list those services on the *one* profile (via the Services section, §3 below), not spin up a
separate profile per service line. Doing the latter is exactly the "different services" duplicate
trigger in [KB-LOCAL-002].

**Reject example (the operating scenario this rule exists to prevent):** an owner running two
unrelated businesses uses one physical address, one phone number, or one shared marketing asset
(a website footer, a shared ad account, a shared social handle) across both brands' public-facing
presence, or links both brands' GBP listings to the same website/phone number without the
distinct-signage and distinct-eligibility conditions actually being true on the ground. This reads
to Google as exactly the same-business-multiple-profiles pattern [KB-LOCAL-001]/[KB-LOCAL-002]
prohibit, and it is also the generic cross-brand-entanglement failure mode this doctrine exists to
flag structurally, independent of any specific company's facts — verify actual physical/legal/
signage separation before treating two brands' listings as eligible for independent profiles, and
never assume eligibility from convenience.

**Pass example:** two genuinely independent businesses at a shared address each with their own
legal name, phone number, and visible signage, each independently meeting GBP eligibility, each
verified and managed as its own profile with no shared linking between them.

## 3. Category selection

**[KB-LOCAL-006]** Every profile has exactly one primary category and up to nine secondary
categories (ten total). The primary category is a strong category-level ranking signal.
(third-party, aggregated GBP-optimization guidance, retrieved 2026-09-27 — Google does not publish
a single canonical page stating the exact 1-primary/9-secondary cap in one sentence; the 10-total
figure is consistent across current GBP editing-UI behavior and third-party guides and should be
re-verified against the live "Business categories" help article before being treated as
load-bearing for a specific claim).

**Mechanism, not number:** choose the most *specific* category the business genuinely qualifies
for, not the broadest one that feels safely inclusive — category specificity is what determines
whether the profile surfaces for a specific-intent local search.

**Reject example:** selecting an overly broad umbrella category when a specific, accurate category
exists and matches the primary service offered.

**Pass example:** selecting the most specific accurate primary category, then adding secondary
categories only for services genuinely and currently offered.

## 4. Services section

**[KB-LOCAL-007]** The Services section lets a profile list individual service offerings with
optional descriptions and pricing, and is Google's own sanctioned mechanism for a multi-service
business to represent its full offering on ONE profile — the structural alternative to the
one-profile-per-service anti-pattern in [KB-LOCAL-005]. (official, mechanism confirmed via GBP's
own profile-editing surface; a canonical single help-center URL for this feature was not
independently re-fetched in this pass — mark the specific field-limit/character-count details
UNVERIFIED until the live "Manage your services" help article is re-pulled at time of use:
https://support.google.com/business/answer/9797848)

**Pass example:** a single profile lists each distinct service line as its own entry with a plain,
accurate description, updated when a service is added, discontinued, or seasonal.

## 5. Posts

**[KB-LOCAL-008]** GBP Posts are short, time-bound updates (offers, events, product/service
highlights, "What's New") published directly to the profile and visible in Search/Maps.
UNVERIFIED (primary source unreachable: https://support.google.com/business/answer/7213077
returned no confirmed fetch in this pass) — treat exact post-type names, expiration windows, and
image-size requirements as needing re-verification against the live help article before citing a
specific number to a customer.

**Mechanism that does not need the exact numbers to be actionable:** Posts age out and go stale —
a profile with no recent Posts activity reads, to a visiting searcher, the same way a business's
last GBP review response from years ago reads: as unattended. Treat Posts as a standing cadence
item, not a one-time setup task.

## 6. Q&A

**[KB-LOCAL-009]** The Questions & Answers feature lets any Google user post a public question on
a profile and lets any Google user (not only the owner) post an answer — the business owner does
not have exclusive control over what answers appear. UNVERIFIED (primary source unreachable in
this pass: https://support.google.com/business/answer/9059491) — re-verify current owner-response
and moderation mechanics before advising a customer on Q&A strategy; do not assume the owner can
delete or gate incoming questions.

**Mechanism, sourced indirectly from the general GBP content-moderation policy already verified in
§7:** an owner-posted Q&A answer is still subject to the same prohibited-content categories as any
other profile content (no fake/misleading claims, no impersonation) — see [KB-LOCAL-011].

**Operational recommendation (mechanism-level, not a numbered claim):** because any user can
answer, an unattended Q&A section risks a competitor or a confused user posting an inaccurate
answer that stands uncorrected. A standing check-and-correct cadence, not a one-time seed, is the
correct operating model.

## 7. Content policy and suspension risk

**[KB-LOCAL-010]** Google may take enforcement action ranging up to account termination for
behavior that "harms our users, community, employees or ecosystem." (official, Google Business
Profile content policies, retrieved 2026-09-27: https://support.google.com/business/answer/2622994)

**[KB-LOCAL-011]** Prohibited content categories, as stated by Google, include: content not based
on a real experience or that does not accurately represent the location/product; paid or
incentivized reviews; content posted from multiple accounts by one person; soliciting reviews in
exchange for payment, discounts, or free goods/services; impersonating any person, group, or
organization; false descriptions of goods or services; distorting or omitting facts to scam other
users; harassment, hate speech, and offensive content; posting others' personal information
without consent; and misinformation, including health/medical falsehoods. (official, Google
Business Profile content policies, retrieved 2026-09-27:
https://support.google.com/business/answer/2622994)

**[KB-LOCAL-012]** A merchant may solicit genuine reviews without offering an incentive, but may
not require or pressure a customer to leave a rating or review while on the premises. (official,
same source as [KB-LOCAL-011], retrieved 2026-09-27)

**[KB-LOCAL-013]** Two suspension states exist: a "soft" suspension, where the profile stays live
on Search/Maps but cannot be edited until an appeal is filed, and a "hard" suspension, where the
profile is removed from Search/Maps entirely pending appeal. (third-party, aggregated GBP
suspension/reinstatement guidance, retrieved 2026-09-27 — Google's own consolidated
"Fix suspended or disabled profiles" help article, https://support.google.com/business/answer/4569145,
should be the source re-pulled at time of use for exact current appeal-flow mechanics; this claim
is directionally reliable but not independently re-verified as an exact Google quote in this pass).

**[KB-LOCAL-014]** Reinstatement runs through Google's Business Profile appeals tool: sign in with
the account tied to the profile, select it, submit the appeal with supporting evidence. A denied
appeal allows one additional review submission with further evidence; a second denial routes to
Google's Business Profile Community for Product Expert help. (third-party, aggregated
GBP-reinstatement guidance, retrieved 2026-09-27 — re-verify the current appeal-tool URL and flow
at time of use, since Google has changed this tooling's exact path multiple times historically).

**Common suspension triggers, named as a mechanism (not a numbered claim needing its own id,
because it restates §2/§7 above in operational terms):** incorrect or inconsistent business
information, fake or incentivized reviews, a profile that misrepresents the business's real-world
name/category/service-area, and — directly relevant to this file's own §2 — creating a duplicate
or improperly-linked profile for a business that already has one, or for a business sharing an
owner or address with another brand without the genuine independence [KB-LOCAL-004] requires.

## 8. Photos and verification, briefly (full photo-volume benchmarks live in the SEO domain)

**[KB-LOCAL-015]** Photo-volume and before/after benchmarks for a visually-driven local business
are covered in `seo/local-seo-for-contractors.md` §7 — this is a plain cross-reference, not a
separate claim; this file does not duplicate those numbers — see that file's own citation for the
sourced figures.

**[KB-LOCAL-016]** Profile verification (the process of proving to Google that the business
genuinely exists at the claimed address/service area) is a prerequisite for a profile to display
publicly and to be edited without triggering a soft-suspension review cycle. UNVERIFIED (primary
source unreachable in this pass: https://support.google.com/business/answer/7107242 was not
independently re-fetched) — re-verify the current verification-method list (video, phone, email,
postcard) before advising a customer on which method to expect, since Google has actively been
retiring postcard verification in favor of video verification and the available methods vary by
account history and business category.

---

## Contractor bend — for home-services/contractor (`local_service`) companies

The owner-operator residential-remodeling GC archetype (whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona, cited elsewhere in this directory only as an owner-operator behavior
illustration) experiences GBP as "my Google listing" — one
undifferentiated thing, not eight separate mechanisms (categories, posts, Q&A, reviews,
verification, suspension risk). Two translations matter most for this buyer:

- **The multi-brand rule in §2 is the single highest-consequence item in this file for an owner
  who runs more than one company** (a remodeling arm and a separate specialty-trade or rental
  business, for example, or any two ventures sharing a phone number or address). Getting this
  wrong risks losing the *primary* listing to suspension, not just failing to gain a second one —
  frame it to the buyer as "don't let Google think your two businesses are the same business," not
  as an abstract policy citation.
- **Suspension risk should be framed as downtime, not as a rules violation** — this buyer does not
  care about Google's spam-policy taxonomy, they care that their single largest lead source can
  disappear from Search for days to weeks during an appeal. Lead every suspension-avoidance
  recommendation with "here's what makes your listing vanish," not with the policy category name.


## Field notes: editing a Business Profile (added 2026-09-28)

- **[KB-LOCAL-058] Google silently adds services.** One contractor's profile had about 130 selected services (UNVERIFIED — seeded, needs derivation),
  including products it doesn't sell, a competitor's brand name and services from an unrelated line
  of business. Audit the full services list at every review. Remove anything the company doesn't
  sell. Services are toggle chips; predefined ones open a name-only editor, and custom ones show the
  name in the first text field. Delete = open service > Delete service > Delete. The panel closed
  after about five deletes in one observed session (UNVERIFIED — seeded, needs derivation); reopen it via "Edit services" (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-LOCAL-059] Edits are not live when saved.** Description edits show "pending" (the form said usually up to
  10 minutes; services up to a day — UNVERIFIED — seeded, needs derivation). The old value stays current until approval. Category edits
  list removed items in a PENDING block, so open the editor to read the real state (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-LOCAL-060] A category the platform lacks goes in services, not in the name.** If no category
  fits (e.g. mold remediation), list it as a service. A service keyword stuffed into the business
  name is a suspension risk (§7) (internal doctrine, retrieved 2026-09-28).
- **[KB-LOCAL-061] The profile panel's ad-status message can be stale.** It showed "Local Services ad
  is live" while the ad had stopped for an overdue balance. Check the source system (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-LOCAL-062] Review "Google updates" notices; never accept them blindly.** They can overwrite
  hours, categories or names with scraped data (internal doctrine, retrieved 2026-09-28).
