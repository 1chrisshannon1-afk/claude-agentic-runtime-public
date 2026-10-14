# Skills & Commands

*Summary/orienting doc for `~/.claude/skills/` and `~/.claude/commands/`.*

## Skill vs. command, in this runtime

A **skill** is a packaged instruction set — a directory containing a `SKILL.md` (optionally with
YAML frontmatter: `name`, `description`, `user-invocable`, `argument-hint`, `meta-skill`, and
helper scripts alongside it) — invoked via the `Skill` tool, either by the model deciding the task
matches its description, or by the user typing `/<name>`. The instructions load directly into the
calling turn; some skills instead run in a subagent and return a finished result.

A **command** is either (a) a Claude Code built-in (`/help`, `/clear`, `/config`, ...) or (b) a
custom slash command: a single markdown file under `~/.claude/commands/` with YAML frontmatter
(`description`, `argument-hint`, `model`) whose body is the literal procedure to run — no directory,
no helper scripts, just one file. Functionally a command and a skill can look similar (both are
markdown instructions triggered by `/name`), but a command is a flatter, simpler mechanism —
one file, no bundled tooling — appropriate for a short fixed procedure; a skill is the right shape
once the task needs its own script, multiple reference files, or `user-invocable`/`argument-hint`
metadata.

**Scope note:** this runtime (`~/.claude/skills/` + `~/.claude/commands/`) authors seven skills and
two commands — everything else in the "available skills" list a session sees each turn (`deliver`,
`code-review`, `design`, `dataviz`, `workflow-authoring`, `update-config`, `loop`, `schedule`,
`claude-api`, and others) ships as part of Claude Code itself, or lives in a product repo's own
`.claude/skills/` (e.g. ExampleApp's `gc-audit`, `architect-review`, `vision-review`,
`code-quality-audit`, `design-review`, `diagnose-*`, `audit-module` — those are product-specific,
not runtime-generic, and correctly live in that repo, not here).

## What's actually present

### `~/.claude/skills/`

**`gtm/`** (`SKILL.md` with frontmatter, argument `"<goal>"`) — thin entry point for a GTM
mission: dispatches the `marketing-director` department orchestrator with the goal passed
verbatim, running clarify → plan → produce → converge → present. Must be a direct top-level
`Agent` call, never inside a `Workflow` (§13's department-orchestrator note has the platform
reason). The real mission-lifecycle mechanics live in `knowledge/marketing_director_primer.md`,
not in this file.

**`live-testing/`** (`SKILL.md`, no YAML frontmatter — a plain instructional doc) — the durable
recipe for agent-driven live-testing via Playwright: staging-first policy (rule zero), the pool
claim/release quick-start, the two lanes (sandbox vs. OtherCompanyB prod), the standing BLOCKERS list,
and credential-handling rules. See `live-testing.md` in this docs tree for the summary, or the file
itself for the full recipe.

**`trim-memory/`** (`SKILL.md` with frontmatter + `trim_memory.py`) — per its own description:
*"Operator MEMORY.md hygiene — five pure-function reapers trim stale, resolved, dead, and oversized
entries. Dry-run by default; --apply moves files to archive. Meta-skill that operates on
`~/.claude/projects/` only."* `user-invocable: true`, `argument-hint: "[--dry-run | --apply]
[--reaper <name>] [--memory-path <path>]"`, `meta-skill: true` (it explicitly does not load company
context or touch product data — it only ever edits the operator's own `MEMORY.md` files). Triggered
urgently once a `MEMORY.md` exceeds its ~24.4 KB load-limit; the five named reapers are
`stale-dated`, `resolved-project`, `superseded-ref`, `dead-path`, `line-length`.

**`kb-sync/`** (`SKILL.md` with frontmatter, no argument) — on-demand run of `scripts/kb_sync_report.py --manual`: compares
runtime knowledge sources with the origin shas in Agency's doctrine `PORT_SOURCES.md` and lists "re-port", "rewrite review
needed" and "overlay review needed" items; posts ONE comment on OtherApp #5496 only when something changed (a real GitHub
comment, so run it only when asked); writes no Agency file; honors `schedules/DISABLED`. Why an Agency-facing skill lives in
the runtime: it reads the runtime's own knowledge sources and is the on-demand twin of the runtime scheduled job
`com.oversight.agency.kbsync` (`knowledge/oversight_install.md` §2). The manual run writes a `manual-` heartbeat so it never
refreshes the scheduled job's liveness.

**`lane-start/`** (`SKILL.md` with frontmatter, argument `<issue#>`) — **LIVE only, no dry-run mode** (exercise it
on a scratch issue). Opens one ledgered lane (CLAUDE.md §2 case (d)) via `scripts/lane.sh open`. It resolves the main
tree as the dirname of `git rev-parse --path-format=absolute --git-common-dir`, never `--show-toplevel`, and stops if
the session is already inside a worktree. Every manifest read passes `--repo <main>` as a literal path; every
`bash ~/.claude/scripts/gh_issue.sh` call runs from the main tree with `GH_REPO` pinned; `lane.sh` and `lane_orphans.sh` run from the main
tree. Order: read the issue (stop unless OPEN), draft any missing AC/UAT section as one `AC/UAT draft — unconfirmed`
comment, then the diff-gap pre-flight on an explicit non-empty file list. Step A is uncommitted main-tree edits:
stop and retry, never a card. Step B is `git diff --name-only <base_ref>...<work branch> -- <files>`: its result is
always posted on the issue, and a non-empty result is carded and stops before open. Then `lane.sh open`, keyed on
its exit code (a refusal is surfaced verbatim; an rc-0 unreachable-GitHub warning leaves the lane unentered), the
orphan check before entering, `EnterWorktree`, and the board move to In progress. Re-running it on any existing
open lane resumes it (never a second `lane.sh open`; a live foreign owner stops it): an UNENTERED lane (board
status not yet `In progress`, `In review` or `Done`) gets the pick-source eligibility re-check for either
`lane.pick_source.kind`, and an ineligible one stops with a `/lane-cleanup <n> --abandon` recommendation that it
never runs itself; an ALREADY-ENTERED lane (for example after `/lane-cleanup`'s exit, or a hand-off from a dead
owner) is re-entered without that re-check and without a board move, so `In review` is never set back to
`In progress`. Operator cards are opened for the operator after writing (`open_path`, or the queue file itself).
On `abandoned-backlog` it posts the prune card; on `cap-reached` it runs a read-only stuck check (stuck = a MERGED
PR, or a CLOSED PR with no OPEN one, counting only the lane's own PRs, i.e. those created at or after its last open,
since a re-picked issue reuses its branch name; or tip-on-base AND an owner pid provably dead on this host; ancestry
alone never counts) and cards stuck lanes with the command that moves each, never reaping. The branch comes from
`lane.sh`'s `branch ` line or the ledger row; `lane.branch_prefix` is REQUIRED and never defaulted. Never pushes or
opens a PR.

**`lane-save/`** (`SKILL.md` with frontmatter, optional argument `[issue#]`) — **LIVE only, no dry-run mode.** Posts a
NEW `## Lane state` comment (progress, remaining work, blockers, files touched, tests actually run with their
results, branch, HEAD sha, tree state) and never edits an earlier one. Without an argument the issue number comes
ONLY from the lane worktree the session is in: its toplevel must be `<main>/.claude/worktrees/issue-<n>-...`, and
the ledger's last row for that issue must be `open` with the same worktree and branch. Anything else, including
running from the main tree, stops and asks; digits are never parsed out of a branch name. With an explicit number
it stops inside a different issue's lane, without an open/abandoned ledger row, or on a non-OPEN issue. No worktree
exit, no `lane.sh` call, no ledger write, no push, no PR.

**`lane-cleanup/`** (`SKILL.md` with frontmatter, argument `<issue#> [--abandon | --update]`) — resolves the main
tree first, leaves any worktree with `ExitWorktree` `"keep"`, and moves the shell out of `.claude/worktrees/`. It
then prints a read-only dry-run (`lane.sh status`, the ledger branch, the issue state, every PR on the branch)
before any mutation. It stops on no lane, and on a failed or unparseable PR/issue lookup (never read as "no PRs").
It keeps only same-repo PRs whose head is the ledger branch and that were created at or after the lane's last open:
an issue re-picked after a reap reuses the branch name, so an earlier lane's PRs are listed as ignored (the two
timestamps are parsed, never compared as strings). It then acts on exactly one cell of an 8-row PR-state x flag
matrix (`--abandon` and `--update` are mutually exclusive; `--update` acts only in the IN-REVIEW cell and is
reported as ignored everywhere else):
- a PR merged to `lane.pr_target` always wins: fetch first, verify the merge sha, require the lane tip on the base,
  resolve with a what/why/how/status comment carrying lead time (`UNKNOWN` when unavailable, never 0; CI minutes are
  not computed by the skill, and the report says they are measured by hand in L5.4 lane 1), Done, `lane.sh reap`;
- a merge only to another base stops and cards;
- an open PR means In review, and the cell is then a decision on the PR's `mergeStateStatus`: `CLEAN` cards a merge
  (6.3); `BEHIND` with `--update` and the base not yet in the lane runs a merge-slot update (6.4, `git merge` of the
  base into the lane, guarded by a `merge-tree` conflict check) and then cards the push (6.1) once the lane has
  unpushed commits; `BEHIND` without `--update` reports and waits for the merge slot; any other status (`BLOCKED`,
  `DIRTY`, `DRAFT`, `UNSTABLE`, `HAS_HOOKS`, `UNKNOWN`) reports and waits for a later run; `--abandon` over an open
  PR refuses and cards regardless of its `mergeStateStatus`;
- without a flag, a lane with no PR or only closed-unmerged PRs is reported "in progress" (naming the closed PRs,
  with a replacement PR or `--abandon` as the ways on; the one board write moves a board left at `In review` by a
  closed PR back to `In progress`), or "abandoned, not reaped" on an already-abandoned lane (it is reaped only with
  `--abandon`);
- abandon runs only for `--abandon`, and only with no open or merged PR; a PR closed unmerged never abandons a lane
  by itself, since it may have been closed for rework. It checks ownership, runs `lane.sh abandon`,
  `lane.sh reap --abandoned` (a refusal is carded), and a board reset that reads the board, not the reason: an issue
  at `In progress`, `In review` or `Done` (a worked lane) goes to `Backlog`, a `label` pick source keeping its label,
  and any other status (a lane never entered) is left alone. An already-abandoned lane has released its owner, so a
  re-run from any session skips the ownership check and `lane.sh abandon` (never twice), and goes on to
  `reap --abandoned`, whose own ancestry, clean-tree and busy checks guard the lane, and to the board reset, which
  makes a reset the first run did not make.
Every board move, in both lane skills, reads the board status first and calls `gh_issue.sh transition` only when it
differs, because the helper posts a status comment on every call. Before any GitHub read it checks whether this
session's own CLI process (`$CLAUDE_PID`) has the lane as its cwd, as it does when the session was launched inside
the lane (ExitWorktree cannot move it): that stops before any mutation and asks for a re-run from a session launched
in the main checkout. A `lane-busy` reap refusal whose holders are all this session's own processes (the CLI's or
this shell's descendants, or processes writing into this session's own Bash-tool output directory, which catches a
`(cd <lane> && cmd &)` job reparented to pid 1) is retried or reported, never carded as "another process"; a holder
it cannot attribute is judged by its command name against the background commands the session started in the lane.
Every other run past the main-tree check ends with `lane_orphans.sh`, and every card it writes is opened for the
operator. Push, PR and merge are each their own carded ask (the mechanism hub card 53 set), and none is carded while
a standing operator ruling holds lane pushes or PRs: before each it searches the open and archived cards on the
operator surface of every lane-enabled repo in the repo registry, because a lane ruling binds every lane-enabled repo
unless it scopes itself to another (as of 2026-09-24, Agency hub #57 holds lane pushes and PRs in every lane-enabled
repo until the CI-efficiency work lands). The push runs from inside the lane, in the session that holds the card
(never a delegated sub-agent, whose working directory resets between calls): `cd <lane>`, a
`git rev-parse --show-toplevel` check that must print the lane, then `git push -u <remote> <branch>` as its own call
so a repo's `git push` permission rule applies, then `cd <main>` — the push call itself runs `run_in_background:
true` with a `Monitor` until-loop waiting on it (a repo's own pre-push local CI can run tens of minutes, past a
foreground Bash call's cap), and `cd <main>` runs only once that loop ends. Immediately before the push, when the
repo's manifest carries an optional `lane.prepush_check` object (naming a venv, a freshness-check script, and a
lockfile location — read the way `lane.link_paths` is, absence-tolerant, never hardcoded to any one repo's paths),
a separate read-only call runs a venv-freshness check and `pip-audit` from inside the lane's own linked venv; a
freshness failure is fixed against the main tree's venv (the lane's is a symlink into it) and both checks re-run
before retrying the push, on the same approval. A repo with no `lane.prepush_check` configured skips this check
entirely. There is no bypass, and no push while an earlier
lane's PR on the same branch name is still open. One PR per lane, whose body says `Refs #<n>` and is checked for GitHub's three closing-reference
forms (`#<n>`, `owner/repo#<n>`, the issue URL), so the PR itself never closes the issue. `/lane-cleanup`'s verified
resolve normally closes it, but a closing keyword in a lane commit message (named on the PR card) or a manual close
can close it first; the MERGED path then comments instead of re-closing. The PR card names the CI workflows the PR
will start and the merge card states the deploy consequence, both derived after a fetch from the triggers in the
actual merge result (`git merge-tree --write-tree <base_ref> <lane head>`, the tree GitHub's PR merge ref and the
merge commit carry), with the changed files from a local three-dot `git diff --no-renames`; `pull_request_target`
uses the base branch's copy, and a merge with conflicts or more than 300 changed files prints `UNKNOWN` and posts no
card. The merge runs `gh pr merge --merge --match-head-commit`, never squash, rebase, admin, auto or
`--delete-branch`.

### `~/.claude/commands/`

**`sweep.md`** — frontmatter: `description: "Manual oversight sweep — the degraded-mode fallback
when scheduled jobs are down. Runs the daily pre-steps + one chosen dimension, or 'all' for the full
rotation."`, `argument-hint: "[health|logs|cost|consistency|all]"`, `model: sonnet`. Body:
kill-switch check, budget pre-flight, then fixed pre-steps that always run: a dispatched
`sentinel` call for the heartbeat audit + deploy-drift poll, plus — run directly in the sweep
session itself, never delegated — the same seven runtime self-checks the daily oversight job runs
(`model_pin_parity.py`, `bundle_parity.py`, `check_safety_core_parity.py`, `heartbeat_audit.py`,
`validate_agentarch_ledger.py`, `agentarch_metric_check.py`, and `daily_spend_rollup.py` — the
daily job's separate spend-rollup pre-step), then the chosen dimension dispatched to `sentinel` or
`consistency-auditor`, findings filed through board-steward's rules, and a `cadence: "manual"`
heartbeat write. See `oversight-wheel.md` in this docs tree for how this fits the scheduled-job
system it stands in for.

**`wheel.md`** — frontmatter: `description: "Run THE ISSUE WHEEL on demand for a repo, outside its
nightly cadence"`, `argument-hint: "[a repo slug — a non-\"_\"-prefixed top-level key of
~/.claude/knowledge/wheel_repos.json]"`, `model: sonnet`. Body: runs `com.oversight.wheel.<slug>`'s
own job (`issue_wheel.txt`) right now for the named repo, instead of waiting for its nightly
cadence — the on-demand counterpart to `/sweep`, for when the wheel's triage/fix/close pass is
needed immediately.

## Where this fits

Every skill and command in this tree is runtime-level (product-agnostic, GTM-department, or
operator-hygiene), matching the same single-definition principle that governs `~/.claude/agents/`
(`~/.claude/CLAUDE.md` preamble): a skill or command authored once, usable from any repo, rather
than duplicated per product. A
product-specific skill (one that references a specific repo's paths, accounts, or domain rules)
correctly lives under that repo's own `.claude/skills/` instead — see ExampleApp's roster for
an example of that pattern.
