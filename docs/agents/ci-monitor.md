# ci-monitor

`ci-monitor` polls a CI run to a terminal state and reports what happened — including surfacing a
failure mid-run, before the whole run finishes, so fixes can start in parallel rather than waiting
out a long pipeline. It never fixes anything and never commits; it exists purely to turn "is CI
green yet" into a bounded, structured signal instead of something the orchestrator has to babysit
by hand.

## Model & tools

- **Model:** `haiku` (frontmatter, `ci-monitor.md:4`) — cheapest tier, appropriate for a polling
  loop with no judgment calls beyond reading `gh run` JSON.
- **Tools:** `Bash, Read` (`ci-monitor.md:5`) — notably narrower than `test-runner`: no
  `Glob`/`Grep`. It runs `gh`/`git` read commands and reads files directly; it has no file-search
  tools because its job is entirely about a remote CI run's status, not the local tree.

## When it's dispatched

On-demand, after a push has gone out and the orchestrator needs to know when CI finishes and
whether it passed — typically after `git-ops` (with explicit operator go-ahead) pushes a branch
that has an open PR, or after any push that triggers a CI workflow. Since a push is one of the
outward-gated actions in `~/.claude/CLAUDE.md` §4 ("ASK before push"), `ci-monitor`'s dispatch
naturally follows an already-approved push, not the push decision itself. It watches a single run;
`git-ops` audits the pipeline's design between runs (speed, security, hygiene) — a different lane
(`ci-monitor.md:9-11`).

## What it does

Follows a fixed polling protocol (`ci-monitor.md:18-63`):
1. Identifies the run for the **exact pushed commit**, not just the branch's newest run: uses the
   commit sha supplied at dispatch as authoritative, falling back to `git rev-parse HEAD` only when
   none was supplied — in this shared multi-agent tree a peer agent's own path-scoped commit can land
   between the push and this agent's spin-up, moving local HEAD past the sha that was actually
   pushed, so trusting local HEAD unconditionally would watch the wrong run. Then `gh run list
   --branch <branch> --workflow "<CI workflow>" --commit <sha> --limit 1 --json
   databaseId,name,headSha,createdAt -q '.[0]'`. A bare `gh run list --branch <branch> --limit 1`
   (no `--workflow`, no `--commit`) returns the newest run of ANY workflow on the branch — it can
   lock onto a scheduled/cron run, or the previous run in the seconds before the new one registers,
   and report a false green for a push that was never actually tested. If the result is empty or
   `.headSha` doesn't match, it does not adopt an older/unrelated run — instead it re-queries on the
   normal poll interval for a bounded registration grace before any terminal report (step 5 below).
2. Polls roughly every 30 seconds for overall status AND conclusion via `gh run view <run-id>
   --json status,conclusion`, reporting **status transitions as they happen** (queued → in_progress
   → completed), not just the terminal state.
3. On every poll, also checks for jobs that have **already failed while the run is still in
   progress** and reports that failure immediately — not after the whole run completes — "so fixes
   can start in parallel." The per-job jq query is representation-agnostic between a null and an
   empty-string conclusion, since `gh`'s common not-yet-concluded shape is `""`, not `null`, and a
   plain `// .status` fallback silently drops status on that shape.
4. On a terminal state: reports success with a job summary, or reports the exact non-success
   conclusion (`failure`, `cancelled`, `timed_out`, `startup_failure`, `action_required`, `skipped`,
   ...) explicitly rather than folding it into "success." For any conclusion that can carry a log,
   it pulls `gh run view <run-id> --log-failed` and reports job/step/key error lines, capped to
   roughly the last ~40 lines per failed job (an unbounded fetch can run hundreds of lines per failed
   job on a many-job workflow) — reports "no log available" if the fetch returns nothing rather than
   skipping the attempt.
5. Distinguishes "nothing to watch" from "`gh` itself is broken": checks `gh`'s exit status and
   stderr separately from an empty JSON result, since an unauthenticated, rate-limited, or
   wrong-working-directory `gh` also returns zero rows and looks identical to "nothing pushed yet."
   A nonzero exit reports `GH-UNAVAILABLE` (command, exit code, stderr). A clean `gh run list`
   returning empty or a mismatched `headSha` is not immediately terminal, though — GitHub can simply
   not have registered the run yet, so it re-queries on the normal ~30s poll interval for a bounded
   registration grace of up to 6 polls (~3 minutes), counting each toward the reported poll count,
   before reporting `NO-RUN-FOUND` (branch, commit, command, as-of time) — never `NO-RUN-FOUND` for a
   broken tool, and never before that grace is exhausted. Every command runs from the repo root or
   carries `-R <owner>/<repo>`; `gh auth status` is the first check when a query returns nothing
   unexpectedly.

It bounds itself to **300 polls (~150 minutes at the ~30s interval, plus `gh` round-trip time per
poll)** — sized with real headroom above this machine's observed CI wall clock, which has exceeded
100 minutes on a genuinely green run; if the run is still non-terminal at the cap, it reports
`TIMED-OUT` with the run ID, URL, elapsed polls, and last-known status rather than polling forever
or silently giving up (`ci-monitor.md:66-74`). The card deliberately points at a re-derivation
command (`gh run list --limit 60 --json name,conclusion,createdAt,updatedAt`, filtered to the
watched workflow) rather than hardcoding a wall-clock minute figure, since that figure decays as the
pipeline changes.

Every terminal report includes: run ID + URL, workflow name, branch, head sha, overall
status/conclusion, per non-success job individually plus an "N/M green" rollup, a failure-log
excerpt (capped to ~40 lines per job) where applicable, and the poll count at time of report
(`ci-monitor.md:81-91`). Workflow name and head sha are in the contract specifically so the
orchestrator can catch a mis-identified run rather than trust a bare "green." It also carries a
specific escalation reminder from the operating contract: if the *same* CI failure recurs a third
time, it should surface the 3-strike stop to the orchestrator rather than implying another blind
retry (`ci-monitor.md:93-95`) — this mirrors `~/.claude/CLAUDE.md` §11's "3-strike rule" almost
verbatim.

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` first if present, specifically for "this repo's CI
build-failure log location and any project-specific CI conventions" (`ci-monitor.md:13-16`).
Missing dossier → say so, fall back to the repo's `CLAUDE.md`/config, never invent a command or
path. Same shared mechanism as the rest of this slice.

## Boundaries — what it will NOT do

- **Never fixes anything, edits files, commits, or pushes.** "Report only" (`ci-monitor.md:75`).
  Its Bash grant is unrestricted, so `push` specifically is honor-system, not gate-blocked —
  `block_branch_ops.py`'s STATE_VERBS covers `checkout`/`switch`/`stash`/`reset`/`rebase`/
  `worktree`/`restore`/`clean`, never `push` — the card states this explicitly rather than leaving
  it implicit (`ci-monitor.md:75-78`).
- **Never silently folds a non-success conclusion into "success."** `cancelled`/`skipped`/`failure`/
  `timed_out`/`startup_failure`/`action_required` are always reported as themselves.
- **Never adopts the wrong run.** Pins identity to the pushed commit's `headSha` and the watched
  workflow rather than trusting the newest run on the branch, which can be a scheduled job or a
  stale prior run.
- **Never reports a broken `gh` as "nothing pushed."** `GH-UNAVAILABLE` and `NO-RUN-FOUND` are
  distinct, deliberately never merged.
- **Never polls past its bound** — 300 polls / ~150 minutes, then `TIMED-OUT`, not silence.
- **Never implies a blind retry on a third recurrence of the same failure** — that's the 3-strike
  stop, surfaced to the orchestrator instead.

## How it fits with other agents

Purely a signal source: it never dispatches other agents and never fixes anything itself. A
`failure` report routes back to the orchestrator, which dispatches `implement` (and, if needed,
`test-writer`) to address the root cause, then re-runs local verification (lint via pre-commit,
`test-runner`) before another `git-ops`-executed, operator-approved push restarts the cycle. Because
it reports mid-run failures immediately rather than waiting for full completion, it can shorten that
fix-and-repush loop meaningfully compared to waiting for the whole pipeline to finish. `git-ops` owns
the reciprocal lane — auditing and improving the pipeline's own design between runs — so a
recurring or structural CI problem (not a one-off failure) routes there, not back through
`ci-monitor`.

## Example invocation

After an operator-approved push to an open PR's branch, the orchestrator dispatches `ci-monitor`
with the branch name and the pushed commit's sha, asking it to watch the run to completion and
report immediately if any job fails — so a fix can be dispatched in parallel rather than waiting for
CI's full run (observed past 100 minutes wall clock) to finish before anyone notices a failing lint
job three minutes in.
