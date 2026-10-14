# code-reviewer

> **In plain English.** `code-reviewer` is the second pair of eyes that reads a code change before
> it is committed, the way a careful colleague reads a pull request. It looks at the pending diff
> (not a landed commit) for bugs, regressions, scope creep, tests that only snapshot today's output,
> missing docs, and fixes that hide a symptom instead of curing the cause. It then returns a
> numbered list of findings and a blocker count. It never commits or files issues, and its prompt
> forbids editing files. The review is enforced, not optional: a hook (gate 3b) refuses `git commit`
> until the exact content being committed has a review on record, and any later edit re-arms it.
> It runs on the strongest model with no Edit/Write tools; it keeps Bash to run tests. Changes to
> auth, tenancy, billing or secrets go to `trust-architect` instead (one reviewer per change, never
> both). Docs-only changes may get a cheaper confirmatory pass; changes to hooks, agent prompts or
> schedules always get the full review. After blockers are fixed the default is a narrow check of
> the fix, not a second full review. If the review tooling itself breaks, the gate lets the commit
> through rather than wedging work.

`code-reviewer` is one of the runtime's two mandatory Opus review gates (CLAUDE.md §10). It reviews
the **pending, not-yet-committed** change against the operator's operating contract before a `git
commit` is allowed to land — correctness, regressions, scope-creep, lock-in tests, missing docs,
suppressions, root-cause-vs-bandaid, and combination coverage on any gate/mutex/branching logic. It
never edits, never commits, and never files issues itself; it returns a numbered findings list plus
a blocker count, and that blocker count is a real gating decision, not commentary
(`agents/code-reviewer.md:39-40`). This is the mechanism that is supposed to make "unreviewed code
never lands" a structural property of this repo rather than a norm agents are trusted to follow.

## Model & tools

- **Model:** `opus` (`agents/code-reviewer.md:4`), hard-pinned, unconditionally — there is no
  cheaper-model fallback wired into the agent definition itself. (The risk-tier ladder below
  *does* sanction a cheaper-model pass for trivial changes, but that is a documented process the
  orchestrator follows, not a different model pin on this agent — see "What it does.")
- **Tools:** `Read, Grep, Glob, Bash` (`agents/code-reviewer.md:5`) — no `Edit`/`Write`. Bash is
  explicitly scoped to read-only verification and running the relevant quick test only: "never
  edit any file inside the repo under review, and never run a git write op there"
  (`agents/code-reviewer.md`, "## Verify, don't assume"). The absence of
  an edit grant is the mechanical enforcement of "reviewers return findings; they do not edit"
  (CLAUDE.md §10 "return findings; they do not edit", restated in
  `agents/code-reviewer.md`, "You review; you do not fix").

## When it's dispatched

Dispatched at a **completed boundary — a commit, phase, or issue — never on every miniscule edit**
(`agents/code-reviewer.md:46-47`). In practice this now means: right before a `git commit`, because
as of 2026-08-19 review was reordered from post-commit to pre-commit
(`agents/code-reviewer.md:11`, CLAUDE.md §10 "Code review (BEFORE every commit — reordered
2026-08-19 by operator direction)").

**The mechanism that makes this mandatory, not advisory, is gate 3b —
`~/.claude/hooks/precommit_review_gate.py`, registered in the `PreToolUse:Bash` dispatcher chain
(`~/.claude/hooks/pretooluse_bash.py`).** Gate 3b denies a `git commit` outright when the exact
content it would land has no review on record (CLAUDE.md §7, gate 3b `precommit_review_gate` —
"has no code review on record"). Its mechanics, read directly
from the hook source:

1. **What gets reviewed.** `pending_key()` (`hooks/precommit_review_gate.py:458-483`) computes
   `git diff HEAD -- <the commit's own pathspec>` plus any untracked files in that pathspec
   (`_untracked_material`, `hooks/precommit_review_gate.py:388-432` — a brand-new file produces no
   `git diff HEAD` output on its own, so without this an unreviewed new file would sail through as
   "nothing pending"). The digest is truncated SHA-256 of that combined text
   (`digest_of`, `hooks/precommit_review_gate.py:450-451`), keyed as `precommit:<digest>`
   (`PRECOMMIT_PREFIX`, `hooks/precommit_review_gate.py:83`).
2. **Content-addressed, not filename-addressed.** Edit a reviewed path afterwards and the digest
   moves, so the gate re-fires — "that is different content" (CLAUDE.md §10, "gate re-fires,
   by design" — the digest-keying bullet). This is also what
   makes the gate survivable in a multi-agent tree: another agent editing unrelated files never
   changes your pathspec's digest, so their concurrent edits never invalidate your review
   (CLAUDE.md §10, "survivable in this multi-agent tree").
3. **Clearing it.** The orchestrator records the reviewer's actual verdict:
   ```
   python3 ~/.claude/hooks/record_review.py <repo> --pre-commit --clean   --paths <paths> \
     --reviewer <agent-type> --reviewer-agent-id <id> --reviewer-tool-use-id <id> < /dev/null
   python3 ~/.claude/hooks/record_review.py <repo> --pre-commit --blockers <n> --paths <paths> \
     --reviewer <agent-type> --reviewer-agent-id <id> --reviewer-tool-use-id <id> < /dev/null
   ```
   The three `--reviewer*` fields carry the reviewer's identity, copied from its dispatch row in
   `~/.claude/.agent_budget/spend.jsonl` (never retyped); the recorder joins the `tool_use_id` to
   that ledger and writes the model the reviewer actually ran on. Omitting them still records but
   logs `missing-reviewer-identity` and proves nothing about who reviewed it.
   (`agents/code-reviewer.md:25-28`). The trailing `< /dev/null` is load-bearing, not decorative —
   omitting it is the exact stdin-hang gotcha this runtime has hit before (`record_review.py` reads
   stdin for an optional JSON event payload; with no redirect, a headless/non-interactive invocation
   blocks waiting on a TTY that will never provide input). `--blockers <n>` records the finding
   count **and** keeps the gate closed until they are fixed and a fresh review is recorded —
   committing over a known blocker is precisely what the boundary exists to stop
   (`hooks/precommit_review_gate.py:47-50`, CLAUDE.md §10, "precisely what the boundary exists
   to stop").
4. **Three distinct denial reasons**, not one (`hooks/precommit_review_gate.py:76-78`):
   `unreviewed-commit` (no entry at all), `review-blockers-unresolved` (an entry exists but recorded
   unresolved blockers), and `unresolvable-pathspec` — an unexpanded `$VAR`, an unquoted
   `$(...)`/backtick command substitution after `--`, or a leading `~` reaching the hook as literal
   text it cannot evaluate. **The third reason can never be cleared by recording a review** — the
   commit must be reissued with literal, quoted paths first
   (`hooks/precommit_review_gate.py:624-636`, CLAUDE.md §7). A glob like `*.py` is *not* this case;
   git expands those itself.
5. **Fails open, deliberately, on tooling failure only.** An unresolvable repo root, an unreadable
   ledger, a git error, or an empty diff all allow (`hooks/precommit_review_gate.py:52-58, 600-602`)
   — "a review-tooling outage must never wedge a commit... it blocks only on a confident, positive
   finding." It does **not** fail open on a positive "no review recorded" or "recorded blockers"
   finding — those are the two cases it exists to catch.
6. **Ordering.** Gate 3b runs before gate 4 (`file_claims`, the per-repo commit mutex) so a
   review-denied commit never parks that mutex for other agents (CLAUDE.md §7, "never parks the
   per-repo commit mutex").
7. **The old post-commit `Stop` gate (`task_completion_gate.py`) is retired**, unregistered from
   `settings.json` on 2026-08-19 (`agents/code-reviewer.md:44`, CLAUDE.md §10, "DECIDED
   2026-08-20: the old post-commit `Stop` gate is RETIRED, committed.") — it checked "was
   HEAD reviewed" after the commit already existed, which meant a blocker finding became a *second*
   commit instead of a correction. Gate 3b is strictly stronger: it is keyed to content, runs before
   the commit, and cannot race a moving HEAD.

**Escape hatch:** `CSA_NO_PRECOMMIT_REVIEW=1` is this gate's own per-gate rollback lever
(`hooks/precommit_review_gate.py:113-123`), separate from the global `CSA_DISABLE_HOOKS=1` kill
switch — so disabling just this gate does not also disable branch-op blocking, unscoped-commit
blocking, or the pathspec gate.

## What it does

**Reads a bounded slice of the repo's shared dev-runtime dossier, then grounds "best practice"
against the target repo's own standards docs** (`agents/code-reviewer.md`, "## Grounding" section —
see "Grounding" below for the full mechanics). A repo with neither a discoverable standards doc nor
enforced lint/type config is **DEGRADED for the best-practice lens only** — the other six lenses
still apply in full.

**Not the reviewer of record on trust-surface commits** (`agents/code-reviewer.md`, "## Scope of
review", "Not the reviewer of record on trust-surface commits" paragraph) — the agent file itself
now states the substitution rule in-prompt, not just as an orchestrator-side convention described in
this doc (see "How it fits with other agents" below for the full mechanics).

**Review lens** (`agents/code-reviewer.md`, "## Review lens") — every change is held to all seven of:
robust, hardened, complete, correct, best-practice, maintainable, scalable. "Not obviously broken is
not a passed review."

**What it checks**, in order (`agents/code-reviewer.md`, "## What to check"):
1. Correctness — logic errors, off-by-one, unhandled errors, boundary/null cases, concurrency.
2. Regressions — changed public signatures/schemas, removed guards, altered error responses.
3. Scope-creep — changes unrelated to the stated task, opportunistic refactors.
4. **Lock-in tests, flagged by name** — any test asserting current output instead of intended
   behavior (CLAUDE.md §6's rule); a redirect/gate assertion with no paired recovery test, a bare
   403 with no paired 200-recovery.
5. **Missing doc/help updates, flagged by name** — a source/behavior change shipped without the
   matching docs/help/harness-index update (CLAUDE.md §5's rule).
6. Suppressions — `--no-verify`, `# noqa`, `type: ignore`, blanket `except: pass`.
7. **Root cause vs. bandaid, flagged by name** — a fix that routes around a symptom instead of the
   actual defect; the finding must name the real root cause and what fixing it would actually
   require.
8. **Combination coverage for gate/mutex/branching logic, flagged by name** — for any decision
   driven jointly by multiple boolean/enum inputs, the reviewer must trace the actual input
   dimensions (not just read the diff), enumerate the semantically distinct combinations (default
   full cross-product; dropping one as unreachable requires shown reasoning), and check whether
   shipped tests actually cover that space — not just the bug report's one case. Cites the real
   precedent this check exists for: issue #3336, "a mutex fix passed its own tests and its own
   review, then shipped with a faucet-only tag combination left with no coverage"
   (`agents/code-reviewer.md`, "## What to check" item 8).

It also **runs the relevant quick test** for the change to confirm it actually passes, rather than
taking "tests pass" on faith (`agents/code-reviewer.md`, "## Verify, don't assume"), and reads the
spec source (not just the diff) when judging whether a test asserts intended behavior.

**Falsifiability is explicit, not just implied by CLAUDE.md §6** (`agents/code-reviewer.md`, "##
Verify, don't assume"): a green test is not evidence until shown to fail without the fix. For any
new/changed test the diff relies on to prove its own fix, the reviewer traces whether it actually
exercises the changed lines and, when the target repo names its own falsifiability harness (found
via the bounded dev-runtime read described under "Grounding" below), runs that first and pastes its
literal verdict. Where no such harness exists, it reverts the production change by hand — never
inside the repo under review, and never with a git state-mutating verb
(`checkout`/`restore`/`stash`/`reset`/`worktree`/`clean`, all blocked for any Bash invocation by
`hooks/block_branch_ops.py`'s `STATE_VERBS` regardless of which directory the command targets): it
`cp -R`s (never a hardlink `cp -al`, which shares inodes and mutates the shared tree) the affected
directory to the session scratchpad outside the repo, then produces pre-fix content there with
`git show HEAD:<path>` or `git diff HEAD -- <path> | git apply -R`, to confirm the test goes RED
there and GREEN with the fix restored — a test that passes identically pre-fix is itself a finding,
not a clean bill of health. Anything that couldn't be confirmed this way is labeled `UNVERIFIED`
with the reason, never silently reported as confirmed.

**An `agents/*.md` change gets a different falsifiability check, because there is no test to
revert-and-rerun** (`agents/code-reviewer.md`, "## Verify, don't assume," added 2026-09-06). The
reviewer cannot run this one itself — it holds no dispatch tool, and a sub-agent cannot use `Agent`
even if granted one (CLAUDE.md §13's confirmed-live nesting restriction) — so it names the specific
defect the edit claims to fix, specifies one small scenario that would expose it, and requires the
**orchestrator** to dispatch the agent twice on that scenario (once at the file's pre-edit content,
once at the live content) and hand back both transcripts for grading. Unlike an ordinary
unreachable-fact case, missing transcripts are a **blocker**, not `UNVERIFIED` — the dependency is
concrete and nameable, so silently downgrading it would let an unfalsified prompt edit ship. The
probe runs at the agent's own pinned model; `model_pin_gate.py` denies a cheaper substitute
(`pin-tier-mismatch`) and no exception reason can authorize one on an `agents/*.md` pathspec, which
is always `high` tier. This check is scoped to `agents/*.md` specifically — a `*_primer.md` or
`.claude/oversight/*.md` dossier edit is `trivial` tier and judged on prose grounds only
(`~/.claude/knowledge/test_architect_primer.md` §17 carries the doctrine; the procedure itself is
enforced only here).

**Output** opens with a **`VERDICT: clean` / `VERDICT: blockers=<n>` line** — the exact outcome
`record_review.py`'s `--clean`/`--blockers <n>` records, so the orchestrator can copy it straight
into that call — followed by a numbered findings list, grouped by severity — `blocker / regression /
lock-in-test / missing-docs / scope-creep / nit` — each with `file:line` and a specific, actionable
fix, the quick-test result(s) including any `UNVERIFIED` label, and a closing **coverage line**
naming what was actually read and what in the blast radius was NOT verified
(`agents/code-reviewer.md`, "## Output").

**The risk-tier ladder** (CLAUDE.md §10, "Cost-gated by risk tier (built 2026-08-20 — the
follow-up this section used to only promise)", `hooks/review_risk_tier.py`) is a *consulted*
classifier the orchestrator runs before dispatching this agent, not a gate this agent enforces
itself: `python3 ~/.claude/hooks/review_risk_tier.py <the pathspec about to be committed>` prints
`TIER\treason`.
- **`trivial`** — every changed path is docs-only or a lock/generated file, and none also match a
  high-risk pattern. Full Opus review *may* be replaced with a cheaper-model confirmatory pass plus
  the existing test suite/lint actually passing — **never with zero review**; self-recording
  `--clean` with no review of any kind is exactly the gaming pattern round-2 review closed
  (CLAUDE.md §10, "self-record `--clean` with no review of any kind"). Test-only changes are
  **deliberately excluded** from `trivial`
  (`hooks/review_risk_tier.py:44-49`) — a diff that only deletes assertions or adds a skip is
  exactly what review exists to catch.
- **`high`** — touches `hooks/`, `agents/` (any agent prompt, not just the two reviewer files),
  `schedules/` (any file — job prompts/plists drive unattended sessions), `CLAUDE.md` at any depth,
  `settings.json`, `firestore.rules`/`storage.rules`/`allowlist.json`, or a path matching a
  money/auth/security/migration/deploy keyword. A single matching path anywhere in the change forces
  `high` regardless of what else is trivial (CLAUDE.md §10, "Opus adversarial review, unchanged,
  no shortcut", `hooks/review_risk_tier.py:32-37`).
  Full Opus adversarial review, no shortcut.
- **`moderate`** — the default: everything else, including test-only changes and an
  empty/unclassifiable pathspec. Full Opus review, unchanged.
- **This is advisory, not mechanically enforced** — "was the right review TIER used" is not
  observable from a `git commit` tool call the way "was a review recorded" is; only the latter is a
  hard gate (CLAUDE.md §10, "was the right review TIER"). It is also **path-based only, not
  diff-size-based** — a
  5,000-line docs-only change still classifies `trivial`.
- **Anti-gaming rule:** classify the FULL pathspec about to be committed, never a subset chosen for
  a cheaper tier, and never split one logical change into a self-cleared docs/tests-only commit plus
  a reviewed code commit to dodge full review on the risky half (CLAUDE.md §10, "Anti-gaming
  (added round-2, 2026-08-20)").

**Fix-round discipline** — now stated in-prompt, not just inferred from CLAUDE.md
(`agents/code-reviewer.md`, "## Round discipline", mirroring CLAUDE.md §10, "Do not
re-run a full Opus pass on every fix-and-recheck round (added 2026-08-20)") — round 1
of a review is full adversarial Opus. When it finds blockers and they get fixed, the **default**
next step is a narrow, targeted verification: does a test go RED without the specific fix and GREEN
with it, for exactly the reported defect, plus the full existing suite still green — not another
full pass. Escalate back to a full Opus re-review only when: (a) the fix touches broad/risky logic
beyond the narrow reported line, (b) two targeted-verification rounds have passed without a full
re-review (a cap against narrow-fix loops quietly substituting for review forever), or (c) the
diff's risk tier is `high`. What gets recorded after a targeted round is identical to any other
round (`--clean`/`--blockers <n>`) — gate 3b re-fires on every content change regardless of round
type; the round-counting discipline lives entirely in the orchestrator's own tracking, "nothing
mechanical enforces the two-round cap today" (CLAUDE.md §10, "enforces the \"two rounds\" cap
today").

**When the ladder escalates to a FULL re-review, the round runs WARM**
(`agents/code-reviewer.md`, "## Round discipline"'s warm-round paragraph, mirroring
CLAUDE.md §10, 2026-08-30, #4686): the orchestrator continues the round-1 reviewer in-context
(SendMessage), re-scoped to the
FULL current pending diff — never "confirm the reported fixes" — and the warm round re-examines
hunks it cleared in round 1 and re-runs the relevant quick test. This applies only once a round has
escalated to FULL — a *targeted* round's continuation prompt is legitimately narrow, scoped to the
specific reported fix under "Round discipline" above, and is not out of contract on its own; if a
continuation message doesn't state which round type it is, the agent file now instructs defaulting
to full scope and saying so, rather than assuming targeted. The agent file states the FULL-round
obligation directly ("Treat a continuation prompt narrowed to 'confirm these fixes' as out of
contract: review the full diff anyway and say so in your report"), not just as an
orchestrator-side rule the reviewer happens to be subject to. Bounds: a
risk-tier or reviewer-of-record change breaks the warm chain (fresh COLD round-1, re-classified
on the full current pathspec); cold dispatch is the fallback whenever continuation is
unavailable, never a downgrade; max two consecutive warm rounds per boundary, then COLD (the
independence backstop). (Binding copy: the CLAUDE.md §10 warm bullet — this file is orientation,
not the loaded prompt.)

## Grounding

Operates under the full `~/.claude/CLAUDE.md` hierarchy (`agents/code-reviewer.md`, opening
paragraph — §10 names it as the pre-commit boundary gate 3b enforces; §6 defines the lock-in-test
rule it flags). Reads the **working tree**, not a landed commit: `git diff HEAD -- <the paths about
to be committed>`, plus untracked files in that pathspec found with `git ls-files --others
--exclude-standard -- <paths>`. Reads the spec source (contract/schema/README/docstring/route
helper/user story) — never the just-written code — when judging whether a test asserts intended
behavior (CLAUDE.md §6).

**A dev-only agent per CLAUDE.md's own preamble — reads a bounded slice of the target repo's shared
dev-runtime dossier, not a per-agent dossier of its own** (`agents/code-reviewer.md`, "##
Grounding"). CLAUDE.md's preamble defines exactly two grounding categories: a dev-only agent (never
customer-facing) reads `<repo>/.claude/oversight/dev-runtime.md`; a product-domain specialist reads
its own `<repo>/.claude/oversight/<agent>.md`. code-reviewer is the former — it is not a third,
repo-agnostic category, and it does not skip the dossier the way an earlier revision of this doc
claimed. Mirroring `design-reviewer`'s own bounded-read pattern (never the whole dossier), it
`Grep`s `.claude/oversight/dev-runtime.md`'s `## `-level headings for the ones carrying
commands/testing/lint facts and reads only those sections, heading to the next `## `-level heading —
used to run the narrowest suite and, when the repo documents one, to invoke its own falsifiability
harness correctly (see "Falsifiability is explicit" above). A missing dossier, or one carrying none
of those sections, is reported explicitly rather than improvised. Its "best practice"/"idiomatic"
judgment then falls back to the TARGET repo's own root `CLAUDE.md` plus whatever
engineering-standards doc it names, falling back further to the repo's actual lint/type-check config
where the standards doc is silent. A repo with none of the above is **DEGRADED for the best-practice
lens only** (the agent file's own vocabulary) — the other six lenses still apply in full. Otherwise
its grounding is the diff plus the operating contract plus whatever spec source the diff implicates.

## Boundaries — what it will NOT do

- **Never edits any file** — no `Edit`/`Write` tool grant; findings only
  (`agents/code-reviewer.md`, "## Output", CLAUDE.md §10, "return findings; they do not edit").
- **Never runs a git write op** — Bash is read-only-verification-and-tests only
  (`agents/code-reviewer.md`, "## Verify, don't assume").
- **Never files, transitions, or closes GitHub issues** — "you have no git/gh write access and
  shouldn't reach for it" (`agents/code-reviewer.md`, "## Issue tracking is the orchestrator's job,
  not yours"). Per CLAUDE.md §8, the orchestrator
  files a tracked issue for *every* finding returned, even ones fixed in the same session
  (fix-and-file, never fix-instead-of-file), and closes each with a completion comment referencing
  the resolving commit. A finding with no corresponding issue is treated as an incomplete review
  cycle — findings are numbered specifically so the orchestrator can account for all of them.
- **Never pushes/PRs/merges/deploys** — outside its tool grant entirely and outside its lane
  (CLAUDE.md §4).

## How it fits with other agents

- **The two-boundary rule.** CLAUDE.md §10 is explicit: "Two Opus review points, and only two —
  reviews happen at boundaries, never on every miniscule edit" (CLAUDE.md §10, "Two Opus review
  points, and only two"). `plan-reviewer`
  covers the plan boundary; `code-reviewer` covers the pre-commit boundary. Nothing else in the
  roster is a *standing* review gate — monthly-audit agents like `test-architect`,
  `agentic-systems-architect`, and `code-quality-architect` judge on a schedule or on demand, never
  at a commit boundary (CLAUDE.md §13).
- **Substitution, never stacking.** `trust-architect` substitutes FOR `code-reviewer` as
  reviewer-of-record on trust-surface commits — anything touching `modules/billing/`,
  `modules/licensing/`, `modules/stripe_module/`, `firestore.rules`, or auth wiring in a given repo
  — "never an added gate" (CLAUDE.md §13 roster table, trust-architect row — cited by anchor;
  see also project CLAUDE.md's "Trust-surface commits" rule). The agent file itself now states this
  boundary in-prompt too (`agents/code-reviewer.md`, "## Scope of review"'s "Not the reviewer
  of record on trust-surface commits" paragraph — the substantive definition is the repo's own
  billing/licensing/payment modules, security-rules files, and auth wiring; `hooks/review_risk_tier.py`'s
  money/auth/security keywords are cited only as a *hint* that a pathspec may land there, mirroring
  `trust-architect.md`'s own "trigger convention" language, never as the trigger by themselves —
  migration/deploy keywords are deliberately excluded from the substitution trigger, since those
  force `high` risk tier generally without making a path trust-surface), including the instruction
  to say so in its report if dispatched onto a trust-surface pathspec anyway. Routing which reviewer to
  dispatch remains the orchestrator's job, not the reviewer's own. A trust-surface commit gets
  exactly one Opus review, from `trust-architect` instead of `code-reviewer`, not both.
- **Design review is a separate, non-gating lane.** `design-reviewer` (sonnet, advisory) never
  substitutes for or stacks onto `code-reviewer` — it is a UI/UX-quality lane that "never bypasses
  `review_risk_tier`/gate 3b for any commit that follows from its findings"
  (project `.claude/skills/design-review/SKILL.md`).
- **Outcome ledger.** Every recorded review — `--clean` or `--blockers <n>` — writes to
  `~/.claude/.review_state/last_reviewed` (`record_review.py`), the same ledger gate 3b reads. This
  makes review quality auditable over time; a **bare** `record_review.py` with no outcome flag
  records only that a review happened, not its verdict, and 2026-08-20 measurement found 703/1,043
  historical entries bare — though all of them predate the pre-commit reorder; every
  `precommit:`-keyed entry from the current gate-3b era carries a real outcome (CLAUDE.md §10,
  the "Record the review OUTCOME" bullet — cited by anchor, not line number: §10 grew a warm-
  re-review bullet 2026-08-30 and line citations into it rot on every edit).

## Example invocation

*Illustrative: the path and line number below are made up to show the shape of a finding; they
are not real citations.*

An implementer finishes a fix to a mutex in the estimate engine's tag-combination gate and is about
to commit `modules/estimate_engine/scope_gate.py` plus its test file. Before that `git commit` runs,
the orchestrator classifies risk tier (`high` — the path's `estimate` keyword forces `high` even
though nothing else in the change is risky; full Opus review, no shortcut), dispatches
`code-reviewer` with the pending diff, and the reviewer traces the actual boolean inputs the gate
branches on, finds one tag combination the new tests never exercise, and returns one `blocker`
finding citing `scope_gate.py:142` (illustrative — see note above) with the missing combination
named explicitly. The orchestrator
fixes it and — because the diff's risk tier is `high`, clause (c) of the fix-round ladder —
continues the same reviewer WARM for a FULL re-review of the current pending diff rather than a
targeted verification; it comes back clean, and the orchestrator records it with the warm
chain-identity field set (`--clean --round 2 --reviewer code-reviewer --reviewer-agent-id <round-1
id> --reviewer-tool-use-id <round-1 tool_use_id> --prev precommit:<round-1 digest>` via
`record_review.py --pre-commit`), and only then does `git commit --
modules/estimate_engine/scope_gate.py <test path>` succeed — gate 3b would have denied it at any
point before that recording.
