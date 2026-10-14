# code-quality-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file for the runtime `code-quality-architect` agent. Every count carries its re-derive
command + as-of date. VERIFIED = read/run directly this pass. **Missing ⇒ DEGRADED; audits only
repo-discoverable state.**

## Scan + ledger (the sensor this agent interprets — never recomputes)

*The deterministic code-debt scanner, subcommands, ledger shape, verdict rules — without this the
agent has no sensor and must say so.* Re-derive: `python3 __CODE_DEBT_SCANNER_PATH__ report`

- **Scanner:** `__CODE_DEBT_SCANNER_PATH__` — subcommands: `__SCANNER_SUBCOMMANDS__`.
- **Ledger:** `__CODE_DEBT_LEDGER_PATH__` — provenance: `__LEDGER_RECORD_PROVENANCE__`. Verdicts:
  `__VERDICT_RULES__`.
- **Write-time signal** (pre-commit delta hook, if any — not this agent's to run):
  `__PRECOMMIT_DEBT_HOOK_NAME__`. Never trend across a scanner rule-set change.

## Rules source (rule diffs amend THIS, never a rival doc)

*The canonical standards doc these diffs amend, its digest location, adjacent-lane docs to cite.*

`__CODE_STANDARDS_DOC_PATH__` — digest at `__CODE_STANDARDS_DIGEST_LOCATION__` (a diff not
reflected in BOTH is dead text). Adjacent-lane standards: `__ADJACENT_STANDARDS_DOCS__`.

## Module inventory + intended boundaries

*Module root(s), layout convention, cross-module import rule, known scanner coverage gaps (never
propose a rule diff against a check that doesn't exist).*
Re-derive: `ls -d __MODULES_ROOT__/*/ | wc -l`

- `__MODULE_COUNT__` module dirs under `__MODULES_ROOT__` + `__OTHER_SCAN_ROOTS__`.
- Layout: `__MODULE_LAYOUT_CONVENTION__`. Import rule: `__CROSS_MODULE_IMPORT_RULE__`. Coverage
  gaps: `__SCANNER_COVERAGE_GAPS__`.

## Known-and-accepted debt (report WITH rationale, never as fresh findings)

*Largest STOCK per-module debt totals (delta-not-stock — never itemize fresh), named hotspots,
accepted lint exceptions.* Re-derive (LATEST record):
```bash
tail -1 __CODE_DEBT_LEDGER_PATH__ | python3 -c "import json,sys;d=json.loads(sys.stdin.read());[print(m['module'],m['total']) for m in sorted(d['modules'],key=lambda m:-m['total'])[:5]]"
```

- Largest totals: `__LARGEST_DEBT_MODULES__`. Named hotspots: `__NAMED_HOTSPOT_FILES__`. Accepted
  lint exceptions: `__ACCEPTED_LINT_EXCEPTIONS__`.

## Out of scope for this agent in this repo

*Hand-off map to sibling agents for adjacent lanes this agent never claims.*

`__OUT_OF_SCOPE_HANDOFF_MAP__` (e.g. "domain architecture → repo's own architect;
tests/observability → `test-architect`; security/money → `trust-architect`; design →
`design-reviewer`; issue filing → orchestrator via board-steward's rules").

## How to re-derive

```bash
python3 __CODE_DEBT_SCANNER_PATH__ report
tail -1 __CODE_DEBT_LEDGER_PATH__ | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['generated_at'], len(d['modules']))"
```
