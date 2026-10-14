# Metric Registry Doctrine

The rules that keep a metric meaning the same thing every time it's reported — a registered id that
is never redefined once other reports depend on it, and a missing value that is reported as missing,
never silently coerced to zero.

---

## 1. Why a metric registry exists

**[KB-MEAS-038] (internal doctrine):** the failure this doctrine exists to prevent is not a wrong number — it's
a number that used to mean one thing and now means another, with nothing in the report itself
flagging the change. A "cost per lead" metric computed one way in January and a different way (a
different lead-qualification filter, a different date-range convention, a different attribution
window) in March produces two numbers that look comparable on a trend chart and are not — the chart
itself becomes a lie even though both individual numbers were computed correctly at the time. This
mirrors the same runtime discipline on drift-prone identifiers that governs this agent runtime more
broadly (a name/id that gets silently redefined is worse than one that never existed) applied to a
marketing metric instead of a code identifier — see the runtime's own operating contract for the
general form of this principle.

## 2. A metric's id is immutable once anything depends on it

**[KB-MEAS-039] (internal doctrine)** Every registered metric (`cost_per_booked_job`, `qualified_lead_count`,
`estimate_close_rate`, etc.) is defined **once**, with an explicit, written formula naming its exact
inputs, filters, date-range convention, and attribution window. **Once any report, dashboard, or
downstream decision has referenced that id, its definition is frozen** — a genuine methodology
improvement (a better lead-qualification filter, a corrected attribution window) creates a **new**
id (`qualified_lead_count_v2`) rather than silently redefining the old one underneath existing
consumers. The old id is marked deprecated (never deleted while anything still references historical
values under it) and the registry records the exact date and reason for the split, so a trend chart
spanning the split date can show the discontinuity explicitly rather than hiding it.

**Reject example:** redefining `cost_per_lead` from "total spend / all form submits" to "total spend
/ qualified leads only" in place, so every historical month's `cost_per_lead` value silently means
something different depending on which side of the change it falls on, with nothing in the
dashboard flagging the boundary. **Pass example:** the original `cost_per_lead` id keeps its
original definition and historical values; a new `cost_per_qualified_lead` id is registered with its
own formula, and any report wanting the improved metric switches to the new id explicitly, with a
visible note on any chart spanning both ids' active periods.

## 3. A missing value is `missing`, never `0`

**[KB-MEAS-040] (internal doctrine)** When a metric's underlying data source has no data for a period — a new campaign
with no spend yet, a conversion action not yet configured, an API call that failed rather than
returning an empty result — the correct rendered value is an explicit `missing` (or a dash, or a
stated "no data" state), **never** `0`. This distinction is not cosmetic: `0` is a real, meaningful
value (zero conversions happened) that is indistinguishable, once rendered, from "we don't know" —
and averaging, summing, or trend-charting a column that silently substitutes `0` for "no data
available" produces a systematically wrong result that looks confidently precise. This is the same
principle the runtime GTM department plan states for its performance-analytics rollup ("missing
metric renders `missing`, never 0; association rows under min-sample suppressed" — the runtime GTM
department plan §0 P3) — restated here as the metric-authoring
rule that rollup depends on, not merely the rollup's own display rule.

**Reject example:** a weekly report showing "Meta ROAS: 0.0x" for a week where the Meta conversion
API integration was actually broken and returned no data — a reader has no way to distinguish this
from a genuinely catastrophic ROAS collapse. **Pass example:** the same cell renders "no data — API
error, see incident log" and the report's own summary line calls out that Meta's numbers for that
week are not usable, rather than folding a fabricated zero into any blended total.

**[KB-MEAS-041] (internal doctrine)** This rule composes with the performance-analytics rollup's aggregation logic (runtime GTM department plan §0 P3, internal doctrine): a
weighted average, sum, or rate computed across a set of periods/segments must **exclude** any period
or segment currently rendering `missing` from both the numerator and the denominator — never
substitute zero into the calculation just because a table needs a number to display. A rollup that
cannot compute a real value because too much of its input is missing renders `missing` itself, with
a note naming which inputs were unavailable, rather than a confidently-wrong partial sum.

## 4. Minimum sample size before a metric is reportable

**[KB-MEAS-042] (internal doctrine)** A rate-based metric (a conversion rate, a close rate, a CPA) computed from a very
small number of underlying events is not wrong, but it is **not yet meaningful** — a "50% close
rate" from 2 leads and a "50% close rate" from 200 leads are not the same claim, and reporting them
identically erases exactly the information a reader needs to judge confidence. The runtime GTM
department plan names the same discipline for association rows ("association rows under min-sample
suppressed," §0 P3); the registry generalizes it to every
rate-based metric: **each registered rate metric states its own minimum-sample threshold below which
it renders as `insufficient data (n=<count>)` rather than a computed percentage.** See
[`reporting-and-dashboards.md`](reporting-and-dashboards.md) §2 for how this interacts with the
association-vs-causation discipline at report-authoring time — the registry sets the threshold once,
per metric; the report-authoring rule is what enforces reading it correctly.

## 5. Every registered metric names its owner and its source system

**[KB-MEAS-043] (internal doctrine)** A metric's registry entry names: its formula (§2), its minimum sample size (§4),
which system(s) its raw inputs come from, and which department seat is responsible for its
correctness (per the roster's KB ownership map — the `measurement-architect` seat is the registry's
own owner per the runtime GTM department plan §4). A metric
whose source system changes (a CRM migration, a new call-tracking vendor) is a registry-update event
with the same discipline as §2's definition-freeze — the id doesn't change if the *meaning* is
preserved, but the registry records the source-system change and the date, so a discontinuity in the
raw data pipeline is distinguishable from a real change in business performance.

---

## Contractor bend

- A GC-facing report that quietly redefines "cost per lead" between two monthly reports, with no
  visible flag, will be read by the GC as "the numbers don't add up" the first time they notice —
  and because this buyer already distrusts confident-sounding software/agency claims
  (`contractor-buyer-psychology.md`), a caught inconsistency here costs disproportionately more trust
  than the same mistake would with a more analytically sophisticated buyer who might charitably
  assume a methodology change.
- The `missing`-not-`0` rule matters more, not less, for this buyer specifically: a GC reading "0
  leads from Google this week" when the real state is "the tracking broke" will very reasonably
  conclude the campaign stopped working and ask to cut the budget — the wrong decision, driven
  entirely by a measurement artifact this rule exists to prevent from ever reaching them.
