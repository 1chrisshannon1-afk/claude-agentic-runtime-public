# Bid-Strategy Ladder

## The rule: never skip a rung

Select the bid strategy from the account's ACTUAL account-wide monthly conversion volume — never
from ambition, never from what a prior vendor was running, never from what a benchmark article
says a "mature" account should run. Skipping a rung (Target CPA on a 10-conversion/month account,
for instance) starves the algorithm of the signal it needs and burns budget with no learning to
show for it.

| Conversion volume (account-wide, trailing 30 days) | Required bid strategy |
|---|---|
| Under 15 conv/month | Manual CPC — Smart Bidding wastes limited budget with no signal to learn from |
| 15-29 conv/month | Maximize Clicks (an optional CPC cap is fine) |
| 30-49 conv/month | Maximize Conversions, with no target set yet |
| 50+ conv/month, stable | Target CPA (set the initial target at or above the observed average CPA) |
| 50+ conv/month, with reliable value data | Target ROAS |

(Structure: ported incident-derived mechanism, 2026-07 — history only, never a live source. Every
conversion-volume cutoff in this table is `UNVERIFIED — seeded, needs derivation`: a heuristic
starting point, not a Google-stated threshold.)

**Never switch directly from Manual CPC to Target CPA.** Pass through Maximize Conversions first —
jumping straight to a target gives the algorithm no historical anchor and it will overspend or
underdeliver trying to find one. (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as
unnamed "third-party synthesis" with no publisher or URL.)

**Enhanced CPC (ECPC) is deprecated:** "Effective the week of March 31, 2025 Enhanced CPC (ECPC) is
no longer available for Search and Display campaigns. Campaigns that were not proactively migrated
to another bid strategy prior to deprecation are now effectively using Manual CPC" (official,
Google Ads Help "About Enhanced CPC (ECPC)," `support.google.com/google-ads/answer/2464964`,
retrieved 2026-09-27). An account still showing ECPC is effectively on Manual CPC — flag it for an
explicit bid-strategy decision rather than assuming Manual CPC was a deliberate choice.

## Setting an initial Target CPA once eligible

1. Read the average CPA from the trailing Maximize Conversions phase (last 30 days).
2. Set the initial Target CPA AT that average, or 10-20% above it, to give the algorithm room —
   never below the current average; setting it lower makes Smart Bidding cut volume aggressively
   trying to hit a target it can't reach.
3. After 2-3 weeks of stable data, tighten the target by 10-15% at a time — never more, and never
   more often than the learning-window cadence allows (see
   [`learning-period-gates.md`](learning-period-gates.md)).

For a genuinely new account with no conversion history at all, back the initial target into the
account's own unit economics rather than a vertical benchmark alone — see the "setting an initial
target CPA with zero history" section in [`budget-as-formula.md`](budget-as-formula.md).

## Portfolio bid strategies

A portfolio strategy applies one Smart Bidding strategy across multiple campaigns, sharing
conversion data between them. Use it when campaigns share the same conversion goal AND either
already individually clear 30+ conv/month, or their COMBINED volume clears the threshold while no
single campaign does alone. Do not portfolio campaigns with different conversion goals or bid
strategies just to pool volume — that corrupts the signal each campaign needs.

## What resets learning when you move up the ladder

Every rung change (any bid-strategy change) is a FULL learning reset — this is the single biggest
lever governed by the age/volume gates in
[`learning-period-gates.md`](learning-period-gates.md). Never change bid strategy AND budget AND
targeting on the same campaign in the same window; change one lever, let it settle, then move to
the next.

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A remodeling GC's monthly conversion volume is almost always going to sit in the bottom two
  rungs of this ladder** — a small GC generating a few dozen leads a month across all channels is
  common, and Google Ads alone is typically a fraction of that (read the company's own lead volume
  from its dossier; this is a directional characterization, not a benchmark). Do not let benchmark articles
  written for larger accounts push a GC toward Target CPA before the account has genuinely earned
  it; staying on Manual CPC or Maximize Clicks for months is often the CORRECT answer here, not a
  failure to progress.
- **"Conversion" for a GC usually means a phone call or a form fill requesting an estimate, not a
  purchase.** Confirm the counted conversion action actually represents a real lead (not a page
  view or a micro-engagement) before reading the account's position on this ladder — an inflated
  conversion count can make the account look ready for a rung it hasn't actually earned. See
  [`measurement-and-attribution.md`](measurement-and-attribution.md).
- **A GC will ask "why can't we just tell Google to get us the cheapest leads" (i.e., jump straight
  to Target CPA).** Explain the ladder in plain terms: Google needs enough real examples of what a
  good lead looks like before it can go find more of them cheaply — skip that step and it's
  guessing, not learning.
