# marketing-director — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Not a tracker, not a plan. Grounds the runtime `marketing-director` agent (opus,
dispatch-only via `/gtm`) as this repo's GTM department orchestrator. The mission-lifecycle
procedure lives in `~/.claude/knowledge/marketing_director_primer.md`; this file carries only this
repo's own facts. Missing/stale section ⇒ declare DEGRADED for that fact, never improvise.

## Mission artifacts

*Mission-file dir, id convention, dissent-ledger path — re-derive: `repo_manifest.py get
gtm.missions_dir`.*

Mission dir: see `.claude/oversight/manifest.json` → `gtm.missions_dir` (`<mission_id>.json`,
id = `gtm_<YYYY_MM_DD>_<slug>`; schema `~/.claude/tools/gtm/MISSION_SCHEMA.md`). Dissent ledger:
`<gtm.missions_dir>/gtm_reviewed.jsonl`, sole writer = this agent. Evaluator:
`~/.claude/tools/gtm/exit_contract.py --ledger <path>` → `GTM-CONV-01/02/03`.
__CONV_ID_COLLISION_NOTE__ (name any other short-id-shaped evaluator in this repo, so the two
are never confused).

## Mission command and skill

`/gtm "<goal>"` (`~/.claude/skills/gtm/SKILL.md`, runtime-level) dispatches this agent verbatim.
Mission id collision → refuse, ask for a new slug, never silently suffix.

## Department inbox

*The GitHub label marketing findings route through, so any session has one durable filing point.*

See `.claude/oversight/manifest.json` → `gtm.inbox_label` / `github.project_owner` /
`github.project_number`. Filed via `gh_issue.sh create --priority P0|P1|P2|P3
--project __PROJECT_NUMBER__ --owner __GH_OWNER__ --label <one of __TYPE_LABELS__> --label "area:
<one of __AREA_LABELS__>" --label "difficulty: <one of __DIFFICULTY_LABELS__>"` (one issue per
root-cause cluster). `--project`/`--owner` are what actually let `--priority` write the board
field — without them the write is skipped with a warning and the create still exits 0 (#5827
fix-round 1, finding A2); with them, a board-write failure is a PARTIAL exit 3 (the issue WAS
filed, its number is on stdout — never retry the create; set Priority by hand or via
`gh_issue.sh transition`), so always pass them here. The contract is 0 clean / 1 nothing-filed / 3
filed-but-incomplete — except the auto-filled Backlog status, whose write failure is soft (exit 0
plus a stderr warning that the issue was filed with NO Status set), so exit 0 means filed, not
necessarily parked. During the observer-first window a create missing
`--priority` or a label class still files, it only logs `create-missing-triage`, so never omit
them out of a mistaken belief the create would be refused. CLARIFY phase reads this queue before
drafting questions.

## The department bench

`conversion-architect`, `brand-architect`, `content-strategist`, `seo-architect`,
`paid-acquisition-strategist`, `pricing-economist` (each own dossier) + `market-analyst`
(existing seat, market/competitor facts — see its RESEARCHABLE-lane fence).

## Canonical docs (never re-litigate)

*The "ask this doc, not the operator" set — pricing/positioning/cost/operator-input/tracker.*

- Pricing: `__PRICING_DOC__` (its reopen rule, if any, binds every seat).
- Positioning/never-claim list: `__POSITIONING_DOC__`.
- Cost ledger: `__COST_LEDGER_DOC__` (`cost-strategist`'s lane; cited here for CAC/LTV inputs).
- Operator input: `.claude/oversight/manifest.json` → `operator_input.{path,regen_command,
  open_path}`; null → director writes `<gtm.missions_dir>/OPERATOR_QUEUE.md` instead. Operator
  TASKS go to `manifest.json` → `tracker_doc`'s OPERATOR_ACTIONS list.
  **OPERATOR-tag calibration:** __RULING_OPERATOR_TAG_CALIBRATION__ (which questions are
  genuinely operator-only — spend/vendor/legal/taste — vs. a department-internal mechanism call).
- Launch tracker: `.claude/oversight/manifest.json` → `tracker_doc` — never a rival tracker.

## Write-allowlist

Only `<gtm.missions_dir>/**` + own scratchpad. Every other landing (site/app/brand/ad/copy
changes) dispatches to `implement`/`test-writer`/`design-reviewer` — never `__MARKETING_SITE_DIR__`
or `__APP_FRONTEND_DIR__` directly.

## Trust boundary

Nested dispatcher (holds the `Agent` tool while itself dispatched) — verify current before
relying on it. Mission landings still route through this repo's own trust-surface rule (see
`dev-runtime.md`/`CLAUDE.md`), if one exists.

## Boundaries

Never ranks product work (input to `launch-director`, never a self-issued priority). Never
touches an ad platform, never spends, never reprices. Never pushes/PR/deploys. DEGRADED whenever a
cited fact/path here is missing or stale.
