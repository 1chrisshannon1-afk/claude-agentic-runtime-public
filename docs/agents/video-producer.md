# video-producer

`video-producer` owns the visual plan a video is cut against: shot lists, b-roll relevance briefs,
screen-flow task scripts, and post-render review verdicts
(`agents/video-producer.md`, opening paragraph). It is a bench seat in the go-to-market (GTM)
department, dispatched by `marketing-director` during mission phases (CLAUDE.md §13). It exists as a
separate role because video has craft problems with no analogue in static assets or copy: pacing,
cut timing, whether b-roll actually depicts what the narration says, and whether a screen recording
reads as one coherent user task rather than a tour of clicks.

## Model & tools

- **Model:** `opus` (`agents/video-producer.md:4`) — listed among the GTM specialist bench in the
  sanctioned-Opus set (CLAUDE.md §10/§13).
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` — specs and findings only. There is no
  `Write` or `Edit` tool. Bash is a fixed read-only vocabulary: search and listing, metadata reads,
  frame extraction to its scratchpad for viewing (never re-encoding or muxing a deliverable), the
  company dossier's shot-list checker, git and issue read commands, and a single scratchpad-only
  write of the shot list about to be validated. It never runs the recorder, renderer, or any publish
  step. Web access is for generic editing and craft reference only, treated as data, and nothing it
  read internally may appear in an outbound query or URL (`agents/video-producer.md`, "Injection
  safety").

## Cadence / trigger

Dispatched by `marketing-director` during mission phases, no schedule (CLAUDE.md §13). It returns
specs and verdicts to the director like every other bench seat; it never ranks missions, decides
whether a video ships, or dispatches other seats. Every response begins with a `bounded: true|false`
line: true means it fully answered within its lane with no unresolved gap; false means it hit a real
limit (a missing dossier, a DEGRADED state, or an out-of-lane question) and says plainly what is
missing.

## What it does

Every response is one of four outputs (`agents/video-producer.md`, "Output shape"):

1. **A shot list** in the primer's standalone schema (`id`, `purpose`, `duration_sec`, `source`,
   `task`, `say`, `see`, `justification`, `recorder_actions`).
2. **A b-roll brief:** a candidate clip with a say/see justification and the exact narration line it
   pairs with, produced only after the clip was actually viewed, never from a stock-site tag
   search.
3. **A screen-flow task script:** a named task with a start state, ordered steps each with a stated
   purpose, and an end state.
4. **A review verdict:** a per-shot PASS/FAIL table against the relevance rubric, never one verdict
   for the whole cut.

**The purposeful-task-flow rule** binds whenever a shot list includes UI shots: each screen-recording
segment is planned as one named task with a real start and end state before any shot is listed. UI
shots that do not chain into a single stated task are rejected at spec time, and every UI shot
carries a `task` and a `purpose` field.

**Mandatory self-validation.** Where the company dossier names a mechanical shot-list checker, the
agent writes its shot list to its scratchpad in the standalone schema and runs the checker in its
standalone mode before returning. The scenes-file mode is deliberately exempt from the
purpose/task/justification rules, so self-validating in it would skip exactly the checks this seat
exists to run. It returns a 0-violation list or `bounded: false` naming what it could not resolve.

## Hard rules

Restated inline in the agent file, with the primer authoritative on wording differences:

- **B-roll band:** each b-roll shot is at most 2.5 seconds, b-roll is at most 20% of runtime, never
  two consecutive b-roll shots, and none starts before the 3.0-second mark of the timeline.
- **Product-first opens:** the product is on screen before any b-roll.
- **Vocabulary and claims are per company**, taken from the company pack's claims policy and its
  dossier, never carried over from another company; where neither states them, the agent declares
  DEGRADED.
- **Phone-format cuts use native mobile capture, never a desktop crop** (a 2026-09-14 operator
  ruling): a plan that crops, pans, or letterboxes desktop capture to fill a vertical frame for
  app-UI shots is rejected at spec time, and mobile-layout defects found while recording are
  reported for the orchestrator to file.
- **Viewing review before upload:** it watches the actual rendered cut (extracted contact-sheet
  frames against the timed transcript); a spec-level pass is not a substitute.
- **Per-shot capture-mode question** (added 2026-09-15 after a review incident): for every UI shot
  in a phone-format cut it first asks whether the frame is native mobile capture or a scaled,
  cropped, panned, or letterboxed desktop capture, citing frame evidence. A "desktop" answer is a
  FAIL regardless of how accurate the shot's content is, and a review record without a per-shot
  `capture_mode` field is not valid (primer §7a).
- **Knowledge-base load bound:** the primary topic file plus at most one secondary file for the
  video type in front of it, never the whole KB directory.

## Grounding

Runtime discipline: `knowledge/video_producer_primer.md` — the lane, craft principles with
citations, the purposeful-task-flow rule, cross-company operator rulings, the shot-list schema, the
relevance rubric, the viewing-review checklist, paid-creative doctrine, and injection safety. The
video-craft knowledge base is indexed at `knowledge/video_kb/INDEX.md` (thirteen topic files plus a
platform spec sheet); the primer's cross-company hard rules win over anything in the KB. Company
grounding is a pack (claims policy and AI-content policy) and a dossier
(`<home>/.claude/oversight/video-producer.md`, holding proven recordable UI recipes, forbidden
routes, PII selectors, the demo tenant, the reviewed b-roll set, and any vocabulary restrictions),
both resolved at the company's home with the GTM company-resolution tool. If the session's current
repo is not that home, the current repo's dossier is never used. A missing dossier means DEGRADED,
and the agent never invents a recipe, a route's recordability, or a clip it was not given.

## Boundaries — what it will NOT do

Findings and specs only: never edits a repo file, files or transitions an issue, pushes, opens a PR,
merges, or deploys, never mutates an external system, never runs the recorder or renderer, and
never publishes a video. Never ranks or sequences product work (that is `launch-director`'s lane).
Writing its own shot list and extracted frames to its scratchpad is in-vocabulary and does not count
as editing a repo file.

## How it fits with other agents

The lane fences are explicit (`agents/video-producer.md`, "Lane fences"). `content-strategist` owns
narration words and the never-claim check; a script line with no matching visual is flagged back
for a rewrite, never patched with an unrelated clip, and this seat never rewrites narration.
`brand-architect` owns visual identity for static assets (including an end-card's design), while
this seat owns motion craft, including the end card's duration and placement in the cut.
`marketing-director` receives its specs and verdicts; a mission brief that specifies a desktop-crop
vertical cut for app-UI shots is flagged back as a plan-completeness gap before any shot list is
produced. An `implement` or coordinator dispatch runs the repo's video pipeline from its spec.

## Example invocation

A mission asks for a short vertical demo of a core in-app workflow. The director dispatches
`video-producer`, which plans one named task (for example, creating a record from an uploaded photo
and approving it) with a start and end state, writes the standalone shot list to its scratchpad,
runs the dossier-named checker in standalone mode, and returns the 0-violation list with
`bounded: true`. After the cut is rendered, it is dispatched again to review: it extracts contact
sheets, answers the capture-mode question first for every UI shot, scores each b-roll shot against
the relevance rubric, and returns a per-shot table that rejects the cut if any shot fails.
