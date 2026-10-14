# Audio, Voice & Captions — Narration Rules for Worker Agents

Terse, applicable rules for producing narration, mixing audio, and captioning video. Every rule
cites a source with retrieval date 2026-09-12, or is flagged **[practitioner consensus, uncited]**
where no single authoritative spec exists.

**Provenance:** aggregated from third-party creator-tool, vendor, and practitioner guides unless a source is marked OFFICIAL (published by the platform, standards body, regulator, or licensor itself). Every non-OFFICIAL source in this file is practitioner opinion, not platform documentation; any platform-behaviour claim (a platform limit, cap, spec, ranking behaviour, or policy) that rests only on such a source is UNCONFIRMED-PRIMARY (the `INDEX.md` flag set) until a platform page confirms it — never report it as the platform's own rule.

**Hard constraints (cross-company operator rulings — never contradict, regardless of what a source
below says):** b-roll ≤2.5s per shot, ≤20% of runtime, never two consecutive, none starting before
3.0s; product-first opens; a viewing review before any upload. The primer
(`~/.claude/knowledge/video_producer_primer.md`) is the canonical statement of all of them. Separately,
vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
and any other wording rule: follow the company pack's `claims_policy` and that company's own
video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
(see `INDEX.md`'s precedence note).

## TTS / AI Voice Quality Checks

- Never use flat, metronomic pacing — constant word-to-word timing is the single biggest tell of
  synthetic speech; real speech speeds up on asides and slows for emphasis. [Fish Audio, TTS Guide 2026](https://fish.audio/blog/text-to-speech-ai-voice-guide/)
- Vary sentence-level pacing deliberately in the script, not just at the TTS-engine level: short
  punchy sentences read faster, longer explanatory sentences read slower — write for that contrast
  rather than relying on the model to invent it. [Digen.ai, robotic voice fix guide 2026](https://resource.digen.ai/avoid-robotic-voice-ai-video-narration-2026/)
- Check for a pitch rise on questions and warmth/emphasis on key nouns (product name, the single
  benefit claim) — a voice that reads every word at the same pitch and stress fails this check.
  [Fish Audio, TTS Guide 2026](https://fish.audio/blog/text-to-speech-ai-voice-guide/)
- Listen for micro-breath sounds and natural sentence-boundary pauses; a voice with zero breath
  artifacts and uniform inter-sentence gaps reads as synthetic even when word-level prosody is good.
  [Fish Audio, TTS Guide 2026](https://fish.audio/blog/text-to-speech-ai-voice-guide/)
- For any narration over ~60–90 seconds, review chapter-by-chapter (not just start/end) — TTS
  stability commonly degrades over long spans even when short clips sound clean.
  [Fish Audio, TTS Guide 2026](https://fish.audio/blog/text-to-speech-ai-voice-guide/)
- Use a custom pronunciation lexicon (supported by major TTS providers) for any recurring proper
  noun, brand term, or domain jargon rather than repeating inline phoneme tags per occurrence —
  cheaper to maintain and eliminates per-clip mispronunciation drift. [Picovoice, SSML for Production TTS 2026](https://picovoice.ai/blog/ssml-text-to-speech/)
- Use `<say-as>` for numbers, dates, currency, and alphanumeric codes (read character-by-character
  with pauses between groups) — do not trust default number-reading heuristics for anything a
  viewer needs to act on. [OneUptime, SSML pronunciation and pauses guide 2026](https://oneuptime.com/blog/post/2026-02-17-how-to-use-ssml-tags-to-control-pronunciation-and-pauses-in-cloud-text-to-speech/view)
- Use `<break>` tags liberally between sections and immediately after any important claim or
  instruction — listeners need processing time; a script with no inserted pauses beyond sentence
  periods under-serves comprehension. [OneUptime, SSML guide 2026](https://oneuptime.com/blog/post/2026-02-17-how-to-use-ssml-tags-to-control-pronunciation-and-pauses-in-cloud-text-to-speech/view)
- `<prosody>` controls pitch, rate, and volume per-span — use it to slow down and lower pitch
  slightly on a caveat or disclaimer line rather than leaving it at the same rate as the surrounding
  copy. [W3C, SSML 1.1 spec](https://www.w3.org/TR/speech-synthesis11/) (OFFICIAL)
- Re-listen to the FINAL rendered audio, not just the text script — SSML tag support and prosody
  behavior differ across TTS engines and even across model versions from the same vendor; a tag
  that worked in one render is not guaranteed to survive a model update. [Picovoice, SSML for Production TTS 2026](https://picovoice.ai/blog/ssml-text-to-speech/)
- Quality bar: most listeners should not notice synthetic origin unless actively listening for it —
  treat any narration that fails this bar on a first casual listen as needing another pass, not as
  "good enough." [Fish Audio, TTS Guide 2026](https://fish.audio/blog/text-to-speech-ai-voice-guide/)
- The company's own vocabulary/claims list (its pack `claims_policy` or dossier — primer §4)
  applies on top of all technical quality checks, to narration as much as to on-screen text.

## Pacing — Words Per Minute

- Baseline planning number: ~150 words per minute of finished video for general explainer content;
  use this to convert a target runtime into a script word-count budget (a 90-second video ≈ 225
  words). [Verstiuk, Ideal Word Count 2026](https://verstiuk.com/blog/ideal-word-count-one-minute/)
- Content-type WPM targets (use the narrower band for anything the viewer must understand and
  retain, the wider band for tone/energy pieces):
  - Technical / complex instructional: 130–140 wpm. [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
  - Instructional tutorials generally: 130–145 wpm. [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
  - Documentary-style narration: 135–150 wpm. [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
  - Casual/conversational: 150–165 wpm. [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
  - High-energy promotional: up to ~170 wpm, only when content is simple and visuals carry load.
    [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
- Safe planning triad if unsure which band applies: 130 wpm = clearly-paced narration, 150 wpm =
  natural conversational default, 170 wpm = ceiling, only for simple/energetic content.
  [Flowshorts, WPM Speaking 2026](https://flowshorts.app/blog/words-per-minute-speaking)
- A product/how-it-works explainer showing a UI on screen should default to the slower end
  (130–145 wpm) — viewers are dividing attention between narration and watching the screen, so
  standard "clear explainer" pacing (~140 wpm) applies, not conversational pacing.
  [YumYum Videos, Explainer Video Length 2026](https://www.yumyumvideos.com/blog/explainer-video-length/)
- Pace is not just a WPM average — the narrator, subject complexity, on-screen information density,
  and where pauses land all shift the *effective* pace a viewer experiences; treat WPM as a planning
  tool, not a QA metric to hit exactly. [Teleprompter.com, Script Timing 2026](https://www.teleprompter.com/blog/how-to-time-your-script)
- Silence has a job: trim dead air the speaker didn't intend, but preserve intentional pauses after
  a key point — retention editing that removes ALL silence produces a rushed, exhausting listen.
  [Syllaby, Voiceover Pacing & Retention Editing](https://syllaby.io/blog/voiceover-pacing-silence-trimming-retention-editing/)

## Music Beds & Ducking

- Set the narration level first; bring music in underneath it — never mix music to a target level
  and then try to fit voice on top. [Zella, Music Ducking Explained](https://zellahq.com/blog/music-ducking-explained/)
- Target music sitting roughly 18–25 dB below the voice level under narration — treat this as the
  operating range, not a single fixed number; the wider end of the band applies with denser mixes.
  [CapCut, Audio Ducking for Clear Voiceover](https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video)
- Ducking compressor starting point: 6–10 dB gain reduction, 30–60 ms attack, 300–500 ms release —
  duck FAST when speech starts (under ~300 ms) and release SLOWER when it ends so the music swell
  feels like breathing, not pumping. [CapCut](https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video) / [Zella](https://zellahq.com/blog/music-ducking-explained/)
- If music snaps back too abruptly between phrases, lengthen release toward 400–700 ms rather than
  reducing the ducking depth. [CapCut, Audio Ducking](https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video)
- Let music swell to a fuller level in genuine gaps (no speech, e.g. between scenes or over a pure
  b-roll beat) — a bed that stays ducked even with no competing dialogue wastes the track and reads
  as timid, not clean. [Zella, Music Ducking Explained](https://zellahq.com/blog/music-ducking-explained/)
- QA the mix on a phone speaker, not just headphones/monitors — music that sits fine under voice on
  headphones frequently buries speech on small, bass-light phone speakers, which is how most social
  video is actually watched. [Zella, Music Ducking Explained](https://zellahq.com/blog/music-ducking-explained/)
- Use automatic ducking for steady voiceover-first edits with a simple structure; switch to manual
  keyframed ducking when the video has punchlines, beat drops, or product-reveal moments that need
  frame-accurate timing against the music. [Zella, Music Ducking Explained](https://zellahq.com/blog/music-ducking-explained/)
- The primer's b-roll timing rules (≤2.5 s/shot, ≤20% runtime, never two consecutive, none
  before 3.0 s) apply independently of music decisions — music swells never justify violating them.

## Loudness Targets Per Platform

Always measure integrated LUFS (or LKFS — the terms are numerically equivalent) and true peak (dBTP)
before delivery; never rely on ear-matching alone.

| Destination | Target | True peak ceiling | Source |
|---|---|---|---|
| YouTube | −14 LUFS integrated | −1 dBTP | [Critical Listening Lab, YouTube Loudness](https://www.criticallisteninglab.com/en/learn/loudness/youtube) |
| Spotify (music & podcasts) | −14 LUFS | — | [SONE, Podcast Loudness 2026](https://sone.app/blog/podcast-loudness-standards-2026-spotify-apple-youtube) |
| Apple Music / Apple Podcasts | −16 LUFS (±1 dB tolerance) | −1 dBFS true peak | [SONE, Podcast Loudness 2026](https://sone.app/blog/podcast-loudness-standards-2026-spotify-apple-youtube) |
| Instagram Reels | ~−14 LUFS (platform-normalized) | — | [UNCITED summary, no source URL recorded: Instagram/TikTok loudness 2026; verify at the platform's own policy page] |
| Netflix / broadcast-style delivery | −27 LKFS, dialogue-gated | −2 dBTP | [Forasoft, LUFS Targets 2026](https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026) |
| General podcast (no specific platform) | −16 LUFS stereo / −19 LUFS mono | −1 dBTP | [Josh Vamos, LUFS Standards](https://www.joshvamos.com/lufs-standards/) |

- **TikTok, Facebook, X/Twitter, and Twitch have never published an official LUFS target** — any
  number quoted for them online is an estimate, not a spec; do not treat a TikTok "-14 to -15 LUFS"
  figure as authoritative. **[flagged: practitioner estimate, uncited to an official source]**
  [UNCITED summary, no source URL recorded: TikTok/Instagram loudness 2026; verify at the platform's own policy page]
- TikTok in-feed playback was NOT loudness-normalized as of mid-2026 — louder uploads play louder
  in-feed on that platform specifically, unlike YouTube/Spotify which apply gain reduction to
  over-target audio. **[flagged: platform behavior reported as of a specific date, may have changed — verify before relying on it]**
  [UNCITED summary, no source URL recorded: TikTok/Instagram loudness 2026; verify at the platform's own policy page]
- YouTube only turns audio DOWN to reach −14 LUFS if it's louder than target; quieter uploads are
  NOT boosted up to target — deliver at or near −14 LUFS rather than well under it, or the video
  will play back quieter than the platform average. [Critical Listening Lab, YouTube Loudness](https://www.criticallisteninglab.com/en/learn/loudness/youtube)
- When a single narration/cut is repurposed across multiple destinations (YouTube + Instagram +
  a podcast feed), master once to the loudest common target (~−14 LUFS) and produce per-platform
  renders rather than shipping one file everywhere — the Apple/Netflix targets are meaningfully
  quieter and a single −14 LUFS master will sound hot for those. **[practitioner consensus, uncited]**
- Always confirm true peak stays under the platform ceiling even after loudness normalization —
  a normalized-loudness file can still clip on transient peaks (percussive SFX, hard consonants)
  if true peak wasn't limited before normalization. [Critical Listening Lab, YouTube Loudness](https://www.criticallisteninglab.com/en/learn/loudness/youtube)

## Captions — Burned-In vs. Platform, Styling, Reading Speed

- Default to producing BOTH: a burned-in (open) caption render for short-form/social feeds, and a
  separate sidecar file (SRT/VTT) for YouTube and any platform with native caption-file support.
  [Blitzcut, Auto vs Manual Captions](https://blitzcutai.com/blog/auto-captions-vs-manual-captions-tiktok) / [Tapescribe, Video Captions Best Practices 2026](https://tapescribe.com/blog/video-captions-best-practices-2026)
- Burned-in captions are close to mandatory for Reels/TikTok/Shorts-style short-form: these feeds
  default to muted autoplay, so a caption-less clip loses its hook entirely in the first seconds.
  [Blitzcut, Auto vs Manual Captions for TikTok](https://blitzcutai.com/blog/auto-captions-vs-manual-captions-tiktok)
- Sidecar caption files (SRT/VTT) often do NOT survive when a video is re-exported/reposted across
  platforms — never assume an SRT attached on YouTube will carry over to a native repost on another
  platform; burn in for anything cross-posted. [Tapescribe, Video Captions Best Practices 2026](https://tapescribe.com/blog/video-captions-best-practices-2026)
- Provide a sidecar SRT/VTT for YouTube and any long-form destination regardless of whether the
  video is also burned-in — it enables the platform's caption toggle, indexing/search, and is what
  most accessibility and legal-compliance expectations (WCAG 1.2.2) are actually built around.
  [W3C WAI, Understanding SC 1.2.2](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html) (OFFICIAL)
- WCAG 1.2.2 (Level A) requires captions for all pre-recorded video with audio; captions must
  include dialogue AND other meaningful sound (sound effects, speaker identification when unclear),
  not just spoken words — an SRT that omits a critical non-speech sound cue fails this bar.
  [W3C WAI, Understanding SC 1.2.2](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html) (OFFICIAL)
- Captions must be synchronized with the audio (not merely present) — a caption track that drifts
  out of sync over a long video fails accessibility intent even if the text itself is accurate.
  [W3C WAI, Understanding SC 1.2.2](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html) (OFFICIAL)
- Reading-speed target: aim for ~150 wpm as a safe default caption reading speed; a 15-word caption
  needs at least ~6 seconds on screen at that rate. **[practitioner consensus, uncited to a single official spec]**
  [Closed Caption Creator, Subtitle Reading Speed 2026](https://www.closedcaptioncreator.com/blog/articles/subtitle-reading-speed.html)
- Broadcast-grade professional target (BBC standard): 160–180 wpm, translating to roughly 13–15
  characters per second — BBC leans toward the slower end of the professional 15–17 CPS range used
  industry-wide. [Clevercast, BBC Subtitling Guidelines](https://www.clevercast.com/bbc-subtitling-guidelines/)
- Do not exceed ~20 characters/second (adults) or ~17 characters/second (content aimed at children)
  as a hard reading-speed ceiling — faster than this and viewers cannot finish reading before the
  caption changes. [Closed Caption Creator, Subtitle Reading Speed 2026](https://www.closedcaptioncreator.com/blog/articles/subtitle-reading-speed.html)
- Minimum on-screen duration: roughly 0.3 seconds per word (a 4-word caption needs ~1.2 s minimum);
  never let a caption flash for less than this regardless of how fast the speaker actually said it.
  [Clevercast, BBC Subtitling Guidelines](https://www.clevercast.com/bbc-subtitling-guidelines/)
- Maximum on-screen duration: cap a single caption at roughly 6–7 seconds even for long sentences —
  split into multiple caption cards rather than leaving one card up too long. [Clevercast, BBC Subtitling Guidelines](https://www.clevercast.com/bbc-subtitling-guidelines/) / [DCMP guidance cited in Closed Caption Creator](https://www.closedcaptioncreator.com/blog/articles/subtitle-reading-speed.html)
- Line-length guideline: keep caption lines within ~68% of a 16:9 frame's width, roughly 38–42
  characters per line depending on font — wider lines force smaller text or edge-cropping on mobile.
  [Clevercast, BBC Subtitling Guidelines](https://www.clevercast.com/bbc-subtitling-guidelines/)
- Legal/regulatory note: the FCC does not publish a numeric WPM/CPS threshold — its rule
  (47 CFR § 79.1(j)(2)(ii)) is a performance standard (captions must be presented at a speed that permits
  them to be read; check the rule's exact wording at eCFR), so the WPM/CPS numbers above are industry practice used to SATISFY that standard, not
  the regulation's own literal text. [UNCITED summary, no source URL recorded: FCC captioning rules 2026; verify at eCFR, 47 CFR 79.1(j)(2)(ii)]
- 80%+ of viewers are more likely to watch a video to completion when captions are present — treat
  captions as a completion-rate lever, not only an accessibility/compliance checkbox.
  [Tapescribe, Video Captions Best Practices 2026](https://tapescribe.com/blog/video-captions-best-practices-2026)

## AI-Voice Disclosure — Platform Policy Landscape (2026)

Relevant because a company's pack `ai_content_policy` may treat "publicly detectable as AI content"
as a launch-blocking risk (`strip_before_publish` or `forbid`); the same caution class applies to
synthetic narration under that company's policy.

- TikTok requires visible labels on AI-generated audio/visuals depicting realistic people or scenes,
  and uses C2PA Content Credentials to detect synthetic media automatically — even undisclosed
  content can be auto-flagged, not only self-disclosed content. [AuditSocials, TikTok AI Content Policy 2026](https://www.auditsocials.com/blog/tiktok-ai-content-disclosure-rules-2026)
- YouTube requires disclosure for "realistic" altered/synthetic content, but explicitly lists
  cloning one's OWN voice for voiceover/dubbing/localization/accessibility as generally NOT requiring
  disclosure — the disclosure trigger is realistic depiction of a person/event, not "any AI audio."
  [UNCITED summary, no source URL recorded: YouTube AI disclosure rules 2026; verify at the platform's own policy page]
- Meta's AI-content labeling is an enforced advertising requirement (not merely optional
  self-disclosure) as of 2026, triggered by a graded synthetic/photorealism test — assume ad
  creative using an AI voice can be labeled even without an explicit uploader disclosure.
  [AuditSocials, Meta AI Content Label Policy 2026](https://www.auditsocials.com/blog/meta-ai-generated-content-label-policy-2026)
- Spotify and Apple Podcasts prohibit deceptive impersonation and unauthorized voice cloning
  specifically — a generic, non-impersonating AI narration voice is a different risk class from a
  cloned/impersonated real person's voice; do not conflate the two when assessing risk.
  [UNCITED summary, no source URL recorded: AI disclosure rules 2026; verify at the platform's own policy page]
- EU Regulation (EU) 2024/1689 requires providers to mark synthetic audio, image and video output as artificially generated and
  deployers to disclose deep fakes (Article 50, applying from 2 August 2026; verify against EUR-Lex),
  including synthetic voices — relevant for any EU
  audience/ad targeting regardless of the hosting platform's own policy. [UNCITED summary, no source URL recorded: AI disclosure rules 2026; verify at EUR-Lex, Regulation (EU) 2024/1689, Article 50]
- Practical implication: an AI-narrated video is a different (generally lower) disclosure-risk
  profile than an AI-generated visual depicting a realistic person/scene, but is NOT risk-free —
  verify current platform policy before an ad-spend or paid-placement use of AI narration,
  separately from the organic-post case. **[practitioner synthesis of the above, not a single citable source]**

## Sources

- [Fish Audio, "Text to Speech: The Complete Guide to AI Voice Technology in 2026"](https://fish.audio/blog/text-to-speech-ai-voice-guide/) — retrieved 2026-09-12
- [Digen.ai, "Why AI Voices Sound Robotic and How to Fix It (2026 Guide)"](https://resource.digen.ai/avoid-robotic-voice-ai-video-narration-2026/) — retrieved 2026-09-12
- [Picovoice, "SSML for Production TTS: Complete Text-to-Speech SSML Guide in 2026"](https://picovoice.ai/blog/ssml-text-to-speech/) — retrieved 2026-09-12
- [OneUptime, "How to Use SSML Tags to Control Pronunciation and Pauses in Cloud Text-to-Speech"](https://oneuptime.com/blog/post/2026-02-17-how-to-use-ssml-tags-to-control-pronunciation-and-pauses-in-cloud-text-to-speech/view) — retrieved 2026-09-12
- [W3C, "Speech Synthesis Markup Language (SSML) Version 1.1"](https://www.w3.org/TR/speech-synthesis11/) (OFFICIAL) — retrieved 2026-09-12
- [Flowshorts, "Words Per Minute Speaking: Average Speed for Every Context (2026)"](https://flowshorts.app/blog/words-per-minute-speaking) — retrieved 2026-09-12
- [Verstiuk, "Ideal Word Count for a 1 Minute Video Script"](https://verstiuk.com/blog/ideal-word-count-one-minute/) — retrieved 2026-09-12
- [YumYum Videos, "Explainer Video Length: How Long Should It Be? (2026)"](https://www.yumyumvideos.com/blog/explainer-video-length/) — retrieved 2026-09-12
- [Teleprompter.com, "How to Time Your Script Perfectly for Video Content"](https://www.teleprompter.com/blog/how-to-time-your-script) — retrieved 2026-09-12
- [Syllaby, "Voiceover Pacing & Retention Editing Audio Strategy"](https://syllaby.io/blog/voiceover-pacing-silence-trimming-retention-editing/) — retrieved 2026-09-12
- [Zella, "Audio Ducking: How to Lower Music Under a Voiceover"](https://zellahq.com/blog/music-ducking-explained/) — retrieved 2026-09-12
- [CapCut, "Audio Ducking for Clear Voiceover in Video"](https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video) — retrieved 2026-09-12
- [Critical Listening Lab, "YouTube Loudness Normalization — Target LUFS for Video"](https://www.criticallisteninglab.com/en/learn/loudness/youtube) — retrieved 2026-09-12
- [Forasoft, "LUFS targets per platform in 2026"](https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026) — retrieved 2026-09-12
- [SONE, "Podcast Loudness in 2026: LUFS & True Peak"](https://sone.app/blog/podcast-loudness-standards-2026-spotify-apple-youtube) — retrieved 2026-09-12
- [Josh Vamos, "LUFS Standards for Podcast, Video & Broadcast"](https://www.joshvamos.com/lufs-standards/) — retrieved 2026-09-12
- [Blitzcut, "Auto vs Manual vs Burned-In Captions for TikTok"](https://blitzcutai.com/blog/auto-captions-vs-manual-captions-tiktok) — retrieved 2026-09-12
- [Tapescribe, "How to Add Captions to Videos: The Best Practices Guide (2026 Update)"](https://tapescribe.com/blog/video-captions-best-practices-2026) — retrieved 2026-09-12
- [W3C WAI, "Understanding Success Criterion 1.2.2: Captions (Prerecorded)"](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html) (OFFICIAL) — retrieved 2026-09-12
- [Clevercast, "BBC Subtitling Guidelines - Closed Captions Guide"](https://www.clevercast.com/bbc-subtitling-guidelines/) — retrieved 2026-09-12
- [Closed Caption Creator, "Subtitle Reading Speed: CPS & WPM Limits Explained (2026)"](https://www.closedcaptioncreator.com/blog/articles/subtitle-reading-speed.html) — retrieved 2026-09-12
- [AuditSocials, "TikTok AI Content Policy 2026: 4-Tier Labels & Penalties"](https://www.auditsocials.com/blog/tiktok-ai-content-disclosure-rules-2026) — retrieved 2026-09-12
- [AuditSocials, "Meta AI Content Label Policy 2026: Detection & Disclosure"](https://www.auditsocials.com/blog/meta-ai-generated-content-label-policy-2026) — retrieved 2026-09-12
