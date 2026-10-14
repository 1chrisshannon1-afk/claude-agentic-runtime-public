# Message Match

Added 2026-09-19. Message match (also called ad scent or message continuity) is the alignment
between an ad's headline/offer and the destination page's hero headline/offer.

## The mechanism

Message match is widely treated across CRO practice as the highest-impact post-click variable:
when the promise, visuals, and tone carry through the click, trust rises and bounce falls
(third-party practitioner consensus — CXL, KlientBoost, Powered by Search, retrieved 2026-09-19;
no primary/official study is cited for a specific effect size — treat the direction as established
practitioner consensus, not a measured number).

Mechanisms, cheapest first:
1. **One destination per ad-group message angle** — the hero restates the ad's promise in the ad's
   own words.
2. **Dynamic Text Replacement** — URL-parameter-driven substitution of headline/subhead/CTA to
   match the triggering ad or query. Start with the headline alone as the correct first increment,
   not a full campaign-aware rebuild (official vendor doc, Unbounce DTR documentation, retrieved
   2026-09-19).

## Duty — a company's own multi-variant doctrine changes under paid traffic

A company may ship several message-angle landing-page variants (e.g. speed-led, ROI-led, pain-led,
social-proof-led, video-led — check the company's own pack/dossier for what actually exists and
where). `ab-testing-discipline.md`'s segmented-positioning bend already instructs segmenting a test
result by traffic source before declaring a single universal winner — it stops short of the
message-match mechanism itself; this file closes that gap.

**With paid traffic, a company's variant set stops being a random-split A/B test and becomes a
message-match asset set:** the speed variant is the destination for speed-angle ads, the money
variant for ROI-angle ads, and so on. Review each variant against the ad copy intended to point at
it, and flag any ad/destination pair whose promise does not survive the click.

**Randomly assigning a variant to paid traffic actively destroys message match and is a reject** —
it guarantees most visitors land on a page that does not restate the promise they clicked on.

## What NOT to cite

Two figures were considered for this file and dropped as unsourced/unmeasured: a "40-60% vs 60-90%
bounce rate" target band (single-source, vendor-adjacent, and this seat cannot measure a
bounce-rate target on any one company's own traffic without a fresh measurement — prescribing an
unmeasured numeric target is exactly the failure this corpus's own operator-set standards forbid),
and a "60-70% of DKI lift from headline alone" figure (single-source vendor content). Keep
"headline first" as the ordering rule for DTR rollout — it needs no percentage to be actionable.
