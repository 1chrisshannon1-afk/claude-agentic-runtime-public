# Script-First Timing

Why narration is written and measured BEFORE any capture, and what breaks if you skip it.

## 1. The discipline, stated plainly

**Narration is generated and MEASURED before any capture; the recorder paces every scene to fill
its narration window** (adaptive — re-timed against the actual clock mid-scene, plus a terminal
top-up hold if needed).

**(internal doctrine):** Script-first timing is the load-bearing discipline. Writing the script
short and letting the screen breathe beats padding narration, always.

## 2. Why this order and not the reverse

If you record screen capture first and write narration to match afterward, you get one of two
failure modes:
1. **Narration padded to fill dead screen time** — awkward pacing, filler words, a script that
   reads worse because it was stretched to match footage length rather than written to be good.
2. **Screen capture that doesn't match the narration's natural rhythm** — a viewer hears a claim
   half a second before or after the thing on screen that proves it, which reads as sloppy or,
   worse, as if the copy and the product don't actually line up.

Writing the script first, measuring its actual spoken duration via TTS, and THEN pacing capture
to that duration keeps the script disciplined (you can't pad it — every extra word costs real
seconds you have to justify) and keeps screen action honestly synced to what's being claimed.

## 3. The hook is everything, and this is where script-first timing pays off hardest

**(internal doctrine):** The hook is everything and loading states kill it. A worst-case take
opening on several seconds of a loading spinner burns the roughly 3-5 second window that decides
whether viewers stay — see the company's own pack/dossier for its own measured example.

**(internal doctrine):** the fix was off-camera readiness waits (a pre-capture wait step in the
pipeline's scene config) so capture starts on a settled, populated page — never a logo, login page,
empty state, or spinner. This is only possible to catch and fix systematically because the
narration timing is known in advance and the capture is built to hit it deliberately, rather than
"whatever the screen happened to be doing when we hit record."

## 4. Length benchmark (internal doctrine — directional)

**(internal doctrine — directional): 60–90 seconds, with engagement peaking around ~60s** for this
kind of product-demo short-form video — no primary study is cited here; treat as a directional
benchmark, not a hard cap. Re-derive/cite a primary video-engagement study with a retrieval date
before quoting this as fact.

**Budget scenes by narration need, not by wish** — if a scene's honest narration is short, the
scene is short; don't pad screen time to hit an arbitrary target length. See the company's own
pack/dossier for its own measured production-length example (actual vs. storyboarded runtime).

## 5. Data realism is a shot requirement, not an afterthought

**(internal doctrine):** A product filmed at its sparse-input worst (a low-confidence banner,
zeroed-out line items, warning walls) is unshippable marketing no matter how good the camera work.
Two levers, in this order:
1. Give the product its best honest inputs (fill everything the UI offers).
2. Seed the account with varied, realistic data (a real fixture of representative records, with
   near-identical test drafts deleted) — see the company's own pack/dossier for its own seeding
   recipe.

Camera framing to hide a bad screen is explicitly called out as the **last resort, not the fix** —
fix the underlying data/state first.

## 6. Long waits get an honest time-skip card, never implied instant

**(internal doctrine):** Long waits get an explicit, honest time-skip card (e.g. "≈ 2 minutes
later") — assembly cuts the middle out (keep head + tail), narration never implies instant.

This connects directly to the never-claim gate (see `never-claim-script-gate.md`): the video
medium has its own version of the "don't overclaim speed" rule — a jump-cut that hides a real wait
without any on-screen acknowledgment is a visual version of the "20 minutes" text-copy violation.

## Per-vertical bend (for companies selling to contractors/trades)

This buyer watches a demo video the same way they'd watch a competitor demo a tool at a trade
show: skeptically, expecting the seller to hide the slow parts. An honest time-skip card ("≈ 2
minutes later") actually builds MORE trust with this audience than a video that implies
instantaneous results, because this buyer has been burned by exactly that kind of implied-instant
software demo before. Script-first timing is what makes that honesty possible to execute
precisely — you know exactly how long the real wait is because you measured the narration and the
actual product timing before cutting anything.
