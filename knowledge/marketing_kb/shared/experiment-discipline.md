# Experiment discipline — running tests honestly

Every GTM seat that proposes or reads the result of a test — an A/B ad variant, a landing-page
headline test, a pricing-page layout change, an email subject-line split — follows the discipline in
this file. It exists because the failure mode isn't usually a bad hypothesis; it's an honest-looking
process that quietly stops being honest at the moment someone checks the results before they're
ready, and nobody notices because the numbers still look like numbers.

## [KB-SHARED-501] The core discipline is a process, not a statistics lecture

The gap between running a test and running one correctly is process discipline, not deeper
statistical knowledge (UNVERIFIED — seeded, needs derivation: general marketing-experimentation
practice asserted from aggregated familiarity with A/B-testing guidance, no single named source or
URL re-confirmed in this pass; re-cite to a specific, named source before this claim anchors a
proposal). **Practical translation for this department:** every seat proposing a test states, before it starts, (1) the
exact hypothesis in the form "we believe [change] will result in [outcome] because [reasoning]," (2)
the metric that decides the outcome, (3) how long the test will run and how many
observations/conversions it needs before anyone looks at the result, and (4) what happens if the
test is genuinely inconclusive (ship neither, ship the control, or extend — decided in advance, not
improvised after the fact). A test proposal missing any of these four is not ready to launch.

## [KB-SHARED-502] Set the duration and stopping rule before the test starts — and don't move it

Google's own Ads Experiments documentation is explicit that a test needs real time to produce a
trustworthy read: **"It's recommended that you run the experiment for at least 4-6 weeks or longer if
you have a long conversion delay,"** and Google additionally discards **"the first 7 days of data...
to account for the experiment ramp-up time"** before any evaluation begins (official, Google Ads
Help, "Experiments FAQs," retrieved 2026-09-27, https://support.google.com/google-ads/answer/13826584).
The same page also notes new experiments require a 7-14 day ramp-up period before results should be
trusted. The platform itself treats "just a few days" as too short to trust — but this page does not
state any specific floor/ceiling on an experiment's end date or an extension limit; **do not cite a
2-12-week window or a 12-week extension rule to this source** (checked directly against the page,
2026-09-27 — no such constraint appears on it). **Practical translation: pick the stop
condition (a date, or a conversion count) before launch, write it into the proposal, and do not move
it once the test is running** — a stop condition chosen after seeing early results is not a stop
condition, it is the exact failure mode described in [KB-SHARED-503] below wearing a different name.

## [KB-SHARED-503] Checking early and stopping on a good result inflates false positives — this is measured, not theoretical

Standard significance testing assumes exactly one look at the data; every additional look at interim
results before the planned stopping point inflates the real false-positive rate above the nominal 5%
figure a seat might otherwise quote with confidence. Specific measured figures, drawn from
simulation-based analysis (third-party, Atticus Li, "The Peeking Problem in A/B Testing," retrieved
2026-09-27, https://atticusli.com/replication-crisis/ab-testing-peeking-problem/ — a single
practitioner's simulation-based write-up citing Optimizely's own published research; treat the exact
percentages as directional, not a guaranteed inflation rate for every test configuration): checking
results every 500 visitors produces roughly a **26% false-positive rate** under the null hypothesis
(where 5% was intended); checking every 1,000 visitors produces roughly **20%**; and continuous
monitoring — looking whenever it's convenient and stopping the moment the number looks good — pushes
the real false-positive rate to **40% or higher** over a realistic test duration. The mechanism: the
5% guarantee is a statement about a single test statistic computed once, not about the maximum of a
whole sequence of test statistics computed repeatedly as data accumulates — and that maximum is
mathematically guaranteed to be larger than any one look. **Practical translation: a seat may *watch*
a live test's dashboard for operational health (is it tracking correctly, is traffic split roughly as
expected — see [KB-SHARED-504] below) without this counting as a "look" for stopping purposes; a
"look" that counts is any point where the seat considers ending the test because the number looked
good or bad.** A seat that reports "we stopped early because it was already clearly winning" has,
per the mechanism above, likely reported a false positive rather than a real winner — the honest fix
is to have picked a sequential-testing method in advance (a method built to allow safe early looks by
adjusting the significance threshold as it goes) rather than deciding informally to stop early on a
fixed-horizon test never designed to be peeked at.

## [KB-SHARED-504] Sample-ratio mismatch is a silent test-invalidating bug, not a result

A **sample ratio mismatch (SRM)** is when the actual number of visitors landing in each test variant
diverges meaningfully from what random assignment should have produced (e.g. a 50/50 test that
actually split 58/42) — and when this happens, the source is clear that this is a **symptom of a
data-quality problem, not a result to trust as-is**: Optimizely states an SRM "is a symptom of a
variety of data quality issues" and that "ignoring a SRM without knowing the root cause may result in
a bad feature appearing to be good and being shipped out to users, or vice versa" (third-party,
Optimizely, "Automatic sample ratio mismatch detection," retrieved 2026-09-27,
https://www.optimizely.com/insights/blog/introducing-optimizelys-automatic-sample-ratio-mismatch-detection/
— checked directly against the page, 2026-09-27; the source does not use the stronger phrase
"regardless of what the significance number says," so this claim does not either).
**Practical translation: before reading any test's result, check the actual visitor/impression count
in each variant against the intended split.** A meaningfully skewed split is a reason to void the
test and fix the underlying assignment mechanism, not a reason to report the result with an asterisk
— an SRM-affected test cannot be salvaged by statistical adjustment after the fact, because the thing
that's broken is the randomization the whole method depends on.

## [KB-SHARED-505] Below a real traffic/conversion floor, A/B testing itself is the wrong tool

**"Low traffic makes A/B testing harder, but it does not make experimentation useless"** — the fix at
low volume is switching methods, not abandoning learning altogether (third-party, Nelio Software
blog, "A/B Testing for Low-Traffic Websites: Is It Still Worth It?", retrieved 2026-09-27,
https://neliosoftware.com/blog/ab-testing-low-traffic-websites/ — a testing-vendor's own blog;
directional guidance, not a universal statistical threshold). There is no single universal traffic
number below which testing "stops working" — what matters is whether the specific page/campaign
being tested can plausibly accumulate enough observations to detect a meaningfully-sized effect
within a timeframe the business can actually wait for; a page converting at 20% with 2,000 monthly
visits can produce a usable test faster than a page converting at 0.2% with 5,000 visits (same
source). **This is often the single most important translation for a small-business buyer base**: a
company at the small end of this department's typical range (a single-location `local_service`
business, or an early-stage B2B tool sold to that scale of buyer — the `contractor-buyer-psychology.md`
worked archetype) will typically run website and ad accounts at volumes far below a national
e-commerce brand's, and a seat that proposes a formal A/B test without first checking whether the
page/campaign in question can realistically reach a usable sample size within a sane timeframe is
proposing a test that will produce noise dressed as a result. **When the traffic floor isn't met, the
same source's recommended alternatives are the correct default**: session recordings and behavioral
analytics to find concrete usability problems ("if a recording reveals a button that doesn't work on
mobile, fix it — don't test it"), direct customer feedback (support conversations, calls, reviews —
channels this kind of buyer already uses heavily, per `contractor-buyer-psychology.md` /
`homeowner-buyer-psychology.md`), and reserving a real split test for the specific, high-uncertainty,
high-value decisions where the wait is actually worth it rather than running one on every small copy
tweak.

## [KB-SHARED-506] Meta/paid-social test windows need a full week minimum, for a reason specific to the platform

Independent of statistical significance math, a paid-social test that runs for less than roughly one
week will systematically miss weekday/weekend behavioral variance and produce a biased read even if
it happens to reach significance early (UNVERIFIED — seeded, needs derivation: general paid-social
practice asserted from aggregated familiarity with the platforms, no named source or URL re-confirmed
in this pass; Meta's own help-center documentation on this specific point could not be independently
confirmed and should be re-verified against Meta's current Ads Manager help center before this figure
anchors a specific test's budget). **Practical translation: never accept "it hit significance in 3
days" as a reason to end a paid-social test early — treat a full weekly cycle as a floor for this
channel specifically, pending re-verification, on top of (not instead of) the peeking discipline in
[KB-SHARED-503].**

## The forbidden shortcuts, restated plainly

- **Never** move the stop date or the required sample size after seeing interim results — that is
  p-hacking wearing an operational excuse ("we needed the budget for something else").
- **Never** report a result from a test with a known sample-ratio mismatch, even with a caveat — void
  it and re-run with the assignment bug fixed.
- **Never** run a formal split test on a page/campaign that structurally cannot reach a usable sample
  size in a reasonable window — use the low-traffic alternatives instead and say so plainly rather
  than reporting a "winner" built on too little data.
- **Never** slice the same test result by multiple segments after the fact looking for *some*
  significant subgroup, and then report that subgroup's result as if it were the planned analysis —
  this is the same undisclosed-flexibility problem the academic replication-crisis literature
  documents at scale (third-party/academic, Simmons, Nelson & Simonsohn, "False-Positive Psychology:
  Undisclosed Flexibility in Data Collection and Analysis Allows Presenting Anything as Significant,"
  *Psychological Science*, 2011 — cited via a secondary source's summary, retrieved 2026-09-27; this
  department has not independently retrieved and read the primary paper, so treat the citation as
  UNVERIFIED at the primary-source level even though the mechanism it describes is corroborated by
  the platform-specific sources above).

## Contractor bend

This file's discipline protects the same kind of buyer `contractor-buyer-psychology.md` /
`homeowner-buyer-psychology.md` describe, in a specific way: a buyer deciding whether to trust this
department's recommendations is watching for exactly the kind of overclaiming a p-hacked "45% lift!"
result represents — a confident number built on a broken process is worse than no number at all,
because it's the kind of vendor overpromise this buyer has already been burned by. Given this kind of
buyer's typically low traffic volumes ([KB-SHARED-505]), the honest, buyer-respecting default is more
often "we don't have enough volume to A/B test this reliably, here's what we learned from watching
real behavior instead" than a manufactured split-test result — and that honesty is itself a
trust-building move for a buyer who
values specificity and proof over polish (`contractor-buyer-psychology.md` fact 5 /
`homeowner-buyer-psychology.md` fact 3).
