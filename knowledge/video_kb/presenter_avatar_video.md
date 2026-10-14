# Presenter & AI-Avatar Videos — Talking-Head Craft for B2B Software

Terse, worker-applicable rules for talking-head presenter videos and AI/synthetic-avatar
presenters in B2B software marketing. Aggregated from third-party creator-tool guides and
platform policy pages, retrieval date 2026-09-12 unless marked OFFICIAL (platform-published) or
UNCITED (practitioner consensus, no single authoritative source found).

## Precedence (read first)

**The primer (`~/.claude/knowledge/video_producer_primer.md`) wins on every conflict over the
cross-company hard rules; vocabulary and claims are per company (below).** It carries
the operator's rulings verbatim and is the single canonical statement of every hard number/rule.
This file is craft background — third-party technique and platform norms — never a source of
rules that override an operator ruling. If this file and the primer disagree, the primer is
correct and this file needs a fix.

## Hard constraints (cross-company operator rulings — never contradict, regardless of what a source below says)

- B-roll ≤2.5 s per shot; ≤20% of total runtime; never two consecutive; none before the 3.0 s mark.
- Every cut opens on the product itself (product-first opens) — not a face, not a logo card.
- Vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
  and any other wording rule: follow the company pack's `claims_policy` and that company's own
  video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
  (see `INDEX.md`'s precedence note). The company's list applies to a presenter's or avatar's spoken script exactly as to any
  other narration.
- **An AI/synthetic avatar is used only where the company pack's `ai_content_policy` permits it.**
  `forbid` rules it out; `strip_before_publish` rules it out for ad creative (primer §8f), and a
  synthetic presenter is a disclosure item that metadata stripping never discharges (primer §8h),
  so treat `strip_before_publish` as ruling it out for any cut. An unknown or unreadable mode means
  DEGRADED — no avatar until the mode is known.
- Viewing review: the rendered cut is watched — contact sheets against the timed transcript, per shot (primer §4/§7) — before any upload; the seat's own frame-viewing review satisfies this, no separate human viewer is required. For a presenter/avatar cut this
  review must specifically watch for lip-sync drift, motion artifacts, and misplaced emphasis (see
  the review checklist below), not just spot-check frames.

## 1. When a presenter beats a pure screen recording — and when it does not

**Presenter wins for:** announcements, policy/release updates, brand-intro/company-trailer
first-impression moments, sales-follow-up personalization, localized variants, and any beat where
a human face is doing the work of building trust rather than showing UI. A talking-head open can
raise engagement versus a faceless voiceover-only open because viewers connect with a face more
than a disembodied voice. [TechSmith](https://www.techsmith.com/blog/talking-head-videos/),
[Piktochart](https://piktochart.com/blog/talking-head-video/)

**Screen recording wins for:** anything the viewer needs to see operate — UI clicks, workflow
steps, dashboard state, a feature actually working. A talking head explaining software risks
reading like a webinar recording instead of a product demo; B2B software buyers specifically need
to see the real interface, not a face narrating it. A synthetic avatar does not replace
screen-recorded footage for this job. [Guideless](https://guideless.ai/blog/best-ai-product-demo-video-tools/),
[Demosmith](https://demosmith.ai/blog/best-ai-demo-video-generators-2026)

**The dominant B2B pattern is hybrid, not either/or:** a presenter (real or avatar) opens/closes
or narrates over picture-in-picture, while the body of the video is real screen capture. Treat a
presenter as a FRAME around the product, not a replacement for showing it — this is directly
compatible with the operator's product-first-open rule (open ON product, presenter voice can still
carry narration under/behind it — see §2 for layout). [Increditors](https://increditors.com/video-editing-for-saas-companies-the-complete-guide/)

**Never use a presenter/avatar for:** an apology, a sensitive or crisis communication, a
customer-facing testimonial, or any moment that needs to survive a skeptical scroll or close a
high-consideration decision — categories where trust is the primary purchase driver (health,
financial, professional services) show the sharpest backlash to AI-generated fronting.
[Storyteller Videos](https://www.storytellervideos.com/blog/what-every-marketer-should-know-before-producing-ai-avatar-videos),
[GueauxStudio](https://gueauxstudio.com/blog/fake-smile-problem-ai-generated-testimonials-backfiring).
A synthetic presenter also underperforms when asked to be funny, emotional, or persuasive —
reserve it for facts, walkthroughs, and status updates. [Viralix](https://viralix.video/blog/ai-spokesperson-videos)

## 2. Framing, eyeline, and lower-thirds

- **Camera at eye height, never below.** Eye-level (or slightly above) reads as face-to-face and
  professional; a low camera forces an upward look that reads unprofessional.
  [VidPros](https://vidpros.com/framing-talking-head-videos-best-practices/)
- **Rule of thirds, eyes on the top horizontal line.** For a medium close-up, line the subject's
  eyes/brow at a top-third intersection point, chosen by which way they face.
  [Wave.video](https://wave.video/blog/how-to-frame-a-talking-head/)
- **Leave "looking room"** — roughly two-thirds of horizontal space on the side the presenter
  faces/looks toward; framing them dead-center with no lead space feels cramped.
  [Wave.video](https://wave.video/blog/how-to-frame-a-talking-head/)
- **Headroom: small, not large.** Aim for roughly one-third of frame height as headroom above the
  head — too much or too little reads as unbalanced. [Wave.video](https://wave.video/blog/how-to-frame-a-talking-head/)
- **Reserve lower-third space deliberately.** Frame with the lower third of the shot kept clear
  enough for a name/title card or caption burn-in without crowding the subject.
  [VidPros](https://vidpros.com/framing-talking-head-videos-best-practices/)
- **Neutral, uncluttered background** for any picture-in-picture presenter box — the viewer's
  focus must stay on the screen content, not the presenter's backdrop.
  [Democreator/Wondershare](https://democreator.wondershare.com/screen-recorder/record-picture-in-picture-video.html)

## 3. Presenter + screen picture-in-picture layout

- **Small corner bubble is the default** for software tutorials/demos — bottom-right or
  bottom-left, sized to show presence without blocking screen content.
  [Democreator/Wondershare](https://democreator.wondershare.com/screen-recorder/record-picture-in-picture-video.html)
- **Reserve full-frame or split-screen presenter shots for intros, summaries, and emotional/CTA
  beats** — moments where the face genuinely carries more weight than the screen. Cut back to a
  corner bubble (or off entirely) the instant the UI is the point again.
  [Democreator/Wondershare](https://democreator.wondershare.com/screen-recorder/record-picture-in-picture-video.html)
- **Size the bubble so head+shoulders are legible** — too small and expression reads as noise, too
  large and it obstructs the UI it's supposed to accompany; test the actual composited frame
  before locking a size, don't guess a percentage.
  [Vibrantsnap](https://www.vibrantsnap.com/blog/talking-head-videos-setup-best-practices)
- **Never let the bubble occlude the exact UI element the narration is describing** — a bubble
  parked over the button/field being discussed defeats the screen recording's purpose; reposition
  per-scene, or per shot, whenever the described UI region changes.

## 4. Script cadence for a synthetic (AI-avatar) presenter

- **Keep each spoken segment short — roughly 50 words / ~20 seconds per beat** before cutting to
  the next shot or scene; longer unbroken blocks read as rushed or monotone from a synthetic
  voice. [Pexo](https://pexo.ai/blog/synthesia-tutorial-9367)
- **Write conversational, not nested/clausal, sentences.** Avatar TTS pronunciation engines
  mis-time complex nested clauses; mix short punchy lines with slightly longer explanatory ones to
  keep rhythm rather than monotone delivery. [HeyGen Academy](https://www.heygen.com/academy/scripting)
- **Punctuate for pacing deliberately**, since punctuation is the main lever a script has over a
  synthetic voice's rhythm: commas for short breaths, periods for full stops with downward
  inflection, ellipses or short line breaks where a line needs room to land.
  [HeyGen Academy](https://www.heygen.com/academy/scripting),
  [HeyGen Community](https://community.heygen.com/public/resources/best-practices-for-writing-scripts-better-and-faster-with-ai)
- **Pre-spell or phonetically hint product names, brand terms, and jargon** before rendering —
  unfamiliar names are a known trigger for lip-sync lag (documented up to ~one syllable of drift)
  and mispronunciation; most avatar tools expose a pronunciation/hint field for exactly this.
  (UNCITED to one source — converged practitioner consensus, retrieved 2026-09-12.)
- **Always preview/scrub the rendered line before treating a script as final** — a
  play-before-submit step is standard practice specifically because pacing/emphasis problems are
  far cheaper to catch in a script preview than after a full paid render.
  [HeyGen Help Center](https://help.heygen.com/en/articles/9574152-script-tips)
- **A word-ban or no-numeric-claim rule applies to an avatar's spoken script identically to any
  other narration** — an avatar voice is not an exemption from a copy rule; if a word or claim is
  banned in on-screen text it is banned in what the avatar says too.

## 5. Synthetic-media / avatar disclosure norms and platform policy

**YouTube (OFFICIAL).** YouTube's Altered or Synthetic Content policy requires disclosure whenever
realistic content could be mistaken for something real — explicitly including synthetically
generating a realistic person's voice to narrate a video, and any synthetic presenter/avatar standing in for
a real person. Clearly unrealistic/animated content, and AI used only for production assistance
(scripts, ideas, captions), does NOT require disclosure. The label is applied at upload (Studio →
"Altered or synthetic content" → Yes) and shows in the expanded description by default, with more
prominent on-video placement reserved for sensitive topics (health, news, elections, finance).
YouTube states disclosure does not by itself affect monetization eligibility or recommendations.
[YouTube Blog — official](https://blog.youtube/news-and-events/disclosing-ai-generated-content/),
[minimatters.com 2026 guide](https://minimatters.com/youtube-altered-or-synthetic-content-disclosure/)

**Meta (Facebook/Instagram).** Meta applies an "AI info" label (renamed from "Made with AI" in
2024) automatically whenever an ad or organic post is detected as AI-generated/significantly
AI-edited, including via Meta's own ad-creation AI features (Background Generation, Image
Generation, Add Animation) — no advertiser opt-in required as of the 2026 rollout. This is a
detection-driven, provenance-metadata-based mechanism, not a manual honesty toggle — a synthetic
avatar presenter carries the same provenance-detection risk as a generated still image and should
be assumed labelable unless proven otherwise.
[Meta Transparency Center](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content/),
[MarketingDive](https://www.marketingdive.com/news/sociable-meta-adds-updated-disclosure-tags-for-ai-generated-ads/824833/)

**LinkedIn.** LinkedIn reads C2PA Content Credentials metadata on upload and applies a generic
"cr" watermark/label when present. An avatar-rendered video's exported file should be assumed to
carry equivalent provenance metadata until checked.
[Parliament AI content labelling briefing](https://researchbriefings.files.parliament.uk/documents/CBP-10467/CBP-10467.pdf)

**TikTok.** Combines a manual creator disclosure toggle with automated detection for generative
media; content depicting realistic synthetic people/voices (including "AI filters or avatars that
make people appear to say or do things they didn't") must be disclosed. TikTok states enabling the
AI-content toggle does not itself reduce distribution, provided the content meets guidelines.
[Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/)

**Cross-platform takeaway:** every platform's mechanism above is metadata- or detection-driven, not
a manual honesty check. Verify via the exported file's actual provenance metadata, never a visual
guess — an AI-avatar presenter video file needs the identical check as any other AI-generated
media before it is treated as safe to post publicly; "it's just a talking head, not a generated
photo" is not a reason to skip the check.

## 6. Trust pitfalls specific to presenter/avatar cuts

- **Uncanny valley is a design-and-trust problem, not only a rendering-quality problem** — a
  near-photorealistic avatar with any residual imperfection (motion, blink timing, texture) tends
  to read as *more* off-putting than a more stylized/obviously-synthetic one. Don't chase maximum
  photorealism as an unqualified goal; a slightly more stylized, clearly competent render can trust
  better than a near-miss photoreal one. [arXiv systematic review](https://arxiv.org/pdf/2505.05543),
  [MimicMinds](https://www.mimicminds.com/post/uncanny-valley-explained)
- **Lip-sync drift compounds on jargon/brand terms** — flagged above in §4; the failure mode is a
  syllable or more of visible lag specifically on unfamiliar words, which a generic script rarely
  surfaces until rendered. Budget a scrub pass targeted at every product-specific noun in the
  script, not just a general watch-through.
- **Perceived eeriness measurably degrades credibility judgments** — research on avatar-fronted
  live content found viewers rate a visibly synthetic presenter's credibility, attractiveness, and
  expertise lower than an equivalent real presenter, and one real-world test of an avatar-led
  channel saw engagement drop roughly 40% versus human-presented material once viewers identified
  the delivery as artificial. This is a real audience cost to weigh against the cost/turnaround
  savings — not merely a hypothetical risk.
  [JTAER study](https://doi.org/10.3390/jtaer21050141), aggregated practitioner report
- **Wrong emphasis is a scripting failure surfacing as a delivery failure** — an avatar reading a
  script with no manual emphasis/pause control tends to flatten emphasis uniformly; a script that
  actually needs a beat of emphasis on one word must say so via punctuation/pacing controls (§4),
  never assumed to land correctly by default.
- **Transparency itself can help, not hurt, trust** — at least one line of research found viewers
  told plainly that a presenter was synthetic trusted the content MORE, not less, than an
  ambiguous or undisclosed one — reinforcing that the disclosure requirements in §5 are not purely
  a compliance cost. [arXiv systematic review](https://arxiv.org/pdf/2505.05543)

## 7. Review checklist — specific to a presenter/avatar cut

Run this in addition to (never instead of) the primer's standard viewing-review requirement:

1. **Lip-sync check, twice**: once at normal speed for overall drift, once scrubbed frame-by-frame
   across every product-specific noun/jargon term in the script (the highest-risk drift points).
2. **Motion/blink/texture artifact scan** on the presenter's face and hands across the full
   duration, not just the opening seconds — artifacts often surface mid-clip after a pose change.
3. **Emphasis/pacing listen** with eyes closed — does the vocal emphasis land on the intended word
   in every sentence, or did the render flatten a beat that needed weight?
4. **Framing/occlusion check** on every scene using picture-in-picture — confirm the presenter
   bubble never covers the UI element the narration is currently describing (§3).
5. **Vocabulary/claims scan** of the FINAL spoken script against the company's list, exactly as
   for any other narration — an avatar script is not exempt from a copy rule that governs on-screen text.
6. **Provenance/metadata check on the exported file** before any public post — check the rendered
   video file itself for embedded AI-provenance metadata (C2PA/IPTC digital-source-type markers),
   not just its source assets; sanitize or accept the platform's disclosure label deliberately,
   never by omission.
7. **Platform disclosure decision, made explicitly** — for each target platform (§5), decide and
   record whether this cut requires a synthetic-content disclosure toggle, rather than leaving it
   to the platform's own automated detection to decide unilaterally.

## 8. Cost/turnaround discipline (process rules only — no cost figures as claims)

- **Preview before render.** Every avatar tool exposes a script/audio preview step before
  committing to a paid render — use it every time; a caught pacing or pronunciation problem in
  preview is free, the same problem caught after render is not.
  [HeyGen Help Center](https://help.heygen.com/en/articles/9574152-script-tips)
- **Render once the script is genuinely final**, not iteratively against a moving script — treat
  the avatar render step as a paid/metered generation step: cache-aware (keyed to the actual
  inputs — voice, script text, render settings), never re-triggered by an unrelated change.
- **Batch small wording fixes** into one re-render pass rather than re-rendering after every
  individual tweak — treat each render as a real cost event to be minimized by batching, not a
  free iteration loop.
- **A manual review gate belongs in the workflow before any output goes live**, confirming both
  content correctness and correct disclosure tagging — never auto-publish an avatar render
  straight from generation. [Influencers-Time cost-per-output guide](https://www.influencers-time.com/ai-video-generation-cost-per-output-guide-for-small-agencies/)
- **Do not treat a generic/off-the-shelf avatar and a custom-trained avatar as interchangeable
  cost decisions** — a custom/trained avatar carries meaningfully higher setup cost and lock-in
  than a generic stock avatar; treat which one to use as a deliberate one-time decision recorded
  before first use, not re-litigated per video. [Leadde](https://leadde.ai/blog/best-ai-avatars-for-video-creation),
  [ai-content.agency](https://ai-content.agency/community/ai-avatar-cost-per-minute-2026.html)

## Sources

[HowdyGo](https://www.howdygo.com/blog/product-demo-video-production); [Guideless](https://guideless.ai/blog/best-ai-product-demo-video-tools/); [Demosmith](https://demosmith.ai/blog/best-ai-demo-video-generators-2026); [Increditors](https://increditors.com/video-editing-for-saas-companies-the-complete-guide/); [TechSmith](https://www.techsmith.com/blog/talking-head-videos/); [Piktochart](https://piktochart.com/blog/talking-head-video/); [Democreator/Wondershare](https://democreator.wondershare.com/screen-recorder/record-picture-in-picture-video.html); [Vibrantsnap](https://www.vibrantsnap.com/blog/talking-head-videos-setup-best-practices); [VidPros](https://vidpros.com/framing-talking-head-videos-best-practices/); [Wave.video](https://wave.video/blog/how-to-frame-a-talking-head/); [HeyGen Academy](https://www.heygen.com/academy/scripting); [HeyGen Help Center](https://help.heygen.com/en/articles/9574152-script-tips); [HeyGen Community](https://community.heygen.com/public/resources/best-practices-for-writing-scripts-better-and-faster-with-ai); [Pexo](https://pexo.ai/blog/synthesia-tutorial-9367); [YouTube Blog (official)](https://blog.youtube/news-and-events/disclosing-ai-generated-content/); [minimatters.com](https://minimatters.com/youtube-altered-or-synthetic-content-disclosure/); [Meta Transparency Center](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content/); [MarketingDive](https://www.marketingdive.com/news/sociable-meta-adds-updated-disclosure-tags-for-ai-generated-ads/824833/); [UK Parliament AI labelling briefing](https://researchbriefings.files.parliament.uk/documents/CBP-10467/CBP-10467.pdf); [Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/); [arXiv (uncanny valley/trust review)](https://arxiv.org/pdf/2505.05543); [MimicMinds](https://www.mimicminds.com/post/uncanny-valley-explained); [JTAER](https://doi.org/10.3390/jtaer21050141); [Storyteller Videos](https://www.storytellervideos.com/blog/what-every-marketer-should-know-before-producing-ai-avatar-videos); [GueauxStudio](https://gueauxstudio.com/blog/fake-smile-problem-ai-generated-testimonials-backfiring); [Viralix](https://viralix.video/blog/ai-spokesperson-videos); [Leadde](https://leadde.ai/blog/best-ai-avatars-for-video-creation); [ai-content.agency](https://ai-content.agency/community/ai-avatar-cost-per-minute-2026.html); [Influencers-Time](https://www.influencers-time.com/ai-video-generation-cost-per-output-guide-for-small-agencies/).

Retrieval date for all sources above: 2026-09-12.
