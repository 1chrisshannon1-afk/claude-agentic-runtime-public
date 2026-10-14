# Account Audit Rubric

Ported incident-derived mechanism, 2026-07 (a 16-point audit rubric and full analysis protocol;
original source not re-fetchable from the runtime). This is the GATE — no bid, budget, or keyword
optimization should be proposed on an account that hasn't cleared it. Structure is domain-agnostic;
any vertical- or company-specific references from the ported source are stripped and replaced with
generic guidance.

---

## Mental model — durable truths to hold before auditing

- **Ad Strength is NOT Ad Rank, and Quality Score is NOT an auction input.** Ad Rank is calculated
  at auction time from the bid amount, the quality of the ad and landing page as measured AT
  auction time, the Ad Rank thresholds, the competitiveness of the auction, the context of the
  search (location, device, time, the nature of the search terms, the other ads/results on the
  page), and the expected impact of assets and other ad formats — **Quality Score is never
  multiplied into that calculation.** ("Ad Rank scores are calculated based on many factors,
  including your bid amount, the quality of your ads and landing page, the Ad Rank thresholds, the
  competitiveness of an auction, the context of the person's search..., and the expected impact of
  assets and other ad formats" — [Google Ads Help: About Ad Rank](https://support.google.com/google-ads/answer/1752122),
  official, retrieved 2026-09-19.) Quality Score (1-10) is a reported **diagnostic** — "Quality
  Score is not an input in the ad auction. It's a diagnostic tool to identify how ads that show for
  certain keywords affect the user experience" ([Google Ads Help: Quality Score](https://support.google.com/google-ads/answer/6167118),
  official, retrieved 2026-09-19) — an aggregate of the same underlying quality signals (expected
  CTR, ad relevance, landing-page experience) that DO feed the auction directly; the reported 1-10
  number itself is never an auction input. Expected CTR and ad relevance are modeled by Google, not
  crawled; landing-page experience is assessed by a pre-click crawl (UNVERIFIED — seeded, needs
  derivation; re-verify the exact landing-page-experience assessment mechanism against Google's
  current Quality Score documentation before citing it as a specific mechanism). A keyword can carry
  a QS before its first click (impression-based, UNVERIFIED — seeded, needs derivation for the exact
  impression threshold); one with too few impressions shows no QS yet at all. Ad Strength is a
  third, separate thing — "Ad Strength is a feedback tool for asset diversity and combination
  testing. It isn't used to calculate Ad Rank, Quality Score, or auction wins."
  ([Google Ads Help: About ad strength](https://support.google.com/google-ads/answer/9921843),
  official, retrieved 2026-09-19.)
- **Diagnostic signature:** high lost impression share from RANK with roughly 0% lost from
  BUDGET means a starved bid or weak relevance — fix bid, Quality Score, or ad relevance, never
  budget. The inverse (high budget-lost IS, low rank-lost IS) means the campaign is genuinely
  capped and budget is the correct lever.
- **Search top impression share below 10%** means the ads are rarely shown above the organic
  results, regardless of overall impression share (ported incident-derived mechanism, 2026-07 —
  UNVERIFIED as an official Google-stated threshold; cite Google's own impression-share metric
  definitions — [Google Ads Help: About impression share metrics](https://support.google.com/google-ads/answer/2497703),
  official, retrieved 2026-09-27 — for the metric itself, treating the specific 10% cutoff as a
  heuristic pending re-derivation).
- **State, don't hardcode.** Pin only stable identifiers (account IDs, conversion-action names) —
  and pin them in the company's own dossier, never in this runtime doctrine file, which is shared
  across every GTM-managed company and names no account. Every live number — CPA, impression
  share, conversion counts, spend — must be read fresh each audit run, never baked into a rule or
  carried forward from a prior review without re-deriving it.

## Step 0 — Verify live data before starting

Pull fresh from the live ad platform, not a cached export, for the trailing 30 days — via the
execution/analyst lane that holds live platform access, or from the company's own dossier's
re-derive pointer if that lane has already run this pull. **This seat itself may never log in or
make an authenticated platform fetch** (see `agents/paid-acquisition-strategist.md`'s advisory-only
scope); if neither the execution lane's live data nor a fresh dossier re-derive is available, the
audit cannot proceed — declare it DEGRADED for this run rather than substituting a cached or
remembered number. Confirm each of these fields is READABLE (returns a real value, even if that
value is legitimately zero): campaign status, spend, a conversion count (counted or
all-conversions), and impression share. **This step checks that the fields exist and return data —
it does not require any of them to be non-zero.** A genuinely zero-conversion account is exactly
what Step 4's conversion-tracking test and the Step 7 scoring table are built to catch; Step 0 would
contradict both if it demanded a non-zero conversion count just to begin.

If total spend across all campaigns is zero for the last 30 days: **record the Spend-present
dimension as 0 (Fail), mark every other dimension "not evaluated — blocked on zero spend", and
report "0/16 — blocked on zero spend, remaining dimensions not evaluated."** "Not evaluated
(blocked)" is a different state from "N/A for scope" (see the Scope note below): a blocked audit is
exempt from N/A normalization and always reports against the full 16 — then STOP; do not attempt Steps 1-7's other checks.
Escalate — verify billing, campaign status, and bid floor before doing anything else. This makes
Step 7's "No spend in 30d" Fail cell an actually-reachable outcome (a genuine 0/16 audit result),
rather than a state Step 0 pre-empts entirely. (Zero SPEND blocks every OTHER check because there
is nothing to audit yet; zero CONVERSIONS with real spend does not block anything — that is a
Step 4/Step 7 finding, not a Step 0 stop condition.)

## Scope note — Search-specific dimensions, N/A normalization, and the non-Search-primary account

**This rubric's scoring dimensions (Steps 2-3, 5, and most of the 16-point table) are Google
Search-specific** (Quality Score, keyword bloat, lost impression share by rank/budget, negatives).
Step 1 (campaign inventory — orphaned campaigns, zero-spend campaigns, channel-type sanity, serving
status) is NOT Search-specific: every check inside it works for any channel type (Search, PMax,
Display, LSA, Meta), so it applies to every audit unchanged, same as Step 0 and Step 4 below.
Step 0 (live-data verification) and Step 4 (the canonical 4-signal conversion-tracking test) also
apply to every channel type unchanged — those two steps are not Search-specific either.

For an account or channel where a Search-specific dimension doesn't apply — PMax asset groups, LSA,
or Meta — the dimension is marked N/A with a one-line reason rather than scored 0/1/2, and the
"Outputs required" section still lists it explicitly as N/A so the audit record is honest about
what it did and did not cover.

**N/A normalization for the 16-point table:** each dimension is worth 2 points. When N dimensions
are marked N/A **for scope reasons** (the dimension does not apply to this channel — never scored
0), score the account out of `2 x (8 - N)` points instead of a flat 16, and scale the lower cut
points of the interpretation bands by the same ratio `(8 - N) / 8`, rounding to whole points — e.g.
an account with 3 N/A dimensions is scored out of 10, and the 14-16/9-13/0-8 bands become 9-10 /
6-8 / 0-5 (14 x 10/16 = 8.75 → 9; 9 x 10/16 = 5.6 → 6). State both the raw score and the denominator
explicitly in the audit record, e.g. "6/10 (3 dimensions N/A)". Never report a raw score against
the full 16-point denominator when any dimension was marked N/A for scope — that silently
understates the account, exactly the failure mode this normalization exists to prevent. **This
normalization never applies to a Step 0 zero-spend block**, which reports "0/16 — blocked, not
evaluated" (see Step 0): a blocked audit did not find the other dimensions inapplicable, it simply
could not evaluate them.

**A Meta-only, PMax-only, or LSA-heavy account cannot be scored on the 16-point Search table** —
every Search-specific dimension is N/A. Score it on this minimal channel-agnostic sub-rubric instead,
out of 6, and say so explicitly in the audit record ("channel-agnostic sub-rubric, N/6"). This is a
minimal floor, not a full per-channel scorecard; a richer PMax/LSA/Meta-specific table is open
follow-up work for this file.

| Dimension | 0 (Fail) | 1 (Warning) | 2 (Pass) |
|---|---|---|---|
| Spend present | No spend in 30d (Step 0 applies — blocked, not evaluated) | Spend below the Step 5a account-level floor | Spend at or above that floor, sustained across the 30-day window |
| Structure (by the channel's own resource hierarchy — PMax campaign → asset group; Meta campaign → ad set → ad; LSA account → service/job types) | Any enabled parent with no enabled child that can serve | Serving, but a structural warning (e.g. an asset group or ad set with incomplete required assets, or over half its children paused) | Every enabled parent has ≥1 enabled, complete child |
| Conversion tracking | 0 primary/counted conversions in 30d | A 4-signal-test signal or the 48-hour rule fails on primary actions | The canonical 4-signal test passes AND the 48-hour rule is satisfied |

*(Band design ported from the Search table's own dimensions; UNVERIFIED as any platform-stated
threshold.)* Interpretation: 6 = ready to optimize; 3-5 = proceed with caution; 0-2 = needs
remediation first. A mixed account (Search plus another channel) scores its Search campaigns on the
16-point table and its other channels on this sub-rubric, reporting both separately — never a
blended single number.

## Step 1 — Campaign inventory

Paused and removed campaigns are
excluded from scoring and surfaced separately as a learning corpus — mine them for proven
keywords, winning copy, and negative-keyword history, but never score or write to them (see
[`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #12).

Checks:
1. **Orphaned campaigns** — status ENABLED but zero impressions for 14+ days (ported incident-derived
   mechanism, 2026-07 — UNVERIFIED as an official Google threshold; needs vertical-specific (per the company's profile)
   re-derivation rather than assumed universal). Flag each; root causes: all keywords paused, budget
   effectively zero, disapproved ads, geo mismatch.
2. **Zero-spend enabled campaigns** — status ENABLED, zero cost for 30 days. Silently inactive;
   flag for investigation.
3. **Channel-type sanity** — every active campaign matches its intended type (Search / PMax /
   Display / LSA). Flag anything unexpected.
4. **Serving status** — must read as actively serving for every intended-active campaign; flag
   ENDED, PENDING, SUSPENDED, or REMOVED statuses that shouldn't be there.

Pass threshold: zero orphaned campaigns, or every orphan has a documented root cause.

## Step 2 — Ad group health

Checks:
1. Paused ad groups inside enabled campaigns — expected if intentional; flag if over 50% of a
   campaign's ad groups are paused (ported incident-derived mechanism, 2026-07 — UNVERIFIED as an
   official Google threshold; treat as a heuristic starting point, not a hard rule).
2. **Ad groups with zero enabled ads** — an enabled ad group with no enabled ads cannot serve.
   This is a CRITICAL structural defect, reported even when the count is zero.
3. Single-keyword ad groups — note but don't automatically flag as bad; confirm intentional.
4. Zero-impression ad groups (enabled, has keywords, zero impressions in 30 days) — candidate
   causes: low bids, low QS, keyword overlap, disapprovals.

**Structural completeness (CRITICAL fail conditions):**
- Any ENABLED campaign with zero ad groups cannot serve at all.
- Any ENABLED ad group with zero enabled ads cannot serve at all.

Both conditions lower the Campaign Structure and Ad Group Health scores independently and are
reported explicitly even at zero, so the audit record is unambiguous.

Pass threshold: zero ad groups with zero enabled ads, AND zero enabled campaigns with zero ad
groups.

## Step 3 — Keyword health

Checks:
1. **Quality Score** — 1-3 with any real spend: flag for landing-page/ad-relevance review. 4-6:
   watch list. 7-10: healthy. NULL (not enough impressions yet): acceptable if genuinely new.
   ("Real spend" here means the same non-trivial-spend floor defined in Step 5a below — a keyword
   with a handful of clicks and near-zero cost is not yet a meaningful QS signal to act on.)
2. **High-spend, zero-conversion keywords** — cost above roughly 3x the account's average CPA with
   zero conversions is bleeding budget (ported incident-derived mechanism, 2026-07 — UNVERIFIED as
   an official Google threshold; the multiplier itself is a heuristic, not a platform-defined
   figure); flag for negative-keyword evaluation. **When the account itself has zero conversions in
   the window, "average CPA" is undefined (division by zero) and this check cannot run as written.**
   Fall back to a target CPA if the company's own dossier records one; otherwise use a spend
   multiple of the account's average CPC instead (e.g. flag a keyword at or above roughly 10x
   account-average CPC with zero conversions — a heuristic substitute, UNVERIFIED, pending
   derivation) until real conversion data exists to compute an actual CPA.
3. **Rarely-served keywords** — "rarely-served" means fewer than 1 impression per day on average
   over the trailing 30 days for an ENABLED keyword with no serving-limiting cause (not
   budget-capped, not disapproved) — functionally inactive; flag (ported incident-derived mechanism,
   2026-07 — UNVERIFIED as an official Google threshold; a heuristic starting point).
4. **Match-type distribution** — an account should not run 100% broad match on Manual CPC. Flag if
   over 60% of spend sits on broad match paired with manual bidding (see
   [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #4).
5. **Negative-keyword coverage** — confirm negative lists exist at both account level (a shared
   negative list applied across campaigns) and campaign level (campaign-specific exclusions);
   absence of either is a real gap, not just a Step 7 scoring input — see the scoring row below for
   the Fail/Warning/Pass bands.

Pass threshold: no keyword spending above ~3x account-average CPA (ported incident-derived
mechanism, 2026-07 — UNVERIFIED as an official Google threshold) with zero conversions and no
documented reason to keep it, AND negative-keyword coverage exists at both levels.

## Step 4 — Conversion tracking verification (the canonical 4-signal test)

Mandatory. Skipping it means every downstream optimization decision rests on possibly-broken
data. This step is the SAME test as
[`measurement-and-attribution.md`](measurement-and-attribution.md)'s "4-signal test: setup is not
the same as tested" — that file is the canonical definition; this step applies it to the audit and
adds audit-specific scoping on top, never a different or weaker substitute test:

- **Judge conversion health ONLY on counted, primary, enabled actions.** A non-counted or deprecated
  action going silent is NOT a tracking break. (Audit-specific scoping, on top of the canonical
  test below.)
- **The canonical 4-signal test** (see `measurement-and-attribution.md` for the full wording): (1) a
  live physical trigger — a real form submit, call, or booking — actually fires the tag; (2) the
  analytics platform's real-time/debug view shows the event landing; (3) the ad platform's
  conversion action reads a real status, not a draft/unpublished state or "no recent conversions";
  (4) the ad platform's own conversion column shows a non-zero, recently-updated value. All four,
  together, are what "tracking is verified" means — any one missing means UNVERIFIED, not
  "probably fine."
- **The 48-hour physical-verification rule applies here too:** if no counted, primary conversion
  has fired in the last 48 hours, the conversion counter is untrustworthy regardless of what the
  4 signals otherwise show — see `measurement-and-attribution.md`'s 48-hour rule.
- **Audit-specific addition — cross-platform variance:** cross-check the ad platform's count
  against an independent analytics source for the same window. The variance bands and what each
  means are defined once, canonically, in
  [`measurement-and-attribution.md`](measurement-and-attribution.md)'s "Cross-platform
  reconciliation" table — never restated or re-derived here; that file's own citation-style
  discipline tags all three percentages `UNVERIFIED — seeded, needs derivation`. Do not optimize
  until a variance flagged by that table as needing investigation or worse is resolved.

Pass threshold: the canonical 4-signal test passes AND the 48-hour rule is satisfied, for the
counted/primary actions specifically. A non-counted action failing does NOT trigger a remediation
flag.

## Step 5 — Impression share and budget check

**Step 5a — the "meaningful spend floor" used throughout this rubric (Step 3's Quality Score check
and the Spend-present scoring row both point here):** a meaningful floor at the **keyword/campaign
level** requires BOTH spend at or above roughly 3x that keyword/campaign's own current average
cost-per-click over the trailing 30 days AND 30+ clicks (ported incident-derived mechanism,
2026-07 — UNVERIFIED as an official Google threshold; a heuristic starting point, not a
platform-defined figure, pending a vertical-specific (per the company's profile) derivation).
**Requiring both, not "whichever is reached first," is deliberate:** 3x average CPC is typically
reached in only ~3 clicks, so an "either" reading would make the floor trivially easy to clear and
would license acting on a keyword with only a handful of clicks — exactly what Step 3's own QS
check (below) says is NOT yet a meaningful signal. Below this floor, a metric (QS, CPA, conversion
rate) is directionally informative at best and should not alone justify an optimization decision.

**Account-level floor (for the Spend-present scoring row, Step 7):** the keyword/campaign-level
floor above does not scale directly to the whole account — 3x the *account's* average CPC is a
far smaller bar than 3x a single keyword's CPC, and would make the Spend-present row's Warning
band nearly unreachable. At account level, "meaningful spend" for the Spend-present row means total
30-day spend at or above roughly 3x the account's average CPC **times the number of enabled
campaigns** (a rough per-campaign scaling of the same underlying idea), OR total spend at or above
roughly $500 in the trailing 30 days, whichever is higher (ported incident-derived mechanism,
2026-07 — UNVERIFIED as an official Google threshold; a heuristic starting point pending
vertical-specific derivation, not a platform-defined figure). This account-level floor is a
distinct number from the per-keyword/campaign floor above — do not apply the per-keyword formula
directly to account-level spend.

Pull impression share, budget-lost IS, rank-lost IS, and absolute-top IS per campaign. Minimum
threshold for "ready to optimize": at least one campaign above 5% impression share (ported
incident-derived mechanism, 2026-07 — UNVERIFIED as an official Google threshold; a heuristic
starting point, not a platform-defined figure). An account sitting uniformly below 5% IS is either
brand-new, severely budget-constrained, or has a structural problem (bad geo targeting,
disapprovals) that needs fixing before optimization is meaningful.

## Step 6 — Zero-impression root-cause tree

For any campaign/ad group flagged in Steps 1-2 with zero impressions, walk this tree in order:
billing active? → campaign status ENABLED? → ads approved? → enabled keywords exist? → is the bid
above the first-page estimate? → is geo/schedule/audience targeting too narrow? Each branch has a
distinct fix; don't guess past a step you haven't checked.

## Step 7 — Scoring rubric (16 points)

Score each dimension 0-2 (Fail / Warning / Pass). Scope reminder: every row scores ONLY ENABLED
campaigns/ad groups.

| Dimension | 0 (Fail) | 1 (Warning) | 2 (Pass) |
|---|---|---|---|
| Spend present | No spend in 30d | Spend below the meaningful floor (Step 5a) | Spend at or above the Step 5a floor, sustained across the 30-day window |
| Campaign structure | Orphaned campaigns OR any ENABLED campaign with 0 ad groups | Minor issues, no zero-ad-group campaigns | All ENABLED campaigns healthy with ≥1 ad group |
| Ad group health | Any ENABLED ad group with 0 enabled ads | Over 50% of ad groups paused | All ENABLED ad groups have ≥1 enabled ad |
| Keyword Quality Score | Any keyword scored 1-3 with real spend | QS 4-6 dominant | Most keywords QS 7+ |
| Keyword bloat (rarely-served / zero-impression) | Over 30% of keywords inactive | 10-30% inactive | Under 10% inactive |
| Conversion tracking | 0 primary/counted conversions in 30d | A verification signal fails on primary actions, or the 48-hour rule fails | The canonical 4-signal test passes AND the 48-hour rule is satisfied, for primary/counted actions |
| Impression share | All campaigns under 5% IS | Any campaign under 10% IS, but not all campaigns under 5% | All active campaigns at or above 10% IS |
| Negatives exist | No negative keywords at all | Only one level present (account-level only, OR campaign-level only) | Campaign-level AND account-level |

*(Ported incident-derived mechanism, 2026-07, for every numeric cutoff in this table —
UNVERIFIED as official Google-stated thresholds. Treat the specific percentages/counts as
heuristic starting points pending a vertical-specific (per the company's profile) derivation; the dimensions and Fail/
Warning/Pass structure are the load-bearing part.)*

**Score interpretation (ported incident-derived mechanism, 2026-07 — UNVERIFIED band boundaries;
the 0/16-16/16 range and relative ordering are the load-bearing part, the exact 14/9 cut points are
a heuristic). These bands assume the full 16-point denominator — when any dimension was marked N/A,
scale both the score and these cut points per the "Scope note" section's normalization rule above
before applying them:**
- 14-16: Ready to optimize. Proceed.
- 9-13: Proceed with caution. Document every warning before optimizing.
- 0-8: Needs remediation first. Do not run bid or budget changes — fix the structural issues.

## Outputs required before proceeding to any optimization work

1. The audit score (N/16, or N/reduced-denominator per the N/A normalization rule above when any
   dimension was marked N/A — state the denominator explicitly, never a bare N assuming 16) with
   per-dimension results.
2. A list of flagged items with a root-cause classification for each.
3. A plain recommendation: "ready to optimize" / "proceed with caution — [warnings]" /
   "needs remediation first — [blockers]".
4. A persisted audit record (dated) so the next audit can measure delta, not just re-derive from
   scratch — home: the company's own `marketing_kb_state/` (per-company, not this shared runtime
   corpus), so the record lives where the company's own dossiers already do.

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

Within that scope, when the account owner is a small contractor or similar first-time Ads advertiser, apply this
conditional vertical doctrine — read the specific persona from that company's own dossier rather
than assuming it here:

- **A first-time-Ads small contractor's account is far more likely to fail Step 1 and Step 4 than
  a mature, marketing-sophisticated account** — commonly an unverified conversion action, a
  homepage-only landing setup, and a campaign structure inherited unedited from a vendor's
  template. Expect to spend most of the first audit in remediation, not optimization, and say so
  plainly rather than rushing to a "ready to optimize" verdict the account hasn't earned.
- **The zero-impression root-cause tree is especially useful for an owner who says "the ads aren't
  showing at all."** Walk it in plain language — billing, then status, then approval, then
  keywords, then bid, then targeting — as a diagnostic conversation, not just an internal
  checklist.
- **Present the 16-point score as a report card, not a jargon dump.** "8 of 16 — needs fixing
  before we spend more" communicates faster than the raw dimension table to a buyer who wants a
  yes/no on whether the money is being managed responsibly.
