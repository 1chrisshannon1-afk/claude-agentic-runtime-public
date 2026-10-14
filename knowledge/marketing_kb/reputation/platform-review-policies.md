# Platform Review Policies — Google, Yelp, Facebook, Angi, Houzz, BBB

What each major review platform actually permits and forbids a business to do around its own
reviews — soliciting them, responding to them, disputing them, and what triggers platform-side
enforcement. This file is platform mechanics; `review-acquisition-compliant.md` is the legal
floor (FTC) that sits underneath all of it; `never-do.md` and `escalation-triggers.md` (this
directory) cover response-drafting conduct once a review exists.

Every claim below carries a stable id `[KB-REP-NNN]` and a citation. Retrieval date for every
source in this file: **2026-09-27**.

## 1. Google (Google Business Profile / Google Maps)

**[KB-REP-001]** Google prohibits reviews and ratings that do not reflect a "genuine, unbiased"
experience with a business — this includes fake/non-genuine reviews, reviews posted from multiple
accounts by one person, and reviews generated or manipulated via automation/emulators. (official,
Google Business Profile Help, "Prohibited and restricted content," retrieved 2026-09-27:
https://support.google.com/business/answer/2622994)

**[KB-REP-002]** A business may **not** offer any incentive — payment, discount, free goods or
services — in exchange for a review, regardless of whether the incentive is conditioned on a
specific rating. Google's own wording: businesses must not "offer incentives — such as payment,
discounts, free goods and/or services — in exchange for posting any review." (official, same
source as [KB-REP-001], retrieved 2026-09-27)

**[KB-REP-003]** A business may **not** discourage negative reviews or selectively solicit only
customers likely to leave a positive one — this is the practice this corpus calls "review gating"
(the prohibition itself is on Google's own prohibited-content page; **UNVERIFIED** whether that
page uses the term "review gating" itself — re-verify against
support.google.com/business/answer/2622994 before asserting Google names it that; compare
`local/yelp.md`'s identical caveat for Yelp's own page), and it is
a policy violation independent of any incentive being offered (compare `never-do.md` #2, which
carries the dated April 2026 tightening on staff-name solicitation specifically). (official, same
source as [KB-REP-001], retrieved 2026-09-27)

**[KB-REP-004]** A business may **not** require customers to write a review while still on the
business's premises, or pressure a customer toward specific wording or content. Soliciting genuine
reviews with no incentive attached and no content pressure remains permitted. (official, same
source as [KB-REP-001], retrieved 2026-09-27)

**[KB-REP-005]** Enforcement ranges from removing the offending content up to suspending or
terminating the business's Google Maps/Business Profile account privileges, for on- or
off-platform behavior Google judges harmful to users or the review ecosystem. Removal is
requested through Google's own "Report abuse" flow, not through a public dispute in a reply.
(official, same source as [KB-REP-001], retrieved 2026-09-27)

**Contractor application:** a homeowner is far more likely to be handed a review-request card,
text, or QR code at the final walkthrough than to be asked in any other retail-style setting —
[KB-REP-004]'s "not on premises" line is exactly the moment a GC crew is most tempted to break.
The compliant version is a request sent later — SMS or email — to every customer alike, with no
content or rating steered (for the email mechanism see
[`../content/email-sequence-doctrine.md`](../content/email-sequence-doctrine.md); for SMS
consent/compliance see [`../compliance/tcpa-a2p-10dlc.md`](../compliance/tcpa-a2p-10dlc.md)).

## 2. Yelp

**[KB-REP-006]** Yelp's own guidance states plainly that businesses should not solicit reviews
from customers at all — "Businesses should never ask customers to write reviews" appears in
Yelp's content guidelines. This is a stricter stance than Google's or most other platforms', which
generally permit non-incentivized solicitation. (official, Yelp Content Guidelines, retrieved
2026-09-27: https://www.yelp.com/guidelines)

**[KB-REP-007]** The existence and trigger of a Yelp "Consumer Alert" banner — placed on a
business's page when Yelp's User Operations team has evidence the business (or someone acting for
it) offered compensation in exchange for writing, changing, or removing reviews — is confirmed via
`local/yelp.md` [KB-LOCAL-004]'s reachable sources (Yelp's own Trust & Safety Consumer Alerts page,
`trust.yelp.com/consumer-alerts/`, and Yelp's 2019 Consumer Alert Report blog post, both retrieved
2026-09-27), which succeeded where the `www.yelp-support.com` article URLs originally attempted for
this claim returned connection/certificate errors. **The removal DURATION remains UNVERIFIED**:
per `local/yelp.md` [KB-LOCAL-004], Yelp's own Consumer Alerts page confirms alerts are
condition-based (removed once the underlying issue is resolved) but states no fixed timeframe for a
review-solicitation alert specifically — do not cite a specific duration (90 days or otherwise).

**Contractor application:** [KB-REP-006] means the single most natural instinct for a GC — "hey,
would you mind leaving us a Yelp review?" — is itself against Yelp's stated policy, unlike every
other platform in this file. A seat proposing a review-acquisition program must route Yelp traffic
through organic discovery and Yelp's own request-a-quote/consumer-initiated flows rather than
direct solicitation, or flag the platform-specific conflict explicitly to whoever owns the
program.

## 3. Facebook (Meta) Page ratings and recommendations

**[KB-REP-008]** UNVERIFIED (primary source unreachable: https://www.facebook.com/business/help/477434545776260
and https://www.facebook.com/help/477434545776260 — both returned "page isn't available" on
retrieval attempt 2026-09-27; https://transparency.meta.com/en-gb/policies/community-standards/fraud-deception/
also 404'd). Facebook Pages support a "recommendations" (thumbs up/down) feature in place of a
star-rating system in most regions as of this corpus's build; whether the underlying policy text
addressing fake/incentivized recommendations is captured at a different, stable URL is unconfirmed
— do not cite specific Meta review-policy language without re-attempting retrieval, and do not
assume Facebook's rules mirror Google's simply because the mechanism (recommendations vs. star
ratings) looks similar.

**[KB-REP-009]** Meta's general platform-wide prohibition on "inauthentic behavior" (coordinated
fake accounts, engagement manipulation) is well-documented as a cross-product policy, but this
corpus has not independently retrieved the specific page naming reviews/recommendations as a
covered surface — treat any claim that Facebook's inauthentic-behavior policy explicitly reaches
Page recommendations as UNVERIFIED per [KB-REP-008] until a working source is retrieved.

**Contractor application:** until [KB-REP-008]/[KB-REP-009] are resolved, treat Facebook
recommendation solicitation under the SAME discipline as Google ([KB-REP-002]/[KB-REP-003]) as a
conservative default — no incentive, no gating, ask everyone alike — rather than assuming a looser
rule exists simply because it hasn't been confirmed.

## 4. Angi (formerly Angie's List / HomeAdvisor)

**[KB-REP-010]** UNVERIFIED (primary source unreachable: https://www.angi.com/company/reviewguidelines/
and https://www.angi.com/articles/ratings-reviews-faq.htm — both 403/404'd on retrieval attempt
2026-09-27). Angi is widely reported (third-party trade press, not independently verified here)
to run a lead-generation/pay-per-lead model where reviews influence a provider's ranking and lead
volume, distinct from Google/Yelp's organic-discovery model — this distinction matters because
Angi review-acquisition incentives interact with the platform's own paid-placement mechanics in a
way the other platforms in this file do not. Do not cite specific Angi review-solicitation or
incentive rules until a working primary source is retrieved.

**Contractor application:** because Angi's exact review-incentive rule is UNVERIFIED, apply the
FTC floor (`review-acquisition-compliant.md`) as the binding constraint regardless of platform —
the FTC rule against paying for reviews (16 CFR 465.4) applies on every platform a review can
appear on, Angi included, independent of whatever additional platform-specific rule Angi may or
may not layer on top.

## 5. Houzz

**[KB-REP-011]** UNVERIFIED (primary source unreachable: https://help.houzz.com/s/article/Review-Guidelines
and https://www.houzz.com/reviewGuidelines — both 404'd on retrieval attempt 2026-09-27). Houzz is
a project-portfolio-first platform for design/build professionals where reviews are commonly tied
to a specific completed, photographed project rather than a general business listing — this
corpus has not independently verified Houzz's specific solicitation or dispute-process rules.

**Contractor application:** same fallback as Angi — apply the FTC floor regardless of Houzz's
specific platform rule until [KB-REP-011] is resolved. A GC using Houzz for project portfolios
should treat photo/project-tied reviews with the same no-incentive, no-gating discipline as every
other platform in this file.

## 6. BBB (Better Business Bureau)

**[KB-REP-012]** UNVERIFIED (primary source unreachable: https://www.bbb.org/all/bbb-rating-and-accreditation-standards,
https://www.bbb.org/faq/reviews-and-complaints/, and https://www.bbb.org/article/tips/23021-bbb-tip-online-reviews
— all 404'd on retrieval attempt 2026-09-27). BBB is widely understood (not independently verified
here) to distinguish "customer reviews" (a star-rating feature) from "complaints" (BBB's formal
dispute-resolution process, which affects a business's letter-grade rating far more directly than
reviews do) — this distinction is operationally important for a GC because an unresolved BBB
*complaint* is a materially bigger reputational and rating risk than a negative *review*, but this
corpus has not confirmed BBB's exact review-incentive or verification rules from a working source.

**Contractor application:** treat a BBB complaint (not a review) as an automatic hard-stop trigger
under `escalation-triggers.md` §2 by extension of that file's existing categories — a formal BBB
complaint functions like a licensing/legal-standing dispute (same file, same section) even though
it is not literally a platform review, because a bad response can affect the business's BBB
rating and accreditation status directly.

## 7. Cross-platform pattern (what's common across every platform above)

**[KB-REP-013]** (internal synthesis of [KB-REP-001] through [KB-REP-012], not a separate citation
— this is a structural observation about the pattern already sourced above.) Every platform this
corpus could confirm (Google, Yelp) bans (a) paying or trading incentives for reviews and (b)
selectively steering only positive-experience customers to the public review surface. The
platforms this corpus could NOT confirm (Facebook, Angi, Houzz, BBB) should be treated as bound by
the SAME two rules as a conservative default, plus the FTC floor in `review-acquisition-compliant.md`,
which applies regardless of any individual platform's own policy — the FTC rule is federal law,
not a platform term of service, so it binds a business's conduct even on a platform whose own
policy is silent or unconfirmed.

## Contractor bend

The owner-operator residential-remodeling GC archetype (whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona)
does not run a coordinated multi-platform review program the way a franchise
chain does — reviews accumulate opportunistically across whichever platforms a homeowner happens
to use (Google is dominant, Facebook and Yelp secondary, Angi/Houzz specific to how the lead was
sourced, BBB mostly relevant if the business is accredited). The practical guidance for this buyer
is not "master six different rulebooks" — it's "ask every customer the same way, at the same
moment, with nothing offered for a specific rating, on whichever platforms you're actually active
on" — which happens to satisfy every platform's rule in this file simultaneously, confirmed or
not, because it never triggers the one mechanism ([KB-REP-002]/[KB-REP-003]/[KB-REP-013]) every
platform bans.
