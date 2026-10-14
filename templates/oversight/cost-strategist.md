# cost-strategist — repo-local grounding dossier (__PRODUCT_NAME__)

Read with `~/.claude/knowledge/cost_strategist_primer.md`. Vendor inventory, ledger path,
baselines, rulings. Missing/stale section ⇒ DEGRADED for this target — never invent a vendor
list, price, or baseline not actually given.

## Ledger of record
*The ONE cost/pricing doc — never a second; findings are diffs to it. See `manifest.json` →
`tracker_doc` if owned there.* __COST_LEDGER_DOC_PATH__

## Billing data sources
*Re-derive commands: billing-export table, app-level per-call cost-tracking module, secrets
census, deploy-config source of truth, CI-spend query.*
__BILLING_EXPORT_TABLE__ · __PER_CALL_COST_TRACKING_MODULE__ · __SECRETS_CENSUS_CMD__ ·
__DEPLOY_CONFIG_SOURCE_OF_TRUTH__ · __CI_SPEND_QUERY__

## Vendor inventory
*Every paid vendor: what for, $/month, MEASURED / OPERATOR-REPORTED / UNVERIFIED (first-audit
obligation) — never MEASURED without a real re-derive command.*

| vendor | what | $/month | basis |
|---|---|---|---|
| __VENDOR_ROW__ | | | |

## Baselines
*Opening investigation baseline: spend trend, any spike + root-cause attribution, in-flight leak
fixes (issue #s), cleanup pending operator approval.*
__COST_BASELINE_TREND__ · __COST_SPIKE_ATTRIBUTION__ · __LEAK_FIXES_IN_FLIGHT__

## Re-derive commands for the baselines above
__RE_DERIVE_COMMAND_BLOCK__

## Ledger carve-out
*Any OTHER doc resembling a duplicate cost ledger that is actually a different sanctioned thing
(e.g. customer-pricing/markup formula) — name it so it's never flagged a duplicate.*
__LEDGER_CARVE_OUT_DOC__

## Operator cost rulings of record
*Standing rulings bounding this agent's recommendations.* __RULING_COST_1__ — operator records own ruling.

## Units for unit economics
*Per-unit measures worth tracking (per output, per QA walkthrough, per deploy, per active
tenant) and the raw source each is defined against.* __UNIT_ECONOMICS_DEFINITIONS__

## Lane fence vs. any GTM/marketing department
*If ad-spend-effectiveness/pricing-strategy seats exist: this seat owns vendor/FinOps ACCOUNTING
only. Mirror this fence in sibling dossiers.* __COST_LANE_FENCE__
