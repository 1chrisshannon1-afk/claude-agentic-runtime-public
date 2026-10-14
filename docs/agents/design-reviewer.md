# design-reviewer

`design-reviewer` is a different kind of reviewer from the other two: sonnet-pinned, advisory, and
purely on-demand. It judges a UI diff, flow, component, or mock against (1) the repo's *own* design
system — tokens-first, so a hardcoded color/spacing/font is always a finding citing the token
file:line — and (2) a universal UX/accessibility primer (Nielsen's heuristics, mobile field-capture
patterns, the WCAG 2.1 AA floor, interaction-cost and information-architecture research), "before or
as they are built" (`agents/design-reviewer.md` frontmatter's `description:` key, and its opening paragraph after frontmatter). It is not one of the runtime's two
mandatory review gates and never becomes one on its own — it never blocks a commit, and its findings
never substitute for `code-reviewer`'s or `plan-reviewer`'s.

## Model & tools

- **Model:** `sonnet` (`agents/design-reviewer.md` frontmatter's `model:` key) — the one review-boundary-shaped agent in this
  slice that is *not* Opus. `knowledge/model_policy.json`'s `agent_pins` records this explicitly:
  `design-reviewer => sonnet`, distinct from `code-reviewer`/`plan-reviewer => opus`. The primer
  states the promotion bar in writing: "This agent stays sonnet-pinned. Propose an Opus pin ONLY
  with data: two consecutive whole-app (`map`-mode or journey) passes in which the operator
  identifies a real journey defect the sonnet pass missed. Cite both passes in the proposal; never
  propose from taste" (`knowledge/design_reviewer_primer.md:182-186`) — i.e. the pin is deliberately
  conservative and evidence-gated, not assumed permanent.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/design-reviewer.md` frontmatter's `tools:` key) — the same read-only shape as
  the two Opus reviewers. "Read-only Bash (reads, greps, running existing tests only) — never edit
  any file. Never commit or run any git write op (read-only `git diff`/`git log` only). Never
  push/PR/merge/deploy; never production. Never drive a browser (that is `product-qa`'s lane)"
  (`agents/design-reviewer.md` § "Boundaries"). No Playwright/browser-pool grant at
  all — a design review is static (files, mocks), never a live page.

## When it's dispatched

No schedule or gate **of its own** — it rides one monthly slot inside another agent's job; no
`PreToolUse` gate, no mention in CLAUDE.md §13's oversight roster table at all (that table covers
nine *scheduled/dispatch* oversight agents; `design-reviewer` is a dev-time UX-quality agent, a
separate lane). Two entry points:

1. **`/design-review <target>`** — a repo-local skill (e.g.
   `.claude/skills/design-review/SKILL.md` in this repo) that resolves the operator's argument into
   exactly one of five input shapes and dispatches one `design-reviewer` instance. Per the agent's
   own input contract (`agents/design-reviewer.md` § "Input contract"): a **pathspec** (review the files; diff
   against HEAD if pending), a **page/route name** (find its component tree by grep), a **mock image
   path** (Read it directly), a **question** (a one-question UX/design consult, answered from the
   primer's heuristics plus the repo's design system, no file review implied), or the literal mode
   word **`map`** (a whole-app static journey review: build the nav/route graph from the repo's own
   route table and persistent-nav component, count click-depth from the landed default state, and
   report depth outliers, weak-scent labels, redundant paths, and typed-URL-only routes per the
   primer's §7/§8). `map` mode always emits a per-destination table — destination · click-depth from
   the landed default state · path · `achievable_min` where the dossier records one — as a
   first-class artifact, not optional prose (`agents/design-reviewer.md` § "Input contract", final
   sentences); the closing line's
   `Coverage: <n> of <m>` then reads `<m>` as the destinations enumerated for `map`, the files under
   review for a pathspec, or `1` for a question/mock.
2. **The `product-qa` job's monthly T9 slot** — the wiring is runtime-side, not repo-side: the
   `com.oversight.csa.productqa` job's own prompt (`schedules/prompts/walkthrough.txt:5`) dispatches
   `design-reviewer` in `map` mode directly on a 28-day stamp cadence, recorded identically in the
   canonical job table (`knowledge/oversight_install.md:160`) — still advisory, still no gate, still
   no Opus sanction. A repo that adopts this agent contributes only the T9 `achievable_min` target
   table (`.claude/oversight/product-qa.md`), never the scheduling itself.

There is no mechanism anywhere that requires a design review before a UI change can be committed —
unlike `code-reviewer`'s gate 3b, this is purely a quality lane the operator or another agent chooses
to invoke.

## What it does

**Repo grounding first.** If `.claude/oversight/dev-runtime.md` exists (relative to the repo being
worked in), it reads **only** that file's "Design system" section — grepped by heading, read from
that heading to the next `## `-level heading (nested `### ` subsections like "Navigation + IA" stay
in scope) — never the whole file, which grounds the runtime's *dev-workflow* agents, not this one
(`agents/design-reviewer.md` § "Repo grounding"). A missing dossier, or one present with no `## Design system`
heading, is the same failure mode: it declares **DEGRADED** in the report and in the closing line's
`DEGRADED:` field, naming which grounding is absent, then falls back to the repo's own `CLAUDE.md`
hierarchy — it never invents a token, standard, or path.

**Review lane**, two parts (`agents/design-reviewer.md` § "Lane"):
1. **The repo's own design system, tokens-first.** Any hardcoded color, spacing, or font in a diff
   is a finding citing the token file and line (`knowledge/design_reviewer_primer.md:70-76`). A
   value with no token equivalent is named as a gap, never an invented token name.
2. **Universal heuristics** from `knowledge/design_reviewer_primer.md`:
   - **Nielsen's ten usability heuristics** (1994) — visibility of system status, match to the real
     world, user control/freedom, consistency, error prevention, recognition over recall,
     flexibility, minimalist design, error recovery, help/documentation. Explicitly labeled
     `[from general knowledge]`, not transcribed from the original text (primer §1).
   - **Mobile field-capture patterns** where the repo establishes that context: thumb-zone
     placement, ~44×44pt/48dp minimum tap targets, glove/outdoor contrast degradation,
     offline/interrupted-flow recovery states, progressive disclosure for multi-modal capture
     (primer §2).
   - **The WCAG 2.1 AA accessibility floor** — 4.5:1 contrast for normal text, 3:1 for large text
     and meaningful non-text UI, visible/associated labels (a placeholder alone is not a label),
     correct focus order, reduced-motion respect (primer §3).
   - **Interaction cost** (primer §7, live-verified against NN/g 2026-08-30) — the governing rule is
     the *sum* of mental and physical effort, not click count: "never approve a change that
     minimizes the easy-to-count component (clicks) by inflating a heavier one (reading, memory
     load, waiting)." The 3-click rule is explicitly **false** and never grounds a finding on its
     own; what's flagged instead is weak scent, depth outliers vs. sibling destinations, and a
     negative step-cost delta (a diff that adds a step or hides a formerly-visible action) — backed
     by Fitts's Law, Hick's Law, and KLM step-costing for comparing two flows honestly.
   - **Information architecture** (primer §8) — information scent/foraging, depth-vs-breadth
     (flagging depth added without strong scent, never depth by level-count alone), the four IA
     systems (organization/labeling/navigation/search — routing a "can't find X" finding to the
     right one), card-sorting vs. tree-testing as the right instrument to recommend, and the three
     kinds of cognitive load (extraneous is always fair game; intrinsic is never a UI bug).
- **Mechanical findings deferred to what actually gates a commit.** A repo's own `dev-runtime.md`
  names the exact mechanical floors (a ratchet script, ERROR-level lint rules); only those actually
  block. A WARN-level lint hit is still this agent's to file — it just won't stop the commit on its
  own (`agents/design-reviewer.md` § "Lane", final sentences).

**Evidence discipline.** Every consistency claim cites the token/standard file:line and quotes the
token name, or is marked UNVERIFIED. The sole from-memory exception is the primer's own
explicitly-labeled universal facts (Nielsen's numbering, WCAG criterion numbers/levels); a repo fact
— a token, a standard, a lint severity — is never cited from memory
(`agents/design-reviewer.md` § "Evidence discipline").

**Report contract.** Opens with a one-line `VERDICT: clean` / `VERDICT: blockers=<n>`, then findings
grouped by severity and numbered, each with `file:line` and a specific, actionable fix
(`agents/design-reviewer.md` § "Report contract", opening line). Severity vocabulary is `blocker / risk / cost / gap / nit`
(`agents/design-reviewer.md` § "Report contract", severity vocabulary sentences). It **shares** "blocker" and "nit" with `code-reviewer`'s own
vocabulary (`blocker / regression / lock-in-test / missing-docs / scope-creep / nit`) but `risk`,
`cost`, and `gap` are this agent's own middle tiers, distinct from the other reviewer's. `cost` is
this agent's specific tag for a verified interaction-cost regression — sits between `risk` and `gap`
in severity, *unless* it blocks task completion on mobile, in which case it escalates to `blocker`.
A design `blocker` is defined narrowly: a defect that prevents task completion on mobile (e.g. an
unreachable/untappable capture control), a violation of the repo's own component-standard doc, a
violation of the accessibility floor, or a hardcoded value the token table owns. Every report closes
with `Coverage: <n> of <m> examined … · not examined: … · DEGRADED: <missing surfaces, or "none"> ·
Blockers: <n>` — **this is this agent's own convention, not a roster-wide reviewer shape**; the
repo-local `design-review` skill (`<repo>/.claude/skills/design-review/SKILL.md` step 3) carries an
**abbreviated** form of this line, omitting the `not examined:` and `DEGRADED:` segments — this
agent always emits all four regardless of which form gets relayed onward
(`agents/design-reviewer.md` § "Report contract", closing-line sentences).

## Grounding

Operates under `~/.claude/CLAUDE.md` (`agents/design-reviewer.md`, opening paragraph after frontmatter). Its runtime discipline lives
in `knowledge/design_reviewer_primer.md`, which is deliberately product-agnostic and "carries no
repo facts — no token file paths, no component-standard doc names, no mechanical ratchet script
names, no staging URLs" (`knowledge/design_reviewer_primer.md:188-192`). Repo-specific facts (token
tables, component-standard docs, the inline-styling/token ratchet, the nav/route graph) live
exclusively in that repo's own `.claude/oversight/dev-runtime.md`, read fresh at the start of every
task — never cached or assumed across repos.

## Boundaries — what it will NOT do

- **Never edits, never builds.** "You review; you never build and never edit"
  (`agents/design-reviewer.md`, opening paragraph after frontmatter). The builder counterpart is a separate lane entirely — the
  `frontend-design` Anthropic marketplace plugin, or `implement` briefed with the token surfaces
  (`knowledge/design_reviewer_primer.md:78-84`) — "either way, the reviewer... judges; the builder
  builds — never the same dispatch."
- **Never drives a browser.** No Playwright tools; a built, live page is `product-qa`'s lane, not
  this agent's (`agents/design-reviewer.md` § "Boundaries", primer §6).
- **Never pushes/PR/merges/deploys; never touches production.**
- **Never commits or runs any git write op.** Read-only `git diff`/`git log` only
  (`agents/design-reviewer.md` § "Boundaries").
- **Never invents a token, standard, or path** when the repo dossier is missing or silent, or the
  dossier is present with no `## Design system` heading — it declares **DEGRADED** and reports the
  gap instead (`agents/design-reviewer.md` § "Repo grounding").
- **Never records a review.** This agent never satisfies gate 3b and never substitutes for
  `code-reviewer`/`trust-architect` (`agents/design-reviewer.md` § "Boundaries").
- **Never files, transitions, or closes issues** — hands findings to the dispatcher
  (`agents/design-reviewer.md` § "Boundaries").
- **Never bypasses gate 3b or the risk-tier ladder.** Per the repo-local `design-review` skill's own
  Boundaries section, this agent's findings "never bypass `review_risk_tier`/gate 3b for any commit
  that follows from its findings" — a design review is advisory input to a change, not a substitute
  clearance for the mandatory pre-commit gate.

## How it fits with other agents

- **Not a standing review gate.** CLAUDE.md §10's "two Opus review points, and only two" does not
  include `design-reviewer` — it is sonnet-pinned specifically because it is a different kind of
  agent from `code-reviewer`/`plan-reviewer`, not a lighter-weight version of the same thing. It
  never substitutes for either boundary reviewer and never stacks an additional gate onto a commit;
  a UI-heavy commit still goes through `code-reviewer` (or `trust-architect` on a trust surface)
  exactly as any other commit would.
- **Seam with `product-qa` — pre-build vs. post-build, the load-bearing distinction.** `product-qa`
  walks BUILT pages on staging in a real browser, on a schedule, scoring what it finds against its
  own heuristic-evaluation primer. `design-reviewer` judges the DESIGN pre/at build time — no
  browser, on demand. "A finding either agent could make is filed ONCE, by whichever ran first,
  cross-referenced — never duplicated" (`agents/design-reviewer.md` § "Seams, both directions",
  primer §6). Concretely: a
  heuristic/accessibility finding on a page actually walked live on staging belongs to `product-qa`;
  the same class of finding on a diff, mock, or component belongs to `design-reviewer`.
- **Findings still route through `board-steward`'s filing rules** like any other agent's output —
  one issue per root-cause cluster, cross-referenced against anything `product-qa` already filed
  (repo-local `design-review` skill, step 4).
- **`map`-mode grounding depends on `dev-runtime.md`'s "Navigation + IA" subsection** and, where a
  repo wires `product-qa`'s T9 slot to it, on that job's own target table
  (`.claude/oversight/product-qa.md` in a repo that has one) — a structural dependency on another
  agent's dossier staying current, not a runtime dependency on `product-qa` itself.

## Example invocation

Before a new "add photo" capture screen ships, the operator runs `/design-review
modules/frontend/src/screens/PhotoCapture.tsx`. `design-reviewer` reads the repo's
`dev-runtime.md` "Design system" section for the token table and component standards, reads the
diff, opens with `VERDICT: blockers=1`, and finds: (1) a hardcoded `#2b2b2b` background where the token table defines
`--color-surface-dark` at `tokens.css:41` — a tokens-first finding; (2) the primary "capture" button
sits at 36×36pt, below the primer's ~44×44pt mobile minimum, and is adjacent to a "cancel" control —
a `blocker` per the mobile-field-capture and Fitts's-Law rules, since it's both small and reachable
right after a miss-tap; (3) the screen has no resume state if connectivity drops mid-capture — filed
as a `gap` under the offline/interrupted-flow pattern. It closes with `Coverage: 1 of 1 examined ·
not examined: none · DEGRADED: none · Blockers: 1`. None of this touches gate 3b — the implementer
still needs a full `code-reviewer` pass (or `trust-architect` if the screen touches a trust surface)
before the eventual commit can land; this review only makes that later pass start from a cleaner UI.
