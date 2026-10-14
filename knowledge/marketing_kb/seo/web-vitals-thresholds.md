# Core Web Vitals Thresholds

The three Core Web Vitals, their exact numeric thresholds, the measurement methodology, and the
2026 tooling change (PSI dropping CrUX data) that affects how an agent should actually pull this
data going forward.

---

## 1. The three metrics and exact thresholds

| Metric | What it measures | Good | Needs improvement | Poor |
|---|---|---|---|---|
| **LCP** (Largest Contentful Paint) | Loading performance — time until the largest visible element renders | ≤ 2.5s | 2.5s–4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | Responsiveness — latency of the slowest user interaction | ≤ 200ms | 200ms–500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | Visual stability — how much visible content shifts unexpectedly | ≤ 0.1 | 0.1–0.25 | > 0.25 |

**Sources (official, web.dev / Chrome for Developers, retrieved 2026-09-05):**
- LCP: https://web.dev/articles/lcp — "Good: 2.5 seconds or less... Needs Improvement: between 2.5
  and 4.0 seconds... Poor: greater than 4.0 seconds."
- INP: https://web.dev/articles/inp — "An INP below or at 200 milliseconds means a page has good
  responsiveness... An INP above 500 milliseconds means a page has poor responsiveness."
- CLS: https://web.dev/articles/cls — "Good: 0.1 or less... Needs Improvement: between 0.1 and
  0.25... Poor: greater than 0.25."

These same numbers are also restated in the source doctrine this corpus was built from (internal
doctrine, retrieved 2026-09-05) — an exact match, expected since both cite the same Google source,
so not independent confirmation.

### Pass / reject examples

- **Pass:** A page measuring LCP = 1.8s, INP = 90ms, CLS = 0.04 at p75 → all three "Good," page
  passes the overall Core Web Vitals assessment.
- **Borderline reject:** LCP = 2.6s (just over the Good line), INP = 150ms (Good), CLS = 0.08
  (Good) → the page is "Needs improvement" overall because Google requires **all three** metrics to
  pass at p75 for an overall "Good" verdict — one metric in the yellow zone is enough to fail the
  page-level assessment even if the other two are comfortably green.
- **Reject:** LCP = 5.1s → "Poor." This is squarely in territory that measurably hurts both
  rankings and conversion (a slow-loading page loses visitors before they see anything).

## 2. Measurement methodology — p75, not average

**"A good threshold to measure is the 75th percentile of page loads, segmented across mobile and
desktop devices."** (official, web.dev, retrieved 2026-09-05, same LCP source as above; identical
methodology stated for INP and CLS). This means:

- Google does not evaluate your *average* or *best* load time. It looks at the value that 75% of
  real visits meet or beat — so a page that's fast most of the time but has a long tail of slow
  loads (a bad CDN edge, a specific device class, a specific geography) can still fail even though
  "most people" had a fine experience.
- **Mobile and desktop are scored separately.** A page can pass on desktop and fail on mobile (very
  common for image-heavy remodeling/before-after content) — never report a single blended number as
  if it represents both.
- This is **field data** (real Chrome users), distinct from **lab data** (a single simulated
  Lighthouse run). Lab data is useful for diagnosis and pre-deploy testing; only field data (CrUX)
  determines the actual Core Web Vitals ranking signal Google uses.

## 3. The 2026 tooling change: PSI is dropping CrUX field data — use the CrUX API instead

**"Google plans to discontinue including real-world data from the Chrome User Experience Report in
the PageSpeed Insights API. Google recommends using the CrUX API or the CrUX History API instead."**
(official, Chrome for Developers blog "CrUX Dashboard deprecation" + PageSpeed Insights API release
notes, retrieved 2026-09-05: https://developer.chrome.com/blog/crux-dashboard-deprecation,
https://developers.google.com/speed/docs/insights/v5/get-started). An exact cutover date was not
independently confirmed in this research pass — **UNVERIFIED, needs derivation**: re-check the PSI
release notes (https://developers.google.com/speed/docs/insights/release_notes) at time of
implementation for the actual sunset date, rather than assuming it has already happened.

**What this means operationally:**
- A PSI report pulled today may already be missing (or may soon be missing) the "field data"
  section that shows real-user CWV — if a PSI call returns lab data only (Lighthouse simulation)
  with no field-data block, that is the expected post-deprecation shape, not a broken call.
- **Going forward, pull real-user Core Web Vitals from the CrUX API directly**
  (https://developer.chrome.com/docs/crux/api) rather than relying on PSI's field-data section.
  The CrUX API "returns faster performance and identical Core Web Vitals data" to what PSI used to
  embed (official, same sources, retrieved 2026-09-05).
- **CrUX has a traffic floor.** The CrUX dataset only reports on origins/URLs with enough real
  Chrome traffic to be statistically meaningful and privacy-safe. A low-traffic page (a brand-new
  landing page, a niche `/lp/*` variant) may simply have **no CrUX data at all** — this is not a
  failure to fix, it's an expected "not enough data" state. Don't report "no CrUX data" as "the page
  has bad Web Vitals" — it means the opposite: nothing can be concluded yet. Fall back to lab data
  (Lighthouse/PSI's lab section) for pre-launch pages that don't yet have real-user traffic.
- **General rule for any audit tooling that calls PSI:** any audit that calls PSI must handle a
  response with no field-data block — treat its absence as the expected post-deprecation shape (see
  above), never as a broken call or as "the page has bad Web Vitals." If a company's own
  website-audit tooling folds a PSI call into its audit, verify directly whether that tool's
  implementation already handles the missing-field-data case, or still assumes PSI always returns
  field data (a company-implementation question — check the company's own pack/dossier for the
  actual state of its own tooling).

## 4. Prioritization discipline

(internal doctrine, retrieved 2026-09-05)

- Fix "Poor" URLs before "Needs improvement" ones.
- Within a tier, sort by impressions/traffic — fix the highest-traffic page first, not the easiest
  one.
- **Validate a fix before declaring it done.** A code change intended to improve LCP/INP/CLS should
  be re-measured (lab data immediately, field data once enough real traffic has passed through it)
  before being reported as resolved — this mirrors the runtime's own falsifiability discipline
  (never report a fix as verified without re-measuring after the change).
- Poor CWV on a page that doubles as a paid landing page compounds the cost: it lowers Google Ads
  Quality Score, which raises CPC on top of the organic/UX harm (internal doctrine, retrieved
  2026-09-05).

---

## Contractor bend

Do not present raw LCP/INP/CLS numbers to the home-services/contracting GC buyer (see
`shared/contractor-buyer-psychology.md`) — "your CLS is 0.18" means nothing
to them and will read as jargon padding an invoice. Translate to outcomes they already understand
from their own trade: "your site takes almost 5 seconds to show a picture when someone taps a link
from a text message — most people give up and call someone else in the time it takes to load. We
fixed that; it's now under 2 seconds." Since this buyer is phone-first and often reviewing sites
from a truck on cellular data, mobile field data (not desktop) is the number that actually matters
to their business, and that's worth saying explicitly — "we test on a phone on a job-site signal,
not a fast office wifi connection," because that framing pre-empts the "well it looked fine when I
checked it" objection this buyer is likely to raise after glancing at the site from their own
office desktop.
