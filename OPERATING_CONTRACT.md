# The full operating contract (optional appendix)

This is the complete rule set the author runs with. The shipped `CLAUDE.md` is deliberately short —
see `POSTMORTEM.md`, lesson 25, for why a long context file costs more than it helps. Adopt
rules from here one at a time, as hooks where possible, rather than pasting this whole file into
your own `CLAUDE.md`.

---

# Dev Runtime — Agent Operating Contract

**This file is the source of truth for how agents OPERATE, in ANY repository.** It is
product-agnostic: it describes the way of working, not what any one codebase is. Product
repositories keep their own engineering standards (branch model, local-CI gate, domain rules,
harness index) in-repo; nothing is shared between this runtime and any product repo —
duplication is fine. If a rule here ever seems to reference a specific product, treat that
reference as an *example only*, never as an authoritative path.

This runtime lives in `~/.claude/` (its own git repo — the only rollback). Product code lives in
its own repo. Never reference a product-repo file path as authoritative from here (a **hardcoded
literal path** is the one thing to avoid — the narrow exception is a runtime agent's own
Read-FIRST list pointing INTO the repo it's currently working in, expressed as `${REPO:<slug>}`
via `knowledge/repo_registry.json`, or reached via that repo's own `<repo>/.claude/oversight/<agent>.md`
dossier — never a bare absolute path baked into this file or an agent definition), and never
reference this runtime from inside a product repo.

> **Boundary test.** A rule that is true in *any* repo belongs here (runtime). A rule true only
> for one product's code belongs in that product's repo. A rule true both ways gets a **copy in
> each layer** — no shared file.
>
> **Agent registries are the one exception to "copy in each layer."** Claude Code resolves
> sub-agents by name with last-write-wins REPLACEMENT — a `<repo>/.claude/agents/<name>.md` fully
> replaces a same-named `~/.claude/agents/<name>.md`. A copy in each layer therefore means one
> copy is DEAD and invisible to any runtime-side governance (model-pin checks, rule-sync checks)
> that only ever scans the runtime directory. **Every agent should have exactly ONE definition, in
> `~/.claude/agents/`** — including product-domain specialists — unless you have deliberately
> decided to accept that invisibility for a good reason.
>
> A runtime agent may still *read* product-repo paths — that's how a domain specialist stays
> grounded in facts that legitimately live in the product's own repo (its trade rules, its schema,
> its incident history). The point above is about *governance* (one place to see the agent, its
> model pin, and its tool grants), never about *grounding portability*: a specialist's largest
> Read-FIRST surface can legitimately be a doc that stays in the product repo, expressed through
> an indirection (a registry lookup or a per-repo dossier file) rather than a hardcoded path.
>
> **Naming.** A runtime agent's name should be DOMAIN-scoped, not product-scoped — a name is
> global across every repo on the machine, and two products sharing a domain can share the agent.
>
> A **dev-only agent** (anything whose purpose is to BUILD software, never to face a customer)
> keeps its repo-specific facts in that repo's own `<repo>/.claude/oversight/dev-runtime.md`. A
> **product-domain specialist** (a trade/engine/vision-domain expert whose grounding includes
> product-repo paths) reads its own `<repo>/.claude/oversight/<agent>.md` dossier instead — a
> missing dossier means it declares itself DEGRADED for that repo's domain facts, never
> improvised.
>
> **Genuinely repo-local surfaces, never migrated into the runtime:**
> `<repo>/.claude/oversight/<agent>.md` dossiers, `<repo>/.claude/skills/`, and
> `<repo>/.claude/settings.json`. **Customer-facing personas that are product FEATURES** (shipped
> to and interacted with by an end user, e.g. an in-app chat assistant) are product code and never
> enter `~/.claude/agents/` at all.

---

## 0. Non-negotiables (the four rules agents most often break)

In priority order:

1. **Never switch branches, never stash.** No `git checkout`/`switch`, no `git stash`/`stash pop`,
   no `git reset`/`rebase`, no `git restore` (working-tree form — `restore --staged`/`-S` alone,
   with no `--worktree`/`-W`, is fine, it only unstages), no `git clean`. Every session may be
   running alongside other agents; these ops wreck other agents' in-flight edits. A `PreToolUse`
   guard can hard-block them when enforcement is on (§7). `git worktree` itself is narrower than a
   blanket ban — see §2's worktree-isolation rules for what's sanctioned.
2. **Path-scoped commits only.** Never `git add -A`/`git add .`/`git commit -a`. Name only the
   paths you changed. Commit often locally; **ASK before any push / PR / merge / deploy** (§3, §4).
3. **Tests assert INTENDED behavior, and docs travel with the change.** Not current behavior; not
   "document it later." A change that leaves docs or tests stale is a defective change (§5, §6).
4. **Every finding becomes a tracked issue with a live lifecycle.** File it, triage it, transition
   its status as you work, and close it with a completion comment referencing the commit (§8).

Everything below expands these plus the multi-agent, review-cadence, and concurrency rules.

---

## 1. Parallel by default — and delegate to sub-agents

- **Parallel by default.** Whenever independent work exists, run it concurrently. Never serialize
  what can run in parallel. The main thread is an *orchestrator*, not a doer.
- **Delegate to sub-agents.** The orchestrator plans, partitions, dispatches, and reviews; the
  sub-agents do the file-level work. Use the defined agents in `~/.claude/agents/` as written — do
  not improvise their roles.
- **Partition by file before dispatching.** Two implementers on overlapping files is forbidden.
  Split the work by path first, then fan out. One issue per commit where practical, so each lands
  as a separable, reviewable change.
- **Fan-out is bounded by live capacity, not a fixed number** (§9).
- **Catch-all agent types (`general-purpose`, `Plan`, `Explore`, `claude`) have no model pin of
  their own** — unlike the named roster in `~/.claude/agents/`, there is no file to pin them with,
  so they silently inherit whatever model the dispatching session is running. Pass an explicit
  cheaper `model` override on the dispatch call whenever the task doesn't itself need Opus-grade
  judgment; don't rely on inheritance.
- **A sub-agent inherits this contract but NOT the conversation.** The named agents in
  `~/.claude/agents/` load the full CLAUDE.md hierarchy, including this file, automatically. The
  exception is the **built-in `Explore` (capital E) and `Plan` agents, which skip CLAUDE.md and git
  status entirely**, with no setting to change it; behavior of the other built-ins
  (`general-purpose`, `claude`) is unverified — brief them explicitly rather than assuming. What a
  sub-agent never gets is the *conversation*: this session's findings, decisions, corrections, and
  constraints. Don't re-paste the contract into a dispatch prompt — but DO brief the task-specific
  context, and when a delegated task touches tests, docs, or issue state, name those obligations in
  the prompt anyway.

## 2. Assume other agents are editing the tree

Behave as if concurrent agents may be mid-edit:

- **Never switch branches, never stash / reset / rebase.** (Restated from §0 because it is the
  single most-broken rule.)
- **Contested file → yield and poll.** If a file you need is being edited by another agent — or a
  half-applied concurrent refactor blocks your build/commit — stop work on that file, move to
  other work you *can* progress, and poll the file until it is clear, then resume. Never force
  through it. When nothing else is progressable, return control rather than spinning.
- **Mechanically enforceable at commit time, not just a norm.** A pattern worth adopting: a
  `PreToolUse` hook on `git commit` that claims the commit's exact target paths in a shared,
  file-based ledger, and denies a commit whose paths overlap another live agent's claim. Claims
  should be all-or-nothing (an agent never holds part of its path set while waiting on the rest) —
  that's what rules out real circular-wait deadlock between two committing agents, leaving only a
  bounded wait that a poll timeout terminates.
- **Harness-native worktree isolation is a good fit for BOTH sub-agents and interactive
  sessions, when nested under the repo root.** Agent-issued `git worktree` (typing the raw command
  into a shared tree) is a different thing and is not sanctioned by this section — it's the
  Agent-tool's `isolation: "worktree"` option, and session-level worktree enter/exit tools, that
  are meant here. Used well: the harness creates a worktree under `.claude/worktrees/<name>/` on
  its own branch, removes it automatically when unused, and keeps it (and its branch) on disk when
  it holds changes.

  **Why this matters for concurrent interactive sessions:** several sessions sharing one tree can
  clobber each other's uncommitted work — sometimes through a content-judgment failure (an agent
  misjudging a peer's legitimate in-progress edit as unmarked foreign drift), and sometimes through
  a genuinely mechanical hole: a `git commit` pre-commit hook that stashes the *entire* working
  tree (not just the committer's own paths) to run hooks, then restores it. A peer session's
  unrelated, unstaged edits sitting in that window can be lost if the restore fails. Per-session
  worktrees fix this by construction: nothing of a peer's sits in the tree a session's own
  pre-commit run touches.

  Rules worth carrying into any adoption of this pattern: **(1) nesting is load-bearing** — a
  worktree is sanctioned only nested under the repo root, because a commit-mutex or file-claim
  ledger keyed off the repo root won't correctly cross-contest a worktree created outside it.
  **(2) never discard changes on exit** — a worktree teardown that force-deletes uncommitted files
  or unmerged commits is as dangerous as a force-push and should be forbidden outright; exiting
  without deleting, and reaping only once everything in it is integrated, is the safe pattern.
  **(3) integration should be path-scoped**, applying the worktree's diff and committing it
  path-scoped in the main tree — never a commit-creating merge verb (`git merge`, `pull`,
  `cherry-pick`, `am`, `revert`) run directly on the worktree branch, since those bypass any
  commit-time gates the main tree relies on. **(4) pin the worktree's base ref** to the current
  HEAD rather than the tool's default (which may branch fresh from the remote default branch and
  silently miss commits already made this session). **(5) large dependency trees don't get copied
  into a worktree for free** (e.g. `node_modules`) — frontend-heavy work may be better done in the
  main tree, or by activating the main tree's own install from inside the worktree.
- **Do not run formatters by hand** (`ruff format`, `prettier`, `eslint --fix`, etc.) if a
  `PostToolUse` format hook already owns formatting — re-running it clobbers in-flight edits.

## 3. Commit often, clean, path-scoped

- **Local commits need no permission.** Commit frequently in small atomic commits; never let
  changes pile up. Only *outward* moves are gated (§4).
- **Every commit names its paths explicitly:** `git commit -m "..." -- <path> [<path>...]`. This
  is worth enforcing mechanically, not just as a style preference: a `git commit` with no
  `--<pathspec>` should be blocked, and a whole-tree pathspec (`-- .`, `:/`, the repo root) should
  also be blocked — naming paths is not satisfied by naming "everything." The only legitimate ways
  to omit a pathspec are a real in-progress merge/cherry-pick/revert/rebase (git itself refuses a
  partial commit there) or `--allow-empty`.
- **Commit only your own files or your own sub-agent's files.** Path-scoping the `git add`/`commit`
  is the *mechanical* half of this; the other half is never claiming to have committed a change you
  didn't author — after a background sub-agent finishes, check `git status --porcelain` for the
  full set of files it actually touched (not a remembered list) before staging.
- **Never `git add -A` / `git add .` / `git commit -a`.**
- **Only one commit in flight per repo at a time, if you're running multiple agents.** A
  synthetic per-repo commit-mutex claim (alongside real path claims) means two agents' commits in
  the same repo contest each other even when their real paths are disjoint. A denied commit just
  means another agent's commit is currently landing — wait and retry the same command.
- Every commit is clean: format hook green, no stray files, message in the format under §11.

## 4. ASK before push / PR / merge / deploy — always, every time

Local commits are free; anything that moves code or state outward is gated and never autonomous:

- `git push` — never autonomous. Each push needs its own go-ahead, **including a fix-forward push
  after red CI** (an open PR re-runs CI on every push — wasted compute when parallel agents are
  about to push behind you). On CI failure: fix locally, re-run local CI, then ask again.
- `gh pr create`, `gh pr merge`, any deploy / promote / release workflow.
- Any GitHub state mutation acting outward: closing/merging a PR, promoting, releasing.
- **Prior approval never carries over.** Approval for one push/PR/deploy does not authorize the
  next.
- **Destructive/irreversible ops** (force-push, `reset --hard`, any wipe/reseed script, anything
  that overwrites unrecovered work) are never run and never suggested — not even in dry-run.

## 5. Keep tests AND docs current — in the same change, never at session end

Documentation and tests travel with the change that causes them; updating them is part of the
work.

- Code change → paired tests in the same commit/PR (§6, and a test-writer role follows an
  implementer role).
- Behavior / architecture / ops change → update the affected docs in the same change.
- Test / coverage / harness change → update the project's own test-coverage audit and harness
  index, whatever that project calls it.
- "I'll document it later" is not allowed. Docs left stale by a change are a defect in that change.
  A reviewer role should flag a source change that ships without the matching doc/help update.

## 6. Tests assert INTENDED behavior, not current behavior

Before writing or modifying any test:

- **Read the spec source** — contract/schema, README, docstring, route helper, or user story — not
  the just-written code.
- If the code does not match the spec: **fix the code, not the test.** A passing test against
  wrong behavior is a regression locked in ("lock-in test"). A code-review role should explicitly
  flag lock-in tests (assertions that merely snapshot current output).
- If the spec is unclear: **ask.** Do not guess.
- If you authored a test by running the code and snapshotting its output, you wrote a lock-in
  test. Rewrite it against the spec.
- **Required pairings.** Every test asserting a redirect/gate to a resolution page should be paired
  with a test that the user can leave it and reach the originally-intended state. Every test
  asserting an auth/permission check *fails* should be paired with one asserting recovery.
- **A green test is NOT evidence until you have seen it fail without the fix.** Two failure modes
  produce a confident, completely false all-clear: (a) the test passes identically against the
  pre-fix source, so it cannot detect the change at all; (b) the changed lines are never executed
  by that test, so the work is unreachable from the thing that supposedly proves it. Reading the
  diff cannot catch either — only running the test against reverted source can. **Before reporting
  any fix as done: revert the production change, keep the new test, and confirm the test goes
  RED.** Report "unverified" honestly rather than reporting a green that hasn't been falsified.

## 7. Git discipline can be HARD-enforced (not just advisory)

A `PreToolUse:Bash` dispatcher hook is a good place to put this. Gates worth building, in order,
first block wins:

1. **Forbidden state-verbs** — the checkout/switch/stash/reset/rebase/branch -d family from §0/§2.
   `worktree` and `restore` should be narrower than a blanket block: `worktree list`/`prune`/`repair`
   are fine (`add`/`remove`/`move`/lock-unlock/bare stay blocked), and `restore --staged`/`-S` with
   no `--worktree`/`-W` is fine (it only unstages).
2. **Bulk staging** — `add -A`/`.`/`-u`, `commit -a`.
3. **Commit pathspec scope** — every writing `git commit` must carry an explicit, non-bulk
   `-- <pathspec>`; a whole-tree pathspec is also blocked. Exemptions only for a real in-progress
   merge/cherry-pick/revert/rebase or `--allow-empty`.
4. **Pre-commit review gate (optional, higher-maturity setups)** — deny a `git commit` whose exact
   pending content has no code review on record, or whose recorded review found unresolved
   blockers. Keying the review to a content digest (not a filename) means editing a reviewed path
   afterwards correctly re-fires the gate — that's different content — and scoping to the commit's
   own pathspec means other agents editing other files never invalidate your review. This should
   **degrade open** on any tooling error — a review-tooling outage must never wedge a commit.
5. **A dirty pre-commit config should block pathspec commits before any commit-mutex claim is
   taken for it** — a doomed, predictable pre-commit failure shouldn't be allowed to leak a claim
   that never gets released.
6. **File-claim / commit-mutex ledger** — blocks a commit whose target paths are contested by
   another live agent's claim, and claims a synthetic per-repo commit-mutex token alongside those
   real paths, so only one commit lands per repo at a time.
7. **Issue-close integrity (if you track issues in a system with a close/resolve action)** —
   refuse a fabricated-resolution close (no real commit cited, or a cited sha that doesn't exist),
   and refuse a close whose own text makes a deploy-status claim the cited commit hasn't actually
   reached.
8. **A pure-observer churn tracker** — never blocks, just logs when a path crosses a
   commits-without-a-clean-review threshold, so you can see which paths are churning without
   review.

Gates 1 and 2 check every segment of a compound command (`a && b`, `x=$(…)`) and **fail closed**
when a git segment cannot be tokenized, or when the hook event itself cannot be parsed and mentions
`git`: if the gate cannot tell what a command does, it blocks it. They do **not** look inside
`bash -c`, `sh -c` or `eval` strings, and neither do the commit gates (3, 3b, 3c, 4), so
`eval "git stash"` gets through today and a wrapped `git commit` skips the pathspec, review and
claim checks; that is a known gap. Gate 1b scans the raw text but treats single-quoted spans as literal, so it misses a wrapped
redirect inside single quotes (`'…'` or `$'…'`); only gate 1c re-parses nested strings, and only for `gcloud`. A crash *inside* a gate's own decision
code fails **open**, and silently (no log row is written today), so one bug in one gate cannot wedge
every Bash call on the machine. The review gate (3b) also fails open on any error, with three
exceptions that deny: a pathspec it cannot resolve (`unresolvable-pathspec`), a git pathspec
environment variable that would change what the commit lands (`pathspec-env-set`), and a pathspec
that resolves outside the repository (`pathspec-outside-repo`).

An escape hatch is worth having for genuine emergencies: a scoped, single-command override read
only from the guard's own environment — never a standing bypass.

## 8. Every finding becomes a tracked issue — with a live lifecycle

Any bug, gap, refactor opportunity, or missing test you discover gets an issue filed immediately —
even when you also fix it the same session.

**A batch of RELATED findings from one audit/review pass should be ONE issue with a checklist, not
N separate issues.** A single review surfacing as ten separate tickets instead of one is a common
failure mode that produces a runaway backlog. When a single pass produces multiple findings that
share a root cause or area, file ONE issue with a markdown checklist of the findings — unless a
finding is independently launch-blocking on its own merits, which still gets its own issue
regardless of what else the pass found. Check for an existing issue covering the same ground before
creating a new one; fold into it rather than filing a duplicate.

1. **Create + triage.** Set the project fields (estimate/points, priority, status) and labels that
   the project uses. Cross-reference where it surfaced.
2. **Fixing discoveries in-session is encouraged, not scope creep.** Defer only when genuinely
   large or clearly out of session scope; then leave it triaged in the backlog.
3. **Keep issue + board state live as you work** — transition status to match reality, and post a
   progress or completion comment on meaningful progress. Never leave board state stale.
4. **Close with a completion comment** referencing the resolving commit/PR (what/why/how/status +
   commit SHAs). Do not close an issue with leftover TODOs or a "could be done" list — do the work
   or file a new triaged issue.

## 9. Adaptive concurrency — scale fan-out to real capacity

Sub-agent fan-out should not be a fixed cap. The binding limit for LLM-agent fan-out is usually the
provider's per-minute rate (input tokens/min), not CPU: agents are network/token-bound, so a
synchronized burst that dumps many big-context requests into one second is what trips rate limits —
not a headcount, and not the (usually ample) longer-window budget. Two things follow:

1. **Cap concurrency across whatever shares the same budget** (e.g. all sessions on one account/
   API key), not just within one session — a shared, machine-wide ledger of live agents is worth
   building if you run several sessions at once.
2. **Pace the launches.** When many agents burst at once, stagger them (a token-bucket rate
   limiter) and prefer the smaller/faster model for the wide leg so they don't throttle each other.

## 10. Review cadence — capable-model review at plan and at each boundary, never per-edit

Two review points, and only two — reviews happen at boundaries, never on every miniscule edit:

- **Plan review (before implementation).** A capable-model `plan-reviewer` role reviews the plan
  against the request and this operating contract, surfacing gaps, risks, and contradictions
  **before** any code is written. Do not start implementing a substantial plan un-reviewed.
  - **The bar is completeness, not coherence.** A plan that reads well but leaves a step as
    "figure it out during implementation," specifies only the obvious happy path, or fixes a
    symptom instead of the root cause is a REJECT, not a nit. Judge a plan by the same lenses code
    review uses — robust / hardened / complete / correct / best-practice / maintainable /
    scalable — applied to what the plan will PRODUCE, not how it reads. The standard: a worker
    agent given only the plan, with no further access to the requester, should produce a correct,
    complete, hardened result.
  - **Record the plan-review outcome, not just that a review happened** — otherwise "does plan
    review add value" is unanswerable from data. Log clean-vs-blockers-found each time.
- **Code review (BEFORE every commit).** A capable-model `code-reviewer` role reviews the pending
  change at each completed task / phase / issue — i.e. at a **commit boundary**, not after every
  edit. It checks correctness, regressions, and scope-creep, and flags lock-in tests and missing
  doc/help updates.
  - **Running the review before the commit, and mechanically enforcing it** (§7's gate 4), closes a
    real gap: a review keyed to a digest of the diff, not a filename, means editing a reviewed path
    afterwards correctly re-fires the gate.
  - **Degrade open, always.** An unresolvable repo, unreadable ledger, git error, or empty diff
    should allow the commit through. A review-tooling outage must never wedge a commit. It should
    deny only on a confident positive finding.
  - **Reviewers return findings; they do not edit.** The orchestrator dispatches fixes from their
    reports.
  - **Don't re-run a full adversarial pass on every fix-and-recheck round.** Round 1 of a review
    is full adversarial review. When it finds blockers and you fix them, the default next step is a
    narrow, targeted check — the same falsifiability discipline as §6: does a test go RED without
    the specific fix and GREEN with it, for exactly the reported defect, plus the existing suite
    still green. Escalate back to a full re-review when the fix touches broad/risky logic beyond
    the narrow reported line, or when several targeted-verification rounds have passed without a
    full re-review (a cap, so narrow-fix loops can't quietly substitute for review forever).
  - **Cost-gate the review by risk tier.** A cheap classifier that looks at the touched paths can
    decide: docs/lockfile-only changes get a cheaper-model confirmatory pass plus the existing
    suite passing (never a self-recorded "clean" with *no* review of any kind — that's
    indistinguishable in the ledger from a real review and defeats the point); changes touching
    hooks/agents/CI config/settings/security-sensitive paths get full adversarial review, no
    shortcut; everything else gets full review by default. Never split one logical change into a
    cheap-tier commit plus a reviewed commit specifically to dodge full review on the risky half —
    that's a bypass of the process, not a legitimate use of it.
- **Reserve the most capable/expensive model for these two boundaries and genuine hard-reasoning
  passes — never as the standing interactive default.** Watch for this drifting back to a global
  default over time (via a settings file, an org-level default, or an "auto mode" pushing a value
  in from outside anything you control) — if you see a mechanical guard designed to catch it,
  understand what it can and can't catch (it can block a *committed* regression, not a live,
  uncommitted, client-driven change) before trusting it fully.
- **Record the review outcome, not just that one happened.** A bare "reviewed" entry with no
  clean-vs-blockers outcome is nearly useless for any future audit of review quality — make
  recording the outcome part of the standard flow, not an optional flag.

## 11. Conventions (portable defaults)

- **Reply format (operator-facing).** Keep replies concise, clear, plain English, and scannable:
  short bullets, no walls of text. Don't restate the request or narrate the process. For a
  non-trivial reply, consider four sections, omitting any that are empty: **Answer** (the direct
  answer/recommendation) / **Actions** (what you actually did this turn) / **Open** (what remains,
  plus any blocker right now) / **Need from you** (the specific decision, input, or approval to
  continue). Trivial answers (one fact, a yes/no) skip the headers.
- **3-strike rule.** If the *same* failure (same test, same lint rule, same job) fails a third
  time, **stop completely.** Report what the error is, what was tried, and why it isn't working;
  wait for input. Do not attempt a fourth fix.
- **Commit message shape:** `type(scope): summary (≤72 chars)` then `## What` / `## Why` (with
  `Fixes #<n>`) / `## How` / `## Status`. Types: feat, fix, docs, style, refactor, test, chore.
- **Issue triage:** one type label, ≥1 area label, one difficulty; project fields (points/priority/
  status) set as project fields, never duplicated as labels. Closing comment carries
  what/why/how/status + commits.
- **Never bypass or suppress to get green.** No `--no-verify`, `# noqa`, `type: ignore`, blanket
  `except: pass`, or skipping the intent of a check. Fix the root cause.

## 12. Live / browser testing

If you give agents live-browser access, treat the allowed origins, tenants, test recipients, and
denied action patterns as a single machine-readable policy file that every consumer (the pool
manager, any proxy, the agent) reads and never restates. Keep agent tool grants least-privilege —
no raw JS-eval or unsafe code-execution tools on an agent that drives authenticated pages — since
an enumerated tool grant may be the only real enforcement boundary if there's no origin-checking
hook in front of the browser tools themselves. Never grant a bare, unpooled, un-isolated browser
server to an agent when a leased, isolated pool slot is available instead. Credentials should never
be typed from memory, guessed, echoed into logs/summaries, or inlined — fetch them live from a
secrets manager at the moment of use.

## 13. An oversight roster (optional, for a mature multi-agent setup)

A useful pattern once a project has enough surface area: a small set of standing, schedule-
triggered (not manually-invoked) agents that watch different dimensions of the system — direction/
priority, issue-tracker hygiene, health/discovery sweeps, cross-surface consistency, test &
observability architecture, security/tenancy/trust, customer-facing QA walkthroughs, the agentic
system's own design quality, and code-quality/tech-debt trend. Each such agent should:

- carry its durable discipline in a runtime-level primer (how it thinks, what it checks, its
  rubric), and
- read a repo-local grounding dossier for the specific facts of whatever project it's watching —
  with a missing dossier meaning it declares itself degraded rather than improvising facts about
  a project it doesn't actually know.

Findings from any such oversight pass should funnel through the same issue-filing discipline as
§8 (one issue per root-cause cluster, destructive dispositions always human-approved). A security/
trust-tier agent, where you have one, is a good candidate to *substitute* for the generic
code-reviewer on trust-surface commits (auth, billing, secrets, tenancy) rather than *stacking* on
top of it — one reviewer of record per boundary, never two.

---

*This contract governs agent OPERATION only. What a given codebase *is*, and its engineering
standards, live in that product's own repo — never here.*
