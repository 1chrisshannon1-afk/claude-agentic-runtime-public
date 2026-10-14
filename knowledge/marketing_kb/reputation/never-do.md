# Never-Do — Reputation Lane

Review and reputation tactics that are illegal (FTC), bannable (Google policy), or otherwise
categorically off the table for a content-strategist seat to recommend, propose, or draft toward.
This is the fast pre-publish check for the reputation lane specifically — pair it with this
directory's own `ANTI-PATTERNS.md` for reputation-lane bans, and with
[`../content/ANTI-PATTERNS.md`](../content/ANTI-PATTERNS.md) for content-wide bans.

**For a HIPAA-covered practice, none of this file's rules substitute for
`compliance/hipaa-marketing-for-practices.md` §6.1** — every reply for a practice account passes
that non-confirming template first (see `escalation-triggers.md` §0 and
`response-templates-by-severity.md` §0).

## 1. Fake or incentivized reviews — illegal, not just risky

**Rule:** Never recommend, draft, or facilitate a fake review, a paid review, a review traded for a
discount/credit/free product, or any review whose author has an undisclosed material connection to
the business.

**Citation (third-party, retrieved 2026-09-05):** The FTC's Rule on the Use of Consumer Reviews and
Testimonials took effect October 21, 2024 (**16 CFR Part 465** — correction 2026-09-05: an earlier
draft of this file cited Part 255, which is wrong; Part 255 is the FTC's separate, older Guides
Concerning the Use of Endorsements and Testimonials in Advertising, last revised 2023, not this
2024 rule — verified against ftc.gov's own Federal Register listing, "16 CFR Part 465: Trade
Regulation Rule on the Use of Consumer Reviews and Testimonials (Final Rule)," and the live eCFR
text at 16 CFR Part 465). It "specifically defines
and prohibits fake or false consumer reviews... as well as buying positive or negative reviews,"
and incentivized reviews — even when disclosed — cannot be exchanged for a **specific outcome
rating** (paying for "5-star reviews" is a violation even with a disclosure attached, per the same
rule). [FTC: Endorsements,
Influencers, and Reviews](https://www.ftc.gov/business-guidance/advertising-marketing/endorsements-influencers-reviews)
· [FTC Issues Final Rule on Consumer Reviews and Testimonials — Morgan Lewis](https://www.morganlewis.com/pubs/2024/08/ftc-issues-final-rule-on-consumer-reviews-and-testimonials)
· [Google's Rules for Incentivizing Reviews — Applause](https://www.applausehq.com/blog/googles-rules-for-incentivizing-reviews)
(rule-scope corroborated across the FTC page and Morgan Lewis). **Per-violation civil penalty ceiling:** see
`compliance/ftc-endorsements-and-fake-reviews.md` [KB-COMPLIANCE-004] for the current figure and its
sourcing — do not restate the number here.

**Dental/medical echo, mechanism-only:** for dental/medical companies, healthcare referral
incentives separately face Anti-Kickback Statute exposure (official, 42 U.S.C. §1320a-7b(b)) — a
different statute for a different act (referrals, not reviews), but the same underlying discipline:
an incentive tied to a specific favorable outcome (a referral that converts, a review that hits 5
stars) is where incentive programs turn into violations. For home-services/contractor companies
there is no direct Anti-Kickback analog, but the FTC review rule above is this vertical's real,
binding equivalent for the reviews specifically.

- REJECT: "Offer a $20 gift card for every 5-star Google review."
- REJECT: "Ask happy customers to leave a review, and quietly skip asking the customers who seemed
  unhappy." (This is review gating — see #2, a related but distinct violation.)
- ACCEPT: "Ask every customer for a review, regardless of how the job went, at the same touchpoint,
  with no reward tied to the review's content or rating."

## 2. Review gating — banned by Google policy even without a cash incentive

**Rule:** Never recommend or build a flow that screens customers before directing them to a public
review platform — i.e., customers who indicate a positive experience get routed to leave a Google
review, while customers who indicate a negative one get routed to a private feedback form instead.

**Citation (third-party, retrieved 2026-09-05):** *"Review gating... is the practice of screening
customers before directing them to a review platform, where customers who respond positively get a
link to leave a Google review while customers who respond negatively get redirected to a private
feedback form instead"* — explicitly against Google's Rating Manipulation policy, with consequences
ranging from review removal to full account suspension. [Google review policy in 2026 —
Birdeye](https://birdeye.com/blog/google-review-policy/) · [Applause, as
above](https://www.applausehq.com/blog/googles-rules-for-incentivizing-reviews).

**Dated update, its own citation (third-party, retrieved 2026-09-05):** Google's policy was
further tightened specifically on **April 16-17, 2026** — Birdeye, on the date itself: *"Google
officially implemented the new pre-publication screening tools and updated its Maps Rating
Manipulation clauses regarding staff name requests"* — and, on the underlying prohibition:
*"Google review policies now prohibit businesses from instructing staff to systematically solicit
reviews that include their individual names."* Applause corroborates the same prohibition
independently: *"Google updated its policy in April 2026 to prohibit soliciting reviews that ask
customers to mention a specific technician by name."* [Birdeye, as
above](https://birdeye.com/blog/google-review-policy/) · [Applause, as
above](https://www.applausehq.com/blog/googles-rules-for-incentivizing-reviews). Treat the
employee-name-solicitation ban as dated to April 16-17, 2026 and sourced to these two quotes.

**Correction 2026-09-05 — "staff review quotas" was NOT part of the dated update, mark
UNVERIFIED-as-dated:** an earlier draft of this file stated that staff review quotas were *also*
made an explicit violation as of April 16-17, 2026, riding the same two links as the name-mention
claim above with no distinct quote of its own. Re-checked against the primary source: Birdeye does
describe a "quota" violation elsewhere on the same page — *"Instructing staff to ask customers to
use specific names to meet quotas"* — but that line appears in Birdeye's general violations list,
not tied to the April 16-17 update announcement itself. Whether a staff-review-quota practice
(independent of employee-name solicitation) is its own violation, and if so since when, is
**UNVERIFIED** — do not cite a specific 2026 date for a quota-specific ban until a source ties one
to it directly.

- REJECT: A post-service survey that asks "how was your experience?" and only shows the "leave us a
  review" button to customers who answer positively.
- REJECT: Setting a monthly review quota per crew member/salesperson and asking customers by name to
  mention that person in their review — the name-solicitation half is the dated April 16-17, 2026
  violation above; the quota-as-such half is a separate, UNVERIFIED-as-dated practice per the
  correction above, but the combined ask is rejected either way.
- ACCEPT: A single, universal post-service touchpoint (SMS or email — for the email mechanism see
  [`../content/email-sequence-doctrine.md`](../content/email-sequence-doctrine.md); for SMS
  consent/compliance see [`../compliance/tcpa-a2p-10dlc.md`](../compliance/tcpa-a2p-10dlc.md)) that
  asks every customer for a review at the same
  moment, regardless of how the job went, with the same link for everyone.

## 3. Defensive, dishonest, or manipulative response tactics

**Rule:** Never draft a review response that disputes facts publicly, threatens the reviewer, or
tries to get a negative review taken down through pressure rather than through the platform's actual
removal process (which exists for genuinely fake/policy-violating reviews, not for true negative
ones).

This mirrors `response-templates-by-severity.md` §4's structural rules but states the harder
version as an absolute ban:
- REJECT: Threatening legal action against a reviewer for leaving a truthful negative review.
- REJECT: Mass-flagging a truthful negative review as "fake" or "spam" to get it removed through the
  platform's report mechanism — this is itself a form of manipulation, not legitimate use of the
  report tool (the report tool exists for genuinely fake reviews, not inconvenient true ones).
- REJECT: Publicly naming and shaming a negative reviewer, or disclosing private details about their
  job/account in a public reply to discredit them (this also crosses into the privacy-exposure
  hard-stop in `escalation-triggers.md` §2).
- ACCEPT: Reporting an ACTUALLY fake review (e.g., from a competitor, a person who was never a
  customer, or a review left as retaliation unrelated to any real service) through the platform's
  legitimate reporting flow — this is the correct tool for that specific problem, never used against
  a true but unflattering review.

## 4. Astroturfing and undisclosed self-promotion

**Rule:** Never recommend or draft content where the business (or an agent acting for it) poses as
an unaffiliated customer, competitor, or neutral third party — on review platforms, forums, or
social media.

**Citation (third-party, retrieved 2026-09-05):** covered by the same FTC endorsement-guide
framework above — an endorsement's true source and any material connection must be disclosed;
posing as an independent voice when one is not is a core violation the guides were revised to
target more explicitly starting with the 2023 update. [Baker Botts, FTC New Guidelines for
Endorsements and Testimonials](https://www.bakerbotts.com/thought-leadership/publications/2023/december/ftc-new-guidelines-for-endorsements-and-testimonials).

- REJECT: Creating a "customer" account to leave a positive review of the business.
- REJECT: Leaving a negative review on a competitor's listing from an account that doesn't disclose
  the competitive relationship.

## 5. Contractor bend

None of the above softens for this buyer — the FTC rule and Google's policy apply identically
regardless of vertical, and for home-services/contractor (`local_service`) companies the
owner-operator residential-remodeling GC archetype (whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`; `shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona) has exactly as much exposure to the per-violation
penalty ceiling (see `compliance/ftc-endorsements-and-fake-reviews.md`) as any
other business. What DOES change is the temptation profile: this buyer runs lean, often has one
person (the owner, or a spouse doing books) handling reviews personally rather than a marketing
department, and is more likely to reach for an informal shortcut precisely because it feels like
"just being efficient" rather than "gaming the system" — asking a crew lead to mention it to happy
customers on-site, handing out a card that says "leave us 5 stars and get $25 off your next job."
Both are real violations under #1/#2 above even though neither feels like corporate-scale
manipulation. When this seat drafts reputation-program guidance for this buyer, state the universal
ask (#2's ACCEPT pattern) explicitly as the alternative, in plain terms this buyer will actually
follow ("ask everybody the same way, every time, no strings") rather than assuming the FTC/Google
citations alone will land — a busy owner-operator is not going to read the CFR section, so the
guidance has to carry the compliant behavior as the default, not as a caveat.
