# Bid Adjustment Framework

Decision trees and numeric thresholds for the 5 bid-adjustment dimensions (ported incident-derived
mechanism, 2026-07 — history only, never a live source). The decision-tree STRUCTURE is the
load-bearing part; **every numeric threshold in this file (the 20% variance bar, 30 clicks / 5
conversions, 14-day cadence, rollback percentages, modifier ranges) is `UNVERIFIED — seeded, needs
derivation`** — a heuristic starting point, not a Google-stated figure; cite it as such in any
proposal. Do not apply a modifier without meeting the minimum data requirement for that
dimension.

## Core principle: variance must be meaningful AND statistically grounded

"Meaningful" is defined by two independent tests, both required:

- **Relative-CPA threshold:** the segment's CPA differs from the account (or campaign, for
  location) average CPA by at least 20%. Example: account average CPA $50, device-segment CPA
  $75 → +50% delta, threshold met. Account average $50, segment $54 → +8% delta, do NOT adjust.
- **Minimum data requirement:** at least 30 clicks AND at least 5 conversions in the measurement
  window before any adjustment. Below this, variance is noise, not signal. Exception: a
  zero-conversion segment with at least 50 clicks AND cost at least 2x the account-average CPA
  warrants a downward adjustment (or exclusion) even without conversions — that's not noise, it's
  a real cost signal.
- **ROAS-bidding accounts:** use a ROAS delta of at least 25% from the account average, with the
  same minimum-data floor.

## Anti-thrashing cadence

**Never adjust the same dimension twice within 14 days.** The platform's algorithm needs time to
learn after a modifier change; adjusting weekly generates noise, not signal.

Required wait periods:
- After any bid-modifier change: 14 days minimum before re-evaluating that same dimension.
- After switching bidding strategy (e.g., Manual CPC → Target CPA): 30 days. Do NOT layer manual
  modifiers on top of Smart Bidding during its own learning period.
- After a campaign launches: 30 days before applying any adjustment at all (insufficient data
  before then).

**Learning-period detection:** if the campaign's own optimization signal is unavailable, or it has
shown "limited by budget" for under 7 days, it may still be in the learning phase. If the observed
CPA differs from the bid strategy's own effective target by more than 100%, the algorithm is still
calibrating — hold off on manual modifiers.

## Rollback triggers

Roll back a modifier to 0% (or its previous non-zero value) if ANY of these occur within 14 days
of applying it:
- Conversion volume drops more than 30% week-over-week with no other change to bids or budget
- CPA increases more than 40% from the pre-adjustment baseline
- Impression share drops more than 20 percentage points with no budget-constraint cause
- CTR drops more than 40% week-over-week (may indicate the modifier is suppressing valid traffic)

Wait 14 days before re-testing after any rollback.

## Restricted-targeting caveat — read before Dimensions 2, 4 and 5

**Housing, employment, and consumer-finance ads in the US and Canada** may not target by gender,
age, parental status, marital status, or ZIP code; radius (minimum 1 km), city, and country
targeting stay available, and in Canada the first three characters of a postal code (FSA) are
acceptable (official, Google Advertising Policies Help, "Restricted targeting in Personalized
advertising", `support.google.com/adspolicy/answer/143465`, retrieved 2026-09-27 — that page lists
these as the "Access to opportunities" categories but does not itself define which ads count as
"consumer finance"). A contractor ad that promotes **financing** can fall into that category, so an
age/gender modifier or a ZIP-code exclusion on it is not an optimization choice — it is prohibited
targeting. Before applying any modifier in Dimensions 2, 4 or 5, confirm the campaign carries no
housing/employment/credit offer; when it does, use radius or city geography only and leave
age/gender unmodified.

**For a company whose pack declares `regulated`** (e.g. a health practice), demographics are
supported only "with exceptions" under Google's health policy, and advertiser-curated audiences
are restricted — follow the Regulated-industry gate in
[`competitor-targeting-doctrine.md`](competitor-targeting-doctrine.md) before any demographic or
audience modifier.

## Dimension 1: Device (mobile / desktop / tablet)

Pull 30-day cost/clicks/conversions/conversion-value by device.

```
For each device:
  If clicks < 30 OR conversions < 5: do not adjust; log "insufficient data."
  Compute device_CPA; compute delta = (device_CPA - account_avg_CPA) / account_avg_CPA.

  delta <= -20% (device is cheaper): candidate for a positive modifier, +15% to +30%,
    capped at +50% unless the account is consistently profitable at scale.
  delta >= +20% (device is more expensive): candidate for a negative modifier, -15% to -30%.
    If delta >= +100% AND zero conversions AND clicks >= 50: consider -70% to -90%.
  delta between -20% and +20%: no adjustment; reset to 0% if one was previously set.
```

**Tablets are a special case** — low volume is common. Below 15 tablet clicks in 30 days, don't
adjust; the default behavior (inheriting the desktop bid) is fine.

## Dimension 2: Location

(ZIP-code targeting and exclusion are prohibited on US/Canada housing, employment, and credit ads —
see the Restricted-targeting caveat above; use radius or city there.)

Pull 30-day cost/clicks/conversions per geographic target.

```
For each location: if clicks < 30, do not adjust.
Compute location_CPA vs the CAMPAIGN average (not account average — different campaigns may
target different geos with different cost profiles).

location_CPA / campaign_avg_CPA < 0.70 (30%+ cheaper): +10% to +25% modifier.
location_CPA / campaign_avg_CPA > 1.50 (50%+ more expensive): -15% to -30%.
location_CPA / campaign_avg_CPA > 2.50 with 0 conversions and clicks >= 30: -50% to -70%.
```

**Never exclude a location that contains the primary service area.** Verify geo coverage before
applying anything approaching an exclusion-equivalent modifier.

## Dimension 3: Ad schedule (day of week / hour)

Aggregate clicks/conversions by hour and day-of-week. Minimum data threshold: 15 clicks per time
bucket before adjusting; below that, no adjustment.

```
Compare hourly_CPA to the campaign average:
  >= +50% above campaign average: candidate for -20% to -40%.
  >= +150% above average with 0 conversions and clicks >= 15: candidate for -60%.
  <= -30% below average with clicks >= 20 and conversions >= 3: candidate for +15%.

After-hours exclusion (-100%) is ONLY appropriate when:
  1. Confirmed the business genuinely does not pursue after-hours leads, AND
  2. The conversion type is a phone call, not a form — forms are valid leads 24/7.
```

**Never set -100% on every off-hour block without confirming the conversion type.** A form
submitted at 2am is still a real lead unless the business has explicitly said otherwise.

## Dimension 4: Age

(Not available on US/Canada housing, employment, and credit ads, and limited for a regulated
company — see the Restricted-targeting caveat above.)

Pull 30-day cost/clicks/conversions per age bucket. Minimum threshold: 20 clicks per bucket
(age data is less dense than device data, so a lower threshold is acceptable here).

```
age_CPA > account_avg_CPA * 1.5 AND clicks >= 20: -20% to -35%.
age_CPA < account_avg_CPA * 0.7 AND clicks >= 20, conversions >= 3: +15% to +25%.
```

**Never exclude the "age unknown/undetermined" bucket.** This covers logged-out users and is
often 15-30% of traffic — excluding it means excluding real converters with unknown age.

## Dimension 5: Gender

(Not available on US/Canada housing, employment, and credit ads, and limited for a regulated
company — see the Restricted-targeting caveat above.)

Same level and threshold as age (20 clicks minimum). Signal quality is lower for search than for
display — only adjust if the delta is at least 40% AND clicks are at least 30. Smaller signals are
noise on search. Never exclude the "gender unknown" bucket, for the same reason as age.

## Testing approach before an account-wide rollout

1. Pick the campaign with the most conversions in the trailing 30 days.
2. Apply the modifier on that campaign only.
3. After 14 days, compare CPA and conversion volume against the 14-day period before the change.
4. If results match expectations, roll out to the remaining campaigns.
5. Document the test (dated, before/after numbers) so a future audit can see what was tried.

**Modifier precision:** round every modifier to the nearest 5% increment (e.g., -15%, -20%, not
-17.3%). Granular modifiers add maintenance complexity with no meaningful lift.

## Summary — when NOT to adjust

- The campaign is inside a Smart Bidding learning period (under 30 days old, or a strategy change
  happened recently)
- The segment has fewer than 30 clicks (device/location/schedule) or fewer than 20 clicks
  (age/gender)
- The last adjustment on this same dimension was under 14 days ago
- The account hasn't cleared the audit gate (see [`account-audit-rubric.md`](account-audit-rubric.md))
- Conversion tracking signals are failing (see [`measurement-and-attribution.md`](measurement-and-attribution.md))

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **A small GC's ad account almost never clears the minimum-data thresholds on 3 of the 5
  dimensions (age, gender, schedule) within a normal month.** Low absolute lead volume means a
  correct, honest answer is often "not enough data yet to adjust this dimension" for most of the
  account's early life. Resist the pressure to manufacture a recommendation just to look active.
- **Device is usually the one dimension worth watching early**, because contractor searches skew
  heavily mobile (someone standing in their kitchen looking at the water damage) — a device-CPA
  gap is more likely to clear the 30-click/5-conversion floor faster than the demographic
  dimensions will.
- **Location is high-leverage for a GC with a real, bounded service radius** — a contractor who
  doesn't travel more than 25 miles from their shop should exclude or heavily discount areas
  outside that radius long before waiting on a full statistical read (use a radius or city
  boundary, never ZIP codes, on any campaign promoting financing — see the Restricted-targeting
  caveat above), since serving those areas is
  a business-fit problem, not just a cost-efficiency one. State that distinction plainly:
  geographic exclusion for service-area fit is a different decision than a data-driven bid
  modifier, and doesn't need to wait on the 30-click threshold.
- **A GC will often ask for schedule exclusions based on gut feel ("nobody calls at 2am about a
  bathroom remodel")** — that's usually right directionally, but confirm the conversion type first
  (a form vs. a phone call) before applying a hard -100% exclusion, per the ad-schedule rule above.
