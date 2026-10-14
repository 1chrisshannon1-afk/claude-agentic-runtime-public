<!--
Why this file is short.

A 2026 evaluation found repository context files raised inference cost over 20% with no measurable
improvement in task success. This project's own author measured his prior operating document at
~14,000 words, on the order of tens of thousands of dollars at list price (a rough estimate of the token usage
priced at list rates, not an invoiced amount) lost to a single silent model-tier drift, and a median 406,000 cached tokens
per sub-agent dispatch — every one of those tokens includes whatever CLAUDE.md says. Every rule below
is individually justifiable; the point is that collectively, rules an agent must re-read and skim on
every turn become noise it pays for and doesn't absorb. Full account: POSTMORTEM.md, lesson 25
("More instructions made the agents worse").

The fix: this file states the four rules that are broken most often and enforced least reliably by
memory alone, plus where the mechanical enforcement actually lives. Everything else — the full
reasoning, the incident histories, the review-cadence detail, the oversight-roster design — is the
audit trail, not the injected prompt. Read it when you're deciding whether to adopt a rule, not on
every turn: docs/subsystems/ (start with gate-chain.md and review-ladder.md).
-->

# Operating Contract (thin)

In this public repo, `CLAUDE.md §N` means `OPERATING_CONTRACT.md §N`.

**Full reasoning and every subsystem's design doc:** `docs/subsystems/`. This file is deliberately
short — it's injected every session; the reasoning behind it is not.

## The four rules most often broken

1. **Never switch branches, never stash, never `reset`/`rebase`/`restore`/`clean` on the working
   tree.** These wreck other agents' in-flight edits in a shared repo. Mechanically blocked by
   `hooks/block_branch_ops.py` (gate 1) when enforcement is on.
2. **Path-scoped commits only.** Never `git add -A`/`add .`/`commit -a`. Name the exact paths you
   changed. Enforced by `hooks/block_unscoped_commit.py` and `hooks/check_staged_scope.py` (gates
   2–3). Commit locally whenever you want; **ask before any push, PR, merge, or deploy** — every
   time, prior approval never carries forward.
3. **A commit needs a review on record for its exact content, before it lands.** Not after — before.
   `hooks/precommit_review_gate.py` (gate 3b) blocks a `git commit` whose pending diff has no clean
   review keyed to that content's digest. Edit the file afterward and the gate re-fires.
4. **Tests assert intended behavior, not current behavior — and prove it by going red first.**
   Before reporting any fix as done: revert the change, keep the test, confirm it fails. A green
   test you haven't seen fail is not evidence.

## Concurrency (you are not the only agent in this repo)

Assume peers are editing the same tree right now. A contested file → stop, work on something else,
poll, resume — never force through it. `hooks/file_claims.py` (gate 4) makes this mechanical at
commit time: overlapping paths, or a second commit racing the same repo, gets denied rather than
silently racing. Announce a commit train to live peers before you stage.

## Model discipline

Pass an explicit `model` on every sub-agent dispatch — don't rely on inheritance.
`hooks/model_pin_gate.py` enforces each named agent's pinned tier; a session's own model can drift
via the client itself, not just your prompts, so an opt-in session-start check
(`hooks/settings_drift_guard.py`, not wired by default) can restore the committed default
(see `knowledge/model_policy.json`).

## Everything else

Delegation patterns, the review-boundary cadence, the oversight-agent pattern, GTM/marketing
agents, telemetry — all real, all optional, all documented in `docs/subsystems/` rather than here.
Start with `gate-chain.md` if you're deciding what to enforce first.

**The full operating contract** the author runs with is `OPERATING_CONTRACT.md` — an optional appendix, not something to paste here.
