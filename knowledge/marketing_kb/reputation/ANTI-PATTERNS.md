# Reputation Anti-Patterns — Things a Seat Must NEVER Recommend

Every item below is something a content-strategist, or any GTM agent touching reputation/review
work, must refuse to propose — even when a founder/operator asks for it directly, even when a
competitor is visibly doing it, and even when it would plausibly work short-term. Cite this file
when refusing. This file is the anti-pattern companion to `never-do.md` (which states the same
categorical bans as flat rules with pass/reject examples); this file exists to give each one its
own "why it's banned" treatment, worked business-consequence framing, and cross-reference, matching
the house structure `seo/ANTI-PATTERNS.md` already uses for its domain.

**For a HIPAA-covered practice, `compliance/hipaa-marketing-for-practices.md` §6.1 is a mandatory
pre-filter on top of every pattern below** — see `escalation-triggers.md` §0 and
`response-templates-by-severity.md` §0.

Every numeric/behavioral claim below carries a stable id `[KB-REP-NNN]` (continuing this
directory's numbering from `review-velocity-metrics.md`, which ends at `[KB-REP-033]`) and a
citation. Retrieval date for every source in this file: **2026-09-27**, unless noted otherwise
(e.g. [KB-REP-037], which cites `never-do.md` §2's own 2026-09-05 retrieval rather than re-fetching).

## 1. Review gating — screening customers before the public review link

**What it is:** Any flow that determines, based on a customer's expressed or predicted sentiment,
which customers get routed to a public review platform (Google, Yelp, Facebook) and which get
routed to a private "tell us more" form instead — most commonly a post-service survey that asks
"how was your experience?" first and only shows the public review link to customers who answer
positively.

**Why it's banned:** This is both a federal violation and a platform violation simultaneously.
**[KB-REP-034]** The FTC's Rule on the Use of Consumer Reviews and Testimonials, §465.7, prohibits
materially misrepresenting that a platform's displayed reviews represent most or all submitted
reviews when negative-sentiment reviews are being suppressed (official, Cornell Law eCFR mirror,
16 CFR Part 465, retrieved 2026-09-27 — full citation and quoted text at
`review-acquisition-compliant.md` [KB-REP-018]; not re-quoted here per this corpus's house rule
against duplicating a cited number/quote across files). **[KB-REP-035]** Google's own policy
independently prohibits this practice (the practice this corpus calls "review gating" — see
`platform-review-policies.md` [KB-REP-003] for the UNVERIFIED caveat on whether Google's own page
uses that exact term) as a Rating Manipulation
violation, with enforcement ranging from content removal to account suspension (official, same
source as `platform-review-policies.md` [KB-REP-001]/[KB-REP-003], retrieved 2026-09-27). A gating
flow is therefore doubly exposed: it can trigger federal penalty exposure (see
`compliance/ftc-endorsements-and-fake-reviews.md` [KB-COMPLIANCE-004] for the current per-violation
ceiling) AND independently get a Google Business Profile suspended, which
is a different and often more immediate business cost than the FTC penalty — a suspended profile
stops showing in Maps/Search entirely, which is a total, sudden loss of the channel most GC
prospects use first (`review-velocity-metrics.md` [KB-REP-024]: 97% read reviews before deciding).

- **REJECT:** A post-service SMS survey that asks "Rate your experience 1-5" and only sends the
  Google review link to responses of 4 or 5.
- **REJECT:** Instructing office staff to "mention the Google review to the customers who seemed
  happy" and skip mentioning it to the ones who complained during the walkthrough — this is
  [KB-REP-034]'s prohibited shape done by hand, not by software, and is exactly as much a
  violation (see `review-acquisition-compliant.md`'s Contractor bend section).
- **ACCEPT:** One universal request — same message, same link, same moment (typically final
  walkthrough or invoice-paid) — sent to every customer regardless of how the job visibly went.
  See `review-acquisition-compliant.md` §5 for the full compliant-flow specification.

## 2. Incentivizing reviews — any reward tied to the act or outcome of reviewing

**What it is:** Offering a discount, gift card, sweepstakes entry, free service, or any other
thing of value in exchange for a customer writing a review — whether or not the incentive is
explicitly conditioned on a specific star rating.

**Why it's banned:** **[KB-REP-036]** The FTC rule's operative language bans compensation or
incentives "in exchange for... the writing or creation of consumer reviews" full stop — the ban
applies even to an unconditional "leave any review, good or bad" incentive, not only a
"5-star reviews get a reward" scheme (official, same source as [KB-REP-034], §465.4, quoted in
full at `review-acquisition-compliant.md` [KB-REP-017]). This is a common trap specifically
because it feels defensible ("we're not paying for good reviews, we're paying for any review") —
the rule does not carry that exception.

- **REJECT:** "Leave us a review — any review — and get entered in our monthly $100 gift card
  drawing."
- **REJECT:** A card handed at the final walkthrough: "leave us 5 stars and get $25 off your next
  job."
- **ACCEPT:** Asking for a review with nothing offered in exchange, applied identically to every
  customer.

## 3. Employee-name solicitation and undisclosed insider reviews

**What it is:** (a) Instructing staff to systematically ask customers to name a specific
technician/crew member in their review, typically to hit a per-employee review quota; (b) an
owner, employee, or close relative posting a review of the business from a personal account with
no disclosure of the relationship.

**Why it's banned:** **[KB-REP-037]** Google's policy was tightened specifically on April 16-17,
2026 to prohibit "instructing staff to systematically solicit reviews that include their
individual names" (third-party, retrieved 2026-09-05, per `never-do.md` §2 — Birdeye and Applause
both confirm this specific date and quote independently; see that
file for the full two-source citation rather than duplicating it here). **[KB-REP-038]** Separately,
the FTC rule's §465.5 prohibits undisclosed insider reviews and testimonials — an owner or
employee's review presented as if from an independent customer, with no disclosure of the
employment or family relationship (official, same source as [KB-REP-034], §465.5, retrieved
2026-09-27; see `review-acquisition-compliant.md` [KB-REP-020] for the fuller treatment and its
own UNVERIFIED-on-exact-wording caveat). These are two distinct violations riding the same
temptation — a small GC office running an informal "ask them to mention Mike" habit to reward a
crew lead, or an owner's spouse posting a glowing review from a personal account — and both are
banned regardless of intent to deceive.

- **REJECT:** Setting a monthly review-mention quota per crew member and asking customers by name
  to mention that person.
- **REJECT:** An owner posting a 5-star review of their own company from a personal Google
  account with no disclosure.
- **ACCEPT:** A genuine customer voluntarily naming a crew member they liked, with no solicitation
  of that specific mention.
- **ACCEPT:** An owner's family member who was ALSO a real paying customer discloses the
  relationship explicitly in the review text before describing their real experience.

## 4. Defensive, argumentative, or dishonest public review responses

**What it is:** A drafted response that publicly disputes facts, argues with the reviewer,
minimizes their experience, discloses private customer/job details to discredit them, or attempts
to pressure a genuinely true negative review into being taken down (as opposed to using a
platform's legitimate reporting flow for an actually fake review).

**Why it's banned:** **[KB-REP-039]** This is the single most-repeated instruction in the
dental-vertical doctrine this corpus's response doctrine ported from (for a HIPAA-covered practice
account itself, this doctrine applies directly and unmodified — see
`escalation-triggers.md` §0): never post a defensive or templated
response (mechanism, internal doctrine, dental vertical, ported and generalized at
`response-templates-by-severity.md` §4 and §1). A defensive public reply is read by every future
prospect who finds the thread — not just the original reviewer — and a public factual dispute or a
privacy-violating callout does more lasting reputational damage than the original negative review
ever could, because it demonstrates how the business behaves under criticism to every subsequent
reader (`review-velocity-metrics.md` [KB-REP-029]: 80% of consumers are more likely to use a
business that responds to all its reviews — the SAME dynamic that rewards responding punishes
responding badly). Publicly naming and shaming a reviewer, or disclosing their private job/account
details, additionally crosses into `escalation-triggers.md` §2's privacy-exposure hard-stop.

- **REJECT:** "That's not what happened — our crew has photos proving otherwise." (Public factual
  dispute; see `response-templates-by-severity.md` §4's rejected-examples list for the same
  pattern stated as a drafting rule.)
- **REJECT:** Mass-flagging a truthful negative review as "fake" or "spam" through a platform's
  report tool to get it removed — this is manipulation of the report mechanism, not legitimate use
  of it (see `never-do.md` §3).
- **ACCEPT:** "I'm sorry the framing timeline didn't match what we discussed. Please call me
  directly at [number] so we can talk through what happened and make it right." — acknowledges,
  takes partial responsibility, moves the dispute off the public thread.

## 5. Auto-posting any review response or reputation-related send without an approval gate

**What it is:** Publishing a drafted review response, a Google Business Profile post, or a
review-request SMS/email campaign without a human (the operator, or whoever holds that role for a
given seat) approving the specific content first.

**Why it's banned:** **[KB-REP-040]** A published reply is seen immediately, the reviewer is
notified, and screenshots outlive any later deletion — so a bad publish is effectively
unrecoverable in practice even where a platform technically permits an edit or delete afterward
(re-cite to the platform's own official help page — e.g. Google's "Read & reply to reviews" page for
GBP — before asserting the mechanical edit/delete question either way; see
`response-templates-by-severity.md` §1's "no auto-posting, at any severity" rule for the current
phrasing). This is why every severity level in `response-templates-by-severity.md` — including a
glowing 5-star reply — is a proposed draft, never a direct publish: the cost of a bad publish is
asymmetric (effectively unrecoverable) while the cost of a one-step approval delay is trivial.

- **REJECT:** A pipeline that drafts a response to every new review and posts it automatically
  the same day with no human review step.
- **ACCEPT:** Draft generated, proposed to the operator (or designated reviewer) with the review
  content and platform link attached, posted only after explicit approval.

## 6. Porting an analogous-vertical review-management number as if it were construction-specific

**What it is:** Citing a dental-vertical (or any other analogous-vertical) reputation-management
benchmark number — a specific response-time target, a specific review-velocity cadence, a specific
star-rating threshold — as if it applies to a residential remodeling GC without independent
home-services sourcing.

**Why it's banned:** **[KB-REP-041]** This corpus's own numbers in `review-velocity-metrics.md`
are sourced independently from a general consumer-behavior survey (BrightLocal), not derived from
the dental-vertical internal doctrine — but the STRUCTURE this corpus ported from that doctrine (the
severity ladder, the escalation triggers, the "no auto-post" rule) is a mechanism port, and
`review-velocity-metrics.md` [KB-REP-032] explicitly flags that a specific home-services review
cadence target ("1-2 new reviews per week") is UNVERIFIED and must not be presented as a settled
number. Porting a mechanism is sound practice (see this directory's INDEX.md reading-order
guidance); porting a NUMBER from a different vertical without re-derivation misprices every
downstream recommendation built on it. See `shared/citation-style.md`'s own worked example on this
exact failure mode.

- **REJECT:** "Aim for 1-2 new reviews per week, same as a dental practice benchmark."
- **ACCEPT:** Deriving a cadence target from this corpus's own sourced numbers — enough volume to
  clear the ~20-review floor ([KB-REP-025]), frequent enough to keep a meaningful share within the
  90-day recency window ([KB-REP-026]) — and marking anything more specific as UNVERIFIED until a
  home-services-specific source is retrieved.

**The ban runs in every direction, not just dental-into-home-services.** The same rule applies
porting a home-services review-management number as if it were dental/medical-specific — e.g.
citing a residential-remodeling response-time target or review-velocity cadence as a benchmark for
a dental or medical practice account without independent, vertical-appropriate sourcing. This
directory's own house style (`INDEX.md`) and `local/ANTI-PATTERNS.md` #10 already state this
symmetrically; it is restated here because a dental practice is now one of the verticals this
corpus's consuming companies operate in, not a hypothetical.

---

## Contractor bend

None of the six patterns above soften for the owner-operator residential-remodeling GC archetype
(whose relevant end-customer persona is `shared/homeowner-buyer-psychology.md`;
`shared/contractor-buyer-psychology.md` is a different, B2B software-buyer persona) — the FTC rule
and every platform's policy apply identically regardless of vertical or company size, and this
buyer has exactly as much exposure to the per-violation penalty ceiling (see
`compliance/ftc-endorsements-and-fake-reviews.md`) or a suspended Google
Business Profile as any larger business. What changes is the temptation profile and the cost of
getting caught: this buyer typically runs lean, with one person (the owner, a spouse doing books,
or an office manager) handling reviews personally rather than a dedicated reputation-management
department, which makes an informal shortcut — asking a crew lead to mention their name, skipping
the review ask on the job that went sideways, firing back at an unfair-feeling review from the
truck — feel like ordinary business behavior rather than a policy violation. It is a violation
either way. This buyer also depends on a comparatively SMALL number of recent reviews to win the
next job in a specific neighborhood (`review-velocity-metrics.md`'s Contractor bend section), which
means the downside of a suspended profile or a viral defensive-reply screenshot is proportionally
larger for this buyer than for a business with thousands of reviews spread across a national
footprint. When a seat drafts reputation guidance for this buyer, lead with the plain-language
version of each rule above ("ask everybody the same way, every time, no strings," "never argue
publicly, take it to the phone") rather than the CFR section number — this buyer is not going to
read the statute, so the guidance has to carry the compliant behavior as the obvious default.
