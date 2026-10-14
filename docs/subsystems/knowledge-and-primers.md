# Knowledge & Primers

*Summary/orienting doc for `~/.claude/knowledge/`.*

## What lives here

```
~/.claude/knowledge/
  admin_portal_architect_primer.md       primer (admin-console seat, added 2026-09-10)
  agentarch_recommendations.jsonl        standing recommendation ledger
  agentic_patterns_evidence_2026_08_30.md supporting evidence doc for one audit
  agentic_systems_architect_primer.md    primer
  agentic_systems_evidence_2026_08_25.md supporting evidence doc for one audit
  karpathy/                              distilled cited reference corpus (research-scout dispatch 2026-08-31; NOT mirrored)
  agricultural_futures_primer.md         primer (trading-strategist, ag-futures lane)
  board_steward_primer.md                primer
  code_quality_architect_primer.md       primer
  consistency_auditor_primer.md          primer
  cost_strategist_primer.md              primer   (FinOps seat, added 2026-09-01)
  design_reviewer_primer.md              primer
  launch_director_primer.md              primer
  market_analyst_primer.md               primer
  model_policy.json                      machine-readable model/review policy
  model_policy.md                        human-readable companion to the above
  oversight_install.md                   oversight wheel operational reference
  product_qa_primer.md                   primer
  repo_registry.json                     ${REPO:slug} resolution table
  research_ledger.jsonl                  research-scout/market-analyst findings ledger
  research_scout_primer.md               primer
  research_scout_runtime_notes.md        runtime-target grounding notes (research-scout)
  sentinel_primer.md                     primer
  test_architect_primer.md               primer
  trading_strategist_equities_primer.md  primer (trading-strategist, equities lane)
  trust_architect_primer.md              primer
  wheel_repos.json                       per-slug wheel config, generated from each repo's
                                          manifest by repo_manifest.py register; field
                                          reference in oversight-wheel.md
```

Primers: run `ls ~/.claude/knowledge/*_primer.md | wc -l` (the literal count drifted three times;
the command is the source of truth) — one per standing oversight agent plus `design-reviewer`,
`research-scout`, `market-analyst`, `cost-strategist`, `admin-portal-architect`, the GTM department
seats, and `trading-strategist`'s two lane primers. Of the non-oversight primer owners,
`design-reviewer` and `trading-strategist` sit outside the §13 table; `research-scout`,
`market-analyst`, `cost-strategist`, and `admin-portal-architect` ARE §13 dispatch-only rows; the
GTM department seats sit in §13's separate department-orchestrator table. None of these primer
owners sit inside the §13 oversight table proper — review-boundary or dispatch-only agents, not
scheduled watchers.

## What a primer is

A primer is an agent's **portable, product-agnostic discipline** — externally-sourced doctrine
(named sources cited per section), reasoning frameworks, and named failure modes, with zero
app-specific facts. It's written once and used by that agent in *any* repo on this machine.

Real structure, `~/.claude/knowledge/launch_director_primer.md`:

```
# Launch Director Primer
## 1. Prioritization frameworks — and their named failure modes
## 2. Riskiest-Assumption Testing (RAT)
## 3. Gold-plating vs. scope-creep
## 4. Launch-readiness review practice
## 5. The weekly state-of-the-product report — 7 recurring sections
## How this agent applies it
```

Every numbered section is doctrine with citations (e.g. RICE/ICE/WSJF frameworks, sourced external
material, each claim marked `[unverified — confirm at the source before citing outward]` when it
hasn't been independently re-verified). The closing `## How this agent applies it` section is where
the primer turns doctrine into concrete instructions for *this* agent — e.g. "always output a ranked
queue in a machine-readable block... never prose-only ranking" (`launch_director_primer.md:124`).
Nothing in either section names a repo, an account, a file path, or a count belonging to one app.

## Primer vs. dossier

A primer is **runtime-level** — one file, read by that agent in every repo it works in. A
**dossier** is the opposite: **repo-local**, at `<repo>/.claude/oversight/<agent>.md`, and carries
only the facts specific to that app — trackers, incident history, staging account references, the
per-dimension commands to actually run something. `code_quality_architect_primer.md:4-7` states the
split directly:

> "Repo-specific facts — the module inventory, which standard applies to which directory, the scan
> command, known-and-accepted debt — live in each repo's own
> `.claude/oversight/code-quality-architect.md` dossier; this primer carries none of them and names
> no repo by default."

ExampleApp's dossiers live at `.claude/oversight/` (one per oversight agent, plus
`dev-runtime.md` for the generic dev agents). A missing dossier means the agent declares itself
**degraded** for that repo rather than improvising app facts it doesn't actually have.

## `model_policy.json` / `model_policy.md`

`model_policy.json` is the single machine-readable source of truth for: which model tier each *kind*
of work gets by default (`task_defaults` — e.g. `poll_report: haiku`, `review_boundary: opus`), which
model each named agent in `~/.claude/agents/` is pinned to (`agent_pins`), the escalate-on-churn
rules (two failures on the cheap tier escalates to the capable tier on attempt three; a finding
demoted in verification for reasoning quality re-runs one tier up; a stabilized recipe can
de-escalate after one calibration comparison), and session rules for unattended jobs (scheduled
sessions always run `sonnet`; no unattended Opus loops; the risk-tier review ladder). `model_policy.md`
is the prose explanation of the same file — if the two ever disagree, the JSON wins.
`~/.claude/hooks/model_pin_parity.py` is the report-only checker that verifies every agent file
actually declares the model this policy pins it to.

## `repo_registry.json` — the `${REPO:slug}` mechanism

A tiny table (currently two entries: `exampleapp` and `agency`, each with a `root` path) that
lets a *runtime* script or ledger reference a product repo **symbolically** instead of hardcoding an
absolute path that would be wrong on a different machine or for a different app. A `metric_command`
or similar field can write `${REPO:exampleapp}` instead of `/Users/.../ExampleApp`, and
`~/.claude/hooks/agentarch_metric_check.py`'s resolver expands it at run time.

Real usage — one of the standing recommendations in `agentarch_recommendations.jsonl` (AA-0004)
carries this `metric_command`:

```
grep -c seven ${REPO:exampleapp}/CLAUDE.md
```

The slash command `~/.claude/commands/sweep.md` explains the mechanism inline (step 3): "every
registered repo's root is automatically an allowed bounds-check root, so no trailing CLI argument is
needed for a repo that is already registered." **`repo_registry.json` is GENERATED, not
hand-edited** — `repo_manifest.py`'s `_write_json_if_changed` is the only writer. To add or change a
registered repo: edit that repo's `<repo>/.claude/oversight/manifest.json`, then run
`python3 ~/.claude/scripts/repo_manifest.py register` — never edit `repo_registry.json` directly (a
hand edit survives only until the next `register` run overwrites it). A root passed as a trailing CLI
argument to a command like `/sweep` is only for a genuine one-off not yet worth registering via a
manifest.

**Consumers with side effects.** Most readers only turn a slug into a path, but three act on what the
registry lists, so a registry change is a change to all of them:

- `scripts/disk_janitor.sh` (the reaper that runs unattended with `--apply`) sweeps
  `<root>/.claude/worktrees/` of **every** registered repo. `repo_manifest.py register`, run for any
  reason, therefore adds that repo's worktrees to the reaper's next run (its per-worktree guards —
  registered worktree, clean, merged, old enough, not in use, disposable-only ignored content — still
  apply). A missing or empty registry means it sweeps no repos and says so; `DISK_JANITOR_REPOS`
  replaces the registry for a single run.
- `schedules/run_oversight_job.sh` takes the browser-pool priming script
  `scripts/prime_browser_pool.sh` from the registered repo that holds it, and **runs** it, for any job
  that sets `OVERSIGHT_PRIME_APP`. The optional `OVERSIGHT_PRIME_REPO` env var names the owning slug;
  without it the lookup needs exactly one registered repo with that script, so registering a second
  repo that carries it makes the lookup ambiguous and the pre-flight is skipped (a
  `WRAPPER: prime pre-flight not run - <reason>` line lands in the job's `.err.log`) until the variable
  names the owner.
- `hooks/agentarch_metric_check.py` treats every registered root as an allowed bounds-check root for
  the standing-recommendation ledger's `metric_command` strings, which are executed.

## `agentarch_recommendations.jsonl` — the standing recommendation ledger

An append-only JSONL ledger of recommendations issued by `agentic-systems-architect` audits, each
row shaped as `{id, issued_at, claim, metric, metric_command, baseline_value, target_direction,
status, checked_at, checked_value}`. What makes it a *living* ledger rather than a one-shot report:
every recommendation carries its own **re-derivable metric** (a literal shell command, often using
the `${REPO:slug}` form above), and the agent **re-scores every prior recommendation against that
command on each new run**, updating `status` (e.g. `"moved"`) and `checked_value`/`checked_at`
rather than leaving old claims to go stale. AA-0004's entry above shows this in practice — a later
re-score added an explanatory note when the same grep pattern legitimately matched new, correct text
for an unrelated reason, rather than silently reporting a false regression.
`~/.claude/hooks/validate_agentarch_ledger.py` and `agentarch_metric_check.py` are the two mechanical
guards over this file — schema/sequence/domain validation, and a repo-agnosticism regression guard
(no hardcoded repo path, no unknown repo slug) respectively; both run daily via the `daily_sweep.txt`
job and via `/sweep`.
