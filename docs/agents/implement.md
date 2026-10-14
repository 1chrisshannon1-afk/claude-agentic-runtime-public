# implement

`implement` is the runtime's code-writing workhorse: the sub-agent an orchestrating session
dispatches to actually make a patch — a feature, a fix, a refactor — via targeted, patch-based
edits. It is the workhorse the main session reaches for when a change is bigger than it should do
inline; per `~/.claude/CLAUDE.md` §1 ("Delegate by size, not by reflex"), the main session makes
small, single-file, already-understood edits itself and dispatches `implement` when the change is
multi-file, needs its own exploration, or can run while the orchestrator does other work. It is deliberately narrow: it edits code, verifies its own
work against a falsifiability check, and reports — it does not touch git, does not format, and
does not decide scope on its own.

## Model & tools

- **Model:** `sonnet` (frontmatter, `implement.md:4`)
- **Tools:** `Read, Edit, Write, Bash, Glob, Grep` (`implement.md:5`)

Practically: `Edit`/`Write` mean this is one of only two dev-workflow agents (with `test-writer`)
actually allowed to change file contents — every other agent in this slice is read-only or
Bash-only. Its `Bash` grant is real but scoped by instruction, not by tool boundary: the doc
explicitly permits "read-only checks the orchestrator asks for (e.g. a compile/type check on your
changed paths)" but forbids running formatters or any git write operation through it
(`implement.md:44-69`) — that boundary is a written rule the agent is expected to follow, not a
mechanically narrower tool grant.

## When it's dispatched

On-demand, whenever an orchestrating session has a concrete, path-scoped piece of implementation
work to hand off — a feature, bug fix, or refactor already partitioned to specific files. Per
`~/.claude/CLAUDE.md` §1, dispatch should partition work by file *before* fanning out, so two
`implement` calls never own overlapping paths. It is typically the first agent in a
implement → test-writer → test-runner → code-reviewer → git-ops chain: `test-writer`'s
own doc states "test-writer follows code-writer... immediately after implement" when covering new
code (`test-writer.md:41`).

## What it does

Given files it owns and task context from the orchestrator, `implement` makes the actual code
change using small, targeted `Edit` calls rather than whole-file rewrites — its doc is explicit
that whole-file overwrites are wrong "for a small fix" (`implement.md:17-18`). It follows the
target repo's own conventions (pulled from the repo's grounding dossier, see below) rather than
imposing a style of its own, finishes what it starts (no TODO/FIXME stubs), and — notably — is
instructed to fix root causes rather than symptoms: a null-check that hides *why* a value is null,
a widened `except` that swallows the real error, a retry that papers over flakiness, or a
special-cased hardcode for one bad input are all named explicitly as bandaids to avoid
(`implement.md:37-42`). If the real fix would require touching files outside its assigned
partition, it is told to report that rather than quietly reaching outside its lane.

Before reporting a bug fix as done, it must satisfy `~/.claude/CLAUDE.md` §6's falsifiability rule:
confirm — via a scratch-copy revert or having watched the paired test fail pre-fix — that a test
actually goes red without the change and green with it. If that can't be established, it must
report the fix as **UNVERIFIED**, not as done (`implement.md:71-77`).

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` (relative to the repo root it's working in) *first*,
if it exists — this is the repo-local grounding dossier described in `~/.claude/CLAUDE.md`'s
preamble as where a "dev-only agent" keeps its stack, layout, and per-change verify commands. If the
dossier is missing, `implement` is told to say so in its report — explicitly **DEGRADED** for the
facts it would have provided — and fall back to the repo's own `CLAUDE.md` hierarchy and config,
"never invent a command or path" (`implement.md:11-14`). This is the generic mechanism shared by all
eight dev-workflow agents in this slice: one runtime-level definition in
`~/.claude/agents/implement.md`, repo facts loaded fresh from that repo's dossier at task start, so
the same agent works unmodified across every product repo on the machine.

## Boundaries — what it will NOT do

- **No git.** "Do NOT commit, push, or run any git write operation" and never `checkout` / `switch` /
  `stash` / `reset` / `rebase` / `worktree` (add/remove/move) / `restore` (working-tree form) /
  `clean` (`implement.md:58-64`) — the orchestrator or `git-ops` owns git. Two narrow carve-outs the
  card names explicitly, matching the live guard: index-only `restore --staged`/`-S` (unstage without
  touching the working tree), and `worktree list`/`prune`/`repair` (read-only enumeration/cleanup).
  If the guard denies a command, the card tells it not to reword or chain around it — the guard fails
  CLOSED on any segment it cannot tokenize (a piece of the line that won't parse and mentions `git` as
  a whole word denies the whole line, even with no state verb present), so the fix is to re-issue as a
  single, simply-quoted command, never to work around the failure. It is also told never to put the
  guard's own inline-bypass escape variable's literal name in a command string (`implement.md:65-69`).
- **No formatting.** Running `ruff format`, `prettier`, `eslint --fix`, or any formatter/autofixer by
  hand is explicitly forbidden because it clobbers concurrent in-flight edits from other agents in the
  shared tree. Whose job formatting actually is depends on the repo: a PostToolUse Edit|Write format
  hook where the repo registers one, otherwise its own commit-time formatter per the dossier — and
  where neither exists, the card tells it to say so under Flags raised rather than format the output
  itself (`implement.md:44-54`). Read-only verification checks stay allowed but may never carry an
  auto-fixing flag (`--fix`, `--write`, `--unsafe-fixes`), targeted or repo-wide.
- **No scope creep.** Stays inside its assigned file partition; a contested file (another agent
  mid-edit, or a half-applied refactor blocking its build) means yield and report the block, "never
  force through it" (`implement.md:28-30`).
- **No silent interface changes.** Must flag, not silently make, any change to output schemas or
  public signatures (`implement.md:31`).
- **No unverified "done" claims.** Cannot report a fix complete without the falsifiability check
  above; must say UNVERIFIED if it can't establish one.
- **No stale docs.** A behavior/schema/ops/user-facing change updates the affected docs/help copy in
  the same change when those paths are in its partition; otherwise it names the exact doc that goes
  stale under Flags raised rather than leaving it for later (`implement.md:32-34`).

## Reporting

Its report contract names five fields: **Files changed**, **What changed and why**, **Docs touched /
doc impact** (added alongside the docs-travel-with-the-change rule above — which docs/help copy it
updated in the same change, or the exact doc that goes stale if that was out of its partition),
**Verification run + result** (including the falsifiability check), and **Flags raised** / **Not
done** (`implement.md:82-91`). "Finish all assigned work before returning" carries one named
exception: the operating contract's 3-strike rule — the same failure recurring a third time is a stop
and report, not a fourth attempt (`implement.md:82-85`).

## How it fits with other agents

`implement` sits at the head of the code-change pipeline. `test-writer` follows it to add paired
tests for the same change (or runs in parallel when covering already-committed code). Pre-commit lint
and `test-runner` verify the result independently (read-only, never fixing what they find — their
findings route back to another `implement` dispatch). `code-reviewer` reviews the pending diff
before any commit lands (`~/.claude/CLAUDE.md` §10, gate 3b). `git-ops` (or the orchestrator itself,
once review is recorded) performs the actual path-scoped commit — `implement` never does this
itself. Because `implement` never touches git state, it can run concurrently with other agents
editing disjoint files without contending for the repo's commit mutex.

## Example invocation

An orchestrating session is fixing a reported bug where a discount code silently applies twice on
checkout. It partitions the fix to `modules/billing/discounts.py` and dispatches `implement` with
that exact path, the bug report, and the relevant spec/contract — expecting back the patch, a note
on the root cause (not just the symptom), and a falsifiability-checked "done" or an honest
"UNVERIFIED."
