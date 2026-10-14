# Reporting and Dashboards

The discipline that keeps a report from implying more than its data supports — the difference
between a correlation and a caused effect, and the minimum evidence bar before either is stated to
the operator, or a client the company reports to.

---

## 1. Association is not causation — say which one you have

**[KB-MEAS-049] (internal doctrine)** A report showing that a metric moved after a change (a new ad creative launched,
a landing page redesigned, a price change) is showing an **association** — the two things happened
in sequence — not a demonstrated **causal** effect, unless the change was tested with a design that
can actually isolate cause (a genuine A/B split test with randomized traffic allocation, a
before/after comparison with a plausible ruled-out set of confounders). **Every report states which
kind of claim it's making, explicitly**, using language that doesn't overclaim:

- Correlational observation: "Conversion rate rose 15% in the two weeks after the new landing page
  launched" — states what happened, not why.
- Causal claim (only when the evidence supports it): "The A/B test (n=..., see §2) showed the new
  landing page caused a statistically distinguishable lift in conversion rate over the control."

**Reject example:** "The new ad creative increased conversions by 20%" stated from a before/after
comparison with no control group, during a period when nothing else was held constant (seasonality,
competitor activity, a simultaneous price change) — this is an association dressed as a causal claim.
**Pass example:** "Conversions were 20% higher in the two weeks after the new creative launched;
note that this coincided with [seasonal factor], so we can't yet attribute the full lift to the
creative change alone — a controlled test is the next step if isolating this matters for the budget
decision."

## 2. Minimum sample size before any comparison is reported

**[KB-MEAS-050] (internal doctrine)** This is [`metric-registry-doctrine.md`](metric-registry-doctrine.md) §4's rule
applied at report-authoring time: before comparing two rates (this week vs. last week's conversion
rate, campaign A vs. campaign B's CPA), confirm both sides clear the registered metric's minimum
sample threshold. A comparison built from an under-powered sample produces noise that *looks* like a
meaningful signal — two coin flips landing heads 100% of the time is not evidence the coin is
weighted, and a campaign converting at "50%" from 2 leads carries exactly that same amount of
information.

**[KB-MEAS-051] (internal doctrine)** When a comparison's sample size is below the threshold, the report states this
explicitly ("insufficient data to compare reliably, n=3 vs n=2") rather than either suppressing the
comparison silently or presenting an unreliable percentage as if it were solid. A reader who sees no
comparison at all cannot tell whether that's because nothing changed or because nobody checked; a
reader who sees "insufficient data" knows exactly what's missing and why.

## 3. A dashboard's default view should not require interpretation to avoid a wrong read

**[KB-MEAS-052] (internal doctrine)** the visual/structural design of a dashboard is itself part of
getting this right, not just the words in a narrative report. Two general dataviz-hygiene rules,
restated here as measurement-reporting rules for a dashboard specifically:

- **Never let a chart's y-axis scaling or a stat tile's framing imply a bigger or smaller change than
  the underlying data supports** (a truncated y-axis making a 2% move look like a 50% move; a
  single-number stat tile with no comparison baseline, trend, or confidence context).
- **A metric currently rendering `missing` per this corpus's own missing-value rule
  ([`metric-registry-doctrine.md`](metric-registry-doctrine.md) §3) must render visibly and
  distinctly as missing in the dashboard itself** — a blank cell that could be mistaken for "not yet
  loaded," or a cell silently showing a stale cached value, both fail this rule as much as a
  fabricated zero would.

## 4. What a weekly/monthly report structurally contains

**[KB-MEAS-053] (internal doctrine)** Every recurring report names, at minimum: the date range and which cohorts within
it are "settled" vs. still filling (per [`reconciliation.md`](reconciliation.md) §5); which
registered metrics moved and by how much, each tagged association or causal per §1; any metric
currently `missing` and why; any reconciliation break found and its resolution status
([`reconciliation.md`](reconciliation.md) §3); and any registered metric whose *definition* changed
this period ([`metric-registry-doctrine.md`](metric-registry-doctrine.md) §2), called out explicitly
rather than left for the reader to notice from a discontinuous trend line.

## 5. Never present a claim about performance without citing what produced it

**[KB-MEAS-054] (internal doctrine)** This corpus's own citation-style discipline (`shared/citation-style.md`) governs
external platform/behavioral claims; the equivalent discipline for a *performance* report is that
every number traces to a named source query, date range, and (where relevant) the registered metric
id that defines it — never a number typed from memory of "about what it usually is." A report
reader (the operator, or a client the company reports to) should be able to ask "where did this number
come from" and get a specific, re-runnable answer, not a shrug.

---

## Contractor bend

- A GC reading a report with no in-house data-analysis background is the reader most likely to take
  an association-framed sentence as a causal guarantee ("the new page increased conversions" reads,
  to this buyer, as "changing the page is what did it," full stop) — which makes the association/
  causation discipline in §1 more load-bearing for this buyer, not less, even though they are the
  least likely reader to ask a clarifying question about methodology.
- This buyer's month-to-month lead volume is often genuinely small (dozens, not thousands) — meaning
  the minimum-sample-size discipline in §2 will trigger *often* for a business this size, not as an
  edge case. Expect to say "insufficient data to tell yet" more often for a GC client than for a
  higher-volume e-commerce account, and treat that as correct, careful reporting rather than a report
  that isn't delivering enough insight.
- When something did NOT work, report it as plainly as when something did — this buyer has been
  burned before by agencies that only ever report good news (`contractor-buyer-psychology.md`), and a
  report that only ever shows wins reads, to this specific buyer, as evidence of exactly that pattern.
