# launch-director

`launch-director` is the runtime's product-direction oversight agent: a principal product
strategist for a solo-founder, pre-revenue SaaS run largely by AI agents. It answers one question,
continuously — "what is the shortest path to the first paying customer, and what is currently
blocking it?" — and ranks, kills, or elevates every piece of visible work against that question
alone (`agents/launch-director.md` § "You are the launch director"). It exists as a STANDING role rather than an on-demand
one because prioritization drift and gold-plating are slow, cumulative failures: nothing else in
the roster looks at the *whole* body of work every week and asks whether it is still pointed at the
one goal. Without a standing cadence, an agent-run codebase can quietly build outward (nice-to-haves,
premature scale, unrequested polish) with no single voice ever stepping back to say so.

## Model & tools

- **Model:** `opus` (`agents/launch-director.md:4`) — one of the runtime's sanctioned-Opus
  agents under CLAUDE.md §10's oversight-roster extension (2026-08-23/§13; the mechanical mirror is
  `hooks/sync_agent_rules.OPUS_AGENTS` plus `knowledge/model_policy.json`). This is judgment work —
  ranking the entire body of open work against a single goal, calling gold-plating vs. legitimate
  scope, synthesizing a weekly verdict — not mechanical detection, which is why it sits at the
  Opus tier rather than the cheaper tier used for sentinel/board-steward/consistency-auditor/
  product-qa.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/launch-director.md:5`) — read-only. There is no
  `Edit`/`Write` grant, which is the mechanical enforcement of its stated boundary: it ranks and
  reports, it does not touch code, docs, or the tracker itself.

## Cadence / trigger

Designed to run weekly as a scheduled oversight job: the `launchdir` row of CLAUDE.md §13's job
table, a plist with a weekly `StartCalendarInterval` (`schedules/example.oversight.plist` shows the
shape of such a job; `docs/subsystems/oversight-install.md` explains how one is installed and how
to tell whether it is loaded). Which jobs are actually loaded is per-machine state, so this page
does not assert it. The agent also runs on demand: any session starting substantial product work is
instructed to read its latest ranked queue first (CLAUDE.md, "Oversight roster" section), and the
manual fallback when schedules are down is `/sweep`.

## What it audits / judges

Its primer (`knowledge/launch_director_primer.md`) supplies the actual frameworks it applies:
RICE/ICE/WSJF prioritization scoring and each one's documented failure modes (subjectivity,
"theater without evidence," missing non-scorable strategic value); Riskiest-Assumption Testing
(falsify the weakest assumption first, cheapest test, before building); and the documented
distinction between **gold-plating** (unrequested extras past the brief — cut it) and **scope
creep** (the operator asked for more but the plan wasn't repriced — renegotiate it, don't
unilaterally refuse). It produces a weekly **state-of-the-app report**
(`agents/launch-director.md` § "What you produce") with a fixed shape: a one-line verdict (on-track / drifting /
blocked), a ranked queue emitted BOTH as prose and as a machine-readable JSON block
(`<script type="application/json" id="oversight-ranked-queue">`) that THE ISSUE WHEEL job's own
P4 QUEUE phase merges in as one ranking input (see above), an explicit kill list (work that doesn't move toward the goal, named plainly),
blockers/asks with a by-when, a trend + spend-sanity line, watch items, and a liveness check on the
daily oversight job's heartbeat — because the watcher chain is a loop, not a line: it watches the
daily job weekly, the same way the daily job watches every other scheduled job daily.

## Grounding

Runtime discipline: `knowledge/launch_director_primer.md`. Repo-local grounding:
`.claude/oversight/launch-director.md` in the repo being reviewed — the app's stated goal, where
its trackers/board/pricing docs live, and its current stage. Per the agent's own Read-FIRST list,
a missing dossier is declared explicitly in the first line of its report and the agent operates
DEGRADED rather than improvising app facts (`agents/launch-director.md` § "Read FIRST, before any
judgment", item 2). A repo adopting the runtime supplies this dossier itself, starting from
`templates/oversight/launch-director.md`.

## Boundaries — what it will NOT do

Per its own definition (`agents/launch-director.md` § "Boundaries"): never edits files; never files, closes,
or transitions issues (findings route through board-steward's rules, executed by the orchestrator);
never pushes/PR/merges/deploys; never touches production. Every claim is either VERIFIED (a file/
board citation with a heading or grep anchor, never a bare line number) or explicitly marked
JUDGMENT — model memory is never evidence, and counts always carry the command used plus an
as-of date. Open questions stay inside the report; they are never relayed to the operator as
separate standalone questions.

## How it fits with other oversight agents / the review boundary

launch-director sits above the other fourteen agents of the fifteen-agent oversight roster
(CLAUDE.md §13) in the sense that its output, the ranked queue, is what THE ISSUE WHEEL job
(`com.oversight.wheel.csa`) consumes, via its own P4 QUEUE phase (`issue_wheel_queue.py`), as one of
several ranking inputs. The former nightly finishing-loop job (`com.oversight.csa.loop`, which
pulled up to two items directly off launch-director's ranked queue each run) was removed in
favour of THE ISSUE WHEEL, whose own queue merges launch-director's ranked queue with several other
sources rather than consuming it exclusively. The wheel's containment is its plist's
`WHEEL_FIX_ENABLED`/`WHEEL_CLOSE_ENABLED` flags; whether the wheel is loaded on a given machine is
that machine's state, read from `knowledge/oversight_install.md` §2's `expected_state` column and
`launchctl list`, never from this page.

launch-director does not file findings itself: anything it surfaces (a stale tracker, a dead-end
effort) goes through board-steward's filing rules like every other agent's output. It never
substitutes for code-reviewer or trust-architect at a commit boundary — those are
correctness/security review, an entirely separate lane from launch-director's product-direction
ranking. Its liveness check on the daily job's heartbeat is the one place it directly depends on
sentinel's own heartbeat-audit duty running correctly.

## Example invocation

The operator has three roughly-equal-effort backlog items: a billing-flow bug affecting the one
active pilot customer, a "nice to have" export-to-PDF feature nobody requested, and a UI polish
pass on a screen used twice a week. launch-director's weekly report would rank the billing bug
highest (blocks the path to a paying customer directly), name the PDF export on its kill list as
gold-plating (unrequested, past the current brief), and flag the polish pass as a watch item rather
than urgent work — with the reasoning for each ranking shown, not just the ordering.
