# Glossary

Words this repo uses in a specific way. Each entry says where the definition comes from, so you can
check it against the code or the docs.

In this public repo, `CLAUDE.md §N` means `OPERATING_CONTRACT.md §N`.

Bare `#1234` and `GH #1234` numbers in comments and docs, and `OtherApp #N` or similar forms, are
tracker numbers from the author's private product repos, redacted for publication. You cannot
follow them from here; the surrounding text says what they were about.

## A to Z

**bench** — The specialist agents a department director dispatches, plus its support seats. The
director holds the `Agent` tool; the bench cannot dispatch further. `marketing-director` and
`venture-director` each name their own bench in their agent file.
Source: `agents/marketing-director.md` ("Your bench"); `agents/venture-director.md`.

**boundary** — A point where a review is required. There are two and only two: the *plan boundary*
(before a substantial plan is implemented) and the *commit boundary* (before `git commit`). Nothing
is reviewed per edit. Gate 3b enforces the commit boundary. In `docs/subsystems/review-ladder.md`,
"one boundary" is one continuous chain of fix-and-recheck rounds on the same pending commit.
Source: `OPERATING_CONTRACT.md` §10; `hooks/precommit_review_gate.py`.

**claim, mutex** — A *claim* is a file in `~/.claude/.file_claims/` listing the paths one commit is
about to land. It is taken all-or-nothing, so two committing agents cannot each hold half of what
the other needs (no deadlock, only a bounded wait). The *mutex* is one extra synthetic claim per
repo (`//commit-mutex::<repo path>`), so only one commit is in flight per repo even when the real
paths do not overlap. A path claim expires after `CSA_FILE_CLAIM_TTL_SEC` (default 300 s), the
mutex part after `CSA_COMMIT_MUTEX_TTL_SEC` (default 60 s).
Source: `hooks/file_claims.py` (module docstring, `MUTEX_PREFIX`).

**CSA** — The prefix on this runtime's environment variables (`CSA_ENFORCE`, `CSA_DISABLE_HOOKS`,
`CSA_ALLOW_GIT_STATE_OPS`, `CSA_PACER`, `CSA_NO_COMMIT_MUTEX`, and others) and on a few log and doc
strings. It is a historical acronym, kept so existing settings and scripts keep working. It is not
a product name, and this repo does not expand it.
Source: `hooks/_lib.py` (`disabled()`, `enforcing()`); `hooks/pretooluse_bash.py` (docstring, POLICY).

**dossier** — A repo-local file, `<repo>/.claude/oversight/<agent>.md`, holding the facts about
*that* repo an agent needs: its commands, trackers, and where things live. Skeletons are in
`templates/oversight/`; `scripts/init_repo.sh` copies them into a repo; `repo_manifest.py doctor`
reports the ones still holding placeholders. An agent with no dossier says it is degraded instead
of guessing. Pair of *primer*.
Source: `docs/subsystems/knowledge-and-primers.md` ("Primer vs. dossier"); `docs/getting-started.md`.

**enforcing, log-only** — Hooks start in *log-only* mode: a gate that blocks writes a `would-block`
row to `~/.claude/.enforcement/log.jsonl` and allows the call. They *enforce*, and also emit the
deny, when any of these holds: `CSA_ENFORCE=1` is set in the environment, `~/.claude/.enforce`
exists, or the nearest enclosing git repo has a `.claude/.csa-enforce` marker file. `CSA_DISABLE_HOOKS=1`
turns every hook off and wins over all three.
Source: `hooks/_lib.py` (`enforcing()`, `disabled()`).

**escape variable** — `CSA_ALLOW_GIT_STATE_OPS=1`. The hook reads it from its own process
environment on every call, so while it is set in the environment Claude Code was launched with,
every git-state or gcloud-identity block (gates 1, 1b, 1c, 2) is let through and logged as
`escape-allowed`. It is a standing switch for that process, not a one-command override. An agent
cannot set it for the hook: a variable assigned inside a command never reaches the hook's own
environment. Writing the variable's name inside a command is denied by those four gates
(`inline-escape-var-forbidden`, never overridden by the variable), but like every deny only in
enforcing mode; in log-only mode it is logged and allowed.
Source: `hooks/block_branch_ops.py` (`ESCAPE_VAR`); `hooks/pretooluse_bash.py`
(`_escape_hatch_active`, `_finish`).

**fable** — A model tier priced above `opus` (the gate's docstring says about twice). No agent is
pinned to it: no entry in `knowledge/model_policy.json` `agent_pins` names it, and `FABLE_AGENTS` in
`hooks/sync_agent_rules.py` is empty. For a pinned agent, gate T1 denies a dispatch that asks for
`fable` (`pin-tier-mismatch`) unless the operator has written a single-use grant with
`scripts/grant_model_exception.sh`; a token an agent mints for itself can never cover it. T1 does
not check the model named for a type that has no pin (the built-in `Explore`, `Plan` and `claude`,
or a type with neither an agent file nor an `agent_pins` entry; `general-purpose` has no file but has a pin, so T1 does check it).
Source: `hooks/model_pin_gate.py` (module docstring; `decide`).

**fail open, fail closed** — When a gate cannot decide because it hit an error, *fail open* means
allow the call; *fail closed* means deny it. Almost every gate fails open on its own errors, so a
broken hook never wedges a session. A few fail closed where allowing would be a bypass: a command
the gate cannot tokenize but that mentions its tool, and a pathspec the review gate cannot resolve.
The per-gate table is in [`ARCHITECTURE.md`](ARCHITECTURE.md).

**gate numbering** — The Bash dispatcher runs its gates in this order and stops at the first
block: 1, 1b, 1c, 2, 3, 3b, 3c, 4, 5, 5b, 6. The number is the position in that order. A *letter*
marks a gate added after the first numbering and slotted into its place without renumbering the
others, so an older reference to "gate 3" or "gate 4" still means the same gate. Gate 3b (review
before commit) was added after gate 3. Gates on the Task path are named T1 and T2. Gate 6 and
`issue_create_observer` only observe and never block.
Source: `hooks/pretooluse_bash.py` (module docstring); `hooks/pretooluse_task.py`;
`docs/subsystems/gate-chain.md`.

**GTM** — Go-to-market: the department of agents that plan and draft marketing work for a company,
run by `marketing-director`. They advise and draft; none posts, publishes or spends.
Source: `docs/subsystems/gtm-department.md`; `agents/marketing-director.md`.

**hub card (historical)** — An entry in the author's *operator hub*, a numbered decision queue where
agents parked questions and approvals only the operator could answer. "Hub card 53" or "hub #57" in
this repo cites one of those entries. The hub has since been replaced by labeled GitHub issues, and
the cards are not in this repo, so such citations cannot be followed.
Source: `skills/lane-cleanup/SKILL.md`; `docs/subsystems/skills-and-commands.md`.

**lane** — Two unrelated senses.
(1) *Responsibility lane*: the area one agent owns and the others stay out of. It is the "lane"
column of the roster tables and the "not for X, use Y" line in each agent's description.
Source: `docs/subsystems/oversight-wheel.md`; `docs/subsystems/gtm-department.md` ("Lane fences").
(2) *Git lane*: one eligible issue worked in its own git worktree and branch, opened and reaped only
by `scripts/lane.sh` (`open`, `reap`, `abandon`), usually driven by the `/lane-start` and
`/lane-cleanup` skills. Every state change appends a row to `~/.claude/.lanes/lanes.jsonl`.
Source: `scripts/lane.sh` (header); `skills/lane-start/SKILL.md`.

**lease** — A file in `~/.claude/.agent_budget/` recording one live sub-agent against the
machine-wide concurrency ceiling (`CSA_ANTHROPIC_CEILING`, default 8). Gate T2 takes one per
dispatch only when `CSA_PACER=1`; `release_hook` removes it when the agent stops, and an unreleased
one goes stale after `CSA_LEASE_TTL_SEC` (default 3600 seconds). The browser pool's numbered
`playwright-NN` slots are leased separately, by `live-testing/browser_pool.py`.
Source: `hooks/agent_budget.py` (docstring); `live-testing/browser_pool.py`.

**mission** — A department's unit of work: one operator-launched goal run through a fixed six-phase
lifecycle (intake, clarify, plan, produce, converge, present), recorded in a mission file whose id
must not already exist. Directors run missions; the oversight roster does not.
Source: `knowledge/marketing_director_primer.md` §2; `agents/marketing-director.md`.

**operator** — The human who owns the machine and the repositories. Agents never act as the
operator. Only the operator approves a push, PR, merge or deploy (contract §4), turns enforcement on
(`~/.claude/.enforce`, or a repo's `.claude/.csa-enforce`), sets the escape variable, and runs
`scripts/grant_model_exception.sh`. A
deny message that says an action is "reserved for the operator" means exactly this.
Source: `OPERATING_CONTRACT.md` §4; `hooks/pretooluse_bash.py` (`_branch_ops_block`);
`hooks/model_pin_gate.py` (operator-grant files).

**oversight roster, THE ISSUE WHEEL** — Two different things that share a doc.
The *oversight roster* is fifteen agents, eight on a schedule and seven dispatch-only, each judging
one dimension of a codebase (direction, tracker hygiene, health, consistency, tests, security,
customer-facing QA, agent design) and returning findings. Source: `OPERATING_CONTRACT.md` §13 (the
pattern); `docs/subsystems/oversight-wheel.md` (the fifteen seats).
*THE ISSUE WHEEL* (always capitalized) is one job: a nightly-or-on-demand run that triages, fixes,
lands and closes GitHub issues for a repo. It is a workflow, not a watcher; it dispatches
`board-steward`, `implement`, `test-writer` and the reviewers. Its fix and close phases are off by
default: `WHEEL_FIX_ENABLED` and `WHEEL_CLOSE_ENABLED` are `0` in `schedules/example.wheel.plist`,
and at `0` it only triages and reports. Source:
`schedules/prompts/issue_wheel.txt`; `workflows/issue-wheel-triage.js`; `schedules/example.wheel.plist`. The doc
`docs/subsystems/oversight-wheel.md` covers both; "the oversight wheel" in lower case is its
older name for the roster.

**pathspec commit** — `git commit -m "..." -- <path> [<path>...]`: a commit that names its paths
after `--`. Gate 3 denies a writing commit with no pathspec (`missing-pathspec`) or a whole-tree one
(`bulk-pathspec`), so a commit lands only what its author named. Exempt from the missing-pathspec
deny: a merge, cherry-pick, revert or rebase in progress, `--allow-empty`, and the operator's
rollback lever `CSA_NO_REQUIRE_PATHSPEC=1`. An exempt commit still goes through the staged-index
scope check.
Source: `hooks/check_staged_scope.py` (docstring); `hooks/pretooluse_bash.py` (gate 3).

**pin** — The model an agent must run on. It is the `model:` line in the agent's own frontmatter,
mirrored in `knowledge/model_policy.json` under `agent_pins`. Gate T1 compares each dispatch with it.
Source: `hooks/model_pin_gate.py` (docstring, "Resolved pin").

**primer** — An agent's portable discipline: `knowledge/<agent>_primer.md` with the agent's hyphens
written as underscores (`trust-architect` has `knowledge/trust_architect_primer.md`), read in every
repo the agent works in. It holds the doctrine, rubric and method, and no facts about any one repo. Pair of
*dossier*.
Source: `docs/subsystems/knowledge-and-primers.md` ("What a primer is").

**`${REPO:<slug>}`** — A placeholder for the root of a registered repo, so a script or ledger never
hard-codes a machine-specific path. The slug is looked up at run time in `knowledge/repo_registry.json`
(`{"repos": {"<slug>": {"root": "..."}}}`; it ships empty). An unknown slug is an error, and a bare
absolute path outside `~/.claude/` and `/tmp/` is flagged. `scripts/repo_manifest.py register` writes
registry entries.
Source: `hooks/agentarch_metric_check.py` (docstring, `resolve_command`).

**reviewer of record** — The one reviewer whose verdict counts at a commit boundary. By default it is
`code-reviewer`. For a commit touching trust-surface paths (auth, tenancy, billing, secrets, an
agent's tool grants, as the repo lists them in `.claude/oversight/trust_surface.json` or the
manifest's `security.trust_surface_globs`) it is `trust-architect`, which *substitutes* for
`code-reviewer` and never runs in addition. Gate 3b names this reviewer in its deny message but does
not check which reviewer actually ran.
Source: `hooks/precommit_review_gate.py` (`reviewer_of_record`); `docs/subsystems/review-ladder.md`
("Substitution, never stacking").

**seat** — One named role on a roster, filled by one agent definition. "Fifteen seats" is the
oversight roster; a *dispatch-only seat* has no schedule and is triggered by name.
Source: `docs/subsystems/oversight-wheel.md`; `docs/subsystems/gtm-department.md`.

**tier** — Two meanings, plus one narrow third.
(1) *Model tier*: `opus`, `sonnet` or `haiku`, the model an agent is pinned to (`fable`, above them, is never a standing pin; see its entry). Gate T1 denies a
dispatch whose tier differs from the pin (`pin-tier-mismatch`). Source: `hooks/model_pin_gate.py`.
(2) *Review risk tier*: `trivial`, `moderate` or `high`, printed by `hooks/review_risk_tier.py
<paths>`. It sets how heavy a review must be: docs-only may get a cheaper confirmatory pass; a change
touching `hooks/`, `agents/`, settings or security paths is `high` and gets a full review. It is a
helper an orchestrator consults, not a hook. Source: `hooks/review_risk_tier.py` (docstring, "TIERS").
(3) *Autonomy tier*, GTM seats only: what a seat may do without asking the operator.
Source: `knowledge/marketing_kb/shared/autonomy-tiers.md`.

**trust surface** — Code where a mistake costs money, identity or another tenant's data: auth,
tenancy, billing, secrets, webhooks, an agent's tool grants. Each repo lists its own paths; they
decide the reviewer of record.
Source: `agents/trust-architect.md`; `hooks/precommit_review_gate.py`.

**warm round, cold round** — Review rounds after the first. In a *warm* round the same reviewer agent
is continued with `SendMessage`, keeping its context, but is re-scoped to the full current diff. A
*cold* round is a fresh dispatch with no memory of earlier rounds. At most two consecutive warm
rounds are allowed on one chain, and the next full round must be cold, because a reviewer grading
fixes it asked for is not independent. `record_review.py` refuses to record a third consecutive warm
round (`--round`, `--prev` and `--warm` link the chain). The warm chain also breaks, forcing a cold
round, when the risk tier or the reviewer of record changes.
Source: `hooks/record_review.py` (`_MAX_CONSECUTIVE_WARM_ROUNDS`); `docs/subsystems/review-ladder.md`
("Full re-review rounds run WARM").
