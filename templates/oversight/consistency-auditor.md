# consistency-auditor.md — grounding dossier (__PRODUCT_NAME__)

FACTS ONLY + AUTHORITY MAP. Every claim cites file + heading/grep token. VERIFIED = opened/ran
directly this session. **Missing ⇒ `consistency-auditor` declares DEGRADED in its verdict line** —
may still inventory surfaces under UNVERIFIED observations, never names an authoritative side.

## 1. Help docs

*Where user-facing help content lives (docs site, in-app FAQ) vs. any INTERNAL-only docs dir that
must never be audited as customer-facing — the biggest false-positive class in this audit.*
Re-derive: `ls __HELP_DOCS_ROOT__`

Docs site: `__HELP_DOCS_SITE_PATH__` (build: `__HELP_DOCS_BUILD_CONFIG__`). In-app FAQ:
`__INAPP_HELP_PATH__`. Internal-only (never audit as customer-facing): `__INTERNAL_DOCS_PATH__`.

## 2. Marketing source of truth

*Which directory the live marketing site is actually BUILT from — verified by reading the build
script's own read paths, never assumed from a directory name — and any dead duplicate directory.*
Re-derive: `grep -n "readdir\|TEMPLATES" __MARKETING_BUILD_SCRIPT_PATH__`

`__MARKETING_SOURCE_DIR__` → `__MARKETING_BUILD_SCRIPT_PATH__` → `__MARKETING_BUILD_OUTPUT_DIR__`
→ `__MARKETING_HOSTING_MECHANISM__`. Dead duplicate dir: `__MARKETING_DEAD_DUPLICATE_DIR__` (or
"none found").

## 3. Pricing/tier truth

*The exact code location(s) authoritative over marketing copy for pricing/tier facts, with each
side's literal vocabulary, so a drift finding can quote both sides precisely.*
Re-derive: `grep -n "__PRICING_TIER_ANCHOR__" __PRICING_CODE_PATH__`

`__PRICING_CODE_PATH__` — tiers: `__TIER_NAMES__`, prices: `__TIER_PRICES__`. Payment-provider
lookup: `__PAYMENT_PROVIDER_CONFIG_PATH__`.

## 4. Known deliberate-divergence traps

*Same-named-but-different concepts this repo has on purpose — the auditor treats the divergence
itself as documented, and hunts for drift ON TOP of it, never as a defect on its own.*

`__KNOWN_TERMINOLOGY_TRAPS__` (or "none currently documented").

## 5. Domain-docs authority chain

*For overlapping canonical domain docs (a WHY doc, a naming doc, a HOW doc), each doc's
self-declared scope and how to treat an apparent conflict — a real overlap vs. a genuine gap.*

`__DOMAIN_DOCS_AUTHORITY_MAP__`.

## 6. Audit slices

*The audit-slice rotation this repo's sweep runs (pricing & tiers, feature claims, terminology,
help-vs-UI, etc.), each cross-checked against the authority map above.*

`__AUDIT_SLICE_LIST__`.

## 7. Living-docs obligation for this role

*Pointer to this repo's "docs travel with the change" rule — this auditor enforces it on every
other change AND files its own drift findings as issues, never just notes-and-leaves.*

`__LIVING_DOCS_RULE_DOC_ANCHOR__`.
