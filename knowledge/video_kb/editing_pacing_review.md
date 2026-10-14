# Editing & Pacing Craft for Software Videos

Terse, applicable rules for cutting and pacing product/software demo, tutorial, and explainer
videos. Every rule below is either cited (URL + 2026-09-12 retrieval) or flagged **[UNCITED —
practitioner consensus]**. Hard constraints from the operator (never override, never soften):

**Provenance:** aggregated from third-party creator-tool, vendor, and practitioner guides unless a source is marked OFFICIAL (published by the platform, standards body, regulator, or licensor itself). Every non-OFFICIAL source in this file is practitioner opinion, not platform documentation; any platform-behaviour claim (a platform limit, cap, spec, ranking behaviour, or policy) that rests only on such a source is UNCONFIRMED-PRIMARY (the `INDEX.md` flag set) until a platform page confirms it — never report it as the platform's own rule.

- B-roll ≤2.5 s per shot, ≤20% of total runtime, never two consecutive b-roll shots, none starting
  before the 3.0 s mark.
- Product-first opens — show the real product before anything else.
- Per the primer §4, vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
  and any other wording rule: follow the company pack's `claims_policy` and that company's own
  video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
  (see `INDEX.md`'s precedence note).
- Viewing review: the rendered cut is watched — contact sheets against the timed transcript, per shot (primer §4/§7) — before any upload; the seat's own frame-viewing review satisfies this, no separate human viewer is required. It covers the actual cut start to finish and is mandatory — no upload
  from a timeline inspection alone.

---

## 1. Cut cadence — how often to cut

- Shot-length target scales with format: calm tutorial/walkthrough narration ≈ 4–8 s per shot;
  fast commentary/vlog-style ≈ 1–3 s per shot; general lifestyle/educational content ≈ every
  1.5–3 s. Pick the tutorial end of this range for software demos — clarity beats energy.
  [Short-Form Video Pacing: The Editing Rhythm Guide, shortzly.com, 2026-09-12]
  **Caveat:** this cadence describes general a-roll/product shot length, not b-roll — the primer's
  hard b-roll numbers (≤2.5s per shot, ≤20% of runtime, never two consecutive, none before 3.0s;
  primer §4) always govern any b-roll cutaway regardless of what this cadence range would otherwise
  suggest. Never apply this 1.5-8s range to a b-roll shot.
- A hard cut is earned by new information arriving with it: a new angle, a new screen state, a
  captioned point, a result. If nothing new appears, the cut is filler — remove it or shorten the
  preceding shot instead of cutting mid-nothing.
  [Video Transitions: Crossfade, Hard Cut, Jump Cut, capcut.com, 2026-09-12]
- Worked structure for a ~45 s software tutorial: hook → hard cut to interface → hard cut to the
  setting/action being changed → hard cut to the result → hard cut back to presenter for the
  takeaway. Four to five cuts total, each one a state change.
  [Video Transitions, capcut.com, 2026-09-12]
- **Mute test:** play the cut with sound off. Any shot that runs past ~3 s without the on-screen
  content itself changing should be trimmed or cut — that 3 s is the ceiling for a static/dead
  shot, not a target to hit on every shot.
  [Video Transitions, capcut.com, 2026-09-12]
- Limit yourself to 2–3 transition *styles* for the whole video (cut, cut, one soft dissolve for a
  scene-level break, say) — style-hopping between wipes/zooms/slides pulls attention onto the edit
  itself, which is the opposite of what a software demo needs.
  [5 Ways To Use Video Transitions, techsmith.com, 2026-09-12]

## 2. Say-see alignment (temporal contiguity)

- Corresponding words and pictures land better together than in sequence — narrate the click as
  (or within a beat of) the click happening, never describe an action well before or after it
  appears on screen. This is Mayer's **temporal contiguity principle**, one of the
  best-replicated findings in multimedia-learning research.
  [Principles for Reducing Extraneous Processing in Multimedia Learning, researchgate.net,
  2026-09-12; Mayer's Principles of Multimedia Learning, educationaltechnology.net, 2026-09-12]
- **Modality principle:** pair the visual with *spoken* narration, not on-screen text doing the
  same job — voice + visual beats text + visual for comprehension.
  [Mayer's Principles, educationaltechnology.net, 2026-09-12]
- **Redundancy principle:** never run narration AND on-screen caption text saying the same words
  at the same time — pick one channel per idea. Captions for accessibility are the exception, not
  a design choice to duplicate the voiceover as decoration.
  [Mayer's Principles, educationaltechnology.net, 2026-09-12]
- **Coherence principle** (largest effect size of the multimedia principles — median d = 0.86
  across 23 studies): cut anything — a shot, a line, a sound effect — that doesn't carry the
  point. Extraneous material doesn't just fail to help, it measurably hurts comprehension.
  [Principles for Reducing Extraneous Processing, researchgate.net, 2026-09-12]
- **Signaling principle:** add a visual cue (highlight box, cursor emphasis, brief motion) to the
  exact element the narration is currently talking about, so attention and audio point the same
  place at the same time.
  [Mayer's Principles, educationaltechnology.net, 2026-09-12]
- Practical build order: record/finalize the screen capture first, then write and record narration
  to match the final visual timing (not the reverse) — this is what makes say-see sync achievable
  without fighting a fixed voiceover track.
  [Narrate Like a Pro, recorded.app, 2026-09-12]
- Narration pace target: ~130–150 words/minute — a touch slower than natural conversation, giving
  the visual room to land before the next line starts. **[UNCITED — practitioner consensus,
  converges across multiple production guides]**

## 3. Avoiding "click-around" (wasted/erratic navigation)

- Plan the exact click path before recording: identify targets, plan the direct route between
  them, do a slow dry run. This is the real fix — smoothing bad navigation in post is a patch, not
  a solution.
  [How to Make Cursor Movements Smoother in Recordings, screenify.studio, 2026-09-12]
- **"Ugly cursor" edit pass:** move the cursor slower than feels natural in the raw capture, pause
  deliberately before and after every click, and keep the cursor motionless when not actively
  doing something — idle drifting cursor motion is visual noise that reads as "looking for
  something."
  [How to Make Tasteful Screen-Recorded Videos, clueso.io, 2026-09-12]
- Disable cursor trails, click ripples/sparkle effects, and other cursor "flair" — they age badly
  and distract from the actual UI.
  [Clueso, clueso.io, 2026-09-12]
- **Trim micro-movements in editing:** any small cursor drift between two intentional clicks —
  hover-and-reconsider, overshoot-and-correct, idle wandering while thinking — gets cut, not just
  sped up. The viewer should see intent, not the search for intent.
  [Clueso, clueso.io, 2026-09-12]
- Cut UI loading waits and idle mouse wandering entirely; use a **ripple delete** so removing the
  dead segment auto-closes the gap instead of leaving a pause.
  [Clueso, clueso.io, 2026-09-12]
- Reserve zoom/push-in for genuine emphasis: 5–10% push-ins on the element being discussed, never
  beyond ~15% except to make truly tiny UI legible; ease the zoom in/out over 120–200 ms so it
  doesn't snap.
  [Clueso, clueso.io, 2026-09-12]
- Avoid jump-cutting over an action the viewer actually needs to see to follow the workflow — in a
  software walkthrough, skipping the middle of a necessary step reads as confusing, not efficient.
  If a gap must be bridged, bridge it with a labeled b-roll/close-up cutaway rather than silence
  the missing step.
  [Video Transitions, capcut.com, 2026-09-12]

## 4. Dead-frame and dead-air detection

- "Dead air" = false starts, hesitation, idle mouse wandering, and UI loading waits — all of it
  gets removed in the rough-cut pass, not left "for later."
  [Clueso, clueso.io, 2026-09-12]
- Detection is two separate checks, not one: **audio** dead air (silence/long pauses/filler words
  in the track) and **visual** dead frames (screen content not changing while something plays).
  Tools exist for both (silence-detection audio scanners; motion-threshold scanners for
  unchanging screen regions) but a manual scrub works identically — the criterion is the same
  either way: nothing new is being communicated.
  [Trimming and Cutting, recorded.app, 2026-09-12; trim-dead-area, github.com, 2026-09-12]
- Manual dead-frame test: scrub at 2x–4x speed once; anywhere the frame looks frozen (no cursor
  motion, no UI change, no narration progressing) at normal-speed scrub, mark it and cut.
  **[UNCITED — practitioner consensus derived from the mute-test and motion-threshold-scan
  methods above]**
- Deliberate exception: intentional holds. A **freeze-frame of 0.5–1.0 s** on a dense info screen
  (a settings panel, an export dialog, a results table) is not dead air — it's reading time, and
  it should be added on purpose, not left to chance. Same logic for the **250–400 ms pause after
  a click** before the next zoom/highlight fires — that gap is processing time, not something to
  ripple-delete.
  [Clueso, clueso.io, 2026-09-12]

## 5. Transitions

- Default to hard cuts for step-to-step and scene-to-scene changes in tutorials/demos — they keep
  attention on content, not on the transition itself.
  [Video Transitions, capcut.com, 2026-09-12]
- Reserve fades/dissolves for instructional-phase boundaries (e.g., "setup" → "using it") where a
  softer break helps the viewer reset context; reserve short slides/wipes/zooms for product-demo
  energy at app-navigation changes — don't mix all three styles in one video (see cadence §1).
  [5 Ways To Use Video Transitions, techsmith.com, 2026-09-12]
- Keep any transition itself short: ≤0.3 s with soft easing for cut-adjacent transitions; longer
  fades are reserved for genuine section/mood breaks (an intro, a chapter change), not routine
  step changes.
  [Clueso, clueso.io, 2026-09-12]
- **J-cuts and L-cuts** for narration/visual overlap: a J-cut starts the next line of narration
  slightly before the visual cuts to match it; an L-cut lets the current visual linger a beat
  after the narration line finishes. Both read as smoother, more connected pacing than a hard
  simultaneous cut on both tracks.
  [Clueso, clueso.io, 2026-09-12]
- A match cut (shared shape/color/motion line across the cut) reads strongest when there genuinely
  is a visual rhyme between two shots — don't force one; an unforced hard cut beats a strained
  match cut.
  [What Is a Match Cut?, borisfx.com, 2026-09-12]

## 6. On-screen text timing

- Hold any on-screen text/lower-third for **3–7 s minimum**, scaled up for longer text — short
  labels can be brief, a full sentence needs the long end of the range or longer. Never let text
  disappear before an average reader (~150 wpm reading speed, i.e., slower than narration pace)
  could have finished it.
  [Optimizing Lower Thirds, softhandtech.com, 2026-09-12; Lower Third Templates, brand.wisc.edu,
  2026-09-12]
- Use a simple fade or short slide-in, not a decorative animation — the animation should support
  legibility, not compete with it.
  [Optimizing Lower Thirds, softhandtech.com, 2026-09-12]
- Never pair on-screen caption text with narration saying the identical words at the same moment
  (redundancy principle, §2) — on-screen text should either stand alone (label/callout) or be true
  accessibility captioning, not a decorative echo of the voiceover.
  [Mayer's Principles, educationaltechnology.net, 2026-09-12]
- Where the company's claims list restricts numeric claims, never let narration or on-screen text
  state one, regardless of how well it would otherwise fit the pacing (see header).

## 7. B-roll pacing (bounded further by the primer's hard cap)

- No universal b-roll ratio exists industry-wide — use it only when it adds information or
  improves pacing, never as filler between "real" shots.
  [Video Styles Explained, vidyard.com, 2026-09-12; How to Create a Visual Story with B-roll,
  wistia.com, 2026-09-12]
- The strongest b-roll illustrates the *meaning* of the line being said, not just a keyword in it
  — e.g., footage of the actual faster workflow, not a generic stock clock for a claim about
  speed. (Where the company's claims list forbids numeric speed/accuracy claims, b-roll choice
  should illustrate the qualitative benefit, never stand in as "proof" of a number that isn't
  spoken.)
  [B-Roll Explained, podcastvideos.com, 2026-09-12]
- Shot length for b-roll scales with role: short/punchy detail cutaways run ~2 s for upbeat
  momentum; longer supporting/process shots can run 20–30 s in slower explainer contexts. **This
  project's hard cap overrides both: every b-roll shot ≤2.5 s, b-roll ≤20% of total runtime, never
  two consecutive, none before 3.0 s into the video.**
  [How to Create a Visual Story with B-roll, wistia.com, 2026-09-12]
- Mute or duck b-roll's native audio so the primary narration/product-audio track carries the
  scene without a jarring audio jump on the cutaway.
  [Wistia, wistia.com, 2026-09-12]
- Product-first constraint interacts directly with this: the opening ~3 s must be real product,
  which also happens to be the exact window the primer bans b-roll from — so the hook is
  necessarily built from real screen/product footage, never a b-roll cold-open.

## 8. Structure and the opening hook

- The first 3–5 s decide whether the rest gets watched — open on the real product/result, not on
  a logo card, a slow build-up, or narration-only setup.
  [45+ Best Product Demo Video Examples, contentbeta.com, 2026-09-12]
- A common effective demo arc: hook (show the result/problem) → context (who/why this matters) →
  walkthrough (start to result) → proof (qualitative payoff, not a stat) → one clear
  call-to-action. Keep the walkthrough the majority of runtime; hook and CTA are short bookends.
  [SaaS Product Demo Video: 7 Examples, moonb.io, 2026-09-12]
- **Segmenting principle:** break a multi-step walkthrough into discrete, self-contained segments
  (one segment per feature/step) rather than one continuous unbroken take — segment boundaries are
  natural cut points and natural places to breathe/reset pacing.
  [Mayer's Principles, educationaltechnology.net, 2026-09-12]

## 9. Watch-based, frame-by-frame QA review method

Do this as a real end-to-end viewing pass — never approve from timeline inspection or scrubbing
alone. Multiple short passes, each with one job, catch more than one long pass trying to judge
everything at once.

1. **Silent pass (visual only, audio muted).** Confirm the cut works on visuals alone: no shot
   exceeds ~3 s without something changing (§1 mute test), no dead frames (§4), no leftover
   click-around (§3), cursor stays purposeful throughout, zoom/highlight cues land on the right
   element at the right moment.
   [Video Transitions, capcut.com, 2026-09-12; Review the Silent Cut Before You Review the
   Spectacle, tilnote.io, 2026-09-12]
2. **Sync pass (full audio + video together).** Confirm say-see alignment (§2): every narration
   line lands within a beat of the visual it describes, no line describes an action that already
   happened or hasn't happened yet, J/L-cut overlaps feel natural rather than confusing, no
   narration references a number/word the company's vocabulary/claims list bans (§ header).
   [Principles for Reducing Extraneous Processing, researchgate.net, 2026-09-12]
3. **Technical pass.** Audio clarity/levels/balance consistent shot to shot; no clipping or
   sudden volume jumps at cut points; frame rate/encoding consistent; captions (if present) match
   spoken words exactly and don't duplicate on-screen text; on-screen text timings hold long
   enough to read (§6); transitions match the 2–3-style budget (§1/§5); aspect ratio and safe
   zones correct for the target platform.
   [What is the Final QC Process for Videos?, beverlyboy.com, 2026-09-12]
4. **Constraint pass — checked explicitly against the primer's hard rules and the company's
   vocabulary/claims list, one by one:**
   b-roll shot lengths (≤2.5 s each), b-roll total share (≤20% of runtime, timed, not eyeballed),
   no two b-roll shots back to back, no b-roll before the 3.0 s mark, product genuinely visible
   first, zero terms the company's list bans and zero claims it restricts, anywhere in narration or
   on-screen text.
   This pass is a checklist against literal text/timestamps, not a vibe check — time-stamp every
   b-roll shot and add up the seconds before certifying the 20% cap.
5. **Full continuous viewing, start to finish, at 1x speed, sound on, no scrubbing or skipping.**
   This is the mandatory pre-upload gate — it is the only pass that reveals cumulative pacing
   problems (a video that's fine shot-by-shot but drags or rushes as a whole) and is what "viewing
   review before upload" means; a timeline audit or the four passes above do not substitute for
   actually watching it once, uninterrupted.
   [Comprehensive Review Criteria, oncevisual.com / videomaker.com continuity-editing guidance,
   2026-09-12]

Any failure in any pass sends the cut back to editing — never patch a failed constraint by
reasoning "close enough"; re-cut and re-run the failed pass (and pass 5) again before sign-off.

---

## Sources

- [Short-Form Video Pacing: The Editing Rhythm Guide (2026), shortzly.com](https://shortzly.com/blog/short-form-video-pacing-editing-guide) — retrieved 2026-09-12
- [Video Transitions: Crossfade, Hard Cut, Jump Cut, capcut.com](https://www.capcut.com/create/video-transitions-crossfade-hard-cut-jump-cut) — retrieved 2026-09-12
- [5 Ways To Use Video Transitions for Smoother, More Professional Videos, techsmith.com](https://www.techsmith.com/blog/ways-to-use-video-transitions/) — retrieved 2026-09-12
- [What Is a Match Cut? Definition, Examples, and How to Use It, borisfx.com](https://borisfx.com/blog/what-is-a-match-cut/) — retrieved 2026-09-12
- [How to Make Tasteful Screen-Recorded Videos, clueso.io](https://www.clueso.io/blog/how-to-make-tasteful-screen-capture-videos) — retrieved 2026-09-12
- [Trimming and Cutting: How to Turn Raw Recordings into Tight, Watchable Videos, recorded.app](https://recorded.app/en/blog/trimming-and-cutting-screen-recordings/) — retrieved 2026-09-12
- [Narrate Like a Pro: Voice and Presentation Tips for Screen Recordings, recorded.app](https://recorded.app/en/blog/narration-tips-for-screen-recordings/) — retrieved 2026-09-12
- [How to Make Cursor Movements Smoother in Recordings, screenify.studio](https://www.screenify.studio/blog/2026-04-20-smooth-cursor-recording) — retrieved 2026-09-12
- [trim-dead-area (motion-threshold dead-frame trimmer), github.com](https://github.com/dilawar/trim-dead-area) — retrieved 2026-09-12
- [Optimizing Lower Thirds: How Long Should They Last for Maximum Engagement?, softhandtech.com](https://softhandtech.com/how-long-should-a-lower-third-last/) — retrieved 2026-09-12
- [Lower Third Templates for Videos, brand.wisc.edu](https://brand.wisc.edu/resource/lower-third-templates-for-videos) — retrieved 2026-09-12
- [How to Create a Visual Story with B-roll, wistia.com](https://wistia.com/learn/production/b-roll) — retrieved 2026-09-12
- [Video Styles Explained: How to Choose the Right Type, vidyard.com](https://www.vidyard.com/blog/different-styles-of-videos/) — retrieved 2026-09-12
- [B-Roll Explained: 25 Smart Shots for Talking-Head and Product Videos, podcastvideos.com](https://www.podcastvideos.com/b-roll-explained-25-smart-shots-for-talking-head-and-product-videos/) — retrieved 2026-09-12
- [45+ Best Product Demo Video Examples for B2B SaaS (2026), contentbeta.com](https://www.contentbeta.com/blog/best-product-demo-video-examples/) — retrieved 2026-09-12
- [SaaS Product Demo Videos: 7 Examples + How to Make Yours, moonb.io](https://www.moonb.io/blog/saas-product-demo-video) — retrieved 2026-09-12
- [Principles for Reducing Extraneous Processing in Multimedia Learning: Coherence, Signaling, Redundancy, Spatial Contiguity, and Temporal Contiguity Principles, researchgate.net](https://www.researchgate.net/publication/262915119_Principles_for_reducing_extraneous_processing_in_multimedia_learning_Coherence_signaling_redundancy_spatial_contiguity_and_temporal_contiguity_principles) — retrieved 2026-09-12
- [Mayer's Principles of Multimedia Learning, educationaltechnology.net](https://educationaltechnology.net/mayers-principles-of-multimedia-learning/) — retrieved 2026-09-12
- [What is the Final QC Process for Videos?, beverlyboy.com](https://beverlyboy.com/filmmaking/what-is-the-final-qc-process-for-videos/) — retrieved 2026-09-12
- [Review the Silent Cut Before You Review the Spectacle, tilnote.io](https://tilnote.io/en/pages/6a8410d691dc6cc5eb7e17ef) — retrieved 2026-09-12
