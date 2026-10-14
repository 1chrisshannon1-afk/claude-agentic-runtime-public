# explore

`explore` (lowercase) is the runtime's read-only codebase research agent: it maps structure, finds
patterns, and returns paths and signatures without ever writing anything. It exists so an
orchestrating session can delegate open-ended "where is X / how does Y work / what pattern is used
for Z" investigation to a sub-agent, rather than burning the main session's own context on broad
exploration — and it deliberately distinguishes itself, by name and by design, from the harness's
own built-in `Explore` (capital E) agent.

## Model & tools

- **Model:** `sonnet` (frontmatter, `explore.md:4`)
- **Tools:** `Read, Glob, Grep, Bash` (`explore.md:5`) — no `Edit`/`Write`. Its `Bash` grant is
  described as "mostly honor system" for read-only analysis (`git log`/`git diff`/`git status`,
  `ls`, `wc`, `grep`, `find`, `python -c` for inspection), with a mechanical backstop for most of
  the state-mutating verbs — `checkout`/`switch`/`stash`/`reset`/`rebase`/`worktree`/`clean`, plus
  the working-tree forms of `restore` (index-only `restore --staged`/`-S` stays allowed) — which
  are hard-blocked by the runtime's `PreToolUse:Bash` gate chain regardless of what any prompt
  tells the agent to do. `push` sits outside that gate chain but is not pure honor system either:
  the permission system asks on every `git push` and denies `--force`/`-f` outright
  (`explore.md:33-40`).

## When it's dispatched

On-demand, whenever an orchestrator needs research rather than a change — before planning an
implementation, when investigating a bug's cause, when mapping an unfamiliar module, or any time
"find out X across the codebase" is cheaper to delegate than to do inline. Per
`~/.claude/CLAUDE.md` §1 ("Delegate by size, not by reflex"), a search that needs its own
exploration is exactly the kind of work to push down to a sub-agent rather than do inline — and
`explore` is the cheap way to do it, since it returns findings instead of a full transcript.

## What it does

Given a scope and specific questions from the orchestrator, `explore` narrows with `Glob`/`Grep`
before reading specific ranges with `Read`, rather than scanning broadly (`explore.md:43`). By
default it **excludes vendored/stale-checkout paths** from every Glob/Grep — `.claude/worktrees/`,
`node_modules/`, `.venv/`, `build`/`dist` — because a worktree holds a stale full copy of the repo
(9 live in ExampleApp as of 2026-08-31, per the agent file) and a repo-wide grep can
otherwise return a majority of hits from a stale checkout; a hit found inside one anyway is named
as such and re-located to its live path in the main tree before being reported (`explore.md:44-49`).
It returns **structured findings**: absolute file paths, function/class signatures, the actual
load-bearing code snippets, and pattern observations — "facts and paths, not narration"
(`explore.md:50-51`).

Its most distinctive rule is an evidence-discipline requirement: **every count or "N occurrences"
claim must ship the exact command that produced it** — "a grep is a hypothesis, not a fact" — and
anything not directly observed (a file actually read, a command actually run) must be labeled
**UNVERIFIED**, never stated as plain fact (`explore.md:52-54`). Paired with that is a **provenance
rule**: every claim states whether it reflects the working tree or HEAD, since other agents edit
this tree concurrently and a match may be someone else's uncommitted in-flight edit — any
structural/grounding claim the orchestrator will act on gets confirmed against HEAD (`git show
HEAD:<path>`, or `git diff HEAD -- <path>` to prove the file is clean) with the check stated
explicitly (`explore.md:55-59`). If the requested scope is ambiguous, it reports what it found plus
an explicit list of areas still unexplored, rather than guessing at the rest (`explore.md:60-61`).

Every response is returned in a fixed **`## Report`** shape — question asked, direct answer (or an
explicit "nothing found" for a negative result), findings as `path:line-range — signature — what it
shows`, the verbatim commands run with their counts, an `UNVERIFIED` list, and a `Not explored`
list — kept bounded (a total count plus a representative sample, never an unbounded hit dump)
(`explore.md:63-76`).

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` first if present — here specifically for "this
repo's stack, project layout, directory conventions, and (where present) a '## How to re-derive'
section of verified commands for common counts/facts" — and is told to reuse those pre-verified
commands rather than composing new ones from scratch (`explore.md:22-27`). Missing dossier → say so
in its findings, fall back to the repo's own `CLAUDE.md`/config, and report any fact it can't ground
that way as **DEGRADED** rather than invented or guessed. Same shared mechanism as the rest of this
slice.

`explore` is also the one agent in this slice whose own doc explicitly cites `~/.claude/CLAUDE.md`
§1's correction about sub-agent context: named runtime agents (including `explore` itself) *do*
load the full `CLAUDE.md` hierarchy and git status automatically on dispatch — it is only the
built-in `Explore`/`Plan` that skip this (`explore.md:11-14`).

## Boundaries — what it will NOT do

- **Never creates, edits, or deletes files.** "Never run a destructive or state-changing command."
  (`explore.md:30`)
- **`Bash` is read-only analysis only** — nothing that writes, stages, or mutates.
- **Never** `git checkout`/`switch`/`stash`/`reset`/`push`, or any write/destructive git op
  (`explore.md:33-40`) — an honor-system rule in its own prompt, mechanically backstopped for most
  of the state verbs (`checkout`/`switch`/`stash`/`reset`/`rebase`/`worktree`/`clean`, plus
  `restore`'s working-tree form) by the runtime's git guard, and for `push` specifically by the
  permission system's ask-on-push + deny-on-force rule rather than the guard.
- **Never fixes, edits, commits, or files/transitions an issue** — `implement` and `git-ops` own
  those; **never a reviewer of record** on a pending commit — `code-reviewer`/`trust-architect` own
  that judgment (`explore.md:16-20`).
- **Never states an unverified count as fact** — the evidence-discipline rule above is a hard
  constraint on its reporting, not a suggestion.
- **Never reports a claim without saying whether it reflects the working tree or HEAD** — the
  provenance rule above.
- **Never guesses at unexplored scope** — it must say explicitly what it didn't cover.

## How it fits with other agents

`explore` is a pure information source, dispatched independently of the implement/test/review
pipeline — it produces the map that later informs where `implement` should make changes, what
`test-writer` should test against, or what an orchestrator tells `plan-reviewer`. It never
dispatches other agents itself and never hands off work to them; it only returns findings upward.
Its own **Seam** statement makes the negative space explicit, not just implicit in what tools it
lacks: it never fixes, edits, or commits (`implement`'s job), never files or transitions an issue
(`git-ops`'s job), and is never a reviewer of record on a pending commit (`code-reviewer`'s or
`trust-architect`'s job) — dispatching `explore` for a code review is a naming/role mistake, not a
legitimate use (`explore.md:16-20`).

Its identity note is worth restating for anyone dispatching by name: **`explore` (lowercase) is
not the same agent as the built-in `Explore`** (capital E) — the built-in skips `CLAUDE.md` and git
status entirely (`~/.claude/CLAUDE.md` §1) and has no repo-dossier grounding or evidence-discipline
rules. **[UNVERIFIED]** the built-in's exact tool grant: no enumeration of it (e.g. "all tools
except Agent/Artifact/ExitPlanMode/Edit/Write/NotebookEdit") appears anywhere in this runtime's own
authored files (verified: `grep -rn "NotebookEdit" agents/ knowledge/ CLAUDE.md` → no hits) — do
not trust a specific tool list for the built-in `Explore` without confirming it against the actual
client/harness documentation first. Either way, a dispatcher choosing between the two named agents
is making a real tradeoff (grounding and evidence discipline vs. the built-in's convenience), not a
naming coincidence.

## Example invocation

Before implementing a new billing feature, the orchestrator dispatches `explore` to map every place
`modules/billing/` currently computes a discount, return the function signatures involved, and
flag (with the exact `grep` command used) how many call sites exist — so the implementation work can
be partitioned accurately before any `implement` dispatch happens.
