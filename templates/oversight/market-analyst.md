# market-analyst — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Not a tracker, not a plan. Grounds the runtime `market-analyst` agent (dispatch-only,
no schedule) as this repo's industry/competitor expert. Missing/stale section ⇒ declare DEGRADED,
never improvise.

**HARD LANE RULE:** market-analyst supplies **inputs only** — dated competitor moves and market
facts. It **never emits a rank, priority score, or ordering.** `launch-director` owns ranking.

## Goal

__PRODUCT_ONE_LINER__. __PRODUCT_MATURITY_STATE__.

## Stack

__PRODUCT_STACK_SUMMARY__ (backend/frontend/datastore/AI-vendor/billing, briefly — enough to
sanity-check a competitor's technical claim against what's feasible for a product like this).

## Industry

__PRIMARY_MARKET__ — __POSITIONING_BET_SUMMARY__ (the specific architectural/GTM choice that
differentiates this product from the pack, if any).

## Competitor roster

*Named competitors, each with a mechanism note — how they actually work, not just their marketing
claim.*

__COMPETITOR_LIST__ — for each: __COMPETITOR_MECHANISM_NOTE__.

## Positioning truth

__POSITIONING_TRUTH_SUMMARY__ (an honest, unflattering-if-warranted comparison against the roster
above — stated plainly, not optimistically).

## Baselines

*Every prior sweep's dated findings, each with a re-derive pointer/URL and as-of date, in
chronological order — future sweeps are a DELTA against the newest baseline, never a fresh read.*

### Baseline #1 (as-of __BASELINE_1_DATE__; re-derive: __BASELINE_1_REDERIVE_COMMAND__)

__BASELINE_1_SUMMARY__

## Watch pattern to carry forward

__WATCH_PATTERN__ (any recurring pattern worth a standing watch across sweeps).

## Briefs

*Dated sweep briefs live in `<repo>/.claude/oversight/market-analyst/briefs/<date>.md` (one file
per date) — create this directory the first time a brief is written. Update this pointer every
time a new brief lands.*

Latest: __LATEST_BRIEF_PATH__.

## Never-ranks reminder

This dossier and every brief are **inputs to `launch-director`**, never a priority queue
themselves. Do not read a competitor move as "so we should build X next" — that's
launch-director's call alone.

## RESEARCHABLE-lane fence

market-analyst serves **market/competitor facts**. `research-scout` serves **tools/OSS/prior-art
facts**. A GTM clarify-phase question tagged RESEARCHABLE routes to whichever fence names it,
never both by default. Mirrored in `.claude/oversight/research-scout.md`.

## Marketing department participation

8th seat in the GTM department alongside `marketing-director` and its 6 specialists — no
agent-file/pin change. `~/.claude/knowledge/marketing_kb/` may cite this seat's briefs (the
`## Briefs` section) as a seed source; this seat never writes to that corpus directly.
