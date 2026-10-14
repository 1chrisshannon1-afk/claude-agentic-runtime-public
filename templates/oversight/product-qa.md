# product-qa — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file. Every count/route carries its re-derive command + as-of date. VERIFIED = read/grepped
live this pass; reported-from-research / reported-from-memory = flagged, verify at first
walkthrough. A missing or stale section here means the agent declares itself DEGRADED and may
audit only public, unauthenticated pages.

## Environment

*What goes here: this app's staging origin(s), the standing QA account (never a real customer
tenant), how a session gets pre-authenticated (or the exact failure mode when it isn't — a
sign-in form is a NOT-RUN condition, never something to hand-drive with a typed credential), and
the shared-auth-provider warning if one applies. Credentials are always fetched live from a secret
manager at time of use per the live-testing skill — never typed from memory, never printed.*
See `.claude/oversight/manifest.json` for any manifest-owned staging/tracker paths already
centralized.

- __STAGING_URL__ — *the staging origin(s), VERIFIED from the runtime's own live-testing
  allowlist.*
- __QA_ACCOUNT_EMAIL__ — *the standing QA account email + company id, never a real tenant.*
- __QA_ACCOUNT_SECRET_NAME__ — *the secret-manager secret name holding its password — never
  fetched by this agent directly unless the live-testing skill's procedure calls for it.*
- __SESSION_PRIMING_PROCEDURE__ — *how a browser-pool slot becomes pre-authenticated, and the
  exact NOT-RUN escalation text when it isn't.*
- __PRODUCTION_TEST_GATE__ — *the standing rule that production is never tested without explicit
  operator go-ahead.*
- __SHARED_AUTH_WARNING__ — *if this app's auth provider is shared between staging and
  production, the standing warning against ever creating/modifying/deleting an account there.*

## Persona

*What goes here: the customer persona this walkthrough judges the app as — their technical
sophistication, what they're trying to accomplish, and the bar they judge success by.*

- __PERSONA_DEFINITION__ — *one paragraph: who they are, what they know, what "success" looks
  like to them.*

## Walkthrough task scripts

*What goes here: the enumerated list of user-facing flows this app has, each with its entry
route(s), the steps a real user takes, and the concrete success criterion. Enumerate from the
app's own real route table (e.g. the frontend router file), not from memory — and name any
discrepancy between a doc's claimed route and the real one.*

- __WALKTHROUGH_TASK_1__ — *entry route(s), flow steps, success criterion.*
- __ROUTE_TABLE_SOURCE__ — *the file this task list was enumerated from, and its re-derive
  command (e.g. `` `grep -c "<Route" <your-router-file>` ``).*
- __JOURNEY_MAP_TASK__ — *if this repo runs a periodic whole-app interaction-cost walk (clicks
  from landing state to each named destination, compared to an `achievable_min`), the target
  table and its re-derive/refresh cadence.*

## Queue

*What goes here: the path to this agent's own findings/revision queue file (if the scheduled job
drains one), and its current state — empty/absent is a valid, honestly-reported state, never
invented content.*

- __PRODUCT_QA_QUEUE_PATH__ — *queue file path + draining-job owner.*

## Known traps

*What goes here: recurring points of confusion a walkthrough is likely to hit and misreport as a
bug — two similarly-named concepts that aren't the same thing, an expected-absent security
challenge on the QA lane, a flow that looks broken but is a known design choice. Each flagged
UNVERIFIED/reported-from-memory where it hasn't been re-confirmed live.*

- __KNOWN_TRAP_1__ — *the trap + why it looks like a bug + why it isn't.*
