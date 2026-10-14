# Change requests from `06_connectors.md` (§6) to other contract files

Each request names the target file, section, and the exact change. They exist because the
06_connectors.md fixes for FID-02, FID-03, FID-23, IMP-10, IMP-11, F20 and the connector isolation
findings depend on text that lives outside §6. 06 cites them as R1–R42. Until a request lands, the
name it defines is pending, and the WP tests that need it stay red.

**Landed (verified in the target files this round; no action needed):**
- `03_schemas.md §3.4.1` `id_fields` (key → kind map) and the row flag **`commits_on_enable`**;
  `03_schemas.md §3.2` "Enable actions" (scope = `commits_on_enable` rows + `_nomatch` enable verbs;
  refusal codes `enable_amount_required`, `enable_value_mismatch`).
- `03_schemas.md §3.22` `target_ids(tier_system, target_ref) -> dict[str, str]` (signature and dict
  form; the grammar table is still R1 item 1).
- `02_act.md §2.2b` `checks.identity_check`, `connector_dispatch.read_committed_ceiling` and the
  `build_read_ctx(slug, tier_system, brand, account_id=None)` signature; `02_act.md §2.6` rule 5a
  (fresh ceiling read, `ceiling_read`, `ceiling_unreadable`, `enable_value_mismatch`).
- `05_approver.md §5.5` step 3b: `commits_on_enable` (no rename) and (ii) narrowed to `_nomatch`.
  Its sentence about act.py passing `{new_absolute_value, unit}` as `connector_dispatch.execute(...,
  approved=…)` is **superseded by R19** (the full verified payload as `approval=…`; 06 §6.2 "Money
  binding"). R19 is still pending in 05 (re-checked 2026-09-28: §5.5 step 3b, L1133, still reads `approved=…`).
- (2026-09-27, later round) **R1** items 1 (grammar table and the account-level key list, as prose),
  2, 3, 5, 6, 7 and the `account_keys` function of item 8, plus item 9 (`CSA_GSM_PROJECT`,
  `CSA_SLUG`) — 03_schemas.md §3.4.1/§3.22. **R2** and **R14** — 02_act.md §2.8 check 1 (positive
  allowlist, account-level/object-level split, `normalize_account_id`, `identity_for:target_system`).
  **R15** — 02_act.md rule 5a and check 8 narrowed to `commits_on_enable` rows + `_nomatch` enable
  verbs. Still open from these: R1 item 8's `company.py validate` requirements, items 10 and 11, the
  §3.22 `target_ids` comment of R14, and R21 below.
- `08_seats_wps.md §9`: the runbook validator/testkit API block is a pointer to 06 §6.4b/§6.5b
  (Appendix B #117); Appendix B #141 (plan §8 deviation); Appendix C item 30 (FID-23 GSM project and
  `gcloud_account` decision before WP-M writes non-CSA `connectors.json`).

**Withdrawn:** the earlier R3 asks to rename `commits_on_enable` → `ceiling_enable` in 05 and to
name the refusal `enable_amount_mismatch`. The one flag is `commits_on_enable` and the one code is
`enable_value_mismatch`, everywhere.

## R1 — FID-02: `03_schemas.md` §3.22 (`system_names.py`), §3.4.1/§3.4.4 and §3.3 (pack schema)

1. **`target_ids` grammar table (normative; full match; any other form → `{}`; a system that
   lists patterns must yield ≥ 1 id, per check 1(c)):**

   | tier system | forms → keys |
   |---|---|
   | `google_ads` | `customers/<cid>` → customer_id; `customers/<cid>/campaigns/<id>` → customer_id, campaign_id; `customers/<cid>/adGroups/<id>` → customer_id, ad_group_id; `customers/<cid>/adGroupAds/<ag>~<ad>` → customer_id, ad_group_id, ad_id; `customers/<cid>/campaignBudgets/<id>` → customer_id, campaign_budget_id; `customers/<cid>/conversionActions/<id>` → customer_id, conversion_action_id. Bare numeric ids are not accepted |
   | `gbp` | `locations/<id>` or `accounts/<aid>/locations/<id>` → location_id (the `<aid>` is not returned) |
   | `meta` | `act_<digits>` → ad_account_id; `act_<digits>/campaigns/<id>`, `/adsets/<id>`, `/ads/<id>` → + campaign_id / adset_id / ad_id |
   | `facebook` | `page/<digits>` → page_id; `page/<digits>/posts/<id>` → + post_id |
   | `instagram` | `ig/<digits>` → ig_user_id; `ig/<digits>/media/<id>` → + media_id |
   | `ga4` | `properties/<id>` → property_id |
   | `gtm` | `accounts/<a>/containers/<c>[/workspaces/<w>]` → gtm_account_id, container_id (+ workspace_id) |
   | `search_console` | `sc-domain:<domain>` or `https://<host>/` → site_url |
   | `website_wordpress` | `https://<host>/<path>` → site_host (= host, lowercased), page_ref (= path) |
   | listing platforms, `lsa` | a URL exactly equal to an `identity_allowlist.listing_urls` entry → listing_url |

   **Account-level keys** (a module constant `ACCOUNT_LEVEL_KEYS`): `customer_id`, `ad_account_id`,
   `page_id`, `ig_user_id`, `location_id`, `property_id`, `gtm_account_id`,
   `container_id`, `site_url`, `site_host`, `listing_url`. Every other key is object-level.
2. **`normalize_account_id(tier_system, value) -> str`**: google_ads strips `-`, meta strips `act_`,
   gbp strips `locations/` and `accounts/<aid>/`, ga4 strips `properties/`, search_console and
   `site_host` lowercase. Every other system returns the value unchanged. Used by check 1(a), 04
   (already cited at 04_hooks.md L69) and 06 §6.2/§6.3.
3. **`identity_bucket(tier_system) -> str | None`**: `google_ads`→`ads_customer_ids`,
   `meta`→`meta_ad_account_ids`, `facebook`→`facebook_page_ids`, `instagram`→`instagram_ids`,
   `gbp`→`gbp_location_ids`, `ga4`→`ga4_property_ids`, `gtm`→`gtm_container_ids`,
   `search_console`/`website_wordpress`→`domains`; else None.
4. **`platform_hosts(tier_system)`** — landed in §3.22; no change.
5. **§3.4.1 row field `object_scope: "account" | "object"`**, required on every write row. `object`
   means the row modifies an object below the account and needs ≥ 1 object-level id (06 §6.2 step 5).
   Fill it on every §3.4.4 row. Money rows without an id in `after` (`google_ads.campaign_budget_edit`,
   `campaign_enable`, `campaign_pause`, `lsa.budget_edit`, `meta.spending_limit_edit`, …) are
   `object` and take their id from `target_ref`. Tier-table validator rule: every row with
   `object_scope: "object"` and empty `id_fields` has a system whose grammar yields an object-level key.
6. **`asset_link` kind.** Change `ids(target_id:identity)` on the `{…}.asset_link` row to a new kind
   **`identity_for:target_system`**: the value must be in
   `identity_allowlist[identity_bucket(after.value.target_system)]` ∪ the `account_keys` values of
   accounts whose normalized system is `target_system`, not merely any `OWN` value. check 1 applies
   it; 06 §6.2 step 6 re-checks it at execute. Validator rule: `after.value.target_system` of an
   `asset_link` is in `{t : identity_bucket(t) is not None}`.
7. **§3.22 account-id note:** `accounts[].account_id` may be written in any display form
   (e.g. the committed fixture's synthetic `100-200-3000`); every comparison goes through `normalize_account_id`.
8. **`account_keys(tier_system, account) -> dict[str, str]`** (06 §6.2 step 2): the platform-native
   account-level keys of one pack account. google_ads `customer_id` = `account_id`; meta
   `ad_account_id` = `account_id`; facebook `page_id` = `account_id`; instagram `ig_user_id` =
   `account_id`; gbp `location_id` = `account_id`; ga4 `property_id` = `account.ga4_property_id`;
   gtm `gtm_account_id` = `account.gtm_account_id`, `container_id` = `account.gtm_container_id`;
   search_console `site_url` = `account_id`; website_wordpress `site_host` = `account.site_host`;
   listing systems and `lsa` `listing_url` = `account.listing_url`. Values are normalized with
   `normalize_account_id`. A key whose source field is absent is omitted (06 then refuses
   `account_key_missing`). **§3.3 pack schema / `company.py validate`:** `site_host` is required on
   every `website_wordpress` account and `listing_url` on every listing/`lsa` account used for writes;
   `ga4_property_id` on every ga4 account and `gtm_account_id` + `gtm_container_id` on every gtm
   account (the committed OtherCompanyB fixture already carries them). A2 fixture test (06 §6.2):
   ga4 `properties/<the fixture's ga4_property_id>` (`properties/100000004`) and gtm `accounts/<gtm_account_id>/containers/<gtm_container_id>` (`accounts/1000000001/containers/100000002`) resolve.
9. **Constants `CSA_GSM_PROJECT = "example-org"` (plan §17 d) and `CSA_SLUG`** (CSA's
   registered slug; empty until the coordinator sets it). 06 §6.3 credential step 3 refuses
   `gsm_project == CSA_GSM_PROJECT` for any other company.
10. **Lead sink pack fields (06 §6.3 "Lead sink"):** add `lead_sink.credential_ref` (`gsm:<name>` or
    `none`) to `company_schema.json`/§3.3/§3.14. `company.py validate` refuses a pack whose `app_crm`
    `lead_sink.ref` host is a `phi_denylist.json` `agency_app` host or a host whose `applies_to`
    includes this pack, a host in another pack's `brands[].domains` or `lead_sink.ref`, or a
    `shared_identifiers` system host. Also add `lead_sink.baa_ref` (optional; its source is
    03_schemas.md §3.14, FID-19) to `company_schema.json`, which today has only `kind` and `ref`.
11. **Account brand conflict (06 §6.3 "Account matching"):** `company.py validate` refuses a pack
    account whose `system` carries a brand suffix (`tier_system_and_brand` returns a non-None brand)
    that differs from its `brand` field. `match_account` treats such an account as
    `account_ambiguous` in any case.

## R2 — FID-02: `02_act.md` §2.8 check 1 (and §9 A2 row in 08)

- check 1(a)/(c)/(d): compare account ids with `system_names.normalize_account_id` (R1 item 2), and
  apply the new `identity_for:target_system` kind (R1 item 6) in (d).
- 08_seats_wps.md §9 A2 "consumes": add `checks.identity_check` (A1, 02_act.md §2.2b) and
  `system_names.target_ids/normalize_account_id/account_keys/identity_bucket` (A1, 03_schemas.md §3.22).

## R4 — `02_act.md` §2.4 (`purge-untrusted`, `ticket --close`, `ticket --setup`)

- `purge-untrusted`: state that it deletes `ST/untrusted/**` **recursively** (including 06 §6.3's
  `act_<action_id>/` and `read_<tier_system>_<ts>/` evidence directories), and that those
  directories are excluded from backups.
- `ticket --close` of a **setup** ticket: runs `secret_sink.py scan --company <slug> --ticket <id>`
  as a subprocess of act.py. On exit 3 it prints the ROTATE line and exits 3 without closing, so
  the ROTATE path (06 §6.6) runs first. The close succeeds once `scan` exits 0, or once the ROTATE
  path has recorded its notice.
- `ticket --setup`: refuse a second re-capture setup ticket for the same action after a ROTATE
  (06 §6.6 "at most one re-capture per action"), exit 3 `recapture_limit`.

## R5 — `03_schemas.md` §3.20 (`phi_denylist.json`)

- Host entries take optional `"agency_app": true`. Such a host is denied to **every** company's
  connector (`connectors.http_request`, 06 §6.5b; plan §20.9/§20.9a), independent of `applies_to`.
  The Agency/OtherApp app hosts already entered with `applies_to: ["othercompany"]` get this flag.
- New top-level key `"agency_gsm_projects": ["<project id>", …]`. `connector_dispatch.credential_getter`
  refuses these projects (06 §6.3). WP-M seeds it from the Agency list-first procedure; `otherapp`
  (plan §17 d) is in it.
- Readers list: add `connectors.http_request` and `connector_dispatch.credential_getter` (both fail
  closed on an unreadable or absent file).

## R6 — IMP-10 / IMP-11: `08_seats_wps.md` §9 (remainder; the pointer and Appendix B #117/#141 landed)

- **L3 row, "writes" column:** add `connectors.idempotent_apply` and `connectors.auth_headers` in the
  package root `tools/gtm/connectors/__init__.py` (06_connectors.md §6.2/§6.3) next to
  `connectors.http_request`.
- **L1 row, "consumes" column:** add `connectors.idempotent_apply` + `connectors.auth_headers` (L3).
- **Connector-test item:** the `write.py`-denied-by-G-B test is an L unit test on
  `gtm_bash_gate.decision(command, environ, cwd)` (04 §4.2; asserting `result[0] is True and
  result[1] == "connector-write-outside-act"`) in Wave 2 — not `decide`, which is `gtm_task_gate`'s
  API (04 §4.6); the `bash_gate.sh` end-to-end variant belongs to B2's activation train (04 §4.7),
  per 06 §6.5.
- **L3 row, "writes" column (additions from the 2026-09-27 round):** `connectors.redact_content`,
  `connectors.mint_google_token`, `RedirectRefused`, `MutationOutsideApply`, `CredentialUnavailable`
  (moved to the package root; `connector_dispatch` re-exports it), and
  `runbook_validate.validate_obj` / `runbook_validate.load_head` (06 §6.4/§6.4b).

## R7 — `08_seats_wps.md` Appendix C, Appendix B, §9 E and M rows

- **Appendix C, new item:** "**secret_sink fallback B review:** trust-architect reviews
  06_connectors.md §6.6 fallback B (a plaintext download file under `H/.playwright-mcp/`). Until the
  ruling is recorded in plan §17, WP-E does not build `ingest-file`."
- **§9 E row:** change "`ingest-file`" to "`ingest-file` (only once fallback B is sanctioned,
  Appendix C new item)".
- **Appendix B #85:** replace "the session re-runs capture under a new setup ticket" with "the
  session re-runs capture under one new setup ticket only when the script's `regenerates` is true;
  otherwise (or when that one re-capture is spent) it writes an urgent `trust` notice and adds the
  platform's revocation step to the batched sign-in card (06_connectors.md §6.6)".
- **Appendix B item 39:** append "(file and shape only: `schema`, `gsm_project`, `gcloud_account`;
  the values for non-CSA companies are trust-architect's, Appendix C item 30)".
- **M row in §9, "consumes" column:** add `trust-architect's GSM-project/gcloud-account decision
  (plan §17 d; Appendix C item 30) before the non-CSA connectors.json`, and `phi_denylist.json
  agency_gsm_projects / agency_app hosts (R5)`. Note for that decision: Agency's `otherapp` project
  is never eligible (plan §20.9/§20.9a); it stays in `agency_gsm_projects`.

## R8 — FID-23: plan `~/.claude/plans/gtm_autonomous_department_plan.md` §17 d (coordinator)

Once trust-architect decides, replace "open item for P1: … trust-architect decides." with the
decided project id(s), the `gcloud_account` value(s) and the date, so 06_connectors.md §6.3 and WP-M
have one recorded value. Agency's `otherapp` project is never eligible (plan §20.9/§20.9a); it
stays in `agency_gsm_projects`. Also record the fallback B ruling (R7), the results of probes `l2`
(secret-sink CORS/PNA) and `j2` (the `gcloud auth print-access-token --impersonate-service-account`
flag set, 06 §6.3), and the MCP env-readability probe (06 §6.3 "MCP read servers": whether
`ps eww` / `ps -E` shows another process's environment to the same non-root macOS user), plus any
trust-architect ruling on the MCP env-var credential channel (Appendix B entry required first).

## R9 — `_nomatch` / unexecutable money rows: `02_act.md` §2.4 (`execute`, `ticket --write`) and §2.11

- `ticket --write`: refuse, with exit 3 `not_agent_executable`, a `_nomatch` action or a money row
  that has no connector `write_rows` entry and no runbook `writes[<row>]` entry (checked before
  `runbook_row_missing`).
- `execute`: the same refusal (connector_dispatch returns `validation` `not_agent_executable`; act.py
  maps it to exit 3, action unchanged).
- §2.11 `record-external --kind owner_executed`: add one sentence stating it is the only completion
  path for such actions after signature (plan §20.8 fallback), with its verify read.
- Test (A2): execute and `ticket --write` of a signed `_nomatch` action are both refused with that code.

## R10 — F20: `07_notices_schedules.md` §7.5 (K setup prompt / ROTATE steps) and `08_seats_wps.md` §9 K row

The K setup-capture prompt steps become:
1. `secret_sink.py serve` (or `prompt`).
2. On ticket close, run `scan` (R4).
3. On `ROTATE`, branch on the allowlist script's `regenerates`. `true` → one new setup ticket and
   one re-capture only. `false`, or the re-capture is spent → an urgent `trust` notice (push) naming
   the platform revocation step, and that step is added to the batched sign-in card. The prompt
   never opens a new card type and never re-runs capture a second time.
4. Exit 9 (`leaked_value_recaptured`) → the same as `regenerates: false`.

`test_k_prompts.py` asserts each step. (07 §7.5's E5 row already points at 06 §6.6; this makes the
checklist itself carry the branch.)

## R11 — `04_hooks.md` §4.1 (G-A) / path gate (conditional)

In GTM scope, deny `Read`/`Grep`/`Glob` (and Bash `cat`/`head`/`tail`/`cp` naming the path) of
`**/.playwright-mcp/gtm-capture-*`. This applies only if trust-architect sanctions fallback B (R7).
Until then no such file is ever created.

## R12 — `00_global_paths.md` §1.3 (state tree)

- Change the row `connector_idem/<system>.jsonl (+ <system>.lock)` to
  `connector_idem/<connector>.jsonl (+ <connector>.lock)` — `<connector>` is the §6.1 connector name
  (one ledger per connector, as `connectors.idempotent_apply` writes it), not the tier system.
- Add the row `reads/   read.py main --out (non-inbox-class reads)   06_connectors.md §6.3`, gitignored
  with the rest of `ST/`, and included in backups like `snapshots_dir`.

## R13 — lead-sink fallback: `02_act.md` §2.4 (`lead-append`) and `03_schemas.md` §3.14

- `lead-append`: when the `lead_sink` connector returns `validation` (incl. `host_not_allowed`,
  `redirect_refused`) or `auth`, **or** the pack's `lead_sink.kind` is `none`, write the row to
  `ST/lead_fallback.jsonl` with `fallback_reason: "sink"`, append `lead_appended` with `sink_ref:
  "fallback:sink"`, and exit 0 with `result.fallback: "sink"` (plan §5 "never lets a lead sit
  unlogged"). `sink` rows are replayed by the next `lead-append` whose sink call succeeds, exactly
  like `trust`/`pack` rows.
- 03 §3.14: add `"sink"` to the `fallback_reason` enum (`"chain" | "trust" | "pack" | "sink"`).
- A1 test: an app_crm sink whose host answers `host_not_allowed` → a `lead_fallback.jsonl` row with
  `fallback_reason: "sink"`, exit 0.

## R14 — FID-02 blocker-level mismatch: `02_act.md` §2.8 check 1(c) and the `03_schemas.md` §3.22 `target_ids` comment

Today check 1(c) requires **every** `system_names.target_ids(system, target_ref)` value ∈ `OWN`.
A campaign, ad group, ad set, ad, post, media, workspace or page-path id is never in `OWN` (no pack
can list them), so every object-scope action — including every `google_ads.campaign_budget_edit`,
`campaign_enable` and `campaign_pause` on `customers/<cid>/campaigns/<id>` — fails check 1 and
becomes class `never`. Replace (c)'s id rule with:
- the values of **account-level** keys (R1 item 1 `ACCOUNT_LEVEL_KEYS`) must be ∈ `OWN` after
  `normalize_account_id`, and at least one account-level key must be present when the system lists
  patterns;
- the values of **object-level** keys are judged exactly as kind `in_account` in (d) (no host/URL
  shape, no `/`, equal to no `SIB` value); they are then resolved only under `ctx.account` by the
  connector (06 §6.2 target resolution) or by the runbook's acting-as check, `not_owned` → no write.
Update the §3.22 `target_ids` comment ("Check 1(c) tests every value") to say the same. A1 test:
`google_ads.campaign_budget_edit` on `customers/<own cid>/campaigns/123` passes check 1;
`customers/<other cid>/campaigns/123` fails it.

## R15 — FID-03 enable scope: `02_act.md` §2.6 rule 5a and §2.8 check 8

03_schemas.md §3.2 "Enable actions" and 05_approver.md §5.5 step 3b define the enable scope as
(i) `commits_on_enable: true` rows and (ii) **`_nomatch`** actions whose verb is `enable`, `resume`
or `unpause`. 02 still says "or whose `action` is `enable`, `resume` or `unpause` (`_nomatch`
included, 05 R9)" (rule 5a) and "`commits_on_enable: true` row or whose `action` ∈ {`enable`,
`resume`, `unpause`}" (check 8), which also captures `google_ads.auto_apply_enable`
(`amount_required: false`, so it could never be signed) and `paid_api.usage_enable` (no connector,
no ceiling). Replace both phrases with "a `commits_on_enable: true` row, or a `_nomatch` action whose
`action` ∈ {`enable`, `resume`, `unpause`} (03_schemas.md §3.2 'Enable actions')", and update
rule 5a's example list to `google_ads.campaign_enable`, `lsa.account_enable`, `meta.campaign_enable`,
`meta.adset_enable`, `L.paid_enable`. 06 §6.5 carries the A2 test that `auto_apply_enable` and
`usage_enable` get no ceiling read.

**Declined:** `requests/05_approver.md` R23 asked 06 to key the enable re-check on every money-class
enable verb. 05 has since narrowed its own step 3b to `_nomatch`, matching 03; 06 follows 03/05.

## R16 — `02_act.md` §2.4 (`ticket --write`/`--write-batch`/`--read`, `execute`, `lead-append`, dry run) — 2026-09-27 round

- **Runbooks from HEAD (06 §6.4 "Trust root"; plan §20.8 N1, §7.1).** The machine runbooks move to
  `tools/gtm/runbooks/<stem>.runbook.json` (TRUST_PATHS). `ticket --write`, `--write-batch` and
  `--read` load a runbook only through `runbook_validate.load_head(R, stem)`: a non-empty code →
  exit 3 with that code (`runbook_not_at_head` | `runbook_dirty` | `runbook_unreadable`), no ticket.
  They then run `runbook_validate.validate_obj(obj, stem, tier_table=<HEAD tier_table.json>)`; any
  problem → exit 3 `runbook_invalid`, no ticket. Every ticket field copied from the runbook
  (`allowed_hosts`, `allowed_tools`, `max_mutating_calls`, steps, before-check values) and every
  placeholder filled into the brief comes from that HEAD object. Order: after R9's
  `not_agent_executable` and before `runbook_row_missing`. A2 tests as 06 §6.4 states.
- **`execute` passes the full verified payload.** act.py calls
  `connector_dispatch.execute(actx, action, dry_run=…, approval=<the dict approvals_verify.verify
  returned>)` instead of `approved={new_absolute_value, unit}`; connector_dispatch re-verifies it
  (06 §6.2 "Money binding"). New refusal messages from `execute` (all `validation`, exit 3, action
  unchanged): `approval_missing`, `approved_mismatch`, `identity_recheck_failed`,
  `internal_system_no_connector`, `mutation_outside_apply`, `redirect_refused`. An `EXIT_TRUST`
  `ActError` raised by the in-connector verify propagates (exit 11).
- **`gtm_ai`:** `execute` never calls `connector_dispatch.execute`/`verify` for system `gtm_ai`
  (05 §5.5 "AI-spend cap" path); state it in §2.4.
- **Recorded results are redacted (plan §20.4).** Wherever act.py persists a connector WriteResult
  or VerifyResult (the `executed`/`verified` event in `actions.jsonl`, any `result` JSON it writes),
  it stores `connectors.redact_content(result)` (06 §6.2 "Persisted and printed content"), never the
  raw result; `--dry-run` prints what `connector_dispatch.execute(dry_run=True)` returned (already
  redacted on a hipaa pack).
- **`ticket --setup`** records `script_id` in the setup ticket file (06 §6.6 "Which script's
  origins" reads it); a setup ticket without it is refused by `secret_sink.py serve` (exit 7).

## R17 — `04_hooks.md` §4.1 `runbook_hosts`, §4.2 rule b parity, §4.3 G-W trust roots; `08_seats_wps.md` `/gtm-signin`

- **`gtm_hooklib.runbook_hosts(systems)`** reads `git -C <R> show HEAD:tools/gtm/runbooks/<runbook_stem(tier_system_of(s))>.runbook.json`
  (new path), and contributes **no** hosts for a system whose working-tree file differs from HEAD,
  is absent at HEAD, or fails to parse (fail closed: a dirty runbook only narrows the allowlist).
  B test: a working-tree runbook adding a `read_hosts` entry → that host is not in G-A's navigate
  allowlist (§4.1 rule at 04 L168); RED when the working-tree file is read.
- **G-W trust roots (§4.3):** add, in GTM scope, anything under `R/tools/gtm/runbooks/` (as for
  `setup_scripts/`), admitted only by the operator-signed trust-edit marker.
- **Rule b parity (§4.2 / §4.7):** the parity test covers every **literal** manifest `api_hosts`
  entry, read-only hosts included; the tokens `{pack_domains}` (covered by the `/wp-json/` path
  rule) and `{lead_sink_host}` (no static value; config-time refusal, 06 §6.3) are exempt by name.
  Each connector WP adds its literal hosts to rule b's list and to the §4.7 token set in the same
  change (06 §6.1 `api_hosts` row).
- **`08_seats_wps.md` `/gtm-signin` row (L440):** read the runbook via `git -C <R> show
  HEAD:tools/gtm/runbooks/<runbook_stem(tier_system_of(system))>.runbook.json`, not the
  `knowledge/marketing_kb/runbooks/` working-tree path.

## R18 — `04_hooks.md` §4.2 G-B: process-environment readers in GTM scope

New G-B rule (GTM scope): deny `ps` whose options request process environments — a dashless
BSD-style option cluster containing `e` (`ps eww`, `ps auxe`) or the flag `-E` — and any
`launchctl procinfo`, reason `process-env-read`. The dashed `-e` ("all processes" on macOS) is not an
environment flag and stays allowed. Required before the MCP env-var credential channel can ever be sanctioned (06
§6.3 "MCP read servers"); useful as defence in depth regardless. B1 tests: `ps eww`, `ps auxe`,
`ps -E -p 1`, `launchctl procinfo 123` denied in GTM scope; `ps -ef`, `ps aux` allowed.

## R19 — `05_approver.md` §5.5 step 3b and §5.5 API block

- Step 3b "At `execute` (API) act.py passes the verified payload's `new_absolute_value` and `unit`
  as `connector_dispatch.execute(..., approved=…)`" → "act.py passes the **full verified payload**
  as `connector_dispatch.execute(..., approval=…)`; connector_dispatch re-runs
  `approvals_verify.verify(actx, action, stage="execute")` itself and derives `ctx.approved` from
  that result (06 §6.2 'Money binding')".
- API block: state that `verify(...)` performs **no** nonce operation and writes nothing (nonce ops
  are only `reserve`/`consume`/`release`), so a second call at stage `execute` from
  `connector_dispatch` is safe; and that the stage-`execute` expiry rule is the one the connector
  layer uses for the `execute`, `run_holds` and API `revert` callers alike.
- TRUST_PATHS prose: name `tools/gtm/runbooks/` among the covered files (it is inside `tools/gtm/`
  already, so no list change; the mention records that runbooks are a trust root, 06 §6.4).

## R20 — `00_global_paths.md` §1.3 / backup notes

- `connector_idem/<connector>.jsonl` row (with R12's rename): add "results stored via
  `connectors.redact_content` — op `fields`, `before_observed` and `requires_before` values are
  sha256 digests (06 §6.2 'Persisted and printed content'), so the ledger holds no lead, reply or
  recipient content and needs no backup exclusion".
- Add the row `tools/gtm/runbooks/<stem>.runbook.json   WP-L (machine runbooks; TRUST_PATHS; read
  from HEAD only)   06_connectors.md §6.4`, and note that `knowledge/marketing_kb/runbooks/` holds
  only the prose twins.

## R21 — FID-02: `03_schemas.md` §3.22 (`system_names.py` code block and the gbp grammar row)

1. **Named constant.** Add to the §3.22 code block, beside `target_ids`:
   `ACCOUNT_LEVEL_KEYS: frozenset[str]  # customer_id, ad_account_id, page_id, ig_user_id, location_id, property_id, gtm_account_id, container_id, site_url, site_host, listing_url — the "Account-level keys" paragraph above; 06_connectors.md §6.2 steps 2/4b/5 and the §6.4 {account_keys.<k>} placeholder read it by this name`.
   The prose list already exists (the "**Account-level keys**" paragraph); this only gives it the
   module name 06 §6.2 (steps 2, 4b), §6.4 (placeholder grammar) and requests/04_hooks.md
   (`IDENTITY_KEYS`) already use. A1 test: the constant equals that paragraph's list.
2. **gbp grammar row.** Change `accounts/<a>/locations/<id>` → gbp_account_id, location_id to
   `accounts/<a>/locations/<id>` → location_id (the `<a>` is matched but not returned), as R1 item 1
   specified. Reason: `gbp_account_id` is in neither the account-level list nor bound by any pack
   value, so today it would count as an object-level id — judged only syntactically by check 1(c)
   (`in_account`) and able to satisfy §6.2 step 5 / the tier-table validator's `object` rule for a
   gbp row that names no object below the location. 06 §6.2 step 2 drops it at execute meanwhile
   ("`gbp_account_id` (DECIDED HERE)"). A1 test: `target_ids("gbp", "accounts/9/locations/123") ==
   {"location_id": "123"}`.
3. **`target_ids` comment (R14 remainder).** "Check 1(c) tests every value (and requires ≥ 1 for a
   system with grammar rows)" → "check 1(c) tests every account-level value against the (a)-matched
   account's `account_keys` and judges every other value as kind `in_account` (02_act.md §2.8 check
   1(c)); ≥ 1 id is required for a system with grammar rows".

## R22 — `08_seats_wps.md` Appendix B, §9 M/L rows; coordinator (plan §17 / operator card): two recorded deviations

1. **Appendix B entry (MCP read servers).** "06 §6.3 'MCP read servers — none in Wave 2': plan §8's
   official `googleads/google-ads-mcp` and `googleanalytics/google-analytics-mcp` read servers are
   not launched in Wave 2. Reason: they take credentials from ADC or environment-configured values,
   and 06 refuses any secret value in a process environment (plan §20.6 NEVER). Replacement read
   path: each connector's `read.py` via `act.py read-run`/collectors. Adding an MCP server is a
   contract change that defines `tools/gtm/mcp_launch/servers.json` and `launch.py` (06 §6.3)."
   In §9, the L1/L2/L3 rows' `tools/gtm/mcp_launch/<…>.sh` entries stay conditional and are empty in
   Wave 2 (no text change needed beyond a pointer to this entry).
2. **Appendix B entry (CSA's own `app_crm` lead sink).** "06 §6.3 'CSA's own `app_crm` sink — not
   served in Wave 2': plan §8 names the CSA app API as CSA's lead sink, but plan §3.3 (WHERE TO TEST,
   `read_only_hosts`) and plan §20.2 (CSA production only on explicit operator instruction) forbid an
   autonomous production write. For `ctx.company == CSA_SLUG` with `lead_sink.kind: app_crm` the
   synthetic `crm` account is `access: browser` and `{lead_sink_host}` expands to nothing; the lead
   goes to `ST/lead_fallback.jsonl`."
3. **WP-M (§9 M row):** write CSA's pack with `lead_sink.kind: google_sheet` (preferred: a
   CSA-owned sheet shared with CSA's per-company SA) or `none` until the ruling in item 4 lands.
4. **Coordinator:** obtain a trust-architect ruling on the production blast radius of serving CSA's
   `app_crm` sink (exact endpoint, a scoped non-interactive credential able to append a lead row and
   nothing else, server-side rate limit, idempotency key, statement that it touches no tenant data
   beyond the lead row) **and** the operator's answer relaxing plan §20.2's "explicit operator
   instruction" for this one write (an Operator Decisions card: it is an outward act on production).
   Only then does a contract change remove the CSA branch in 06 §6.3 and §6.1 `api_hosts`, and
   amend 06 §6.3 "Config-time refusal" if CSA's app host is one of CSA's own `shared_identifiers`.
5. **R13 extension (`02_act.md` §2.4 `lead-append`, `03_schemas.md` §3.14):** route a lead whose
   `crm` account is not API-executable for the CSA branch above exactly as a `kind: none` lead: a
   row in `ST/lead_fallback.jsonl` with the `fallback_reason` R13 defines for `kind: none`, exit 0.
   A1 test: a CSA fixture pack with `lead_sink.kind: app_crm` → `lead-append` writes the fallback row
   and makes zero `FakeHTTP.calls`.

## R23 — `03_schemas.md` §3.3 (pack schema) and `company.py validate`: `identity_allowlist.meta_business_ids`

Add the optional identity bucket `identity_allowlist.meta_business_ids: [str]` (Meta business
ids, digits only). `company.py validate` refuses a value that appears in another pack's
`meta_business_ids` (the same cross-pack rule as the other identity buckets). It is read only by
06 §6.3 "`meta_bearer` identity check" (a system-user token's business-id scope targets). Not an
account-level key and not a `target_ref` grammar value; `identity_bucket()` is unchanged. A1 test:
two fixture packs listing the same business id → the second fails validate. Until this lands, 06
refuses every meta token carrying a business-id target (fail closed).

## R24 — `02_act.md` §2.2b (`pauses`), §2.4 (`execute`, `run-holds`, `revert`, `lead-append`), §2.6 rule 5a

1. **`pauses.chain_paused(ctx: Ctx) -> bool`** — true iff `ST/PAUSE.chain` exists (03_schemas.md
   §3.10 row). Read by 06 §6.3 "The pause step of `execute`" step 4, because an in-process importer
   of `connector_dispatch` never passes the dispatcher's chain-policy check (§2.3). A1 test: file
   present → true; absent → false.
2. **`op=` on every `connector_dispatch.execute` call:** `act.py execute` passes `op="execute"`,
   `run-holds` `op="run_holds"`, `revert` step 2 `op="revert"`, `lead-append` `op="lead_append"`
   (the `pauses.blocking` op names of §2.2b). 06 refuses any other value `validation` `bad_op`.
3. **Exit mapping of the new refusals:** a WriteResult `validation` whose message starts `paused:` →
   exit 11 for `paused:PAUSE.trust`, exit 10 for `paused:PAUSE.chain`, exit 5 for every other
   `paused:<name>` (the codes act.py already uses for the same pauses); `bad_op` → exit 1 (a
   programming error). These refusals carry `side_effect: "none"`, so 05 §5.5 step 5 releases the
   `$` nonce.
4. **§2.6 rule 5a:** `CeilingUnreadable` gains the reason `shared_budget` (06 §6.2 "Shared
   budgets"); rule 5a already maps every reason to `ceiling_unreadable`, so only the reason list, if
   quoted, changes.
5. **Test-mode refusal:** 06 now maps `CredentialUnavailable("test_mode_no_live")` to
   `validation` `test_mode_no_live` (the same shape as `TestModeNoLive`), so act.py maps exit 3
   `test_mode_no_live` from the message alone and never parses a `credential_unavailable:` prefix.
6. **`ticket --close` of a setup ticket:** keep "a subprocess of act.py" (06 §6.6 now says the same).

## R25 — `02_act.md` (3 hits), `03_schemas.md` (14), `04_hooks.md` (4): remove real OtherCompanyB account ids

`tools/` is in the mirror publish set (`.mirror/config.json` `include` has `tools`), and redaction
covers company names only. The committed fixture `tests/test_other-company_pack_fixture.py` already
replaced every real id with synthetic stand-ins (its "Major finding #4 (data exposure)"). Replace in
each file every real value (the Ads customer id in dashed or undashed form, the GA4 measurement id
and property id, the GTM public tag, container id and account id) with the fixture's synthetic
values: Ads `100-200-3000` / normalized `1002003000`; ga4 `account_id` `G-ABCD123456`,
`ga4_property_id` `100000004` (`ga4_account_id` `100000003`); gtm `account_id` `GTM-ABCD1234`,
`gtm_container_id` `100000002`, `gtm_account_id` `1000000001`. Restate test targets as
`properties/100000004` and `accounts/1000000001/containers/100000002`, and phrase examples as "the
committed fixture's `<field>`", never as a literal real value. Find them with
`grep -nE '<the real values>' contracts/*.md` (06 and requests/06 are already clean). Also check the
plan and every other published file under `tools/` for the same values.

## R26 — `08_seats_wps.md` §9 L1/L2/L3 rows and `/gtm-signin`: machine runbook path

The L1/L2/L3 rows (and the `/gtm-signin` row, if R17 has not already changed it) place the machine
runbooks at `knowledge/marketing_kb/runbooks/{…}.runbook.json`. 06 §6.1/§6.4 put them at
`tools/gtm/runbooks/<stem>.runbook.json` (TRUST_PATHS, read from HEAD only), with only the prose
`.md` twin under `knowledge/marketing_kb/runbooks/`. Change every `.runbook.json` path in those rows
to `tools/gtm/runbooks/<stem>.runbook.json`; keep the `.md` twins where they are.

## R27 — `03_schemas.md` §3.3 / `company.py validate`: slug bound for `google_sa` companies

GCP service-account ids are 6–30 characters of `[a-z0-9-]` starting with a letter (UNVERIFIED
against current GCP docs; the coordinator confirms with the first SA). 06 §6.3 requires
`gtm-<slug>-[a-z0-9-]+@…`, so `company.py validate` refuses a pack that has any `google_sa` account
(tier systems `google_ads`, `ga4`, `search_console`, `gtm`, `gbp`, or `lead_sink.kind:
google_sheet`) when the slug contains `_` or `len("gtm-" + slug + "-x") > 30`. A1 test: a fixture
pack with slug `a_b` and a ga4 account → refused; a 25-character slug → refused; RED when the
check is removed.

## R28 — `00_global_paths.md` §1.3 (state tree, backups), `02_act.md` §2.4 (`purge-untrusted`, every persisted connector result): hipaa redaction key

06 §6.2 "Persisted and printed content" now digests hipaa-pack content with an HMAC-SHA256 under a
per-company key, because a plain sha256 of a phone number or a name is reversible by enumeration
and the idempotency ledger is backed up and never purged (plan §20.4/§20.13).
1. **00 §1.3:** register `ST/untrusted/redact_key` (32 random bytes, mode `0600`, created on first
   use by `connectors.redact_key(state_dir, pack)`; purgeable; never backed up, like all of
   `ST/untrusted/`, 08_seats_wps.md Appendix C item 5), and state beside the `ST/connector_idem/`
   row that on hipaa packs its `result` digests are `hmac-sha256:` digests under that key (R20
   records the redacted form; this adds the key).
2. **02 §2.4 (every place act.py persists a connector result, R16, and the hipaa dry-run print):**
   pass `key=connectors.redact_key(ctx.paths.state_dir, pack)` to `connectors.redact_content`.
3. **02 §2.4 `purge-untrusted`:** state that it deletes `ST/untrusted/redact_key` by age like every
   other file there (its mtime is its creation time), so the key rotates at least every N ≥ 30 days.
   A1 test: a key older than N days is deleted and the next redaction mints a new one.

## R29 — `02_act.md` §2.2b `pauses.blocking` (and `04_hooks.md` §4.1 rule 6b): the stop-row exemption needs the action

03_schemas.md §3.2/§3.10 DECIDE the stop-row exemption and say "`pauses.blocking` therefore takes
the action", citing "requests/03_schemas.md R57", which does not exist in requests/03_schemas.md
(checked 2026-09-28; the coordinator should re-home that citation). 06 §6.3 "The pause step of
`execute`" calls the pending form:
1. **Signature:** `blocking(ctx, system, cls, op, brand=None, *, action: dict | None = None) -> str | None`
   (keyword-only, so every existing call stays valid). With `action` None the exemption never fires.
2. **Rule:** while walking its resolution order, a `PAUSE.<system>` / `PAUSE.<system>@<brand>` file is
   skipped (and the walk continues) iff all of 03 §3.10 hold: `read_pause` gives `created_by ==
   "breaker"`, `ruling_ref` null, `lift_card` null; the matched row (never `_nomatch`) has `class:
   "money"` and `lanes_key: "none"`; `(action.get("money_brief") or {}).get("urgency") == "urgent"`;
   `after.new_absolute_value == "0.00"` or `Decimal(after.new_absolute_value) <
   Decimal(before.value.current_absolute_value)` (unparseable → not exempt). `DISABLED`, `PAUSE`,
   every other pause file and `PAUSE.trust`/`PAUSE.chain` (checked by their own callers) still block.
3. **Callers:** `authorize`, `ticket --write`, `execute`, `run-holds` (and 06's
   `connector_dispatch.execute`) pass `action=`. 04 §4.1 rule 6b keeps using the ticket's
   `stop_exempt` flag (03 §3.6), which mint sets from the same function.
A1 tests (mirroring 06's A2 stop-row tests): under a breaker `PAUSE.google_ads`, an urgent `"0.00"`
`google_ads.campaign_pause` → `None`; a raising budget edit, a non-urgent pause, and the urgent pause
under a `created_by: "migration"` or `"operator"` pause → the pause name; each RED when the rule is
removed or widened.

## R30 — `02_act.md` §2.2b / §2.4 (`execute`, `run-holds`, `revert` step 2, `lead-append`): what 06's op binding and class step need from act.py

1. **State before the connector call.** 06 §6.3 "The class step" refuses `not_authorized` unless the
   folded record's `state` is `authorized` or `executing`. `act.py execute` already appends
   `executing` first. State the same for `run-holds` (a due API hold: `held` → `executing` before
   `connector_dispatch.execute`) and `revert` step 2 (the child → `executing` after its approval is
   verified, before the call).
2. **`holds.cancel_pending(ctx, action_id) -> bool`** (A2, `holds.py`, read-only): true iff
   `S/cancels/<slug>/<action_id>` or an `_all.<UTC ts>` marker newer than the last ingest exists
   (03_schemas.md §3.11). 06's class step calls it for `identity`-class actions. A2 test: marker
   present → true, absent → false.
3. **Arguments:** `revert` step 2 passes `card_id=<its --approval card id>` for a non-money child
   (06 verifies `revert <child>` itself when the child was admitted only by the `DISABLED`/`PAUSE`
   carve-out); `lead-append` calls with `op="lead_append"` only for its `crm.lead_append` action;
   `run-holds` passes `op="run_holds"` only for actions with a `hold` block.
4. **`lead-append` under `PAUSE.chain`:** 06 now refuses `lead_append` under `PAUSE.chain`
   (`paused:PAUSE.chain`), so `lead-append` must route the lead to `ST/lead_fallback.jsonl` **before**
   calling the connector whenever `pauses.chain_paused(ctx)` (plan §6.8; `chain-repair --replay`
   replays it); confirm the text says so.
5. **Exit mapping of the new refusals** (all `validation`, `side_effect: "none"`, so 05 §5.5 step 5
   releases a `$` nonce): `card_not_approved`, `card_subject_mismatch`, `hold_pending`, `cancelled`,
   `not_authorized`, `baa_missing` → exit 5 (refused); `redact_key_unavailable` → exit 3; `bad_op`
   stays exit 1 (R24 item 3).

## R31 — `03_schemas.md` §3.3 / `company.py validate`: no slug may be a hyphen-extension of another

06 §6.3 credential step 2 and the SA identity check match `gtm-<slug>-[a-z0-9-]+`, which lets slug
`acme` match `gtm-acme-west-…`. `company.py validate` refuses registering a slug `s` when another
registered slug `t` satisfies `s.startswith(t + "-")` or `t.startswith(s + "-")`. A1 test: `acme-west`
while `acme` exists, and `acme` while `acme-west` exists → refused; RED when the check is removed.
(The current slugs do not collide; this keeps it so.)

## R32 — `08_seats_wps.md` Appendix B; coordinator + trust-architect (plan §17 j): Meta `SYSTEM_USER` tokens

Plan §17 j records that system users need a Business Portfolio and are "not available to us". 06
§6.3 "`meta_bearer` identity check" now refuses `SYSTEM_USER` tokens while
`connector_dispatch.META_SYSTEM_USER_RULING` is None. Admitting them needs: an Appendix B entry
(deviation from plan §17 j), a trust-architect ruling recorded in plan §17 that also confirms the
portfolio contents check (06: every owned/client page, ad account and IG account of the portfolio is
in the pack's identity buckets, else refusal + isolation hit), the plan §20.6 portfolio card if a
portfolio would have to be created or joined (never autonomous; CSA CLAUDE.md "NEVER
CROSS-CONNECT"), and then the constant set to the ruling's reference in the same signed change.

## R33 — `03_schemas.md` §3.6 (`dispatch_brief.steps`, write and read tickets), `04_hooks.md` §4.1 rule 7b: object-level placeholders

06 §6.4 adds the placeholder `{target_ids.<k>}` (object-level keys only; never `target_ref`, never an
account-level key) and the validator code `object_unaddressed` (every `object_scope: "object"` row
reaches its object through a `navigate` whose URL embeds it).
1. **03 §3.6:** `dispatch_brief.steps` fills `{target_ids.<k>}` from the ticket's check-1-verified
   `target_ids` (today it fills only from `after_fields`/`after_value_fields`); a `<k>` the ticket
   does not carry refuses the mint `target_missing`.
2. **03 §3.6 read tickets:** a read ticket for an object-scoped read path (e.g. `committed_ceiling`)
   carries that object's `target_ids` (resolved and check-1-verified like a write ticket's), and its
   brief fills `{target_ids.<k>}` in `read_paths[].start_url`.
3. **04 §4.1 rule 7b:** no rule change expected — rule 7b already judges the ids in a navigate URL by
   key class; confirm the object-level class admits exactly the ticket's `target_ids` values.

## R34 — `00_global_paths.md` §1.4 / `03_schemas.md` constants table, `02_act.md` §2.2b/§2.4, `07_notices_schedules.md` §7.5, `08_seats_wps.md` §9 K row: fallback C (`secret_sink.py prompt`)

06 §6.6 "`prompt` admission" makes the operator's terminal capture usable hours after the sign-in
card: `prompt --company <slug> --action <action_id>`, admitted by a TTY and a signed operator marker,
minting its own setup ticket.
1. **00 §1.4 / 03 (`OPERATOR_OK_COMMANDS`):** add `"secret_sink_prompt"`, whose `target` is the
   `action_id` (grammar: 00 §0.3 action id). `operator_ok.sh` accepts it. `consume_operator_ok`
   consumes it like the others (holder `operator-ok:secret_sink_prompt:<action_id>`).
2. **02 §2.2b/§2.4:** factor `ticket --setup`'s writer as `tickets.mint_setup(ctx, action, *,
   script_id: str | None, created_by: str) -> dict` (A2), used by `ticket --setup` and by
   `secret_sink prompt` (`script_id=None`, `created_by="secret_sink_prompt"`); the ticket's
   `session_id` is the `session_id` of the action's latest `authorize` event when `created_by ==
   "secret_sink_prompt"`.
3. **07 §7.5 / 08 §9 K row (WP-K setup prompt) and the batched sign-in card:** list, for fallback C,
   the two operator commands in order — sign `operator_ok.sh secret_sink_prompt <action_id>`, then
   run `secret_sink.py prompt --company <slug> --action <action_id>` in his own terminal — replacing
   any text that tells him to pass `--ticket`.

## Round 8 — review-finding fixes in 06 (2026-09-28): status notes and new requests R35–R42

**Status notes.**
- **R29 landed** (verified 2026-09-28): 02_act.md §2.2b `pauses.blocking(ctx, system, cls, op, brand=None,
  action=None)` takes the action and implements the stop-row exemption through `tiers.is_stop_action`
  / `tiers.STOP_ROWS` and the signed-revert exemption. 06 §6.3's pause step now calls it and no longer
  restates either predicate. R29's item-2 wording ("`class: money` and `lanes_key: none`") is
  **superseded** by 02's `STOP_ROWS` rule; nothing further is asked.
- **R30 item 3 is superseded.** 06 §6.3 no longer has a card path under `DISABLED`/`PAUSE`: an
  unsigned revert child is refused under every pause, a signed child passes by 02 §2.2b's signed-revert
  exemption and is re-verified by 06's approval binding, and the card of a card-unlocked child (no
  pause) is read from the child's folded `authorized` event. `revert` step 2 need not pass `card_id`
  (the keyword stays, optional; a value that differs from the event's card is refused). Items 1, 2, 4
  and 5 of R30 stand; item 5 gains `card_predates_event`, `hipaa_prohibited`, `static_not_connector`,
  `upload_source_missing` (all `validation`, `side_effect: "none"` → exit 5 refused, except
  `static_not_connector` and `upload_source_missing` → exit 3).
- **requests/02_act.md item 92 answered:** 06 §6.3 exports `connector_dispatch.ERROR_KINDS` (every
  `error.code`) and `connector_dispatch.VALIDATION_MESSAGES` (every `validation` message, plus the
  `paused:` prefix).
- **requests/02_act.md item 96 answered:** 06 §6.3 credential step 1 and `check_secret_target` read
  `HEAD:./.claude/gtm/connectors.json`.
- **requests/03_schemas.md R28, R29, R55, R60 (b), R61 (b), R62 (b), R70 answered in 06** (§6.4
  `account_breadcrumb` + `in_account_check_missing`; §6.6 setup-ticket status set; §6.6 acting-as
  binding from the ticket file; §6.2 "Asset and upload bytes"; §6.2 target-resolution step 7; §6.1
  `ad_content` + §6.2 "Ad content read and verify"; §6.6 WordPress role check).
- **requests/04_hooks.md R41 answered in 06:** §6.4 optional `identity_in_url`/`acting_as_step`, a
  runbook-unique step `id`, validator code `acting_as_step_invalid`.
- **08_seats_wps.md Appendix C item 16 landed** (committed `company.py` `_credential_refs` collects only
  `gsm:` refs); 06 §6.3 now says so.

## R35 — `03_schemas.md` §3.22 (`system_names`) and `08_seats_wps.md` Appendix C (`company.validate_company`): shared-hosting parents

06 §6.1 `{pack_domains}` admits every subdomain of a brand domain, so a brand domain that is a
shared-hosting or platform parent would let the wordpress connector send its Basic-auth application
password to any tenant under it.
1. **03 §3.22:** add `system_names.SHARED_HOST_PARENTS: frozenset[str]`, a pinned literal (lowercase,
   no leading dot) holding at least `wpengine.com`, `wordpress.com`, `wpcomstaging.com`,
   `kinsta.cloud`, `pantheonsite.io`, `netlify.app`, `vercel.app`, `github.io`, `herokuapp.com`,
   `web.app`, `firebaseapp.com`, `appspot.com`, `azurewebsites.net`, `cloudfront.net`,
   `squarespace.com`, `wixsite.com`, `godaddysites.com`, `co.uk`, `com.au`. Adding an entry is an
   ordinary reviewed change.
2. **08 Appendix C / `company.validate_company`:** refuse a pack whose `brands[].domains` holds a
   domain with fewer than two dot-separated labels or equal to a `SHARED_HOST_PARENTS` entry (reason
   `brand_domain_shared_host`); a tenant subdomain (`acme.wpengine.com`) stays valid. A1 validate
   test: `domains: ["wpengine.com"]` → refused; `["acme.wpengine.com"]` → valid; RED when removed.
06 §6.1 drops such a domain at host-guard build (fail closed) regardless, so this is defence in depth.

## R36 — `04_hooks.md` §4.2 rule b and §4.7 (B2's `tools/gtm/wave2_pending/b2_gb_wiring.patch`): Wave-2 connector hosts

06 §6.1 now says an L WP files a request instead of editing the live `bash_gate.sh`, `gtm_bash_gate.py`
or B2's patch. Pre-populate rule b's host-pattern list and the `bash_gate.sh` token set **in the
patch** with the literal hosts the Wave-2 manifests declare: `googleads.googleapis.com`,
`analyticsadmin.googleapis.com`, `analyticsdata.googleapis.com`, `searchconsole.googleapis.com`,
`tagmanager.googleapis.com`, `mybusinessbusinessinformation.googleapis.com`,
`mybusinessaccountmanagement.googleapis.com`, `graph.facebook.com`, `sheets.googleapis.com`,
`oauth2.googleapis.com`. The `listings`/`call_tracking` vendor hosts follow by later requests. State in
04 that the P2 G-B host-parity test is owned by **B2**, reads every committed
`tools/gtm/connectors/*/manifest.json` `api_hosts` (the `{pack_domains}` and `{lead_sink_host}` tokens
exempt by name), runs against the patch's lists, and gates the activation train.

## R37 — `02_act.md` §2.4 (`execute`, `run-holds`, `revert` step 2): what 06's asset/upload rules need from act.py

06 §6.2 "Asset and upload bytes" makes the connector read asset bytes only from
`ST/assets/<action_id>/<sha256>` (it builds `ctx.bound_assets` from `action["assets"]` itself) and an
upload row's data file only from a path act.py hands it.
1. **`upload_source`:** for every `*_upload` row, act.py calls `connector_dispatch.execute(...,
   upload_source=<the absolute realpath of source_ref>)` immediately after its execute-time
   `home_data` re-check (03 §3.4.1 rule "Checked twice"), and never for any other row. A missing value
   is refused by the connector `upload_source_missing` (exit 3).
2. Confirm that `checks.rebind_assets` runs before every `connector_dispatch.execute` call that can
   upload an asset (the connector re-hashes the copy again and refuses `asset_sha_mismatch` /
   `asset_unbound`, exit 3, action `failed` like 02's own `asset_sha_mismatch`).
3. Exit mapping of the new connector-built refusals: `asset_unbound`, `asset_sha_mismatch`,
   `source_mismatch` → exit 3 and the action `failed` (as 02's `asset_sha_mismatch`).

## R38 — `02_act.md` §2.2b (`store.fold`) and §2.4 `revert`: the folded `authorized` event

06 §6.3 reads, from `store.fold(actx)[action_id]`, the fields of the action's **latest `authorized`
event** (`approval_request_id`, `card_id`; 02 §2.2 event table) — the same fields 02's signed-revert
exemption reads — and the `ts` of the action's latest `failed` event (for `cards.require_approved(...,
not_before=…)`). State the folded record's key for each (e.g. `rec["authorized"] = <payload of the
latest authorized event>`, `rec["last_failed_ts"]`), so 06, `pauses.blocking` and `authorize` read one
spelling. A1 test: a revert child authorized by a signed request folds `rec["authorized"]
["approval_request_id"]` non-null and `card_id` null; a card-unlocked child the reverse.

## R39 — `03_schemas.md` §3.4.4 "Enabling ads" and `02_act.md` §2.9: `ad_content` data shape and item keys

06 §6.2 "Ad content read and verify" fixes `ad_content`'s `data` as `{"items": [{"kind", "id",
"status", "content": {…}, "item_digest"}], "content_digest"}` and needs the image-hash key named.
1. **03 §3.4.4:** name the item content keys as JSON keys: Meta ad `image_hash` (the creative's image
   hash) and asset `image_hash`; profile and post keys likewise when `profile_content`/`post_content`
   are specified (requests/03_schemas.md R67). State that a key the platform does not return is
   present with value `null` inside the digested object.
2. **02 §2.9:** the `verified` event of an ad/asset create or edit records the connector's
   `observed.content_digest` as that item's `item_digest` (03 §3.4.4 "Content-bound").

## R40 — `03_schemas.md` §3.6 (setup tickets), `07_notices_schedules.md` §7.5 and `08_seats_wps.md` §9 E/K rows: capture-script contract

06 §6.6 now fixes the capture POST as `{"ticket_id", "secret_name", "acting_as_label", "value"}` to the
literal port 47823, a `serve` reply table, a `--timeout` exit (7 `ticket_expired`), and the
WordPress Editor-role check before any application password is created.
1. **08 §9 E row:** every allowlisted capture script reads and posts `acting_as_label`, and the
   WordPress script performs the `users/me?context=edit` role read first (abort `before_mismatch`,
   no sink POST, unless `["editor"]`).
2. **07 §7.5 / 08 K row (setup prompt):** on a `refused:acting_as_mismatch` reply the seat stops
   (no retry) and the session posts the sign-in card again; on `before_mismatch` from the WordPress
   role read the setup card asks the operator for a dedicated Editor user (plan §17 j).
3. **03 §3.6:** confirm `secret_sink` stores only on `pending`/`bound` and that `scan` runs on
   `pending`/`bound`/`stopped`/`expired` (the close-time scan), as 06 now states.

## R41 — `00_global_paths.md` §1.2/§1.3: modes of the connector state directories

06 now fixes: `ST/untrusted/` created `0700` (§6.2 `redact_key`); `ST/connector_idem/` `0700` with
`0600` files; evidence directories `0700` with `0600` files (§6.2 "Evidence files"). Record these
modes in the §1.3 state-tree rows so every creator uses them.

## R42 — `08_seats_wps.md` §9 L rows: new L3/L1 obligations from this round

Add to the L3 row: `ConnectorCtx` in the package root, `testkit.make_ctx`, the `_secrets`-based
`ctx.log` closure, `ERROR_KINDS`/`VALIDATION_MESSAGES` are A2's (connector_dispatch) — list them in A2's
row — and validator codes `in_account_check_missing`, `acting_as_step_invalid`. Add to the L1 rows
(google_ads, meta, gtm_api, wordpress): the §6.2 step-7 in-account ownership reads with their
per-kind docstring list, `ad_content` (google_ads, meta), the asset/upload byte rules, and the
wordpress Editor-role check on first credential use.

## R43 — `03_schemas.md` §3.6 and `02_act.md` §2.4 `ticket --setup`: setup ticket `secret_name` is the BARE name

06 §6.3 credential step 2 "Secret name form" (DECIDED HERE, wave1c) fixes the secret name every
consumer carries as the BARE name: the pack account's `credential_ref` with its `gsm:` prefix
removed (only `credential_ref` carries `gsm:`).
1. **03 §3.6 (`setup` ticket row, `secret_name` field):** state "`secret_name` is the bare GSM secret
   name — the pack account's `credential_ref` minus its `gsm:` prefix (e.g. `gtm-other-company-meta`,
   never `gsm:gtm-other-company-meta`); `secret_sink.py --secret-name` and the capture POST's
   `secret_name` must equal it byte-for-byte."
2. **02 §2.4 `ticket --setup`:** in "`credential_ref` is `gsm:<name>` — `<name>` becomes the ticket's
   `secret_name`", append "(the bare `<name>`, prefix removed; 06 §6.3 step 2)".

## R44 — `08_seats_wps.md` §9 L3 and A2 rows: log factory and A2 test seams

1. **L3 row:** add `connectors.make_log(secrets)` and the package-root `_REDACT_RE` (an inline copy of
   `activity_log.REDACT_RE`) with their L3 parity test against `activity_log.redact` (06 §6.2 "The log
   closure"); `testkit.make_ctx` builds `log` only through `make_log`. Also note `mint_google_token`
   serves a non-expired `ctx._token_cache` before its test-mode statement (06 §6.3 "Test mode first").
2. **A2 row:** `_build_ctx` builds `log` only through `connectors.make_log(ctx._secrets)`; calls
   `credential_getter` through the module global; honours `connector_dispatch._TEST_TOKEN_CACHE` only
   under test mode; and A2 tests never monkeypatch `gtm_env.test_mode`/`refuse_real_state` in a file
   that calls `execute`/`verify` (06 §6.3 credential step 0 "A2 test seam"). The step-6 `owns` test
   runs against a derived pack whose `ga4` account is `access: api`, `gsm:gtm-other-company-ga4`.
