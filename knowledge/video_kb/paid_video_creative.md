# Paid Video Ad Creative — Meta, YouTube, LinkedIn (advisory, no spend)

Terse rules a worker agent can apply when producing or reviewing paid video ad creative.
Retrieval date for every rule below: 2026-09-12, unless flagged UNCITED (practitioner
consensus, no single authoritative doc). This file is advisory only — it authorizes no ad
spend and no publish action by itself.

**Provenance:** aggregated from third-party vendor/agency guides unless a source is marked
OFFICIAL. Every non-OFFICIAL source below is practitioner opinion, not platform documentation;
a platform-behaviour claim that rests only on such a source is flagged UNCONFIRMED-PRIMARY (the
`INDEX.md` flag set). Where this file and `video_producer_primer.md` §8 (paid-creative doctrine)
disagree, the primer wins.

**Hard constraints (cross-company operator rulings — never contradict, cite from every relevant
section):** b-roll ≤2.5s per shot, ≤20% of runtime, never two consecutive, none starting before
3.0s; product-first opens; the rendered cut is watched (contact sheets against the timed
transcript, per shot) before any upload — the seat's own frame-viewing review satisfies this, per
primer §4/§7. Separately, vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
and any other wording rule: follow the company pack's `claims_policy` and that company's own
video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
(see `INDEX.md`'s precedence note).

---

## 1. Platform lengths — hard limits vs. recommended

- **Meta Reels ads:** a 90s cap with a 15–30s performance sweet spot is reported —
  **UNCONFIRMED-PRIMARY** (no Meta Business Help page confirmed it; primer §8j). Keep Reels ad
  cuts ≤30s, which is safe whether or not the cap figure is right. [Meta ad sizes 2026](https://superscale.ai/learn/meta-ad-sizes) (practitioner opinion, not platform documentation)
- **Meta Feed/Stories video:** a 1s–240min technical file range is reported (UNCONFIRMED-PRIMARY);
  treat 15–30s as the working target regardless of the technical ceiling. [Meta ad sizes 2026](https://superscale.ai/learn/meta-ad-sizes) (practitioner opinion, not platform documentation)
- **YouTube skippable in-stream (TrueView):** recommended 12s minimum, 3min maximum; viewer
  can skip after 5s (UNCONFIRMED-PRIMARY). [YouTube Ad Specs 2026](https://blog.adnabu.com/google-ads/youtube-ad-specs/) (practitioner opinion, not platform documentation)
- **YouTube bumper ads:** 6 seconds or fewer, non-skippable — a format rule, not a guideline
  (the 6s definition is UNCONFIRMED-PRIMARY in this pass; separately OFFICIAL: videos under 10s
  are ineligible for Demand Gen In-stream, so a bumper cannot carry that placement — primer §8a).
  Use as a repetition/reinforcement tool, never to tell a story. [YouTube Ad Specs 2026](https://blog.adnabu.com/google-ads/youtube-ad-specs/) (practitioner opinion, not platform documentation)
- **YouTube Shorts ads:** up to 3 minutes accepted, but only the **first 60 seconds** plays
  in the Shorts feed — treat 60s as the real ceiling; recommended <60s, action-oriented cuts
  10–30s. [YouTube Shorts specs (OFFICIAL)](https://support.google.com/google-ads/answer/16041697?hl=en)
- **LinkedIn video ads:** technical range 3s–30min; in-stream can extend to 90s; recommended
  15–30s for the broadest placement eligibility. [LinkedIn video ad specs (OFFICIAL)](https://www.linkedin.com/help/lms/answer/a424737)
- **Cross-platform default when no format is yet chosen:** cut a 15–30s core version first;
  derive the 6s bumper and any 60–90s longer cut from it, never the reverse.

## 2. Aspect ratio & resolution

- **Meta:** primary formats 1080×1350 (4:5, feed), 1080×1920 (9:16, Reels/Stories), 1080×1080
  (1:1, carousel/Marketplace). A March-2026 shift of Meta's recommended Feed ratio away from
  square toward 4:5/9:16 is reported — **UNCONFIRMED-PRIMARY** (primer §8a: Meta Business Help
  returned no spec content). Specify both 9:16 and 4:5 regardless. [Meta ad sizes 2026](https://superscale.ai/learn/meta-ad-sizes) (practitioner opinion, not platform documentation)
- **Google Demand Gen (OFFICIAL):** requires 1:1, 16:9, AND 4:5; 9:16 optional; videos under 10s
  are ineligible for YouTube In-stream; the video must be YouTube-hosted — see primer §8a for the
  full sourced rows. [Demand Gen video specs (OFFICIAL)](https://support.google.com/google-ads/answer/17141078?hl=en)
- **YouTube in-stream/bumper:** native horizontal 16:9 is standard; vertical/square accepted
  but 16:9 remains the default for in-stream placements. [YouTube Ad Specs 2026](https://blog.adnabu.com/google-ads/youtube-ad-specs/) (practitioner opinion, not platform documentation)
- **YouTube Shorts:** 9:16 vertical is recommended; a horizontal asset still runs but is
  letterboxed with blurred top/bottom bars in the Shorts feed — always cut a true vertical
  master for Shorts rather than relying on auto-reframe. [YouTube Shorts specs (OFFICIAL)](https://support.google.com/google-ads/answer/16041697?hl=en)
- **LinkedIn:** four supported ratios — 16:9 (640×360–1920×1080), 1:1 (360×360–1920×1920),
  4:5 vertical (360×450–1080×1350, LinkedIn's recommended vertical), 9:16 vertical
  (360×640–1080×1920, mobile-only delivery). If targeting desktop + mobile together, use
  16:9. [LinkedIn video ad specs (OFFICIAL)](https://www.linkedin.com/help/lms/answer/a424737)
- **Master-file rule:** shoot/compose to the tallest ratio you'll need (9:16) and pull 4:5 and
  16:9 crops from it, protecting action for the narrowest safe zone at edit time — cheaper
  than separate shoots per platform. UNCITED (practitioner consensus).

## 3. Safe zones (keep text/logo/CTA clear of these)

- **Meta 9:16 (Stories/Reels/9:16 Feed):** keep text and logo out of the top 14%, bottom 35%,
  and outer 6% of each side. Practitioner sources describe this as one zone "unified as of March
  2026" — both the percentages and the unification are **UNCONFIRMED-PRIMARY** (primer §8g: no
  Meta page confirming them was fetchable). Designing to this stricter band is still the safe
  default. [Meta safe zones 2026](https://billo.app/blog/meta-ads-safe-zones/) (practitioner opinion, not platform documentation)
- **Meta 4:5 feed:** roughly top 14% (~250px on 1080×1350) and bottom 20% (~340px) clear
  (UNCONFIRMED-PRIMARY). [Meta ad sizes 2026](https://superscale.ai/learn/meta-ad-sizes) (practitioner opinion, not platform documentation)
- **YouTube Shorts:** keep primary message, logo, and CTA clear of the right-side
  Like/Share/Subscribe button rail, and note the ad's CTA appears 3s in — both OFFICIAL.
  [YouTube Shorts specs (OFFICIAL)](https://support.google.com/google-ads/answer/16041697?hl=en)
  Google publishes **no** numeric bottom safe-zone figure for Shorts; keeping key content out of
  the bottom ~20% (captions/channel-name overlay zone) is UNCITED (practitioner consensus, not a
  Google spec) — per primer §8g.
- **YouTube in-stream:** platform CTA/companion banner occupies the lower-left/skip-button
  corner — avoid placing your own end-card CTA or logo in the bottom-right where the skip
  countdown and CTA overlay render. UNCITED (practitioner consensus).
- **LinkedIn:** no published percentage safe zone; because captions and the sponsored-content
  header/footer chrome sit top and bottom in-feed, keep key text vertically centered and off
  the extreme top/bottom ~10%. UNCITED (practitioner consensus, conservative default).
- **Universal rule:** never place burned-in text or a CTA overlay in the outer safe-zone band
  for the platform's native aspect ratio for that placement — reframing a 16:9 master to 9:16
  without re-checking safe zones is the most common way a CTA gets clipped.

## 4. Hook-in-first-frame

- Practitioner sources report that 87% of viewers decide to keep watching or skip within the
  first 3 seconds, and attribute to a Meta/Nielsen study the figure that ~47% of a video
  campaign's total value lands in those first 3 seconds — UNCONFIRMED-PRIMARY (no Meta/Nielsen
  primary located). [Why the first 3 seconds matter](https://animoto.com/blog/video-marketing/why-first-3-seconds-matter) (practitioner opinion, not platform documentation)
- **Hard constraint reminder:** this KB's b-roll rule (none starting before 3.0s, product-first
  opens) means frame 1 must show the real product/output, not b-roll or a logo card — the hook
  and the product-first rule are satisfied by the same opening shot, not two competing ones.
- Design the hook for **sound-off** viewing first: 85% of Facebook video, 80% of LinkedIn
  video, and 40% of Instagram video play with no audio — the visual + on-screen text must
  carry the hook alone (percentages UNCONFIRMED-PRIMARY; treat as directional). [Sound on/off trends](https://verbit.ai/captioning/sound-on-sound-off-64-marketers-using-video-see-benefit-of-captions/) (practitioner opinion, not platform documentation)
- Effective hook devices: a direct-to-camera human face (highest attention capture of any
  single visual element), a specific on-screen claim or question, a pattern interrupt (unusual
  angle, mid-action open), or motion/contrast in the first frame. [Hook rate guidance](https://zeely.ai/blog/boost-meta-ads-hook-rate/) (practitioner opinion, not platform documentation)
- Given this KB's constraints, the sanctioned hook is: open on the real product/UI already
  mid-action (nothing the company's vocabulary/claims list restricts), paired with on-screen text
  stating the concrete outcome in the audience's own plain language — never an abstract statement
  about how the software works internally.
- **Hook/hold benchmarks (practitioner figures, never platform specification — never quote them
  to the operator as Meta's own numbers):** hook rate (3s views / impressions) 25–35% cold /
  35–45% retargeting, kill below 15%; hold rate (ThruPlays / 3s views) 20–25% cold / 30–40%
  retargeting, optimize below 18%; ThruPlay rate 18–28% cold, scale above 30%. These replace an
  earlier "70–80% first-3-second retention" bar that was wrong by 2–3x for the metric it purported
  to measure — source and correction: `video_producer_primer.md` §8b. [Meta video ad benchmarks 2026](https://www.get-ryze.ai/blog/meta-video-ad-benchmarks-thruplay-hook-and-hold-rate-2026) (practitioner analysis, not Meta documentation)

## 5. Captions & sound design

- Caption 100% of video ads — spoken dialogue and voiceover both — for accessibility and
  because most viewing is sound-off across every platform in scope here. [Captioning best practice](https://verbit.ai/captioning/sound-on-sound-off-64-marketers-using-video-see-benefit-of-captions/) (practitioner opinion, not platform documentation)
- Burned-in (open) captions are safer for feed/Reels/Shorts placements where the platform UI
  may hide or not render closed-caption tracks by default; closed captions remain required
  wherever the platform supports them (LinkedIn requires **SRT format, text-only, no custom
  styling**). [LinkedIn video ad specs (OFFICIAL)](https://www.linkedin.com/help/lms/answer/a424737)
- Measured lift from captioning: +13% brand linkage, +10% ad memory quality, +8% ad recall;
  viewers are ~80% more likely to watch a captioned video to completion. [Captioning lift data](https://www.3playmedia.com/blog/take-your-video-ads-to-the-next-level-with-captions/) (practitioner opinion, not platform documentation) — practitioner-compiled figures, treat as directional, not platform-verified.
- Never let burned-in caption text sit inside the safe-zone bands from Section 3 — caption
  placement is a frequent silent safe-zone violation because captions are added last, after
  the CTA overlay is already placed.

## 6. CTA overlays

- Place the CTA text/button clear of every platform's safe-zone band (Section 3); never
  anchor a CTA to the extreme bottom edge on 9:16 formats — practitioner guidance puts a 20–35%
  bottom exclusion band on Meta and YouTube Shorts (UNCONFIRMED-PRIMARY for Meta, UNCITED for
  Shorts — Section 3), and designing to it is the safe default.
- On YouTube in-stream, the platform's own CTA overlay/skip button appears in the same region
  from ~3 seconds in for most campaign types — do not compete with it by adding a second CTA
  card in the same corner. [YouTube Shorts specs (OFFICIAL)](https://support.google.com/google-ads/answer/16041697?hl=en)
- Where the company's claims list forbids numeric/accuracy claims, the CTA copy itself must state
  an action ("See how it works," "Book a free consult") never a metric or time promise ("in 60
  seconds," "99% accurate").
- Reinforce, don't just append: a CTA card at the very end is necessary but not sufficient —
  repeat the core action verbally/on-screen at least once mid-video for anything over ~20s.
  UNCITED (practitioner consensus).

## 7. Creative testing & iteration cadence

- **Refresh cadence scales with spend, not a fixed calendar:** ~$500–1,000/day → refresh every
  2–3 weeks; >$1,000/day → refresh every 1–2 weeks; lower/always-on spend → 2–4 weeks.
  [Creative refresh cadence 2026](https://www.superads.ai/blog/creative-refresh-cadence) (practitioner opinion, not platform documentation)
- **Format-specific rotation:** Reels need faster rotation (7–14 days at typical spend) than
  broad Feed prospecting (3–6 weeks) — vertical short-form burns out faster. [Creative refresh cadence 2026](https://www.superads.ai/blog/creative-refresh-cadence) (practitioner opinion, not platform documentation)
- **Fatigue trigger, not just a calendar:** let a new creative clear the ~7-day learning phase
  first, then rotate when Frequency reaches 2.5–3x or CTR drops meaningfully — frequency of 4
  same-creative exposures correlates with ~45% drop in conversion likelihood. [Ad fatigue guidance](https://www.superads.ai/blog/creative-refresh-cadence) (practitioner opinion, not platform documentation)
- **Weekly cadence discipline:** run a creative-health check twice weekly (frequency, CTR
  trend, CPM movement per active creative) and make pause/refresh/keep decisions on a weekly
  cycle rather than ad hoc. [Creative health audit cadence](https://www.superads.ai/blog/creative-refresh-cadence) (practitioner opinion, not platform documentation)
- **Variation volume for dynamic/Advantage+ creative:** minimum ~6 creative assets per ad set
  to feed Advantage+ optimization; 20–50+ assets for fuller coverage; keep per-element
  variation (images/video, headlines, primary text) to 3–5 distinct options each so the
  algorithm isn't diluted across too many combinations at once. [Dynamic creative testing tips](https://www.hunchads.com/blog/dynamic-creative-optimization) (practitioner opinion, not platform documentation)
- **Vary concept, not just cosmetics:** feed the system genuinely different hooks/angles/
  formats rather than palette-swapped versions of the same cut — the ROAS gains from creative
  testing come from real conceptual diversity, sustained continuously (new assets every 2–4
  weeks as a floor). [Dynamic creative testing tips](https://www.hunchads.com/blog/dynamic-creative-optimization) (practitioner opinion, not platform documentation)
- **Derive variants from one approved master cut** so every variant still passes this KB's
  hard constraints (b-roll ratio/timing, product-first open) and the company's vocabulary/claims
  list — testing
  velocity never justifies skipping the pre-upload viewing review on a new variant.
- **This file is advisory only:** it informs creative production and testing strategy and
  authorizes nothing by itself. **Spend and launch** follow the governing money rule
  (`~/.claude/knowledge/paid_acquisition_strategist_primer.md` §4: creating a campaign PAUSED,
  even with a budget field, is T1, not `$`; enabling, pausing, or removing a campaign or ad set,
  starting spend, or changing any budget or cap is operator sign-off). **Publishing** reviewed
  creative follows the company's autonomy tier after the required reviews, not the money rule.
  **Asset and ad-copy swaps inside an operator-approved budget** are within-ceiling optimizations
  (same primer §4). Where the creative is AI-assisted, the company pack's `ai_content_policy`
  applies on top of all of these.

---

## Sources

- [Meta ad sizes 2026: the operator-grade spec sheet for Facebook and Instagram](https://superscale.ai/learn/meta-ad-sizes) (practitioner opinion, not platform documentation)
- [Meta Ads Safe Zones: A Guide to the 2026 Unified Creative Updates](https://billo.app/blog/meta-ads-safe-zones/) (practitioner opinion, not platform documentation)
- [YouTube Ad Specs Guide: Formats, Sizes & Requirements 2026](https://blog.adnabu.com/google-ads/youtube-ad-specs/) (practitioner opinion, not platform documentation)
- [YouTube Shorts ads: Asset specs and best practices (OFFICIAL, Google Ads Help)](https://support.google.com/google-ads/answer/16041697?hl=en)
- [Demand Gen video ad specs (OFFICIAL, Google Ads Help)](https://support.google.com/google-ads/answer/17141078?hl=en) — fetched 2026-09-19 (primer §8a)
- [LinkedIn Video ads advertising specifications (OFFICIAL, Marketing Solutions Help)](https://www.linkedin.com/help/lms/answer/a424737)
- [Why The First 3 Seconds of Video Matter More Than the Next 30 — Animoto](https://animoto.com/blog/video-marketing/why-first-3-seconds-matter) (practitioner opinion, not platform documentation)
- [Meta video ad benchmarks 2026: ThruPlay, hook and hold rate — Ryze](https://www.get-ryze.ai/blog/meta-video-ad-benchmarks-thruplay-hook-and-hold-rate-2026) (practitioner analysis, not platform documentation) — fetched 2026-09-19 (primer §8b)
- [How to Improve hook rate for Meta Ads — Zeely AI](https://zeely.ai/blog/boost-meta-ads-hook-rate/) (practitioner opinion, not platform documentation)
- [Sound On? Sound Off? Marketers Using Video See Benefit of Captions — Verbit](https://verbit.ai/captioning/sound-on-sound-off-64-marketers-using-video-see-benefit-of-captions/) (practitioner opinion, not platform documentation)
- [Take Your Video Ads to the Next Level with Captions — 3Play Media](https://www.3playmedia.com/blog/take-your-video-ads-to-the-next-level-with-captions/) (practitioner opinion, not platform documentation)
- [Creative Refresh Cadence: When to Refresh Your Paid Ads (2026) — SuperAds](https://www.superads.ai/blog/creative-refresh-cadence) (practitioner opinion, not platform documentation)
- [Dynamic Creative Optimization guide for Meta [2026] — Hunch Ads](https://www.hunchads.com/blog/dynamic-creative-optimization) (practitioner opinion, not platform documentation)

Retrieved 2026-09-12 unless dated otherwise above. Practitioner-consensus items with no single authoritative source are
marked UNCITED inline; treat them as directional, not platform-verified.
