# I am not a developer. I shipped three production apps in nine months with AI agents. Here is everything that went wrong.

*Chris Shannon, September 2026. Updated October 2026.*

I run a remodeling company. In January 2026 I could not write code. By
September I had three applications running in production on Google Cloud — an estimating platform
for remodelers, an operations platform for dental practices, and a research pipeline — built almost
entirely by AI agents I directed. By October, more than twenty-five thousand commits. Hundreds of
thousands of lines.

That is the part people want to hear. It is the least useful thing I can tell you.

The useful part is the failure log. Agents do not fail like junior developers. They fail
confidently, in parallel, at 3am, and then write a fluent summary explaining why everything is fine.
Every rule in the system I ended up with exists because something specific broke, and I wrote down
what it was. This is that list — thirty-one lessons, grouped by the kind of failure they belong to,
with the measured numbers. The system built from this list ships in this repository; the table below
maps each enforced lesson to the actual hook that enforces it.

If you are running agents against a real codebase, you will hit most of these. You do not have to
hit them the way I did.

---

## Lesson → enforcement mapping

Not every lesson has a mechanical fix — some (routing decisions, status-not-narration) are working
habits, not code. Where one exists, it's a real file in `hooks/`, not a promise.

| # | Lesson | Enforced by |
|---|---|---|
| 1 | Two agents in one repo overwrite each other (stash-window collision) | `hooks/file_claims.py` (gate 4) + `CLAUDE.md` §2's "stage everything by name first" |
| 2 | Never let an agent run `git stash` | `hooks/block_branch_ops.py` (gate 1) — `stash` is a blocked state verb |
| 3 | A shell redirect destroyed unrecoverable work | `hooks/block_head_overwrite.py` (gate 1b) — the dedicated guard for this exact shape |
| 4 | A write during a peer's commit gets blamed on the hook | `CLAUDE.md` §2 (announce-before-commit norm) — no mechanical gate; a working discipline |
| 5 | Reading a file during a peer's commit returns stale content | `docs/subsystems/concurrency-and-claims.md` (read the index, not the working tree) |
| 6 | An agent reported a review it never performed | `hooks/precommit_review_gate.py` (gate 3b) — content-digest-keyed, blocks the commit itself |
| 7 | A green test proved nothing (no revert-and-rerun) | `CLAUDE.md` §6 falsifiability rule — working discipline, not a hook |
| 8–16 | Verification/evidence discipline (silent instruments, ungrounded greps, un-designed test batteries) | `CLAUDE.md` conventions + `agents/code-reviewer.md`'s review lens — no single hook; caught at the review boundary |
| 17 | Mandatory per-agent worktree isolation caused a worse outage than it fixed | `docs/subsystems/concurrency-and-claims.md` — worktree isolation is documented as *available*, never default |
| 18 | "Make a scratch copy" filled the disk twice | Working discipline (`git worktree`/extract-from-history instead of `cp -R`); no hook currently blocks a raw `cp -R` |
| 19 | Never kill processes by name on a shared machine | Working discipline |
| 20 | A skipped test reports green | `CLAUDE.md` §6 — pattern named, not independently gated |
| 21 | Suppress with one positive marker, not by clearing inputs | Working discipline |
| 22 | The model setting silently reverted four times, once costing tens of thousands of dollars at list price | `hooks/settings_drift_guard.py`, a session-start self-heal that is opt-in (see `knowledge/model_policy.json` / `model_policy.md`) |
| 23 | The expensive model leaked into every sub-agent | `hooks/model_pin_gate.py` (Task gate T1) — denies an off-pin dispatch |
| 24 | Volume, not model choice, is the real cost lever | `hooks/agent_budget.py` (Task gate T2) — paces/caps fan-out; `telemetry/` measures spend |
| 25 | More instructions made the agents worse | This repo's own `CLAUDE.md` is short by design; the long reasoning lives in docs, not in what's injected every turn |
| 26 | Never bypass a check to get green | `hooks/block_branch_ops.py` / `hooks/block_unscoped_commit.py` don't stop `--no-verify` directly — this one is still a working discipline, named honestly as a gap |
| 27–31 | Human-facing discipline (card decisions, route to specialist, status not narration, don't stop at "deployed," prefer the unbypassable mechanism) | `CLAUDE.md` conventions — working habits, the summary principle behind every hook above |

---

# Part 1: Agents destroy each other's work

## 1. Two agents in one repository will overwrite each other

Three sessions were running in the same repo one night. An entire session's uncommitted work
vanished mid-session.

The mechanism surprised everyone. Git's pre-commit hook stashes your **entire working tree** before
running checks — not just the files you are committing. I verified it in pre-commit's own source: it
runs `git diff-index` with no pathspec from the repository root and restores with `git checkout --
.`. So when agent A commits, agent B's unrelated unsaved edits sit inside that stash window, and if
the restore fails they are gone.

The work was recovered only because pre-commit keeps every stash as a patch file in its cache. That
is luck, not design.

**Fix:** stage every unstaged file by name before committing, so the stash set is empty. Announce
the commit to live sessions. A shared ledger claims file paths so two agents cannot commit
overlapping files at once. See `hooks/file_claims.py`.

## 2. Never let an agent run `git stash`

An agent stashed files it did not own. From every other session's view, completed and verified work
simply disappeared. **This happened three times in one session** before the rule went in.

A stash is global to the repository. It ignores the path-scoping that makes everything else safe.

**Fix:** `stash`, `reset`, `checkout`, `restore` and `clean` are blocked outright for agents. If a
command demands a clean tree, scope the command instead. And note: "I only run one session" does not
make stash safe — a background agent is a second session. See `hooks/block_branch_ops.py`.

## 3. One shell redirect destroyed work that git could not recover

An agent ran `git show HEAD:path > path` — restoring a file from history over itself — to "fix formatting
sanity." The working tree differed from history for a reason: genuine, never-committed feature work
was sitting in that file. The redirect overwrote it instantly and **unrecoverably**. Unstaged
content leaves no object in git's database, so there was nothing to recover: no dangling blob, no
sibling branch, no worktree copy. Gone.

What makes this one instructive is that **no existing guard caught it**. Blocking dangerous git
subcommands does nothing here, because `git show` is read-only. The destructive act was a *shell
redirect*, using git only as the content source.

**Fix:** a dedicated guard for the self-overwrite shape (`hooks/block_head_overwrite.py`). The wider
lesson: enumerate dangerous *effects*, not dangerous *commands*. Your list of forbidden verbs will
always have a hole shaped like a tool you classified as safe.

## 4. Any write during someone else's commit gets blamed on the hook

In a shared tree, if any agent writes a tracked file while a peer's pre-commit hooks are running,
pre-commit attributes the change to *its own hook* — "files were modified by this hook" — and fails
the commit. One slow documentation check made that window about 50 seconds wide. **Nine consecutive
commit failures** were traced to this, none of them caused by the content being committed.

**Fix:** treat a commit announcement as a write pause. Do not retry blindly — identify whose write
landed in the window.

## 5. Reading a file during a peer's commit returns the wrong content

While any commit is in flight, a working-tree read of a staged file can return the pre-commit
content rather than what is actually staged. Two agents — a reviewer and a documentation fixer —
both read the same file inside that window, saw stale content, and "corrected" a sentence that was
already true.

**Fix:** read the index copy (`git show :path`), not the working tree, for anything that matters.
And `git status` in a shared tree is a measurement with a shelf life of seconds, not a description
of the world.

---

# Part 2: Agents report things they did not verify

This is the category that actually matters, and it took me longest to see.

## 6. An agent reported a code review it never performed

I had a rule that code must be reviewed before commit. An agent reported the review complete. It was
not. The report was fluent, specific, and false.

You cannot fix this with a better prompt, because the thing writing the code also writes the report
about the code. Asking an agent whether it followed the rules is asking the defendant to file the
verdict.

**Fix:** the review is keyed to a cryptographic digest of the exact pending changes. The commit is
blocked at the git level unless a review exists for *that content*. Edit one line afterward and the
gate re-fires, because it is different content. No agent can self-certify, because the certificate
is checked by something outside the agent. See `hooks/precommit_review_gate.py`.

## 7. A green test proved nothing

An agent fixed a bug and showed a passing test. Both facts were true; together they meant nothing,
because the test passed equally well *without* the fix.

There is a nastier variant where the test never executes the changed lines at all. Reading the diff
catches neither.

**Fix:** revert the production change, keep the new test, confirm it goes **red**. If it does not,
it is not evidence. I now require this before any fix is accepted.

## 8. Confirm the instrument can hear before trusting silence

To prove a bug had never occurred in production, I ran a log query, got zero results, and reported
it as proof. A peer ran the control I skipped: **the same query also returned zero on staging, where
the thing had provably happened 23 times.** The filter was matching the wrong payload field. It was
deaf everywhere.

**Fix:** before concluding "X never happened" from an empty result, run the same query where X
provably did happen. If it returns zero there too, your instrument proves nothing anywhere.

## 9. The five-second disconfirming test

One night, five sessions independently made the same mistake: observe something, pattern-match it to
a mechanism, report confidently, and skip the cheap test that would have falsified it. One `curl`
returning 200 became "staging recovered." A clean rebase became "the bug is gone." A per-IP rate
limit became "the account is locked out," costing about two hours.

The unifying frame is worth more than the individual rules: **before trusting a green signal, name
the question it actually answers.** A clean patch application answers "do these hunks fit?", not
"does this repo still have the bug?" One 200 answers "was it up at that instant?", not "is it up?"

## 10. A grep is a hypothesis, not a measurement

I wrote a plan whose entire thesis was "verify before asserting." Review found **11 false measured
claims in it.** Every one came from a single grep I never cross-checked — I searched for
`blockers=` when the format was `blockers:`, and concluded zero had ever been recorded. I reported a
mean as a median. I cited a line number in a file that was shorter than the line I cited.

**Fix:** any number that enters a document gets verified by a second, different query. And look at
three matching lines before trusting a count.

## 11. Grep for the caller before believing "it's wired"

For any claim of the form "X is wired," "X emits Y," or "no wiring needed" — check for the caller
before believing it. **Three instances in one day.** A confident wrong assertion is worse than
silence: silence invites a look, an assertion closes the question.

## 12. Verify what your agent actually changed, line by line

An implement agent was given three narrow, precisely specified edits to one file. It made them — and
also rewrote unrelated nearby content it happened to be looking at. Its own report sounded precise
and scoped. **The identical thing happened again in a different file minutes later.**

**Fix:** read the full diff of every touched file yourself before review or commit. The agent's
summary is not the diff.

## 13. A battery you design only tests what you imagined

When I verify my own work and declare it correct, that is evidence of internal consistency, not
coverage. In one case my gate matrix passed 46 of 46 — while **10 of its own 17 positive controls
flipped to the wrong answer** the moment a second fixture was introduced.

**Fix:** a self-designed verification suite needs an adversarial second pass by something that did
not write it. For questions that gate real work, put the identical question to two specialists
independently. Agreement is strong evidence; disagreement is the finding, and it points exactly at
the subtle spot.

## 14. Never describe a guard by what it was built to catch

Three consecutive reviews caught me making the same over-claim: describing a new guard by the defect
class it was designed for, rather than by what it was measured to catch.

**Fix:** build the adversarial probe set *before* writing the commit message, and state only the
measured catch rate.

## 15. Check the failure mode before auditing the outputs

When you find a broken tool, the first question is *how* it broke. A tool that crashed loudly cannot
have produced artifacts — those are fine. A tool that silently returned empty makes **every
downstream artifact suspect**. Same defect, opposite blast radius.

## 16. An inherited symptom is a claim with a date on it

An open issue's description is not a description of today. Re-measure before promoting any inherited
symptom into an acceptance criterion. I gated real work on a symptom that had already been fixed.

---

# Part 3: The fixes cause the next outage

## 17. Isolating every agent was worse than the problem it solved

The obvious answer to agents clobbering each other is to give each its own checkout. I made it
mandatory for every session and sub-agent.

Five days later: six crashed sessions, **233 checkouts consuming 103 GB**, agents unable to clean up
after themselves, and phantom deletion diffs in stale copies.

I had traded a rare, recoverable problem for an unbounded one.

**Fix:** main tree by default, accept the occasional clobber, fix it when it happens. Isolation only
for three narrow cases: three or more agents writing genuinely separate files, work that must be
abortable as a whole, and unattended jobs where isolation is the verification mechanism.

**The wider lesson:** when a mitigation is cheap to apply everywhere, you *will* apply it everywhere.
Ask what happens when it runs 233 times.

## 18. "Make a scratch copy" filled the disk. Twice.

Two agents doing falsification checks each copied the repository into scratch space. Each copy
dragged in `node_modules`, `.git`, and 227 stale checkouts — **99.8 GB of worktrees alone.** My
scratch directory went from 60 GB to 364 GB in about an hour and **the volume hit zero bytes free**.
Every session on the machine stopped; `df` itself failed. A peer's writes failed six times with
no-space errors.

It happened a second time on a different day: 137 GB of real content became **332 GB across 387
session directories.**

The instruction was mine: "revert your change in a scratch copy." An agent told to copy the repo
copies the repo.

**Fix:** copying a repository is banned. Extract the handful of files under test directly from git
history, or use git's own worktree mechanism which copies no file content. Bound the instruction,
not the intent.

## 19. Never kill processes by name in a shared machine

`pkill -f pytest` kills every concurrent agent's test run, not just yours. Kill exact process IDs
you own.

## 20. A skipped test reports green

A safety test used a standard pattern: skip if a fixture is missing. The fixture went missing. The
test skipped, reported green, and checked nothing for weeks.

**Fix:** gate by the actual dependency per call site, and require safety tests to demonstrate they
still execute. A skip is a failure, not a pass.

## 21. Suppress with one positive marker, not by clearing inputs

When a decision gate reads several signals, suppressing it by clearing inputs one at a time is
whack-a-mole. Use a single positive state marker.

---

# Part 4: Cost and configuration

## 22. The model setting silently reverted four times

Four separate times, the configuration specifying which model to use reverted to a more expensive
one — not by any script of mine. The editor itself rewrote the file.

The first time, it ran for **two weeks before anyone noticed, at a cost on the order of tens of
thousands of dollars at list price** (a rough estimate of the token usage priced at list rates, not an
invoiced amount).
The drift leaves no commit and no log entry. It simply sits there.

**Fix:** a session-start check (shipped as an opt-in hook) compares that setting against its committed
value and restores it.
With the hook enabled, exposure is bounded to "until the next session starts" rather than "until the bill
arrives". The hook is opt-in and the shipped `settings.json` does not wire it, so without it nothing catches the
drift.

## 23. The expensive model leaked into every sub-agent

Sub-agents inherit the session's model unless you pass one explicitly. Measured: **247 of 317
sub-agent dispatches carried no model field** and silently inherited the expensive orchestrator
model for hours.

**Fix:** pass the model explicitly on every dispatch. Never rely on inheritance, and never assume a
named agent's own configured default applies. See `hooks/model_pin_gate.py`.

## 24. Volume is the cost, not model choice

I spent months tuning which model handled which task. Small lever.

The large one: every dispatch re-sends its entire context. Measured across my own usage, the median
dispatch wrote about **406,000 cached tokens**, and cache writes were **36.5% of total spend**. Ten
parallel agents cost roughly ten context prefixes. Parallelism buys wall-clock time, never tokens.

I was running **566 dispatches a day** and wondering where the money went.

**Fix:** fan out only when work is genuinely independent *and* the serial path is too slow. Small
known edits are done inline. A dispatch is a purchase.

## 25. More instructions made the agents worse

My operating document reached roughly 14,000 words. I was proud of it. It was hurting me.

Independent findings agree: a 2026 evaluation found repository context files raised inference cost
over 20% with no measurable improvement in task success. One developer measured 69,200 tokens
consumed before their first message. Another deleted 93% of an 8,000-line instruction system and
concluded the layer "was making Claude dumber."

Every rule I added was individually justified. Collectively they became noise the agent paid for and
skimmed.

**Fix:** the shipped instruction file is short. The long document is the *audit trail* of why each
rule exists — valuable to a human deciding whether to adopt one, harmful pasted into every request.
Rules that can be enforced mechanically live in code, because a hook cannot be skimmed. This is why
this repo's own `CLAUDE.md` is short and this document is separate.

## 26. Never bypass a check to get green

`--no-verify`, blanket lint suppressions, broad exception catches. Every one converts a loud failure
into a silent one. In one case a broad `except Exception` swallowed a type error and **three
separate bugs hid behind it**.

The corollary: a permanently-red test is camouflage, not furniture. I repeated a sub-agent's
"environmental, not our problem" diagnosis about **fifteen times without once running it myself.**
It was a real bug.

---

# Part 5: Working with the human

## 27. A question raised only in chat is a question never asked

I do not watch the terminal. Agents would surface a decision in a chat reply, consider the duty
discharged, and the work would sit silently blocked.

**Fix:** the moment an agent forms a question for me, it writes a card to one file I actually open.
Chat is not a channel.

## 28. Route decisions to the specialist, not to the owner

I once received 21 decision cards, most of which an agent could have answered. My response: "These
are obvious answers to obvious questions that should never have been presented to me."

**Fix:** card only what genuinely requires the owner — vendor identity, an irreversible outward act,
a real business judgment. Everything technical goes to the right specialist agent.

## 29. Status, not narration

Agents narrate. I do not need to know how the fix works. I need: what is done, what remains, what is
blocked. Everything else is tokens I paid for and did not read.

## 30. Do not stop at "deployed"

Deployed is not a resting state; it is a to-do. If a change reaches production, verifying it there
is part of the same task, not a follow-up somebody else picks up.

## 31. Prefer the thing that cannot silently be wrong

If I had to compress all of it: **every mechanism that actually held is one an agent cannot talk its
way past.** A hook that blocks a command. A digest that must match. A test that must go red. A
ledger that claims a file.

Everything that failed was a paragraph asking nicely.

---

# What I would tell someone starting today

**Assume the agent is confident and wrong.** Not often. But when it is, it sounds exactly like when
it is not — and that is the whole problem. Build for it.

**Put guardrails in the tool, not the prompt.** Everything above that held is executable. That is
what `hooks/` in this repository is.

**Write down what broke.** Not what you built. Nine months in, my configuration files are
unremarkable and largely reproducible from the free frameworks. This list is the part I could not
have downloaded.

**The hard part was never the code.** The code got written. What took nine months was learning
which failures are possible, and that only comes from having them.

---

# Update, October 2026

A month on, the lessons above still hold. What changed:

- **Reviews are batched.** I used to review every small fix and re-review every fix to a fix. Four
  sub-plans of one feature took four to seven review rounds each, mostly tiny fix-and-recheck loops.
  Now one full review covers a whole unit of work, every finding is fixed in one parallel pass, and
  one targeted check follows. Anything left that is not a blocker becomes a tracked issue, not
  another round. Same lesson as 24: volume is the cost.
- **Working documents are Markdown, not HTML.** Plans, status files and the decision queue were
  HTML. Agents read and rewrite them constantly, and the markup was tokens nobody needed.
- **The marketing department grew, and a venture department joined it.** Twelve specialists plus an
  analyst, a drafter and a checker, and the checker is never the drafter (lesson 13). The venture
  team drafts fundraising, exit, recruiting and outreach work. Neither sends, posts, signs or spends
  anything on its own.
- **Domain teams stay private.** My estimating product runs a general-contractor agent that directs
  one specialist per construction trade to review the engine's output and feed fixes back into it.
  Those agents are the product, so they are not in this repository; the theory is in
  `docs/patterns/estimate-feedback-loop.md`.

---

*A footnote, added while writing this: the guard from lesson 3 blocked me mid-draft. My editing
script contained that command as a quoted example, and the hook's raw-text scan does not care
whether a string is an instruction or a sentence about an instruction. It refused, explained itself,
and suggested redirecting to a different path instead. That is the correct behavior for something
protecting unrecoverable work, and it is a fair illustration of the whole argument: the mechanism
does not need to understand my intent to save me from the case where I am wrong.*

*I install this system for teams adopting Claude Code — hooks, review gate, concurrency controls,
tuned to your stack, in about a week. Contact: [@1chrisshannon1-afk](https://github.com/1chrisshannon1-afk), email on the profile.*
