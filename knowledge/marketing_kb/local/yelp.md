# Yelp — Doctrine

Corpus for the `local/` domain (local-lead-platform doctrine feeding the GTM department's local
lead-generation lane). Company-agnostic: every example below is generic, not a real company's
account or numbers. Citation format per `shared/citation-style.md`: every claim carries a stable id
`[KB-LOCAL-NNN]` plus a provenance tag and retrieval date. Retrieval date for every claim in this
file: 2026-09-27, unless noted otherwise.

---

## 1. No-solicitation rule (the single most consequential Yelp-specific rule)

**[KB-LOCAL-001]** Yelp's Content Guidelines state plainly that "Businesses should never ask
customers to write reviews." (official, Yelp Content Guidelines, https://www.yelp.com/guidelines,
retrieved 2026-09-27).

**[KB-LOCAL-002]** Yelp's own Business Help Center article "Don't Ask for Reviews" defines
solicitation broadly — it is not limited to a direct verbal ask. Prohibited actions confirmed on
Yelp's official support content include (official, Yelp for Business Support Center, "Don't Ask for
Reviews," https://biz.yelp.com/support-center/article/Don-t-Ask-for-Reviews — the
`www.yelp-support.com` mirror of this same article failed TLS verification during this pass; this
`biz.yelp.com` URL is the reachable primary source and is confirmed live, retrieved 2026-09-27):

- Direct solicitation — verbally or digitally asking a customer, friend, or family member to
  leave a review.
- Incentivized reviews — offering a discount, free item, payment, or contest entry in exchange
  for a review.
- Routing customer feedback away from Yelp — the page states plainly, "Don't ask for reviews
  after requesting customer feedback in other places like surveys or contact forms." This is the
  mechanism sometimes called "review gating" elsewhere in the industry (using a satisfaction survey
  or similar filter to route only happy customers toward leaving a Yelp review, and unhappy ones
  elsewhere) — but that exact term does not appear on this page; treat "review gating" as this
  corpus's shorthand for the confirmed rule above, not as Yelp's own vocabulary.
- Paying for review removal — offering any incentive to get an existing review taken down.

Yelp's official blog, "Why Businesses Should Not Work with Review Solicitation Companies"
(https://blog.yelp.com/news/businesses-not-work-review-solicitation-companies/, retrieved
2026-09-27), confirms Yelp's general opposition to solicitation and states Yelp will demote
businesses showing "indicators of organized review solicitation through reputation management
companies" — but on this pass it did **not** contain an explicit line stating that hiring a
third-party review-solicitation service is itself a separately-named prohibited category (as
opposed to a way of triggering the same demotion consequence as direct solicitation). Treat "using a
reputation-management/solicitation vendor is against Yelp policy" as supported by this
demotion-risk language, but do not cite a standalone "hiring a third party is separately banned"
rule to that URL specifically.

**[KB-LOCAL-003]** The mechanism, not just the rule: Yelp's recommendation software is described
by Yelp itself as evaluating "hundreds of signals of quality, reliability, and user activity,"
and one of its four named detection categories is "reviews that it suspects the business owner or
an employee asked for" (official, Yelp Trust & Safety, "Recommendation software,"
https://trust.yelp.com/recommendation-software/, retrieved 2026-09-27). A review the software
flags as solicited is filed under "not recommended" — it stays visible via a link at the bottom of
the business page but does not count toward the star rating or review count (official, same
source). This means solicitation does not just risk a policy violation; it structurally fails at
its own goal — a solicited review that gets flagged never touches the number a prospective
customer actually sees.

**[KB-LOCAL-004]** The most severe enforcement outcome is a Consumer Alert: Yelp's User Operations
team places one on a business's page when it has evidence the business (or someone acting for it)
offered compensation — cash, discounts, gift certificates, or other incentives — in exchange for
writing, changing, or removing reviews. Yelp's own reporting states over 300 businesses received a
Consumer Alert in one measured year, with home services the single largest category at 17% of
alerts (third-party-reported Yelp statistic via Yelp's own blog, "Yelp's 2019 Consumer Alert
Report," https://blog.yelp.com/news/yelp-2019-consumer-alert-report/, retrieved 2026-09-27 — note
this specific figure is from Yelp's 2019 annual report, cited here for the mechanism and category
distribution, not as a current-year number). A Consumer Alert is a public banner on the page
itself — visible to every visitor, not just an internal flag. Yelp's Trust & Safety Consumer
Alerts page (https://trust.yelp.com/consumer-alerts/, retrieved 2026-09-27) confirms alerts are
removed once the underlying issue is resolved, but its only stated removal condition covers a
*different* alert type (Unusual Activity Alerts): "when activity returns to normal, our
moderators remove the alert and clean up the page" — no fixed duration is given anywhere on that
page, and it contains no "90 days" figure for a review-solicitation Consumer Alert. **No specific
removal timeframe for a review-solicitation Consumer Alert is confirmed by any source checked in
this pass — do not state a specific duration (90 days or otherwise) to a contractor.**

**Mechanism vs. number:** the rule (never ask, never incentivize, never gate, never outsource to a
solicitation vendor) is the portable, hard doctrine. The 300-businesses/17%-home-services figure is
cited only to establish that home services is a real, disproportionately-affected category — it is
not a rate any specific company should expect to apply to itself. The alert-removal *duration* is
unconfirmed; only the fact that it is condition-based (not automatic/scheduled) is documented.

### What compliant review growth looks like instead

**[KB-LOCAL-005]** Yelp's own guidance for growing reviews without asking centers on making the
Yelp page easy to *find* passively rather than prompting anyone to write anything: displaying a
"Find us on Yelp" window cling/sticker at the physical location, adding a Yelp badge or link to a
business's own website and email signature, and simply delivering good service consistently
(official, Yelp for Business, "How to get Yelp reviews without asking,"
https://business.yelp.com/resources/articles/how-to-get-yelp-reviews-without-asking/, retrieved
2026-09-27). None of this is a request — it is discoverability.

---

## 2. The recommendation ("filter") algorithm

**[KB-LOCAL-006]** Yelp officially describes the recommendation software as fully automated, with
no manual override by Yelp employees or advertisers, applying the same rules uniformly to every
business (official, https://trust.yelp.com/recommendation-software/, retrieved 2026-09-27). It
evaluates reviews across four named categories:

1. **Conflicts of interest** — reviews suspected to come from people with an undisclosed tie to
   the business: competitors, disgruntled ex-employees, friends, or family.
2. **Solicited reviews** — reviews the software suspects were asked for by the business owner or
   an employee (see §1 above — this is the mechanical enforcement arm of the no-ask rule).
3. **Reliability** — reviews from accounts too new or too inactive for the software to have
   enough signal to trust.
4. **Usefulness** — content that is an "unhelpful rant or rave" or otherwise low-information is
   deprioritized even absent any conflict-of-interest or solicitation signal.

**[KB-LOCAL-007]** Roughly three-quarters of all reviews submitted are recommended; the rest are
still visible to any visitor who clicks "reviews that are not currently recommended" at the bottom
of the page — they are never deleted, only excluded from the star average and count (official,
Yelp for Business Support Center, "Does Yelp recommend every review?,"
https://biz.yelp.com/support-center/article/Does-Yelp-recommend-every-review — the
`www.yelp-support.com` mirror of this same article failed TLS verification during this pass; this
`biz.yelp.com` URL is the reachable primary source and is confirmed live, retrieved 2026-09-27).
Practical implication: a business owner checking their own Yelp rating should also check the
not-recommended tail — a real customer's genuine review can land there for reliability/usefulness
reasons alone, with no wrongdoing on the business's part, and that review is not lost, just excluded
from the count.

**[KB-LOCAL-008]** A California appellate court affirmed that Yelp's public description of how its
recommendation software works is truthful (official, Yelp's own announcement of the ruling, Yelp
blog, "Appellate court affirms Yelp truthfully describes its recommendation software,"
https://blog.yelp.com/news/appellate-court-affirms-yelp-truthfully-describes-its-recommendation-software/,
retrieved 2026-09-27). This is cited here only to establish that the mechanism described in
[KB-LOCAL-006]/[KB-LOCAL-007] is Yelp's real, litigation-tested position, not marketing copy that
oversells manual curation as pure automation.

---

## 3. Business accounts, users, and access

**[KB-LOCAL-009]** A Yelp for Business account supports adding multiple users at no extra cost —
official guidance states up to 15 users can be invited to a single business (official, Yelp for
Business Support Center, "How do I share access to the Yelp page for my business?,"
https://biz.yelp.com/support-center/article/How-do-I-set-up-additional-logins-for-my-Yelp-Business-Account
— the `www.yelp-support.com` mirror of this same article failed TLS verification during this pass;
this `biz.yelp.com` URL is the reachable primary source and is confirmed live, retrieved 2026-09-27,
corroborated by Yelp for Business, "How to add another user to your Yelp for Business account,"
https://business.yelp.com/resources/articles/add-users-on-yelp/, retrieved 2026-09-27).

**[KB-LOCAL-010]** **Users all get full access — there is no read-only or restricted role.** Once
an invited user accepts, they receive the *same* access as the account owner to the selected
business page: they can change business information, purchase ads using the existing payment
method on file or change the payment method entirely, and — critically — grant that same
full-access level to still more users (official, same sources as [KB-LOCAL-009]). Yelp's invite
flow does ask the inviter to pick a "job title" label for the new user during setup, but this is a
descriptive label for internal reference, not a permission tier — it does not gate what the user
can actually do on the account.

**Why this matters operationally (mechanism, not a company-specific fact):** because every invited
user can independently authorize ad spend against the account's payment method and can invite
further full-access users, a business should treat every Yelp user invite as equivalent to handing
over the account, not as a scoped "employee login." A business with more than ~10 locations may need
to go through Yelp support rather than the self-serve flow to add a user at all (official, same
sources).

---

## 4. Yelp Ads basics

**[KB-LOCAL-011]** Yelp Ads run on a cost-per-click (CPC) model: a business is charged only when a
user actually clicks the ad, and CPC ads are shown within the business's own category plus other
categories Yelp's delivery system judges relevant (official, Yelp for Business Support Center, "How
does Yelp's Cost Per Click (CPC) advertising program work?,"
https://biz.yelp.com/support-center/article/How-does-Yelp-s-Cost-Per-Click-CPC-advertising-program-work,
retrieved 2026-09-27). This same page states plainly that ad spend is **not paced evenly** across a
billing period: "Since your CPC can vary, your ad will not be paced to spend your budget evenly each
day of the month. You could spend $5 one day and $7 another day." (official, same source, verbatim
quote confirmed by direct re-fetch 2026-09-27). The total across the month never exceeds the set
budget — the daily spend is simply uneven, driven by the same auction dynamics described in
[KB-LOCAL-012] below.

**[KB-LOCAL-012]** CPC price is **not fixed** — it is set dynamically through an automated,
real-time auction. Yelp's own words: "You pay a different price per click depending on the supply
and demand of that moment." The price paid for any given click depends on supply and demand at that
moment: how many similar businesses are competing for the same clicks, available ad inventory, and
consumer search interest at that time (official, Yelp for Business Support Center, "How is the
cost-per-click for Yelp Ads determined?,"
https://biz.yelp.com/support-center/article/How-is-the-cost-per-click-for-Yelp-Ads-determined,
retrieved 2026-09-27). This page does **not** itself address ad-spend pacing — that specific
sentence lives on the sibling CPC-program page cited at [KB-LOCAL-011] above, which does confirm
spend is not paced evenly; do not cite the pacing sentence to this URL, cite it to [KB-LOCAL-011]'s
URL instead.

**Practical implication for budget-setting doctrine:** because CPC is auction-driven and, per
[KB-LOCAL-011], not paced evenly across the month, a monthly ad budget on Yelp should be treated
the same way a paid-search budget is treated elsewhere in this corpus — as a ceiling the auction
spends against at a fluctuating per-click price and an uneven daily rate, not a number that
guarantees a fixed click volume or a level daily spend. Any specific CPC-range claim for a real
account belongs in that account's own `internal-measured` record, never asserted here as a general
figure — no general CPC-range number is recorded in this file because none was independently
verified from a primary Yelp source during this pass.

---

## Contractor bend

A residential remodeling GC reading this file cares about exactly two things: (1) never let anyone
on the team — including a well-meaning office manager — text a happy client "hey, would you mind
leaving us a Yelp review?", because that single message is precisely what both the Content
Guidelines and the recommendation software exist to catch, and getting caught costs a visible
public Consumer Alert on the page that every future customer sees before they ever call, for as
long as the underlying issue remains unresolved — **never quote a specific duration (90 days or
otherwise) to a contractor; see [KB-LOCAL-004], which confirms removal is condition-based with no
fixed timeframe documented by any source checked** — and (2) treat
every Yelp user invite as a master key, not a limited login — a scheduler or estimator added "just
to see leads" can spend the ad budget and add more full-access users the same afternoon. The
compliant path to more reviews is boring and structural: a Yelp window cling on the shop door, a
Yelp link in the email signature, and consistently good work — never a request.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend on this platform. Claim ids 001-012 in
this file are shared with `gbp-optimization.md` (both files independently define this range) and
must be file-qualified in any reference; see `INDEX.md`'s "Known pre-existing overlaps" note.*
