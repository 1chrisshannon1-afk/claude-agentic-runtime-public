# Launch Director Primer

Runtime-level oversight primer. Product-agnostic: contains no app-specific paths, account
names, or counts belonging to any one repository. Distilled from external research on
prioritization frameworks, launch-readiness practice, and status-reporting shape; every claim
below carries its source. Do not treat anything here as doctrine beyond what its citation
supports — extend only by adding a new sourced finding, never by inventing a rule.

## 1. Prioritization frameworks — and their named failure modes

**RICE = (Reach × Impact × Confidence) / Effort.** Reach = number of people/events in a time
window; Impact scored on a discrete scale (3 = massive, 2 = high, 1 = medium, 0.5 = low,
0.25 = minimal); Confidence as a percentage; Effort in person-time. Originated by Sean McBride
at Intercom, published January 2018 [date unverified — also widely cited as 2016; confirm before
citing outward]. The source article's own caveat: "RICE scores shouldn't be
used as a hard and fast rule" — dependencies and sales/contract table-stakes items can
legitimately override the score.
(Source: "RICE: Simple prioritization for product managers" — Intercom Blog,
https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/)

**ICE = Impact × Confidence × Ease.** No Reach term, no Effort divisor — faster to compute,
suited to early-stage quick triage, but structurally biased toward loud, small, easy-to-serve
segments over broad-but-quiet value, precisely because it never weighs how many people a change
touches.
(Sources: plane.so "RICE vs ICE vs Kano," kaizenko.com "Scoring Frameworks: ICE, RICE, and
Weighted Scoring")

**RICE/ICE failure modes (apply to both, distinct from each other's structural bias above):**
1. Subjectivity — a team with no historical data cannot score Impact/Confidence honestly; the
   inputs become opinion dressed as arithmetic.
2. "Theater without evidence" — precise-looking output built on conviction, not data.
3. Neither captures non-scorable strategic value (a design-partner-retention commitment, a
   company-defining bet) — a low RICE/ICE score is not evidence the item is wrong to build.
4. Most real prioritization failure is choosing the wrong tool for the job, not "no framework at
   all."
(Sources: evelance.io "RICE vs ICE," plane.so "RICE vs ICE vs Kano")

**WSJF = Cost of Delay ÷ Job Size.** Cost of Delay (CoD) = Business Value + Time Criticality +
Risk Reduction/Opportunity Enablement, each component scored on a modified-Fibonacci scale
(1, 2, 3, 5, 8, 13, 20) via relative comparison, not absolute units. Rooted in Don Reinertsen's
queueing-theory Cost-of-Delay work; adopted as SAFe 6.0's primary economic-prioritization tool
for Lean Portfolio Management (Features/Capabilities/Epics). Economic logic that RICE/ICE do not
express: a 2-week moderate-value job can legitimately outrank a 6-month high-value job, because
delayed value decays over time — WSJF prices that decay directly into the ranking.
(Sources: "WSJF" — Scaled Agile Framework, https://framework.scaledagile.com/wsjf/;
ProductPlan glossary "Weighted Shortest Job First")

**When to use which:** RICE/WSJF for anything with real dependency or delay-cost structure and
where the team can commit to honest inputs; ICE for fast early-stage triage where the overhead
of a Reach estimate isn't worth it; neither replaces judgment on non-scorable strategic bets.

## 2. Riskiest-Assumption Testing (RAT)

Distinct from an MVP. An MVP previews the product's strengths and is built to accumulate early
adopters on the assumption most of the underlying idea is sound. A RAT deliberately targets the
single weakest, most fail-prone assumption in the plan first, with the cheapest test that can
falsify it — the point is not to preview success, it is to find the reason the plan fails as
early and cheaply as possible.
(Source: "Riskiest Assumption Test" — ModelThinkers, https://modelthinkers.com/mental-model/riskiest-assumption-test)

This nests inside the broader Lean Startup Build-Measure-Learn loop: convert assumptions into
falsifiable, pre-committed-threshold hypotheses (e.g. "≥30% of users complete X within 48h")
*before* building, grouped by theme — customer/problem, solution desirability, feasibility,
viability, growth — then build the smallest thing that tests the hypothesis, measure against the
pre-committed threshold, and only then decide what to build next.
(Source: "Lean Startup / Build-Measure-Learn Loop" — Umbrex,
https://umbrex.com/resources/frameworks/organization-frameworks/lean-startup-build-measure-learn-loop/)

## 3. Gold-plating vs. scope-creep

Both degrade cost, schedule, and satisfaction, but they are not the same failure and call for
different responses:
- **Gold plating**: the team adds *unrequested* extras; the scope baseline never changed; the
  work goes past the point of diminishing returns; cost is added with no client-desired value
  behind it. The fix is internal discipline — stop building past the requested bar.
- **Scope creep**: the client/stakeholder *requests* additions that expand the baseline without a
  matching adjustment to schedule, budget, or risk. The fix is a change-control conversation, not
  a unilateral no.
(Sources: PMI usage as summarized by Wrike "Scope Creep vs. Gold Plating,"
https://www.wrike.com/professional-services-guide/faq/scope-creep-vs-gold-plating/;
Project Management Academy, "Gold Plating vs. Scope Creep")

A launch-direction review should be able to name which of the two is happening for any item that
grew past its original brief — "nobody asked for this" (gold plating, cut it) is a different
verdict from "the stakeholder asked for more and we haven't repriced the plan" (scope creep,
renegotiate it).

## 4. Launch-readiness review practice

A standard go/no-go review runs roughly one week pre-launch, ~30 minutes, with every functional
lead present, and ends in an explicit, documented decision: proceed, delay, or scope-down —
communicated afterward, not left implicit. Checklist scope commonly includes: QA sign-off, a
phased rollout plan, written success/failure metrics defined in advance, a rollback plan,
customer-facing team training, legal/policy sign-off, a monitoring plan, and a dated post-launch
review already on the calendar before launch happens.
(Sources: "Launch Readiness Checklist for Startups" — Wellows,
https://wellows.com/blog/launch-readiness-checklist-for-startups/;
"Product Launch Readiness Checklist" — OpenView Partners)

## 5. The weekly state-of-the-product report — 7 recurring sections

Assembled from multiple templated-report sources (thin/no single canonical source — treat as a
converging pattern, not one doctrine). The sections that recur across sources:
1. **Accomplishments/progress** — tied to metrics, not activity for its own sake.
2. **Metrics & trend data** — with a recommendation attached, not bare numbers.
3. **Challenges** — stated plainly, with a stated fix plan; do not bury bad news.
4. **Next 1–2 weeks' priorities.**
5. **Customer/market insight** surfaced that period.
6. **Explicit blockers/asks** — each with a by-when.
7. **Team capacity/morale line.**
(Sources: dooyongro.com "Product Manager Weekly Report Template" [unverified — confirm at the
source before citing outward], visme.co "Weekly Report," monday.com "Report Templates for
Product Managers")

---

## How this agent applies it

- **Rank against ONE goal at a time** — either the single goal the repo dossier states as
  current (e.g. its own stated "first thing that matters" objective) or, absent a dossier
  statement, the most conservative reading of "get to the next real external validation point."
  Never blend multiple goals into one ranking; if the dossier names no single goal, say so
  explicitly rather than picking one.
- **Always output a ranked queue in a machine-readable block** (e.g. a fenced JSON or YAML list:
  `[{"item": ..., "score_method": "RICE|ICE|WSJF", "score": ..., "why_this_rank": ...}, ...]`) —
  never prose-only ranking. The scoring method used must be named per item, and any Reach/Impact/
  Confidence/Effort or CoD/Job-Size inputs must be visible, not collapsed into a single opaque
  number, so a human can contest an input rather than just the output.
- **Name what should NOT be built** — every report includes an explicit "not now" list with the
  one-line reason each item is excluded (gold-plating past the goal, scope-creep without a
  repriced plan, fails a riskiest-assumption test that hasn't been run yet, or simply outranked).
  A ranked queue with no stated exclusions is incomplete — silence on an obviously-adjacent item
  reads as an oversight, not a decision.
