# launch-director.md — grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Every count carries its re-derive command + as-of date. VERIFIED = opened/ran directly
this session. **Missing ⇒ `launch-director` declares DEGRADED in its first line, names the gap.**

## 1. The prime directive

*The ONE goal this app's work is ranked against, in the operator's own words, cited — every
ranking decision downstream depends on this sentence being exact, not paraphrased.*

**`__PRIME_DIRECTIVE_STATEMENT__`** — verbatim, cited: `__PRIME_DIRECTIVE_SOURCE__`.

Rule: `__PROMOTE_VS_FIX_CYCLE_RULE__` (e.g. "on a SAFE-TO-PROMOTE verdict with only non-blocking
findings, promote, then file the findings as issues — do not chain another fix-review cycle").

## 2. Where launch truth lives

*The ONE living launch-readiness/QA tracker doc (if any), its row-field schema, and how status
rolls up (computed vs. hand-edited — name exactly which fields a human touches vs. formulas).*
Re-derive: see `.claude/oversight/manifest.json` → `tracker_doc`.

Path: see `.claude/oversight/manifest.json` → `tracker_doc` (or null). Row fields:
`__TRACKER_ROW_SCHEMA__`. Rollup: `__TRACKER_ROLLUP_RULE__` (finish-line leaf value, e.g.
"verified: live on prod AND re-confirmed there").

**Leaf-status counts, as-of `__AS_OF_DATE__`** (re-derive, never trust a cached number):
```bash
__TRACKER_STATUS_COUNT_COMMAND__
```

## 3. Cost/pricing truth

*The ONE cost/pricing analysis doc this repo maintains, if any, and its section map — prevents
citing a stale or duplicate pricing doc.*

Path: `__PRICING_DOC_PATH__` (or null). Sections: `__PRICING_DOC_SECTIONS__`.

## 4. The GitHub board

*Same board facts as `board-steward.md` §1, deliberately repeated so this file self-grounds.*

See `.claude/oversight/manifest.json` → `github.project_owner`/`github.repo`/`github.project_number`.
`__BOARD_ITEM_COUNT__` items as-of `__AS_OF_DATE__`.

## 5. Open-issue totals

*The re-derivable open-issue count command — always with an explicit `--limit` above the expected
total, since the default page size can silently truncate.*

```bash
gh issue list --state open --limit 1000 --json number | python3 -c \
  "import json,sys; print(len(json.load(sys.stdin)))"
```

## 6. Weekly-report obligations

*Any output the operator expects beyond the base report shape — point to a schedule-status doc
rather than hardcoding schedule state (it goes stale the moment a job changes).*

Schedule status: `__SCHEDULE_STATUS_DOC__`. Spend-sanity source (if any):
`__SPEND_DASHBOARD_PATH__`.
