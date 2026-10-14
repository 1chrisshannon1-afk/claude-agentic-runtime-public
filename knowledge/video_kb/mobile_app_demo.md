# Mobile App Demo Recording & Presentation

Terse, applicable rules for recording and presenting mobile-app footage in demo/marketing video.
**This header is a partial reminder only — the primer §4 hard rules are the complete, authoritative
list and govern on any conflict.** Vocabulary/claims restrictions (banned terms, numeric-claims
restriction): follow the company pack's `claims_policy` and that company's video-producer dossier;
where neither states them, declare DEGRADED rather than inventing or
assuming a vocabulary rule (see `INDEX.md`'s precedence note for the full statement of this
fallback chain). The rules below are cross-company craft rules that hold regardless of company:
product-first opens; b-roll ≤2.5s/shot, ≤20% of runtime, never two consecutive, none starting before
3.0s, never leading the words it covers; no PII on screen (seeded demo-tenant data only); no loading
screens, spinners, or blank/skeleton frames; any phone-format deliverable showing app UI is captured
natively at a real phone viewport (§4 below); a per-shot viewing review, including the capture-mode
check (primer §7/§7a), before any upload.

**Provenance:** aggregated from third-party creator-tool, vendor, and practitioner guides unless a source is marked OFFICIAL (published by the platform, standards body, regulator, or licensor itself). Every non-OFFICIAL source in this file is practitioner opinion, not platform documentation; any platform-behaviour claim (a platform limit, cap, spec, ranking behaviour, or policy) that rests only on such a source is UNCONFIRMED-PRIMARY (the `INDEX.md` flag set) until a platform page confirms it — never report it as the platform's own rule.

## 1. Real device vs. simulator/emulator — which to record

- Prefer a **real device** for anything that ships publicly. Apps often run faster in a
  simulator than on real hardware because dev machines are more powerful, so simulator
  footage can misrepresent real load/scroll/animation performance (UNCITED — practitioner
  consensus; the [oreilly.com](https://www.oreilly.com/library/view/ios-9-sdk/9781680501889/f_0056.xhtml)
  page previously cited here returns HTTP 403 and could not be independently verified,
  retrieved 2026-09-12).
- A mouse/trackpad pointer is more precise than a finger, so simulator interaction can hide
  real touch-target/usability problems present on-device (UNVERIFIED — the only source found for
  this specific point, [oreilly.com](https://www.oreilly.com/library/view/ios-9-sdk/9781680501889/f_0056.xhtml),
  returns HTTP 403 and is unreachable; the adjacent 42gears.com citation on this topic does not
  itself address touch-precision when checked directly. Treat this bullet as a plausible but
  unconfirmed claim until a reachable source is found).
- Simulator output resolution does not automatically match real-device output: e.g. simulator
  "3x" capture can be 1242×2208 where the equivalent physical device outputs 1080×1920 —
  never assume simulator capture equals real-device deliverable resolution without checking
  ([pado.name](https://pado.name/blog/2017/01/simulator-video/), retrieved 2026-09-12).
- Simulator/emulator capture is acceptable for internal review cuts, storyboarding, or
  rapid iteration where hardware-fidelity isn't the point — cheap and fast to reshoot
  ([42gears.com](https://www.42gears.com/blog/emulator-vs-simulator-mobile-app-testing/), retrieved 2026-09-12).
- Rule of thumb: **generic OS simulator/emulator for drafts and internal iteration only; for
  anything going to a viewer (customer-facing demo, ad creative, app-store preview, GTM asset),
  use either a real device OR the product's own sanctioned mobile-emulation recorder at a real
  phone viewport (see §4 and the primer) — never a generic, unrecorded-quality simulator, and
  never a desktop capture scaled/cropped to look like a phone.** §4's native-capture rule and this
  rule are not in tension: "real device" here is one of two sanctioned ways to get a real,
  native-phone-viewport master; a generic simulator/emulator window used only for drafting is the
  thing being ruled out, not the product's own purpose-built mobile-emulation recorder.
- Apple's App Review Guideline 2.3.4 requires App Store preview videos to be actual
  screen-capture footage of the app itself — no simulated/mocked interactions. Official source:
  [developer.apple.com/app-store/review/guidelines](https://developer.apple.com/app-store/review/guidelines/) (OFFICIAL)
  (§2.3.4, retrieved 2026-09-12); third-party summaries corroborating the practical implications:
  [appvideos.co](https://appvideos.co/blog/apple-app-preview-guidelines-explained/), retrieved 2026-09-12;
  [mockup.60fps.design](https://mockup.60fps.design/blog/app-store-preview-video), retrieved 2026-09-12.
- If recording on simulator anyway (e.g. `xcrun simctl io booted recordVideo out.mp4`), verify
  final output resolution and frame rate before treating it as deliverable-ready — it can
  differ from the simulator window's on-screen scale ([pado.name](https://pado.name/blog/2017/01/simulator-video/), retrieved 2026-09-12).

## 2. Clean recording conditions (status bar / OS chrome)

- Never ship footage with a live carrier bar, patchy wifi icon, low battery, or a stray
  notification banner — it reads as unpolished and can be a real distraction mid-flow.
- **iOS — three capture paths, three different status-bar outcomes:**
  - **QuickTime recording of a Lightning-tethered device from a Mac** is the ONLY on-device path
    that normalizes the status bar automatically (clean 9:41-style signal/wifi/battery), per
    Apple's own tethered-recording behavior
    ([techjunkie.com](https://www.techjunkie.com/iphone-screenshot-status-bar/), retrieved
    2026-09-12, re-verified 2026-09-27 — the source states this explicitly only for the
    Mac-tethered QuickTime path, not for on-device recording).
  - **On-device Control Center screen recording shows the REAL, live status bar** (actual signal,
    battery, wifi, time) — it is not normalized. If shooting this way, apply the same real-device
    hygiene as §2's other bullets (DND, full battery, wifi on) rather than assuming the recording
    path cleans it for you.
  - **The iOS Simulator does NOT show 9:41 or a clean status bar by default** — it must be
    explicitly overridden per-boot with `xcrun simctl status_bar <device> override --time "9:41"`
    (plus `--wifiBars`/`--cellularBars`/`--batteryState`/`--batteryLevel` flags for the rest of the
    bar), run before recording (UNCITED beyond widespread developer-community documentation of this
    `simctl` subcommand; no single Apple page enumerating the full flag set was found reachable at
    verification time — treat the command syntax as accurate practitioner knowledge, not an Apple
    citation).
- **Android:** built-in "System UI Demo Mode" (Settings → System → Developer options →
  "Demo mode") freezes the status bar to full battery, full signal, no notifications, and a
  fixed clock — the standard move before recording any Android capture
  ([androidpolice.com](https://www.androidpolice.com/2015/07/19/android-m-feature-spotlight-demo-mode-hides-notifications-sets-battery-to-100-and-clock-to-520-perfect-for-screenshots/), retrieved 2026-09-12;
  [guidingtech.com](https://www.guidingtech.com/demo-mode-on-android/), retrieved 2026-09-12 — both
  sources document only the Settings-menu toggle). A headless `adb shell` broadcast-command path for
  the same Demo Mode exists: enable it once with `adb shell settings put global sysui_demo_allowed 1`,
  then enter demo mode with `adb shell am broadcast -a com.android.systemui.demo -e command enter`
  (exit with `-e command exit`); further commands set clock, battery, wifi, and other status-bar
  state as string extras on the same broadcast action (OFFICIAL/primary:
  [AOSP `packages/SystemUI/docs/demo_mode.md`](https://android.googlesource.com/platform/frameworks/base/+/master/packages/SystemUI/docs/demo_mode.md),
  mirrored at
  [github.com/aosp-mirror](https://github.com/aosp-mirror/platform_frameworks_base/blob/master/packages/SystemUI/docs/demo_mode.md)
  — the googlesource.com original returned HTTP 503 on retrieval 2026-09-27; the GitHub mirror of
  the same file was reachable and used to confirm the exact command text above).
- Turn demo mode / clean status bar OFF after recording — leaving it on can mask a real
  device state issue in later ad-hoc use of the same device.
- Silence notifications (DND / airplane-mode-minus-wifi) for the whole capture session, not
  just the hero shot — a banner mid-take forces a full reshoot of that take.
- Set device brightness to a fixed, camera/eye-friendly level before recording; inconsistent
  brightness across clips in the same edit reads as sloppy.

## 3. Device frames vs. bare screen capture

- **App Store preview videos:** submit RAW, unframed screen capture only. Apple's Guideline 2.3.4
  itself states only that "previews may only use video screen captures of the app itself" (official,
  exact text: [developer.apple.com/app-store/review/guidelines](https://developer.apple.com/app-store/review/guidelines/) (OFFICIAL)
  §2.3.4, retrieved 2026-09-12, re-verified 2026-09-27) — it does **not** itself enumerate product
  photography, hands holding a phone, or 3D device mockups as banned; that enumeration is a
  practical-interpretation elaboration from third-party summaries only, not Apple's own text
  ([mockup.60fps.design](https://mockup.60fps.design/blog/app-store-preview-video), retrieved 2026-09-12;
  [appvideos.co](https://appvideos.co/blog/apple-app-preview-guidelines-explained/), retrieved
  2026-09-12 — both are secondary sources describing common review rejections, not an Apple-published
  list; treat the elaboration as plausible practical guidance, not a quoted rule). Because no source
  found states the enumerated list as Apple's own text, the honest resolution is this hedge — cite
  the official screen-capture-only rule from Apple directly, and label the enumerated examples as
  third-party practical interpretation, never as something Apple itself lists.
- **Everywhere else** (website hero, social ad, YouTube, email, landing page): a device frame
  is allowed and often looks more professional than a bare rectangle of footage floating on a
  background — Apple simply doesn't require it outside the App Store preview slot itself
  ([appvideos.co](https://appvideos.co/blog/apple-app-preview-guidelines-explained/), retrieved 2026-09-12).
- Use a device frame when: the shot needs to visually signal "this is a phone" against a
  busy or ambiguous background, or the same composition mixes phone + desktop footage and a
  frame disambiguates which is which.
- Skip the device frame when: cutting fast (frame bezel eats usable screen area at small
  sizes), the shot is already unambiguous (full-bleed vertical video, obviously phone-shaped
  content), or the destination is the literal **App Store** preview slot, where a raw device
  frame is forbidden per Apple's Guideline 2.3.4 above. **The Play Store has no equivalent
  source cited in this file** — no Play Console page found states a frame ban for its preview
  slot; treat "skip the frame in the Play Store preview slot" as practitioner-safe-default
  guidance only, not a sourced platform rule, until a Play Console citation is found.
- If using a frame, match device generation to the product's actual target hardware — an
  outdated frame (physical home button, thick bezels) undercuts a modern-app impression.
- Never crop a frame so tightly that hardware elements (camera notch render, side buttons)
  bleed into the visible frame in a way Apple's reviewers could read as "hardware in the
  preview" if this same asset is repurposed for a store submission — keep store-bound and
  marketing-bound versions as clearly separate exports.

## 4. Portrait 9:16 masters — orientation and resolution

- **Capture-mode viewing-review requirement:** the viewing review for any phone-format cut asks
  the capture-mode question per shot BEFORE any content question, with an explicit FAIL condition
  that a correct content/say-see match never overrides — see the runtime primer §7/§7a for the
  exact question, the FAIL condition, and the `capture_mode` review-record field contract. This
  file states the recording-side rule (record natively); the primer states the review-side rule
  (verify natively, structurally, per shot).
- **Operator ruling (2026-09-14, binding on every phone-format deliverable of any product that
  shows the product's own app UI):** "anytime we are doing Facebook or Instagram reels, it needs to
  be in the phone app or the phone version of the application, not just cropped to fit the phone.
  It should actually be exactly the way that it would look if they were on their phone. That's the
  whole point. and it will help us find issues with the phone version of the application as we
  record these videos." Generalized: any phone-format deliverable (Reels, Stories, Shorts, any
  9:16 cut) that shows the product's app UI has its master recorded natively, in the product's own
  mobile-emulation or real-device capture mode, at a real phone viewport — the product's own
  mobile-emulation recorder, as named in that product's video-producer dossier, not a desktop
  capture cropped or panned to fit; such a deliverable therefore needs its own separately recorded
  native-portrait source (never re-derived from a landscape/desktop master by cropping). Every
  mobile-layout defect met while recording is reported in the seat's findings for the orchestrator
  to file — the recording IS a mobile
  QA pass. A desktop-UI frame in a phone-format cut showing app UI is a per-shot viewing-review
  FAIL. **Carve-out:** a frame is exempt from native-capture ONLY when it has no product/app UI
  visible on screen, including no device screen displaying the app — an end card, pure b-roll, or a
  presenter/brand slate (this is the primer §7a `capture_mode: "not_applicable"` definition, cited
  here as the single source rather than restated as a separately-worded list that could drift from
  it). Such frames carry no responsive UI on screen and may be produced at any aspect ratio and
  repurposed (crop, pan, pad) per `short_form_vertical.md`'s repurposing techniques. This rule
  exists because a 2026-09-14 incident shipped a phone-format reel as a crop of a desktop capture
  when a Reels routing mistake sent the work to `short_form_vertical.md` instead of this file
  (fixed in `INDEX.md` the same day); a given company's own incident/issue number and its
  recorder's exact CLI invocation live in that company's own dossier,
  `<home>/.claude/oversight/video-producer.md` (`<home>` from
  `python3 ~/.claude/tools/gtm/company.py resolve <slug>`, never the session's current repo),
  never here.
- Record a **native vertical (9:16) master** when the primary destination is phone-native
  viewing (Reels, Shorts, TikTok-style feeds, in-app placements). Sources on native-vs-crop-after
  are mixed: [recorded.app](https://recorded.app/en/blog/vertical-video-screen-recording/)
  (retrieved 2026-09-12) itself treats both as legitimate tradeoffs — native capture for full-frame
  control, landscape-then-crop for downstream flexibility — and does not claim crop-after loses
  resolution or composition control. The 2026-09-14 operator-ruling bullet above settles this for
  any phone-format cut showing app UI regardless of general craft opinion: native capture is
  mandatory there, not because native is generically superior, but because it doubles as a
  mobile-UI QA pass and the ruling requires it outright.
- Standard vertical master resolution: **1080×1920** (1080p full-screen 9:16)
  ([marpipe.com](https://www.marpipe.com/ad-glossary/9-16-aspect-ratio-vertical), retrieved
  2026-09-12). 720×1280 is a commonly used lighter-weight export resolution at the same 9:16
  aspect ratio (UNCITED — marpipe.com does not itself state this as an alternative; practitioner
  convention only).
- **Safe zone discipline:** use the reconciled Meta Reels/Stories safe zone from the spec sheet
  (`video_production_kb_social_2026_09_12.md`, row 27) for top/bottom clearance (**top ~14%, bottom
  ~35%** of frame — provenance and confidence level given once in `short_form_vertical.md`'s
  Instagram Reels section; not restated here), and see that same section for the right-edge
  clearance rule (**max(6% of frame width, 130px)** — 130px on a 1080-wide frame, syllaby.io's
figure)
  rather than the narrower 6%-of-width (~65px) figure alone — Reels-class action-rail UI commonly
  sits in that space. This file states only the mobile-capture-specific application of that rule;
  `short_form_vertical.md` is the single cited source of the numbers themselves.
- A phone screen recorded at native resolution already fills a 9:16 frame almost exactly —
  minimal letterboxing needed; confirm actual device aspect ratio (some phones are taller/
  narrower than exactly 9:16) before assuming a zero-padding fit.
- If the same footage must serve both a horizontal (YouTube/website) and vertical (Reels/
  Shorts) cut, record the phone screen at native resolution once and compose two separate
  timelines/backgrounds around it — don't stretch or letterbox-crush one orientation to fake
  the other.
- Google Play's promo video is hosted via a linked YouTube URL rather than a directly-uploaded
  file ([appradar.com](https://appradar.com/blog/android-app-screenshot-sizes-and-guidelines-for-google-play),
  retrieved 2026-09-12). Play IS orientation-agnostic for the general store-listing preview video:
  "Create a video in either landscape or portrait, both orientations are supported on the store
  listing page," recommending the orientation that best matches the app experience (OFFICIAL:
  [Play Console Help — Add preview assets to showcase your
  app](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en), retrieved
  2026-09-27, re-verified 2026-09-27). That same page's only mention of recommended-games video
  sections is that they show preview videos "in a large format" — it states no orientation
  requirement of any kind for that placement, so no landscape-filming rule is asserted here for it;
  produce a portrait vertical demo cut without concern for a games-section orientation requirement.

## 5. Touch/tap visibility — making interaction legible

- A viewer cannot see a finger touching glass the way they'd see a mouse cursor click — tap
  location must be made visible deliberately, or gestures in the demo look like the screen is
  changing on its own.
- **Android:** enable **Settings → Developer options → "Show taps"** (label varies slightly
  by OEM — search "show taps" or "show touches" if not found directly) before recording; this
  overlays a visible dot at every touch point, and screen-recording software picks it up
  natively ([medium.com/theuxblog](https://medium.com/theuxblog/enabling-show-touches-in-android-screen-recordings-for-user-research-cc968563fcb9), retrieved 2026-09-12;
  [support.usertesting.com](https://support.usertesting.com/hc/en-us/articles/4405196389011-How-to-show-taps-on-your-Android-device-during-an-App-test), retrieved 2026-09-12).
- **iOS has no native tap-indicator toggle for on-device screen recording.** The workaround
  is AssistiveTouch (Settings → General → Accessibility → AssistiveTouch → create a custom
  gesture) — functional but adds a persistent floating button to the screen for the whole
  recording, and it only shows discrete taps, not swipe paths
  ([anyrec.io](https://www.anyrec.io/show-taps-wipes-when-recording-on-iphone/), retrieved 2026-09-12;
  [medium.com/whisperarts](https://medium.com/whisperarts/how-to-record-and-show-screen-taps-gestures-in-app-previews-videos-for-ios-4f82d7b6fdc9), retrieved 2026-09-12).
- **iOS Simulator** can get injected tap-indicator overlays via a framework like ShowTime,
  loaded through `simctl` environment injection — this works at the OS/SpringBoard level in
  simulator only, and does not carry over to real-device recording
  ([maestro.dev](https://maestro.dev/blog/showing-tap-indicators-on-ios-recordings), retrieved 2026-09-12).
- If neither native nor injected tap indicators are available/acceptable for a real-device
  iOS shoot, compensate in post: add a lightweight animated tap-ripple graphic composited at
  the known touch coordinates, or narrate/caption the action ("tapping Save") so the
  transition isn't unexplained.
- Never leave a stray AssistiveTouch floating button visible in a shipped cut unless it was
  deliberately used as the tap indicator for that shot — remove/crop it if it wasn't.
- Swipes and drags are inherently harder to visualize than taps on both platforms; prefer
  slow, deliberate swipe gestures during capture, and consider a brief directional arrow
  overlay in post if the gesture's direction isn't obvious from the resulting UI change alone.

## 6. Text legibility at phone-screen viewing size

- Any burned-in caption, label, or callout must be legible when the final video is watched
  at actual phone-screen size, not just full-size on an editing monitor — always preview a
  cut at real mobile scale before finalizing.
- For 1080×1920 vertical masters, minimum readable caption size is roughly **44px** for body
  text, larger for a headline-style callout ([itnavideo.com](https://www.itnavideo.com/blog/caption-font-size-guide-reels), retrieved 2026-09-12).
- Use clean, high-x-height sans-serif faces (Roboto, Open Sans, Atkinson Hyperlegible,
  Helvetica/Arial-class) — avoid condensed, script, or thin-weight fonts for anything meant
  to be read quickly on a small screen ([madegooddesigns.com](https://madegooddesigns.com/best-fonts-for-captions/), retrieved 2026-09-12;
  [waywithwords.net](https://waywithwords.net/blog/mobile-video-captions-enhancing-viewing), retrieved 2026-09-12).
- Maintain at least a **4.5:1 contrast ratio** between caption text and its background; add a
  scrim, outline, or solid caption bar behind text over busy footage rather than relying on
  color alone ([wintersummer.ca](https://www.wintersummer.ca/blog/choosing-the-right-size-and-style-for-video-captions), retrieved 2026-09-12).
- Keep captions bottom-anchored but inside the platform safe zone (see §4) — don't let text
  collide with platform-overlaid UI (like/share buttons, captions) or the frame's own bottom
  edge.
- If the in-app UI text itself is small (a dense settings screen, a data table), consider a
  brief zoom/crop-in on that region during the demo rather than relying on the viewer to read
  full-screen small text off a phone-sized video frame.
- Test legibility on an actual phone playback, not just a laptop preview — desktop screens
  make small text look more readable than it will on the delivery device
  ([waywithwords.net](https://waywithwords.net/blog/mobile-video-captions-enhancing-viewing), retrieved 2026-09-12).

## 7. Showing the same flow on phone AND desktop

- When a product genuinely works on both surfaces, showing the identical user flow on each
  builds credibility — but keep this as normal product footage, never faked with a resized
  desktop browser window pretending to be a "mobile app."
- Do not stretch, downscale, or letterbox a desktop browser recording to imply it's phone
  footage — record the actual mobile surface separately, either a real device or the product's own
  sanctioned mobile-emulation recorder at a real phone viewport (§4), never a resized desktop
  browser window.
- Side-by-side composition (phone frame beside a desktop frame, same task happening on both)
  is the standard way to make "same flow, both surfaces" visually legible in one shot —
  dedicated split-screen/side-by-side editing tools exist for exactly this composition
  ([riverside.com](https://riverside.com/blog/side-by-side-video-app), retrieved 2026-09-12;
  [filmora.wondershare.com](https://filmora.wondershare.com/video-editor/best-split-screen-video-apps.html), retrieved 2026-09-12).
- Keep the two surfaces' timing synchronized in the cut — if the demo narrative is "do this
  once, see it everywhere," the desktop and phone views should reach the same state at
  roughly the same cut point, not drift out of sync.
- A device frame is useful here specifically to disambiguate which panel is phone vs. desktop
  when both are cropped into similar aspect ratios in a shared composition (see §3).
- Prefer real captures of the company's own product or work over any AI-generated or stock UI
  mockup for this comparison — real captures are lowest-risk and highest-credibility, regardless of
  company. Beyond that default: follow the company pack's `ai_content_policy` where one exists for
  the company you're producing for; where no pack exists yet, follow that company's own dossier/
  standing rule for AI-content handling (e.g. mandatory metadata sanitization before publish); where
  neither exists, treat any AI-generated or AI-edited visual as unsafe to publish until a specialist
  or operator ruling says otherwise, rather than assuming any one approach (strip metadata, disclose,
  or forbid outright) applies by default.
- If only one surface exists today (e.g. mobile-only, no desktop equivalent), do not
  simulate the missing surface with a mockup implying parity that doesn't exist — this is a
  factual/credibility risk, not just a style choice.

## 8. General capture hygiene checklist (apply before every take)

**This is a partial reminder, not the full list — the primer §4 hard rules (no PII, no loading
screens, seeded demo-tenant data only, b-roll timing/placement, product-first opens) are the
complete set and govern on any conflict.**

- [ ] Real device, or the product's own sanctioned mobile-emulation recorder at a real phone
      viewport (§4) — never a generic simulator/emulator window or a desktop capture cropped to
      fit, for anything customer-facing or store-bound.
- [ ] **Capture-mode check (primer §7/§7a): for any UI shot, is this native mobile capture, or a
      desktop capture that has been scaled/cropped/panned/letterboxed?** Answer this BEFORE any
      content question — a desktop-shaped frame in a phone-format cut is an automatic FAIL
      regardless of how correct the content is.
- [ ] Status bar cleaned per §2's capture path: iOS Mac-tethered QuickTime is auto-clean; iOS
      on-device Control Center recording is NOT auto-clean (apply manual hygiene); iOS Simulator
      needs an explicit `simctl status_bar override` before recording; Android Demo Mode on.
- [ ] Notifications silenced for the full session.
- [ ] Tap/touch visibility enabled or planned for in post (Android: Show Taps; iOS:
      AssistiveTouch or post-production overlay).
- [ ] Recording orientation matches the primary delivery format (native vertical for
      phone-native placements).
- [ ] Brightness and device state consistent across all takes in one edit.
- [ ] No device frame if this asset is bound for an actual App Store/Play Store preview slot.
- [ ] No PII on screen — synthetic/seeded demo-tenant data only, real phone/email/street address
      never shown (primer §4).
- [ ] No loading screens, spinners, or blank/skeleton frames — every page warmed off camera
      before recording begins (primer §4).
- [ ] Any burned-in text checked for legibility at real phone-playback scale.
- [ ] If comparing phone + desktop, both are real captures of the same real flow, synced in
      time.
- [ ] Full clip previewed at final aspect ratio and real device size before it's treated as
      done — an editing-monitor preview is not the review.

## Sources

- [App Store Review Guidelines §2.3.4 — Apple Developer (OFFICIAL)](https://developer.apple.com/app-store/review/guidelines/) — retrieved 2026-09-12
- [Emulator vs Simulator in Mobile App Testing: Key Differences and Best Practices — 42gears](https://www.42gears.com/blog/emulator-vs-simulator-mobile-app-testing/) — retrieved 2026-09-12
- [Running and Testing on the Device — O'Reilly / iOS 9 SDK](https://www.oreilly.com/library/view/ios-9-sdk/9781680501889/f_0056.xhtml) — retrieved 2026-09-12 (page returns HTTP 403 as of this check; kept for record, treat as unverified)
- [Recording iOS Simulator Video — Geoff Pado](https://pado.name/blog/2017/01/simulator-video/) — retrieved 2026-09-12
- [Apple App Preview Guidelines Explained in Plain English — App Videos](https://appvideos.co/blog/apple-app-preview-guidelines-explained/) — retrieved 2026-09-12
- [App Store Preview Video: What Apple Actually Requires — 60fps Mockup](https://mockup.60fps.design/blog/app-store-preview-video) — retrieved 2026-09-12
- [How to Show Finger Taps & Wipes in iPhone Screen Recording — AnyRec](https://www.anyrec.io/show-taps-wipes-when-recording-on-iphone/) — retrieved 2026-09-12
- [How to record and show screen taps gestures in App Previews videos for iOS — Whisper Arts / Medium](https://medium.com/whisperarts/how-to-record-and-show-screen-taps-gestures-in-app-previews-videos-for-ios-4f82d7b6fdc9) — retrieved 2026-09-12
- [Showing Tap Indicators on iOS Recordings — Maestro](https://maestro.dev/blog/showing-tap-indicators-on-ios-recordings) — retrieved 2026-09-12
- [Enabling 'show touches' in Android screen recordings for user research — Medium/theuxblog](https://medium.com/theuxblog/enabling-show-touches-in-android-screen-recordings-for-user-research-cc968563fcb9) — retrieved 2026-09-12
- [How to show taps on your Android device during an App test — UserTesting Support](https://support.usertesting.com/hc/en-us/articles/4405196389011-How-to-show-taps-on-your-Android-device-during-an-App-test) — retrieved 2026-09-12
- [[Android M Feature Spotlight] Demo Mode Hides Notifications, Sets Battery to 100 And Clock to 5:20 — Android Police](https://www.androidpolice.com/2015/07/19/android-m-feature-spotlight-demo-mode-hides-notifications-sets-battery-to-100-and-clock-to-520-perfect-for-screenshots/) — retrieved 2026-09-12
- [What Is Demo Mode on Android and How to Enable It — Guiding Tech](https://www.guidingtech.com/demo-mode-on-android/) — retrieved 2026-09-12
- [How To Take a Screenshot on an iPhone without the Status Bar — TechJunkie](https://www.techjunkie.com/iphone-screenshot-status-bar/) — retrieved 2026-09-12
- [9:16 Aspect Ratio (Vertical) — Marpipe Ad Glossary](https://www.marpipe.com/ad-glossary/9-16-aspect-ratio-vertical) — retrieved 2026-09-12
- [Aspect Ratios & Safe Zones for Shorts, Reels and TikTok — Syllaby](https://syllaby.io/blog/aspect-ratios-safe-zones-shorts-reels-tiktok/) — retrieved 2026-09-12
- [How to Record Vertical Screen Videos for Shorts, Reels & TikTok — Recorded](https://recorded.app/en/blog/vertical-video-screen-recording/) — retrieved 2026-09-12 (treats native-vs-crop-after as a tradeoff, not a resolution/composition-loss claim)
- [Caption Font Size Guide for Reels: What Works on Mobile Screens — Itnavideo](https://www.itnavideo.com/blog/caption-font-size-guide-reels) — retrieved 2026-09-12
- [Best Fonts for Captions and Subtitles (2026) — Made Good Designs](https://madegooddesigns.com/best-fonts-for-captions/) — retrieved 2026-09-12
- [Mobile Video Captions: Better Enhance Viewer Experiences — Way With Words](https://waywithwords.net/blog/mobile-video-captions-enhancing-viewing) — retrieved 2026-09-12
- [Choosing the Right Size and Style for Video Captions — Winter Summer Media](https://www.wintersummer.ca/blog/choosing-the-right-size-and-style-for-video-captions) — retrieved 2026-09-12
- [12 Best Side-by-side Video Apps — Riverside](https://riverside.com/blog/side-by-side-video-app) — retrieved 2026-09-12
- [10 Best Split Screen Video Apps for iOS & Android — Filmora/Wondershare](https://filmora.wondershare.com/video-editor/best-split-screen-video-apps.html) — retrieved 2026-09-12
- [Google Play screenshot sizes 2026: requirements for every asset — AppRadar](https://appradar.com/blog/android-app-screenshot-sizes-and-guidelines-for-google-play) — retrieved 2026-09-12
- [Demo Mode for the Android System UI — AOSP `packages/SystemUI/docs/demo_mode.md` (OFFICIAL)](https://android.googlesource.com/platform/frameworks/base/+/master/packages/SystemUI/docs/demo_mode.md) — retrieved 2026-09-27 (googlesource.com returned HTTP 503 on this check; confirmed via the [GitHub aosp-mirror copy](https://github.com/aosp-mirror/platform_frameworks_base/blob/master/packages/SystemUI/docs/demo_mode.md) of the same file)
- [Add preview assets to showcase your app — Play Console Help (OFFICIAL)](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en) — retrieved 2026-09-27 (re-verified: states no orientation requirement for the recommended-games video placement)
- `xcrun simctl status_bar override` command syntax (UNCITED beyond widespread developer-community documentation; no single reachable Apple page enumerating the full flag set was found) — see inline note in §2
