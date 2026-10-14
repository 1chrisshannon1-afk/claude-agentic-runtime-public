# research-scout — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Not a tracker, not a plan. Grounds the runtime `research-scout` agent for prior-art
sweeps and one-question consults scoped to this repo. A missing/stale section here means the
agent declares itself DEGRADED for this target — it can still search/evaluate OSS generally, but
cannot claim target-specific framing it was not actually given.

## Goal

*One paragraph: what this product is, its stage, and its hardest unsolved problem, if any —
needed to prioritize which domains are worth surveying.*

- __PRODUCT_GOAL_SUMMARY__

## Stack

*Backend/frontend framework, datastore(s), hosting/cloud project, monorepo layout — enough to
reject prior art targeting an incompatible stack before wasting a query.*

- __STACK_SUMMARY__

## Domains

*Numbered list of technical domains worth surveying, each with why it matters — not a generic
"search everything" list.*

- __RESEARCH_DOMAIN_1__ — *domain + why.*

## Seed queries

*Starting queries per domain, plus known junk-query lessons (which phrasings return garbage) so a
fresh sweep doesn't repeat a known-bad query shape.*

- __SEED_QUERY_LIST__ · __QUERY_CRAFT_LESSONS__

## Hard constraints

*Verbatim-faithful, non-negotiable constraints on usable prior art — pricing/vendor rules, budget
constraints, scope limits, and any "nobody in this market solved X" fact that raises the evidence
bar for claims about X.*

- __HARD_CONSTRAINT_1__

## QUARANTINE — any research-only / shadow-mode domain

*If an operator ruling quarantines a domain from ever becoming a live-system input, name it here.
Delete this section if no such ruling exists.*

- __RULING_QUARANTINE__ — *operator records their own ruling here.*

## Degraded facts

*Facts carried from a groundwork/probe process that are themselves marked unverified or
point-in-time — kept honest, never upgraded to fact by repetition.*

- __DEGRADED_FACT_1__

## RESEARCHABLE-lane fence

*If this repo also runs `market-analyst`: research-scout serves tools/OSS/prior-art facts;
market-analyst serves market/competitor facts. Mirror this fence in the sibling dossier.*

- __RESEARCHABLE_LANE_FENCE__

## Already-evaluated repos — the runtime ledger

*Pointer to the runtime research ledger and this target's slug, so a sweep checks for
already-recorded findings before re-surveying a domain.*

- __RESEARCH_LEDGER_TARGET_SLUG__
