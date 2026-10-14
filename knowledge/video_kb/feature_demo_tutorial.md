# Feature Demos, Tutorials & Screencasts (2–6 min) — Task-Flow, Cursor/Zoom Craft, Chaptering

Terse, worker-applicable rules for narrated feature-demo, tutorial, and screencast videos in the
2–6 minute range. Aggregated from third-party creator-tool and platform guides current as of
retrieval date 2026-09-12 unless marked OFFICIAL (platform-published) or UNCITED (practitioner
consensus, no single authoritative source found).

## Hard constraints (cross-company operator rulings — never contradict, regardless of what a source below says)

- B-roll ≤2.5 s per shot.
- B-roll ≤20% of total runtime.
- Never two b-roll shots consecutively.
- No b-roll starts before the 3.0 s mark of the video.
- Every video opens on the product itself (product-first opens) — not a face, not a logo card,
  not scenery, not an "intro to our company" preamble.
- Vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
  and any other wording rule: follow the company pack's `claims_policy` and that company's own
  video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
  (see `INDEX.md`'s precedence note).
- Viewing review: the rendered cut is watched — contact sheets against the timed transcript, per shot (primer §4/§7) — before any upload; the seat's own frame-viewing review satisfies this, no separate human viewer is required. Every shot is viewed, not spot-checked; no upload skips this step.

## Structuring the task flow — one goal per sequence

- Define the single goal for the whole video before recording anything: name the one workflow it
  captures, and refuse to let a second, unrelated workflow ride along in the same cut — viewers
  overwhelmed by multiple processes retain neither.
  [Wyzowl — Onboarding Users With Video](https://wyzowl.com/onboarding-users-with-video/),
  [ispringsolutions — How to Make a Screencast](https://www.ispringsolutions.com/blog/how-to-make-a-screencast-tips-and-tricks)
- Inside that one goal, break the flow into independent lessons/beats, each with its own
  well-defined sub-goal — a viewer who needs to re-watch one step should never have to scrub past
  an unrelated step to find it.
  [neteye-blog — Recording a Good Task-based Screencast](https://www.neteye-blog.com/blog/2026/02/25/making-your-own-video-tutorials-part-20-recording-a-good-task-based-screencast/)
- Write a short action script per beat before recording: starting state of the UI, the exact
  sequence of clicks/keys, and the one sentence of narration that explains *why* this step matters
  — not just what it does.
  [P2PU — Script your Screencast](https://courses.p2pu.org/en/groups/how-to-make-screencasts/content/scripting-your-screencast/)
- A 2–6 minute runtime supports 3–6 beats at most; more than that and the video needs to become a
  series rather than one longer cut — a video that tries to cover every feature is a video nobody
  finishes.
  [Wyzowl — Onboarding Users With Video](https://wyzowl.com/onboarding-users-with-video/) (UNCITED
  extrapolation of the "under 5 minutes, else split into a series" finding to a specific beat count)
- Sequence beats by value, not by menu order: the one or two actions that get the viewer to the
  "aha" outcome fastest go first; secondary capabilities come after, once the core flow has landed.
  [Appcues — Onboarding UX patterns](https://www.appcues.com/blog/user-onboarding-ui-ux-patterns)
- Open on the product already mid-task (per the hard constraint above), not on a logo card or a
  restated problem statement — but pairing the open with the *viewer's* problem in the first line
  of narration (not a feature list) still earns attention before the literal first click.
  [Vidico — Best Product Demo Video Examples](https://vidico.com/news/best-product-demo-video-examples/)

## Narration craft

- Keep narration shorter than instinct suggests: if the visual already shows the action, don't
  describe it a second time — use the spoken line to add context (why, what happens next, what to
  watch for) instead of restating the click.
  [tutorial.ai — Software Demo Best Practices](https://www.tutorial.ai/b/software-demo-best-practices)
- Narrate decision points explicitly: when a step involves a choice (which button, which setting),
  say why that choice is being made now — this is the line most likely to actually teach something,
  versus a play-by-play of cursor movement.
  [tutorial.ai — Software Demo Best Practices](https://www.tutorial.ai/b/software-demo-best-practices)
- Use first person / direct address and lead with outcome, not mechanism — describe what the
  viewer gets, not the internal steps the software takes to produce it.
  [tutorial.ai — Software Demo Best Practices](https://www.tutorial.ai/b/software-demo-best-practices)
- Use plain, active-voice UX-style language even in narration: concrete verbs ("save," "send,"
  "add") over abstract ones, consistent terms for the same UI element throughout, no jargon a new
  user wouldn't already know.
  [Contentphilic — User Onboarding UX Writing](https://contentphilic.com/user-onboarding-ux-writing-examples/)
- Match caption/narration density to reading speed if captions are burned in: concise lines the
  average viewer can read before the visual moves on, not a transcript dump.
  [Bird Eats Bug — Video Captioning Best Practices](https://birdeatsbug.com/blog/video-captioning-best-practices)

## Recording technique (capture once, craft in post)

- Record the full task flow once at a natural pace with slow, deliberate mouse movement — do not
  click around randomly, do not double-click when a single click will do, and do not "talk with
  the cursor" (waving it around while explaining something unrelated to its position).
  [TechSmith — Add Cursor Effects](https://www.techsmith.com/learn/tutorials/camtasia/cursor-effects/),
  [ScreenBuddy — Screen Recording with Zoom Effects](https://screenbuddy.xyz/blog/screen-recording-with-zoom-effects)
- Keep the cursor near the field being typed into — cursor position is what most auto-focus/zoom
  tooling (and a human editor's eye) uses to find where to zoom next; a cursor left far from the
  actual action breaks the zoom logic and the viewer's attention with it.
  [TechSmith — Camtasia AI auto zoom and pan](https://www.techsmith.com/camtasia/features/ai-auto-zoom-and-pan/)
- Prefer the scroll wheel over dragging a scrollbar handle when navigating a long page — a dragged
  scrollbar reads as fast, jittery, hard-to-follow motion on screen.
  [TechSmith — Camtasia AI auto zoom and pan](https://www.techsmith.com/camtasia/features/ai-auto-zoom-and-pan/)
- Add cursor smoothing and click emphasis (a highlight ring or click-pulse) in post rather than
  relying on the raw capture — separating screen and cursor data lets an editor smooth jumpy
  movement and emphasize clicks without re-recording.
  [CapCut — Zoom Effects for Tutorial Videos](https://www.capcut.com/create/zoom-effects-for-tutorial-videos-guide-attention)
- Record in short independent takes per beat rather than one unbroken pass of the whole flow —
  a flubbed step then costs one re-take, not the entire video.
  [ispringsolutions — How to Make a Screencast](https://www.ispringsolutions.com/blog/how-to-make-a-screencast-tips-and-tricks)

## Zoom and pan craft

- Use the "full screen → cue → zoom → return" pattern per beat: show the full UI for 1–2 seconds
  so the viewer has spatial context, use the cursor or a callout to cue where attention is going,
  zoom in for the actual action, then return to the wider frame before the next beat starts —
  never leave the viewer zoomed in with no idea what part of the screen they're looking at.
  [CapCut — Zoom Effects for Tutorial Videos](https://www.capcut.com/create/zoom-effects-for-tutorial-videos-guide-attention)
- Target 2×–3× zoom for most tutorial actions — enough to make small buttons, menu items, and
  body text legible, without cropping out enough surrounding UI that the viewer loses their place.
  [CapCut — Zoom Effects for Tutorial Videos](https://www.capcut.com/create/zoom-effects-for-tutorial-videos-guide-attention)
- Treat zoom as a precision tool for "look exactly here," not a decorative rhythm device — a zoom
  that doesn't correspond to something the viewer needs to read or click is friction, not polish.
  [ScreenBuddy — Screen Recording with Zoom Effects](https://screenbuddy.xyz/blog/screen-recording-with-zoom-effects)
- Use pan (moving the viewing rectangle across a static canvas) to follow cursor travel between two
  related elements on the same screen; use zoom-in/zoom-out (scale) to change how much detail is
  visible at one spot. Don't conflate the two — a pan that also scales disorients faster than
  either alone.
  [TechSmith — Zoom In to Focus Attention](https://www.techsmith.com/learn/tutorials/camtasia/animations/)
- If the screen would otherwise sit static for more than ~10 seconds, introduce *some* visual
  change — a zoom, a callout, a cursor highlight, or a brief cutaway — purely to keep the frame
  from feeling frozen; this is a pacing minimum, not license to zoom constantly.
  [CapCut — Zoom Effects for Tutorial Videos](https://www.capcut.com/create/zoom-effects-for-tutorial-videos-guide-attention)
- When relying on AI/auto-zoom tooling, record with the discipline it needs to guess correctly:
  clips longer than ~30 seconds, deliberate (not rapid-fire) clicks, and no unrelated cursor
  wandering — the automation infers focus points from mouse activity, so noisy input yields noisy
  auto-zoom.
  [TechSmith — Camtasia AI auto zoom and pan](https://www.techsmith.com/camtasia/features/ai-auto-zoom-and-pan/)

## Cut vs. let-the-screen-run

- Default to cutting/trimming dead time — clarity beats atmosphere for a product clip. If showing
  something in full real time doesn't add understanding, cut it.
  [Arcade — Product Tour Examples](https://www.arcade.software/post/product-tour-examples)
- Speed up (don't cut entirely) segments that are real but not informative: loading screens, page
  transitions, long scrolls through a list/dashboard, repetitive setup steps, searching for a file,
  switching tabs. ~1.5× is a reasonable default for "navigating, not learning" stretches.
  [Zight — How to Speed Up a Video](https://zight.com/blog/how-to-speed-up-a-video/) (UNCITED
  specific multiplier; directional, not an authoritative spec)
- Keep the actual "aha" moment — the feature reveal or the payoff of the task — at 1× (real time),
  never sped up; speeding up the one moment the video exists to show undercuts the whole demo.
  [Zight — How to Speed Up a Video](https://zight.com/blog/how-to-speed-up-a-video/)
- Let a genuinely complex or technical step play closer to real time rather than rushing it — for a
  considered-evaluation audience or a non-obvious step, rushing loses viewers before the payoff;
  for a simple, high-velocity self-serve flow, shorten the tour and trim narration more
  aggressively.
  [Arcade — Product Tour Examples](https://www.arcade.software/post/product-tour-examples)
- Jump-cut out verbal filler (um, uh, long pauses) always; use a cut (not a speed-ramp) specifically
  when the intent is to signal a skipped span of time, not just tighten pacing.
  [Arcade — Product Tour Examples](https://www.arcade.software/post/product-tour-examples)
- Mark the boundary between tutorial steps with a consistent, minimal transition (a short wipe or
  equivalent) rather than a hard cut with no visual signal — but use it sparingly: every transition
  style used more than a few times per video reduces its own signal value and adds perceived
  friction.
  [TechSmith — 5 Ways to Use Video Transitions](https://www.techsmith.com/blog/ways-to-use-video-transitions/)

## Chaptering (2–6 min still benefits even below the platform chapter-eligibility floor)

- Chapters require: first timestamp at 0:00, at least 3 timestamps total, each chapter at least 10
  seconds long, listed in ascending order in the video description as `0:00 Chapter Title`.
  [YouTube Help Center — Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en)
  (OFFICIAL)
- A 2–6 minute demo is short enough that platform guidance generally targets chapters at 8+
  minutes — but the same beat-boundary structure this doc already requires (one goal per sequence)
  produces chapter-ready timestamps for free; add them even on a 3-minute video since they cost
  nothing once beats are scripted, and they double as an implicit outline for skimmers.
  [YouTube Help Center — Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en)
  (OFFICIAL, chapter mechanics only — the "still add them below 8 min" recommendation is this KB's
  own extrapolation, UNCITED)
- Title each chapter as the search query a viewer would type to find just that step ("Add a team
  member," "Export as PDF") — never a generic label like "Intro" or "Part 2," which carries no
  information for search or for a skimming viewer.
  [Tubics — YouTube Chapters Guide](https://www.tubics.com/blog/youtube-chapters)
- Chapter boundaries should land exactly on the beat boundaries already defined during scripting
  (per "Structuring the task flow" above) — don't invent a separate chapter structure after the
  edit; the two should be the same list.
  [Tubics — YouTube Chapters Guide](https://www.tubics.com/blog/youtube-chapters)

## Help / onboarding video specifics

- Cap in-product help/onboarding videos under 5 minutes; if a topic needs more, split it into a
  series of focused videos rather than one long video covering everything.
  [Wyzowl — Onboarding Users With Video](https://wyzowl.com/onboarding-users-with-video/)
- For very short onboarding-screen sequences (not full task demos), 3–8 seconds per screen stitched
  together is the working range — much longer per-screen and the sequence stops feeling like
  onboarding and starts feeling like a tutorial (which should then be scripted as one, per the
  rules above).
  [Vidico — Onboarding Videos](https://vidico.com/news/onboarding-videos/)
- Every onboarding/help flow should map to one explicit activation goal — the single action or
  outcome that proves the viewer found value — and the video's one task-flow goal (per the first
  section) should BE that activation goal, not a tangential feature.
  [Appcues — Onboarding UX patterns](https://www.appcues.com/blog/user-onboarding-ui-ux-patterns)
- Plan accessibility before recording, not after: script narration so it also verbally describes
  any visual-only information (so a non-visual viewer isn't lost), and plan for captions plus a
  separate text transcript as standard deliverables, not an afterthought bolt-on.
  [CAST — How to Create Accessible Video](https://www.cast.org/resources/tips-articles/how-to-create-accessible-video/),
  [UMich Accessibility — Make Video & Audio Accessible](https://accessibility.umich.edu/how-to/video-audio/make-video-audio-accessible)
- Never autoplay a help/tutorial video embedded in-product — let the viewer choose to start it, and
  give a visible toggle to hide captions (forcing video + audio + captions simultaneously on every
  viewer is a cognitive-load problem, not an accessibility win).
  [UMich Accessibility — Make Video & Audio Accessible](https://accessibility.umich.edu/how-to/video-audio/make-video-audio-accessible)

## Pre-upload checklist (feature demo / tutorial specific)

- Confirm the video has exactly one stated goal and every beat serves it — cut anything that
  doesn't.
- Confirm zoom/pan events correspond to a real "look here" moment, not rhythm-filler.
- Confirm the "aha" beat plays at 1×; confirm dead/navigation time is cut or sped up.
- Confirm chapter timestamps (if used) exactly match scripted beat boundaries and follow the
  0:00-first, 10-second-minimum, ascending-order rules.
- Confirm captions and a transcript exist, autoplay is off, and captions can be toggled off.
- Confirm the viewing-review hard constraint above (primer §4/§7) has actually happened before upload.

## Sources

- [tutorial.ai — 8 Software Demo Best Practices for 2026](https://www.tutorial.ai/b/software-demo-best-practices) — retrieved 2026-09-12
- [Vidico — 12 Best Product Demo Video Examples in 2026](https://vidico.com/news/best-product-demo-video-examples/) — retrieved 2026-09-12
- [CapCut — Zoom Effects for Tutorial Videos: Guide Attention](https://www.capcut.com/create/zoom-effects-for-tutorial-videos-guide-attention) — retrieved 2026-09-12
- [TechSmith — Introduction to Cursor Editing (Camtasia)](https://www.techsmith.com/learn/tutorials/camtasia/cursor-editing-basics/) — retrieved 2026-09-12
- [TechSmith — Add Cursor Effects (Camtasia)](https://www.techsmith.com/learn/tutorials/camtasia/cursor-effects/) — retrieved 2026-09-12
- [TechSmith — Zoom In to Focus Attention (Camtasia)](https://www.techsmith.com/learn/tutorials/camtasia/animations/) — retrieved 2026-09-12
- [TechSmith — AI auto zoom and pan (Camtasia)](https://www.techsmith.com/camtasia/features/ai-auto-zoom-and-pan/) — retrieved 2026-09-12
- [ScreenBuddy — How to Add Zoom Effects to Screen Recordings (2026 Guide)](https://screenbuddy.xyz/blog/screen-recording-with-zoom-effects) — retrieved 2026-09-12
- [YouTube Help Center — Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en) (OFFICIAL) — retrieved 2026-09-12
- [Tubics — YouTube Chapters: The Ultimate Guide](https://www.tubics.com/blog/youtube-chapters) — retrieved 2026-09-12
- [Arcade — Product Tour Examples to Copy in 2026](https://www.arcade.software/post/product-tour-examples) — retrieved 2026-09-12
- [Zight — How to Speed Up a Video](https://zight.com/blog/how-to-speed-up-a-video/) — retrieved 2026-09-12
- [TechSmith — 5 Ways to Use Video Transitions for Smoother, More Professional Videos](https://www.techsmith.com/blog/ways-to-use-video-transitions/) — retrieved 2026-09-12
- [Wyzowl — The Ultimate Guide to Onboarding Users With Video](https://wyzowl.com/onboarding-users-with-video/) — retrieved 2026-09-12
- [Vidico — Onboarding Videos: Types, Examples & How to Create One (2026)](https://vidico.com/news/onboarding-videos/) — retrieved 2026-09-12
- [Appcues — Onboarding UX: 10 patterns, best practices, and real examples](https://www.appcues.com/blog/user-onboarding-ui-ux-patterns) — retrieved 2026-09-12
- [Contentphilic — Learn User Onboarding UX Writing with 7 Powerful Examples](https://contentphilic.com/user-onboarding-ux-writing-examples/) — retrieved 2026-09-12
- [neteye-blog — Making Your Own Video Tutorials, Part 20: Recording a Good Task-based Screencast](https://www.neteye-blog.com/blog/2026/02/25/making-your-own-video-tutorials-part-20-recording-a-good-task-based-screencast/) — retrieved 2026-09-12
- [ispringsolutions — How to Make a Screencast in 6 Easy Steps](https://www.ispringsolutions.com/blog/how-to-make-a-screencast-tips-and-tricks) — retrieved 2026-09-12
- [P2PU — How to Make Screencasts: Script your Screencast](https://courses.p2pu.org/en/groups/how-to-make-screencasts/content/scripting-your-screencast/) — retrieved 2026-09-12
- [Bird Eats Bug — 15 Video Captioning Best Practices to Improve Accessibility](https://birdeatsbug.com/blog/video-captioning-best-practices) — retrieved 2026-09-12
- [CAST — How to Create Accessible Video](https://www.cast.org/resources/tips-articles/how-to-create-accessible-video/) — retrieved 2026-09-12
- [UMich Accessibility — Make Video & Audio Accessible](https://accessibility.umich.edu/how-to/video-audio/make-video-audio-accessible) — retrieved 2026-09-12
