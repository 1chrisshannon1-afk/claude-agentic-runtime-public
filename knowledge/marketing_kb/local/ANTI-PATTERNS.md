# Local Domain Anti-Patterns — Things a Seat Must NEVER Recommend

Every item below is something any GTM agent touching a local-presence or local-lead-marketplace
platform (GBP, Yelp, Angi/HomeAdvisor, Thumbtack, Houzz Pro, Nextdoor, BBB, Apple Business Connect,
Bing Places) must refuse to propose, even when a founder/operator asks for it directly, even when a
competitor is visibly doing it, and even when it would plausibly work short-term. Cite this file when
refusing.

---

## 1. Asking for, incentivizing, or gating reviews

**What it is:** Directly or indirectly asking a customer to leave a review, offering a discount,
free item, payment, or contest entry in exchange for a review, or using a satisfaction survey/filter
to route only happy customers toward a public review platform while diverting unhappy ones
elsewhere.

**Why it's banned:** Yelp's own Content Guidelines state plainly that "Businesses should never ask
customers to write reviews," and Yelp's Business Help Center separately confirms "Don't ask for
reviews after requesting customer feedback in other places like surveys or contact forms" — the
mechanism this corpus calls "review gating," though that exact term is this corpus's own shorthand,
not Yelp's published vocabulary (`local/yelp.md` [KB-LOCAL-001], [KB-LOCAL-002]). Incentivized
reviews are separately and explicitly prohibited by the same source. Google Business Profile content
policy separately prohibits paid or incentivized reviews and pressuring a customer to leave a rating
while on the premises (`local/gbp-optimization.md` [KB-LOCAL-011], [KB-LOCAL-012]). Both platforms'
own automated detection systems specifically target this behavior — Yelp's recommendation software
names "solicited reviews" as one of four detection categories (`local/yelp.md` [KB-LOCAL-006]) — so
this is not a policy risk that can be quietly worked around; it is mechanically detected.

**Reject example:** a follow-up text to every completed job reading "Loved working with us? We'd
really appreciate a Yelp review!" A satisfaction survey that only forwards 4-5 star respondents to a
public review link.

**Pass example:** a Yelp window cling at the shop, a review-platform badge in the email signature,
and consistently good work — passive discoverability, never a request (`local/yelp.md` §1 "What
compliant review growth looks like instead").

## 2. Review-gating disguised as "quality control"

**What it is:** A variant of #1 worth naming separately because it is often proposed in good faith:
routing customers through a private feedback form first and only inviting the ones who report
satisfaction to post publicly, framed internally as "making sure we only surface real happy
customers" rather than as solicitation.

**Why it's banned:** This is the exact mechanism Yelp's own "don't ask for reviews after requesting
customer feedback in other places like surveys or contact forms" rule and Google's content policy
both target — filtering who gets asked based on anticipated sentiment is prohibited regardless of
the internal justification offered for it (`local/yelp.md` [KB-LOCAL-002];
`local/gbp-optimization.md` [KB-LOCAL-011]). Relabeling the mechanism as "quality control" does not
change what the platform's enforcement system sees.

**Reject example:** "Rate your experience 1-5 privately first — we'll only send our public review
link to customers who rate us 4 or higher."

**Pass example:** the same review-request cadence sent identically to every customer regardless of
any private sentiment signal, with no differential routing based on anticipated rating.

## 3. Creating a duplicate or cross-linked profile instead of fixing access

**What it is:** Spinning up a second GBP, Yelp, or marketplace profile for a business that already
has one — because login credentials were lost, because an agency set up the "wrong" one, or because
it seems faster than requesting ownership transfer — or linking two genuinely different businesses'
profiles/accounts together for convenience.

**Why it's banned:** Google explicitly states there should be only one profile per business, and
lists "multiple profiles exist for the same business" as a duplicate trigger that gets a profile
suppressed from Search/Maps entirely (`local/gbp-optimization.md` [KB-LOCAL-001], [KB-LOCAL-002]).
The correct path — requesting ownership/manager access to the existing profile, or reporting a
genuine duplicate for merge — exists precisely so this shortcut is never necessary
(`local/gbp-optimization.md` §1 reject/pass examples).

**Reject example:** creating a second GBP listing for the same location because the original
account's login was lost, rather than going through Google's ownership-recovery flow.

**Pass example:** requesting ownership/manager access to the existing verified profile, or filing a
duplicate-merge report, and treating access recovery as the blocking task rather than routing around
it with a new profile.

## 4. Treating two brands sharing an owner, address, or contact info as independently eligible for separate profiles without verifying it

**What it is:** Setting up separate GBP (or Yelp, or any local-listing) profiles for two brands that
share a physical address, a phone number, or other public-facing infrastructure, without confirming
the platform's actual independence requirements (distinct, visible signage; genuine independent
eligibility for each brand) are met on the ground.

**Why it's banned:** Google's guidance requires "a clearly visible difference in signage" and
genuine independent eligibility before two brands at one address may each hold a separate profile —
absent that, it reads as exactly the same-business-multiple-profiles pattern that gets a profile
suppressed (`local/gbp-optimization.md` [KB-LOCAL-003], [KB-LOCAL-004]). This is the single
highest-consequence item in the GBP file for any operator who runs more than one business, because
getting it wrong risks the *primary* listing's suspension, not merely a rejected second listing
(`local/gbp-optimization.md` Contractor bend). It is also, independently, exactly the kind of
cross-business entanglement `shared/company-pack-authoring.md` §4-§5/§7 (the `credential_ref` /
`identity_allowlist` / `shared_identifiers` cross-company checks) treats as
categorically forbidden regardless of platform mechanics — never assume eligibility from
convenience; verify actual physical/legal/signage separation first
(`local/gbp-optimization.md` [KB-LOCAL-005] reject example).

**Reject example:** linking two unrelated businesses' GBP listings to the same website or phone
number, or assuming two brands at a shared address qualify for separate profiles without checking
for genuine on-site signage separation.

**Pass example:** two genuinely independent businesses at a shared address, each with its own legal
name, phone number, and visible signage, each independently verified and managed with no shared
linking between the profiles.

## 5. Handing out full-access platform logins as if they were scoped employee accounts

**What it is:** Inviting a field employee, scheduler, or estimator to a Yelp, Angi, or Houzz Pro
business account using whatever the default/simplest invite flow offers, without checking whether
that platform's roles are actually scoped or all-or-nothing.

**Why it's banned:** This is platform-specific and the risk is asymmetric — Yelp's invite flow grants
every added user the *same* full access as the account owner, including the ability to spend against
the account's payment method and invite further full-access users; the "job title" field at invite
time is descriptive only and gates nothing (`local/yelp.md` [KB-LOCAL-009], [KB-LOCAL-010]). Angi
and Houzz Pro, by contrast, do offer a genuinely scoped lower-access role (Angi's Associate; Houzz
Pro's Field Crew/Design Team) that is safe to hand to field staff (`local/angi-homeadvisor.md`
[KB-LOCAL-013]–[KB-LOCAL-014]; `local/houzz-pro.md` §1). Recommending an invite without first
checking which kind of platform this is treats every invite as equally safe when it is not.

**Reject example:** adding an office employee to the Yelp business account "just to check leads,"
without flagging that this grants them full spend authority and the power to add more full-access
users.

**Pass example:** on Yelp, reserving every invite for someone accountable for spend decisions; on
Angi or Houzz Pro, defaulting field/office staff to the scoped role (Associate; Field Crew/Design
Team) and reserving the unrestricted role for the owner or whoever owns the budget decision.

## 6. Disputing a marketplace lead on grounds the platform's own policy already excludes

**What it is:** Filing (or recommending filing) a lead-credit dispute for a lead that simply didn't
convert — the consumer didn't call back, found someone else, changed their mind, or was
window-shopping — as if non-conversion alone were a valid dispute reason.

**Why it's banned:** Angi/HomeAdvisor's own official Lead Credit Guidelines explicitly list these as
**not** eligible for credit, stating they are "accounted for in our lead pricing and therefore not
eligible for lead credits" (`local/angi-homeadvisor.md` [KB-LOCAL-019]). Recommending a dispute on
these grounds wastes the 30-day dispute window on a claim that cannot succeed by the platform's own
stated policy, and it sets an unrealistic expectation that every paid lead should convert.

**Reject example:** advising a client to dispute a lead because "they never called us back" with no
other data-quality defect (wrong service area, wrong job type, duplicate, disconnected contact info)
present.

**Pass example:** disputing only leads that meet the platform's own stated eligible-category list
(duplicate, wrong service area, wrong job type, competitor test, bad contact info —
`local/angi-homeadvisor.md` [KB-LOCAL-017]) within the stated window, and treating a low close rate
with no such defect as a sales-process problem, not a platform dispute.

## 7. Comparing lead-marketplace platforms by raw cost-per-lead or cost-per-click

**What it is:** Recommending a budget shift between platforms (e.g. "move spend from Angi to
Thumbtack") based on comparing each platform's raw per-lead or per-click price, without computing
cost per actually-booked job.

**Why it's banned:** Every platform in this directory bills on a different unit (per-click, per-lead
with two sub-types, bundled-subscription-plus-lead), so raw per-unit price is not a comparable
number across platforms, and it ignores credits recovered and the labor cost of working low-intent
leads that a cheaper-looking platform may generate in higher volume
(`local/lead-marketplace-economics.md` §1–§3). This produces exactly the kind of unsourced,
seeded-from-nowhere recommendation `shared/citation-style.md` and this directory's own economics
doctrine exist to prevent.

**Reject example:** "Angi is cheaper than Thumbtack" based only on comparing each platform's
advertised average lead price.

**Pass example:** computing fully-loaded cost per booked job for each platform from the business's
own CRM/billing data over a comparable trailing period before recommending any budget shift
(`local/lead-marketplace-economics.md` §2, §4).

## 8. Recommending a specialist/specialty claim without licensure verification (dental/medical accounts)

**What it is:** Drafting ad copy, website copy, or a GBP post using "specialist," "specializes in,"
or an equivalent claim of advanced/exclusive expertise for a dental or medical practice account,
without first confirming the practice's state licensing board recognizes that named area as an
accredited specialty and that the specific practitioner holds the required credential.

**Why it's banned:** every U.S. state prohibits false or misleading professional advertising, and a
practice claiming an unrecognized specialty is a named, board-enforced violation independent of any
platform policy or HIPAA question (`local/dental-practice-local-notes.md` [KB-LOCAL-049], citing
`compliance/hipaa-marketing-for-practices.md` [KB-COMPLIANCE-057]). This is not a GC-archetype rule —
it exists in this file specifically because it is easy for a GTM seat used to writing home-services
copy to treat a specialty claim as a pure positioning/SEO choice, which it is not for a licensed
practice.

**Reject example:** writing "our cosmetic dentistry specialist" into ad copy for a practice without
checking whether the practitioner holds a board-recognized cosmetic-dentistry credential or whether
the state even recognizes that as a specialty.

**Pass example:** using accurate non-specialty framing ("experienced in," "offers," "focuses much of
the practice on") unless and until the `hipaa` compliance lane has confirmed the specific
practitioner's credential against the specific state board's recognized-specialty list.

## 9. Drafting a public reply to a dental/medical review the way a home-services review reply is drafted

**What it is:** Applying this directory's general review-reply tone/timing doctrine to a dental or
medical practice's review reply without first routing the draft through the compliance file's
non-confirming reply template.

**Why it's banned:** two HHS OCR enforcement actions are documented for exactly this failure mode —
a practice confirming patient status or restating treatment/cost/insurance details in a public reply,
even when the patient volunteered that information first — with real settlement money and multi-year
corrective action plans attached. **Both are UNVERIFIED against a primary source as of this
writing** — the compliance file's own citations for them (`compliance/hipaa-marketing-for-practices.md`
[KB-COMPLIANCE-055], [KB-COMPLIANCE-056]) mark each one `UNVERIFIED (primary source unreachable)`:
the live HHS.gov pages and an archived mirror all returned HTTP 403 to that pass's automated fetch.
The settlement amounts, practice names, and disclosure mechanism are corroborated across multiple
independent third-party legal/trade sources (`(third-party)`, per that file), so the underlying facts
are well-attested — but treat this as third-party-corroborated, not primary-source-verified, until
the `hipaa`/trust-architect lane re-fetches the HHS press release or a reachable archived copy of it
directly. This directory's own review-reply doctrine
(`yelp.md`, `gbp-optimization.md`) covers platform mechanics only and contains no PHI-safety rule of
its own — it must never be applied to a practice account as if it were sufficient on its own
(`local/dental-practice-local-notes.md` [KB-LOCAL-052]).

**Reject example:** drafting a warm, personalized reply to a negative dental review using this
directory's general "acknowledge and invite offline" tone guidance, without checking it against
`compliance/hipaa-marketing-for-practices.md` §6.1's non-confirming rules first.

**Pass example:** every dental/medical review reply passes through the compliance file's §6.1
template (never confirm patient status, never restate clinical/financial/insurance detail, invite
offline via neutral language, escalate rather than draft-and-publish for anything naming a clinical
detail or alleging malpractice) before this directory's own platform-tone doctrine is layered on top.

## 10. Porting a number from one platform, vertical, or buyer archetype as if it applies to another

**What it is:** Quoting a specific dollar figure, percentage, or benchmark from one platform's
doctrine (or from the dental-vertical corpus) as if it applies directly to a different platform or
buyer archetype, without independent derivation or an explicit UNVERIFIED marking.

**Why it's banned:** this directory is built specifically to keep vertical- and platform-specific
numbers from silently generalizing — Angi's dispute-denial-rate and sub-30-day filing-window figures
circulating in trade content were removed from `local/angi-homeadvisor.md` for lack of any
attributable source (`local/angi-homeadvisor.md` [KB-LOCAL-020], [KB-LOCAL-021]), a
prior Nextdoor free-post figure ("2 free posts per month... within 2 miles") was found to be stale
and actively contradicted by Nextdoor's own current page (which states unlimited free posts) and
was removed rather than ported forward or re-hedged (`local/nextdoor.md` [KB-LOCAL-035]), and
`dental-practice-local-notes.md` explicitly forbids porting `lead-marketplace-economics.md`'s method
with home-services-specific inputs onto a dental account
(`local/dental-practice-local-notes.md` [KB-LOCAL-055]). The same citation-style discipline that
governs dental-vertical numbers porting into home-services doctrine (`seo/ANTI-PATTERNS.md` #10)
applies in every direction across this corpus, not just that one.

**Reject example:** quoting any Angi dispute-denial percentage, or applying an Angi dispute figure to
a Thumbtack conversation.

**Pass example:** citing a platform-specific figure only for that platform, with its existing
UNVERIFIED marking preserved, and independently deriving or explicitly flagging as UNVERIFIED any
number proposed for a different platform or vertical.

---

## Contractor bend — for home-services/contractor (`local_service`) companies

None of the above changes for the owner-operator residential-remodeling GC archetype (whose
relevant end-customer persona is `shared/homeowner-buyer-psychology.md`;
`shared/contractor-buyer-psychology.md` is a different, B2B software-buyer persona, used elsewhere
only as an owner-operator behavior illustration) — if
anything the stakes are higher for items #3–#5 (duplicate profiles, cross-brand entanglement,
full-access logins) because this buyer typically has no dedicated marketing or IT staff to catch the
mistake before it costs a suspended primary listing or a hijacked ad budget. When explaining why
something here is off-limits, skip the platform-policy-taxonomy framing and lead with the concrete
business consequence in plain terms — "if we do this, your listing disappears from Search for weeks"
lands; "this violates Google's duplicate-content policy" does not. For items #8–#9 specifically
(dental/medical-only), remember this buyer archetype does not exist in the rest of this directory —
never apply a dental/medical anti-pattern rule to a GC account or vice versa, and never assume a rule
that's safe for one archetype is safe for the other just because the underlying platform (GBP, Yelp)
is the same one. The obligation not to offer any of these shortcuts is entirely on the agent, never
on the operator to catch and refuse first.
