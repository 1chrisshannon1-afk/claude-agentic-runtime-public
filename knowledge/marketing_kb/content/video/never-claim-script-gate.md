# Never-Claim Script Gate

The per-line gate every video script line must pass before recording, with three example classes of
lines that typically get cut (a company's own real examples live in its pack/dossier).

## 1. The gate, stated plainly

**Every narration line is checked against the current company's own never-claim list BEFORE
recording.** This is not a final QA pass done after the video is cut — it happens at the script
stage, before a single frame is captured, because re-shooting is expensive and re-writing a script
line is nearly free.

**Citation (internal doctrine — mechanism; see the company's own pack/dossier for its actual video
production log).**

## 2. Three example save-classes — what gets cut and why

| Line class that almost ships | Why it gets cut | Which never-claim rule |
|---|---|---|
| A line describing a UI interaction the real product doesn't have in that flow (e.g. a free-text field the UI doesn't actually offer) | The real UI turned out not to support the described interaction — the line described a capability the product doesn't actually have in that flow. | Not necessarily a positioning-doc item directly, but the same discipline: never claim a UI behavior that isn't what the product actually does. |
| A line that over-extends a measured generation-TIME claim across a time-skip (e.g. pairing a speed claim with "start to finish" when only one step was measured) | Implies the whole flow (including parts before/after the measured step) took the measured duration, when only one step was measured at that duration. | `ANTI-PATTERNS.md` #1 (speed claim precision) — a technically-true claim used in a misleading context is still a violation. |
| A line claiming a feature that is currently live-broken in production | Rather than film a claim the product couldn't actually demonstrate, the beat becomes disclosure-only or gets cut. | `ANTI-PATTERNS.md` #6 (never claim an unshipped/broken capability) — extended here to "never claim a currently-broken capability," which is the same principle applied to a live bug rather than a permanently-unshipped feature. |

See the company's own pack/dossier for that company's own real, dated examples of lines cut under
this gate.

## 3. The honesty rule underneath all three

**(internal doctrine):** never fake product output; masks cover test-account IDENTITY only
(company name, login email), and an OCR gate should prove no leakage frame-by-frame.

This draws a hard line: **masking is for privacy (hiding which test account/company was used),
never for making the product look better than it actually performs.** If the product's real output
on camera would show something embarrassing (a warning banner, a $0.00 line item, a broken
feature), the fix is to change the SHOT (better inputs, different scenario, cut the beat entirely)
— never to hide or alter what the product actually did.

## 4. Practical checklist for a script line

Before a line goes into a scene's narration, ask:

1. Does this claim a specific number (time, dollar amount, percentage)? → Is that number measured,
   or is it strategy shorthand being smuggled into copy? (See `ANTI-PATTERNS.md` #1.)
2. Does this imply the product does something automatically from a photo (or any other capability)?
   → Check the current company's own never-claim list (`ANTI-PATTERNS.md` #2) — regardless of
   phrasing softness, a capability that company hasn't shipped and gate-cleared stays cut.
3. Does this describe a UI interaction (typing, clicking, describing something in plain English)?
   → Does the actual current UI support that interaction? If unsure, verify against the live app
   before writing the line into the script — do not write from memory or imagination (this mirrors
   the storyboard-verification lesson in §6 below).
4. Does this claim a feature (export type, recalculation behavior, integration) is currently
   working? → Is it actually deployed and functioning today, not "landed locally" or "fixed but
   not yet deployed"? (See §5's deploy-awareness rule below, and `ANTI-PATTERNS.md` #6.)
5. Does this present an assumed/defaulted value as if it came purely from user input? → Needs
   accept-or-change framing or must be cut (`ANTI-PATTERNS.md` #4).

## 5. Deploy awareness — a rule specific to video (and demo-ware generally)

**Only what is DEPLOYED is filmable. Landed-local fixes are not.**

**(internal doctrine):** This is a video-specific corollary of the never-claim gate: a fix that
exists in a merged commit but hasn't shipped to the environment being filmed is, from the video's
perspective, not real yet. Filming it anyway is the same category of defect as claiming an
unshipped feature in written copy.

## 6. Review cadence that actually catches these

**(internal doctrine):** plan review BEFORE building — a storyboard or script written from
imagination, rather than verified against the live code/app, is exactly how factual errors get
baked into a production plan before anyone catches them; a review round should be able to reject a
storyboard outright on factual-error grounds. Also: live pre-flight to resolve selectors; frame QA
+ an OCR leak gate; an operator watch-through as final acceptance.

The lesson generalizes beyond video: **a storyboard or script written from memory of how the
product works, rather than verified against the live app, is exactly how a factual error gets
baked into a whole production pipeline before anyone catches it.** Always verify claims against
the live, deployed product — never against what you remember it doing, or what the roadmap says it
will do soon.

## Per-vertical bend (for companies selling to contractors/trades)

A demo video is the single highest-stakes content format for this buyer's trust: it's the closest
thing to watching someone actually use the product, which is exactly the kind of proof a
software-skeptical buyer wants before believing a claim. That also means it's the format where a
caught lie (or a caught overclaim) does the most damage — a viewer who spots a claim contradicted
by what's on screen won't just distrust that one claim, they'll distrust the whole video and
probably the company. The per-line gate isn't bureaucratic overhead here; it's the thing standing
between "this looks legit" and "these guys are full of it," for the exact buyer who's already
primed to assume the latter.
