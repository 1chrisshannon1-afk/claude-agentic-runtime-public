# sentinel — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY, fully enumerated. Not a tracker, not a plan. Every command carries an expected-output
shape + an as-of date. VERIFIED = run/opened directly this session. A missing or stale section
here means the agent declares itself DEGRADED for that app-scoped leg and runs only the
runtime-scoped legs (the heartbeat audit, the runtime-mirror health leg) — both read no dossier
and touch no cloud, so they never need to improvise an app fact.

## (a) GCP inventory

*What goes here: the cloud project id(s), region(s), and the live list of deployed
services/environments this app actually runs. The auditor needs this before any deploy-drift or
health check can target the right resource.* Re-derive: `` `gcloud run services list --project=<your-project-id> --region=<your-region> --format="value(metadata.name)"` ``.

- __CLOUD_PROJECT_ID__ — *the cloud project id, and whether it is the only one this app uses.*
- __CLOUD_REGION__ — *the deploy region(s), and whether they're consistent across deploy configs.*
- __LIVE_SERVICES_LIST__ — *the live per-environment service names (staging vs. production), as
  actually returned by a live list command — not names copied from a doc that may have drifted.*

## (b) Deploy-drift command

*What goes here: the exact, VERIFIED-working command to fetch the newest deployed revision name
for a given service, plus any deeper cross-check (image digest → build tag → running version
endpoint → git ancestry) this app has for catching a stale/mismatched deploy.*

- __DEPLOY_DRIFT_COMMAND__ — *the working revision-list command + expected output shape.*
- __DEPLOY_INTEGRITY_CHECK__ — *a deeper verification script/procedure, if one exists, and why it
  exists (what incident it was built to catch).*

## (c) Logs / error-rate baseline

*What goes here: the working command to read recent error-level logs, and where the durable
error-rate BASELINE actually lives (which file/heartbeat field, written by which job) — never
invent a baseline number here; state where it is captured and by whom.*

- __LOG_READ_COMMAND__ — *the working `gcloud logging read`-equivalent command + filter.*
- __ERROR_RATE_BASELINE_OWNER__ — *which scheduled job/heartbeat field owns the durable baseline,
  and its current state (empty/populated, as-of date).*

## (d) Uptime/health-monitor service

*What goes here: whether this app uses an external uptime-monitoring service (healthchecks.io or
similar), whether it's actually configured with a live check, and how to verify.*

- __UPTIME_MONITOR_SERVICE__ — *the service name, if any, and whether a live check/ping URL is
  confirmed configured (never assumed).*

## (e) Health endpoints

*What goes here: the app's real, currently-live health-check URL(s) — hostname form, live curl
result, and any known discrepancy between a doc's claimed hostname/behavior and what a live curl
actually returns. This section is the sentinel's most failure-prone: prefer live curl evidence
over static-config inference every time, and say explicitly when a claim is corroborated by only
one source.*

- __HEALTH_ENDPOINT_STAGING__ — *the live, working staging health URL + expected response.*
- __HEALTH_ENDPOINT_PRODUCTION__ — *the live, working production health URL + expected response
  (never probed without the operator's go-ahead per this repo's WHERE-TO-TEST rule).*
- __INGRESS_OR_ACCESS_POSTURE__ — *why a direct service URL may 404/403 by design (ingress
  setting, load-balancer-only front door) vs. a real regression — state the DESIGN INTENT and the
  live-verified actual state, and flag any mismatch as its own issue rather than silently
  reconciling it.*

## (f) Queue path, dedupe key, retention owner — DESIGN, not live

*What goes here: if this sentinel keeps its own findings queue (a per-finding record with a
dedupe key and a retention policy), the design of that queue — modeled on this repo's own
precedents for similar queues, if any exist. State plainly when a decision (e.g. the retention
owner) is still undecided; never report a policy as active until it is actually built.*

- __FINDINGS_QUEUE_DESIGN__ — *proposed or actual queue shape, dedupe key, retention owner.*

## (g) Cost dimension

*What goes here: where to read this machine's own agent-spend dashboard, the model-pin-drift
checker command, this app's canonical cost/pricing doc (never a second one), and the
code-review-blocker-rate ledger if this runtime tracks one.*

- __AGENT_SPEND_DASHBOARD_CMD__ — *the command to summarize local agent spend.*
- __MODEL_PIN_DRIFT_CMD__ — *the report-only model-pin-parity check command.*
- __CANONICAL_COST_DOC__ — *the one cost/pricing analysis doc for this product — see
  `.claude/oversight/manifest.json` if this path is manifest-owned.*

## (h) Tracker lifecycle law — resting-states check

*What goes here: if this app has a living launch-readiness/QA tracker with a "no silent resting
states" rule (a `deployed` or `failed` row must not sit unverified past a grace window), the
script (if any) that mechanically enforces it, its report classes, and the current finding count
at the date this rule was added.* See `.claude/oversight/manifest.json` → the tracker-doc key.

- __TRACKER_RESTING_STATES_CMD__ — *the report-only script/command, if one exists, and its
  report-only posture (never wired into a blocking gate).*

## Auth precondition

*What goes here: the exact `gcloud auth list`-style output this sentinel expects (which account
must be ACTIVE for its cloud calls to succeed), and the other listed-but-inactive accounts that
must never be used for this repo's calls (e.g. another product's service account). On mismatch,
the agent reports BLOCKED-AUTH and stops rather than attempting a wrong-identity call.*

- __AUTH_ACTIVE_ACCOUNT__ — *the account that must be active for this repo's cloud calls.*
- __AUTH_WRONG_IDENTITY_TRAPS__ — *other listed accounts that belong to a DIFFERENT product/repo
  and must never be used here.*
