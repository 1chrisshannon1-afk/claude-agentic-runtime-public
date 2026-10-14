# trading-strategist

**This agent is out of the runtime bundle.** It is a personal-finance product-domain specialist
scoped to one repo (`other-project`), not a shipped runtime capability — it carries no
`.claude/oversight/trading-strategist.md` dossier and no `templates/oversight/trading-strategist.md`
template, and its two grounding primers (`knowledge/agricultural_futures_primer.md`,
`knowledge/trading_strategist_equities_primer.md`) are not exported by the mirror sync's `include`
list. This page documents the agent as it exists today for orientation only; it is not evidence
that the agent is portable to another repo the way the other 29 runtime agents are.

`trading-strategist` is an advisory trading-domain specialist for equities and agricultural
futures: it analyzes market structure, ranks opportunities, and argues for or against specific
trades using verified data and named judgment calls (`agents/trading-strategist.md:3`). It **never
sizes a position, sets or moves a stop, alters a circuit breaker, or places an order**, and it
holds no broker or write tooling of any kind. Every output it produces is data — a thesis for a
human and the journal, never an input any deterministic rail reads.

## Model & tools

- **Model:** `sonnet` (`agents/trading-strategist.md:4`). The agent's own file is explicit that it
  is a product-domain specialist, not a member of CLAUDE.md §13's oversight roster — it carries no
  scheduled trigger and no row in that section's table, so none of §10's Opus-reservation rules
  apply to it and it is not one of §10's sanctioned-Opus oversight extensions either
  (`agents/trading-strategist.md:33-41`). It must still be a listed row in
  `knowledge/model_policy.json`'s `agent_pins` — confirmed present, pinned `sonnet`, 2026-09-09.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/trading-strategist.md:5`) — no `Edit`/`Write`, no
  broker tool, no path into `risk/`, `execution/`, `config/`, or `prompts/` via any tool it holds.
  **Its own file is unusually direct that the `Bash` read-only discipline is UNENFORCED PROSE, not
  a mechanical rail** — nothing in that repo's hook chain, `settings.json` deny list, or any other
  gate stops a `Bash`-holding agent from running a mutating SQL statement or redirecting output
  into a config file; the discipline binds because the agent chooses to honor it on every call, the
  same way every other rule in the file binds (`agents/trading-strategist.md:15-31`).

## When it's dispatched

By name, on demand — to get a second, disciplined opinion on a candidate trade, to stress-test a
thesis someone else proposed, or to explain what a repo's deterministic gates would do with a given
setup, never to execute anything (`agents/trading-strategist.md:3`).

## What it does

Reads two domain-corpus primers (equities market microstructure, order types, risk semantics,
position-sizing frameworks, regime awareness, and a full walkthrough of how a recommendation flows
through the repo's deterministic gates; agricultural-futures contract mechanics, margin/daily-limit
behavior, first-notice-day risk, USDA/CFTC/EIA data cadence, and seasonality) plus the repo-local
dossier for repo-specific facts (`agents/trading-strategist.md:47-79`). Every output binds to a
**prime-invariant compliance** discipline: the model reasons and recommends, deterministic code
owns every consequence — a verdict is data, never phrased as an instruction any rail would consume;
conviction never exceeds a repo's deterministic cap; no symbol outside the deterministic candidate
universe is recommended as actionable; a hand-executed recommendation is labeled
`OPERATOR-EXECUTED` on its face. It applies a method-discipline checklist (pre-registration,
episode counting, correlated-symbol deflation, out-of-sample-once, reporting the embarrassing
number, lift-over-control) on every quantitative claim, and treats a deterministic gate's refusal
as information about the trade, never an obstacle to route around
(`agents/trading-strategist.md:80-172`).

## Grounding

Two primers, both **UNVERIFIED as exported**: `~/.claude/knowledge/agricultural_futures_primer.md`
and `~/.claude/knowledge/trading_strategist_equities_primer.md` — a missing primer degrades this
agent's *domain competence* itself, with nothing else in the file to answer from, unlike a missing
dossier which only degrades repo-specific facts. Repo-local dossier:
`<repo>/.claude/oversight/trading-strategist.md` in the `other-project` repo — not present in
ExampleApp (checked 2026-09-09; this agent has no dossier here, consistent with it being
scoped to a different repo entirely, not an install gap in this one).

## Boundaries — what it will NOT do

Never determines position size, sets or moves a stop, alters a circuit breaker, or places an order
— not even hypothetically phrased as a suggestion with numbers attached. Never proposes a symbol
outside the deterministic candidate universe as actionable. Never drafts language engineered to
slip past a deterministic rail or suggests one should be loosened for a compelling case.

## How it fits with other agents

It is not part of the oversight roster or the GTM department documented elsewhere in this
directory — it is a standalone product-domain specialist for a repo outside the scope of this
bundle's other 29 documented agents. This page exists so the runtime's `docs/agents/` directory
accounts for all 30 defined agents, not because this one ships the same way the others do.
