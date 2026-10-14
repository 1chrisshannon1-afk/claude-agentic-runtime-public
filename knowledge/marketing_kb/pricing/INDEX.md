# Pricing domain — index

**Seat status: LIVE.** `pricing-economist` (opus) is a live runtime agent (defined once in
`~/.claude/agents/`, pinned in `knowledge/model_policy.json`) — this corpus is its operating
discipline. Per-company grounding comes from that company's own pack/dossier, read fresh each
time; a seat with no dossier for a given company declares itself DEGRADED for that company's facts
rather than improvising them, the same convention every other runtime agent follows. Whichever
runtime agent or session actually handles a pricing question for a company applies this corpus
directly.

Doctrine covered: COGS currency (moving figures from calculated to measured) and price-position
challenge. This seat's discipline **questions pricing, it never reprices** — a company's own ladder
is settled and owned by that company's own pricing-ruling document (see the company's own
pack/dossier for where that lives) via its own reopen rule (see
[`reopen-discipline.md`](reopen-discipline.md)). The job is to keep the evidence under that
ladder honest, watch for the four conditions that legitimately reopen it, and bring cost/margin/
competitive facts current — never to propose a new number on its own initiative.

Grep-reachable, not read wholesale. One line per file: what question it answers.

| File | Answers |
|---|---|
| [`reopen-discipline.md`](reopen-discipline.md) | When may a pricing decision already ruled by a company's own pricing source-of-truth document be revisited — what are the four evidence classes, what does the reopen rule typically look like, and what does a seat do when it *thinks* it has found one? |
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must this seat's discipline never recommend or do — churn-by-reopen, premium-anchoring against an operator's volume ruling, silent repricing, and the other domain-specific failure modes? |
| [`cogs-currency-method.md`](cogs-currency-method.md) | What does "COGS currency" mean, why is a company's per-unit COGS figure often calculated-not-measured, and what is the general method (routing fix, instrumented cost-audit run, unpriced-stage resolution) that converts it to a measured, trustworthy number? |
| [`cac-ltv-payback.md`](cac-ltv-payback.md) | What are the CAC/LTV/payback-period norms for SMB SaaS, how does a company compare against them today, and how does a seat challenge a growth plan that violates the ratios without ever touching the price itself? |
| [`price-position-watch.md`](price-position-watch.md) | How does this domain's pricing discipline monitor competitor price moves on a standing basis, what cadence and method, and how does that watch hand off to `market-analyst` (the runtime's competitor/market-facts seat) rather than duplicate it? |

## How this discipline operates day to day

1. Read `reopen-discipline.md` before touching anything price-related — most requests that look like
   "should we reprice X" are answered "no, see the reopen rule" without further analysis.
2. When a genuine evidence-class trigger fires (measured COGS, real churn data, a competitor
   repricing, or an operator ruling), the job is to **surface the evidence and ask a
   question** — never to compute or propose the new number itself. See `ANTI-PATTERNS.md`.
3. The standing maintenance work is `cogs-currency-method.md` (closing the measured-COGS gap that
   a company's own pricing source-of-truth doc typically flags as blocking) and
   `price-position-watch.md` (competitor price-move monitoring, fenced to `market-analyst` for the
   actual market research).
4. `cac-ltv-payback.md` is the lens for judging whether a *growth* plan (not a price change)
   is unit-economically sound — e.g. "is this CAC number healthy for our LTV," never "should the
   price be different."

## Company-specific facts

This corpus is company-agnostic by design (see `~/.claude/CLAUDE.md`'s preamble "Boundary test").
A company's actual ruled prices, its own COGS figures, its own named competitor set, and its own
operator rulings live in that company's own pricing source-of-truth document and pack — see the
company's own pack/dossier, never a path baked into this file.
