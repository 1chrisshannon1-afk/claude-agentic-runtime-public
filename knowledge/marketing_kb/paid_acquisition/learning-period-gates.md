# Learning-Period Gates

## Why this exists

Google's (and Meta's) machine learning needs time to evaluate every entity it serves. Acting on
immature data is worse than not acting at all. This is one of the most incident-anchored rules in
the entire corpus.

**Incident (ported incident-derived mechanism, 2026-07; history only):** an agent paused 1-2 day old RSA ads for "POOR" ad strength,
fragmenting Google's learning period before any real performance data existed. Ad Strength is a
structural/compositional signal, not a performance signal — it can read POOR on day 1 and improve
to GOOD by day 14 with zero changes made, purely as Google accumulates impressions on the asset
combinations. PENDING means Google hasn't evaluated the entity yet at all — that is never a reason
to act, in either direction.

## Mandatory age verification before ANY modification

Before pausing (never deleting — see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #11), editing, or
replacing any campaign, ad group, ad, keyword, or asset:

1. Find the entity's first-impression date from the platform's own reporting.
2. Calculate its age in days from that date to today.
3. If the entity has zero impressions, determine whether it's genuinely new or completely blocked
   (disapproval, budget exhausted, targeting too narrow) — these require different fixes, and
   "zero impressions" alone doesn't tell you which.
4. Report the age and data volume alongside any recommendation or action.

## Minimum learning periods — hard gates, never modify before these thresholds

| Entity | Minimum age | Minimum data required |
|---|---|---|
| Campaign | 14 days with active spend | 1,000+ impressions |
| Ad Group | 14 days | 500+ impressions |
| RSA Ad | 14 days | 200+ impressions OR Ad Strength actually evaluated (not PENDING) |
| Keyword | 14 days | 100+ impressions, for Quality Score to stabilize |
| Bid strategy | 21 days (≈ Google's "up to 3 weeks"; ported operating threshold) | A full conversion cycle |
| Smart Bidding (Target CPA/ROAS) | 30 days | 30+ conversions in the period |
| Asset (sitelink/callout/snippet) | 7 days | Visible in at least 1 impression report |
| Meta ad set | ~7 days | ~50 optimization events (see meta-ads-doctrine.md) |

(Structure: ported incident-derived mechanism, 2026-07 — history only, never a live source. Google's
own official documentation states the learning
period can run "up to 3 weeks or 1-2 conversion cycles" and depends on conversion volume,
conversion-cycle length, and bid-strategy type — official, [Google Ads Help: Duration of the
learning period](https://support.google.com/google-ads/answer/13020501), retrieved 2026-09-05.
Google's official page does not publish exact day/conversion thresholds for every entity type the
way the table above does — the table's specific numbers are ported operating thresholds layered on
top of Google's own, more general guidance, and are `UNVERIFIED — seeded, needs derivation`; treat
them as the practical operating rule, never as a Google-stated figure.)

## What counts as "modification" (these all require the age gate)

- Pausing an ad, keyword, ad group, or campaign (never deleting — see
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #11; pausing a campaign or ad set is also `$`, primer §4)
- Changing bid strategy or a target CPA/ROAS value
- Changing budget by more than 20%
- Removing or replacing RSA headlines/descriptions
- Changing keyword match types

## What resets learning (track every change against this)

| Change | Resets learning? |
|---|---|
| Budget change greater than 20% in one week | Yes |
| Bid-strategy change (any type) | Yes — full reset |
| Portfolio bid-strategy membership change | Yes |
| Keyword/audience structure change greater than 10% | Yes — real risk |
| Conversion-tracking change | Yes |
| Budget change of 20% or less in one week | No |
| Adding a new ad group (additive) | No |
| Pausing one keyword | No |

## Exceptions to the learning-period age gate (timing only; authority unchanged)

This list says only that no learning-period wait applies. It never changes WHO may do the action:
every item still carries its own approval tier from the primer §4 (governing plan §20.6/§20.13).

- ADDING new keywords, ads, or assets alongside existing ones (purely additive)
- Fixing an objectively broken item (wrong URL, wrong phone number, a policy violation)
- Enabling a previously paused item — **enabling a campaign or ad set remains `$` (signed operator
  approval, primer §4); this row only means no learning-period wait applies.** A paused campaign is
  otherwise read-only to this seat, and re-enabling it is a proposal, never an action
  ([`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #12).
- Budget increases under 20% — **changing any budget or cap remains `$` (signed operator
  approval, primer §4); this row only means no learning-period wait applies.**
- Adding negative keywords
- Fixing a typo in ad copy (note: this requires recreating the specific asset text — do it in
  place via a field-mask update where the platform supports it, to keep the entity's history,
  rather than deleting and recreating the whole ad)

## Quality Score is not real-time

Quality Score lags days behind a landing-page or ad-copy change. After making either change, wait
7-14 days before evaluating its QS impact. Always pull all three QS sub-components (expected CTR,
ad relevance, landing-page experience) — never report just the composite number, since the fix
differs depending on which sub-component is weak.

## The 20% budget rule and the 4-gate ramp check

See [`budget-as-formula.md`](budget-as-formula.md) for the Google ramp cadence and
[`meta-ads-doctrine.md`](meta-ads-doctrine.md) §6 for Meta's. Every increase is a separate `$`
proposal needing its own signed approval (primer §4). Before proposing ANY budget increase, all four
gates below must be met — no exceptions:

1. At least 7 days of data at the CURRENT budget (not 7 days since launch — 7 days of meaningful
   spend at this specific budget level)
2. CPA within ±15% of target (`UNVERIFIED — seeded, needs derivation`)
3. Click volume of at least 30 in the evaluation window (`UNVERIFIED — seeded, needs derivation`)
4. No single-day anomaly (a weather event, a site outage, a tracking blip) is driving the decision

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A remodeling GC's low, seasonal lead volume means MANY entities will sit below the minimum
  data thresholds for a long time** — a small GC might not clear 100 impressions on a given
  keyword for weeks. Do not force a decision before the threshold is met just because the calendar
  says "it's been a month." Report honestly: "this keyword hasn't earned enough data yet" is a
  correct answer, not a stall.
- **Seasonality collides directly with learning-period discipline for this vertical.** A GC's
  spring project-rush ramp and a Smart Bidding learning window can land in direct conflict — a
  budget jump timed to spring demand can look, mechanically, exactly like the >20%-in-a-week
  violation that resets learning. Plan the ramp to start BEFORE the seasonal push, in bounded 20%
  steps, rather than reactively jumping the budget once demand is already spiking.
- **A GC who has been burned before will want to "just turn it up" the moment leads slow down.**
  This is precisely the instinct the learning-period gates exist to check — explain in plain terms
  that a sudden jump resets the very calibration that's been building toward efficient leads, and
  that patience here is what the earlier, cheaper vendor probably never explained.
