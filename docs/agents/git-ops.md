# git-ops

`git-ops` is the runtime's git/GitHub operations sub-agent: path-scoped local commits, GitHub issue
lifecycle management, PR text preparation via the `gh` CLI, and the standing CI/workflow-optimization
lane. It exists to keep git discipline — explicit pathspecs, no bulk staging, no unreviewed commits,
no autonomous outward moves — enforced consistently rather than left to each session's own judgment,
and to work *with* the runtime's `PreToolUse:Bash` git guard rather than around it (git-ops.md,
"work *with* it, never around it").

> **Citation style note:** this doc cites `agents/git-ops.md` by distinctive quoted phrase, not by
> line number — the agent file itself gained several mid-file insertions in the same change that
> produced this doc revision, which shifts everything after each insertion point. A line-number
> citation rots the moment content is inserted above it; a quoted phrase does not.

## Model & tools

- **Description (frontmatter):** "Path-scoped local commits, issue lifecycle, PR text prep, and the
  standing CI/workflow-optimization lane (speed, security, safety, quality — measured, never
  guessed). Never git add -A. Never pushes/merges/deploys without explicit instruction." (git-ops.md
  frontmatter `description:` field.)
- **Model:** `sonnet` (git-ops.md frontmatter `model:` field)
- **Tools:** `Bash, Read, Glob, Grep` (git-ops.md frontmatter `tools:` field) — no `Edit`/`Write`: it
  can inspect a diff and run `git`/`gh` commands, but has no mechanical way to modify source files,
  only to stage and commit what other agents already changed.

## When it's dispatched

On-demand, once there is something to commit, an issue to triage/transition/close, PR text to
prepare, or — per the standing lane below — a CI/workflow audit to run. Its own doc draws an
important seam here (git-ops.md, "the reviewing session is the natural committer"): **"you own issue
lifecycle and PR text prep. When gate 3b (below) applies, the orchestrator that ran the code review
owns the commit itself — the review is keyed to a digest of the diff it reviewed, so the reviewing
session is the natural committer."** In practice that means `git-ops` is not automatically the one
running `git commit` on every change — under the review-gate flow described in `~/.claude/CLAUDE.md`
§10 (gate 3b denies a commit whose exact pending content has no recorded review), the session that
just ran `code-reviewer` and recorded the outcome is best positioned to immediately commit that exact
content, and may do so itself rather than round-tripping through `git-ops`. `git-ops` remains the
agent to dispatch for issue-lifecycle work, PR-text prep, and CI/workflow audits regardless, and for
commits outside that tight review-then-commit sequence.

## What it does

**Commits.** Every commit names its paths explicitly — `git commit -m "..." -- <path> [<path>...]`
— never `git add -A`/`.`/`commit -a` (git-ops.md, "**NEVER `git add -A` / `git add .` / `git commit
-a`**"). This isn't just house style: a commit with no `--<pathspec>` is mechanically blocked
(`missing-pathspec`), and a whole-tree pathspec is also blocked (`bulk-pathspec`). It knows several
distinct denial modes and how to respond to each:

- A **`commit-in-flight`** denial (another agent's commit landing in the same repo right now) is
  expected — wait and retry, UNLESS the denial says the claim is LEAKED (its holder no longer
  running), in which case it runs the `file_claims.py release <holder>` command the denial itself
  prints, then retries (git-ops.md, "unless the message says the claim is LEAKED").
- A **`contested-paths`** denial is a different case again — another agent holds a live claim on one
  of the commit's exact target paths — and calls for re-scoping the pathspec or waiting for that
  file to free, per the operating contract's §2 (git-ops.md, "another agent holds one of your exact
  paths").
- A **gate-3b `unreviewed-commit`** denial is different in kind from either of the above — do NOT
  retry, report back to the orchestrator and stop, because what's missing isn't time or an exact
  path collision, it's a recorded review. A review that itself recorded unresolved blockers denies
  as **`review-blockers-unresolved`** instead, and recording `--clean` over that is a bypass, not a
  fix (git-ops.md, "recording `--clean` over it is a bypass, not a fix").
- A **`unresolvable-pathspec`** denial (an unexpanded `$VAR`, an unquoted `$(...)`/backtick
  substitution, an unquoted `{a,b}` brace expansion, or a leading `~`) can never be cleared by
  recording a review either — it needs the commit reissued with literal, quoted paths.
- A **gate-3c `dirty-precommit-config`** denial is *also* not a simple retry-and-wait: it fires when
  the repo's own `.pre-commit-config.yaml` has uncommitted changes, and no amount of waiting fixes
  that — recovery is a real 3-step chain instead (review the config diff and record it, land a
  config-only commit, then retry the original commit) (git-ops.md, "NOT retry-and-wait, unlike
  `commit-in-flight` above").

It reads the diff before composing a message, using a fixed `type(scope): summary` + What/Why/How/
Status shape (git-ops.md, "Read the diff and the changed files before composing a message"), and is
told local commits need no permission — "commit often in small atomic commits. One issue per commit
where practical."

**Issues.** Uses `~/.claude/scripts/gh_issue.sh`'s `create`/`transition`/`resolve` subcommands rather
than bare `gh issue` calls: `create` sets project fields and labels and cross-references origin;
`transition` keeps board Status live and posts progress comments; `resolve` closes only with a
completion comment and a real resolving commit SHA. It rolls related findings from one review/audit
pass into a single checklist issue rather than fanning out N separate issues — the doc cites the
historical failure mode by name (git-ops.md, "that pattern once produced 71 issues in a day"). The
`create` helper itself searches for overlap first and requires `--related <n>` or `--force-new`.

**PR text.** May *prepare* PR text but does not create or merge the PR itself (git-ops.md, "you do
not create/merge the PR yourself").

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` first if present, specifically for this repo's
"branch model, PR target, label taxonomy, the local-CI entry point and its summary-log location,
which CI jobs are blocking vs advisory, and the flake registry" (git-ops.md, "the local-CI entry
point and its summary-log location") — the dossier scope grew alongside the standing CI/workflow
lane below, since auditing a repo's CI without knowing what's blocking vs advisory or where the
flake registry lives is exactly the kind of invented fact this rule exists to prevent. Missing
dossier → say so, fall back to the repo's `CLAUDE.md`/config, never invent a branch name, PR target,
or label; and a CI fact specifically that the dossier lacks is reported as **DEGRADED for that
dimension**, never guessed (git-ops.md, "reported as DEGRADED for that dimension"). Same shared
mechanism as the rest of this slice; repo-specific epic/labeling conventions are explicitly stated
to come from the dossier, "not from here."

## CI & workflow optimization — a standing lane

Beyond commits/issues/PR text, `git-ops` also owns continuous CI/workflow performance and hygiene —
local CI, GitHub workflows, git hooks — for **speed, security, safety, and quality** (git-ops.md,
"## CI & workflow optimization — a standing lane"). Two modes:

**1. Audit mode**, dispatched on demand — no recurring schedule slot exists today. It measures
before proposing anything: real GH-run timings via `gh run view <id> --json jobs --jq '.jobs[] |
"\(.name) \(.startedAt) \(.completedAt)"'` (durations computed from the timestamps), the repo's own
local-CI summary logs, and then ranks the top wall-clock costs against the recurring pattern list in
the agent prompt — dependency-layer caching, an artifact CI already built that the pipeline should
deploy by digest rather than rebuild, advisory jobs sitting on the critical path, timeout budgets vs
measured runtimes, sharding/parallelism imbalance, redundant matrix legs. Alongside Speed it also
checks Security (workflow `permissions:` least-privilege, SHA-pinned third-party actions, no
`pull_request_target` against untrusted head refs, no secrets in logs), Safety (blocking-vs-advisory
classification actually matches reality; concurrency groups can't kill a deploy mid-flight), and
Quality (flake candidates *named in its report*, never written to a registry directly — see the seam
below; hook runtimes bounded; local/GH CI duplicate coverage called out explicitly).

**The non-edit boundary.** `git-ops` returns a ranked, evidence-backed report and files it per the
issue roll-up rule — it does **not** edit workflows, hooks, or CI configs itself; those edits are
`implement`'s job, under full review either way regardless of tier (git-ops.md, "you do NOT edit
workflows, hooks, or CI configs yourself"). Risk-tier split for that follow-up review (per
`hooks/review_risk_tier.py`'s own classifier): GitHub-workflow (`.github/`) and runtime-hook
(`hooks/`) paths classify **HIGH**; local-CI scripts and `.pre-commit-config.yaml` classify
**moderate** — both still get full review, moderate is not a shortcut here (git-ops.md, "classify
moderate — both get full review either way").

**2. The standing observation rule** applies on every dispatch, in either mode: while doing ordinary
git/issue work, if `git-ops` sees a gate/hook/CI behavior wasting time or carrying risk, it appends a
one-line `CI-OBS:` note to its report rather than fixing it inline — folded into an issue's checklist
it's already touching per the roll-up rule, or filed under its own `CI-OBS` heading for the
orchestrator to turn into an issue otherwise. It never fixes it inline and never lets it end with its
report unrecorded (git-ops.md, "Never fix it inline; never let it end with your report").

**Seams with the two agents this lane borders:**
- **`ci-monitor`** watches a *single run* to a terminal state (live polling, "is CI green yet");
  `git-ops` audits the *pipeline's design between runs* and never polls a live run itself (git-ops.md,
  "never poll a live run").
- **`test-architect`** owns the flake *budget* — the judgment axis. It writes nothing here either (its one sanctioned write is the test-quality ledger's first snapshot, never a flake registry):
  `test-runner` runs the N-identical-reruns measurement on the orchestrator's dispatch, and
  `test-architect` reads what it reports. `git-ops` only *names* flake candidates (same sha,
  different verdicts) in its report for the orchestrator to route — it never writes
  the registry (git-ops.md, "you never write the flake registry").

## Boundaries — what it will NOT do

- **Never moves code outward on its own authority.** No `git push`, `gh pr create`, `gh pr merge`, or
  any deploy/promote workflow unless the orchestrator relays an explicit operator go-ahead for that
  specific action, and prior approval never carries over to the next push (git-ops.md, "unless the
  orchestrator relays an explicit operator go-ahead for that specific action"). The same boundary
  extends to CI/workflow triggers: **never** `gh run rerun` / `gh workflow run` / `gh run cancel` —
  reading run history is its job, triggering or cancelling a run is an outward move (git-ops.md,
  "triggering or cancelling a run is an outward move").
- **Never** `git checkout`/`switch`/branch-create/`stash`/`reset`/`rebase`/force-push — hard-blocked
  under enforcement regardless.
- **Never bulk-stages** (`add -A`/`.`/`commit -a`).
- **Never edits workflows, hooks, or CI configs itself** — see the standing CI lane above; it returns
  findings only, never fixes.
- **Never closes an issue with leftover TODOs** or a "could be done" list — finish the work or file a
  new triaged issue instead.
- If it ever pushes to a protected branch by accident, it's told to stop and report immediately — an
  explicit acknowledgment that the guardrails are not assumed infallible.

## How it fits with other agents

Sits at the tail of the standard pipeline: `implement`/`test-writer` produce the diff,
`test-runner` verifies it, `code-reviewer` reviews and records the gate-3b outcome, and
then either `git-ops` or the reviewing orchestrator (per the seam above) performs the actual
path-scoped commit. `git-ops` is also the agent an orchestrator reaches for standalone issue-board
hygiene work unrelated to any specific commit — triage, transitions, closes — independent of the
implement/test/review cycle, and for the standing CI/workflow-optimization lane's own audits (the
`ci-monitor` and `test-architect` seams are covered in that section above).

## Example invocation

A change has been implemented, tested, and reviewed clean (gate-3b review recorded). The
orchestrator dispatches `git-ops` with the exact changed paths and a summary of what/why/how, asking
it to compose the commit message and run the path-scoped commit — and, once landed, to transition
the tracking issue to Done with a completion comment citing the commit SHA.
