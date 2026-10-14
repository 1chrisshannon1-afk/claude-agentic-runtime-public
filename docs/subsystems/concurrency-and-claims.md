# File-Claims Concurrency System

**Module:** `~/.claude/hooks/file_claims.py`, consulted from `pretooluse_bash.py` gate 4 and
released from `~/.claude/hooks/posttooluse_bash.py`, wired via `~/.claude/settings.json`'s
`PostToolUse` **and** `PostToolUseFailure` events (both `"Bash"`-matched, both dispatching the same
`post_bash_gate.sh` → `posttooluse_bash.py` path — see "The leak-on-hook-failure bug and its fix"
in the History section below for why both are required). Complementary/alternative mechanism: optional worktree
isolation (`CLAUDE.md` §2; available, not the default).

## The rule

Before a `git commit` proceeds, its target paths are checked against a shared ledger of every other
live agent's claims (`~/.claude/.file_claims/`). If another live agent holds an overlapping path,
the commit is contested: under enforcement it polls briefly (45 seconds by default) and then blocks,
naming the holder, and it never forces through. Alongside the real paths, every commit also claims a
synthetic per-repo token, so only one commit lands per repo at a time even when the paths are
disjoint.

- **All or nothing.** A commit claims its whole path set in one atomic step, or claims nothing. Two
  agents can therefore never each hold part of what the other needs, which rules out deadlock; only
  a bounded wait remains.
- **A claim is released by the call that took it.** Both `PostToolUse` and `PostToolUseFailure`
  release the claim by the Bash call's own `tool_use_id`. A crashed session's claim expires by
  time-to-live instead: 300 seconds for a real path, 60 for the commit mutex, and 15 once its owning
  process is confirmed dead.
- **Failure is open.** An unreadable ledger, an unacquirable lock or any unexpected error resolves
  to "claimed, untracked" rather than wedging a commit. In log-only mode a contest is recorded but
  never blocks.
- **Worktrees are optional.** Isolating a unit of work in its own git worktree is a second,
  available answer to the same problem. It is not the default.

The rest of this page is the mechanics. Dated corrections, incident narratives and machine-state
notes are collected, word for word, in the History section at the end.

## The problem this solves

`CLAUDE.md` §2 states the norm directly: "Contested file → yield and poll... Never force through
it." Before this ledger existed, that was pure prose — an agent had to *remember* to check
whether another agent was mid-edit on a file, with no mechanical enforcement at all. Two
concrete failure modes motivate the mechanism:

1. **Two agents committing overlapping paths** — agent A's `git commit -- foo.py` lands while
   agent B is still mid-edit on `foo.py`, and B's later commit either silently overwrites A's
   change or produces a confusing merge state.
2. **Two agents' `git commit` invocations racing inside the *same repo*, even on disjoint
   paths** — pre-commit's own stash/unstash cycle operates on the *whole working tree*, not just
   the committer's own paths (confirmed against `pre_commit/staged_files_only.py`'s pathless
   `git diff-index` and `git checkout -- .` restore path). Two concurrent pre-commit runs in the
   same repo can step on each other regardless of which files either commit actually names.

`file_claims.py` is the mechanical answer: right before a `git commit` proceeds, its target
paths are checked against every *other* agent's live claim in `~/.claude/.file_claims/`.
Overlap means contested, and (under enforcement) the commit polls briefly and then blocks rather
than racing through.

## The claim lifecycle: taken, held, released

### Taken

`try_claim_paths(claims_dir, ttl, agent_id, paths, lock_timeout, ...)`
(in `file_claims.py`) is one **atomic** check-and-claim attempt:

1. Normalize every path in the target set (`normalize_path()` strips a leading `./` and trailing
   `/`).
2. Acquire the shared admission lock (reused from `agent_budget.py`'s proven flock primitive),
   bounded by `lock_timeout` (default 2.0s, `CSA_LOCK_TIMEOUT_SEC`).
3. Read every currently-live claim (`read_live_claims()`, see TTL section below).
4. Check for overlap against every *other* agent's claim (`find_contest()`) using a **prefix-aware** overlap rule
   (`paths_overlap()`): two paths overlap if they're equal, or one is a
   directory prefix of the other (`"modules"` overlaps `"modules/x.py"`).
5. If contested: claim **nothing**, return the contesting record.
6. If clear: write **one** claim file covering the *entire* target path set in a single atomic
   step (`_write_claim()`, temp file + `os.replace()`).

`poll_claim_paths()` wraps this in a bounded, jittered retry loop for
callers under `enforcing()`: each attempt is a **fresh** atomic try (never a partial hold between
attempts), sleeping `min(jitter(poll), remaining)` between tries until either it claims or the
configured `max_wait` (default 45s, `CSA_COMMIT_CLAIM_MAX_WAIT_SEC`) elapses — deliberately kept
under the ~60s PreToolUse hook timeout.

Gate 4 in `pretooluse_bash.py` (`_file_claim_block()`) is the only
caller that matters in practice: in **log-only** mode it does one non-blocking check-and-claim
and never delays the commit (a contest is logged as `would-wait`, not blocked); under
**enforcing()** it polls via `poll_claim_paths()` and, on a genuine timeout, emits a deny naming
the contesting agent.

### Held: what a claim record looks like on disk

One JSON file per claiming agent under `~/.claude/.file_claims/`, named `claim-<safe_id>`
(`claim_path()`). Body (`_write_claim()`):

```json
{"agent_id": "<tool_use_id or auto-<uuid>>", "pid": <CLAUDE_PID or null>,
 "claimed_at": <epoch seconds>, "paths": ["<normalized path>", "..."]}
```

`agent_id` is normally the Bash tool call's own `tool_use_id` — unique per invocation, so two
concurrent commits from the *same* agent type never collapse onto one claim
(`_claim_agent_id()` in `pretooluse_bash.py`). A commit whose event carries no
`tool_use_id` mints a fallback `auto-<uuid>` id instead — this claim has no correlated release on
either wired event (`PostToolUse` or `PostToolUseFailure` — neither can correlate to an id it was
never given) and simply TTL-reaps.

### Released

**CORRECTED 2026-09-05** (was previously wrong on this exact point — see "The leak-on-hook-
failure bug and its fix" in the History section below for the full incident): `posttooluse_bash.py`'s release logic is
wired to **two distinct hook events**, not "the same event" the claim was taken under. Claude
Code's hook lifecycle fires `PostToolUse` only when the Bash **tool call itself** completes
(regardless of the invoked command's own exit code — an ordinary `git commit` rejected by a
pre-commit hook, git exiting 1, still counts as the tool call "succeeding"); a Bash tool call that
itself **errors, times out, or is interrupted mid-run** instead fires the distinct
`PostToolUseFailure` event. `settings.json` wires the *same* `post_bash_gate.sh` →
`posttooluse_bash.py` path to both events (`"Bash"` matcher on each), so a commit attempt is
released regardless of which of the two shapes its failure took. For a *commit* event (on either
wired event), two things happen, in this order (see the module docstring; the dispatcher's third
job — the `git push`-keyed runtime-mirror trigger, `runtime_mirror_sync.maybe_trigger()` — is
independent of claims entirely and documented in [mirror-sync.md](mirror-sync.md)):

1. **Record commit authorship** (`_record_commit_author()` in `posttooluse_bash.py`):
   resolve the repo's fresh HEAD and attribute it to this event's `session_id` via
   `commit_authors.record()`. Skipped silently if HEAD's committer timestamp is older than
   `STALE_HEAD_SEC` (600s) — a stale HEAD means this call didn't actually advance the tree (a
   failed/no-op re-commit), and attributing it would be wrong.
2. **Release the claim** (`fc.release_claim(_lib.FILE_CLAIMS_DIR, tid)`, keyed on the *same*
   `tool_use_id` gate 4 claimed with).

`should_release()`/`main()` themselves never read `hook_event_name` at all — they decide purely
from the command's own shape and the event's `tool_use_id`, so wiring the second event required
**no code change** in `posttooluse_bash.py`, only the missing `settings.json` entry (see
`test_posttooluse_bash.py::TestEventAgnosticRelease` and `test_settings_wiring.py`).

**Ordering is load-bearing**: authorship is recorded *before* the claim (and, when claimed, the
per-repo commit-mutex token bundled into it) is released. While the claim is still held, the
mutex guarantees no *other* commit can land in this repo — so recording authorship first
guarantees it's attributing the correct HEAD, not a HEAD some other concurrently-landing commit
just produced.

A crashed/killed session never runs `PostToolUse` **or** `PostToolUseFailure` at all (neither
event fires — there is no tool call to report on once the process is gone), so its claim is never
explicitly released — this is exactly what the TTL self-heal below exists for.

## The TTL mechanism — three distinct clocks in one record

A naive read of "a claim expires after N seconds" undersells what's actually implemented. There
are **three** independently-configured TTLs, all read via `read_live_claims()`, and which one governs a given entry in a claim record depends on
*what that entry is* and *whether its owner is confirmed dead* — this is a **read-time
distinction**, not a second lock or a second claim-acquisition step; the deadlock-freedom
argument below still holds because there is still only ever one atomic `try_claim_paths()` call
per commit.

| TTL | Env var | Default | Governs |
|-----|---------|---------|---------|
| Real-path TTL | `CSA_FILE_CLAIM_TTL_SEC` | 300s | An ordinary claimed file path. Long enough to outlast a slow pre-commit run; much shorter than `agent_budget`'s 3600s task lease because a commit is a far shorter unit of work than a whole agent task. |
| Commit-mutex TTL | `CSA_COMMIT_MUTEX_TTL_SEC` | 60s | The synthetic per-repo commit-mutex token (see below) bundled into the *same* claim record. A real `git commit` completes in seconds, not minutes, so a leaked mutex claim should stop wedging *other* commits in that repo within about a minute — not the full 5-minute real-path TTL, which was the original (buggy) behavior before this distinction existed. |
| Dead-pid TTL | `CSA_DEAD_PID_TTL_SEC` | 15s | Applied **on top of** either TTL above, only when the record's owning process is *confirmed* dead (see below). Can only ever shorten a record's effective lifetime, never lengthen it. |

`read_live_claims()` computes, per record: `eff_ttl`/`eff_mutex_ttl` (clamped to `dead_pid_ttl`
if the owner is confirmed dead), then removes the underlying **file** entirely once
`age > max(eff_ttl, eff_mutex_ttl)` — every path type it could hold has expired. Short of that,
the record survives but its returned `paths` list is filtered to only the entries still live for
*their own* type (a mutex token dropped once `age > eff_mutex_ttl`, a real path dropped once
`age > eff_ttl`) — so a record holding both a still-fresh real path and an aged-out mutex token
correctly stops contesting the mutex while continuing to protect the real path
(`read_live_claims()`).

## Dead-pid self-heal (#4670) — what it fixes and its careful boundary

**The gap:** a whole-session crash (kill, window close) leaves a claim behind with neither
`PostToolUse` nor `PostToolUseFailure` ever able to release it (no tool call ever completes to
report on). Before this fix, that claim rode out its *full* TTL
(up to 5 minutes for the commit mutex, under the old shared-TTL bug) while blocking every other
commit in the repo with a misleading "another agent has uncommitted work" message — a landmine
#4670 named directly.

**The mechanism:** every claim's `pid` field records **`CLAUDE_PID`** — the Claude Code CLI's
own long-lived process for the session that made the claim — deliberately **not**
`os.getpid()` of the one-shot `pretooluse_bash.py` hook subprocess that wrote the claim, which
always exits within milliseconds and would read "dead" almost immediately for *every* claim,
live or not (`_owner_pid()`). `CLAUDE_PID` persists for the session's
entire lifetime and dies exactly when the session does — precisely the condition under which a
claim can never be released through the normal path.

`pid_alive(pid)` probes via `os.kill(pid, 0)` (no signal sent, just an
existence/permission check):

- `ProcessLookupError` → **confirmed dead** — the only case that returns `False`.
- `PermissionError` (pid exists, owned by another user) → alive.
- Anything else, or a missing/non-positive pid → **unknown → treated as alive.**

This fails open on purpose: an unproven liveness must never masquerade as "definitely dead" and
force an early release of a claim that might still be perfectly valid. `_owner_pid()` itself
returns `None` (never a fallback to the writer's own knowably-dead `os.getpid()`) when
`CLAUDE_PID` is absent or unparseable — an earlier draft of this fix fell back to
`os.getpid()`, which silently collapsed *every* such record's self-heal window down to the
15-second dead-pid grace period, reopening exactly the hazard the fix exists to close, wherever
`CLAUDE_PID` happened to be unset. Whether a launchd-spawned `claude -p` session (an unattended
scheduled job that commits) actually inherits `CLAUDE_PID` is **explicitly marked
unverified** in the code (the "DEAD-PID SELF-HEAL" section of the `file_claims.py` module docstring).

**Gate 4's "honesty fix"** (`_file_claim_block()` in `pretooluse_bash.py`, the #4670 item 2 half of this same
change): when a deny actually fires because of a contested claim, the deny message now checks
`fc.pid_alive()` on the blocking claim's recorded pid. A dead owner gets an honest "this is a
LEAKED claim, not another agent's active work" message naming the exact standalone release
command (`python3 ~/.claude/hooks/file_claims.py release <id>`) — never the misleading "another
agent has uncommitted work" text, which is reserved for a genuinely live holder. The code notes
this message branch is rarely actually *reached* under the shipped defaults, because
`dead_pid_ttl` (15s) is well inside the 45s poll budget — a retrying commit whose only contest is
a dead record usually just claims through with no deny at all before the message would ever need
to fire; the honest message is defense-in-depth for a misconfigured ratio, not the primary fix.

## The commit-mutex token — "only one commit in flight per repo at a time"

Alongside a commit's real target paths, gate 4 also claims a synthetic per-repo token —
`mutex_token(repo_root)` returns `"//commit-mutex::" + os.path.realpath(repo_root)`
(`MUTEX_PREFIX` and `mutex_token()` in `file_claims.py`) — so every commit landing in the *same* repo contests every
*other* concurrent commit's claim, regardless of whether their real paths overlap at all. This
piggybacks on the exact same all-or-nothing ledger (one claim file per agent, written in a single
atomic step) rather than introducing a second acquisition mechanism, so it inherits the
deadlock-freedom argument below unchanged. `mutex_enabled()` gates this on
`CSA_NO_COMMIT_MUTEX` (default: mutex ON).

The `"//"` prefix can never collide with a real normalized path (`normalize_path()` only ever
strips a leading `./`, never introduces a leading `/`), and `paths_overlap()`'s prefix rule means
two commit-mutex tokens for the *same* repo (or a repo genuinely nested inside another) will also
contest each other — an accepted, documented side effect, not a bug.

**What this closes, mechanically:** #4091 documented two hazards. *Mechanism 1* — pre-commit's
own whole-tree stash cycle silently discarding a concurrent agent's uncommitted work — requires
two pre-commit runs racing in the same repo. The mutex serializes commits per repo under
`enforcing()`, which structurally rules out two concurrent pre-commit runs *provided the mutex
claim never leaks past a legitimate run's own duration* — which is exactly what the dead-pid
self-heal (above) and gate 3c (see `gate-chain.md`) close. Two residual gaps remain, both
explicitly documented in the code rather than silently assumed away
(the "#4091" section of the `file_claims.py` module docstring):

- Under **log-only** mode, gate 4 never actually blocks on a contest, so two pre-commit runs can
  still race — any install without the global
  `.enforce` marker, `CSA_ENFORCE` or a project marker is exposed to it.
- A single compound Bash call that legitimately outlives the 60s mutex TTL (e.g. a genuinely slow
  pre-commit hook chain) can lose the mutex mid-flight to a second commit — a documented, narrow
  race window, unrelated to and unfixed by any of this work.

*Mechanism 2* — a pathspec commit silently absorbing a concurrent agent's uncommitted edit to a
*named* path (proven empirically: `git add b.py` with content "v1", then edit the working tree
to "v2", then `git commit -- b.py` commits "v2" — a pathspec commit always reads current
working-tree content, regardless of what was separately staged) — is explicitly **not fixable at
this layer**, and the code says so as a considered conclusion rather than an unexplored gap: the
only local signal ("does this path's working-tree content differ from the real index") can't
distinguish a concurrent agent's edit from the agent's own entirely normal, never-pre-staged
edit, because this runtime's own path-scoped-commit convention almost never involves a prior
`git add` at all. The operator's own #4091 comment named the one change that *would* close this
(committing a pre-staged index with no pathspec instead) and explicitly declined to adopt it
unilaterally — "a change to the house rule's mechanics, not just tooling," i.e. an operator
policy decision the file-claims mechanism cannot make on its own (the "Mechanism 2" paragraph of that same docstring section).

## Why claiming is all-or-nothing: deadlock avoidance

The module's own docstring (its "DEADLOCK ANALYSIS" section) gives the formal argument, worth restating
because it's the design's central property:

Classic (Coffman) deadlock requires all four of: mutual exclusion, hold-and-wait, no preemption,
and circular wait. This ledger removes **hold-and-wait by construction**: `try_claim_paths()`
acquires an agent's *entire* target path set in one atomic, lock-protected step — either every
path is free and it claims all of them at once, or it claims *nothing* and reports contested.
There is no reachable state where agent A holds path X and waits on path Y held by agent B while
B holds Y and waits on X, for any number of agents or paths. (Contrast: if claiming were
incremental — grab X, then try to grab Y — two agents committing `[X, Y]` and `[Y, X]`
respectively *could* deadlock exactly that way. All-or-nothing acquisition is the standard
prevention technique for this class of problem, and it's why gate 4 claims the whole commit
pathspec in one call, never path-by-path.)

What remains, structurally, is **livelock** (repeated failed attempts), not true deadlock — and
three independent backstops bound it:

1. **TTL self-heal** — a crashed/killed agent's claim expires and is pruned on the next read.
2. **Jittered backoff** between polling retries — desyncs two agents that would otherwise wake
   and retry in lockstep forever.
3. **A bounded max-wait** (default 45s) after which the caller stops polling and reports
   "contested" rather than spinning — mechanizing `CLAUDE.md` §2's own rule: "never force through
   it... return control rather than spinning; come back when the file is free."

Everything fails open, matching the rest of the hook suite: an unreadable ledger, an
unacquirable lock, or any unexpected error resolve to "claim succeeded, untracked" rather than
wedging a commit. A missed claim is a rare unflagged race; a wedged commit would be a much worse
failure mode.

## Complementary mechanism: worktree isolation (available, not the default)

`file_claims` protects the shared working tree, which is where work happens by default. Worktree
isolation is a second, optional answer to the same problem: give a unit of work its own git worktree
under `<repo>/.claude/worktrees/<name>/`, so nothing of a peer's sits in the tree that pre-commit's
commit-time stash cycle could touch. The contract (`CLAUDE.md` §2, revised 2026-09-16) makes this
available rather than the default; it was retired as the default after a worktree-sprawl incident
(`knowledge/worktree_and_disk_incident_history.md`) in favour of speed. The default mitigations are
this ledger, path-scoped commits (`CLAUDE.md` §3) and announcing a commit train to live peers first.

A worktree is warranted for a wave of three or more concurrent writing sub-agents on genuinely
disjoint file sets, for a unit of work that must be abortable as a whole, for an unattended job
whose isolation is itself a verification mechanism, and for a lane (one operator-picked issue worked
in its own worktree and branch, opened and reaped only through `scripts/lane.sh`).

Five rules govern a worktree whenever one is used (full detail in `CLAUDE.md` §2 — summarized here
since it's the direct complement to file-claims, not this document's own subject):

1. **Nesting is load-bearing** — a worktree is sanctioned *only* at
   `<repo>/.claude/worktrees/<name>/`. `file_claims.py`'s per-repo mutex token is keyed on `git
   rev-parse --show-toplevel`, which only correctly cross-contests a nested worktree against the
   main tree via a path-prefix rule; a worktree created *outside* the repo root silently drops
   out of the commit mutex entirely.
2. **`discard_changes: true` is forbidden outright** for `ExitWorktree`, same standing as a force
   push — it can delete uncommitted files and unmerged commits invisibly to every gate. Exiting
   with `action: "remove"` (no `discard_changes`) is safe and self-refusing: the tool itself
   declines whenever the worktree still holds uncommitted files or unmerged commits.
3. **Integration into the shared tree is path-scoped, never a commit-creating merge verb** — pull
   the worktree's diff with `git -C <worktree> diff HEAD --binary --find-renames -- <paths>` and
   `git apply` it in the main tree, then commit path-scoped there. `git merge`/`pull`/
   `cherry-pick`/`am`/`revert` on the worktree branch are never used — none of those is a `git
   commit`, so none of the gate-chain protections in `gate-chain.md` would even see them.
4. **`worktree.baseRef: "head"`** must be set in the repo's `.claude/settings.json` — the
   documented default `"fresh"` branches every worktree from `origin/<default>`, silently missing
   the session's own already-landed commits.
5. **Frontend work stays in the main tree** — `node_modules` isn't copied into a worktree
   (measured ~1.95 GB per frontend-capable worktree in this project), so frontend work either
   activates the main tree's own install or simply doesn't move into a worktree for that stretch.

The two mechanisms are layered, not competing. File claims protect the shared tree, where work
happens by default; a worktree removes a unit of work from the shared tree entirely when that is
worth its cost. A worktree's own commits still pass through the same `pretooluse_bash.py` gate
chain, and nesting under the repo root is what keeps the commit-mutex and file-claims protections
working correctly across both.

A lane is the exception to the integrate-by-patch rule (rule 3), the reap rule (rule 2's
`ExitWorktree remove` path) and the frontend rule (rule 5): it commits on its own branch, lands by a
merge-commit pull-request merge, and is reaped only through `scripts/lane.sh reap`. See `CLAUDE.md`
§2 for the exact conditions.

## CLI reference

`file_claims.py` doubles as an operator CLI (`main()` in `file_claims.py`):

- `status` — live claims as JSON (`status_payload()`): per entry, `agent_id`, `pid`, `pid_alive`,
  `age_sec`, `paths` (real paths only), `commit_mutex` (repo paths, mutex tokens split out via
  `split_mutex_paths()` so raw `//commit-mutex::...` tokens never leak into operator-facing
  output).
- `claim-check <id> <paths...>` — one non-blocking check-and-claim attempt.
- `release <id>` — remove that agent's claim (the exact recovery command gate 4's deny message
  names for a leaked claim).
- `reset` — clear every stale/malformed claim file (`reset_ledger()`, mirrors
  `read_live_claims()`'s own full-removal threshold, including the dead-pid clamp).
- `doctor` — ledger health check.

Run `python3 ~/.claude/hooks/file_claims.py status` at any time to see exactly who holds what,
right now.

## History

<details>
<summary>History</summary>

These are the dated corrections, incident narratives and machine-state notes that used to sit inline
in the sections above. They are kept word for word, in their original order, grouped under the
section they came from. They are a record, not the rule: where one of them disagrees with the
sections above, the sections above are current.

### From "The claim lifecycle": the leak-on-hook-failure bug and its fix (2026-09-05)

**The bug:** before this fix, `settings.json` wired the release path only to `PostToolUse`. A
commit whose Bash tool call itself errored, timed out (e.g. a genuinely slow pre-commit hook
chain exceeding the tool's own timeout), or was interrupted mid-run fired `PostToolUseFailure`
instead — an event nothing was listening on — so its claim (and, when claimed, the per-repo
commit-mutex token bundled into it) was never released and outlived the attempt under its own
`tool_use_id`. The *same live session* then retrying the identical commit minted a **fresh**
`tool_use_id` (`_claim_agent_id()` in `pretooluse_bash.py`), so the old claim contested the retry,
forcing a manual `python3 ~/.claude/hooks/file_claims.py release <toolu_id>` every time — the
dead-pid self-heal above could not help, because the owning `CLAUDE_PID` was still very much
alive (the same session, still running).

**A first fix attempt was rejected at review.** Making `find_contest()` treat a live claim as
self-owned whenever its recorded `pid` equalled the *current* attempt's own `CLAUDE_PID` seemed
to close the gap, but broke a load-bearing fact about this runtime's *default* execution mode:
up to 30 **parallel sub-agents** fanned out from one orchestrating session all share that single
session's `CLAUDE_PID` (confirmed empirically — a sub-agent's own Bash environment shows
`CLAUDE_PID` equal to the one top-level CLI process). `pid` can distinguish different *sessions*,
never concurrent same-session *actors*. A pid-equality reclaim therefore let two genuinely
concurrent same-session sub-agent commits in the same repo claim through each other's live
per-repo commit mutex and even delete each other's claim files mid-commit — breaking exactly the
two guarantees this whole ledger exists to provide (§2's path contest, §3's one-commit-in-flight-
per-repo mutex). See `test_file_claims.py::TestSameSessionConcurrentCommitsStillContest` for the
permanent regression pin against reintroducing this.

**The actual fix is release-time, not contest-time**, and needed no change to `file_claims.py` at
all: wire `PostToolUseFailure` (`"Bash"` matcher) to the same `post_bash_gate.sh` →
`posttooluse_bash.py` path as `PostToolUse`. Releasing by the call's own `tool_use_id` is safe by
construction regardless of concurrency — a call only ever releases the claim it itself made, never
another agent's, live or leaked.

### From "Complementary mechanism": the worktree framing when per-session worktrees were mandatory (2026-08-27 to 2026-09-16)

Superseded by the 2026-09-16 revision of `CLAUDE.md` §2, which made worktree isolation available
rather than the default. The five rules in the section above still apply whenever a worktree is
used.

`file_claims` protects a *shared* working tree. `CLAUDE.md` §2 (2026-08-27, extended 2026-08-28)
sanctions a structurally different answer to the same underlying problem: give each agent (or
each interactive session) its **own** git worktree under `<repo>/.claude/worktrees/<name>/`, so
nothing of a peer's sits in the tree that pre-commit's own commit-time stash cycle could ever
touch. This was adopted after a real incident: three concurrent interactive sessions sharing one
tree lost an entire session's uncommitted diff when pre-commit's stash-and-restore window raced
a peer's unrelated, unstaged edits and the restore's `git apply` failed (recovered only because
pre-commit retains every stash as a patch file under `~/.cache/pre-commit/`).

These two mechanisms are not competing solutions to the same problem so much as layered ones:
file-claims protects the *shared* tree when agents work there directly (the common case for
quick, narrow edits); worktree isolation removes an agent from the shared tree's blast radius
entirely for anything substantial enough to warrant its own checkout. A worktree's own commits
still pass through the exact same `pretooluse_bash.py` gate chain — nesting under the repo root
is what keeps the commit-mutex and file-claims protections working correctly across both.

### Re-verification, 2026-10-13

Re-checked against the code and the contract for the restructure that produced this page's current
layout: the TTL defaults (`DEFAULT_TTL` 300, `DEFAULT_MUTEX_TTL` 60, `DEFAULT_DEAD_PID_TTL` 15), the
poll bound (`DEFAULT_MAX_WAIT` 45) and the lock timeout (2.0), the CLI subcommands (`status`,
`claim-check`, `release`, `reset`, `doctor`), `settings.json` wiring both `PostToolUse` and
`PostToolUseFailure` on `Bash` to `post_bash_gate.sh`, and the worktree rules against `CLAUDE.md`
§2. Every `file_claims.py` line citation still resolved correctly on this date; all line-number
citations on this page were nevertheless replaced with symbol names, because the
`pretooluse_bash.py` ones had drifted and the rest would.

### Statements corrected in place during the 2026-10-13 restructure

Each quoted statement below was replaced in the sections above because it no longer matched the code or the contract.

> — this machine runs `enforcing()` globally, so it isn't exposed here, but any repo
>   without the global marker or `CSA_ENFORCE` is.

A claim about one machine's enforcement state; the rule is that any install without an enforcement
switch is exposed.

> (the nightly
> finishing loop, which commits unattended)

The nightly finishing loop was removed on 2026-09-08. The module's own comment in `file_claims.py`
still names it.

> Complementary/alternative mechanism: harness-native per-session
> worktree isolation (`CLAUDE.md` §2).

The header presented per-session worktrees as the standing alternative; the contract now makes them
available, not the default.

</details>
