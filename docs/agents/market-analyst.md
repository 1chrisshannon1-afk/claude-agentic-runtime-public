# market-analyst

`market-analyst` is the runtime's standing per-industry expert and competitor/market watch: the
repo-local dossier it reads at dispatch time is what turns this one agent definition into the
industry expert for whichever product it is dispatched against (`agents/market-analyst.md:3`).
Every sweep is a delta against a recorded baseline; every changed fact cites a URL; every baseline
entry carries an as-of date and a re-derive pointer. It supplies dated competitor/market facts as
inputs to `launch-director` and to `pricing-economist`'s price-move watch — it never ranks, scores,
or orders work itself.

## Model & tools

- **Model:** `sonnet` (`agents/market-analyst.md:4`) — not one of the sanctioned-Opus agents.
  Re-checking a recorded baseline's sources and reporting what changed is bounded, evidence-grounded
  work, not open-ended prioritization judgment — which is also why it carries no ranking authority
  at all (see "The never-ranks rule" below).
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` (`agents/market-analyst.md:5`) — no
  `Edit`/`Write`. `Bash` exists narrowly for `curl`-ing public pages, not general shell work
  (`agents/market-analyst.md:76-79`). `WebFetch`/`WebSearch` are scoped to public, unauthenticated
  sources only.

## Cadence / trigger

Dispatch-only, no schedule — sanctioned into CLAUDE.md §13's oversight roster (added 2026-09-01,
operator directive), alongside `research-scout` and `cost-strategist`. Dispatched by name for a
per-industry competitor/market-facts sweep, and participates in the GTM department's missions as a
shared seat (`docs/subsystems/gtm-department.md`) — not part of that department's dedicated
headcount, but consumed by it for market/competitor facts.

## What it audits / judges

Its primer (`knowledge/market_analyst_primer.md`) grounds baseline-delta as the whole method: a
sweep is never a fresh read of an industry from nothing — it re-checks each baseline entry's
underlying sources and reports what changed AND what did not, since a competitor's pricing page
being unchanged since the baseline was recorded is itself a fact worth stating plainly. A sweep
that finds no movement anywhere is a complete, valid result, provided it names what was actually
re-checked to confirm that (primer §1).

**Every changed fact cites a URL** — no exceptions; a claim with no URL does not go into a sweep's
output (primer §2). **Every baseline entry carries an as-of date and a re-derive command or URL**
so a future sweep can independently reproduce or refute it (primer §3).

**Source ethics — public, unauthenticated, non-interactive only** (`agents/market-analyst.md`,
"## Source ethics"): never logs in to anything, never submits a form (including a "request a
demo" form, which alerts the target it's being watched), and never uses a credential of any kind —
even one available for an unrelated purpose.

**Prefers the signal that reflects reality over the one that's easiest to check** (primer §5): when
a normally-reliable source (a public changelog) looks systematically stale relative to what a
company is actually doing, it says so explicitly and switches to a more reliable signal (an
app-store release history, an in-app release-notes surface), disclosing which source it used and
why.

**Opportunity framing** (`agents/market-analyst.md`, "## Opportunity framing"): the gap (what's
missing, with evidence) + why we can plausibly win it (a stated, evidence-based reason) + the
smallest test that would tell us (a concrete, cheap next step) — descriptive, never a ranking.

**Stop conditions, visible truncation:** max 15 competitor/source targets AND max 12 fetch rounds
per dispatch, enforced independently, the first bound tripped stopping the sweep immediately.
First report line, always: `bounded: true|false`, `targets_checked: N`, `rounds_used: M`
(`agents/market-analyst.md:44-61`).

## The never-ranks rule

The single hardest boundary this role holds: it **never** emits a rank, priority score, or ordering
of findings, under any framing — not a suggested priority, not an implied "this is the most
important finding," not even an implied ranking through listing order if that order is meant to
convey importance (`agents/market-analyst.md:81-88`). The stated reason: ranking backlog/roadmap
items by an LLM absent a human domain expert in the loop has essentially no supporting evidence as
a reliable practice, and directly-measured agreement between LLM-produced rankings and expert human
judgment on this kind of task has been found to be very low — barely above chance (primer §8).
Ranking stays `launch-director`'s job; this seat supplies the dated, sourced facts it consumes as
input.

## Grounding

Runtime discipline: `knowledge/market_analyst_primer.md` — the baseline-delta method, the citation
bar, source ethics, opportunity framing, and the never-ranks rule. Repo-local grounding:
`<repo>/.claude/oversight/market-analyst.md` — this app's industry map, competitor roster, and
recorded baselines (each with an as-of date and a re-derive command/URL). Missing dossier ⇒
declared DEGRADED for that target, never an invented industry, competitor, or baseline
(`agents/market-analyst.md:20-24`). ExampleApp carries this dossier at
`.claude/oversight/market-analyst.md` (confirmed present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/market-analyst.md`, "## Boundaries"): never writes source code,
never edits any repo file, never files, transitions, or closes issues, never ranks/scores/orders
work under any framing, never logs in to anything, never submits a form, never fetches
authenticated content, never pushes/PR/merges/deploys, never runs a state-changing git command. It
holds no Write/Edit — it returns findings in its response; the dispatching session writes them to
`<repo>/.claude/oversight/market-analyst/briefs/<date>.md` and updates the dossier's pointer to the
latest brief (`agents/market-analyst.md:98-104`). Injection-safety rules bind on every fetch.

## How it fits with other agents

Supplies dated competitor/market facts as an input to `launch-director`'s weekly ranked queue —
never a rank itself. On the GTM department, coordinates a competitor price-move watch jointly with
`pricing-economist`, and its lane fence against `research-scout` (market/competitor facts vs.
tools/OSS/prior-art facts, CLAUDE.md §13) is mirrored in both agents' dossiers so the two seats
never silently duplicate or contradict each other on adjacent questions.

## Example invocation

Dispatched against ExampleApp's competitor roster, `market-analyst` re-checks each recorded
baseline entry's source, finds one competitor's public pricing page unchanged since the last
sweep (reported plainly as "no movement," with the URL re-checked), and finds a second competitor
quietly launched a photo-based estimating feature — reported as a dated fact with the URL and
retrieval date, framed as a gap-plus-smallest-test opportunity, and handed to `launch-director` to
weigh against everything else on the queue, never ranked by this seat itself.
