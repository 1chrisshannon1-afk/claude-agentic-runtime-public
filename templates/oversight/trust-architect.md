# trust-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file. Every count carries its re-derive command + as-of date. VERIFIED = read/grepped live
this pass; reported-from-research = carried, not re-run this pass (flagged). A missing/stale
section here means the agent declares itself DEGRADED and reviews only what the code proves.

## (a) TENANT AUTHORITY RULE — the one source of company/tenant access

*The single authoritative rule for how this app decides tenant scope — quoted verbatim from its
own standards doc — plus every RIVAL store that looks like authority but isn't (records "about" a
user, never authority "for" one). A code path that reads a rival store to DECIDE access is a
finding regardless of exploitability.*

- __TENANT_AUTHORITY_RULE__ · __TENANT_AUTHORITY_RIVAL_STORES__ · __TENANT_AUTHORITY_GRANT_CHOKEPOINT__

## (b) WHERE-TO-TEST rule

*This repo's staging/production/real-tenant testing rule, cited from its canonical source.*

- __WHERE_TO_TEST_RULE_CITATION__

## (c) Rules files — the access-control model

*Database/storage security-rules files: deny-all posture, any explicit named-collection denies
kept for defense-in-depth, and whether a storage-rules file exists at all.*

- __SECURITY_RULES_FILE_PATH__ · __SECURITY_RULES_EXPLICIT_DENIES__ · __STORAGE_RULES_STATUS__

## (d) Money surfaces

*Payment-webhook handler (signature-check mechanism, route registration), licensing/seat modules,
payment-provider config/secrets modules — enough to know which files a money commit touches.*

- __PAYMENT_WEBHOOK_HANDLER__ · __LICENSING_SEAT_MODULES__ · __PAYMENT_PROVIDER_CONFIG__

## (e) Secrets doc

*This app's canonical secrets/env-var doc — path, size, headline sections — plus the env-var
canonical-home rule (where each class of value belongs).*

- __SECRETS_DOC_PATH__ · __ENV_VAR_CANONICAL_HOME_RULE__

## (f) INCIDENT HISTORY — compliance anchors, never re-litigated

*Past tenant-isolation/data-handling incidents that produced a standing rule. Cited once; a later
audit checks compliance with the resulting rule, never re-litigates the incident.*

- __INCIDENT_1__ — *what happened, the rule it produced, its doc citation.*

## (g) Trust-surface path map — reviewer-of-record substitution trigger

*The exact path list that triggers this agent as reviewer-of-record (substituting for, never
stacking on, the generic code-reviewer), plus the frontend auth-guard inventory if this app has
one, and any doc-vs-real-directory discrepancy.*

- __TRUST_SURFACE_PATHS__ — see `.claude/oversight/manifest.json` → `security.*` if centralized.
- __FRONTEND_AUTH_GUARDS__ — *from a live directory listing, not a possibly-stale doc table.*

## (h) Agentic surfaces — untrusted-content ingestion paths

*Every path by which untrusted external content (customer input, uploads, third-party responses)
enters an in-app agent's context — mechanism, incident history, producer-side review owner. Name
any class NOT YET grounded here (confused-deputy fan-out, output exfiltration, cross-agent trust)
as an explicit open gap, never silently skipped.*

- __UNTRUSTED_INGESTION_PATH_1__
- __UNGROUNDED_AGENTIC_TRUST_CLASSES__
