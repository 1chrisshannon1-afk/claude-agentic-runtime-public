# Video KB Index

This directory is the video-producer seat's craft knowledge base: thirteen topic files, each a
terse, citation-backed rulebook for one class of video work. Read the file(s) matching the video
type in front of you; read `video_producer_primer.md` first regardless, since it holds the
operator's cross-company hard rulings, which override any craft recommendation in this directory.

## Precedence

**The primer (`~/.claude/knowledge/video_producer_primer.md`) wins on every conflict for the
cross-company craft rules it states** (b-roll timing band, product-first opens, viewing review
before upload, no PII, no loading screens) — this KB is craft background — third-party technique,
platform norms, and practitioner consensus — never a source of rules that override an operator
ruling. Each topic file below carries a partial header reminder of these cross-company hard
constraints; the primer §4 list is complete, and the primer's text is the one that actually
governs; if a topic file and the primer
ever appear to disagree on one of these, the primer is correct and the topic file's line needs a
fix (flag it, don't silently follow the topic file).

**Vocabulary and claims restrictions are per company, never runtime-wide** — the primer §4 and
the agent definition state the same rule. Banned terms, numeric-claim restrictions, and any other
wording rule: follow the company pack's `claims_policy` and that company's video-producer dossier;
where neither states them, declare DEGRADED for vocabulary/claims, and never invent, assume, or
carry over another company's list. The dossier is `<home>/.claude/oversight/video-producer.md`,
where `<home>` is what `python3 ~/.claude/tools/gtm/company.py resolve <slug>` returns for that
company — the same call that locates its pack; if the session's current repo is not `<home>`, never
read the current repo's dossier for that consult, since it belongs to a different company. Every topic file below follows
this chain; any example in a topic file that names specific banned terms or a no-numeric-claims
rule is an illustration of what a company's list might contain, never a rule for every company.

## Provenance-convention note

This KB (and the platform spec sheet it indexes) marks source confidence with its own flag set —
**OFFICIAL** (platform-published and independently verified), **UNREACHABLE** (a cited platform page
that returns only a title/could not be fetched — could-not-verify, never confirmed fact),
**UNCONFIRMED-PRIMARY** (a platform-attributed claim from a secondary source with no primary
confirmation found), and **UNCITED** (practitioner consensus, no single authoritative source found)
— distinct from `marketing_kb`'s own conventions, which do not apply here: `citation-style.md`
defines that corpus's provenance tags, and its `[KB-<DIR>-<NNN>]` claim IDs come from
`shared/kb-verification-procedure.md`. Neither convention is wrong; they answer different needs
(this KB's flags grade a single citation's confidence; `marketing_kb`'s claim IDs track a claim
through its verification procedure). Do not mix the two conventions or assume one implies the other.

## Topic files

- **`video_types_catalog.md`** — the master catalog of B2B software video types, seventeen
  sections: (1) intro/brand intro, (2) explainer, (3) feature demo, (4) tutorial/how-to,
  (5) onboarding, (6) release notes/changelog, (7) FAQ/objection-handling, (8) comparison,
  (9) testimonial, (10) case study, (11) founder update/investor update, (12) webinar cut-down,
  (13) event (conference/trade show), (14) recruiting/employer brand, (15) ad creative (paid
  social/search), (16) teaser, (17) Shorts/vertical micro-content — each with purpose, length,
  platform fit, structure beats, CTA, and thumbnail/title guidance, plus cross-cutting rules. **Read this first** when the video type
  itself is still undecided — it routes you to the more detailed topic file below once the type is
  known.

- **`brand_intro_explainer.md`** — brand-intro and how-it-works explainer videos for B2B software
  (60-120s). Covers the brand-intro-vs-explainer-vs-demo distinction, narrative structure, founder
  framing, and how the hard constraints apply specifically to a first-impression video. Read
  when producing a brand intro, company trailer, or positioning explainer.

- **`feature_demo_tutorial.md`** — narrated feature-demo, tutorial, and screencast videos in the
  2-6 minute range: single-goal task-flow structuring, cursor/zoom craft, chaptering, and
  creator-tool-sourced screencast technique. Read when producing any per-feature walkthrough or
  onboarding tutorial (the bulk of a product's video library).

- **`mobile_app_demo.md`** — recording and presenting mobile-app footage: real device vs.
  simulator/emulator tradeoffs, App Store preview-video rules, resolution/fidelity gotchas.
  **PRIMARY for any phone-format (Reels/Stories/Shorts/9:16) deliverable showing product UI —
  native capture mandatory.**

- **`presenter_avatar_video.md`** — talking-head and AI-avatar presenter videos for B2B software:
  when a presenter beats a pure screen recording (and when it does not), framing/eyeline/
  lower-thirds, presenter+screen picture-in-picture layout, script cadence for a synthetic
  presenter, avatar/synthetic-media disclosure norms (YouTube altered/synthetic labels, Meta AI
  labels, LinkedIn), trust pitfalls (uncanny valley, lip-sync drift, wrong emphasis), a
  presenter-cut-specific review checklist, and cost/turnaround process discipline for paid avatar
  renders. Read before producing any talking-head or AI-avatar-hosted cut, including a
  picture-in-picture presenter layer over a screen recording.

- **`short_form_vertical.md`** — YouTube Shorts, Instagram Reels, TikTok, and Facebook Reels specs,
  hooks, captions, cadence; its repurposing section is **NON-APP footage only** — any phone-format
  cut showing product UI routes to `mobile_app_demo.md` first.

- **`linkedin_b2b_founder.md`** — LinkedIn native video and founder build-in-public content for
  B2B small-business software buyers (the specific buyer persona comes from the company's pack
  `persona_file` or dossier): format choice (including when a non-video format wins),
  native-video specs, founder-content norms. Read for any LinkedIn founder update, company-page
  video, or B2B thought-leadership cut.

- **`testimonial_case_study.md`** — testimonial, case-study, and before/after "results" video
  craft: what each format is for, consent/release paperwork, and — critically — how a company's own
  claims-policy restrictions (e.g. a no-numeric-claims rule) can override standard
  testimonial-marketing advice to lean on specific numbers. Read the company pack's `claims_policy`
  before producing any customer testimonial or case study; whether any exist yet for a given company
  is a fact in that company's own video-producer dossier, never here.

- **`paid_video_creative.md`** — paid video ad creative for Meta, YouTube, and LinkedIn: platform
  length limits, safe zones, captioning for paid placements, refresh cadence by spend level. This
  file is explicitly advisory-only — this seat never commits money. Per the governing money rule
  (stated in `~/.claude/knowledge/paid_acquisition_strategist_primer.md` §4): creating a campaign
  PAUSED, even with a budget field, is T1; enabling a campaign, starting spend, pausing or removing a
  campaign or ad set, or changing any budget or cap is `$` — an operator sign-off on a data-backed proposal
  (agents recommend, never execute money). Whether a given company's ads are
  live is a fact in that company's own pack or dossier, not a runtime-wide state — read craft
  technique here regardless of a company's current ads status, since built-but-paused creative still
  needs to be built correctly.

- **`youtube_channel_ops.md`** — channel-level operations: titles, thumbnails, descriptions, tags,
  chapters, end screens, playlists, channel trailer, upload defaults, scheduling, and
  analytics-driven iteration. Read when publishing to or operating a YouTube channel, distinct from
  producing an individual video's content.

- **`editing_pacing_review.md`** — cut cadence, transition discipline, the mute test, pacing craft
  general to any software video, and the mechanics of a real viewing review. Read alongside any
  other topic file — this one is cross-cutting editing craft, not tied to one video type. **Caveat
  inserted 2026-09-12:** its general a-roll shot-length cadence guidance (§1) is NOT a substitute
  for the primer's b-roll numeric band — see the inline note in that file.

- **`audio_voice_captions.md`** — narration/TTS quality checks, SSML/pronunciation control, mixing
  and loudness targets per platform, and captioning (burned-in vs. sidecar) craft. Read for any
  video with narration, voiceover, or a mix step.

- **`licensing_policy_safety.md`** — stock footage/photo licensing (Pixabay), music licensing,
  platform AI-disclosure policy, and content-safety rules including the AI-content-label check.
  Read before sourcing any stock asset, any music track, or publishing anything AI-assisted.

- **`video_production_kb_social_2026_09_12.md`** (this directory's sibling, one level up at
  `~/.claude/knowledge/`) — the **platform spec sheet**: aspect ratios, resolutions, safe zones,
  caption/sound-off norms, and character limits for YouTube (long-form + Shorts), Instagram
  (Reels + feed), Facebook, LinkedIn, and TikTok, plus hook patterns, pacing/shot-length guidance,
  screen-recording craft, structure templates by video type, and a mechanical AI-video failure-mode
  detection checklist. This file predates the topic-file split above and is **kept as-is, not
  duplicated here** — it is the fine-grained numeric reference (exact pixel dimensions, exact
  character caps) that the topic files above summarize qualitatively. Where both cover the same
  ground (e.g. platform aspect ratios), treat this spec sheet as the numeric source of record and
  the relevant topic file as the applied craft guidance built on top of those numbers.
  **Not in the public export:** this spec sheet and the planning document cited in this knowledge base as "governing
  plan §20.5/§20.6" stay in the author's private runtime; the topic files carry the applied guidance
  and their own sources.

## Load bound (read before routing)

**Read at most the primary file plus ONE secondary file for the video type in front of you** — not
every file the table below lists, and never the whole directory. For the platform spec sheet
specifically, don't read it whole for one number: `grep` it for the specific platform/field you
need (e.g. `grep -A3 "Instagram Reels" video_production_kb_social_2026_09_12.md`) rather than
loading its full ~48KB. This costs nothing and preserves the precedence rule above — a targeted
`grep` still returns the authoritative numeric source, just without paying for the rest of the
file's unrelated platforms.

**Compliance files are outside the bound.** A `marketing_kb/compliance/` file named in a routing
row below (e.g. `hipaa-marketing-for-practices.md` for a `regulated: ["hipaa"]` company) is a
mandatory read for that row and does not count against the primary-plus-one limit — that limit
governs `video_kb` topic files only.

**This bound never hides a hard operator ruling (2026-09-15 note, post-incident).** A 2026-09-14
incident happened in part because a correct rule lived only in `mobile_app_demo.md` §4 while the
routing table sent a Reels dispatch to `short_form_vertical.md` instead, and this load bound then
forbade reading the file that held the rule. The fix applied since is structural, not a promise to
route better next time: every hard operator ruling that a mis-route could hide is duplicated into
`video_producer_primer.md` itself (§4 for the capture rule, §7/§7a for the review-side capture-mode
check and its FAIL condition) — the primer is **always read first, regardless of this bound or the
routing table below**, so a topic-file mis-route can no longer make a hard rule unreachable. This
load bound still governs *craft background* (technique, platform norms, practitioner consensus);
it was never meant to gate a hard rule. (A given product's own tracking-issue number and dossier
citation for the incident that motivated this, if any, live in that product's own
`<home>/.claude/oversight/video-producer.md` dossier — never here, since this KB serves every company the
GTM seat operates for.)

## Which file for which video type

| Video type in front of you | Primary file | Secondary files |
|---|---|---|
| Brand intro / company trailer | `brand_intro_explainer.md` | `video_types_catalog.md`, `editing_pacing_review.md` |
| How-it-works explainer | `brand_intro_explainer.md` | `video_types_catalog.md` |
| Per-feature tutorial / screencast | `feature_demo_tutorial.md` | `editing_pacing_review.md`, `audio_voice_captions.md` |
| Onboarding / getting-started | `feature_demo_tutorial.md` | `video_types_catalog.md` |
| Mobile-mode / device-emulation cut | `mobile_app_demo.md` | `short_form_vertical.md` (if also vertical) |
| Talking-head / AI-avatar presenter cut, or a presenter-over-screen picture-in-picture layer | `presenter_avatar_video.md` | `licensing_policy_safety.md` (AI-disclosure check), `audio_voice_captions.md` |
| Shorts / Reels / TikTok cut-down **of app UI** (any phone-format deliverable that shows the product) | `mobile_app_demo.md` (§4: native phone-viewport capture is MANDATORY — operator ruling 2026-09-14; never a desktop crop) | `short_form_vertical.md` (hooks/captions/cadence only; its "Repurposing a landscape master" section is scoped to non-app footage) |
| Shorts / Reels / TikTok cut-down of non-app footage (b-roll, presenter, brand slates) | `short_form_vertical.md` | `editing_pacing_review.md` |
| LinkedIn founder update / build-in-public | `linkedin_b2b_founder.md` | `video_types_catalog.md` |
| Testimonial / case study / before-after | `testimonial_case_study.md` | `licensing_policy_safety.md` (consent/release) |
| Paid ad creative (advisory; spend = operator sign-off) | `paid_video_creative.md` | `short_form_vertical.md`, `video_production_kb_social_2026_09_12.md` |
| YouTube channel setup / publishing / metadata | `youtube_channel_ops.md` | `video_production_kb_social_2026_09_12.md` |
| Release-notes / changelog video | `video_types_catalog.md` (§ release notes) | `feature_demo_tutorial.md` |
| Any video with narration/voiceover | `audio_voice_captions.md` | — |
| Sourcing stock footage, music, or checking AI-disclosure risk | `licensing_policy_safety.md` | — |
| Deciding exact pixel/aspect/caption-length specs for a platform | `video_production_kb_social_2026_09_12.md` | the matching topic file above |
| Local-service / real-world footage (job-site, before/after, practice or team tour, in-person testimonial) for a non-software company | `testimonial_case_study.md` (consent/release; also the nearest-match doctrine for general craft in the absence of a dedicated file — treat as background craft only, not a literal fit) | `licensing_policy_safety.md`; for a company whose pack carries `regulated: ["hipaa"]` (e.g. a healthcare/dental practice), also read [`../marketing_kb/compliance/hipaa-marketing-for-practices.md`](../marketing_kb/compliance/hipaa-marketing-for-practices.md) before filming any real person or patient-adjacent footage; do not paraphrase the HIPAA rule here. **Default absent that file's checklist clearing the shot: patient-adjacent or other real-person footage for a `regulated: ["hipaa"]` company is prohibited.** Reviewers of record: content-side HIPAA questions go to the content reviewer the company's pack or dossier assigns (the governing plan §20.5 names `local-presence-architect`, whose definition ships as `agents/local-presence-architect.md`); this knowledge base does not itself establish a HIPAA-lane content reviewer, so until a pack or dossier assigns one every content-side HIPAA item is treated as prohibited (never routed to a substitute reviewer); tracking, pixel, form, call-recording, chat or booking-widget changes go to `trust-architect`. |

**Known gap:** the topic files above are written for B2B software video; a local-service business
(no app, e.g. a remodeling company or a dental practice) has no dedicated topic file for its own
video types (job-site footage, before/after, a practice/team tour), and "product-first open" has no
settled meaning for a company with no app (the primer §4 carries the provisional reading —
"product" = the company's delivered work or service per its pack/dossier — and scopes §2's A-roll
band and §4's demo-tenant rule to app/software UI). No issue number is recorded here. Until a dedicated file exists, use the row
above and note in the dispatch that the nearest-match doctrine is software-centric and may not
transfer cleanly.
