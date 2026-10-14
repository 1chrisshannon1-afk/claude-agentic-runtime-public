# devops-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file for the runtime `devops-architect` agent (opus, findings-only, dispatch-only, read-only
against cloud state). Discipline lives in `~/.claude/knowledge/devops_architect_primer.md`; this
file carries this repo's own delivery and infrastructure facts only. Every count and duration
carries its re-derive command + an as-of date. VERIFIED = read, grepped, or run live this pass;
anything else is carried forward, not re-measured. A missing or stale section here means the agent
declares itself DEGRADED at the top of its report and audits only repo-discoverable state, saying
explicitly what it could not ground. It never improvises a service name, URL, environment mapping,
or timing.

## (a) Scope, environments and live traffic

*What goes here: the subsystems the audit judges, the environments they run in, and what is on
production right now. The agent's standing constraint (never break production, never break
automated testing) is only as sharp as this section's statement of who is on production today.*
Re-derive: `` `__DEPLOY_DRIFT_COMMAND__` ``.

- Product / stack: __PRODUCT_NAME__ — __STACK_SUMMARY__. Maturity: __PRODUCT_MATURITY_STATE__.
- Cloud: __CLOUD_PROVIDER__, project or account `__CLOUD_PROJECT_ID__`, region(s)
  `__CLOUD_REGION__`. Identity that must be ACTIVE for cloud calls: `__AUTH_ACTIVE_ACCOUNT__`;
  identities belonging to another product, never to be used here: `__AUTH_WRONG_IDENTITY_TRAPS__`.
- Environments: __ENVIRONMENT_TOPOLOGY__ — *name each environment, what it is for, and how it
  differs structurally from the others (data, ingress, scaling, secrets, feature flags).*
- Live services per environment: __LIVE_SERVICES_LIST__. Health endpoints:
  __HEALTH_ENDPOINT_STAGING__ and __HEALTH_ENDPOINT_PRODUCTION__. Ingress posture:
  __INGRESS_OR_ACCESS_POSTURE__.
- Cloud checks are **read-only, always**: `list` / `describe` / `get` only; production is
  read-only without exception.

## (b) CI topology, branch model and measured timings

*What goes here: which pipelines exist, what triggers each, which jobs gate a merge or a promote
versus only report, the branch model, and measured stage durations. Never quote a duration from
memory or from this repo's own docs without re-deriving it: a documented figure being wrong is a
finding.*
Re-derive: `` `__LOCAL_CI_SCRIPT__ --help` `` and the run-history command in the block at the
end of this file.

- Pipeline inventory: __CI_WORKFLOW_INVENTORY__ — *workflow / pipeline files, triggers, jobs.*
- Blocking vs advisory: __CI_BLOCKING_VS_ADVISORY_JOBS__.
- Local gate: `__LOCAL_CI_SCRIPT__` with `__LOCAL_CI_FLAGS__`; pre-commit config at
  `__PRECOMMIT_CONFIG_PATH__`; build-failure artifacts land in `__CI_BUILD_FAILURE_LOG_DIR__`.
- Branch model: branches named `__BRANCH_NAMING_CONVENTION__`; PRs target `__PR_TARGET_BRANCH__`;
  promotion path `__PROMOTION_PATH__`.
- Measured timings: __PIPELINE_TIMINGS_MEASURED__ — *per stage: duration range, sample size, the
  command that measured it, as-of date. The named constraint is derived from THESE numbers.*

## (c) IaC and deploy-config inventory

*What goes here: every place infrastructure or deploy configuration is declared, and which of
them actually takes effect. Authority conflicts (two sources appear to define a value and only
one is live) are a drift class of their own, so list both sources and say which wins.*
Re-derive: `` `__DEPLOY_INTEGRITY_CHECK__` ``.

- Source of truth: __DEPLOY_CONFIG_SOURCE_OF_TRUTH__.
- Inventory: __IAC_INVENTORY__ — *one line per declared file or module: what it declares, which
  environment it applies to, and whether it is applied by automation or by hand.*
- Runtime service configuration (judged for correctness and SAFETY, never cost):
  __RUNTIME_SERVICE_CONFIG__ — *minimum instances, concurrency, timeouts, health checks, as
  declared AND as running.*
- Secrets census (names only, never values): `__SECRETS_CENSUS_CMD__`.

## (d) Image build and supply chain

*What goes here: how images are built and promoted. The questions the agent asks: are base
images current and pinned, is the build reproducible, is the artifact that was tested the
artifact that ships (build once, promote the digest), and is promotion by tag or by digest.
Build SPEED belongs to `git-ops`; PROVENANCE and REPRODUCIBILITY belong here.*

- __IMAGE_SUPPLY_CHAIN__ — *registry, base images and how they are pinned, build trigger,
  tag-versus-digest promotion, whether staging and production run the same built artifact.*

## (e) Release, promote and rollback path

*What goes here: the real promote path and the hotfix path, the rollback mechanism, and the rule
for rollback versus roll-forward, decided BEFORE a deploy, not during an incident. Include
database or data migration ordering: a rollback that cannot undo its migration is not a
rollback.*

- __RELEASE_AND_ROLLBACK_PATH__ — *promote steps and who or what triggers each; hotfix path;
  rollback command or procedure and its measured recovery time; migration ordering rule.*

## (f) Delivery-metric sources (the five DORA metrics, 2025 model)

*What goes here: for each of lead time for changes, deployment frequency, failed deployment
recovery time, change fail rate and rework rate, the primary source and the command that reads
it. A metric with no source here is reported as "not measurable here, and why", never estimated.
Name the edition when citing DORA: this seat uses the 2025 five-metric model with tiers
retired.*

- __DORA_METRIC_SOURCES__

## (g) Known-and-accepted drift (report WITH rationale, never as fresh findings)

*What goes here: drift and deliberate trade-offs already recorded with a reason or an operator
ruling. Read a config's stated rationale before classifying it a defect; report it WITH that
rationale and cite the ruling instead of re-filing it.*

- __ACCEPTED_DRIFT__

## (h) Out of scope for this agent in this repo

*Hand-off map to sibling agents for adjacent lanes this agent never claims.*

`__OUT_OF_SCOPE_HANDOFF_MAP__` (for example: CI job internals, caching, `permissions:` blocks and
action pinning → `git-ops`; watching one run to a terminal state → `ci-monitor`; secret values,
auth, tenancy and money → `trust-architect`; whether spend is worth it → `cost-strategist`;
logging sufficiency and alerts → `observability-architect`; agent-loop and gate-friction design →
`agentic-systems-architect`; issue filing → the orchestrator via `board-steward`'s rules).

## First assignment

__FIRST_ASSIGNMENT__

## How to re-derive

```bash
__RE_DERIVE_COMMAND_BLOCK__
```
