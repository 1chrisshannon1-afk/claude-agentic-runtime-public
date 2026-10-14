# Design Review Primer

Product-agnostic UX/design-review discipline for `design-reviewer`, usable in any repo. Repo-
specific design-system surfaces — token tables, component-standard docs, the mechanical
inline-styling/token ratchet — live in each repo's own `.claude/oversight/dev-runtime.md`; this
primer carries none of them and names no repo by default.

## 1. Heuristics — Nielsen's ten usability heuristics (1994)

Named source: Jakob Nielsen's ten usability heuristics for interface design (1994; later
republished under the Nielsen Norman Group catalog). The list below is recalled from general
knowledge, not transcribed from the original text — exact wording may differ from Nielsen's own
phrasing; verify before quoting externally [from general knowledge — verify before citing
externally]:

1. Visibility of system status — the user always knows what is happening.
2. Match between system and the real world — familiar language and concepts, not internal jargon.
3. User control and freedom — an easy, obvious way out of an unwanted state (undo, cancel, back).
4. Consistency and standards — the same word/icon/action means the same thing everywhere.
5. Error prevention — design out the mistake before it happens, not just message it after.
6. Recognition rather than recall — options and actions are visible, not memorized.
7. Flexibility and efficiency of use — shortcuts for experts without penalizing novices.
8. Aesthetic and minimalist design — no information competing with what matters right now.
9. Help users recognize, diagnose, and recover from errors — plain language, precise cause, a
   constructive next step.
10. Help and documentation — findable, task-focused, not a wall of text, when it's needed at all.

## 2. Mobile field-capture patterns

Where the repo's `dev-runtime.md`/`CLAUDE.md` establishes a field-capture context (work away from
a desk, outdoors, gloved), judge every mobile flow against [from general knowledge — verify before
citing externally]:

- **One-hand reach / thumb zone** — primary actions sit in the bottom two-thirds of the screen;
  a control only reachable by repositioning the whole hand is a real friction finding, not a nit.
- **Tap targets** — a minimum around **44×44pt** (historically Apple HIG's figure; Android
  Material's equivalent guidance runs slightly larger, ~48dp) — a control smaller than that,
  especially adjacent to another tappable control, is a design blocker on mobile.
- **Glove / outdoor contrast** — direct sunlight and work gloves both degrade effective contrast
  and touch precision beyond the indoor-office case; a flow that only reads comfortably at ideal
  indoor contrast and target size is a real field-usability gap.
- **Offline / interrupted-flow states** — a field capture session (photos, voice notes,
  measurements) can be interrupted by connectivity loss or an incoming call; a flow with no
  resume/recovery state for a multi-step capture is a gap, not a nit.
- **Progressive disclosure for multi-modal capture** — a screen combining dropdowns, typed
  measurements, photo capture, and voice notes in one view should reveal secondary inputs only as
  the primary ones are satisfied, not present all modes at once as equal-weight noise.

## 3. Accessibility floor — WCAG 2.1 AA

Named source: WCAG 2.1 (W3C). The ratios below are the two contrast success criteria I am
confident of by number; treat every other specific criterion number/level pairing in this section
as recalled, not verified, and re-check the current spec before citing a criterion number
externally [from general knowledge — verify exact criterion numbers/levels before citing
externally]:

- **Contrast** — 4.5:1 for normal text, 3:1 for large text (≈18pt, or ≈14pt bold) and for
  meaningful non-text UI boundaries/icons (WCAG 2.1 AA, commonly cited as SC 1.4.3 / 1.4.11).
- **Labels** — every input has a visible or programmatically-associated label; a placeholder alone
  is not a label (it disappears on input and fails screen readers).
- **Focus order** — keyboard/assistive-tech focus moves in the same order the page reads visually;
  a focus trap or an order that skips a visible interactive element is a blocker.
- **Reduced motion** — an animation triggered by an interaction should respect a
  reduced-motion preference; this is best practice at minimum, and formalized in WCAG 2.1 at a
  stricter level than this floor's AA baseline (commonly cited as SC 2.3.3, level AAA) — treated
  here as floor-level regardless of its formal level, because a field-use context (bright
  outdoor screens, one-handed use), where the repo establishes one per §2 above, makes motion
  sensitivity a real usability cost, not just a compliance one.

## 4. Tokens-first consistency method

The repo's own design system is the first-class source of truth, not this primer's generic taste.
A value present in the repo's token table (color, spacing, radius, font) that shows up hardcoded
elsewhere in a diff is always a finding — cite the token file:line and the token name that should
have been used instead. A value with NO token equivalent is a gap to name, never an invented token
name to assume exists.

## 5. Build-side companion (D4)

The builder counterpart to this review lane is the `frontend-design` Anthropic marketplace plugin
(`frontend-design@claude-plugins-official`), enabled user-scope (not harness-native) and cached
under `~/.claude/plugins/cache/`. **Fallback:** where the plugin is disabled or absent, the builder
is `implement`, briefed with the repo's token surfaces from its `dev-runtime.md`. Either way, the
reviewer (`design-reviewer`) judges; the builder builds — never the same dispatch.

## Cadence note

This agent's default trigger is on-demand, but "on demand" does not mean "never scheduled": the
monthly T9 slot inside `product-qa`'s scheduled walkthrough job dispatches this agent in `map` mode
FIRST, as the static journey-graph baseline for that slot's live walk (see `oversight_install.md`'s
`com.oversight.csa.productqa` row). That monthly dispatch and an ad hoc on-demand one are the same
agent on the same discipline, not two — do not read the monthly T9 firing as evidence of a second,
undocumented cadence, and do not duplicate a `map`-mode finding the T9 pass already produced when
later dispatched on-demand for the same surface.

## 6. Seam with `product-qa`

`product-qa` walks BUILT pages on staging in a real browser, on a schedule, and scores what it
finds against its own heuristic-evaluation primer. `design-reviewer` judges pre/at build time — no
browser, on demand. A heuristic/accessibility finding on a page actually walked live on staging is
`product-qa`'s; the same class of finding on a diff, mock, or component is `design-reviewer`'s. A
finding either could make is filed once, by whichever ran first, cross-referenced — never
duplicated.

## 7. Interaction cost — the "too many clicks" problem class, done right

Verification scope (§7 and §8, precisely): every NN/g claim below was VERIFIED against the live
cited page on 2026-08-30 (research pass; URLs in Sources) and may be cited externally as
written. The PRIMARY-SOURCE bibliographic details (journal volume/issue/pages, DOIs, book
editions, the exact KLM operator values) were NOT independently fetched — treat those specifics
as `[from general knowledge — verify before citing externally]`, even where the surrounding
claim is live-verified.

- **The governing definition** (Raluca Budiu, NN/g, "Interaction Cost: Definition", 2013, last
  reviewed 2024): interaction cost is *the sum of mental and physical efforts* a user deploys to
  reach a goal — reading, scrolling, locating, comprehending, clicking/touching, typing,
  waiting/page loads, attention switching, and memory load. Components weigh differently per user
  and device. **Review rule:** never approve a change that minimizes the easy-to-count component
  (clicks) by inflating a heavier one (reading, memory load, waiting) for the target user.
- **The 3-click rule is FALSE — never flag on absolute click count.** NN/g (Page Laubheimer, "The
  3-Click Rule for Navigation Is False", 2019): "not supported by data in any published studies to
  date." The underlying study (Joshua Porter, UIE, 2003 — 44 users, 620 tasks) found neither
  drop-off nor satisfaction decline past 3 clicks. What matters is whether each click is
  *confident*: strong **information scent** (§8) and visible wayfinding. **Review rule:** flag a
  flow when added steps carry weak scent or no wayfinding cues; flag a destination whose depth is
  an OUTLIER vs its sibling destinations; flag a diff whose **step-cost delta** is negative
  (adds a step to an existing flow, hides a formerly-visible action behind a menu) — never a flow
  merely for exceeding N clicks.
- **Fitts's Law** (Fitts 1954; NN/g 2022): target-acquisition time grows with distance-to-target
  and shrinks with target size — MT = a + b·log₂(2D/W). **Review rule:** flag an element that is
  both small (below the §2 platform minimums) AND far from the preceding interaction point; the
  compounding is what costs, not either alone.
- **Hick's Law** (Hick 1952 / Hyman 1953; NN/g video, Sherwin 2018): decision time grows
  *logarithmically* with the number of choices. **Review rule:** flag a flat, ungrouped choice set
  (menu, filter list, options) once it grows large with no chunking/grouping/progressive
  disclosure — the fix is grouping, not deleting options; the cost curve is sub-linear.
- **KLM step-costing** (Card, Moran & Newell, CACM 1980) — how to compare two flows honestly:
  sum standard operator times — K keystroke ≈ 0.2s · P pointing ≈ 1.1s · H homing hand-switch
  ≈ 0.4s · **M mental preparation ≈ 1.35s** — for each flow and compare totals. M is roughly 7× a
  keystroke: **a flow with fewer clicks but more decisions/typing can be slower.** Review rule:
  when a diff claims "fewer steps", cost both versions with KLM; flag the claim if the summed
  cost did not actually drop.
- **The `cost:` finding tag** (this agent's report vocabulary, §7-specific): a verified
  interaction-cost regression — step added to an existing task flow, existing action newly hidden,
  sibling-destination depth made non-uniform, or a KLM-costed regression — sits between `risk` and
  `gap` in severity unless it blocks task completion on mobile (then it is a `blocker` per the
  report contract).

## 8. Information architecture — structure findings, routed to the broken layer

Verification scope: same as §7's header — NN/g pages live-verified; primary-source
bibliographic specifics from general knowledge.

- **Information scent / foraging** (Pirolli & Card, *Psychological Review* 1999; NN/g, Budiu
  2019): users follow the strongest-scent path and abandon when scent weakens; scent = proximal
  cues (labels, snippets, congruent imagery) forecasting what is behind a link. **Review rule:**
  flag any nav label, card, or button whose text does not forecast its destination in the USER'S
  task vocabulary — "Solutions"/"Resources"-class vagueness, internal jargon, marketing-branded
  names for functional categories. This is the mechanism behind §7's extra-clicks-are-fine rule.
- **Depth vs breadth** (NN/g, Whitenton, "Flat vs. Deep Website Hierarchies", 2013; Larson &
  Czerwinski, CHI '98 — two converging but distinct sources): all else equal, deep hierarchies are
  harder — and in the CHI '98 data (three structures over 512 items: 8×8×8, 16×32, 32×16 — NO
  one-level flat condition existed, so this study cannot support any "flat lost" claim), the
  16×32 medium depth/breadth mix outperformed the broadest-first 32×16; scent at the level
  introducing depth is decisive. **Review rule:** flag depth added
  WITHOUT strong scent at the introducing level ("click through blind"); never flag depth by
  level-count alone, and never recommend a flattening that would create long overlapping top-level
  menus (that trades a depth cost for a Hick's-Law cost, §7).
- **The four IA systems** (Rosenfeld & Morville, *Information Architecture*, O'Reilly — "the
  polar bear book"; 4th ed. 2015 with Arango): organization (grouping), labeling (naming),
  navigation (movement structures), search (retrieval). Findability failures are STRUCTURE
  failures, not visual ones. **Review rule:** for any "user can't find X" finding, name which of
  the four systems is broken and route the fix there — never propose a visual fix for a
  structural defect.
- **Card sorting vs tree testing** (NN/g: Tankala & Sherwin 2024; Laubheimer 2023): card sorting
  is GENERATIVE (uncovers users' mental-model groupings, used before a structure exists); tree
  testing is EVALUATIVE (measures findability of a specific candidate hierarchy, text-only).
  **Review rule:** when a structural judgment exceeds what a review can settle, recommend the
  right instrument — card sorting to generate, tree testing to validate, never swapped.
- **Cognitive load, three kinds** (Sweller 1988; Sweller/van Merriënboer/Paas 1998; NN/g,
  Whitenton 2013): *extraneous* load (design-imposed: clutter, unlabeled icons, cross-screen
  memory demands, redundant confirmations) is always a legitimate finding; *intrinsic* load
  (the task's inherent complexity) is never a UI bug — the fix there is progressive disclosure and
  support; *germane* load (effort that builds the user's working model) must not be stripped in
  the name of fewer clicks.
- **Whole-app `map` mode grounding:** the nav/route graph is derived from the repo's route table
  and persistent-nav component(s), named per-repo in `dev-runtime.md`'s "Design system" section
  ("Navigation + IA" subsection where present). Depth is counted in CLICKS from the landed
  default state (opening a menu counts); a route reachable only by typed URL has depth ∞ and is
  always a named finding (deliberate exclusions get reported WITH their stated rationale).

## Model-pin promotion trigger (§7/§8 lanes)

This agent stays sonnet-pinned. Propose an Opus pin ONLY with data: two consecutive whole-app
(`map`-mode or journey) passes in which the operator identifies a real journey defect the sonnet
pass missed. Cite both passes in the proposal; never propose from taste.

## What this primer is NOT

This primer carries no repo facts — no token file paths, no component-standard doc names, no
mechanical ratchet script names, no staging URLs. Those live in each repo's own
`.claude/oversight/dev-runtime.md`, read fresh by `design-reviewer` at the start of every task.

## Sources

- Jakob Nielsen — ten usability heuristics (1994) — §1 [content recalled from general knowledge]
- WCAG 2.1 (W3C) — accessibility floor — §3 [specific criterion numbers/levels recalled from
  general knowledge; verify before citing externally]
- Apple Human Interface Guidelines / Android Material Design — tap-target sizing convention — §2
  [from general knowledge]
- This runtime's own config: `frontend-design@claude-plugins-official` enabled in
  `~/.claude/settings.json` and cached under `~/.claude/plugins/cache/claude-plugins-official/
  frontend-design/` — VERIFIED directly, not from memory — §5

§7/§8 sources — every entry that carries a URL below was fetched and verified live 2026-08-30
(research pass) and is safe to cite externally as stated; entries without a URL (the primary
papers/books and their volume/issue/page/DOI/edition details) are from general knowledge —
verify before citing externally:

- Raluca Budiu (NN/g) — "Interaction Cost: Definition" (2013, reviewed 2024) —
  nngroup.com/articles/interaction-cost-definition/ — §7
- Page Laubheimer (NN/g) — "The 3-Click Rule for Navigation Is False" (2019) —
  nngroup.com/articles/3-click-rule/ — §7 (debunk; underlying study: Joshua Porter, UIE 2003,
  44 users / 620 tasks)
- Fitts, P.M. (1954), *J. Exp. Psychology* 47(6) 381–391; NN/g "Fitts's Law and Its Applications
  in UX" (2022) — nngroup.com/articles/fitts-law/ — §7
- Hick (1952) / Hyman (1953); NN/g VIDEO "Hick's Law: Designing Long Menu Lists" (Sherwin, 2018) —
  nngroup.com/videos/hicks-law-long-menus/ — §7 (note: NN/g has no dedicated TEXT article on
  Hick's Law — cite the original papers for the formula, the video for applied framing)
- Card, Moran & Newell — "The Keystroke-Level Model…" *CACM* 23(7) 396–410 (1980); operator
  times K/P/H/M — §7
- Pirolli & Card — "Information Foraging", *Psychological Review* 106(4) 643–675 (1999); NN/g
  "Information Foraging" (Budiu, 2019) — nngroup.com/articles/information-foraging/ — §8
- Kathryn Whitenton (NN/g) — "Flat vs. Deep Website Hierarchies" (2013) —
  nngroup.com/articles/flat-vs-deep-hierarchy/; Larson & Czerwinski, CHI '98,
  DOI 10.1145/274644.274649 — §8 (two distinct sources — NN/g does not itself cite L&C)
- Rosenfeld, Morville (& Arango, 4th ed. 2015) — *Information Architecture* (O'Reilly) — §8
  (the Morville "UX Honeycomb" with Findable is a separate 2004 essay, not the book)
- Tankala & Sherwin (NN/g) — "Card Sorting: Uncover Users' Mental Models" (2024) —
  nngroup.com/articles/card-sorting-definition/ — §8
- Page Laubheimer (NN/g) — "Tree Testing" (2023, reviewed 2026) —
  nngroup.com/articles/tree-testing/ — §8
- Sweller (1988) *Cognitive Science* 12(2); Sweller, van Merriënboer & Paas (1998); NN/g
  "Minimize Cognitive Load to Maximize Usability" (Whitenton, 2013) —
  nngroup.com/articles/minimize-cognitive-load/ — §8
- Nielsen's ten heuristics: current canonical text at
  nngroup.com/articles/ten-usability-heuristics/ (verified 2026-08-30) — §1's recalled list
  cross-checked; §1's own from-memory label stands for its paraphrasing
