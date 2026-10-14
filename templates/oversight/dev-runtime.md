# dev-runtime — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Not a plan, not a tracker. Grounds the runtime's generic **dev-workflow** agents
(`implement`, `test-writer`, `test-runner`, `git-ops`, `ci-monitor`, `explore`, `browser-ops`,
`design-reviewer`) — all defined once in `~/.claude/agents/`, shared across every repo on this
machine. Most read the whole file; `browser-ops` reads ONLY "Local dev ports", `design-reviewer`
reads ONLY "Design system". **Missing file (or a missing named section) ⇒ that agent declares
itself DEGRADED and falls back to this repo's own `CLAUDE.md`/config — never invents a fact.**

Every command/path/count below should carry a `file:line` or shell-command provenance note and an
as-of date; where a canonical repo doc already states a fact in full, point to that doc's section
instead of copying it — copy only what no canonical doc states literally.

## Stack + infra

*Language(s)/framework(s), datastore, cloud provider + the ONE project/account name if there is
only one — `implement` needs this before writing a line; guessing wastes a dispatch.*
Re-derive: `grep -n "<stack anchor heading>" __PATH_TO_OPERATIONS_DOC__`

`__STACK_SUMMARY__` — `__CLOUD_PROJECT_OR_ACCOUNT__` is the only `__CLOUD_PROVIDER__` project
(state the constraint explicitly if a second one would be a mistake, e.g. "never create a second
Spanner-class datastore").

## Local dev ports

*Every port a local dev/test process binds, one row per service — `browser-ops` reads only this
section (origins/tenants/recipients live in the runtime live-testing allowlist instead).*
Re-derive: `sed -n '<port table lines>p' __PATH_TO_OPERATIONS_DOC__`

| Service | Port |
|---|---|
| __SERVICE_1__ | __PORT_1__ |
| __SERVICE_2__ | __PORT_2__ |

## Project layout

*Backend entry path, per-module test convention, frontend location(s), integration-test root —
a wrong assumed entry path (e.g. a `main.py` that doesn't exist) burns a dispatch on a 404.*
Re-derive: `ls -d __MODULES_ROOT__/*/  | wc -l`

- Backend entry: `__BACKEND_ENTRY_PATH__`.
- Modules: `__MODULES_ROOT__/<name>/` (each with its own `tests/`).
- Frontend(s): `__FRONTEND_PATHS__`.
- Integration tests: `__INTEGRATION_TESTS_ROOT__`.
- Config/docs: `__DOCS_ROOT__`.

## Test commands + gates

*Exact runnable test commands per layer, the canonical pre-PR/pre-push gate script(s), and the
real coverage-gate wording — the wrong invocation (a missing flag) gets a false green.*
Re-derive: `grep -n "<pre-PR gate heading>" __PATH_TO_ENGINEERING_STANDARDS__`

- Backend unit: `__BACKEND_UNIT_TEST_CMD__`
- Frontend: `__FRONTEND_TEST_CMD__`
- E2E: `__E2E_TEST_CMD__`
- Full pre-PR / pre-push gate: `__LOCAL_CI_SCRIPT__ __LOCAL_CI_FLAGS__`
- Coverage-gate posture: `__COVERAGE_GATE_POSTURE__` (state plainly whether the coverage floor is
  enforced on every PR or only when a specific job actually runs — never assume the stricter
  reading without checking this repo's own CI config).
- Flake registry: `__FLAKE_REGISTRY_PATH__` (the file/ledger tracking known-flaky tests, if one
  exists — `git-ops` reads this before treating a CI red as a real regression rather than a
  registered flake).
- Blocking vs advisory jobs: `__CI_BLOCKING_VS_ADVISORY_JOBS__` (which named CI jobs actually gate
  a merge vs. which report only — never assume every green checkmark is blocking).

## Test placement + markers + spec docs

*Where a new test file goes, the marker/naming convention, any vendor no-mock list, and the
priority-ordered spec docs `test-writer` reads first — the biggest source of misplaced/lock-in tests.*
Re-derive: `ls -d __INTEGRATION_TESTS_ROOT__/*/`

- Module-owned tests: `__MODULES_ROOT__/<name>/tests/`.
- Cross-module/integration subject dirs: `__INTEGRATION_SUBJECT_DIRS__`.
- Markers: `__TEST_MARKER_CONVENTION__`.
- Vendor no-mock list (real test keys required, missing key fails the test, never skips — except
  a stated skip-registry): `__VENDOR_NO_MOCK_LIST__`.

Spec docs, in priority order (highest overrides on conflict):
1. `__TESTING_STANDARD_DOC__` — canonical testing policy.
2. `__TEST_CORRECTNESS_STANDARD_DOC__` — tests assert intended behavior, never current/broken
   behavior.
3. `__ENGINEERING_STANDARDS_DOC__` — general engineering/domain rules.

## Test quality (digest)

*A load-bearing SUMMARY of the real testing standard (never the standard itself), any mechanical
test-quality scanner + its checks, and the falsifiability-gate command if one exists.*
Re-derive: `python3 __TEST_QUALITY_SCANNER_PATH__ --help`

**The lock-in test rule, in one paragraph:** a test asserts what the SPEC says the behavior should
be, never what the code currently outputs. An assertion written by running the code and copying its
output is a lock-in test — it passes trivially against a bug and defends that bug against the fix.

Mechanical scanner (if one exists): `__TEST_QUALITY_SCANNER_PATH__` — violation checks:
`__TEST_QUALITY_VIOLATION_CHECKS__`.

Falsifiability check (if one exists): `__FALSIFIABILITY_GATE_COMMAND__` — exit codes:
`__FALSIFIABILITY_EXIT_CODES__`.

## Lint / format / type / secret-scan commands

*The EXACT flags the real pre-commit/CI gate passes, not the bare tool invocation — a proven
gotcha class (a bare lint command silently auto-discovering a different config).*
Re-derive: `sed -n '<pre-commit lint lines>p' __PRECOMMIT_CONFIG_PATH__`

- Lint: `__LINT_COMMAND__`
- Format check: `__FORMAT_CHECK_COMMAND__`
- Type check: `__TYPE_CHECK_COMMAND__` (note here if it must run from inside a subdirectory rather
  than the repo root — a proven gotcha class when a nested package pins its own tool version)
- Secret scan: `__SECRET_SCAN_COMMAND__` (always pass the real baseline file flag — a bare
  invocation without it reports every already-reviewed false positive as new)

## Code standards (digest)

*A load-bearing SUMMARY of the canonical code standard's numbered rule areas + thresholds, plus
any delta-scanner reporting only violations a pending change introduces.*
Re-derive: `python3 __CODE_STANDARDS_SCANNER_PATH__ delta -- <changed files>`

Canonical doc: `__CODE_STANDARDS_DOC__`. Rule areas (numbered, with thresholds):
1. `__RULE_1_SUMMARY__`
2. `__RULE_2_SUMMARY__`
3. `__RULE_N_SUMMARY__`

Self-check before reporting done: `__CODE_STANDARDS_SCANNER_PATH__ delta -- <your changed files>`
(informational; fix what it prints before handing off — it senses a SUBSET of the rule areas, a
silent delta does not clear you on the rest).

## Datastore rules

*The one-sentence datastore constraint (e.g. "Firestore only") and where secrets/files live —
a wrong datastore choice is expensive to unwind.*

`__DATASTORE_RULE__`. Secrets: `__SECRETS_LOCATION__`. File storage: `__FILE_STORAGE_LOCATION__`.

## API routes

*The one-line contract-test requirement for any new/changed route — loops `test-writer` in
automatically whenever `implement` adds one.*

Every new or changed API route needs contract tests (methods, status codes, request/response
shapes, error cases) — flag a new route to the orchestrator so `test-writer` covers it in the same
change.

## Design system

*`design-reviewer`'s ENTIRE repo-local grounding: token table, component standard doc, mechanical
floors (ratchet script, lint-rule severities — only ERROR-level and the ratchet actually gate).
Its own definition greps for this exact heading and reads only to the next `## ` heading.*
Re-derive: `ls -la __TOKEN_TABLE_PATH__`

- **Token table — cite this, never a compat re-export:** `__TOKEN_TABLE_PATH__`.
- **Global token/component CSS** (if separate from the token table): `__TOKEN_CSS_PATH__`,
  `__COMPONENT_CSS_PATH__`.
- **Component standard:** `__UI_COMPONENT_STANDARD_DOC__`.
- **Compat re-export — NOT a citation target** (if one exists, name it so a finding never lands
  there): `__COMPAT_REEXPORT_PATH__`.
- **Mechanical floor 1 — ratchet script** (if one exists): `__INLINE_STYLE_RATCHET_SCRIPT__` — a
  per-file ratchet against a pre-existing backlog, never a hard zero-violations gate.
- **Mechanical floor 2 — lint plugin severities** (if one exists): `__LINT_CONFIG_PATH__` — name
  which specific rules sit at `error` (real gate) vs `warn` (advisory only, does not fail the
  commit) — never assume; state this repo's actual severities.

### Navigation + IA

*Route table, persistent-nav component, the landed default state after sign-in, and deliberate
typed-URL-only exclusions with rationale — `design-reviewer`'s `map`-mode journey baseline.*

- **Route table:** `__ROUTE_TABLE_PATH__`.
- **Persistent nav:** `__NAV_COMPONENT_PATH__`.
- **Landed default state after sign-in:** `__DEFAULT_LANDING_ROUTE__`.
- **Deliberate typed-URL-only exclusions** (report WITH rationale, never as fresh findings):
  `__TYPED_URL_ONLY_ROUTES__`.
- **Journey baseline of record** (if a target table exists elsewhere, e.g. in a QA dossier):
  `__JOURNEY_BASELINE_LOCATION__`.

## Branch model + GitHub/PR conventions

*The CANONICAL branch-naming convention (flag any conflicting doc rather than silently picking
one), PR template location, and issue-triage label/field split.*

- Branch naming: `__BRANCH_NAMING_CONVENTION__`.
- PR target branch: `__PR_TARGET_BRANCH__`; promotion path: `__PROMOTION_PATH__`.
- PR template: `__PR_TEMPLATE_PATH__`.
- Commit message format / issue triage / closing-comment template: see `__ENGINEERING_STANDARDS_DOC__`.
- Label taxonomy: one type label, at least one `area:` label, exactly one `difficulty:` label —
  never duplicate a project field (points/priority/status) as a label.
- Issue intake: sweeps roll up (one epic per audit, findings as checklist items), they do not fan
  out — a finding gets its own issue only if independently actionable.

## CI build-failure logs

*Where build-failure artifacts land, if this repo has such a directory — `ci-monitor` needs a
drop location, not a static index.*

`__CI_BUILD_FAILURE_LOG_DIR__`.

## Browser testing

*A pointer, not a restatement — origins/tenants/test recipients live in the runtime's
live-testing allowlist, never duplicated here.*

Origins, tenants, and test recipients: `~/.claude/live-testing/allowlist.json` (never duplicated
here). Local dev surfaces: see "Local dev ports" above.

## ⛔ Announce before you commit

*This repo's own copy of the runtime's shared-tree commit-coordination rule if its `CLAUDE.md`
states one — point at the runtime rule; add only repo-specific mitigations here.*

Before any `git commit` or staging sweep on the shared tree: announce to live peer sessions first,
per `~/.claude/CLAUDE.md` §2/§3 and this repo's own `CLAUDE.md`. `__REPO_SPECIFIC_COMMIT_NOTES__`
(e.g. any worktree exclusions, size-of-train guidance).

## ⛔ Opening the app for the OPERATOR

*The exact, repeatable recipe for handing the operator an ALREADY-AUTHENTICATED session per
environment — never a sign-in screen; a repeated, named failure mode otherwise.*

**The operator likely has no personal login for local or staging.** Any agent that opens an app
URL for the operator delivers an already-authenticated session landing on the target page.

- **LOCAL:** `__LOCAL_AUTH_RECIPE__` (account, and the exact steps/commands to mint a session).
- **STAGING:** `__STAGING_AUTH_RECIPE__` (account, and where its password lives — a secret
  manager, never hardcoded).
- **PROD:** `__PROD_AUTH_RECIPE__` — only on explicit operator instruction, per this repo's own
  WHERE-TO-TEST rule if one exists.

## How to re-derive

```bash
# Fill this with the actual commands used above, e.g.:
# grep -n "<stack anchor heading>" __PATH_TO_OPERATIONS_DOC__
# ls -d __MODULES_ROOT__/*/  | wc -l
# python3 __TEST_QUALITY_SCANNER_PATH__ --help
```
