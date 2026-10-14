# Template placeholder tokens

Every `__TOKEN__` used across `templates/**` appears in this table
(`bundle_parity` rule (b) requires it — a template that introduces a new placeholder without
adding it here is a defect in the same change that adds the placeholder). Reuse a token name
across templates for the same concept rather than minting a near-duplicate.

| token | meaning | example |
|---|---|---|
| `__PRODUCT_NAME__` | the product's display name | `ExampleApp` |
| `__STACK_SUMMARY__` | one-line language/framework/datastore/cloud summary | `Flask/Python backend, React/Vite TS frontend, Postgres, AWS` |
| `__CLOUD_PROVIDER__` | the cloud provider name | `GCP` |
| `__CLOUD_PROJECT_OR_ACCOUNT__` | the one project/account name, if there's only one | `exampleapp-prod` |
| `__PATH_TO_OPERATIONS_DOC__` | path to this repo's ops/infra reference doc | `docs/OPERATIONS.md` |
| `__SERVICE_1__` / `__SERVICE_2__` | a local dev service name | `Backend (local)` |
| `__PORT_1__` / `__PORT_2__` | that service's local port | `8080` |
| `__MODULES_ROOT__` | the root directory holding per-module code | `src/components/` |
| `__BACKEND_ENTRY_PATH__` | the backend's real entry path (package or file) | `backend/main/` |
| `__FRONTEND_PATHS__` | one or more frontend directory paths | `web/frontend/` |
| `__INTEGRATION_TESTS_ROOT__` | root dir for cross-module/integration tests | `integration_tests/` |
| `__DOCS_ROOT__` | root dir for repo/config docs | `docs/` |
| `__BACKEND_UNIT_TEST_CMD__` | exact backend unit test invocation | `pytest src/components/<name>/tests/ -v` |
| `__FRONTEND_TEST_CMD__` | exact frontend test invocation | `npx vitest run` |
| `__E2E_TEST_CMD__` | exact E2E test invocation | `npx playwright test` |
| `__LOCAL_CI_SCRIPT__` | path to the canonical pre-PR/pre-push gate script | `scripts/local_ci.sh` |
| `__LOCAL_CI_FLAGS__` | the flags that select the real gate mode | `--mode=full` |
| `__COVERAGE_GATE_POSTURE__` | whether the coverage floor is enforced every PR or only when a job runs | `enforced-when-run, not every PR` |
| `__FLAKE_REGISTRY_PATH__` | the file/ledger tracking known-flaky tests, if one exists | `docs/flaky_tests.md` |
| `__CI_BLOCKING_VS_ADVISORY_JOBS__` | which named CI jobs actually gate a merge vs. report only | `unit-tests blocking; lint-advisory report-only` |
| `__PATH_TO_ENGINEERING_STANDARDS__` | path to the general engineering/domain standards doc | `docs/ENGINEERING_STANDARDS.md` |
| `__INTEGRATION_SUBJECT_DIRS__` | the list of subject subdirectories under the integration-tests root | `API_CONTRACTS, BILLING, SECURITY` |
| `__TEST_MARKER_CONVENTION__` | how unit vs. integration tests are marked | `pytestmark = pytest.mark.unit` |
| `__VENDOR_NO_MOCK_LIST__` | vendors that must never be mocked in CI | `Stripe, email send, Secret Manager` |
| `__TESTING_STANDARD_DOC__` | canonical testing-policy doc path | `docs/ENTERPRISE_TESTING_STANDARD.md` |
| `__TEST_CORRECTNESS_STANDARD_DOC__` | doc requiring tests assert intended, not current, behavior | `docs/TEST_CORRECTNESS_STANDARD.md` |
| `__ENGINEERING_STANDARDS_DOC__` | same as `__PATH_TO_ENGINEERING_STANDARDS__` (kept for section-local naming) | `docs/ENGINEERING_STANDARDS.md` |
| `__TEST_QUALITY_SCANNER_PATH__` | path to a deterministic test-quality scanner, if one exists | `tools/test_quality/scan.py` |
| `__TEST_QUALITY_VIOLATION_CHECKS__` | the scanner's named violation checks | `no_assert_test, vacuous_assert` |
| `__FALSIFIABILITY_GATE_COMMAND__` | command that proves a fix's test actually falsifies | `scripts/verify_fix.py --test ... --paths ...` |
| `__FALSIFIABILITY_EXIT_CODES__` | that command's exit-code vocabulary | `0 PROVEN, 1 PARTIAL, 2 FALSE_ALLCLEAR` |
| `__PRECOMMIT_CONFIG_PATH__` | path to the pre-commit config | `.pre-commit-config.yaml` |
| `__LINT_COMMAND__` | the exact lint command the real gate runs | `ruff check --config=ruff.toml .` |
| `__FORMAT_CHECK_COMMAND__` | the exact format-check command the real gate runs | `ruff format --config=ruff.toml --check .` |
| `__TYPE_CHECK_COMMAND__` | the exact type-check command, noting any required cwd | `npx tsc -b (run from frontend/)` |
| `__SECRET_SCAN_COMMAND__` | the exact secret-scan command with its baseline flag | `detect-secrets scan --baseline .secrets.baseline` |
| `__CODE_STANDARDS_DOC__` | this repo's canonical code standard doc | `docs/CODE_RESILIENCE_STANDARD.md` |
| `__RULE_1_SUMMARY__` / `__RULE_2_SUMMARY__` / `__RULE_N_SUMMARY__` | one numbered code-standard rule area with its threshold | `No silent failures — every except logs or re-raises` |
| `__CODE_STANDARDS_SCANNER_PATH__` | path to a deterministic code-debt delta scanner, if one exists | `tools/code_debt/scan.py` |
| `__DATASTORE_RULE__` | the one-sentence datastore constraint | `Firestore only; never create a second datastore kind` |
| `__SECRETS_LOCATION__` | where secrets actually live | `GCP Secret Manager` |
| `__FILE_STORAGE_LOCATION__` | where uploaded/generated files live | `GCS bucket exampleapp-files` |
| `__TOKEN_TABLE_PATH__` | the canonical design-token table file | `web/theme/tokens.ts` |
| `__TOKEN_CSS_PATH__` / `__COMPONENT_CSS_PATH__` | global token/component CSS files, if separate | `web/design/tokens.css` |
| `__UI_COMPONENT_STANDARD_DOC__` | the component-standard doc | `docs/UI_COMPONENT_STANDARD.md` |
| `__COMPAT_REEXPORT_PATH__` | a compat re-export file that must never be cited directly | `frontend/src/designTokens.ts` |
| `__INLINE_STYLE_RATCHET_SCRIPT__` | a per-file inline-styling ratchet script, if one exists | `scripts/check_inline_styling.py` |
| `__LINT_CONFIG_PATH__` | the lint config naming rule severities | `eslint.config.mjs` |
| `__ROUTE_TABLE_PATH__` | where the frontend route table is defined | `web/src/App.tsx` |
| `__NAV_COMPONENT_PATH__` | the persistent-nav component | `web/src/components/AppShell.tsx` |
| `__DEFAULT_LANDING_ROUTE__` | the route a user lands on after sign-in | `/home` |
| `__TYPED_URL_ONLY_ROUTES__` | routes deliberately unreachable by nav, with rationale | `/internal-tools — staff only, typed URL by design` |
| `__JOURNEY_BASELINE_LOCATION__` | where a per-destination click-depth target table lives, if one exists | `.claude/oversight/product-qa.md`'s journey-map table |
| `__BRANCH_NAMING_CONVENTION__` | the canonical branch-naming pattern | `issues/<number>-<short>` |
| `__PR_TARGET_BRANCH__` / `__PROMOTION_PATH__` | PR target branch and how it promotes further | `staging; promoted to main via a Promote workflow` |
| `__PR_TEMPLATE_PATH__` | the PR template file | `.github/PULL_REQUEST_TEMPLATE.md` |
| `__CI_BUILD_FAILURE_LOG_DIR__` | where CI build-failure artifacts land | `ci/build-failures/` |
| `__REPO_SPECIFIC_COMMIT_NOTES__` | any repo-specific commit-train mitigation beyond the runtime default | `frontend work stays out of worktrees (no node_modules copy)` |
| `__LOCAL_AUTH_RECIPE__` / `__STAGING_AUTH_RECIPE__` / `__PROD_AUTH_RECIPE__` | exact steps to hand the operator an authenticated session per environment | `mint a magic-link token via the local auth store` |
| `__GH_OWNER__` | the GitHub org/user that owns the repo | `exampleorg` |
| `__PROJECT_NUMBER__` / `__PROJECT_NAME__` | the GitHub Projects board number and display name | `1`, `ExampleApp Board` |
| `__ITEM_COUNT__` / `__AS_OF_DATE__` | a live count and the date it was measured | `312`, `2026-09-09` |
| `__STATUS_OPTIONS__` / `__PRIORITY_OPTIONS__` | the board's real `Status`/`Priority` field option values | `Backlog, Ready, In progress, Done` |
| `__TYPE_LABELS__` / `__AREA_LABELS__` / `__DIFFICULTY_LABELS__` | the repo's real label sets by convention | `bug, enhancement, chore` |
| `__PRIORITY_TAXONOMY__` | which of a priority label or field is truth | `Priority field is truth; labels retired` |
| `__LEGACY_LABELS__` / `__UNCLASSIFIED_LABELS__` / `__LABEL_COLLISIONS__` | labels being retired, unclassified, or colliding with a field | `bare P1/P2/P3 labels, retiring` |
| `__SWEEP_MUTATION_CAP__` | max non-destructive mutations per steward sweep | `40` |
| `__DISPOSITION_AGE_THRESHOLD__` / `__ICEBOX_AGE_THRESHOLD__` | staleness thresholds for disposition/icebox candidates | `no activity >90 days` |
| `__GROOMING_PIPELINE_PATH__` / `__DISPOSITION_VOCABULARY__` | an existing scripted grooming pipeline and its disposition vocabulary | `close_duplicate, close_fixed, keep_needs_human` |
| `__SCRATCH_TITLES_FILE__` | a scratch file path for a dedup-clustering command | `/tmp/titles.txt` |
| `__SUBISSUE_USAGE_FACT__` / `__CROSSREF_CONVENTION__` | whether native sub-issues are used, and the cross-reference convention | `sub-issues unused; title-prefix convention instead` |
| `__PRIME_DIRECTIVE_STATEMENT__` / `__PRIME_DIRECTIVE_SOURCE__` | the one goal all product work is ranked against, and its citation | `"get to the first paying customer"` |
| `__PROMOTE_VS_FIX_CYCLE_RULE__` | the rule for when to promote vs. chain another review cycle | `promote on SAFE-TO-PROMOTE, file non-blockers as issues` |
| `__TRACKER_ROW_SCHEMA__` / `__TRACKER_ROLLUP_RULE__` | the launch tracker's row-field schema and rollup formula | `category/subcategory/status; worst-of-children rollup` |
| `__TRACKER_STATUS_COUNT_COMMAND__` | the re-derivable command for current leaf-status counts | `grep -c '"s": "verified"' tracker.html` |
| `__PRICING_DOC_PATH__` / `__PRICING_DOC_SECTIONS__` | the one cost/pricing analysis doc and its section list | `docs/opex_and_pricing.html` |
| `__BOARD_ITEM_COUNT__` | the board's live item count | `312` |
| `__SCHEDULE_STATUS_DOC__` | doc holding live scheduled-job status (never hardcoded here) | `knowledge/oversight_install.md` |
| `__SPEND_DASHBOARD_PATH__` | path to a spend/usage dashboard tool, if any | `usage-dashboard/data/dashboard.db` |
| `__HELP_DOCS_ROOT__` / `__HELP_DOCS_SITE_PATH__` / `__HELP_DOCS_BUILD_CONFIG__` | where user-facing help docs live and build from | `docs-site/, docusaurus.config.ts` |
| `__INAPP_HELP_PATH__` | in-app FAQ/help content file | `web/src/content/faq.json` |
| `__INTERNAL_DOCS_PATH__` | internal-only docs never to audit as customer-facing | `docs-site/internal-docs/` |
| `__MARKETING_SOURCE_DIR__` / `__MARKETING_BUILD_SCRIPT_PATH__` / `__MARKETING_BUILD_OUTPUT_DIR__` / `__MARKETING_HOSTING_MECHANISM__` | the marketing site's real build pipeline | `website/templates/, website/build.mjs, website/dist/, Firebase Hosting` |
| `__MARKETING_DEAD_DUPLICATE_DIR__` | a directory that looks live but the build never reads | `website/landing_pages/ (confirmed dead)` |
| `__PRICING_CODE_PATH__` / `__TIER_NAMES__` / `__TIER_PRICES__` | the code-level pricing/tier source of truth | `licensing/usage_limits.py; economy/standard/premium; $99/$249/$499` |
| `__PAYMENT_PROVIDER_CONFIG_PATH__` | the payment-provider price-id lookup | `stripe_module/config.py` |
| `__PRICING_TIER_ANCHOR__` | a grep anchor for the pricing-tier vocabulary | `class JobTier` |
| `__KNOWN_TERMINOLOGY_TRAPS__` | documented same-word-different-concept pairs | `"premium" is both a billing tier and a retired finish-grade alias` |
| `__DOMAIN_DOCS_AUTHORITY_MAP__` | which doc is authoritative for which overlapping scope | `rulings doc = WHY; CANON doc = naming; architecture doc = HOW` |
| `__AUDIT_SLICE_LIST__` | the rotation of consistency-audit slices | `pricing & tiers, feature claims, terminology` |
| `__LIVING_DOCS_RULE_DOC_ANCHOR__` | citation for this repo's docs-travel-with-change rule | `ENGINEERING_STANDARDS.md §10` |
| `__CODE_DEBT_SCANNER_PATH__` / `__CODE_DEBT_LEDGER_PATH__` | the code-quality-architect's sensor and its ledger | `tools/code_debt/scan.py`, `.../history.jsonl` |
| `__SCANNER_SUBCOMMANDS__` | the scanner's subcommand list | `snapshot, report, delta` |
| `__LEDGER_RECORD_PROVENANCE__` | what each ledger record carries for provenance | `head_sha + dirty flag` |
| `__VERDICT_RULES__` | the scanner's verdict classification rules | `off-track if total +>10% or any critical metric up` |
| `__PRECOMMIT_DEBT_HOOK_NAME__` | the pre-commit hook name that reports deltas at commit time | `code-debt-delta-report` |
| `__CODE_STANDARDS_DOC_PATH__` / `__CODE_STANDARDS_DIGEST_LOCATION__` | the standards doc code-quality-architect amends, and its digest location | `docs/CODE_RESILIENCE_STANDARD.md`, `dev-runtime.md` digest |
| `__ADJACENT_STANDARDS_DOCS__` | sibling standards docs in adjacent lanes | `ENTERPRISE_TESTING_STANDARD.md (test-architect's lane)` |
| `__MODULE_COUNT__` / `__OTHER_SCAN_ROOTS__` | the module count and any other scan roots | `24`, `common/, web/shared/` |
| `__MODULE_LAYOUT_CONVENTION__` | the canonical per-module directory layout | `api/ domain/ infrastructure/ tests/` |
| `__CROSS_MODULE_IMPORT_RULE__` | the cross-module import boundary rule | `import only via modules.<name> public API` |
| `__SCANNER_COVERAGE_GAPS__` | surfaces the scanner deliberately does not cover | `TypeScript is outside the scanner's surface` |
| `__LARGEST_DEBT_MODULES__` / `__NAMED_HOTSPOT_FILES__` / `__ACCEPTED_LINT_EXCEPTIONS__` | stock debt facts reported with rationale, never as fresh findings | `module X: 611 total; adapter.py 8,454 lines (open recommendation)` |
| `__OUT_OF_SCOPE_HANDOFF_MAP__` | the explicit hand-off to sibling agents' lanes | `security/tenancy/money → trust-architect` |
| `__ADMIN_ROUTES_ROOT__` / `__ADMIN_ROUTE_PATTERN__` | admin-portal-architect's backend route census root and grep pattern | `src/admin/routes/`, `@admin_bp.route` |
| `__ADMIN_FRONTEND_ROOT__` | admin-portal-architect's frontend page census root | `web/admin/pages/` |
| `__ADMIN_DI_WIRING_CONVENTION__` / `__ADMIN_ENV_WIRING_CONFIG_PATH__` | how a route/page is wired to its real (vs. stub/local) implementation, and where that's configured per environment | `dependency_injector Container`, `config/di_bindings.py` |
| `__ADMIN_COMPOSITE_INDEX_DECLARATION_PATH__` | where composite indexes admin queries depend on are declared for deployment | `firestore.indexes.json` |
| `__ADMIN_AUTH_BOUNDARY_MECHANISM__` / `__ADMIN_ROLE_LEVELS__` | the admin-realm auth boundary every admin route must inherit, and its role levels | `IAP + require_admin decorator`, `admin, super_admin` |
| `__ADMIN_ACCEPTED_GAPS__` | admin-surface gaps already recorded with an operator ruling | `no per-tenant AI spend view yet — #5301, deferred to post-beta` |
| `__ADMIN_OUT_OF_SCOPE_HANDOFF_MAP__` | the explicit hand-off to sibling agents' lanes for admin-surface findings | `security correctness → trust-architect; ranking → launch-director` |

## GTM / marketing seats

| token | meaning | example |
|---|---|---|
| `__PRODUCT_ONE_LINER__` | one-sentence what-the-product-is, shared across every GTM seat's Goal section | `AI-generated construction estimates from photos` |
| `__APP_FRONTEND_DIR__` | the product app's own frontend directory (as distinct from a separate marketing site) | `src/frontend/` |
| `__APP_FRONTEND_STACK__` | the app frontend's framework, for a visual/funnel seat's stack line | `React/Vite TS` |
| `__APP_PUBLIC_HOST__` | the public hostname the app frontend serves from | `app.exampleapp.com` |
| `__APP_PUBLIC_ROUTE_LIST__` | the app's own public (pre-auth) route list, if any | `/pricing, /signup` |
| `__MARKETING_SITE_DIR__` | the marketing site's own directory, if separate from the app frontend | `website/` |
| `__MARKETING_SITE_SURFACE_LIST__` | the marketing site's own public pages/surfaces | `/, /pricing, /blog` |
| `__HOSTING_REDIRECT_RULE_SOURCE__` | where the routing/redirect rule between the marketing site and app lives | `firebase.json hosting.rewrites` |
| `__RULING_LOCAL_SEO__` | whether local SEO is in-scope or ruled out, by whom/when | `ruled out — no local/regional service area, 2026-09-05` |
| `__SEO_PIPELINE_FILE_1__` / `__SEO_PIPELINE_FILE_2__` | this repo's build-time SEO generation pipeline files (page manifest → meta/sitemap), if one exists | `website/build/seo_manifest.json`, `website/build.mjs` |
| `__SEO_PIPELINE_COVERAGE_NOTE__` | what that pipeline covers vs. leaves to hand-editing | `covers all marketing pages; app public routes are hand-maintained` |
| `__ROBOTS_SITEMAP_LOCATION_1__` | the robots.txt/sitemap file location | `website/public/robots.txt` |
| `__ROBOTS_SITEMAP_STATUS_1__` | whether that file is actually served, verified live | `verified served at /robots.txt, 200` |
| `__JSON_LD_COVERAGE_STATUS__` | this app's JSON-LD/structured-data coverage state | `no JSON-LD on any page yet` |
| `__PER_ROUTE_HEAD_MECHANISM__` | whether this app can vary title/meta per public route | `static head only — no per-route injection or SSR` |
| `__CSP_PIN_LOCATION__` | where inline-script CSP hash pins live, if this app hash-pins under a CSP directive | `no CSP directive configured` |
| `__PRICING_DOC__` | the one canonical pricing/positioning doc every GTM seat defers to | `docs/domain/opex_and_pricing.html` |
| `__PRICING_COPY_LOCATION_1__` / `__PRICING_COPY_LOCATION_2__` | places pricing/tier copy is duplicated outside the canonical doc | `website/pricing.html`, `app onboarding modal` |
| `__AB_VARIANT_SET_PATH__` | path to a live A/B variant definition, if one exists | `website/experiments/hero_v2.json` |
| `__AB_VARIANT_RESULTS_STATUS__` | whether that variant has measured results yet | `no results doc yet — treat as hypothesis` |
| `__AB_VARIANT_RESULTS_DOC__` | the results doc for that variant, or none | `none` |
| `__ANALYTICS_TAG_CONTAINER__` | the tag-manager/analytics container in use, if any | `GTM-XXXXXXX` |
| `__ANALYTICS_TAG_CONTAINER_STATUS__` | whether that container is actually wired and firing | `installed, unverified live-firing` |
| `__ANALYTICS_ADDITIONAL_SURFACES__` | other analytics/pixel surfaces beyond the main tag container | `Meta Pixel` |
| `__ANALYTICS_ADDITIONAL_SURFACES_STATUS__` | that surface's wired/unset status | `unset` |
| `__KNOWN_FUNNEL_DEFECT_1__` | a named, already-known funnel defect | `signup form drops UTM params` |
| `__KNOWN_FUNNEL_DEFECT_1_ISSUE__` | the tracked issue number for that defect | `#4900` |
| `__FIRST_ASSIGNMENT__` | this seat's concrete first task, shared closing section across every GTM specialist dossier | `audit the /pricing page against the canonical pricing doc` |
| `__BRAND_ASSET_DIR__` | the directory holding brand assets (logos, photography) | `website/assets/brand/` |
| `__BRAND_ASSET_INVENTORY__` | a one-line inventory of what's actually in that directory | `logo (3 variants), no photography library` |
| `__MARKETING_IMAGE_DIR__` | the marketing imagery directory | `website/assets/images/` |
| `__IMAGE_ASSET_BRIEF_DOC__` | a generated-image brief doc, if one exists | `none` |
| `__BRAND_GUIDELINE_DOC_STATUS__` | whether a brand-guideline doc exists, and its path | `no brand-guideline doc exists yet` |
| `__DESIGN_TOKENS_FILE__` | the app's own design-token file | `shared_frontend/theme/tokens.ts` |
| `__DESIGN_COMPONENTS_FILE__` | the app's shared component library file, alongside the tokens file | `shared_frontend/components/index.ts` |
| `__MARKETING_SITE_CSS_FILE__` | the marketing site's own CSS file, if separate from the app's | `website/styles/main.css` |
| `__DESIGN_SYSTEM_RECONCILIATION_NOTE__` | whether app and marketing-site styling are reconciled under one token set | `deliberately separate — marketing site is static HTML` |
| `__RULING_DESIGN_TOOLING__` | an operator ruling on which design tool/workflow this repo uses | `Figma is source of truth for marketing comps` |
| `__POSITIONING_DOC__` | the canonical positioning/never-claim-list doc | `docs/domain/positioning.md` |
| `__EMAIL_SEQUENCE_DIR__` | directory holding email/lifecycle sequence copy | `docs/domain/gtm_missions/email_sequences/` |
| `__EMAIL_SEQUENCE_1__` / `__EMAIL_SEQUENCE_2__` | named existing email sequences in that directory | `onboarding_day1.md`, `trial_ending.md` |
| `__EMAIL_SEQUENCE_STALENESS_NOTE__` | whether an existing sequence's premise may be stale vs. the current pricing model | `authored under the free-trial model, now retired — needs a rewrite` |
| `__PRICING_MIRROR_DOC_1__` / `__PRICING_MIRROR_DOC_2__` | docs that mirror (not author) pricing/positioning content | `website/pricing.html`, `README.md pricing table` |
| `__VIDEO_PIPELINE_DIR__` | this repo's video-production pipeline directory, if any | `tools/demo_video/` |
| `__VIDEO_LESSONS_DOC__` / `__VIDEO_RUNBOOK_DOC__` / `__VIDEO_SPEC_DOC__` | that pipeline's lessons/runbook/spec docs | `RUNBOOK.md`, `SPEC.md`, `LESSONS.md` |
| `__VIDEO_HOST_PERSONA__` | the talking-avatar host persona used in video, if any | `Dale (AI host)` |
| `__VIDEO_AVATAR_VENDOR_PIPELINE__` | the avatar vendor/pipeline mechanism | `<avatar-vendor>` |
| `__VIDEO_NARRATION_VOICE__` | the narration voice used | `ElevenLabs voice id abc123` |
| `__VIDEO_NEVER_CLAIM_MECHANISM__` | the mechanism (if any) enforcing a never-claim/FTC fence on scripts | `spelled-out-number endorsement fence in scene JSON schema` |
| `__ICP_SUMMARY__` | the target customer archetype for paid acquisition | `owner-operator remodeling GCs, 1-10 crews` |
| `__RULING_PAID_EXECUTION_LANE__` | any separate execution-capable lane for a specific ad channel | `none — paid-acquisition-strategist stays findings-only` |
| `__AD_ACCOUNT_AUDIT_REDERIVE_COMMAND__` | the command to re-derive the ad-account audit history | `none — no ad account exists yet` |
| `__AD_ACCOUNT_AUDIT_HEADLINE__` | the one-line headline of the last ad-account audit | `no ad account exists yet` |
| `__AD_ACCOUNT_AUDIT_SOURCE__` | the source of that audit (live pull vs. carried) | `n/a` |
| `__AD_ACCOUNT_AUDIT_CONFIDENCE_NOTE__` | whether that audit is independently re-verified or pending re-verification | `n/a` |
| `__GOOGLE_ADS_PLAYBOOK_DIR__` / `__META_ADS_PLAYBOOK_DIR__` | playbook directories per ad channel, if any | `none yet` |
| `__TAG_CONTAINER__` / `__TAG_CONTAINER_STATUS__` | the conversion-tracking tag container and its wired/unset status | `GTM-XXXXXXX`, `unset` |
| `__GOOGLE_ADS_CONVERSION_STATUS__` / `__META_PIXEL_STATUS__` | each channel's conversion-tracking wiring status | `not configured — no Google Ads account exists` |
| `__INSTRUMENTATION_AS_OF_DATE__` | the date the instrumentation map above was last verified | `2026-09-09` |
| `__INSTRUMENTATION_KNOWN_GAP__` | a known instrumentation gap | `no conversion pixel installed anywhere` |
| `__INSTRUMENTATION_GAP_ISSUE__` | the tracked issue for that gap | `UNTRACKED` |
| `__MARKETING_LEGAL_CONSTRAINT_POINTER__` | a jurisdiction/legal marketing constraint | `US-only marketing claims, #4901` |
| `__PRICING_RULING_STATUS__` | whether pricing was ruled formally | `ruled 2026-09-04, LOCKED` |
| `__RULING_PRICING_REOPEN_RULE__` | the verbatim reopen rule from the pricing doc | `"reopen only on measured COGS drift, real churn data, a competitor repricing, or an operator ruling"` |
| `__PRICING_REOPEN_CLASS_LIST__` | the enumerated allowed reopen classes | `measured COGS, churn data, competitor reprice, operator ruling` |
| `__COGS_MEASUREMENT_STATUS__` | current status of measured-COGS-vs-calculated-basis | `not yet measured — tracked as a gap` |
| `__CONVERSION_CHURN_DATA_STATUS__` | current status of real post-launch conversion/churn data | `pre-launch — no data exists yet` |
| `__COMPETITOR_PRICE_ANCHOR__` | the closest architectural-twin competitor price point on file | `$149/mo (closest twin)` |
| `__COST_LEDGER_DOC__` | the one company-cost ledger doc, cited for CAC/LTV inputs | `opex_and_pricing.html` |
| `__COST_BASIS_CAVEAT__` | a caveat on a cost number's basis | `treat $X as a placeholder pending measurement` |
| `__CONV_ID_COLLISION_NOTE__` | any other short-id-shaped evaluator in this repo that could be confused with the GTM exit-contract ids | `none found` |
| `__RULING_OPERATOR_TAG_CALIBRATION__` | which clarify-phase questions are genuinely operator-only vs. department-internal | `spend/vendor/legal/taste = operator; mechanism calls = director` |
| `__PRIMARY_MARKET__` | the primary industry/market this product sells into | `US residential remodeling contractors` |
| `__PRODUCT_MATURITY_STATE__` | the product's current maturity stage | `pre-launch, no paying customers yet` |
| `__PRODUCT_STACK_SUMMARY__` | a brief backend/frontend/datastore/AI-vendor/billing summary for sanity-checking competitor claims | `Flask/Python, Firestore, Claude/Vertex AI, Stripe` |
| `__POSITIONING_BET_SUMMARY__` | the specific architectural/GTM bet differentiating this product | `photo-first estimating, no site visit required` |
| `__COMPETITOR_LIST__` | named competitors | `Handoff, Buildxact` |
| `__COMPETITOR_MECHANISM_NOTE__` | how a named competitor actually works, not its marketing claim | `Handoff: manual takeoff, no photo-AI measurement` |
| `__POSITIONING_TRUTH_SUMMARY__` | an honest comparison of this product against the competitor roster | `no competitor measures from photos; this is a real differentiator` |
| `__BASELINE_1_DATE__` | the as-of date of the first competitive baseline sweep | `2026-08-27` |
| `__BASELINE_1_REDERIVE_COMMAND__` | how to re-derive that baseline | `re-crawl each competitor's public pricing/demo pages` |
| `__BASELINE_1_SUMMARY__` | that baseline's dated findings | `see project_competitor_mechanism_teardown_2026_08_27` |
| `__WATCH_PATTERN__` | a recurring pattern worth a standing watch across sweeps | `competitors converging on AI-generated estimate copy, none on measurement` |
| `__LATEST_BRIEF_PATH__` | path to the most recent dated market-analyst brief | `.claude/oversight/market-analyst/briefs/2026-08-27.md` |

## Oversight seats (large set)

| token | meaning | example |
|---|---|---|
| `__CLOUD_PROJECT_ID__` | sentinel's GCP project id | `exampleapp-prod` |
| `__CLOUD_REGION__` | sentinel's deploy region(s) | `us-central1` |
| `__LIVE_SERVICES_LIST__` | the live per-environment Cloud Run service names, from an actual list command | `exampleapp-backend-staging, exampleapp-backend-prod` |
| `__DEPLOY_DRIFT_COMMAND__` | the working command to fetch the newest deployed revision name | `gcloud run revisions list --service=... --limit=1` |
| `__DEPLOY_INTEGRITY_CHECK__` | a deeper deploy-verification script/procedure, if one exists | `tools/verify_deploy.py` |
| `__LOG_READ_COMMAND__` | the working error-level log read command | `gcloud logging read "severity>=ERROR" --limit=50` |
| `__ERROR_RATE_BASELINE_OWNER__` | which job/heartbeat field owns the durable error-rate baseline | `daily oversight heartbeat, error_rate_7d field` |
| `__UPTIME_MONITOR_SERVICE__` | the external uptime-monitoring service in use, if any | `none configured` |
| `__HEALTH_ENDPOINT_STAGING__` / `__HEALTH_ENDPOINT_PRODUCTION__` | the live health-check URLs per environment | `https://staging.exampleapp.com/health` |
| `__INGRESS_OR_ACCESS_POSTURE__` | why a direct service URL may legitimately 404/403 | `internal-only ingress; only the load balancer front door is public` |
| `__FINDINGS_QUEUE_DESIGN__` | sentinel's own findings-queue design, if it keeps one | `no queue yet — findings filed directly as issues` |
| `__AGENT_SPEND_DASHBOARD_CMD__` | the command to summarize local agent spend | `python3 ~/.claude/hooks/agent_budget.py status` |
| `__MODEL_PIN_DRIFT_CMD__` | the report-only model-pin-parity check command | `python3 ~/.claude/hooks/model_pin_parity.py` |
| `__CANONICAL_COST_DOC__` | the one cost/pricing analysis doc for this product | `opex_and_pricing.html` |
| `__TRACKER_RESTING_STATES_CMD__` | the report-only script enforcing "no silent resting states" on the tracker | `tools/check_resting_states.py` |
| `__AUTH_ACTIVE_ACCOUNT__` | the gcloud account that must be ACTIVE for this repo's cloud calls | `deploy-bot@exampleapp-prod.iam.gserviceaccount.com` |
| `__AUTH_WRONG_IDENTITY_TRAPS__` | other listed gcloud accounts belonging to a different product, never to be used here | `deploy-bot@otherapp-prod.iam.gserviceaccount.com` |
| `__COST_LEDGER_DOC_PATH__` | cost-strategist's one ledger-of-record path | `opex_and_pricing.html` |
| `__BILLING_EXPORT_TABLE__` | the BigQuery billing-export table used for spend queries | `billing_export.gcp_billing_export_v1_XXXXXX` |
| `__PER_CALL_COST_TRACKING_MODULE__` | the app-level module tracking per-call AI cost | `shared/ai/cost_tracker.py` |
| `__SECRETS_CENSUS_CMD__` | the command to enumerate live secrets | `gcloud secrets list --project=...` |
| `__DEPLOY_CONFIG_SOURCE_OF_TRUTH__` | the authoritative deploy-config location | `_XAC_Base/ci/gcp_cicd/ cloudbuild DEPLOY_VARS` |
| `__CI_SPEND_QUERY__` | the query/command for CI-minute spend | `gh api /repos/:owner/:repo/actions/billing/usage` |
| `__VENDOR_ROW__` | one row of the vendor-inventory table (repeat per vendor) | `Stripe \| payments \| $0 base + fees \| MEASURED` |
| `__COST_BASELINE_TREND__` | the opening spend-trend baseline | `flat, ~$1,200/mo since launch` |
| `__COST_SPIKE_ATTRIBUTION__` | root cause of any spend spike found | `none observed` |
| `__LEAK_FIXES_IN_FLIGHT__` | issue numbers for in-flight cost-leak fixes | `none open` |
| `__LEDGER_CARVE_OUT_DOC__` | a doc that looks like a duplicate cost ledger but is a different sanctioned thing | `pricing_go_live.md (customer markup formula, not company cost)` |
| `__RULING_COST_1__` | a standing operator cost ruling | `Vertex/Imagen image spend pre-approved standing` |
| `__UNIT_ECONOMICS_DEFINITIONS__` | per-unit cost measures worth tracking, and their raw source | `$/estimate generated = AI spend / estimate count` |
| `__COST_LANE_FENCE__` | the fence between this seat's vendor/FinOps accounting and any ad-spend/pricing seat | `paid-acquisition-strategist owns ad-spend effectiveness, not accounting` |
| `__RE_DERIVE_COMMAND_BLOCK__` | the full command block backing every count in a dossier, grouped by fact | `gcloud run services list ...; python3 scan.py --help ...` |
| `__PRODUCT_GOAL_SUMMARY__` | what the product is, its stage, and its hardest unsolved problem | `AI-generated remodel estimates from photos; hardest problem: measurement accuracy` |
| `__RESEARCH_DOMAIN_1__` | one numbered technical domain worth surveying, with why | `photo-based measurement — core unsolved accuracy problem` |
| `__SEED_QUERY_LIST__` | starting search queries per domain | `"photogrammetry room measurement open source"` |
| `__QUERY_CRAFT_LESSONS__` | known junk-query phrasings to avoid repeating | `"AI measurement" alone returns marketing pages, not tools` |
| `__HARD_CONSTRAINT_1__` | a non-negotiable constraint on usable prior art | `no paid vision API — hard cost blocker` |
| `__RULING_QUARANTINE__` | an operator ruling quarantining a domain from live-system input | `photo-AI measurement stays SHADOW mode until proven` |
| `__DEGRADED_FACT_1__` | a fact carried from a groundwork process, marked unverified | `"3 viable OSS libs" — from a single unverified sweep` |
| `__RESEARCHABLE_LANE_FENCE__` | the fence between research-scout (tools/OSS/prior-art) and market-analyst (market/competitor facts) | `tools/OSS questions → research-scout; competitor facts → market-analyst` |
| `__RESEARCH_LEDGER_TARGET_SLUG__` | this repo's slug in the runtime's already-evaluated-repos ledger | `exampleapp` |
| `__STAGING_URL__` | product-qa's staging origin(s), from the runtime live-testing allowlist | `https://staging.exampleapp.com` |
| `__QA_ACCOUNT_EMAIL__` | the standing QA account email + company id | `staging-qa@exampleapp.com, co-abc123` |
| `__QA_ACCOUNT_SECRET_NAME__` | the secret-manager secret holding that account's password | `<staging-login-secret-name>` |
| `__SESSION_PRIMING_PROCEDURE__` | how a browser-pool slot becomes pre-authenticated, and the NOT-RUN escalation | `claim pool slot, sign in via seeded session cookie; NOT-RUN if sign-in screen appears` |
| `__PRODUCTION_TEST_GATE__` | the standing rule that production is never tested without operator go-ahead | `CLAUDE.md ⛔ WHERE TO TEST rule` |
| `__SHARED_AUTH_WARNING__` | the warning against ever creating/modifying/deleting a shared-auth-provider account | `Firebase Auth is shared between staging and production — never mutate` |
| `__PERSONA_DEFINITION__` | the customer persona a QA walkthrough judges the app as | `a first-time GC owner, non-technical, judges success by "did I get a usable estimate"` |
| `__WALKTHROUGH_TASK_1__` | one enumerated user-facing flow, its entry route(s) and success criterion | `create estimate from photo — entry /estimates/new — success: line items generated` |
| `__ROUTE_TABLE_SOURCE__` | the file a task list was enumerated from, and its re-derive command | `App.tsx, grep -c "<Route" App.tsx` |
| `__JOURNEY_MAP_TASK__` | a periodic whole-app click-depth walk target table, if one exists | `none yet` |
| `__PRODUCT_QA_QUEUE_PATH__` | product-qa's own findings/revision queue file path | `none — findings filed directly as issues` |
| `__KNOWN_TRAP_1__` | a recurring point of confusion a walkthrough may misreport as a bug | `no auth challenge on the QA account — by design, not a security hole` |
| `__TENANT_AUTHORITY_RULE__` | the single authoritative rule for tenant scope, quoted verbatim | `"tenant gate reads ONLY memberships/{uid}"` |
| `__TENANT_AUTHORITY_RIVAL_STORES__` | rival stores that look like authority but aren't | `user profile doc's companyId field (descriptive only)` |
| `__TENANT_AUTHORITY_GRANT_CHOKEPOINT__` | the one chokepoint where tenant grants are actually issued | `src/billing/grant_membership.py` |
| `__WHERE_TO_TEST_RULE_CITATION__` | this repo's where-to-test rule citation | `CLAUDE.md ⛔ WHERE TO TEST: STAGING. ALWAYS.` |
| `__SECURITY_RULES_FILE_PATH__` | the database/storage security-rules file path | `firestore.rules` |
| `__SECURITY_RULES_EXPLICIT_DENIES__` | explicit named-collection denies kept for defense-in-depth | `explicit deny on /internal_admin/**` |
| `__STORAGE_RULES_STATUS__` | whether a storage-rules file exists at all | `storage.rules exists, deny-all default` |
| `__PAYMENT_WEBHOOK_HANDLER__` | the payment-webhook handler module, with its signature-check mechanism | `src/billing/webhook.py` |
| `__LICENSING_SEAT_MODULES__` | licensing/seat-management modules | `src/licensing/` |
| `__PAYMENT_PROVIDER_CONFIG__` | the payment-provider config/secrets module | `src/billing/config.py` |
| `__SECRETS_DOC_PATH__` | this app's canonical secrets/env-var doc | `docs/SECRETS_AND_ENV.md` |
| `__ENV_VAR_CANONICAL_HOME_RULE__` | the rule for where each class of env value belongs | `secrets → GCP Secret Manager; local → .env; see CLAUDE.md ⛔ ENV VAR rule` |
| `__INCIDENT_1__` | a past tenant-isolation/data-handling incident and the rule it produced | `2026-07-31 staging tenant leak → rule: staging never holds a real tenant` |
| `__TRUST_SURFACE_PATHS__` | the exact path list that triggers trust-architect as reviewer-of-record | `src/billing/, src/licensing/, firestore.rules` |
| `__FRONTEND_AUTH_GUARDS__` | the frontend auth-guard inventory, from a live directory listing | `shared_frontend/auth/RequireAuth.tsx` |
| `__UNTRUSTED_INGESTION_PATH_1__` | one path by which untrusted external content enters an in-app agent's context | `customer photo upload → vision-measurement prompt` |
| `__UNGROUNDED_AGENTIC_TRUST_CLASSES__` | agentic-trust classes not yet grounded here, named as an open gap | `cross-agent trust between Scout and the estimate engine — not yet audited` |
| `__IN_APP_AGENT_ROSTER__` | this repo's own in-app `.claude/agents/*.md` roster, each with tools/model pin | `implement (sonnet, Edit/Write/Bash)` |
| `__IN_APP_ORCHESTRATOR__` | the one in-app agent (if any) holding the `Agent` tool itself | `none — this repo has no in-app orchestrator` |
| `__FAN_OUT_WORKER_CLASS__` | a group of agents dispatched in parallel by an orchestrator, with shared tool grant | `n/a` |
| `__VERIFIER_AGENT__` | an agent that re-checks another agent's claims against a real document | `n/a` |
| `__CUSTOMER_FACING_AGENT__` | an agent that talks to paying customers directly, its module path and gate posture | `none — no customer-facing in-app agent exists` |
| `__DISPATCH_TOPOLOGY_DIAGRAM__` | the actual dispatch wiring as run, drawn as an arrow diagram | `/gtm → marketing-director → {conversion-architect, brand-architect, ...}` |
| `__ORCHESTRATION_SKILLS__` | skill files that orchestrate a multi-agent review flow, with trigger + procedure | `.claude/skills/gtm/SKILL.md — /gtm "<goal>"` |
| `__NON_DISPATCHING_RUNBOOKS__` | operator-invoked runbook skills that never dispatch a sub-agent | `.claude/skills/local_ci/SKILL.md` |
| `__KNOWLEDGE_BASE_ROOT__` | this app's top-level domain-knowledge corpus path | `docs/knowledge_base/` |
| `__KNOWLEDGE_READERS__` | which agents Read-FIRST which part of that knowledge base | `bathroom-trade agent reads trade_kb/bathrooms/` |
| `__KNOWLEDGE_CITATION_DISCIPLINE__` | the stated citation rule knowledge-consuming agents follow | `cite the document path, never recall from memory` |
| `__DEAD_WEIGHT_SURFACES__` | a pipeline-stage output directory with no confirmed reader | `none found` |
| `__STANDING_DECISION_1__` | one settled architectural/product decision, with citation | `"v1 engine is dead, v3 only" — feedback_v1_engine_is_dead_v3_only.md` |
| `__STANDING_DECISION_TESTING_ENVIRONMENT__` | this repo's own where-to-test rule, cited for this auditor | `CLAUDE.md ⛔ WHERE TO TEST rule` |
| `__RULING_GUARD_ALLOWLIST_CEILING__` | a standing ruling on reviewing new entries against an advisory guard-count ceiling | `none recorded` |
| `__KNOWN_GAP_1__` | a currently-open gap in the in-app agentic system's wiring, with proof | `verifier agent defined but zero dispatch-count callers — grep proof, UNTRACKED` |
| `__CLOSED_GAP_HISTORY__` | one worked example of a gap found and fixed since the last pass | `2026-08-31: agentarch job symlinked + loaded, closing AA-0050/AA-0051` |
| `__FAN_OUT_SIZING__` | max parallel workers one orchestrator can dispatch, vs. the machine-wide ceiling | `marketing-director dispatches up to 6 specialists; machine ceiling per agent_budget.py` |
| `__VERIFICATION_ECONOMICS__` | measured verifier:generator dispatch ratio, with re-derive command | `1:12 — grep -c '"agent_type": "code-reviewer"' spend.jsonl` |
| `__GROUNDING_QUALITY__` | the citation discipline each worker follows, and any check mechanism | `cite the doc path; no mechanical check yet` |
| `__LOOP_LEDGER_PATH__` | the append-only ledger of reviewed rounds/scenarios, if one exists | `tools/rule_coverage/history.jsonl` |
| `__LOOP_CAUSE_REGISTRY__` | the durable cause-key registry a convergence evaluator consults | `tools/engine_tests/cause_registry.py` |
| `__LOOP_EXIT_CONTRACT__` | the offline evaluator module and its named convergence assertions | `tools/gtm/exit_contract.py — GTM-CONV-01/02/03` |
| `__LOOP_CYCLE_TELEMETRY__` | where per-cycle loop records land | `cycle_log dashboard` |
| `__LOOP_SPEND_OR_CHURN_ORACLE__` | whether the runtime's churn/spend tool measures a different ledger than this loop | `churn_report.py measures commit churn, not estimate-loop rounds — distinct` |
| `__HARNESS_INDEX_DOC__` | this app's master test/harness index doc, with size + top sections | `docs/TESTING_AND_HARNESSES.md` |
| `__TEST_RUNNER_CMD__` | the one canonical "run everything" command plus named tier variants | `pytest -m unit`, `pytest -m integration` |
| `__BUNDLE_COMPILE_PREREQUISITE__` | a build/compile step a suite needs before it can pass | `python3 build_catalog_bundle.py` |
| `__SHARED_ARTIFACT_CONTENTION_RULE__` | the rule for compiling a shared artifact to a scratch path under concurrent runs | `compile to a per-run tmp path, never overwrite the shared bundle live` |
| `__CI_GATING_ENTRY_POINT__` | the pre-push/local-CI recipe and its CI-parity flag | `scripts/local_ci.sh --mode=full` |
| `__SCAN_ROOTS__` | the exact top-level dirs/units the scanner covers and excludes | `src/, shared/; excludes node_modules, .claude/worktrees` |
| `__VIOLATION_CHECKS__` | the named violation checks summed into a debt total | `no_assert_test, vacuous_assert, lock_in_test` |
| `__MEASURE_CHECKS__` | informational-only checks never summed into a total | `assertion density, test:code ratio` |
| `__TEST_QUALITY_LEDGER_PATH__` | the append-only ledger file and its write-ownership rule | `tools/code_debt/history.jsonl — scheduled job only` |
| `__RULESET_VERSION_RULE__` | the current scanner ruleset version and last bump date | `v3, bumped 2026-08-15` |
| `__EXPECTED_RED_BASELINE__` | suites currently expected-red, why, and the signal distinguishing that from a real new failure | `test_legacy_migration.py — skipped pending #4900, marked xfail` |
| `__LEDGER_WRITE_OWNERSHIP_SPLIT__` | the split between who writes the first ledger record vs. every subsequent one | `agent takes baseline if none exists; scheduled job owns every append after` |
| `__DIRTY_TREE_TREND_POLICY__` | whether a record from a dirty tree is trend-eligible | `flagged, not suppressed` |
| `__TEST_DEBT_BASELINE__` | the current stock baseline: total violations, breakdown, as-of date | `142 total, as-of 2026-09-01` |
| `__TEST_DEBT_ACCEPTED_PATTERN__` | a check dominating the backlog for a structural, accepted reason | `vacuous_assert dominated by fixture-only test files` |
| `__WORST_UNITS_RANKING__` | the worst-unit ranking at baseline | `1. estimate_engine/scope_enhancer.py 2. ...` |
| `__CATEGORY_D_MEASURES_SHAPE__` | informational-only measures at baseline, at low precision deliberately | `test:code ratio ~0.4` |
| `__STRUCTURALLY_UNMEASURED_LANE__` | a test lane the scanner cannot see because it's outside its scope | `Playwright E2E — different language, not scanned` |
| `__GOLDEN_NET_BASELINE_TRUST__` | how a golden-net baseline's trust state is tracked | `condemned on any unreviewed metric_version bump` |
| `__MUTATION_BATTERY_SIZE__` | the planted-bug mutation count and how to run it | `30+ reviewer checks, runner.py --batch` |
| `__FALSIFIABILITY_GATE_TOOL__` | the tool that reverts a fix and confirms red, with its exit codes | `scripts/verify_fix.py — 0 PROVEN, 1 PARTIAL, 2 FALSE_ALLCLEAR` |
| `__FALSIFIABILITY_GATE_WIRING__` | whether that tool is wired into a real consumer or invoked by nobody | `wired into pre-commit; exit code checked` |
| `__D1_MUTATION_SURVIVAL_COUNT__` | survived/killed counts for a tool-dispatch mutation-survival check, as-of date | `2 survived / 40 killed, as-of 2026-08-20` |
| `__D1_KNOWN_SURVIVOR_CLASS__` | the specific class of tool dispatch that still survives | `receipt-minting tool with no dedicated recorder-call assertion` |
| `__COVERAGE_FLOOR_VALUE__` | the configured coverage-floor value and its file/line | `80%, pyproject.toml [tool.coverage]` |
| `__COVERAGE_GATE_REAL_INVOCATION__` | the CI job/step that actually enforces the floor | `.github/workflows/ci.yml, test job, coverage step` |
| `__COVERAGE_GATE_ENFORCEMENT_TIER__` | enforced-when-run vs. report-only, sourced from the real CI-config classification | `enforced-when-run, not every PR` |
| `__STRUCTURED_LOGGER_MODULE__` | the structured-logging wrapper module | `shared/logging/structured.py` |
| `__PLAIN_LOGGER_COEXISTENCE__` | modules that bypass the wrapper and call stdlib logging directly | `entrypoint_backend/legacy/*.py` |
| `__LOG_READBACK_RECIPE__` | the actual command to read recent logs live | `gcloud logging read ...` |
| `__STANDING_DEFECT_1__` | an already-filed issue relevant to test-net/observability health | `#4900 — flaky Playwright timing, verify: rerun 3x` |
| `__ORPHAN_TOOL_CHECK__` | a test-support module found with zero live callers, and the decision left open | `old_harness.py, 0 callers via grep, decision: delete pending` |
| `__LANE_BOUNDARY_NOTE__` | the specific subsystem carved out to a separate test-architecture specialist | `estimate-engine correctness net owned by its own harness, not this seat` |
| `__LANE_BOUNDARY_EVIDENCE__` | the concrete paths proving this agent's own app-wide scope | `TESTING_AND_HARNESSES.md, integration_tests/` |
| `__SUBSYSTEM_ROW__` | one row of the subsystem-inventory table (repeat per subsystem) | `billing subsystem \| tools/billing_tests/ \| pricing vocab \| harness.py \| ledger \| 287 items` |
| `__SHARED_ROUTE_COVERAGE_INSTRUMENT__` | a shared route-presence helper deployed identically across modules, and what it does NOT measure | `assert_route_exists() — checks presence only, not auth outcomes` |
| `__SUBSYSTEM_SWEEP_FOLLOWUP__` | the follow-up to sweep subsystems not yet covered by the table | `#4901 — sweep remaining 12 modules` |

## Delivery, observability and video seats

Added with the `devops-architect`, `observability-architect` and `video-producer` dossier
templates. Tokens those templates share with other seats (for example `__CLOUD_PROJECT_ID__`,
`__LIVE_SERVICES_LIST__`, `__STRUCTURED_LOGGER_MODULE__`, `__VIDEO_PIPELINE_DIR__`) stay in the
tables above.

| token | meaning | example |
|---|---|---|
| `__ENVIRONMENT_TOPOLOGY__` | the environments, what each is for, and how they differ structurally | `staging and production; same image, separate datastores and secrets` |
| `__CI_WORKFLOW_INVENTORY__` | the CI / pipeline files, their triggers and jobs | `.github/workflows/ci.yml on pull_request; deploy.yml on push to main` |
| `__PIPELINE_TIMINGS_MEASURED__` | per-stage durations with sample size, measuring command and as-of date | `unit-tests 6-9 min (n=20, gh run list ..., 2026-09-09)` |
| `__IAC_INVENTORY__` | each place infrastructure or deploy config is declared, and which one takes effect | `deploy/cloudbuild.yaml (applied by CI); deploy/env.yaml (inert, superseded)` |
| `__RUNTIME_SERVICE_CONFIG__` | declared and running runtime settings (instances, concurrency, timeouts, health checks) | `min-instances 1, concurrency 80, timeout 300s, /health probe` |
| `__IMAGE_SUPPLY_CHAIN__` | registry, base images and pinning, and whether the tested artifact is the shipped artifact | `registry app-images; base pinned by tag, not digest; rebuilt per environment` |
| `__RELEASE_AND_ROLLBACK_PATH__` | promote path, hotfix path, rollback procedure and migration ordering rule | `staging then manual promote; rollback = redeploy previous revision` |
| `__DORA_METRIC_SOURCES__` | the primary source and command for each of the five delivery metrics, or why one is unmeasurable | `lead time: git log + deploy run timestamps; recovery time: not measurable (no incident log)` |
| `__ACCEPTED_DRIFT__` | recorded drift and deliberate trade-offs, each with its rationale or ruling | `prod min-instances 1 vs IaC 0 — deliberate, operator ruling 2026-09-09` |
| `__OBSERVABILITY_SUBSYSTEM_ROW__` | one row of the observability scope table (repeat per subsystem) | `billing \| src/billing/ \| payment provider, datastore \| structured wrapper \| webhook-failure alert` |
| `__LOG_SEVERITY_FORMATTER_NOTE__` | what the formatter emits for warning and critical levels, checked against the cloud severity enum | `emits WARNING and CRITICAL; matches the enum (checked in logging/formatter.py)` |
| `__REDACTION_MECHANISM__` | the log redaction layer and the shapes it covers | `filter in the structured wrapper; covers flat fields, not nested dicts` |
| `__LOG_SINK_AND_RETENTION__` | where logs land and for how long | `cloud logging default bucket, 30 days` |
| `__CORRELATION_MECHANISM__` | the trace / request id mechanism, its injection points and known drop-outs | `request id header injected in middleware; dropped in background tasks` |
| `__ALERT_INVENTORY__` | each alert / notifier / paging rule, its filter field, emitter and recipient | `payment-failure alert \| filter error_class=payment \| billing/webhook.py \| pages on-call` |
| `__TELEMETRY_CONSUMERS__` | the named consumer of each signal, for the dead-telemetry check | `error_class: payment-failure alert; request_latency: dashboard only` |
| `__OBSERVABILITY_ACCEPTED_GAPS__` | logging and observability gaps already ruled on or tracked | `no tracing on the export job — accepted until post-launch, #4900` |
| `__VIDEO_RECORDER_CAPABILITIES__` | the recorder's action vocabulary, scene grouping, end-card navigation rule, fit strategies and scene-schema path | `click, type, wait, scroll; scenes group by task; schema in tools/video/scene.schema.json` |
| `__VIDEO_MOBILE_CAPTURE_RECIPE__` | the exact setting that records a native portrait master | `recorder --device phone-portrait` |
| `__VIDEO_DEFAULT_FORMAT__` | the default deliverable format and length when a brief states none | `20-second screen recording of one task, 16:9` |
| `__VIDEO_SHOT_LIST_CHECKER__` | the shot-list checker's path and its standalone- and scenes-mode invocations | `tools/video/check_shots.py --standalone <file>` |
| `__VIDEO_REVIEW_RECORD_VALIDATOR__` | the review-record validator's path and whether it enforces `capture_mode` | `tools/video/validate_review.py; does not yet check capture_mode` |
| `__VIDEO_RECORDABLE_RECIPES__` | proven recording recipes (task, start state, steps, end state, as-of date) | `create-record-from-photo: start empty project, 6 steps, end approved record, 2026-09-09` |
| `__VIDEO_FORBIDDEN_ROUTES__` | routes that must never appear on camera, with the reason | `/admin/* — internal tools; /billing/* — payment details` |
| `__VIDEO_PII_SELECTORS__` | selectors or regions that can show personal data, and the masking mechanism | `.customer-name, .email-cell; blurred by the recorder mask option` |
| `__VIDEO_DEMO_TENANT__` | the identity recordings run as, its seeded data, and the no-real-identity rule | `demo workspace "Sample Co", fully synthetic seed data` |
| `__VIDEO_BROLL_SET__` | the reviewed b-roll clip table (id, content, approved narration line, review date) | `clip-04: crew on a roof, approved for "work on real jobs", 2026-09-09` |
| `__VIDEO_CLAIMS_RESTRICTIONS__` | the company's own vocabulary and claims restrictions for video, or where they are enforced | `no outcome guarantees; see the pack's claims_policy` |

## Knowledge seed tokens

These are used by `templates/knowledge/oversight_install.md`, not by an `oversight/*.md` dossier —
they're per-INSTALL seed values, filled once when that seed file is copied to
`~/.claude/knowledge/oversight_install.md` on a fresh machine, never per-agent-dossier facts.

| token | meaning | example |
|---|---|---|
| `__TRACKING_ISSUE__` | this install's open oversight tracking issue number | `#4901` |
| `__ABSOLUTE_PATH_TO_YOUR_REPO__` | the absolute path of the repo a scheduled job's WorkingDirectory points at | `/Users/x/Desktop/ExampleApp` |
| `__GTM_LISTINGS__` | the company's local listings (platform, profile id or URL, owner account, verification state, as-of date) | `GBP 1000000000000000001 (verified, 2026-09-28); Yelp example-co` |
| `__GTM_NAP__` | the one correct business name, address and phone per brand, with its source | `Example Co, 1 Main St, 555-010-1001 (pack, 2026-09-28)` |
| `__GTM_REVIEW_COUNTS__` | per-platform review count, average, unanswered count, as-of date | `GBP 42 reviews, 4.8, 3 unanswered (2026-09-28)` |
| `__GTM_RULINGS__` | operator rulings that narrow or widen this seat's lane for this company | `Nextdoor out of scope (operator, 2026-09-28)` |
| `__GTM_SOCIAL_ACCOUNTS__` | the company's social accounts (platform, handle or Page id, admin account, as-of date) | `Facebook Page 100000000000001; Instagram @exampleco` |
| `__GTM_ASSET_SOURCES__` | where real photos and screenshots live, and what is off limits | `Drive folder "Job photos"; no AI-generated images` |
| `__GTM_CADENCE__` | current posting cadence and results, with dates | `2 posts/week, median reach 400 (Aug 2026)` |
| `__GTM_GA4_GTM__` | the GA4 property and GTM container, and who may publish | `GA4 100000001; GTM-EXAMPLE; publish = operator only` |
| `__GTM_KEY_EVENTS__` | each key event: name, trigger, meaning, where it is imported | `generate_lead — form success page — imported to Google Ads` |
| `__GTM_METRICS__` | the company's metric definitions | `lead = form or 60s+ call, de-duplicated by phone` |
| `__GTM_GAPS__` | known tracking gaps | `calls double-counted (ads + call tracking)` |
| `__GTM_CRM__` | the CRM and where each lead source lands | `Example CRM; web form → "New lead" stage` |
| `__GTM_NUMBERS__` | current response time and close-rate figures with sample and date range | `median first response 19h, close 22% (Jul–Aug 2026, n=64)` |
| `__GTM_CONSENT__` | which contacts may be texted or called, and how consent was captured | `web form checkbox since 2026-03; no consent for older leads` |
| `__GTM_HIRING_ROLES__` | the company's open or planned roles with pay band and how pay works | `Carpenter — $26–34/hr guaranteed, full time (owner, 2026-09-28)` |
| `__GTM_HIRING_LOCATIONS__` | the work location (state, city) of each role | `Metro City, ST` |
| `__GTM_HIRING_BENEFITS__` | the benefits offered, as they must appear in postings | `PTO 5 days, company truck, tool allowance` |
| `__GTM_HIRING_BOARDS__` | job boards used, whose login, feed or manual posting | `Indeed (owner's employer account, manual posting)` |
| `__GTM_HIRING_BOARD_IDENTITY__` | per job board, the exact employer-account name and login email the owner recorded | `Indeed: "Example Co" / hiring@example.com` |
