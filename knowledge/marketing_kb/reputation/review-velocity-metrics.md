# Review Velocity Metrics — Volume, Recency, Response Time, Rating Thresholds

What the research says about how many reviews, how recent, and how fast a response needs to be
before it measurably changes consumer behavior. This file is the numbers; `review-acquisition-compliant.md`
and `never-do.md`/`escalation-triggers.md`/`response-templates-by-severity.md` are the compliant
mechanics and response doctrine that use these numbers to set cadence and priority.

Every claim below carries a stable id `[KB-REP-NNN]` (continuing this directory's numbering) and a
citation. Retrieval date: **2026-09-27**.

## 1. Review-reading behavior and volume threshold

**[KB-REP-024]** 97% of consumers read reviews for local businesses before deciding whether to use
them. (third-party, BrightLocal Local Consumer Review Survey 2026, retrieved 2026-09-27:
https://www.brightlocal.com/research/local-consumer-review-survey/ — annual survey; methodology
and sample size not independently re-verified beyond what the source states.)

**[KB-REP-025]** 47% of consumers will not use a business with fewer than 20 reviews; only 9%
will accept five or fewer. (third-party, same source as [KB-REP-024], retrieved 2026-09-27) This
sets a practical floor: a newly-launched or review-light GC profile is invisible to nearly half of
prospects doing due diligence, independent of star rating.

## 2. Recency threshold

**[KB-REP-026]** 74% of consumers want to see reviews written within the last three months to
consider them relevant; 32% want reviews from within the preceding two weeks specifically.
(third-party, same source as [KB-REP-024], retrieved 2026-09-27) This is the number that makes
review acquisition an ONGOING cadence rather than a one-time push — a GC with 40 reviews all from
18 months ago fails [KB-REP-026]'s recency bar for most prospects even though it clears
[KB-REP-025]'s volume bar.

## 3. Star-rating threshold

**[KB-REP-027]** 31% of consumers will only use a business rated 4.5 stars or higher; 68% require
at least 4 stars. (third-party, same source as [KB-REP-024], retrieved 2026-09-27) Read together
with [KB-REP-025]: volume and rating are independent gates a prospect applies — a business needs
to clear BOTH the count threshold and the rating threshold, not just one.

## 4. Response-time expectations

**[KB-REP-028]** 89% of consumers expect a business owner to respond to reviews at all (any
response, not speed-specific). Of those expecting a response: 19% expect it the same day it's
posted, 32% expect it by the next day, and 81% expect to hear back within a week. (third-party,
same source as [KB-REP-024], retrieved 2026-09-27)

**[KB-REP-029]** 80% of consumers say they are more likely to use a business that responds to all
of its reviews; 42% say they are unlikely to choose a business that ignores reviews entirely.
(third-party, same source as [KB-REP-024], retrieved 2026-09-27) This is the evidentiary basis for
`response-templates-by-severity.md` §1's "no auto-posting, but also no ignoring" standing practice
— responding (even to positive reviews) is not merely good manners, it measurably affects
conversion for the NEXT prospect reading the thread, not just the original reviewer.

**[KB-REP-030]** 50% of consumers are put off by a generic or templated-sounding reply. (third-party,
same source as [KB-REP-024], retrieved 2026-09-27) This is the quantitative backing for
`response-templates-by-severity.md` §2's "reference one SPECIFIC detail" rule and the file's
explicit reject examples for generic non-apologies — roughly half of readers can tell, and are
turned off when they can.

## 5. What this corpus could NOT confirm — flagged, not guessed

**[KB-REP-031]** UNVERIFIED — seeded, needs derivation. Whether review VELOCITY (the rate at which
new reviews arrive, independent of total count or rating) is itself a ranking factor in Google's
local-search algorithm is a commonly repeated claim in SEO/marketing trade content, but the
retrieval pass for this file explicitly asked BrightLocal's 2026 survey about this relationship and
the source stated it does not address review-arrival-frequency effects on ranking. Do not cite a
specific velocity-to-ranking correlation without a source that actually measures it — this corpus's
`seo/local-seo-for-contractors.md` (if/when it addresses local ranking factors) is the more
appropriate place to carry a properly-sourced ranking-factor claim; this file only carries the
CONSUMER-BEHAVIOR numbers above, which are confirmed.

**[KB-REP-032]** UNVERIFIED — seeded, needs derivation. A commonly repeated home-services-specific
benchmark ("aim for 1-2 new reviews per week" or similar cadence targets) exists in trade-press and
agency-blog content but was not independently sourced for this file. Do not present a specific
weekly/monthly review-acquisition cadence target as a settled number; derive one from
[KB-REP-025]/[KB-REP-026] instead (enough volume to clear the ~20-review floor, frequent enough to
keep a meaningful share within the 3-month recency window) until a direct, home-services-specific
source is retrieved.

## 6. How a seat should use these numbers

**[KB-REP-033]** (internal synthesis of [KB-REP-024] through [KB-REP-030] — not a separate
citation.) Practical reading order for a content-strategist or reputation-focused seat evaluating a
GC's current review profile:
1. Count check against [KB-REP-025] — is the business above or below the ~20-review floor.
2. Recency check against [KB-REP-026] — what share of reviews fall inside the last 90 days.
3. Rating check against [KB-REP-027] — is the business above or below 4.0/4.5.
4. Response-rate check against [KB-REP-028]/[KB-REP-029] — what share of existing reviews (any
   rating) have an owner response, and how stale is the most recent one.
A profile that's strong on rating but weak on recency or response-rate is a different problem
(and a different fix) than one that's strong on volume but weak on rating — do not collapse these
into a single "reputation score" without naming which specific gate is failing.

## Contractor bend

None of these numbers change for the owner-operator residential-remodeling GC archetype (whose
relevant end-customer persona is `shared/homeowner-buyer-psychology.md`;
`shared/contractor-buyer-psychology.md` is a different, B2B software-buyer persona) — a homeowner researching a five-figure
remodel applies the same 97%-read-reviews, ~20-review-floor, ~90-day-recency scrutiny as a
consumer researching a restaurant, arguably MORE scrutiny given the stakes of the purchase. What
changes is the GC's typical starting point: most residential contractors this corpus's buyer
profile represents have never run a deliberate review-acquisition cadence at all, so the realistic
first move is almost always closing the [KB-REP-025] volume gap and the [KB-REP-026] recency gap
before optimizing anything else — a business with 6 reviews from two years ago fails on count and
recency simultaneously, and no amount of response-quality polish (however well `response-templates-by-severity.md`
is followed) fixes either of those two gates.
