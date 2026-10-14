# Short-Form Vertical Video — Specs, Hooks, Captions, Repurposing, Cadence

Terse, worker-applicable rules for YouTube Shorts, Instagram Reels, TikTok, and Facebook Reels.
All figures are aggregated from third-party creator-tool guides current as of retrieval date
2026-09-12 unless marked with one of these confidence flags: **OFFICIAL** (platform-published and
independently verified), **UNREACHABLE** (a cited platform page that returns only a title/could not
be fetched — treated as could-not-verify, never as confirmed fact), **UNCONFIRMED-PRIMARY** (a
platform-attributed claim from a secondary source with no primary confirmation found), or
**UNCITED** (practitioner consensus, no single authoritative source found). Numeric safe-zone pixel
values vary source-to-source by design differences in each guide's own template — treat them as
directional, not exact, and always test on-device before shipping a template.

## Hard constraints (cross-company craft rules — never contradict the primer)

Vocabulary and claims restrictions (banned terms, numeric-claims restriction) are per-company, not
universal: follow the company pack's `claims_policy` and that company's video-producer dossier;
where neither states them, declare DEGRADED rather than inventing or assuming a
vocabulary rule (see `INDEX.md`'s precedence note for the full statement of this fallback chain).
The rules below are cross-company craft rules that hold regardless of company, restating the
primer's own cross-company hard rules that bear specifically on short-form vertical work — the
primer's text is the one that actually governs on any conflict:

- Every cut opens on the product itself (**product-first opens** — primer §2, "never open on
  generic footage"; primer §8 item c) — a cut never opens on b-roll.
- B-roll only after a human/agent has actually viewed the candidate frames — never selected by
  stock-site tag/description alone.
- B-roll ≤2.5 s per shot.
- B-roll ≤20% of total runtime.
- Never two b-roll shots consecutively.
- No b-roll starts before the 3.0 s mark of the video.
- No PII on screen — seeded demo-tenant data only.
- No loading screens, spinners, or blank/skeleton frames.
- Screen recordings follow a purposeful task flow, never "clicking around."
- Any phone-format deliverable showing app UI is captured natively at a real phone viewport
  (primer §4) — never a desktop crop.
- Viewing review before any upload: the rendered cut is watched per shot against the timed
  transcript (primer §4/§7); the seat's own frame-viewing review satisfies it.
- A per-shot viewing review (primer §7/§7a, including the `capture_mode` field for any phone-format
  cut) before any upload — no upload skips this step.

## Universal canvas (all four platforms converge here)

- Target one master export: **1080×1920 px, 9:16, H.264 MP4, AAC audio, 30 fps** (60 fps only for
  genuinely high-motion footage). This single file is the safe common denominator for YouTube
  Shorts, Instagram Reels, TikTok, and Facebook Reels — cross-post the same export, don't
  re-render per platform, unless a platform-specific safe-zone conflict forces a re-crop.
  [Hopper HQ](https://www.hopperhq.com/blog/youtube-shorts-dimensions/),
  [Fliki](https://fliki.ai/blog/instagram-reel-dimensions-and-size-guide),
  [AdManage.ai](https://admanage.ai/blog/tiktok-ad-specs),
  [sendshort.ai](https://sendshort.ai/guides/facebook-reels-size/)
- Minimum acceptable resolution 720p; **1080×1920 is the practical floor for 2026** — anything
  lower gets visibly soft after platform re-compression.
  [Meta Business Help Center — Instagram Stories ads design requirements](https://www.facebook.com/business/help/2222978001316177)
  (cited as minimum resolution 720p, minimum 30 fps, for Reels-class placements — **UNREACHABLE**:
  this fetch returns only the page title, not the body, consistent with a login-walled or
  JS-rendered Meta help page; could not be independently verified. Treat as could-not-verify, not
  as confirmed official fact, until a reachable copy of this or an equivalent Meta help page is
  found.)
- Upload bitrate: aim 10–12 Mbps minimum for 1080p; some creator guides push 20–35 Mbps on strong
  Wi-Fi since every platform re-compresses on ingest regardless. Don't upload 4K — it wastes
  bitrate budget and can look worse after re-encode than a clean 1080p source.
  [TikTok Creative Center discovery pages, aggregated](https://www.tiktok.com/discover/what-is-video-bitrate)
  (UNCITED beyond TikTok's own community-sourced "discover" pages — treat bitrate specifics as
  practitioner consensus, not an official spec page)
- Audio: AAC, 256 kbps target. Never ship silent-only audio with no caption track — most short-form
  is watched muted.
  [AdManage.ai](https://admanage.ai/blog/tiktok-ad-specs)
- File size ceilings vary widely by platform and upload path (mobile app vs. desktop studio) —
  always check the current in-app limit before a bulk upload; do not hardcode a byte ceiling into
  automation.

## YouTube Shorts

- Canvas: 1080×1920, 9:16. Max upload resolution 1080p.
  [Hopper HQ](https://www.hopperhq.com/blog/youtube-shorts-dimensions/)
- Duration: up to 3 minutes (extended from the earlier 60 s cap via the multi-segment camera).
  [YouTube Help Center — Shorts creation](https://support.google.com/youtube/answer/10059070)
  (OFFICIAL — duration and 1080p max only; YouTube's own help page does not publish exact safe-zone
  pixel guidance, so all safe-zone numbers below are third-party estimates)
- Safe zone: design against the spec sheet figure as the number of record
  (`video_production_kb_social_2026_09_12.md`, YouTube Shorts row): the **bottom third of the frame (~640 px of
  a 1920 px-tall canvas) is covered** by title/channel/like/comment/share icons on mobile — keep
  key text/UI in the center-safe area above that band. Third-party guides below give a
  less-conservative bottom figure (~380 px) that this file previously stated as the practical
  default — that number risks placing content inside the actual bottom-third overlay the spec sheet
  names; treat it as a secondary, looser estimate. Third-party estimates for the full safe rectangle:
  roughly **900×1350 px to 1080×1420 px**, with some guides recommending as tight as 900×1160 px, and
  a **90 px side clearance** as a conservative default for the sides specifically (the spec sheet
  gives no separate side figure).
  [postlinkapp](https://postlinkapp.com/blog/youtube-shorts-size-and-dimensions),
  [youtubetoolkit](https://youtubetoolkit.com/blog/youtube-shorts-dimensions) ([Kreatli](https://kreatli.com/guides/youtube-shorts-safe-zone)
  is qualitative-only — it restates the 1080×1920/9:16 spec with no pixel safe-zone numbers of its
  own and defers to an external checker tool).
- The Shorts UI overlays: channel name/subscribe button, like/comment/share/remix rail (right
  edge), and title text (bottom) — all in the outer ~10–15% margin (UNCITED — consistent with, but
  not independently sourced beyond, the safe-zone guides above; treat as a rough synthesis, not a
  separately-verified figure). Center your subject.
- Posting windows (practitioner data, not official): 12–3 PM and 5–8 PM local audience time;
  Sunday ~10 AM is frequently cited as a top single slot.
  [Socialync](https://www.socialync.io/blog/best-time-to-post-tiktok-instagram-youtube),
  [FlowShorts](https://flowshorts.app/tools/best-time-to-post)

## Instagram Reels

- Canvas: 1080×1920, 9:16 (Meta officially supports 1.91:1 through 9:16; 9:16 is the recommended
  full-screen spec).
  [Meta Business Help Center](https://www.facebook.com/business/help/2222978001316177)
  (**UNREACHABLE** — this fetch returns only the page title, not the body; could not be
  independently verified. This aspect-ratio range is standard Reels knowledge repeated across many
  secondary sources, so treat the range itself as likely correct, but the citation is not verified
  official confirmation.)
- Minimum spec: 30 fps minimum, 720p minimum resolution, per the same **UNREACHABLE** citation
  above — could not independently verify.
- Duration: sources disagree on the current maximum upload length (figures found range from 3
  minutes to 15 minutes to 20 minutes depending on account type/region/upload method) and this
  file's own research pass found no single reachable Instagram/Meta help page settling it —
  **UNCITED/UNVERIFIED for an exact maximum; do not treat any one of these numbers as confirmed.**
  The platform spec sheet's Instagram Reels row now flags its maximum as UNCITED/UNVERIFIED too
  (corrected 2026-09-28). What IS consistent
  across sources (**UNCONFIRMED-PRIMARY** — a Meta-attributed recommendation repeated by multiple
  secondary sources with no primary Meta page found stating it directly): Meta recommends against
  Reels over ~3 minutes for reaching new (non-follower) audiences regardless of the technical cap.
  Practical creative ceiling for cold-audience reach: 90 seconds (**UNCITED** — no source in this
  file's research pass states this 90-second figure directly; treat as a practitioner-consensus
  synthesis of the surrounding completion-rate data, not an independently sourced number);
  most-viral window is much shorter.
  [postfa.st](https://postfa.st/sizes/instagram/reels) (states 20 minutes; not independently
  confirmed against a primary source)
- Ideal length for completion rate (**a 50-Reel single-account test — 10 Reels per length cohort on
  one 11,200-follower account, not a broad industry sample**): **7–15 s for entertainment-style
  content, 15–30 s for tutorial/educational**. Measured completion by length in that test: 7 s →
  ~94%, 15 s → ~78%, 30 s → ~56%, 60 s → ~41%, 90 s → ~29%. Given the small, single-account
  methodology, treat exact percentages as weak evidence, not a universal law — but the
  monotonic decay with length is a safe planning assumption.
  [CreatorHouse](https://creatorhouse.app/blog/instagram-reel-length-2026-test),
  [Moonb](https://www.moonb.io/blog/instagram-reel-length)
- **Safe zone — use the reconciled Meta Reels figure from the source of record
  (`video_production_kb_social_2026_09_12.md`, Instagram Reels row): top ~14%, bottom ~35%, sides ~6% of frame
  kept clear of text/logo/key creative** (for a 1080×1920 frame: roughly top 270px, bottom 670px,
  sides ~65px). **Provenance:** the spec sheet's own source note for this figure says the
  underlying Meta Business Help Center page fetch **timed out** and the percentages were taken from
  a **search-result excerpt**, not a directly-read primary page — and the spec sheet's own citation
  URL (`facebook.com/business/help/980593475366490/`, "About text overlays and the Safe Zone for ads
  in Stories and Reels") differs from the URL cited elsewhere in this file
  (`facebook.com/business/help/2222978001316177`). Both Meta URLs return only a page title when
  fetched directly — **neither is independently verifiable**; treat the 14%/35%/6% figure as the
  best available estimate, sourced from a search excerpt of an unreachable Meta page, not as
  confirmed primary fact.
  **This figure is NOT uniformly more conservative than the third-party estimate below — it is
  more conservative on top and bottom, but LESS conservative on the right edge:** 6% of 1080px is
  ~65px, while syllaby.io's independently-verified right-edge figure is **130px (~12% of a
  1080px-wide frame)** — wider than 65px. Use the Meta figure for top/bottom clearance, and a
  separate **right-edge clearance rule of max(6% of frame width, 130px)** — 130px on a 1080-wide
  frame. syllaby.io states "keep graphics 130 pixels away from the right edge and 60 pixels away
  from the left edge"; on the right edge that is the more conservative of the two figures, so it is
  the one adopted. Design-relevant UI (like/comment/share icons, profile link) commonly sits in that
  action rail on Reels-class placements, and the narrower 65px figure alone risks captions sitting
  inside it.
  [syllaby.io](https://syllaby.io/blog/aspect-ratios-safe-zones-shorts-reels-tiktok/), retrieved
  2026-09-12, re-verified 2026-09-27.
- Cover image: Instagram's stated cover crop is 420×654 px (≈1:1.55); upload the cover at full
  1080×1920 for a sharp downsample rather than pre-cropping to 420×654.
  [Somake AI](https://www.somake.ai/blog/instagram-reel-size-guide)
- Posting windows (practitioner data): Tue–Thu 10 AM–3 PM local; Reels specifically skew well at
  9 AM–12 PM weekdays.
  [Sendible](https://www.sendible.com/insights/best-time-to-upload-reels-on-instagram),
  [Metricool](https://metricool.com/best-time-to-post-social-networks/)

## TikTok

- Canvas: 1080×1920, 9:16, MP4/H.264 + AAC audio. 30 fps standard; 60 fps for genuinely
  high-motion footage only.
  [AdManage.ai](https://admanage.ai/blog/tiktok-ad-specs)
- File size: no source in this file's research pass states a specific mobile-app upload ceiling
  with confidence (an earlier draft of this file stated ~287.6 MB with no source found for it
  directly — removed rather than kept as an unsourced number). Desktop/web upload via TikTok Studio
  is 500 MB standard, up to 10 GB for some eligible accounts
  [flowshorts.app](https://flowshorts.app/blog/how-long-can-tiktok-be). Always verify current limits
  in-app before batch-uploading, as these move often and this file found no reliable mobile-specific
  figure to cite.
- Duration: app-record cap 10 minutes; pre-recorded upload cap up to 60 minutes. Neither is a
  creative target — see length guidance below.
  [flowshorts.app](https://flowshorts.app/blog/how-long-can-tiktok-be)
- Ideal creative length (practitioner consensus, two sources in rough agreement): **21–34 s**
  ([Sociality.io](https://sociality.io/blog/tiktok-video-length/)) to **24–38 s** ("Viral Sweet
  Spot," [Joyspace](https://joyspace.ai/ideal-video-length-social-platform-2026)) as the general
  completion-rate/virality sweet spot, up to **60–90 s for talking-head/educational** content that
  needs to deliver real substance. TikTok's own ranking signal weighs completion rate heavily — the
  right length is "long enough to deliver the promised value, no longer."
- Safe zone: design against the spec-sheet figures as the number of record
  (`video_production_kb_social_2026_09_12.md`, TikTok row, itself flagged there as practitioner
  consensus pending direct TikTok-for-Business confirmation, not OFFICIAL) for **top and bottom**:
  **top ~130 px clear, bottom ~440 px clear.** [Quso.ai](https://quso.ai/blog/tiktok-dimensions)
  states bottom 270 px and right 100 px, with **no top-bar figure at all**;
  [Kreatli](https://kreatli.com/guides/tiktok-safe-zone) gives only a general 1080×1420 px
  text-safe rectangle with **no per-edge pixel breakdown**. Quso's 270 px bottom figure is ~170 px
  LESS conservative than the spec sheet's ~440 px (design against the spec sheet's ~440 px, not
  Quso's 270 px, or captions risk landing under TikTok's caption/CTA block). For the **right edge**,
  use a clearance of **max(44 px, ~100 px)** — i.e. Quso's 100 px, since 100 px is MORE
  conservative than the spec sheet's 44 px, the same max()-of-the-more-conservative-figure rule
  used for Meta placements above; never design to the narrower 44 px alone on that edge. **A precise
  top-bar clearance figure beyond the spec sheet's own practitioner-consensus ~130 px is
  UNCITED/UNVERIFIED — no source found states one independently.**
- Posting windows (practitioner data): 7–9 AM, 12–2 PM, 7–11 PM in the audience's local timezone;
  Sunday 9 AM and 1 PM also cited as strong.
  [Socialync](https://www.socialync.io/blog/best-time-to-post-tiktok-instagram-youtube)
- Frequency: accounts posting 2–5×/week saw up to ~17% more views per post than sparser posters;
  11+/week saw up to ~34% more in one aggregated dataset — read as "more consistent posting
  compounds," not as a guarantee at any specific number.
  [posteverywhere.ai](https://posteverywhere.ai/blog/how-often-to-post-on-social-media)

## Facebook Reels

- Canvas: identical to Instagram Reels — 1080×1920, 9:16. Same master file works for both without
  re-export.
  [socialrails](https://socialrails.com/sizes/facebook/reels)
- Duration: Meta officially removed Facebook Reels' length/format restrictions as part of folding
  all Facebook video into Reels in June 2025 — "Reels on Facebook will also not have any length or
  format restrictions" (OFFICIAL: [about.fb.com — Making it Easier to Create Videos on
  Facebook](https://about.fb.com/news/2025/06/making-it-easier-create-videos-facebook/), retrieved
  2026-09-27). There is therefore **no platform duration cap to cite** — any earlier "up to 90
  seconds" figure in this file was a stale pre-2025 platform limit, not a current one. Treat
  60–90s as a practitioner creative TARGET for cold-audience reach (matching the Instagram Reels
  guidance above), never a platform-imposed ceiling.
- **Safe zone — same figure used for Instagram Reels above (top ~14%, bottom ~35%, sides ~6%;
  spec sheet's Facebook video/Reels row, same unreachable/search-excerpt provenance as the Instagram Reels section
  above — treat as best-available estimate, not confirmed primary fact), with the same
  top/bottom-vs-right-edge split: this figure is more conservative than the third-party guides
  below on top/bottom, but its ~65px sides figure (6% of 1080px) is LESS conservative than their
  right-edge estimates — use the same max(6%, 130px) right-edge rule given for Instagram Reels.**
  Third-party guides below gave a wider, inconsistent range — top ~210–270px, bottom ~290–670px,
  right ~65–120px. Design against the spec sheet's figure for top/bottom (its bottom figure is the
  more conservative of the two), and against the 130px right-edge rule, which is wider than every
  right-edge figure in that range.
  [1clickreport](https://www.1clickreport.com/blog/meta-ads-creative-safe-zones-2026-guide),
  [lucidmedia](https://www.lucidmedia.co.nz/blog/instagram-facebook-ad-safe-zones-2026/)
- **UNCONFIRMED-PRIMARY: whether Stories and Reels now share one unified 9:16 safe zone.** One
  source reports a March 2026 Meta update unifying the two placements' safe zone so one creative
  satisfies both without a separate re-crop pass, but attributes this to Meta without linking a
  primary Meta changelog, and it could not be independently verified against one at retrieval time.
  Treat the two placements as needing an independent safe-zone check until a primary Meta source is
  found, rather than assuming the unification.
  [billo.app](https://billo.app/blog/meta-ads-safe-zones/) (UNCONFIRMED-PRIMARY — Meta-attributed
  claim, no primary source found)

## Hooks (first 1–3 seconds)

- The first 3 seconds decide retention on every one of these platforms — one aggregated dataset
  puts the split-decision point at 65% of viewers deciding to stay or scroll within 3 s.
  [go-viral.app](https://www.go-viral.app/blog/hook-first-3-seconds/)
- Retention-to-reach relationship (one dataset, TikTok-specific but treated as directionally true
  across all four platforms in this file, since each short-form algorithm weights completion rate):
  videos holding 70–85% of viewers through the first 3 s got ~2.2× the total views of
  lower-retention videos;
  below ~60% early retention, algorithmic distribution drops sharply.
  [TTS Vibes](https://insights.ttsvibes.com/tiktok-first-3-seconds-hook-retention-rate/),
  [HypeNest](https://hypenest.ai/blogs/tiktok-algorithm-2026-video-hooks-retention)
- Deliver the core value proposition or payoff signal inside the first 3 seconds — don't save it
  for a slow build. **UNCONFIRMED-PRIMARY** (TikTok-attributed figure from a secondary source, no
  primary TikTok confirmation found): one report states 63% of top-performing ads state their core
  message or brand signal within the first 3 s.
  [Hansen Insights](https://hansencommerce.com/insights-tiktok-hook-3-seconds)
- Combine a **visual pattern interrupt** (unexpected first frame, direct eye contact, on-screen
  bold-claim text) with a **verbal/textual hook** delivered simultaneously — audio-only or
  visual-only hooks underperform hooks that fire on both channels at once.
  [Opus.pro](https://www.opus.pro/blog/tiktok-hook-formulas)
- Working hook shapes (practitioner templates, UNCITED beyond aggregator blog consensus):
  - Bold claim / surprising result stated flat, no windup.
  - Direct question that opens a curiosity gap the viewer must watch to close.
  - Visual interrupt — motion, unexpected object, or a mid-action first frame instead of a static
    intro card.
  - Social-proof lead ("X people already...") — use only when the claim is real and unembellished;
    never a fabricated number.
  [faceless.so](https://faceless.so/blog/17-hook-formulas-for-short-video-retention),
  [vexub.com](https://vexub.com/blog/viral-short-form-video-hooks)
- **The primer's cross-company hard rules override all of the above:** the hook must still open on
  the product itself (product-first open, no b-roll before 3.0 s — primer §4/§8c) — never a
  bold-claim card, a logo sting, or b-roll before the product is shown. On top of that cross-company
  floor, apply the company's own vocabulary/claims restrictions per the Hard constraints section
  above (its own `claims_policy`/dossier/DEGRADED fallback chain) — a company with a no-numeric-claims
  rule needs a hook shape that avoids numbers (a bold claim about outcome stated qualitatively, or a
  direct question) shown over real product footage; a company with no such restriction may use a
  real, unembellished number. **For a company with no software product** (a local-service business
  — see `INDEX.md`'s local-service routing row), read "product" in "product-first open" as the
  company's delivered work or service as that company's own pack/dossier defines it — the
  provisional reading the primer §4 states. **This reading is provisional** — no operator ruling or
  settled doctrine defines it yet (see `INDEX.md`'s "Known gap" note); state that it is provisional
  in any dispatch that relies on it.

## Captions

- Burn captions into the video (open captions) for short-form feeds — there is no reliable way to
  attach a toggleable .srt on TikTok/Reels/Shorts feed placements, platform auto-captions are
  inconsistent in styling and timing accuracy, and most short-form is watched muted so the words
  must be visible the instant the clip starts.
  [Tapescribe](https://tapescribe.com/blog/video-captions-best-practices-2026),
  [BOIA (accessibility)](https://www.boia.org/blog/how-do-burned-in-captions-affect-accessibility)
- Accessibility trade-off: burned-in (open) captions are not machine-readable by screen readers or
  assistive tools the way closed captions are. Best practice is to produce **both**: an SRT/VTT
  track for accessibility, search, and any platform (e.g. YouTube long-form) that supports real
  closed captions, plus a burned-in version for the vertical feed cut.
  [BOIA](https://www.boia.org/blog/how-do-burned-in-captions-affect-accessibility)
- Never rely on raw auto-generated captions without human review — auto-caption accuracy is not
  sufficient for accessibility compliance on its own.
  [Captions.ai](https://captions.ai/blog/how-to-add-auto-captions-to-videos-tips-tools)
- Font size: **minimum 44px body caption on a 1080-wide vertical frame** (the floor stated in
  `mobile_app_demo.md` §6 — cite-once), up to ~60px for emphasis words — viewers are at arm's length
  on a phone screen. Third-party guides quote a 36–48px range; the lower part of that range is below
  this KB's floor and is not used.
  [vsubtitle.com](https://vsubtitle.com/subtitle-font-size-and-reading-speed-2026/),
  [reelwords.ai](https://reelwords.ai/blog/best-fonts-for-captions)
- Font choice: bold geometric sans-serif (Montserrat, Poppins, Inter, Roboto, SF Pro, Helvetica-
  class). Avoid thin weights, scripts, or serif faces — they lose legibility at small size and at
  the frame rates typical of fast cuts.
  [socaptions.com](https://socaptions.com/blog/best-fonts-for-subtitles)
- Contrast: bold text plus a high-contrast outline or drop shadow (or a background pill) — outline
  is the most dependable choice against variable/busy backgrounds; a solid background pill is most
  dependable when absolute clarity matters more than aesthetics.
  [overlaytext.com](https://overlaytext.com/blog/text-overlay-for-reels-tiktok-viral-templates)
- Keep one consistent caption style across all four platforms for brand recognition — vary only
  size/placement to respect each platform's own safe zone (see per-platform sections above).
- Always test caption legibility on an actual phone screen at arm's length — desktop preview
  reliably overstates legibility.
  [emax.studio](https://emax.studio/blog/best-caption-fonts-for-ai-reels-2026)

## Repurposing a landscape master into vertical cuts

**Scope (operator ruling 2026-09-14 — read before anything below): these techniques apply ONLY to
non-app footage — a frame with no product/app UI visible on screen, including no device screen
displaying the app: an end card, pure b-roll, or a presenter/brand slate (the primer §7a
`capture_mode: "not_applicable"` definition — cited as the single source for what counts as
non-app footage, rather than restating a separately-worded list here that could drift from it). Any
frame that shows the product's UI in a phone-format deliverable (Reels, Stories, Shorts, any 9:16
app cut) is recorded NATIVELY in the product's mobile/responsive layout at a real phone viewport —
the product's own mobile-emulation recorder, as named in that product's video-producer dossier, and see
`mobile_app_demo.md` §4 and the video-producer primer's hard rules — never produced by cropping,
panning or letterboxing a desktop capture. Operator, verbatim: "it needs to be in the phone app or
the phone version of the application, not just cropped to fit the phone. It should actually be
exactly the way that it would look if they were on their phone. That's the whole point. and it
will help us find issues with the phone version of the application as we record these videos." A
2026-09-14 incident — a phone-format reel shipped as a 9:16 crop of a desktop capture because this
file was the primary source loaded for a Reels cut — is why a desktop-UI frame in a phone-format
cut is now a per-shot viewing-review FAIL. (A given product's own incident/issue number lives in
that company's own `<home>/.claude/oversight/video-producer.md` dossier, never here — this KB serves
every company the GTM seat operates for.)**

**Post-incident reinforcement (2026-09-15):** that incident's record shows a reviewer can read this
section's own crop/pan/letterbox techniques as generally-applicable craft and apply them to app-UI
footage by default, because nothing at the point of use forced a check of WHICH kind of footage was
in front of it. The runtime primer now requires an explicit per-shot capture-mode question, asked
before any content question, with a FAIL condition that stands even when content is otherwise
correct (primer §7/§7a) — read that before applying any technique below to a shot that might show
app UI. **If you are not certain a shot is non-app footage, it is not in scope for this section.**

- Three standard techniques for NON-APP footage, in order of typical quality-for-effort:
  1. **Static center crop to 9:16** — simplest, fastest, but loses both side margins of a 16:9
     frame; fine only when the subject stays centered and static throughout the shot.
  2. **AI/subject-tracking reframe** — dynamically follows the speaker/subject/motion so the crop
     window pans within the source frame instead of using one fixed crop; strictly better than a
     static crop whenever anyone in the shot moves or when there are multiple points of interest.
  3. **Padded/blurred-background fill** — keeps the full 16:9 frame visible letterboxed inside a
     9:16 canvas, filling the top/bottom bars with a blurred/extended version of the same footage;
     avoids losing any original framing at the cost of a smaller effective subject size.
  [Descript](https://www.descript.com/blog/article/how-to-make-horizontal-video-vertical),
  [VideoProc](https://www.videoproc.com/video-editor/how-to-make-horizontal-video-vertical.htm)
- For any shot with significant subject or camera movement, cut it into multiple shorter scenes
  and re-track/re-crop per scene rather than trying to hold one crop window across the whole shot.
  [Socialive support](https://support.socialive.us/support/solutions/articles/67000741606-guide-to-repurposing-from-landscape-to-vertical-video)
- Re-verify safe-zone placement AFTER reframing, not before — a crop or pan that looked centered
  in the 16:9 source can push a subject's face or key on-screen text into a platform's UI-overlay
  band once cropped to 9:16.
- When repurposing one landscape master into multiple platform cuts, cut hook and pacing per
  platform (see length guidance above) rather than shipping one identical cut everywhere — a
  25 s TikTok-paced edit and a 60 s YouTube Shorts edit of the same source material will retain
  differently even on the same footage.
- **The primer's b-roll hard rules apply identically to repurposed cuts**: any inserted
  secondary footage (b-roll) in a repurposed edit still obeys ≤2.5 s/shot, ≤20% of runtime, never
  two in a row, none before 3.0 s — reframing the master does not reset or relax these limits.

## Posting cadence (cross-platform synthesis)

- Consistency compounds: see the TikTok section's Frequency bullet above for the cited figures
  (2–5×/week vs. 11+/week view-count deltas) — treat as "more consistent" evidence, not a fixed
  target to hit mechanically, and not re-cited here to avoid stating the same figure twice.
- Suggested minimum viable cadence for a small/lean operation (UNCITED, practitioner-consensus
  synthesis of the above): 2–3 short-form posts/week sustained beats occasional bursts followed by
  silence — algorithms on all four platforms in this file appear to reward accounts with a steady
  recent posting history over one-off virality attempts.
- Best local-time posting windows are stated once each, in their own platform section above
  (TikTok's Posting windows bullet, Instagram Reels' Posting windows bullet, YouTube Shorts'
  Posting windows bullet) — not restated here. Facebook Reels has no distinct authoritative window
  found separate from general Facebook video guidance; default to the Instagram Reels windows given
  the shared Meta backend and identical creative spec.
- These windows are averages across large aggregated account samples — a worker agent should treat
  them as a reasonable default schedule only, and defer to the company's own audience analytics
  (its pack metrics / scoreboard) once any exist, rather than treating third-party benchmark
  windows as authoritative forever.
- Cross-platform coordination: when posting the same repurposed cut to multiple platforms, stagger
  rather than simultaneously blast — but no source found gives a specific recommended stagger
  interval; treat same-day posting across platforms as acceptable absent contrary data (UNCITED).

## Sources

- [YouTube Shorts Dimensions & Size Guide (2026) — Hopper HQ](https://www.hopperhq.com/blog/youtube-shorts-dimensions/) — retrieved 2026-09-12
- [YouTube Shorts Safe Zone — Kreatli](https://kreatli.com/guides/youtube-shorts-safe-zone) — retrieved 2026-09-12 (qualitative-only, see inline note)
- [TikTok Creative Center — video bitrate discussion](https://www.tiktok.com/discover/what-is-video-bitrate) — retrieved 2026-09-12, cited inline in "Universal canvas" above; flagged there as UNCITED beyond this one community-sourced "discover" page — no separate official bitrate spec page was found to corroborate it
- [YouTube Shorts Size 2026 — postlinkapp](https://postlinkapp.com/blog/youtube-shorts-size-and-dimensions) — retrieved 2026-09-12
- [YouTube Shorts Dimensions Safe Zone Pixel Map — youtubetoolkit](https://youtubetoolkit.com/blog/youtube-shorts-dimensions) — retrieved 2026-09-12
- [YouTube Help Center — Shorts creation (OFFICIAL)](https://support.google.com/youtube/answer/10059070) — retrieved 2026-09-12
- [Instagram Reels Dimensions and Size Guide (2026) — Fliki](https://fliki.ai/blog/instagram-reel-dimensions-and-size-guide) — retrieved 2026-09-12
- [Instagram Safe Zone Guide — Outfy](https://www.outfy.com/blog/instagram-safe-zone/) — retrieved 2026-09-12
- [Aspect ratios and safe zones for Shorts, Reels and TikTok — syllaby.io](https://syllaby.io/blog/aspect-ratios-safe-zones-shorts-reels-tiktok/) — retrieved 2026-09-12, re-verified 2026-09-27 (source of the 130px right-edge figure)
- [Instagram Safe Zone Sizes Guide 2026 — CampaignSwift](https://campaignswift.com/blog/instagram-safe-zone-sizes) — retrieved 2026-09-12
- [Instagram Reel Size Guide 2026 — Somake AI](https://www.somake.ai/blog/instagram-reel-size-guide) — retrieved 2026-09-12
- [Meta Business Help Center — Instagram Stories ads design requirements](https://www.facebook.com/business/help/2222978001316177) — retrieved 2026-09-12, re-checked 2026-09-27 (**UNREACHABLE** — fetch returns only the page title, not the body; not independently verified; see inline notes)
- [Instagram Reels Size — postfa.st](https://postfa.st/sizes/instagram/reels) — retrieved 2026-09-12
- [Making it Easier to Create Videos on Facebook — Meta Newsroom (OFFICIAL)](https://about.fb.com/news/2025/06/making-it-easier-create-videos-facebook/) — retrieved 2026-09-27
- [TikTok Ad Specs 2026 — AdManage.ai](https://admanage.ai/blog/tiktok-ad-specs) — retrieved 2026-09-12
- [TikTok Dimensions 2026 Safe Zone Guide — Quso.ai](https://quso.ai/blog/tiktok-dimensions) — retrieved 2026-09-12
- [TikTok Safe Zone (2026) — Kreatli](https://kreatli.com/guides/tiktok-safe-zone) — retrieved 2026-09-12
- [TikTok video length guide for 2026 — Sociality.io](https://sociality.io/blog/tiktok-video-length/) — retrieved 2026-09-12
- [Ideal Video Length for TikTok, Reels & YouTube Shorts 2026 — Joyspace](https://joyspace.ai/ideal-video-length-social-platform-2026) — retrieved 2026-09-12
- [TikTok Video Length Limits 2026 — flowshorts.app](https://flowshorts.app/blog/how-long-can-tiktok-be) — retrieved 2026-09-12
- [Facebook Reels: Dimensions & Size Guide (2026) — sendshort.ai](https://sendshort.ai/guides/facebook-reels-size/) — retrieved 2026-09-12
- [Facebook Reels Size — socialrails](https://socialrails.com/sizes/facebook/reels) — retrieved 2026-09-12
- [Meta Ads Safe Zones 2026 — 1clickreport](https://www.1clickreport.com/blog/meta-ads-creative-safe-zones-2026-guide) — retrieved 2026-09-12
- [Instagram & Facebook Ad Safe Zones 2026 — lucidmedia](https://www.lucidmedia.co.nz/blog/instagram-facebook-ad-safe-zones-2026/) — retrieved 2026-09-12
- [Meta Ads Safe Zones: 2026 Unified Creative Updates — billo.app](https://billo.app/blog/meta-ads-safe-zones/) — retrieved 2026-09-12
- [TikTok Hook Formulas That Drive 3-Second Holds — Opus.pro](https://www.opus.pro/blog/tiktok-hook-formulas) — retrieved 2026-09-12
- [TikTok First 3 Seconds Hook Retention Rate Statistics — TTS Vibes](https://insights.ttsvibes.com/tiktok-first-3-seconds-hook-retention-rate/) — retrieved 2026-09-12
- [TikTok Algorithm 2026: 7 Hooks for Retention — HypeNest](https://hypenest.ai/blogs/tiktok-algorithm-2026-video-hooks-retention) — retrieved 2026-09-12
- [The First 3 Seconds — go-viral.app](https://www.go-viral.app/blog/hook-first-3-seconds/) — retrieved 2026-09-12
- [The 3-Second Hook: Why TikTok Videos Win or Die in 2026 — Hansen Insights](https://hansencommerce.com/insights-tiktok-hook-3-seconds) — retrieved 2026-09-12
- [17 Hook Formulas for Short Video Retention — faceless.so](https://faceless.so/blog/17-hook-formulas-for-short-video-retention) — retrieved 2026-09-12
- [25 Viral Hook Formulas — vexub.com](https://vexub.com/blog/viral-short-form-video-hooks) — retrieved 2026-09-12
- [How Burned-In Captions Affect Accessibility — BOIA](https://www.boia.org/blog/how-do-burned-in-captions-affect-accessibility) — retrieved 2026-09-12
- [How to Add Captions to Videos: Best Practices 2026 — Tapescribe](https://tapescribe.com/blog/video-captions-best-practices-2026) — retrieved 2026-09-12
- [How to Add Auto-Captions to Videos — Captions.ai](https://captions.ai/blog/how-to-add-auto-captions-to-videos-tips-tools) — retrieved 2026-09-12
- [Best Fonts for Captions — reelwords.ai](https://reelwords.ai/blog/best-fonts-for-captions) — retrieved 2026-09-12
- [Best fonts for subtitles — socaptions.com](https://socaptions.com/blog/best-fonts-for-subtitles) — retrieved 2026-09-12
- [The Science of Readability: Subtitle Font Size & Speed 2026 — vsubtitle.com](https://vsubtitle.com/subtitle-font-size-and-reading-speed-2026/) — retrieved 2026-09-12
- [Text Overlay Styles for Reels and TikTok — overlaytext.com](https://overlaytext.com/blog/text-overlay-for-reels-tiktok-viral-templates) — retrieved 2026-09-12
- [Best Caption Fonts for AI Reels 2026 — emax.studio](https://emax.studio/blog/best-caption-fonts-for-ai-reels-2026) — retrieved 2026-09-12
- [How to Make a Horizontal Video Vertical for Reels — Descript](https://www.descript.com/blog/article/how-to-make-horizontal-video-vertical) — retrieved 2026-09-12
- [Guide to repurposing from landscape to vertical video — Socialive](https://support.socialive.us/support/solutions/articles/67000741606-guide-to-repurposing-from-landscape-to-vertical-video) — retrieved 2026-09-12
- [6 Ways to Convert Horizontal Video Vertical — VideoProc](https://www.videoproc.com/video-editor/how-to-make-horizontal-video-vertical.htm) — retrieved 2026-09-12
- [The Best Time to Upload Reels on Instagram — Sendible](https://www.sendible.com/insights/best-time-to-upload-reels-on-instagram) — retrieved 2026-09-12
- [Best Time to Post on Social Media in 2026 — Metricool](https://metricool.com/best-time-to-post-social-networks/) — retrieved 2026-09-12
- [Best Time to Post on TikTok, Instagram, YouTube — Socialync](https://www.socialync.io/blog/best-time-to-post-tiktok-instagram-youtube) — retrieved 2026-09-12
- [Best Time to Post YouTube Shorts, TikTok & Reels 2026 — FlowShorts](https://flowshorts.app/tools/best-time-to-post) — retrieved 2026-09-12
- [How Often to Post on Social Media in 2026 — posteverywhere.ai](https://posteverywhere.ai/blog/how-often-to-post-on-social-media) — retrieved 2026-09-12
- [Best Instagram Reel Length 2026 — Moonb](https://www.moonb.io/blog/instagram-reel-length) — retrieved 2026-09-12
- [How Long Should an Instagram Reel Be 2026 — CreatorHouse](https://creatorhouse.app/blog/instagram-reel-length-2026-test) — retrieved 2026-09-12
