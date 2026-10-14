# A/B Testing Discipline

How a test gets proposed, sized, run, and called a winner — ported from a CRO procedure's testing
methodology, plus a worked example of how to read a real multi-variant landing-page setup against
that discipline.

## The core testing rules (internal doctrine)

| Rule | Detail |
|---|---|
| **One variable at a time** | Change one element per test. Changing headline AND image AND CTA together makes the result uninterpretable — you cannot attribute the effect to any one change (internal doctrine, retrieved 2026-09-05). |
| **Statistical significance** | Do not call a winner before 95% confidence (internal doctrine, retrieved 2026-09-05). |
| **Minimum sample size** | Typically 1,000+ visitors per variation for a meaningful test; calculate the required size from the baseline conversion rate and minimum detectable effect BEFORE starting, don't eyeball it after (internal doctrine, retrieved 2026-09-05). |
| **Run time** | Minimum 2 full weeks to capture weekday/weekend cycles, even if significance arrives sooner — run at least 7 days regardless (internal doctrine, retrieved 2026-09-05). |
| **Full-funnel measurement** | Measure the complete conversion, not just the click. A CTA change that raises clicks but lowers actual signups/purchases is a net loss the click-through metric alone would hide (internal doctrine, retrieved 2026-09-05). |
| **Document everything** | Hypothesis, what changed, dates, traffic volume, result, decision — every test builds the institutional knowledge base, win or lose (internal doctrine, retrieved 2026-09-05). |

## The PIE prioritization framework

Score every candidate test on three factors, 1–10 each, and rank by total (internal doctrine,
retrieved 2026-09-05):

- **Potential** — how much room for improvement exists on this page? (A low-converting page has
  more headroom than an already-strong one.)
- **Importance** — how much traffic/revenue actually flows through this page? (A high-traffic page's
  win matters more than the same percentage win on a low-traffic page.)
- **Ease** — how simple is this test to implement? (Prefer simple changes first, all else equal.)

PIE has a named originator — Chris Goward / WiderFunnel — rather than being this corpus's own
mechanism (originator attribution: UNVERIFIED — seeded, no retrieval date: the originating
WiderFunnel page was not fetched this pass — re-verify directly before citing the framework's
specifics, e.g. its exact scoring guidance, as anything more than "attributed to WiderFunnel"; the
three factor definitions above are this corpus's own restatement and carry their own
internal-doctrine citation independent of the open originator-attribution question).

## Reading a company's own multi-variant setup against this discipline

A company may ship several distinct message-angle landing-page variants (e.g. speed-led,
ROI/money-led, pain-point-led, social-proof-led, video-led) — check the company's own pack/dossier
for what actually exists on disk today, since this changes as pages are built and retired.

**What a healthy setup looks like, per the discipline above:** the variants should isolate a single
dimension — the core message angle — which is consistent with the "one variable at a time" rule if
each variant otherwise holds the rest of the page constant. A message-angle test is also a
genuinely high-PIE-score test to run when the angle question is fundamentally unresolved for the
product: it touches the homepage/entry point (high Importance), the angle question matters (high
Potential), and swapping a hero angle is a comparatively Easy change relative to a structural
redesign.

**What a conversion-architect must verify before trusting any such setup, rather than assume:** a
file existing on disk is not evidence a real, running A/B test infrastructure exists behind it.
Before citing "we are running an A/B test" as a fact in any review, the reviewer must confirm,
don't assume:

1. **Is there real traffic-splitting infrastructure** (a router, a feature flag, a redirect rule)
   actually assigning visitors to these variants, or are these static files sitting unrouted on
   disk (e.g., legacy variants from a prior test, or drafts never wired up)?
2. **Is there a real analytics/conversion-tracking hookup** per variant, or would "which variant won"
   be unanswerable even if traffic were being split?
3. **Does each variant actually isolate one variable**, or do they differ on message angle AND
   layout AND CTA copy simultaneously (which would violate the one-variable rule even though the
   naming suggests a single-dimension test)?
4. **N simultaneous variants is a real sample-size cost** — splitting traffic N ways multiplies the
   visitors-per-variation needed to reach the 1,000+/95%-confidence bar in the same total time
   compared to a straight two-way test. A reviewer should check this was a deliberate tradeoff
   (enough total traffic to support N-way splitting in a reasonable window) rather than an
   unconsidered one.

**UNVERIFIED — needs derivation, per engagement:** whether a company's own variants are currently
live-routed with real traffic-splitting and measurement, or are static/dormant files. This corpus
does not assert an answer either way for any given company; a conversion-architect reviewing a
specific engagement must check the actual routing/analytics config before treating a multi-variant
setup as "a test in progress" in any finding.

## What NOT to do with multiple variants, per this domain's anti-patterns

- Never let "we have N variants" become an excuse to skip the PIE-prioritization discipline for
  what to test NEXT once a winner is called — several variants running once is not a standing
  testing program by itself.
- Never call a winner off partial-week or sub-1,000-visitor data just because one variant "looks
  ahead" early — the 95%-confidence and 2-week-minimum rules apply regardless of which variant is
  currently informally winning.
- Never let a message-angle test double as cover for smuggling in a never-claim-list violation on
  one variant only (e.g., a "pain" variant overstating a problem, or a "social proof" variant using
  a fabricated number) — every variant is bound by the same never-claim list (see the company's own
  pack/dossier); a test cannot be used to justify a claim that wouldn't clear review on its own.

## Bends: small-traffic companies and segmented positioning

1. **An early-stage company's actual traffic volume is very likely far below the 1,000+/variant
   threshold.** An early-stage B2B product selling into a narrow buyer band does not have
   consumer-e-commerce-scale traffic. A conversion-architect must flag, honestly, when a "test
   result" is being read off a sample too small to trust (e.g., 40 visitors per variant) — the
   discipline above doesn't relax for a smaller company; it means fewer valid tests get run, and the
   ones that do run may need to be simpler two-way tests rather than N-way splits, or run longer
   than 2 weeks to accumulate enough volume. Recommending "just look at which variant has more
   signups so far" on a 3-day, 60-visitor sample is a reviewer failure, not a shortcut.
2. **A message-angle question can map directly onto a company's own settled positioning split**
   (e.g. a "two pitches, one product" split targeting two different buyer sub-segments — see the
   company's own pack/dossier for its specific split). A conversion-architect reviewing this kind of
   test should treat "which angle wins overall" as potentially a false single-winner question — the
   honest read may be that different variants win for different traffic sources/audience segments
   (e.g., paid-search visitors who searched a pain-point term vs. referral visitors from a trusted
   peer), not that one variant "beats" the others universally. Segment the result by traffic source
   before declaring a single universal winner, whenever the buyer segmentation is already a
   documented, deliberate part of the product's own positioning strategy.
