# The GTM Department

*Summary/orienting doc. The mechanism itself lives in
[`knowledge/marketing_director_primer.md`](../../knowledge/marketing_director_primer.md) — read
that for the actual lifecycle, convergence, and injection-safety discipline. This page explains
what the department is, where its machinery lives, and what a repo must provide to run it.*

## What it is

The GTM department is a separate, mission-scoped organization from the oversight wheel — it does
not watch an app, it BUILDS go-to-market artifacts on operator-launched missions. Sixteen seats:
the orchestrator, eleven opus specialists, one shared opus seat, and three sonnet support seats.

| agent | lane |
|---|---|
| marketing-director (opus) | department orchestrator — mission lifecycle, dissent consolidation, sole operator interface |
| conversion-architect (opus) | skeptical-stranger review of every public funnel surface |
| brand-architect (opus) | marketing-surface visual identity verdicts |
| content-strategist (opus) | copy, SEO content briefs, lifecycle sequences, voice guide, video scripts |
| seo-architect (opus) | crawlability/indexation, schema strategy, Core Web Vitals |
| paid-acquisition-strategist (opus) | ad-platform strategy — advisory only, zero write access |
| pricing-economist (opus) | COGS-currency + price-position challenge — questions, never reprices |
| video-producer (opus) | shot lists, narration-visual pairing, screen-flow scripts, post-render viewing-review verdicts |
| local-presence-architect (opus) | local listings, NAP consistency, compliant review acquisition and response policy |
| social-media-strategist (opus) | organic social calendar, format mix, cadence caps, community policy; never posts |
| measurement-architect (opus) | analytics events, tag governance, consent, conversion tracking, metric definitions |
| revenue-ops-architect (opus) | speed-to-lead, lead routing, CRM hygiene, follow-up cadences; never contacts a lead |
| market-analyst (opus, shared runtime seat) | market/competitor facts, participates across departments |
| gtm-analyst (sonnet) | read-only analyst: drafts scoreboard values, weekly report, reconciliations |
| gtm-drafter (sonnet) | drafts replies, posts, listing text from doctrine; proposals only |
| gtm-checker (sonnet) | applies lane checklists to drafts and proposals; pass/fail verdicts; never the drafter |

`marketing-director` is the only seat holding the `Agent` tool — it is the sole seat capable of
dispatching the other fifteen, and the sole writer of every mission artifact. Every specialist is
findings-only (never edits a repo file directly; a separately-dispatched `implement`/`test-writer`/
`design-reviewer` lands whatever a spec calls for). The three sonnet support seats hold read-only
tools (`Read, Grep, Glob`) and are dispatched by the director.

A separate **venture department** exists alongside this one (`venture-director`,
`capital-and-exit-strategist`, `bizdev-outbound-strategist`, `partner-recruiter`,
`hiring-specialist`); it is not part of the GTM mission lifecycle. See
[`../agents/venture-director.md`](../agents/venture-director.md).

## Mission lifecycle, in one paragraph

A mission is launched with `/gtm "<goal>"`, which dispatches `marketing-director` as a direct
top-level `Agent` call (never inside a `Workflow` — that structurally strips the `Agent` tool) with
the goal string verbatim. The director runs it through six phases: INTAKE (record the goal
verbatim) → CLARIFY (fan out to the bench for open questions, tagged REPO/RESEARCHABLE/
ANSWERED-IN-A-RULED-DOC/OPERATOR, with OPERATOR residue batched into one numbered card set) → PLAN
(a reviewed plan with mechanically-checkable success criteria, approved by the operator as a
decision card) → PRODUCE (bench fan-out, one spec/draft artifact per workstream, partitioned by
file so no two seats collide) → CONVERGE (lane-scoped cross-review, a shared dissent ledger, and a
mechanical exit contract — never an agent's own claim of consensus) → PRESENT (every artifact plus
the evaluator's verbatim verdict, never softened). Convergence and injection-safety mechanics are
covered in full in the primer; this doc does not restate them.

## Where the machinery lives now

Everything below is runtime-level — a repo never carries its own copy, the same shadowing rule
that applies to any other runtime skill/agent twin:

- **Entry point:** `~/.claude/skills/gtm/SKILL.md` — a user-level skill, invoked as `/gtm "<goal>"`
  in any session on this machine (Personal-level skills resolve ahead of a same-named project-level
  one, the opposite precedence direction from agents).
- **Convergence evaluator:** `~/.claude/tools/gtm/exit_contract.py` (assertion ids
  `GTM-CONV-01/02/03`) + its test suite `~/.claude/tools/gtm/tests/test_gtm_exit_contract.py`.
  Takes `--ledger <path>` (defaults, when omitted, to `<gtm.missions_dir>/gtm_reviewed.jsonl`
  resolved at runtime via `repo_manifest.py get gtm.missions_dir` — never a hardcoded product
  path) and `--mission-id <id>` (required — the ledger is one shared file across every mission
  ever run).
- **Schema reference:** `~/.claude/tools/gtm/MISSION_SCHEMA.md` — the mission JSON and dissent
  ledger row schemas, the `#4893`-class regression note (a different, unrelated evaluator once
  reported full convergence over 9 real open dissents — GTM-CONV-03 exists specifically to make
  that failure class impossible here), and the sole-writer rule.
- **Sixteen primers:** `knowledge/marketing_director_primer.md` (the department-orchestrator class
  + full mission lifecycle) plus one `knowledge/<agent>_primer.md` for each of the eleven
  specialists and the three support seats (`gtm_analyst`, `gtm_drafter`, `gtm_checker`).
  `market-analyst`'s primer (`market_analyst_primer.md`) lives with the oversight roster (it's a
  shared seat, not GTM-only) and is the sixteenth.

## What a repo must provide

Every path the machinery above touches is resolved through that repo's own
`.claude/oversight/manifest.json` — never a literal baked into runtime code. At minimum:

- `gtm.missions_dir` — where mission JSON files and the shared `gtm_reviewed.jsonl` ledger live in
  that repo. Missions are repo-local artifacts; they are never exported to the runtime mirror.
- `gtm.inbox_label` — the GitHub label that is this department's durable cross-department inbox
  (any loop, director, or session with a marketing-relevant finding files an issue with that
  label; the department's own CLARIFY phase reads it before drafting operator questions).
- `operator_input` — that repo's card surface (kind/path/regen_command/open_path), or `null` to
  use the runtime fallback: numbered cards written to `<gtm.missions_dir>/OPERATOR_QUEUE.md`.
- A repo-local grounding dossier per seat, `<repo>/.claude/oversight/<agent>.md`, for the director
  and the specialist seats — a missing dossier means that seat DEGRADED-self-declares rather than
  improvising facts about the app. The three sonnet support seats expect no per-agent dossier; they
  ground in the company pack and the specialist dossier(s) a dispatch names. `python3 ~/.claude/scripts/repo_manifest.py doctor` reports the current gap set for a repo.

## Registration

`~/.claude/tools/gtm/tests` is this department's own test suite, collected under the runtime's
`~/.claude/pyproject.toml` pytest config (`[tool.pytest.ini_options]` registers no paths of its
own — it is discovery configuration, not a per-suite registry). Run command: `python3 -m pytest ~/.claude/tools/gtm/tests -q`.

## Lane fences

Two seats never silently duplicate or contradict each other on adjacent questions — see each
seat's own dossier for the exact fence line: market/competitor facts belong to `market-analyst`,
tools/OSS/prior-art facts belong to `research-scout`; vendor/FinOps spend accounting
(`cost-strategist`) is a different question from ad-spend effectiveness
(`paid-acquisition-strategist`) and from customer-price strategy (`pricing-economist`); visual-
system verdicts (`brand-architect`), copy (`content-strategist`), and funnel-structure verdicts
(`conversion-architect`) are three different lanes on the same page.
