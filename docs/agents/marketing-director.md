# marketing-director

`marketing-director` is the GTM department's orchestrator: the runtime's first (and, as of
2026-09-09, only) **department orchestrator** — a sanctioned-Opus mission runner, not an oversight
watcher (CLAUDE.md §13, "The department-orchestrator class"). It runs operator-launched missions
("a highly converting website," "ad campaigns ready to initiate") through a fixed six-phase
lifecycle, dispatching a bench of six findings-only sonnet specialists plus the existing
`market-analyst` seat, and it is the **only** department seat holding the `Agent` tool
(`agents/marketing-director.md` frontmatter's `tools:` key). It exists as a mission-scoped role, not a standing watch,
because GTM work is fundamentally project-shaped (a campaign, a site rebuild, a pricing-page
overhaul) rather than a continuous audit — the oversight roster's agents watch an app that already
exists; this department builds the go-to-market artifacts around it, on demand.

## Model & tools

- **Model:** `opus` (`agents/marketing-director.md` frontmatter's `model:` key) — sanctioned under CLAUDE.md §10's
  2026-09-05 extension (`~/.claude/plans/marketing_team_roster_plan.md`); the mechanical mirror is
  `hooks/sync_agent_rules.OPUS_AGENTS` plus `knowledge/model_policy.json`'s `agent_pins` entry
  (confirmed `opus`, 2026-09-09). Consolidating cross-seat dissent into a mechanical convergence
  verdict, authoring every downstream implementation dispatch from a spec's structured fields, and
  running the mission lifecycle itself are judgment-and-synthesis work, not mechanical detection —
  consistent with why the other five oversight Opus seats sit at that tier.
- **Tools:** `Read, Grep, Glob, Bash, Agent` (`agents/marketing-director.md` frontmatter's `tools:` key) — **no `Write`, no
  `Edit`, at all.** This is tool absence, not a scoped allowlist: the director cannot modify any
  repo file directly, on any path, ever (`agents/marketing-director.md`, "## No Write or Edit
  tool"). `Agent` is the one capability that distinguishes it from every specialist on its bench —
  a dispatched agent cannot itself dispatch further agents, so a specialist holding `Agent` would be
  dead weight and surplus authority (`knowledge/marketing_director_primer.md` §1).

## When it's dispatched

Mission-dispatch only, no schedule — trigger is `/gtm "<goal>"` (`.claude/skills/gtm/SKILL.md`),
which dispatches `marketing-director` with the goal string verbatim. **The sanctioned dispatch path
is a direct top-level `Agent` call, never inside a `Workflow` tool call** — a workflow-spawned agent
structurally cannot hold the `Agent` tool ("Agent is disabled for this session, in subagents as
well as here" — a platform nesting restriction, confirmed live 2026-09-05 on this agent's first
mission attempt, CLAUDE.md §13). A director invoked inside a `Workflow` is silently reduced to
read-only analysis: it cannot run PRODUCE, cannot fan out its bench, and — holding no Write/Edit
tool regardless — cannot land any mission artifact either way; the primer instructs it to report
this state and halt rather than simulate its bench's output
(`knowledge/marketing_director_primer.md` §4).

## The six-phase mission lifecycle

Every mission runs INTAKE → CLARIFY → PLAN → PRODUCE → CONVERGE → PRESENT
(`knowledge/marketing_director_primer.md` §2, carried **verbatim** — the agent file instructs
reading it in full rather than operating from a paraphrase, `agents/marketing-director.md` §"Read FIRST", item 1):

1. **INTAKE** — record the operator's goal verbatim, never paraphrased or "cleaned up."
2. **CLARIFY** — fan out to the bench in parallel; each seat returns only the questions it needs
   answered before producing anything, tagged REPO / RESEARCHABLE / ANSWERED-IN-A-RULED-DOC /
   OPERATOR. Genuine OPERATOR residue is batched into ONE numbered card set (2-4 options plus a
   free-answer field per question) — never one card per question. The card surface is resolved
   mechanically via `repo_manifest.py get operator_input`, falling back to
   `<gtm.missions_dir>/OPERATOR_QUEUE.md` when the repo names none.
3. **PLAN** — a mission plan with mechanically-checkable success criteria, routed through the
   existing plan-review boundary (the standing Opus plan-review gate, never a second one this class
   invents), then approved by the operator as a decision card.
4. **PRODUCE** — fan out to the bench per workstream, partitioned by file/artifact so no two seats
   collide. Every returned artifact is a SPEC or DRAFT, never a live repo edit; a spec missing any
   mandated field (exact target, current state, intended state, success criterion, evidence) is
   refused at intake, not patched around.
5. **CONVERGE** — see "Convergence" below.
6. **PRESENT** — every artifact plus the evaluator's verbatim verdict, on a STOP condition, never
   paraphrased or softened even when it disagrees with the director's own read of the round.

## Convergence — mechanical, not a claim

"They all agree" is never an agent's claim to make (`knowledge/marketing_director_primer.md` §3).
Round shape: produce/fix → lane-scoped cross-review (each seat judges only artifacts inside its own
lane; no voting, no seat overriding another's lane) → the director records every verdict →
consolidates findings by shared root-cause key (ten symptoms of one defect become one fix) →
parallel fix wave → **re-run the round from the top**, never a narrow per-fix spot-check. The
director is the **sole writer** of the mission artifact and the dissent ledger — no specialist ever
appends to either. The exit contract is computed by an offline evaluator,
`~/.claude/tools/gtm/exit_contract.py` (assertion ids `GTM-CONV-01/02/03`,
`~/.claude/tools/gtm/MISSION_SCHEMA.md` for the schema), over the ledger at
`<gtm.missions_dir>/gtm_reviewed.jsonl` — never the director's own narrative judgment. It evaluates,
at minimum: no blocker-severity cause still recurring; no fix caused a regression (a prior
concurrence flipping to dissent because of a different artifact's fix); every mandated judge
returned a verdict for every in-scope artifact with no dissent left open. **Narrowing a round's
scope specifically to dodge an open dissent is a bypass of the exit contract, never a legitimate
move** — the primer names this the single most important discipline in the whole document, because
it is the failure mode that makes "convergence" theater instead of a real gate. Rounds carry
explicit knobs (how many CLEAN rounds count as "done," a hard round cap, and a **snowball stop** —
a round ending with MORE open dissents than the round before it halts immediately, evidence the fix
approach itself is wrong rather than that one more round will help).

## Its bench

Six sonnet specialists — `conversion-architect`, `brand-architect`, `content-strategist`,
`seo-architect`, `paid-acquisition-strategist`, `pricing-economist` — plus the existing
`market-analyst` seat participating in this department (`agents/marketing-director.md` §"Your bench"). Each
is findings-only: none edits a repo file, touches git, or mutates any external system, and none
holds the `Agent` tool. The director may also dispatch `browser-ops` for screenshot evidence and
`research-scout` for tools/OSS prior art.

**Fan-out bounds, enforced by the director itself, every mission** (`agents/marketing-director.md`,
"## Fan-out bounds"): max 6 parallel seat dispatches at once; a live pacer-status check
(`agent_budget.py status`) before every fan-out, batching down when recommended capacity is lower
than the intended fan-out; back off and serialize on a pacer denial rather than retry-looping; a
per-mission dispatch ceiling of 60, past which the mission halts to the operator rather than
continuing to spend; a `TaskStop`-based kill path with the dispatching session (never the director
itself) setting the mission's `status` to `halted`.

## Grounding

Runtime discipline: `knowledge/marketing_director_primer.md` — the department-orchestrator class,
the full lifecycle, convergence/ledger/evaluator mechanics, fan-out bounds, inter-department
communication, and the injection fence, carried verbatim rather than summarized in the agent file.
Repo-local grounding: `<repo>/.claude/oversight/marketing-director.md` — this product's GTM
surfaces, pricing source-of-truth doc, mission-artifact directory, dissent-ledger path, exit-contract
module, and the department's inbox convention. Missing dossier ⇒ declared DEGRADED, never an
invented mission directory, ledger path, or app-specific fact
(`agents/marketing-director.md` §"Read FIRST", item 2). ExampleApp carries this dossier at
`.claude/oversight/marketing-director.md` (confirmed present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/marketing-director.md`, "## Boundaries"): never edits or writes any
repo file itself — every write is directed to a separately-dispatched landing agent; never files,
transitions, or closes an issue itself (the dispatching session does, through the standing board
rules); never pushes, opens a PR, merges, or deploys; never mutates any external system (no
ad-platform, CMS, GBP, or account write of any kind); never ranks or sequences product work
(`launch-director`'s lane, cited by name, never silently absorbed into a mission decision); never
passes a `model:` override on a dispatch outside a minted, single-use exception; never accepts a
bench seat's claim of consensus as a substitute for the evaluator's own mechanical verdict.

## How it fits with other agents / the GTM department

`marketing-director` is a peer to the oversight roster's Opus agents, not a member of it — it
carries no scheduled trigger and no row in CLAUDE.md §13's oversight table; its own row lives in
that section's second table (the department-orchestrator class). It never substitutes for
`code-reviewer`/`trust-architect` at a commit boundary — every landing a mission produces still
passes the repo's own pre-commit review gate; the mission's own convergence rounds are a lane-scoped
specialist cross-review, not a replacement for that gate
(`knowledge/marketing_director_primer.md` §5). The department's own durable inbox is the
`dept:marketing` GitHub label (CLAUDE.md §13): any loop, director, or session with a
marketing-relevant finding files an issue with that label, and the CLARIFY phase reads that open
queue before drafting operator questions. `market-analyst` supplies dated competitor/market facts
into missions but is not part of this department's dedicated headcount — it is an existing
oversight-roster seat participating across departments, mirrored in its own dossier's
RESEARCHABLE-lane fence. `docs/subsystems/gtm-department.md` is the orienting subsystem doc for the
department as a whole; this page covers the director agent specifically.

## Example invocation

The operator runs `/gtm "get our pricing page converting better before the next launch push"`. The
director records the goal verbatim, fans out CLARIFY to `conversion-architect` (funnel friction on
the current pricing page), `pricing-economist` (whether the COGS basis still holds), and
`brand-architect` (visual-identity read) in parallel, batches the genuine OPERATOR-tagged residue
(e.g. "should the annual-plan discount be shown above or below the fold" — a taste call) into one
numbered card, and only proceeds to PLAN once that card is resolved. PRODUCE fans out specs to the
relevant seats; CONVERGE runs lane-scoped cross-review until the evaluator reports `GTM convergence:
3 of 3`; PRESENT hands the operator the finished specs plus that verbatim verdict for approval
before any `implement` dispatch lands them.
