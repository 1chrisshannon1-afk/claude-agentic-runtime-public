# admin-portal-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file for the runtime `admin-portal-architect` agent. Every count carries its re-derive
command + as-of date. VERIFIED = read/run directly this pass. **Missing ⇒ DEGRADED; audits only
repo-discoverable state.**

## Admin route + page inventory

*Where the admin-facing backend routes and frontend pages live, and how to enumerate them.*
Re-derive: `grep -rn "__ADMIN_ROUTE_PATTERN__" __ADMIN_ROUTES_ROOT__ | wc -l`

- **Backend routes root:** `__ADMIN_ROUTES_ROOT__` — route pattern: `__ADMIN_ROUTE_PATTERN__`.
- **Frontend pages root:** `__ADMIN_FRONTEND_ROOT__`.

## DI-wiring conventions

*How this app wires a route/page to its real (vs. stub/local-fallback) implementation, and where
that wiring is configured per environment.*

- __ADMIN_DI_WIRING_CONVENTION__ · __ADMIN_ENV_WIRING_CONFIG_PATH__

## Composite index list

*The composite indexes admin queries depend on, and where they're declared for deployment.*

- __ADMIN_COMPOSITE_INDEX_DECLARATION_PATH__

## IAP / realm auth model

*How the admin realm is gated from the customer-facing realm — the proxy/middleware/decorator
every admin route must inherit, and the admin-vs-super_admin role boundary.*

- __ADMIN_AUTH_BOUNDARY_MECHANISM__ · __ADMIN_ROLE_LEVELS__

## Known-and-accepted gaps (report WITH rationale, never as fresh findings)

*Admin-surface gaps already recorded with an operator ruling — cite the ruling, never re-file.*

- __ADMIN_ACCEPTED_GAPS__

## Out of scope for this agent in this repo

*Hand-off map to sibling agents for adjacent lanes this agent never claims.*

`__ADMIN_OUT_OF_SCOPE_HANDOFF_MAP__` (e.g. "security correctness → `trust-architect`; product
ranking → `launch-director`; visual/UX → `design-reviewer`; live browser walks →
`product-qa`/`browser-ops`; commit-boundary correctness → `code-reviewer`; issue filing →
orchestrator via `board-steward`'s rules").

## How to re-derive

```bash
grep -rn "__ADMIN_ROUTE_PATTERN__" __ADMIN_ROUTES_ROOT__ | wc -l
ls -d __ADMIN_FRONTEND_ROOT__ | wc -l
```
