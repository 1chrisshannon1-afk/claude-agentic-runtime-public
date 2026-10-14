# Worktree sprawl and disk-exhaustion incident history (extracted from CLAUDE.md §2, 2026-09-21)

Companion to `~/.claude/CLAUDE.md` §2. That section states the rules; this file holds the
incident narrative, the measured figures, and the load-state correction history that justify
them. Nothing here is a rule — every normative statement from the relocated text remains in §2.

## 1. The 2026-09-15 worktree-sprawl incident (why the mandatory-worktree default was retired)

The 2026-09-10 mandatory-default period ("every session / every WRITING sub-agent, every unit of
work" gets its own worktree) ended after a real incident on 2026-09-15: 6 sessions crashed, 233
worktrees / 103GB on disk, agents unable to cleanly `git worktree remove`, and phantom-deletion
diffs left in stale checkouts. That made clear the cure had a worse failure mode than the
disease: a rare, self-healing pre-commit stash clobber had been traded for unbounded worktree
sprawl and unrecoverable checkout state.

The 2026-09-16 operator ruling therefore returned the default to the main tree. Operator,
verbatim: "i want to work with speed... accepting risk of clobbering and fixing it at that time. i
want to be done with our whole worktree process." See the issue tracker record for the repo this
was ruled in.

The mitigations §2 now relies on instead — the `file_claims.py` contested-path ledger, path-scoped
commit hygiene, announcing a commit train to live peers first, and staging every currently-unstaged
tracked path by name before committing — were never the cause of the 2026-09-15 incident and stayed
in force unchanged through it.

Measured detail behind §2's clobber-recovery step: the bare `patch*` glob over
`~/.cache/pre-commit/` exceeds `ARG_MAX` once the cache grows past a few thousand entries, which it
does — 16,989 entries were counted on the author's machine on 2026-09-16, which is why §2 prescribes
`ls -t ~/.cache/pre-commit/ | grep '^patch' | head` rather than a glob.

`~/.claude/knowledge/worktree_integration_flow.md` was retitled on 2026-09-16 to reflect its
optional-path status after this ruling.

## 2. The 2026-09-19 `cp -R` disk-exhaustion incident (why `cp -R` of a repo is banned outright)

Root cause of a real incident on 2026-09-19: two sessions each `cp -R`'d the whole repo into their
own `/private/tmp/claude-501/<session>/` scratchpad, and each copy nested a full copy of every
`.claude/worktrees/` checkout (102G) plus `repo_tooling/demo_video/out` (35G) — turning ~137G of
real content into 332G on disk across 387 session dirs, and blocking every session on the machine
when the disk hit 100%.

## 3. Workflow-leg and dispatched-worktree teardown (measured 2026-09-19)

> **NOT relocated — DUPLICATED, deliberately flagged.** Unlike §1, §2 and §4, this narrative was
> never removed from `CLAUDE.md` §2; both copies exist. **The `CLAUDE.md` copy is the binding
> one.** Recorded here only because the figures sit naturally alongside §1's and §2's. If the two
> ever disagree, §2 wins and this section is the stale one — a drift surface, which is why it is
> labelled rather than left to look like a relocation.


20 `wf_*`-named worktrees were created by `Workflow` legs AFTER the 2026-09-16 ruling retired
worktrees as the default, none torn down by anything — `Workflow` opens one worktree per leg
unconditionally and has no CLAUDE.md-reading mechanism to know the default changed. The same day,
10 `agent-*`-named worktrees showed the identical pattern from `Agent`/Task dispatches passing
`isolation: "worktree"` explicitly. This is the measured basis for §2's rule that the DISPATCHING
session owns the reap.

## 4. Disk-janitor load-state history (why §2 refuses to state a load state)

The `com.oversight.diskjanitor` job was UNLOADED on 2026-09-20 on operator directive ("pause it"),
pending review of its fail-closed fixes.

§2 no longer names any load state, because prose drifts from fact: corrected 2026-09-20, an
earlier same-day version of that paragraph said "unloaded" while `launchctl list` still showed the
job loaded. The declaration of record is `~/.claude/knowledge/oversight_install.md` §2's
`expected_state` column; the fact is `launchctl list`; `hooks/heartbeat_audit.py` diffs the two in
both directions.

§2's "The SCHEDULED job is NOT a dry run" sentence is stated explicitly there because a previous
wording said "dry-run by default" and then named the schedule in the next breath, from which a
reader reasonably concluded the scheduled run was also a dry run; it never was.
