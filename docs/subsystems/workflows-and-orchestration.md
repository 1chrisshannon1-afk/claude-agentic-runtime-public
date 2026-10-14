# Workflows & Orchestration

*Shorter doc by design — this is a tool capability, not a persistent subsystem with its own state.
For the mechanics of writing a Workflow script, see the `workflow-authoring` skill (load it before
authoring one; it doesn't itself authorize running one).*

## The Workflow tool's role

The `Workflow` tool runs a saved JavaScript pipeline script that orchestrates multiple sub-agent
dispatches with real control flow between them — parallel fan-out, a schema-validated hand-off from
one phase to the next, conditional rework loops — rather than one agent making ad-hoc `Agent` tool
calls turn by turn. Two scripts are saved under `~/.claude/workflows/`: `deliver.js` and
`issue-wheel-triage.js` (the sonnet-only, read-and-report triage pass of THE ISSUE WHEEL, covered in
`oversight-wheel.md`). `deliver.js` is the concrete reference for the general shape:

```
meta.phases = [
  Understand  — parallel read-only investigation (N angles, sonnet, agentType: explore)
  Plan        — one plan proposal + an INDEPENDENT Opus plan review before any code is written
  Execute     — parallel implementers, one per plan item, split by disjoint file sets
  Verify      — adversarial multi-lens verification (opus) — "works", "regressions",
                "intent-and-tests" (mandatory baseline lens), "docs-and-issues"
  Report      — honest status: `done` is a conjunction of "everything landed" AND
                "every lens confirmed"; NOT_done lists exactly what's outstanding
]
```

This is the **readers → judge → verify** pattern named in the task: a cheap-tier parallel read-only
pass builds context, a plan gets reviewed by a different, more capable tier *before* code is
written, implementation runs split by file so parallel agents never touch the same path, and
verification runs multiple independent "lenses" (different questions, not just more copies of the
same check) against the result — with a hard round cap so a rework loop can't spin forever, and a
report that surfaces blocked/unverified work rather than laundering it into a false "done."

`deliver.js`'s own design notes are worth citing directly, since they document real failure modes an
earlier, more elaborate draft was rejected for by two independent Opus reviewers: claiming `done` while
items were still unimplemented; silently corrupting operator intent via a regex that stripped
anything that looked like a "+<number>"; a "max 3 rework rounds" that actually computed to 5; a
5-way concurrent Opus whole-diff review fan-out (exactly the synchronized big-context burst that
trips per-minute rate limits); and a planning agent with `Edit`/`Write` access that could silently
modify files before any review ran. Every one of those is named inline in the source as a thing
deliberately designed out, so a future editor doesn't reintroduce it.

Beyond the saved scripts, a session can also author a **Workflow script inline**, for a
one-off task, without saving it under `~/.claude/workflows/` — the standing recommendation ledger
records a real instance of this: on 2026-08-27 a session ran three such inline workflows totaling
33 agent dispatches (10 trade specialists run twice, 12 discovery/verify readers, plus the General
Contractor, `engine-architect`, and `vision-measurement-architect`) for a review pass, none of it
persisted as a reusable script (`~/.claude/knowledge/agentarch_recommendations.jsonl`, entry
`AA-0047`, status: moved). The still-open gap this pass surfaced — agents dispatched *inside* a
Workflow run leave no row in the spend ledger the way a direct `Agent` tool dispatch does, so
`churn_report.py`'s spend metrics currently undercount any work done through this mechanism — is
now tracked as `AA-0049` (status: open).

## Warm continuation of a dispatched agent (`SendMessage`)

An `Agent` dispatch returns an agent id; `SendMessage` to that id resumes the SAME
agent with its context intact — this is how `CLAUDE.md` §10's warm re-review rule continues a
round-1 reviewer for a full re-review round (2026-08-30, #4686). What is MEASURED
(2026-08-30/31): a plain FOREGROUND dispatch (`run_in_background: false` or unset) is
continuable by its agent id — 6 of 6 continuations that night, all foreground, all within one
session. UNVERIFIED in either direction: continuing a background dispatch, a
worktree-isolated dispatch, a workflow-internal agent, or an agent from a DIFFERENT session —
treat a failed continuation as non-continuable and fall back rather than improvising.
Other hard preconditions: the dispatching session still alive, the agent's context not
exhausted, and a client that has the tool. A continuation mints NO new
budget lease (`settings.json` registers `agent_budget.py` on `PreToolUse:Task`,
`PostToolUse:Task`, and `SubagentStop` — a continuation triggers only the `SubagentStop` leg,
whose no-claim fall-through appends a stop row with `tool_use_id: null, model: null`). That row is
**not** content-free, though: `agent_budget.py`'s stale-stop reap (the `stale_stop_kind` handling
in `reap_stale()`) computes real `tokens`/`tokens_total` from the agent's transcript
file — measured 2026-08-30/31, 954 of 996 no-claim rows carry a real `tokens_total`, not null.
The field is `tokens_total`, never `total_tokens`. Because `sum_transcript_tokens` sums the
WHOLE transcript on every call, and a continuation's transcript keeps growing across rounds, the
consequence is not invisibility but **cumulative mis-attribution**: each round's reap re-emits a
`tokens_total` that is the FULL transcript total to that point, under the SAME `agent_id` (no new
`tool_use_id` distinguishes one round's row from the next), so a naive `sum(tokens_total)` over
that agent's rows DOUBLE-COUNTS every earlier round — measured on one continued agent's three
release rows: `tokens_total` read 41.8M → 278.3M → 360.6M, the same underlying transcript counted
three times, not three independent costs. This is why a warm review round can only cite round 1's
identity pair in the review ledger, and why fixing this — not merely making it visible — is what
the `--warm` ledger dimension on #4686 must solve (e.g. a delta-since-last-round field, rather
than naive summation over `agent_id`). When continuation is unavailable, dispatch fresh — for
reviews, that is the COLD fallback, never a downgrade.

## Workflow dispatch vs. plain parallel `Agent`-tool dispatch

`~/.claude/CLAUDE.md` §1 ("Parallel when it pays — delegate by size, not by reflex", rewritten
2026-09-20; it replaced "Parallel by default — and ALWAYS delegate to sub-agents") describes the
**everyday path**: the main session makes small, single-file, already-understood edits itself;
when work is multi-file or needs its own exploration it dispatches an `Agent`; and it fans several
`Agent` calls out in one message only when the items are genuinely independent AND the serial path
is too slow for the task at hand — because every dispatch pays its own context prefix, so N agents
cost ~N prefixes. That path stays low-ceremony — no saved script, no schema, no phase structure.

`Workflow` is reached for the same reason `deliver` exists at all — namely, when a task is substantial
enough to want the *whole* shape — independent plan review before implementation, multiple
verification lenses after, a bounded rework loop, and a single honest report — codified once so it
runs the same way every time, instead of a session hand-rolling those steps turn by turn and
potentially skipping one under time pressure. The `deliver` **skill** (listed separately in the
skills roster, described as "the standard way to run a substantial task without hand-driving each
step") is the user-facing entry point to this exact script — invoking it is what actually launches
`Workflow({name: 'deliver', args: '<task>'})`.

Practical rule of thumb: independent, disjoint pieces of work with no real hand-off between them,
when the serial path is too slow for the task at hand → plain parallel `Agent` dispatch (§1). A task that itself has *stages* — must be understood, then
planned, then independently reviewed, then built, then adversarially verified, with each stage's
output feeding the next — is what `Workflow` is for.

**Correction (2026-08-30):** "Ultracode" is real — no agent, hook, knowledge doc, schedule, or
`CLAUDE.md` line authors or configures it, because it is a **Claude Code harness-level
`agentType`**, not a `~/.claude` dotfiles subsystem. It is not a
Workflow-specific gating mechanism distinguishing Workflow usage from plain parallel `Agent` dispatch
— it shows up as a dispatched agent's `agentType` value the same way `"workflow-subagent"` or a named
runtime agent's id does. Two pieces of live, verified evidence: `hooks/spend_attribution.py`'s own
`_output_entry_score()` docstring records observing it directly in a real dispatch's `.output`
`workflowProgress` snapshot (`agentType: "ultracode", model: "claude-opus-5[1m]"` — a long-context
Opus variant tag), and `~/.claude/.agent_budget/spend.jsonl` carries real rows with
`"agent_type": "ultracode"` at very high token counts (10 rows as of 2026-08-30, summing to
~187.5M `tokens_total`; verify with
`grep -c '"agent_type": "ultracode"' ~/.claude/.agent_budget/spend.jsonl`). `spend_attribution.py`
already treats it like any other agent_type value when resolving/pricing ledger rows — there is no
special-cased handling for it and no opt-in flag anywhere in this runtime that turns it on; it is
simply a real value the harness itself emits for some dispatches.
